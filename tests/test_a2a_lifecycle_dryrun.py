import tempfile
from pathlib import Path
import unittest

from bodesign_workflow_core.substate_machine import (
    A2ARole,
    C03State,
    C04State,
    GateVerdict,
    SubstateMachine,
    SelfApprovalProhibitedError,
    ControlViolationError,
    StateTransitionBlockedError,
    GovernanceError,
)
from bodesign_workflow_core.circuit_blocks import (
    apply_circuit_block,
    CircuitBlockRegistry,
)
from bodesign_workflow_core.blocker_hub import (
    BlockerHub,
    BlockerStatus,
)


class TestA2ALifecycleDryRun(unittest.TestCase):
    """
    End-to-end validation of the IDEF0 A2A institutional hardware design workflow.
    Validates complete lifecycle across S0..S5 (C03) -> P0..P7 (C04) with role
    separation, Zero Self-Approval, receipt chains, and blocker repair loops.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)
        self.hub = BlockerHub(self.work_dir)
        self.reg = CircuitBlockRegistry()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_complete_governed_lifecycle(self):
        # -------------------------------------------------------------
        # 1. C03 Schematic Lifecycle (S0 -> S5)
        # -------------------------------------------------------------
        sm = SubstateMachine(c03_current=C03State.S0_SPEC_FROZEN)

        # S0 -> S1: EE Designer resolves components
        r1 = sm.advance_c03(
            target_state=C03State.S1_PARTS_RESOLVED,
            calling_role=A2ARole.EE_DESIGNER,
            artifact_payload={"bom_parts": ["STM32F401", "TPS62130", "USB-C"]},
        )
        self.assertEqual(sm.c03_current, C03State.S1_PARTS_RESOLVED)
        self.assertIn("functional_circuit_simulation", r1.not_checked)

        # S1 -> S2: EE Designer expands verified circuit blocks
        block_res = apply_circuit_block(
            block_id="usb_c_sink",
            port_mapping={"VBUS": "VBUS_5V", "GND": "GND", "CC1": "MCU_CC1", "CC2": "MCU_CC2"},
            instance_id="pwr1",
            registry=self.reg,
        )
        self.assertGreater(len(block_res.components), 0)
        self.assertGreater(len(block_res.layout_constraints), 0)

        r2 = sm.advance_c03(
            target_state=C03State.S2_BLOCKS_EXPANDED,
            calling_role=A2ARole.EE_DESIGNER,
            artifact_payload=block_res.to_dict(),
        )
        self.assertEqual(sm.c03_current, C03State.S2_BLOCKS_EXPANDED)

        # S2 -> S3: EE Designer wires nets
        r3 = sm.advance_c03(
            target_state=C03State.S3_NETS_WIRED,
            calling_role=A2ARole.EE_DESIGNER,
            artifact_payload={"netlist_sha256": "abcdef1234567890"},
        )
        self.assertEqual(sm.c03_current, C03State.S3_NETS_WIRED)

        # S3 -> S4: Verification Adversary checks stage entry (Zero Self-Approval)
        with self.assertRaises(SelfApprovalProhibitedError):
            sm.advance_c03(
                target_state=C03State.S4_CHECK_C03_VERIFIED,
                calling_role=A2ARole.EE_DESIGNER,  # Prohibited!
            )

        r4 = sm.advance_c03(
            target_state=C03State.S4_CHECK_C03_VERIFIED,
            calling_role=A2ARole.VERIFICATION_ADVERSARY,  # Authorized
            gate_verdicts=[GateVerdict(gate_name="check_c03", passed=True, blocking_count=0)],
        )
        self.assertEqual(sm.c03_current, C03State.S4_CHECK_C03_VERIFIED)

        # S4 -> S5: Systems Architect locks C03
        r5 = sm.advance_c03(
            target_state=C03State.S5_C03_LOCKED,
            calling_role=A2ARole.SYSTEMS_ARCHITECT,
            artifact_payload={"freeze_json": "C03_Netlist_Freeze.json"},
        )
        self.assertEqual(sm.c03_current, C03State.S5_C03_LOCKED)

        # -------------------------------------------------------------
        # 2. C04 Layout Lifecycle (P0 -> P7)
        # -------------------------------------------------------------
        # P0: Layout Specialist establishes board boundary
        r_p0 = sm.advance_c04(
            target_state=C04State.P0_BOARD_BOUNDED,
            calling_role=A2ARole.LAYOUT_SPECIALIST,
        )
        self.assertEqual(sm.c04_current, C04State.P0_BOARD_BOUNDED)

        # P0 -> P1: Layout Specialist locks topology anchors
        r_p1 = sm.advance_c04(
            target_state=C04State.P1_TOPOLOGY_PLACED,
            calling_role=A2ARole.LAYOUT_SPECIALIST,
        )
        self.assertEqual(sm.c04_current, C04State.P1_TOPOLOGY_PLACED)

        # P1 -> P2: Layout Specialist applies peripheral tidy
        r_p2 = sm.advance_c04(
            target_state=C04State.P2_PERIPHERAL_TIDIED,
            calling_role=A2ARole.LAYOUT_SPECIALIST,
        )
        self.assertEqual(sm.c04_current, C04State.P2_PERIPHERAL_TIDIED)

        # P2 -> P3: Preflight Verification (Verification Adversary)
        # Simulate initial failure -> blocker logged
        blocker = self.hub.create_blocker(
            source_step="P2",
            owning_activity="A3",
            error_code="ERR_COURTYARD_OVERLAP",
            summary="Courtyard collision between C1 and U1",
            evidence={"offenders": ["C1", "U1"], "distance_mm": -0.05},
            resume_condition="P2 peripheral tidy must clear courtyard overlap",
        )
        self.assertEqual(blocker.status, BlockerStatus.OPEN)
        self.assertEqual(blocker.target_role, "layout-specialist")

        # Layout Specialist resolves blocker
        resolved_blocker = self.hub.resolve_blocker(
            blocker.blocker_id,
            resolution_notes="Moved C1 0.5mm right along X grid",
        )
        self.assertEqual(resolved_blocker.status, BlockerStatus.RESOLVED)

        # Now Verification Adversary verifies preflight pass
        r_p3 = sm.advance_c04(
            target_state=C04State.P3_PREFLIGHT_PASSED,
            calling_role=A2ARole.VERIFICATION_ADVERSARY,
            gate_verdicts=[GateVerdict(gate_name="placement_preflight", passed=True, blocking_count=0)],
        )
        self.assertEqual(sm.c04_current, C04State.P3_PREFLIGHT_PASSED)

        # P3 -> P4: Routing
        r_p4 = sm.advance_c04(
            target_state=C04State.P4_ROUTED,
            calling_role=A2ARole.LAYOUT_SPECIALIST,
        )
        self.assertEqual(sm.c04_current, C04State.P4_ROUTED)

        # P4 -> P5: Planes & Micro-stub Tidy
        r_p5 = sm.advance_c04(
            target_state=C04State.P5_PLANES_AND_TIDY,
            calling_role=A2ARole.LAYOUT_SPECIALIST,
        )
        self.assertEqual(sm.c04_current, C04State.P5_PLANES_AND_TIDY)

        # P5 -> P6: DRC & Visual Closure (Verification Adversary)
        r_p6 = sm.advance_c04(
            target_state=C04State.P6_DRC_AND_VISUAL_CLOSED,
            calling_role=A2ARole.VERIFICATION_ADVERSARY,
            gate_verdicts=[GateVerdict(gate_name="layout_drc_gate", passed=True, blocking_count=0)],
        )
        self.assertEqual(sm.c04_current, C04State.P6_DRC_AND_VISUAL_CLOSED)

        # P6 -> P7: Final Fab Release (Requires Human Approval Token)
        with self.assertRaises(GovernanceError):
            sm.advance_c04(
                target_state=C04State.P7_FAB_RELEASED,
                calling_role=A2ARole.RELEASE_ENGINEER,
                human_approved=False,  # Blocked!
            )

        r_p7 = sm.advance_c04(
            target_state=C04State.P7_FAB_RELEASED,
            calling_role=A2ARole.RELEASE_ENGINEER,
            human_approved=True,  # Approved!
        )
        self.assertEqual(sm.c04_current, C04State.P7_FAB_RELEASED)
        self.assertTrue(r_p7.human_approved)


if __name__ == "__main__":
    unittest.main()
