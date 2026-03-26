#!/bin/sh
# Labgrid Exporter Entrypoint Script
# Generates configuration from template and starts the exporter.

set -eu

echo "Starting Labgrid Exporter: ${EXPORTER_NAME}"
echo "  DUT Host: ${DUT_HOST}"
echo "  DUT Port: ${DUT_PORT}"
echo "  Coordinator: ${COORDINATOR_URL}"

SERIAL_HOST="${SERIAL_HOST:-${DUT_HOST}}"
SERIAL_PORT="${SERIAL_PORT:-${DUT_PORT}}"
SSH_ADDRESS="${SSH_ADDRESS:-${DUT_HOST}}"
SSH_USERNAME="${SSH_USERNAME:-root}"
SSH_PASSWORD="${SSH_PASSWORD-labgrid}"

echo "Generating exporter configuration..."
sed -e "s/__SERIAL_HOST__/${SERIAL_HOST}/g" \
    -e "s/__SERIAL_PORT__/${SERIAL_PORT}/g" \
    -e "s/__SSH_ADDRESS__/${SSH_ADDRESS}/g" \
    -e "s/__SSH_USERNAME__/${SSH_USERNAME}/g" \
    -e "s/__SSH_PASSWORD__/${SSH_PASSWORD}/g" \
    -e "s/__EXPORTER_NAME__/${EXPORTER_NAME}/g" \
    /config/exporter-template.yaml > /config/exporter.yaml

echo "Generated configuration:"
cat /config/exporter.yaml

configure_exporter_ssh() {
    if [ "${EXPORTER_ISOLATED:-0}" != "1" ]; then
        echo "Exporter SSH disabled for ${EXPORTER_NAME}; running in direct mode."
        return
    fi

    echo "Configuring exporter SSH access for ${EXPORTER_NAME}..."
    mkdir -p /run/sshd /root/.ssh
    chmod 700 /root/.ssh

    if [ -f "${EXPORTER_SSH_SERVER_DIR}/ssh_host_ed25519_key" ]; then
        cp "${EXPORTER_SSH_SERVER_DIR}/ssh_host_ed25519_key" /etc/ssh/ssh_host_ed25519_key
        chmod 600 /etc/ssh/ssh_host_ed25519_key
    else
        ssh-keygen -A >/dev/null 2>&1 || true
    fi

    if [ -f "${EXPORTER_SSH_SERVER_DIR}/ssh_host_ed25519_key.pub" ]; then
        cp "${EXPORTER_SSH_SERVER_DIR}/ssh_host_ed25519_key.pub" /etc/ssh/ssh_host_ed25519_key.pub
        chmod 644 /etc/ssh/ssh_host_ed25519_key.pub
    fi

    sed -i \
        -e 's/^#\?PermitRootLogin .*/PermitRootLogin yes/' \
        -e 's/^#\?PubkeyAuthentication .*/PubkeyAuthentication yes/' \
        -e 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' \
        -e 's/^#\?UsePAM .*/UsePAM no/' \
        /etc/ssh/sshd_config

    case "${EXPORTER_SSH_AUTH_MODE:-none}" in
        private_key)
            if [ ! -f "${EXPORTER_SSH_SERVER_DIR}/authorized_keys" ]; then
                echo "Missing authorized_keys for ${EXPORTER_NAME}"
                exit 1
            fi
            cp "${EXPORTER_SSH_SERVER_DIR}/authorized_keys" /root/.ssh/authorized_keys
            chmod 600 /root/.ssh/authorized_keys
            ;;
        password)
            exporter_password="${EXPORTER_SSH_PASSWORD:-}"
            if [ -z "${exporter_password}" ] && [ -n "${EXPORTER_SSH_PASSWORD_FILE:-}" ] && [ -f "${EXPORTER_SSH_PASSWORD_FILE}" ]; then
                exporter_password="$(cat "${EXPORTER_SSH_PASSWORD_FILE}")"
            fi
            if [ -z "${exporter_password}" ]; then
                echo "Missing EXPORTER_SSH_PASSWORD or EXPORTER_SSH_PASSWORD_FILE for ${EXPORTER_NAME}"
                exit 1
            fi
            echo "root:${exporter_password}" | chpasswd
            rm -f /root/.ssh/authorized_keys
            sed -i \
                -e 's/^PubkeyAuthentication .*/PubkeyAuthentication no/' \
                -e 's/^PasswordAuthentication .*/PasswordAuthentication yes/' \
                /etc/ssh/sshd_config
            ;;
        *)
            echo "Unsupported EXPORTER_SSH_AUTH_MODE '${EXPORTER_SSH_AUTH_MODE}'"
            exit 1
            ;;
    esac

    echo "Starting SSH daemon for ${EXPORTER_NAME}..."
    /usr/sbin/sshd -e
}

configure_exporter_ssh

echo "Waiting for coordinator at ${COORDINATOR_URL}..."
sleep 5

COORDINATOR_HOST_PORT=$(echo "${COORDINATOR_URL}" | sed 's|ws://||' | sed 's|/ws$||')

echo "Starting labgrid-exporter..."
echo "  Coordinator: ${COORDINATOR_HOST_PORT}"

if [ "${EXPORTER_ISOLATED:-0}" = "1" ]; then
    EXPORTER_RUNTIME_HOSTNAME="${EXPORTER_HOSTNAME:-${EXPORTER_NAME}}"
    echo "  Isolated mode: enabled (${EXPORTER_RUNTIME_HOSTNAME})"
    exec labgrid-exporter -c "${COORDINATOR_HOST_PORT}" \
        --name "${EXPORTER_NAME}" \
        --isolated \
        --hostname "${EXPORTER_RUNTIME_HOSTNAME}" \
        /config/exporter.yaml
fi

echo "  Isolated mode: disabled"
exec labgrid-exporter -c "${COORDINATOR_HOST_PORT}" \
    --name "${EXPORTER_NAME}" \
    /config/exporter.yaml
