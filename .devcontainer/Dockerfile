# Dev Container Dockerfile
# Python 3.11 + Node.js 22 for full-stack development
FROM mcr.microsoft.com/devcontainers/python:1-3.11-bullseye

# Install Node.js 22
ARG NODE_VERSION="22"
RUN if [ "${NODE_VERSION}" != "none" ]; then su vscode -c "umask 0002 && . /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} 2>&1"; fi

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    git \
    curl \
    socat \
    && rm -rf /var/lib/apt/lists/*

# Install global npm packages
RUN su vscode -c "source /usr/local/share/nvm/nvm.sh && npm install -g npm@latest" 2>&1

# Set Python environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace
