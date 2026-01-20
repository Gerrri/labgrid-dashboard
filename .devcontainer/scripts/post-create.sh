#!/bin/bash
# Post-create script - runs once after container creation
set -e

echo "🚀 Installing dependencies..."

# Python backend
cd /workspace/backend
pip install --user -r requirements.txt
pip install --user black isort mypy debugpy ruff pytest-cov

# Node.js frontend
cd /workspace/frontend
npm install

# Copy .env files if they don't exist
cd /workspace
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || true
fi
if [ ! -f frontend/.env ]; then
    cp frontend/.env.example frontend/.env 2>/dev/null || true
fi

# Shell aliases
cat >> ~/.bashrc << 'EOF'

# Labgrid Dashboard aliases
alias backend="cd /workspace/backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --loop asyncio"
alias frontend="cd /workspace/frontend && npm run dev -- --host 0.0.0.0 --port 3000"
alias pytest="cd /workspace/backend && python -m pytest"
alias pytest-cov="cd /workspace/backend && python -m pytest --cov=app --cov-report=html"
alias lint="cd /workspace/backend && ruff check . && cd /workspace/frontend && npm run lint"
alias format="cd /workspace/backend && black . && isort . && cd /workspace/frontend && npm run format"

# Docker staging aliases (uses main docker-compose.yml)
alias staging-up="docker compose -f /workspace/docker-compose.yml --profile staging up -d"
alias staging-down="docker compose -f /workspace/docker-compose.yml --profile staging down"
alias staging-logs="docker compose -f /workspace/docker-compose.yml --profile staging logs -f"
EOF

echo "✅ Setup complete! Use 'backend' and 'frontend' to start servers."
