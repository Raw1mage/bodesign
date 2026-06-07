"""Layer mode contracts — how C00 hands control to a downstream layer.

The orchestration spine (`orchestration.py`) is layer-agnostic: it dispatches
work packets and ingests blockers. A *mode contract* is the concrete binding for
one downstream layer — which C00 PRD sections feed it, what it emits, and what it
may ask the user — wiring the agent registry, the work-packet runtime, the C00
template's `handoff_targets`, and the layer's existing emitter together.

C01-I3 (C00 → C01 industrial-design mode):
- ENTER: C00 dispatches a C01 work packet scoped to the PRD sections whose
  `handoff_targets` include C01 (derived from the template, not hardcoded), then
  the C01 emitter produces the Rockbox-like package.
- ASK: C01-scoped *preference* questions are asked directly via the C01 question
  bank (`c01_next_question`); they never touch the PRD contract.
- RETURN: anything that needs a product-level decision goes back to C00 as a
  blocker (`orchestration.return_blocker`) — C01 never mutates the PRD itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .c00_prd_template import load_c00_prd_template
from .c01_id_package import C01_OUTPUTS, c01_next_question, emit_c01_rockbox_package
from .orchestration import WorkPacket, dispatch_work_packet

# Rockbox canonical C01 deliverable slots (the packet's expected outputs),
# derived from the C01 emitter so the contract never drifts from what is written.
_C01_EXPECTED_OUTPUTS = [str(rel) for rel in C01_OUTPUTS.values()]

_C01_DEFAULT_OBJECTIVE = (
    "Produce the first-pass industrial-design package (Ai file / CMF / Display UI-UX) "
    "and exposed-interface constraints from the PRD's visual/mechanical fields. "
    "Draft only — no final aesthetics, CMF samples, or ID sign-off."
)


def layer_relevant_prd_sections(target_layer: str) -> list[str]:
    """C00 PRD section ids whose `handoff_targets` include `target_layer`.

    Derived from the committed C00 template so the mode contract tracks the
    document architecture instead of a hardcoded list.
    """
    template = load_c00_prd_template()
    sections: list[str] = []
    for section in template.project_sections:
        targets = section.get("handoff_targets") or []
        if target_layer in targets and section.get("id"):
            sections.append(section["id"])
    return sections


@dataclass(slots=True)
class C01ModeEntry:
    packet: dict[str, Any]
    package: dict[str, Any]
    next_question: dict[str, Any]
    prd_sections: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet": self.packet,
            "package": self.package,
            "next_question": self.next_question,
            "prd_sections": list(self.prd_sections),
            "boundary": (
                "C01 emits draft visual sources + constraints and may ask C01 preference "
                "questions; product-level decisions return to C00 as blockers. C01 does not "
                "mutate the PRD or claim ID approval."
            ),
        }


def enter_c01_mode(
    folder: str | Path,
    *,
    c00: dict[str, Any] | str | None = None,
    answers: dict[str, Any] | None = None,
    objective: str | None = None,
) -> C01ModeEntry:
    """C00 enters C01 mode: dispatch the C01 work packet, emit the C01 package,
    and report the next C01-scoped preference question.

    `folder` is the client project root: the work packet lands under
    `_orchestration/`, the C01 package + answer-state under the root (Rockbox slots).
    """
    root = Path(folder)
    sections = layer_relevant_prd_sections("C01")
    packet: WorkPacket = dispatch_work_packet(
        root, "C01", objective or _C01_DEFAULT_OBJECTIVE,
        sections=sections, expected_outputs=_C01_EXPECTED_OUTPUTS,
    )
    package = emit_c01_rockbox_package(root, c00, answers)
    next_q = c01_next_question(root)
    return C01ModeEntry(
        packet=packet.to_dict(),
        package=package.to_dict(),
        next_question=next_q.to_dict(),
        prd_sections=sections,
    )
