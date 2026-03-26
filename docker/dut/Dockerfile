# DUT (Device Under Test) Simulator Container
# Provides a simulated device with serial-over-TCP console and SSH access

FROM alpine:latest

# Install tools for command execution, serial simulation, and SSH
RUN apk add --no-cache \
    bash \
    socat \
    util-linux \
    procps \
    coreutils \
    openssh-server

# Setup SSH server
RUN ssh-keygen -A && \
    mkdir -p /run/sshd /root/.ssh && \
    echo "root:labgrid" | chpasswd

# Serial-over-TCP listener script
COPY entrypoint.sh /entrypoint.sh
COPY serial-console.sh /serial-console.sh
RUN chmod +x /entrypoint.sh /serial-console.sh

# Expose serial port and SSH port
EXPOSE 5000 22

# Environment variable for device name (optional)
ENV DUT_NAME=dut
ENV DUT_SSH_AUTH_MODE=password
ENV DUT_SSH_PASSWORD=labgrid
ENV DUT_SSH_SERVER_DIR=/ssh-server
ENV DUT_SERIAL_USERNAME=root
ENV DUT_SERIAL_PASSWORD=labgrid

CMD ["/entrypoint.sh"]
