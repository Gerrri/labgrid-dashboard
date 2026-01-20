# Development Environment

This document describes the development environment setup for the Labgrid Dashboard project.

## Dev Container

The project uses a VS Code Dev Container for consistent development environments.

### Base Image
- **Python**: 3.11 (mcr.microsoft.com/devcontainers/python:1-3.11-bullseye)
- **Node.js**: 22 (via nvm)

### System Dependencies
- gcc, libffi-dev (Python compilation)
- git, curl (tooling)
- socat (network utilities)
- Docker CLI (docker-outside-of-docker)

## Project Structure

```
/workspace
├── backend/          # FastAPI backend (Python 3.11)
├── frontend/         # React + Vite frontend (Node.js 22)
├── docker/           # Docker configurations for services
├── .devcontainer/    # Dev Container configuration
├── .vscode/          # VS Code workspace settings
└── agent-rules/      # AI Agent coding guidelines
```

## Ports

| Service         | Port  | Description                    |
|-----------------|-------|--------------------------------|
| Frontend (Vite) | 3000  | React development server       |
| Backend (FastAPI)| 8000 | REST API + WebSocket           |
| Labgrid Coordinator | 20408 | Labgrid crossbar coordinator |

## Quick Commands

These aliases are available in the dev container:

```bash
# Development servers
backend         # Start FastAPI on :8000 with hot-reload
frontend        # Start Vite on :3000 with hot-reload
pytest          # Run backend tests

# Staging environment (with simulated DUTs)
staging-up      # Start full staging stack
staging-down    # Stop staging stack
staging-logs    # View staging logs
```

## Python Environment

- **Interpreter**: `/usr/local/bin/python`
- **Package Manager**: pip (user install)
- **Linting**: ruff, black, isort
- **Type Checking**: mypy, pylance
- **Testing**: pytest, pytest-cov
- **Debugging**: debugpy

### Backend Dependencies
See [`backend/requirements.txt`](backend/requirements.txt) for full list.

Key packages:
- FastAPI + Uvicorn (async web framework)
- labgrid (hardware test automation)
- aiohttp (async HTTP client)
- pydantic (data validation)

## Node.js Environment

- **Runtime**: Node.js 22 (via nvm)
- **Package Manager**: npm
- **Linting**: ESLint
- **Formatting**: Prettier
- **Testing**: Vitest
- **Build Tool**: Vite

### Frontend Dependencies
See [`frontend/package.json`](frontend/package.json) for full list.

Key packages:
- React 18 (UI library)
- TypeScript (type safety)
- Vite (build tool)
- Vitest (testing)

## VS Code Extensions

The following extensions are automatically installed:

### Python
- `ms-python.python` - Python language support
- `ms-python.vscode-pylance` - Type checking
- `ms-python.debugpy` - Debugging
- `ms-python.black-formatter` - Code formatting

### JavaScript/TypeScript
- `dbaeumer.vscode-eslint` - Linting
- `esbenp.prettier-vscode` - Formatting

### General
- `rooveterinaryinc.roo-cline` - AI coding assistant
- `ms-azuretools.vscode-docker` - Docker support
- `eamodio.gitlens` - Git visualization
- `redhat.vscode-yaml` - YAML support

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Backend
LABGRID_COORDINATOR=ws://coordinator:20408/ws
ENVIRONMENT=development

# Frontend
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

## Docker Compose Profiles

The `docker-compose.yml` supports multiple profiles:

- **staging**: Full stack with simulated DUTs
- **coordinator**: Only labgrid coordinator
- **production**: Production-ready configuration

## Debugging

### Backend (Python)
1. Set breakpoints in VS Code
2. Run "Debug: Backend (FastAPI)" from launch configurations
3. Use the debug console for inspection

### Frontend (React)
1. Set breakpoints in VS Code
2. Run "Debug: Frontend (Chrome)" from launch configurations
3. Browser DevTools also available

## Troubleshooting

### Container won't start
```bash
# Rebuild without cache
docker compose down -v
docker compose build --no-cache
```

### Port already in use
```bash
# Check what's using the port
lsof -i :8000
# Kill the process or use a different port
```

### Python packages not found
```bash
# Reinstall dependencies
pip install --user -r backend/requirements.txt
```

### Node modules issues
```bash
# Clean reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Docker Staging Mode Issues (Dev Container)

When running staging mode inside a Dev Container with docker-outside-of-docker,
volume mounts may not work correctly because the host paths don't match the
container paths.

**Symptoms:**
- `ModuleNotFoundError: No module named 'app'` in backend
- `ENOENT: no such file or directory, open '/app/package.json'` in frontend

**Solution:**
The volume mounts in `docker-compose.yml` are disabled by default for staging mode.
For local development with hot-reload outside of Dev Container, uncomment the volumes:

```yaml
# In docker-compose.yml
backend:
  volumes:
    - ./backend:/app  # Uncomment for local dev

frontend:
  volumes:
    - ./frontend:/app  # Uncomment for local dev
    - /app/node_modules
```

**Connecting Dev Container to labgrid-network:**
```bash
# Connect your Dev Container to access services by name
docker network connect labgrid-network $(hostname)

# Then you can access services via container names
curl http://labgrid-backend:8000/api/health
```
