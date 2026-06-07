"""Orchestration spine — C00 dispatch / downstream blocker backflow runtime.

Implements the `bodesign.c00.work_packet.v1` and `bodesign.c00.blocker_return.v1`
schemas drafted in `c00_downstream_contract.md` as real, persisted runtime state,
plus the folder/state model that ties the 15 Cxx tools into a driven workflow.

Boundary (enforced, not advisory):
- C00 is the requirement-contract owner: only C00 dispatches work packets and
  ingests blockers. Work packets target C01–C06 (never C00 itself).
- Downstream layers may return blockers; product-direction changes flow back to
  C00, never the reverse. Authority comes from `agent_registry` — a dispatched
  packet inherits its target layer's allowed/forbidden actions and return triggers.
- No fallback / no silent fill: unknown layers, bad severities/owners/states, and
  malformed persisted state fail fast.

Folder/state model (under the client project root):

    <folder>/_orchestration/
        work_packets/<packet_id>.json   # bodesign.c00.work_packet.v1
        blockers/<blocker_id>.json      # bodesign.c00.blocker_return.v1
        log.jsonl                       # append-only dispatch/return/ingest events

IDs are deterministic and timestamp-free (count-based) so runs are reproducible:
work packets are `C00-WP-0001…`, blockers are `<LAYER>-BLOCK-0001…`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .agent_registry import DOWNSTREAM_CODES, AgentRegistry, load_agent_registry

WORK_PACKET_SCHEMA = "bodesign.c00.work_packet.v1"
BLOCKER_RETURN_SCHEMA = "bodesign.c00.blocker_return.v1"

ORCH_REL_DIR = Path("_orchestration")
_WP_REL_DIR = ORCH_REL_DIR / "work_packets"
_BLOCKER_REL_DIR = ORCH_REL_DIR / "blockers"
_LOG_REL_PATH = ORCH_REL_DIR / "log.jsonl"

# Default C00 source pointers (mirror the contract's `source` block).
_DEFAULT_C00_FOLDER = "C00-PRD"
_DEFAULT_ANSWER_STATE = "C00-PRD/answer_state.json"

_INPUT_BUCKETS = ["answered", "drafted", "accepted_risks", "external_needed", "blocked"]
_SEVERITIES = {"decision", "external-needed", "blocked", "accepted-risk-request"}
_OWNERS = {"user", "external_expert", "downstream_agent", "ai_draft"}
_PROPOSED_STATES = {"missing", "drafted", "answered", "external-needed", "blocked", "accepted-risk"}


class OrchestrationError(ValueError):
    """Raised on contract violations or malformed/inconsistent orchestration state."""


# ── Dataclasses ────────────────────────────────────────────────────────


@dataclass(slots=True)
class WorkPacket:
    packet_id: str
    target_layer: str
    target_role: str
    objective: str
    source: dict[str, Any]
    inputs: dict[str, list[Any]]
    allowed_actions: list[str]
    forbidden_actions: list[str]
    expected_outputs: list[str]
    return_to_c00_when: list[str]
    status: str  # ready | partial | blocked
    schema: str = WORK_PACKET_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "packet_id": self.packet_id,
            "target_layer": self.target_layer,
            "target_role": self.target_role,
            "objective": self.objective,
            "source": self.source,
            "inputs": self.inputs,
            "allowed_actions": list(self.allowed_actions),
            "forbidden_actions": list(self.forbidden_actions),
            "expected_outputs": list(self.expected_outputs),
            "return_to_c00_when": list(self.return_to_c00_when),
            "status": self.status,
        }


@dataclass(slots=True)
class BlockerReturn:
    blocker_id: str
    packet_id: str
    source_layer: str
    severity: str
    summary: str
    question_for_user: str
    evidence: dict[str, list[Any]]
    affected_c00_fields: list[str]
    affected_downstream_layers: list[str]
    options: list[Any]
    recommended_owner: str
    proposed_state: str
    resolved: bool = False
    resolution: dict[str, Any] | None = None
    schema: str = BLOCKER_RETURN_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "blocker_id": self.blocker_id,
            "packet_id": self.packet_id,
            "source_layer": self.source_layer,
            "severity": self.severity,
            "summary": self.summary,
            "question_for_user": self.question_for_user,
            "evidence": self.evidence,
            "affected_c00_fields": list(self.affected_c00_fields),
            "affected_downstream_layers": list(self.affected_downstream_layers),
            "options": list(self.options),
            "recommended_owner": self.recommended_owner,
            "proposed_state": self.proposed_state,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


@dataclass(slots=True)
class IngestResult:
    blocker_id: str
    packet_id: str
    resolved: bool
    proposed_state: str
    affected_c00_fields: list[str]
    note: str
    resolution: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocker_id": self.blocker_id,
            "packet_id": self.packet_id,
            "resolved": self.resolved,
            "proposed_state": self.proposed_state,
            "affected_c00_fields": list(self.affected_c00_fields),
            "note": self.note,
            "resolution": self.resolution,
        }


# ── Persistence helpers ────────────────────────────────────────────────


def _orch_root(folder: str | Path) -> Path:
    return Path(folder).expanduser().resolve()


def _ensure_dirs(root: Path) -> None:
    (root / _WP_REL_DIR).mkdir(parents=True, exist_ok=True)
    (root / _BLOCKER_REL_DIR).mkdir(parents=True, exist_ok=True)


def _normalize_inputs(inputs: dict[str, Any] | None) -> dict[str, list[Any]]:
    result = {bucket: [] for bucket in _INPUT_BUCKETS}
    if inputs is None:
        return result
    if not isinstance(inputs, dict):
        raise OrchestrationError("work packet `inputs` must be an object")
    for key, value in inputs.items():
        if key not in _INPUT_BUCKETS:
            raise OrchestrationError(f"unknown work packet input bucket: {key!r} (allowed: {_INPUT_BUCKETS})")
        if not isinstance(value, list):
            raise OrchestrationError(f"work packet input `{key}` must be a list")
        result[key] = list(value)
    return result


def _status_for_inputs(inputs: dict[str, list[Any]]) -> str:
    if inputs["blocked"]:
        return "blocked"
    if inputs["external_needed"]:
        return "partial"
    return "ready"


def _next_packet_id(root: Path) -> str:
    existing = sorted((root / _WP_REL_DIR).glob("C00-WP-*.json")) if (root / _WP_REL_DIR).exists() else []
    return f"C00-WP-{len(existing) + 1:04d}"


def _next_blocker_id(root: Path, source_layer: str) -> str:
    prefix = f"{source_layer}-BLOCK-"
    existing = (
        sorted((root / _BLOCKER_REL_DIR).glob(f"{prefix}*.json"))
        if (root / _BLOCKER_REL_DIR).exists()
        else []
    )
    return f"{prefix}{len(existing) + 1:04d}"


def _append_log(root: Path, event: dict[str, Any]) -> None:
    _ensure_dirs(root)
    with (root / _LOG_REL_PATH).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _read_json(path: Path, expected_schema: str) -> dict[str, Any]:
    if not path.exists():
        raise OrchestrationError(f"not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != expected_schema:
        raise OrchestrationError(f"unsupported schema in {path}: {data.get('schema')!r} (expected {expected_schema})")
    return data


# ── Dispatch (C00 → C01–C06) ───────────────────────────────────────────


def dispatch_work_packet(
    folder: str | Path,
    target_layer: str,
    objective: str,
    *,
    sections: list[str] | None = None,
    fields: list[str] | None = None,
    generated_docs: list[str] | None = None,
    inputs: dict[str, Any] | None = None,
    expected_outputs: list[str] | None = None,
    registry: AgentRegistry | None = None,
) -> WorkPacket:
    """C00 dispatches a scoped work packet to a downstream layer.

    The packet inherits the target layer's authority (allowed/forbidden actions,
    return triggers) from the agent registry. Targeting C00 itself, an unknown
    layer, or omitting an objective fails fast.
    """
    if not objective or not objective.strip():
        raise OrchestrationError("work packet requires a non-empty `objective`")
    if target_layer not in DOWNSTREAM_CODES:
        raise OrchestrationError(
            f"cannot dispatch to {target_layer!r}; work packets target downstream layers {DOWNSTREAM_CODES}"
        )
    reg = registry or load_agent_registry()
    role = reg.get(target_layer)
    root = _orch_root(folder)
    _ensure_dirs(root)

    norm_inputs = _normalize_inputs(inputs)
    packet = WorkPacket(
        packet_id=_next_packet_id(root),
        target_layer=target_layer,
        target_role=role.target_role,
        objective=objective.strip(),
        source={
            "c00_folder": _DEFAULT_C00_FOLDER,
            "answer_state_path": _DEFAULT_ANSWER_STATE,
            "sections": list(sections or []),
            "fields": list(fields or []),
            "generated_docs": list(generated_docs or []),
        },
        inputs=norm_inputs,
        allowed_actions=list(role.allowed_actions),
        forbidden_actions=list(role.forbidden_actions),
        expected_outputs=list(expected_outputs or []),
        return_to_c00_when=list(role.return_to_c00_when),
        status=_status_for_inputs(norm_inputs),
    )
    (root / _WP_REL_DIR / f"{packet.packet_id}.json").write_text(
        json.dumps(packet.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _append_log(root, {"event": "dispatch", "packet_id": packet.packet_id, "target_layer": target_layer, "status": packet.status})
    return packet


def _packet_from_data(data: dict[str, Any]) -> WorkPacket:
    return WorkPacket(
        packet_id=data["packet_id"],
        target_layer=data["target_layer"],
        target_role=data.get("target_role", ""),
        objective=data.get("objective", ""),
        source=data.get("source", {}),
        inputs=data.get("inputs", {b: [] for b in _INPUT_BUCKETS}),
        allowed_actions=data.get("allowed_actions", []),
        forbidden_actions=data.get("forbidden_actions", []),
        expected_outputs=data.get("expected_outputs", []),
        return_to_c00_when=data.get("return_to_c00_when", []),
        status=data.get("status", "ready"),
    )


def get_work_packet(folder: str | Path, packet_id: str) -> WorkPacket:
    root = _orch_root(folder)
    return _packet_from_data(_read_json(root / _WP_REL_DIR / f"{packet_id}.json", WORK_PACKET_SCHEMA))


def list_work_packets(folder: str | Path) -> list[WorkPacket]:
    root = _orch_root(folder)
    wp_dir = root / _WP_REL_DIR
    if not wp_dir.exists():
        return []
    return [_packet_from_data(_read_json(p, WORK_PACKET_SCHEMA)) for p in sorted(wp_dir.glob("C00-WP-*.json"))]


# ── Blocker backflow (C01–C06 → C00) ───────────────────────────────────


def return_blocker(
    folder: str | Path,
    packet_id: str,
    *,
    severity: str,
    summary: str,
    question_for_user: str,
    affected_c00_fields: list[str] | None = None,
    affected_downstream_layers: list[str] | None = None,
    options: list[Any] | None = None,
    recommended_owner: str = "user",
    proposed_state: str = "blocked",
    evidence: dict[str, Any] | None = None,
) -> BlockerReturn:
    """A downstream layer returns a blocker against its work packet to C00.

    The blocker's source layer is taken from the referenced packet (a layer can
    only block work it was actually assigned). Marks the packet `blocked`.
    """
    if severity not in _SEVERITIES:
        raise OrchestrationError(f"invalid severity {severity!r} (allowed: {sorted(_SEVERITIES)})")
    if recommended_owner not in _OWNERS:
        raise OrchestrationError(f"invalid recommended_owner {recommended_owner!r} (allowed: {sorted(_OWNERS)})")
    if proposed_state not in _PROPOSED_STATES:
        raise OrchestrationError(f"invalid proposed_state {proposed_state!r} (allowed: {sorted(_PROPOSED_STATES)})")
    if not summary.strip() or not question_for_user.strip():
        raise OrchestrationError("blocker requires non-empty `summary` and `question_for_user`")

    root = _orch_root(folder)
    packet = get_work_packet(root, packet_id)  # fails fast if the packet does not exist
    _ensure_dirs(root)

    norm_evidence = {"artifact_paths": [], "field_refs": [], "tool_results": []}
    if evidence is not None:
        if not isinstance(evidence, dict):
            raise OrchestrationError("blocker `evidence` must be an object")
        for key, value in evidence.items():
            if key not in norm_evidence:
                raise OrchestrationError(f"unknown evidence bucket {key!r} (allowed: {list(norm_evidence)})")
            if not isinstance(value, list):
                raise OrchestrationError(f"blocker evidence `{key}` must be a list")
            norm_evidence[key] = list(value)

    blocker = BlockerReturn(
        blocker_id=_next_blocker_id(root, packet.target_layer),
        packet_id=packet_id,
        source_layer=packet.target_layer,
        severity=severity,
        summary=summary.strip(),
        question_for_user=question_for_user.strip(),
        evidence=norm_evidence,
        affected_c00_fields=list(affected_c00_fields or []),
        affected_downstream_layers=list(affected_downstream_layers or []),
        options=list(options or []),
        recommended_owner=recommended_owner,
        proposed_state=proposed_state,
    )
    (root / _BLOCKER_REL_DIR / f"{blocker.blocker_id}.json").write_text(
        json.dumps(blocker.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Mark the originating packet blocked.
    packet.status = "blocked"
    (root / _WP_REL_DIR / f"{packet_id}.json").write_text(
        json.dumps(packet.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _append_log(root, {"event": "blocker_returned", "blocker_id": blocker.blocker_id, "packet_id": packet_id, "source_layer": packet.target_layer, "severity": severity})
    return blocker


def _blocker_from_data(data: dict[str, Any]) -> BlockerReturn:
    return BlockerReturn(
        blocker_id=data["blocker_id"],
        packet_id=data["packet_id"],
        source_layer=data["source_layer"],
        severity=data["severity"],
        summary=data.get("summary", ""),
        question_for_user=data.get("question_for_user", ""),
        evidence=data.get("evidence", {}),
        affected_c00_fields=data.get("affected_c00_fields", []),
        affected_downstream_layers=data.get("affected_downstream_layers", []),
        options=data.get("options", []),
        recommended_owner=data.get("recommended_owner", "user"),
        proposed_state=data.get("proposed_state", "blocked"),
        resolved=data.get("resolved", False),
        resolution=data.get("resolution"),
    )


def get_blocker(folder: str | Path, blocker_id: str) -> BlockerReturn:
    root = _orch_root(folder)
    return _blocker_from_data(_read_json(root / _BLOCKER_REL_DIR / f"{blocker_id}.json", BLOCKER_RETURN_SCHEMA))


def list_blockers(folder: str | Path, *, unresolved_only: bool = False) -> list[BlockerReturn]:
    root = _orch_root(folder)
    b_dir = root / _BLOCKER_REL_DIR
    if not b_dir.exists():
        return []
    blockers = [_blocker_from_data(_read_json(p, BLOCKER_RETURN_SCHEMA)) for p in sorted(b_dir.glob("*-BLOCK-*.json"))]
    return [b for b in blockers if not b.resolved] if unresolved_only else blockers


def ingest_blocker(
    folder: str | Path,
    blocker_id: str,
    *,
    resolved_state: str,
    decision: str,
    decided_by: str = "user",
) -> IngestResult:
    """C00 records the human/owner resolution of a blocker and closes it.

    This does NOT silently mutate the C00 answer-state — it records the decision
    and the C00 field-state it maps to; applying it to the PRD remains C00's
    explicit emit/update step. `resolved_state` must be a valid answer-state and
    `decision` must be non-empty (no empty/auto resolutions).
    """
    if resolved_state not in _PROPOSED_STATES:
        raise OrchestrationError(f"invalid resolved_state {resolved_state!r} (allowed: {sorted(_PROPOSED_STATES)})")
    if not decision or not decision.strip():
        raise OrchestrationError("ingest requires a non-empty `decision` (no silent/auto resolution)")
    if decided_by not in _OWNERS:
        raise OrchestrationError(f"invalid decided_by {decided_by!r} (allowed: {sorted(_OWNERS)})")

    root = _orch_root(folder)
    blocker = get_blocker(root, blocker_id)
    if blocker.resolved:
        raise OrchestrationError(f"blocker {blocker_id} is already resolved")

    blocker.resolved = True
    blocker.resolution = {"resolved_state": resolved_state, "decision": decision.strip(), "decided_by": decided_by}
    (root / _BLOCKER_REL_DIR / f"{blocker_id}.json").write_text(
        json.dumps(blocker.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _append_log(root, {"event": "blocker_ingested", "blocker_id": blocker_id, "resolved_state": resolved_state, "decided_by": decided_by})
    note = (
        f"Recorded resolution for {blocker_id}; map C00 field(s) "
        f"{blocker.affected_c00_fields or '[unspecified]'} to state '{resolved_state}'. "
        "Apply via the C00 PRD update/emit step — ingest does not mutate answer_state."
    )
    return IngestResult(
        blocker_id=blocker_id,
        packet_id=blocker.packet_id,
        resolved=True,
        proposed_state=resolved_state,
        affected_c00_fields=list(blocker.affected_c00_fields),
        note=note,
        resolution=blocker.resolution,
    )
