"""C01 Rockbox-like ID package generation and readiness checks.

This module is deterministic and intentionally script-first: it creates the
minimum C01 package that can be handed to an ID designer and downstream layers
without claiming final industrial design, Illustrator output, CAD, or approval.
"""

from __future__ import annotations

import json
import base64
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


C01_OUTPUTS = {
    "ai_file": Path("C01-ID") / "Ai file" / "Design_Direction.md",
    "cmf": Path("C01-ID") / "CMF" / "CMF_Direction.md",
    "display_uiux": Path("C01-ID") / "Display UIUX" / "UIUX_Requirements.md",
    "constraints": Path("C01-ID") / "Interface_Constraints.json",
    "handoff": Path("C01-ID") / "Handoff_to_ID_Designer.md",
}

C01_ANSWER_STATE_REL_PATH = Path("C01-ID") / "answer_state.json"
C01_ANSWER_STATES = {"missing", "answered", "drafted", "no-preference", "external-needed", "blocked", "accepted-risk"}

# A2: optional concept/moodboard/UI prompt artifacts for ID handoff.
C01_PROMPT_OUTPUTS = {
    "concept": Path("C01-ID") / "Ai file" / "Concept_Image_Prompts.md",
    "moodboard": Path("C01-ID") / "Ai file" / "Moodboard_Prompts.md",
    "ui": Path("C01-ID") / "Display UIUX" / "UI_Concept_Prompts.md",
}
# N7/N8: reference-image cue intake + traceability.
C01_REFERENCE_CUES_REL_PATH = Path("C01-ID") / "reference_cues.json"
C01_CUE_TYPES = {"form", "cmf", "ui", "component", "mood"}
C01_CUE_CONFIRMATIONS = {"reference-derived", "confirmed", "rejected"}
C01_INTERACTION_FIELDS = (
    {
        "key": "form_archetype",
        "label": "Product form archetype",
        "question": "Should this look like a dev-kit, handheld product, desktop sensor, wearable module, wall-mounted box, or another form archetype?",
        "owner": "user",
        "downstream_targets": ["C01", "C02"],
    },
    {
        "key": "usage_posture",
        "label": "Usage posture",
        "question": "How will the product usually be used: held, placed on a desk, mounted, worn, embedded, or serviced occasionally?",
        "owner": "user",
        "downstream_targets": ["C01", "C02"],
    },
    {
        "key": "primary_face",
        "label": "Primary user-facing face",
        "question": "Which face is the user's primary interaction face, and which components must live there?",
        "owner": "user+ID",
        "downstream_targets": ["C01", "C02", "C04"],
    },
    {
        "key": "visible_component_treatment",
        "label": "Visible component treatment",
        "question": "Should camera, microphone, LEDs, buttons, connectors, and antenna regions be emphasized, subtly integrated, hidden, or protected?",
        "owner": "user+ID",
        "downstream_targets": ["C01", "C02", "C03", "C04"],
    },
    {
        "key": "exposed_components",
        "label": "Exposed component list",
        "question": "Which components must be visible or user-accessible, such as camera, microphone, LED, button, display, USB-C, antenna, vents, or mounting features?",
        "owner": "user+ID+EE",
        "downstream_targets": ["C01", "C02", "C03", "C04", "C05"],
    },
    {
        "key": "cmf_direction",
        "label": "CMF direction",
        "question": "What emotional direction should CMF express: rugged, premium, medical-clean, playful, industrial, invisible/utility, or brand-specific?",
        "owner": "user+ID",
        "downstream_targets": ["C01", "C02"],
    },
    {
        "key": "display_uiux",
        "label": "Display UI/UX or status behavior",
        "question": "How should status be shown: display screens, LEDs, buttons, buzzer, app feedback, or no local status surface?",
        "owner": "user+ID+FW",
        "downstream_targets": ["C01", "C05"],
    },
    {
        "key": "owner",
        "label": "C01 approval owner",
        "question": "Who owns C01 approval: product owner, ID designer, ME, EE/RF, FW, vendor, or another reviewer?",
        "owner": "user",
        "downstream_targets": ["C01"],
    },
    {
        "key": "reference_image_cues",
        "label": "Reference image cues",
        "question": "Do you have reference images, and which cues should be borrowed or avoided?",
        "owner": "user+ID",
        "downstream_targets": ["C01"],
    },
)

CONCEPT_IMAGE_REL_PATH = Path("C01-ID") / "Ai file" / "Concept_Reference.png"
CONCEPT_REFERENCE_REL_PATH = Path("C01-ID") / "Ai file" / "Concept_Reference.md"
DEFAULT_GOOGLE_IMAGE_MODEL = "gemini-2.0-flash-preview-image-generation"
DEFAULT_OPENCODE_ACCOUNTS_PATH = Path.home() / ".config" / "opencode" / "accounts.json"
DEFAULT_OPENCODE_GOOGLE_FAMILY = "gemini-cli"

EXPOSED_COMPONENT_KEYWORDS = {
    "camera": ("camera", "csi", "dcmi", "mipi", "image sensor", "相機", "攝影", "鏡頭", "镜头"),
    "microphone": ("microphone", "mic", "audio input", "麥克風", "麦克", "收音"),
    "speaker": ("speaker", "buzzer", "audio output", "喇叭", "蜂鳴", "蜂鸣"),
    "display": ("display", "screen", "lcd", "oled", "螢幕", "屏幕", "顯示", "显示"),
    "led": ("led", "status light", "indicator", "狀態燈", "指示燈"),
    "button": ("button", "key", "switch", "按鍵", "按鈕", "开关", "開關"),
    "usb-c": ("usb-c", "usb c", "type-c", "type c", "typec"),
    "antenna": ("antenna", "wifi", "wi-fi", "ble", "bluetooth", "rf", "天線", "天线", "無線", "无线"),
    "vent": ("vent", "thermal", "heat", "散熱", "散热", "通風"),
    "mounting": ("mount", "wall", "clip", "screw", "固定", "壁掛", "螺絲"),
}


@dataclass(slots=True)
class C01PackageArtifact:
    key: str
    rel_path: str
    status: str
    next_action: str = ""


@dataclass(slots=True)
class C01PackageReadiness:
    folder: str
    readiness_pct: int
    usable: bool
    next_step: str
    artifacts: list[C01PackageArtifact] = field(default_factory=list)
    answer_state_path: str | None = None
    field_gaps: list[dict[str, str]] = field(default_factory=list)
    human_approved: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "readiness_pct": self.readiness_pct,
            "usable": self.usable,
            "next_step": self.next_step,
            "answer_state_path": self.answer_state_path,
            "field_gaps": self.field_gaps,
            "human_approved": self.human_approved,
            "artifacts": [
                {"key": a.key, "rel_path": a.rel_path, "status": a.status, "next_action": a.next_action}
                for a in self.artifacts
            ],
        }


@dataclass(slots=True)
class C01PackageResult:
    folder: str
    files: list[str]
    readiness: C01PackageReadiness

    def to_dict(self) -> dict[str, object]:
        return {"folder": self.folder, "files": self.files, "readiness": self.readiness.to_dict()}


@dataclass(slots=True)
class C01ConceptImageResult:
    folder: str
    image_path: str
    reference_path: str
    provider: str
    model: str
    prompt: str
    mime_type: str
    limitations: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "image_path": self.image_path,
            "reference_path": self.reference_path,
            "provider": self.provider,
            "model": self.model,
            "prompt": self.prompt,
            "mime_type": self.mime_type,
            "limitations": self.limitations,
        }


@dataclass(slots=True)
class C01NextQuestionResult:
    folder: str
    target_field: str
    question: str
    field_state: str
    answer_state_exists: bool
    status: str = "question_available"

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "status": self.status,
            "target_field": self.target_field,
            "question": self.question,
            "field_state": self.field_state,
            "answer_state_exists": self.answer_state_exists,
        }


@dataclass(slots=True)
class C01AnswerUpdateResult:
    folder: str
    answer_state_path: str
    updated_fields: list[str]
    package: C01PackageResult
    next_question: C01NextQuestionResult
    status: str = "answers_updated"

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "status": self.status,
            "answer_state_path": self.answer_state_path,
            "updated_fields": self.updated_fields,
            "package": self.package.to_dict(),
            "next_question": self.next_question.to_dict(),
            "human_approved": False,
        }


def emit_c01_rockbox_package(
    out_dir: str | Path,
    c00: dict[str, Any] | str | None = None,
    answers: dict[str, Any] | None = None,
) -> C01PackageResult:
    """Create a Rockbox-like C01 package with non-empty structured scripts."""
    root = Path(out_dir)
    model = _build_model(c00, answers or {})
    files = {
        C01_OUTPUTS["ai_file"]: _render_design_direction(model),
        C01_OUTPUTS["cmf"]: _render_cmf_direction(model),
        C01_OUTPUTS["display_uiux"]: _render_uiux_requirements(model),
        C01_OUTPUTS["constraints"]: json.dumps(_constraints(model), ensure_ascii=False, indent=2) + "\n",
        C01_OUTPUTS["handoff"]: _render_handoff(model),
    }
    written: list[str] = []
    for rel_path, content in files.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(str(rel_path))
    return C01PackageResult(str(root), written, assess_c01_package_readiness(root))


# ── A2: concept / moodboard / UI prompt artifacts ──────────────────────


@dataclass(slots=True)
class C01PromptArtifactsResult:
    folder: str
    files: list[str]

    def to_dict(self) -> dict[str, object]:
        return {"folder": self.folder, "files": list(self.files),
                "reference_only": True,
                "note": "Reference-only prompts for ID handoff/communication; not final art, "
                        "and not a copy of any specific product or brand."}


def emit_c01_concept_prompts(
    out_dir: str | Path,
    c00: dict[str, Any] | str | None = None,
    answers: dict[str, Any] | None = None,
) -> C01PromptArtifactsResult:
    """Persist concept/moodboard/UI prompt artifacts derived from accumulated C01 intent.

    Reference-only and copyright-safe: prompts describe generalized design language
    (archetype + CMF route + brand tone), never a named product/brand to copy."""
    root = Path(out_dir)
    model = _build_model(c00, answers or {})
    comp_names = ", ".join(c["name"] for c in model["components"]) or "exposed components TBD"
    base = (f"{model['form_archetype']}, for {model['usage_posture']}, primary face: "
            f"{model['primary_face']}, visible: {comp_names}")
    files: list[str] = []
    for key, content in (
        ("concept", "\n".join([
            "# C01 Concept Image Prompts (reference-only)",
            "",
            "> Generalized design language, not a copy of any product/brand. Feed `bodesign_c01_generate_concept_image`.",
            "",
            f"- **Concept:** {base}, {model['cmf_direction']}, neutral studio render, 3/4 view.",
            f"- **Front view:** {base}, straight-on, {model['visual_tone']}.",
        ]) + "\n"),
        ("moodboard", "\n".join([
            "# C01 Moodboard Prompts (reference-only)",
            "",
            f"- Tone: {model['visual_tone']}; CMF: {model['cmf_direction']}; environment: {model['environment']}.",
            f"- Archetype influence: {model['form_archetype']} (generalized, not brand-specific).",
        ]) + "\n"),
        ("ui", "\n".join([
            "# C01 UI Concept Prompts (reference-only)",
            "",
            f"- Display/status model: {model['display_uiux']}.",
            "- Show key states/screens generically; align vocabulary with C05 firmware states.",
        ]) + "\n"),
    ):
        rel = C01_PROMPT_OUTPUTS[key]
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        files.append(str(rel))
    return C01PromptArtifactsResult(str(root), files)


# ── N7/N8: reference-image cue intake + traceability ───────────────────


@dataclass(slots=True)
class C01ReferenceCuesResult:
    folder: str
    path: str
    cues: list[dict[str, Any]]

    def to_dict(self) -> dict[str, object]:
        return {"folder": self.folder, "path": self.path, "cues": list(self.cues),
                "unconfirmed_count": sum(1 for c in self.cues if c.get("user_confirmation") == "reference-derived"),
                "note": "Cues stay `reference-derived` until the user confirms; confirmed cues are "
                        "generalized design intent, never a copy of the source."}


def _read_reference_cues(root: Path) -> dict[str, Any]:
    path = root / C01_REFERENCE_CUES_REL_PATH
    if not path.exists():
        return {"schema": "bodesign.c01.reference_cues.v1", "cues": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "bodesign.c01.reference_cues.v1":
        raise ValueError(f"Unsupported C01 reference_cues schema: {path}")
    if not isinstance(data.get("cues"), list):
        raise ValueError(f"C01 reference_cues.cues must be a list: {path}")
    return data


def _write_reference_cues(root: Path, data: dict[str, Any]) -> None:
    path = root / C01_REFERENCE_CUES_REL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def c01_add_reference_image(
    folder: str | Path,
    source_image: str,
    cue_type: str,
    observed_cue: str,
    target_artifact: str = "Ai file",
    notes: str = "",
) -> C01ReferenceCuesResult:
    """Record a reference-image cue (N7). The cue stays `reference-derived` until the
    user confirms it; it is never auto-promoted to an approved preference. Persists
    source path, cue summary, confirmation status, and target artifact (N8)."""
    if not source_image or not source_image.strip():
        raise ValueError("source_image path is required")
    if cue_type not in C01_CUE_TYPES:
        raise ValueError(f"invalid cue_type {cue_type!r} (allowed: {sorted(C01_CUE_TYPES)})")
    if not observed_cue or not observed_cue.strip():
        raise ValueError("observed_cue (what to borrow/avoid, generalized) is required")
    root = Path(folder)
    data = _read_reference_cues(root)
    cue = {
        "cue_id": f"C01-CUE-{len(data['cues']) + 1:04d}",
        "source_image": source_image.strip(),
        "cue_type": cue_type,
        "observed_cue": observed_cue.strip(),
        "user_confirmation": "reference-derived",
        "target_artifact": target_artifact,
        "notes": notes.strip(),
    }
    data["cues"].append(cue)
    _write_reference_cues(root, data)
    return C01ReferenceCuesResult(str(root), str(C01_REFERENCE_CUES_REL_PATH), data["cues"])


def c01_confirm_reference_cue(
    folder: str | Path,
    cue_id: str,
    confirmation: str,
    note: str = "",
) -> C01ReferenceCuesResult:
    """Explicitly confirm or reject a reference cue (N8). Only the user may move a cue
    out of `reference-derived`; copyright note: confirmed cues remain generalized intent."""
    if confirmation not in {"confirmed", "rejected"}:
        raise ValueError("confirmation must be 'confirmed' or 'rejected'")
    root = Path(folder)
    data = _read_reference_cues(root)
    for cue in data["cues"]:
        if cue.get("cue_id") == cue_id:
            cue["user_confirmation"] = confirmation
            if note.strip():
                cue["notes"] = (cue.get("notes", "") + f" | {note.strip()}").strip(" |")
            _write_reference_cues(root, data)
            return C01ReferenceCuesResult(str(root), str(C01_REFERENCE_CUES_REL_PATH), data["cues"])
    raise ValueError(f"unknown cue_id: {cue_id}")


def assess_c01_package_readiness(folder: str | Path) -> C01PackageReadiness:
    root = Path(folder)
    artifacts: list[C01PackageArtifact] = []
    present = 0
    for key, rel_path in C01_OUTPUTS.items():
        path = root / rel_path
        if not path.exists():
            artifacts.append(C01PackageArtifact(key, str(rel_path), "missing", f"Create `{rel_path}`."))
            continue
        if path.stat().st_size == 0:
            artifacts.append(C01PackageArtifact(key, str(rel_path), "partial", f"Fill `{rel_path}` with labeled draft content."))
            continue
        if key == "constraints" and not _valid_constraints(path):
            artifacts.append(C01PackageArtifact(key, str(rel_path), "partial", "Make constraints valid JSON with an `exposed_components` list."))
            continue
        artifacts.append(C01PackageArtifact(key, str(rel_path), "present"))
        present += 1
    file_readiness_pct = round(100 * present / len(C01_OUTPUTS))
    pending = [a for a in artifacts if a.status != "present"]
    answer_state_path = root / C01_ANSWER_STATE_REL_PATH
    field_gaps: list[dict[str, str]] = []
    field_readiness_pct: int | None = None
    field_next_step = ""
    if answer_state_path.exists():
        state = _read_c01_answer_state(root)
        field_gaps = _c01_field_gaps(state)
        fields = state.get("fields") or {}
        ready_fields = [field for field in fields.values() if isinstance(field, dict) and field.get("state") in {"answered", "no-preference", "accepted-risk"}]
        field_readiness_pct = round(100 * len(ready_fields) / len(C01_INTERACTION_FIELDS))
        next_question = c01_next_question(root)
        if next_question.status != "complete":
            field_next_step = f"Ask C01 preference `{next_question.target_field}`: {next_question.question}"
    readiness_pct = min(file_readiness_pct, field_readiness_pct) if field_readiness_pct is not None else file_readiness_pct
    usable = not pending and not field_gaps
    if pending:
        next_step = pending[0].next_action
    elif field_next_step:
        next_step = field_next_step
    else:
        next_step = "C01 Rockbox-like package is usable as a first-pass ID handoff."
    return C01PackageReadiness(
        str(root),
        readiness_pct,
        usable,
        next_step,
        artifacts,
        str(C01_ANSWER_STATE_REL_PATH) if answer_state_path.exists() else None,
        field_gaps,
        False,
    )


def c01_next_question(folder: str | Path) -> C01NextQuestionResult:
    root = Path(folder)
    state_path = root / C01_ANSWER_STATE_REL_PATH
    answer_state_exists = state_path.exists()
    state = _read_c01_answer_state(root) if answer_state_exists else _new_c01_answer_state(None)
    field = _first_open_c01_field(state)
    if field is None:
        return C01NextQuestionResult(str(root), "", "All C01 preference fields are complete enough for the current interaction model.", "answered", answer_state_exists, "complete")
    return C01NextQuestionResult(str(root), field["key"], field["question"], field["state"], answer_state_exists)


def c01_update_answers(
    folder: str | Path,
    answers: dict[str, Any],
    c00: dict[str, Any] | str | None = None,
) -> C01AnswerUpdateResult:
    root = Path(folder)
    state = _read_c01_answer_state(root) if (root / C01_ANSWER_STATE_REL_PATH).exists() else _new_c01_answer_state(c00)
    if not isinstance(answers, dict) or not answers:
        raise ValueError("answers must be a non-empty object for C01 update")
    updated: list[str] = []
    fields = state["fields"]
    for key, raw in answers.items():
        if key not in fields:
            raise ValueError(f"Unknown C01 answer field: {key}")
        value, answer_state, source, owner = _normalize_answer(raw, fields[key])
        fields[key]["value"] = value
        fields[key]["state"] = answer_state
        fields[key]["source"] = source
        fields[key]["owner"] = owner
        updated.append(key)
    state["status"] = "answers-updated"
    state["package_emitted"] = False
    _write_c01_answer_state(root, state)
    package = emit_c01_rockbox_package(root, c00, _answers_from_c01_state(state))
    state["package_emitted"] = True
    _write_c01_answer_state(root, state)
    next_question = c01_next_question(root)
    return C01AnswerUpdateResult(str(root), str(C01_ANSWER_STATE_REL_PATH), updated, package, next_question)


def generate_c01_concept_image(
    out_dir: str | Path,
    prompt: str,
    model: str | None = None,
    api_key: str | None = None,
) -> C01ConceptImageResult:
    """Generate an optional C01 concept reference image via Google AI Studio.

    This is an add-on communication artifact. It is deliberately outside C01
    readiness and fails fast when Google credentials or image data are missing.
    """
    if not prompt.strip():
        raise ValueError("prompt is required for C01 concept image generation")
    selected_model = model or os.environ.get("BODESIGN_GOOGLE_IMAGE_MODEL") or os.environ.get("GEMINI_IMAGE_MODEL") or DEFAULT_GOOGLE_IMAGE_MODEL
    key = api_key or _resolve_google_api_key()
    if not key:
        raise RuntimeError(
            "Google AI Studio API key is required: set BODESIGN_GOOGLE_API_KEY/GEMINI_API_KEY/GOOGLE_API_KEY "
            "or configure an active opencode accounts.json API account for gemini-cli"
        )

    mime_type, image_bytes = _call_google_image_api(prompt, selected_model, key)
    root = Path(out_dir)
    image_rel = _image_rel_path_for_mime(mime_type)
    image_path = root / image_rel
    reference_path = root / CONCEPT_REFERENCE_REL_PATH
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(image_bytes)
    reference_path.write_text(_render_concept_reference(prompt, selected_model, mime_type, image_rel), encoding="utf-8")
    return C01ConceptImageResult(
        folder=str(root),
        image_path=str(image_rel),
        reference_path=str(CONCEPT_REFERENCE_REL_PATH),
        provider="google-ai-studio",
        model=selected_model,
        prompt=prompt,
        mime_type=mime_type,
        limitations=_concept_limitations(),
    )


def _new_c01_answer_state(c00: dict[str, Any] | str | None) -> dict[str, Any]:
    fields = {}
    for spec in C01_INTERACTION_FIELDS:
        fields[spec["key"]] = {
            "key": spec["key"],
            "label": spec["label"],
            "question": spec["question"],
            "state": "missing",
            "value": None,
            "source": None,
            "owner": spec["owner"],
            "downstream_targets": spec["downstream_targets"],
        }
    return {
        "schema": "bodesign.c01.answer_state.v1",
        "status": "scaffold-only",
        "source_summary": _source_text(c00),
        "allowed_states": sorted(C01_ANSWER_STATES),
        "package_emitted": False,
        "human_approved": False,
        "fields": fields,
    }


def _read_c01_answer_state(root: Path) -> dict[str, Any]:
    path = root / C01_ANSWER_STATE_REL_PATH
    if not path.exists():
        raise FileNotFoundError(f"C01 answer state not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "bodesign.c01.answer_state.v1":
        raise ValueError(f"Unsupported C01 answer_state schema: {path}")
    fields = data.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise ValueError(f"C01 answer_state fields must be a non-empty object: {path}")
    for key, field in fields.items():
        if not isinstance(field, dict):
            raise ValueError(f"C01 answer_state field `{key}` must be an object")
        state = field.get("state")
        if state not in C01_ANSWER_STATES:
            raise ValueError(f"C01 answer_state field `{key}` has invalid state: {state}")
    return data


def _write_c01_answer_state(root: Path, state: dict[str, Any]) -> None:
    path = root / C01_ANSWER_STATE_REL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _first_open_c01_field(state: dict[str, Any]) -> dict[str, Any] | None:
    fields = state.get("fields") or {}
    for spec in C01_INTERACTION_FIELDS:
        field = fields.get(spec["key"])
        if isinstance(field, dict) and field.get("state") in {"missing", "blocked"}:
            return field
    for spec in C01_INTERACTION_FIELDS:
        field = fields.get(spec["key"])
        if isinstance(field, dict) and field.get("state") in {"drafted", "external-needed"}:
            return field
    return None


def _c01_field_gaps(state: dict[str, Any]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    fields = state.get("fields") or {}
    for spec in C01_INTERACTION_FIELDS:
        field = fields.get(spec["key"])
        if not isinstance(field, dict):
            gaps.append({
                "key": spec["key"],
                "label": spec["label"],
                "state": "missing",
                "owner": spec["owner"],
                "next_action": spec["question"],
            })
            continue
        field_state = str(field.get("state"))
        if field_state in {"answered", "no-preference", "accepted-risk"}:
            continue
        gaps.append({
            "key": str(field.get("key") or spec["key"]),
            "label": str(field.get("label") or spec["label"]),
            "state": field_state,
            "owner": str(field.get("owner") or spec["owner"]),
            "next_action": str(field.get("question") or spec["question"]),
        })
    return gaps


def _normalize_answer(raw: Any, current: dict[str, Any]) -> tuple[Any, str, str, str]:
    if isinstance(raw, dict):
        value = raw.get("value")
        state = raw.get("state") or "answered"
        source = raw.get("source") or "user"
        owner = raw.get("owner") or current.get("owner") or "user"
    else:
        value = raw
        state = "answered"
        source = "user"
        owner = current.get("owner") or "user"
    if state not in C01_ANSWER_STATES:
        raise ValueError(f"Invalid C01 answer state for `{current.get('key')}`: {state}")
    if state == "answered" and (value is None or value == ""):
        raise ValueError(f"Answered C01 field `{current.get('key')}` requires a non-empty value")
    return value, state, source, owner


def _answers_from_c01_state(state: dict[str, Any]) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    fields = state.get("fields") or {}
    for key, field in fields.items():
        if not isinstance(field, dict):
            continue
        value = field.get("value")
        field_state = field.get("state")
        if key == "visible_component_treatment":
            answers["visual_tone"] = value if value not in (None, "") else f"missing — {field.get('question', 'visible component treatment is not decided')}"
            continue
        if key == "reference_image_cues":
            continue
        if key == "exposed_components" and isinstance(value, str):
            value = [part.strip() for part in value.split(",") if part.strip()]
        if value in (None, ""):
            answers[key] = f"missing — {field.get('question', key)}"
        elif field_state in {"drafted", "external-needed", "blocked", "accepted-risk", "no-preference"}:
            answers[key] = f"{value} [{field_state}]"
        else:
            answers[key] = value
    source_summary = state.get("source_summary")
    if source_summary:
        answers["source_summary"] = source_summary
    return answers


def _build_model(c00: dict[str, Any] | str | None, answers: dict[str, Any]) -> dict[str, Any]:
    source_text = _source_text(c00)
    answer_text = "\n".join(str(v) for v in answers.values() if v is not None)
    corpus = "\n".join([source_text, answer_text]).lower()
    components = _component_list(answers.get("exposed_components"), corpus)
    return {
        "product_name": _field(answers, c00, "product_name", "Unnamed product"),
        "source_summary": source_text.strip() or "No C00 summary provided; all unprovided decisions remain missing.",
        "form_archetype": _field(answers, c00, "form_archetype", "missing — user/ID must choose product archetype"),
        "usage_posture": _field(answers, c00, "usage_posture", "missing — desktop / handheld / wearable / wall-mounted / embedded is not decided"),
        "primary_face": _field(answers, c00, "primary_face", "missing — primary user-facing side is not decided"),
        "visual_tone": _field(answers, c00, "visual_tone", "draft — utilitarian, clean, and engineering-visible until human brand direction is provided"),
        "cmf_direction": _field(answers, c00, "cmf_direction", "draft — neutral dark/white plastic routes pending ID approval"),
        "environment": _field(answers, c00, "environment", "missing — use environment not confirmed"),
        "display_uiux": _field(answers, c00, "display_uiux", "draft — status states must be mapped to display, LED, button, buzzer, or app behavior"),
        "owner": _field(answers, c00, "owner", "missing — ID decision owner not assigned"),
        "components": components,
    }


def _field(answers: dict[str, Any], c00: dict[str, Any] | str | None, key: str, default: str) -> str:
    value = answers.get(key)
    if value not in (None, ""):
        return str(value)
    if isinstance(c00, dict):
        value = c00.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def _source_text(c00: dict[str, Any] | str | None) -> str:
    if isinstance(c00, str):
        return c00
    if isinstance(c00, dict):
        chunks = []
        for key in ("summary", "prd", "project_overall", "id_me_requirements", "electrical_requirements", "software_requirements"):
            value = c00.get(key)
            if value:
                chunks.append(str(value))
        return "\n".join(chunks)
    return ""


# N6: per-exposed-component downstream targets + risk notes, so every constraint
# carries owner + status + downstream targets + risk (not just a name). Keyed by the
# normalized component type; an unknown type still gets owner/status + a generic risk.
_COMPONENT_CONSTRAINT_MAP = {
    "camera":     (["C02", "C04"],       "FOV can be obstructed by enclosure geometry; opening + clearance needed."),
    "microphone": (["C02", "C04"],       "Acoustic path can be blocked or noisy; needs a port and seal strategy."),
    "speaker":    (["C02", "C04"],       "Audio/buzzer output can be muffled; needs an acoustic opening/cavity."),
    "display":    (["C02", "C04", "C05"], "Viewing angle, window/bezel, and placement affect usability; align UI with C05."),
    "led":        (["C02", "C04", "C05"], "Status light can be invisible to the user; needs a light pipe / visible face."),
    "button":     (["C02", "C04"],       "Placement, size, travel, and tactile feedback are unresolved; needs ME review."),
    "usb-c":      (["C02", "C03", "C04"], "Connector insertion and cable clearance can be insufficient; edge opening needed."),
    "antenna":    (["C03", "C04"],       "Metal/finish or poor placement can block RF; keepout + non-metal window required."),
    "vent":       (["C02", "C04"],       "Thermal openings can conflict with waterproofing; needs thermal/ingress tradeoff."),
    "mounting":   (["C02", "C04"],       "Mounting bosses/strength and service access are unresolved; needs ME review."),
}


def _component_list(value: Any, corpus: str) -> list[dict[str, Any]]:
    if isinstance(value, list) and value:
        names = [str(v) for v in value]
    else:
        names = [name for name, keywords in EXPOSED_COMPONENT_KEYWORDS.items() if any(k in corpus for k in keywords)]
    if not names:
        names = ["missing — exposed component list not confirmed"]
    out: list[dict[str, Any]] = []
    for name in names:
        missing = name.startswith("missing")
        targets, risk = _COMPONENT_CONSTRAINT_MAP.get(
            name.lower(),
            (["C02", "C04"], "Exposed component treatment unconfirmed; placement/visibility need ID + ME review."),
        )
        out.append({
            "name": name,
            "placement_preference": "draft/missing — C01 must ask user or ID designer",
            "decision_status": "missing" if missing else "drafted",
            "owner": "C00 user + ID designer",
            "downstream_targets": [] if missing else list(targets),
            "risk_notes": "exposed component list not confirmed — cannot assess risk yet" if missing else risk,
        })
    return out


def _render_design_direction(m: dict[str, Any]) -> str:
    rows = "\n".join(f"| {c['name']} | {c['placement_preference']} | {c['decision_status']} |" for c in m["components"])
    return f"""# Ai file — Design Direction Script

## Status

- State: AI draft, not final industrial design.
- Owner: {m['owner']}
- Source: C00-derived visual/human-interface intent.

## C00 Source Summary

{m['source_summary']}

## Form Direction

- Product: {m['product_name']}
- Form archetype: {m['form_archetype']}
- Usage posture: {m['usage_posture']}
- Primary face: {m['primary_face']}
- Visual tone: {m['visual_tone']}

## Visible Component Intent

| Component | Placement Preference | Decision Status |
|---|---|---|
{rows}

## Open ID Decisions

- Final proportions, brand treatment, logo/label zones, and visual hierarchy require human/ID approval.
- This script is the minimum Rockbox-like substitute for an `Ai file` until a designer produces final source artwork.
"""


def _render_cmf_direction(m: dict[str, Any]) -> str:
    return f"""# CMF — Direction Script

## Status

- State: AI draft, not CMF sample approval.
- Owner: {m['owner']}

## Direction

- CMF intent: {m['cmf_direction']}
- Environment rationale: {m['environment']}

## Candidate Routes

1. **Clean utility** — neutral body, low-gloss finish, minimal accent color; good for engineering POC and broad acceptance.
2. **Industrial durable** — darker enclosure, textured touch surfaces, protected openings; good when ruggedness matters.
3. **Brand-forward** — controlled accent color, visible status zone, logo/label priority; requires human brand approval.

## Required Human / ID Checks

- Material feasibility, surface finish, supplier samples, cost, wear, thermal effect, and brand fit.
- Any route selected here remains `drafted` until ID designer or product owner approval.
"""


def _render_uiux_requirements(m: dict[str, Any]) -> str:
    return f"""# Display UI/UX — Requirements Script

## Status

- State: AI draft, not final UI/UX design.
- Owner: {m['owner']}

## User-Visible Status Model

{m['display_uiux']}

## Minimum States To Resolve

| State | User Feedback Surface | C05 Firmware Dependency | Decision Status |
|---|---|---|---|
| Power on / booting | display, LED, buzzer, or app | boot/status event | drafted |
| Normal operation | display, LED, or app | operating-state event | drafted |
| Error / fault | display, LED, buzzer, or app | error code vocabulary | drafted |
| Low battery / charging | display or LED | power-management state | drafted |
| Connectivity / pairing | display or LED | connectivity state | drafted |

## No-Display Rule

If the product has no screen, `Display UI/UX` still maps to LED/button/buzzer/app-facing status behavior and must not be omitted silently.
"""


def _constraints(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "bodesign.c01.interface_constraints.v1",
        "state": "drafted",
        "product_name": m["product_name"],
        "source": "C00-derived C01 Rockbox-like script emitter",
        "exposed_components": m["components"],
        "downstream_targets": {
            "C02": ["form archetype", "openings", "primary/user-facing surfaces", "mounting and handling assumptions"],
            "C03": ["visible electrical interfaces", "connector/display/button/LED/sensor presence", "antenna constraints"],
            "C04": ["preferred component faces", "placement keepouts", "visibility/RF/acoustic constraints"],
            "C05": ["status state labels", "button/LED/display/app interaction behavior"],
        },
        "open_decisions": [
            "primary face and placement zones require human/ID confirmation",
            "CMF route requires material/sample/brand approval",
            "UI/status vocabulary requires C05 alignment",
        ],
    }


def _render_handoff(m: dict[str, Any]) -> str:
    return f"""# Handoff to ID Designer

## Package Status

- This is a Rockbox-like C01 first-pass package.
- It is suitable for ID continuation and downstream constraint discussion.
- It is not final `.ai`, final CMF board, final Display UI/UX, CAD, or sign-off.

## From C00

{m['source_summary']}

## AI Drafted

- Form direction: {m['form_archetype']}
- Usage posture: {m['usage_posture']}
- Primary face: {m['primary_face']}
- CMF direction: {m['cmf_direction']}
- UI/status direction: {m['display_uiux']}

## Human / ID Must Decide

- Final visual proportions and product style.
- CMF route, material samples, finish, and brand fit.
- Exact visible component treatment and opening placement.
- Whether any conflict with C02/C03/C04/C05 is accepted as risk.

## Downstream Notes

- C02 consumes form/opening/mounting constraints.
- C03 consumes visible electrical interface and antenna/connector constraints.
- C04 consumes placement/keepout/visibility/acoustic/RF constraints.
- C05 consumes UI/status behavior labels.
"""


def _valid_constraints(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and isinstance(data.get("exposed_components"), list)


def _resolve_google_api_key() -> str | None:
    for env_name in ("BODESIGN_GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = os.environ.get(env_name)
        if value:
            return value
    return _resolve_opencode_google_api_key()


def _resolve_opencode_google_api_key() -> str | None:
    accounts_path = Path(os.environ.get("BODESIGN_OPENCODE_ACCOUNTS_JSON") or DEFAULT_OPENCODE_ACCOUNTS_PATH).expanduser()
    family = os.environ.get("BODESIGN_GOOGLE_ACCOUNT_FAMILY") or DEFAULT_OPENCODE_GOOGLE_FAMILY
    if not accounts_path.exists():
        return None
    try:
        data = json.loads(accounts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read opencode accounts.json for Google credentials: {accounts_path}") from exc
    provider_data = (data.get("families") or {}).get(family) or {}
    active_id = provider_data.get("activeAccount")
    accounts = provider_data.get("accounts") or {}
    if not active_id:
        if accounts:
            raise RuntimeError(f"opencode accounts.json family `{family}` has accounts but no activeAccount; select an active account")
        return None
    account = accounts.get(active_id)
    if not account:
        raise RuntimeError(f"opencode accounts.json family `{family}` activeAccount `{active_id}` is missing")
    if account.get("type") != "api":
        raise RuntimeError(f"opencode accounts.json family `{family}` active account is `{account.get('type')}`; C01 image generation requires an API-key account")
    key = account.get("apiKey")
    if not key:
        raise RuntimeError(f"opencode accounts.json family `{family}` active API account has no apiKey")
    return str(key)


def _call_google_image_api(prompt: str, model: str, api_key: str) -> tuple[str, bytes]:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": _concept_prompt(prompt)}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google image generation failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Google image generation request failed: {exc.reason}") from exc
    return _extract_google_inline_image(data)


def _extract_google_inline_image(data: dict[str, Any]) -> tuple[str, bytes]:
    for candidate in data.get("candidates", []):
        content = candidate.get("content") or {}
        for part in content.get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline, dict):
                continue
            encoded = inline.get("data")
            if not encoded:
                continue
            mime_type = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            return str(mime_type), base64.b64decode(encoded)
    raise RuntimeError("Google image generation returned no inline image data; verify the selected model supports image output")


def _image_rel_path_for_mime(mime_type: str) -> Path:
    ext = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
    }.get(mime_type.lower(), ".png")
    return CONCEPT_IMAGE_REL_PATH.with_suffix(ext)


def _concept_prompt(prompt: str) -> str:
    return "\n".join(
        [
            prompt.strip(),
            "",
            "Create a C01 industrial design concept reference image for product discussion.",
            "Do not include dimensions, manufacturing claims, brand logos, or copied proprietary product styling.",
            "The image is mood/reference only, not final industrial design, not CAD, and not manufacturing-ready.",
        ]
    )


def _concept_limitations() -> list[str]:
    return [
        "AI concept reference only",
        "not dimensionally accurate",
        "not manufacturing-ready",
        "not ID designer approved",
        "not a substitute for C02 CAD/STEP",
    ]


def _render_concept_reference(prompt: str, model: str, mime_type: str, image_rel: Path) -> str:
    limitations = "\n".join(f"- {item}" for item in _concept_limitations())
    generated_at = datetime.now(timezone.utc).isoformat()
    return f"""# C01 Concept Reference

## Status

{limitations}

## Generated Artifact

- Image: `{image_rel}`
- Provider: Google AI Studio
- Model: `{model}`
- MIME type: `{mime_type}`
- Generated at: `{generated_at}`

## Prompt

```text
{prompt.strip()}
```
"""
