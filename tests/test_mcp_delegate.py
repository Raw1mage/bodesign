import importlib
import json
import os
import unittest
from unittest.mock import patch


class McpDelegateTests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("mcp_delegate")

    def test_resolve_from_per_name_env(self):
        with patch.dict(os.environ, {"BODESIGN_MCP_DOCXMCP_URL": "http://docx:9/mcp/"}, clear=False):
            os.environ.pop("BODESIGN_MCP_SERVERS", None)
            cfg = self.mod.resolve_mcp_server("docxmcp")
            self.assertEqual(cfg["url"], "http://docx:9/mcp/")

    def test_resolve_from_json_registry_with_headers(self):
        servers = {"docxmcp": {"url": "http://docx/mcp/", "headers_env": "DX_HDRS"}}
        with patch.dict(os.environ, {"BODESIGN_MCP_SERVERS": json.dumps(servers),
                                     "DX_HDRS": json.dumps({"Authorization": "Bearer x"})}, clear=False):
            cfg = self.mod.resolve_mcp_server("docxmcp")
            self.assertEqual(cfg["url"], "http://docx/mcp/")
            self.assertEqual(cfg["headers"], {"Authorization": "Bearer x"})

    def test_unknown_server_is_worker_unavailable(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BODESIGN_MCP_SERVERS", None)
            os.environ.pop("BODESIGN_MCP_NOPE_URL", None)
            r = self.mod.call_external_mcp_tool("nope", "some_tool", {})
            self.assertFalse(r["ok"])
            self.assertTrue(r["worker_unavailable"])
            self.assertNotIn("worker_starting", r)

    def test_configured_but_unreachable_is_worker_starting(self):
        # Nothing listening on port 1 -> fast connection refused -> retryable starting.
        with patch.dict(os.environ, {"BODESIGN_MCP_DEAD_URL": "http://127.0.0.1:1/mcp/"}, clear=False):
            os.environ.pop("BODESIGN_MCP_SERVERS", None)
            r = self.mod.call_external_mcp_tool("dead", "some_tool", {})
            self.assertFalse(r["ok"])
            self.assertTrue(r["worker_starting"])
            self.assertNotIn("worker_unavailable", r)
            self.assertGreater(r["retry_after_seconds"], 0)

    def test_normalize_text_content_json(self):
        class _Block:
            type = "text"
            text = json.dumps({"ok": True, "result": {"a": 1}})

        class _Res:
            isError = False
            structuredContent = None
            content = [_Block()]

        out = self.mod._normalize(_Res())
        self.assertTrue(out["ok"])
        self.assertEqual(out["result"], {"ok": True, "result": {"a": 1}})


if __name__ == "__main__":
    unittest.main()
