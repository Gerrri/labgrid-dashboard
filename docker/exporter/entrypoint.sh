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
echo "Starting labgrid-exporter..."
exec labgrid-exporter --name "${EXPORTER_NAME}" \
    --crossbar "${COORDINATOR_URL}" \
    /config/exporter.yaml
