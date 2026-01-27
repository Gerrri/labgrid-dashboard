#!/bin/bash
# Auto-acquire exporter-1 for staging demonstration
# This script creates places for ALL exporters, matches them to exporter resources,
# and acquires only exporter-1 for the staging user.
# Uses labgrid-client CLI from latest labgrid version

COORDINATOR_HOST="${COORDINATOR_HOST:-coordinator:20408}"
ACQUIRE_PLACE="${ACQUIRE_PLACE:-exporter-1}"
USER_NAME="${USER_NAME:-staging-user}"
WAIT_TIME="${WAIT_TIME:-10}"

# Define all exporters to create places for
EXPORTERS=("exporter-1" "exporter-2" "exporter-3")

echo "=========================================="
echo "Labgrid Auto-Acquire Script"
echo "=========================================="
echo "Coordinator: ${COORDINATOR_HOST}"
echo "Exporters: ${EXPORTERS[*]}"
echo "Place to acquire: ${ACQUIRE_PLACE}"
echo "User: ${USER_NAME}"
echo "=========================================="

# Wait for services to be fully ready
echo "Waiting ${WAIT_TIME}s for services to initialize..."
sleep "${WAIT_TIME}"

# Set environment for labgrid-client
export LG_COORDINATOR="${COORDINATOR_HOST}"
export LG_USERNAME="${USER_NAME}"

echo ""
echo "Step 1: Show labgrid-client version..."
labgrid-client --version 2>&1 || true

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
echo "Step 4: Creating places for all exporters..."
for exporter in "${EXPORTERS[@]}"; do
    place_name="${exporter}"
    echo ""
    echo "  Creating place '${place_name}' for exporter '${exporter}'..."
    echo "  Running: labgrid-client -p ${place_name} create"
    if labgrid-client -p "${place_name}" create 2>&1; then
        echo "  Place '${place_name}' created successfully"
    else
        CREATE_EXIT=$?
        echo "  Create returned exit code: ${CREATE_EXIT}"
        echo "  Place might already exist, continuing..."
    fi
done

echo ""
echo "Step 5: Adding match rules for each place..."
for exporter in "${EXPORTERS[@]}"; do
    place_name="${exporter}"
    echo ""
    echo "  Adding match rule for place '${place_name}' -> exporter '${exporter}'..."
    echo "  Running: labgrid-client -p ${place_name} add-match '*/${exporter}/*'"
    labgrid-client -p "${place_name}" add-match "*/${exporter}/*" 2>&1 || {
        echo "  Match rule might already exist or failed"
    }
done

echo ""
echo "Step 6: Listing all places..."
labgrid-client places || labgrid-client p 2>&1

echo ""
echo "Step 7: Showing details for all places..."
for exporter in "${EXPORTERS[@]}"; do
    place_name="${exporter}"
    echo ""
    echo "  Details for place '${place_name}':"
    labgrid-client -p "${place_name}" show 2>&1 || {
        echo "  Could not show place details for '${place_name}'"
    }
done

echo ""
echo "Step 8: Acquiring place '${ACQUIRE_PLACE}'..."
if labgrid-client -p "${ACQUIRE_PLACE}" acquire 2>&1; then
    echo ""
    echo "Step 9: Verifying acquisition..."
    labgrid-client -p "${ACQUIRE_PLACE}" show

    echo ""
    echo "=========================================="
    echo "SUCCESS: Setup complete!"
    echo "=========================================="
    echo "Places created: ${EXPORTERS[*]}"
    echo "Place acquired: ${ACQUIRE_PLACE} (by ${USER_NAME})"
    echo "=========================================="

    sleep 2
    exit 0
else
    echo "ERROR: Failed to acquire place '${ACQUIRE_PLACE}'"
    echo ""
    echo "Debug info:"
    echo "All places:"
    labgrid-client places 2>&1 || labgrid-client p 2>&1
    echo ""
    echo "All resources:"
    labgrid-client resources
    exit 1
fi
