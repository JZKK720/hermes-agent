#!/usr/bin/env bash
# docker/start-all.sh — Self-contained single-container entrypoint (optional).
#
# RECOMMENDED: Use the two-service docker-compose.yml instead (hermes-web +
# hermes-gateway run independently so Docker can restart each on failure).
#
# WHEN TO USE THIS SCRIPT:
#   When you need everything in ONE container, override the entrypoint:
#
#     docker run --entrypoint /opt/hermes/docker/start-all.sh \
#       -e HERMES_UID=1000 -e OPENAI_API_KEY=ollama \
#       -p 9119:9119 -p 8789:8789 -p 8644:8644 \
#       -v "$(pwd)/data:/opt/data" \
#       hermes-agent
#
#   Or in docker-compose (single-service override):
#     services:
#       hermes:
#         build: .
#         entrypoint: ["/opt/hermes/docker/start-all.sh"]
#         command: []
#         ports: ["9119:9119", "8789:8789", "8644:8644"]
#         volumes: ["./data:/opt/data", "./docker/hermes-config.yaml:/opt/hermes/cli-config.yaml.example:ro"]
#         environment: [HERMES_UID=1000, OPENAI_API_KEY=ollama]
#         extra_hosts: ["host.docker.internal:host-gateway"]
#
# This script replicates the bootstrap steps from docker/entrypoint.sh, then
# starts hermes web and hermes gateway as background processes in one container.

set -euo pipefail

HERMES_UID=${HERMES_UID:-10000}
DATA_DIR="/opt/data"
VENV="/opt/hermes/venv"

log() { echo "[hermes] $*"; }

# ── Privilege drop (when running as root) ────────────────────────────────────
if [ "$(id -u)" = "0" ]; then
    chown -R "${HERMES_UID}:${HERMES_UID}" "$DATA_DIR" 2>/dev/null || true
    exec gosu "${HERMES_UID}" "$0" "$@"
fi

# ── Activate venv ─────────────────────────────────────────────────────────────
# shellcheck disable=SC1091
source "${VENV}/bin/activate"

# ── Ensure data directories exist ─────────────────────────────────────────────
mkdir -p "${DATA_DIR}"/{sessions,logs,memories,skills,cron}

# ── Bootstrap config, .env, SOUL.md (first-run only) ─────────────────────────
if [ ! -f "${DATA_DIR}/config.yaml" ] && [ -f /opt/hermes/cli-config.yaml.example ]; then
    cp /opt/hermes/cli-config.yaml.example "${DATA_DIR}/config.yaml"
    log "Bootstrapped config.yaml"
fi
if [ ! -f "${DATA_DIR}/.env" ] && [ -f /opt/hermes/.env.example ]; then
    cp /opt/hermes/.env.example "${DATA_DIR}/.env"
fi
if [ ! -f "${DATA_DIR}/SOUL.md" ] && [ -f /opt/hermes/docker/SOUL.md ]; then
    cp /opt/hermes/docker/SOUL.md "${DATA_DIR}/SOUL.md"
fi

# ── Sync bundled skills ───────────────────────────────────────────────────────
SKILLS_SYNC="/opt/hermes/scripts/skills_sync.py"
if [ -f "${SKILLS_SYNC}" ]; then
    python "${SKILLS_SYNC}" 2>/dev/null || true
fi

# ── Web UI ────────────────────────────────────────────────────────────────────
log "Starting web UI on :9119 ..."
hermes web --host 0.0.0.0 --port 9119 &
WEB_PID=$!

# ── Wait for web to be ready before starting gateway ─────────────────────────
log "Waiting for web UI to be ready..."
for _i in $(seq 1 30); do
    curl -sf http://127.0.0.1:9119/health >/dev/null 2>&1 && break
    sleep 1
done

# ── Gateway (api_server :8789 + webhook :8644) ────────────────────────────────
log "Starting gateway (api_server :8789 | webhook :8644) ..."
hermes gateway &
GW_PID=$!

log "All services running."
log "  Web UI              : http://0.0.0.0:9119"
log "  OpenSpace agent API : http://0.0.0.0:8789/v1  (OpenAI-compatible)"
log "  Webhook             : :8644"
log "  CLI                 : docker exec -it <container> hermes"

# ── Graceful shutdown ─────────────────────────────────────────────────────────
_shutdown() {
    log "Shutdown signal — stopping services..."
    kill "${WEB_PID}" "${GW_PID}" 2>/dev/null || true
    wait "${WEB_PID}" "${GW_PID}" 2>/dev/null || true
    exit 0
}
trap _shutdown SIGTERM SIGINT

# Block until any child exits (compose will restart the container)
wait "${WEB_PID}" "${GW_PID}"
