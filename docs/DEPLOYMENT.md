# Production Deployment Guide

This guide covers deploying the Labgrid Dashboard to production using the pre-built Docker image from GitHub Container Registry (GHCR).

## Overview

The Labgrid Dashboard is distributed as a single production-ready Docker image that combines:
- **Frontend** - React/Vite application served by nginx
- **Backend** - FastAPI application running on uvicorn
- **Nginx** - Web server that serves frontend static files and proxies API requests to the backend
- **Supervisord** - Process manager that runs both nginx and uvicorn

The image is published to: `ghcr.io/gerrri/labgrid-dashboard`

## Prerequisites

- Docker 20.10+ installed
- Running Labgrid coordinator (the dashboard connects to an existing coordinator)
- Network access from the dashboard container to the coordinator

## Quick Start

### Using Docker Run

```bash
docker pull ghcr.io/gerrri/labgrid-dashboard:latest

docker run -d \
  --name labgrid-dashboard \
  -p 80:80 \
  -e COORDINATOR_URL=ws://coordinator:20408/ws \
  -e CORS_ORIGINS=http://localhost \
  -v ./commands.yaml:/app/commands.yaml:ro \
  -v ./target_presets.json:/app/target_presets.json:ro \
  ghcr.io/gerrri/labgrid-dashboard:latest
```

Access the dashboard at: http://localhost

### Using Docker Compose

See the example `docker-compose.prod.yml` file in the repository root.

```bash
# Copy and customize the environment template
cp .env.production.example .env.production

# Edit .env.production with your coordinator URL and settings
nano .env.production

# Start the dashboard
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Stop the dashboard
docker compose -f docker-compose.prod.yml down
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `COORDINATOR_URL` | Labgrid coordinator WebSocket endpoint | `ws://coordinator:20408/ws` or `coordinator:20408` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost` | Comma-separated list of allowed origins for API access |
| `COORDINATOR_REALM` | `realm1` | Labgrid coordinator realm name |
| `COORDINATOR_TIMEOUT` | `30` | Connection timeout in seconds |
| `LABGRID_COMMAND_TIMEOUT` | `30` | Command execution timeout in seconds |
| `LABGRID_POLL_INTERVAL_SECONDS` | `5` | Polling interval for target status updates |
| `COMMANDS_FILE` | `/app/commands.yaml` | Path to commands configuration file |
| `PRESETS_FILE` | `/app/target_presets.json` | Path to target presets configuration file |
| `DEBUG` | `false` | Enable debug logging (`true` or `false`) |
| `WS_URL_EXTERNAL` | `/api/ws` | External WebSocket URL (for reverse proxy scenarios) |

### Environment Variable Notes

- **COORDINATOR_URL**: Can be provided as `ws://host:port/ws` (full WebSocket URL) or `host:port` (protocol will be added automatically)
- **CORS_ORIGINS**: Set this to match your dashboard's public URL(s) to prevent CORS errors. Multiple origins can be comma-separated.
- **WS_URL_EXTERNAL**: Only needed if the dashboard is behind a reverse proxy with a different external URL for WebSocket connections

## Volume Mounts

The dashboard requires two configuration files to be mounted:

```bash
-v /path/to/commands.yaml:/app/commands.yaml:ro \
-v /path/to/target_presets.json:/app/target_presets.json:ro
```

### commands.yaml

Defines the available commands for targets. Example:

```yaml
commands:
  - name: reboot
    command: "reboot"
    description: "Reboot the target"
  - name: uptime
    command: "uptime"
    description: "Show system uptime"
```

### target_presets.json

Defines hardware presets with associated commands. Example:

```json
{
  "presets": [
    {
      "id": "default",
      "name": "Default",
      "description": "Default preset",
      "commands": [],
      "scheduled_commands": [],
      "auto_refresh_commands": []
    }
  ],
  "default_preset": "default"
}
```

## Production Considerations

### Security

1. **Use HTTPS**: Always deploy behind a reverse proxy with TLS termination (nginx, traefik, etc.)
2. **CORS Configuration**: Set `CORS_ORIGINS` to match your production domain(s)
3. **Network Isolation**: Use Docker networks to isolate the dashboard from other services
4. **Read-only Volumes**: Mount configuration files as read-only (`:ro` flag)
5. **Non-root User**: The container runs as non-root user `appuser` (UID 1000)

### Scaling

The current image runs 2 uvicorn workers. For higher load:

1. **Horizontal Scaling**: Run multiple dashboard containers behind a load balancer
2. **Resource Limits**: Set memory and CPU limits in docker-compose or Kubernetes
3. **Health Checks**: Use the built-in health endpoint at `/health`

### Monitoring

**Health Check Endpoint**: `http://localhost/health`

```bash
# Check nginx health
curl http://localhost/health

# Check backend API health
curl http://localhost/api/health
```

**Logs**:

```bash
# View all logs (nginx + backend)
docker logs labgrid-dashboard

# Follow logs
docker logs -f labgrid-dashboard

# Check process status
docker exec labgrid-dashboard supervisorctl status
```

**Metrics**:
- Monitor container metrics: CPU, memory, network
- Monitor coordinator connectivity via `/api/health` endpoint
- Monitor WebSocket connections

### Backup

Configuration files should be backed up:
- `commands.yaml`
- `target_presets.json`

The dashboard itself is stateless - no persistent data storage is required.

## Reverse Proxy Example

### Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name dashboard.example.com;

    ssl_certificate /etc/ssl/certs/dashboard.crt;
    ssl_certificate_key /etc/ssl/private/dashboard.key;

    location / {
        proxy_pass http://labgrid-dashboard:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /api/ws {
        proxy_pass http://labgrid-dashboard:80;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 7d;
    }
}
```

### Traefik (docker-compose)

```yaml
services:
  labgrid-dashboard:
    image: ghcr.io/gerrri/labgrid-dashboard:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.dashboard.rule=Host(`dashboard.example.com`)"
      - "traefik.http.routers.dashboard.entrypoints=websecure"
      - "traefik.http.routers.dashboard.tls.certresolver=letsencrypt"
      - "traefik.http.services.dashboard.loadbalancer.server.port=80"
    environment:
      - COORDINATOR_URL=ws://coordinator:20408/ws
      - CORS_ORIGINS=https://dashboard.example.com
```

## Troubleshooting

### Dashboard won't start

**Check logs**:
```bash
docker logs labgrid-dashboard
```

**Common issues**:
- Coordinator URL incorrect or unreachable
- Port 80 already in use (change port mapping: `-p 8080:80`)
- Configuration files not mounted correctly

### Cannot connect to coordinator

**Verify coordinator is reachable**:
```bash
# From inside the container
docker exec labgrid-dashboard curl -v ws://coordinator:20408/ws
```

**Check environment variables**:
```bash
docker exec labgrid-dashboard env | grep COORDINATOR
```

### WebSocket connection fails

**Check CORS settings**:
- Ensure `CORS_ORIGINS` matches your dashboard URL
- If behind reverse proxy, set `WS_URL_EXTERNAL` to the external WebSocket URL

**Check browser console**:
- Open browser DevTools → Network tab
- Look for WebSocket connection errors

### API requests fail with CORS errors

**Update CORS_ORIGINS**:
```bash
docker run -e CORS_ORIGINS=http://localhost,https://dashboard.example.com ...
```

### Configuration changes not applied

**Restart the container** after modifying mounted configuration files:
```bash
docker restart labgrid-dashboard
```

## Version Pinning

For production deployments, always pin to a specific version:

```bash
# Pin to exact version
docker pull ghcr.io/gerrri/labgrid-dashboard:1.2.3

# Pin to minor version (receives patch updates)
docker pull ghcr.io/gerrri/labgrid-dashboard:1.2

# Pin to major version (receives minor + patch updates)
docker pull ghcr.io/gerrri/labgrid-dashboard:1

# Latest (not recommended for production)
docker pull ghcr.io/gerrri/labgrid-dashboard:latest
```

## Multi-Architecture Support

The image is built for multiple architectures:
- `linux/amd64` (x86_64)
- `linux/arm64` (aarch64)

Docker will automatically pull the correct architecture for your platform.

## Migration from Development Setup

If migrating from the development docker-compose setup:

1. **Export configuration**: Copy `commands.yaml` and `target_presets.json`
2. **Note coordinator URL**: Check your dev docker-compose for coordinator connection details
3. **Pull production image**: `docker pull ghcr.io/gerrri/labgrid-dashboard:latest`
4. **Deploy**: Use the production docker-compose or docker run command
5. **Verify**: Check health endpoints and test basic functionality

## Architecture Diagram

```
┌─────────────────────────────────────┐
│   Docker Container (Port 80)        │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  Nginx (Port 80)             │  │
│  │  - Serves frontend static    │  │
│  │  - Proxies /api to backend   │  │
│  └──────────┬───────────────────┘  │
│             │                       │
│  ┌──────────▼───────────────────┐  │
│  │  Uvicorn (Port 8000)         │  │
│  │  - FastAPI backend           │  │
│  │  - WebSocket handler         │  │
│  └──────────┬───────────────────┘  │
│             │                       │
│  ┌──────────▼───────────────────┐  │
│  │  Supervisord                 │  │
│  │  - Process manager           │  │
│  └──────────────────────────────┘  │
└─────────────┬───────────────────────┘
              │
              ▼
    Labgrid Coordinator
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/Gerrri/labgrid-dashboard/issues
- Documentation: https://github.com/Gerrri/labgrid-dashboard

## License

See LICENSE file in the repository.
