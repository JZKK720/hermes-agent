---
name: "Fork Sync Checklist"
description: "Review the current codebase state, compare local or fork main with live upstream, determine whether the repo is behind the requested release line such as 0.11.x, explain the fork-specific implementation, and stop before any rebuild or upgrade."
argument-hint: "[target branch, release line, or version]"
agent: "agent"
---

Use the maintenance workflow in [fork-maintenance](../skills/fork-maintenance/SKILL.md) to inspect the current repository state and prepare a no-surprises sync report.

Ground the report in the existing repo sources of truth:

- [AGENTS.md](../../AGENTS.md)
- [INSTALL.md](../../INSTALL.md)
- [pyproject.toml](../../pyproject.toml)
- [hermes_cli/__init__.py](../../hermes_cli/__init__.py)
- [scripts/release.py](../../scripts/release.py)
- [docker-compose.yml](../../docker-compose.yml)
- [docker/deploy.sh](../../docker/deploy.sh)
- [.github/workflows/docker-publish.yml](../workflows/docker-publish.yml)
- [.github/workflows/tests.yml](../workflows/tests.yml)

Return exactly these sections:

1. `Repository state`
   Include branch, worktree cleanliness, remotes, local `HEAD`, `origin/main`, live `upstream/main`, and how upstream was verified.
2. `Release-line status`
   Separate commit lag from version-file lag. Compare the version-owned files against the requested or latest upstream release line, such as `0.11.x`, and call out missing or stale `RELEASE_v*.md` coverage.
3. `Fork-specific implementation`
   Explain why this fork exists, which files implement that difference, and whether the delta is still justified.
4. `Approval-gated next steps`
   Give the exact commands that would be used to fetch, merge, rebuild, or upgrade, but keep them clearly separated from the read-only findings.
5. `Validation and risk notes`
   Include local Docker Compose follow-up, upstream-only Docker publish caveats, normal test-workflow coverage, dirty or untracked customization files, and blockers that require approval before fetch, merge, stash, push, rebuild, or upgrade.

End the report by stating that no rebuild, upgrade, fetch, merge, stash, push, or Docker Compose action has been run and that you are waiting for the user's advice or plan.

Constraints:

- Do not modify files unless the user explicitly asks for edits.
- Do not run destructive git commands.
- Default to read-only checks. Prefer `git ls-remote` or GitHub web or API verification when local tracking refs may be stale.
- Do not run `git fetch`, `git merge`, `git stash`, `git pull`, `git push`, `docker compose up -d --build`, installer scripts, or version-bump commands without explicit user approval.
- If the requested version is already present, say that clearly instead of proposing a bump.
- Prefer the repo-documented workflow over invented commands.
