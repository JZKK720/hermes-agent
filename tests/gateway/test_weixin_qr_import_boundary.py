"""The weixin plugin must not import back into core.

Regression for the import cycle where ``plugins/platforms/weixin/adapter.py`` imported
``gateway.platforms.weixin_qr_session._normalise_ilink_base_url`` while that module already
imported the adapter — a mutual dependency across the plugin/core boundary
(``plugins/AGENTS.md``: plugins work within the surface core provides, never the reverse).

The iLink normalisation rule is protocol knowledge, so it belongs to the plugin; core keeps a
thin delegate for its own callers. This asserts the direction, so a future edit cannot quietly
re-introduce the back-import.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from plugins.platforms.weixin.adapter import normalise_ilink_base_url

_ADAPTER = pathlib.Path(__file__).resolve().parents[2] / "plugins" / "platforms" / "weixin" / "adapter.py"


def test_the_plugin_never_imports_the_qr_session_module() -> None:
    tree = ast.parse(_ADAPTER.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)

    assert not [m for m in imported if "weixin_qr_session" in m], (
        "the weixin plugin must not import gateway.platforms.weixin_qr_session — that module "
        "already imports this adapter, so it is an import cycle across the plugin/core "
        "boundary. Put the shared rule in the plugin and delegate from core."
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # A canonical URL is kept as the server sent it.
        ("https://ilinkai.weixin.qq.com", "https://ilinkai.weixin.qq.com"),
        # iLink's known typo host (missing `.qq.com`) must not be saved.
        ("https://ilinkai.wechat.com", "https://ilinkai.weixin.qq.com"),
        # A downgraded scheme is not trusted either.
        ("http://ilinkai.weixin.qq.com", "https://ilinkai.weixin.qq.com"),
        # Exact-host match only: a suffix attack must not pass a substring check.
        ("https://ilinkai.weixin.qq.com.evil.com", "https://ilinkai.weixin.qq.com"),
        ("", "https://ilinkai.weixin.qq.com"),
    ],
)
def test_normalisation_is_exact_host_and_falls_back_to_canonical(raw: str, expected: str) -> None:
    assert normalise_ilink_base_url(raw) == expected


def test_core_delegate_agrees_with_the_plugin() -> None:
    """Core keeps a shim for its own callers; it must not drift from the plugin's rule."""
    from gateway.platforms.weixin_qr_session import _normalise_ilink_base_url

    for raw in (
        "https://ilinkai.weixin.qq.com",
        "https://ilinkai.wechat.com",
        "https://ilinkai.weixin.qq.com.evil.com",
    ):
        assert _normalise_ilink_base_url(raw) == normalise_ilink_base_url(raw)
