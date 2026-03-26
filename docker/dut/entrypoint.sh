#!/bin/bash
# DUT Entrypoint Script
# Simulates a serial console over TCP using socat and provides SSH access
#
# This script creates a TCP listener that, when connected to,
# provides an interactive bash shell - simulating a serial console
# connection to a device under test. Additionally, it starts an SSH server
# for labgrid SSHDriver access.

echo "Starting DUT simulator: ${DUT_NAME:-dut}"

configure_dut_ssh() {
  mkdir -p /run/sshd /root/.ssh
  chmod 700 /root/.ssh

  sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
  sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
  sed -i 's/#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config

  case "${DUT_SSH_AUTH_MODE:-password}" in
    private_key)
      if [ ! -f "${DUT_SSH_SERVER_DIR}/authorized_keys" ]; then
        echo "Missing authorized_keys in ${DUT_SSH_SERVER_DIR} for ${DUT_NAME}"
        exit 1
      fi
      cp "${DUT_SSH_SERVER_DIR}/authorized_keys" /root/.ssh/authorized_keys
      chmod 600 /root/.ssh/authorized_keys
      sed -i 's/^PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
      ;;
    password)
      echo "root:${DUT_SSH_PASSWORD:-labgrid}" | chpasswd
      rm -f /root/.ssh/authorized_keys
      sed -i 's/^PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
      ;;
    *)
      echo "Unsupported DUT_SSH_AUTH_MODE '${DUT_SSH_AUTH_MODE}'"
      exit 1
      ;;
  esac
}

configure_dut_ssh

# Start SSH server in background
echo "Starting SSH server on port 22..."
/usr/sbin/sshd -D &
SSHD_PID=$!

# Handle termination signals
trap "kill $SSHD_PID; exit 0" SIGTERM SIGINT

echo "Listening on port 5000 for serial-over-TCP connections..."

# Start socat to listen on TCP port 5000
# - TCP-LISTEN: Listen on port 5000, reuse address, fork for each connection
# - EXEC: Execute the staging serial login shell with PTY
exec socat TCP-LISTEN:5000,reuseaddr,fork EXEC:'/serial-console.sh',pty,stderr,setsid,sigint,sane
