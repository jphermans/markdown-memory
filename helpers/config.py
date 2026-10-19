"""Configuration resolution for the Markdown Memory plugin.

Merges ``default_config.yaml`` with the user's ``config.json`` and applies
validation/clamping so every consumer receives a fully-populated, typed
configuration dictionary. The framework only falls back to
``default_config.yaml`` when no config.json exists; this module performs the
merge explicitly so partial user configs keep working.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "inject_policy": True,
    "inject_recall": True,
    "vault_path": "/a0/usr/AI-Memory",
    "index_path": "/a0/usr/AI-Memory-Index/memory-granite.db",
    "embedding_url": "",
    "embedding_model": "granite-embedding:278m",
    "embedding_dimensions": 768,
    "embedding_timeout_seconds": 15,
    "recall_limit": 3,
    "min_message_chars": 5,
    "search_timeout_seconds": 20,
    "max_note_chars": 6000,
}


def _as_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off", ""}:
            return False
    return fallback


def _as_int(value: Any, fallback: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = fallback
    return max(low, min(high, number))


def _as_str(value: Any, fallback: str) -> str:
    return value.strip() if isinstance(value, str) else fallback


def normalize(settings: dict | None) -> dict[str, Any]:
    """Return a complete, validated copy of ``settings`` merged over defaults."""
    merged = copy.deepcopy(DEFAULTS)
    for key, value in (settings or {}).items():
        if key in merged:
            merged[key] = value

    merged["inject_policy"] = _as_bool(merged["inject_policy"], True)
    merged["inject_recall"] = _as_bool(merged["inject_recall"], True)
    merged["vault_path"] = _as_str(merged["vault_path"], str(DEFAULTS["vault_path"]))
    merged["index_path"] = _as_str(merged["index_path"], str(DEFAULTS["index_path"]))
    merged["embedding_url"] = _as_str(merged["embedding_url"], "")
    merged["embedding_model"] = _as_str(
        merged["embedding_model"], str(DEFAULTS["embedding_model"])
    )
    merged["embedding_dimensions"] = _as_int(
        merged["embedding_dimensions"], int(DEFAULTS["embedding_dimensions"]), 1, 8192
    )
    merged["embedding_timeout_seconds"] = _as_int(
        merged["embedding_timeout_seconds"],
        int(DEFAULTS["embedding_timeout_seconds"]),
        1,
        300,
    )
    merged["recall_limit"] = _as_int(merged["recall_limit"], int(DEFAULTS["recall_limit"]), 1, 10)
    merged["min_message_chars"] = _as_int(
        merged["min_message_chars"], int(DEFAULTS["min_message_chars"]), 0, 10_000
    )
    merged["search_timeout_seconds"] = _as_int(
        merged["search_timeout_seconds"],
        int(DEFAULTS["search_timeout_seconds"]),
        1,
        300,
    )
    merged["max_note_chars"] = _as_int(
        merged["max_note_chars"], int(DEFAULTS["max_note_chars"]), 500, 100_000
    )
    return merged


def load_config() -> dict[str, Any]:
    """Load the effective plugin settings (default_config.yaml + config.json)."""
    from helpers.plugins import get_plugin_config

    stored = get_plugin_config("markdown_memory") or {}
    return normalize(stored if isinstance(stored, dict) else {})


def recall_ready(config: dict[str, Any]) -> bool:
    """True when semantic recall has everything it needs."""
    return bool(
        config.get("inject_recall")
        and config.get("embedding_url")
        and Path(str(config.get("vault_path", ""))).is_dir()
        and Path(str(config.get("index_path", ""))).is_file()
    )
