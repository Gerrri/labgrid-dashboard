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
    labgrid>=24.0

# Expose WAMP port
EXPOSE 20408

# Run the labgrid coordinator
# -l specifies the listen address and port
CMD ["labgrid-coordinator", "-l", "0.0.0.0:20408"]
