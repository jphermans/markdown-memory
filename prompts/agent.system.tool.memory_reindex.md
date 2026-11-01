### memory_reindex
refresh the Markdown memory vector index; runs server-side, so it works in local and remote sessions (A0 CLI included)
no args; safe to run repeatedly, unchanged notes are skipped automatically
run it after writing or updating vault notes, and before memory_search when answers may depend on fresh knowledge
returns indexed/skipped/removed counts
example:
~~~json
{
  "thoughts": ["I saved a memory note, so the search index needs a refresh."],
  "headline": "Refreshing Markdown memory index",
  "tool_name": "memory_reindex",
  "tool_args": {}
}
~~~
