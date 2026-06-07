"""C00 PRD template and rubric loading/scaffolding.

This module loads and validates the committed C00 template artifacts and can
scaffold blank PRD source files. It does not provide fallback templates,
compute readiness, or render final PRD prose.
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


@dataclass(slots=True)
class C00ScaffoldResult:
    folder: str
    files: list[str]
    project_section_count: int
    rf_section_count: int
    status: str = "scaffold_created"

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "files": self.files,
            "status": self.status,
            "project_section_count": self.project_section_count,
            "rf_section_count": self.rf_section_count,
            "readiness_computed": False,
            "prd_emitted": False,
            "human_approved": False,
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


def scaffold_c00_prd_package(
    out_dir: str | Path,
    project_name: str | None = None,
    include_rf: bool = False,
) -> C00ScaffoldResult:
    template = load_c00_prd_template()
    root = Path(out_dir)
    c00_dir = root / "C00-PRD"
    c00_dir.mkdir(parents=True, exist_ok=True)

    documents: list[tuple[str, list[dict[str, Any]]]] = [("Project_Requirements.md", template.project_sections)]
    if include_rf:
        if not template.rf_sections:
            raise C00TemplateError("C00 template has no RF_Requirements.md sections to scaffold")
        for section in template.rf_sections:
            _validate_scaffold_section(section, Path(template.path))
        documents.append(("RF_Requirements.md", template.rf_sections))

    written: list[str] = []
    for filename, sections in documents:
        path = c00_dir / filename
        path.write_text(_render_blank_markdown(filename, sections, project_name), encoding="utf-8")
        written.append(str(Path("C00-PRD") / filename))

    answer_state = _build_answer_state(project_name, documents, include_rf)
    answer_path = c00_dir / "answer_state.json"
    answer_path.write_text(json.dumps(answer_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    written.append(str(Path("C00-PRD") / "answer_state.json"))

    return C00ScaffoldResult(
        folder=str(root),
        files=written,
        project_section_count=len(template.project_sections),
        rf_section_count=len(template.rf_sections) if include_rf else 0,
    )


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


def _validate_scaffold_section(section: Any, path: Path) -> None:
    if not isinstance(section, dict):
        raise C00TemplateError(f"C00 template section must be an object: {path}")
    for key in ("id", "title"):
        if not isinstance(section.get(key), str) or not section[key].strip():
            raise C00TemplateError(f"C00 template section missing non-empty {key}: {path}")
    value = section.get("required_fields")
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        section_id = section.get("id", "<unknown>")
        raise C00TemplateError(f"C00 template section {section_id} must have non-empty string list required_fields: {path}")


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


def _render_blank_markdown(filename: str, sections: list[dict[str, Any]], project_name: str | None) -> str:
    title = filename.removesuffix(".md").replace("_", " ")
    lines = [f"# {title}", ""]
    if project_name:
        lines.extend([f"Project: {project_name}", ""])
    lines.extend([
        "Status: scaffold-only",
        "",
        "This file is a blank C00 source scaffold. Fill content through C00 consultant intake; do not treat placeholders as answered requirements.",
        "",
    ])
    for section in sections:
        lines.extend([
            f"## {section['title']}",
            "",
            f"Section ID: `{section['id']}`",
            "",
            "State: `missing`",
            "",
            "Required fields:",
        ])
        for field in section["required_fields"]:
            lines.append(f"- `{field}`: {{missing}}")
        lines.extend(["", "Consultant prompts:"])
        prompts = section.get("consultant_prompts") or []
        if prompts:
            for prompt in prompts:
                lines.append(f"- {prompt}")
        else:
            lines.append("- {missing}: no template prompt declared for this section")
        lines.extend(["", "Handoff targets:"])
        targets = section.get("handoff_targets") or []
        if targets:
            for target in targets:
                lines.append(f"- {target}")
        else:
            lines.append("- {missing}: no handoff target declared for this section")
        lines.append("")
    return "\n".join(lines)


def _build_answer_state(project_name: str | None, documents: list[tuple[str, list[dict[str, Any]]]], include_rf: bool) -> dict[str, Any]:
    state_documents: dict[str, Any] = {}
    for filename, sections in documents:
        state_documents[filename] = {
            "sections": [
                {
                    "id": section["id"],
                    "title": section["title"],
                    "state": "missing",
                    "fields": {
                        field: {
                            "state": "missing",
                            "value": None,
                            "source": None,
                            "owner": "user",
                            "section_id": section["id"],
                            "handoff_targets": section.get("handoff_targets") or [],
                        }
                        for field in section["required_fields"]
                    },
                    "consultant_prompts": section.get("consultant_prompts") or [],
                    "handoff_targets": section.get("handoff_targets") or [],
                }
                for section in sections
            ]
        }
    return {
        "schema": "bodesign.c00.answer_state.v1",
        "status": "scaffold-only",
        "project_name": project_name,
        "include_rf": include_rf,
        "readiness_computed": False,
        "prd_emitted": False,
        "human_approved": False,
        "allowed_states": ["missing", "drafted", "answered", "external-needed", "blocked", "accepted-risk"],
        "documents": state_documents,
    }


def _sections_for(data: dict[str, Any], filename: str) -> list[dict[str, Any]]:
    for document in data.get("documents", []):
        if isinstance(document, dict) and document.get("file") == filename:
            sections = document.get("sections")
            return sections if isinstance(sections, list) else []
    return []
