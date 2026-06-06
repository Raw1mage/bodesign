import unittest

from bodesign_eda_bridge import (
    build_pin_allocation,
    render_pin_allocation_csv,
    render_pin_allocation_md,
)

NETS = [
    {"name": "VIN", "nodes": ["U1.1", "R1.1"]},
    {"name": "MID", "nodes": ["U1.2", "R1.2", "C1.1"]},
    {"name": "GND", "nodes": ["U1.10", "C1.2"]},
]


class PinAllocationTests(unittest.TestCase):
    def test_pivots_nets_to_pin_rows_with_mcu_flag(self):
        alloc = build_pin_allocation(NETS, mcu_refs=("U1",))

        self.assertEqual(["C1", "R1", "U1"], alloc.refs)
        self.assertEqual(3, alloc.net_count)
        by = {(r.ref, r.pin): r for r in alloc.rows}
        self.assertEqual("VIN", by[("U1", "1")].net)
        self.assertTrue(by[("U1", "1")].is_mcu)
        self.assertFalse(by[("R1", "1")].is_mcu)
        # natural pin sort: U1.2 sorts before U1.10
        u1 = [r.pin for r in alloc.rows if r.ref == "U1"]
        self.assertEqual(["1", "2", "10"], u1)

    def test_accepts_tuple_nodes(self):
        alloc = build_pin_allocation([{"name": "N", "nodes": [("U1", "5")]}])
        self.assertEqual("N", alloc.rows[0].net)
        self.assertEqual("U1", alloc.rows[0].ref)

    def test_renders_csv_and_md(self):
        alloc = build_pin_allocation(NETS, mcu_refs=("U1",))
        csv_text = render_pin_allocation_csv(alloc)
        self.assertIn("RefDes,Pin,Net,MCU_GPIO", csv_text)
        self.assertIn("U1,1,VIN,yes", csv_text)
        mcu_only = render_pin_allocation_csv(alloc, mcu_only=True)
        self.assertNotIn("R1,1", mcu_only)
        md = render_pin_allocation_md(alloc)
        self.assertIn("## U1 (MCU/GPIO)", md)


if __name__ == "__main__":
    unittest.main()
