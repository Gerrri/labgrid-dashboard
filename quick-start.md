# Quick Start

## Development Mode (Mock Data)

```bash
docker compose up -d
```

## Staging Mode (Simulated DUTs)

```bash
docker compose --profile staging up -d --build
```

## Live Mode (Real Labgrid Coordinator)

```bash
# Set your coordinator URL
export COORDINATOR_URL=ws://your-coordinator:20408/ws
docker compose up -d backend frontend
```

## Stop All Services

```bash
docker compose down
# or for staging:
docker compose --profile staging down
```

## URLs

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
