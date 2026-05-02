---
name: "Release Files"
description: "Use when reviewing or editing version metadata, release notes, docker publish workflow, fork install docs, or release automation. Keeps release-owned files aligned and supports review-first fork maintenance workflows."
applyTo:
  - "pyproject.toml"
  - "hermes_cli/__init__.py"
  - "scripts/release.py"
  - "RELEASE_v*.md"
  - ".github/workflows/docker-publish.yml"
  - "INSTALL.md"
  - "docker/deploy.sh"
---

# Release File Guidelines

- Keep the version string synchronized between [pyproject.toml](../../pyproject.toml) and [hermes_cli/__init__.py](../../hermes_cli/__init__.py).
- When the task is review-first, verify the live upstream branch or release line before declaring the repo current. Separate branch commit lag from version-file lag.
- Prefer [scripts/release.py](../../scripts/release.py) for release bumping, tag generation, and changelog preparation instead of ad hoc release edits.
- When updating release notes, follow the existing `RELEASE_vX.Y.Z.md` pattern and keep the file aligned with the actual version being shipped.
- Remember that [.github/workflows/docker-publish.yml](../workflows/docker-publish.yml) only publishes Docker images on `NousResearch/hermes-agent`; fork validation must be done locally. Keep that distinct from the regular coverage in [.github/workflows/tests.yml](../workflows/tests.yml).
- If [INSTALL.md](../../INSTALL.md) or [docker/deploy.sh](../../docker/deploy.sh) includes fork-specific clone or curl URLs, update those references consistently when the fork target changes.
- When explaining why the fork exists, ground the answer in [INSTALL.md](../../INSTALL.md), [docker-compose.yml](../../docker-compose.yml), and [docker/deploy.sh](../../docker/deploy.sh) instead of broad speculation.
- For review requests about release readiness or version drift, stop after the analysis and proposed next steps. Do not run fetch, merge, rebuild, deploy, or upgrade commands until the user approves a plan.
- Call out dirty or untracked maintenance customizations when they affect the repo-state story.
- Do not broaden release guidance into general docs; link to [INSTALL.md](../../INSTALL.md), [AGENTS.md](../../AGENTS.md), and existing release files instead of duplicating them.
