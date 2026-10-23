"""
Unit tests for C03-C04 SubstateMachine, Governance Engine, and BlockerHub.

Verifies:
- Monotonic state progression across C03 (S0-S5) and C04 (P0-P7).
- Rejection of invalid state jumps and backward transitions.
- Multi-agent role authority and Zero Self-Approval enforcement.
- Upstream control invariant (C04 cannot proceed without locked C03).
- Mandatory unmeasured axes disclosure and mechanical pass marking.
- Strict human approval requirement for final fab release (天條 3).
- BlockerHub structured logging, directed repair routing, and retry bounds.
"""

import json
from pathlib import Path
import tempfile
import unittest

from bodesign_workflow_core import (
    A2ARole,
    BlockerHub,
    BlockerRecord,
    BlockerStatus,
    C03State,
    C04State,
    ControlViolationError,
    GateVerdict,
    GovernanceError,
    SelfApprovalProhibitedError,
    StateReceipt,
    StateTransitionBlockedError,
    SubstateMachine,
    mint_receipt,
)


class TestSubstateMachineAndBlockerHub(unittest.TestCase):

    def setUp(self) -> None:
        self.sm = SubstateMachine()

    def test_happy_path_c03_progression(self) -> None:
        """Verify full, monotonic progression from S0 to S5 with receipts."""
        self.assertEqual(self.sm.current_state, C03State.S0_SPEC_FROZEN.value)

        # S0 -> S1
        r1 = self.sm.advance_c03(
            C03State.S1_PARTS_RESOLVED,
            calling_role=A2ARole.EE_DESIGNER,
            artifact_payload="parts: mcu, ldo",
        )
        self.assertEqual(self.sm.c03_current, C03State.S1_PARTS_RESOLVED)
        self.assertEqual(r1.author_role, A2ARole.EE_DESIGNER.value)
        self.assertTrue(r1.mechanical_axes_only)
        self.assertGreater(len(r1.not_checked), 0)

        # S1 -> S2
        r2 = self.sm.advance_c03(
            C03State.S2_BLOCKS_EXPANDED,
            calling_role=A2ARole.EE_DESIGNER,
            artifact_payload="blocks: usb_c_sink",
        )
        self.assertEqual(self.sm.c03_current, C03State.S2_BLOCKS_EXPANDED)

        # S2 -> S3
        r3 = self.sm.advance_c03(
            C03State.S3_NETS_WIRED,
            calling_role=A2ARole.EE_DESIGNER,
            artifact_payload="nets: GND, +3V3, CC1",
        )
        self.assertEqual(self.sm.c03_current, C03State.S3_NETS_WIRED)

        # S3 -> S4 (requires verification-adversary and passed check_c03)
        r4 = self.sm.advance_c03(
            C03State.S4_CHECK_C03_VERIFIED,
            calling_role=A2ARole.VERIFICATION_ADVERSARY,
            gate_verdicts=[GateVerdict("check_c03", passed=True, blocking_count=0)],
            artifact_payload="check_c03: PASS",
        )
        self.assertEqual(self.sm.c03_current, C03State.S4_CHECK_C03_VERIFIED)

        # S4 -> S5 (locked by systems-architect)
        r5 = self.sm.advance_c03(
            C03State.S5_C03_LOCKED,
            calling_role=A2ARole.SYSTEMS_ARCHITECT,
            artifact_payload="frozen_netlist_digest",
        )
        self.assertEqual(self.sm.c03_current, C03State.S5_C03_LOCKED)
        self.assertIsNotNone(self.sm.get_receipt(C03State.S5_C03_LOCKED.value))

    def test_state_jump_rejection(self) -> None:
        """Verify that skipping micro-states is strictly blocked."""
        # Current is S0, attempt to jump directly to S2
        with self.assertRaises(StateTransitionBlockedError) as ctx:
            self.sm.advance_c03(
                C03State.S2_BLOCKS_EXPANDED,
                calling_role=A2ARole.EE_DESIGNER,
            )
        self.assertIn("Missing prerequisite: S1_PARTS_RESOLVED", str(ctx.exception))

    def test_backward_transition_rejection(self) -> None:
        """Verify that transitioning backward is blocked."""
        self.sm.advance_c03(C03State.S1_PARTS_RESOLVED, calling_role=A2ARole.EE_DESIGNER)
        with self.assertRaises(StateTransitionBlockedError) as ctx:
            self.sm.advance_c03(C03State.S0_SPEC_FROZEN, calling_role=A2ARole.SYSTEMS_ARCHITECT)
        self.assertIn("Cannot advance backward", str(ctx.exception))

    def test_self_approval_prohibited_s4(self) -> None:
        """EE Designer cannot self-approve S4_CHECK_C03_VERIFIED (Adversarial Verification Gate)."""
        self.sm.advance_c03(C03State.S1_PARTS_RESOLVED, calling_role=A2ARole.EE_DESIGNER)
        self.sm.advance_c03(C03State.S2_BLOCKS_EXPANDED, calling_role=A2ARole.EE_DESIGNER)
        self.sm.advance_c03(C03State.S3_NETS_WIRED, calling_role=A2ARole.EE_DESIGNER)

        with self.assertRaises(SelfApprovalProhibitedError) as ctx:
            self.sm.advance_c03(
                C03State.S4_CHECK_C03_VERIFIED,
                calling_role=A2ARole.EE_DESIGNER,  # Authoring role cannot verify
                gate_verdicts=[GateVerdict("check_c03", passed=True, blocking_count=0)],
            )
        self.assertIn("GOV_SELF_APPROVAL_PROHIBITED", str(ctx.exception))

    def test_c04_blocked_without_c03_lock(self) -> None:
        """C04 layout cannot begin if C03 is not locked in S5."""
        self.assertEqual(self.sm.c03_current, C03State.S0_SPEC_FROZEN)

        with self.assertRaises(ControlViolationError) as ctx:
            self.sm.advance_c04(
                C04State.P0_BOARD_BOUNDED,
                calling_role=A2ARole.LAYOUT_SPECIALIST,
            )
        self.assertIn("Cannot enter C04 layout without locked C03 schematic", str(ctx.exception))

    def test_happy_path_c04_progression(self) -> None:
        """Verify full C04 progression up to P7 with human approval."""
        # Fast-forward C03 to S5
        self.sm.advance_c03(C03State.S1_PARTS_RESOLVED, calling_role=A2ARole.EE_DESIGNER)
        self.sm.advance_c03(C03State.S2_BLOCKS_EXPANDED, calling_role=A2ARole.EE_DESIGNER)
        self.sm.advance_c03(C03State.S3_NETS_WIRED, calling_role=A2ARole.EE_DESIGNER)
        self.sm.advance_c03(
            C03State.S4_CHECK_C03_VERIFIED,
            calling_role=A2ARole.VERIFICATION_ADVERSARY,
            gate_verdicts=[GateVerdict("check_c03", passed=True, blocking_count=0)],
        )
        self.sm.advance_c03(C03State.S5_C03_LOCKED, calling_role=A2ARole.SYSTEMS_ARCHITECT)

        # C04 P0 -> P1 -> P2
        self.sm.advance_c04(C04State.P0_BOARD_BOUNDED, calling_role=A2ARole.LAYOUT_SPECIALIST)
        self.sm.advance_c04(C04State.P1_TOPOLOGY_PLACED, calling_role=A2ARole.LAYOUT_SPECIALIST)
        self.sm.advance_c04(C04State.P2_PERIPHERAL_TIDIED, calling_role=A2ARole.LAYOUT_SPECIALIST)

        # P3: placement_preflight audit by verification-adversary
        p3_receipt = self.sm.advance_c04(
            C04State.P3_PREFLIGHT_PASSED,
            calling_role=A2ARole.VERIFICATION_ADVERSARY,
            gate_verdicts=[GateVerdict("placement_preflight", passed=True, blocking_count=0)],
        )
        self.assertEqual(p3_receipt.state, C04State.P3_PREFLIGHT_PASSED.value)

        # P4: Routing
        self.sm.advance_c04(C04State.P4_ROUTED, calling_role=A2ARole.LAYOUT_SPECIALIST)

        # P5: Planes & Silk Tidy
        self.sm.advance_c04(C04State.P5_PLANES_AND_TIDY, calling_role=A2ARole.LAYOUT_SPECIALIST)

        # P6: DRC by verification-adversary
        p6_receipt = self.sm.advance_c04(
            C04State.P6_DRC_AND_VISUAL_CLOSED,
            calling_role=A2ARole.VERIFICATION_ADVERSARY,
            gate_verdicts=[GateVerdict("layout_drc_gate", passed=True, blocking_count=0)],
        )
        self.assertEqual(p6_receipt.state, C04State.P6_DRC_AND_VISUAL_CLOSED.value)

        # P7: Fab Release requires human approval (天條 3)
        with self.assertRaises(GovernanceError) as ctx:
            self.sm.advance_c04(
                C04State.P7_FAB_RELEASED,
                calling_role=A2ARole.RELEASE_ENGINEER,
                human_approved=False,  # Should be rejected
            )
        self.assertIn("NO_SEND_TO_FAB_WITHOUT_HUMAN_APPROVAL", str(ctx.exception))

        # P7 with human approval succeeds
        p7_receipt = self.sm.advance_c04(
            C04State.P7_FAB_RELEASED,
            calling_role=A2ARole.RELEASE_ENGINEER,
            human_approved=True,
        )
        self.assertEqual(p7_receipt.state, C04State.P7_FAB_RELEASED.value)
        self.assertTrue(p7_receipt.human_approved)

    def test_self_approval_prohibited_c04(self) -> None:
        """Layout Specialist cannot self-approve P3 (Preflight) or P6 (DRC)."""
        # Fast-forward to P2
        self.sm.advance_c03(C03State.S1_PARTS_RESOLVED, calling_role=A2ARole.EE_DESIGNER)
        self.sm.advance_c03(C03State.S2_BLOCKS_EXPANDED, calling_role=A2ARole.EE_DESIGNER)
        self.sm.advance_c03(C03State.S3_NETS_WIRED, calling_role=A2ARole.EE_DESIGNER)
        self.sm.advance_c03(
            C03State.S4_CHECK_C03_VERIFIED,
            calling_role=A2ARole.VERIFICATION_ADVERSARY,
            gate_verdicts=[GateVerdict("check_c03", passed=True, blocking_count=0)],
        )
        self.sm.advance_c03(C03State.S5_C03_LOCKED, calling_role=A2ARole.SYSTEMS_ARCHITECT)
        self.sm.advance_c04(C04State.P0_BOARD_BOUNDED, calling_role=A2ARole.LAYOUT_SPECIALIST)
        self.sm.advance_c04(C04State.P1_TOPOLOGY_PLACED, calling_role=A2ARole.LAYOUT_SPECIALIST)
        self.sm.advance_c04(C04State.P2_PERIPHERAL_TIDIED, calling_role=A2ARole.LAYOUT_SPECIALIST)

        # Attempt P3 self-approval
        with self.assertRaises(SelfApprovalProhibitedError):
            self.sm.advance_c04(
                C04State.P3_PREFLIGHT_PASSED,
                calling_role=A2ARole.LAYOUT_SPECIALIST,
                gate_verdicts=[GateVerdict("placement_preflight", passed=True, blocking_count=0)],
            )

    def test_routing_blocked_without_p3_receipt(self) -> None:
        """Agent cannot call routing if P3 preflight receipt is missing."""
        # Setup up to S5 + P0
        self.sm.advance_c03(C03State.S1_PARTS_RESOLVED, calling_role=A2ARole.EE_DESIGNER)
        self.sm.advance_c03(C03State.S2_BLOCKS_EXPANDED, calling_role=A2ARole.EE_DESIGNER)
        self.sm.advance_c03(C03State.S3_NETS_WIRED, calling_role=A2ARole.EE_DESIGNER)
        self.sm.advance_c03(
            C03State.S4_CHECK_C03_VERIFIED,
            calling_role=A2ARole.VERIFICATION_ADVERSARY,
            gate_verdicts=[GateVerdict("check_c03", passed=True, blocking_count=0)],
        )
        self.sm.advance_c03(C03State.S5_C03_LOCKED, calling_role=A2ARole.SYSTEMS_ARCHITECT)
        self.sm.advance_c04(C04State.P0_BOARD_BOUNDED, calling_role=A2ARole.LAYOUT_SPECIALIST)

        # Attempt to jump to P4
        with self.assertRaises(StateTransitionBlockedError):
            self.sm.advance_c04(C04State.P4_ROUTED, calling_role=A2ARole.LAYOUT_SPECIALIST)

    def test_receipt_serialization_roundtrip(self) -> None:
        """Verify StateReceipt serializes to/from dict and JSON losslessly."""
        receipt = mint_receipt(
            state="P3_PREFLIGHT_PASSED",
            author_role=A2ARole.VERIFICATION_ADVERSARY,
            artifact_payload={"utilization": 0.45, "overlaps": 0},
            gate_verdicts=[GateVerdict("placement_preflight", passed=True, blocking_count=0)],
        )
        data = receipt.to_dict()
        restored = StateReceipt.from_dict(data)

        self.assertEqual(receipt.token, restored.token)
        self.assertEqual(receipt.sha256_digest, restored.sha256_digest)
        self.assertEqual(receipt.mechanical_axes_only, restored.mechanical_axes_only)
        self.assertEqual(receipt.not_checked, restored.not_checked)
        self.assertEqual(len(restored.gate_verdicts), 1)

    def test_blocker_hub_lifecycle_and_routing(self) -> None:
        """Verify BlockerHub logging, routing, retry tracking, and escalation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hub = BlockerHub(storage_dir=tmpdir)

            # 1. Create DRC Blocker (Activity A4)
            record = hub.create_blocker(
                source_step=7,
                owning_activity="A4",
                error_code="DRC_CLEARANCE_VIOLATION",
                summary="Clearance between Pad 1 and Track at (124.5, 45.2) < 0.2mm",
                evidence={"coords": [124.5, 45.2], "visual_crop": "crops/drc_01.png"},
                resume_condition="Clearance >= 0.2mm",
                max_retries=2,
            )

            self.assertEqual(record.blocker_id, "BLK-001")
            self.assertEqual(record.target_role, A2ARole.LAYOUT_SPECIALIST.value)
            self.assertEqual(record.status, BlockerStatus.OPEN)

            # Assert file was persisted
            disk_file = Path(tmpdir) / "BLK-001.json"
            self.assertTrue(disk_file.exists())

            # 2. First dispatch repair (attempt 1)
            work_order_1 = hub.dispatch_repair("BLK-001")
            self.assertEqual(work_order_1["status"], "ROUTED")
            self.assertEqual(work_order_1["target_role"], A2ARole.LAYOUT_SPECIALIST.value)
            self.assertEqual(work_order_1["repair_directive"]["attempt"], 1)

            # 3. Second dispatch repair (attempt 2)
            work_order_2 = hub.dispatch_repair("BLK-001")
            self.assertEqual(work_order_2["status"], "ROUTED")
            self.assertEqual(work_order_2["repair_directive"]["attempt"], 2)

            # 4. Third attempt exceeds max_retries (2) -> Escalate to Orchestrator
            escalation = hub.dispatch_repair("BLK-001")
            self.assertEqual(escalation["status"], "ESCALATED")
            self.assertEqual(escalation["target_role"], A2ARole.ORCHESTRATOR.value)

            # 5. Resolution
            resolved = hub.resolve_blocker("BLK-001", resolution_notes="Layout Specialist re-routed track to 0.25mm clearance.")
            self.assertEqual(resolved.status, BlockerStatus.RESOLVED)
            self.assertEqual(len(hub.list_open_blockers()), 0)


if __name__ == "__main__":
    unittest.main()
