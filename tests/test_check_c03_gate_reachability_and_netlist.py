"""BR_20260730 — C03 gate reachability (F1), BOM<->netlist (F2/R5), pin-spec
polarity (R6), and the two gate-internal defects found while verifying the BR
(R3 column-absent false-red, '#' comment rows misdiagnosed as quoting breakage).

Every positive assertion here has a paired REVERSE-DISCRIMINATION test: undo the
fix and the test must go red. A check that stays green with the fix removed has no
discriminating power and would let CI report a false pass — the very failure mode
this BR family exists to eliminate.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from bodesign_workflow_core import check_c03

_PKG_DIR = Path(__file__).parent.parent / "packages" / "workflow-core"
_MOD_DIR = _PKG_DIR / "bodesign_workflow_core"


# ── fixtures ────────────────────────────────────────────────────────────────

_NETLIST = """\
(export (version "E")
  (design (source "/work/probe/probe.kicad_sch"))
  (components
    (comp (ref "J_LED") (value "FPC 4P"))
    (comp (ref "J_MIC") (value "FPC 4P"))
    (comp (ref "U1") (value "SoC")))
  (nets
    (net (code "1") (name "K_R") (class "Default")
      (node (ref "J_LED") (pin "1") (pintype "passive")))
    (net (code "2") (name "K_G") (class "Default")
      (node (ref "J_LED") (pin "2") (pintype "passive")))
    (net (code "3") (name "K_B") (class "Default")
      (node (ref "J_LED") (pin "3") (pintype "passive")))
    (net (code "4") (name "+3V3_PB") (class "Default")
      (node (ref "J_LED") (pin "4") (pintype "passive")))
    (net (code "5") (name "PDM_CLK") (class "Default")
      (node (ref "J_MIC") (pin "1") (pintype "passive")))
    (net (code "6") (name "PDM_DATA0") (class "Default")
      (node (ref "J_MIC") (pin "2") (pintype "passive")))
    (net (code "7") (name "+1V8") (class "Default")
      (node (ref "J_MIC") (pin "3") (pintype "passive")))
    (net (code "8") (name "GND") (class "Default")
      (node (ref "J_MIC") (pin "4") (pintype "passive")))
    (net (code "9") (name "SYS") (class "Default")
      (node (ref "U1") (pin "A1") (pintype "power_in")))))
"""

_HDR = "board,ref,value,mpn,qty,status,deck_status\n"


def _write(tmp: str, name: str, body: str) -> str:
    p = os.path.join(tmp, name)
    Path(p).write_text(body, encoding="utf-8")
    return p


def _bom(tmp: str, rows: list[str], name: str = "bom.csv") -> str:
    return _write(tmp, name, _HDR + "".join(r if r.endswith("\n") else r + "\n" for r in rows))


def _net(tmp: str) -> str:
    return _write(tmp, "probe.net", _NETLIST)


def _codes(result) -> list[str]:
    return [f.code for f in result.blocking]


# ── F1: the pure-python gate must be importable without ee-only packages ────

class ReachabilityTests(unittest.TestCase):
    """§3 — a zero-dependency CSV gate must not inherit pcbnew-side deps via the
    package __init__. This is what drove the consumer to hand-write a rival gate."""

    def _clean_child(self, code: str) -> subprocess.CompletedProcess:
        """Run `code` in a child whose sys.path has ONLY workflow-core, so no other
        bodesign_* package is importable. Reproduces a consumer repo exactly."""
        env = dict(os.environ)
        env["PYTHONPATH"] = str(_PKG_DIR)
        return subprocess.run([sys.executable, "-c", code], capture_output=True,
                              text=True, env=env, cwd=tempfile.gettempdir())

    def test_check_c03_imports_without_design_ir(self):
        r = self._clean_child(
            "from bodesign_workflow_core import check_c03; print('OK', check_c03.__name__)")
        self.assertEqual(r.returncode, 0,
                         f"pure gate not reachable without ee deps:\n{r.stderr[-1500:]}")
        self.assertIn("OK", r.stdout)

    def test_lazy_export_still_resolves_when_deps_present(self):
        """Deferring resolution must not remove the symbols for callers that DO have
        the ee packages — otherwise F1 trades one breakage for another."""
        pp = os.pathsep.join(str(p) for p in sorted(
            (Path(__file__).parent.parent / "packages").glob("*/")))
        env = dict(os.environ, PYTHONPATH=pp)
        r = subprocess.run(
            [sys.executable, "-c",
             "from bodesign_workflow_core import CheckerError, guard_tier, PackageReadiness;"
             "print('OK')"],
            capture_output=True, text=True, env=env, cwd=tempfile.gettempdir())
        self.assertEqual(r.returncode, 0, f"lazy exports broke:\n{r.stderr[-1200:]}")

    def test_unknown_attribute_still_raises_attribute_error(self):
        """Lazy resolution must not swallow genuine typos into a silent None."""
        r = self._clean_child(textwrap.dedent("""
            import bodesign_workflow_core as m
            try:
                m.definitely_not_a_symbol
            except AttributeError:
                print('OK')
        """))
        self.assertIn("OK", r.stdout, r.stderr[-800:])

    def test_no_third_eager_offender_appears(self):
        """REVERSE DISCRIMINATION for the lazy-export map.

        The map in __init__ is a hand-written list, i.e. exactly the kind of copy
        that drifts (BR_20260729 V4-c). Re-derive the audit from source: every
        submodule eagerly imported by __init__ must not import an external
        bodesign_* package at module level. A third offender appearing later fails
        here instead of silently re-breaking consumer reachability.
        """
        init_src = (_MOD_DIR / "__init__.py").read_text(encoding="utf-8")
        eager = set(re.findall(r"^from \.(\w+) import", init_src, re.M))
        self.assertIn("check_c03", eager, "sanity: __init__ should eagerly export the pure gate")

        offenders: dict[str, list[str]] = {}
        for mod in sorted(eager):
            f = _MOD_DIR / f"{mod}.py"
            if not f.is_file():
                continue
            src = f.read_text(encoding="utf-8")
            deps = sorted(set(
                re.findall(r"^from (bodesign_(?!workflow_core)\w+)", src, re.M)
                + re.findall(r"^import (bodesign_(?!workflow_core)\w+)", src, re.M)))
            if deps:
                offenders[mod] = deps
        self.assertEqual(
            offenders, {},
            "these submodules are eagerly imported by __init__ but need an external "
            f"bodesign_* package, re-breaking consumer reachability: {offenders}. "
            "Move their exports into _LAZY_EXTERNAL_DEP_EXPORTS.")

    def test_audit_would_catch_an_offender(self):
        """The audit above must actually be able to fail (guard against a walk that
        silently finds nothing)."""
        src = "from bodesign_design_ir import NET_ROLES\n"
        deps = re.findall(r"^from (bodesign_(?!workflow_core)\w+)", src, re.M)
        self.assertEqual(deps, ["bodesign_design_ir"],
                         "the offender-detection regex no longer matches a known offender")


# ── F3: design-ready is an admitted lifecycle state ─────────────────────────

class DesignReadyStatusTests(unittest.TestCase):
    """§2 — two gates returned opposite verdicts on the same BOM because one knew
    'design-ready' and the other did not."""

    def test_design_ready_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["CORE,U1,SoC,STM32N657,1,design-ready,symbol=official"])
            res = check_c03(b)
            self.assertNotIn("R1_SCHEMA", _codes(res),
                             "design-ready must be a known status (F3 adjudication)")
            self.assertNotIn("R2_READINESS", _codes(res),
                             "design-ready clears the C04-entry readiness bar")

    def test_design_ready_may_carry_a_generic_mpn(self):
        """The deferred-mpn allowance IS the difference from `finalized`; penalising
        it would leave the state with no reason to exist."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["PRODUCT,J_LED,FPC 4P,TBD 型號後定,1,design-ready,symbol=official"])
            self.assertNotIn("R2_READINESS", _codes(check_c03(b)))

    def test_finalized_still_rejects_a_placeholder_mpn(self):
        """REVERSE: the placeholder rule must remain live for `finalized`, else F3
        would have quietly disabled a real check."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["PRODUCT,J_LED,FPC 4P,TBD,1,finalized,symbol=official"])
            self.assertIn("R2_READINESS", _codes(check_c03(b)))

    def test_genuinely_unknown_status_still_blocks(self):
        """REVERSE: admitting design-ready must not have opened the enum."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["CORE,U1,SoC,X,1,almost-ready,symbol=official"])
            self.assertIn("R1_SCHEMA", _codes(check_c03(b)))


# ── N1/N2: the two gate-internal defects ────────────────────────────────────

class GateInternalDefectTests(unittest.TestCase):

    def test_deck_status_is_recognised_as_the_symbol_column(self):
        """N1 — `deck_status` is the column every product BOM and the c03-ee GUIDE
        actually use. Not recognising it made EVERY row fail R3: a gate that fails
        all rows has the same discriminating power as one that passes all rows."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, [
                "CORE,U1,SoC,X,1,finalized,symbol=official Device:R",
                "CORE,U2,PMIC,Y,1,finalized,C12345",
            ])
            self.assertNotIn("R3_DRAWABILITY", _codes(check_c03(b)))

    def test_missing_symbol_column_is_one_schema_finding_not_n_row_findings(self):
        """N1 — 'I could not find the column' must not be reported as 'the column is
        empty' for each of N rows (mcpctl busy-probe UNKNOWN lesson)."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _write(tmp, "nosym.csv",
                       "board,ref,value,mpn,qty,status\n"
                       "CORE,U1,SoC,X,1,finalized\n"
                       "CORE,U2,PMIC,Y,1,finalized\n"
                       "CORE,U3,LDO,Z,1,finalized\n")
            res = check_c03(b)
            r3 = [f for f in res.blocking if f.code == "R3_DRAWABILITY"]
            self.assertEqual(len(r3), 1, f"expected ONE schema-level finding, got {len(r3)}")
            self.assertEqual(r3[0].ref, "<schema>")
            self.assertIn("no symbol-source column found", r3[0].detail)

    def test_row_missing_a_marker_still_blocks(self):
        """REVERSE for N1: recognising more column names must not stop the check
        from firing on a row that genuinely declares nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["CORE,U1,SoC,X,1,finalized,deck-confirmed only"])
            self.assertIn("R3_DRAWABILITY", _codes(check_c03(b)))

    def test_declared_but_unrecognised_origin_is_reported_distinctly(self):
        """A row whose deck_status HAS `symbol=` but names an origin class we do not
        know must not be told 'no symbol source marker' — that sends the caller
        looking for a field which is in fact present. Still blocking."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["PRODUCT,DS1,OLED,X,1,design-ready,symbol=模組接口 自定義 header"])
            res = check_c03(b)
            r3 = [f for f in res.blocking if f.code == "R3_DRAWABILITY"]
            self.assertEqual(len(r3), 1)
            self.assertIn("origin class is unrecognised", r3[0].detail)
            self.assertEqual(res.gate, "FAIL", "vocabulary is not widened to let it pass")

    def test_comment_banner_rows_are_not_quoting_breakage(self):
        """N2 — '#' section banners are a documented BOM convention. Reporting each
        as R1_SCHEMA 'likely CSV quoting breakage' pointed the caller at a quoting
        bug that does not exist (28 such misdiagnoses on the real aiguard BOM)."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _write(tmp, "commented.csv",
                       _HDR
                       + "# ==== CORE STAMP MODULE ====\n"
                       + "CORE,U1,SoC,X,1,finalized,symbol=official\n"
                       + "# ==== PRODUCT BOARD ====\n"
                       + "PRODUCT,U9,PMIC,Y,1,finalized,symbol=official\n")
            res = check_c03(b)
            self.assertEqual(_codes(res), [], f"unexpected findings: {[(f.ref, f.detail) for f in res.blocking]}")
            self.assertEqual(res.bom_rows, 2, "comment rows must not count as BOM rows")

    def test_real_column_count_breakage_still_blocks(self):
        """REVERSE for N2: skipping comments must not blind R1 to genuine damage."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _write(tmp, "broken.csv",
                       _HDR + "CORE,U1,SoC\n")
            self.assertIn("R1_SCHEMA", _codes(check_c03(b)))


# ── R4: SSOT crosscheck applicability ───────────────────────────────────────

class SsotApplicabilityTests(unittest.TestCase):
    """N1's twin, found by the consumer at round=4. `_load_pin_alloc_refs` returned
    an empty set both when a ref column was absent and when it was empty, so every
    active BOM part looked missing from the SSOT — 26/26 on the real inputs, each
    worded as "BOM<->SSOT conflict — owner must reconcile", which reads like 26 real
    conflicts awaiting adjudication rather than one unreadable input.

    Contract note: the c03-ee GUIDE deliverable table (:43/:340/:374) defines
    Pin_Allocation.csv as a ball->GPIO->function pinmap, which has no ref column by
    design; only the §3c prose assumes a ref list. All four Pin_Allocation.csv files
    in the fleet follow the deliverable table, so "no ref column" is the CONFORMING
    case and must not be a finding."""

    _PINMAP = ("peripheral,function,interface,net_group,rail,ball_assignment\n"
               "SAI1,PDM_CLK,PDM,MIC,+1V8,PA4\n")
    _REFMAP = "ref,peripheral,function\nU1,SAI1,PDM_CLK\n"

    def test_ball_oriented_pinmap_reports_not_run_not_n_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, [
                "CORE,U1,SoC,X,1,finalized,symbol=official",
                "PRODUCT,J_LED,FPC 4P,generic,1,design-ready,symbol=official",
                "PRODUCT,U9,PMIC,Y,1,finalized,symbol=official",
            ])
            pin = _write(tmp, "Pin_Allocation.csv", self._PINMAP)
            res = check_c03(b, pin_allocation_csv=pin)
            self.assertNotIn("R4_SSOT", _codes(res),
                             "an inapplicable crosscheck must not become findings")
            self.assertEqual(res.ssot_crosscheck["status"], "not_run")
            self.assertFalse(res.ssot_checked, "ssot_checked must stay False when nothing was checked")
            self.assertIn("no ref-bearing column", res.ssot_crosscheck["reason"])
            self.assertEqual(sorted(res.ssot_crosscheck["active_parts_unverified"]),
                             ["J_LED", "U1", "U9"],
                             "the parts that were NOT verified must be named, not hidden")

    def test_ref_bearing_pinmap_still_crosschecks(self):
        """REVERSE: reporting not_run for one schema must not disable R4 entirely."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, [
                "CORE,U1,SoC,X,1,finalized,symbol=official",
                "CORE,U4A,Radio,Y,1,finalized,symbol=official",
            ])
            pin = _write(tmp, "Pin_Allocation.csv", self._REFMAP)
            res = check_c03(b, pin_allocation_csv=pin)
            self.assertTrue(res.ssot_checked)
            self.assertEqual(res.ssot_crosscheck["status"], "run")
            r4 = [f.ref for f in res.blocking if f.code == "R4_SSOT"]
            self.assertEqual(r4, ["U4A"], "U4A is genuinely absent from the ref pinmap")

    def test_no_pin_allocation_supplied_is_also_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["CORE,U1,SoC,X,1,finalized,symbol=official"])
            res = check_c03(b)
            self.assertEqual(res.ssot_crosscheck["status"], "not_run")
            self.assertIn("not supplied", res.ssot_crosscheck["reason"])


# ── R3: bare LCSC part number is vendor-fetchable evidence ──────────────────

class LcscEvidenceTests(unittest.TestCase):
    """A third vocabulary divergence with the consumer gate (check_bom.py R4 has
    always accepted a bare LCSC id). Accepting it is stricter than the bare literal
    "lcsc" already allowed — an id resolves, the word does not."""

    def test_bare_lcsc_id_counts_as_symbol_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["CORE,U2,PMIC,BQ25890,1,finalized,deck-confirmed C165948"])
            self.assertNotIn("R3_DRAWABILITY", _codes(check_c03(b)))

    def test_short_numeric_is_not_mistaken_for_a_part_number(self):
        """REVERSE: the id pattern must not be so loose that a value like C1 or a
        4-digit code silently satisfies the evidence requirement."""
        with tempfile.TemporaryDirectory() as tmp:
            for evidence in ("deck-confirmed C1", "class 6-8 C123", "pin C12"):
                b = _bom(tmp, [f"CORE,U3,LDO,Z,1,finalized,{evidence}"], name="short.csv")
                self.assertIn("R3_DRAWABILITY", _codes(check_c03(b)),
                              f"{evidence!r} must not pass as an LCSC id")


# ── F2 / R5: BOM <-> netlist ────────────────────────────────────────────────

class NetlistCrosscheckTests(unittest.TestCase):

    def test_bom_row_absent_from_netlist_blocks(self):
        """THE BR's ACCEPTANCE CRITERION: a BOM row declaring a part that was never
        drawn must not reach C04."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, [
                "PRODUCT,J_LED,FPC 4P 1.0mm,generic,1,design-ready,symbol=official",
                "PRODUCT,J_NOPE,Phantom connector,generic,1,design-ready,symbol=official",
            ])
            res = check_c03(b, netlist_path=_net(tmp))
            r5 = {f.ref for f in res.blocking if f.code == "R5_NETLIST"}
            self.assertEqual(r5, {"J_NOPE"})
            self.assertEqual(res.gate, "FAIL")

    def test_not_run_is_explicit_when_no_netlist_supplied(self):
        """A verdict must carry the scope that produced it: PASS with no netlist must
        never read as 'every part is drawn'."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["CORE,U1,SoC,X,1,finalized,symbol=official"])
            res = check_c03(b)
            self.assertEqual(res.gate, "PASS")
            self.assertEqual(res.netlist_crosscheck["status"], "not_run")
            self.assertIn("NOT checked", res.netlist_crosscheck["reason"])
            self.assertEqual(res.pin_polarity["status"], "not_run")

    def test_exemptions_are_reported_not_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, [
                "PRODUCT,C*/R*,Passives,generic,TBD,design-ready,symbol=official",
                "MIC_MODULE,MIC1_ALT,Alternate,generic,0,alternate,symbol=official",
                "CAM_MODULE,LENS,M12 lens,generic,1,design-ready,N/A",
            ])
            res = check_c03(b, netlist_path=_net(tmp))
            ex = res.netlist_crosscheck["exempted"]
            self.assertEqual(ex["aggregate"], ["C*/R*"])
            self.assertEqual(ex["qty_zero"], ["MIC1_ALT"])
            self.assertEqual(ex["non_electrical"], ["LENS"])
            self.assertNotIn("R5_NETLIST", _codes(res))

    def test_reverse_direction_is_a_counted_warning_never_a_blocker(self):
        """A netlist may legitimately cover more than one BOM's scope. Measured on
        the real inputs a symmetric difference gave 33 findings of which 2 were real;
        a gate that cries wolf 31 times gets ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["PRODUCT,J_LED,FPC 4P,generic,1,design-ready,symbol=official"])
            res = check_c03(b, netlist_path=_net(tmp))
            self.assertNotIn("R5_NETLIST", _codes(res))
            self.assertTrue(any("no BOM row" in w for w in res.warnings),
                            f"orphan netlist refs must still be surfaced: {res.warnings}")

    def test_per_board_coverage_separates_uncaptured_boards(self):
        """A flat list of missing refs hides the one distinction that changes the
        fix: 'this board has no schematic at all' vs 'this part is missing'."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, [
                "PRODUCT,J_LED,FPC 4P,generic,1,design-ready,symbol=official",
                "DEV,J3,Debug hdr,generic,1,design-ready,symbol=official",
                "DEV,J_BRK,Breakout,generic,1,design-ready,symbol=official",
            ])
            nc = check_c03(b, netlist_path=_net(tmp)).netlist_crosscheck
            self.assertEqual(nc["boards_not_captured"], ["DEV"])
            self.assertEqual(nc["per_board"]["PRODUCT"],
                             {"rows": 1, "drawn": 1, "drawn_as_other_refdes": 0,
                              "missing": []})
            self.assertEqual(nc["per_board"]["DEV"]["drawn"], 0)

    def test_named_but_absent_netlist_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["CORE,U1,SoC,X,1,finalized,symbol=official"])
            with self.assertRaises(ValueError) as cm:
                check_c03(b, netlist_path=os.path.join(tmp, "nope.net"))
            self.assertIn("NETLIST_MISSING", str(cm.exception))

    def test_scope_of_each_netlist_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["CORE,U1,SoC,X,1,finalized,symbol=official"])
            nc = check_c03(b, netlist_path=[_net(tmp)]).netlist_crosscheck
            self.assertEqual(nc["netlist_scopes"], ["probe.kicad_sch"])


# ── R6: pin-spec polarity ───────────────────────────────────────────────────

class PinPolarityTests(unittest.TestCase):
    """BR round=2: a BOM pin spec of "(R/G/B/GND)" against a common-ANODE LED had
    pin 4 wired to GND. Electrically legal -> ERC/DRC green -> LED can never light."""

    _BUGGY = 'PRODUCT,J_LED,"FPC 4P 1.0mm(R/G/B/GND)",generic,1,design-ready,symbol=official'
    _FIXED = ('PRODUCT,J_LED,"FPC 4P 1.0mm(K_R/K_G/K_B/+3V3 common-anode)",'
              'generic,1,design-ready,symbol=official')

    def test_ground_where_the_netlist_has_supply_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = check_c03(_bom(tmp, [self._BUGGY]), netlist_path=_net(tmp))
            r6 = [f for f in res.blocking if f.code == "R6_PIN_POLARITY"]
            self.assertEqual(len(r6), 1, f"expected the GND/supply inversion: {res.blocking}")
            self.assertEqual(r6[0].ref, "J_LED")
            self.assertIn("pin 4", r6[0].detail)
            self.assertIn("ERC/DRC cannot catch", r6[0].detail)

    def test_the_corrected_spec_passes(self):
        """REVERSE DISCRIMINATION, and the reason token-exact matching was rejected:
        the corrected spec '+3V3 common-anode' does NOT string-equal its net
        '+3V3_PB'. A check that flags the right answer is worse than no check."""
        with tempfile.TemporaryDirectory() as tmp:
            res = check_c03(_bom(tmp, [self._FIXED]), netlist_path=_net(tmp))
            self.assertNotIn("R6_PIN_POLARITY", _codes(res))

    def test_a_correct_spec_with_different_wording_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = ('PRODUCT,J_MIC,"FPC 4P 0.5mm(CLK/DATA0/VDD/GND)",'
                   'generic,1,design-ready,symbol=official')
            res = check_c03(_bom(tmp, [row]), netlist_path=_net(tmp))
            self.assertNotIn("R6_PIN_POLARITY", _codes(res),
                             "VDD vs +1V8 and GND vs GND are both consistent")

    def test_supply_where_the_netlist_has_ground_also_blocks(self):
        """The check must be symmetric — the inversion is wrong in either direction."""
        with tempfile.TemporaryDirectory() as tmp:
            row = ('PRODUCT,J_MIC,"FPC 4P(CLK/DATA0/VDD/+3V3)",'
                   'generic,1,design-ready,symbol=official')
            res = check_c03(_bom(tmp, [row]), netlist_path=_net(tmp))
            r6 = [f for f in res.blocking if f.code == "R6_PIN_POLARITY"]
            self.assertEqual(len(r6), 1)
            self.assertIn("pin 4", r6[0].detail)

    def test_unaligned_token_count_is_reported_not_guessed(self):
        """When the spec's token count does not match the ref's pin count the
        positional assumption is unknown. Report it; do not guess an offset and emit
        findings from a wrong premise."""
        with tempfile.TemporaryDirectory() as tmp:
            row = ('PRODUCT,J_LED,"FPC 6P(R/G/B/GND/NC/NC)",'
                   'generic,1,design-ready,symbol=official')
            res = check_c03(_bom(tmp, [row]), netlist_path=_net(tmp))
            self.assertNotIn("R6_PIN_POLARITY", _codes(res))
            un = res.pin_polarity["unaligned"]
            self.assertEqual(len(un), 1)
            self.assertEqual(un[0], {"ref": "J_LED", "spec_tokens": 6, "netlist_pins": 4})

    def test_refs_checked_is_reported_so_a_vacuous_run_is_visible(self):
        """A 'run' that examined nothing must be distinguishable from a clean run —
        otherwise R6 becomes a check with no discriminating power reporting success."""
        with tempfile.TemporaryDirectory() as tmp:
            b = _bom(tmp, ["CORE,U1,SoC,X,1,finalized,symbol=official"])
            pol = check_c03(b, netlist_path=_net(tmp)).pin_polarity
            self.assertEqual(pol["status"], "run")
            self.assertEqual(pol["refs_checked"], [], "U1 has no parenthesised pin spec")
            self.assertEqual(pol["rows_without_pin_spec"], 1)

    def test_row_absent_from_netlist_is_r5_not_r6(self):
        """R6 must not pile a second finding onto a part R5 already reported."""
        with tempfile.TemporaryDirectory() as tmp:
            row = ('PRODUCT,J_GHOST,"FPC 4P(R/G/B/GND)",'
                   'generic,1,design-ready,symbol=official')
            res = check_c03(_bom(tmp, [row]), netlist_path=_net(tmp))
            self.assertIn("R5_NETLIST", _codes(res))
            self.assertNotIn("R6_PIN_POLARITY", _codes(res))


# ── source-level guard: R5/R6 must stay wired ───────────────────────────────

class WiringGuardTests(unittest.TestCase):
    """REVERSE DISCRIMINATION at the wiring layer. The behavioural tests above all
    pass a netlist; if a future edit dropped the R5/R6 call sites entirely those
    tests would fail loudly — but a subtler edit that stops APPENDING the findings
    would not. Assert the call sites exist and their results are folded in."""

    def test_check_c03_calls_both_netlist_checks_and_uses_their_findings(self):
        src = (_MOD_DIR / "check_c03.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == "check_c03")
        body = ast.dump(fn)
        for helper in ("_check_netlist", "_check_pin_polarity"):
            self.assertIn(helper, body, f"check_c03 no longer calls {helper}")
        # both results must be accumulated into `findings`
        aug = [n for n in ast.walk(fn)
               if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name)
               and n.target.id == "findings"]
        self.assertGreaterEqual(len(aug), 4,
                                "findings no longer accumulates every rule's output")

    def test_netlist_path_is_a_keyword_parameter(self):
        src = (_MOD_DIR / "check_c03.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.parse(src).body
                  if isinstance(n, ast.FunctionDef) and n.name == "check_c03")
        self.assertIn("netlist_path", [a.arg for a in fn.args.kwonlyargs])


_SERVER_PY = Path(__file__).parent.parent / "services" / "mcp" / "server.py"


class FacadeReachabilityTests(unittest.TestCase):
    """Every check_c03 parameter must be reachable THROUGH THE MCP FACADE.

    §3 of this BR is about a gate that cannot execute where the caller stands. That
    defect recurred one layer over, in the code fixing it: F2 added `netlist_path`
    (R5) and R6 to the function, and round=8 added `covers_boards`, but neither was
    added to the facade's inputSchema or forwarded by `_h_check_c03`. So R5/R6 were
    UNREACHABLE for every MCP caller — they silently received
    netlist_crosscheck.status='not_run' and could read a PASS as "every part is
    drawn". The behavioural tests above all call the Python function directly, so
    they were green throughout; only a caller going through the facade would have
    noticed, and the reporter happened to be invoking the function directly.

    Derived from check_c03's own signature rather than a hand-written list of
    parameter names, because such a list is the V4-c duplicate-fact shape: it is a
    copy of the signature and would drift from it exactly as _EE_GROUP_TOOLS did
    (twice). A new parameter added tomorrow fails this test until it is exposed.
    """

    def _params(self) -> list[str]:
        src = (_MOD_DIR / "check_c03.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.parse(src).body
                  if isinstance(n, ast.FunctionDef) and n.name == "check_c03")
        return [a.arg for a in fn.args.args] + [a.arg for a in fn.args.kwonlyargs]

    def _facade(self) -> tuple[str, str]:
        """(schema_properties_fragment, handler_source) for bodesign_check_c03."""
        src = _SERVER_PY.read_text(encoding="utf-8")
        i = src.find('"name": "bodesign_check_c03"')
        self.assertNotEqual(i, -1, "bodesign_check_c03 is not registered in server.py")
        entry = src[i:i + 6000]
        m = re.search(r'"schema":\s*\{"type": "object", "properties": \{(.*?)\},\s*"required"',
                      entry, re.S)
        self.assertIsNotNone(m, "could not locate the tool's schema properties")
        h_start = src.find("def _h_check_c03")
        self.assertNotEqual(h_start, -1, "_h_check_c03 handler not found")
        h_end = src.find("\ndef ", h_start + 1)
        return m.group(1), src[h_start:h_end]

    def test_the_signature_scan_actually_finds_parameters(self):
        # Reverse discrimination for the scan itself: if the AST walk returned an
        # empty list, every assertion below would pass vacuously forever — the
        # zero-discriminating-power failure this BR family exists to eliminate.
        params = self._params()
        self.assertIn("bom_csv", params)
        self.assertIn("netlist_path", params)
        self.assertGreaterEqual(len(params), 5, f"suspiciously few params: {params}")

    def test_every_parameter_is_declared_in_the_facade_schema(self):
        props, _ = self._facade()
        missing = [p for p in self._params() if f'"{p}"' not in props]
        self.assertEqual(
            missing, [],
            f"check_c03 accepts {missing} but the MCP inputSchema does not declare "
            f"them — an MCP caller cannot discover or pass them, so those rules are "
            f"unreachable through the facade (BR_20260730 §3, one layer over). The "
            f"inputSchema is the ONLY documentation an MCP caller sees at call time.",
        )

    def test_every_parameter_is_forwarded_by_the_handler(self):
        # A schema entry with no forwarding is worse than an absent one: the caller
        # passes the argument, the call succeeds, and the argument is discarded.
        _, handler = self._facade()
        missing = [p for p in self._params() if p not in handler]
        self.assertEqual(
            missing, [],
            f"_h_check_c03 does not forward {missing} — a caller passing them would "
            f"get a successful call in which the argument was silently dropped",
        )

    def test_the_schema_says_what_omitting_netlist_path_costs(self):
        # Declaring the parameter is not enough: a caller who does not know that
        # omitting it SKIPS R5/R6 will read gate=PASS as "every part is drawn".
        props, _ = self._facade()
        m = re.search(r'"netlist_path":.*?"description":\s*"(.*?[^\\])"', props, re.S)
        self.assertIsNotNone(m, "netlist_path carries no description")
        desc = m.group(1)
        self.assertIn("not_run", desc,
                      "the description must name the status a caller gets without it")
        self.assertIn("R5", desc)


# ── round=8: a multi-board BOM must not be permanently red ───────────────

_MULTIBOARD_HDR = "board,ref,value,mpn,qty,status,deck_status\n"

# Two netlists' worth of coverage in one file: PRODUCT is fully captured, CORE is
# captured but has a part drawn under a different refdes, and the *_MODULE boards
# are not covered at all (their schematics do not exist yet).
_MULTIBOARD_NET = """\
(export (version "E")
  (design (source "/work/probe/product.kicad_sch"))
  (components
    (comp (ref "J_MIC") (value "FPC 4P"))
    (comp (ref "U1") (value "SoC"))
    (comp (ref "UW1") (value "nRF7002 WiFi") (footprint "QFN:nRF7002-QFAA-R")))
  (nets
    (net (code "1") (name "SYS") (class "Default")
      (node (ref "U1") (pin "A1") (pintype "power_in")))))
"""


def _mb_bom(tmp: str, rows: list[str]) -> str:
    return _write(tmp, "mb.csv", _MULTIBOARD_HDR + "".join(r + "\n" for r in rows))


def _mb_net(tmp: str) -> str:
    return _write(tmp, "mb.net", _MULTIBOARD_NET)


_MB_ROWS = [
    'PRODUCT,U1,SoC,STM32N657,1,finalized,symbol=official',
    'PRODUCT,J_MIC,"FPC 4P(PDM_CLK/PDM_DATA/3V3/GND)",generic,1,design-ready,symbol=official',
    'CORE,U4A,Wi-Fi companion,nRF7002-QFAA-R,1,finalized,symbol=official',
    'MIC_MODULE,MIC1,PDM mic,MP23DB01HP,1,design-ready,symbol=official',
    'LED_MODULE,D1,RGB LED,XL-1615RGBC,1,design-ready,symbol=official',
]


class MultiBoardCoverageTests(unittest.TestCase):
    """round=8 — R5 must not cry wolf over boards no netlist covers.

    A product BOM spans every board; one netlist covers ONE schematic. On the real
    aiguard inputs R5 reported 11 blocking rows of which 0 were actionable, because
    5 boards (the external modules) have no schematic yet. A gate that is
    permanently red teaches its reader to skip it — and then the one real J_MIC gap
    goes unseen too. Same rule as consumer_fork_drift's forks_unassessable: a gap in
    the REFERENCE is not a defect in the thing being checked.
    """

    def _run(self, tmp: str, rows: list[str] | None = None, **kw):
        return check_c03(_mb_bom(tmp, rows or _MB_ROWS),
                         netlist_path=_mb_net(tmp), **kw)

    def test_rows_on_an_uncovered_board_are_not_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = self._run(tmp)
            refs = [f.ref for f in res.blocking]
            self.assertNotIn("MIC1", refs, "MIC_MODULE has no netlist — nothing to compare against")
            self.assertNotIn("D1", refs, "LED_MODULE has no netlist — nothing to compare against")

    def test_they_are_reported_rather_than_dropped(self):
        # "Not assessed" must never be indistinguishable from "assessed, clean".
        with tempfile.TemporaryDirectory() as tmp:
            nc = self._run(tmp).netlist_crosscheck
            un = nc["rows_unassessable_board_not_captured"]
            self.assertEqual(sorted(un), ["LED_MODULE", "MIC_MODULE"])
            self.assertEqual(un["MIC_MODULE"], ["MIC1"])

    def test_a_real_gap_on_a_COVERED_board_still_blocks(self):
        # THE reverse-discrimination test. If the demotion were written as "missing
        # => unassessable", every real omission would vanish with the noise.
        rows = _MB_ROWS + ['PRODUCT,J_GHOST,"FPC 4P",generic,1,design-ready,symbol=official']
        with tempfile.TemporaryDirectory() as tmp:
            res = self._run(tmp, rows)
            self.assertIn("J_GHOST", [f.ref for f in res.blocking],
                          "PRODUCT IS covered, so an undrawn part there is a real gap")
            self.assertEqual(res.gate, "FAIL")

    def test_the_report_states_how_coverage_was_decided(self):
        with tempfile.TemporaryDirectory() as tmp:
            nc = self._run(tmp).netlist_crosscheck
            self.assertEqual(nc["board_coverage_basis"], "inferred_from_drawn_refs")
            self.assertIn("PRODUCT", nc["boards_covered"])

    def test_covers_boards_makes_coverage_authoritative(self):
        # Inference cannot tell "no netlist covers this board" from "every row on it
        # is undrawn"; the caller can. Declaring it must override the guess.
        #
        # §Q narrowed what a declaration can do: it may only WIDEN the assessable
        # set (make a zero-sighting board assessable), never SHRINK it below what
        # was observed. So the discriminating case is a board with NO sighting at
        # all — LED_MODULE. Declaring it covered turns its rows into real gaps;
        # omitting it leaves them unassessable.
        #
        # (A CORE row cannot serve here any more: CORE is observed via U4A -> UW1,
        # so under §Q it stays assessable whatever the declaration says. That is
        # tested directly in DeclaredCoverageMustNotOutrankObservationTests.)
        with tempfile.TemporaryDirectory() as tmp:
            declared = self._run(tmp, covers_boards=["PRODUCT", "CORE", "LED_MODULE"])
            self.assertEqual(declared.netlist_crosscheck["board_coverage_basis"],
                             "declared")
            self.assertIn("D1", [f.ref for f in declared.blocking],
                          "LED_MODULE declared covered -> its undrawn part is a real gap")

        with tempfile.TemporaryDirectory() as tmp:
            omitted = self._run(tmp, covers_boards=["PRODUCT", "CORE"])
            nc = omitted.netlist_crosscheck
            self.assertNotIn("D1", [f.ref for f in omitted.blocking])
            self.assertIn("D1",
                          nc["rows_unassessable_board_not_captured"].get("LED_MODULE", []),
                          "LED_MODULE not declared and drawn nowhere -> no baseline")

    def test_positive_mpn_evidence_outranks_declared_coverage(self):
        # A part whose mpn IS in a netlist is drawn, whatever the declared scope says.
        # Absence of coverage is absence of EVIDENCE; an mpn hit is evidence. Letting
        # the exemption win would hide a real BOM/schematic disagreement behind a
        # scope declaration.
        with tempfile.TemporaryDirectory() as tmp:
            res = self._run(tmp, covers_boards=["PRODUCT"])
            codes = {f.ref: f.code for f in res.blocking}
            self.assertEqual(codes.get("U4A"), "R5_REFDES_DIVERGENCE",
                             "U4A is drawn as UW1; a scope declaration must not erase that")

    def test_a_typo_in_covers_boards_is_reported(self):
        # Otherwise a misspelt board name silently exempts nothing while looking
        # accepted — the caller would believe they had scoped the check.
        with tempfile.TemporaryDirectory() as tmp:
            nc = self._run(tmp, covers_boards=["PRODUKT"]).netlist_crosscheck
            self.assertEqual(nc["boards_declared_not_in_bom"], ["PRODUKT"])

    def test_a_netlist_matching_NOTHING_exempts_nothing(self):
        # A demotion rule that can silence itself is a false-green generator: pass
        # an unrelated netlist and the whole BOM would be "out of scope", gate PASS.
        with tempfile.TemporaryDirectory() as tmp:
            unrelated = _write(tmp, "other.net",
                              '(export (version "E")\n  (components\n'
                              '    (comp (ref "ZZ99") (value "nothing"))))\n')
            res = check_c03(_mb_bom(tmp, _MB_ROWS), netlist_path=unrelated)
            nc = res.netlist_crosscheck
            self.assertFalse(nc["exemptions_granted"],
                             "a comparison that resolves no board is BROKEN, not out of scope")
            self.assertEqual(res.gate, "FAIL")
            self.assertEqual(nc["rows_unassessable_board_not_captured"], {})


class RefdesDivergenceTests(unittest.TestCase):
    """round=8 — "drawn under another name" is not "never drawn".

    The reporter asserted all 11 findings were parts correctly absent from the
    netlists. Two were not: the BOM's U4A/U4B (nRF7002-QFAA-R / MDBT53-P1M) ARE
    drawn, as UW1/UB1, and those refdes appear in no BOM row. R5's message said
    "never drawn", which is what made a real BOM/schematic disagreement read as
    by-design — the finding was right and its wording sent the reader away.
    """

    def test_a_part_drawn_under_another_refdes_is_classified_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = check_c03(_mb_bom(tmp, _MB_ROWS), netlist_path=_mb_net(tmp))
            codes = {f.ref: f.code for f in res.blocking}
            self.assertEqual(codes.get("U4A"), "R5_REFDES_DIVERGENCE",
                             "U4A's mpn is drawn as UW1 — the part exists")

    def test_the_finding_names_the_refdes_it_was_found_under(self):
        # "Missing" sends the reader to draw it again; naming UW1 sends them to
        # reconcile the two documents, which is the actual fix.
        with tempfile.TemporaryDirectory() as tmp:
            res = check_c03(_mb_bom(tmp, _MB_ROWS), netlist_path=_mb_net(tmp))
            detail = next(f.detail for f in res.blocking if f.ref == "U4A")
            self.assertIn("UW1", detail)
            self.assertIn("mpn", detail)
            self.assertNotIn("never drawn", detail)

    def test_divergences_are_also_structured_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            nc = check_c03(_mb_bom(tmp, _MB_ROWS),
                           netlist_path=_mb_net(tmp)).netlist_crosscheck
            div = {d["bom_ref"]: d["netlist_ref"] for d in nc["refdes_divergences"]}
            self.assertEqual(div.get("U4A"), "UW1")

    def test_a_genuinely_undrawn_part_is_still_plain_R5(self):
        # Reverse discrimination: if everything became a divergence, a real omission
        # would be reported as "go rename something", which is worse than silence.
        rows = _MB_ROWS + ['PRODUCT,U7,unique regulator,TPS62826XYZ,1,finalized,symbol=official']
        with tempfile.TemporaryDirectory() as tmp:
            res = check_c03(_mb_bom(tmp, rows), netlist_path=_mb_net(tmp))
            codes = {f.ref: f.code for f in res.blocking}
            self.assertEqual(codes.get("U7"), "R5_NETLIST")

    def test_a_too_short_or_placeholder_mpn_never_claims_a_divergence(self):
        # Matching on "C" or "TBD" would hit everything; a FALSE divergence claim is
        # worse than a missed one because it asserts a part exists when it may not.
        rows = [
            'PRODUCT,U1,SoC,STM32N657,1,finalized,symbol=official',
            'PRODUCT,U8,mystery,TBD,1,design-ready,symbol=official',
            'PRODUCT,U9,tiny,X1,1,design-ready,symbol=official',
        ]
        with tempfile.TemporaryDirectory() as tmp:
            res = check_c03(_mb_bom(tmp, rows), netlist_path=_mb_net(tmp))
            codes = {f.ref: f.code for f in res.blocking}
            self.assertEqual(codes.get("U8"), "R5_NETLIST", "placeholder mpn must not match")
            self.assertEqual(codes.get("U9"), "R5_NETLIST", "2-char mpn is not evidence")


class DeclaredCoverageMustNotOutrankObservationTests(unittest.TestCase):
    """§Q — `covers_boards` must never become a mute button.

    round=8 made a DECLARED scope authoritative, which handed the caller a way to
    turn the gate green: narrow covers_boards to one board and every undrawn row on
    the others moves into rows_unassessable. Measured on the real inputs,
    covers_boards=['PRODUCT'] produced gate=PASS blocking=0 while CORE was sitting
    in that very netlist at drawn=2.

    That inverts the ordering rule this module already applies one level down (an
    mpn hit is checked BEFORE the board exemption): positive evidence outranks
    absence of evidence, and `drawn > 0` is positive evidence. So a board the
    netlists were OBSERVED to draw stays assessable no matter what the declaration
    says, and the disagreement is reported instead of silently resolved.
    """

    # PRODUCT fully drawn; CORE drawn=1 of 2 -> CORE is observably captured while
    # still having a genuinely undrawn row. Declaring only PRODUCT must not exempt it.
    _ROWS = [
        'PRODUCT,U1,SoC,STM32N657,1,finalized,symbol=official',
        'CORE,U4A,Wi-Fi companion,nRF7002-QFAA-R,1,finalized,symbol=official',
        'CORE,U7X,unique reg,TPS999888XYZ,1,finalized,symbol=official',
    ]

    def _run(self, tmp: str, **kw):
        return check_c03(_mb_bom(tmp, self._ROWS), netlist_path=_mb_net(tmp), **kw)

    def test_an_observed_board_is_not_exempt_even_when_undeclared(self):
        # THE §Q test. Without the fix this row lands in rows_unassessable and the
        # gate goes PASS.
        with tempfile.TemporaryDirectory() as tmp:
            res = self._run(tmp, covers_boards=["PRODUCT"])
            self.assertIn("U7X", [f.ref for f in res.blocking],
                          "CORE is drawn in this netlist; declaring it away must not "
                          "exempt its undrawn rows")
            self.assertEqual(res.gate, "FAIL")
            self.assertEqual(
                res.netlist_crosscheck["rows_unassessable_board_not_captured"], {},
                "nothing here lacks a baseline")

    def test_the_contradiction_itself_is_reported(self):
        # Resolving it silently in EITHER direction hides a fact a human must judge:
        # either the declaration is stale, or those refs belong to another board.
        with tempfile.TemporaryDirectory() as tmp:
            nc = self._run(tmp, covers_boards=["PRODUCT"]).netlist_crosscheck
            conflicts = {c["board"]: c for c in nc["board_coverage_conflicts"]}
            self.assertIn("CORE", conflicts)
            c = conflicts["CORE"]
            # CORE is observed through a DIVERGED refdes here (U4A drawn as UW1),
            # which is the real aiguard shape — so the conflict must count both
            # kinds of sighting, not just refdes-literal ones.
            self.assertGreater(c["observed_drawn"] + c["observed_drawn_as_other_refdes"], 0)
            self.assertEqual(nc["board_coverage_basis"], "declared_with_observed_conflict",
                             "the basis must show the declaration was not taken at face value")

    def test_a_truly_uncovered_board_is_still_exempt(self):
        # Reverse discrimination for the §Q fix: if it were written as "declarations
        # never exempt anything", round=8's whole point would be undone and a
        # multi-board BOM would go permanently red again.
        rows = self._ROWS + ['LED_MODULE,D1,RGB LED,XL-1615RGBC,1,design-ready,symbol=official']
        with tempfile.TemporaryDirectory() as tmp:
            res = check_c03(_mb_bom(tmp, rows), netlist_path=_mb_net(tmp),
                            covers_boards=["PRODUCT", "CORE"])
            nc = res.netlist_crosscheck
            self.assertNotIn("D1", [f.ref for f in res.blocking],
                             "LED_MODULE is drawn nowhere — no baseline, still exempt")
            self.assertIn("D1", nc["rows_unassessable_board_not_captured"].get("LED_MODULE", []))

    def test_no_conflict_is_reported_when_declaration_matches_observation(self):
        # The conflict list must not cry wolf on the normal case.
        with tempfile.TemporaryDirectory() as tmp:
            nc = self._run(tmp, covers_boards=["PRODUCT", "CORE"]).netlist_crosscheck
            self.assertEqual(nc["board_coverage_conflicts"], [])
            self.assertEqual(nc["board_coverage_basis"], "declared")


class ArrayArgumentsMustNotBeDeclaredAsUnionsTests(unittest.TestCase):
    """§P — a union declaration is itself the stringify trigger.

    N1 was diagnosed as "symbol_dirs had no declared type, so the client serialised
    the array to text". The repair declared anyOf[array, string] — and the client
    stringifies THAT too. Proven by an A/B inside ONE request: `covers_boards`
    ({type: array}) arrived as a real list while `netlist_path` (anyOf) arrived as
    '["a.net","b.net"]' and died on NETLIST_MISSING.

    So the loud typed error from N1 was unobeyable: it demanded a real array from a
    caller whose transport could not send one. A single-value call could dodge it
    with a bare string; a multi-value call had no route at all.

    Rule: schema declares the ARRAY only; the runtime stays wider and still accepts
    a bare string. The schema may be narrower than the runtime, never a union of
    both. Pure static shape-checking cannot catch this — an anyOf looks perfectly
    legal — so this guard encodes the transport fact the A/B established.
    """

    def _tool_entry(self, name: str) -> str:
        src = _SERVER_PY.read_text(encoding="utf-8")
        i = src.find(f'"name": "{name}"')
        self.assertNotEqual(i, -1, f"{name} is not registered in server.py")
        return src[i:i + 6000]

    def _prop(self, tool: str, prop: str) -> dict:
        entry = self._tool_entry(tool)
        m = re.search(rf'"{prop}":\s*(\{{.*?\}}),\n', entry, re.S)
        self.assertIsNotNone(m, f"{tool}.{prop} schema shape not found")
        return ast.literal_eval(m.group(1).replace("_STR", '{"type": "string"}'))

    def test_netlist_path_declares_a_plain_array(self):
        node = self._prop("bodesign_check_c03", "netlist_path")
        self.assertEqual(node.get("type"), "array")
        self.assertNotIn("anyOf", node)
        self.assertEqual(node.get("items"), {"type": "string"})

    def test_symbol_dirs_declares_a_plain_array(self):
        node = self._prop("bodesign_compose_schematic", "symbol_dirs")
        self.assertEqual(node.get("type"), "array")
        self.assertNotIn("anyOf", node)

    def test_no_array_argument_anywhere_is_declared_as_a_union(self):
        # Derived from the file rather than a hand-listed pair: the two known
        # offenders were found one at a time, and a third added tomorrow would
        # reproduce the defect silently. Any union CONTAINING an array is suspect,
        # because that is precisely the shape that fails to transport.
        src = _SERVER_PY.read_text(encoding="utf-8")
        offenders = []
        for m in re.finditer(r'"(\w+)":\s*\{"anyOf":\s*\[(.*?)\]', src, re.S):
            if '"type": "array"' in m.group(2):
                offenders.append(m.group(1))
        self.assertEqual(
            offenders, [],
            f"{offenders} declare an array inside a union. An MCP client serialises "
            f"such an argument to TEXT, so a multi-value call cannot be made at all "
            f"while the schema claims it can (BR_20260730b §P). Declare the array "
            f"alone and keep accepting a bare string at runtime.",
        )

    def test_the_scan_would_catch_a_reintroduced_union(self):
        # Reverse discrimination for the scan itself: a regex that matched nothing
        # would keep this suite green forever after the defect returned.
        sample = '"foo": {"anyOf": [{"type": "array", "items": _STR}, _STR],'
        found = [m.group(1) for m in re.finditer(r'"(\w+)":\s*\{"anyOf":\s*\[(.*?)\]', sample, re.S)
                 if '"type": "array"' in m.group(2)]
        self.assertEqual(found, ["foo"])

    def test_the_runtime_still_accepts_a_bare_string(self):
        # The schema narrowing must not break single-value callers: the runtime is
        # deliberately WIDER than the declaration.
        with tempfile.TemporaryDirectory() as tmp:
            res = check_c03(_mb_bom(tmp, _MB_ROWS), netlist_path=_mb_net(tmp))
            self.assertEqual(res.netlist_crosscheck["status"], "run")

    def test_the_runtime_accepts_a_real_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = check_c03(_mb_bom(tmp, _MB_ROWS), netlist_path=[_mb_net(tmp)])
            self.assertEqual(res.netlist_crosscheck["status"], "run")

    def test_the_schema_description_records_why_the_union_was_removed(self):
        # Without the reason, the next reader sees a schema NARROWER than the
        # runtime, calls it a bug, and re-adds the union.
        for tool, prop in (("bodesign_check_c03", "netlist_path"),
                           ("bodesign_compose_schematic", "symbol_dirs")):
            desc = self._prop(tool, prop).get("description", "")
            self.assertIn("BR_20260730b", desc, f"{tool}.{prop} loses its provenance")
            self.assertIn("runtime", desc,
                          f"{tool}.{prop} must say a bare string still works")


if __name__ == "__main__":
    unittest.main()
