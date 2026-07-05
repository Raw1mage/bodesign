import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    BOARD_SURGERY_UNSAFE_PATH,
    CONNECTOR_FACE_CONFLICT,
    UPSTREAM_CONSTRAINT_MISSING,
    BoardSurgeryError,
    UpstreamConstraintError,
    assert_face_frozen,
    assert_safe_surgery_path,
    build_castellation,
    parse_castellation_request,
    parse_face_layout,
    require_upstream_constraints,
    solve_face_placement,
)
from bodesign_workflow_core.board_surgery import SAFE_PATH

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

_FACE_LAYOUT = {
    "schema": "bodesign.c01.face_layout.v1",
    "frozen": True,
    "board_outline": {"width_mm": 40.0, "height_mm": 40.0},
    "connectors": [
        {"ref": "J1", "component": "USB-C", "face": "BOTTOM", "provenance": "C01_物理配置SSOT.md:L12"},
        {"ref": "J2", "component": "microSD", "face": "LEFT", "provenance": "C01_物理配置SSOT.md:L18"},
    ],
}


class UpstreamConstraintTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-upc-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    # ── TV-3: 缺上游凍結約束 → placement verb 拒絕（切面 4 lifecycle 方向性）──
    def test_tv3_missing_upstream_constraint_hard_blocks(self):
        with self.assertRaises(UpstreamConstraintError) as ctx:
            require_upstream_constraints(self.work, layer="C04", required=["face_layout", "mechanical"])
        self.assertEqual(ctx.exception.code, UPSTREAM_CONSTRAINT_MISSING)
        missing_keys = {m["key"] for m in ctx.exception.detail["missing"]}
        # ALL gaps at once, not just the first.
        self.assertEqual(missing_keys, {"face_layout", "mechanical"})

    def test_present_upstream_constraint_passes(self):
        import json
        (self.work / "C01-ID").mkdir(parents=True, exist_ok=True)
        (self.work / "C01-ID" / "Face_Layout.json").write_text(json.dumps(_FACE_LAYOUT), encoding="utf-8")
        loaded = require_upstream_constraints(self.work, layer="C04", required=["face_layout"])
        self.assertIn("face_layout", loaded)

    # ── TV-4: 連接器綁定 C01 face-layout（USB-C=BOTTOM）→ 面向正確（切面 2）──
    def test_tv4_connector_face_is_frozen_and_placed_correctly(self):
        fl = parse_face_layout(_FACE_LAYOUT)
        placements = {p.ref: p for p in solve_face_placement(fl)}
        usb = placements["J1"]
        self.assertEqual(usb.face, "BOTTOM")
        self.assertFalse(usb.movable_by_c04)  # DD-4: face not a C04 degree of freedom
        # USB-C on BOTTOM edge → y at board height (40mm bottom edge).
        self.assertEqual(usb.edge_span["y_mm"], 40.0)
        self.assertTrue(usb.provenance)  # traces to SSOT anchor

    def test_face_conflict_when_c04_moves_connector_off_frozen_face(self):
        fl = parse_face_layout(_FACE_LAYOUT)
        # C04 tries to move USB-C from frozen BOTTOM to TOP → refused.
        with self.assertRaises(UpstreamConstraintError) as ctx:
            assert_face_frozen(fl, "J1", "TOP")
        self.assertEqual(ctx.exception.code, CONNECTOR_FACE_CONFLICT)
        self.assertEqual(ctx.exception.detail["frozen_face"], "BOTTOM")
        # placing WITHIN the frozen face is allowed.
        assert_face_frozen(fl, "J1", "BOTTOM")  # no raise

    def test_face_layout_missing_provenance_is_fabrication_block(self):
        bad = {"schema": "x", "connectors": [{"ref": "J1", "face": "TOP"}]}  # no provenance
        with self.assertRaises(UpstreamConstraintError):
            parse_face_layout(bad)


class CastellationBoardSurgeryTests(unittest.TestCase):
    _SPEC = {
        "edge": "BOTTOM",
        "pad_count": 4,
        "pitch_mm": 2.0,
        "pad_width_mm": 0.9,
        "pad_height_mm": 1.2,
        "drill_mm": 0.5,
        "net_names": ["GND", "VBUS", "D+", "D-"],
        "provenance": "stamp_module_footprint.md:L5",
    }
    _OUTLINE = {"width_mm": 40.0, "height_mm": 40.0}

    # ── DD-5: refuse the known-segfault pcbnew paths ────────────────────────
    def test_unsafe_pcbnew_path_refused(self):
        for bad in ("pcbnew_settextsize", "pcbnew_pad_primitive", "pcbnew_direct"):
            with self.assertRaises(BoardSurgeryError) as ctx:
                assert_safe_surgery_path(bad)
            self.assertEqual(ctx.exception.code, BOARD_SURGERY_UNSAFE_PATH)

    def test_safe_sexpr_path_allowed(self):
        assert_safe_surgery_path(SAFE_PATH)  # no raise

    def test_build_castellation_emits_sexpr_injection(self):
        req = parse_castellation_request(self._SPEC)
        out = build_castellation(req, self._OUTLINE)
        self.assertEqual(out["path"], SAFE_PATH)
        self.assertTrue(out["safe"])
        self.assertEqual(out["pad_count"], 4)
        self.assertEqual(len(out["pads"]), 4)
        # castellated pads land on the BOTTOM edge (y = board height 40mm).
        self.assertTrue(all(p["y_mm"] == 40.0 for p in out["pads"]))
        # S-expr fragments carry the castellated marker + no pcbnew object build.
        self.assertIn('(property "castellated" "true")', out["sexpr_block"])
        self.assertIn("thru_hole", out["sexpr_block"])
        # nets threaded through deterministically.
        self.assertEqual(out["pads"][0]["net"], "GND")

    def test_build_castellation_refuses_unsafe_path(self):
        req = parse_castellation_request(self._SPEC)
        with self.assertRaises(BoardSurgeryError) as ctx:
            build_castellation(req, self._OUTLINE, path="pcbnew_direct")
        self.assertEqual(ctx.exception.code, BOARD_SURGERY_UNSAFE_PATH)

    def test_castellation_missing_provenance_blocked(self):
        spec = dict(self._SPEC)
        del spec["provenance"]
        with self.assertRaises(BoardSurgeryError):
            parse_castellation_request(spec)

    def test_castellation_needs_positive_outline(self):
        req = parse_castellation_request(self._SPEC)
        with self.assertRaises(BoardSurgeryError):
            build_castellation(req, {"width_mm": 0, "height_mm": 0})

    def test_deterministic_same_input_same_output(self):
        req = parse_castellation_request(self._SPEC)
        a = build_castellation(req, self._OUTLINE)
        b = build_castellation(req, self._OUTLINE)
        self.assertEqual(a["sexpr_block"], b["sexpr_block"])


if __name__ == "__main__":
    unittest.main()
