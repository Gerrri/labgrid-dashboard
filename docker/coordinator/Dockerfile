# Labgrid Coordinator Dockerfile
# Since there's no official labgrid Docker image, we build our own
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install labgrid and its dependencies
RUN pip install --no-cache-dir \
    labgrid>=24.0 \
    crossbar>=23.6.0

# Create configuration directory
RUN mkdir -p /etc/labgrid

# Copy coordinator configuration
COPY coordinator.yaml /etc/labgrid/coordinator.yaml

# Expose WAMP port (Crossbar.io)
EXPOSE 20408

# Run the labgrid coordinator
CMD ["labgrid-coordinator", "--config", "/etc/labgrid/coordinator.yaml"]
