import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import compose_schematic, export_bom, export_netlist

SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
HAS_SYMBOLS = (SYMBOL_DIR / "Device.kicad_sym").exists()
HAS_CLI = shutil.which("kicad-cli") is not None
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

SPEC = {
    "components": [
        {"ref": "R1", "symbol": "Device:R", "value": "10k", "footprint": "Resistor_SMD:R_0402_1005Metric"},
        {"ref": "R2", "symbol": "Device:R", "value": "10k", "footprint": "Resistor_SMD:R_0402_1005Metric"},
        {"ref": "C1", "symbol": "Device:C", "value": "100nF", "footprint": "Capacitor_SMD:C_0402_1005Metric"},
    ],
    "nets": [{"name": "MID", "nodes": ["R1.2", "R2.1", "C1.1"]}, {"name": "GND", "nodes": ["R2.2", "C1.2"]}],
}


@unittest.skipUnless(HAS_SYMBOLS and HAS_CLI, "KiCad symbols / kicad-cli not available")
class BomExportTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-bom-", dir=PRIVATE_BASE))
        self.sch = compose_schematic(self.work, "bom_demo", SPEC, symbol_dirs=SYMBOL_DIR).emit.schematic_path

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_export_bom_groups_by_value(self):
        result = export_bom(self.sch, self.work, group_by="Value")
        self.assertEqual("ok", result.status)
        self.assertTrue(Path(result.csv_path).exists())
        self.assertEqual(2, result.line_count)  # 10k (R1,R2) + 100nF (C1)
        text = Path(result.csv_path).read_text()
        self.assertIn('"R1,R2"', text)  # grouped refs
        self.assertIn('"2"', text)      # quantity
        self.assertIn("MPN", text)      # MPN column present

    def test_export_netlist(self):
        result = export_netlist(self.sch, self.work)
        self.assertEqual("ok", result.status)
        self.assertTrue(Path(result.netlist_path).exists())

    def test_missing_schematic_fails_cleanly(self):
        result = export_bom(self.work / "nope.kicad_sch", self.work)
        self.assertEqual("failed", result.status)
        self.assertTrue(result.warnings)

    # ── BR_20260730c: the filters that silently shrink a BOM ────────────────

    def test_a_clean_schematic_reports_an_empty_audit_that_actually_ran(self):
        # THE case that matters most in practice. The reporting fleet encodes
        # "do not populate" as a BOM qty=0 row, NOT as a schematic dnp property,
        # so on their real inputs every casualty list is empty — and empty is the
        # CORRECT answer. It must still be distinguishable from "nobody looked",
        # which is exactly what exclusion_audit carries.
        result = export_bom(self.sch, self.work)
        self.assertEqual("run", result.exclusion_audit)
        self.assertEqual([], result.excluded_dnp)
        self.assertEqual([], result.excluded_from_bom)
        self.assertTrue(result.exclude_dnp, "the rule in force must be echoed, not assumed")
        self.assertFalse([w for w in result.warnings if "omitted" in w],
                         "nothing was excluded, so nothing should be reported as excluded")


_FILTERED_SPEC = {
    "components": [
        {"ref": "R1", "symbol": "Device:R", "value": "10k", "footprint": "Resistor_SMD:R_0402_1005Metric"},
        # Same VALUE as R1 on purpose: grouping would fold these two into one row.
        {"ref": "R3", "symbol": "Device:R", "value": "10k", "footprint": "Resistor_SMD:R_0402_1005Metric"},
        {"ref": "R9", "symbol": "Device:R", "value": "47k", "footprint": "Resistor_SMD:R_0402_1005Metric"},
        {"ref": "C1", "symbol": "Device:C", "value": "100nF", "footprint": "Capacitor_SMD:C_0402_1005Metric"},
    ],
    "nets": [{"name": "MID", "nodes": ["R1.2", "R3.1", "C1.1"]},
             {"name": "GND", "nodes": ["R3.2", "C1.2", "R9.2"]}],
}


@unittest.skipUnless(HAS_SYMBOLS and HAS_CLI, "KiCad symbols / kicad-cli not available")
class BomExclusionAuditTests(unittest.TestCase):
    """BR_20260730c — a BOM is the (schematic, filter-rules) pair.

    `line_count` counts what SURVIVED the filters, so on its own it cannot tell
    "this board has 42 parts" from "47 parts, 5 filtered out". The downstream
    reader is purchasing: a part omitted here is a part never ordered, while its
    footprint still sits on the board.

    TWO rules drop symbols and only one was ever documented: --exclude-dnp
    (opt-out, default on) and 'Exclude from BOM' (dropped unless
    --include-excluded-from-bom is passed, i.e. opt-IN, so the default omits them).
    """

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-bomx-", dir=PRIVATE_BASE))
        sch = compose_schematic(self.work, "filtered", _FILTERED_SPEC,
                                symbol_dirs=SYMBOL_DIR).emit.schematic_path
        self.sch = Path(sch)
        # The composer always emits (dnp no)/(in_bom yes); flip the two flags on
        # disk so this fixture exercises real kicad-cli filtering.
        text = self.sch.read_text(encoding="utf-8")
        blocks = text.split("  (symbol\n")
        out = [blocks[0]]
        for b in blocks[1:]:
            if '"Reference" "R3"' in b:
                b = b.replace("(dnp no)", "(dnp yes)", 1)
            if '"Reference" "R9"' in b:
                b = b.replace("(in_bom yes)", "(in_bom no)", 1)
            out.append(b)
        self.sch.write_text("  (symbol\n".join(out), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_the_fixture_really_is_filtered_by_kicad_cli(self):
        # Reverse discrimination for the FIXTURE: if the on-disk flag edit silently
        # stopped working, every assertion below would pass vacuously.
        result = export_bom(self.sch, self.work / "probe")
        csv_text = Path(result.csv_path).read_text(encoding="utf-8")
        self.assertNotIn("R3", csv_text, "R3 is DNP; it must not reach the shipped BOM")
        self.assertNotIn("R9", csv_text, "R9 is Exclude-from-BOM; likewise")

    def test_both_filters_name_the_parts_they_removed(self):
        result = export_bom(self.sch, self.work / "a")
        self.assertEqual("run", result.exclusion_audit)
        self.assertEqual(["R3"], result.excluded_dnp)
        self.assertEqual(["R9"], result.excluded_from_bom,
                         "the undocumented second filter must be reported too")

    def test_the_rules_in_force_are_echoed(self):
        # §J: a verdict must carry the budget that produced it. Here the 'budget'
        # is the filter set, and the caller may not have passed it explicitly.
        result = export_bom(self.sch, self.work / "b")
        self.assertIs(True, result.exclude_dnp)
        self.assertIs(False, result.include_excluded_from_bom)

    def test_a_dropped_part_is_surfaced_in_warnings_next_to_the_count(self):
        result = export_bom(self.sch, self.work / "c")
        omitted = [w for w in result.warnings if "omitted" in w]
        self.assertTrue(omitted, "a reader who only skims warnings must still see it")
        self.assertIn("R3", omitted[0])
        self.assertIn(str(result.line_count), omitted[0])

    def test_disabling_a_filter_empties_its_list_rather_than_overclaiming(self):
        # REVERSE DISCRIMINATION. An implementation that always reports every DNP
        # part would pass the positive tests while telling a caller who asked to
        # KEEP those parts that they were dropped.
        result = export_bom(self.sch, self.work / "d", exclude_dnp=False)
        self.assertEqual([], result.excluded_dnp, "nothing was excluded by this rule")
        self.assertEqual(["R9"], result.excluded_from_bom, "the other rule still applies")
        self.assertIn("R3", Path(result.csv_path).read_text(encoding="utf-8"))

    def test_opting_into_excluded_from_bom_grows_the_bom(self):
        base = export_bom(self.sch, self.work / "e")
        opted = export_bom(self.sch, self.work / "f", include_excluded_from_bom=True)
        self.assertEqual(base.line_count + 1, opted.line_count)
        self.assertEqual([], opted.excluded_from_bom)
        self.assertEqual(["R3"], opted.excluded_dnp)

    def test_the_audit_is_ungrouped_so_a_group_mate_is_not_falsely_accused(self):
        # The reason the audit costs a second kicad-cli pass. Grouped, R1 (normal)
        # and R3 (DNP) collapse into one row '"R1,R3","10k","2","DNP"' and the flag
        # covers BOTH. Auditing off the grouped export would report R1 — a part
        # that WAS shipped — as excluded, sending someone to order a part twice.
        result = export_bom(self.sch, self.work / "g", group_by="Value")
        self.assertNotIn("R1", result.excluded_dnp,
                         "R1 shipped; sharing a value with a DNP part must not indict it")
        self.assertIn("R1", Path(result.csv_path).read_text(encoding="utf-8"))

    def test_an_unrunnable_audit_is_never_reported_as_a_clean_one(self):
        # The whole point of exclusion_audit. If the second pass fails, empty lists
        # would read as "nothing was excluded" — a false all-clear handed to
        # purchasing. It must say it did not look.
        import bodesign_eda_bridge.bom_export as mod
        original = mod._audit_exclusions
        mod._audit_exclusions = lambda *a, **k: ([], [], "failed:probe")
        try:
            result = export_bom(self.sch, self.work / "h")
        finally:
            mod._audit_exclusions = original
        self.assertTrue(result.exclusion_audit.startswith("failed:"))
        self.assertTrue([w for w in result.warnings if "UNKNOWN" in w],
                        "an unrun audit must be loud, not an empty list")

    def test_power_symbols_never_enter_the_casualty_list(self):
        # Every schematic this emitter produces carries #PWR/#FLG symbols, and they
        # are all in_bom=no — by nature, not by anyone's decision. This fixture has
        # four of them against one real R9. If they reached excluded_from_bom, a
        # real board's list would be dozens of power flags with the one genuinely
        # omitted part buried inside: a casualty list nobody reads is the cry-wolf
        # failure this BR family exists to prevent.
        #
        # Measured on kicad-cli 9.0.9: power symbols are filtered BEFORE the
        # exclude-from-BOM stage, so they never appear even with
        # --include-excluded-from-bom. This test pins that behaviour — if a future
        # kicad-cli stops doing it, the list silently degrades and we must know.
        result = export_bom(self.sch, self.work / "pwr")
        polluters = [r for r in result.excluded_from_bom if r.startswith("#")]
        self.assertEqual([], polluters,
                         f"power/flag symbols leaked into the casualty list: {polluters}")
        self.assertEqual(["R9"], result.excluded_from_bom)

    def test_the_audit_leaves_no_stray_file_beside_the_deliverable(self):
        out = self.work / "i"
        export_bom(self.sch, out)
        strays = [p.name for p in out.iterdir() if "audit" in p.name]
        self.assertEqual([], strays, "the audit pass is an implementation detail")


if __name__ == "__main__":
    unittest.main()
