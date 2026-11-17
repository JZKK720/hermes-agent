#!/usr/bin/env python3
"""List or resolve this fork's GHCR image tags without the read:packages scope.

`gh api user/packages/container/hermes-agent/versions` needs `read:packages`,
which the CLI token on this machine does not carry (and adding it needs a
browser round-trip). The package is public, so the registry's own anonymous
bearer token answers the same questions — no scope, no browser:

    python scripts/ghcr_tags.py                 # list tags, newest last
    python scripts/ghcr_tags.py --sha-only      # just the immutable sha-* pins
    python scripts/ghcr_tags.py --digest latest # resolve a tag to its digest

Used by the sync runbook to confirm a rebuild landed before pinning it in .env.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

REGISTRY = "ghcr.io"
REPOSITORY = "jzkk720/hermes-agent"
TIMEOUT_SECONDS = 30


def _get(url: str, token: str | None = None) -> dict:
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    if url.endswith("/manifests/latest") or "/manifests/" in url:
        # the registry returns an OCI index only when asked for it
        request.add_header(
            "Accept",
            "application/vnd.oci.image.index.v1+json,"
            "application/vnd.docker.distribution.manifest.list.v2+json",
        )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def anonymous_token(repository: str = REPOSITORY) -> str:
    """A pull-scoped bearer token for a public package. No credentials involved."""
    url = (
        f"https://{REGISTRY}/token"
        f"?scope=repository:{repository}:pull&service={REGISTRY}"
    )
    return _get(url)["token"]


def list_tags(repository: str = REPOSITORY) -> list[str]:
    token = anonymous_token(repository)
    payload = _get(f"https://{REGISTRY}/v2/{repository}/tags/list", token)
    return payload.get("tags") or []


def resolve_digest(tag: str, repository: str = REPOSITORY) -> str:
    token = anonymous_token(repository)
    request = urllib.request.Request(f"https://{REGISTRY}/v2/{repository}/manifests/{tag}")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header(
        "Accept",
        "application/vnd.oci.image.index.v1+json,"
        "application/vnd.docker.distribution.manifest.list.v2+json,"
        "application/vnd.docker.distribution.manifest.v2+json",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.headers.get("Docker-Content-Digest") or ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=REPOSITORY)
    parser.add_argument(
        "--sha-only",
        action="store_true",
        help="only the immutable sha-<short> pins",
    )
    parser.add_argument(
        "--digest",
        metavar="TAG",
        help="print the manifest digest for TAG instead of listing tags",
    )
    args = parser.parse_args()

    try:
        if args.digest:
            digest = resolve_digest(args.digest, args.repository)
            if not digest:
                print("no digest returned", file=sys.stderr)
                return 1
            print(f"{REGISTRY}/{args.repository}@{digest}")
            return 0

        tags = list_tags(args.repository)
        if args.sha_only:
            tags = [tag for tag in tags if tag.startswith("sha-")]
        for tag in tags:
            print(tag)
        print(f"\n{len(tags)} tag(s) in {REGISTRY}/{args.repository}", file=sys.stderr)
        return 0
    except urllib.error.HTTPError as exc:
        print(f"registry returned HTTP {exc.code} for {args.repository}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"cannot reach {REGISTRY}: {exc.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
