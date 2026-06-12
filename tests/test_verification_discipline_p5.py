"""P5 (workflow_verification-discipline) — G7 Reference Comparator.

Covers spec.md scenarios / test-vectors.json:
- 良品自比對得滿分 (TV-G7-01)
- 擾動設計輸出分級退化分數與明細 (TV-G7-02)
- 元件匹配採兩段式 + Hungarian 全域指派 (TV-G7-03)
- 輸入 IR 不合法即 fail fast (TV-G7-04)
- 確定性與規模 (TV-G7-05)
"""

import json
import time
import unittest

from bodesign_design_ir import BoardDesign, ComponentInstance, Net
from bodesign_design_ir.compare import (
    SYM_PIN,
    CompareError,
    ScoringConfig,
    compare_designs,
)


def _golden(optional_c9=True, drop_u2=False, r3_val="10k", swap=False):
    """Small MCU board fixture: U1 MCU + U2 LDO + R3/C5 passives + optional C9."""
    comps = [
        ComponentInstance("U1", part_number="STM32F4",
                          flexible_pin_groups={"GPIO_A": ["PA0", "PA1", "PA2"]}),
        ComponentInstance("R3", part_number="RES", value=r3_val),
        ComponentInstance("C5", part_number="CAP", value="100n"),
    ]
    if not drop_u2:
        comps.append(ComponentInstance("U2", part_number="LDO33"))
    comps.append(ComponentInstance("C9", part_number="CAP", value="10u", optional=optional_c9))
    sda, scl = ("SCL0", "SDA0") if swap else ("SDA0", "SCL0")
    nets = [
        Net("GND", connected_pads=["U1-GND", "R3-2", "C5-2", "C9-2"]
            + ([] if drop_u2 else ["U2-GND"])),
        Net("3V3", connected_pads=["U1-VDD", "C5-1", "C9-1"]
            + ([] if drop_u2 else ["U2-OUT"])),
        Net(sda, connected_pads=["U1-PB7", "R3-1"]),
        Net(scl, connected_pads=["U1-PB6"]),
    ]
    return BoardDesign(id="bd", version="1", title="golden", components=comps, nets=nets)


class SelfCompareTests(unittest.TestCase):
    """TV-G7-01: a design compared against itself scores perfectly."""

    def test_self_compare_is_perfect(self):
        ref = _golden()
        result = compare_designs(_golden(), ref)
        self.assertEqual((result.s_comp, result.s_attr, result.s_conn, result.s_total),
                         (1.0, 1.0, 1.0, 1.0))
        self.assertIsNone(result.first_divergence)
        self.assertTrue(all(i["status"] == "matched"
                            for i in result.items if i["severity"] != "info"))


class PerturbationTests(unittest.TestCase):
    """TV-G7-02: graded degradation + per-dimension mismatch details."""

    def setUp(self):
        self.ref = _golden()
        self.result = compare_designs(
            _golden(drop_u2=True, r3_val="1k", swap=True), self.ref)

    def test_scores_degrade_with_weighted_total(self):
        r = self.result
        self.assertLess(r.s_comp, 1.0)
        self.assertLess(r.s_attr, 1.0)
        self.assertLess(r.s_conn, 1.0)
        expected = round(0.4 * r.s_comp + 0.2 * r.s_attr + 0.4 * r.s_conn, 6)
        self.assertEqual(r.s_total, expected)

    def test_missing_required_component_is_critical(self):
        items = [i for i in self.result.items
                 if i["dimension"] == "component" and i["key"] == "U2"]
        self.assertEqual(items[0]["status"], "missing")
        self.assertEqual(items[0]["severity"], "critical")

    def test_value_change_flagged_with_both_sides(self):
        rows = [i for i in self.result.items
                if i["dimension"] == "component_value" and i["key"] == "R3"]
        self.assertEqual(len(rows), 1)
        detail = rows[0]["evidence_refs"][0]["detail"]
        self.assertIn("1k", detail)
        self.assertIn("10k", detail)

    def test_pin_level_details_not_binary(self):
        pin_rows = [i for i in self.result.items if i["dimension"] == "pin"]
        self.assertTrue(pin_rows)
        statuses = {i["status"] for i in self.result.items}
        self.assertTrue({"matched", "missing"} <= statuses)

    def test_first_divergence_points_at_top_severity(self):
        fd = self.result.items[self.result.first_divergence]
        self.assertEqual(fd["severity"], "critical")
        self.assertNotEqual(fd["status"], "matched")


class TwoStageMatchingTests(unittest.TestCase):
    """TV-G7-03: required-first Hungarian; optional free; __sym__; FlexiblePin."""

    def test_optional_absence_not_penalized(self):
        ref = _golden(optional_c9=True)
        cand = _golden(optional_c9=True)
        cand.components = [c for c in cand.components if c.refdes != "C9"]
        cand.nets = [Net(n.name, connected_pads=[p for p in n.connected_pads
                                                 if not p.startswith("C9-")])
                     for n in cand.nets]
        result = compare_designs(cand, ref)
        self.assertEqual(result.s_comp, 1.0)
        c9_rows = [i for i in result.items if i["key"] == "C9"]
        self.assertTrue(all(i["severity"] == "info" for i in c9_rows))

    def test_required_absence_is_penalized(self):
        ref = _golden(optional_c9=False)  # C9 now required
        cand = _golden(optional_c9=False)
        cand.components = [c for c in cand.components if c.refdes != "C9"]
        cand.nets = [Net(n.name, connected_pads=[p for p in n.connected_pads
                                                 if not p.startswith("C9-")])
                     for n in cand.nets]
        result = compare_designs(cand, ref)
        self.assertLess(result.s_comp, 1.0)

    def test_symmetric_passive_pins_normalized(self):
        # swap R3 pin numbers: '__sym__' normalization keeps it a perfect match
        ref = _golden()
        cand = _golden()
        for net in cand.nets:
            net.connected_pads = [
                p.replace("R3-1", "R3-X").replace("R3-2", "R3-1").replace("R3-X", "R3-2")
                for p in net.connected_pads]
        result = compare_designs(cand, ref)
        self.assertEqual(result.s_conn, 1.0)

    def test_flexible_pin_group_members_interchangeable(self):
        ref = _golden()
        ref.nets.append(Net("LED", connected_pads=["U1-PA0"]))
        cand = _golden()
        cand.nets.append(Net("LED", connected_pads=["U1-PA2"]))  # different group member
        result = compare_designs(cand, ref)
        self.assertEqual(result.s_conn, 1.0)

    def test_sym_pin_constant(self):
        self.assertEqual(SYM_PIN, "__sym__")


class FailFastTests(unittest.TestCase):
    """TV-G7-04 + CMP_CONFIG_INVALID."""

    def test_net_referencing_unknown_component(self):
        ref = _golden()
        bad = _golden()
        bad.nets[0].connected_pads.append("UNKNOWN-1")
        with self.assertRaises(CompareError) as ctx:
            compare_designs(bad, ref)
        self.assertIn("CMP_IR_INVALID", str(ctx.exception))

    def test_malformed_pad_string(self):
        bad = _golden()
        bad.nets[0].connected_pads.append("NOSEPARATOR")
        with self.assertRaises(CompareError):
            compare_designs(bad, _golden())

    def test_empty_components(self):
        empty = BoardDesign(id="e", version="1", title="empty")
        with self.assertRaises(CompareError):
            compare_designs(empty, _golden())
        with self.assertRaises(CompareError):
            compare_designs(_golden(), empty)

    def test_duplicate_refdes(self):
        bad = _golden()
        bad.components.append(ComponentInstance("U1", part_number="DUP"))
        with self.assertRaises(CompareError):
            compare_designs(bad, _golden())

    def test_config_weights_must_sum_to_one(self):
        with self.assertRaises(CompareError) as ctx:
            ScoringConfig(weight_comp=0.9, weight_attr=0.9, weight_conn=0.9)
        self.assertIn("CMP_CONFIG_INVALID", str(ctx.exception))
        with self.assertRaises(CompareError):
            ScoringConfig(weight_comp=-0.2, weight_attr=0.8, weight_conn=0.4)

    def test_custom_valid_config_accepted(self):
        cfg = ScoringConfig(weight_comp=0.5, weight_attr=0.1, weight_conn=0.4)
        result = compare_designs(_golden(), _golden(), config=cfg)
        self.assertEqual(result.s_total, 1.0)


class DeterminismAndScaleTests(unittest.TestCase):
    """TV-G7-05: byte-equal reruns + board-scale Hungarian feasibility."""

    def test_byte_equal_output(self):
        ref = _golden()
        a = json.dumps(compare_designs(_golden(drop_u2=True), ref).to_dict(), sort_keys=True)
        b = json.dumps(compare_designs(_golden(drop_u2=True), ref).to_dict(), sort_keys=True)
        self.assertEqual(a, b)

    def _large_board(self, n_components=200, perturb=False):
        comps, nets = [], []
        for i in range(n_components):
            comps.append(ComponentInstance(f"U{i}", part_number=f"PART{i % 20}"))
        for i in range(n_components):
            a, b = f"U{i}", f"U{(i + 1) % n_components}"
            nets.append(Net(f"NET{i}", connected_pads=[f"{a}-2", f"{b}-1"]))
        if perturb:
            comps = comps[:-2]  # drop two components
            nets = [n for n in nets
                    if all(not p.startswith(("U198-", "U199-")) for p in n.connected_pads)]
        return BoardDesign(id="big", version="1", title="large",
                           components=comps, nets=nets)

    def test_board_scale_within_wall_time(self):
        ref = self._large_board()
        cand = self._large_board(perturb=True)
        start = time.monotonic()
        result = compare_designs(cand, ref)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 30.0, f"comparator too slow at board scale: {elapsed:.1f}s")
        self.assertLess(result.s_comp, 1.0)
        self.assertGreater(result.s_comp, 0.9)

    def test_envelope_wrapping(self):
        """DD-11: result wraps as a ValidationEvidence envelope (tool=crosscheck)."""
        result = compare_designs(_golden(drop_u2=True), _golden())
        env = result.to_validation_evidence()
        self.assertEqual(env["schema"], "bodesign.validation_evidence.v1")
        self.assertEqual(env["tool"], "crosscheck")
        self.assertEqual(env["severity"], "critical")  # missing required component
        self.assertEqual(env["raw_result"]["scores"]["S_total"], result.s_total)
        self.assertTrue(any(f["id"].startswith("cmp-component-U2") for f in env["findings"]))

    def test_envelope_roundtrips_into_spine(self):
        """G7 output flows through A3 evidence backflow unchanged."""
        import os
        import shutil
        import tempfile
        from pathlib import Path

        from bodesign_workflow_core import dispatch_work_packet, return_evidence

        base = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"
        base.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-cmp-spine-", dir=base))
        try:
            packet = dispatch_work_packet(work, "C04", "compare against golden reference")
            env = compare_designs(_golden(drop_u2=True), _golden()).to_validation_evidence()
            ev = return_evidence(work, packet.packet_id, envelope=env)
            self.assertEqual(ev.envelope["tool"], "crosscheck")
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
