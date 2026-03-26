"""
Runtime preparation for exporter-side SSH access.

This service reads per-exporter SSH bundles from a configured directory and
materializes the SSH assets needed by labgrid's proxy SSH path:

- a managed SSH config snippet included from ~/.ssh/config
- a managed known_hosts file
- copied private keys with strict permissions
- a wrapper ssh binary for password-authenticated exporters
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

logger = logging.getLogger(__name__)

MANAGED_CONFIG_INCLUDE = "Include ~/.ssh/labgrid-dashboard/config"
MANAGED_DIR_NAME = "labgrid-dashboard"
DEFAULT_PRIVATE_KEY_CANDIDATES = ("id_ed25519", "id_rsa")
AUTH_FILE_ENV = "LABGRID_DASHBOARD_EXPORTER_SSH_AUTH_FILE"
REAL_SSH_ENV = "LABGRID_DASHBOARD_REAL_SSH"
DEFAULT_SSH_WRAPPER_INSTALL_PATH = "/usr/local/bin/ssh"


class ExporterSSHAuthConfig(BaseModel):
    """SSH authentication settings for a single exporter bundle."""

    method: Optional[Literal["private_key", "password"]] = Field(
        default=None,
        description="Authentication method for exporter SSH access.",
    )
    private_key_path: Optional[str] = Field(
        default=None,
        description="Bundle-relative private key path for key-based auth.",
    )
    password: Optional[str] = Field(
        default=None,
        description="Inline password for password-based auth.",
    )
    password_env: Optional[str] = Field(
        default=None,
        description="Environment variable containing the SSH password.",
    )

    @model_validator(mode="after")
    def _normalize_method(self) -> "ExporterSSHAuthConfig":
        if self.method is None:
            if self.private_key_path:
                self.method = "private_key"
            elif self.password is not None or self.password_env:
                self.method = "password"
            else:
                self.method = "private_key"

        if self.method == "password" and self.password is None and not self.password_env:
            raise ValueError(
                "Password auth requires either 'password' or 'password_env'"
            )

        return self


class ExporterSSHConnectionConfig(BaseModel):
    """SSH connection settings for a single exporter bundle."""

    user: Optional[str] = Field(
        default=None,
        description="Static SSH username for exporter access.",
    )
    user_env: Optional[str] = Field(
        default=None,
        description="Environment variable containing the SSH username.",
    )
    auth: ExporterSSHAuthConfig = Field(default_factory=ExporterSSHAuthConfig)

    def resolve_user(self) -> str:
        """Resolve the SSH username from inline value or environment."""
        if self.user:
            return self.user

        if self.user_env:
            value = os.environ.get(self.user_env)
            if value:
                return value

        return "root"


class ExporterSSHBundleConfig(BaseModel):
    """Declarative SSH access bundle for a single exporter."""

    alias: str = Field(..., description="Exporter alias used by labgrid proxying.")
    host: str = Field(..., description="DNS name or IP address of the exporter host.")
    port: int = Field(default=22, ge=1, le=65535)
    ssh: ExporterSSHConnectionConfig = Field(
        default_factory=ExporterSSHConnectionConfig
    )
    known_hosts: List[str] = Field(
        default_factory=list,
        description="One or more complete known_hosts lines for this exporter.",
    )

    @field_validator("known_hosts", mode="before")
    @classmethod
    def _normalize_known_hosts(cls, value) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        return [str(entry).strip() for entry in value if str(entry).strip()]

    @model_validator(mode="after")
    def _validate_known_hosts(self) -> "ExporterSSHBundleConfig":
        if not self.known_hosts:
            raise ValueError("At least one known_hosts entry is required")
        return self


@dataclass
class PreparedExporterSSHBundle:
    """Resolved exporter SSH bundle ready for runtime materialization."""

    alias: str
    host: str
    port: int
    user: str
    auth_method: Literal["private_key", "password"]
    known_hosts: List[str]
    private_key_source: Optional[Path] = None
    password: Optional[str] = None
    password_env: Optional[str] = None


class ExporterSSHRuntimeService:
    """Generate managed SSH runtime assets for exporter proxy access."""

    def __init__(
        self,
        bundles_dir: str,
        managed_dir: Optional[str] = None,
        wrapper_install_path: Optional[str] = DEFAULT_SSH_WRAPPER_INSTALL_PATH,
    ) -> None:
        self._bundles_dir = Path(bundles_dir)
        self._managed_dir_override = Path(managed_dir).expanduser() if managed_dir else None
        self._wrapper_install_path = (
            Path(wrapper_install_path).expanduser() if wrapper_install_path else None
        )
        self._prepared_bundles: Dict[str, PreparedExporterSSHBundle] = {}

    @property
    def prepared_bundles(self) -> Dict[str, PreparedExporterSSHBundle]:
        """Return the resolved exporter bundles keyed by alias."""
        return dict(self._prepared_bundles)

    def setup(self) -> None:
        """Load bundles and generate SSH runtime assets if configured."""
        if not self._bundles_dir.exists():
            logger.info(
                "Exporter SSH bundle directory '%s' does not exist; skipping setup",
                self._bundles_dir,
            )
            return

        if not self._bundles_dir.is_dir():
            logger.warning(
                "Exporter SSH bundle path '%s' is not a directory; skipping setup",
                self._bundles_dir,
            )
            return

        bundle_dirs = sorted(path for path in self._bundles_dir.iterdir() if path.is_dir())
        if not bundle_dirs:
            logger.info(
                "No exporter SSH bundles found in '%s'; skipping setup",
                self._bundles_dir,
            )
            return

        prepared: Dict[str, PreparedExporterSSHBundle] = {}
        for bundle_dir in bundle_dirs:
            try:
                bundle = self._load_bundle(bundle_dir)
            except Exception as exc:
                logger.warning(
                    "Skipping exporter SSH bundle '%s': %s",
                    bundle_dir.name,
                    exc,
                )
                continue

            if bundle.alias in prepared:
                logger.warning(
                    "Skipping duplicate exporter SSH bundle alias '%s'",
                    bundle.alias,
                )
                continue

            prepared[bundle.alias] = bundle

        if not prepared:
            logger.info("No valid exporter SSH bundles were loaded")
            return

        self._write_managed_assets(prepared)
        self._prepared_bundles = prepared
        logger.info(
            "Prepared exporter SSH runtime for %d exporter bundle(s)",
            len(prepared),
        )

    def _load_bundle(self, bundle_dir: Path) -> PreparedExporterSSHBundle:
        bundle_file = bundle_dir / "exporter.yaml"
        if not bundle_file.is_file():
            raise FileNotFoundError(f"missing {bundle_file.name}")

        data = yaml.safe_load(bundle_file.read_text(encoding="utf-8")) or {}
        try:
            bundle = ExporterSSHBundleConfig.model_validate(data)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        auth = bundle.ssh.auth
        key_source: Optional[Path] = None

        if auth.method == "private_key":
            private_key_path = auth.private_key_path
            if not private_key_path:
                private_key_path = self._infer_private_key_path(bundle_dir)

            if not private_key_path:
                raise ValueError(
                    "private_key auth requires 'private_key_path' or a default key file"
                )

            key_source = (bundle_dir / private_key_path).resolve()
            if not key_source.is_file():
                raise FileNotFoundError(
                    f"private key '{private_key_path}' not found in bundle"
                )

        return PreparedExporterSSHBundle(
            alias=bundle.alias,
            host=bundle.host,
            port=bundle.port,
            user=bundle.ssh.resolve_user(),
            auth_method=auth.method or "private_key",
            known_hosts=bundle.known_hosts,
            private_key_source=key_source,
            password=auth.password,
            password_env=auth.password_env,
        )

    def _infer_private_key_path(self, bundle_dir: Path) -> Optional[str]:
        for candidate in DEFAULT_PRIVATE_KEY_CANDIDATES:
            candidate_path = bundle_dir / candidate
            if candidate_path.is_file():
                return candidate
        return None

    def _write_managed_assets(
        self,
        bundles: Dict[str, PreparedExporterSSHBundle],
    ) -> None:
        home_ssh_dir = Path.home() / ".ssh"
        managed_dir = self._managed_dir_override or home_ssh_dir / MANAGED_DIR_NAME
        keys_dir = managed_dir / "keys"
        bin_dir = managed_dir / "bin"
        auth_file = managed_dir / "auth.json"
        managed_config = managed_dir / "config"
        managed_known_hosts = managed_dir / "known_hosts"
        real_ssh = self._resolve_real_ssh()

        home_ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.rmtree(managed_dir, ignore_errors=True)
        keys_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        bin_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

        config_lines = ["# Managed by Labgrid Dashboard", ""]
        known_hosts_lines: List[str] = []
        auth_metadata: Dict[str, Dict[str, str]] = {}

        for alias, bundle in sorted(bundles.items()):
            key_target: Optional[Path] = None
            if bundle.private_key_source is not None:
                key_target = keys_dir / alias
                shutil.copyfile(bundle.private_key_source, key_target)
                key_target.chmod(0o600)

            known_hosts_lines.extend(bundle.known_hosts)

            config_lines.extend(self._render_host_block(bundle, key_target))
            config_lines.append("")

            auth_entry: Dict[str, str] = {"auth_method": bundle.auth_method}
            if bundle.password is not None:
                auth_entry["password"] = bundle.password
            if bundle.password_env:
                auth_entry["password_env"] = bundle.password_env
            auth_metadata[alias] = auth_entry

        managed_config.write_text("\n".join(config_lines).rstrip() + "\n", encoding="utf-8")
        managed_config.chmod(0o644)
        managed_known_hosts.write_text(
            "\n".join(dict.fromkeys(known_hosts_lines)).rstrip() + "\n",
            encoding="utf-8",
        )
        managed_known_hosts.chmod(0o644)
        auth_file.write_text(
            json.dumps(auth_metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        auth_file.chmod(0o600)

        wrapper_path = bin_dir / "ssh"
        wrapper_path.write_text(_build_ssh_wrapper_script(), encoding="utf-8")
        wrapper_path.chmod(0o755)
        self._install_wrapper(wrapper_path)

        self._ensure_main_config_includes_managed_config(home_ssh_dir / "config")

        os.environ[AUTH_FILE_ENV] = str(auth_file)
        os.environ[REAL_SSH_ENV] = real_ssh
        os.environ["PATH"] = self._prepend_path(str(bin_dir), os.environ.get("PATH", ""))

    def _render_host_block(
        self,
        bundle: PreparedExporterSSHBundle,
        key_target: Optional[Path],
    ) -> List[str]:
        lines = [
            f"Host {bundle.alias}",
            f"  HostName {bundle.host}",
            f"  Port {bundle.port}",
            f"  User {bundle.user}",
            f"  HostKeyAlias {bundle.alias}",
            "  StrictHostKeyChecking yes",
            f"  UserKnownHostsFile {self._managed_known_hosts_path()}",
        ]

        if bundle.auth_method == "private_key" and key_target is not None:
            lines.extend(
                [
                    f"  IdentityFile {key_target}",
                    "  IdentitiesOnly yes",
                    "  PreferredAuthentications publickey",
                    "  PasswordAuthentication no",
                ]
            )
        else:
            lines.extend(
                [
                    "  PubkeyAuthentication no",
                    "  PreferredAuthentications password,keyboard-interactive",
                    "  PasswordAuthentication yes",
                ]
            )

        return lines

    def _managed_known_hosts_path(self) -> Path:
        managed_dir = self._managed_dir_override or (Path.home() / ".ssh" / MANAGED_DIR_NAME)
        return managed_dir / "known_hosts"

    def _ensure_main_config_includes_managed_config(self, config_path: Path) -> None:
        include_line = MANAGED_CONFIG_INCLUDE
        if config_path.exists():
            content = config_path.read_text(encoding="utf-8")
            if include_line in content:
                return
            suffix = "" if content.endswith("\n") else "\n"
            config_path.write_text(
                f"{content}{suffix}{include_line}\n",
                encoding="utf-8",
            )
        else:
            config_path.write_text(f"{include_line}\n", encoding="utf-8")

        config_path.chmod(0o600)

    def _prepend_path(self, entry: str, existing_path: str) -> str:
        if not existing_path:
            return entry

        parts = existing_path.split(":")
        if entry in parts:
            return existing_path
        return f"{entry}:{existing_path}"

    def _resolve_real_ssh(self) -> str:
        preferred_real_ssh = Path("/usr/bin/ssh")
        if preferred_real_ssh.is_file():
            return str(preferred_real_ssh)

        ssh_path = shutil.which("ssh")
        if ssh_path:
            if self._wrapper_install_path and Path(ssh_path) == self._wrapper_install_path:
                fallback = shutil.which("ssh", path="/usr/bin:/bin:/usr/sbin:/sbin")
                if fallback:
                    return fallback
            return ssh_path

        return str(preferred_real_ssh)

    def _install_wrapper(self, wrapper_path: Path) -> None:
        if self._wrapper_install_path is None:
            return

        self._wrapper_install_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(wrapper_path, self._wrapper_install_path)
        self._wrapper_install_path.chmod(0o755)


def _build_ssh_wrapper_script() -> str:
    return f"""#!{sys.executable}
import json
import os
import shutil
import sys

OPTIONS_WITH_ARGUMENT = {{
    "-B", "-b", "-c", "-D", "-E", "-e", "-F", "-I", "-i", "-J", "-L",
    "-l", "-m", "-O", "-o", "-p", "-Q", "-R", "-S", "-W", "-w",
}}
AUTH_FILE_ENV = "{AUTH_FILE_ENV}"
REAL_SSH_ENV = "{REAL_SSH_ENV}"


def extract_host(arguments):
    index = 0
    end_of_options = False
    while index < len(arguments):
        arg = arguments[index]
        if end_of_options:
            return arg

        if arg == "--":
            end_of_options = True
            index += 1
            continue

        if not arg.startswith("-") or arg == "-":
            return arg

        if arg in OPTIONS_WITH_ARGUMENT:
            index += 2
            continue

        option_prefix = arg[:2]
        if option_prefix in OPTIONS_WITH_ARGUMENT and len(arg) > 2:
            index += 1
            continue

        index += 1

    return None


def normalize_host(host):
    if host is None:
        return None
    if "@" in host:
        host = host.split("@", 1)[1]
    return host


def rewrite_password_args(arguments):
    rewritten = []
    index = 0
    while index < len(arguments):
        arg = arguments[index]
        if arg == "-o" and index + 1 < len(arguments):
            option = arguments[index + 1]
            lowered = option.lower()
            if lowered.startswith("passwordauthentication="):
                index += 2
                continue
            if lowered.startswith("pubkeyauthentication="):
                index += 2
                continue
            if lowered.startswith("preferredauthentications="):
                index += 2
                continue
            rewritten.extend([arg, option])
            index += 2
            continue

        rewritten.append(arg)
        index += 1

    rewritten.extend([
        "-o", "PasswordAuthentication=yes",
        "-o", "PubkeyAuthentication=no",
        "-o", "PreferredAuthentications=password,keyboard-interactive",
    ])
    return rewritten


def main():
    auth_file = os.environ.get(AUTH_FILE_ENV)
    if not auth_file:
        os.execv(os.environ.get(REAL_SSH_ENV, "/usr/bin/ssh"), [os.environ.get(REAL_SSH_ENV, "/usr/bin/ssh"), *sys.argv[1:]])

    try:
        with open(auth_file, "r", encoding="utf-8") as handle:
            metadata = json.load(handle)
    except Exception:
        metadata = {{}}

    host = normalize_host(extract_host(sys.argv[1:]))
    entry = metadata.get(host or "")
    real_ssh = os.environ.get(REAL_SSH_ENV, "/usr/bin/ssh")

    if not entry or entry.get("auth_method") != "password":
        os.execv(real_ssh, [real_ssh, *sys.argv[1:]])

    password = entry.get("password")
    password_env = entry.get("password_env")
    if password is None and password_env:
        password = os.environ.get(password_env)

    if not password:
        sys.stderr.write(
            f"Exporter SSH password is not configured for '{{host}}'\\n"
        )
        raise SystemExit(255)

    sshpass = shutil.which("sshpass")
    if sshpass is None:
        sys.stderr.write("sshpass is required for exporter password authentication\\n")
        raise SystemExit(255)

    rewritten_args = rewrite_password_args(sys.argv[1:])
    os.execv(sshpass, [sshpass, "-p", password, real_ssh, *rewritten_args])


if __name__ == "__main__":
    main()
"""
