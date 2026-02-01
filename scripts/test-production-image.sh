#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

IMAGE_NAME="labgrid-dashboard:test"
CONTAINER_NAME="labgrid-test"
PORT="8080"

echo -e "${YELLOW}=== Labgrid Dashboard Production Image Test ===${NC}\n"

# Step 1: Build production image
echo -e "${YELLOW}Step 1: Building production image...${NC}"
docker build -t "$IMAGE_NAME" -f Dockerfile.prod .
echo -e "${GREEN}✓ Image built successfully${NC}\n"

# Step 2: Stop and remove any existing test container
echo -e "${YELLOW}Step 2: Cleaning up existing test container...${NC}"
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true
echo -e "${GREEN}✓ Cleanup complete${NC}\n"

# Step 3: Start container
echo -e "${YELLOW}Step 3: Starting container...${NC}"
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "${PORT}:80" \
  -e COORDINATOR_URL="${COORDINATOR_URL:-ws://localhost:20408/ws}" \
  -e COORDINATOR_REALM="${COORDINATOR_REALM:-realm1}" \
  -e DEBUG="${DEBUG:-false}" \
  -v "$(pwd)/backend/commands.yaml:/app/commands.yaml:ro" \
  -v "$(pwd)/backend/target_presets.json:/app/target_presets.json:ro" \
  "$IMAGE_NAME"

echo -e "${GREEN}✓ Container started${NC}\n"

# Step 4: Wait for health endpoint
echo -e "${YELLOW}Step 4: Waiting for services to be ready...${NC}"
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if curl -s -f "http://localhost:${PORT}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Services are ready${NC}\n"
    break
  fi
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}✗ Timeout waiting for services${NC}"
    echo "Container logs:"
    docker logs "$CONTAINER_NAME"
    exit 1
  fi
  sleep 1
done

# Step 5: Test endpoints
echo -e "${YELLOW}Step 5: Testing endpoints...${NC}"

# Test nginx health
echo -n "  - Nginx health endpoint: "
if curl -s -f "http://localhost:${PORT}/health" | grep -q "OK"; then
  echo -e "${GREEN}✓${NC}"
else
  echo -e "${RED}✗${NC}"
  exit 1
fi

# Test backend API health (may fail without coordinator)
echo -n "  - Backend API health: "
if curl -s -f "http://localhost:${PORT}/api/health" > /dev/null 2>&1; then
  echo -e "${GREEN}✓${NC}"
else
  echo -e "${YELLOW}⚠${NC} (requires coordinator)"
fi

# Test frontend serves HTML
echo -n "  - Frontend HTML: "
if curl -s "http://localhost:${PORT}/" | grep -q "<!doctype html>"; then
  echo -e "${GREEN}✓${NC}"
else
  echo -e "${RED}✗${NC}"
  exit 1
fi

# Test env-config.js is generated
echo -n "  - Runtime config (env-config.js): "
if curl -s "http://localhost:${PORT}/env-config.js" | grep -q "window.ENV"; then
  echo -e "${GREEN}✓${NC}"
else
  echo -e "${RED}✗${NC}"
  exit 1
fi

echo ""

# Step 6: Check supervisord processes
echo -e "${YELLOW}Step 6: Checking supervisord processes...${NC}"
docker exec "$CONTAINER_NAME" supervisorctl status

echo ""

# Step 7: Success message
echo -e "${GREEN}=== All tests passed! ===${NC}\n"
echo "Container is running and accessible at:"
echo "  - Frontend: http://localhost:${PORT}"
echo "  - API: http://localhost:${PORT}/api/health"
echo ""
echo "To view logs:"
echo "  docker logs -f $CONTAINER_NAME"
echo ""
echo "To check process status:"
echo "  docker exec $CONTAINER_NAME supervisorctl status"
echo ""
echo "To stop and remove:"
echo "  docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME"
