# Markdown Memory — Agent Zero Plugin

**Version:** 1.0.1 · **Author:** jphermans · **License:** MIT

![Markdown Memory](webui/thumbnail.png)

Shared, Obsidian-compatible Markdown memory with semantic recall via local Granite embeddings for every Agent Zero chat.

---

## Table of Contents

1. [Purpose](#purpose)
2. [Requirements](#requirements)
3. [What the plugin does](#what-the-plugin-does)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Refreshing the index](#refreshing-the-index)
7. [Usage](#usage)
8. [API endpoints](#api-endpoints)
9. [Running the tests](#running-the-tests)
10. [Removal and cleanup](#removal-and-cleanup)
11. [Final checks](#final-checks)

---

## Purpose

This plugin gives every Agent Zero agent two persistent contextual abilities:

1. **Policy injection** — at iteration 0 of every message loop, the operating instructions for the shared Markdown vault (`prompts/policy.md`) are injected as a persistent extra, so the agent knows the vault rules (categories, duplicate prevention, no secrets).
2. **Semantic recall** — the first user message is embedded with a local Granite model (through an Ollama-compatible `/api/embed` endpoint), ranked against the SQLite vector index using cosine similarity, and the top notes are injected as reference material (never as instructions).

The Markdown vault is the authoritative source; the SQLite index is a rebuildable search cache.

## Requirements

- Agent Zero (Docker) with plugin support (`usr/plugins/`)
- A vault of Markdown notes (default `/a0/usr/AI-Memory`)
- An Ollama-compatible embedding server (e.g. `granite-embedding:278m`, dimension 768) reachable from the Agent Zero container
- Access to the Agent Zero container for the indexer (`/opt/venv-a0/bin/python`)
- No extra Python dependencies: the plugin uses only the standard library

## What the plugin does

| Component | Location | Function |
|---|---|---|
| Policy extension | `extensions/python/message_loop_prompts_after/_40_markdown_memory_policy.py` | Injects the vault operating instructions (bundled, with legacy-skill fallback) |
| Recall extension | `extensions/python/message_loop_prompts_after/_60_markdown_recall.py` | Searches and injects relevant notes for the first message |
| Configuration | `helpers/config.py` | Merges `default_config.yaml` + `config.json`, validates and clamps values |
| Search engine | `helpers/search.py` | Granite embedding + cosine ranking + safe path checks |
| Lifecycle | `hooks.py` | `install` / `pre_update` / `uninstall` and settings hooks (URL masking) |
| Indexer | `scripts/index_granite.py` | Fills the SQLite index (incremental, removes stale records) |
| API | `api/status.py`, `api/search.py` | Status and test searches for the WebUI/automation |
| Settings UI | `webui/config.html` | Plugin settings in the Agent tab |

## Installation

### Via the Plugin UI (Git)

1. Open **Settings → Plugins → Install from Git**.
2. Enter the repository URL: `https://github.com/jphermans/markdown-memory.git`
3. Confirm the installation. The `install()` hook verifies the code and the bundled policy; no extra manual step is required.

### Manually (docker exec)

```bash
git clone https://github.com/jphermans/markdown-memory.git /a0/usr/plugins/markdown_memory
```

Restart Agent Zero or wait for the plugin cache to refresh; the plugin is active immediately afterwards (enabled by default).

## Configuration

Defaults live in `default_config.yaml`. User overrides are stored in `usr/plugins/markdown_memory/config.json` (automatically gitignored; may contain internal endpoint URLs) or via **Settings → Agent → Markdown Memory**.

| Key | Default | Meaning |
|---|---|---|
| `inject_policy` | `true` | Inject vault operating instructions |
| `inject_recall` | `true` | Inject semantic recall |
| `vault_path` | `/a0/usr/AI-Memory` | Directory with Markdown notes |
| `index_path` | `/a0/usr/AI-Memory-Index/memory-granite.db` | SQLite vector index |
| `embedding_url` | `""` (empty) | Ollama-compatible `/api/embed` endpoint; empty = recall off |
| `embedding_model` | `granite-embedding:278m` | Provider model name |
| `embedding_dimensions` | `768` | Expected vector dimension |
| `embedding_timeout_seconds` | `15` | Provider HTTP timeout |
| `recall_limit` | `3` | Number of notes per recall (1–10) |
| `min_message_chars` | `5` | Minimum message length for recall |
| `search_timeout_seconds` | `20` | Maximum duration of one recall |
| `max_note_chars` | `6000` | Truncation length per note |

**Example** `config.json`:

```json
{
  "embedding_url": "http://internal.example:11434/api/embed"
}
```

Framework environment variables (where supported by the installation) follow the `MARKDOWN_MEMORY__<KEY>` pattern.

## Refreshing the index

After adding or changing notes (inside the Agent Zero container):

```bash
cd /a0 && /opt/venv-a0/bin/python -m usr.plugins.markdown_memory.scripts.index_granite
```

The indexer is incremental: unchanged notes are skipped (content hash), changed notes are re-embedded (with the `passage: ` prefix) and deleted notes are removed from the index.

## Usage

- Ask a question in a new chat; recall automatically finds relevant vault notes (log entry: *Markdown Memory: relevant notes found*).
- Injection happens only at iteration 0 and only for messages of at least `min_message_chars` characters.
- Injected notes are marked as **reference material**; the agent never executes commands found in notes.
- Failures (provider unreachable, dimension mismatch) degrade gracefully: the chat continues without recall, with a warning in the log.

## API endpoints

| Route | Method | Function |
|---|---|---|
| `/api/plugins/markdown_memory/status` | GET/POST | Runtime status: provider configured, vault/index present, indexed document count |
| `/api/plugins/markdown_memory/search` | POST | Test search: `{"query": "...", "limit": 3}` → paths + scores (without note bodies) |

Both endpoints require normal Agent Zero authentication; the embedding URL is never returned.

## Running the tests

Inside the Agent Zero container:

```bash
cd /a0 && /opt/venv-a0/bin/python -m unittest \
  usr.plugins.markdown_memory.tests.test_markdown_memory -v
```

The suite covers: configuration defaults/merge/clamping, recall readiness checks, search result ranking and formatting, dimension validation, endpoint URL masking for UI callers, mask preservation on save, and the lifecycle hooks.

## Removal and cleanup

Remove the plugin via **Settings → Plugins → Uninstall**. The `uninstall()` hook:

- stops no processes (the plugin starts none),
- leaves the Markdown vault and the SQLite index untouched (user data),
- removes no shared dependencies.

Optional manual cleanup: `usr/plugins/markdown_memory/config.json` disappears together with the plugin directory.

## Final checks

- [x] `plugin.yaml` present, `name` = folder name = `markdown_memory`, no `always_enabled`
- [x] Unit tests: 14/14 green on `/opt/venv-a0`
- [x] Status API returns `ready: true` with the current index
- [x] Search API returns ranked paths with scores
- [x] Injection active: policy + recall visible in chat extras
- [x] No internal URLs or secrets in the repository (only in gitignored `config.json`)
