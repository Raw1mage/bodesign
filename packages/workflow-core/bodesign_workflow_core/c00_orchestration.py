"""C00 autonomous orchestration loop — the conductor over the spine.

Design: `plans/feature_doc-package-scaffold/c00_orchestration_loop.md`.

A deterministic selector that reads existing runtime state (C00 PRD readiness +
work packets + blockers + the agent registry) and surfaces ONE next step, so C00
guides the non-EE owner through the C00→C06 chain instead of waiting to be driven.

Boundary: it MAY auto-dispatch a scoped work packet (safe, reversible), but NEVER
auto-answers a PRD field, resolves a blocker, or marks approval. Human decisions and
blocker resolutions always return to the user. No fabrication, no fallback.

`c00_orchestration_tick` advances one step (may dispatch); `c00_orchestration_status`
is a read-only board. Both are deterministic: same state → same result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from typing import Callable

from .agent_registry import DOWNSTREAM_CODES, load_agent_registry
from .c00_prd_template import assess_c00_prd_readiness
from .mcp_adapters import AdapterError, build_external_call
from .mode_contracts import enter_c01_mode
from .orchestration import dispatch_work_packet, list_blockers, list_work_packets, return_blocker

_C00_ANSWER_STATE_REL = Path("C00-PRD") / "answer_state.json"

# Blocker severity → preemption priority (lower = handled first).
_SEVERITY_ORDER = {"decision": 0, "accepted-risk-request": 1, "external-needed": 2, "blocked": 3}

# C00 PRD readiness gates downstream layers via combined targets (e.g. "C01/C02"
# from PRD §5). Layers C00 does NOT gate directly (C04 — layout depends on the
# C01 interface + C03 constraints, not on the PRD) become dispatchable once their
# upstream layers are dispatched.
_UPSTREAM_DEPS: dict[str, tuple[str, ...]] = {"C04": ("C01", "C03")}


def _expand_gate_status(gates: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map each downstream code to the C00 gate covering it (gate targets may be
    combined like "C01/C02", which covers both C01 and C02)."""
    per_code: dict[str, dict[str, Any]] = {}
    for target, gate in gates.items():
        for code in str(target).split("/"):
            code = code.strip()
            if code in DOWNSTREAM_CODES:
                per_code[code] = gate
    return per_code


def _dispatchable(code: str, code_gate: dict[str, dict[str, Any]], dispatched: set[str]) -> bool:
    if code in code_gate:
        return code_gate[code].get("status") == "ready"
    deps = _UPSTREAM_DEPS.get(code)
    if deps:
        return all(dep in dispatched for dep in deps)
    return False


@dataclass(slots=True)
class NextAction:
    kind: str  # scaffold_c00 | resolve_blocker | ask_c00 | dispatch | waiting | done
    message: str
    owner: str  # user | downstream_agent | external | none
    question: str | None = None
    layer: str | None = None
    layers: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    dispatched_packet: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "owner": self.owner,
            "question": self.question,
            "layer": self.layer,
            "layers": list(self.layers),
            "evidence": self.evidence,
            "dispatched_packet": self.dispatched_packet,
        }


@dataclass(slots=True)
class LayerBoard:
    code: str
    target_role: str
    gate_status: str  # ready | partial | blocked | unknown
    blocking_sections: list[str]
    dispatched: bool
    packet_id: str | None
    packet_status: str | None
    open_blockers: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "target_role": self.target_role,
            "gate_status": self.gate_status,
            "blocking_sections": list(self.blocking_sections),
            "dispatched": self.dispatched,
            "packet_id": self.packet_id,
            "packet_status": self.packet_status,
            "open_blockers": self.open_blockers,
        }


@dataclass(slots=True)
class Board:
    c00_scaffolded: bool
    c00_status: str | None
    next_question: str | None
    layers: list[LayerBoard]
    open_blocker_count: int
    work_packet_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "c00_scaffolded": self.c00_scaffolded,
            "c00_status": self.c00_status,
            "next_question": self.next_question,
            "layers": [l.to_dict() for l in self.layers],
            "open_blocker_count": self.open_blocker_count,
            "work_packet_count": self.work_packet_count,
        }


def _objective_for(code: str, role_target: str) -> str:
    return (
        f"{code} ({role_target}) work packet dispatched by the C00 orchestration loop: "
        f"produce this layer's draft deliverables/constraints from the satisfied PRD handoff "
        f"sections. Draft only — return product-level decisions to C00 as blockers; no approval."
    )


def _gather(root: Path):
    """Read all runtime state once; returns (scaffolded, readiness, gates, packets, blockers)."""
    scaffolded = (root / _C00_ANSWER_STATE_REL).exists()
    if not scaffolded:
        return False, None, {}, [], []
    readiness = assess_c00_prd_readiness(root)
    raw_gates = {g.get("target"): g for g in readiness.downstream_handoff_gates if g.get("target")}
    code_gate = _expand_gate_status(raw_gates)
    packets = list_work_packets(root)
    blockers = list_blockers(root, unresolved_only=True)
    return True, readiness, code_gate, packets, blockers


def _pick_blocker(blockers):
    return sorted(blockers, key=lambda b: (_SEVERITY_ORDER.get(b.severity, 9), b.blocker_id))[0]


def c00_orchestration_status(folder: str | Path) -> Board:
    """Read-only board: per-layer gate status, dispatch state, and open blockers. Mutates nothing."""
    root = Path(folder).expanduser().resolve()
    scaffolded, readiness, gates, packets, blockers = _gather(root)
    if not scaffolded:
        return Board(False, None, None, [], 0, 0)

    dispatched = {p.target_layer: p for p in packets}
    blockers_by_layer: dict[str, int] = {}
    for b in blockers:
        blockers_by_layer[b.source_layer] = blockers_by_layer.get(b.source_layer, 0) + 1

    registry = load_agent_registry()
    layers: list[LayerBoard] = []
    for role in registry.downstream():
        gate = gates.get(role.code, {})
        pkt = dispatched.get(role.code)
        layers.append(LayerBoard(
            code=role.code,
            target_role=role.target_role,
            gate_status=gate.get("status", "unknown"),
            blocking_sections=list(gate.get("blocking_sections", [])),
            dispatched=pkt is not None,
            packet_id=pkt.packet_id if pkt else None,
            packet_status=pkt.status if pkt else None,
            open_blockers=blockers_by_layer.get(role.code, 0),
        ))
    return Board(
        c00_scaffolded=True,
        c00_status=readiness.status,
        next_question=readiness.next_question or None,
        layers=layers,
        open_blocker_count=len(blockers),
        work_packet_count=len(packets),
    )


def _dispatch_external_mcp(root, code, role, packet, mcp_caller) -> NextAction:
    """Dispatch a layer whose backend is an external MCP server (F-5). Calls the
    declared adapter → mcp_caller; records the result, or a blocker when the external
    MCP is unreachable/unconfigured (never fabricates the layer's output)."""
    backend = role.backend or {}
    server = backend.get("server", "?")
    base_ev = {"packet_id": packet["packet_id"], "backend": "external_mcp", "server": server}
    if mcp_caller is None:
        return NextAction(kind="dispatch", owner="downstream_agent", layer=code, dispatched_packet=packet,
                          message=f"Dispatched {code}; backend is external MCP '{server}', but no MCP caller is wired in this context.",
                          evidence={**base_ev, "mcp_caller": "unwired"})
    try:
        call = build_external_call(backend.get("adapter", ""), packet, root)
    except AdapterError as error:
        blk = return_blocker(root, packet["packet_id"], severity="blocked",
                             summary=f"{code} external MCP backend has no usable adapter.",
                             question_for_user=f"Register an adapter for the '{server}' MCP backend of {code}.",
                             recommended_owner="downstream_agent", proposed_state="blocked")
        return NextAction(kind="dispatch", owner="downstream_agent", layer=code, dispatched_packet=packet,
                          message=f"Dispatched {code} but its external MCP adapter is missing ({error}); recorded a blocker.",
                          evidence={**base_ev, "blocker_id": blk.blocker_id})
    result = mcp_caller(call["server"], call["tool"], call["arguments"]) or {}
    if not result.get("ok") and (result.get("worker_unavailable") or result.get("worker_starting")):
        blk = return_blocker(root, packet["packet_id"], severity="external-needed",
                             summary=f"{code} external MCP '{call['server']}' is {result.get('status', 'unreachable')}.",
                             question_for_user=f"Bring up / configure the '{call['server']}' MCP server, then re-dispatch {code}.",
                             recommended_owner="external_expert", proposed_state="external-needed")
        return NextAction(kind="dispatch", owner="external", layer=code, dispatched_packet=packet,
                          message=f"Dispatched {code} to external MCP '{call['server']}' but it is {result.get('status')}; recorded a blocker.",
                          evidence={**base_ev, "tool": call["tool"], "external_status": result.get("status"), "blocker_id": blk.blocker_id})
    return NextAction(kind="dispatch", owner="downstream_agent", layer=code, dispatched_packet=packet,
                      message=f"Dispatched {code} to external MCP '{call['server']}' (tool {call['tool']}); result recorded.",
                      evidence={**base_ev, "tool": call["tool"], "external_ok": bool(result.get("ok"))})


def c00_orchestration_tick(folder: str | Path, *, auto_dispatch: bool = True,
                           mcp_caller: Callable[..., dict] | None = None) -> NextAction:
    """Return the single highest-value next step; may dispatch a ready layer.

    Priority: resolve_blocker → ask_c00 (to unblock a gate) → dispatch a ready,
    undispatched layer → ask_c00 (advance the PRD) → waiting → done. Never answers a
    PRD field, resolves a blocker, or marks approval. Set auto_dispatch=False for a
    recommendation without performing the dispatch.
    """
    root = Path(folder).expanduser().resolve()
    scaffolded, readiness, gates, packets, blockers = _gather(root)

    # 0. C00 not scaffolded yet.
    if not scaffolded:
        return NextAction(
            kind="scaffold_c00", owner="user",
            message="No C00 PRD exists yet. Scaffold C00 first (bodesign_c00_scaffold_prd), then start answering.",
        )

    dispatched_layers = {p.target_layer for p in packets}

    # 1. Unresolved blocker preempts everything — the user owes a decision.
    if blockers:
        b = _pick_blocker(blockers)
        return NextAction(
            kind="resolve_blocker", owner=b.recommended_owner or "user",
            question=b.question_for_user, layer=b.source_layer,
            message=f"{b.source_layer} returned a {b.severity} blocker. Resolve it via bodesign_ingest_blocker before advancing.",
            evidence={"blocker_id": b.blocker_id, "severity": b.severity,
                      "affected_c00_fields": list(b.affected_c00_fields)},
        )

    next_q = readiness.next_question or None
    blocked_gates = [code for code, g in gates.items() if g.get("status") == "blocked"]

    # 2. Ask the C00 PRD question that unblocks a blocked downstream gate.
    if next_q and blocked_gates:
        return NextAction(
            kind="ask_c00", owner="user", question=next_q, layers=sorted(blocked_gates),
            message=f"Answer this C00 PRD question — it unblocks {', '.join(sorted(blocked_gates))}.",
            evidence={"blocking_gates": sorted(blocked_gates)},
        )

    # 3. Dispatch a dispatchable, not-yet-dispatched downstream layer (C01..C06 order).
    ready_undispatched = [
        code for code in DOWNSTREAM_CODES
        if code not in dispatched_layers and _dispatchable(code, gates, dispatched_layers)
    ]
    if ready_undispatched:
        code = ready_undispatched[0]
        role = load_agent_registry().get(code)
        backend_kind = (role.backend or {}).get("kind", "native")
        if not auto_dispatch:
            return NextAction(
                kind="dispatch", owner="downstream_agent", layer=code,
                message=f"{code} ({role.target_role}) is ready to dispatch (gate satisfied, backend={backend_kind}). Recommendation only — auto_dispatch is off.",
                evidence={"gate_status": "ready", "backend": backend_kind, "dry_run": True},
            )
        # C01 has a dedicated mode contract; otherwise create the work packet for traceability.
        if code == "C01" and backend_kind != "external_mcp":
            packet = enter_c01_mode(root).packet
        else:
            packet = dispatch_work_packet(
                root, code, _objective_for(code, role.target_role),
                sections=list(gates.get(code, {}).get("source_sections", [])),
            ).to_dict()
        # One declarative branch on the backend kind (no per-layer hardcoding).
        if backend_kind == "external_mcp":
            return _dispatch_external_mcp(root, code, role, packet, mcp_caller)
        return NextAction(
            kind="dispatch", owner="downstream_agent", layer=code,
            message=f"Dispatched {code} ({role.target_role}); its gate is satisfied. It will draft deliverables and return any blockers to C00.",
            evidence={"packet_id": packet.get("packet_id"), "backend": backend_kind}, dispatched_packet=packet,
        )

    # 4. All layers dispatched and no open blockers → the loop's job is done.
    undispatched_downstream = [
        code for code in DOWNSTREAM_CODES if code not in dispatched_layers
    ]
    if not undispatched_downstream:
        return NextAction(
            kind="done", owner="none",
            message="All downstream layers are dispatched with no open blockers. "
                    "Review per-layer deliverables; final ID/ME/EE/FW/approval gates remain human/vendor owned.",
            evidence={"dispatched": sorted(dispatched_layers)},
        )

    # 5. Keep deepening the PRD to unlock the remaining (partial) gates.
    if next_q:
        return NextAction(
            kind="ask_c00", owner="user", question=next_q,
            message="Deepen the C00 PRD with the next highest-value question to unlock the remaining layers.",
        )

    # 6. Nothing actionable by the user right now — downstream/partial in flight.
    partial_gates = [code for code, g in gates.items() if g.get("status") == "partial"]
    return NextAction(
        kind="waiting", owner="user" if partial_gates else "downstream_agent",
        layers=sorted(undispatched_downstream),
        message=(
            "Downstream layers are in flight. "
            + (f"Gates still partial (need PRD fields approved, not just drafted): {', '.join(sorted(partial_gates))}. "
               if partial_gates else "")
            + f"Not yet dispatchable: {', '.join(sorted(undispatched_downstream)) or 'none'}."
        ),
        evidence={"partial_gates": sorted(partial_gates), "undispatched": sorted(undispatched_downstream)},
    )
