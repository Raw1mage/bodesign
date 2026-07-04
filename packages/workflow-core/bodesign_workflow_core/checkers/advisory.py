"""M3 — advisory-only injection (DD-1 T-C / DD-5): qualitative verified controls
→ G2 design-review structured prompts.

Not every verified control can be a hard gate. A control whose rule is a
qualitative layout/geometry judgement (short trace, minimal loop area, keep
components close, correct topology) carries no machine-readable numeric
threshold that a checker could gate a design on with the available design IR.
Fabricating a numeric pass/fail for such a control would violate no-fabrication.

DD-5 routes these to the G2 design-review gate instead of a checker: each
qualitative verified control becomes a structured `ReviewScenario` prompt the
reviewer must walk through and conclude on. This module is that projection —
it reads the owning ragbase control objects and emits advisory scenarios
carrying the control_id + source anchor, so the review verdict stays traceable
to the distilled datasheet knowledge (datasheet-grounded).

Contract (no-fabrication + no-silent-fallback):
- Only `confidence=verified` controls are projected. A partial/todo control is
  NOT advisory-injected here (its knowledge is not settled enough to prompt a
  reviewer as authoritative) — it is left to the T-C backlog, mirroring the
  registry tier guard.
- A control that is already realised as a landed/stub checker binding is NOT
  re-emitted as an advisory scenario (a design gate and a review prompt for the
  same control would double-count) — the caller passes the registered set.
- Meta / process controls (workflow天條 such as no-fabrication,
  no-silent-fallback, the gate-definition controls) are excluded by an explicit
  deny-list: they govern the AI/workflow, not a per-design layout review.
- The projection is a pure read over sqlite; same DB rows → byte-identical
  scenario list (stable ordering by control_id).
"""

import sqlite3
from dataclasses import dataclass
from typing import Any

from .errors import CheckerError

# Meta / process controls — they constrain the workflow / AI conduct, not a
# per-design layout walkthrough, so they are never emitted as review scenarios.
# (An explicit deny-list, not a heuristic — no silent mis-classification.)
_META_CONTROLS: frozenset[str] = frozenset({
    "control.no-fabrication",
    "control.no-silent-fallback",
    "control.datasheet-grounded-claims",
    "control.deterministic-validation-before-fab",
    "control.design-review-g2",
    "control.tool-landed-redirect",
    "control.pcb-false-complete-dfm-gates",
    "control.requirements.prd-quality-characteristics",
    "control.verify.kicad-dru-rule-language",
})

_SEVERITY = "info"  # advisory prompts are info-severity; the reviewer sets the
# real severity per their walkthrough conclusion.


@dataclass(frozen=True, slots=True)
class AdvisoryScenario:
    """A qualitative verified control projected as a G2 review prompt.

    Taxonomy:
      - name: AdvisoryScenario
      - represents: the advisory (non-gate) realisation of a single qualitative
        verified control — the structured prompt a design reviewer walks through.
      - input (construction): control_id, name (human label), walkthrough (the
        distilled rule prompt), source_anchor (traceable citation from the
        control body), severity (default "info").
      - output: an immutable row convertible to the ReviewScenario dict shape the
        design_review gate consumes (via to_scenario_dict).
      - must NOT be read as: a pass/fail verdict — it is a prompt; the reviewer
        supplies the conclusion. It carries NO numeric gate (that is the whole
        reason it is advisory, not a checker).
      - complete when: construction returns (control_id + walkthrough non-empty).
    """

    control_id: str
    name: str
    walkthrough: str
    source_anchor: str
    severity: str = _SEVERITY

    def to_scenario_dict(self) -> dict[str, Any]:
        """Project onto the design_review.ReviewScenario dict contract.

        The reviewer fills `conclusion`; the injector seeds an empty conclusion
        placeholder the gate will reject until walked through — advisory prompts
        do NOT pre-approve themselves (no-silent-fallback).
        """
        return {
            "name": self.name,
            "walkthrough": self.walkthrough,
            "conclusion": "",  # reviewer must fill; empty fails the gate on purpose
            "severity": self.severity,
            "control_id": self.control_id,
            "source_anchor": self.source_anchor,
        }


def _first_source_anchor(body_md: str) -> str:
    """Extract a traceable source citation from a control body_md.

    Taxonomy:
      - name: _first_source_anchor
      - represents: the deterministic pull of the control's citation so an
        advisory prompt is datasheet-grounded (mirrors the checker source_anchor).
      - input: the control body_md text.
      - output: the citation substring (the parenthetical「來源：…」/「source：…」
        segment, else the first line) — always a non-empty string.
      - must NOT be read as: inventing a citation — it only lifts text already in
        the body; a body with no explicit source falls back to its first line
        (still verbatim, never fabricated).
      - complete when: a non-empty anchor string is returned.
    """
    for marker in ("來源：", "來源:", "source：", "source:", "（來源", "(來源"):
        idx = body_md.find(marker)
        if idx != -1:
            tail = body_md[idx:]
            end = tail.find("\n")
            seg = tail if end == -1 else tail[:end]
            return seg.strip().strip("（）()")
    first_line = body_md.strip().splitlines()[0] if body_md.strip() else ""
    return first_line.strip()


def build_advisory_scenarios(
    db_path: str,
    *,
    registered_control_ids: frozenset[str] | set[str],
) -> tuple[AdvisoryScenario, ...]:
    """Project qualitative verified controls into G2 advisory review prompts.

    Args:
      db_path: absolute path to the repo's ragbase.sqlite.
      registered_control_ids: the control ids already realised as checker
        bindings (from CheckerRegistry) — excluded so a design gate and a review
        prompt never double-count the same control.

    Returns:
      Tuple of AdvisoryScenario, stable-ordered by control_id. Only
      confidence=verified, non-meta, non-registered controls are included.

    Raises:
      CheckerError(CHK_CONTROL_NOT_FOUND): the ragbase_objects table is absent
        (a mis-pathed DB — fail fast, never an empty silent result).
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, body_md, confidence FROM ragbase_objects "
                "WHERE id LIKE 'control.%' AND confidence = 'verified' ORDER BY id"
            ).fetchall()
        except sqlite3.OperationalError as exc:
            raise CheckerError(
                "CHK_CONTROL_NOT_FOUND",
                f"ragbase control table not readable at {db_path!r}: {exc}",
            ) from exc
    finally:
        conn.close()

    out: list[AdvisoryScenario] = []
    for row in rows:
        cid = row["id"]
        if cid in _META_CONTROLS or cid in registered_control_ids:
            continue
        body = row["body_md"] or ""
        # Human label: strip the "control." prefix, dotted → spaced.
        label = cid.removeprefix("control.").replace(".", " ").replace("-", " ")
        walkthrough = body.strip().splitlines()[0].strip() if body.strip() else label
        out.append(AdvisoryScenario(
            control_id=cid,
            name=label,
            walkthrough=walkthrough,
            source_anchor=_first_source_anchor(body),
        ))
    return tuple(out)
