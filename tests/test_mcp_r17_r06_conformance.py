"""R17 (minimum operational toolset) + R0.6 (companion-skill wall-nudge) conformance.

Covers the 20 test vectors in plans/mcp_r17-r06-conformance/test-vectors.json. The
pure preflight / assertion / wall-nudge logic is asserted directly (no server), and
the init capability summary / workspace-inspect tool / remedy projection / R17.5
parity are asserted against the imported server module. R17.1.2/R17.6 assertions
branch on the STRUCTURED payload, never on mere text presence.
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / "services" / "mcp"
for p in (str(MCP_DIR), *[str(d) for d in (REPO_ROOT / "packages").glob("*")]):
    if p not in sys.path:
        sys.path.insert(0, p)

import preflight  # noqa: E402
import _skill_nudge  # noqa: E402


def _load_server():
    spec = importlib.util.spec_from_file_location("bd_server_r17", MCP_DIR / "server.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["bd_server_r17"] = m
    spec.loader.exec_module(m)
    return m


SERVER = _load_server()


def _mkdir_with(files: dict) -> Path:
    d = Path(tempfile.mkdtemp())
    for rel, content in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return d


# ── R17.1.1/.1.2 init capability summary (structured, test-branchable) ────

class TestInitCapabilities(unittest.TestCase):
    def test_tv1_capabilities_present_and_branchable(self):
        caps = SERVER._build_capabilities()
        # Structured, not prose — every required family key present.
        for key in ("transport", "file_ingress", "file_egress", "webdav_state",
                    "companion_skill", "conditional_tool_families"):
            self.assertIn(key, caps)
        # R17.1.1: a container UDS endpoint MUST NOT look host-executable. We
        # EXECUTE this decision (R17.1.2), not merely assert text exists.
        svc = caps["transport"]["service_endpoints"]
        self.assertTrue(svc, "at least one service endpoint")
        self.assertFalse(svc[0]["host_executable"],
                         "container UDS endpoint must be host_executable=False")
        self.assertEqual(caps["companion_skill"], "bodesign")
        self.assertIn("companion_cli", caps)
        self.assertEqual(
            caps["companion_cli"]["runtime_bundle_url"],
            "/skills/bodesign-runtime.tar.gz",
        )
        self.assertIn("--bootstrap", caps["companion_cli"]["bootstrap_command"])
        self.assertIn("--doctor", caps["companion_cli"]["doctor_command"])

    def test_tv17_init_tool_returns_capabilities(self):
        res = SERVER.run_tool("bodesign_init", {})
        self.assertTrue(res["ok"])
        self.assertIn("doctrine", res)          # prose preserved
        self.assertIn("capabilities", res)      # additive structured summary
        # R17.6 (b): the init-recommended container socket is flagged non-executable.
        ep = res["capabilities"]["transport"]["service_endpoints"][0]
        self.assertFalse(ep["host_executable"])


# ── R17.2.4 typed asset preflight ─────────────────────────────────────────

class TestPreflight(unittest.TestCase):
    def test_tv5_unresolved(self):
        d = _mkdir_with({"real.txt": "x"})
        v = preflight.preflight_assets(d, ["missing.pdf"])
        self.assertFalse(v["ok"])
        self.assertEqual(v["failures"][0]["reason"], preflight.REASON_UNRESOLVED)
        self.assertEqual(v["error"]["code"], preflight.CODE_UNRESOLVED)
        self.assertIn("note", v["error"]["remedy"])

    def test_tv6_out_of_namespace(self):
        d = _mkdir_with({"real.txt": "x"})
        v = preflight.preflight_assets(d, ["../../etc/passwd"])
        self.assertFalse(v["ok"])
        self.assertEqual(v["failures"][0]["reason"], preflight.REASON_OUT_OF_NAMESPACE)
        self.assertEqual(v["error"]["code"], preflight.CODE_OUT_OF_NAMESPACE)

    def test_tv7_host_only_absolute_blocks_in_token(self):
        d = _mkdir_with({"real.txt": "x"})
        v = preflight.preflight_assets(d, ["/home/user/board.kicad_pcb"], in_token=True)
        self.assertFalse(v["ok"])
        self.assertEqual(v["failures"][0]["reason"], preflight.REASON_HOST_ONLY_ABSOLUTE)

    def test_host_only_absolute_advisory_when_tokenless(self):
        # DD-4 R1: a real host path in a same-host token-less call is not blocking.
        d = _mkdir_with({"real.txt": "x"})
        v = preflight.preflight_assets(d, ["/home/user/board.kicad_pcb"], in_token=False)
        self.assertTrue(v["ok"])  # recorded as a failure row but not blocking
        self.assertEqual(v["failures"][0]["reason"], preflight.REASON_HOST_ONLY_ABSOLUTE)

    def test_missing_media_sharper_code(self):
        d = _mkdir_with({"real.txt": "x"})
        v = preflight.preflight_assets(d, ["logo.png"])
        self.assertEqual(v["failures"][0]["reason"], preflight.REASON_MISSING_MEDIA)

    def test_resolved_passes(self):
        d = _mkdir_with({"board.kicad_pcb": "x", "sub/m.svg": "y"})
        v = preflight.preflight_assets(d, ["board.kicad_pcb", "sub/m.svg"])
        self.assertTrue(v["ok"])
        self.assertEqual(v["failures"], [])


# ── R17.2.5 content assertion ─────────────────────────────────────────────

class TestContentAssertion(unittest.TestCase):
    def test_tv8_empty_not_delivery_ready(self):
        v = preflight.assert_content([{"rel": "out.pdf", "size": 0}], {"non_empty": True})
        self.assertFalse(v["delivery_ready"])
        self.assertEqual(v["error"]["code"], preflight.CODE_ASSERTION_EMPTY)

    def test_tv9_nonempty_expected_file_passes(self):
        v = preflight.assert_content(
            [{"rel": "out.pdf", "size": 4096}],
            {"non_empty": True, "expected_files": ["out.pdf"]})
        self.assertTrue(v["delivery_ready"])

    def test_tv10_missing_required_text(self):
        v = preflight.assert_content(
            [{"rel": "report.md", "size": 20, "text": "no marker here"}],
            {"required_text": ["FCC"]})
        self.assertFalse(v["delivery_ready"])
        self.assertEqual(v["error"]["code"], preflight.CODE_ASSERTION_MISSING_TEXT)

    def test_missing_expected_file(self):
        v = preflight.assert_content([{"rel": "a.pdf", "size": 10}],
                                     {"expected_files": ["b.pdf"]})
        self.assertFalse(v["delivery_ready"])
        self.assertEqual(v["error"]["code"], preflight.CODE_ASSERTION_MISSING_FILE)

    def test_no_assertions_is_ready(self):
        v = preflight.assert_content([{"rel": "a.pdf", "size": 10}], None)
        self.assertTrue(v["delivery_ready"])


# ── R0.6 wall-nudge fingerprint + force levels ────────────────────────────

class TestWallNudge(unittest.TestCase):
    def test_tv11_hard_bad_shape_id(self):
        w = _skill_nudge.detect_wall("edit", {"target": "word/document.xml"}, None)
        self.assertIsNotNone(w)
        self.assertEqual(w["force"], "hard")
        self.assertEqual(w["correct_primitive"], "bodesign_workspace_inspect")
        self.assertIn("skill(bodesign)", w["remedy"]["note"])

    def test_hard_grain_mismatch_zero_element(self):
        w = _skill_nudge.detect_wall("edit", {"target": "ghost.kicad_pcb"}, None,
                                     workspace_files=["real.kicad_pcb"])
        self.assertEqual(w["force"], "hard")
        self.assertIn("zero", w["why"])

    def test_tv12_advisory_unbounded_sweep(self):
        files = [f"f{i}.txt" for i in range(60)]
        w = _skill_nudge.detect_wall("scan", {"bounded": False}, None,
                                     workspace_files=files, prior_recon=False)
        self.assertEqual(w["force"], "advisory")
        self.assertIn("advisory", w)

    def test_tv13_no_nudge_on_legitimate_call(self):
        w = _skill_nudge.detect_wall("edit", {"target": "real.kicad_pcb"}, None,
                                     workspace_files=["real.kicad_pcb"], prior_recon=True)
        self.assertIsNone(w)

    def test_advisory_suppressed_after_recon(self):
        files = [f"f{i}.txt" for i in range(60)]
        w = _skill_nudge.detect_wall("scan", {"bounded": False}, None,
                                     workspace_files=files, prior_recon=True)
        self.assertIsNone(w)


# ── R0.6.4 remedy projection to portable content text ─────────────────────

class TestRemedyProjection(unittest.TestCase):
    def test_tv14_note_projected(self):
        line = SERVER.render_remedy_line({"error": {"remedy": {"note": "load skill(bodesign)"}}})
        self.assertEqual(line, "remedy: load skill(bodesign)")

    def test_tv14_no_remedy_is_none(self):
        # 天條 11: byte-identical to before when there is nothing to project.
        self.assertIsNone(SERVER.render_remedy_line({"error": {}}))
        self.assertIsNone(SERVER.render_remedy_line({"ok": True}))

    def test_string_remedy_verbatim(self):
        line = SERVER.render_remedy_line({"error": {"remedy": "do X"}})
        self.assertEqual(line, "remedy: do X")


# ── R17.2.3 workspace inspection ──────────────────────────────────────────

class TestWorkspaceInspect(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        os.environ["BODESIGN_SESSIONS_ROOT"] = str(self.root)

    def _stage(self, files):
        from token_store import TokenStore
        return TokenStore(root=self.root).stage_files(files)

    def test_tv4_inspect_lists_tree_no_mutation(self):
        staged = self._stage({"x.gbr": {"content": "g"}, "sub/y.drl": {"content": "d"}})
        token = staged["token"]
        res = SERVER.run_tool("bodesign_workspace_inspect", {"token": token})
        self.assertEqual(res["count"], 2)
        self.assertEqual(sorted(res["files"]), ["sub/y.drl", "x.gbr"])

    def test_subpath_escape_rejected(self):
        staged = self._stage({"x.gbr": {"content": "g"}})
        res = SERVER.run_tool("bodesign_workspace_inspect",
                              {"token": staged["token"], "subpath": "../.."})
        self.assertFalse(res.get("ok", True))
        self.assertEqual(res["error"], "WORKSPACE_SUBPATH_ESCAPE")

    def test_registered_read_only(self):
        spec = SERVER.TOOLS_BY_NAME["bodesign_workspace_inspect"]
        self.assertTrue(spec["annotations"]["readOnlyHint"])


# ── R17.5 companion-skill parity across three faces ───────────────────────

class TestCompanionParity(unittest.TestCase):
    def test_tv15_tv20_single_source(self):
        import json
        # face 1: mcp.json skillPaths declares a skills tree carrying the companion.
        mcp = json.loads((REPO_ROOT / "mcp.json").read_text(encoding="utf-8"))
        self.assertIn("skills", mcp["skillPaths"])
        self.assertTrue((REPO_ROOT / "skills" / "bodesign").is_dir())
        # face 2: bodesign_init capabilities.companion_skill (single-source constant).
        self.assertEqual(SERVER.COMPANION_SKILL, "bodesign")
        self.assertEqual(SERVER._build_capabilities()["companion_skill"], "bodesign")
        # face 3: the wall-nudge generator points at the same skill.
        self.assertEqual(_skill_nudge.COMPANION_SKILL, "bodesign")
        self.assertIn("skill(bodesign)", _skill_nudge.skill_nudge_note())

    def test_doctrine_first_use_names_concrete_tools(self):
        # R17.5: the guide's first-use section names concrete tools, not "load the skill".
        doctrine = (REPO_ROOT / "skills" / "bodesign" / "doctrine.md").read_text(encoding="utf-8")
        for tool in ("bodesign_init", "bodesign_stage_dir", "bodesign_workspace_inspect",
                     "bodesign_emit_fab"):
            self.assertIn(tool, doctrine)


# ── R17.6 (a)-(e) five scenarios no longer silent-pass ────────────────────

class TestR176Scenarios(unittest.TestCase):
    def test_tv16_scenario_a_fuse_absolute_flagged(self):
        d = _mkdir_with({"real.txt": "x"})
        v = preflight.preflight_assets(d, ["/mnt/fuse/board.pcb"], in_token=True)
        self.assertFalse(v["ok"])  # not silently accepted
        self.assertEqual(v["failures"][0]["reason"], preflight.REASON_HOST_ONLY_ABSOLUTE)

    def test_tv17_scenario_b_container_socket_flagged(self):
        caps = SERVER._build_capabilities()
        self.assertFalse(caps["transport"]["service_endpoints"][0]["host_executable"])

    def test_tv18_scenario_c_unresolved_media_refused(self):
        d = _mkdir_with({"real.txt": "x"})
        v = preflight.preflight_assets(d, ["logo.png"])
        self.assertFalse(v["ok"])

    def test_tv19_scenario_d_empty_template_not_ready(self):
        v = preflight.assert_content([{"rel": "deck.pptx", "size": 0}], {"non_empty": True})
        self.assertFalse(v["delivery_ready"])
        self.assertEqual(v["error"]["code"], preflight.CODE_ASSERTION_EMPTY)

    def test_tv20_scenario_e_single_source_rails(self):
        self.assertEqual(SERVER.COMPANION_SKILL, _skill_nudge.COMPANION_SKILL)
        self.assertEqual(SERVER._build_capabilities()["companion_skill"],
                         _skill_nudge.COMPANION_SKILL)


if __name__ == "__main__":
    unittest.main()
