"""
gRPC client for Labgrid Coordinator communication.

This service handles the connection to the Labgrid Coordinator using gRPC protocol
(labgrid 24.0+). It provides methods to query places/targets, subscribe
to real-time updates, and execute commands on targets.

Note: Labgrid switched from WAMP to gRPC in version 24.0.
"""

import asyncio
import logging
import socket
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.models.target import CommandOutput, Resource, Target

logger = logging.getLogger(__name__)

# Constants for serial communication
COMMAND_TIMEOUT = 30  # seconds
READ_BUFFER_SIZE = 4096
COMMAND_DELAY = 0.1  # seconds to wait after sending command


class LabgridConnectionError(Exception):
    """Raised when connection to Labgrid Coordinator fails."""

    pass


class LabgridClient:
    """Async gRPC client for Labgrid Coordinator communication (labgrid 24.0+)."""

    def __init__(
        self,
        url: str = "localhost:20408",  # gRPC address (host:port, no protocol prefix)
        realm: str = "realm1",  # Kept for compatibility, not used in gRPC
        timeout: int = 30,
    ):
        """Initialize the Labgrid client.

        Args:
            url: gRPC address of the Labgrid Coordinator (host:port format).
            realm: Not used in gRPC mode, kept for API compatibility.
            timeout: Connection timeout in seconds.
        """
        # Clean URL: remove ws:// prefix if present (migration from WAMP config)
        self._url = url.replace("ws://", "").replace("/ws", "").rstrip("/")
        self._realm = realm
        self._timeout = timeout
        self._connected = False
        self._session = None  # labgrid ClientSession
        self._subscriptions: List[Any] = []
        self._resources_cache: Dict[str, Dict[str, Any]] = {}
        self._places_cache: Dict[str, Dict[str, Any]] = {}
        # Cache of all known exporters (persists offline exporters)
        self._known_exporters_cache: Dict[str, Dict[str, Any]] = {}

    @property
    def connected(self) -> bool:
        """Check if the client is connected to the coordinator."""
        return self._connected

    async def connect(self) -> bool:
        """Connect to the Labgrid Coordinator using labgrid's ClientSession.

        Returns:
            True if connection was successful.

        Raises:
            LabgridConnectionError: If connection fails.
        """
        try:
            logger.info(f"Connecting to Labgrid Coordinator at {self._url}...")

            # Try to establish connection using labgrid's ClientSession
            try:
                from labgrid.remote.client import ClientSession

                logger.info("labgrid ClientSession imported successfully")

                # Get the current event loop
                loop = asyncio.get_event_loop()

                # Create ClientSession with address and loop
                self._session = ClientSession(self._url, loop)

                # Start the session (connects to coordinator)
                await self._session.start()
                logger.info("ClientSession started successfully")

                # Wait for initial sync with coordinator
                await asyncio.sleep(1)

                # Refresh our cache from the session
                await self._refresh_cache()

                self._connected = True
                logger.info("Successfully connected to Labgrid Coordinator")
                logger.info(
                    f"Found {len(self._resources_cache)} resources, "
                    f"{len(self._places_cache)} places"
                )
                return True

            except ImportError as e:
                logger.error(f"Import error (labgrid not available): {e}")
                raise LabgridConnectionError(
                    f"labgrid library not available: {e}"
                ) from e
            except asyncio.TimeoutError as e:
                logger.error(f"Connection timeout after {self._timeout}s")
                raise LabgridConnectionError(
                    f"Connection timeout after {self._timeout}s"
                ) from e
            except Exception as e:
                logger.error(f"Exception during connection: {type(e).__name__}: {e}")
                import traceback

                logger.error(f"Traceback: {traceback.format_exc()}")
                raise LabgridConnectionError(
                    f"Failed to connect to coordinator: {e}"
                ) from e

        except LabgridConnectionError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            raise LabgridConnectionError(
                f"Unexpected error during connection: {e}"
            ) from e

    async def _refresh_cache(self) -> None:
        """Refresh the local cache of resources and places from the session.

        This method preserves knowledge of previously seen exporters. When an
        exporter goes offline, it remains in _known_exporters_cache with
        avail=False instead of being removed entirely.
        """
        if not self._session:
            return

        try:
            # Get resources from session (exporter -> group -> resource_type -> ResourceEntry)
            current_resources: Dict[str, Dict[str, Any]] = {}
            current_exporter_names: set = set()

            for exporter_name, exporter_data in self._session.resources.items():
                current_exporter_names.add(exporter_name)
                for group_name, group_resources in exporter_data.items():
                    for res_type, res_entry in group_resources.items():
                        # ResourceEntry attributes need careful handling
                        # - properties may raise KeyError
                        params = {}
                        cls_name = res_type
                        acquired = None
                        avail = True
                        params_available = True  # Track if params could be loaded

                        try:
                            # Try to get params - labgrid property may raise KeyError
                            # when offline
                            params = dict(res_entry.params) if res_entry.params else {}
                        except (KeyError, AttributeError):
                            # Fallback to data dict
                            if hasattr(res_entry, "data") and isinstance(
                                res_entry.data, dict
                            ):
                                params = res_entry.data.get("params", {})
                            # Mark that params couldn't be loaded from property
                            params_available = False

                        try:
                            # Get cls attribute
                            cls_name = res_entry.cls
                        except (KeyError, AttributeError):
                            if hasattr(res_entry, "data") and isinstance(
                                res_entry.data, dict
                            ):
                                cls_name = res_entry.data.get("cls", res_type)

                        try:
                            # Get acquired attribute
                            acquired = res_entry.acquired
                        except (KeyError, AttributeError):
                            if hasattr(res_entry, "data") and isinstance(
                                res_entry.data, dict
                            ):
                                acquired = res_entry.data.get("acquired")

                        try:
                            # Get avail attribute - key indicator of online/offline status
                            avail = res_entry.avail
                        except (KeyError, AttributeError):
                            if hasattr(res_entry, "data") and isinstance(
                                res_entry.data, dict
                            ):
                                avail = res_entry.data.get("avail", True)
                            else:
                                avail = True  # Default, will be overridden below

                        # If params couldn't be loaded, the exporter is likely offline
                        # Labgrid returns the exporter but with empty/missing data
                        if not params_available or not params:
                            avail = False
                            logger.debug(
                                f"Exporter '{exporter_name}' marked offline "
                                "(no params available)"
                            )

                        current_resources[exporter_name] = {
                            res_type: {
                                "cls": cls_name,
                                "params": params,
                                "acquired": acquired,
                                "avail": avail,
                            }
                        }

            # Update known exporters cache with current online exporters
            for exporter_name, resources in current_resources.items():
                self._known_exporters_cache[exporter_name] = resources

            # Mark previously known exporters that are now offline
            for exporter_name in list(self._known_exporters_cache.keys()):
                if exporter_name not in current_exporter_names:
                    # Exporter is offline - mark all its resources as unavailable
                    for res_type in self._known_exporters_cache[exporter_name]:
                        self._known_exporters_cache[exporter_name][res_type][
                            "avail"
                        ] = False
                    logger.info(f"Exporter '{exporter_name}' is now offline")

            # _resources_cache now includes all known exporters (online + offline)
            self._resources_cache = dict(self._known_exporters_cache)

            # Get places from session (place_name -> Place object)
            self._places_cache = {}
            for place_name, place_obj in self._session.places.items():
                self._places_cache[place_name] = {
                    "name": place_name,
                    "acquired": getattr(place_obj, "acquired", None),
                    "comment": getattr(place_obj, "comment", ""),
                    "tags": dict(getattr(place_obj, "tags", {})),
                }

            online_count = len(current_exporter_names)
            offline_count = len(self._known_exporters_cache) - online_count
            logger.debug(
                f"Cache refreshed: {online_count} online, {offline_count} offline "
                f"exporters, {len(self._places_cache)} places"
            )

        except Exception as e:
            logger.error(f"Failed to refresh cache: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

    async def disconnect(self) -> None:
        """Disconnect from the Labgrid Coordinator."""
        if self._session:
            try:
                await self._session.close()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")

        self._session = None
        self._connected = False
        self._resources_cache = {}
        self._places_cache = {}
        self._known_exporters_cache = {}
        logger.info("Disconnected from Labgrid Coordinator")

    def _resolve_hostname_to_ip(self, hostname: str) -> Optional[str]:
        """Resolve a hostname to its IP address.

        Args:
            hostname: The hostname to resolve.

        Returns:
            The IP address as string, or None if resolution fails.
        """
        try:
            ip = socket.gethostbyname(hostname)
            return ip
        except socket.gaierror as e:
            logger.debug(f"Could not resolve hostname '{hostname}': {e}")
            return None

    async def get_places(self) -> List[Target]:
        """Get all places/targets from the coordinator.

        Returns:
            List of Target objects representing all places.
        """
        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return []

        try:
            # Refresh cache and return parsed places
            await self._refresh_cache()

            # Convert resources cache to targets
            # In labgrid, resources are organized by exporter name
            targets = []
            for exporter_name, exporter_resources in self._resources_cache.items():
                # Collect all resources for this exporter
                resources_list = []
                ip_address = None
                acquired_by = None
                is_available = True

                for res_type, res_data in exporter_resources.items():
                    params = res_data.get("params", {})

                    # Track acquired status
                    if res_data.get("acquired"):
                        acquired_by = res_data.get("acquired")

                    # Track availability
                    if not res_data.get("avail", True):
                        is_available = False

                    # Create Resource with correct field names (type and params)
                    resources_list.append(
                        Resource(
                            type=res_data.get("cls", res_type),
                            params=params,
                        )
                    )

                    # Extract exporter hostname from params.extra.proxy
                    # This is the hostname of the exporter machine
                    extra = params.get("extra", {})
                    exporter_hostname = extra.get("proxy") or exporter_name

                    # Only resolve IP for online exporters to avoid DNS timeouts
                    # The hostname resolution can block if the host is unreachable
                    if (
                        exporter_hostname
                        and not ip_address
                        and res_data.get("avail", True)
                    ):
                        ip_address = self._resolve_hostname_to_ip(exporter_hostname)

                # Determine status based on availability and acquisition
                if not is_available:
                    status = "offline"
                elif acquired_by:
                    status = "acquired"
                else:
                    status = "available"

                target = Target(
                    name=exporter_name,
                    status=status,
                    acquired_by=acquired_by,
                    ip_address=ip_address,
                    resources=resources_list,
                )
                targets.append(target)

            return targets
        except Exception as e:
            logger.error(f"Failed to get places: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def get_place_info(self, name: str) -> Optional[Target]:
        """Get detailed information about a specific place.

        Args:
            name: The place name to query.

        Returns:
            Target object if found, None otherwise.
        """
        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return None

        try:
            # Refresh cache first
            await self._refresh_cache()

            # Look for the exporter matching the name
            if name in self._resources_cache:
                exporter_resources = self._resources_cache[name]
                resources = []
                avail = True
                for res_type, res_data in exporter_resources.items():
                    resources.append(
                        Resource(
                            name=res_type,
                            type=res_data.get("cls", res_type),
                            info=res_data.get("params", {}),
                        )
                    )
                    if not res_data.get("avail", False):
                        avail = False

                return Target(
                    name=name,
                    status="available" if avail else "offline",
                    acquired_by=None,
                    resources=resources,
                    tags={},
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get place info for {name}: {e}")
            return None

    async def subscribe_updates(
        self, callback: Callable[[str, Dict[str, Any]], None]
    ) -> bool:
        """Subscribe to real-time place updates.

        Note: gRPC streaming not yet implemented. Uses polling instead.

        Args:
            callback: Function to call when a place is updated.
                     Receives (place_name, place_data) as arguments.

        Returns:
            True if subscription was successful, False otherwise.
        """
        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return False

        # TODO: Implement gRPC streaming subscription
        # For now, we use polling via _refresh_cache()
        logger.info(
            "Subscriptions use polling mode (gRPC streaming not yet implemented)"
        )
        return True

    async def execute_command(self, place_name: str, command: str) -> Tuple[str, int]:
        """Execute a command on a target via direct serial connection.

        This method finds the NetworkSerialPort resource for the target
        and executes the command via the serial console.

        Args:
            place_name: The name of the place/target to execute on.
            command: The shell command to execute.

        Returns:
            Tuple of (output, exit_code). exit_code is 0 for success.
        """
        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return ("Error: Not connected to coordinator", 1)

        try:
            # Refresh cache to get latest resources
            await self._refresh_cache()

            # Get resources for this place
            resources = self._get_place_resources_from_cache(place_name)
            if not resources:
                return (f"Error: No resources found for '{place_name}'", 1)

            # Find NetworkSerialPort resource
            serial_resource = None
            for res in resources:
                if res.get("cls") == "NetworkSerialPort":
                    serial_resource = res
                    break

            if not serial_resource:
                return (f"Error: No NetworkSerialPort resource for '{place_name}'", 1)

            # Execute command via serial connection
            host = serial_resource.get("params", {}).get("host")
            port = serial_resource.get("params", {}).get("port", 5000)

            if not host:
                return ("Error: Serial resource has no host configured", 1)

            output = await self._execute_via_serial(host, port, command)
            return (output, 0)

        except Exception as e:
            logger.error(f"Failed to execute command on {place_name}: {e}")
            return (f"Error: {str(e)}", 1)

    def _get_place_resources_from_cache(
        self, place_name: str
    ) -> List[Dict[str, Any]]:
        """Get resources for a place from the local cache.

        Args:
            place_name: The place name.

        Returns:
            List of resource dictionaries.
        """
        place_resources = []

        # Look for exact match first
        if place_name in self._resources_cache:
            for res_name, res_data in self._resources_cache[place_name].items():
                place_resources.append(res_data)
            return place_resources

        # Search for partial matches
        for group_name, group_resources in self._resources_cache.items():
            if place_name in group_name:
                for res_name, res_data in group_resources.items():
                    place_resources.append(res_data)

        return place_resources

    def _parse_serial_output(self, raw_output: str, command: str) -> str:
        """Parse serial output to extract only the command result.

        Serial output typically contains:
        1. Echo of the command we sent
        2. The actual output
        3. Shell prompt(s)

        Example raw: "uptime -p\\r\\ndut-1:/# uptime -p\\r\\nup 1 hour, 45 minutes\\r\\ndut-1:/# "
        Desired: "up 1 hour, 45 minutes"

        Args:
            raw_output: Raw output from serial connection.
            command: The command that was executed.

        Returns:
            Cleaned output containing only the command result.
        """
        import re

        if not raw_output:
            return ""

        # Normalize line endings
        output = raw_output.replace("\r\n", "\n").replace("\r", "\n")

        # Split into lines
        lines = output.split("\n")

        # Filter out:
        # 1. Lines that are just the command (echo)
        # 2. Lines that look like shell prompts (ending with # or $ or >)
        # 3. Empty lines at start/end

        # Common prompt patterns: "user@host:path# ", "root@dut:/# ", "dut-1:/# ", "$ ", "# "
        prompt_pattern = re.compile(r"^.*[@:].*[#$>]\s*$|^[#$>]\s*$")

        filtered_lines = []
        for line in lines:
            line_stripped = line.strip()

            # Skip empty lines
            if not line_stripped:
                continue

            # Skip if line is just the command we sent
            if line_stripped == command or line_stripped == command.strip():
                continue

            # Skip if line looks like a prompt
            if prompt_pattern.match(line_stripped):
                continue

            # Skip if line contains the command followed by prompt-like characters
            # e.g., "uptime -p dut-1:/# uptime -p" should be filtered
            if command in line_stripped and (
                "#" in line_stripped or "$" in line_stripped
            ):
                continue

            filtered_lines.append(line_stripped)

        return "\n".join(filtered_lines).strip()

    async def _execute_via_serial(self, host: str, port: int, command: str) -> str:
        """Execute a command via serial-over-TCP connection.

        Args:
            host: TCP host of the serial server.
            port: TCP port of the serial server.
            command: Command to execute.

        Returns:
            Command output as string (cleaned, without prompts/echo).
        """
        loop = asyncio.get_event_loop()

        def _sync_execute():
            """Synchronous execution in thread pool."""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(COMMAND_TIMEOUT)
                sock.connect((host, port))

                # Send command with newline
                sock.sendall(f"{command}\n".encode("utf-8"))

                # Wait for response
                import time

                time.sleep(COMMAND_DELAY)

                # Read output
                output_parts = []
                sock.setblocking(False)
                try:
                    while True:
                        try:
                            data = sock.recv(READ_BUFFER_SIZE)
                            if not data:
                                break
                            output_parts.append(data.decode("utf-8", errors="replace"))
                        except BlockingIOError:
                            break
                        except socket.timeout:
                            break
                except Exception:
                    pass

                sock.close()
                return "".join(output_parts)

            except socket.timeout:
                return f"Error: Connection timeout to {host}:{port}"
            except ConnectionRefusedError:
                return f"Error: Connection refused to {host}:{port}"
            except Exception as e:
                return f"Error: {str(e)}"

        # Execute in thread pool to avoid blocking
        raw_output = await loop.run_in_executor(None, _sync_execute)

        # Parse the output to extract only the command result
        return self._parse_serial_output(raw_output, command)

    def _parse_places(self, places_data: Dict[str, Any]) -> List[Target]:
        """Parse places data from the coordinator into Target objects.

        Args:
            places_data: Raw places data from the coordinator.

        Returns:
            List of parsed Target objects.
        """
        targets = []
        for name, data in places_data.items():
            target = self._parse_place(name, data)
            if target:
                targets.append(target)
        return targets

    def _parse_place(self, name: str, data: Dict[str, Any]) -> Optional[Target]:
        """Parse a single place into a Target object.

        Args:
            name: The place name.
            data: Raw place data from the coordinator.

        Returns:
            Parsed Target object, or None if parsing fails.
        """
        try:
            # Determine status based on acquired state
            acquired = data.get("acquired")
            if acquired:
                status = "acquired"
            else:
                # Check if place has any resources (indicates it's online)
                status = "available"

            # Parse resources
            resources = []
            for res_type in data.get("acquired_resources", []):
                resources.append(Resource(type=res_type, params={}))

            # Extract additional info from tags
            tags = data.get("tags", {})
            ip_address = tags.get("ip", None)
            web_url = tags.get("web_url", None)

            return Target(
                name=name,
                status=status,
                acquired_by=acquired,
                ip_address=ip_address,
                web_url=web_url,
                resources=resources,
                last_command_outputs=[],
            )
        except Exception as e:
            logger.error(f"Failed to parse place {name}: {e}")
            return None
