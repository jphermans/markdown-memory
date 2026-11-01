# Changelog

All notable changes to the **Markdown Memory** plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] - 2026-11-01

### Added

- README section "Choosing the vault location (host folder)": how to
  place the Markdown vault in a host folder via Docker/Podman bind mounts or
  a Kubernetes hostPath, keeping the container-side `vault_path` unchanged,
  including an ownership-normalization tip.

## [1.2.0] - 2026-11-01

### Added

- Server-side agent tools `memory_search` (semantic search over the vault index) and
  `memory_reindex` (incremental index refresh). Both run inside the Agent Zero server
  process and therefore also work in remote A0 CLI sessions, where the agent terminal
  runs on the client computer and container paths do not exist.
- Hub documentation: rewritten `README.md` (architecture, remote usage, runtime
  neutrality, security, troubleshooting), `docs/HUB-RELEASE.md` release-parity
  checklist, and this changelog.

### Changed

- The bundled memory policy (`prompts/policy.md`) is now **tools-first**: agents are
  instructed to prefer the server-side tools for search and reindexing; the legacy
  container-side shell scripts remain available as a fallback inside the container.

## [1.1.1] - 2026-10-30

### Added

- *Restore defaults* button in the settings UI: one click restores the local embedding
  defaults (local Ollama endpoint, `granite-embedding:278m`, 768 dimensions, cloud off,
  no API key, standard recall/timeout values). Vault/index paths and injection toggles
  are untouched; press Save to persist.

## [1.1.0] - 2026-10-30

### Added
- Cloud embedding support: `embedding_cloud` checkbox and a masked `embedding_api_key`
  field. The `Authorization: Bearer` header is sent only when cloud mode is enabled
  **and** a key is set — local Ollama behaviour is unchanged.
- Dual embedding-response parsing: Ollama (`embeddings[0]`) and OpenAI
  (`data[0].embedding`) formats are accepted automatically (search and indexer).
- Environment override `A0_SET_MARKDOWN_MEMORY__EMBEDDING_API_KEY` (verified framework
  prefix form: `A0_SET_MARKDOWN_MEMORY__<KEY>`).
- Verified live: OpenRouter `nvidia/nemotron-3-embed-1b:free` (2048 dims),
  `liquid/lfm-2.5-embedding-350m:free` (1024), `openai/text-embedding-3-small` (1536);
  Ollama Cloud `nomic-embed-text` (768) verified at API-contract level.

### Security

- `embedding_url` and `embedding_api_key` are masked (`***`) for settings-UI callers;
  submitting the mask preserves the stored value.

## [1.0.1] - 2026-10-20

### Changed

- README and settings UI fully translated to English (Plugin Hub ready).
- Example URLs sanitized to `internal.example`; no internal hostnames in the repository.

## [1.0.0] - 2026-10-19

### Added

- Initial public release: shared Obsidian-compatible Markdown memory for every chat.
- Policy injection at iteration 0 (`_40_markdown_memory_policy.py`, bundled
  `prompts/policy.md` with legacy-skill fallback).
- Semantic recall of the first user message (`_60_markdown_recall.py`): embedding via
  an Ollama-compatible `/api/embed` endpoint, cosine ranking against a SQLite vector
  index, top notes injected as reference data (local Ollama `granite-embedding:278m`,
  768 dimensions).
- Configuration layer (`helpers/config.py`): `default_config.yaml` + user `config.json`
  merge with validation and clamping.
- Search engine (`helpers/search.py`) with vault-only path checks and `.md` filtering.
- API endpoints: `/api/plugins/markdown_memory/status` (GET/POST) and `/search` (POST,
  structured results without note bodies).
- Settings UI (`webui/config.html`) with endpoint-URL masking for UI callers.
- Incremental indexer (`scripts/index_granite.py`): content-hash skip, `passage:`
  prefix, stale-record removal.
- Lifecycle hooks (`install`/`pre_update`/`uninstall`); vault and index preserved on
  uninstall.
- Unit test suite (14 tests) for configuration, search, masking and hooks.

[1.2.0]: https://github.com/jphermans/markdown-memory
[1.1.1]: https://github.com/jphermans/markdown-memory/releases/tag/v1.1.1
[1.1.0]: https://github.com/jphermans/markdown-memory/releases/tag/v1.1.0
[1.0.1]: https://github.com/jphermans/markdown-memory/releases/tag/v1.0.1
[1.0.0]: https://github.com/jphermans/markdown-memory/releases/tag/v1.0.0
