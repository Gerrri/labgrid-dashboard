# Init-Places Container
# Creates exporter places for staging demonstration.
#
# This container runs once at startup to create place mappings and can
# optionally acquire a place if ACQUIRE_PLACE is set.

FROM python:3.11-slim

# Install git and labgrid from git for latest CLI features
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install labgrid from git (latest version with full CLI)
RUN pip install --no-cache-dir git+https://github.com/labgrid-project/labgrid.git

# Show available labgrid-client commands for debugging
RUN labgrid-client --help || true

# Copy the place setup script
COPY acquire-exporter.sh /scripts/acquire-exporter.sh
RUN chmod +x /scripts/acquire-exporter.sh

# Set working directory
WORKDIR /scripts

# Default environment variables
ENV COORDINATOR_HOST=coordinator:20408
ENV ACQUIRE_PLACE=none
ENV EXPORTER_NAME=exporter-1
ENV USER_NAME=staging-user
ENV WAIT_TIME=10

# Run the place setup script
CMD ["/scripts/acquire-exporter.sh"]
