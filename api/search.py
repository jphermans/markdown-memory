"""Plugin API handler: Markdown Memory test search.

Route: POST /api/plugins/markdown_memory/search
Body: {"query": "...", "limit": 3}
Returns structured results without note bodies.
"""

from __future__ import annotations

from helpers.api import ApiHandler, Input, Output, Request

from usr.plugins.markdown_memory.helpers.config import load_config, recall_ready
from usr.plugins.markdown_memory.helpers.search import SearchError, search_results


class Search(ApiHandler):
    """Run a test search and return structured results (no note bodies)."""

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: Input, request: Request) -> Output:
        data = input if isinstance(input, dict) else {}
        query = str(data.get("query", "")).strip()
        if len(query) < 3:
            return {"error": "query_too_short", "results": []}

        try:
            config = load_config()
            if not recall_ready(config):
                return {"error": "recall_not_ready", "results": []}
            results = search_results(query, config, limit=int(data.get("limit", 3)))
            return {"query": query, "results": results}
        except SearchError as exc:
            return {"error": "search_failed", "detail": str(exc)[:200], "results": []}
        except Exception as exc:
            return {"error": type(exc).__name__, "results": []}
