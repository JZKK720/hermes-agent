---
name: fork-maintenance
description: "Review the current codebase state, compare local or fork main with live upstream, review current local PR or fork-only deltas before sync, verify whether the repo is behind the requested release line such as 0.11.x, preserve intentional fork changes, and wait for approval before any fetch, merge, or runtime refresh work."
argument-hint: "[target version, release line, or maintenance task]"
user-invocable: true
---

# Fork Maintenance

Use this skill for repository maintenance tasks that combine git comparison, version alignment, release prep, and deployment-wrapper validation against the published upstream image.

## Read First

Start from the repo's existing sources of truth instead of re-deriving the workflow:

- [AGENTS.md](../../../AGENTS.md) for the repo-wide guardrails and test wrapper requirement.
- [INSTALL.md](../../../INSTALL.md) for fork sync and Docker Compose commands.
- [docker-compose.yml](../../../docker-compose.yml) for service names, ports, and env handling.
- [docker-compose.upstream.yml](../../../docker-compose.upstream.yml) for comparing the fork wrapper against the raw published upstream image when needed.
- [docker/deploy.sh](../../../docker/deploy.sh) for fork-specific deployment behavior.
- [docker/hermes-env.example](../../../docker/hermes-env.example) for the local env template.
- [.github/PULL_REQUEST_TEMPLATE.md](../../../.github/PULL_REQUEST_TEMPLATE.md) for the repo's PR checklist expectations.
- [scripts/release.py](../../../scripts/release.py) for release bump and tag generation.
- [RELEASE_v0.10.0.md](../../../RELEASE_v0.10.0.md) as an example of the current release notes pattern. Verify whether a newer `RELEASE_v*.md` file exists before treating `0.10.0` as current.
- [pyproject.toml](../../../pyproject.toml) and [hermes_cli/__init__.py](../../../hermes_cli/__init__.py) for version ownership.
- [.github/workflows/docker-publish.yml](../../../.github/workflows/docker-publish.yml) for fork-vs-upstream CI behavior.
- [.github/workflows/tests.yml](../../../.github/workflows/tests.yml) for non-publish CI behavior on branches and PRs.

## When to Use

- Review the entire codebase state before deciding whether a fork sync or runtime refresh is needed.
- Review the currently active local PR work, checked-out review branch, or fork-only delta before proposing an upstream sync.
- Review a build or release before merging.
- Compare `origin/main` with `upstream/main`.
- Determine whether the local repo or fork is behind a release line such as `0.11.x`.
- Explain why the fork exists and what fork-specific implementation it still carries.
- Protect intentional fork-owned files such as install docs, compose files, deploy scripts, prompts, and skills from being blindly overwritten by upstream.
- Validate the fork's Docker Compose wrapper stack with a local env file.
- Check whether a fork push will get the same CI coverage as upstream.

## Procedure

### 1. Establish repository state first, with a read-only default

Run read-only checks before proposing changes:

```bash
git status --short --branch
git remote -v
git rev-parse HEAD
git rev-parse origin/main
git ls-remote upstream refs/heads/main
```

Summarize:

- whether `upstream` is configured;
- the local `HEAD`, `origin/main`, and live `upstream/main` commit ids;
- whether the fork is ahead or behind upstream;
- whether the worktree is dirty or has untracked customization files that could complicate a merge or stash.

Do not rely only on cached local tracking refs when answering upstream status. If GitHub smart-HTTP is flaky on this machine, fall back to live GitHub web or API checks before declaring the fork current.

If the repo has local changes, do not assume stashing, resetting, merging, or refreshing containers is safe. Ask before any state-changing operation.

### 2. Review local PR work and fork-only deltas before proposing sync

When the request mentions local PRs, pending review work, or preserving fork behavior:

- inspect the active PR, checked-out PR branch, or local review worktree before proposing a merge plan;
- separate fork-owned changes that must remain on `fork/main` from generic upstream drift;
- call out whether each delta is an intentional fork customization, a candidate for upstreaming, or stale carry-over that should be reconsidered;
- treat [INSTALL.md](../../../INSTALL.md), [docker-compose.yml](../../../docker-compose.yml), [docker-compose.upstream.yml](../../../docker-compose.upstream.yml), [docker/deploy.sh](../../../docker/deploy.sh), and repo-local prompts or skills under `.github/` as fork-owned surfaces unless the diff proves otherwise.

Do not recommend syncing away fork-owned changes just because upstream differs. The review must preserve the local env contract, host ports, and other deliberate fork behavior unless the user explicitly chooses to drop them.

### 3. Verify version and release ownership

Treat these files as the authoritative release inputs:

- [pyproject.toml](../../../pyproject.toml)
- [hermes_cli/__init__.py](../../../hermes_cli/__init__.py)

Keep the version string synchronized in both places. Before editing, confirm the current version so you do not propose a no-op upgrade when the repo is already on the requested version.

Separate these two questions in the report:

- whether the branch is commit-behind live `upstream/main`;
- whether the version-owned files are behind the requested or latest upstream release line, such as `0.11.x`.

Use [scripts/release.py](../../../scripts/release.py) for release prep when the task includes bumping versions, generating changelog text, or publishing a release. Do not hand-edit tags or release metadata first if the script already owns that workflow.

### 4. Explain the fork-specific implementation before proposing sync

Ground the explanation in the files that actually carry the fork delta:

- [INSTALL.md](../../../INSTALL.md)
- [docker-compose.yml](../../../docker-compose.yml)
- [docker/deploy.sh](../../../docker/deploy.sh)

Summarize the practical reason the fork exists, which files implement that difference, and whether the delta is narrow or broad relative to upstream.

### 5. Stop for approval before any sync or runtime refresh

For review-first requests, stop after the analysis and proposed next steps. Do not run `git fetch`, `git stash`, `git merge`, `git pull`, `git push`, `docker compose pull`, `docker compose up -d`, `docker compose -f docker-compose.upstream.yml up -d`, installer scripts, or version-bump commands until the user approves a plan.

### 6. Follow the documented fork sync path after approval

When the user wants the fork updated from upstream, prefer the sequence already documented in [INSTALL.md](../../../INSTALL.md):

```bash
git fetch upstream
git stash push -u -m "local-changes"
git merge upstream/main --no-edit
git stash pop
git push origin main
docker compose pull
docker compose up -d
```

Adjust this flow to the actual repo state:

- skip the stash steps when there are no local changes;
- do not run stash or merge steps without user approval if there is any risk of conflict;
- explain conflicts and blockers before continuing;
- if local PR work must be preserved, spell out whether that work should be rebased, re-reviewed, or merged after the upstream sync instead of assuming a direct fast-forward into `fork/main`.

### 7. Use the fork deployment wrapper for routine runtime validation

When the goal is install/runtime validation, fork-sync confidence, or routine wrapper updates, default to the documented fork deployment wrapper:

```bash
docker compose pull
docker compose up -d
```

This keeps the local `data/.env`, `data/config.yaml`, persisted data, and host ports (`9119`, `8789`, `8644`, `5433`) while upgrading the Hermes containers through the fork-owned wrapper around `nousresearch/hermes-agent:latest`.

If the user explicitly wants to compare the wrapper against the raw published upstream image without the fork-local entrypoint overlay, use [docker-compose.upstream.yml](../../../docker-compose.upstream.yml):

```bash
docker compose -f docker-compose.upstream.yml pull
docker compose -f docker-compose.upstream.yml up -d
```

### 8. Use the documented deployment-wrapper workflow after approval

For local stack bring-up, use the repo's `data/.env` convention:

```bash
mkdir -p data
cp docker/hermes-env.example data/.env
docker compose pull
docker compose up -d
```

Important checks:

- `data/.env` is local runtime state and should not be committed.
- `data/config.yaml` is bootstrapped on first start from `docker/hermes-config.yaml`.
- `docker compose pull` plus `docker compose up -d` is the expected update path for this fork's deployment wrapper.
- `docker exec -it hermes-web hermes` is the documented interactive smoke test.

Useful follow-up commands:

```bash
docker compose ps
docker compose logs -f hermes-web
docker compose logs -f hermes-gateway
docker exec -it hermes-web hermes
```

### 9. Validate with the repo's CI-parity test path

Prefer the wrapper from [scripts/run_tests.sh](../../../scripts/run_tests.sh):

```bash
scripts/run_tests.sh
scripts/run_tests.sh tests/gateway/
scripts/run_tests.sh -v --tb=long
```

Do not default to `pytest` directly. [AGENTS.md](../../../AGENTS.md) documents that the wrapper normalizes env vars, locale, timezone, and worker count to match CI.

### 10. Account for fork-specific CI behavior

[.github/workflows/docker-publish.yml](../../../.github/workflows/docker-publish.yml) only runs its Docker job when `github.repository == 'NousResearch/hermes-agent'`.

Implications:

- fork pushes and PRs do not get the same Docker publish validation as upstream;
- [.github/workflows/tests.yml](../../../.github/workflows/tests.yml) still provides regular test coverage on branch pushes and PRs;
- local Docker Compose validation matters more on forks;
- do not assume a fork PR exercised the publish path.

## Guardrails

- Native Windows is not the supported runtime path in the main README; prefer WSL2-oriented guidance when the user is on Windows.
- Do not commit `data/.env`, generated `data/config.yaml`, or other local runtime state.
- Do not overwrite fork-owned install and deployment surfaces just to match upstream; justify each retained or removed fork delta explicitly.
- If you are working in a different fork, audit hardcoded fork URLs in [INSTALL.md](../../../INSTALL.md) and [docker/deploy.sh](../../../docker/deploy.sh) before suggesting one-line install commands.
- Call out dirty or untracked customization files when they affect the maintenance story.
- Do not use destructive git commands such as `git reset --hard` unless the user explicitly asks.
- When a doc conflicts with repo instructions, prefer the newer repo-owned workflow files and the current AGENTS guidance.

## Expected Output Shape

For maintenance requests in this area, structure the response in this order:

1. current repository state, including local `HEAD`, `origin/main`, live `upstream/main`, and worktree cleanliness;
2. local PR or fork-delta review, including what must remain on `fork/main`;
3. release-line status, including commit lag versus version-file lag;
4. fork-specific implementation and whether it still justifies the fork;
5. approval-gated next steps, with sync or runtime-refresh commands separated from the read-only findings;
6. blockers, risks, and the explicit statement that execution is paused pending user approval.
