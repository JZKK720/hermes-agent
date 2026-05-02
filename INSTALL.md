# Hermes-Agent — Installation Guide

Deploy the JZKK720/hermes-agent fork with Ollama and PostgreSQL using Docker Compose.

## Prerequisites

| Requirement | Install |
|---|---|
| Docker + Docker Compose v2 | https://docs.docker.com/get-docker/ |
| Git | https://git-scm.com/ |
| Ollama | https://ollama.com/ |

### Pull the default model

```bash
ollama pull gemma4:e4b-it-q8_0
```

To use a different model, follow the [Change the model](#change-the-model) section after install.

---

## Quick Install (one command)

```bash
curl -fsSL https://raw.githubusercontent.com/JZKK720/hermes-agent/main/docker/deploy.sh | bash
```

The script clones the repo, seeds `data/.env`, pulls `nousresearch/hermes-agent:latest`, and starts all services.

---

## Manual Install

### 1. Clone the fork

```bash
git clone https://github.com/JZKK720/hermes-agent.git
cd hermes-agent
```

### 2. Create the data directory and env file

```bash
mkdir -p data
cp docker/hermes-env.example data/.env
```

Edit `data/.env` if needed (see [Configuration](#configuration) below). For a plain Ollama setup no changes are required.

### 3. Start all services

```bash
docker compose pull
docker compose up -d
```

This stack now runs the upstream `nousresearch/hermes-agent:latest` image while keeping the fork-local `docker/hermes-config.yaml` and `docker/entrypoint.sh` overlays mounted.

---

## Services

| Service | URL | Description |
|---|---|---|
| Hermes Web UI | http://localhost:9119 | Chat interface |
| OpenSpace agent API | http://localhost:8789/v1 | OpenAI-compatible API endpoint |
| Gateway webhook | :8644 | Platform webhook receiver |
| PostgreSQL | localhost:5433 | Internal database (host port 5433) |

### Interactive CLI

```bash
docker exec -it hermes-web hermes
```

### Useful commands

```bash
docker compose logs -f             # stream logs from all services
docker compose logs -f hermes-web  # web UI logs only
docker compose down                # stop all services
docker compose pull                # fetch the latest upstream Hermes image
docker compose up -d               # start or refresh containers with the pulled image
```

---

## Configuration

### `data/.env` — secrets (never committed to git)

| Variable | Purpose | Required |
|---|---|---|
| `API_SERVER_KEY` | Bearer token securing `:8789` (OpenSpace endpoint) | No — open if unset |
| `TELEGRAM_BOT_TOKEN` | Telegram gateway | Optional |
| `DISCORD_BOT_TOKEN` | Discord gateway | Optional |
| `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN` | Slack gateway | Optional |
| `EXA_API_KEY` | AI-native web search | Optional |

### `data/config.yaml` — runtime settings

Auto-created from `docker/hermes-config.yaml` on first start.  
Edit directly; no rebuild needed — takes effect on next container restart.

### Change the model

Edit `data/config.yaml`:

```yaml
model:
  default: "llama3.3:70b"        # any model pulled in Ollama
  context_length: 131072
```

Then restart the containers:

```bash
docker compose restart hermes-web hermes-gateway
```

---

## Keeping Up to Date

### Pull upstream changes

```bash
git fetch upstream
git stash push -u -m "local-changes"
git merge upstream/main --no-edit
git stash pop
git push origin main
docker compose pull
docker compose up -d
```

### Pull your own fork changes (on a second machine)

```bash
git pull origin main
docker compose pull
docker compose up -d
```
---

## Troubleshooting

### Web UI not reachable

```bash
docker compose ps              # check service state
docker compose logs hermes-web # read startup output
```

### Model calls fail / "unknown provider"

Ensure Ollama is running on the host and the model is pulled:

```bash
ollama list
ollama pull gemma4:e4b-it-q8_0
```

Check `data/config.yaml` has `provider: "custom"` (not `"ollama"`).

### Permission errors on `web_dist/`

The `entrypoint.sh` runs `chown -R` on startup. If it still fails:

```bash
docker compose down
docker compose pull
docker compose up -d
```

### Reset everything (start fresh)

```bash
docker compose down -v   # removes named volumes
rm -rf data/             # removes persisted data (config, sessions, memories)
docker compose pull
docker compose up -d
```

---

## Ports Reference

| Port (host) | Port (container) | Service |
|---|---|---|
| 9119 | 9119 | Hermes Web UI |
| 8789 | 8789 | OpenSpace API (OpenAI-compatible) |
| 8644 | 8644 | Gateway webhook |
| 5433 | 5432 | PostgreSQL |
