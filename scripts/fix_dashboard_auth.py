#!/usr/bin/env python3
"""Write the dashboard basic_auth block into data/config.yaml.

This replaces a one-off helper that hardcoded the password hash and the
session-signing secret. Those were committed to a public repository, which is
the same class of leak the repo's own security rules forbid — a scrypt hash of a
dashboard password plus the token-signing key is a credential, not a setting.

Both values now come from the environment, so nothing secret lives in the tree:

    HERMES_DASHBOARD_HASH    scrypt$... hash, as produced by hash_password()
    HERMES_DASHBOARD_SECRET  32+ random bytes, hex

Usage (from host, with containers running):

    docker cp scripts/fix_dashboard_auth.py hermes-web:/tmp/fix_auth.py
    docker exec -e HERMES_DASHBOARD_HASH -e HERMES_DASHBOARD_SECRET \\
        hermes-web python3 /tmp/fix_auth.py

Generate a hash inside the container:

    docker exec hermes-web /opt/hermes/.venv/bin/python3 \\
        -c 'from hermes_cli.dashboard_auth.basic import hash_password; \\
            print(hash_password(input("password: ")))'
"""
import os
import sys

import yaml

CONFIG = os.environ.get("HERMES_CONFIG", "/opt/data/config.yaml")


def main() -> int:
    password_hash = os.environ.get("HERMES_DASHBOARD_HASH", "").strip()
    secret = os.environ.get("HERMES_DASHBOARD_SECRET", "").strip()

    missing = [
        name
        for name, value in (
            ("HERMES_DASHBOARD_HASH", password_hash),
            ("HERMES_DASHBOARD_SECRET", secret),
        )
        if not value
    ]
    if missing:
        print(
            "missing required env var(s): " + ", ".join(missing) + "\n"
            "refusing to write a dashboard auth block with empty credentials",
            file=sys.stderr,
        )
        return 2

    if not password_hash.startswith("scrypt$"):
        print(
            "HERMES_DASHBOARD_HASH does not look like a scrypt hash; "
            "expected it to start with 'scrypt$'",
            file=sys.stderr,
        )
        return 2

    with open(CONFIG, encoding="utf-8-sig") as handle:
        config = yaml.safe_load(handle)

    config.setdefault("dashboard", {})
    config["dashboard"]["basic_auth"] = {
        "username": os.environ.get("HERMES_DASHBOARD_USER", "admin"),
        "password_hash": password_hash,
        "secret": secret,
        "session_ttl_seconds": int(os.environ.get("HERMES_DASHBOARD_TTL", "86400")),
    }

    with open(CONFIG, "w", encoding="utf-8") as handle:
        yaml.dump(
            config,
            handle,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    # Read back through the same code path the dashboard uses, so a write that
    # produced unparseable YAML is caught here rather than at next boot.
    with open(CONFIG, encoding="utf-8-sig") as handle:
        written = yaml.safe_load(handle)

    stored = written["dashboard"]["basic_auth"]["password_hash"]
    print(f"wrote dashboard.basic_auth to {CONFIG}")
    print("password_hash round-trips:", stored == password_hash)
    return 0 if stored == password_hash else 1


if __name__ == "__main__":
    raise SystemExit(main())
