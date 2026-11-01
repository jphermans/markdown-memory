### memory_search
semantic search in the shared Markdown memory vault; runs server-side, so it works in local and remote sessions (A0 CLI included)
args: `query` (natural-language question, required), optional `limit` (1-10)
returns top matching notes with source path, similarity score and content
read the original note with a file tool before treating its content as fact
do not repeat identical queries within the same task
example:
~~~json
{
  "thoughts": ["Prior project knowledge may exist about the k3s backup setup."],
  "headline": "Searching shared Markdown memory",
  "tool_name": "memory_search",
  "tool_args": {
    "query": "how are k3s backups configured",
    "limit": 5
  }
}
~~~
