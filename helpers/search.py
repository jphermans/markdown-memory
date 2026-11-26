"""Semantic search over the shared Markdown vault.

Behaviour-compatible with the original inline implementation: Granite query
embeddings via an Ollama-compatible ``/api/embed`` endpoint, cosine similarity
against the SQLite cache, and the exact same note formatting.

Every embedding request goes through embed_text(). Provider and network
failures are reported as SearchError with an actionable message, for example
a model that is missing on the embedding server (HTTP 404) instead of a bare
"HTTP Error 404: Not Found" that suggests a wrong endpoint URL.
"""

from __future__ import annotations

import http.client
import json
import math
import re
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from usr.plugins.markdown_memory.helpers.config import normalize


class SearchError(RuntimeError):
    """Raised when the embedding provider or index cannot be used."""


#: Longest part of the provider's own error text kept in a message.
MAX_ERROR_DETAIL_CHARS = 300


def _request_headers(config: dict[str, Any]) -> dict[str, str]:
    """Content-Type plus Bearer auth only when cloud mode and a key are set."""
    headers = {"Content-Type": "application/json"}
    api_key = str(config.get("embedding_api_key") or "").strip()
    if config.get("embedding_cloud") and api_key:
        headers["Authorization"] = "Bearer " + api_key
    return headers


def _extract_vector(data: dict[str, Any]) -> list[float]:
    """Accept both Ollama (embeddings[0]) and OpenAI (data[0].embedding) shapes."""
    embeddings = data.get("embeddings")
    if isinstance(embeddings, list) and embeddings:
        return embeddings[0]
    items = data.get("data")
    if isinstance(items, list) and items and isinstance(items[0], dict):
        vector = items[0].get("embedding")
        if isinstance(vector, list):
            return vector
    raise SearchError("Unexpected embedding response format from provider")


def _redact(text: str, config: dict[str, Any]) -> str:
    """Keep the API key and the endpoint URL out of error messages."""
    for value in (
        str(config.get("embedding_api_key") or "").strip(),
        str(config.get("embedding_url") or "").strip(),
    ):
        # Very short values would only mangle the message; real keys and URLs are longer.
        if value and len(value) >= 8:
            text = text.replace(value, "***")
    return text


def _error_detail(exc: urllib.error.HTTPError, config: dict[str, Any]) -> str:
    """Return the provider's own error text, bounded and without secrets."""
    try:
        raw = exc.read(2048)
    except Exception:
        return ""
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw or "")
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            text = str(error.get("message") or error.get("detail") or error.get("code") or text)
        elif isinstance(error, str) and error:
            text = error
        else:
            text = str(data.get("message") or data.get("detail") or text)
    return _redact(" ".join(text.split()), config)[:MAX_ERROR_DETAIL_CHARS]


def _is_missing_model_detail(detail: str) -> bool:
    """Recognise the common wording embedding providers use for an unknown model."""
    lowered = detail.lower()
    return "model" in lowered and ("not found" in lowered or "not exist" in lowered)


def _invalid_url_error(exc: Exception) -> SearchError:
    """Report a URL the HTTP client cannot use; no request was sent yet.

    No part of the configured URL is repeated: the client's reason text can
    contain the scheme, host or path of the URL.
    """
    text = str(getattr(exc, "reason", exc))
    lowered = text.lower()
    if "unknown url type" in lowered:
        reason = "the URL scheme is missing or is not http or https"
    elif "no host given" in lowered:
        reason = "the URL has no host"
    elif "port can't be converted" in lowered or "nonnumeric port" in lowered:
        reason = "the port is not a number"
    else:
        match = re.search(r"found at least (.*?)\)?$", text)
        if match:
            reason = "the URL contains a character that is not allowed: " + match.group(1)
        else:
            reason = "the HTTP client rejected it"
    return SearchError(
        f"Invalid embedding_url ({reason}). Use a complete URL with scheme, "
        "host and path, for example http://<embedding-host>:11434/api/embed."
    )


def _provider_error(exc: Exception, config: dict[str, Any]) -> SearchError:
    """Translate a failed embedding request into an actionable SearchError."""
    model = str(config.get("embedding_model") or "")
    if isinstance(exc, urllib.error.HTTPError):
        status = exc.code
        detail = _error_detail(exc, config)
        detail_part = " (" + detail + ")" if detail else ""
        if status == 404 and _is_missing_model_detail(detail):
            return SearchError(
                f"Embedding model '{model}' is not available on the embedding server "
                f"(HTTP {status}: {detail}). Pull or install the model there "
                f"(for Ollama: ollama pull {model}), or set embedding_model to an "
                "installed model and run a full re-index."
            )
        if status == 404:
            return SearchError(
                f"Embedding provider answered HTTP {status}{detail_part}. Check that "
                "embedding_url points to the provider's /api/embed endpoint and that "
                "embedding_model exists on that server."
            )
        if status in (401, 403):
            return SearchError(
                f"Embedding provider rejected the request (HTTP {status}"
                + (": " + detail if detail else "")
                + "). Check the API key and the embedding_cloud setting."
            )
        return SearchError(f"Embedding provider answered HTTP {status}{detail_part}.")
    if isinstance(exc, urllib.error.URLError):
        if isinstance(exc.reason, TimeoutError):
            return SearchError(
                "Embedding provider timed out. Check the server load or raise "
                "embedding_timeout_seconds."
            )
        reason_text = str(exc.reason)
        if "unknown url type" in reason_text or "no host given" in reason_text:
            return _invalid_url_error(exc)
        return SearchError(
            f"Embedding provider unreachable: {_redact(str(exc.reason), config)}. "
            "Check embedding_url and that the embedding server is running."
        )
    if isinstance(exc, TimeoutError):
        return SearchError(
            "Embedding provider timed out. Check the server load or raise "
            "embedding_timeout_seconds."
        )
    return SearchError(
        f"Embedding request failed: {type(exc).__name__}: {_redact(str(exc), config)}"
    )


def embed_text(text: str, config: dict[str, Any], timeout: int | None = None) -> list[float]:
    """Embed one text with the configured provider and validate its dimension.

    This is the single embedding request for recall, the agent tools, the
    search API and the indexer. Raises :class:`SearchError` when the provider
    rejects the request, cannot be reached, answers in an unexpected format, or
    when `embedding_url` itself cannot be used.
    """
    payload = json.dumps({"model": config["embedding_model"], "input": text}).encode("utf-8")

    seconds = config["embedding_timeout_seconds"] if timeout is None else timeout
    try:
        request = urllib.request.Request(
            config["embedding_url"],
            data=payload,
            headers=_request_headers(config),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=seconds) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise _provider_error(exc, config) from exc
    except http.client.InvalidURL as exc:
        raise _invalid_url_error(exc) from exc
    except http.client.HTTPException as exc:
        raise SearchError(
            "Embedding provider sent a malformed or incomplete response: "
            f"{type(exc).__name__}: {_redact(str(exc), config)}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise _provider_error(exc, config) from exc
    except ValueError as exc:
        # urllib raises this for a URL without a usable scheme or host, before any request is sent.
        raise _invalid_url_error(exc) from exc

    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise SearchError("Embedding provider returned a response that is not valid JSON") from exc

    vector = _extract_vector(data)

    expected = config["embedding_dimensions"]
    if len(vector) != expected:
        raise SearchError(f"Unexpected embedding dimension: {len(vector)} != {expected}")
    return vector


def _embed_query(query: str, config: dict[str, Any]) -> list[float]:
    return embed_text("search_query: " + query[:2000], config)


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
