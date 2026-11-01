from helpers.tool import Tool, Response

from usr.plugins.markdown_memory.scripts.index_granite import run_index


class MemoryReindex(Tool):
    async def execute(self, **kwargs) -> Response:
        try:
            stats = run_index()
        except Exception as exc:
            return Response(
                message=f"Indexing failed: {type(exc).__name__}: {exc}",
                break_loop=False,
            )
        return Response(
            message=(
                f"Index refreshed: indexed={stats['indexed']}, "
                f"skipped={stats['skipped']}, removed={stats['removed']}."
            ),
            break_loop=False,
        )
