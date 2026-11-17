#!/usr/bin/env python3
"""Print the facts a fork-sync review needs, so they are measured and not recalled.

Written after a sync review reported that the fork had "changed nothing since the
merge base" in the files both sides touched. That was wrong: the fork had changed
all five, including +229 lines in ``gateway/platforms/api_server.py``. A clean
``git merge-tree`` returns a tree with no conflict block, which is *not* evidence
that the fork's own additions survived. Both mistakes are one command away from
being detected — this script is that command.

Usage::

    python scripts/fork_sync_facts.py                  # origin/main..upstream/main
    python scripts/fork_sync_facts.py --base HEAD --target upstream/main
    python scripts/fork_sync_facts.py --markdown        # paste into a plan file

Exits 0 when the merge is conflict-free, 1 when it is not. Read-only: it never
creates a worktree, a stash, or a commit.
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def git(*args: str) -> str:
    return subprocess.run(
        ("git", *args), capture_output=True, text=True, check=True
    ).stdout.strip()


def try_git(*args: str) -> str:
    """Like git() but returns "" instead of raising (for optional probes)."""
    result = subprocess.run(("git", *args), capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def numstat(base: str, target: str, path: str) -> str:
    """`+added/-deleted` for *path* between *base* and *target*, or `unchanged`."""
    raw = try_git("diff", "--numstat", base, target, "--", path)
    if not raw:
        return "unchanged"
    added, deleted = raw.split("\t")[:2]
    return f"+{added}/-{deleted}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--target", default="upstream/main")
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="emit the both-sides table as markdown instead of plain text",
    )
    args = parser.parse_args()

    base, target = args.base, args.target
    tip = git("rev-parse", "--short", "HEAD")
    base_sha, target_sha = git("rev-parse", f"{base}^!"), git("rev-parse", target)
    merge_base = git("merge-base", base, target)

    print(f"HEAD          = {tip}")
    print(f"{base:<13} = {base_sha[:10]}")
    print(f"{target:<13} = {target_sha[:10]}")
    print(f"merge-base    = {merge_base[:10]}")
    print()

    # Ancestry, not a commit count: "behind" is meaningless if the target is
    # already merged, and a count alone hides that.
    merged = (
        subprocess.run(
            ("git", "merge-base", "--is-ancestor", target, "HEAD"),
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    print(f"upstream merged into HEAD : {'YES' if merged else 'NO'}")
    print(f"commits behind upstream   : {git('rev-list', '--count', f'HEAD..{target}')}")

    # git cherry is the authoritative fork-only measure: '+' = not upstream,
    # '-' = equivalent patch already upstream.
    cherry = try_git("cherry", target, "HEAD").splitlines()
    plus = sum(1 for line in cherry if line.startswith("+"))
    minus = sum(1 for line in cherry if line.startswith("-"))
    print(f"fork-only patches (cherry): {plus} '+'  {minus} '-'")
    print()

    # The merge itself. A tree oid with no conflict block means the textual
    # merge is clean -- nothing more. It does not mean fork code survived.
    merged_tree = try_git("merge-tree", "--write-tree", "HEAD", target)
    conflict_free = bool(merged_tree) and "\n" not in merged_tree
    print(f"merge conflict-free       : {'YES' if conflict_free else 'NO'}")
    if conflict_free:
        print(f"merged tree               : {merged_tree[:12]}")
    else:
        for line in merged_tree.splitlines():
            if line.startswith("CONFLICT") or "\t" in line:
                print(f"  {line}")
    print()

    # The table that was wrong. Every file both sides touched gets a per-side
    # numstat so "the fork changed nothing" is a measurement, not an assumption.
    upstream_files = set(try_git("diff", "--name-only", merge_base, target).splitlines())
    fork_files = set(try_git("diff", "--name-only", merge_base, "HEAD").splitlines())
    both = sorted(upstream_files & fork_files)

    print(f"files both sides changed  : {len(both)}")
    if args.markdown:
        print()
        print("| File | Fork side | Upstream side |")
        print("|---|---|---|")
        for path in both:
            print(
                f"| `{path}` | {numstat(merge_base, 'HEAD', path)} "
                f"| {numstat(merge_base, target, path)} |"
            )
    else:
        for path in both:
            fork_side = numstat(merge_base, "HEAD", path)
            up_side = numstat(merge_base, target, path)
            print(f"  {path}")
            print(f"    fork     {fork_side}")
            print(f"    upstream {up_side}")

    return 0 if conflict_free else 1


if __name__ == "__main__":
    sys.exit(main())
