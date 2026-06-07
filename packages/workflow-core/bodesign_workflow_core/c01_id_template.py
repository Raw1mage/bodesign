"""C01 ID template/rubric loading and emitter binding (RB-3 / C01-I1).

The C01 emitter (`c01_id_package.emit_c01_rockbox_package`) writes a fixed set of
Rockbox draft carriers (`C01_OUTPUTS`). Before RB-3 those slots were hardcoded
with no link to `c01_id.template.json`, so the template was a dead design artifact
and the emitter could silently drift from the declared target package.

This module loads the committed C01 template + rubric (fail-fast, no fallback) and
binds the emitter to them: `validate_c01_outputs_binding` asserts every Rockbox
draft carrier declared in the template's `target_package.outputs` is actually
produced by `C01_OUTPUTS`, and vice-versa. The binding runs in tests and is the
mechanism that keeps "題庫 ≡ 文件架構" true for C01 as it is for C00.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .c01_id_package import C01_OUTPUTS

DEFAULT_C01_ARTIFACT_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_C01_TEMPLATE_PATH = DEFAULT_C01_ARTIFACT_DIR / "c01_id.template.json"
DEFAULT_C01_RUBRIC_PATH = DEFAULT_C01_ARTIFACT_DIR / "c01_id.rubric.json"


class C01TemplateError(ValueError):
    """Raised when the C01 template/rubric is missing, malformed, or drifts from the emitter."""


@dataclass(slots=True)
class C01IdTemplate:
    path: str
    data: dict[str, Any]

    @property
    def folder(self) -> str:
        return self.data["target_package"]["folder"]

    @property
    def outputs(self) -> list[dict[str, Any]]:
        return self.data["target_package"]["outputs"]

    def draft_carriers(self) -> list[str]:
        """Rockbox deliverable draft carriers declared in the template (folder-relative)."""
        return [o["draft_carrier"] for o in self.outputs if o.get("draft_carrier")]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.data.get("name", ""),
            "folder": self.folder,
            "draft_carriers": self.draft_carriers(),
            "output_count": len(self.outputs),
        }


@dataclass(slots=True)
class C01IdRubric:
    path: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.data.get("name", ""),
            "readiness_states": list(self.data.get("readiness_states", {}).keys()),
            "artifact_gates": [g.get("artifact", "") for g in self.data.get("artifact_gates", [])],
            "downstream_gates": [g.get("target", g.get("layer", "")) for g in self.data.get("downstream_gates", [])],
        }


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise C01TemplateError(f"{label} not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise C01TemplateError(f"{label} is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise C01TemplateError(f"{label} must be a JSON object: {path}")
    return data


def load_c01_id_template(path: str | Path | None = None) -> C01IdTemplate:
    template_path = Path(path) if path is not None else DEFAULT_C01_TEMPLATE_PATH
    data = _read_json_object(template_path, "C01 template")
    target = data.get("target_package")
    if not isinstance(target, dict) or not target.get("folder"):
        raise C01TemplateError(f"C01 template missing target_package.folder: {template_path}")
    outputs = target.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise C01TemplateError(f"C01 template missing target_package.outputs: {template_path}")
    for out in outputs:
        if not isinstance(out, dict) or "rockbox_deliverable" not in out:
            raise C01TemplateError(f"C01 template output missing rockbox_deliverable: {template_path}")
    return C01IdTemplate(path=str(template_path), data=data)


def load_c01_id_rubric(path: str | Path | None = None) -> C01IdRubric:
    rubric_path = Path(path) if path is not None else DEFAULT_C01_RUBRIC_PATH
    data = _read_json_object(rubric_path, "C01 rubric")
    if not data.get("readiness_states") or not data.get("artifact_gates"):
        raise C01TemplateError(f"C01 rubric missing readiness_states/artifact_gates: {rubric_path}")
    return C01IdRubric(path=str(rubric_path), data=data)


def validate_c01_outputs_binding(template: C01IdTemplate | None = None) -> dict[str, Any]:
    """Assert the emitter's Rockbox carriers match the template's declared carriers.

    Fails fast on drift in either direction. Returns the resolved mapping so the
    binding can be inspected/tested. Support artifacts (constraints, handoff) carry
    a null draft_carrier in the template and are not part of this carrier check.
    """
    tpl = template or load_c01_id_template()
    folder = tpl.folder
    # Template carriers, normalized to the emitter's folder-prefixed posix form.
    template_carriers = {f"{folder}/{c}" for c in tpl.draft_carriers()}
    emitter_carriers = {p.as_posix() for p in C01_OUTPUTS.values()}

    missing_in_emitter = sorted(template_carriers - emitter_carriers)
    if missing_in_emitter:
        raise C01TemplateError(
            f"C01 template declares draft carriers the emitter does not produce: {missing_in_emitter}"
        )
    # Every template carrier is produced; the emitter may add support artifacts
    # (Interface_Constraints.json, Handoff_to_ID_Designer.md) beyond the carriers.
    unmatched_emitter = sorted(
        c for c in emitter_carriers
        if c not in template_carriers
        and not c.endswith(("Interface_Constraints.json", "Handoff_to_ID_Designer.md"))
    )
    if unmatched_emitter:
        raise C01TemplateError(
            f"C01 emitter produces carriers absent from the template (drift): {unmatched_emitter}"
        )
    return {
        "folder": folder,
        "template_carriers": sorted(template_carriers),
        "emitter_carriers": sorted(emitter_carriers),
        "bound": True,
    }
