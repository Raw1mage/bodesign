"""
Unit tests for Verified Circuit Blocks System.

Verifies:
- Core circuit blocks registry and schema validation.
- Datasheet grounding enforcement (天條 4).
- Port mapping validation and missing-port fail fast.
- Refdes conflict avoidance and dynamic sequential allocation.
- Netlist fragment synthesis and instance-scoped internal nets.
- Spatial layout constraint mapping.
"""

import unittest

from bodesign_workflow_core import (
    AppliedBlockResult,
    BlockComponent,
    BlockLayoutConstraint,
    BlockPort,
    BlockValidationError,
    CircuitBlockDefinition,
    CircuitBlockRegistry,
    apply_circuit_block,
    get_core_circuit_blocks,
)


class TestCircuitBlocks(unittest.TestCase):

    def setUp(self) -> None:
        self.registry = CircuitBlockRegistry(load_core=True)

    def test_core_blocks_loaded(self) -> None:
        """Verify that all core blocks are registered and validated."""
        blocks = self.registry.list_blocks()
        block_ids = {b["block_id"] for b in blocks}

        expected = {"usb_c_sink", "power_ldo_3v3", "power_dcdc_buck", "esd_protection_array"}
        self.assertTrue(expected.issubset(block_ids))

        # Check citations exist (天條 4)
        for b in blocks:
            self.assertNotEqual(b["citation"], "UNGROUNDED")
            self.assertGreater(len(b["citation"]), 10)

    def test_ungrounded_block_rejected(self) -> None:
        """Attempting to register a block without datasheet citation must fail fast."""
        bad_block = CircuitBlockDefinition(
            block_id="bad_block",
            name="Ungrounded Circuit",
            category="power",
            description="Lacks datasheet reference",
            datasheet_citation="",  # Empty citation
            external_ports=[BlockPort(name="VIN", direction="power")],
            components=[],
        )
        with self.assertRaises(BlockValidationError) as ctx:
            self.registry.register(bad_block)
        self.assertEqual(ctx.exception.code, "BLOCK_CITATION_MISSING")

    def test_unresolved_pin_net_rejected(self) -> None:
        """Component pin pointing to non-existent net must fail validation."""
        bad_block = CircuitBlockDefinition(
            block_id="unresolved_net_block",
            name="Invalid Net Block",
            category="interface",
            description="Pin points to GHOST_NET",
            datasheet_citation="Mock Standard §1.0",
            external_ports=[BlockPort(name="GND", direction="ground")],
            components=[
                BlockComponent(
                    ref_prefix="R",
                    value="10k",
                    package="R_0402",
                    pins={"1": "GND", "2": "GHOST_NET"},  # GHOST_NET not in ports/internal
                )
            ],
        )
        with self.assertRaises(BlockValidationError) as ctx:
            self.registry.register(bad_block)
        self.assertEqual(ctx.exception.code, "BLOCK_NET_UNRESOLVED")

    def test_apply_usb_c_sink_happy_path(self) -> None:
        """Verify standard application of usb_c_sink block."""
        port_mapping = {
            "VBUS": "+5V_IN",
            "GND": "GND",
            "CC1": "USB_CC1",
            "CC2": "USB_CC2",
        }

        result = apply_circuit_block(
            block_id="usb_c_sink",
            port_mapping=port_mapping,
            instance_id="usb1",
            registry=self.registry,
        )

        self.assertIsInstance(result, AppliedBlockResult)
        self.assertEqual(result.block_id, "usb_c_sink")
        self.assertEqual(len(result.components), 4)  # 2 resistors, 2 caps

        # Check refdes sequential assignment
        refdes_list = [c.refdes for c in result.components]
        self.assertEqual(refdes_list, ["R1", "R2", "C1", "C2"])

        # Check net connections
        self.assertIn("USB_CC1", result.net_connections)
        self.assertIn("USB_CC2", result.net_connections)
        self.assertIn("+5V_IN", result.net_connections)
        self.assertIn("GND", result.net_connections)

        self.assertIn("R1.1", result.net_connections["USB_CC1"])
        self.assertIn("R1.2", result.net_connections["GND"])
        self.assertIn("R2.1", result.net_connections["USB_CC2"])

        # Check BOM rows
        self.assertEqual(len(result.bom_rows), 4)
        cc1_row = next(r for r in result.bom_rows if r["Designator"] == "R1")
        self.assertEqual(cc1_row["Value"], "5.1k 1%")
        self.assertEqual(cc1_row["LCSC_Part"], "C25905")

        # Check layout constraints mapped to assigned refdes
        self.assertGreater(len(result.layout_constraints), 0)
        c_layout = result.layout_constraints[0]
        self.assertIn("R1", c_layout.target_elements)

    def test_refdes_collision_avoidance(self) -> None:
        """Verify that existing refdes are avoided and incremented."""
        used = {"R1", "R2", "R3", "C1", "C2"}

        port_mapping = {
            "VBUS": "+5V_IN",
            "GND": "GND",
            "CC1": "USB_CC1",
            "CC2": "USB_CC2",
        }

        result = apply_circuit_block(
            block_id="usb_c_sink",
            port_mapping=port_mapping,
            instance_id="usb2",
            used_refdes=used,
            registry=self.registry,
        )

        assigned_refs = [c.refdes for c in result.components]
        # Should allocate R4, R5, C3, C4
        self.assertEqual(assigned_refs, ["R4", "R5", "C3", "C4"])

    def test_missing_required_port_fails_fast(self) -> None:
        """Missing required port mapping must raise PORT_MAPPING_INCOMPLETE."""
        incomplete_mapping = {
            "VBUS": "+5V_IN",
            # Missing GND, CC1, CC2
        }

        with self.assertRaises(BlockValidationError) as ctx:
            apply_circuit_block(
                block_id="usb_c_sink",
                port_mapping=incomplete_mapping,
                registry=self.registry,
            )
        self.assertEqual(ctx.exception.code, "PORT_MAPPING_INCOMPLETE")
        self.assertIn("CC1", ctx.exception.details["missing_ports"])

    def test_apply_dcdc_buck_with_internal_nets(self) -> None:
        """Buck converter internal nets (SW, FB) must be scoped to the instance."""
        port_mapping = {
            "VIN": "+12V",
            "VOUT": "+3V3_SYS",
            "GND": "GND",
            "EN": "SYS_EN",
        }

        result = apply_circuit_block(
            block_id="power_dcdc_buck",
            port_mapping=port_mapping,
            instance_id="buck1",
            registry=self.registry,
        )

        # Check internal nets are prefixed
        self.assertIn("NET_buck1_SW", result.net_connections)
        self.assertIn("NET_buck1_FB", result.net_connections)

        # Verify feedforward capacitor C_FF is instantiated
        c_ff = next(c for c in result.components if c.value == "22pF 50V")
        self.assertIsNotNone(c_ff)
        self.assertEqual(c_ff.pin_connections["1"], "+3V3_SYS")
        self.assertEqual(c_ff.pin_connections["2"], "NET_buck1_FB")

    def test_apply_esd_protection_array(self) -> None:
        """Verify ESD protection array maps channels to data/CC lines."""
        port_mapping = {
            "CH1": "USB_D_P",
            "CH2": "USB_D_N",
            "CH3": "USB_CC1",
            "CH4": "USB_CC2",
            "GND": "GND",
        }

        result = apply_circuit_block(
            block_id="esd_protection_array",
            port_mapping=port_mapping,
            instance_id="esd1",
            registry=self.registry,
        )

        d_tvs = result.components[0]
        self.assertEqual(d_tvs.value, "TPD4E05U06")
        self.assertEqual(d_tvs.pin_connections["1"], "USB_D_P")
        self.assertEqual(d_tvs.pin_connections["2"], "USB_D_N")
        self.assertEqual(d_tvs.pin_connections["3"], "GND")


if __name__ == "__main__":
    unittest.main()
