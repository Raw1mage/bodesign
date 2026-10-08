"""Synthetic rejecting controls per PP gate; live specimen asserts shape only."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from bodesign_eda_bridge.c03_presentation_gate import (
    C03PresentationInputError, c03_presentation_gate, native_inventory,
)

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "plans/eda-bridge_unified-collaborative-rebuild/data-schema.json"
LIVE = Path("/home/pkcs12/products/bodesign/outputs/btdongle_ms")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PresentationGate(unittest.TestCase):
    def setUp(self):
        scratch = Path.home() / ".cache/scratch/c03-pp-tests"
        scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.d = Path(tempfile.mkdtemp(dir=scratch))
        self.addCleanup(shutil.rmtree, self.d)
        self.net = self.d / "book.net"
        self.plan = self.d / "plan.json"
        self.net.write_text('''(export (design
          (sheet (name "/a/") (title_block (source "a.kicad_sch")))
          (sheet (name "/b/") (title_block (source "b.kicad_sch"))))
          (components (comp (ref "U1") (libsource (lib "local") (part "IC")))
                      (comp (ref "R1") (libsource (lib "Device") (part "R"))))
          (libparts (libpart (lib "local") (part "IC") (pins (pin (num "1")) (pin (num "2")) (pin (num "3"))))
                    (libpart (lib "Device") (part "R") (pins (pin (num "1")) (pin (num "2")))))
          (nets (net (name "SIG") (node (ref "U1") (pin "1")) (node (ref "U1") (pin "3")) (node (ref "R1") (pin "1")))
                (net (name "GND") (node (ref "R1") (pin "2")))
                (net (name "unconnected-U1-2") (node (ref "U1") (pin "2")))))''')
        for page in ("a", "b"):
            resistor = '''(symbol (lib_id "Device:R") (unit 1) (uuid "r-b") (property "Reference" "R1"))''' if page == "b" else ""
            (self.d / f"{page}.kicad_sch").write_text(f'''(kicad_sch
              (lib_symbols (symbol "local:IC" (symbol "IC_1_1"
                (pin passive line (at 0 0 0) (number "1"))
                (pin passive line (at 0 1 0) (number "2"))
                (pin passive line hide (at 0 0 0) (number "3"))))
                (symbol "Device:R" (symbol "R_1_1"
                  (pin passive line (at 0 0 0) (number "1"))
                  (pin passive line (at 0 1 0) (number "2")))))
              (symbol (lib_id "local:IC") (unit 1) (uuid "u-{page}") (property "Reference" "U1")) {resistor})''')
            (self.d / f"{page}-v1.png").write_bytes(b"synthetic image: content outside gate scope")
        art = lambda name: {"path": str(self.d / name), "sha256": sha(self.d / name)}
        occurrence = lambda p, s, dest=None, rel=None: {"pin": p, "state": s, "destination": dest, "relationship_id": rel, "exception_id": None}
        self.m = {"schema_version": "presentation_plan/1.0.0", "revision_id": "synthetic-v1", "status": "DRAFT - not human approval",
                  "baseline_refs": {"netlist": art("book.net"), "legacy_netlist": art("book.net"), "book_pdf": art("a-v1.png"),
                                    "bundle_manifest": art("a-v1.png"), "hashes_root": "0" * 64,
                                    "legacy_sheet_mapping": [{"ref": r, "Sheetname": "old", "Sheetfile": "old.kicad_sch", "sheetpath": "/old/", "home_page": h} for r, h in (("U1", "a"), ("R1", "b"))]},
                  "generator": art("book.net"), "pages": [{"id": p, "role": "home", "order": k + 1, "primary_refs": ["U1"],
                      "native": art(p + ".kicad_sch"), "image": art(p + "-v1.png"), "intent_refs": ["synthetic"]} for k, p in enumerate(("a", "b"))],
                  "home_pages": ["a", "b"], "instance_coverage": [],
                  "local_support": [{"id": "support", "anchor_ref": "U1", "anchor_pins": ["1", "3"], "page": "b", "support_refs": ["R1"], "evidence_ref": "synthetic"}],
                  "interfaces": [], "intent_refs": ["synthetic"], "review_evidence": [], "human_locks": [], "exceptions": [], "evidence_gaps": []}
        for ref, home, vp in (("U1", "a", ["a", "b"]), ("R1", "b", ["b"])):
            lib = "local:IC" if ref == "U1" else "Device:R"
            ni = native_inventory(str(self.d / f"{home}.kicad_sch"), ref, lib)
            pins, views = [], []
            for p, f in ni["pins"].items():
                state = "NC" if ref == "U1" and p == "2" else ("hidden-stacked" if f["hidden"] else "placed")
                pins.append({"pin": p, **f, "state": state, "page": "b" if state != "NC" else home,
                             "net": "unconnected-U1-2" if state == "NC" else ("GND" if ref == "R1" and p == "2" else "SIG")})
            for page in vp:
                vps = [occurrence(p["pin"], "off-page-label", f"b.U1.{p['pin']}", "support")
                       if ref == "U1" and page == "a" and p["state"] != "NC" else occurrence(p["pin"], p["state"]) for p in pins]
                views.append({"page": page, "native_uuid": ("u-" + page) if ref == "U1" else "r-b",
                              "physical_id": "legacy:" + ref, "approval_provenance": "synthetic approved view", "review_ids": [], "pins": vps})
            self.m["instance_coverage"].append({"ref": ref, "physical_id": "legacy:" + ref, "role": "ic" if ref == "U1" else "support",
                                               "home_page": home, "units": ni["units"], "pins": pins, "views": views})
        self.save()

    def save(self):
        self.plan.write_text(json.dumps(self.m))

    def run_gate(self):
        return c03_presentation_gate(str(self.plan), str(SCHEMA), str(self.net), str(self.d))

    def reject(self, gate):
        self.save()
        result = self.run_gate()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["gates"][gate]["status"], "fail", result)
        return result

    def test_accepting_all_five(self):
        self.assertTrue(self.run_gate()["ok"])

    def test_pp01_version(self):
        self.m["schema_version"] = "presentation_plan/2.0.0"
        self.reject("PP-01")

    def test_pp01_missing_required(self):
        del self.m["interfaces"]
        self.reject("PP-01")

    def test_pp01_bool_not_integer(self):
        self.m["pages"][0]["order"] = True
        self.reject("PP-01")

    def test_pp01_unknown_field(self):
        self.m["human_approved"] = True
        self.reject("PP-01")

    def test_pp02_missing_pin(self):
        self.m["instance_coverage"][0]["pins"].pop()
        self.reject("PP-02")

    def test_pp02_duplicate_pin(self):
        self.m["instance_coverage"][0]["pins"].append(copy.deepcopy(self.m["instance_coverage"][0]["pins"][0]))
        self.reject("PP-02")

    def test_pp02_orphan_pin(self):
        self.m["instance_coverage"][0]["pins"][0]["pin"] = "999"
        self.reject("PP-02")

    def test_pp02_view_pin_missing(self):
        self.m["instance_coverage"][0]["views"][0]["pins"].pop()
        self.reject("PP-02")

    def test_pp02_hidden_metadata(self):
        self.m["instance_coverage"][0]["pins"][2]["hidden"] = False
        self.reject("PP-02")

    def test_pp02_wrong_unit(self):
        self.m["instance_coverage"][0]["units"] = [2]
        self.reject("PP-02")

    def test_pp02_wrong_nc(self):
        self.m["instance_coverage"][0]["views"][0]["pins"][1]["state"] = "placed"
        self.reject("PP-02")

    def test_pp02_real_net_wins_over_duplicate_nc(self):
        self.net.write_text(self.net.read_text().replace('(nets ', '(nets (net (name "unconnected-view-U1-1") (node (ref "U1") (pin "1"))) ', 1))
        self.m["baseline_refs"]["netlist"]["sha256"] = sha(self.net)
        self.save()
        self.assertTrue(self.run_gate()["ok"])

    def test_pp02_distinct_real_net_conflict(self):
        self.net.write_text(self.net.read_text().replace('(nets ', '(nets (net (name "OTHER") (node (ref "U1") (pin "1"))) ', 1))
        self.reject("PP-02")

    def test_pp02_missing_net_node_not_empty_pass(self):
        self.net.write_text(self.net.read_text().replace('(node (ref "U1") (pin "2"))', ''))
        self.reject("PP-02")

    def test_pp03_missing_relationship(self):
        self.m["local_support"] = []
        self.reject("PP-03")

    def test_pp03_destination_wrong(self):
        self.m["instance_coverage"][0]["views"][0]["pins"][0]["destination"] = "b.U1.2"
        self.reject("PP-03")

    def test_pp03_local_support_orphan(self):
        self.m["local_support"][0]["support_refs"] = ["R404"]
        self.reject("PP-03")

    def test_pp03_interface_without_named_support(self):
        self.m["interfaces"] = [{"id": "i", "net": "GND", "evidence_ref": "unnamed",
                                 "endpoints": [{"ref": "U1", "pin": "1", "page": "a"},
                                               {"ref": "U1", "pin": "1", "page": "b"}]}]
        self.reject("PP-03")

    def test_pp04_home_set(self):
        self.m["home_pages"] = ["a"]
        self.reject("PP-04")

    def test_pp04_missing_png(self):
        (self.d / "b-v1.png").unlink()
        self.reject("PP-04")

    def test_pp04_stale_native(self):
        self.m["pages"][0]["native"]["sha256"] = "f" * 64
        self.reject("PP-04")

    def test_pp05_no_approval(self):
        self.m["human_locks"] = [{"id": "l", "target": "U1", "justification": "fixture", "approval": None}]
        self.reject("PP-05")

    def test_pp05_unknown_target(self):
        self.m["exceptions"] = [{"id": "x", "target": "U404", "justification": "fixture", "approval": {"actor": "human", "source": "synthetic", "decision": "approved"}}]
        self.reject("PP-05")

    def test_pp05_rejected_approval(self):
        self.m["exceptions"] = [{"id": "x", "target": "U1", "justification": "fixture", "approval": {"actor": "human", "source": "synthetic", "decision": "rejected"}}]
        self.reject("PP-05")

    def test_approved_exception_not_issued_by_gate(self):
        target = "a.U1.1"
        self.m["exceptions"] = [{"id": "x", "target": target, "justification": "synthetic waiver", "approval": {"actor": "human", "source": "synthetic", "decision": "approved"}}]
        pin = self.m["instance_coverage"][0]["views"][0]["pins"][0]
        pin.update(exception_id="x", relationship_id=None, destination=None)
        self.save()
        before = self.plan.read_bytes()
        self.assertTrue(self.run_gate()["ok"])
        self.assertEqual(self.plan.read_bytes(), before)

    def test_unresolved_library_fails_fast(self):
        (self.d / "a.kicad_sch").write_text('(kicad_sch (lib_symbols))')
        with self.assertRaisesRegex(C03PresentationInputError, "inventory unmeasured"):
            self.run_gate()

    def test_schema_unsupported_keyword_refuses(self):
        schema = json.loads(SCHEMA.read_text())["presentation_plan"]
        schema["anyOf"] = []
        path = self.d / "schema.json"
        path.write_text(json.dumps(schema))
        with self.assertRaisesRegex(C03PresentationInputError, "unsupported keywords"):
            c03_presentation_gate(str(self.plan), str(path), str(self.net), str(self.d))

    def test_readonly_all_artifact_bytes(self):
        before = {p: p.read_bytes() for p in self.d.iterdir()}
        self.run_gate()
        self.assertEqual({p: p.read_bytes() for p in self.d.iterdir()}, before)


class LiveShape(unittest.TestCase):
    @unittest.skipUnless((LIVE / "c03_presentation_plan-v1.json").is_file(), "live specimen unavailable")
    def test_shape_only(self):
        result = c03_presentation_gate(str(LIVE / "c03_presentation_plan-v1.json"), str(SCHEMA),
                                      str(LIVE / ".src/book_modules-v2.net"), "/home/pkcs12/products/bodesign/btdongle_ms")
        self.assertEqual(set(result["gates"]), {f"PP-0{i}" for i in range(1, 6)})
        self.assertIsInstance(result["ok"], bool)
        self.assertTrue(result["not_checked"])
