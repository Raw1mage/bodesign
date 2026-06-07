"""C00 PRD template and rubric loading.

This module only loads and validates the committed C00 template artifacts. It
does not provide fallback templates, scaffold projects, compute readiness, or
render PRD documents.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_C00_ARTIFACT_DIR = Path(__file__).resolve().parents[3] / "plans" / "feature_doc-package-scaffold"
DEFAULT_C00_TEMPLATE_PATH = DEFAULT_C00_ARTIFACT_DIR / "c00_prd.template.json"
DEFAULT_C00_RUBRIC_PATH = DEFAULT_C00_ARTIFACT_DIR / "c00_prd.rubric.json"


class C00TemplateError(ValueError):
    """Raised when C00 template or rubric artifacts are missing or invalid."""


@dataclass(slots=True)
class C00PrdTemplate:
    path: str
    data: dict[str, Any]
    project_sections: list[dict[str, Any]]
    rf_sections: list[dict[str, Any]]

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "name": self.data.get("name", ""),
            "project_section_count": len(self.project_sections),
            "rf_section_count": len(self.rf_sections),
            "documents": [document.get("file", "") for document in self.data.get("documents", [])],
        }


@dataclass(slots=True)
class C00PrdRubric:
    path: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "name": self.data.get("name", ""),
            "field_states": list(self.data.get("field_states", {}).keys()),
            "document_gates": [gate.get("gate", "") for gate in self.data.get("document_gates", [])],
            "downstream_targets": [gate.get("target", "") for gate in self.data.get("downstream_handoff_gates", [])],
        }


def load_c00_prd_template(path: str | Path | None = None) -> C00PrdTemplate:
    template_path = Path(path) if path is not None else DEFAULT_C00_TEMPLATE_PATH
    data = _read_json_object(template_path)
    project_sections = _validate_template(data, template_path)
    rf_sections = _sections_for(data, "RF_Requirements.md")
    return C00PrdTemplate(str(template_path), data, project_sections, rf_sections)


def load_c00_prd_rubric(path: str | Path | None = None) -> C00PrdRubric:
    rubric_path = Path(path) if path is not None else DEFAULT_C00_RUBRIC_PATH
    data = _read_json_object(rubric_path)
    _validate_rubric(data, rubric_path)
    return C00PrdRubric(str(rubric_path), data)


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise C00TemplateError(f"C00 artifact not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise C00TemplateError(f"C00 artifact is not valid JSON: {path}: {error}") from error
    if not isinstance(data, dict):
        raise C00TemplateError(f"C00 artifact must be a JSON object: {path}")
    return data


def _validate_template(data: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    documents = data.get("documents")
    if not isinstance(documents, list) or not documents:
        raise C00TemplateError(f"C00 template documents must be a non-empty list: {path}")
    project_sections = _sections_for(data, "Project_Requirements.md")
    if not project_sections:
        raise C00TemplateError(f"C00 template must include Project_Requirements.md sections: {path}")
    for section in project_sections:
        _validate_section(section, path)
    return project_sections


def _validate_section(section: Any, path: Path) -> None:
    if not isinstance(section, dict):
        raise C00TemplateError(f"C00 template section must be an object: {path}")
    for key in ("id", "title"):
        if not isinstance(section.get(key), str) or not section[key].strip():
            raise C00TemplateError(f"C00 template section missing non-empty {key}: {path}")
    for key in ("required_fields", "consultant_prompts", "handoff_targets"):
        value = section.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            section_id = section.get("id", "<unknown>")
            raise C00TemplateError(f"C00 template section {section_id} must have non-empty string list {key}: {path}")


def _validate_rubric(data: dict[str, Any], path: Path) -> None:
    field_states = data.get("field_states")
    if not isinstance(field_states, dict) or not field_states:
        raise C00TemplateError(f"C00 rubric field_states must be a non-empty object: {path}")
    for key in ("document_gates", "downstream_handoff_gates"):
        value = data.get(key)
        if not isinstance(value, list) or not value:
            raise C00TemplateError(f"C00 rubric {key} must be a non-empty list: {path}")
    scoring_policy = data.get("scoring_policy")
    if not isinstance(scoring_policy, dict) or not scoring_policy:
        raise C00TemplateError(f"C00 rubric scoring_policy must be a non-empty object: {path}")


def _sections_for(data: dict[str, Any], filename: str) -> list[dict[str, Any]]:
    for document in data.get("documents", []):
        if isinstance(document, dict) and document.get("file") == filename:
            sections = document.get("sections")
            return sections if isinstance(sections, list) else []
    return []
