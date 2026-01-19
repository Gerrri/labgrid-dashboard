#!/bin/bash
# DUT Entrypoint Script
# Simulates a serial console over TCP using socat
#
# This script creates a TCP listener that, when connected to,
# provides an interactive bash shell - simulating a serial console
# connection to a device under test.

echo "Starting DUT simulator: ${DUT_NAME:-dut}"
echo "Listening on port 5000 for serial-over-TCP connections..."

# Start socat to listen on TCP port 5000
# - TCP-LISTEN: Listen on port 5000, reuse address, fork for each connection
# - EXEC: Execute bash as login shell with PTY
exec socat TCP-LISTEN:5000,reuseaddr,fork EXEC:'/bin/bash -li',pty,stderr,setsid,sigint,sane
