# Dev Container Dockerfile
# Python 3.11 + Node.js 22 for full-stack development
FROM mcr.microsoft.com/devcontainers/python:1-3.11-bullseye

# Install Node.js 22
ARG NODE_VERSION="22"
RUN if [ "${NODE_VERSION}" != "none" ]; then su vscode -c "umask 0002 && . /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} 2>&1"; fi

# Fix Yarn repository GPG key issue (prevents docker-outside-of-docker feature from failing)
RUN rm -f /etc/apt/sources.list.d/yarn.list || true

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

# Install Claude Code CLI
RUN curl -fsSL https://claude.ai/install.sh -o /tmp/install-claude.sh && \
    chmod +x /tmp/install-claude.sh && \
    su vscode -c "/tmp/install-claude.sh stable" && \
    rm /tmp/install-claude.sh

# Set Python environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace
