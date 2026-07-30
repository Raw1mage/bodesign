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
            self.assertEqual(nc["per_board"]["PRODUCT"], {"rows": 1, "drawn": 1, "missing": []})
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


if __name__ == "__main__":
    unittest.main()
