# Markdown Memory — Agent Zero Plugin

**Version:** 1.2.0 · **Author:** jphermans · **License:** MIT

![Markdown Memory](webui/thumbnail.png)

Shared, Obsidian-compatible Markdown memory for every Agent Zero chat: operating-policy injection, semantic recall via local Ollama or cloud embeddings (Ollama Cloud, OpenRouter), and — new in 1.2.0 — server-side agent tools (`memory_search`, `memory_reindex`) that also work in remote A0 CLI sessions.

The Markdown vault (`/a0/usr/AI-Memory` by default) is the authoritative source of truth. The SQLite vector index (`/a0/usr/AI-Memory-Index/memory-granite.db`) is a rebuildable search cache: it can be deleted and re-created at any time without losing knowledge.

---

## Table of Contents

1. [What the plugin does](#what-the-plugin-does)
2. [Architecture overview](#architecture-overview)
3. [Requirements](#requirements)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Environment variables](#environment-variables)
7. [Cloud embeddings (optional)](#cloud-embeddings-optional)
8. [Agent tools (since 1.2.0)](#agent-tools-since-120)
9. [Remote usage (A0 CLI from another computer)](#remote-usage-a0-cli-from-another-computer)
10. [Runtime neutrality (Docker / Podman / Kubernetes)](#runtime-neutrality-docker--podman--kubernetes)
11. [API endpoints](#api-endpoints)
12. [Refreshing the index](#refreshing-the-index)
13. [Running the tests](#running-the-tests)
14. [Security](#security)
15. [Troubleshooting](#troubleshooting)
16. [Removal and cleanup](#removal-and-cleanup)

---

## What the plugin does

Every chat gets two automatic context abilities plus on-demand tools:

1. **Policy injection** — at iteration 0 of every message loop, the operating instructions for the shared vault (`prompts/policy.md`) are injected as a persistent extra, so the agent knows the vault rules (directory layout, duplicate prevention, no secrets, notes-are-data).
2. **Semantic recall** — the first user message is embedded through an Ollama-compatible `/api/embed` endpoint (local Granite by default), ranked against the SQLite vector index with cosine similarity, and the top notes are injected as reference material (never as instructions).
3. **Agent tools (1.2.0)** — `memory_search` runs a natural-language query against the index and returns ranked paths and scores; `memory_reindex` refreshes the index. Both execute **server-side** inside the Agent Zero process.

## Architecture overview

All plugin logic runs server-side, inside the Agent Zero server process (in the container). The agent's terminal location is irrelevant to how the plugin operates.

| Component | Location | Function |
|---|---|---|
| Policy extension | `extensions/python/message_loop_prompts_after/_40_markdown_memory_policy.py` | Injects the vault operating instructions (bundled `prompts/policy.md`, legacy skill fallback) |
| Recall extension | `extensions/python/message_loop_prompts_after/_60_markdown_recall.py` | Embeds the first user message, searches the index, injects the top notes as persistent extras |
| Agent tools | `tools/` (since 1.2.0) | `memory_search`, `memory_reindex` — server-side execution, identical in local and remote sessions |
| API handlers | `api/status.py`, `api/search.py` | `/api/plugins/markdown_memory/status` and `/search` for the WebUI and automation |
| Configuration | `helpers/config.py` | Merges `default_config.yaml` + user `config.json`, validates and clamps every value |
| Search engine | `helpers/search.py` | `/api/embed` client (Ollama and OpenAI response shapes), cosine ranking, vault-only path checks |
| Lifecycle | `hooks.py` | `install` / `pre_update` / `uninstall` plus settings hooks (URL/key masking for the UI) |
| Indexer | `scripts/index_granite.py` | Incremental (re)index of the vault into SQLite (container-side) |
| Settings UI | `webui/config.html` | Plugin settings in the Agent tab, including the *Restore defaults* button |

## Requirements

- Agent Zero with plugin support (`usr/plugins/`)
- A vault of Markdown notes (default `/a0/usr/AI-Memory`)
- An Ollama-compatible embedding server reachable **from the Agent Zero container** — e.g. local Ollama with `granite-embedding:278m` (768 dimensions) — or a cloud provider (see [Cloud embeddings](#cloud-embeddings-optional))
- No extra Python dependencies: the plugin uses only the standard library

## Installation

### Via the Plugin UI (Git)

1. Open **Settings → Plugins → Install from Git**.
2. Enter the repository URL: `https://github.com/jphermans/markdown-memory.git`
3. Confirm the installation. The `install()` hook verifies the code and the bundled policy; no extra manual step is required.

### Manually (container shell)

```bash
git clone https://github.com/jphermans/markdown-memory.git /a0/usr/plugins/markdown_memory
```

Restart Agent Zero or wait for the plugin cache to refresh; the plugin is active immediately afterwards (enabled by default).

After installation, verify via `GET /api/plugins/markdown_memory/status`: `configured`, `inject_policy` and `inject_recall` should be `true`, and once an index exists, `ready` becomes `true`.

## Configuration

Defaults live in `default_config.yaml`. User overrides are stored in `usr/plugins/markdown_memory/config.json` (automatically gitignored; may contain internal endpoint URLs) or set via **Settings → Agent → Markdown Memory**.

| Key | Default | Meaning |
|---|---|---|
| `inject_policy` | `true` | Inject vault operating instructions |
| `inject_recall` | `true` | Inject semantic recall |
| `vault_path` | `/a0/usr/AI-Memory` | Directory with Markdown notes |
| `index_path` | `/a0/usr/AI-Memory-Index/memory-granite.db` | SQLite vector index |
| `embedding_url` | `""` (empty) | Ollama-compatible `/api/embed` endpoint; empty = recall off |
| `embedding_cloud` | `false` | Send `Authorization: Bearer` with the API key (enable only for cloud endpoints) |
| `embedding_api_key` | `""` (empty) | Cloud API key (Ollama Cloud / OpenRouter); masked in the UI |
| `embedding_model` | `granite-embedding:278m` | Provider model name |
| `embedding_dimensions` | `768` | Expected vector dimension |
| `embedding_timeout_seconds` | `15` | Provider HTTP timeout (1–300) |
| `recall_limit` | `3` | Number of notes per recall (1–10) |
| `min_message_chars` | `5` | Minimum first-message length for recall |
| `search_timeout_seconds` | `20` | Maximum duration of one recall search |
| `max_note_chars` | `6000` | Truncation length per injected note (500–100000) |

Settings apply per installation: `plugin.yaml` declares `per_project_config: false` and `per_agent_config: false`, because the plugin intentionally maintains one shared vault.

### Choosing the vault location (host folder)

The `vault_path` setting is always a **container-side** path and defaults to
`/a0/usr/AI-Memory`. To store the Markdown files in a folder **on the host
machine**, mount the host folder onto that path — do not change `vault_path`:

| Runtime | Mount |
|---|---|
| Docker | `-v /home/you/AI-Memory:/a0/usr/AI-Memory` |
| Podman | same `-v` flag as Docker |
| Kubernetes | `hostPath` volume mounted at `/a0/usr/AI-Memory` |

Example Kubernetes volume for a single-node cluster:

```yaml
volumes:
  - name: vault
    hostPath:
      path: /home/you/AI-Memory
      type: Directory
```

…mounted on the Agent Zero container with:

```yaml
volumeMounts:
  - name: vault
    mountPath: /a0/usr/AI-Memory
```

Ownership tip: when Agent Zero runs as root (common in containers), files it
creates on the host become root-owned. Add an initContainer, or a small host
cron job run periodically as root:

```bash
find /home/you/AI-Memory -user root -exec chown you:yourgroup {} +
```

Only change `vault_path` in Settings (or
`A0_SET_MARKDOWN_MEMORY__VAULT_PATH`) when you want a different path
**inside** the container; the host folder choice is always made on the
mount side.

#### How it works: one folder, two paths

After the mount is active, the container path and the host path are
**the same physical folder** — not a copy and not a sync:

```
Agent Zero (container)  ── reads/writes ──►  /a0/usr/AI-Memory     ┐
                                                                   ├──  ONE folder on the host disk
You / Obsidian / backup ── reads/writes ──►  /home/you/AI-Memory   ┘
```

- **The plugin keeps working unchanged:** `vault_path` still points at
  `/a0/usr/AI-Memory`; recall, `memory_search`, `memory_reindex` and
  server-side file tools all keep using that path.
- **Everything is stored on the host disk:** notes the agent writes appear
  immediately in your host folder, and edits you make on the host
  (for example in Obsidian) are immediately visible to the agent.
- **"Are my notes still in `/a0/usr/AI-Memory`?" Yes.** Both paths are
  names for the same folder — there is exactly one copy of the data.
- **Verify it yourself** — the hashes must match:

  ```bash
  # inside the Agent Zero container
  sha256sum /a0/usr/AI-Memory/MEMORY.md
  # on the host
  sha256sum /home/you/AI-Memory/MEMORY.md
  ```

Migration note: anything already stored at the container path (inside the
image or a PVC) is **shadowed** by the mount while it is active — the host
folder becomes the single source of truth. If you migrate an existing
vault, copy its files into the host folder **before** mounting the path
(or with the container stopped), so nothing appears to "disappear".

### Restore defaults button (since 1.1.1)

The settings panel has a **Restore defaults** button that restores the embedding-related defaults in one click: the local Ollama endpoint of this installation, `granite-embedding:278m`, 768 dimensions, cloud off, no API key, and the standard recall/timeout values. It does **not** change the vault/index paths or the injection toggles. Press **Save** afterwards to persist.

### Example `config.json`

```json
{
  "embedding_url": "http://internal.example:11434/api/embed"
}
```

## Environment variables

Every setting can be pre-seeded with an environment variable. **Verified prefix form (framework `helpers/plugins.py` + `helpers/settings.py`):**

```
A0_SET_MARKDOWN_MEMORY__<KEY>
```

The framework builds `<plugin>__<KEY>` from `default_config.yaml` (double underscore between plugin name and key) and reads `A0_SET_<name>` (upper-case form is canonical). Values are type-normalized: booleans accept `true/1/yes/on`, numbers are cast, strings are trimmed; an invalid value logs a warning and falls back to the default.

| Environment variable | Config key |
|---|---|
| `A0_SET_MARKDOWN_MEMORY__INJECT_POLICY` | `inject_policy` |
| `A0_SET_MARKDOWN_MEMORY__INJECT_RECALL` | `inject_recall` |
| `A0_SET_MARKDOWN_MEMORY__VAULT_PATH` | `vault_path` |
| `A0_SET_MARKDOWN_MEMORY__INDEX_PATH` | `index_path` |
| `A0_SET_MARKDOWN_MEMORY__EMBEDDING_URL` | `embedding_url` |
| `A0_SET_MARKDOWN_MEMORY__EMBEDDING_CLOUD` | `embedding_cloud` |
| `A0_SET_MARKDOWN_MEMORY__EMBEDDING_API_KEY` | `embedding_api_key` |
| `A0_SET_MARKDOWN_MEMORY__EMBEDDING_MODEL` | `embedding_model` |
| `A0_SET_MARKDOWN_MEMORY__EMBEDDING_DIMENSIONS` | `embedding_dimensions` |
| `A0_SET_MARKDOWN_MEMORY__EMBEDDING_TIMEOUT_SECONDS` | `embedding_timeout_seconds` |
| `A0_SET_MARKDOWN_MEMORY__RECALL_LIMIT` | `recall_limit` |
| `A0_SET_MARKDOWN_MEMORY__MIN_MESSAGE_CHARS` | `min_message_chars` |
| `A0_SET_MARKDOWN_MEMORY__SEARCH_TIMEOUT_SECONDS` | `search_timeout_seconds` |
| `A0_SET_MARKDOWN_MEMORY__MAX_NOTE_CHARS` | `max_note_chars` |

**Precedence (verified):** environment values are applied on top of `default_config.yaml` when no `config.json` exists yet. Once settings are saved from the UI (creating `config.json`), the stored values take precedence over environment variables.

## Cloud embeddings (optional)

Cloud use is **off by default**: with the *Cloud embeddings* checkbox off, no `Authorization` header is sent and the plugin talks to the local Ollama endpoint exactly as before.

To use a cloud provider:

1. Set **Embedding endpoint** to the cloud URL.
2. Enable **Cloud embeddings**.
3. Fill **Embedding API key** (stored masked; see [Security](#security)).
4. Set **Embedding model** and **Embedding dimensions** to match the chosen model (see table).
5. Re-run the indexer — switching models always requires a full re-index.

| Provider | Endpoint URL | Example model | Default dims | Verified |
|---|---|---|---|---|
| Ollama Cloud | `https://ollama.com/api/embed` | `nomic-embed-text` | 768 | API contract (live test needs a cloud key) |
| OpenRouter | `https://openrouter.ai/api/v1/embeddings` | `nvidia/nemotron-3-embed-1b:free` | 2048 | yes (live) |
| OpenRouter | `https://openrouter.ai/api/v1/embeddings` | `liquid/lfm-2.5-embedding-350m:free` | 1024 | yes (live) |
| OpenRouter | `https://openrouter.ai/api/v1/embeddings` | `openai/text-embedding-3-small` | 1536 | yes (live) |

Notes:

- The plugin sends `{model, input}` and accepts both Ollama (`embeddings[0]`) and OpenAI (`data[0].embedding`) response shapes automatically.
- API keys: OpenRouter from openrouter.ai/keys; Ollama Cloud from ollama.com (account → API keys).
- The key is stored in `config.json` (gitignored) and always shown masked in the UI, or provided via `A0_SET_MARKDOWN_MEMORY__EMBEDDING_API_KEY`.
- Privacy: with a cloud provider, note content used for embeddings leaves your infrastructure.

## Agent tools (since 1.2.0)

The plugin registers two server-side agent tools:

| Tool | Arguments | Function |
|---|---|---|
| `memory_search` | `query` (string), optional `limit` (1–10) | Semantic search over the index; returns ranked paths, titles and similarity scores |
| `memory_reindex` | — | Incrementally refreshes the SQLite index from the vault |

Both tools run inside the Agent Zero server process, so they work identically in local sessions and in remote A0 CLI sessions (see next section). The bundled policy is **tools-first**: agents are instructed to prefer these tools over the legacy container-side shell scripts.

## Remote usage (A0 CLI from another computer)

When a session is connected through A0 CLI, the **agent terminal executes on the client computer** (e.g. your laptop). Container paths such as `/a0/...` do **not** exist there. This has practical consequences:

- **Use the server-side tools.** `memory_search` and `memory_reindex` run inside Agent Zero itself and are the correct route from any remote session.
- **Recall just works.** Automatic policy and recall injection happen server-side at iteration 0 and need no local shell at all.
- **Reading notes** works with server-side file tools (e.g. the text editor) — they resolve paths inside the container, not on the laptop.
- **Shell instructions are container-side only.** Commands like the indexer invocation in [Refreshing the index](#refreshing-the-index) must never be run on the remote host; they only work inside the Agent Zero container (or via `kubectl exec`/`docker exec` into it).

## Runtime neutrality (Docker / Podman / Kubernetes)

The plugin is runtime-neutral. It uses only container-internal absolute paths and standard-library Python, with no calls specific to a container engine. Behaviour is identical under Docker, Podman and Kubernetes.

- **Paths are container paths.** `vault_path` and `index_path` mean the same thing in every runtime.
- **Persistence is a deployment choice.** Where the vault lives on the host is determined by the mount, not by the plugin: Docker/Podman bind mounts (e.g. `-v /host/path:/a0/usr`) or Kubernetes PVC / hostPath volumes.
- **Recreating the container** without a persistent mount loses the vault and index; always mount `/a0/usr` (or at least the vault and index directories) when durability matters.

## API endpoints

| Route | Method | Function |
|---|---|---|
| `/api/plugins/markdown_memory/status` | GET/POST | Runtime status: provider configured, cloud flag, key set, vault/index present, indexed document count |
| `/api/plugins/markdown_memory/search` | POST | Test search: `{"query": "...", "limit": 3}` → paths + scores (without note bodies) |

Both endpoints require normal Agent Zero authentication. The status payload contains booleans/counts only — the embedding URL itself is never returned.

## Refreshing the index

After adding or changing notes (inside the Agent Zero container, or via `memory_reindex` from any session):

```bash
cd /a0 && /opt/venv-a0/bin/python -m usr.plugins.markdown_memory.scripts.index_granite
```

The indexer is incremental: unchanged notes are skipped (content hash), changed notes are re-embedded (with the `passage: ` prefix) and deleted notes are removed from the index.

## Running the tests

Inside the Agent Zero container:

```bash
cd /a0 && /opt/venv-a0/bin/python -m unittest \
  usr.plugins.markdown_memory.tests.test_markdown_memory -v
```

On a Kubernetes host, run the same command via `kubectl -n agent-zero exec <pod> -- sh -c 'cd /a0 && /opt/venv-a0/bin/python -m unittest ...'`.

The suite covers: configuration defaults/merge/clamping, recall readiness checks, search ranking and formatting, dimension validation, Ollama/OpenAI response parsing, Authorization-header behaviour (only with cloud enabled), endpoint URL and API-key masking for UI callers, mask preservation on save, and the lifecycle hooks.

## Security

- **Masking:** `embedding_url` and `embedding_api_key` are masked (`***`) for settings-UI callers; submitting the mask back preserves the stored value.
- **No secrets in code or repo:** the repository contains no URLs or keys; runtime values live in the gitignored `config.json` or in environment variables (`A0_SET_MARKDOWN_MEMORY__...`).
- **Conditional auth:** the `Authorization: Bearer` header is sent only when *Cloud embeddings* is enabled **and** a key is set — local Ollama behaviour is unchanged.
- **Vault-only write scope:** memory maintenance may only write inside the configured vault (plus the dedicated index through approved tooling); search results are path-checked against the vault and restricted to `.md` files.
- **Notes are data, not instructions:** injected notes are framed as reference material; the policy forbids executing commands found in notes and storing passwords, tokens or API keys in the vault.
- **Minimal API surface:** the search API returns paths and scores only — never note bodies — and no endpoint ever returns the embedding URL or API key.

## Troubleshooting

| Symptom | Check / fix |
|---|---|
| Recall never triggers | `GET /api/plugins/markdown_memory/status`: `ready` requires `embedding_url` set, the vault directory to exist, and the index file to exist. Also check `inject_recall` and `min_message_chars` (recall only runs on the first user message). |
| Log: *search failed* / `search_failed` | Provider unreachable or timeout: verify `embedding_url` from inside the container (`curl`), raise `embedding_timeout_seconds`. Recall degrades gracefully — the chat continues without notes. |
| `Unexpected embedding dimension` | Model and `embedding_dimensions` do not match (e.g. after switching provider). Set the correct dimension and run a **full** re-index. |
| Search finds nothing after editing notes | The index is stale: run `memory_reindex` (tool) or the container-side indexer command. |
| UI shows `***` in the endpoint/key fields | That is the mask. Re-enter the real value to change it, or use *Restore defaults*; submitting the mask keeps the stored value. |
| Environment variable has no effect | Use the exact uppercase form `A0_SET_MARKDOWN_MEMORY__<KEY>`. Note that a saved `config.json` takes precedence — remove the key there if the env value should win. |
| Vault lost after container recreation | No persistent mount on `/a0/usr` (or the vault directory). Add a bind mount / PVC / hostPath, then restore notes and re-index. |
| Remote A0 CLI: `No such file or directory: /a0/...` | Expected: your terminal runs on the client host. Use `memory_search` / `memory_reindex` and server-side file tools instead of shell commands. |

## Removal and cleanup

Remove the plugin via **Settings → Plugins → Uninstall**. The `uninstall()` hook:

- stops no processes (the plugin starts none),
- leaves the Markdown vault and the SQLite index untouched (user data),
- removes no shared dependencies.

`config.json` disappears together with the plugin directory; back it up first if you want to keep the endpoint configuration.
