---
name: "Fork Sync Checklist"
description: "Review the current codebase state, compare local or fork main with live upstream, review any current local PR or fork-only delta that must survive the sync, determine whether the repo is behind the requested release line such as 0.11.x, explain the fork-specific implementation, and stop before any runtime refresh or upgrade."
argument-hint: "[target branch, release line, or version]"
agent: "agent"
---

Use the maintenance workflow in [fork-maintenance](../skills/fork-maintenance/SKILL.md) to inspect the current repository state and prepare a no-surprises sync report. When validation planning is needed, prefer the fork-wrapper pull-only guidance in [docker-compose-smoke-test](../skills/docker-compose-smoke-test/SKILL.md). Use [docker-compose.upstream.yml](../../docker-compose.upstream.yml) only when the user explicitly wants to compare against the raw published upstream image.

Ground the report in the existing repo sources of truth:

- [AGENTS.md](../../AGENTS.md)
- [INSTALL.md](../../INSTALL.md)
- [pyproject.toml](../../pyproject.toml)
- [hermes_cli/__init__.py](../../hermes_cli/__init__.py)
- [scripts/release.py](../../scripts/release.py)
- [docker-compose.yml](../../docker-compose.yml)
- [docker-compose.upstream.yml](../../docker-compose.upstream.yml)
- [docker/deploy.sh](../../docker/deploy.sh)
- [.github/PULL_REQUEST_TEMPLATE.md](../PULL_REQUEST_TEMPLATE.md)
- [.github/workflows/docker-publish.yml](../workflows/docker-publish.yml)
- [.github/workflows/tests.yml](../workflows/tests.yml)

Return exactly these sections:

1. `Repository state`
   Include branch, worktree cleanliness, remotes, local `HEAD`, `origin/main`, live `upstream/main`, how upstream was verified, and which local PR branch, review worktree, or pending fork work was inspected.
2. `Local PR and fork-delta review`
   Identify the current local PRs, pending review branches, or fork-only changes that must remain on `fork/main`. Separate intentional fork behavior from stale carry-over, and call out any overlap with the incoming upstream commits.
3. `Release-line status`
   Separate commit lag from version-file lag. Compare the version-owned files against the requested or latest upstream release line, such as `0.11.x`, and call out missing or stale `RELEASE_v*.md` coverage.
4. `Fork-specific implementation`
   Explain why this fork exists, which files implement that difference, and whether the delta is still justified.
5. `Approval-gated next steps`
   Give the exact commands that would be used to fetch, merge, review, or refresh the runtime, but keep them clearly separated from the read-only findings. Default to `docker compose pull` and `docker compose up -d` for wrapper validation, and use `docker-compose.upstream.yml` only when explicitly comparing against the raw published upstream image.
6. `Validation and risk notes`
   Include local Docker Compose follow-up, wrapper runtime preference, upstream-only Docker publish caveats, normal test-workflow coverage, dirty or untracked customization files, and blockers that require approval before fetch, merge, stash, push, runtime refresh, or upgrade.

End the report by stating that no runtime refresh, upgrade, fetch, merge, stash, push, PR merge, or Docker Compose action has been run and that you are waiting for the user's advice or plan.

Constraints:

- Do not modify files unless the user explicitly asks for edits.
- Do not run destructive git commands.
- Default to read-only checks. Prefer `git ls-remote` or GitHub web or API verification when local tracking refs may be stale.
- Do not run `git fetch`, `git merge`, `git stash`, `git pull`, `git push`, `docker compose pull`, `docker compose up -d`, installer scripts, or version-bump commands without explicit user approval.
- Do not treat fork-owned install, compose, deploy, prompt, or skill files as disposable just because upstream differs; explain what must be preserved.
- Prefer `docker compose pull` and `docker compose up -d` for no-build runtime validation of the fork wrapper. Use `docker-compose.upstream.yml` only when explicitly comparing against the raw published upstream image.
- If the requested version is already present, say that clearly instead of proposing a bump.
- Prefer the repo-documented workflow over invented commands.
