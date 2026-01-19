#!/bin/bash
# Auto-acquire exporter-1 for staging demonstration
# This script creates a place, matches it to exporter resources, and acquires it
# Uses labgrid-client CLI from latest labgrid version

COORDINATOR_HOST="${COORDINATOR_HOST:-coordinator:20408}"
PLACE_NAME="${PLACE_NAME:-exporter-1}"
EXPORTER_NAME="${EXPORTER_NAME:-exporter-1}"
USER_NAME="${USER_NAME:-staging-user}"
WAIT_TIME="${WAIT_TIME:-10}"

echo "=========================================="
echo "Labgrid Auto-Acquire Script"
echo "=========================================="
echo "Coordinator: ${COORDINATOR_HOST}"
echo "Place: ${PLACE_NAME}"
echo "Exporter: ${EXPORTER_NAME}"
echo "User: ${USER_NAME}"
echo "=========================================="

# Wait for services to be fully ready
echo "Waiting ${WAIT_TIME}s for services to initialize..."
sleep "${WAIT_TIME}"

# Set environment for labgrid-client
export LG_COORDINATOR="${COORDINATOR_HOST}"
export LG_USERNAME="${USER_NAME}"

echo ""
echo "Step 1: Show labgrid-client version and available commands..."
labgrid-client --version 2>&1 || true
echo ""
labgrid-client --help 2>&1

echo ""
echo "Step 2: Checking coordinator connection..."
if ! labgrid-client resources; then
    echo "ERROR: Cannot connect to coordinator at ${COORDINATOR_HOST}"
    exit 1
fi

echo ""
echo "Step 3: Listing available resources..."
labgrid-client resources

echo ""
echo "Step 4: Creating place '${PLACE_NAME}'..."
# The create command uses -p to specify the place name
echo "Running: labgrid-client -p ${PLACE_NAME} create"
if labgrid-client -p "${PLACE_NAME}" create 2>&1; then
    echo "Place '${PLACE_NAME}' created successfully"
else
    CREATE_EXIT=$?
    echo "Create returned exit code: ${CREATE_EXIT}"
    echo "Place might already exist, continuing..."
fi

echo ""
echo "Step 5: Listing places..."
labgrid-client places || labgrid-client p 2>&1

echo ""
echo "Step 6: Adding match rule for exporter resources..."
echo "Running: labgrid-client -p ${PLACE_NAME} add-match '*/${EXPORTER_NAME}/*'"
labgrid-client -p "${PLACE_NAME}" add-match "*/${EXPORTER_NAME}/*" 2>&1 || {
    echo "Match rule might already exist or failed"
}

echo ""
echo "Step 7: Showing place details..."
labgrid-client -p "${PLACE_NAME}" show 2>&1 || {
    echo "Could not show place details"
}

echo ""
echo "Step 8: Acquiring place '${PLACE_NAME}'..."
if labgrid-client -p "${PLACE_NAME}" acquire 2>&1; then
    echo ""
    echo "Step 9: Verifying acquisition..."
    labgrid-client -p "${PLACE_NAME}" show
    
    echo ""
    echo "=========================================="
    echo "SUCCESS: Place '${PLACE_NAME}' acquired by '${USER_NAME}'"
    echo "=========================================="
    
    sleep 2
    exit 0
else
    echo "ERROR: Failed to acquire place '${PLACE_NAME}'"
    echo ""
    echo "Debug info:"
    echo "All places:"
    labgrid-client places 2>&1 || labgrid-client p 2>&1
    echo ""
    echo "All resources:"
    labgrid-client resources
    exit 1
fi
