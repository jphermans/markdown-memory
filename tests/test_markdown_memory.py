"""Unit tests for the Markdown Memory plugin helpers and hooks.

Run inside the Agent Zero framework runtime:

    cd /a0 && /opt/venv-a0/bin/python -m unittest \
        usr.plugins.markdown_memory.tests.test_markdown_memory -v
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import asyncio
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, "/a0")

from usr.plugins.markdown_memory.helpers.config import DEFAULTS, normalize, recall_ready  # noqa: E402
from usr.plugins.markdown_memory.helpers import search as search_mod  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ConfigTests(unittest.TestCase):
    def test_defaults_when_empty(self):
        config = normalize(None)
        self.assertEqual(config, DEFAULTS)

    def test_partial_overrides_merge_with_defaults(self):
        config = normalize({"recall_limit": 5})
        self.assertEqual(config["recall_limit"], 5)
        self.assertEqual(config["embedding_model"], DEFAULTS["embedding_model"])

    def test_clamping(self):
        config = normalize({"recall_limit": 99, "search_timeout_seconds": 0, "max_note_chars": 1})
        self.assertEqual(config["recall_limit"], 10)
        self.assertEqual(config["search_timeout_seconds"], 1)
        self.assertEqual(config["max_note_chars"], 500)

    def test_bool_coercion(self):
        config = normalize({"inject_policy": "false", "inject_recall": "1"})
        self.assertFalse(config["inject_policy"])
        self.assertTrue(config["inject_recall"])

    def test_cloud_defaults_off(self):
        config = normalize({})
        self.assertFalse(config["embedding_cloud"])
        self.assertEqual(config["embedding_api_key"], "")

    def test_cloud_fields_coerce(self):
        config = normalize({"embedding_cloud": "true", "embedding_api_key": " k "})
        self.assertTrue(config["embedding_cloud"])
        self.assertEqual(config["embedding_api_key"], "k")

    def test_unknown_keys_ignored(self):
        config = normalize({"evil_key": "x"})
        self.assertNotIn("evil_key", config)

    def test_recall_ready_requires_url_vault_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            db = Path(tmp) / "index.db"
            sqlite3.connect(db).close()

            base = {"vault_path": str(vault), "index_path": str(db)}
            self.assertFalse(recall_ready(normalize(base)))
            self.assertTrue(recall_ready(normalize({**base, "embedding_url": "http://x/api/embed"})))
            self.assertFalse(
                recall_ready(
                    normalize({**base, "embedding_url": "http://x/api/embed", "inject_recall": False})
                )
            )


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "sub").mkdir(parents=True)
        (self.vault / "root.md").write_text("# Root\nalpha", encoding="utf-8")
        (self.vault / "sub" / "note.md").write_text("# Note\nbeta", encoding="utf-8")

        self.db = Path(self.tmp.name) / "index.db"
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "CREATE TABLE documents (path TEXT PRIMARY KEY, content_hash TEXT,"
                " embedding TEXT, model TEXT, updated_at TEXT)"
            )
            conn.execute(
                "INSERT INTO documents VALUES (?,?,?,?,?)",
                ("root.md", "h1", json.dumps([1.0, 0.0]), "test-model", "t"),
            )
            conn.execute(
                "INSERT INTO documents VALUES (?,?,?,?,?)",
                ("sub/note.md", "h2", json.dumps([0.0, 1.0]), "test-model", "t"),
            )

        self.config = normalize(
            {
                "vault_path": str(self.vault),
                "index_path": str(self.db),
                "embedding_url": "http://fake/api/embed",
                "embedding_model": "test-model",
                "embedding_dimensions": 2,
                "recall_limit": 2,
            }
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _patch_urlopen(self, vector):
        return mock.patch.object(
            urllib.request,
            "urlopen",
            return_value=_FakeResponse({"embeddings": [vector]}),
        )

    def test_search_notes_ranking_and_format(self):
        with self._patch_urlopen([0.9, 0.1]):
            result = search_mod.search_notes("query", self.config)
        self.assertIn("Source: root.md", result)
        self.assertIn("Similarity: ", result)
        self.assertIn("# Root", result)
        self.assertTrue(result.index("root.md") < result.index("sub/note.md"))

    def test_search_results_structure_and_limit(self):
        with self._patch_urlopen([0.9, 0.1]):
            results = search_mod.search_results("query", self.config, limit=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "root.md")
        self.assertEqual(results[0]["title"], "root")
        self.assertIsInstance(results[0]["similarity"], float)

    def test_dimension_mismatch_raises_search_error(self):
        with self._patch_urlopen([1.0, 2.0, 3.0]):
            with self.assertRaises(search_mod.SearchError):
                search_mod.search_notes("query", self.config)

    def test_missing_files_skipped(self):
        (self.vault / "root.md").unlink()
        with self._patch_urlopen([1.0, 0.0]):
            result = search_mod.search_notes("query", self.config)
        self.assertNotIn("root.md", result)
        self.assertIn("sub/note.md", result)

    def test_no_auth_header_without_cloud(self):
        captured = {}

        def _capture(req, timeout=None):
            captured["req"] = req
            return _FakeResponse({"embeddings": [[0.9, 0.1]]})

        with mock.patch.object(urllib.request, "urlopen", _capture):
            search_mod.search_notes("query", self.config)
        self.assertNotIn("Authorization", captured["req"].headers)

    def test_auth_header_sent_when_cloud_enabled(self):
        cfg = normalize({**self.config, "embedding_cloud": True, "embedding_api_key": "secret-key"})
        captured = {}

        def _capture(req, timeout=None):
            captured["req"] = req
            return _FakeResponse({"embeddings": [[0.9, 0.1]]})

        with mock.patch.object(urllib.request, "urlopen", _capture):
            search_mod.search_notes("query", cfg)
        self.assertEqual(captured["req"].headers.get("Authorization"), "Bearer secret-key")

    def test_openai_style_response_accepted(self):
        with mock.patch.object(
            urllib.request,
            "urlopen",
            return_value=_FakeResponse({"data": [{"embedding": [0.9, 0.1]}]}),
        ):
            result = search_mod.search_notes("query", self.config)
        self.assertIn("root.md", result)


class HooksTests(unittest.TestCase):
    def test_get_config_shows_url_for_ui(self):
        from usr.plugins.markdown_memory import hooks

        config = hooks.get_plugin_config(
            {"embedding_url": "http://internal/api/embed"}, hook_context={"caller": "ui"}
        )
        self.assertEqual(config["embedding_url"], "http://internal/api/embed")

        config = hooks.get_plugin_config(
            {"embedding_url": "http://internal/api/embed"}, hook_context={"caller": "agent"}
        )
        self.assertEqual(config["embedding_url"], "http://internal/api/embed")

    def test_get_config_masks_api_key_for_ui(self):
        from usr.plugins.markdown_memory import hooks

        config = hooks.get_plugin_config(
            {"embedding_api_key": "sk-secret"}, hook_context={"caller": "ui"}
        )
        self.assertEqual(config["embedding_api_key"], hooks.MASK)

    def test_save_config_keeps_stored_api_key_on_mask(self):
        from usr.plugins.markdown_memory import hooks

        with tempfile.TemporaryDirectory() as tmp:
            stored_path = Path(tmp) / "config.json"
            stored_path.write_text(json.dumps({"embedding_api_key": "sk-real"}))

            fake = types_mod = type(sys)("helpers.plugins")
            fake.find_plugin_asset = lambda *a, **k: {"path": str(stored_path)}
            with mock.patch.dict(sys.modules, {"helpers.plugins": fake}):
                saved = hooks.save_plugin_config(
                    settings={"embedding_api_key": hooks.MASK, "recall_limit": 4},
                    project_name="",
                    agent_profile="",
                )
            self.assertEqual(saved["embedding_api_key"], "sk-real")
            self.assertEqual(saved["recall_limit"], 4)

    def test_save_config_allows_explicit_new_url(self):
        from usr.plugins.markdown_memory import hooks

        with tempfile.TemporaryDirectory() as tmp:
            stored_path = Path(tmp) / "config.json"
            stored_path.write_text(json.dumps({"embedding_url": "http://old/api"}))

            fake = type(sys)("helpers.plugins")
            fake.find_plugin_asset = lambda *a, **k: {"path": str(stored_path)}
            with mock.patch.dict(sys.modules, {"helpers.plugins": fake}):
                saved = hooks.save_plugin_config(
                    settings={"embedding_url": "http://new/api"},
                    project_name="",
                    agent_profile="",
                )
            self.assertEqual(saved["embedding_url"], "http://new/api")

    def test_install_hook_requires_bundled_policy(self):
        from usr.plugins.markdown_memory import hooks

        self.assertTrue(hooks.install())
        self.assertTrue(hooks.pre_update())
        self.assertTrue(hooks.uninstall())


if __name__ == "__main__":
    unittest.main()



class AgentToolsTest(unittest.TestCase):
    """Server-side agent tools (v1.2.0)."""

    def test_tool_classes_importable(self):
        from helpers.tool import Tool
        from usr.plugins.markdown_memory.tools.memory_reindex import MemoryReindex
        from usr.plugins.markdown_memory.tools.memory_search import MemorySearch

        for cls in (MemorySearch, MemoryReindex):
            self.assertTrue(issubclass(cls, Tool))

    def test_run_index_importable_and_rejects_empty_url(self):
        from usr.plugins.markdown_memory.scripts.index_granite import run_index

        with self.assertRaises(RuntimeError):
            run_index({"embedding_url": ""})

    def test_memory_search_success(self):
        from usr.plugins.markdown_memory.tools import memory_search

        with unittest.mock.patch.object(
            memory_search, "search_notes", return_value="Source: Decisions/x.md\nSimilarity: 0.900\ncontent"
        ):
            response = asyncio.run(memory_search.MemorySearch.execute(None, query="vault", limit=3))
        self.assertIn("Decisions/x.md", response.message)
        self.assertFalse(response.break_loop)

    def test_memory_search_error_path(self):
        from usr.plugins.markdown_memory.helpers.search import SearchError
        from usr.plugins.markdown_memory.tools import memory_search

        with unittest.mock.patch.object(
            memory_search, "search_notes", side_effect=SearchError("provider down")
        ):
            response = asyncio.run(memory_search.MemorySearch.execute(None, query="vault"))
        self.assertIn("Search failed", response.message)
        self.assertFalse(response.break_loop)

    def test_memory_search_requires_query(self):
        from usr.plugins.markdown_memory.tools.memory_search import MemorySearch

        response = asyncio.run(MemorySearch.execute(None, query="  "))
        self.assertIn("Error", response.message)
