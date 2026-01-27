#!/bin/bash
# DUT Entrypoint Script
# Simulates a serial console over TCP using socat and provides SSH access
#
# This script creates a TCP listener that, when connected to,
# provides an interactive bash shell - simulating a serial console
# connection to a device under test. Additionally, it starts an SSH server
# for labgrid SSHDriver access.

echo "Starting DUT simulator: ${DUT_NAME:-dut}"

# Start SSH server in background
echo "Starting SSH server on port 22..."
/usr/sbin/sshd -D &
SSHD_PID=$!

# Handle termination signals
trap "kill $SSHD_PID; exit 0" SIGTERM SIGINT

echo "Listening on port 5000 for serial-over-TCP connections..."

# Start socat to listen on TCP port 5000
# - TCP-LISTEN: Listen on port 5000, reuse address, fork for each connection
# - EXEC: Execute bash as login shell with PTY
exec socat TCP-LISTEN:5000,reuseaddr,fork EXEC:'/bin/bash -li',pty,stderr,setsid,sigint,sane
