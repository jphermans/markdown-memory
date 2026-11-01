from helpers.tool import Tool, Response

from usr.plugins.markdown_memory.helpers.config import load_config
from usr.plugins.markdown_memory.helpers.search import SearchError, search_notes


class MemorySearch(Tool):
    async def execute(self, query: str = "", limit=None, **kwargs) -> Response:
        query = str(query or "").strip()
        if not query:
            return Response(
                message='Error: provide a search query in tool_args, e.g. {"query": "k3s backups"}.',
                break_loop=False,
            )
        try:
            result = search_notes(query, settings=load_config(), limit=limit)
        except SearchError as exc:
            return Response(message=f"Search failed: {exc}", break_loop=False)
        except Exception as exc:
            return Response(
                message=f"Search failed unexpectedly: {type(exc).__name__}: {exc}",
                break_loop=False,
            )
        if not result.strip():
            return Response(message="No matching notes found.", break_loop=False)
        return Response(message=result, break_loop=False)
