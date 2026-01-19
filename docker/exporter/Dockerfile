# Labgrid Exporter Container
# Exports DUT resources to the Labgrid Coordinator

FROM python:3.11-slim

# Install labgrid and dependencies
RUN pip install --no-cache-dir labgrid

# Create config directory
RUN mkdir -p /config

# Copy configuration template
COPY exporter-config.yaml /config/exporter-template.yaml

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment variables (to be overridden)
ENV DUT_HOST=dut
ENV DUT_PORT=5000
ENV EXPORTER_NAME=exporter
ENV COORDINATOR_URL=ws://coordinator:20408/ws

# Working directory for exporter
WORKDIR /config

CMD ["/entrypoint.sh"]
