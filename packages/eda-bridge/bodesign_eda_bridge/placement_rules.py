"""Placement rules with mandatory source anchors (DD-5).

Every rule value used by the deterministic pre-placement engine carries its
provenance (patent number / literature id). A rule without a source anchor
must NOT be hardcoded anywhere else — this table is the only place thresholds
live (no-silent-fallback 天條).

Sources (see specs/validation/prd-to-gerber-e2e/research/patent-placement-rules.md):
  R1  US7929315B2  claim 1 (Canon)  — decap→IC power-pin path impedance proxy;
       3.0mm threshold per the post-place-quality-checks knowledge object.
  R4  US9582628B1  claim 1 (Altera) — decap placement order: largest footprint
       first, each placed at the nearest available slot.
  R8  US20090140400A1 (DuPont)      — mid-freq decap effective range = die
       shadow; proxied as the served IC's courtyard bbox expanded by
       die_shadow_margin_mm (no die geometry available).
  R16 US7919840B2 (IBM)             — regulator close to load: attraction
       weight for the SA affinity energy. phase=planned: NOT yet consumed by
       preplace.py — do not claim R16 compliance until it is wired in.
"""
from __future__ import annotations

RULES: dict[str, dict] = {
    "R1": {
        "id": "R1", "source": "US7929315B2", "value": 3.0, "unit": "mm",
        "phase": "check",
        "note": "decap center to served IC power pin max distance (path-impedance proxy)",
    },
    "R4": {
        "id": "R4", "source": "US9582628B1", "value": 1.0, "unit": "order",
        "phase": "generate",
        "note": "decap placement order: largest footprint first, nearest available slot",
    },
    "R8": {
        "id": "R8", "source": "US20090140400A1", "value": 1.0, "unit": "mm",
        "phase": "check",
        "note": "mid-freq (<=100nF) decap must sit inside served IC courtyard bbox "
                "expanded by this margin (die-shadow proxy, DD-6)",
    },
    "R16": {
        "id": "R16", "source": "US7919840B2", "value": 1.0, "unit": "weight",
        "phase": "planned",
        "note": "regulator-near-load attraction weight for the SA affinity energy — "
                "NOT yet consumed by preplace.py (wire before claiming R16)",
    },
}


def get_rule(rule_id: str) -> dict:
    """Fail-fast rule lookup — an unknown rule id is a programming error."""
    if rule_id not in RULES:
        raise KeyError(f"unknown placement rule {rule_id!r}; anchored rules: {sorted(RULES)}")
    return RULES[rule_id]
