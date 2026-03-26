"""
Preset-aware command execution service.
"""

import asyncio
import contextlib
from dataclasses import dataclass
import logging
from typing import Optional, Tuple

from app.config import get_settings
from app.models.target import (
    CommandExecutionConfig,
    ExecutionTransport,
    SerialCommandExecutionConfig,
    Target,
)
from app.services.command_service import CommandService
from app.services.labgrid_client import (
    LabgridClient,
    LabgridConnectionError,
    TargetAcquiredByOtherError,
)
from app.services.preset_service import PresetService

logger = logging.getLogger(__name__)


@dataclass
class CommandExecutionResult:
    """Command execution result with the transport actually used."""

    output: str
    exit_code: int
    execution_transport: Optional[ExecutionTransport] = None

    def __iter__(self):
        yield self.output
        yield self.exit_code


class TransportExecutionError(RuntimeError):
    """Raised when a configured command transport fails before command execution."""

    pass


class CommandExecutionService:
    """Resolve target command capabilities and execute commands."""

    def __init__(
        self,
        labgrid_client: LabgridClient,
        command_service: CommandService,
        preset_service: PresetService,
    ) -> None:
        self._labgrid_client = labgrid_client
        self._command_service = command_service
        self._preset_service = preset_service
        self._last_command_outputs: dict[str, list] = {}

    def enrich_targets(self, targets: list[Target]) -> list[Target]:
        """Annotate a list of targets with command capability metadata."""
        return [self.enrich_target(target) for target in targets]

    def enrich_target(self, target: Target) -> Target:
        """Annotate a target with command capability metadata."""
        capable, transport, error = self.get_target_command_state(
            target.name,
            target_status=target.status,
        )
        target.command_capable = capable
        target.command_transport = transport
        target.command_capability_error = error
        target.last_command_outputs = self.get_outputs_for_target(target.name)
        return target

    def record_output(self, target_name: str, output, *, limit: int = 10) -> None:
        """Store the latest command outputs for a target in memory."""
        outputs = [output]
        outputs.extend(self._last_command_outputs.get(target_name, []))
        self._last_command_outputs[target_name] = outputs[:limit]

    def get_outputs_for_target(self, target_name: str) -> list:
        """Return the cached manual command outputs for a target."""
        return list(self._last_command_outputs.get(target_name, []))

    def get_target_command_state(
        self,
        target_name: str,
        *,
        target_status: Optional[str] = None,
    ) -> Tuple[bool, Optional[ExecutionTransport], Optional[str]]:
        """Resolve whether a target currently supports command execution."""
        if target_status == "offline":
            return (False, None, "Commands unavailable - target is offline")

        session = getattr(self._labgrid_client, "_session", None)
        if not self._labgrid_client.connected or session is None:
            return (
                False,
                None,
                "Commands unavailable - coordinator is disconnected",
            )

        resource_entries = self._labgrid_client.get_place_resource_entries(target_name)
        if not resource_entries:
            return (
                False,
                None,
                f"Commands unavailable - target '{target_name}' has no matched resources",
            )

        preset_id = self._get_target_preset_id(target_name)
        execution_config = self._command_service.get_execution_config_for_preset(
            preset_id
        )
        transport = self._resolve_available_transport(resource_entries, execution_config)
        if transport is None:
            return (
                False,
                None,
                self._build_capability_error(target_name, execution_config),
            )

        return (True, transport, None)

    async def execute_command(
        self,
        target_name: str,
        command: str,
    ) -> CommandExecutionResult:
        """Execute a command using the preset's configured transport order."""
        if not self._labgrid_client.connected or not getattr(
            self._labgrid_client, "_session", None
        ):
            logger.warning("Not connected to coordinator")
            return CommandExecutionResult(
                "Error: Not connected to coordinator",
                1,
            )

        target_lock = self._labgrid_client._command_locks.setdefault(
            target_name,
            asyncio.Lock(),
        )

        try:
            async with target_lock:
                acquired_here = await self._labgrid_client.acquire_target(target_name)

                try:
                    return await self._execute_with_transport_order(target_name, command)
                finally:
                    if acquired_here:
                        released = await self._labgrid_client.release_target_with_retry(
                            target_name
                        )
                        if not released:
                            logger.error(
                                "Command succeeded but release failed for '%s'",
                                target_name,
                            )

        except TargetAcquiredByOtherError:
            raise
        except FileNotFoundError as exc:
            logger.error("labgrid-client not found: %s", exc)
            return CommandExecutionResult("Error: labgrid-client CLI not found", 1)
        except TimeoutError as exc:
            logger.error("Command timeout on %s: %s", target_name, exc)
            return CommandExecutionResult(f"Error: {exc}", 1)
        except RuntimeError as exc:
            logger.error("Command execution error on %s: %s", target_name, exc)
            return CommandExecutionResult(f"Error: {exc}", 1)
        except LabgridConnectionError:
            logger.exception("Coordinator connection lost during execution")
            return CommandExecutionResult("Error: Not connected to coordinator", 1)
        except Exception as exc:
            logger.exception("Failed to execute command on %s", target_name)
            return CommandExecutionResult(f"Error: {exc}", 1)

    async def _execute_with_transport_order(
        self,
        target_name: str,
        command: str,
    ) -> CommandExecutionResult:
        session = getattr(self._labgrid_client, "_session", None)
        if session is None:
            return CommandExecutionResult("Error: Not connected to coordinator", 1)

        place = self._get_place(target_name)
        if place is None:
            return CommandExecutionResult(
                f"Error: target '{target_name}' has no coordinator place",
                1,
            )

        preset_id = self._get_target_preset_id(target_name)
        execution_config = self._command_service.get_execution_config_for_preset(
            preset_id
        )
        last_transport_error: Optional[str] = None
        self._reset_target_proxy_connections(target_name)

        for transport in execution_config.transport_order:
            if transport == "serial":
                try:
                    result = await self._try_execute_via_serial(
                        place,
                        target_name,
                        command,
                        execution_config.serial,
                    )
                except TransportExecutionError as exc:
                    last_transport_error = self._normalize_transport_error(
                        exc,
                        fallback_message="serial transport failed",
                    )
                    self._reset_target_proxy_connections(target_name)
                    logger.warning(
                        "Serial transport failed on '%s', trying next transport: %s",
                        target_name,
                        last_transport_error,
                    )
                    continue

                if result is not None:
                    return result
                continue

            if transport == "ssh":
                try:
                    result = await self._try_execute_via_ssh(
                        place,
                        command,
                        execution_config.ssh,
                    )
                except TransportExecutionError as exc:
                    last_transport_error = self._normalize_transport_error(
                        exc,
                        fallback_message="ssh transport failed",
                    )
                    self._reset_target_proxy_connections(target_name)
                    logger.warning(
                        "SSH transport failed on '%s': %s",
                        target_name,
                        last_transport_error,
                    )
                    continue

                if result is not None:
                    return result
                continue

            logger.warning(
                "Unknown command execution transport '%s' for preset '%s'",
                transport,
                preset_id,
            )

        if last_transport_error:
            return CommandExecutionResult(f"Error: {last_transport_error}", 1)

        return CommandExecutionResult(
            f"Error: {self._build_capability_error(target_name, execution_config)}",
            1,
        )

    def _normalize_transport_error(
        self,
        error: Exception,
        *,
        fallback_message: str,
    ) -> str:
        message = str(error).strip()
        return message or fallback_message

    def _reset_target_proxy_connections(self, target_name: str) -> None:
        """Drop cached exporter SSH proxy connections for a target."""
        try:
            from labgrid.util.ssh import sshmanager
        except Exception:
            return

        aliases: set[str] = set()
        for _, _, res_data in self._labgrid_client.get_place_resource_entries(target_name):
            params = res_data.get("params") or {}
            extra = params.get("extra") or {}
            proxy = extra.get("proxy")
            if proxy:
                aliases.add(proxy)

        connections = getattr(sshmanager, "_connections", {})
        for alias in aliases:
            connection = connections.get(alias)
            if connection is None:
                continue
            with contextlib.suppress(Exception):
                connection.disconnect()
            with contextlib.suppress(Exception):
                sshmanager.remove_by_name(alias)

    async def _try_execute_via_serial(
        self,
        place,
        target_name: str,
        command: str,
        serial_config: SerialCommandExecutionConfig,
    ) -> Optional[CommandExecutionResult]:
        session = getattr(self._labgrid_client, "_session", None)
        if session is None:
            return None

        try:
            target = session._get_target(place)
            serial_resource = self._resolve_serial_resource(target, serial_config)
            if serial_resource is None:
                return None

            resource_name, resource_cls = serial_resource
            serial_driver = self._get_or_create_serial_driver(
                target,
                resource_name=resource_name,
                resource_cls=resource_cls,
            )
            if serial_driver is None:
                return None

            shell_driver = self._get_or_create_shell_driver(
                target,
                serial_driver_name=serial_driver.name,
                serial_config=serial_config,
            )
            if shell_driver is None:
                return None

            return await asyncio.to_thread(
                self._run_serial_command,
                target,
                shell_driver,
                command,
                serial_config,
            )
        except Exception as exc:
            raise TransportExecutionError(str(exc)) from exc

    def _run_serial_command(
        self,
        target,
        shell_driver,
        command: str,
        serial_config: SerialCommandExecutionConfig,
    ) -> CommandExecutionResult:
        """Run a command through the labgrid ShellDriver on a serial console."""
        try:
            target.activate(shell_driver)
            timeout = (
                serial_config.command_timeout_seconds
                or get_settings().labgrid_command_timeout
            )
            stdout_lines, _, exit_code = shell_driver.run(
                command,
                timeout=float(timeout),
            )
            output = "\n".join(stdout_lines).strip()
            return CommandExecutionResult(output, exit_code, "serial")
        finally:
            with contextlib.suppress(Exception):
                target.deactivate_all_drivers()

    def _get_target_preset_id(self, target_name: str) -> str:
        preset_id = self._preset_service.get_target_preset(target_name)
        if preset_id:
            return preset_id
        return self._command_service.get_default_preset_id()

    def _get_place(self, target_name: str):
        """Get a coordinator place by name from the current session."""
        session = getattr(self._labgrid_client, "_session", None)
        if session is None:
            return None

        try:
            return session.get_place(target_name)
        except Exception:
            return None

    def _resolve_available_transport(
        self,
        resource_entries,
        execution_config: CommandExecutionConfig,
    ) -> Optional[ExecutionTransport]:
        for transport in execution_config.transport_order:
            if transport == "serial":
                if self._has_cached_serial_resource(
                    resource_entries,
                    execution_config.serial,
                ):
                    return "serial"
            elif transport == "ssh":
                if self._has_cached_ssh_resource(
                    resource_entries,
                    execution_config.ssh,
                ):
                    return "ssh"
        return None

    def _build_capability_error(
        self,
        target_name: str,
        execution_config: CommandExecutionConfig,
    ) -> str:
        serial_config = execution_config.serial
        ssh_config = execution_config.ssh
        transport_order = execution_config.transport_order

        if "serial" in transport_order and serial_config.resource_name:
            serial_reason = (
                f"serial resource '{serial_config.resource_name}' is not available"
            )
        elif "serial" in transport_order:
            serial_reason = "no serial console is available"
        else:
            serial_reason = ""

        if "ssh" in transport_order and ssh_config.resource_name:
            ssh_reason = f"SSH resource '{ssh_config.resource_name}' is not available"
        elif "ssh" in transport_order:
            ssh_reason = "no SSH service is available"
        else:
            ssh_reason = ""

        reasons = [reason for reason in (serial_reason, ssh_reason) if reason]
        if reasons:
            return f"Commands unavailable - {' and '.join(reasons)} for '{target_name}'"
        return f"Commands unavailable - no supported transport is configured for '{target_name}'"

    def _resolve_serial_resource(
        self,
        target,
        serial_config: SerialCommandExecutionConfig,
    ) -> Optional[Tuple[str, str]]:
        """Find the configured or first available serial resource on a target."""
        configured_name = serial_config.resource_name
        allowed_classes = {"SerialPort", "NetworkSerialPort"}
        candidates: list[Tuple[str, str]] = []

        for resource in target.resources:
            resource_cls_name = type(resource).__name__
            if resource_cls_name not in allowed_classes:
                continue
            if not getattr(resource, "avail", True):
                continue

            candidates.append((resource.name, resource_cls_name))
            if configured_name and resource.name == configured_name:
                return (resource.name, resource_cls_name)

        if configured_name:
            return None
        if candidates:
            return candidates[0]
        return None

    def _has_cached_serial_resource(
        self,
        resource_entries,
        serial_config: SerialCommandExecutionConfig,
    ) -> bool:
        """Check the cached place resources for a usable serial console."""
        configured_name = serial_config.resource_name
        allowed_classes = {"SerialPort", "NetworkSerialPort"}

        for _, _, res_data in resource_entries:
            resource_name = res_data.get("name")
            resource_cls = res_data.get("cls") or res_data.get("resource_type")
            if resource_cls not in allowed_classes:
                continue
            if not res_data.get("avail", True):
                continue
            if configured_name and resource_name != configured_name:
                continue
            return True

        return False

    def _has_cached_ssh_resource(
        self,
        resource_entries,
        ssh_config,
    ) -> bool:
        """Check the cached place resources for a usable SSH service."""
        configured_name = ssh_config.resource_name

        for _, _, res_data in resource_entries:
            resource_name = res_data.get("name")
            resource_cls = res_data.get("cls") or res_data.get("resource_type")
            if resource_cls != "NetworkService":
                continue
            if configured_name and resource_name != configured_name:
                continue
            if res_data.get("avail", True):
                return True
        return False

    def _has_available_ssh_resource(self, place, ssh_config) -> bool:
        """Check whether a place exposes a usable SSH-capable resource."""
        session = getattr(self._labgrid_client, "_session", None)
        if session is None:
            return False

        try:
            resource_entries = session.get_target_resources(place)
        except Exception:
            return False

        configured_name = ssh_config.resource_name

        for (resource_name, resource_cls), resource_entry in resource_entries.items():
            resource_cls_name = (
                resource_cls
                if isinstance(resource_cls, str)
                else getattr(resource_cls, "__name__", str(resource_cls))
            )
            if resource_cls_name != "NetworkService":
                continue
            if configured_name and resource_name != configured_name:
                continue
            if getattr(resource_entry, "avail", True):
                return True

        return False

    async def _try_execute_via_ssh(
        self,
        place,
        command: str,
        ssh_config,
    ) -> Optional[CommandExecutionResult]:
        session = getattr(self._labgrid_client, "_session", None)
        if session is None:
            return None

        try:
            target = session._get_target(place)
            ssh_resource_name = self._resolve_ssh_resource_name(target, ssh_config)
            if ssh_resource_name is None:
                return None

            ssh_driver = self._get_or_create_ssh_driver(
                target,
                resource_name=ssh_resource_name,
                ssh_config=ssh_config,
            )
            if ssh_driver is None:
                return None

            return await asyncio.to_thread(
                self._run_ssh_command,
                target,
                ssh_driver,
                command,
                ssh_config,
            )
        except Exception as exc:
            raise TransportExecutionError(str(exc)) from exc

    def _resolve_ssh_resource_name(
        self,
        target,
        ssh_config,
    ) -> Optional[str]:
        configured_name = ssh_config.resource_name
        candidates: list[str] = []

        for resource in target.resources:
            if type(resource).__name__ != "NetworkService":
                continue
            if not getattr(resource, "avail", True):
                continue

            candidates.append(resource.name)
            if configured_name and resource.name == configured_name:
                return resource.name

        if configured_name:
            return None
        if candidates:
            return candidates[0]
        return None

    def _get_or_create_serial_driver(
        self,
        target,
        *,
        resource_name: str,
        resource_cls: str,
    ):
        """Get or bind a SerialDriver for a specific resource."""
        from labgrid.driver import SerialDriver

        try:
            resource = target.get_resource(
                resource_cls,
                name=resource_name,
                wait_avail=False,
            )
        except Exception as exc:
            logger.warning(
                "Failed to resolve serial resource '%s' (%s): %s",
                resource_name,
                resource_cls,
                exc,
            )
            return None

        try:
            return target.get_driver(
                SerialDriver,
                resource=resource,
                activate=False,
            )
        except Exception:
            pass

        driver_name = f"serial-{resource_name}"
        target.set_binding_map({"port": resource_name})
        return SerialDriver(target, driver_name)

    def _get_or_create_shell_driver(
        self,
        target,
        *,
        serial_driver_name: str,
        serial_config: SerialCommandExecutionConfig,
    ):
        """Get or bind a ShellDriver on top of a serial console."""
        from labgrid.driver import ShellDriver

        driver_name = f"shell-{serial_driver_name}"
        try:
            return target.get_driver(
                ShellDriver,
                name=driver_name,
                activate=False,
            )
        except Exception:
            pass

        target.set_binding_map({"console": serial_driver_name})
        shell_driver = ShellDriver(
            target,
            driver_name,
            prompt=serial_config.prompt,
            login_prompt=serial_config.login_prompt,
            username=serial_config.resolve_username(),
            password=serial_config.resolve_password(),
            login_timeout=serial_config.login_timeout_seconds,
            console_ready=serial_config.console_ready,
            await_login_timeout=serial_config.await_login_timeout_seconds,
            post_login_settle_time=serial_config.post_login_settle_time_seconds,
        )
        return shell_driver

    def _get_or_create_ssh_driver(
        self,
        target,
        *,
        resource_name: str,
        ssh_config,
    ):
        """Get or bind an SSHDriver for a specific resource."""
        from labgrid.driver import SSHDriver

        try:
            resource = target.get_resource(
                "NetworkService",
                name=resource_name,
                wait_avail=False,
            )
        except Exception as exc:
            logger.warning(
                "Failed to resolve SSH resource '%s': %s",
                resource_name,
                exc,
            )
            return None

        driver_name = f"ssh-{resource_name}"
        try:
            return target.get_driver(
                SSHDriver,
                name=driver_name,
                activate=False,
            )
        except Exception:
            pass

        target.set_binding_map({"networkservice": resource_name})

        kwargs = {}
        keyfile = ssh_config.resolve_keyfile()
        username = ssh_config.resolve_username()
        password = ssh_config.resolve_password()
        if keyfile:
            kwargs["keyfile"] = keyfile
        if username:
            kwargs["username"] = username
        if password is not None:
            kwargs["password"] = password

        return SSHDriver(target, driver_name, **kwargs)

    def _run_ssh_command(
        self,
        target,
        ssh_driver,
        command: str,
        ssh_config,
    ) -> CommandExecutionResult:
        """Run a command through the labgrid SSHDriver."""
        try:
            target.activate(ssh_driver)
            timeout = (
                ssh_config.command_timeout_seconds
                or get_settings().labgrid_command_timeout
            )
            stdout_lines, stderr_lines, exit_code = ssh_driver.run(
                command,
                timeout=float(timeout),
            )
            output_lines = list(stdout_lines)
            output_lines.extend(line for line in stderr_lines if line)
            output = "\n".join(output_lines).strip()
            return CommandExecutionResult(output, exit_code, "ssh")
        finally:
            with contextlib.suppress(Exception):
                target.deactivate_all_drivers()
