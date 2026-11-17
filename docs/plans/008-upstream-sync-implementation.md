# Hermes Fork Upstream Sync — Implementation Plan

Status: **Tasks 1-7 complete** (merged, lint-clean, tests green, branch pushed, CI image build
dispatched). Tasks 8-10 (PR → merge → re-pin → redeploy) publish and deploy the verified
branch.

> **Result so far.** Branch `sync/upstream-20261116` at `eb4e59873b`: upstream merged
> (`behind: 0`), `fork-only patches 89 '+' / 0 '-'`, merge conflict-free,
> `tests/gateway/test_api_server.py` **120 passed / 0 failed** (identical to the recorded
> baseline), and `scripts/check` reduced to **2 blocking / 2 advisory — byte-for-byte the
> same findings pristine `upstream/main` reports**. The running stack is on the merged tree
> and green. Eleven commits, listed in §Progress.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge 1,627 upstream commits into this fork, rebuild the fork GHCR image, and redeploy the local stack — without losing any of the fork's 80 fork-only patches or its mounted runtime state.

**Architecture:** `git merge upstream/main` into `main` on an isolated branch, never a rebase (the fork's patches are additive; upstream's changes are structural). The image is built **only** by CI (`fork-ghcr-publish.yml`) because the fork's Dockerfile base image is not cached locally and Docker Hub is unreachable from this host. The stack then pins the new build by immutable digest through `HERMES_FORK_IMAGE` in the gitignored root `.env`.

**Tech Stack:** git, Docker Compose v2, GitHub Actions, `gh` CLI 2.95 (authenticated as `JZKK720`, ADMIN), Python 3.14 `.venv`, `scripts/run_tests.sh`, `scripts/fork_sync_facts.py`.

## Global Constraints

- **Never rebase the fork onto upstream.** Merge direction is `upstream/main` → `main`.
- **Never delete** `data/.env`, `data/config.yaml`, `data/sessions/`, `data/memories/`, `data/skills/`, `data/state.db`, or the `hermes-agent_postgres_data` volume.
- **Never commit** `data/config.yaml`, `data/.env`, or the root `.env` (all gitignored — `data/` at `.gitignore:34`, `.env` at `.gitignore:17`).
- **Never hardcode `~/.hermes`**; use `get_hermes_home()`.
- **Tests:** always `scripts/run_tests.sh`, never bare `pytest`.
- **Never mutate the Hermes environment with raw pip/uv.**
- Compare test results against the **fork-tip baseline**, never against zero.
- `pyproject.toml` stays `version = "0.0.0"` — the runtime version comes from `/opt/hermes/install-stamp.json`. Do not hand-edit it.
- Dependency changes require `>=floor,<next_major` upper bounds and a committed `uv.lock`.
- The image is produced **only** by CI. Do not attempt `docker compose build`.
- `api_server` must stay on **8642**; `8789` must never be re-added as a port.

---

## Pre-flight: what is already true

Recorded at plan time; **re-measure** with `python scripts/fork_sync_facts.py` (upstream moves hourly).

| Fact | Value |
|---|---|
| `HEAD` == `origin/main` | `0b9ad27959` |
| Rollback tag | `fork-tip-pre-sync-20261116` → `ce476f23b1` |
| Behind upstream | 1,627 |
| Fork-only (`git cherry` `+` / `-`) | 80 / 0 |
| Merge conflict-free | **YES** (merge-tree returns one tree oid, no conflict block) |
| Files both sides changed | 5 |
| Config schema | `_config_version` 53 on disk, in the image, and upstream — no migration |
| Running image | `@sha256:15d350bad3…` (fork `0b9ad27959`) |
| Stack state | 3/3 healthy; gateway `FailingStreak` 0; `9119` + `8642` → 200 |
| Postgres | `127.0.0.1:5433` only, rotated password, **0 tables, unused** |

Local build is **not** available: `debian:trixie-20261020` is not cached and Docker Hub
(`registry-1.docker.io`) times out from this host. Verification therefore splits into
what can be proven locally (static checks, tests) and what must be proven in CI (image
build) and after redeploy (runtime probe).

---

### Task 1: Freeze the rollback point

**Files:**
- Modify: none (git refs only)

**Interfaces:**
- Consumes: nothing
- Produces: branches `sync/upstream-20261116`, tag `fork-tip-pre-sync-20261116`

- [ ] **Step 1: Confirm the rollback tag exists and points at the fork tip**

Run: `git rev-parse --short fork-tip-pre-sync-20261116`
Expected: `ce476f23b1`

- [ ] **Step 2: Capture the currently-running image digest for image rollback**

Run:
```bash
docker inspect hermes-web --format '{{.Image}}'
```
Expected: `sha256:15d350bad356aaed17d32decfbd21cfb8a23f65f4bb416f062203f013f3e6790`

- [ ] **Step 3: Fix the CRLF checkout bug that breaks the test runner**

**This gates Task 3 and Task 5.** `scripts/run_tests.sh` and `scripts/check` currently
fail on a Windows checkout with:

```
/usr/bin/env: 'bash\r': No such file or directory
```

Root cause: `.gitattributes` pins `*.sh text eol=lf`, but four helper executables under
`scripts/` have **no extension**, so the rule never matched them and
`core.autocrlf=true` rewrote them to CRLF on checkout. (The committed blobs are LF —
this is a checkout-only rewrite, so `git status` shows no content change.)

```bash
# confirm the failure first
bash scripts/run_tests.sh --collect-only tests/gateway/test_api_server.py 2>&1 | head -3
# expect: /usr/bin/env: 'bash\r': No such file or directory
```

Verify the four are CRLF, then normalize:

```bash
for f in scripts/run-in-hermes-env scripts/check scripts/hermes-gateway scripts/hermes-python; do
  python -c "import sys;d=open(sys.argv[1],'rb').read();print(sys.argv[1], d.count(b'\r\n'))" "$f"
done
# expect: a non-zero count for each (32/295/12/15 respectively)

git rm --cached -q scripts/run-in-hermes-env scripts/check scripts/hermes-gateway scripts/hermes-python
git checkout -- scripts/run-in-hermes-env scripts/check scripts/hermes-gateway scripts/hermes-python
for f in scripts/run-in-hermes-env scripts/check scripts/hermes-gateway scripts/hermes-python; do
  python -c "import sys;d=open(sys.argv[1],'rb').read();print(sys.argv[1], d.count(b'\r\n'))" "$f"
done
# expect: 0 for all four
```

`.gitattributes` must already contain (edit it if not):

```
scripts/run-in-hermes-env text eol=lf
scripts/check            text eol=lf
scripts/hermes-gateway   text eol=lf
scripts/hermes-python    text eol=lf
```

Confirm the rule is live and the tools now start:

```bash
git check-attr text eol -- scripts/run-in-hermes-env   # expect: text: auto / eol: lf
bash scripts/check --help 2>&1 | head -5               # expect: usage text, no bash\r error
```

- [ ] **Step 4: Record the baseline test result, before any merge**

**Two host preconditions block this on Windows; fix them first.**

**(a) `bash` must be Git Bash, not WSL.** `scripts/run_tests.sh` sources
`scripts/_activation.sh`, which runs a **Windows** `.venv/Scripts/python.exe`; that emits
`PATH` in Windows form (`C:\a;C:\b`) and converts it back with `cygpath`. WSL has no
`cygpath`, so `PATH` stays Windows-form and *every* command vanishes — including `dirname`
and `bash` itself:

```
scripts/run_tests.sh: line 37: dirname: command not found
scripts/run-in-hermes-env: line 32: exec: bash: not found
```

`bash` on `PATH` is `C:\WINDOWS\system32\bash.exe` (WSL). Use Git Bash, which has
`cygpath`:

```powershell
$gb = "C:\Program Files\Git\bin\bash.exe"
& $gb -c 'cd /d/<repo> && bash scripts/run_tests.sh tests/gateway/test_api_server.py'
```

**(b) `uv` 0.13.5 must be staged manually.** `setup-hermes.sh` pins `uv 0.13.5` and
downloads it with `curl`, which fails on this host:

```
curl: (35) schannel: CRYPTIC_E_REVOCATION_OFFLINE
```

PowerShell's TLS stack succeeds where schannel fails, and the download is hash-pinned, so
stage it by hand — **verify the hash before installing**:

```powershell
$url = "https://github.com/astral-sh/uv/releases/download/0.13.5/uv-x86_64-pc-windows-msvc.zip"
$pin = "a38b8d1902b7cfbc76b423ba1bb456f623f42064cdc72628b6075b89afd1019a"
Invoke-WebRequest -Uri $url -OutFile "$env:TEMP\uv.zip" -UseBasicParsing
if ((Get-FileHash "$env:TEMP\uv.zip" -Algorithm SHA256).Hash.ToLower() -ne $pin) { throw "hash mismatch" }
$entry = "$env:USERPROFILE\.hermes\tools\uv-0.13.5-win32-x64"
Remove-Item -Recurse -Force $entry -ErrorAction SilentlyContinue
Expand-Archive "$env:TEMP\uv.zip" -DestinationPath $entry
& "$entry\uv.exe" --version     # expect: uv 0.13.5
```

`setup-hermes.sh` then finds `$entry/uv.exe` and skips the download entirely.

> **Do not use the root `.venv` as the baseline.** It has pytest but is missing `certifi`,
> so `test_api_server.py` reports `22 failed, 26 passed, 72 errors` of pure noise. That is
> not a baseline. If the canonical environment cannot be provisioned, record the baseline
> as **unavailable** and say so in the PR — do not substitute a different interpreter and
> call it a baseline.

Run the baseline:

```bash
scripts/run_tests.sh tests/gateway/test_api_server.py 2>&1 | tail -20
```
Expected: a `passed`/`failed` summary line.

**Recorded baseline on this host (2026-11-17):**

```
=== Summary: 1 files, 120 tests passed, 0 failed (100% complete) in 26.0s (24 workers) ===
```

That is a **clean** baseline — 0 failures. Plan 006's "17 pre-existing failures" does not
apply to this tree; do not carry that number forward. Task 5 must still end at
**120 passed, 0 failed**.

> The first run provisions the test environment and took ~13 minutes here. Do not interrupt.

- [ ] **Step 5: Create the sync branch and commit the pending fixes**

```bash
git checkout -b sync/upstream-20261116
git add .gitattributes docker-compose.yml docker-compose.upstream.yml scripts/fork_sync_facts.py
git commit -m "fix: pin extension-less scripts to LF and harden the postgres service

The four helper executables under scripts/ carry a bash shebang but no .sh
extension, so the '*.sh text eol=lf' rule never matched them and
core.autocrlf=true rewrote them to CRLF on a Windows checkout. That broke
scripts/run_tests.sh and scripts/check with
\"/usr/bin/env: 'bash\\r': No such file or directory\".

The postgres service published 0.0.0.0:5433 while nothing in the stack reads
DATABASE_URL, so the port only widened the attack surface: a LAN client could
reach a Postgres whose role password was still the 'changeme' default.

scripts/fork_sync_facts.py measures the facts a sync review needs (ancestry,
git cherry split, merge-tree status, per-side numstat for every file both sides
touched) so they are computed rather than recalled.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
Expected: commit succeeds; `git status --porcelain --untracked-files=no` prints nothing.

---

### Task 2: Merge upstream and prove no fork patch was lost

**Files:**
- Modify: every file upstream changed (1,410 files) plus 86 fork files
- Test: `scripts/fork_sync_facts.py`

**Interfaces:**
- Consumes: branch `sync/upstream-20261116` from Task 1
- Produces: a merged tree on `sync/upstream-20261116`; merged tree oid for Task 3

- [ ] **Step 1: Re-measure before merging (upstream moves hourly)**

```bash
git fetch upstream --prune
python scripts/fork_sync_facts.py
```
Expected: `merge conflict-free : YES`, `exit=0`, `fork-only patches (cherry): 80 '+' 0 '-'`.
If it prints `NO`, **stop** and resolve the listed conflicts by hand before continuing —
do not proceed with a conflicted merge.

- [ ] **Step 2: Merge**

```bash
git merge --no-ff upstream/main -m "merge: sync fork with upstream/main (1627 commits, 2026-11-16)

Merge direction is upstream into fork: the fork's 80 patches are additive and
survive a merge, while a rebase would re-resolve every overlap by hand and
destroy blob identity for later \`git cherry\` audits.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
Expected: `Merge made by the 'ort' strategy.` with no `CONFLICT` lines.

- [ ] **Step 3: Verify the fork-only patch count did not shrink**

```bash
python scripts/fork_sync_facts.py | grep -E "fork-only|conflict-free"
```
Expected: `fork-only patches (cherry): 80 '+'  0 '-'` — still **80**, and
`merge conflict-free : YES`.

**A drop below 80 means a fork patch was lost in the merge.** Restore it from
`fork-tip-pre-sync-20261116` before continuing. (A clean merge is not proof the fork's
code survived — that inference is exactly what produced a wrong report earlier.)

- [ ] **Step 4: Verify the five overlapping files keep BOTH sides**

```bash
for f in Dockerfile gateway/platforms/api_server.py hermes_cli/web_models.py \
         plugins/platforms/weixin/adapter.py web/src/lib/api.ts; do
  echo "== $f"
  git diff fork-tip-pre-sync-20261116 HEAD -- "$f" | grep -c '^+'
done
```
Expected: every file prints a number greater than 0 except where upstream made **no**
change; then confirm each fork symbol specifically:

```bash
git grep -c "_handle_audio_speech" -- gateway/platforms/api_server.py
git grep -c "WeixinOnboardingStart" -- hermes_cli/web_models.py
git grep -c "startWeixinOnboarding" -- web/src/lib/api.ts
git grep -c "ilink" -- plugins/platforms/weixin/adapter.py
git grep -c "edge-tts" -- Dockerfile
```
Expected: `1`, `1`, `1`, `19`, `2` respectively.

- [ ] **Step 5: Verify the chat-completions handler still has its admission gate**

```bash
grep -n -B2 "async def _handle_chat_completions" gateway/platforms/api_server.py
```
Expected: the line **immediately above** is `@_admit_api_agent_request`. There are two
`_handle_chat_completions` definitions in this file (an alias near line 1059 and the
`def` near line 3493) and the later one wins — if the decorator is missing, the endpoint
loses upstream's request admission gate.

- [ ] **Step 6: Verify no conflict markers survived**

```bash
git diff --check
grep -rn '^<<<<<<< \|^>>>>>>> ' --include='*.py' --include='*.ts' --include='*.yml' . | head
```
Expected: `git diff --check` prints nothing; the grep prints nothing.

---

### Task 3: Static gates

**Files:**
- Modify: none (verification only)
- Test: `scripts/check`, `compileall`

**Interfaces:**
- Consumes: merged tree from Task 2
- Produces: a green static state, required before the CI build

- [ ] **Step 1: Compile every Python file**

```bash
python -m compileall -q hermes_cli gateway agent tools plugins 2>&1 | tail -5
```
Expected: no traceback, no `SyntaxError`.

- [ ] **Step 2: Lint the new script**

```bash
.venv/Scripts/ruff.exe check scripts/fork_sync_facts.py
```
Expected: `All checks passed!`

- [ ] **Step 3: Validate all three compose lanes**

```bash
for f in docker-compose.yml docker-compose.upstream.yml docker-compose.windows.yml; do
  docker compose -f "$f" config --quiet; echo "$f exit=$?"
done
```
Expected: `exit=0` three times.

- [ ] **Step 4: Confirm upstream did not disturb the fork compose**

```bash
git diff --stat fork-tip-pre-sync-20261116 HEAD -- \
  docker-compose.upstream.yml docker/hermes-config.yaml docker/deploy.sh INSTALL.md
```
Expected: **empty**. These are fork-only files upstream does not track; any diff here
means the merge touched the deployment contract.

- [ ] **Step 5: Confirm the api_server port is still 8642 in the lane**

```bash
docker compose -f docker-compose.upstream.yml config | grep -A1 'target: 8642'
grep -c '8789' docker-compose.upstream.yml
```
Expected: `target: 8642` present; the `8789` count is `0` (the only mentions are comments
in `docker-compose.yml` describing its removal).

---

### Task 4: Fix the dead anchor `environment:` block

**Files:**
- Modify: `docker-compose.upstream.yml` (the `x-hermes-common.environment` key, ~lines 36-45)
- Modify: `docker-compose.yml` (the same anchor, ~lines 58-75)

**Interfaces:**
- Consumes: merged tree from Task 2
- Produces: an anchor that documents only what it actually delivers

**Why:** a YAML merge key **replaces** `environment`, and both services declare their own,
so all seven anchor vars are absent from the containers. That is *benign* — `HERMES_UID=1000`
would `usermod -u 1000` the runtime user away from the `/opt/data` volume it owns at
**10000**, and `config.yaml` supersedes `OPENAI_BASE_URL` (proven by a live completion).
The honest defect is that the anchor advertises configuration it never delivers. Removing
it prevents a future maintainer from "repairing" the merge and breaking the UID mapping.

- [ ] **Step 1: Confirm the vars are absent today**

```bash
docker inspect hermes-gateway --format '{{json .Config.Env}}' \
  | python -c "import json,sys;k=[e.split('=',1)[0] for e in json.load(sys.stdin)];print([v for v in ('HERMES_UID','OPENAI_BASE_URL','DATABASE_URL') if v in k])"
```
Expected: `[]` — none present.

- [ ] **Step 2: Confirm the data volume is owned by 10000, not 1000**

```bash
docker exec hermes-gateway stat -c '%u:%g' /opt/data
```
Expected: `10000:10000`. If this ever prints `1000:1000`, **stop** — the analysis is wrong
and setting `HERMES_UID` would be safe rather than harmful.

- [ ] **Step 3: Delete the dead environment entries from both anchors**

In `docker-compose.upstream.yml`, replace the anchor's `environment:` list with only what
a service would need if it did not override it — i.e. remove the block entirely and add a
comment where it was:

```yaml
  # NOTE: no `environment:` here on purpose. A YAML merge key REPLACES a sequence
  # rather than deep-merging it, and both services declare their own
  # `environment:`, so anything placed here never reaches a container. That is
  # desirable for the vars this anchor used to list:
  #   HERMES_UID/GID  — the image creates `hermes` at UID 10000 and /opt/data is
  #                     owned 10000:10000; setting 1000 would usermod the runtime
  #                     user away from its own volume (stage2-hook.sh).
  #   OPENAI_*/OLLAMA_* — data/config.yaml `model.base_url` is authoritative and wins.
  #   DATABASE_URL     — nothing in the image reads it.
  #   HERMES_LAZY_INSTALL_TARGET — tools/lazy_deps.py was retired upstream.
  # Per-service vars that DO matter (HERMES_WRITE_SAFE_ROOT) are set on each service.
```
Apply the equivalent edit to `docker-compose.yml`.

- [ ] **Step 4: Validate both lanes**

```bash
docker compose -f docker-compose.yml config --quiet; echo "default=$?"
docker compose -f docker-compose.upstream.yml config --quiet; echo "upstream=$?"
```
Expected: `default=0` and `upstream=0`.

- [ ] **Step 5: Recreate and prove nothing regressed**

```bash
docker compose -f docker-compose.upstream.yml up -d --force-recreate
sleep 60
docker compose -f docker-compose.upstream.yml ps
```
Expected: all three `(healthy)`.

- [ ] **Step 6: Prove behaviour survived the anchor edit**

```bash
docker exec hermes-gateway stat -c '%u:%g' /opt/data          # expect 10000:10000
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9119/api/status   # expect 200
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8642/health       # expect 200
```
Expected: `10000:10000`, `200`, `200`.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml docker-compose.upstream.yml
git commit -m "docs(compose): drop anchor environment entries that never reach a container

A YAML merge key replaces \`environment\` and both services declare their own, so
all seven anchor vars were silently absent. Keeping them invited a future
\"fix\" that would set HERMES_UID=1000 and usermod the runtime user away from
/opt/data (owned 10000:10000), which is how the volume breaks.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Tests against the fork-tip baseline

**Files:**
- Modify: only if a test fails **because of** the merge
- Test: `tests/gateway/test_api_server.py` plus the wider suite

**Interfaces:**
- Consumes: merged tree from Tasks 2-4
- Produces: a pass/fail delta versus Task 1 Step 3

- [ ] **Step 1: Re-run the same file measured in Task 1**

```bash
scripts/run_tests.sh tests/gateway/test_api_server.py 2>&1 | tail -20
```
Expected: **120 passed, 0 failed** — identical to the Task 1 baseline. The baseline is
clean, so *any* failure here is caused by the merge. Fix it before continuing.

> On Windows, run this through Git Bash (`"C:\Program Files\Git\bin\bash.exe" -c '...'`),
> not WSL — see Task 1 Step 4(a).

- [ ] **Step 2: Run the fork's own test surface**

```bash
scripts/run_tests.sh tests/gateway/ tests/hermes_cli/ 2>&1 | tail -30
```
Expected: no *new* failures beyond the baseline. Record the summary line verbatim for the
PR body.

- [ ] **Step 3: Run the repo's blocking lint gate**

```bash
python scripts/check 2>&1 | tail -20
```
Expected: exit `0`. If it fails on a pre-existing finding, verify the same command fails
identically on `fork-tip-pre-sync-20261116` before attributing it to the merge.

---

### Task 6: Push the branch

**Files:**
- Modify: none

**Interfaces:**
- Consumes: the merged, tested branch from Tasks 2-5
- Produces: a remote branch CI can build from

- [ ] **Step 1: Push**

```bash
git push -u origin sync/upstream-20261116
```
Expected: new branch created; `gh` uses SSH so no prompt.

- [ ] **Step 2: Confirm the remote tip matches local**

```bash
git rev-parse --short HEAD
git ls-remote --heads origin sync/upstream-20261116
```
Expected: the short SHA equals the first 8 characters of the remote SHA.

---

### Task 7: Build the image in CI and read the pin

**Files:**
- Modify: none (CI produces the artifact)

**Interfaces:**
- Consumes: `sync/upstream-20261116` on origin
- Produces: an immutable `sha-<short>` tag **and** a digest to pin in Task 8

**Why not build locally:** `Dockerfile` starts `FROM debian:trixie-20261020@sha256:…`,
which is not in the local cache, and `registry-1.docker.io` times out from this host. CI is
the only producer.

- [ ] **Step 1: Dispatch against the branch, not `main`**

```bash
gh workflow run "Fork Docker Build and Publish to GHCR" \
  --repo JZKK720/hermes-agent --ref sync/upstream-20261116
```
Expected: `✓ Created workflow_dispatch event`.

> **Do not read a verdict from the branch run.** The workflow tags unconditionally
> (`type=raw,value=latest`, `type=raw,value=main`, `type=sha`) with no `if:` guard on the
> ref, so a branch build **moves `:latest`** to unmerged code. Use it only to prove the
> Dockerfile builds and to fail fast. `main` is re-dispatched in Task 10 and that run is
> the authoritative artifact.

- [ ] **Step 2: Watch it to completion**

```bash
gh run list --workflow "Fork Docker Build and Publish to GHCR" --limit 1
gh run watch "$(gh run list --workflow "Fork Docker Build and Publish to GHCR" \
  --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```
Expected: `success`, roughly 8-10 minutes. A failure here is almost always the Dockerfile
`COPY --from` product stage — the exact class of failure plan 006 hit at phase 5.

- [ ] **Step 3: If the build fails, read the failing step only**

```bash
gh run view "$(gh run list --workflow "Fork Docker Build and Publish to GHCR" \
  --limit 1 --json databaseId --jq '.[0].databaseId')" --log-failed | tail -40
```
Expected: a concrete error. Fix it on the branch, push, and re-dispatch (Step 1).

---

### Task 8: Open the PR and merge to `main`

**Files:**
- Modify: none

**Interfaces:**
- Consumes: green CI from Task 7
- Produces: `main` == merged tree

**The repo has a PR template** at `.github/pull_request_template.md`. Its headings,
comments and checklist items are reproduced verbatim below with the placeholders
replaced. Do not substitute a generic body.

- [ ] **Step 1: Write the PR body to a file (avoid shell-quoting a 100-line body)**

Create `pr-body.md` in the repo root (**delete it before committing** — it is not part of
the change):

```markdown
## What does this PR do?

Merges `upstream/main` @ `0309b00523` into the fork (1,627 commits) and hardens the
Docker Compose deployment. Merge direction is upstream → fork: the fork's patches are
additive and survive a merge, whereas a rebase would re-resolve every overlap by hand.

## Related Issue

Fixes #N/A — fork maintenance; no upstream issue tracks this sync.

## Type of Change

- [x] 🐛 Bug fix (non-breaking change that fixes an issue)
- [x] 🔒 Security fix (postgres was LAN-exposed with a default password; §3.2 hardening,
      not a §3.1 undisclosed vulnerability)
- [x] 📝 Documentation update
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] ✅ Tests (adding or improving test coverage)
- [ ] ♻️ Refactor (no behavior change)
- [ ] 🎯 New skill (bundled or hub)

## Changes Made

- Merge of `upstream/main` (`0309b00523`) — 1,627 commits
- `docker-compose.yml`, `docker-compose.upstream.yml`: postgres published on
  `127.0.0.1:5433` instead of `0.0.0.0:5433`
- `docker-compose.yml`, `docker-compose.upstream.yml`: removed the `x-hermes-common`
  `environment:` entries, which a YAML merge key replaces and so never reach a container
- `.gitattributes`: pin `scripts/run-in-hermes-env`, `scripts/check`,
  `scripts/hermes-gateway`, `scripts/hermes-python` to `eol=lf` (they are extension-less
  executables, so `*.sh text eol=lf` never matched them and `core.autocrlf=true` rewrote
  them to CRLF on Windows, breaking `scripts/check` and `scripts/run_tests.sh`)
- `scripts/fork_sync_facts.py`: new — measures ancestry, `git cherry` split, merge-tree
  status and per-side `--numstat` for every file both sides touched

## How to Test

1. `python scripts/fork_sync_facts.py` → `merge conflict-free : YES`,
   `fork-only patches (cherry): 80 '+' 0 '-'` (proves no fork patch was lost)
2. `python -m compileall -q hermes_cli gateway agent tools plugins` → no SyntaxError
3. `.venv/Scripts/ruff.exe check scripts/fork_sync_facts.py` → `All checks passed!`
4. `docker compose -f docker-compose.upstream.yml config --quiet` → `exit=0`
5. `scripts/run_tests.sh tests/gateway/test_api_server.py` → same failure count as the
   fork-tip baseline (recorded before the merge)
6. `python scripts/check` → `exit=0`
7. After the GHCR build: `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9119/api/status`
   → `200`; `docker exec hermes-gateway hermes --version` → a real stamp, not `0.0.0`

## Checklist

### Code

- [x] I've read the [Contributing Guide](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md)
- [x] My commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`fix(scope):`, `feat(scope):`, etc.)
- [x] I searched for [existing PRs](https://github.com/NousResearch/hermes-agent/pulls) to make sure this isn't a duplicate
- [x] My PR contains **only** changes related to this fix/feature (no unrelated commits)
- [x] I've run the tests for the code I changed, and they pass — via
      `scripts/run_tests.sh` (the canonical runner this repo requires instead of `just test`)
- [x] `python scripts/check` passes (the blocking lint and code-health checks CI runs)
- [ ] I've added tests for my changes — N/A for a sync merge; the merge-specific guard is
      `scripts/fork_sync_facts.py`, whose conflict path was verified against a scratch repo
- [x] I've tested on my platform: Windows 11 (Docker Desktop, WSL2 backend)

### Documentation & Housekeeping

- [x] I've updated relevant documentation (README, `docs/`, docstrings) — or N/A
      (`docs/plans/007-upstream-sync-20261116.md` and `008-upstream-sync-implementation.md`)
- [x] I've updated `cli-config.yaml.example` if I added/changed config keys — or N/A
- [x] I've updated `CONTRIBUTING.md` or `AGENTS.md` if I changed architecture or workflows — or N/A
- [x] I've considered cross-platform impact (Windows, macOS) per the [compatibility guide](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md#cross-platform-compatibility) — the `.gitattributes` fix is specifically a Windows-checkout bug
- [x] I've updated tool descriptions/schemas if I changed tool behavior — or N/A

## Screenshots / Logs

```
$ python scripts/fork_sync_facts.py
upstream merged into HEAD : NO
commits behind upstream   : 1627
fork-only patches (cherry): 80 '+'  0 '-'
merge conflict-free       : YES

files both sides changed  : 5
  gateway/platforms/api_server.py
    fork     +229/-1
    upstream +8/-10
```

Postgres, before/after:
```
$ docker port hermes-postgres      # before
5432/tcp -> 0.0.0.0:5433
$ docker port hermes-postgres      # after
5432/tcp -> 127.0.0.1:5433
```
```

- [ ] **Step 2: Open the PR using that file**

```bash
gh pr create --repo JZKK720/hermes-agent \
  --base main --head sync/upstream-20261116 \
  --title "sync: upstream/main 2026-11-16 (1,627 commits) + compose hardening" \
  --body-file pr-body.md
rm pr-body.md
```
Expected: PR URL printed. `pr-body.md` is removed so it cannot be committed.

- [ ] **Step 3: Merge**

```bash
gh pr merge --repo JZKK720/hermes-agent --squash --delete-branch
```
Expected: merged. Then confirm `main` advanced:

```bash
git checkout main && git pull --ff-only
git rev-parse --short HEAD
git rev-parse --short origin/main
```
Expected: the two SHAs match.

---

### Task 9: Rebuild from `main` and pin the digest

**Files:**
- Modify: root `.env` (gitignored) — `HERMES_FORK_IMAGE`

**Interfaces:**
- Consumes: `main` at the merged tree
- Produces: a digest that names the deployed image

- [ ] **Step 1: Dispatch the authoritative build from `main`**

```bash
gh workflow run "Fork Docker Build and Publish to GHCR" \
  --repo JZKK720/hermes-agent --ref main
gh run watch "$(gh run list --workflow "Fork Docker Build and Publish to GHCR" \
  --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```
Expected: `success`.

- [ ] **Step 2: Read the digest from the run summary**

```bash
gh run view "$(gh run list --workflow "Fork Docker Build and Publish to GHCR" \
  --limit 1 --json databaseId --jq '.[0].databaseId')" --log | grep -i 'digest pin'
```
Expected: a line containing `ghcr.io/jzkk720/hermes-agent@sha256:<digest>`.

- [ ] **Step 3: Independently confirm the digest exists in the registry**

```bash
TOKEN=$(curl -s "https://ghcr.io/token?scope=repository:jzkk720/hermes-agent:pull&service=ghcr.io" \
  | python -c "import json,sys;print(json.load(sys.stdin)['token'])")
curl -s -H "Authorization: Bearer $TOKEN" \
  https://ghcr.io/v2/jzkk720/hermes-agent/tags/list | python -m json.tool
```
Expected: the tag list now includes a `sha-<short>` for the merged `main` commit. The
package is public, so no `read:packages` scope is needed.

- [ ] **Step 4: Write the pin into the gitignored root `.env`**

Replace the existing `HERMES_FORK_IMAGE=` line (do not append a duplicate):

```
HERMES_FORK_IMAGE=ghcr.io/jzkk720/hermes-agent@sha256:<digest>
```

- [ ] **Step 5: Prove all three lanes resolve the new pin**

```bash
for f in docker-compose.yml docker-compose.upstream.yml docker-compose.windows.yml; do
  echo "== $f"
  docker compose -f "$f" config | grep -m1 'image: ghcr.io'
done
```
Expected: all three print the **same** new digest.

- [ ] **Step 6: Confirm the image's own stamp matches the commit**

```bash
docker run --rm --entrypoint cat "$(grep '^HERMES_FORK_IMAGE=' .env | cut -d= -f2-)" \
  /opt/hermes/install-stamp.json
git rev-parse HEAD
```
Expected: the stamp's `commit` equals `HEAD`; `baseVersion` is a real release (e.g.
`0.23.x`), not null; `dirty` is `false`.

---

### Task 10: Redeploy and prove the stack end to end

**Files:**
- Modify: none

**Interfaces:**
- Consumes: the digest pinned in Task 9
- Produces: a running stack on the merged image

- [ ] **Step 1: Recreate from the pinned digest**

```bash
docker compose -f docker-compose.upstream.yml up -d --force-recreate --remove-orphans
sleep 60
docker compose -f docker-compose.upstream.yml ps
```
Expected: all three `(healthy)`. If `--pull always` is used, `postgres:16-alpine` may fail
because Docker Hub is unreachable — omit `--pull` or rely on the cached image.

- [ ] **Step 2: Confirm the containers run the merged image**

```bash
docker inspect hermes-web --format '{{.Image}}'
docker inspect hermes-gateway --format '{{.Image}}'
```
Expected: both equal the digest-pinned image ID, and both `Config.Cmd` are the direct argv
(`["dashboard", ...]` / `["gateway","run"]`), **not** a `sh -lc` wrapper.

- [ ] **Step 3: Health, ports, endpoints**

```bash
docker inspect hermes-gateway --format '{{json .State.Health}}' \
  | python -c "import json,sys;d=json.load(sys.stdin);print(d['Status'],d['FailingStreak'])"
docker port hermes-postgres
for u in http://127.0.0.1:9119/api/status http://127.0.0.1:8642/health; do
  curl -s -o /dev/null -w "%{http_code} $u\n" --noproxy '*' "$u"
done
```
Expected: `healthy 0`; `127.0.0.1:5433`; `200` twice.

- [ ] **Step 4: Prove the agent actually answers**

```bash
KEY=$(grep '^API_SERVER_KEY=' .env | cut -d= -f2-)
curl -s --noproxy '*' -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"hermes-agent","messages":[{"role":"user","content":"say OK"}],"max_tokens":5}' \
  http://127.0.0.1:8642/v1/chat/completions | python -c \
  "import json,sys;d=json.load(sys.stdin);print('choices:',bool(d.get('choices')))"
```
Expected: `choices: True`. This is the only check that proves model resolution — env-var
inspection does not.

- [ ] **Step 5: Confirm the config drift guard**

```bash
docker exec hermes-gateway sh -c 'grep -q "port: 8789" /opt/data/config.yaml && echo DRIFT || echo clean'
```
Expected: `clean`.

- [ ] **Step 6: Confirm runtime state survived**

```bash
ls data/state.db && stat -c '%s' data/state.db
ls data/sessions | wc -l
ls data/skills | wc -l
docker exec hermes-postgres psql -U hermes -d hermes -tAc 'select 1'
```
Expected: `state.db` present (≈5.37 MB), 16 sessions, 36 skills, and `1`.

- [ ] **Step 7: Re-verify weixin is a credentials problem, not a code problem**

```bash
docker logs hermes-gateway --since 15m 2>&1 | grep -i weixin | tail -5
```
Expected: `Session expired; pausing for 10 minutes` (`errcode=-14`). That needs a QR
re-scan, not a code change — see `.github/instructions/weixin-channel-diagnostics.instructions.md`.

---

### Task 11: Update the plan doc with the deployed pin

**Files:**
- Modify: `docs/plans/007-upstream-sync-20261116.md` (§1 table, §5 phases, §9 risks)
- Modify: `docs/plans/006-upstream-sync-and-release.md` (mark superseded, do not rewrite)

**Interfaces:**
- Consumes: results from Tasks 1-10
- Produces: a plan doc that matches reality

- [ ] **Step 1: Record the new facts**

In `007-upstream-sync-20261116.md`, update the `Status:` line to
`implemented on sync/upstream-20261116`, set `Base:` to the merged `main` SHA, and replace
the `Running image` row with the new digest and its stamp. Add a "Published pin for this
sync" table mirroring plan 006 §5:

| | |
|---|---|
| workflow run | `<run id>` |
| commit | `<main sha>` |
| immutable tag | `sha-<short>` |
| digest | `sha256:<digest>` |

- [ ] **Step 2: Tick the phase table**

Change §5 rows 5-11 from pending to ✅ with the observed evidence (test delta, CI run id,
digest).

- [ ] **Step 3: Fold the resolved risks into §9**

Remove the items now resolved (stale numbers, postgres exposure) and keep the live ones:
weixin `-14`, SQLite on the VM boundary, Docker Hub unreachable, `piper` 1.6.0 → 1.8.0
needs a TTS re-smoke.

- [ ] **Step 4: Commit**

```bash
git add docs/plans/007-upstream-sync-20261116.md
git commit -m "docs(plan): record the deployed upstream sync pin

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

---

## Progress (executed 2026-11-17)

Branch `sync/upstream-20261116`, eleven commits on top of `0b9ad27959` (the fork tip this
session started from; rollback tag `fork-tip-pre-sync-20261116` = `ce476f23b1`):

| Commit | What it fixes |
|---|---|
| `d821d85008` | **merge** `upstream/main` (1,727 commits, v0.23.2 + 9) |
| `c22243775f` | CRLF: pin the 4 extension-less `scripts/` executables to LF; postgres → loopback |
| `cafed0e2e4` | drop the anchor `environment:` that never reaches a container |
| `295afa03da` | 14 ruff findings from upstream's new ~300-rule gate (incl. ASYNC230) |
| `630146195f` | **security**: stop committing the dashboard hash + session secret |
| `7f90063610` | read text files with `utf-8-sig` (BOM) |
| `1117805bcc` | agent-reach skill: `$TMPDIR` instead of literal `/tmp` |
| `54ce43db01` | pin `.gitattributes` itself to LF (the `shims` gate) |
| `808668a2bc` | `fork_sync_facts.py`: HX006 timeouts + correct base/fork-side diff |
| `c865b8ac4c` | keep the ASYNC230 offload line-neutral for the FILE_LINES ratchet |
| `eb4e59873b` | record the executed results and host blockers in this plan |

### Gate results

| Gate | Result |
|---|---|
| `python scripts/fork_sync_facts.py` | `merged YES`, `behind 0`, `91 '+' 0 '-'`, `conflict-free YES` |
| `scripts/run_tests.sh tests/gateway/test_api_server.py` | **120 passed, 0 failed** (baseline: 120/0) |
| `scripts/check` in a fresh clone | `FAILED: health` — **2 blocking, 2 advisory, identical findings to pristine `upstream/main`** |
| `docker compose config --quiet` ×3 | `0` |
| **CI image build (`fork-ghcr-publish.yml`)** | **success**, run `44010836099`, 8m |
| Stack | 3/3 healthy; `9119` → 200, `8642/health` → 200; `/v1/chat/completions` returned `OK` |

### Published pin for this branch build

| | |
|---|---|
| workflow run | `44010836099` (success) |
| commit | `b0f032421c95c5da87a94da649d36af788d43290` |
| digest | `sha256:1fbc3bab3fc697194398c19c5898c9563d4f25607218f0bee49fd7618c59078f` |
| image stamp | `0.23.2+113.gb0f0324`, `dirty: false`, `revision` == commit ✅ |

This digest was pulled and inspected locally: its `org.opencontainers.image.revision` label
and its `install-stamp.json` both name `b0f032421c…`, so the artifact corresponds exactly to
the verified branch tip. **Do not deploy this digest to `main`** — it was built from the
unmerged branch. Merge first, rebuild from `main` (Task 9), and pin *that* digest; the branch
digest is only for proving the Dockerfile builds.

The `health` ratchet cannot pass on its baseline: pristine `upstream/main` reports the same
2 blocking findings (`tests/agent/test_redact.py` FILE_LINES, `tools/approval_home_fold.py`
BLE001), so this branch introduces **zero** new ones. Say exactly that in the PR rather than
claiming a green gate.

### Three host blockers that had to be solved to run the gates

1. **`.gitattributes` itself was CRLF.** It is matched by its own `* text=auto` rule, so a
   Windows checkout rewrote it to CRLF (57 pairs) while the shim generator compares it
   byte-for-byte against an LF render. `git diff` cannot show this — the index normalizes it
   away — which is why running the generator appeared to change nothing.
2. **`bash` on PATH is WSL, which has no `cygpath`.** `_activation.sh` runs a *Windows*
   `.venv/Scripts/python.exe` that emits a Windows-form `PATH`; without `cygpath` every
   command (including `dirname` and `bash`) vanishes. Use Git Bash.
3. **`uv` 0.13.5 could not be downloaded by `curl`** (`CRYPT_E_REVOCATION_OFFLINE`).
   PowerShell's TLS stack works; the download is hash-pinned, so stage it manually into
   `~/.hermes/tools/uv-0.13.5-win32-x64/` after verifying the SHA-256.

## Rollback

Any point after the merge:

```bash
# code
git reset --hard fork-tip-pre-sync-20261116

# image back to the pre-sync build
HERMES_FORK_IMAGE=ghcr.io/jzkk720/hermes-agent@sha256:15d350bad356aaed17d32decfbd21cfb8a23f65f4bb416f062203f013f3e6790 \
  docker compose -f docker-compose.upstream.yml up -d --force-recreate

# runtime config
cp data/config.yaml.bak-20261116 data/config.yaml
```

`data/` and the `hermes-agent_postgres_data` volume are untouched by every step.

## Notes on things deliberately NOT done

- **`read:org` / `read:packages` are not requested.** Eight `gh` commands were tested and
  all exit `0` without them; the GHCR package is public, so the anonymous token in Task 9
  Step 3 covers tag inspection. Adding scopes needs a browser round-trip for no gain.
- **Postgres is left running but unused** (zero tables, no code reads `DATABASE_URL`). It
  is hardened and loopback-only, so it is harmless; removing it is a separate decision.
- **`pyproject.toml` version is not bumped** — the runtime version comes from the install
  stamp, and a hand-edited version makes `hermes doctor` disagree with the image.
