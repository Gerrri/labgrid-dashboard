# Labgrid Dashboard

A web-based dashboard for monitoring and interacting with devices (DUTs) managed by a [Labgrid](https://github.com/labgrid-project/labgrid) Coordinator.

## ⚠️ Disclaimer

> **This project is largely developed using AI-assisted "vibe coding".**
> 
> While functional, the code may contain patterns, approaches, or implementations that were generated with significant AI assistance. Use in production environments should be done with appropriate review and testing.

## What is this project?

Labgrid Dashboard provides a real-time web interface to:

- **View all targets** managed by your Labgrid Coordinator in a clean table view
- **Monitor status** - See which devices are available, acquired, or offline
- **Track ownership** - Know who currently has acquired each exporter/target
- **Quick access** - Click on IP addresses to directly access device web interfaces
- **Execute commands** - Run predefined commands on DUTs and view their outputs
- **Real-time updates** - WebSocket-based live status updates without manual refresh

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | React + TypeScript |
| Backend | Python + FastAPI |
| Real-time | WebSockets |
| Labgrid Communication | WAMP Protocol (via autobahn) |
| Development | Docker Compose |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local development)
- Python 3.11+ (for local development)

### Running with Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Local Development

**Backend:**

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev        # With backend
npm run dev:mock   # Without backend (mock data)
```

### Running Tests

**Backend:**

```bash
cd backend
pip install -r requirements.txt  # Includes test dependencies
pytest
```

**Frontend:**

```bash
cd frontend
npm install
npm test
```

## Configuration

### Backend (`backend/commands.yaml`)

Define custom commands that can be executed on targets:

```yaml
commands:
  - name: "Linux Version"
    command: "cat /etc/os-release"
    description: "Shows the Linux distribution"

  - name: "System Time"
    command: "date"
    description: "Current system time"
```

### Environment Variables

See `.env.example` for available configuration options.

| Variable | Description | Default |
|----------|-------------|---------|
| `COORDINATOR_URL` | Labgrid Coordinator WebSocket URL | `ws://coordinator:20408/ws` |
| `COORDINATOR_REALM` | WAMP realm | `realm1` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000` |

## API Documentation

When backend is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check with coordinator status |
| `/api/targets` | GET | List all targets |
| `/api/targets/{name}` | GET | Get specific target details |
| `/api/targets/{name}/commands` | GET | Get available commands for target |
| `/api/targets/{name}/command` | POST | Execute command on target |
| `/api/ws` | WebSocket | Real-time updates |

## Architecture

See [plans/architecture-plan.md](plans/architecture-plan.md) for detailed architecture documentation.

### Project Structure

```
labgrid-dashboard/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes and WebSocket handlers
│   │   ├── models/         # Pydantic models
│   │   └── services/       # Business logic (Labgrid client, commands)
│   ├── tests/              # Backend tests
│   └── commands.yaml       # Predefined commands configuration
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── hooks/          # Custom React hooks
│   │   ├── services/       # API client
│   │   ├── types/          # TypeScript types
│   │   └── __tests__/      # Frontend tests
│   └── vitest.config.ts    # Test configuration
├── docker/                 # Docker configurations
│   └── coordinator/        # Labgrid Coordinator for development
└── docker-compose.yml      # Development environment
```

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

*License to be determined.*
