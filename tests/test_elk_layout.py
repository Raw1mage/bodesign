"""S3 engine spike: elk_layout bridge (DD-15, DD-9 clearance conditions 3/5).

Populations:
  * graph build from a small synthetic sheet (stock Device:R/C symbols);
  * quantize + verify on a synthetic ELK solution (no Node needed);
  * typed refusal on timeout / malformed runner output / nonzero exit;
  * connectivity-preservation: a solution that fuses two nets, or leaves a
    net in two fragments, is refused with the fused/missing populations named;
  * end-to-end through the real runner when node + elkjs are installed
    (skipped with the reason named otherwise -- never silently green).
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge.elk_layout import (
    DEFAULT_LAYOUT_OPTIONS,
    ELKJS_PINNED_VERSION,
    RUNNER,
    ElkLayoutError,
    PresentationSolution,
    build_elk_graph,
    quantize_solution,
    resolve_symbol_geometry,
    run_elk,
    solve_sheet,
    verify_solution,
)
from bodesign_eda_bridge.kicad_emit import EmitComponent, EmitNet

SYMBOL_DIR = "/usr/share/kicad/symbols"
HAVE_SYMBOLS = Path(SYMBOL_DIR, "Device.kicad_sym").is_file()
HAVE_NODE = bool(os.environ.get("BODESIGN_NODE_BIN") or shutil.which("node"))
HAVE_ELK = (RUNNER.parent / "node_modules" / "elkjs" / "package.json").is_file()


def _comps():
    return [
        EmitComponent(ref="R1", lib_id="Device:R", value="1k", footprint="", x=0, y=0),
        EmitComponent(ref="R2", lib_id="Device:R", value="1k", footprint="", x=0, y=0),
        EmitComponent(ref="C1", lib_id="Device:C", value="100n", footprint="", x=0, y=0),
    ]


def _nets():
    return [
        EmitNet("NETA", [("R1", "2"), ("R2", "1"), ("C1", "1")]),
        EmitNet("NETB", [("R2", "2"), ("C1", "2")]),
        EmitNet("GND", [("R1", "1")]),
    ]


@unittest.skipUnless(HAVE_SYMBOLS, f"KiCad symbol library not at {SYMBOL_DIR}")
class GraphBuild(unittest.TestCase):
    def test_nodes_have_fixed_ports_at_pin_tips_on_grid(self):
        geo = resolve_symbol_geometry(_comps(), SYMBOL_DIR)
        b = build_elk_graph(_comps(), _nets(), geo)
        ids = {n["id"] for n in b.graph["children"]}
        self.assertEqual(ids, {"R1", "R2", "C1"})
        for n in b.graph["children"]:
            self.assertEqual(n["properties"]["elk.portConstraints"], "FIXED_POS")
            ox, oy = b.origins[n["id"]]
            for p in n["ports"]:
                ref, pin = b.ports[p["id"]]
                px, py, _rot = geo[ref].pins[pin]
                self.assertAlmostEqual(p["x"], ox + px, places=4)
                self.assertAlmostEqual(p["y"], oy - py, places=4)
                # node origin + pin offset is a grid multiple => tips snap with the node
                self.assertAlmostEqual((p["x"] / 1.27) % 1.0 % 1.0, 0.0, places=3)
                self.assertAlmostEqual((p["y"] / 1.27) % 1.0 % 1.0, 0.0, places=3)

    def test_one_edge_per_extra_node_and_single_pin_nets_undrawn(self):
        geo = resolve_symbol_geometry(_comps(), SYMBOL_DIR)
        b = build_elk_graph(_comps(), _nets(), geo)
        self.assertEqual(sorted(b.edge_nets.values()), ["NETA", "NETA", "NETB"])
        self.assertEqual(b.drawn_nets, ["NETA", "NETB"])
        self.assertIn("GND", b.undrawn)
        self.assertEqual(b.graph["layoutOptions"], DEFAULT_LAYOUT_OPTIONS)

    def test_drawn_filter_reason_is_recorded(self):
        geo = resolve_symbol_geometry(_comps(), SYMBOL_DIR)
        b = build_elk_graph(_comps(), _nets(), geo,
                            drawn_filter=lambda n: (n.name != "NETB", "policy"))
        self.assertEqual(b.undrawn["NETB"], "policy")
        self.assertEqual(b.drawn_nets, ["NETA"])

    def test_unknown_pin_in_net_is_refused(self):
        geo = resolve_symbol_geometry(_comps(), SYMBOL_DIR)
        with self.assertRaises(ElkLayoutError) as cm:
            build_elk_graph(_comps(), [EmitNet("X", [("R1", "1"), ("R9", "1")])], geo)
        self.assertEqual(cm.exception.code, "E_ELK_PIN_UNRESOLVED")

    def test_missing_symbol_is_refused_not_guessed(self):
        comps = _comps() + [EmitComponent(ref="U9", lib_id="Nope:Nothing", value="",
                                          footprint="", x=0, y=0)]
        with self.assertRaises(ElkLayoutError) as cm:
            resolve_symbol_geometry(comps, SYMBOL_DIR)
        self.assertEqual(cm.exception.code, "E_ELK_SYMBOL_UNRESOLVED")
        self.assertIn("U9", str(cm.exception.details["missing"]))


def _synthetic_solution(b, geo, *, routes):
    """Build an ELK-shaped solution for the synthetic sheet: nodes at given
    positions; each edge routed as given (list of (x, y) in ELK space)."""
    children = []
    for n in b.graph["children"]:
        x, y = routes["nodes"][n["id"]]
        children.append({**n, "x": x, "y": y})
    edges = []
    for e in b.graph["edges"]:
        pts = routes["edges"][e["id"]]
        edges.append({**e, "sections": [{
            "startPoint": {"x": pts[0][0], "y": pts[0][1]},
            "endPoint": {"x": pts[-1][0], "y": pts[-1][1]},
            "bendPoints": [{"x": p[0], "y": p[1]} for p in pts[1:-1]],
            "incomingShape": e["sources"][0], "outgoingShape": e["targets"][0]}]})
    return {"id": "sheet", "children": children, "edges": edges}


# --------------------------------------------------------------------------
# T-vs-foreign-X regression (round 2, ruling 4): a same-net interior T must be
# split into three wire ENDS with ONE dot; a foreign-net interior crossing must
# get neither endpoints nor a dot. Verified on a FRESH native kicad-cli export.

import re
import subprocess

from bodesign_eda_bridge.elk_layout import ElkGraphBuild, _split_at_contacts
from bodesign_eda_bridge.kicad_emit import emit_kicad_schematic

HAVE_KICAD = bool(shutil.which("kicad-cli"))


def _t_vs_x_fixture():
    """A: R1.1 -- R2.1 run at y=50.8 with a branch down to R3.1 from its interior
    (same-net T at (35.56, 50.8)). B: R4.2 above to R5.1 below, vertical at
    x=30.48, crossing A's first segment interior at (30.48, 50.8) (foreign X)."""
    comps = [
        EmitComponent(ref="R1", lib_id="Device:R", value="1k", footprint="", x=20.32, y=54.61),
        EmitComponent(ref="R2", lib_id="Device:R", value="1k", footprint="", x=50.8, y=54.61),
        EmitComponent(ref="R3", lib_id="Device:R", value="1k", footprint="", x=35.56, y=59.69),
        EmitComponent(ref="R4", lib_id="Device:R", value="1k", footprint="", x=30.48, y=41.91),
        EmitComponent(ref="R5", lib_id="Device:R", value="1k", footprint="", x=30.48, y=59.69),
    ]
    nets = [EmitNet("NETA", [("R1", "1"), ("R2", "1"), ("R3", "1")]),
            EmitNet("NETB", [("R4", "2"), ("R5", "1")])]
    return comps, nets


@unittest.skipUnless(HAVE_SYMBOLS and HAVE_KICAD,
                     "needs the KiCad symbol library and kicad-cli (named, not silently green)")
class TJunctionVsForeignCrossing(unittest.TestCase):
    def test_split_is_same_net_only(self):
        a = [((20.32, 50.8), (50.8, 50.8)), ((35.56, 50.8), (35.56, 55.88))]
        out = _split_at_contacts(a)
        self.assertIn(((20.32, 50.8), (35.56, 50.8)), out)
        self.assertIn(((35.56, 50.8), (50.8, 50.8)), out)
        # per-net call: net B's vertical never splits net A's run (and vice versa)
        b = _split_at_contacts([((30.48, 45.72), (30.48, 55.88))])
        self.assertEqual(b, [((30.48, 45.72), (30.48, 55.88))])
        self.assertNotIn((30.48, 50.8), {p for s in out for p in s})

    def test_fresh_native_export_has_one_dot_and_no_fusion(self):
        comps, nets = _t_vs_x_fixture()
        geo = resolve_symbol_geometry(comps, SYMBOL_DIR)
        poses = {c.ref: (c.x, c.y) for c in comps}
        tips = {}
        for ref, g in geo.items():
            x, y = poses[ref]
            for pin, (px, py, _r) in g.pins.items():
                tips[(ref, pin)] = (round(x + px, 4), round(y - py, 4))
        self.assertEqual(tips[("R1", "1")], (20.32, 50.8))
        self.assertEqual(tips[("R3", "1")], (35.56, 55.88))
        self.assertEqual(tips[("R4", "2")], (30.48, 45.72))
        self.assertEqual(tips[("R5", "1")], (30.48, 55.88))
        segs = {"NETA": _split_at_contacts([((20.32, 50.8), (50.8, 50.8)),
                                            ((35.56, 50.8), (35.56, 55.88))]),
                "NETB": _split_at_contacts([((30.48, 45.72), (30.48, 55.88))])}
        build = ElkGraphBuild(
            graph={}, ports={}, edge_nets={}, origins={}, drawn_nets=["NETA", "NETB"],
            undrawn={}, declared_pin_nets={(r, p): n.name for n in nets for r, p in n.nodes})
        sol = PresentationSolution(
            poses=poses, segments=segs, junctions={}, label_anchors={},
            drawn_nets=["NETA", "NETB"], undrawn={}, pin_tips=tips)
        from bodesign_eda_bridge.elk_layout import verify_solution as _verify
        report = _verify(sol, build)
        self.assertEqual((report["fused"], report["missing"], report["misrouted"]), ([], [], []))
        self.assertEqual(sol.junctions, {"NETA": [(35.56, 50.8)]})
        with tempfile.TemporaryDirectory(dir=os.environ.get("XDG_RUNTIME_DIR")) as td:
            res = emit_kicad_schematic(td, "tx", comps, nets, symbol_dir=SYMBOL_DIR,
                                       connection_style="wire", power_ports=False,
                                       presentation_solution=sol)
            sch = Path(res.schematic_path)
            text = sch.read_text(encoding="utf-8")
            dots = re.findall(r"\(junction \(at ([-\d.]+) ([-\d.]+)\)", text)
            self.assertEqual([(float(x), float(y)) for x, y in dots], [(35.56, 50.8)])
            # no wire END on the foreign crossing point
            for m in re.finditer(r"\(wire \(pts \(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)", text):
                x1, y1, x2, y2 = map(float, m.groups())
                self.assertNotIn((30.48, 50.8), {(x1, y1), (x2, y2)})
            net = Path(td) / "tx.net"
            subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
                            "-o", str(net), str(sch)], check=True, capture_output=True)
            groups = {}
            body = net.read_text(encoding="utf-8")
            for chunk in re.split(r'\(net \(code "\d+"\) ', body)[1:]:
                nm = re.match(r'\(name "([^"]+)"\)', chunk)
                groups[nm.group(1)] = sorted(re.findall(
                    r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', chunk))
            joined = {tuple(v) for v in groups.values()}
            self.assertIn((("R1", "1"), ("R2", "1"), ("R3", "1")), joined)
            self.assertIn((("R4", "2"), ("R5", "1")), joined)
            self.assertEqual(len([v for v in groups.values() if ("R4", "2") in v and ("R1", "1") in v]), 0)


# --------------------------------------------------------------------------
# Round 3: D1 native-orientation extension. One cell per predeclared transform,
# each round-tripped through a FRESH native kicad-cli netlist export: a wrong
# pin-tip map would leave D1.3 / D1.6 unconnected or joined to the wrong resistor.

from bodesign_eda_bridge.kicad_emit import (
    ORIENTATIONS, orient_pin_angle, orient_point)

D1_LIB = "Power_Protection:PESD5V0L4UF"
HAVE_D1 = HAVE_SYMBOLS and Path(SYMBOL_DIR, "Power_Protection.kicad_sym").is_file()


class OrientationMaps(unittest.TestCase):
    def test_declared_set_is_exactly_four_native_transforms(self):
        self.assertEqual(sorted(ORIENTATIONS), ["MX", "MY", "R0", "R180"])
        self.assertEqual(ORIENTATIONS["R180"], (180, None))
        self.assertEqual(ORIENTATIONS["MX"], (0, "x"))
        self.assertEqual(ORIENTATIONS["MY"], (0, "y"))

    def test_point_and_angle_maps(self):
        self.assertEqual(orient_point("R0", 2.54, -7.62), (2.54, -7.62))
        self.assertEqual(orient_point("R180", 2.54, -7.62), (-2.54, 7.62))
        self.assertEqual(orient_point("MX", 2.54, -7.62), (2.54, 7.62))
        self.assertEqual(orient_point("MY", 2.54, -7.62), (-2.54, -7.62))
        self.assertEqual([orient_pin_angle(o, 0) for o in ("R0", "R180", "MX", "MY")],
                         [0, 180, 0, 180])
        self.assertEqual([orient_pin_angle(o, 90) for o in ("R0", "R180", "MX", "MY")],
                         [90, 270, 270, 90])
        with self.assertRaises(ValueError):
            orient_point("R90", 0, 0)

    def test_orientation_set_validation_is_typed_and_bounded(self):
        comps = _comps()
        bad = [{"R1": ("R0", "R180"), "R2": ("R0", "MX")},          # two refs: no combinations
               {"R1": ("R180", "R0")},                              # identity not first
               {"R1": ("R0", "R180", "MX", "MY", "R0")},            # > 4 / repeat
               {"R1": ("R0", "R90")}]                               # not a native id
        for osets in bad:
            with self.assertRaises(ElkLayoutError) as cm:
                solve_sheet(comps, _nets(), symbol_dir=SYMBOL_DIR, orientation_sets=osets)
            self.assertEqual(cm.exception.code, "E_ELK_ORIENT_SET_INVALID", osets)


@unittest.skipUnless(HAVE_D1 and HAVE_KICAD,
                     "needs the KiCad Power_Protection library and kicad-cli (named, not silently green)")
class OrientationRoundTrip(unittest.TestCase):
    def _case(self, orient):
        comps = [EmitComponent(ref="D1", lib_id=D1_LIB, value="PESD5V0L4UF", footprint="",
                               x=50.8, y=40.64),
                 EmitComponent(ref="R1", lib_id="Device:R", value="1k", footprint="", x=0, y=0),
                 EmitComponent(ref="R2", lib_id="Device:R", value="1k", footprint="", x=0, y=0)]
        orients = {} if orient == "R0" else {"D1": orient}
        geo = resolve_symbol_geometry(comps, SYMBOL_DIR, orientations=orients)
        self.assertEqual(geo["D1"].orientation, orient)
        tips = {}
        for ref, g in geo.items():
            x, y = (comps[0].x, comps[0].y) if ref == "D1" else (0, 0)
        segs = {}
        poses = {"D1": (50.8, 40.64)}
        d1_tip = {p: (round(50.8 + g[0], 4), round(40.64 - g[1], 4)) for p, g in geo["D1"].pins.items()}
        for net, pin, ref in (("NETA", "3", "R1"), ("NETB", "6", "R2")):
            tx, ty = d1_tip[pin]
            dx = -10.16 if geo["D1"].pins[pin][0] < 0 else 10.16
            rx, ry = round(tx + dx, 4), round(ty + 3.81, 4)
            poses[ref] = (rx, ry)
            segs[net] = [((tx, ty), (rx, ty))]
        for c in comps:
            c.x, c.y = poses[c.ref]
        for ref, g in resolve_symbol_geometry(comps, SYMBOL_DIR, orientations=orients).items():
            for pin, (px, py, _r) in g.pins.items():
                tips[(ref, pin)] = (round(poses[ref][0] + px, 4), round(poses[ref][1] - py, 4))
        nets = [EmitNet("NETA", [("D1", "3"), ("R1", "1")]),
                EmitNet("NETB", [("D1", "6"), ("R2", "1")])]
        sol = PresentationSolution(
            poses=poses, segments=segs, junctions={}, label_anchors={},
            drawn_nets=["NETA", "NETB"], undrawn={}, pin_tips=tips, orientations=orients)
        with tempfile.TemporaryDirectory(dir=os.environ.get("XDG_RUNTIME_DIR")) as td:
            res = emit_kicad_schematic(td, "to", comps, nets, symbol_dir=SYMBOL_DIR,
                                       connection_style="wire", power_ports=False,
                                       presentation_solution=sol)
            text = Path(res.schematic_path).read_text(encoding="utf-8")
            rot, mirror = ORIENTATIONS[orient]
            d1 = text[text.index(f'(lib_id "{D1_LIB}")\n    (at'):]
            d1 = d1[:d1.index("(unit")]
            self.assertIn(f"(at {poses['D1'][0]} {poses['D1'][1]} {rot})", d1)
            self.assertEqual("(mirror" in d1, mirror is not None)
            if mirror:
                self.assertIn(f"(mirror {mirror})", d1)
            just = "right" if orient in ("R180", "MY") else "left"
            self.assertIn(f"(justify {just})", text)
            net = Path(td) / "to.net"
            subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
                            "-o", str(net), res.schematic_path], check=True, capture_output=True)
            groups = []
            for chunk in re.split(r'\(net \(code "\d+"\) ', net.read_text(encoding="utf-8"))[1:]:
                groups.append(tuple(sorted(re.findall(
                    r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', chunk))))
            return groups

    def test_each_declared_transform_round_trips_through_native_export(self):
        for orient in ("R0", "R180", "MX", "MY"):
            with self.subTest(orientation=orient):
                groups = self._case(orient)
                self.assertIn((("D1", "3"), ("R1", "1")), groups)
                self.assertIn((("D1", "6"), ("R2", "1")), groups)
                for g in groups:        # no other D1 pin joined to either resistor
                    if ("R1", "1") in g or ("R2", "1") in g:
                        self.assertEqual(len([n for n in g if n[0] == "D1"]), 1, g)


# --------------------------------------------------------------------------
# Round 4: bounded placement models (ELK partitioning). Graph-level, no Node.

from bodesign_eda_bridge.elk_layout import PLACEMENT_MODELS, realized_placement


@unittest.skipUnless(HAVE_SYMBOLS, f"KiCad symbol library not at {SYMBOL_DIR}")
class PlacementModels(unittest.TestCase):
    def test_predeclared_set_is_baseline_plus_two(self):
        self.assertEqual([m["name"] for m in PLACEMENT_MODELS],
                         ["R0", "M1-D1-mid", "M2-R1|D1|R2"])

    def test_partitions_become_elk_options_and_no_coordinates(self):
        geo = resolve_symbol_geometry(_comps(), SYMBOL_DIR)
        b = build_elk_graph(_comps(), _nets(), geo, partitions={"R1": 0, "R2": 1})
        self.assertEqual(b.graph["layoutOptions"]["elk.partitioning.activate"], "true")
        props = {n["id"]: n["properties"] for n in b.graph["children"]}
        self.assertEqual(props["R1"]["elk.partitioning.partition"], "0")
        self.assertEqual(props["R2"]["elk.partitioning.partition"], "1")
        self.assertNotIn("elk.partitioning.partition", props["C1"])   # unconstrained = unmarked
        for n in b.graph["children"]:
            self.assertNotIn("x", n)
            self.assertNotIn("y", n)

    def test_baseline_graph_has_no_partitioning(self):
        geo = resolve_symbol_geometry(_comps(), SYMBOL_DIR)
        b = build_elk_graph(_comps(), _nets(), geo)
        self.assertNotIn("elk.partitioning.activate", b.graph["layoutOptions"])

    def test_partition_for_unknown_ref_is_refused(self):
        geo = resolve_symbol_geometry(_comps(), SYMBOL_DIR)
        with self.assertRaises(ElkLayoutError):
            build_elk_graph(_comps(), _nets(), geo, partitions={"R9": 0})

    @unittest.skipUnless(HAVE_NODE and HAVE_ELK, "needs node + elkjs (named, not silently green)")
    def test_realized_order_is_read_back_from_solved_poses(self):
        model = {"name": "t", "partitions": {"R1": 0, "R2": 1}, "above": ()}
        sol = solve_sheet(_comps(), _nets(), symbol_dir=SYMBOL_DIR,
                          placement_models=(model,),
                          drawn_filter=lambda n: (n.name != "GND", "gnd"),
                          variants=({"name": "default", "root": "first", "options": {}},))
        entry = [e for e in sol.variant_log if e["placement"] == "t"][0]
        self.assertTrue(entry["realized_placement"]["executed"])
        self.assertEqual(sol.placement_model, "t")


# --------------------------------------------------------------------------
# Round 5 / Amendment A: D1 package outline = ONE dashed (rectangle), NO native
# (group) (kicad-cli 9.0.9 rejected 14 group syntaxes at file version 20250114).
# The D1<->rectangle tie is a data-layer ownership record on the solution.

import uuid as _uuid_mod

from bodesign_eda_bridge.elk_layout import plan_node_ink
from bodesign_eda_bridge.kicad_emit import OUTLINE_UUID_RULE_NAME


def _d1_only():
    comps = [EmitComponent(ref="D1", lib_id=D1_LIB, value="PESD5V0L4UF", footprint="",
                           x=102.87, y=78.74)]
    geo = resolve_symbol_geometry(comps, SYMBOL_DIR)
    tips = {(r, p): (round(102.87 + x, 4), round(78.74 - y, 4))
            for r, g in geo.items() for p, (x, y, _a) in g.pins.items()}
    return comps, geo, tips


@unittest.skipUnless(HAVE_SYMBOLS, f"KiCad symbol library not at {SYMBOL_DIR}")
class D1OutlineInkModel(unittest.TestCase):
    def test_outline_is_graphics_bbox_plus_margin_and_extends_hull(self):
        comps, geo, _ = _d1_only()
        g = geo["D1"]
        ink = plan_node_ink(comps[0], g, {}, (10, 30, 5, 25), 1.0, outline=True)
        gx0, gy0, gx1, gy1 = g.gfx
        self.assertEqual(ink.outline, (round(gx0 - 0.254, 4), round(-gy1 - 0.254, 4),
                                       round(gx1 + 0.254, 4), round(-gy0 + 0.254, 4)))
        self.assertLessEqual(ink.hull[0], ink.outline[0])
        self.assertGreaterEqual(ink.hull[3], ink.outline[3])

    def test_no_outline_requested_changes_nothing(self):
        comps, geo, _ = _d1_only()
        ink = plan_node_ink(comps[0], geo["D1"], {}, (10, 30, 5, 25), 1.0)
        self.assertIsNone(ink.outline)

    def test_outline_without_graphics_is_refused_not_invented(self):
        import dataclasses
        comps, geo, _ = _d1_only()
        bare = dataclasses.replace(geo["D1"], gfx=None)
        with self.assertRaises(ElkLayoutError) as cm:
            plan_node_ink(comps[0], bare, {}, (10, 30, 5, 25), 1.0, outline=True)
        self.assertEqual(cm.exception.code, "E_ELK_OUTLINE_NO_GRAPHICS")


@unittest.skipUnless(HAVE_SYMBOLS and HAVE_KICAD,
                     "needs the KiCad symbol library and kicad-cli (named, not silently green)")
class D1OutlineEmit(unittest.TestCase):
    def _emit(self, td):
        comps, geo, tips = _d1_only()
        outline = {"outline": [101.6, 77.47, 104.14, 102.87], "caption": [0, 0, 0, 0],
                   "ref_at": [106.68, 88.9], "val_at": [106.68, 91.44]}
        sol = PresentationSolution(
            poses={"D1": (102.87, 78.74)}, segments={}, junctions={}, label_anchors={},
            drawn_nets=[], undrawn={}, pin_tips=tips, outlines={"D1": outline})
        res = emit_kicad_schematic(td, "tx", comps, [], symbol_dir=SYMBOL_DIR,
                                   connection_style="wire", power_ports=False,
                                   presentation_solution=sol)
        return sol, Path(res.schematic_path)

    def test_exactly_one_rectangle_zero_groups_and_ownership_record(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("XDG_RUNTIME_DIR")) as td:
            sol, sch = self._emit(td)
            text = sch.read_text(encoding="utf-8")
            self.assertEqual(text.count("(group"), 0)
            rects = re.findall(r'\(rectangle \(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\)', text)
            # lib_symbols carry their own (rectangle ..) bodies only for rectangle symbols;
            # D1's lib block has none, so the sheet-level one is the only rectangle.
            self.assertEqual(len(rects), 1)
            self.assertIn("(type dash)", text)
            rec = sol.outlines["D1"]
            m = re.search(r'\(lib_id "%s"\)[\s\S]*?\(uuid "([0-9a-f-]{36})"\)' % re.escape(D1_LIB), text)
            self.assertEqual(rec["symbol_uuid"], m.group(1))
            self.assertEqual(rec["rect_uuid"],
                             str(_uuid_mod.uuid5(_uuid_mod.UUID(m.group(1)), OUTLINE_UUID_RULE_NAME)))
            self.assertIn(rec["rect_uuid"], text)
            self.assertEqual(rec["uuid_rule"],
                             'rect_uuid = uuid5(D1_symbol_uuid, "presentation.outline")')

    def test_fresh_native_export_loads_with_outline(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("XDG_RUNTIME_DIR")) as td:
            _sol, sch = self._emit(td)
            net = Path(td) / "tx.net"
            for fmt, out in (("netlist", net),):
                subprocess.run(["kicad-cli", "sch", "export", fmt, "--format", "kicadsexpr",
                                "-o", str(out), str(sch)], check=True, capture_output=True)
            self.assertIn('(ref "D1")', net.read_text(encoding="utf-8"))
            svgdir = Path(td) / "svg"
            subprocess.run(["kicad-cli", "sch", "export", "svg", "-o", str(svgdir), str(sch)],
                           check=True, capture_output=True)
            self.assertTrue(list(svgdir.glob("*.svg")))
