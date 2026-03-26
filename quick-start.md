# Quick Start

## Development Mode (Mock Data)

```bash
docker compose up -d
```

## Staging Mode (Simulated DUTs)

```bash
docker compose --profile staging up -d --build
```

This starts 4 simulated DUTs (Alpine Linux containers) with Labgrid exporters, providing a realistic test environment.

The staging setup also exercises exporter SSH bundles so serial command execution can reach exporters over SSH:
- `exporter-1` uses private key authentication
- `exporter-4` uses username/password authentication
- the bundle tree is mounted into the backend at `/app/exporter-ssh`

The four staging targets are wired like this:
- `exporter-1`: serial command execution
- `exporter-2`: serial-first with SSH fallback
- `exporter-3`: SSH using a DUT private key
- `exporter-4`: SSH using DUT username/password

## Live Mode (Real Labgrid Coordinator)

```bash
# Set your coordinator URL
export COORDINATOR_URL=ws://your-coordinator:20408/ws
docker compose up -d backend frontend
```

For live mode, provide the exporter SSH bundle tree as well if you use serial command execution against real exporters.

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
