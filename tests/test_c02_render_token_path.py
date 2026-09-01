"""C02 render/export token-relative path rail (BR_20260901).

Predicate this module answers, in one line: **when a call carries a `token`, does
the path the HANDLER actually receives resolve inside that token's doc_dir, and
does the envelope `ok` agree with what the handler reported?**

Why it exists
─────────────
`bodesign_c02_render_enclosure(token=…, stl_path="C02-ME/Enclosure.stl")` returned
outer `ok:true` + inner `status:"error"` + note `STL not found`, with the file
demonstrably present in the token tree. Two independent defects, both of which
made a failure read as a success:

  D1  `PATH_ARG_KEYS` omitted `stl_path` / `glb_path`, so the token dispatch loop
      rewrote `out_dir` but handed the handler a BARE RELATIVE `stl_path`, which
      the renderer then resolved against the container CWD. R17.2.4 preflight
      resolved the SAME arg correctly against doc_dir and passed it — so the two
      layers disagreed and the call was neither blocked nor served.
  D2  `run_tool` hard-coded `ok:True` around any handler return, so a handler that
      declared `status:"error"` still shipped an ok envelope.

Every test below names its predicate and is paired with a control that FAILS when
the guarantee is violated. The renderer boundary is mocked (trimesh/EGL are not
present in the lean core), but the mock records the path it was handed — so the
positive test proves the RESOLVED ABSOLUTE PATH LIES INSIDE the token doc_dir,
which is the actual contract, rather than merely proving "no exception".
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / "services" / "mcp"
for _p in (str(MCP_DIR), *[str(d) for d in (REPO_ROOT / "packages").glob("*")]):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import preflight  # noqa: E402

_SESSIONS = Path(tempfile.mkdtemp(prefix="bd_sessions_"))
os.environ["BODESIGN_SESSIONS_ROOT"] = str(_SESSIONS)


def _load_server():
    spec = importlib.util.spec_from_file_location("bd_server_c02tok", MCP_DIR / "server.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["bd_server_c02tok"] = m
    spec.loader.exec_module(m)
    return m


SERVER = _load_server()

STL_BYTES = "solid cube\nendsolid cube\n"


class _RendererSpy:
    """Records what the renderer boundary was handed, and what it returned.

    `outcome` decides the simulated renderer verdict so the "resolved but the
    renderer failed" state is reachable WITHOUT a real GL stack — that state must
    be distinguishable from "never resolved", and a spy that can only succeed
    could not tell them apart.
    """

    def __init__(self, outcome="rendered"):
        self.outcome = outcome
        self.calls = []

    def __call__(self, stl_path, out_dir, **kw):
        self.calls.append({"stl_path": str(stl_path), "out_dir": str(out_dir), "kw": kw})
        if self.outcome == "rendered":
            out = Path(out_dir)
            out.mkdir(parents=True, exist_ok=True)
            img = out / "Enclosure_iso.png"
            img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
            return {"source": str(stl_path), "status": "rendered",
                    "images": [str(img)], "bounds_mm": [0, 0, 0, 10, 10, 10],
                    "primitive_count": 12, "note": ""}
        if self.outcome == "no-gl":
            return {"source": str(stl_path), "status": "no-gl", "images": [],
                    "bounds_mm": None, "primitive_count": 12,
                    "note": "offscreen GL render failed: no EGL device"}
        return {"source": str(stl_path), "status": "error", "images": [],
                "bounds_mm": None, "primitive_count": 0,
                "note": "STL load failed: simulated"}


class _TokenCase(unittest.TestCase):
    """Shared fixture: one token whose tree holds C02-ME/Enclosure.{scad,stl}."""

    def setUp(self):
        import token_store
        self.store = token_store.default_store()
        self.token, self.doc_dir = self.store.new_token()
        me = self.doc_dir / "C02-ME"
        me.mkdir(parents=True, exist_ok=True)
        (me / "Enclosure.stl").write_text(STL_BYTES, encoding="utf-8")
        (me / "Enclosure.scad").write_text("cube([10,10,10]);\n", encoding="utf-8")
        (me / "render").mkdir(exist_ok=True)  # a DIRECTORY, for the wrong-kind control

    def _render(self, spy, **overrides):
        """Invoke the tool with the renderer boundary replaced by `spy`."""
        import bodesign_eda_bridge
        args = {"token": self.token, "stl_path": "C02-ME/Enclosure.stl",
                "out_dir": "C02-ME/out", "views": ["iso"]}
        args.update(overrides)
        original = bodesign_eda_bridge.render_enclosure_model

        class _Wrapped:
            def __init__(self, inner):
                self.inner = inner

            def __call__(self, *a, **kw):
                return _Dict(self.inner(*a, **kw))

        class _Dict:
            def __init__(self, d):
                self._d = d

            def to_dict(self):
                return self._d

        bodesign_eda_bridge.render_enclosure_model = _Wrapped(spy)
        try:
            return SERVER.run_tool("bodesign_c02_render_enclosure", args)
        finally:
            bodesign_eda_bridge.render_enclosure_model = original


# ── D1: the handler must receive a path INSIDE the token doc_dir ─────────────

class TestTokenRelativeResolution(_TokenCase):
    def test_positive_handler_receives_absolute_path_inside_doc_dir(self):
        """Predicate: does the renderer get an ABSOLUTE path under this token's
        doc_dir when the caller passes a token-relative `stl_path`?

        Asserting `status == rendered` alone would NOT answer it — the spy renders
        whatever it is handed. The load-bearing assertions are the two below it:
        the recorded path is absolute AND relative_to(doc_dir) succeeds.
        """
        spy = _RendererSpy("rendered")
        res = self._render(spy)

        self.assertEqual(len(spy.calls), 1, "renderer boundary must be reached exactly once")
        got = Path(spy.calls[0]["stl_path"])
        self.assertTrue(got.is_absolute(),
                        f"handler received a non-absolute path: {got}")
        # THE contract: the resolved path lies inside this token's namespace.
        got.resolve().relative_to(self.doc_dir.resolve())
        self.assertTrue(got.is_file(), f"resolved path is not a readable file: {got}")
        self.assertEqual(got.read_text(encoding="utf-8"), STL_BYTES,
                         "resolved to a DIFFERENT file than the one staged")
        self.assertTrue(res["ok"])
        self.assertEqual(res["result"]["status"], "rendered")

    def test_positive_out_dir_also_lands_inside_doc_dir(self):
        """Predicate: is the OUTPUT path token-resolved on the same rail as the
        input? (Regression guard: out_dir already worked; the fix must not have
        traded one for the other.)"""
        spy = _RendererSpy("rendered")
        self._render(spy)
        out = Path(spy.calls[0]["out_dir"])
        self.assertTrue(out.is_absolute())
        out.resolve().relative_to(self.doc_dir.resolve())

    def test_control_stl_path_is_registered_as_a_token_path_arg(self):
        """CONTROL for D1 at the source: `stl_path`/`glb_path` must be in
        PATH_ARG_KEYS. This fails loudly if someone removes them again, and it is
        the check whose ABSENCE let the original defect ship."""
        self.assertIn("stl_path", SERVER.PATH_ARG_KEYS)
        self.assertIn("glb_path", SERVER.PATH_ARG_KEYS)

    def test_control_every_preflighted_asset_key_is_token_resolved(self):
        """CONTROL, generalised: ANY arg key that R17.2.4 preflights as a token
        asset MUST also be token-resolved before dispatch.

        This is the invariant the original bug broke — preflight resolved
        `stl_path` against doc_dir and passed, while dispatch left it relative.
        Stated over the whole map, so the next tool added to
        _RENDER_EMIT_ASSET_KEYS cannot reintroduce the same split silently.
        """
        preflighted = {k for keys in SERVER._RENDER_EMIT_ASSET_KEYS.values() for k in keys}
        missing = sorted(preflighted - set(SERVER.PATH_ARG_KEYS))
        self.assertEqual(missing, [],
                         f"preflighted asset args not token-resolved at dispatch: {missing}")

    def test_control_resolver_agrees_with_preflight_frame(self):
        """CONTROL: the dispatch resolver and preflight must use the SAME frame.

        Positive leg: a rel path preflight accepts resolves inside doc_dir.
        Negative leg: a traversal path preflight REJECTS would, if it were ever
        resolved, land outside doc_dir — proving the probe can distinguish the
        two rather than accepting everything.
        """
        ok_rel = "C02-ME/Enclosure.stl"
        verdict = preflight.preflight_assets(self.doc_dir, [ok_rel], in_token=True)
        self.assertTrue(verdict["ok"], verdict)
        resolved = Path(SERVER._resolve_token_path(self.doc_dir, ok_rel))
        resolved.relative_to(self.doc_dir.resolve())  # raises if the frames diverge

        escaping = "../../etc/passwd"
        bad = preflight.preflight_assets(self.doc_dir, [escaping], in_token=True)
        self.assertFalse(bad["ok"], "control is inert: traversal was not rejected")
        escaped = Path(SERVER._resolve_token_path(self.doc_dir, escaping))
        with self.assertRaises(ValueError):
            escaped.relative_to(self.doc_dir.resolve())


# ── D2 + the four states: each outcome must be distinct at the envelope ──────

class TestFourStatesAreMutuallyDistinct(_TokenCase):
    """The four reachable outcomes must NOT share an output.

      A resolved + renderer succeeded      -> ok:true,  result_status=rendered
      B resolved + renderer failed         -> ok:false, error=TOOL_REPORTED_ERROR
      C file absent                        -> ok:false, error=PREFLIGHT_UNRESOLVED
      D path is a directory                -> ok:false, error=PREFLIGHT_NOT_A_FILE
      E traversal / out of namespace       -> ok:false, error=PREFLIGHT_OUT_OF_NAMESPACE

    Empty `produced` is explicitly NOT load-bearing anywhere: B, C and D all
    produce nothing, so `produced == []` cannot by itself tell them apart. Each
    assertion below branches on a code that differs between the states.
    """

    def test_a_resolved_and_rendered(self):
        res = self._render(_RendererSpy("rendered"))
        self.assertTrue(res["ok"])
        self.assertEqual(res["result_status"], "rendered")
        self.assertNotIn("error", res)
        self.assertTrue(res["produced"], "a successful render must report produced files")

    def test_b_resolved_but_renderer_failed_is_not_ok(self):
        """D2 regression: a handler-declared `status:"error"` must NOT ship ok:true."""
        spy = _RendererSpy("error")
        res = self._render(spy)
        self.assertEqual(len(spy.calls), 1,
                         "state B requires the renderer to have been REACHED")
        self.assertFalse(res["ok"], "handler reported error but envelope said ok")
        self.assertEqual(res["error"], "TOOL_REPORTED_ERROR")
        self.assertEqual(res["result_status"], "error")
        # The inner payload is preserved verbatim — nothing swallowed.
        self.assertEqual(res["result"]["status"], "error")
        self.assertIn("simulated", res["message"])

    def test_b2_honest_degradation_stays_ok_but_is_labelled(self):
        """`no-gl` is the tool honestly reporting a missing capability, NOT a
        failed call: it keeps ok:true, and `result_status` keeps it separable from
        a real render. Without this, the D2 fix would over-reach and collapse
        'toolchain absent' into 'call failed'."""
        res = self._render(_RendererSpy("no-gl"))
        self.assertTrue(res["ok"])
        self.assertEqual(res["result_status"], "no-gl")
        self.assertNotIn("error", res)

    def test_c_missing_file_is_preflight_unresolved(self):
        spy = _RendererSpy("rendered")
        res = self._render(spy, stl_path="C02-ME/DoesNotExist.stl")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], preflight.CODE_UNRESOLVED)
        self.assertEqual(spy.calls, [], "renderer must NOT be reached for a missing input")

    def test_d_directory_input_is_its_own_code(self):
        """A path that EXISTS but is a directory must not be reported as 'not found'."""
        spy = _RendererSpy("rendered")
        res = self._render(spy, stl_path="C02-ME/render")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], preflight.CODE_NOT_A_FILE)
        self.assertNotEqual(res["error"], preflight.CODE_UNRESOLVED,
                            "directory and missing-file must not share a code")
        self.assertEqual(spy.calls, [])

    def test_e_traversal_is_out_of_namespace(self):
        spy = _RendererSpy("rendered")
        res = self._render(spy, stl_path="../../../etc/passwd")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], preflight.CODE_OUT_OF_NAMESPACE)
        self.assertEqual(spy.calls, [])

    def test_all_five_states_carry_pairwise_distinct_discriminators(self):
        """The summarising assertion: collect the (ok, code) discriminator of every
        state in one run and assert they are PAIRWISE DISTINCT.

        Individually each test above could pass while two states still coincided;
        this is the check that the set as a whole has discriminating power.
        """
        seen = {}
        seen["A_rendered"] = self._discriminator(self._render(_RendererSpy("rendered")))
        seen["B_render_failed"] = self._discriminator(self._render(_RendererSpy("error")))
        seen["B2_degraded"] = self._discriminator(self._render(_RendererSpy("no-gl")))
        seen["C_missing"] = self._discriminator(
            self._render(_RendererSpy("rendered"), stl_path="C02-ME/Nope.stl"))
        seen["D_directory"] = self._discriminator(
            self._render(_RendererSpy("rendered"), stl_path="C02-ME/render"))
        seen["E_traversal"] = self._discriminator(
            self._render(_RendererSpy("rendered"), stl_path="../../../etc/passwd"))
        self.assertEqual(len(set(seen.values())), len(seen),
                         f"states share a discriminator (indistinguishable): {seen}")

    @staticmethod
    def _discriminator(res: dict) -> tuple:
        return (bool(res.get("ok")), res.get("error"), res.get("result_status"))


# ── export -> render chain: the relative-path contract must be consistent ────

class TestExportRenderChainContract(_TokenCase):
    def test_export_out_dir_and_render_stl_path_share_one_frame(self):
        """Predicate: does the rel path an export step WRITES under a token match
        the rel path a later render step can READ back?

        Chains the two halves through the real dispatch: resolve an export-style
        `out_dir` under the token, drop an STL there, then feed the SAME rel path
        back as `stl_path`. If the two args were resolved in different frames, the
        second call would not find the first call's output.
        """
        export_out = Path(SERVER._resolve_token_path(self.doc_dir, "C02-ME/chain"))
        export_out.mkdir(parents=True, exist_ok=True)
        (export_out / "Enclosure.stl").write_text(STL_BYTES, encoding="utf-8")

        rel_from_token = str(Path("C02-ME/chain/Enclosure.stl"))
        spy = _RendererSpy("rendered")
        res = self._render(spy, stl_path=rel_from_token, out_dir="C02-ME/chain/render")

        self.assertTrue(res["ok"], res)
        got = Path(spy.calls[0]["stl_path"])
        self.assertEqual(got.resolve(), (export_out / "Enclosure.stl").resolve(),
                         "render did not read back the file export wrote")

    def test_control_chain_probe_fails_when_frames_differ(self):
        """CONTROL for the test above: if the render leg is given a rel path that
        the export leg did NOT write, the chain assertion must FAIL (i.e. the probe
        is not accepting everything)."""
        spy = _RendererSpy("rendered")
        res = self._render(spy, stl_path="C02-ME/chain/NotWritten.stl")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], preflight.CODE_UNRESOLVED)


# ── preflight unit-level: the new not_a_file reason ──────────────────────────

class TestPreflightNotAFile(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="bd_pf_"))
        (self.d / "sub").mkdir()
        (self.d / "real.stl").write_text("x", encoding="utf-8")

    def test_directory_is_not_a_file(self):
        v = preflight.preflight_assets(self.d, ["sub"], in_token=True)
        self.assertFalse(v["ok"])
        self.assertEqual(v["failures"][0]["reason"], preflight.REASON_NOT_A_FILE)
        self.assertEqual(v["error"]["code"], preflight.CODE_NOT_A_FILE)

    def test_control_regular_file_still_passes(self):
        """CONTROL: the new is_file() gate must not reject legitimate inputs."""
        v = preflight.preflight_assets(self.d, ["real.stl"], in_token=True)
        self.assertTrue(v["ok"], v)

    def test_control_missing_still_reports_unresolved(self):
        """CONTROL: adding not_a_file must not have absorbed the missing case."""
        v = preflight.preflight_assets(self.d, ["nope.stl"], in_token=True)
        self.assertEqual(v["failures"][0]["reason"], preflight.REASON_UNRESOLVED)


if __name__ == "__main__":
    unittest.main()
