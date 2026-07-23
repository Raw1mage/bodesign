import importlib.util
import os
import unittest
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _worker_deps_present():
    """eda_bridge package __init__ pulls kiutils/httpx (worker-only, absent in
    the monolith/unittest env by design). Routing tests that import the real
    package are skipped there."""
    return importlib.util.find_spec("kiutils") is not None


def _load_module(name, relpath):
    """Load a single module by file path, bypassing package __init__ (which
    pulls in worker-only heavy deps like kiutils/httpx that are absent in the
    monolith/unittest env by design — AGENTS.md §4)."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(_ROOT, relpath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


component_fetch = _load_module(
    "bodesign_eda_bridge_component_fetch",
    "packages/eda-bridge/bodesign_eda_bridge/component_fetch.py",
)


class FetchComponentsBatchTests(unittest.TestCase):
    def test_all_success(self):
        def fake(lcsc_id, output_lib, *, overwrite=True):
            return {"ok": True, "lcsc_id": lcsc_id, "has_3d": True}

        with mock.patch.object(component_fetch, "fetch_component", side_effect=fake):
            res = component_fetch.fetch_components(["C1", "C2", "C3"], "/tmp/lib")

        self.assertTrue(res["ok"])
        self.assertEqual(res["requested"], 3)
        self.assertEqual(res["fetched"], 3)
        self.assertEqual(res["failed"], 0)
        self.assertEqual([r["lcsc_id"] for r in res["results"]], ["C1", "C2", "C3"])

    def test_partial_failure_continue_on_error(self):
        def fake(lcsc_id, output_lib, *, overwrite=True):
            if lcsc_id == "BAD":
                return {"ok": False, "reason": "vendor lacks id", "lcsc_id": lcsc_id}
            return {"ok": True, "lcsc_id": lcsc_id, "has_3d": False}

        with mock.patch.object(component_fetch, "fetch_component", side_effect=fake):
            res = component_fetch.fetch_components(["C1", "BAD", "C3"], "/tmp/lib")

        # continue-on-error: BAD does not abort C3
        self.assertFalse(res["ok"])
        self.assertEqual(res["requested"], 3)
        self.assertEqual(res["fetched"], 2)
        self.assertEqual(res["failed"], 1)
        self.assertEqual(len(res["results"]), 3)
        self.assertFalse(res["results"][1]["ok"])
        self.assertTrue(res["results"][2]["ok"])

    def test_empty_list_fail_fast(self):
        res = component_fetch.fetch_components([], "/tmp/lib")
        self.assertFalse(res["ok"])
        self.assertIn("empty lcsc_ids", res["reason"])

    def test_non_list_fail_fast(self):
        res = component_fetch.fetch_components("C1", "/tmp/lib")  # type: ignore[arg-type]
        self.assertFalse(res["ok"])


class HandlerXorDispatchTests(unittest.TestCase):
    def _handler(self):
        mod = _load_module("bodesign_mcp_server", "services/mcp/server.py")
        return mod._h_component_fetch

    def test_neither_provided_errors(self):
        h = self._handler()
        res = h({"output_lib": "/tmp/lib"})
        self.assertFalse(res["ok"])
        self.assertIn("exactly one", res["reason"])

    def test_both_provided_errors(self):
        h = self._handler()
        res = h({"lcsc_id": "C1", "lcsc_ids": ["C2"], "output_lib": "/tmp/lib"})
        self.assertFalse(res["ok"])
        self.assertIn("exactly one", res["reason"])

    @unittest.skipUnless(_worker_deps_present(), "kiutils (worker-only) absent")
    def test_single_routes_to_fetch_component(self):
        h = self._handler()
        with mock.patch("bodesign_eda_bridge.fetch_component",
                        return_value={"ok": True, "lcsc_id": "C1"}) as m:
            res = h({"lcsc_id": "C1", "output_lib": "/tmp/lib"})
        m.assert_called_once()
        self.assertTrue(res["ok"])

    @unittest.skipUnless(_worker_deps_present(), "kiutils (worker-only) absent")
    def test_batch_routes_to_fetch_components(self):
        h = self._handler()
        with mock.patch("bodesign_eda_bridge.fetch_components",
                        return_value={"ok": True, "fetched": 2, "failed": 0}) as m:
            res = h({"lcsc_ids": ["C1", "C2"], "output_lib": "/tmp/lib"})
        m.assert_called_once()
        self.assertEqual(res["fetched"], 2)


if __name__ == "__main__":
    unittest.main()
