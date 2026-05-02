import json
import re
import sys
from typing import Any


DANGEROUS_COMMAND_PATTERNS = [
    (re.compile(r"docker\s+compose\s+down\b[^\n\r]*\s-v(?:\s|$)", re.IGNORECASE), "`docker compose down -v` would delete named volumes."),
    (re.compile(r"docker-compose\s+down\b[^\n\r]*\s-v(?:\s|$)", re.IGNORECASE), "`docker-compose down -v` would delete named volumes."),
    (re.compile(r"rm\s+-rf\s+(?:\./)?data(?:[\\/]|\s|$)", re.IGNORECASE), "`rm -rf data` would delete persisted runtime state."),
    (re.compile(r"remove-item\b[^\n\r]*\bdata(?:[\\/]|\s|$)", re.IGNORECASE), "`Remove-Item ... data` would delete persisted runtime state."),
]

DATA_FILE_PATTERNS = [
    re.compile(r"(?:^|[\\/])data[\\/]\.env(?:$|\s)", re.IGNORECASE),
    re.compile(r"(?:^|[\\/])data[\\/]config\.ya?ml(?:$|\s)", re.IGNORECASE),
]

PATCH_FILE_PATTERNS = [
    re.compile(r"\*\*\* (?:Add|Update|Delete) File: .*?[\\/]data[\\/]\.env\b", re.IGNORECASE),
    re.compile(r"\*\*\* (?:Add|Update|Delete) File: .*?[\\/]data[\\/]config\.ya?ml\b", re.IGNORECASE),
]


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_walk_strings(item))
        return result
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_walk_strings(item))
        return result
    return []


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        json.dump({"continue": True}, sys.stdout)
        return 0

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {"raw": raw}

    strings = _walk_strings(payload)
    reasons: list[str] = []

    for text in strings:
        for pattern, reason in DANGEROUS_COMMAND_PATTERNS:
            if pattern.search(text):
                reasons.append(reason)

        if any(pattern.search(text) for pattern in PATCH_FILE_PATTERNS):
            reasons.append("This change edits a persisted runtime file under `data/`.")

        if any(pattern.search(text) for pattern in DATA_FILE_PATTERNS):
            if "apply_patch" not in text.lower():
                reasons.append("This tool call references `data/.env` or `data/config.yaml`, which should only change with explicit approval.")

    if not reasons:
        json.dump({"continue": True}, sys.stdout)
        return 0

    unique_reasons = []
    for reason in reasons:
        if reason not in unique_reasons:
            unique_reasons.append(reason)

    json.dump(
        {
            "continue": True,
            "systemMessage": "Persisted deployment state is protected in this repo. Confirm before deleting volumes, removing `data/`, or editing `data/.env` or `data/config.yaml`.",
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": " ".join(unique_reasons),
            },
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())