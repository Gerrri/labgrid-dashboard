# DUT (Device Under Test) Simulator Container
# Provides a simulated device with serial-over-TCP console

FROM alpine:latest

# Install tools for command execution and serial simulation
RUN apk add --no-cache \
    bash \
    socat \
    util-linux \
    procps \
    coreutils

# Serial-over-TCP listener script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Default serial port
EXPOSE 5000

# Environment variable for device name (optional)
ENV DUT_NAME=dut

CMD ["/entrypoint.sh"]
