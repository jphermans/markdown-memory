# Changelog

All notable changes to the **Markdown Memory** plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.5] - 2026-11-25

### Fixed

- Provider failures are no longer reported as a bare `HTTPError: HTTP Error 404:
  Not Found`, which suggests a wrong endpoint URL. Every embedding request
  (recall, `memory_search`, `memory_reindex`, the search API and the
  container-side indexer) now raises `SearchError` with an actionable message:
  a missing model is named as such (`Embedding model '...' is not available on
  the embedding server (HTTP 404: ...)`, with the pull and re-index remedy),
  a rejected request points to the API key, and an unreachable, slow or
  malformed-answer provider is reported as such. An `embedding_url` that
  cannot be used (missing scheme or host, nonnumeric port, unusable path) is
  reported as an
  invalid setting. The provider's own error text is included;
  the API key and the endpoint URL are kept out of every message.

### Changed

- The indexer uses the shared embedding client (`embed_text` in
  `helpers/search.py`) instead of a duplicated request. Request format,
  `passage:` prefix and the 180 s indexer timeout are unchanged.
- `memory_reindex` reports a provider failure without the exception class
  prefix (`Indexing failed: Embedding model ... is not available ...`).

- The search API returns up to 400 characters of the failure detail (was 200)
  so the remedy is not cut off; recall logs the failure message instead of
  only the exception class name.

### Added

- README section "Moving to a new host or cluster": the embedding model is a
  dependency outside the vault and must be present on the new embedding
  server; includes a cut-over checklist and a provider smoke test.
- README troubleshooting rows for the new provider messages, and a note that
  `ready` in the status API does not contact the embedding server.
- Unit tests for missing-model, generic 404, rejected-request, unreachable,
  timeout and non-JSON responses, secret redaction, and the indexer's use of
  the shared client, and unusable embedding URLs (25 to 44 tests).

## [1.2.4] - 2026-11-01

### Changed

- The settings UI shows the embedding endpoint URL in plain text again
  (user request): an internal endpoint is not a secret. Only
  `embedding_api_key` remains masked (`***`); `hooks.py` `SECRET_KEYS`
  covers the API key only. Tests, README and hub documentation updated
  accordingly.

## [1.2.3] - 2026-11-01

### Changed

- Spelling consistency: `behaviour` throughout the documentation (one `behavior`
  outlier in the bundled policy).
- README version header now tracks `plugin.yaml` (was stale at 1.2.0).
- `docs/HUB-RELEASE.md` refreshed: tool and tool-test checklist items marked
  verified (25 unit tests), feature table extended with 1.2.1–1.2.3, roadmap
  updated after the live hostPath migration, stale internal workdir reference
  removed.
- Added missing link references for 1.2.1 and 1.2.2.

## [1.2.2] - 2026-11-01

### Added

- README subsection "How it works: one folder, two paths" under the vault
  location section: after mounting, the container path and the host folder
  are the same physical folder (not a copy, not a sync), the plugin keeps
  using the container path, notes are immediately visible on both sides,
  a `sha256sum` verification recipe, and a migration/shadowing note.

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

[1.2.0]: https://github.com/jphermans/markdown-memory/releases/tag/v1.2.0
[1.2.4]: https://github.com/jphermans/markdown-memory/releases/tag/v1.2.4
[1.2.5]: https://github.com/jphermans/markdown-memory/releases/tag/v1.2.5
[1.2.3]: https://github.com/jphermans/markdown-memory/releases/tag/v1.2.3
[1.2.2]: https://github.com/jphermans/markdown-memory/releases/tag/v1.2.2
[1.2.1]: https://github.com/jphermans/markdown-memory/releases/tag/v1.2.1
[1.1.1]: https://github.com/jphermans/markdown-memory/releases/tag/v1.1.1
[1.1.0]: https://github.com/jphermans/markdown-memory/releases/tag/v1.1.0
[1.0.1]: https://github.com/jphermans/markdown-memory/releases/tag/v1.0.1
[1.0.0]: https://github.com/jphermans/markdown-memory/releases/tag/v1.0.0
