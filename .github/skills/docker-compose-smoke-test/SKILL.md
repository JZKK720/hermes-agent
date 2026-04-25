---
name: docker-compose-smoke-test
description: "Bring up Hermes locally with Docker Compose, seed data/.env from docker/hermes-env.example, inspect logs, and smoke test hermes-web, hermes-gateway, and postgres. Use when asked to build locally, validate docker compose, debug container startup, or check local stack health."
argument-hint: "[service or issue to verify]"
user-invocable: true
---

# Docker Compose Smoke Test

Use this skill for local stack validation after code changes or fork sync work.

## Read First

- [docker-compose.yml](../../../docker-compose.yml)
- [INSTALL.md](../../../INSTALL.md)
- [docker/hermes-env.example](../../../docker/hermes-env.example)
- [docker/hermes-config.yaml](../../../docker/hermes-config.yaml)
- [docker/entrypoint.sh](../../../docker/entrypoint.sh)

## When to Use

- Build the local stack after code or dependency changes.
- Confirm that `hermes-web`, `hermes-gateway`, and `postgres` start correctly.
- Debug a failed local bring-up.
- Verify that the stack is usable before pushing a fork update.

## Procedure

### 1. Check prerequisites and environment

- On Windows, prefer WSL2-oriented workflows because the main README does not treat native Windows as the supported runtime path.
- Confirm Docker Engine and Docker Compose are available before changing files or starting containers.
- Treat `data/.env` and generated `data/config.yaml` as local runtime state, not committed source.

### 2. Seed the local env file if needed

Use the repo-documented layout:

```bash
mkdir -p data
cp docker/hermes-env.example data/.env
```

If `data/.env` already exists, inspect it before replacing it.

### 3. Build and start the stack

```bash
docker compose up -d --build
```

This should start:

- `hermes-web` on `:9119`
- `hermes-gateway` on `:8789` and `:8644`
- `postgres` on host port `5433`

### 4. Check status and logs

Use targeted inspection before escalating:

```bash
docker compose ps
docker compose logs --tail=100 hermes-web
docker compose logs --tail=100 hermes-gateway
docker compose logs --tail=100 postgres
```

Focus on:

- healthcheck failures;
- config bootstrap problems in `entrypoint.sh`;
- missing env vars or permission errors;
- port binding conflicts.

### 5. Smoke test the running stack

Validate these expectations:

- `http://127.0.0.1:9119/api/status` returns a healthy status for the web UI.
- `hermes-gateway` binds the OpenAI-compatible API on `:8789`.
- `postgres` reports healthy in `docker compose ps`.
- `docker exec -it hermes-web hermes` is the documented interactive smoke test when an interactive shell is appropriate.

### 6. Shut down safely when needed

Non-destructive stop:

```bash
docker compose down
```

Destructive reset:

```bash
docker compose down -v
```

Do not use the destructive reset unless the user clearly wants volumes and persisted state removed.

## Guardrails

- Prefer repo-documented commands from [INSTALL.md](../../../INSTALL.md) over improvised alternatives.
- Do not overwrite an existing `data/.env` without checking whether it contains local secrets.
- If the stack fails because Ollama or another external dependency is unavailable, report that as an environment blocker rather than guessing at code changes.
- When the stack comes up on a fork, remember that upstream Docker publish CI does not validate the fork automatically.

## Expected Output Shape

1. what was started or skipped;
2. container status summary;
3. health/log findings by service;
4. next action or blocker.
