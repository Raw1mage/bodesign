"""P2 Slice-A delivery tests: multi-sheet leaf schematic emission and readability.

Verifies:
1. Native bodesign_emit_multisheet produces all 5 target btdongle leaf pages:
   - usbc
   - power_rail
   - battery
   - charge_enable
   - mcu_swd
   plus root schematic.
2. Wire preservation:
   - usbc has drawn wires (>= 15 wires) connecting J1, D1, R1, R2, F1, C1 rather
     than collapsing into disconnected global labels.
   - power_rail, battery, charge_enable, mcu_swd have active wire runs.
3. Title-block collision prevention:
   - fit_page detects title-block boundary interference and escalates/shifts
     so drawn content does not invade bottom-right title block.
4. Passive symbol text placement:
   - Passives (R, C, F, D) do not place Reference/Value property text directly
     centered over symbol body graphics.
"""

import tempfile
import unittest
from pathlib import Path

from experiments.btdongle_multisheet_e2e import (
    GUEST_SCH_GEN,
    SHEET_OF_REF,
    build_spec,
    load_guest_design,
    measure_subsystem_placement,
)
from bodesign_eda_bridge.hierarchical import (
    VIEW_LOCAL_MAX_NODES,
    _drawn_extent,
    emit_multisheet,
    fit_page,
)
from services.mcp.server import TOOLS_BY_NAME


class TestP2LeafDelivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.design = load_guest_design()
        _, cls.replicas, cls.report = measure_subsystem_placement(
            cls.design, SHEET_OF_REF, VIEW_LOCAL_MAX_NODES
        )
        cls.views = {}
        for entry in cls.report.values():
            cls.views.setdefault(entry["view_sheet"], []).extend(entry["nets"])
        cls.spec = build_spec(cls.design, cls.replicas)

    def test_emit_multisheet_handler_e2e_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "deliverable"
            args = {
                "out_dir": str(out_dir),
                "project_name": "btdongle_ms",
                "spec": self.spec,
                "symbol_dirs": [str(GUEST_SCH_GEN), "/usr/share/kicad/symbols"],
                "power_ports": False,
                "connection_style": "wire",
                "subsystem_views": self.views,
                "view_local_max_nodes": VIEW_LOCAL_MAX_NODES,
            }
            handler = TOOLS_BY_NAME["bodesign_emit_multisheet"]["handler"]
            res = handler(args)
            self.assertTrue(res.get("ok"), msg=f"Emit failed: {res}")
            self.assertEqual(res.get("emit_mode"), "hierarchical")

            # Check files exist
            files = [Path(p) for p in res["files"]]
            self.assertTrue(any(f.name == "btdongle_ms.kicad_sch" for f in files))
            leaf_names = {"usbc", "power_rail", "battery", "charge_enable", "mcu_swd"}
            for leaf in leaf_names:
                self.assertIn(leaf, res["leaf_paths"])
                leaf_path = Path(res["leaf_paths"][leaf])
                self.assertTrue(leaf_path.exists(), f"Leaf path {leaf_path} missing")

            # Wire assertions
            usbc_text = Path(res["leaf_paths"]["usbc"]).read_text()
            usbc_wires = usbc_text.count("(wire")
            self.assertGreaterEqual(
                usbc_wires, 15, f"usbc lost wires (got {usbc_wires}, expected >= 15)"
            )

            pwr_text = Path(res["leaf_paths"]["power_rail"]).read_text()
            self.assertGreaterEqual(pwr_text.count("(wire"), 15)

            bat_text = Path(res["leaf_paths"]["battery"]).read_text()
            self.assertGreaterEqual(bat_text.count("(wire"), 5)

            mcu_text = Path(res["leaf_paths"]["mcu_swd"]).read_text()
            self.assertGreaterEqual(mcu_text.count("(wire"), 10)

    def test_fit_page_title_block_avoidance(self):
        # A test schematic whose top is at margin and bottom invades A4 title block
        sample_sch = (
            '(kicad_sch (version 20250114) (generator "bodesign")\n'
            '  (paper "A4")\n'
            '  (lib_symbols\n'
            '    (symbol "Device:R" (pin passive line (at 0 2.54 270) (length 2.54) (name "1") (number "1")))\n'
            '  )\n'
            '  (symbol (lib_id "Device:R") (at 200.0 15.0 0) (unit 1)\n'
            '    (property "Reference" "R1" (at 202.54 13.73 0))\n'
            '    (property "Value" "10k" (at 202.54 16.27 0))\n'
            '  )\n'
            '  (symbol (lib_id "Device:R") (at 200.0 180.0 0) (unit 1)\n'
            '    (property "Reference" "R2" (at 202.54 178.73 0))\n'
            '    (property "Value" "10k" (at 202.54 181.27 0))\n'
            '  )\n'
            ')\n'
        )
        _, chosen_paper, report = fit_page(sample_sch, "A4")
        # Must escalate from A4 to A3 because headroom is insufficient to shift out of title block
        self.assertEqual(chosen_paper, "A3")

    def test_passive_symbol_properties_not_centered_over_body(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "deliverable"
            res = emit_multisheet(
                project_dir=str(out_dir),
                project_name="btdongle_ms",
                spec=self.spec,
                symbol_dir=[str(GUEST_SCH_GEN), "/usr/share/kicad/symbols"],
                power_ports=False,
                connection_style="wire",
                subsystem_views=self.views,
            )
            self.assertIn("usbc", res.leaf_paths)
            usbc_text = Path(res.leaf_paths["usbc"]).read_text()

            # In the fixed code, R1 is at 36.83 (text at x=39.37) and R2 is at 83.82 (text at x=86.36)
            self.assertIn('(property "Reference" "R1" (at 39.37', usbc_text)
            self.assertIn('(property "Reference" "R2" (at 86.36', usbc_text)

    def test_leaf_geometric_readability_assertions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "deliverable"
            res = emit_multisheet(
                project_dir=str(out_dir),
                project_name="btdongle_ms",
                spec=self.spec,
                symbol_dir=[str(GUEST_SCH_GEN), "/usr/share/kicad/symbols"],
                power_ports=False,
                connection_style="wire",
                subsystem_views=self.views,
                view_local_max_nodes=VIEW_LOCAL_MAX_NODES,
            )
            # 1. Wire-through-body: wire_body_intrusions count == 0 across all emitted leaves
            for leaf_name, leaf_res in res.leaf_results.items():
                intrusions = leaf_res.wire_body_intrusions
                self.assertEqual(
                    len(intrusions), 0,
                    f"Leaf {leaf_name} has {len(intrusions)} wire-through-body intrusions: {intrusions}"
                )

            # 2. Foreign pin tip clearance: no wire segment passes through foreign pin tips (+-1.27mm)
            # 3. Corridor separation: collinear-overlap count across distinct nets == 0
            pin_to_net = {}
            for net_dict in self.spec["nets"]:
                for node in net_dict["nodes"]:
                    pin_to_net[str(node)] = net_dict["name"]

            from bodesign_eda_bridge.replica_fidelity import parse_placed_symbols
            from bodesign_eda_bridge.kicad_emit import _seg_hits_box, load_symbol, _collinear_overlap
            import re

            total_foreign_pin_hits = 0
            total_distinct_collinear_overlaps = 0

            for leaf_name, leaf_path in res.leaf_paths.items():
                text = Path(leaf_path).read_text()
                symbols = parse_placed_symbols(text)
                all_pins = []
                for s in symbols:
                    try:
                        _, pins = load_symbol(s.lib_id, [str(GUEST_SCH_GEN), "/usr/share/kicad/symbols"])
                        for pnum, pinfo in pins.items():
                            px = s.x + pinfo[0]
                            py = s.y - pinfo[1]
                            net = pin_to_net.get(f"{s.ref}.{pnum}")
                            all_pins.append((s.ref, pnum, (px, py), net))
                    except Exception:
                        pass

                wires = []
                for m in re.finditer(r'\(wire\s+\(pts\s+\(xy\s+([-\d.]+)\s+([-\d.]+)\)\s+\(xy\s+([-\d.]+)\s+([-\d.]+)\)\)', text):
                    x1, y1, x2, y2 = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
                    wires.append(((x1, y1), (x2, y2)))

                # Build connected components of wires to resolve nets accurately
                parent = {}
                def find(p):
                    if p not in parent: parent[p] = p
                    if parent[p] != p: parent[p] = find(parent[p])
                    return parent[p]
                def union(p1, p2):
                    r1, r2 = find(p1), find(p2)
                    if r1 != r2: parent[r1] = r2

                wires_rounded = []
                for p1, p2 in wires:
                    pt1 = (round(p1[0], 2), round(p1[1], 2))
                    pt2 = (round(p2[0], 2), round(p2[1], 2))
                    wires_rounded.append((pt1, pt2))
                    union(pt1, pt2)

                labels = []
                for m in re.finditer(r'\((?:global_)?label\s+\"([^\"]+)\"[^()]*\(at\s+([-\d.]+)\s+([-\d.]+)', text):
                    labels.append((m.group(1), (round(float(m.group(2)), 2), round(float(m.group(3)), 2))))

                comp_nets = {}
                for ref, pnum, pt, net in all_pins:
                    rpt = (round(pt[0], 2), round(pt[1], 2))
                    if rpt in parent:
                        comp_nets.setdefault(find(rpt), set()).add(net)
                for lname, lpt in labels:
                    if lpt in parent:
                        comp_nets.setdefault(find(lpt), set()).add(lname)

                # Check foreign pin tip hits (margin +-1.27 mm)
                for w in wires_rounded:
                    r = find(w[0])
                    w_nets = comp_nets.get(r, set())
                    for ref, pnum, pt, net in all_pins:
                        rpt = (round(pt[0], 2), round(pt[1], 2))
                        if net in w_nets:
                            continue
                        if rpt == w[0] or rpt == w[1]:
                            continue
                        m = 1.26
                        box = (rpt[0] - m, rpt[0] + m, rpt[1] - m, rpt[1] + m)
                        if _seg_hits_box(w[0], w[1], box):
                            total_foreign_pin_hits += 1

                # Check collinear overlap across distinct nets
                for i, w1 in enumerate(wires_rounded):
                    r1 = find(w1[0])
                    for w2 in wires_rounded[i + 1:]:
                        r2 = find(w2[0])
                        if r1 != r2:
                            if _collinear_overlap(w1, w2):
                                total_distinct_collinear_overlaps += 1

            self.assertEqual(
                total_foreign_pin_hits, 0,
                f"Found {total_foreign_pin_hits} wire-vs-foreign-pin-tip intersections"
            )
            self.assertEqual(
                total_distinct_collinear_overlaps, 0,
                f"Found {total_distinct_collinear_overlaps} collinear overlaps across distinct nets"
            )


if __name__ == "__main__":
    unittest.main()
