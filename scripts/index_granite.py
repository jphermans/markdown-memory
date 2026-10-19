#!/usr/bin/env python3
"""Rebuild or refresh the Granite vector index for the Markdown vault.

Drop-in compatible with the historical ``/a0/usr/AI-Memory-Index/index_granite.py``
workflow, but fully configuration-driven through the plugin settings.

Usage inside the Agent Zero container:

    /opt/venv-a0/bin/python -m usr.plugins.markdown_memory.scripts.index_granite

Or as a plain script when the plugin directory is on PYTHONPATH.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Allow running both as a module and as a plain script.
try:
    from usr.plugins.markdown_memory.helpers.config import load_config
except ImportError:  # plain-script execution
    sys.path.insert(0, "/a0")
    from usr.plugins.markdown_memory.helpers.config import load_config


def embed(text: str, config: dict) -> str:
    payload = json.dumps(
        {"model": config["embedding_model"], "input": text}
    ).encode("utf-8")

    request = urllib.request.Request(
        config["embedding_url"],
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        data = json.load(response)

    vector = data["embeddings"][0]
    if len(vector) != config["embedding_dimensions"]:
        raise ValueError(
            f"Unexpected embedding dimension: {len(vector)} != {config['embedding_dimensions']}"
        )

    return json.dumps(vector)


def main() -> int:
    try:
        config = load_config()
    except Exception as exc:
        print(f"Config unavailable ({type(exc).__name__}); cannot index.", file=sys.stderr)
        return 1

    if not config["embedding_url"]:
        print("embedding_url is not configured; cannot index.", file=sys.stderr)
        return 1

    vault = Path(config["vault_path"])
    db_path = Path(config["index_path"])
    model = config["embedding_model"]

    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                path TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                embedding TEXT NOT NULL,
                model TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """
        )

        files = sorted(vault.rglob("*.md"))
        current_paths = set()
        indexed = 0
        skipped = 0

        for file in files:
            if file.is_symlink():
                continue

            relative = str(file.relative_to(vault))
            current_paths.add(relative)

            content = file.read_text(encoding="utf-8")
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

            row = conn.execute(
                "SELECT content_hash, model FROM documents WHERE path=?",
                (relative,),
            ).fetchone()

            if row == (digest, model):
                skipped += 1
                continue

            print(f"Indexing: {relative}", flush=True)
            vector = embed(f"passage: {content}", config)

            conn.execute(
                """
                INSERT INTO documents
                    (path, content_hash, embedding, model, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    content_hash=excluded.content_hash,
                    embedding=excluded.embedding,
                    model=excluded.model,
                    updated_at=excluded.updated_at
            """,
                (
                    relative,
                    digest,
                    vector,
                    model,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            indexed += 1

        # Remove records for Markdown files that no longer exist.
        rows = conn.execute("SELECT path FROM documents").fetchall()
        removed = 0

        for (path,) in rows:
            if path not in current_paths:
                conn.execute("DELETE FROM documents WHERE path=?", (path,))
                removed += 1

        conn.commit()

    print(f"Finished: indexed={indexed}, skipped={skipped}, removed={removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
