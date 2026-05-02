---
description: "Use when syncing this fork with upstream main, comparing fork divergence, migrating docker-compose from local image builds to upstream nousresearch/hermes-agent images, preserving data/.env credentials and Postgres state, or smoke-testing container updates."
name: "Fork Maintenance"
applyTo:
  - "docker-compose.yml"
  - "INSTALL.md"
  - "docker/*.sh"
  - "docker/*.yaml"
  - ".github/workflows/docker-publish.yml"
---

# Fork Maintenance

## Start From Current State

- Verify remotes before planning merges. The usual layout in this fork is `origin` for the personal fork and `upstream` for `NousResearch/hermes-agent`, but always confirm with `git remote -v`.
- Read [docker-compose.yml](../../docker-compose.yml), [INSTALL.md](../../INSTALL.md), [docker/hermes-config.yaml](../../docker/hermes-config.yaml), [docker/entrypoint.sh](../../docker/entrypoint.sh), and [docker publish workflow](../workflows/docker-publish.yml) before proposing Docker changes.
- The upstream container reference is [website/docs/user-guide/docker.md](../../website/docs/user-guide/docker.md).

## Safety Rules

- Preserve local runtime state: never overwrite, regenerate, or delete `data/.env`, `data/config.yaml`, `data/SOUL.md`, `data/memories/`, `data/sessions/`, or the `postgres_data` volume unless the user explicitly asks.
- Avoid destructive reset commands like `docker compose down -v` or deleting `data/` during sync or image-migration work.
- Do not push fork-specific deployment changes to `upstream`. Merge or rebase locally, then push only to `origin` unless the user explicitly wants an upstream contribution.
- Treat bind-mounted files as part of the deployment contract. If [docker/entrypoint.sh](../../docker/entrypoint.sh) or [docker/hermes-config.yaml](../../docker/hermes-config.yaml) stays mounted, upstream image updates can still be partially pinned by local files.

## Evaluating Upstream Images

- [docker-compose.yml](../../docker-compose.yml) now targets `nousresearch/hermes-agent:latest` from Docker Hub rather than a local `hermes-agent:local` build.
- The upstream repo publishes `nousresearch/hermes-agent` from [docker publish workflow](../workflows/docker-publish.yml). Do not assume a GHCR image exists for Hermes unless the target registry is explicitly documented or verified.
- If moving to an upstream image, prefer `docker compose pull` plus `docker compose up -d` for future updates.
- Re-check whether local mounts of [docker/entrypoint.sh](../../docker/entrypoint.sh) or [docker/hermes-config.yaml](../../docker/hermes-config.yaml) are still necessary after the migration; they may preserve local fixes but also block future upstream behavior changes.

## Merge and Divergence Checks

- Inspect divergence with `git fetch upstream --prune`, `git fetch origin --prune`, and `git rev-list --left-right --count origin/main...upstream/main` before discussing merge strategy.
- If the fork carries local-only deployment commits, keep them on `origin/main` or a dedicated branch. The safe default is to merge `upstream/main` into the fork, resolve conflicts locally, test, and push back to `origin`.
- If the user wants to review upstream without integrating it yet, compare commits and diffs without rewriting remotes or force-pushing.

## Smoke Test Expectations

- After editing compose or deployment docs, validate with `docker compose config`.
- For upstream-image stacks, use `docker compose pull` then `docker compose up -d`.
- Check `docker compose ps`, the dashboard health endpoint `http://127.0.0.1:9119/api/status`, and the agent API `http://127.0.0.1:8789/v1/models` when available.
- Report any step that would change credentials, rebuild volumes, or replace mounted config before doing it.