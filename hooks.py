"""Lifecycle and settings hooks for the Markdown Memory plugin.

No external dependencies are required: the plugin uses only the Python
standard library. The shared vault and the SQLite index are user data and are
never created, moved, or deleted by lifecycle hooks.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from usr.plugins.markdown_memory.helpers.config import DEFAULTS, normalize

SECRET_KEYS = ("embedding_url",)
MASK = "***"


def _load_stored_settings(project_name: str = "", agent_profile: str = "") -> dict:
    """Best-effort read of the stored config.json without the full stack."""
    from helpers.plugins import find_plugin_asset

    entries = find_plugin_asset(
        "markdown_memory",
        "config.json",
        project_name=project_name or "",
        agent_profile=agent_profile or "",
    )
    entry = entries if isinstance(entries, dict) else None
    path = (entry or {}).get("path", "")
    if path and Path(path).is_file():
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8") or "{}")
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
    return {}


def get_plugin_config(default=None, hook_context=None, **kwargs) -> dict[str, Any]:
    """Return a fully-populated config; mask internal URLs for UI callers."""
    config = normalize(default if isinstance(default, dict) else None)
    caller = (hook_context or {}).get("caller", "api")
    if caller == "ui":
        for key in SECRET_KEYS:
            if str(config.get(key) or "").strip():
                config[key] = MASK
    return config


def save_plugin_config(
    settings=None, default=None, project_name=None, agent_profile=None, **kwargs
) -> dict[str, Any]:
    """Persist settings; keep stored internal URLs when the UI submits masks."""
    submitted = copy.deepcopy(settings if isinstance(settings, dict) else default)
    stored = _load_stored_settings(
        project_name=project_name or "", agent_profile=agent_profile or ""
    )
    for key in SECRET_KEYS:
        if submitted and str(submitted.get(key, "")).strip() == MASK:
            submitted[key] = stored.get(key, "")
    return normalize(submitted)


def install() -> bool:
    """Idempotent post-install/update initialization.

    Verifies that the plugin code is importable in the framework runtime and
    that the bundled policy is readable. Creates no external state.
    """
    import usr.plugins.markdown_memory.helpers.config  # noqa: F401

    policy = (
        Path(__file__).resolve().parent / "prompts" / "policy.md"
    )
    if not policy.is_file():
        raise FileNotFoundError("Bundled prompts/policy.md is missing")
    return True


def pre_update() -> bool:
    """Prepare for a code update; plugin keeps no owned processes."""
    return True


def uninstall() -> bool:
    """Cleanup before directory deletion.

    The Markdown vault and the SQLite index are user data and are preserved.
    Only plugin-owned in-framework state would be removed here; there is none
    beyond the plugin directory itself.
    """
    return True
