"""
Tests for exporter SSH runtime preparation.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app.services.exporter_ssh_runtime import (
    AUTH_FILE_ENV,
    REAL_SSH_ENV,
    ExporterSSHRuntimeService,
)


def _write_file(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def _write_executable(path: Path, content: str) -> None:
    _write_file(path, content, mode=0o755)


def test_exporter_ssh_runtime_generates_managed_assets(monkeypatch, tmp_path: Path):
    """Bundle setup should render config, known_hosts, keys, and wrapper metadata."""
    home = tmp_path / "home"
    bundles = tmp_path / "bundles"
    fake_bin = tmp_path / "fake-bin"
    monkeypatch.setenv("HOME", str(home))

    _write_file(
        bundles / "exporter-key" / "exporter.yaml",
        """
alias: exporter-key
host: 10.0.0.11
ssh:
  user: exporter
  auth:
    method: private_key
known_hosts:
  - "exporter-key ssh-ed25519 AAAAKEY"
""".strip()
        + "\n",
    )
    _write_file(
        bundles / "exporter-key" / "id_ed25519",
        "PRIVATE KEY",
        mode=0o600,
    )
    _write_file(
        bundles / "exporter-password" / "exporter.yaml",
        """
alias: exporter-password
host: 10.0.0.12
ssh:
  user: root
  auth:
    method: password
    password_env: EXPORTER_PASSWORD
known_hosts:
  - "exporter-password ssh-ed25519 AAAAPASSWORD"
""".strip()
        + "\n",
    )

    service = ExporterSSHRuntimeService(
        str(bundles),
        wrapper_install_path=str(fake_bin / "ssh"),
    )
    service.setup()

    managed_dir = home / ".ssh" / "labgrid-dashboard"
    assert (managed_dir / "config").exists()
    assert (managed_dir / "known_hosts").exists()
    assert (managed_dir / "bin" / "ssh").exists()
    assert (managed_dir / "keys" / "exporter-key").read_text(encoding="utf-8") == "PRIVATE KEY"

    config_text = (managed_dir / "config").read_text(encoding="utf-8")
    assert "Host exporter-key" in config_text
    assert "IdentityFile" in config_text
    assert "Host exporter-password" in config_text
    assert "PreferredAuthentications password,keyboard-interactive" in config_text

    known_hosts_text = (managed_dir / "known_hosts").read_text(encoding="utf-8")
    assert "exporter-key ssh-ed25519 AAAAKEY" in known_hosts_text
    assert "exporter-password ssh-ed25519 AAAAPASSWORD" in known_hosts_text

    home_config = (home / ".ssh" / "config").read_text(encoding="utf-8")
    assert "Include ~/.ssh/labgrid-dashboard/config" in home_config
    assert os.environ[AUTH_FILE_ENV] == str(managed_dir / "auth.json")
    assert str(managed_dir / "bin") in os.environ["PATH"].split(":")


def test_exporter_ssh_wrapper_uses_sshpass_for_password_exporters(
    monkeypatch,
    tmp_path: Path,
):
    """Password-authenticated exporters should route through sshpass."""
    home = tmp_path / "home"
    bundles = tmp_path / "bundles"
    fake_bin = tmp_path / "fake-bin"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("EXPORTER_PASSWORD", "s3cr3t")
    monkeypatch.setenv("PATH", str(fake_bin))

    _write_file(
        bundles / "exporter-password" / "exporter.yaml",
        """
alias: exporter-password
host: 10.0.0.12
ssh:
  user: root
  auth:
    method: password
    password_env: EXPORTER_PASSWORD
known_hosts:
  - "exporter-password ssh-ed25519 AAAAPASSWORD"
""".strip()
        + "\n",
    )

    _write_executable(
        fake_bin / "sshpass",
        "#!/bin/sh\n"
        "test -n \"$SSHPASS\" || exit 2\n"
        "printf 'SSHPASS_SET\\n'\n"
        "printf '%s\\n' \"$@\"\n",
    )
    _write_executable(
        fake_bin / "ssh-real",
        "#!/bin/sh\nprintf '%s\\n' \"$@\"\n",
    )

    install_wrapper = fake_bin / "ssh"
    service = ExporterSSHRuntimeService(
        str(bundles),
        wrapper_install_path=str(install_wrapper),
    )
    service.setup()

    wrapper = home / ".ssh" / "labgrid-dashboard" / "bin" / "ssh"
    env = os.environ.copy()
    env[REAL_SSH_ENV] = str(fake_bin / "ssh-real")

    result = subprocess.run(
        [
            str(wrapper),
            "-x",
            "-o",
            "PasswordAuthentication=no",
            "exporter-password",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    output = result.stdout
    output_lines = output.splitlines()
    assert "SSHPASS_SET" in output
    assert "-e" in output_lines
    assert "-p" not in output_lines
    assert all("s3cr3t" not in line for line in output_lines)
    assert "PasswordAuthentication=no" not in output
    assert "PasswordAuthentication=yes" in output
    assert "exporter-password" in output
    assert install_wrapper.read_text(encoding="utf-8") == wrapper.read_text(encoding="utf-8")


def test_exporter_ssh_wrapper_passthrough_for_private_key_exporters(
    monkeypatch,
    tmp_path: Path,
):
    """Key-authenticated exporters should call the real ssh binary unchanged."""
    home = tmp_path / "home"
    bundles = tmp_path / "bundles"
    fake_bin = tmp_path / "fake-bin"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(fake_bin))

    _write_file(
        bundles / "exporter-key" / "exporter.yaml",
        """
alias: exporter-key
host: 10.0.0.11
ssh:
  auth:
    method: private_key
known_hosts:
  - "exporter-key ssh-ed25519 AAAAKEY"
""".strip()
        + "\n",
    )
    _write_file(
        bundles / "exporter-key" / "id_ed25519",
        "PRIVATE KEY",
        mode=0o600,
    )

    _write_executable(
        fake_bin / "ssh-real",
        "#!/bin/sh\nprintf '%s\\n' \"$@\"\n",
    )

    install_wrapper = fake_bin / "ssh"
    service = ExporterSSHRuntimeService(
        str(bundles),
        wrapper_install_path=str(install_wrapper),
    )
    service.setup()

    wrapper = home / ".ssh" / "labgrid-dashboard" / "bin" / "ssh"
    env = os.environ.copy()
    env[REAL_SSH_ENV] = str(fake_bin / "ssh-real")

    result = subprocess.run(
        [str(wrapper), "-x", "exporter-key"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.stdout.splitlines() == ["-x", "exporter-key"]
    assert install_wrapper.read_text(encoding="utf-8") == wrapper.read_text(encoding="utf-8")
