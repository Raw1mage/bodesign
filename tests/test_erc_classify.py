import unittest

from bodesign_eda_bridge import ErcClassification, classify_erc_report

# pin_not_connected block shape is verbatim real kicad-cli 9.0.9 output
# (experiments/e2e-led-driver/C03-EE/e2e-led-driver.erc.rpt).
PIN_NC_REPORT = """ERC report (2026-07-03T05:03:12+0000, Encoding UTF8)
Report includes: Errors, Warnings

***** Sheet /
[pin_not_connected]: Pin not connected
    ; error
    @(350.52 mm, 116.84 mm): Symbol J1 Pin A7 [D-, Bidirectional, Line]
[pin_not_connected]: Pin not connected
    ; error
    @(350.52 mm, 121.92 mm): Symbol J1 Pin A6 [D+, Bidirectional, Line]

 ** ERC messages: 2  Errors 2  Warnings 0
"""

# short/pad-net-bug shapes are ASSUMPTIONS grounded in
# concept.no-connect-classification (two named nets => real short; empty second
# net / single net => pad-net bug). No real kicad-cli short fixture existed to
# verify wording; the classifier keys on the semantic net-count signature.
REAL_SHORT_REPORT = """ERC report
***** Sheet /
[net_conflict]: Two nets connected
    ; error
    @(10.0 mm, 10.0 mm): nets VBUS and GND
"""

PAD_NET_BUG_REPORT = """ERC report
***** Sheet /
[net_conflict]: Net-less pad touched by trace
    ; error
    @(10.0 mm, 10.0 mm): nets VBUS and )
"""

OTHER_REPORT = """ERC report
***** Sheet /
[endpoint_off_grid]: Symbol pin off grid
    ; warning
    @(10.0 mm, 10.0 mm): Symbol U1 Pin 3
"""


class ClassifyErcReportTests(unittest.TestCase):
    def test_real_short_two_named_nets(self):
        c = classify_erc_report(REAL_SHORT_REPORT)
        self.assertEqual(1, c.real_short_count)
        self.assertEqual(0, c.pad_net_bug_count)
        self.assertIn("VBUS and GND", c.real_shorts[0])
        self.assertEqual(1, c.blocking_count)

    def test_pad_net_bug_empty_second_net(self):
        c = classify_erc_report(PAD_NET_BUG_REPORT)
        self.assertEqual(1, c.pad_net_bug_count)
        self.assertEqual(0, c.real_short_count)
        self.assertEqual(1, c.blocking_count)

    def test_pin_not_connected_declared_is_intentional_nc(self):
        c = classify_erc_report(PIN_NC_REPORT, declared_nc=["J1.A7", "J1.A6"])
        self.assertEqual(2, c.intentional_nc_count)
        self.assertEqual(0, c.unconnected_count)
        # intentional NC is INFO, must NOT count as blocking.
        self.assertEqual(0, c.blocking_count)

    def test_pin_not_connected_undeclared_is_unconnected(self):
        c = classify_erc_report(PIN_NC_REPORT, declared_nc=["J1.A7"])
        self.assertEqual(1, c.intentional_nc_count)  # A7 declared
        self.assertEqual(1, c.unconnected_count)      # A6 not declared
        self.assertEqual(1, c.blocking_count)         # only the undeclared one blocks

    def test_pin_not_connected_none_declared_all_unconnected(self):
        c = classify_erc_report(PIN_NC_REPORT)
        self.assertEqual(0, c.intentional_nc_count)
        self.assertEqual(2, c.unconnected_count)
        self.assertEqual(2, c.blocking_count)

    def test_unparseable_line_goes_to_other_not_dropped(self):
        c = classify_erc_report(OTHER_REPORT)
        self.assertEqual(1, c.other_count)
        self.assertIn("endpoint_off_grid", c.other[0])
        # other is surfaced, not auto-gated.
        self.assertEqual(0, c.blocking_count)

    def test_empty_report_yields_empty_classification(self):
        c = classify_erc_report("ERC report\n***** Sheet /\n ** ERC messages: 0  Errors 0  Warnings 0\n")
        self.assertEqual(0, c.blocking_count)
        self.assertEqual(0, c.other_count)

    def test_deterministic_byte_identical_output(self):
        report = PIN_NC_REPORT + REAL_SHORT_REPORT + OTHER_REPORT
        a = classify_erc_report(report, declared_nc=["J1.A7"])
        b = classify_erc_report(report, declared_nc=["J1.A7"])
        self.assertEqual(a, b)
        self.assertEqual(a.real_shorts, b.real_shorts)
        self.assertEqual(a.unconnected, b.unconnected)
        self.assertEqual(a.intentional_nc, b.intentional_nc)
        self.assertEqual(a.other, b.other)

    def test_raw_description_preserved_for_traceability(self):
        c = classify_erc_report(PIN_NC_REPORT)
        # the raw block retains the @(...) detail line for the affected pin
        self.assertTrue(any("Symbol J1 Pin A7" in v for v in c.unconnected))

    def test_result_is_ercclassification_instance(self):
        c = classify_erc_report("")
        self.assertIsInstance(c, ErcClassification)


if __name__ == "__main__":
    unittest.main()
