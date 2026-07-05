"""DoD refs-traceback verification (EPIC refs-derived-design, 切面 5).

The paradigm inversion's acceptance gate. bodesign's existing DoD check
(guide_dod.py) verifies a deliverable FILE EXISTS. That is surface-existence: it
cannot catch an agent who fabricated placement coordinates / component picks with
no design root, because a fabricated file still "exists". 切面 5 upgrades the DoD
from existence to TRACEABILITY: every delivered coordinate / pin / component must
trace back to an SSOT anchor, and every SSOT-required item must actually appear in
the deliverable. Two failure directions, both BLOCKING:

  * untraceable[]  — a delivered item carries no SSOT provenance anchor (憑空發明,
                     天條 2 no-fabrication). This is what caught the original bug:
                     U1@(18,16) invented with no ref to any 01_refs/ SSOT.
  * unfulfilled[]  — an SSOT-required item is absent from the deliverable (漏做).
                     e.g. the SSOT lists WiFi/BT/PHY/IMU but the board omits them.

Either non-empty ⇒ DOD_TRACEBACK_FAILED (blocking). Pure-python, deterministic,
core-side; the LLM never adjudicates — the traceback is a mechanical set/anchor
comparison.

Data taxonomy (BINDING):
  * DeliverableItem — one delivered coordinate/pin/component. input: {ref,
                      provenance?}. A missing/empty provenance ⇒ untraceable.
  * SsotIndex       — the set of SSOT-required refs (what the design MUST cover).
  * TracebackReport — {dod_ok, blocking, untraceable[], unfulfilled[], traced[]}.
                      dod_ok IFF untraceable AND unfulfilled are both empty.
  * dod_refs_traceback — the checker. Done IFF it has classified every
                      deliverable item and every SSOT-required ref.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DOD_TRACEBACK_FAILED = "DOD_TRACEBACK_FAILED"
DOD_TRACEBACK_SCHEMA = "bodesign.c04.dod_traceback.v1"


@dataclass(slots=True)
class TracebackReport:
    schema: str
    dod_ok: bool
    blocking: bool
    traced: list[dict[str, Any]]
    untraceable: list[dict[str, Any]]
    unfulfilled: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "dod_ok": self.dod_ok,
            "blocking": self.blocking,
            "traced_count": len(self.traced),
            "traced": list(self.traced),
            "untraceable": list(self.untraceable),
            "untraceable_count": len(self.untraceable),
            "unfulfilled": list(self.unfulfilled),
            "unfulfilled_count": len(self.unfulfilled),
            "warnings": list(self.warnings),
        }


def _provenance_traces(provenance: Any, ssot_anchors: set[str] | None) -> bool:
    """A provenance anchor is valid IFF it is a non-empty string AND — when an
    explicit ssot_anchors allowlist is given — its source-file part is in it.

    provenance form: ``<ssot_file>:<locator>`` (e.g. "C03_元件與腳位SSOT.md:L12").
    With no allowlist, any non-empty provenance is accepted (the caller trusts
    the anchor text); with an allowlist, the file part must match a known SSOT.
    """
    if not isinstance(provenance, str) or not provenance.strip():
        return False
    if ssot_anchors is None:
        return True
    src = provenance.split(":", 1)[0].strip()
    return src in ssot_anchors


def dod_refs_traceback(
    deliverable_items: list[dict[str, Any]],
    ssot_required_refs: list[str],
    *,
    ssot_anchors: list[str] | None = None,
) -> TracebackReport:
    """Upgrade the DoD from surface-existence to SSOT traceability (切面 5).

    Args:
      deliverable_items: [{ref, provenance?}] — every delivered component/pin/coord.
      ssot_required_refs: the refs the SSOT REQUIRES the design to cover.
      ssot_anchors: optional allowlist of valid SSOT source-file names; when given,
        a provenance whose source file is not in it does NOT count as traced.

    Returns a TracebackReport. dod_ok IFF nothing is untraceable AND nothing is
    unfulfilled. Deterministic; no LLM. Never a silent pass.
    """
    anchors = set(ssot_anchors) if ssot_anchors is not None else None
    required = list(dict.fromkeys(ssot_required_refs))  # stable-dedup

    traced: list[dict[str, Any]] = []
    untraceable: list[dict[str, Any]] = []
    delivered_refs: set[str] = set()

    for item in deliverable_items:
        ref = str(item.get("ref", "")).strip()
        provenance = item.get("provenance")
        if ref:
            delivered_refs.add(ref)
        if _provenance_traces(provenance, anchors):
            traced.append({"ref": ref, "provenance": provenance})
        else:
            untraceable.append({
                "ref": ref or "<unnamed>",
                "reason": "no SSOT provenance anchor (憑空發明, 天條 2)"
                if not provenance else "provenance does not resolve to a known SSOT source",
                "provenance": provenance,
            })

    # coverage: SSOT-required refs absent from the deliverable (漏做).
    unfulfilled = [ref for ref in required if ref not in delivered_refs]

    blocking = bool(untraceable or unfulfilled)
    return TracebackReport(
        schema=DOD_TRACEBACK_SCHEMA,
        dod_ok=not blocking,
        blocking=blocking,
        traced=traced,
        untraceable=untraceable,
        unfulfilled=unfulfilled,
    )
