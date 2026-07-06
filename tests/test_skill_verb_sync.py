"""LANDED_VERBS ↔ skill-docs sync gate (BR_20260706).

Every verb registered in ``skills/bodesign/scripts/gate.py`` LANDED_VERBS must be
mentioned at least once in the workflow-doc layer (SKILL.md / stage GUIDEs /
references). Registering a capability without teaching it produces orphan verbs
that guide-following agents never use — exactly the drift BR_20260706 reported
(refs_ingest / c04_face_placement / c04_castellation / c04_dod_traceback landed
in gate.py but had zero doc coverage).

Legacy verbs that predate this gate and are still undocumented live in
``LEGACY_UNDOCUMENTED`` — an explicit burn-down list. Removing an entry after
documenting its verb is progress; ADDING an entry to make a new verb pass is a
defect (document the verb instead).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE_PY = REPO / "skills" / "bodesign" / "scripts" / "gate.py"
DOC_ROOTS = (
    REPO / "skills" / "bodesign" / "SKILL.md",
    REPO / "skills" / "bodesign" / "stages",
    REPO / "skills" / "bodesign" / "references",
)

# Burn-down list: verbs registered before this gate existed and still awaiting
# doc coverage. Do NOT add new verbs here — document them in SKILL.md and the
# owning stage GUIDE instead (see issues/BR_20260706_*.md).
LEGACY_UNDOCUMENTED = {
    "c01_next_question",
    "c01_update_answers",
    "c01_add_reference_image",
    "c01_confirm_reference_cue",
    "c01_emit_cmf_package",
    "c01_emit_uiux_package",
    "c02_plan_intent",
    "agent_registry",
    "list_work_packets",
    "wrap_validation_evidence",
    "return_evidence",
    "list_evidence_returns",
    "ingest_evidence",
    "enter_c01_mode",
    "c00_orchestration_status",
    "c00_orchestration_tick",
    "reference_board_workflow",
}

_VERB_KEY = re.compile(r'^\s{4}"([a-z0-9_]+)":\s*\(', re.M)


def _landed_verbs() -> list[str]:
    src = GATE_PY.read_text(encoding="utf-8")
    verbs = _VERB_KEY.findall(src)
    if not verbs:
        raise AssertionError(f"no LANDED_VERBS keys parsed from {GATE_PY}")
    return verbs


def _doc_corpus() -> str:
    chunks: list[str] = []
    for root in DOC_ROOTS:
        if root.is_file():
            chunks.append(root.read_text(encoding="utf-8"))
        elif root.is_dir():
            for p in sorted(root.rglob("*.md")):
                chunks.append(p.read_text(encoding="utf-8"))
    if not chunks:
        raise AssertionError(f"no skill docs found under {DOC_ROOTS}")
    return "\n".join(chunks)


class TestSkillVerbSync(unittest.TestCase):
    def test_every_landed_verb_is_documented(self):
        verbs = _landed_verbs()
        docs = _doc_corpus()
        missing = [
            v for v in verbs
            if v not in LEGACY_UNDOCUMENTED and v not in docs
        ]
        self.assertEqual(
            missing, [],
            "LANDED_VERBS registered in gate.py but absent from the skill-doc "
            "layer (SKILL.md / stage GUIDEs / references). Document each verb "
            "(verb table + owning stage GUIDE SOP/Gate section) — do NOT "
            f"allowlist it: {missing}",
        )

    def test_allowlist_carries_no_stale_entries(self):
        """A documented or deregistered verb must leave the burn-down list."""
        verbs = set(_landed_verbs())
        docs = _doc_corpus()
        stale = sorted(
            v for v in LEGACY_UNDOCUMENTED
            if v not in verbs or v in docs
        )
        self.assertEqual(
            stale, [],
            "LEGACY_UNDOCUMENTED entries that are now documented (or no longer "
            f"registered) — remove them from the allowlist: {stale}",
        )


if __name__ == "__main__":
    unittest.main()
