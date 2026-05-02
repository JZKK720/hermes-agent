#!/bin/bash
# Docker/Podman entrypoint: bootstrap config files into the mounted volume, then run hermes.
set -e

HERMES_HOME="${HERMES_HOME:-/opt/data}"
INSTALL_DIR="/opt/hermes"

# --- Privilege dropping via gosu ---
# When started as root (the default for Docker, or fakeroot in rootless Podman),
# optionally remap the hermes user/group to match host-side ownership, fix volume
# permissions, then re-exec as hermes.
if [ "$(id -u)" = "0" ]; then
    if [ -n "$HERMES_UID" ] && [ "$HERMES_UID" != "$(id -u hermes)" ]; then
        echo "Changing hermes UID to $HERMES_UID"
        usermod -u "$HERMES_UID" hermes
    fi

    if [ -n "$HERMES_GID" ] && [ "$HERMES_GID" != "$(id -g hermes)" ]; then
        echo "Changing hermes GID to $HERMES_GID"
        # -o allows non-unique GID (e.g. macOS GID 20 "staff" may already exist
        # as "dialout" in the Debian-based container image)
        groupmod -o -g "$HERMES_GID" hermes 2>/dev/null || true
    fi

    # Fix ownership of the data volume. When HERMES_UID remaps the hermes user,
    # files created by previous runs (under the old UID) become inaccessible.
    # Always chown -R when UID was remapped; otherwise only if top-level is wrong.
    actual_hermes_uid=$(id -u hermes)
    needs_chown=false
    if [ -n "$HERMES_UID" ] && [ "$HERMES_UID" != "10000" ]; then
        needs_chown=true
    elif [ "$(stat -c %u "$HERMES_HOME" 2>/dev/null)" != "$actual_hermes_uid" ]; then
        needs_chown=true
    fi
    if [ "$needs_chown" = true ]; then
        echo "Fixing ownership of $HERMES_HOME to hermes ($actual_hermes_uid)"
        # In rootless Podman the container's "root" is mapped to an unprivileged
        # host UID — chown will fail.  That's fine: the volume is already owned
        # by the mapped user on the host side.
        chown -R hermes:hermes "$HERMES_HOME" 2>/dev/null || \
            echo "Warning: chown failed (rootless container?) — continuing anyway"
    fi

    # Ensure the web UI source dir is owned by the (possibly remapped) hermes UID
    # so that _build_web_ui can run npm install/build at startup.
    if [ "$(stat -c %u "$INSTALL_DIR/web" 2>/dev/null)" != "$actual_hermes_uid" ]; then
        chown -R hermes:hermes "$INSTALL_DIR/web"
    fi

    # Pre-create vite's output dir (../hermes_cli/web_dist) so hermes can write to it.
    # Without this, vite fails with EACCES because hermes_cli/ is owned by the old UID.
    # Use -R so pre-built files from the image layer are also chowned to the correct UID.
    mkdir -p "$INSTALL_DIR/hermes_cli/web_dist"
    chown -R hermes:hermes "$INSTALL_DIR/hermes_cli/web_dist"

    # Ensure config.yaml is readable by the hermes runtime user even if it was
    # edited on the host after initial ownership setup. Must run here (as root)
    # rather than after the gosu drop, otherwise a non-root caller like
    # `docker run -u $(id -u):$(id -g)` hits "Operation not permitted" (#15865).
    if [ -f "$HERMES_HOME/config.yaml" ]; then
        chown hermes:hermes "$HERMES_HOME/config.yaml" 2>/dev/null || true
        chmod 640 "$HERMES_HOME/config.yaml" 2>/dev/null || true
    fi
    echo "Dropping root privileges"
    exec gosu hermes "$0" "$@"
fi

# --- Running as hermes from here ---
source "${INSTALL_DIR}/.venv/bin/activate"

# Create essential directory structure.  Cache and platform directories
# (cache/images, cache/audio, platforms/whatsapp, etc.) are created on
# demand by the application - don't pre-create them here so new installs
# get the consolidated layout from get_hermes_dir().
# The "home/" subdirectory is a per-profile HOME for subprocesses (git,
# ssh, gh, npm, etc.).  Without it those tools write to /root which is
# ephemeral and shared across profiles.  See issue #4426.
mkdir -p "$HERMES_HOME"/{cron,sessions,logs,hooks,memories,skills,skins,plans,workspace,home}

# .env
if [ ! -f "$HERMES_HOME/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$HERMES_HOME/.env"
fi

# config.yaml
if [ ! -f "$HERMES_HOME/config.yaml" ]; then
    cp "$INSTALL_DIR/cli-config.yaml.example" "$HERMES_HOME/config.yaml"
fi

# Ensure the main config file remains accessible to the hermes runtime user
# even if it was edited on the host after initial ownership setup.
if [ -f "$HERMES_HOME/config.yaml" ]; then
    chown hermes:hermes "$HERMES_HOME/config.yaml"
    chmod 640 "$HERMES_HOME/config.yaml"
fi

# SOUL.md
if [ ! -f "$HERMES_HOME/SOUL.md" ]; then
    cp "$INSTALL_DIR/docker/SOUL.md" "$HERMES_HOME/SOUL.md"
fi

# Fail fast when this Docker profile is configured to use the host-local Ollama
# endpoint. That avoids Hermes booting into a broken state when Ollama is down.
require_local_ollama() {
    local probe_url

    if ! probe_url="$(HERMES_HOME="$HERMES_HOME" python3 - <<'PY'
from pathlib import Path
import os
import urllib.parse

try:
    import yaml
except Exception:
    raise SystemExit(0)

config_path = Path(os.environ["HERMES_HOME"]) / "config.yaml"
if not config_path.exists():
    raise SystemExit(0)

try:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
except Exception:
    raise SystemExit(0)

model = data.get("model") or {}
provider = str(model.get("provider") or "").strip().lower()
base_url = str(model.get("base_url") or "").strip()

if provider not in {"custom", "ollama"} or not base_url:
    raise SystemExit(0)

normalized = base_url.lower()
if not any(host in normalized for host in (
    "host.docker.internal:11434",
    "127.0.0.1:11434",
    "localhost:11434",
)):
    raise SystemExit(0)

parsed = urllib.parse.urlparse(base_url)
if not parsed.netloc:
    raise SystemExit(0)

scheme = parsed.scheme or "http"
print(f"{scheme}://{parsed.netloc}/api/tags")
PY
)"; then
        return 0
    fi

    [ -z "$probe_url" ] && return 0

    if python3 - "$probe_url" >/dev/null 2>&1 <<'PY'
import sys
import urllib.request

url = sys.argv[1]
with urllib.request.urlopen(url, timeout=5) as resp:
    status = getattr(resp, "status", None) or resp.getcode()
    if not 200 <= status < 300:
        raise RuntimeError(f"HTTP {status}")
PY
    then
        echo "Verified Ollama availability at $probe_url"
        return 0
    fi

    echo "Error: Hermes is configured to use local Ollama at $probe_url, but it is not reachable."
    echo "Start Ollama first (for example: ollama serve) and then restart the container."
    exit 1
}

# Sync bundled skills (manifest-based so user edits are preserved)
if [ -d "$INSTALL_DIR/skills" ]; then
    python3 "$INSTALL_DIR/tools/skills_sync.py"
fi

# Final exec: two supported invocation patterns.
#
#   docker run <image>                 -> exec `hermes` with no args (legacy default)
#   docker run <image> chat -q "..."   -> exec `hermes chat -q "..."` (legacy wrap)
#   docker run <image> sleep infinity  -> exec `sleep infinity` directly
#   docker run <image> bash            -> exec `bash` directly
#
# If the first positional arg resolves to an executable on PATH, we assume the
# caller wants to run it directly (needed by the launcher which runs long-lived
# `sleep infinity` sandbox containers — see tools/environments/docker.py).
# Otherwise we treat the args as a hermes subcommand and wrap with `hermes`,
# preserving the documented `docker run <image> <subcommand>` behavior.
if [ $# -gt 0 ] && [ "$1" = "hermes" ]; then
    shift
    require_local_ollama
    exec hermes "$@"
fi

if [ $# -gt 0 ] && command -v "$1" >/dev/null 2>&1; then
    exec "$@"
fi

require_local_ollama
exec hermes "$@"
