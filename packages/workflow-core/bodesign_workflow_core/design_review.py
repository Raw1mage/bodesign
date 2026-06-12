"""G2 (workflow_verification-discipline) — Design Review Gate.

DD-4: design-review is a workflow stage + evidence record, not a new MCP tool.
The review itself is walkthrough work (an AI/engineer following the
skills/bodesign methodology); this module only validates that "a review
happened and produced a verdict", persists the record into the client project
folder, and derives the gate status consumed by the workflow plan.

Fail-fast error codes (errors.md): REVIEW_MISSING, REVIEW_VERDICT_INVALID,
REVIEW_REJECTED. No silent fallback.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DESIGN_REVIEW_SCHEMA = "bodesign.design_review.v1"
_REVIEW_REL_PATH = Path("_design_review") / "design_review.json"

REVIEW_VERDICTS: tuple[str, ...] = ("APPROVE", "APPROVE_WITH_CONCERNS", "REJECT")
_SCENARIO_SEVERITIES: tuple[str, ...] = ("critical", "major", "minor", "info")

# Minimum scenario set the methodology expects reviewers to consider; recorded
# here so gate messages can point at it. Applicability is judged per design —
# the gate enforces non-empty scenarios, not this exact list.
RECOMMENDED_SCENARIOS: tuple[str, ...] = (
    "power sequencing",
    "reset chain",
    "I2C address conflict",
    "level compatibility",
    "diff-pair topology",
)


class DesignReviewError(ValueError):
    """Raised for invalid review records (REVIEW_VERDICT_INVALID family)."""


@dataclass(slots=True)
class ReviewScenario:
    name: str
    walkthrough: str
    conclusion: str
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "walkthrough": self.walkthrough,
                "conclusion": self.conclusion, "severity": self.severity}


@dataclass(slots=True)
class DesignReviewRecord:
    subject: str
    scenarios: list[ReviewScenario]
    verdict: str
    evidence_refs: list[Any] = field(default_factory=list)
    schema: str = DESIGN_REVIEW_SCHEMA

    def __post_init__(self) -> None:
        missing: list[str] = []
        if not self.subject or not self.subject.strip():
            missing.append("subject")
        if not self.scenarios:
            missing.append("scenarios (non-empty)")
        if self.verdict not in REVIEW_VERDICTS:
            missing.append(f"verdict (allowed: {', '.join(REVIEW_VERDICTS)})")
        if missing:
            raise DesignReviewError(
                f"REVIEW_VERDICT_INVALID: design-review record is incomplete: {', '.join(missing)}; "
                "gate requires verdict and non-empty scenarios"
            )
        for i, s in enumerate(self.scenarios):
            if not s.name.strip() or not s.walkthrough.strip() or not s.conclusion.strip():
                raise DesignReviewError(
                    f"REVIEW_VERDICT_INVALID: scenario[{i}] requires non-empty name/walkthrough/conclusion"
                )
            if s.severity not in _SCENARIO_SEVERITIES:
                raise DesignReviewError(
                    f"REVIEW_VERDICT_INVALID: scenario[{i}].severity {s.severity!r} invalid "
                    f"(allowed: {', '.join(_SCENARIO_SEVERITIES)})"
                )

    @property
    def counts(self) -> dict[str, int]:
        c = {"critical": 0, "major": 0, "minor": 0}
        for s in self.scenarios:
            if s.severity in c:
                c[s.severity] += 1
        return c

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "subject": self.subject,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "counts": self.counts,
            "verdict": self.verdict,
            "evidence_refs": list(self.evidence_refs),
        }


def record_design_review(
    folder: str | Path,
    *,
    subject: str,
    scenarios: list[dict[str, Any]],
    verdict: str,
    evidence_refs: list[Any] | None = None,
) -> DesignReviewRecord:
    """Validate and persist a design-review record into the client project folder."""
    parsed = [
        ReviewScenario(
            name=str(s.get("name", "")),
            walkthrough=str(s.get("walkthrough", "")),
            conclusion=str(s.get("conclusion", "")),
            severity=str(s.get("severity", "")),
        )
        for s in scenarios
    ]
    record = DesignReviewRecord(
        subject=subject, scenarios=parsed, verdict=verdict,
        evidence_refs=list(evidence_refs or []),
    )
    path = Path(folder).expanduser().resolve() / _REVIEW_REL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def load_design_review(folder: str | Path) -> DesignReviewRecord | None:
    """Load the persisted review record; None when no review has been recorded."""
    path = Path(folder).expanduser().resolve() / _REVIEW_REL_PATH
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != DESIGN_REVIEW_SCHEMA:
        raise DesignReviewError(
            f"REVIEW_VERDICT_INVALID: unsupported review schema {data.get('schema')!r} at {path}"
        )
    return DesignReviewRecord(
        subject=data.get("subject", ""),
        scenarios=[
            ReviewScenario(
                name=s.get("name", ""), walkthrough=s.get("walkthrough", ""),
                conclusion=s.get("conclusion", ""), severity=s.get("severity", ""),
            )
            for s in data.get("scenarios", [])
        ],
        verdict=data.get("verdict", ""),
        evidence_refs=data.get("evidence_refs", []),
    )


def review_gate_status(folder: str | Path | None) -> tuple[str, list[str]]:
    """Derive the design-review stage status + downstream validation blockers.

    Returns (stage_status, validation_blockers):
    - no folder context     -> ("required", [REVIEW_MISSING ...])  — review not done yet
    - no record on disk     -> ("required", [REVIEW_MISSING ...])
    - verdict REJECT        -> ("rejected", [REVIEW_REJECTED ...])
    - APPROVE_WITH_CONCERNS -> ("approved-with-concerns", [])
    - APPROVE               -> ("approved", [])
    """
    missing_msg = (
        "REVIEW_MISSING: design-review record not found; deterministic-validation is blocked "
        f"until review completes (minimum scenario set: {', '.join(RECOMMENDED_SCENARIOS)})"
    )
    if folder is None:
        return "required", [missing_msg]
    record = load_design_review(folder)
    if record is None:
        return "required", [missing_msg]
    if record.verdict == "REJECT":
        return "rejected", [
            "REVIEW_REJECTED: design-review verdict is REJECT; resolve concerns and re-review before validation"
        ]
    if record.verdict == "APPROVE_WITH_CONCERNS":
        return "approved-with-concerns", []
    return "approved", []
