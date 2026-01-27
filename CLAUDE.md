# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Getting Started

**Please read [AGENTS.md](AGENTS.md) for complete workflow and coding guidelines.**

The AGENTS.md file contains:
- Project language requirements (English)
- Testing environment setup
- Workflow steps (Implement → Document → Test → Git)
- Links to detailed agent rules for coding, documentation, testing, and git

## Quick Reference

**Docker Staging Environment:**
```bash
# Start full stack with mock DUTs
docker compose --profile staging up -d --build

# Stop staging
docker compose --profile staging down

# View logs
docker compose --profile staging logs -f

# Rebuild specific service
docker compose --profile staging up -d --build backend
```

**Project Language:** All code, documentation, and communication should be in English.

## Key Files & Architecture

**Backend (FastAPI):**
- `backend/app/main.py` - FastAPI app initialization, CORS, WebSocket setup
- `backend/app/api/websocket.py` - WebSocket handler for real-time target updates
- `backend/app/services/labgrid_service.py` - Labgrid client integration (target locking/unlocking)
- `backend/app/services/scheduler_service.py` - Background task scheduler for command execution
- `backend/app/config.py` - Environment configuration
- `backend/commands.yaml` - Command presets for targets

**Frontend (React + Vite):**
- `frontend/src/components/TargetTable/` - Main target display component
- `frontend/src/hooks/useWebSocket.ts` - WebSocket connection management
- `frontend/src/types/` - TypeScript type definitions

**Infrastructure:**
- `docker-compose.yml` - Multi-service orchestration (coordinator, exporters, DUTs)
- `.devcontainer/` - VS Code dev container configuration

## Testing Instructions

**Run Backend Tests:**
```bash
cd backend
python -m pytest                          # Run all tests
python -m pytest tests/test_file.py       # Run specific file
python -m pytest -k test_function_name    # Run specific test
python -m pytest -v                       # Verbose output
```

**Coverage Reports:**
```bash
cd backend
python -m pytest --cov=app --cov-report=html    # Generate HTML report
python -m pytest --cov=app --cov-report=term    # Terminal report
# View HTML report: backend/htmlcov/index.html
```

**Test Requirements:**
- Minimum 80% code coverage
- All tests must pass before commits
- Follow AAA pattern (Arrange, Act, Assert)
- See [agent-rules/testing.md](./agent-rules/testing.md) for detailed guidelines

**Test Locations:**
- Backend: `backend/tests/`
- Frontend: `frontend/src/__tests__/` (if applicable)

- **No Co-Author**: Do NOT add "Co-Authored-By: Claude" lines to commit messages
