"""Unit tests for symbol_resolver (eda_draftsman-v2 task 1.1, IDEF0 A1).

Covers test-vectors TV-1 (real MPN family hit) and TV-2 (fabricated MPN → gap,
no fabricated geometry). Also pins the DD-1 no-fallback invariants that surfaced
during the aiguard C03 coverage run: family-collision guard + placeholder MPN
detection.
"""
import unittest

from bodesign_eda_bridge.symbol_resolver import (
    resolve_mpn,
    resolve_bom,
    _is_placeholder,
)


class TestSymbolResolver(unittest.TestCase):
    def test_tv1_real_mpn_family_hit(self):
        """A concrete MPN whose family exists in the official lib resolves.

        BQ25890 has no exact official symbol but the BQ2589x family does; the
        resolver accepts it only because the symbol name shares a strong prefix.
        """
        rs, gap = resolve_mpn("BQ25890")
        self.assertIsNotNone(rs, f"expected a ResolvedSymbol, got gap={gap}")
        self.assertIsNone(gap)
        self.assertTrue(rs.lib_id.startswith("Battery_Management:BQ2589"))
        self.assertEqual(rs.lib_source, "official")

    def test_tv2_fabricated_mpn_is_gap_no_geometry(self):
        """A fabricated MPN yields a SymbolGap and never fabricates geometry."""
        rs, gap = resolve_mpn("NOSUCHPART-999")
        self.assertIsNone(rs)
        self.assertIsNotNone(gap)
        self.assertEqual(gap.mpn, "NOSUCHPART-999")
        self.assertEqual(gap.disposition, "pending")
        self.assertEqual(gap.cause, "no_official_symbol")

    def test_bom_invariant_generated_geometry_zero(self):
        """resolve_bom must always report generated_geometry == 0 (DD-1)."""
        res = resolve_bom([{"mpn": "NOSUCHPART-999", "ref": "U99"}])
        self.assertEqual(res["generated_geometry"], 0)
        self.assertEqual(len(res["resolved"]), 0)
        self.assertEqual(len(res["gaps"]), 1)

    def test_placeholder_mpn_detected(self):
        """BOM placeholder MPNs are unresolved_mpn gaps, not lib misses."""
        for ph in ["APS512 class (TBC)", "UNDECIDED (deck S8 open item)",
                   "various", "18650 holder", "", "n/a"]:
            self.assertTrue(_is_placeholder(ph), f"should be placeholder: {ph!r}")
        rs, gap = resolve_mpn("MIC5365 (TBC)")
        self.assertIsNone(rs)
        self.assertEqual(gap.cause, "unresolved_mpn")

    def test_family_collision_not_official_mis_resolved(self):
        """STM32N657 must NOT mis-resolve to an STM32C0 official symbol (5-char
        'stm32' collision). Post DD-7 it resolves via vendor CAD instead, so the
        invariant under test is: it never becomes an *official* family match.
        (The bare-official path is exercised by test_family_collision_bare.)"""
        rs, gap = resolve_mpn("STM32N657L0Q3")
        # DD-7: vendor CAD now covers this MPN. The guard we still assert is that
        # it did NOT sneak in as a low-confidence official STM32C0 match.
        if rs is not None:
            self.assertEqual(rs.lib_source, "vendor_cad")
            self.assertFalse(rs.lib_id.startswith("MCU_ST_STM32C0"))
        else:
            self.assertEqual(gap.cause, "low_confidence")

    def test_family_collision_bare_official_rejected(self):
        """A non-vendored STM32N6 MPN must NOT auto-resolve to an STM32C0 symbol
        (5-char 'stm32' collision) — it becomes a low_confidence gap."""
        rs, gap = resolve_mpn("STM32N699Z9Q9")  # fabricated N6, not in vendor map
        self.assertIsNone(rs, f"bare STM32N6 must not auto-resolve, got {rs}")
        self.assertIsNotNone(gap)
        self.assertEqual(gap.cause, "low_confidence")


    def test_dd7_stm32n657_resolves_via_vendor_cad(self):
        """DD-7: STM32N657L0Q3 has no official symbol but a ballout-verified
        vendor CAD symbol; it must resolve with lib_source='vendor_cad'."""
        rs, gap = resolve_mpn("STM32N657L0Q3")
        self.assertIsNotNone(rs, f"expected vendor resolve, got gap={gap}")
        self.assertIsNone(gap)
        self.assertEqual(rs.lib_source, "vendor_cad")
        self.assertEqual(rs.lib_id, "ST_vendor:STM32N657L0H3Q")


if __name__ == "__main__":
    unittest.main()
