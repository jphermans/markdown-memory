"""Plugin API handler: Markdown Memory status and search test.

Routes:
- GET/POST /api/plugins/markdown_memory/status -> runtime status
- POST /api/plugins/markdown_memory/search -> {"query": ...} test search

Never returns the embedding URL itself; only booleans/counts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from helpers.api import ApiHandler, Input, Output, Request

from usr.plugins.markdown_memory.helpers.config import load_config, recall_ready


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_payload() -> dict:
    try:
        config = load_config()
        provider = {
            "configured": bool(config["embedding_url"]),
            "model": config["embedding_model"],
        }
        vault_exists = Path(config["vault_path"]).is_dir()
        index_exists = Path(config["index_path"]).is_file()
        indexed = None
        if index_exists:
            import sqlite3

            try:
                with sqlite3.connect(
                    f"file:{config['index_path']}?mode=ro", uri=True
                ) as conn:
                    indexed = conn.execute(
                        "SELECT COUNT(*) FROM documents WHERE model=?",
                        (config["embedding_model"],),
                    ).fetchone()[0]
            except sqlite3.Error:
                indexed = None
        return {
            "configured": provider["configured"],
            "ready": recall_ready(config),
            "inject_policy": bool(config["inject_policy"]),
            "inject_recall": bool(config["inject_recall"]),
            "provider": provider,
            "vault": {"path": config["vault_path"], "exists": vault_exists},
            "index": {
                "path": config["index_path"],
                "exists": index_exists,
                "documents": indexed,
            },
            "recall_limit": config["recall_limit"],
            "updated_at": _iso_now(),
        }
    except Exception as exc:
        return {
            "configured": False,
            "ready": False,
            "error": type(exc).__name__,
            "updated_at": _iso_now(),
        }


class Status(ApiHandler):
    """Return the current Markdown Memory runtime status."""

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET", "POST"]

    @classmethod
    def requires_csrf(cls) -> bool:
        return False

    async def process(self, input: Input, request: Request) -> Output:
        return _status_payload()
