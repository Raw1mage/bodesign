"""C00–C06 agent registry — the orchestration spine's role/authority source.

Derives each layer's identity (code, key, title, bodesign_role, owner, skills)
from the committed `doc_architecture.template.json` so the registry never drifts
from the document architecture ("題庫 ≡ 文件架構"). Layered on top are the
machine-readable authority rules the human-readable `c00_downstream_contract.md`
only describes in prose: per-layer target_role, allowed/forbidden actions, the
human/external approval gate, and the default return-to-C00 triggers.

C00 is the requirement-contract owner. C01–C06 are downstream worker agents:
they may diagnose, ask scoped follow-ups, draft labeled artifacts, run tools,
and return blockers — but never change product direction, mark human approval,
silently fill missing data, or claim professional sign-off. This module does not
dispatch work or fabricate defaults; it is a declarative lookup validated against
the architecture template.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_ARCHITECTURE_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "doc_architecture.template.json"
)

LAYER_CODES = ["C00", "C01", "C02", "C03", "C04", "C05", "C06"]

# C00 owns the product/requirement contract; the rest are downstream workers.
DOWNSTREAM_CODES = ["C01", "C02", "C03", "C04", "C05", "C06"]

# Machine rules the prose contract (c00_downstream_contract.md) only describes.
# target_role mirrors bodesign.c00.work_packet.v1 `target_role`.
_TARGET_ROLE = {
    "C00": "product",
    "C01": "industrial_design",
    "C02": "mechanical",
    "C03": "electrical",
    "C04": "layout",
    "C05": "firmware",
    "C06": "verification",
}

# The human/external authority that must approve each layer's final output.
_HUMAN_GATE = {
    "C00": "user — product direction, business, legal/compliance, schedule, accepted risk",
    "C01": "ID designer — final aesthetics, CMF samples, brand approval, production ID sign-off",
    "C02": "ME / vendor — final CAD dimensions, tolerance stackup, DFM, STEP/assembly, manufacturing",
    "C03": "EE reviewer + fab — schematic sign-off, part approval, manufacturability",
    "C04": "layout engineer — final placement/routing, stackup, Gerber/fab release",
    "C05": "FW team — firmware code, security/update sign-off (bodesign owns the spec, not the code)",
    "C06": "test lab / EVT-DVT — compliance certification, validation evidence acceptance",
}

# Downstream worker action envelope (from the contract's allowed/forbidden sets).
_DOWNSTREAM_ALLOWED = ["diagnose", "ask_followup", "draft_artifact", "run_tool", "return_blocker"]
_DOWNSTREAM_FORBIDDEN = [
    "change_product_direction",
    "mark_human_approved",
    "silently_fill_missing",
    "claim_professional_signoff",
]
_DOWNSTREAM_RETURN_TRIGGERS = [
    "product decision needed",
    "scope conflict",
    "external approval needed",
    "accepted-risk required",
]

# C00 is the contract owner: it dispatches and ingests, and only the user may
# change product direction or accept risk on its behalf.
_C00_ALLOWED = ["elicit", "draft_assumption", "dispatch_work_packet", "ingest_blocker", "emit_prd"]
_C00_FORBIDDEN = [
    "mark_human_approved",
    "silently_fill_missing",
    "claim_legal_or_certification_compliance",
]


class AgentRegistryError(ValueError):
    """Raised when the registry source is missing, malformed, or inconsistent."""


@dataclass(slots=True)
class AgentRole:
    code: str  # C00..C06
    key: str  # prd/id/me/circuit/layout/fw/verification
    title: str
    bodesign_role: str  # generate / visual-source / constraints / spec / draft+guide / ...
    target_role: str  # work_packet.v1 target_role
    owner: str | None  # external owning team, if any
    is_contract_owner: bool  # True only for C00
    skills: list[str]
    allowed_actions: list[str]
    forbidden_actions: list[str]
    human_gate: str
    return_to_c00_when: list[str]
    # Declarative dispatch backend (F-5): {kind: native|worker|external_mcp, ...}.
    # native/worker → the spine creates a work packet; external_mcp → the spine
    # invokes a per-MCP adapter. This is data, not a hardcoded per-layer branch.
    backend: dict[str, Any] = None  # type: ignore[assignment]

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "key": self.key,
            "title": self.title,
            "bodesign_role": self.bodesign_role,
            "target_role": self.target_role,
            "owner": self.owner,
            "is_contract_owner": self.is_contract_owner,
            "skills": list(self.skills),
            "allowed_actions": list(self.allowed_actions),
            "forbidden_actions": list(self.forbidden_actions),
            "human_gate": self.human_gate,
            "return_to_c00_when": list(self.return_to_c00_when),
            "backend": dict(self.backend or {"kind": "native"}),
        }


@dataclass(slots=True)
class AgentRegistry:
    schema: str
    source_path: str
    roles: list[AgentRole]

    def codes(self) -> list[str]:
        return [r.code for r in self.roles]

    def get(self, code: str) -> AgentRole:
        for role in self.roles:
            if role.code == code:
                return role
        raise AgentRegistryError(f"Unknown layer code: {code!r} (known: {self.codes()})")

    def downstream(self) -> list[AgentRole]:
        return [r for r in self.roles if not r.is_contract_owner]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "source_path": self.source_path,
            "roles": [r.to_dict() for r in self.roles],
        }


def load_agent_registry(path: str | Path | None = None) -> AgentRegistry:
    """Build the C00–C06 registry from the architecture template + contract rules.

    Fails fast (no fallback) if the template is missing, malformed, omits a
    required layer code, or carries an unexpected code.
    """
    template_path = Path(path) if path is not None else DEFAULT_ARCHITECTURE_TEMPLATE_PATH
    if not template_path.exists():
        raise AgentRegistryError(f"Architecture template not found: {template_path}")
    try:
        data = json.loads(template_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise AgentRegistryError(f"Architecture template is not valid JSON: {template_path}: {exc}") from exc

    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        raise AgentRegistryError(f"Architecture template has no `sections`: {template_path}")

    by_code: dict[str, dict[str, Any]] = {}
    for section in sections:
        if not isinstance(section, dict):
            raise AgentRegistryError(f"Architecture section must be an object: {template_path}")
        code = section.get("code")
        if code not in LAYER_CODES:
            raise AgentRegistryError(
                f"Architecture section has unexpected code {code!r} (expected one of {LAYER_CODES})"
            )
        if code in by_code:
            raise AgentRegistryError(f"Duplicate layer code in architecture template: {code}")
        by_code[code] = section

    missing = [c for c in LAYER_CODES if c not in by_code]
    if missing:
        raise AgentRegistryError(f"Architecture template missing layer codes: {missing}")

    roles: list[AgentRole] = []
    for code in LAYER_CODES:
        section = by_code[code]
        key = section.get("key")
        title = section.get("title")
        if not key or not title:
            raise AgentRegistryError(f"Layer {code} missing `key`/`title` in architecture template")
        is_owner = code == "C00"
        backend = section.get("backend") or {"kind": "native"}
        if not isinstance(backend, dict) or backend.get("kind") not in {"native", "worker", "external_mcp"}:
            raise AgentRegistryError(f"Layer {code} has invalid backend {backend!r} (kind must be native|worker|external_mcp)")
        roles.append(
            AgentRole(
                code=code,
                key=key,
                title=title,
                bodesign_role=section.get("bodesign_role") or "unspecified",
                target_role=_TARGET_ROLE[code],
                owner=section.get("owner"),
                is_contract_owner=is_owner,
                skills=list(section.get("skill") or []),
                allowed_actions=list(_C00_ALLOWED if is_owner else _DOWNSTREAM_ALLOWED),
                forbidden_actions=list(_C00_FORBIDDEN if is_owner else _DOWNSTREAM_FORBIDDEN),
                human_gate=_HUMAN_GATE[code],
                return_to_c00_when=[] if is_owner else list(_DOWNSTREAM_RETURN_TRIGGERS),
                backend=dict(backend),
            )
        )

    return AgentRegistry(
        schema="bodesign.agent_registry.v1",
        source_path=str(template_path),
        roles=roles,
    )
