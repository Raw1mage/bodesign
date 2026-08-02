"""Constraint provenance taxonomy (plan capability_refs-first-emitters, DD-2).

Every C01/C02 constraint item carries a ``provenance`` dict declaring where it
came from. Only owner-grounded kinds pass the readiness dod gate; anything the
emitter inferred stays VISIBLE but can never silently satisfy DoD (天條 1/2).

Taxonomy (BINDING):
  * kind="refs"    — item traces to a file under the stage's ``01_refs/`` SSOT.
                     source = path relative to 01_refs/; detail = anchor
                     (heading / line hint). Passes the gate IFF the source
                     resolves to a real path INSIDE 01_refs/ (traversal and
                     symlink escapes rejected; no folder to check → fail closed).
  * kind="answer"  — the user answered the field via answer_state.json.
                     source = "answer_state.json"; detail = field key.
                     Owner input by definition → passes the gate.
  * kind="derived" — the emitter inferred it (keyword corpus, unattributed
                     caller dict). source = derivation label ("c00_corpus" /
                     "caller_unattributed"); detail = matched keyword / reason.
                     NEVER passes the gate; surfaces as a provenance gap.

An item with no provenance at all (legacy v1 files) is a
``provenance_missing`` gap — old artifacts are not silently whitewashed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

PROVENANCE_KINDS = ("refs", "answer", "derived")
GATE_PASSING_KINDS = ("refs", "answer")

KIND_REFS = "refs"
KIND_ANSWER = "answer"
KIND_DERIVED = "derived"

REFS_DIRNAME = "01_refs"


def make_provenance(kind: str, source: str, detail: str = "") -> dict[str, str]:
    """Build a provenance dict; unknown kind is a programming error (fail fast)."""
    if kind not in PROVENANCE_KINDS:
        raise ValueError(f"unknown provenance kind {kind!r} (allowed: {PROVENANCE_KINDS})")
    return {"kind": kind, "source": str(source), "detail": str(detail)}


def _refs_source_resolves(source: str, *, stage_dir: Path) -> bool:
    if not source:
        return False
    candidate = Path(source)
    if candidate.is_absolute():
        return False  # refs sources are 01_refs-relative by contract
    refs_root = (stage_dir / REFS_DIRNAME).resolve()
    try:
        resolved = (refs_root / candidate).resolve(strict=True)
    except OSError:
        return False
    # Containment check (review F2): `../` traversal or a symlink pointing
    # outside 01_refs/ must not count as an owner-grounded SSOT source.
    return resolved.is_relative_to(refs_root)


def provenance_gap_for(
    item_name: str,
    provenance: Any,
    *,
    stage_dir: str | Path | None = None,
) -> dict[str, str] | None:
    """Adjudicate one item's provenance. Returns a gap dict or None (passes).

    ``stage_dir`` is the OWNING STAGE's directory (e.g. ``<product>/C02-ME``),
    NOT the product root: ``01_refs/`` is a per-stage bucket by the
    stage-structure contract. It is keyword-only and named for what it is
    because the bug this fixes (BR_20260719 c02) was exactly a ``Path`` argument
    whose meaning differed between two code paths while the type stayed the
    same — a positional ``folder`` let a product root be passed where a stage
    dir was expected, and nothing could detect it.

    Gap reasons (errors.md):
      * provenance_missing        — no/invalid provenance dict (legacy v1)
      * kind_derived              — emitter-inferred, needs owner grounding
      * refs_source_unresolvable  — kind=refs but source does not resolve to a
        real path INSIDE <stage_dir>/01_refs/ (traversal/symlink escapes rejected).
        With no stage_dir to resolve against, the claim fails CLOSED (review F3):
        an unverifiable refs claim never passes the gate.
    """
    if not isinstance(provenance, dict) or provenance.get("kind") not in PROVENANCE_KINDS:
        return {
            "item": item_name,
            "reason": "provenance_missing",
            "fix": "re-emit with the current emitter (v2 schema) or attribute the item to an 01_refs/ source",
        }
    kind = provenance["kind"]
    if kind == KIND_DERIVED:
        return {
            "item": item_name,
            "reason": "kind_derived",
            "fix": f"answer the owning field or add an 01_refs/ source for '{item_name}', then re-emit "
                   f"(derived from: {provenance.get('source', '?')}/{provenance.get('detail', '?')})",
        }
    if kind == KIND_REFS:
        source = str(provenance.get("source") or "")
        if stage_dir is None:
            return {
                "item": item_name,
                "reason": "refs_source_unresolvable",
                "fix": f"refs provenance ({source!r}) cannot be verified without the owning stage dir; "
                       "re-run the adjudication with stage_dir= (fail-closed, no weak mode)",
            }
        if not _refs_source_resolves(source, stage_dir=Path(stage_dir)):
            return {
                "item": item_name,
                "reason": "refs_source_unresolvable",
                "fix": f"fix provenance.source ({source!r}) to a path relative to {REFS_DIRNAME}/ that exists "
                       f"and stays inside {REFS_DIRNAME}/",
            }
    return None


def collect_provenance_gaps(
    named_items: list[tuple[str, Any]],
    *,
    stage_dir: str | Path | None = None,
) -> list[dict[str, str]]:
    """Adjudicate (item_name, provenance) pairs; return all gaps (never raises).

    ``stage_dir`` is the owning stage's directory (see ``provenance_gap_for``);
    keyword-only so a product root can never be passed positionally in its place.
    """
    gaps: list[dict[str, str]] = []
    for name, prov in named_items:
        gap = provenance_gap_for(name, prov, stage_dir=stage_dir)
        if gap is not None:
            gaps.append(gap)
    return gaps
