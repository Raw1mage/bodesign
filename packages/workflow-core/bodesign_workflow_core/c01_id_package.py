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

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "readiness_pct": self.readiness_pct,
            "usable": self.usable,
            "next_step": self.next_step,
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
    readiness_pct = round(100 * present / len(C01_OUTPUTS))
    pending = [a for a in artifacts if a.status != "present"]
    usable = not pending
    next_step = pending[0].next_action if pending else "C01 Rockbox-like package is usable as a first-pass ID handoff."
    return C01PackageReadiness(str(root), readiness_pct, usable, next_step, artifacts)


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


def _component_list(value: Any, corpus: str) -> list[dict[str, str]]:
    if isinstance(value, list) and value:
        names = [str(v) for v in value]
    else:
        names = [name for name, keywords in EXPOSED_COMPONENT_KEYWORDS.items() if any(k in corpus for k in keywords)]
    if not names:
        names = ["missing — exposed component list not confirmed"]
    return [
        {
            "name": name,
            "placement_preference": "draft/missing — C01 must ask user or ID designer",
            "decision_status": "drafted" if not name.startswith("missing") else "missing",
            "owner": "C00 user + ID designer",
        }
        for name in names
    ]


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
