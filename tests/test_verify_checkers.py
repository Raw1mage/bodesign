"""M1 verify-checker skillification — TV-1..TV-7 (test-vectors.json).

Covers the decoupling-pdn IR-native checker (TV-1/2/3/7), the ValidationEvidence
envelope tool guard (TV-5), the erc adapter (TV-6, M1-1), and the no-fabrication
tier guard (TV-4).
"""

import unittest

from bodesign_workflow_core.checkers import (
    CheckerError,
    check_board_edge_keepout,
    check_datasheet_derating,
    check_decoupling_pdn,
    check_placement_topology,
    check_spacing_via_return_path,
    guard_tier,
)
from bodesign_workflow_core.validation_evidence import (
    ValidationEvidence,
    ValidationEvidenceError,
    wrap_validation_evidence,
)

_CONTROL = "control.power.decoupling-pdn-strategy"
_THRESH = {"metric": "decoupling_distance_mm", "value": 2.0, "unit": "mm",
           "source_anchor": "TI SPRABV2"}


class DecouplingPdnTests(unittest.TestCase):
    def test_tv1_cap_over_threshold_major_finding(self):
        ir = {"components": [{"refdes": "C1", "placement": {"x": 10.0, "y": 0.0}}],
              "power_pin": {"x": 15.0, "y": 0.0}}
        ev = check_decoupling_pdn(ir, control_id=_CONTROL, threshold_block=_THRESH)
        self.assertEqual("major", ev.severity)
        self.assertEqual(1, len(ev.findings))
        self.assertEqual(_CONTROL, ev.inputs["control_id"])
        self.assertTrue(ev.inputs.get("source_anchor"))
        self.assertIn({"kind": "control", "ref": _CONTROL}, ev.anchors)

    def test_tv2_cap_within_threshold_pass_info(self):
        ir = {"components": [{"refdes": "C1", "placement": {"x": 14.0, "y": 0.0}}],
              "power_pin": {"x": 15.0, "y": 0.0}}
        thresh = {"metric": "decoupling_distance_mm", "value": 2.0, "unit": "mm",
                  "source_anchor": "TI SPRABV2"}
        ev = check_decoupling_pdn(ir, control_id=_CONTROL, threshold_block=thresh)
        self.assertEqual("info", ev.severity)
        self.assertEqual(0, len(ev.findings))

    def test_tv3_missing_ir_fields_fail_fast(self):
        ir = {"components": [{"refdes": "C1", "placement": {}}]}
        with self.assertRaises(CheckerError) as cm:
            check_decoupling_pdn(ir, control_id=_CONTROL, threshold_block=_THRESH)
        self.assertEqual("CHK_IR_FIELD_MISSING", cm.exception.code)
        missing = cm.exception.detail["missing_fields"]
        self.assertIn("components[0].placement.x", missing)
        self.assertIn("power_pin", missing)

    def test_tv7_byte_identical_across_runs(self):
        ir = {"components": [{"refdes": "C1", "placement": {"x": 10.0, "y": 0.0}}],
              "power_pin": {"x": 15.0, "y": 0.0}}
        a = check_decoupling_pdn(ir, control_id=_CONTROL, threshold_block=_THRESH)
        b = check_decoupling_pdn(ir, control_id=_CONTROL, threshold_block=_THRESH)
        self.assertEqual(a.to_dict(), b.to_dict())


class EnvelopeToolGuardTests(unittest.TestCase):
    def test_tv5_unregistered_tool_raises(self):
        with self.assertRaises(ValidationEvidenceError) as cm:
            ValidationEvidence(tool="decoupling_checker_unregistered", inputs={},
                               raw_result={"distance_mm": 5.0})
        self.assertIn("ENV_TOOL_UNKNOWN", str(cm.exception))

    def test_decoupling_uses_registered_oracle(self):
        ir = {"components": [{"refdes": "C1", "placement": {"x": 10.0, "y": 0.0}}],
              "power_pin": {"x": 15.0, "y": 0.0}}
        # must not raise ENV_TOOL_UNKNOWN — the checker's envelope tool is valid.
        ev = check_decoupling_pdn(ir, control_id=_CONTROL, threshold_block=_THRESH)
        self.assertIsInstance(ev, ValidationEvidence)


class ErcAdapterTests(unittest.TestCase):
    def test_tv6_erc_adapter_findings_and_severity(self):
        ev = wrap_validation_evidence(
            "erc", {"real_short": 1, "unconnected": 2, "intentional_nc": 3})
        self.assertEqual(3, len(ev.findings))
        self.assertEqual("critical", ev.severity)
        # intentional_nc must NOT appear in findings.
        self.assertFalse(any("intentional_nc" in f.id for f in ev.findings))

    def test_erc_adapter_byte_identical(self):
        raw = {"real_short": 1, "unconnected": 2, "intentional_nc": 3}
        a = wrap_validation_evidence("erc", dict(raw))
        b = wrap_validation_evidence("erc", dict(raw))
        self.assertEqual(a.to_dict(), b.to_dict())


class TierGuardTests(unittest.TestCase):
    def test_tv4_partial_control_forbidden_ta(self):
        with self.assertRaises(CheckerError) as cm:
            guard_tier("control.dfm.ipc-trace-width-current",
                       confidence="partial", requested_tier="T-A")
        self.assertEqual("CHK_TIER_FORBIDDEN_PARTIAL", cm.exception.code)

    def test_verified_control_allows_ta(self):
        # verified control at T-A is allowed (returns None, no raise).
        self.assertIsNone(guard_tier(_CONTROL, confidence="verified",
                                     requested_tier="T-A"))

    def test_partial_control_allows_advisory(self):
        self.assertIsNone(guard_tier("control.dfm.ipc-trace-width-current",
                                     confidence="partial", requested_tier="T-C"))


class BoardEdgeKeepoutTests(unittest.TestCase):
    _TB = {"metric": "board_edge_clearance_mm", "value": 0.5, "unit": "mm",
           "source_anchor": "IPC-2221 board-edge keepout; test"}
    # A simple 10x10mm rectangular board outline (Edge.Cuts rect).
    _OUTLINE = {"edges": [{"type": "rect", "start": [0.0, 0.0], "end": [10.0, 10.0]}]}

    def test_missing_board_outline_fails_fast(self):
        with self.assertRaises(CheckerError) as cm:
            check_board_edge_keepout({"features": []}, threshold_block=self._TB)
        self.assertEqual("CHK_IR_FIELD_MISSING", cm.exception.code)
        self.assertIn("board_outline.edges", cm.exception.detail["missing_fields"])

    def test_no_threshold_fails_fast(self):
        with self.assertRaises(CheckerError) as cm:
            check_board_edge_keepout(
                {"board_outline": self._OUTLINE, "features": []},
                threshold_block=None)
        self.assertEqual("CHK_THRESHOLD_UNBOUND", cm.exception.code)

    def test_feature_near_edge_flagged(self):
        # feature at (0.2, 5.0) is 0.2mm from the left edge < 0.5mm limit -> major
        ir = {"board_outline": self._OUTLINE,
              "features": [{"ref": "V1", "x": 0.2, "y": 5.0}]}
        ev = check_board_edge_keepout(ir, threshold_block=self._TB)
        self.assertEqual(len(ev.findings), 1)
        self.assertEqual(ev.findings[0].id, "board-edge-V1")
        self.assertEqual(ev.severity, "major")

    def test_feature_clear_of_edge_passes(self):
        # feature at center (5,5) is 5mm from all edges > 0.5mm -> no finding
        ir = {"board_outline": self._OUTLINE,
              "features": [{"ref": "V1", "x": 5.0, "y": 5.0}]}
        ev = check_board_edge_keepout(ir, threshold_block=self._TB)
        self.assertEqual(len(ev.findings), 0)
        self.assertEqual(ev.severity, "info")
        self.assertEqual(ev.inputs["source_anchor"], self._TB["source_anchor"])

    def test_missing_feature_coord_fails_fast(self):
        ir = {"board_outline": self._OUTLINE, "features": [{"ref": "V1", "x": 0.2}]}
        with self.assertRaises(CheckerError) as cm:
            check_board_edge_keepout(ir, threshold_block=self._TB)
        self.assertEqual("CHK_IR_FIELD_MISSING", cm.exception.code)
        self.assertIn("features[0].y", cm.exception.detail["missing_fields"])


class SpacingViaReturnPathTests(unittest.TestCase):
    """M2-1 copper-spacing T-A checker (si.spacing-via-return-path)."""

    _CID = "control.si.spacing-via-return-path"
    _TB = {"metric": "return_via_distance_mm", "value": 0.5, "unit": "mm",
           "source_anchor": "atlaspcb 二手 of TI spraar7j; test"}

    def test_signal_via_over_threshold_major_finding(self):
        # nearest return via is 1.0mm away > 0.5mm limit -> major
        ir = {"signal_vias": [{"ref": "V1", "x": 0.0, "y": 0.0}],
              "return_vias": [{"ref": "G1", "x": 1.0, "y": 0.0}]}
        ev = check_spacing_via_return_path(ir, threshold_block=self._TB)
        self.assertEqual(len(ev.findings), 1)
        self.assertEqual(ev.findings[0].id, "via-return-V1")
        self.assertEqual(ev.severity, "major")

    def test_signal_via_within_threshold_pass_info(self):
        # nearest return via is 0.3mm away < 0.5mm limit -> no finding
        ir = {"signal_vias": [{"ref": "V1", "x": 0.0, "y": 0.0}],
              "return_vias": [{"ref": "G1", "x": 0.3, "y": 0.0},
                              {"ref": "G2", "x": 2.0, "y": 0.0}]}
        ev = check_spacing_via_return_path(ir, threshold_block=self._TB)
        self.assertEqual(len(ev.findings), 0)
        self.assertEqual(ev.severity, "info")
        self.assertEqual(ev.inputs["source_anchor"], self._TB["source_anchor"])

    def test_no_threshold_fails_fast(self):
        with self.assertRaises(CheckerError) as cm:
            check_spacing_via_return_path(
                {"signal_vias": [], "return_vias": []}, threshold_block=None)
        self.assertEqual("CHK_THRESHOLD_UNBOUND", cm.exception.code)

    def test_missing_via_coord_fails_fast(self):
        ir = {"signal_vias": [{"ref": "V1", "x": 0.0}],
              "return_vias": [{"ref": "G1", "x": 1.0, "y": 0.0}]}
        with self.assertRaises(CheckerError) as cm:
            check_spacing_via_return_path(ir, threshold_block=self._TB)
        self.assertEqual("CHK_IR_FIELD_MISSING", cm.exception.code)
        self.assertIn("signal_vias[0].y", cm.exception.detail["missing_fields"])

    def test_no_return_vias_fails_fast(self):
        # a via-to-return gate with no return vias cannot pass silently
        ir = {"signal_vias": [{"ref": "V1", "x": 0.0, "y": 0.0}],
              "return_vias": []}
        with self.assertRaises(CheckerError) as cm:
            check_spacing_via_return_path(ir, threshold_block=self._TB)
        self.assertEqual("CHK_IR_FIELD_MISSING", cm.exception.code)
        self.assertIn("return_vias", cm.exception.detail["missing_fields"])

    def test_missing_source_anchor_rejected(self):
        ir = {"signal_vias": [{"ref": "V1", "x": 0.0, "y": 0.0}],
              "return_vias": [{"ref": "G1", "x": 1.0, "y": 0.0}]}
        bad = {"metric": "return_via_distance_mm", "value": 0.5, "unit": "mm"}
        with self.assertRaises(CheckerError) as cm:
            check_spacing_via_return_path(ir, threshold_block=bad)
        self.assertEqual("CHK_SOURCE_ANCHOR_MISSING", cm.exception.code)

    def test_byte_identical_across_runs(self):
        ir = {"signal_vias": [{"ref": "V1", "x": 0.0, "y": 0.0},
                              {"ref": "V2", "x": 3.0, "y": 0.0}],
              "return_vias": [{"ref": "G1", "x": 1.0, "y": 0.0}]}
        a = check_spacing_via_return_path(ir, threshold_block=self._TB)
        b = check_spacing_via_return_path(ir, threshold_block=self._TB)
        self.assertEqual(a.raw_result, b.raw_result)
        self.assertEqual([f.id for f in a.findings], [f.id for f in b.findings])


class PlacementTopologyTests(unittest.TestCase):
    """M2-3 placement-topology T-A checker (esd.tvs-placement-routing)."""

    _CID = "control.esd.tvs-placement-routing"
    _TB = {"metric": "tvs_to_connector_distance_mm", "value": 10.0, "unit": "mm",
           "source_anchor": "TI slva680A / atlaspcb: TVS 到 connector 距離≤10mm; test"}

    def test_part_over_threshold_major_finding(self):
        # TVS 15mm from connector anchor > 10mm limit -> major
        ir = {"anchor": {"ref": "J1", "x": 0.0, "y": 0.0},
              "parts": [{"ref": "D1", "x": 15.0, "y": 0.0}]}
        ev = check_placement_topology(ir, control_id=self._CID, threshold_block=self._TB)
        self.assertEqual("major", ev.severity)
        self.assertEqual(1, len(ev.findings))
        self.assertEqual(self._CID, ev.inputs["control_id"])
        self.assertTrue(ev.inputs.get("source_anchor"))
        self.assertIn({"kind": "control", "ref": self._CID}, ev.anchors)

    def test_part_within_threshold_pass_info(self):
        # TVS 8mm from connector < 10mm limit -> no finding
        ir = {"anchor": {"ref": "J1", "x": 0.0, "y": 0.0},
              "parts": [{"ref": "D1", "x": 8.0, "y": 0.0}]}
        ev = check_placement_topology(ir, control_id=self._CID, threshold_block=self._TB)
        self.assertEqual("info", ev.severity)
        self.assertEqual(0, len(ev.findings))
        self.assertEqual(self._TB["source_anchor"], ev.inputs["source_anchor"])

    def test_no_threshold_fails_fast(self):
        ir = {"anchor": {"ref": "J1", "x": 0.0, "y": 0.0}, "parts": []}
        with self.assertRaises(CheckerError) as cm:
            check_placement_topology(ir, control_id=self._CID, threshold_block=None)
        self.assertEqual("CHK_THRESHOLD_UNBOUND", cm.exception.code)

    def test_missing_part_coord_fails_fast(self):
        ir = {"anchor": {"ref": "J1", "x": 0.0, "y": 0.0},
              "parts": [{"ref": "D1", "x": 15.0}]}
        with self.assertRaises(CheckerError) as cm:
            check_placement_topology(ir, control_id=self._CID, threshold_block=self._TB)
        self.assertEqual("CHK_IR_FIELD_MISSING", cm.exception.code)
        self.assertIn("parts[0].y", cm.exception.detail["missing_fields"])

    def test_missing_anchor_fails_fast(self):
        ir = {"parts": [{"ref": "D1", "x": 15.0, "y": 0.0}]}
        with self.assertRaises(CheckerError) as cm:
            check_placement_topology(ir, control_id=self._CID, threshold_block=self._TB)
        self.assertEqual("CHK_IR_FIELD_MISSING", cm.exception.code)
        self.assertIn("anchor", cm.exception.detail["missing_fields"])

    def test_missing_source_anchor_rejected(self):
        ir = {"anchor": {"ref": "J1", "x": 0.0, "y": 0.0},
              "parts": [{"ref": "D1", "x": 15.0, "y": 0.0}]}
        bad = {"metric": "tvs_to_connector_distance_mm", "value": 10.0, "unit": "mm"}
        with self.assertRaises(CheckerError) as cm:
            check_placement_topology(ir, control_id=self._CID, threshold_block=bad)
        self.assertEqual("CHK_SOURCE_ANCHOR_MISSING", cm.exception.code)

    def test_byte_identical_across_runs(self):
        ir = {"anchor": {"ref": "J1", "x": 0.0, "y": 0.0},
              "parts": [{"ref": "D1", "x": 15.0, "y": 0.0},
                        {"ref": "D2", "x": 3.0, "y": 0.0}]}
        a = check_placement_topology(ir, control_id=self._CID, threshold_block=self._TB)
        b = check_placement_topology(ir, control_id=self._CID, threshold_block=self._TB)
        self.assertEqual(a.to_dict(), b.to_dict())


class DatasheetDeratingTests(unittest.TestCase):
    """M2-4 datasheet derating checker (fuse / mov / ntc)."""

    _FUSE = "control.protection.fuse-ptc-derating"
    _NTC = "control.protection.ntc-inrush-selection"
    _TB_FRACTION = {"metric": "fuse_current_derating", "value": 0.75,
                    "unit": "fraction_of_rating", "direction": "max_fraction",
                    "source_anchor": "Littelfuse Fuseology 25% derating"}
    _TB_SURGE = {"metric": "ntc_surge_current_limit", "value": "surge=V/R25<=max_inrush",
                 "unit": "ratio", "direction": "surge_formula",
                 "source_anchor": "Vishay/Ametherm Doc#24291"}

    def test_fraction_over_derating_major_finding(self):
        # 8A design on a 10A fuse: 8 > 0.75*10 = 7.5 -> violation
        inputs = {"refdes": "F1", "design_value": 8.0, "rating": 10.0}
        ev = check_datasheet_derating(inputs, control_id=self._FUSE,
                                      threshold_block=self._TB_FRACTION)
        self.assertEqual("major", ev.severity)
        self.assertEqual(1, len(ev.findings))
        self.assertEqual(self._FUSE, ev.inputs["control_id"])
        self.assertTrue(ev.inputs.get("source_anchor"))
        self.assertIn({"kind": "control", "ref": self._FUSE}, ev.anchors)

    def test_fraction_within_derating_pass_info(self):
        # 7A design on a 10A fuse: 7 <= 7.5 -> pass
        inputs = {"refdes": "F1", "design_value": 7.0, "rating": 10.0}
        ev = check_datasheet_derating(inputs, control_id=self._FUSE,
                                      threshold_block=self._TB_FRACTION)
        self.assertEqual("info", ev.severity)
        self.assertEqual(0, len(ev.findings))

    def test_surge_formula_over_max_inrush(self):
        # V=12, R25=1 -> surge 12A > max inrush 10A -> violation
        inputs = {"refdes": "RT1", "input_voltage_v": 12.0, "r25_ohm": 1.0,
                  "max_inrush_current_a": 10.0}
        ev = check_datasheet_derating(inputs, control_id=self._NTC,
                                      threshold_block=self._TB_SURGE)
        self.assertEqual("major", ev.severity)
        self.assertEqual(1, len(ev.findings))
        self.assertEqual("inrush-RT1", ev.findings[0].id)

    def test_surge_formula_within_max_inrush(self):
        # V=12, R25=2 -> surge 6A <= 10A -> pass
        inputs = {"refdes": "RT1", "input_voltage_v": 12.0, "r25_ohm": 2.0,
                  "max_inrush_current_a": 10.0}
        ev = check_datasheet_derating(inputs, control_id=self._NTC,
                                      threshold_block=self._TB_SURGE)
        self.assertEqual("info", ev.severity)

    def test_missing_input_fails_fast(self):
        inputs = {"refdes": "F1", "design_value": 8.0}  # no rating
        with self.assertRaises(CheckerError) as cm:
            check_datasheet_derating(inputs, control_id=self._FUSE,
                                     threshold_block=self._TB_FRACTION)
        self.assertEqual("CHK_IR_FIELD_MISSING", cm.exception.code)
        self.assertIn("rating", cm.exception.detail["missing_fields"])

    def test_no_threshold_fails_fast(self):
        inputs = {"refdes": "F1", "design_value": 8.0, "rating": 10.0}
        with self.assertRaises(CheckerError) as cm:
            check_datasheet_derating(inputs, control_id=self._FUSE,
                                     threshold_block=None)
        self.assertEqual("CHK_THRESHOLD_UNBOUND", cm.exception.code)

    def test_unsupported_direction_fails_fast(self):
        bad = {"metric": "x", "value": 1.0, "direction": "bogus",
               "source_anchor": "s"}
        with self.assertRaises(CheckerError) as cm:
            check_datasheet_derating({"refdes": "F1"}, control_id=self._FUSE,
                                     threshold_block=bad)
        self.assertEqual("CHK_THRESHOLD_UNBOUND", cm.exception.code)

    def test_missing_source_anchor_rejected(self):
        bad = {"metric": "fuse_current_derating", "value": 0.75,
               "direction": "max_fraction"}
        inputs = {"refdes": "F1", "design_value": 8.0, "rating": 10.0}
        with self.assertRaises(CheckerError) as cm:
            check_datasheet_derating(inputs, control_id=self._FUSE,
                                     threshold_block=bad)
        self.assertEqual("CHK_SOURCE_ANCHOR_MISSING", cm.exception.code)

    def test_ntc_zero_r25_fails_fast(self):
        inputs = {"refdes": "RT1", "input_voltage_v": 12.0, "r25_ohm": 0.0,
                  "max_inrush_current_a": 10.0}
        with self.assertRaises(CheckerError) as cm:
            check_datasheet_derating(inputs, control_id=self._NTC,
                                     threshold_block=self._TB_SURGE)
        self.assertEqual("CHK_IR_FIELD_MISSING", cm.exception.code)

    def test_byte_identical_across_runs(self):
        inputs = {"refdes": "F1", "design_value": 8.0, "rating": 10.0}
        a = check_datasheet_derating(inputs, control_id=self._FUSE,
                                     threshold_block=self._TB_FRACTION)
        b = check_datasheet_derating(inputs, control_id=self._FUSE,
                                     threshold_block=self._TB_FRACTION)
        self.assertEqual(a.to_dict(), b.to_dict())


if __name__ == "__main__":
    unittest.main()
