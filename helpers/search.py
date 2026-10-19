"""Semantic search over the shared Markdown vault.

Behaviour-compatible with the original inline implementation: Granite query
embeddings via an Ollama-compatible ``/api/embed`` endpoint, cosine similarity
against the SQLite cache, and the exact same note formatting.
"""

from __future__ import annotations

import json
import math
import sqlite3
import urllib.request
from pathlib import Path
from typing import Any

from usr.plugins.markdown_memory.helpers.config import normalize


class SearchError(RuntimeError):
    """Raised when the embedding provider or index cannot be used."""


def _embed_query(query: str, config: dict[str, Any]) -> list[float]:
    payload = json.dumps(
        {
            "model": config["embedding_model"],
            "input": "search_query: " + query[:2000],
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        config["embedding_url"],
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    timeout = config["embedding_timeout_seconds"]
    with urllib.request.urlopen(request, timeout=timeout) as response:
        vector = json.load(response)["embeddings"][0]

    expected = config["embedding_dimensions"]
    if len(vector) != expected:
        raise SearchError(
            f"Unexpected embedding dimension: {len(vector)} != {expected}"
        )
    return vector


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def _rank(query: str, config: dict[str, Any]) -> list[tuple[float, str]]:
    vector = _embed_query(query, config)

    with sqlite3.connect(f"file:{config['index_path']}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT path, embedding FROM documents WHERE model=?",
            (config["embedding_model"],),
        ).fetchall()

    matches: list[tuple[float, str]] = []
    for relative_path, stored_embedding in rows:
        other = json.loads(stored_embedding)
        if len(other) != len(vector):
            continue
        score = _cosine_similarity(vector, other)
        matches.append((score, relative_path))

    matches.sort(reverse=True)
    return matches


def _safe_result_paths(matches, vault: Path):
    """Yield (score, relative_path, absolute_path) for safe vault matches."""
    for score, relative_path in matches:
        path = (vault / relative_path).resolve()
        if not path.is_relative_to(vault) or path.suffix != ".md":
            continue
        if not path.is_file():
            continue
        yield score, relative_path, path


def search_notes(query: str, settings: dict | None = None, limit: int | None = None) -> str:
    """Return the top matching vault notes formatted for prompt injection.

    Raises :class:`SearchError` on provider or index failures so callers can
    degrade gracefully.
    """
    config = normalize(settings)
    vault = Path(config["vault_path"]).resolve()
    max_notes = config["recall_limit"] if limit is None else max(1, min(10, int(limit)))

    notes: list[str] = []
    for score, relative_path, path in _safe_result_paths(_rank(query, config), vault):
        if len(notes) >= max_notes:
            break
        try:
            content = path.read_text(encoding="utf-8")[: config["max_note_chars"]]
        except (OSError, UnicodeDecodeError):
            continue
        notes.append(
            f"Source: {relative_path}\n"
            f"Similarity: {score:.3f}\n"
            f"{content}"
        )

    return "\n\n---\n\n".join(notes)


def search_results(
    query: str, settings: dict | None = None, limit: int | None = None
) -> list[dict[str, Any]]:
    """Structured results for API/UI consumers (no note bodies)."""
    config = normalize(settings)
    vault = Path(config["vault_path"]).resolve()
    max_notes = config["recall_limit"] if limit is None else max(1, min(10, int(limit)))

    results: list[dict[str, Any]] = []
    for score, relative_path, path in _safe_result_paths(
        _rank(query, config), vault
    ):
        results.append(
            {
                "path": relative_path,
                "title": path.stem,
                "similarity": round(score, 4),
            }
        )
        if len(results) >= max_notes:
            break
    return results
