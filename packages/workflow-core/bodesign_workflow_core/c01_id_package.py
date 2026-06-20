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
    companion_readiness: dict[str, Any] | None = None
    id_native_readiness: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
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
        if self.companion_readiness is not None:
            out["companion_readiness"] = self.companion_readiness
        if self.id_native_readiness is not None:
            out["id_native_readiness"] = self.id_native_readiness
        return out


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
    # v2 (DD-7): dual-track readiness. companion_readiness aliases the existing
    # core companion track (backward compatible — readiness_pct/usable/artifacts
    # above keep their core-companion semantics). id_native_readiness reports the
    # three optional ID-native buckets; it never lifts the package to approved.
    companion_present = sum(1 for a in artifacts if a.status == "present")
    companion_readiness = {
        "readiness_pct": file_readiness_pct,
        "present": companion_present,
        "total": len(C01_OUTPUTS),
        "artifacts": [{"key": a.key, "rel_path": a.rel_path, "status": a.status} for a in artifacts],
    }
    id_native_readiness = _assess_id_native_track(root)
    return C01PackageReadiness(
        str(root),
        readiness_pct,
        usable,
        next_step,
        artifacts,
        str(C01_ANSWER_STATE_REL_PATH) if answer_state_path.exists() else None,
        field_gaps,
        False,
        companion_readiness,
        id_native_readiness,
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


# ════════════════════════════════════════════════════════════════════════
# v2 (BR issue_20260617): C01 ID-native deliverable buckets.
# Three independent emitters (Ai file / CMF / Display UI_UX) sharing the same
# answer_state + Interface_Constraints.json inputs, fail-fast discipline, and
# draft-marking rules. Plus readiness dual-track (companion vs id_native).
# ════════════════════════════════════════════════════════════════════════

# ── Phase 1: shared infra ───────────────────────────────────────────────

# BR bucket rel paths. NOTE the Display bucket uses `Display UI_UX/` (underscore),
# which COEXISTS with the core companion `Display UIUX/` (no underscore) in
# C01_OUTPUTS["display_uiux"]. Companion = source-of-truth markdown; ID-native
# bucket = optional demo deliverable.
C01_AI_FILE_BUCKET_REL = Path("C01-ID") / "Ai file"
C01_CMF_BUCKET_REL = Path("C01-ID") / "CMF"
C01_UIUX_BUCKET_REL = Path("C01-ID") / "Display UI_UX"

# Visible draft markings stamped on every visual/document (天條: never empty).
_DRAFT_MARKINGS = {
    "ai_file": "draft / not final industrial design",
    "cmf": "not CMF approval",
    "uiux": "not UI sign-off",
}

# The three ID-native bucket rel paths keyed by readiness/bucket id.
C01_ID_NATIVE_BUCKETS = {
    "ai_file": C01_AI_FILE_BUCKET_REL,
    "cmf": C01_CMF_BUCKET_REL,
    "display_uiux": C01_UIUX_BUCKET_REL,
}


@dataclass(slots=True)
class BucketResult:
    """Shared return contract for the three ID-native bucket emitters."""
    status: str            # success | missing | external-needed | validation-failed
    bucket: str            # ai_file | cmf | display_uiux
    out_dir: str | None = None
    files: list[str] = field(default_factory=list)
    draft_markings: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "status": self.status,
            "bucket": self.bucket,
            "out_dir": self.out_dir,
            "files": list(self.files),
            "draft_markings": list(self.draft_markings),
            "missing_fields": list(self.missing_fields),
            "validation_errors": list(self.validation_errors),
        }
        out.update(self.extra)
        return out


def _read_bucket_inputs(folder: str | Path) -> dict[str, Any]:
    """Shared input reader (DD-8): Interface_Constraints.json (primary) +
    answer_state (supplement). Returns a flat field map with field completeness;
    callers fail-fast on missing required keys (no silent fallback)."""
    root = Path(folder)
    fields: dict[str, Any] = {}

    # Primary: Interface_Constraints.json (the C01 downstream contract).
    constraints_path = root / C01_OUTPUTS["constraints"]
    constraints: dict[str, Any] | None = None
    if constraints_path.exists():
        try:
            data = json.loads(constraints_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                constraints = data
        except (OSError, json.JSONDecodeError):
            constraints = None
    if constraints:
        fields["product_name"] = constraints.get("product_name")
        comps = constraints.get("exposed_components")
        if isinstance(comps, list):
            names = []
            for c in comps:
                if isinstance(c, dict) and c.get("name"):
                    name = str(c["name"])
                elif isinstance(c, str):
                    name = c
                else:
                    continue
                if not name.startswith("missing"):
                    names.append(name)
            if names:
                fields["exposed_components"] = names

    # Supplement: answer_state.json fields that are actually answered.
    state_path = root / C01_ANSWER_STATE_REL_PATH
    if state_path.exists():
        try:
            state = _read_c01_answer_state(root)
        except (OSError, ValueError):
            state = None
        if state:
            answers = _answers_from_c01_state(state)
            for key in ("form_archetype", "primary_face", "usage_posture",
                        "visible_component_treatment", "cmf_direction", "display_uiux"):
                value = answers.get(key)
                if _field_answered(value):
                    fields[key] = value
            ec = answers.get("exposed_components")
            if "exposed_components" not in fields and isinstance(ec, list):
                clean = [str(v) for v in ec if isinstance(v, str) and not str(v).startswith("missing")]
                if clean:
                    fields["exposed_components"] = clean

    return {"fields": fields, "constraints": constraints, "root": root}


def _field_answered(value: Any) -> bool:
    """A field is usable only if it is a non-empty, non-`missing —`/`draft —` marker."""
    if value in (None, ""):
        return False
    if isinstance(value, str):
        low = value.strip().lower()
        if low.startswith("missing") or low.startswith("draft —") or low.startswith("draft -"):
            return False
        return bool(low)
    if isinstance(value, list):
        return bool(value)
    return True


def _merge_inline_answer_state(folder: str | Path, answer_state: dict[str, Any] | None) -> dict[str, Any]:
    """Merge an inline `answer_state` dict (test/MCP convenience) over folder inputs.

    The MCP/test callers may pass a plain {field: value} answer_state directly
    instead of (or in addition to) a persisted answer_state.json. Inline values
    are treated as answered. This stays deterministic and never invents values."""
    base = _read_bucket_inputs(folder)
    fields = base["fields"]
    if isinstance(answer_state, dict):
        for key, value in answer_state.items():
            if key == "exposed_components":
                if isinstance(value, list):
                    clean = [str(v) for v in value if str(v).strip()]
                    if clean:
                        fields["exposed_components"] = clean
                elif isinstance(value, str) and value.strip():
                    fields["exposed_components"] = [p.strip() for p in value.split(",") if p.strip()]
                continue
            if _field_answered(value):
                fields[key] = value
    # Interface_Constraints exposed_components may be passed inline too.
    return base


def _bucket_product_name(fields: dict[str, Any]) -> str:
    name = fields.get("product_name")
    if isinstance(name, str) and name.strip() and not name.lower().startswith("unnamed"):
        return name.strip()
    return "Product"


def _safe_stem(product_name: str) -> str:
    stem = "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in product_name.strip())
    return stem.strip("_") or "Product"


# ── Phase 2: Ai file bucket — deterministic SVG glyph library ────────────

# Shell archetype prototypes. Keyed by normalized form_archetype tokens.
_SHELL_GLYPHS = {
    "handheld": ("shell-handheld", "M40,20 h120 a16,16 0 0 1 16,16 v200 a16,16 0 0 1 -16,16 h-120 a16,16 0 0 1 -16,-16 v-200 a16,16 0 0 1 16,-16 z"),
    "desktop-sensor": ("shell-desktop-sensor", "M30,120 h160 a20,20 0 0 1 20,20 v90 a12,12 0 0 1 -12,12 h-176 a12,12 0 0 1 -12,-12 v-90 a20,20 0 0 1 20,-20 z"),
    "wearable": ("shell-wearable", "M70,40 h60 a30,30 0 0 1 30,30 v100 a30,30 0 0 1 -30,30 h-60 a30,30 0 0 1 -30,-30 v-100 a30,30 0 0 1 30,-30 z"),
    "wall-mounted": ("shell-wall-mounted", "M30,40 h160 a10,10 0 0 1 10,10 v140 a10,10 0 0 1 -10,10 h-160 a10,10 0 0 1 -10,-10 v-140 a10,10 0 0 1 10,-10 z"),
    "dev-kit": ("shell-dev-kit", "M20,40 h180 v180 h-180 z"),
}
_SHELL_DEFAULT = ("shell-generic", "M30,40 h160 a12,12 0 0 1 12,12 v160 a12,12 0 0 1 -12,12 h-160 a12,12 0 0 1 -12,-12 v-160 a12,12 0 0 1 12,-12 z")

# Component glyphs, aligned with EXPOSED_COMPONENT_KEYWORDS keys.
_COMPONENT_GLYPHS = {
    "camera": ("comp-camera", '<circle cx="0" cy="0" r="14" fill="none" stroke="#222" stroke-width="2"/><circle cx="0" cy="0" r="7" fill="#222"/>'),
    "microphone": ("comp-microphone", '<rect x="-6" y="-12" width="12" height="20" rx="6" fill="none" stroke="#222" stroke-width="2"/>'),
    "speaker": ("comp-speaker", '<circle cx="0" cy="0" r="12" fill="none" stroke="#222" stroke-width="2"/><circle cx="0" cy="0" r="3" fill="#222"/>'),
    "display": ("comp-display", '<rect x="-22" y="-14" width="44" height="28" rx="3" fill="none" stroke="#222" stroke-width="2"/>'),
    "led": ("comp-led", '<circle cx="0" cy="0" r="5" fill="#e33" stroke="#222" stroke-width="1.5"/>'),
    "button": ("comp-button", '<circle cx="0" cy="0" r="9" fill="none" stroke="#222" stroke-width="2"/>'),
    "usb-c": ("comp-usb-c", '<rect x="-12" y="-4" width="24" height="8" rx="4" fill="none" stroke="#222" stroke-width="2"/>'),
    "antenna": ("comp-antenna", '<path d="M0,12 L0,-12 M-6,-6 L0,-12 L6,-6" fill="none" stroke="#222" stroke-width="2"/>'),
    "vent": ("comp-vent", '<path d="M-12,-6 H12 M-12,0 H12 M-12,6 H12" stroke="#222" stroke-width="2"/>'),
    "mounting": ("comp-mounting", '<circle cx="0" cy="0" r="7" fill="none" stroke="#222" stroke-width="2"/><circle cx="0" cy="0" r="2" fill="#222"/>'),
}
_PLACEHOLDER_GLYPH = '<rect x="-12" y="-12" width="24" height="24" fill="none" stroke="#999" stroke-width="1.5" stroke-dasharray="4 3"/><text x="0" y="20" font-size="7" text-anchor="middle" fill="#999">placeholder</text>'

# CMF colorway lookup keyed by normalized cmf_direction token.
_CMF_COLORWAYS = {
    "rugged": {"primary": "#2b2b2b", "secondary": "#5a5a5a", "accent": "#d9822b"},
    "premium": {"primary": "#1a1a1a", "secondary": "#c0c0c0", "accent": "#b8860b"},
    "medical-clean": {"primary": "#f5f5f5", "secondary": "#dfe6ea", "accent": "#2a9d8f"},
    "playful": {"primary": "#ffcc4d", "secondary": "#4dd0e1", "accent": "#e91e63"},
    "industrial": {"primary": "#3c3c3c", "secondary": "#7f8c8d", "accent": "#f1c40f"},
    "utility": {"primary": "#4a4a4a", "secondary": "#9e9e9e", "accent": "#0277bd"},
}
_CMF_COLORWAY_DEFAULT = {"primary": "#404040", "secondary": "#a0a0a0", "accent": "#0277bd"}


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


def _resolve_shell_glyph(form_archetype: str) -> tuple[str, str]:
    token = _normalize_token(form_archetype)
    for key, glyph in _SHELL_GLYPHS.items():
        if key in token or token in key:
            return glyph
    return _SHELL_DEFAULT


def _resolve_cmf_colorway(cmf_direction: str) -> dict[str, str]:
    token = _normalize_token(cmf_direction)
    for key, colorway in _CMF_COLORWAYS.items():
        if key in token or token in key:
            return dict(colorway)
    return dict(_CMF_COLORWAY_DEFAULT)


def _build_layered_svg(
    fields: dict[str, Any],
) -> tuple[str, list[str], list[str], list[str], dict[str, str]]:
    """Assemble a layered, semantically-named SVG from the structured inputs (S2
    engine). Returns (svg_text, layers, glyphs_used, placeholders, cmf_applied)."""
    form_archetype = fields.get("form_archetype", "")
    cmf_direction = fields.get("cmf_direction", "")
    components = fields.get("exposed_components") or []
    shell_id, shell_path = _resolve_shell_glyph(form_archetype)
    colorway = _resolve_cmf_colorway(cmf_direction)

    glyphs_used: list[str] = [shell_id]
    placeholders: list[str] = []

    canvas_w, canvas_h = 240, 280
    layers = ["outline", "panel", "cmf-fill", "components", "annotations"]

    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
                 f'viewBox="0 0 {canvas_w} {canvas_h}">')
    # cmf-fill layer (below outline so the shell fill reads as the body colour).
    parts.append('<g id="cmf-fill">')
    parts.append(f'<path d="{shell_path}" fill="{colorway["primary"]}" fill-opacity="0.18"/>')
    parts.append('</g>')
    # outline layer
    parts.append('<g id="outline">')
    parts.append(f'<path d="{shell_path}" fill="none" stroke="#111" stroke-width="2.5"/>')
    parts.append('</g>')
    # panel layer (primary_face grid)
    parts.append('<g id="panel">')
    parts.append(f'<rect x="44" y="44" width="{canvas_w - 88}" height="{canvas_h - 100}" '
                 f'fill="none" stroke="{colorway["secondary"]}" stroke-width="1" stroke-dasharray="3 3"/>')
    parts.append('</g>')
    # components layer — each exposed component is its own named group.
    parts.append('<g id="components">')
    instances: dict[str, int] = {}
    grid_cols = 3
    for idx, raw in enumerate(components):
        ctype = _normalize_token(raw)
        glyph = _COMPONENT_GLYPHS.get(ctype)
        n = instances.get(ctype, 0) + 1
        instances[ctype] = n
        col = idx % grid_cols
        row = idx // grid_cols
        cx = 70 + col * 50
        cy = 80 + row * 50
        if glyph is None:
            placeholders.append(str(raw))
            inner = _PLACEHOLDER_GLYPH
            gid = f"component-{_safe_stem(str(raw)).lower()}-{n}"
        else:
            glyph_id, inner = glyph
            glyphs_used.append(glyph_id)
            gid = f"component-{ctype}-{n}"
        parts.append(f'<g id="{gid}" transform="translate({cx},{cy})">{inner}</g>')
    parts.append('</g>')
    # annotations layer (draft marking is mandatory)
    parts.append('<g id="annotations">')
    parts.append(f'<text x="12" y="{canvas_h - 12}" font-size="11" fill="#c0392b" '
                 f'font-family="sans-serif">{_DRAFT_MARKINGS["ai_file"]}</text>')
    parts.append('</g>')
    parts.append('</svg>')

    svg_text = "\n".join(parts) + "\n"
    # de-dup glyphs_used preserving order
    seen: set[str] = set()
    glyphs_unique = [g for g in glyphs_used if not (g in seen or seen.add(g))]
    return svg_text, layers, glyphs_unique, placeholders, colorway


_SVG_REQUIRED_LAYERS = ("outline", "panel", "cmf-fill", "components", "annotations")


def _validate_layered_svg(svg_text: str) -> list[str]:
    """SVG schema validator (DD-3): five named layers present, at least one
    component group, well-formed XML. Returns a list of violations (empty = ok)."""
    errors: list[str] = []
    try:
        import xml.etree.ElementTree as ET
        ET.fromstring(svg_text)
    except Exception as exc:  # noqa: BLE001 - report any parse failure as a violation
        errors.append(f"malformed SVG: {type(exc).__name__}: {exc}")
        return errors
    for layer in _SVG_REQUIRED_LAYERS:
        if f'id="{layer}"' not in svg_text:
            errors.append(f"missing required layer group id='{layer}'")
    if 'id="component-' not in svg_text:
        errors.append("no component-<type>-<n> group found")
    return errors


def _render_svg_to_png(svg_text: str, out_path: Path) -> tuple[bool, str]:
    """Rasterise the verified ID-skeleton SVG to a static PNG via cairosvg
    (DD-9). Toolchain-gated fail-soft: when cairosvg or its native libs are
    absent the PNG is left unrendered and the caller does NOT list a phantom
    .png in `files` (天條: no fabricated deliverable). Returns (rendered, note)."""
    try:
        import cairosvg  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return False, "PNG pending — cairosvg unavailable (C01V-E003)"
    try:
        cairosvg.svg2png(bytestring=svg_text.encode("utf-8"), write_to=str(out_path))
    except Exception as exc:  # noqa: BLE001
        return False, f"PNG pending — cairosvg render failed: {type(exc).__name__} (C01V-E003)"
    if out_path.exists() and out_path.stat().st_size > 0:
        return True, "PNG rendered via cairosvg"
    return False, "PNG pending — cairosvg produced no output (C01V-E003)"


def _build_svg_preview_html(
    svg_text: str,
    product: str,
    layers: list[str],
    placeholders: list[str],
    draft_marking: str,
) -> str:
    """Wrap the verified SVG in a self-contained, no-dependency preview HTML
    (DD-9): the SVG embeds inline so the page opens in any browser without a
    design tool, carrying the draft marking + layer/component legend. This is a
    PREVIEW of the editable SVG source, never a claim of final `.ai` artwork."""
    import html as _html  # noqa: PLC0415

    layer_items = "".join(f"<li><code>{_html.escape(l)}</code></li>" for l in layers)
    if placeholders:
        ph_items = "".join(
            f"<li><code>{_html.escape(p)}</code> — generic placeholder symbol</li>"
            for p in placeholders
        )
    else:
        ph_items = "<li>(none — all exposed components have dedicated glyphs)</li>"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(product)} — ID Skeleton Preview</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; background: #f4f4f5; color: #1c1c1f; }}
  .draft-banner {{ background: #c0392b; color: #fff; padding: 8px 16px; font-weight: 600; letter-spacing: .02em; }}
  .wrap {{ max-width: 880px; margin: 0 auto; padding: 24px 16px; }}
  .stage {{ background: #fff; border: 1px solid #e4e4e7; border-radius: 8px; padding: 24px; display: flex; justify-content: center; }}
  .stage svg {{ max-width: 100%; height: auto; }}
  h1 {{ font-size: 1.15rem; }}
  h2 {{ font-size: .95rem; margin-top: 1.6em; color: #3f3f46; }}
  ul {{ line-height: 1.6; }}
  code {{ background: #ececef; padding: 1px 5px; border-radius: 4px; font-size: .85em; }}
  .note {{ color: #71717a; font-size: .85rem; margin-top: 2em; border-top: 1px solid #e4e4e7; padding-top: 1em; }}
</style></head>
<body>
<div class="draft-banner">{_html.escape(draft_marking)}</div>
<div class="wrap">
  <h1>{_html.escape(product)} — ID Skeleton Preview</h1>
  <div class="stage">{svg_text}</div>
  <h2>SVG Layers</h2>
  <ul>{layer_items}</ul>
  <h2>Placeholders</h2>
  <ul>{ph_items}</ul>
  <p class="note">This HTML is a browser-viewable preview of the editable
  <code>{_html.escape(product)}_ID_skeleton.svg</code> source. It is NOT final
  industrial design, NOT an Illustrator <code>.ai</code> source, and NOT an ID
  approval. Edit the SVG directly in Figma / Illustrator / Inkscape.</p>
</div>
</body></html>
"""


def emit_c01_id_visual_package(
    folder: str | Path,
    answer_state: dict[str, Any] | None = None,
    figma_available: bool = False,
    ai_export_path: str | None = None,
) -> BucketResult:
    """Emit the Ai file ID-native bucket (DD-5). Produces a layered editable SVG
    + figma_import_spec.json + README.md. Fails fast when required answer_state
    fields are absent (C01V-E001). Never fabricates a .ai (天條)."""
    base = _merge_inline_answer_state(folder, answer_state)
    root = base["root"]
    fields = base["fields"]

    required = ["form_archetype", "primary_face", "exposed_components", "cmf_direction"]
    missing = [k for k in required if not fields.get(k)]
    if missing:
        return BucketResult(status="missing", bucket="ai_file", missing_fields=missing,
                            extra={"error_code": "C01V-E001"})

    svg_text, layers, glyphs_used, placeholders, cmf_applied = _build_layered_svg(fields)
    validation_errors = _validate_layered_svg(svg_text)
    if validation_errors:
        return BucketResult(status="validation-failed", bucket="ai_file",
                            validation_errors=validation_errors,
                            extra={"error_code": "C01V-E002"})

    product = _bucket_product_name(fields)
    stem = _safe_stem(product)
    out_dir = root / C01_AI_FILE_BUCKET_REL
    out_dir.mkdir(parents=True, exist_ok=True)

    svg_rel = C01_AI_FILE_BUCKET_REL / f"{stem}_ID_skeleton.svg"
    figma_rel = C01_AI_FILE_BUCKET_REL / "figma_import_spec.json"
    readme_rel = C01_AI_FILE_BUCKET_REL / "README.md"

    (root / svg_rel).write_text(svg_text, encoding="utf-8")

    # DD-9: browser-viewable HTML preview (always emitted — pure string wrap, no
    # external dependency) + optional static PNG raster (toolchain-gated).
    preview_html_rel = C01_AI_FILE_BUCKET_REL / f"{stem}_ID_skeleton.preview.html"
    preview_html = _build_svg_preview_html(
        svg_text, product, layers, placeholders, _DRAFT_MARKINGS["ai_file"]
    )
    (root / preview_html_rel).write_text(preview_html, encoding="utf-8")

    png_rel = C01_AI_FILE_BUCKET_REL / f"{stem}_ID_skeleton.png"
    png_rendered, png_note = _render_svg_to_png(svg_text, root / png_rel)

    # ai_emitted: only true if a real Illustrator-compatible export path exists.
    ai_emitted = bool(ai_export_path)

    figma_spec = {
        "schema": "bodesign.c01.figma_import_spec.v1",
        "source_svg": str(svg_rel),
        "draft_marking": _DRAFT_MARKINGS["ai_file"],
        "layers": layers,
        "component_group_id_pattern": "component-<type>-<n>",
        "glyphs_used": glyphs_used,
        "placeholders": placeholders,
        "cmf_applied": cmf_applied,
        "figma_available": bool(figma_available),
        "note": "Import the SVG into Figma; each component-<type>-<n> group is "
                "independently selectable. Not final industrial design.",
    }
    (root / figma_rel).write_text(json.dumps(figma_spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    placeholder_note = (
        "\n".join(f"- `{p}` rendered as generic placeholder symbol (glyph library not yet covering this type)"
                  for p in placeholders)
        or "- (none — all exposed components have dedicated glyphs)"
    )
    png_line = (
        f"- `{stem}_ID_skeleton.png` — static raster preview (slide/attachment use; not editable)."
        if png_rendered
        else f"- `{stem}_ID_skeleton.png` — *pending* ({png_note}); the SVG + HTML preview are the truth."
    )
    readme = f"""# Ai file — ID Skeleton Bucket

> {_DRAFT_MARKINGS["ai_file"]}

## Contents

- `{stem}_ID_skeleton.svg` — layered, designer-editable SVG (open directly in Figma/Illustrator).
- `{stem}_ID_skeleton.preview.html` — browser-viewable preview (no design tool needed; embeds the SVG).
{png_line}
- `figma_import_spec.json` — import spec; each exposed component is an independently-selectable group.
- `README.md` — this file.

## SVG Layers (DD-3)

{chr(10).join(f"- `{layer}`" for layer in layers)}

Each exposed component is wrapped as `component-<type>-<n>` for independent selection.

## Placeholders

{placeholder_note}

## `.ai` Substitutes (DD-9)

The Illustrator `.ai` source is never fabricated. Three honest stand-ins ship instead:
- **SVG** — the editable vector source (the real substitute; open in Figma/Illustrator/Inkscape).
- **HTML preview** — browser-viewable, zero-dependency; for review without a design tool.
- **PNG** — static raster for slides/attachments (toolchain-gated; pending when cairosvg is absent).

## Honesty Notes

- `ai_emitted = {str(ai_emitted).lower()}` — no `.ai` is fabricated; only emitted when a real Illustrator-compatible export path is configured.
- `png_rendered = {str(png_rendered).lower()}` — a phantom `.png` is never listed in `files`.
- This is a落地 skeleton, NOT final industrial design and NOT an ID approval.
"""
    (root / readme_rel).write_text(readme, encoding="utf-8")

    files = [str(svg_rel), str(preview_html_rel), str(figma_rel), str(readme_rel)]
    if png_rendered:
        files.insert(2, str(png_rel))

    return BucketResult(
        status="success",
        bucket="ai_file",
        out_dir=str(C01_AI_FILE_BUCKET_REL),
        files=files,
        draft_markings=[_DRAFT_MARKINGS["ai_file"]],
        extra={
            "ai_emitted": ai_emitted,
            "png_rendered": png_rendered,
            "png_note": png_note,
            "preview_html": str(preview_html_rel),
            "glyphs_used": glyphs_used,
            "placeholders": placeholders,
            "layers": layers,
            "cmf_applied": cmf_applied,
        },
    )


# ── Phase 3: CMF bucket ─────────────────────────────────────────────────

# CMF token derivation table keyed by normalized cmf_direction token.
_CMF_TOKEN_TABLE = {
    "rugged": {
        "material_family": ["PC-ABS blend", "TPU overmould"],
        "finish": ["matte", "textured soft-touch"],
        "gasket_sealing_notes": ["IP-rated gasket groove on parting line", "compression seal at USB-C door"],
        "sample_vendor_gates": ["material sample approval", "drop-test coupon sign-off"],
    },
    "premium": {
        "material_family": ["aluminium", "PC"],
        "finish": ["anodized", "high-gloss"],
        "gasket_sealing_notes": ["precision-fit seam", "co-moulded light gasket"],
        "sample_vendor_gates": ["anodize colour sample", "surface-finish master approval"],
    },
    "medical-clean": {
        "material_family": ["PC", "antimicrobial ABS"],
        "finish": ["smooth matte", "wipeable"],
        "gasket_sealing_notes": ["fully sealed wipe-down enclosure", "no debris-trapping seams"],
        "sample_vendor_gates": ["biocompatibility material gate", "cleaning-agent compatibility sign-off"],
    },
    "playful": {
        "material_family": ["ABS", "silicone"],
        "finish": ["glossy", "soft-touch"],
        "gasket_sealing_notes": ["snap-fit seam with light seal"],
        "sample_vendor_gates": ["colour-match sample approval"],
    },
    "industrial": {
        "material_family": ["PC-ABS blend", "aluminium"],
        "finish": ["matte", "bead-blasted"],
        "gasket_sealing_notes": ["dust-resistant seam gasket"],
        "sample_vendor_gates": ["material sample approval"],
    },
    "utility": {
        "material_family": ["ABS", "PC"],
        "finish": ["matte"],
        "gasket_sealing_notes": ["basic seam fit"],
        "sample_vendor_gates": ["material sample approval"],
    },
}
_CMF_TOKEN_DEFAULT = {
    "material_family": ["ABS", "PC"],
    "finish": ["matte"],
    "gasket_sealing_notes": ["seam seal strategy pending"],
    "sample_vendor_gates": ["material sample approval"],
}


def _derive_cmf_tokens(cmf_direction: str, exposed_components: list[str]) -> dict[str, Any]:
    token = _normalize_token(cmf_direction)
    base = None
    for key, table in _CMF_TOKEN_TABLE.items():
        if key in token or token in key:
            base = table
            break
    if base is None:
        base = _CMF_TOKEN_DEFAULT
    colorway = _resolve_cmf_colorway(cmf_direction)
    color_routes = [
        {"name": "body primary", "hex": colorway["primary"], "role": "primary"},
        {"name": "body secondary", "hex": colorway["secondary"], "role": "secondary"},
        {"name": "accent", "hex": colorway["accent"], "role": "accent"},
    ]
    # RF-transparent zones derive from antenna presence (天條: explicit decision, not fallback).
    rf_zones: list[str] = []
    comps_low = [_normalize_token(c) for c in (exposed_components or [])]
    if "antenna" in comps_low:
        rf_zones.append("non-metal RF window over antenna keepout")
    return {
        "cmf_direction": cmf_direction,
        "material_family": list(base["material_family"]),
        "finish": list(base["finish"]),
        "color_routes": color_routes,
        "rf_transparent_zones": rf_zones,
        "gasket_sealing_notes": list(base["gasket_sealing_notes"]),
        "sample_vendor_gates": list(base["sample_vendor_gates"]),
        "approval_state": "not-approved",
    }


def _emit_doc_pdf(root: Path, md_rel: Path) -> tuple[Path | None, str]:
    """Attempt markdown→PDF via the approved emit_document pipeline. Returns
    (pdf_rel_or_None, note). When the toolchain (LibreOffice) is unavailable the
    PDF is left pending (C01D-E001) — never hand-stitched (天條)."""
    try:
        from bodesign_reverse_core import emit_document
    except Exception:  # noqa: BLE001
        return None, "PDF pending — emit_document pipeline unavailable (C01D-E001)"
    md_path = root / md_rel
    out_dir = md_path.parent
    try:
        res = emit_document(md_path, out_dir, formats=("pdf",))
    except Exception as exc:  # noqa: BLE001
        return None, f"PDF pending — emit_document failed: {type(exc).__name__} (C01D-E001)"
    pdf_path = res.outputs.get("pdf") if hasattr(res, "outputs") else None
    # emit_document always writes a `{stem}.html` LibreOffice intermediate into
    # out_dir; it is never a declared deliverable, so prune it to keep the bucket
    # clean (only the markdown source + rendered PDF remain).
    html_intermediate = out_dir / f"{md_path.stem}.html"
    if html_intermediate.exists():
        try:
            html_intermediate.unlink()
        except OSError:
            pass
    if pdf_path and Path(pdf_path).exists():
        return Path(pdf_path).relative_to(root), "PDF rendered via emit_document pipeline"
    return None, "PDF pending — LibreOffice toolchain unavailable, markdown source emitted (C01D-E001)"


def emit_c01_cmf_package(
    folder: str | Path,
    answer_state: dict[str, Any] | None = None,
) -> BucketResult:
    """Emit the CMF draft bucket (DD-5). Produces cmf_tokens.json + a CMF
    direction markdown (→PDF via pipeline when available) + README.md. Fails
    fast when cmf_direction is absent (C01C-E001)."""
    base = _merge_inline_answer_state(folder, answer_state)
    root = base["root"]
    fields = base["fields"]

    if not fields.get("cmf_direction"):
        return BucketResult(status="missing", bucket="cmf", missing_fields=["cmf_direction"],
                            extra={"error_code": "C01C-E001"})

    tokens = _derive_cmf_tokens(fields["cmf_direction"], fields.get("exposed_components") or [])
    if not tokens["material_family"] or not tokens["color_routes"]:
        return BucketResult(status="validation-failed", bucket="cmf",
                            validation_errors=["empty material_family or color_routes"],
                            extra={"error_code": "C01C-E002"})

    product = _bucket_product_name(fields)
    stem = _safe_stem(product)
    out_dir = root / C01_CMF_BUCKET_REL
    out_dir.mkdir(parents=True, exist_ok=True)

    tokens_rel = C01_CMF_BUCKET_REL / "cmf_tokens.json"
    md_rel = C01_CMF_BUCKET_REL / f"{stem}_CMF_Direction.md"
    readme_rel = C01_CMF_BUCKET_REL / "README.md"

    (root / tokens_rel).write_text(json.dumps(tokens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    routes_md = "\n".join(f"| {r['name']} | `{r['hex']}` | {r['role']} |" for r in tokens["color_routes"])
    rf_md = "\n".join(f"- {z}" for z in tokens["rf_transparent_zones"]) or "- (none — no antenna RF window required)"
    cmf_md = f"""# {product} — CMF Direction

> {_DRAFT_MARKINGS["cmf"]}

## Direction

- CMF intent: {fields["cmf_direction"]}
- Approval state: **{tokens["approval_state"]}** (no CMF sample is claimed approved).

## Material Family

{chr(10).join(f"- {m}" for m in tokens["material_family"])}

## Finish

{chr(10).join(f"- {f}" for f in tokens["finish"])}

## Colour Routes

| Name | Hex | Role |
|---|---|---|
{routes_md}

## RF-Transparent Zones

{rf_md}

## Gasket / Sealing Notes

{chr(10).join(f"- {g}" for g in tokens["gasket_sealing_notes"])}

## Sample / Vendor Gates

{chr(10).join(f"- {s}" for s in tokens["sample_vendor_gates"])}

---

_{_DRAFT_MARKINGS["cmf"]}. Material feasibility, samples, and brand fit require human/ID approval._
"""
    (root / md_rel).write_text(cmf_md, encoding="utf-8")

    pdf_rel, pdf_note = _emit_doc_pdf(root, md_rel)
    files = [str(tokens_rel), str(md_rel), str(readme_rel)]
    # Honesty (天條): only list the PDF in `files` when it actually exists on disk.
    # Pending state is communicated via extra.pdf_status + the README note — never by
    # naming a phantom file in the deliverable list (markdown is the source of truth).
    if pdf_rel is not None:
        files.append(str(pdf_rel))

    readme = f"""# CMF — Direction Bucket

> {_DRAFT_MARKINGS["cmf"]}

## Contents

- `cmf_tokens.json` — derived CMF design tokens (material/finish/colour/RF/gasket/gates), `approval_state = not-approved`.
- `{stem}_CMF_Direction.md` — CMF direction document (markdown source of truth).
- `{stem}_CMF_Direction.pdf` — {pdf_note}.
- `README.md` — this file.

## Honesty Notes

- `approval_state` is permanently `not-approved`; this bucket never claims CMF sample approval.
- {pdf_note}
"""
    (root / readme_rel).write_text(readme, encoding="utf-8")

    return BucketResult(
        status="success",
        bucket="cmf",
        out_dir=str(C01_CMF_BUCKET_REL),
        files=files,
        draft_markings=[_DRAFT_MARKINGS["cmf"]],
        extra={"cmf_tokens": tokens, "pdf_status": "rendered" if pdf_rel else "pending", "pdf_note": pdf_note},
    )


# ── Phase 4: Display UI_UX bucket ───────────────────────────────────────

# UIUX state vocabulary. Display-bearing products get OLED screens; otherwise we
# map explicitly to LED/status/button interaction (天條: explicit, not silent omit).
_UIUX_DISPLAY_STATES = ["oled boot screen", "oled status icons", "oled error screen",
                        "led indicator", "charging state", "connectivity state",
                        "insert/remove feedback", "privacy/local-only state", "error state"]
_UIUX_NODISPLAY_STATES = ["led boot blink", "led normal heartbeat", "led error pattern",
                          "button feedback", "charging state", "connectivity state",
                          "insert/remove feedback", "privacy/local-only state", "error state"]


def _derive_uiux_states(display_uiux: str, exposed_components: list[str]) -> tuple[list[str], bool]:
    """Derive the UIUX state set. Returns (states, has_display)."""
    text = _normalize_token(display_uiux)
    comps_low = [_normalize_token(c) for c in (exposed_components or [])]
    has_display = ("display" in comps_low or "oled" in text or "screen" in text
                   or "lcd" in text or "display" in text)
    if has_display:
        return list(_UIUX_DISPLAY_STATES), True
    return list(_UIUX_NODISPLAY_STATES), False


def _build_uiux_wireframe_svg(states: list[str], has_display: bool) -> str:
    parts: list[str] = []
    w, h = 320, 60 + 56 * len(states)
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
    parts.append('<g id="wireframe">')
    for i, state in enumerate(states):
        y = 30 + i * 56
        parts.append(f'<g id="state-{i + 1}" transform="translate(20,{y})">')
        parts.append('<rect x="0" y="0" width="280" height="40" rx="6" fill="none" stroke="#333" stroke-width="1.5"/>')
        parts.append(f'<text x="12" y="25" font-size="13" font-family="sans-serif" fill="#222">{_xml_escape(state)}</text>')
        parts.append('</g>')
    parts.append('</g>')
    parts.append('<g id="annotations">')
    parts.append(f'<text x="20" y="{h - 14}" font-size="11" fill="#c0392b" font-family="sans-serif">'
                 f'{_DRAFT_MARKINGS["uiux"]}{" (no-display → LED/status mapping)" if not has_display else ""}</text>')
    parts.append('</g>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def _xml_escape(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def emit_c01_uiux_package(
    folder: str | Path,
    answer_state: dict[str, Any] | None = None,
) -> BucketResult:
    """Emit the Display UI/UX draft bucket (DD-5). Produces uiux_wireframes.svg +
    a UIUX flow markdown (→PDF via pipeline when available) + README.md. Fails
    fast when neither display_uiux nor any status interaction is described
    (C01U-E001)."""
    base = _merge_inline_answer_state(folder, answer_state)
    root = base["root"]
    fields = base["fields"]

    display_uiux = fields.get("display_uiux")
    components = fields.get("exposed_components") or []
    status_comps = {"display", "led", "button", "speaker"}
    has_status_component = any(_normalize_token(c) in status_comps for c in components)
    if not _field_answered(display_uiux) and not has_status_component:
        return BucketResult(status="missing", bucket="display_uiux",
                            missing_fields=["display_uiux"],
                            extra={"error_code": "C01U-E001"})

    states, has_display = _derive_uiux_states(display_uiux or "", components)
    if not states:
        return BucketResult(status="validation-failed", bucket="display_uiux",
                            validation_errors=["empty UIUX state set"],
                            extra={"error_code": "C01U-E002"})

    product = _bucket_product_name(fields)
    stem = _safe_stem(product)
    out_dir = root / C01_UIUX_BUCKET_REL
    out_dir.mkdir(parents=True, exist_ok=True)

    svg_rel = C01_UIUX_BUCKET_REL / "uiux_wireframes.svg"
    md_rel = C01_UIUX_BUCKET_REL / f"{stem}_UIUX_Flow.md"
    readme_rel = C01_UIUX_BUCKET_REL / "README.md"

    (root / svg_rel).write_text(_build_uiux_wireframe_svg(states, has_display), encoding="utf-8")

    states_md = "\n".join(f"- {s}" for s in states)
    nodisplay_note = (
        "This product has no display screen; UI/UX maps to LED/status/button interaction (explicit design decision, not omitted)."
        if not has_display else
        "This product has a display; OLED screens/states drive the primary UI."
    )
    uiux_md = f"""# {product} — UI/UX Flow

> {_DRAFT_MARKINGS["uiux"]}

## Interaction Surface

- Source description: {display_uiux or "(derived from exposed status components)"}
- {nodisplay_note}

## States Covered

{states_md}

## State Coverage Notes

- OLED screens/states, LED state vocabulary, module insert/remove feedback, privacy/local-only state, and charging/connectivity/error states are all addressed above.

---

_{_DRAFT_MARKINGS["uiux"]}. State vocabulary must be aligned with C05 firmware; this is not UI sign-off._
"""
    (root / md_rel).write_text(uiux_md, encoding="utf-8")

    pdf_rel, pdf_note = _emit_doc_pdf(root, md_rel)
    files = [str(svg_rel), str(md_rel), str(readme_rel)]
    # Honesty (天條): only list the PDF in `files` when it actually exists on disk.
    # Pending state is communicated via extra.pdf_status + the README note — never by
    # naming a phantom file in the deliverable list (markdown is the source of truth).
    if pdf_rel is not None:
        files.append(str(pdf_rel))

    readme = f"""# Display UI_UX — Flow Bucket

> {_DRAFT_MARKINGS["uiux"]}

## Contents

- `uiux_wireframes.svg` — state wireframes.
- `{stem}_UIUX_Flow.md` — UI/UX flow document (markdown source of truth).
- `{stem}_UIUX_Flow.pdf` — {pdf_note}.
- `README.md` — this file.

## Honesty Notes

- {nodisplay_note}
- {pdf_note}
- This bucket is not UI sign-off.
"""
    (root / readme_rel).write_text(readme, encoding="utf-8")

    return BucketResult(
        status="success",
        bucket="display_uiux",
        out_dir=str(C01_UIUX_BUCKET_REL),
        files=files,
        draft_markings=[_DRAFT_MARKINGS["uiux"]],
        extra={"states": states, "has_display": has_display,
               "pdf_status": "rendered" if pdf_rel else "pending", "pdf_note": pdf_note},
    )


# ── Phase 5: readiness dual-track ───────────────────────────────────────


def _assess_id_native_track(root: Path) -> dict[str, Any]:
    """ID-native readiness track (Ai file / CMF / Display UI_UX buckets). Optional/
    demo; presence keyed by the bucket's signature primary artifact."""
    bucket_signatures = {
        "ai_file": (C01_AI_FILE_BUCKET_REL, "_ID_skeleton.svg"),
        "cmf": (C01_CMF_BUCKET_REL, "cmf_tokens.json"),
        "display_uiux": (C01_UIUX_BUCKET_REL, "uiux_wireframes.svg"),
    }
    artifacts: list[dict[str, str]] = []
    present = 0
    for key, (bucket_rel, signature) in bucket_signatures.items():
        bucket_dir = root / bucket_rel
        status = "missing"
        if bucket_dir.is_dir():
            if signature.startswith("_"):
                hit = any(p.name.endswith(signature) for p in bucket_dir.glob("*") if p.is_file())
            else:
                hit = (bucket_dir / signature).exists()
            if hit:
                status = "present"
                present += 1
            elif any(bucket_dir.iterdir()):
                status = "partial"
        artifacts.append({"key": key, "rel_path": str(bucket_rel), "status": status})
    total = len(bucket_signatures)
    return {
        "readiness_pct": round(100 * present / total),
        "present": present,
        "total": total,
        "artifacts": artifacts,
    }

