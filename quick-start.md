# Quick Start

## Development Mode (Mock Data)

```bash
docker compose up -d
```

## Staging Mode (Simulated DUTs)

```bash
docker compose --profile staging up -d --build
```

This starts 3 simulated DUTs (Alpine Linux containers) with Labgrid exporters, providing a realistic test environment.

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

## Hardware Presets

The dashboard supports **hardware presets** - predefined command sets for different hardware types:

1. **View Targets by Preset**: Targets are grouped by their assigned preset (Basic, Hardware 1, etc.)
2. **Change Preset**: Expand a target → Click ⚙️ (Settings) → Select a preset → Save
3. **Preset-specific Columns**: Each preset group shows its scheduled command outputs as columns

Presets are defined in `backend/commands.yaml`. See the main [README.md](README.md) for configuration details.
