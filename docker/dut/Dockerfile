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
    mkdir -p /run/sshd && \
    echo "root:labgrid" | chpasswd && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Serial-over-TCP listener script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose serial port and SSH port
EXPOSE 5000 22

# Environment variable for device name (optional)
ENV DUT_NAME=dut

CMD ["/entrypoint.sh"]
