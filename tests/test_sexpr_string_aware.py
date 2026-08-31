"""BR_20260901f: s-expression scanning must be string-aware.

Three independent copies of a paren-balancing walk existed in eda-bridge and
none tracked quoted strings, so a `(` or `)` inside a KiCad property VALUE
desynchronised the depth counter. The scan then ran past the true block end --
silently, with three different plausible-looking wrong answers.

Every test's docstring first line states the question it answers.
"""
import unittest

from bodesign_eda_bridge.sexpr import balanced_end
from bodesign_eda_bridge import kicad_emit
from bodesign_eda_bridge import fidelity


# A block whose property value contains an unpaired '(' -- the real shape seen in
# KiCad's Isolator.kicad_sym (TLP184xSE's description). TRAILER is deliberately
# more text after the block: a correct scan must stop before it.
BLOCK_OPEN = '(symbol "X" (property "Description" "photocoupler (AC input"))'
BLOCK_CLOSE = '(symbol "X" (property "Description" "photocoupler AC) input"))'
BLOCK_ESCAPED = '(symbol "X" (property "Description" "he said \\"hi(\\" loudly"))'
TRAILER = '(symbol "NEXT" (pin "1"))'


class TestBalancedEndCore(unittest.TestCase):
    def test_unpaired_open_paren_in_string_does_not_extend_the_block(self):
        """Q: does a '(' inside a quoted value inflate the depth counter?"""
        s = BLOCK_OPEN + TRAILER
        self.assertEqual(balanced_end(s, 0), len(BLOCK_OPEN))

    def test_unpaired_close_paren_in_string_does_not_truncate_the_block(self):
        """Q: does a ')' inside a quoted value close the block early?"""
        s = BLOCK_CLOSE + TRAILER
        self.assertEqual(balanced_end(s, 0), len(BLOCK_CLOSE))

    def test_escaped_quote_does_not_end_the_string(self):
        r'''Q: is a \" inside a string treated as text rather than as a closer?'''
        s = BLOCK_ESCAPED + TRAILER
        self.assertEqual(balanced_end(s, 0), len(BLOCK_ESCAPED))

    def test_plain_block_without_any_quoted_paren_still_works(self):
        """Q: control -- does the string-awareness break the ordinary case?"""
        s = '(a (b) (c))' + TRAILER
        self.assertEqual(balanced_end(s, 0), len('(a (b) (c))'))

    def test_unclosed_block_returns_none(self):
        """Q: is 'never closes' reported distinctly rather than as a bogus end?"""
        self.assertIsNone(balanced_end('(a (b)', 0))


class TestWrapperNotFoundContracts(unittest.TestCase):
    """The three wrappers have three DIFFERENT not-found values that their
    existing callers depend on. BR_20260901f fixed the scan, not the contracts;
    these pin the contracts so a later "cleanup" cannot silently unify them."""

    def test_kicad_emit_balanced_block_returns_tail_when_unclosed(self):
        """Q: does kicad_emit._balanced_block still return s[start:] on failure?"""
        self.assertEqual(kicad_emit._balanced_block('(a (b)', 0), '(a (b)')

    def test_fidelity_balanced_block_returns_empty_string_when_unclosed(self):
        """Q: does fidelity._balanced_block still return '' on failure?"""
        self.assertEqual(fidelity._balanced_block('(a (b)', 0), '')

    def test_extract_symbol_block_returns_none_when_marker_absent(self):
        """Q: does a GENUINELY absent symbol still yield None (no false positive)?"""
        self.assertIsNone(kicad_emit._extract_symbol_block(BLOCK_OPEN, 'NOPE'))


class TestExtractSymbolBlockOnQuotedParens(unittest.TestCase):
    def test_symbol_whose_property_holds_an_open_paren_is_found(self):
        """Q: does the 'marker present but parse desynced' false absence recur?"""
        source = BLOCK_OPEN + TRAILER
        got = kicad_emit._extract_symbol_block(source, 'X')
        self.assertEqual(got, BLOCK_OPEN)

    def test_symbol_after_a_quoted_paren_block_is_still_found(self):
        """Q: does a desync in an EARLIER block corrupt a later lookup?"""
        source = BLOCK_OPEN + TRAILER
        got = kicad_emit._extract_symbol_block(source, 'NEXT')
        self.assertEqual(got, TRAILER)

    def test_symbol_children_splits_correctly_across_a_quoted_paren(self):
        """Q: does _symbol_children still return one child per s-expr?"""
        block = ('(symbol "X" (property "D" "a (b") (pin "1") (pin "2"))')
        kids = kicad_emit._symbol_children(block)
        self.assertEqual(kids, ['(property "D" "a (b")', '(pin "1")', '(pin "2")'])


if __name__ == '__main__':
    unittest.main()
