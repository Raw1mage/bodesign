"""Net-role helpers: explicit-supply mapping, provenance invariant, role-aware query.

Role is a first-class, closed-enum property of a Net supplied EXPLICITLY from the
upstream schematic net-class or user annotation. It is NEVER inferred from the net
name (no-fabrication). A role without provenance is rejected; an unknown net-class
resolves to None (no heuristic fallback).
"""

from __future__ import annotations

from bodesign_shared import EvidenceRef

from .contracts import NET_ROLES, BoardDesign, Net, NetRole


def set_net_role(net: Net, role: NetRole | None, evidence: EvidenceRef | None) -> Net:
    """Set role + provenance on a Net, enforcing the grounding invariant.

    - role is None            -> clears role and role_evidence (roleless net).
    - role in NET_ROLES       -> requires a non-None EvidenceRef, else ValueError
                                 (ROLE_PROVENANCE_MISSING). Sets both fields.
    - role out of closed enum -> leaves role None (fail-fast, no-guess); does NOT raise
                                 on this path so a bad net-class token cannot smuggle in.
    """
    if role is None:
        net.role = None
        net.role_evidence = None
        return net
    if role not in NET_ROLES:
        # Out-of-enum token: no-guess. Leave roleless rather than fabricate.
        net.role = None
        net.role_evidence = None
        return net
    if evidence is None:
        raise ValueError("role requires role_evidence provenance")
    net.role = role
    net.role_evidence = evidence
    return net


def map_netclass_to_role(
    netclass: str | None,
    table: dict[str, NetRole],
) -> NetRole | None:
    """Deterministically map a schematic net-class label to a role via an explicit table.

    Zero net-name heuristic, zero LLM. A net-class absent from the table (or a net with
    no class) resolves to None \u2014 the caller then leaves the net roleless (no-fabrication).
    Values in the table that are not valid roles resolve to None as well.
    """
    if netclass is None:
        return None
    role = table.get(netclass)
    if role is None or role not in NET_ROLES:
        return None
    return role


def nets_with_role(design: BoardDesign, role: NetRole) -> list[Net]:
    """Return the subset of design.nets whose role == role.

    Nets with role None are ALWAYS excluded. An unknown role token raises ValueError
    (ROLE_QUERY_UNKNOWN_ROLE). Pure-python, deterministic (byte-identical for identical
    input): preserves design.nets ordering.
    """
    if role not in NET_ROLES:
        raise ValueError(f"unknown role: {role}")
    return [net for net in design.nets if net.role == role]
