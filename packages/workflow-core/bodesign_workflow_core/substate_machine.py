"""
Substate Machine and Governance Engine for C03-C04 IDEF0 A2A Institutional Regime.

Implements monotonic micro-state progression across Schematic (S0-S5) and Layout (P0-P7),
enforces multi-agent role authority boundaries (Zero Self-Approval), and issues
immutable cryptographic receipts with explicit unmeasured verification disclosure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any
import uuid


class C03State(str, Enum):
    S0_SPEC_FROZEN = "S0_SPEC_FROZEN"
    S1_PARTS_RESOLVED = "S1_PARTS_RESOLVED"
    S2_BLOCKS_EXPANDED = "S2_BLOCKS_EXPANDED"
    S3_NETS_WIRED = "S3_NETS_WIRED"
    S4_CHECK_C03_VERIFIED = "S4_CHECK_C03_VERIFIED"
    S5_C03_LOCKED = "S5_C03_LOCKED"


class C04State(str, Enum):
    P0_BOARD_BOUNDED = "P0_BOARD_BOUNDED"
    P1_TOPOLOGY_PLACED = "P1_TOPOLOGY_PLACED"
    P2_PERIPHERAL_TIDIED = "P2_PERIPHERAL_TIDIED"
    P3_PREFLIGHT_PASSED = "P3_PREFLIGHT_PASSED"
    P4_ROUTED = "P4_ROUTED"
    P5_PLANES_AND_TIDY = "P5_PLANES_AND_TIDY"
    P6_DRC_AND_VISUAL_CLOSED = "P6_DRC_AND_VISUAL_CLOSED"
    P7_FAB_RELEASED = "P7_FAB_RELEASED"


class A2ARole(str, Enum):
    SYSTEMS_ARCHITECT = "systems-architect"
    EE_DESIGNER = "ee-designer"
    LAYOUT_SPECIALIST = "layout-specialist"
    VERIFICATION_ADVERSARY = "verification-adversary"
    RELEASE_ENGINEER = "release-engineer"
    ORCHESTRATOR = "orchestrator"


# Monotonic progression sequences
C03_SEQUENCE: list[C03State] = [
    C03State.S0_SPEC_FROZEN,
    C03State.S1_PARTS_RESOLVED,
    C03State.S2_BLOCKS_EXPANDED,
    C03State.S3_NETS_WIRED,
    C03State.S4_CHECK_C03_VERIFIED,
    C03State.S5_C03_LOCKED,
]

C04_SEQUENCE: list[C04State] = [
    C04State.P0_BOARD_BOUNDED,
    C04State.P1_TOPOLOGY_PLACED,
    C04State.P2_PERIPHERAL_TIDIED,
    C04State.P3_PREFLIGHT_PASSED,
    C04State.P4_ROUTED,
    C04State.P5_PLANES_AND_TIDY,
    C04State.P6_DRC_AND_VISUAL_CLOSED,
    C04State.P7_FAB_RELEASED,
]

# Authorized roles per micro-state transition
AUTHORIZED_ROLES: dict[str, set[A2ARole]] = {
    C03State.S0_SPEC_FROZEN.value: {A2ARole.SYSTEMS_ARCHITECT, A2ARole.ORCHESTRATOR},
    C03State.S1_PARTS_RESOLVED.value: {A2ARole.EE_DESIGNER},
    C03State.S2_BLOCKS_EXPANDED.value: {A2ARole.EE_DESIGNER},
    C03State.S3_NETS_WIRED.value: {A2ARole.EE_DESIGNER},
    C03State.S4_CHECK_C03_VERIFIED.value: {A2ARole.VERIFICATION_ADVERSARY},
    C03State.S5_C03_LOCKED.value: {A2ARole.SYSTEMS_ARCHITECT, A2ARole.ORCHESTRATOR},
    C04State.P0_BOARD_BOUNDED.value: {A2ARole.SYSTEMS_ARCHITECT, A2ARole.LAYOUT_SPECIALIST},
    C04State.P1_TOPOLOGY_PLACED.value: {A2ARole.LAYOUT_SPECIALIST},
    C04State.P2_PERIPHERAL_TIDIED.value: {A2ARole.LAYOUT_SPECIALIST},
    C04State.P3_PREFLIGHT_PASSED.value: {A2ARole.VERIFICATION_ADVERSARY},
    C04State.P4_ROUTED.value: {A2ARole.LAYOUT_SPECIALIST},
    C04State.P5_PLANES_AND_TIDY.value: {A2ARole.LAYOUT_SPECIALIST},
    C04State.P6_DRC_AND_VISUAL_CLOSED.value: {A2ARole.VERIFICATION_ADVERSARY},
    C04State.P7_FAB_RELEASED.value: {A2ARole.RELEASE_ENGINEER, A2ARole.ORCHESTRATOR},
}

# Required unmeasured disclosure axes for mechanical validation
MANDATORY_UNMEASURED_AXES: list[str] = [
    "functional_circuit_simulation",
    "high_speed_si_pi_simulation",
    "thermal_fem_analysis",
    "rf_tuning_and_emc",
    "human_visual_inspection",
]


class GovernanceError(Exception):
    """Base exception for governance protocol violations."""
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.details = details or {}


class StateTransitionBlockedError(GovernanceError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("GOV_TRANSITION_BLOCKED", message, details)


class SelfApprovalProhibitedError(GovernanceError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("GOV_SELF_APPROVAL_PROHIBITED", message, details)


class ControlViolationError(GovernanceError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("GOV_CONTROL_VIOLATION", message, details)


class InvalidReceiptError(GovernanceError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("GOV_RECEIPT_INVALID", message, details)


@dataclass(slots=True)
class GateVerdict:
    gate_name: str
    passed: bool
    blocking_count: int
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "passed": self.passed,
            "blocking_count": self.blocking_count,
            "details": self.details,
        }


@dataclass(slots=True)
class StateReceipt:
    token: str
    state: str
    author_role: str
    timestamp: str
    sha256_digest: str
    mechanical_axes_only: bool
    not_checked: list[str]
    gate_verdicts: list[dict[str, Any]]
    human_approved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "state": self.state,
            "author_role": self.author_role,
            "timestamp": self.timestamp,
            "sha256_digest": self.sha256_digest,
            "mechanical_axes_only": self.mechanical_axes_only,
            "not_checked": list(self.not_checked),
            "gate_verdicts": list(self.gate_verdicts),
            "human_approved": self.human_approved,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateReceipt:
        return cls(
            token=data["token"],
            state=data["state"],
            author_role=data["author_role"],
            timestamp=data["timestamp"],
            sha256_digest=data["sha256_digest"],
            mechanical_axes_only=data.get("mechanical_axes_only", True),
            not_checked=list(data.get("not_checked", MANDATORY_UNMEASURED_AXES)),
            gate_verdicts=list(data.get("gate_verdicts", [])),
            human_approved=data.get("human_approved", False),
            metadata=dict(data.get("metadata", {})),
        )


def mint_receipt(
    state: str,
    author_role: A2ARole,
    artifact_payload: bytes | str | dict[str, Any],
    gate_verdicts: list[GateVerdict],
    human_approved: bool = False,
    metadata: dict[str, Any] | None = None,
) -> StateReceipt:
    """Mints a cryptographic receipt with unmeasured axes disclosure and mechanical pass marking."""
    if isinstance(artifact_payload, dict):
        raw_bytes = json.dumps(artifact_payload, sort_keys=True).encode("utf-8")
    elif isinstance(artifact_payload, str):
        raw_bytes = artifact_payload.encode("utf-8")
    else:
        raw_bytes = artifact_payload

    digest = hashlib.sha256(raw_bytes).hexdigest()
    now_iso = datetime.now(timezone.utc).isoformat()

    return StateReceipt(
        token=str(uuid.uuid4()),
        state=state,
        author_role=author_role.value,
        timestamp=now_iso,
        sha256_digest=digest,
        mechanical_axes_only=True,
        not_checked=list(MANDATORY_UNMEASURED_AXES),
        gate_verdicts=[v.to_dict() for v in gate_verdicts],
        human_approved=human_approved,
        metadata=metadata or {},
    )


class SubstateMachine:
    """Governs C03 and C04 micro-state transitions, role authorities, and receipt chains."""

    def __init__(
        self,
        c03_current: C03State = C03State.S0_SPEC_FROZEN,
        c04_current: C04State | None = None,
        receipts: dict[str, StateReceipt] | None = None,
    ) -> None:
        self.c03_current = c03_current
        self.c04_current = c04_current
        self.receipts: dict[str, StateReceipt] = receipts or {}

    @property
    def current_state(self) -> str:
        if self.c04_current is not None:
            return self.c04_current.value
        return self.c03_current.value

    def get_receipt(self, state: str) -> StateReceipt | None:
        return self.receipts.get(state)

    def advance_c03(
        self,
        target_state: C03State,
        calling_role: A2ARole,
        gate_verdicts: list[GateVerdict] | None = None,
        artifact_payload: bytes | str | dict[str, Any] = b"",
    ) -> StateReceipt:
        """Advance C03 micro-state with role authority and monotonic sequence checks."""
        # 1. Authority Gate
        allowed_roles = AUTHORIZED_ROLES.get(target_state.value, set())
        if calling_role not in allowed_roles:
            raise SelfApprovalProhibitedError(
                f"Role '{calling_role.value}' is not authorized to advance to '{target_state.value}'. "
                f"Required role in: {[r.value for r in allowed_roles]}",
                {"calling_role": calling_role.value, "target_state": target_state.value},
            )

        # 2. Sequence Gate (Monotonicity)
        curr_idx = C03_SEQUENCE.index(self.c03_current)
        target_idx = C03_SEQUENCE.index(target_state)

        if target_idx <= curr_idx:
            # Re-affirming current state or duplicate call
            if target_idx == curr_idx and target_state.value in self.receipts:
                return self.receipts[target_state.value]
            raise StateTransitionBlockedError(
                f"Cannot advance backward from {self.c03_current.value} to {target_state.value}",
                {"current": self.c03_current.value, "target": target_state.value},
            )

        if target_idx > curr_idx + 1:
            skipped_state = C03_SEQUENCE[curr_idx + 1].value
            raise StateTransitionBlockedError(
                f"Cannot jump states from {self.c03_current.value} to {target_state.value}. "
                f"Missing prerequisite: {skipped_state}",
                {"current": self.c03_current.value, "target": target_state.value, "missing": skipped_state},
            )

        # 3. Gate Verdict Compliance
        verdicts = gate_verdicts or []
        for v in verdicts:
            if not v.passed or v.blocking_count > 0:
                raise StateTransitionBlockedError(
                    f"Gate '{v.gate_name}' failed with {v.blocking_count} blocking violations.",
                    {"gate": v.gate_name, "blocking_count": v.blocking_count, "target": target_state.value},
                )

        # 4. Specific Stage Gate Rules
        if target_state == C03State.S4_CHECK_C03_VERIFIED:
            has_check_c03 = any(v.gate_name == "check_c03" and v.passed for v in verdicts)
            if not has_check_c03:
                raise StateTransitionBlockedError(
                    "Transition to S4_CHECK_C03_VERIFIED requires passed 'check_c03' gate verdict.",
                    {"target": target_state.value},
                )

        if target_state == C03State.S5_C03_LOCKED:
            s4_receipt = self.receipts.get(C03State.S4_CHECK_C03_VERIFIED.value)
            if not s4_receipt:
                raise StateTransitionBlockedError(
                    "Transition to S5_C03_LOCKED requires valid S4_CHECK_C03_VERIFIED receipt.",
                    {"target": target_state.value},
                )

        # 5. Mint Receipt & Lock State
        receipt = mint_receipt(
            state=target_state.value,
            author_role=calling_role,
            artifact_payload=artifact_payload,
            gate_verdicts=verdicts,
        )
        self.c03_current = target_state
        self.receipts[target_state.value] = receipt
        return receipt

    def advance_c04(
        self,
        target_state: C04State,
        calling_role: A2ARole,
        gate_verdicts: list[GateVerdict] | None = None,
        artifact_payload: bytes | str | dict[str, Any] = b"",
        human_approved: bool = False,
    ) -> StateReceipt:
        """Advance C04 micro-state with role authority, C03 handoff check, and monotonic sequence checks."""
        # 0. Upstream Control Check: S5 must be locked before C04 starts
        if self.c03_current != C03State.S5_C03_LOCKED:
            raise ControlViolationError(
                f"Cannot enter C04 layout without locked C03 schematic. Current C03 state: {self.c03_current.value}",
                {"c03_state": self.c03_current.value},
            )

        # 1. Authority Gate
        allowed_roles = AUTHORIZED_ROLES.get(target_state.value, set())
        if calling_role not in allowed_roles:
            raise SelfApprovalProhibitedError(
                f"Role '{calling_role.value}' is not authorized to advance to '{target_state.value}'. "
                f"Required role in: {[r.value for r in allowed_roles]}",
                {"calling_role": calling_role.value, "target_state": target_state.value},
            )

        # 2. Sequence Gate (Monotonicity)
        if self.c04_current is None:
            if target_state != C04State.P0_BOARD_BOUNDED:
                raise StateTransitionBlockedError(
                    f"C04 layout must start with P0_BOARD_BOUNDED, got {target_state.value}",
                    {"target": target_state.value},
                )
        else:
            curr_idx = C04_SEQUENCE.index(self.c04_current)
            target_idx = C04_SEQUENCE.index(target_state)

            if target_idx <= curr_idx:
                if target_idx == curr_idx and target_state.value in self.receipts:
                    return self.receipts[target_state.value]
                raise StateTransitionBlockedError(
                    f"Cannot advance backward from {self.c04_current.value} to {target_state.value}",
                    {"current": self.c04_current.value, "target": target_state.value},
                )

            if target_idx > curr_idx + 1:
                skipped_state = C04_SEQUENCE[curr_idx + 1].value
                raise StateTransitionBlockedError(
                    f"Cannot jump states from {self.c04_current.value} to {target_state.value}. "
                    f"Missing prerequisite: {skipped_state}",
                    {"current": self.c04_current.value, "target": target_state.value, "missing": skipped_state},
                )

        # 3. Gate Verdict Compliance
        verdicts = gate_verdicts or []
        for v in verdicts:
            if not v.passed or v.blocking_count > 0:
                raise StateTransitionBlockedError(
                    f"Gate '{v.gate_name}' failed with {v.blocking_count} blocking violations.",
                    {"gate": v.gate_name, "blocking_count": v.blocking_count, "target": target_state.value},
                )

        # 4. Specific Stage Gate Rules
        if target_state == C04State.P3_PREFLIGHT_PASSED:
            has_preflight = any(v.gate_name == "placement_preflight" and v.passed for v in verdicts)
            if not has_preflight:
                raise StateTransitionBlockedError(
                    "Transition to P3_PREFLIGHT_PASSED requires passed 'placement_preflight' gate verdict.",
                    {"target": target_state.value},
                )

        if target_state == C04State.P4_ROUTED:
            p3_receipt = self.receipts.get(C04State.P3_PREFLIGHT_PASSED.value)
            if not p3_receipt:
                raise StateTransitionBlockedError(
                    "Cannot route (P4_ROUTED) without valid P3_PREFLIGHT_PASSED receipt.",
                    {"target": target_state.value},
                )

        if target_state == C04State.P6_DRC_AND_VISUAL_CLOSED:
            has_drc = any(v.gate_name == "layout_drc_gate" and v.passed for v in verdicts)
            if not has_drc:
                raise StateTransitionBlockedError(
                    "Transition to P6_DRC_AND_VISUAL_CLOSED requires passed 'layout_drc_gate' verdict.",
                    {"target": target_state.value},
                )

        if target_state == C04State.P7_FAB_RELEASED:
            if not human_approved:
                raise GovernanceError(
                    "NO_SEND_TO_FAB_WITHOUT_HUMAN_APPROVAL",
                    "Final manufacturing release P7_FAB_RELEASED strictly requires explicit human approval (天條 3).",
                    {"target": target_state.value},
                )
            p6_receipt = self.receipts.get(C04State.P6_DRC_AND_VISUAL_CLOSED.value)
            if not p6_receipt:
                raise StateTransitionBlockedError(
                    "Cannot release to fab without valid P6_DRC_AND_VISUAL_CLOSED receipt.",
                    {"target": target_state.value},
                )

        # 5. Mint Receipt & Lock State
        receipt = mint_receipt(
            state=target_state.value,
            author_role=calling_role,
            artifact_payload=artifact_payload,
            gate_verdicts=verdicts,
            human_approved=human_approved,
        )
        self.c04_current = target_state
        self.receipts[target_state.value] = receipt
        return receipt

    def to_dict(self) -> dict[str, Any]:
        return {
            "c03_current": self.c03_current.value,
            "c04_current": self.c04_current.value if self.c04_current else None,
            "receipts": {k: v.to_dict() for k, v in self.receipts.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubstateMachine:
        c03_curr = C03State(data["c03_current"])
        c04_curr = C04State(data["c04_current"]) if data.get("c04_current") else None
        rcpts = {k: StateReceipt.from_dict(v) for k, v in data.get("receipts", {}).items()}
        return cls(c03_current=c03_curr, c04_current=c04_curr, receipts=rcpts)
