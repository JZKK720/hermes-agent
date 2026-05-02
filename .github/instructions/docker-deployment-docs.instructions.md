---
description: "Use when editing docker-compose.yml, INSTALL.md, docker deploy scripts, or deployment comments for the Ollama/OpenSpace stack. Keeps Docker docs aligned with the actual image source, state-preserving update commands, and mounted local customizations."
name: "Docker Deployment Docs"
applyTo:
  - "docker-compose.yml"
  - "INSTALL.md"
  - "docker/*.sh"
  - "docker/*.yaml"
---

# Docker Deployment Docs

- Keep deployment comments and install docs aligned with the real compose behavior. If the stack uses upstream images, the docs should prefer `docker compose pull` and `docker compose up -d`, not `--build`.
- Do not describe Hermes upstream images as GHCR-backed unless you have re-verified a public GHCR tag. The validated upstream publish target in this repo is `nousresearch/hermes-agent`.
- Preserve mention of fork-local overlays when they exist. In this repo, [docker/entrypoint.sh](../../docker/entrypoint.sh) and [docker/hermes-config.yaml](../../docker/hermes-config.yaml) stay bind-mounted even after moving off local image builds.
- Treat `data/.env`, `data/config.yaml`, and the PostgreSQL volume as persistent state in both docs and commands. Avoid suggesting `docker compose down -v` except for explicit reset instructions.
- When changing update instructions, include a smoke-test step that checks `docker compose ps`, the dashboard status endpoint, and the API endpoint used by OpenSpace.