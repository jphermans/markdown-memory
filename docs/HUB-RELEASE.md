# Markdown Memory — Plugin Hub Release Checklist (v1.2.4)

Parity checklist for publishing/updating **markdown_memory** on the Agent Zero Plugin Hub. Every item must be checked before the hub release is announced. Status legend: ✅ verified.

---

## 1. Repository structure (expected tree)

```
markdown_memory/
├── plugin.yaml                  # name = folder name, version 1.2.4, settings_sections: [agent]
├── README.md                    # hub-quality, English
├── CHANGELOG.md                 # Keep a Changelog style
├── LICENSE                      # MIT
├── .gitignore                   # excludes config.json, __pycache__, etc.
├── default_config.yaml          # documented defaults (source of env var names)
├── hooks.py                     # install/pre_update/uninstall + API-key masking
├── helpers/
│   ├── config.py                # DEFAULTS, normalize(), load_config(), recall_ready()
│   └── search.py                # embed client (Ollama/OpenAI), cosine ranking
├── extensions/python/message_loop_prompts_after/
│   ├── _40_markdown_memory_policy.py
│   └── _60_markdown_recall.py
├── api/
│   ├── status.py                # GET/POST /api/plugins/markdown_memory/status
│   └── search.py                # POST /api/plugins/markdown_memory/search
├── tools/                       # 1.2.0: memory_search, memory_reindex (server-side)
├── scripts/
│   └── index_granite.py         # incremental indexer (container-side)
├── prompts/
│   └── policy.md                # bundled operating policy (tools-first since 1.2.0)
├── tests/
│   └── test_markdown_memory.py
├── webui/
│   ├── config.html              # settings UI incl. Restore defaults button
│   └── thumbnail.png
└── docs/
    └── HUB-RELEASE.md           # this file
```

Not in the repository (ever): `config.json` (runtime-only, gitignored, may contain the internal endpoint URL and cloud key).

## 2. Feature list per version

| Version | Features |
|---|---|
| 1.0.x | First public release: policy injection (`_40`), semantic recall (`_60`), bundled policy prompt, SQLite Granite index via local Ollama `granite-embedding:278m` (768 dims), status/search API endpoints, settings UI, incremental indexer, endpoint-URL masking for UI callers, unit tests. 1.0.1: English README + settings UI, sanitized example URLs. |
| 1.1.0 | Cloud embeddings: `embedding_cloud` checkbox + masked `embedding_api_key` field; `Authorization: Bearer` sent only when cloud mode is on; response parser accepts Ollama (`embeddings[0]`) **and** OpenAI (`data[0].embedding`) shapes; env override `A0_SET_MARKDOWN_MEMORY__EMBEDDING_API_KEY`. |
| 1.1.1 | *Restore defaults* button in the settings UI (restores local embedding defaults; paths and toggles untouched). |
| 1.2.0 | Server-side agent tools `memory_search` and `memory_reindex` (also usable from remote A0 CLI sessions where the terminal runs on the client host); policy is now **tools-first** (shell scripts demoted to container-side fallback); hub documentation (README rewrite, `docs/HUB-RELEASE.md`, `CHANGELOG.md`). |
| 1.2.1 | README section "Choosing the vault location (host folder)": Docker/Podman bind mounts, Kubernetes `hostPath` volume, ownership-normalization tip. |
| 1.2.2 | README subsection "How it works: one folder, two paths": mount semantics (one physical folder, not a copy), FAQ, `sha256sum` verification recipe, migration/shadowing note. |
| 1.2.3 | Documentation polish: spelling consistency, README version header synced with `plugin.yaml`, checklist refreshed. |
| 1.2.4 | Settings UI shows the embedding endpoint URL in plain text again (user decision): only `embedding_api_key` remains masked (`***`); README, tests and hub docs updated. |

## 3. Pre-release parity checklist

| # | Item | Status |
|---|---|---|
| 1 | `plugin.yaml`: `name` matches folder (`markdown_memory`), `version: 1.2.4`, `settings_sections: [agent]`, no `always_enabled` | ✅ |
| 2 | README: hub-quality, English, architecture/configuration/remote-usage/security/troubleshooting complete | ✅ |
| 3 | Env-prefix documented in verified form `A0_SET_MARKDOWN_MEMORY__<KEY>` (framework `helpers/plugins.py` `_apply_defaults_from_env` + `helpers/settings.py` `get_default_value`) | ✅ |
| 4 | `CHANGELOG.md` covers 1.0.x → 1.2.4 in Keep a Changelog style | ✅ |
| 5 | Keys in `default_config.yaml` == keys in `helpers/config.py` `DEFAULTS` | ✅ |
| 6 | No secrets/URLs in the repo; `config.json` gitignored; example URLs sanitized (`internal.example`) | ✅ |
| 7 | Unit tests green on `/opt/venv-a0` (25 tests, including the 1.2.0 tool tests) | ✅ |
| 8 | `tools/memory_search.py`, `tools/memory_reindex.py` present, registered, documented in README and policy | ✅ (1.2.0) |
| 9 | Tools covered by unit tests (server-side execution, remote-session equivalence) | ✅ (1.2.0) |
| 10 | Status/search API smoke-tested against the live index (`ready: true`, ranked results) | ✅ |
| 11 | Policy injection and recall proven via chat extras (policy + recall blocks visible) | ✅ |
| 12 | Thumbnail present (`webui/thumbnail.png`) and rendering in the hub/plugin list | ✅ |

## 4. Installation & configuration (hub instructions)

Full details in [`README.md`](../README.md). Summary for the hub listing:

1. **Install:** Settings → Plugins → Install from Git → `https://github.com/jphermans/markdown-memory.git` (or `git clone` into `/a0/usr/plugins/markdown_memory`).
2. **Vault:** place Markdown notes in `/a0/usr/AI-Memory` (or set `vault_path`). Mount `/a0/usr` persistently (bind mount / PVC / hostPath).
3. **Embeddings (local):** set the endpoint to an Ollama-compatible `/api/embed` URL reachable from the container; keep *Cloud embeddings* off.
4. **Embeddings (cloud):** set the cloud URL, enable *Cloud embeddings*, fill the masked API key, adjust model + dimensions, full re-index.
5. **Verify:** `GET /api/plugins/markdown_memory/status` → `ready: true`; run a test query via the search endpoint.
6. **Environment overrides:** `A0_SET_MARKDOWN_MEMORY__<KEY>` (e.g. `A0_SET_MARKDOWN_MEMORY__VAULT_PATH`). Note: a saved `config.json` takes precedence over env vars.

## 5. Test instructions

Unit tests (inside the Agent Zero container):

```bash
cd /a0 && /opt/venv-a0/bin/python -m unittest \
  usr.plugins.markdown_memory.tests.test_markdown_memory -v
```

From a Kubernetes host:

```bash
kubectl -n agent-zero exec <pod> -- sh -c \
  'cd /a0 && /opt/venv-a0/bin/python -m unittest usr.plugins.markdown_memory.tests.test_markdown_memory -v'
```

Coverage: config defaults/merge/clamping, recall readiness, ranking and formatting, dimension validation, dual response parsing, Authorization-header behaviour, API-key masking and mask preservation, lifecycle hooks.

Functional smoke test: after (re)indexing, `POST /api/plugins/markdown_memory/search` with a known note topic returns that note's path with the highest score; the status endpoint reports `ready: true` and a document count > 0.

## 6. Security considerations

- `embedding_api_key` is masked (`***`) for UI callers; submitting the mask preserves the stored value (`hooks.py` `SECRET_KEYS`). The embedding endpoint URL is shown in plain text (since v1.2.4, user decision): internal endpoints are not secrets.
- The repository must stay free of endpoints/keys: `config.json` is gitignored; prefer env vars (`A0_SET_MARKDOWN_MEMORY__...`) for deployments.
- `Authorization: Bearer` is sent only when `embedding_cloud` is enabled and a key is set.
- The search API returns paths/scores only — no note bodies; no endpoint returns the URL or key.
- Memory writes are restricted to the vault (plus the dedicated index via approved tooling); search results are vault-path-checked and `.md`-only.
- Injected notes are framed as data, never instructions; the bundled policy forbids executing commands from notes and storing secrets in the vault.
- Cloud embeddings send note content to an external provider — document this in any deployment that enables it.

## 7. Known limitations

- One embedding model per index: switching model/provider/dimensions requires a **full** re-index (the index filters on model).
- Recall triggers only on the first user message of a chat (iteration 0) and only above `min_message_chars`.
- The index is not refreshed automatically on note changes; run `memory_reindex` / the indexer after writes.
- Recall readiness requires `embedding_url` plus an existing vault directory and index file; without them the plugin still injects policy but no recall.
- Settings are per installation (`per_project_config` / `per_agent_config` are `false`) — intentional: one shared vault.
- Remote A0 CLI sessions cannot use the container-side shell fallback by design; the server-side tools are the supported route.
- Semantic quality depends on the embedding model (Granite/Nomic are English-centric; other languages work but with lower precision).

## 8. Roadmap

- **Vault storage on Kubernetes:** implemented in practice on a single-node cluster via a dedicated `hostPath` volume for `/a0/usr/AI-Memory` (node-pinned) with an ownership-normalization initContainer and a periodic ownership cron; deeper mounts on top of a PVC verified working via mountinfo. A portable PVC-based setup guide may still be added.
- **Cloud key as secret:** inject the Ollama Cloud key as a Kubernetes Secret via `A0_SET_MARKDOWN_MEMORY__EMBEDDING_API_KEY` instead of storing it in `config.json`.
- Optional `vault.host_mounted` indicator in the status API (host-vs-container storage visibility).
- Additional embedding providers via a small adapter layer (OpenAI/Voyage/Cohere-native formats).
- Optional scheduled/background re-indexing and a reindex-after-write hook.
