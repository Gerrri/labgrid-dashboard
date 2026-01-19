#!/bin/bash
# Labgrid Exporter Entrypoint Script
# Generates configuration from template and starts the exporter

set -e

echo "Starting Labgrid Exporter: ${EXPORTER_NAME}"
echo "  DUT Host: ${DUT_HOST}"
echo "  DUT Port: ${DUT_PORT}"
echo "  Coordinator: ${COORDINATOR_URL}"

# Generate exporter configuration from template
echo "Generating exporter configuration..."
sed -e "s/__DUT_HOST__/${DUT_HOST}/g" \
    -e "s/__DUT_PORT__/${DUT_PORT}/g" \
    -e "s/__EXPORTER_NAME__/${EXPORTER_NAME}/g" \
    /config/exporter-template.yaml > /config/exporter.yaml

echo "Generated configuration:"
cat /config/exporter.yaml

# Wait for coordinator to be available
echo "Waiting for coordinator at ${COORDINATOR_URL}..."
sleep 5

# Start the labgrid exporter
# -c HOST:PORT format requires extracting host:port from ws://host:port/ws URL
COORDINATOR_HOST_PORT=$(echo "${COORDINATOR_URL}" | sed 's|ws://||' | sed 's|/ws$||')

echo "Starting labgrid-exporter..."
echo "  Coordinator: ${COORDINATOR_HOST_PORT}"
exec labgrid-exporter -c "${COORDINATOR_HOST_PORT}" \
    --name "${EXPORTER_NAME}" \
    /config/exporter.yaml
