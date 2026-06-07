"""C00 PRD template and rubric loading/scaffolding.

This module loads and validates the committed C00 template artifacts,
scaffolds blank PRD source files, computes answer-state readiness, and renders
Markdown outputs from explicit answer_state values. It does not provide
fallback templates, fill missing fields, or mark human approval.
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


@dataclass(slots=True)
class C00ReadinessResult:
    folder: str
    readiness_pct: int
    status: str
    next_question: str
    field_counts: dict[str, int]
    sections: list[dict[str, Any]]
    document_gates: list[dict[str, Any]]
    downstream_handoff_gates: list[dict[str, Any]]

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "readiness_pct": self.readiness_pct,
            "status": self.status,
            "next_question": self.next_question,
            "field_counts": self.field_counts,
            "sections": self.sections,
            "document_gates": self.document_gates,
            "downstream_handoff_gates": self.downstream_handoff_gates,
            "readiness_computed": True,
            "prd_emitted": False,
            "human_approved": False,
        }


@dataclass(slots=True)
class C00EmitResult:
    folder: str
    files: list[str]
    readiness: C00ReadinessResult
    status: str = "prd_markdown_emitted"

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "files": self.files,
            "status": self.status,
            "readiness": self.readiness.to_dict(),
            "readiness_computed": True,
            "prd_emitted": True,
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


def assess_c00_prd_readiness(folder: str | Path) -> C00ReadinessResult:
    root = Path(folder)
    state = _read_answer_state(root / "C00-PRD" / "answer_state.json")
    rubric = load_c00_prd_rubric().data
    scoring = rubric["scoring_policy"]
    complete_states = set(scoring["complete_states"])
    partial_states = set(scoring["partial_states"])
    blocking_states = set(scoring["blocking_states"])

    sections = _assess_sections(state, complete_states, partial_states, blocking_states)
    section_by_id = {section["id"]: section for section in sections}
    field_counts = _field_counts(sections)
    completed_fields = field_counts.get("complete", 0)
    total_fields = field_counts.get("total", 0)
    readiness_pct = round(100 * completed_fields / total_fields) if total_fields else 0
    next_question = _next_question(sections)
    document_gates = _assess_document_gates(rubric["document_gates"], section_by_id)
    downstream_gates = _assess_downstream_gates(rubric["downstream_handoff_gates"], section_by_id)
    status = "ready" if total_fields and completed_fields == total_fields else "blocked"
    if status != "ready" and field_counts.get("partial", 0) and not field_counts.get("blocking", 0):
        status = "partial"
    return C00ReadinessResult(
        folder=str(root),
        readiness_pct=readiness_pct,
        status=status,
        next_question=next_question,
        field_counts=field_counts,
        sections=sections,
        document_gates=document_gates,
        downstream_handoff_gates=downstream_gates,
    )


def emit_c00_prd_markdown(folder: str | Path) -> C00EmitResult:
    root = Path(folder)
    c00_dir = root / "C00-PRD"
    state = _read_answer_state(c00_dir / "answer_state.json")
    readiness = assess_c00_prd_readiness(root)
    c00_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for source_filename, document in state["documents"].items():
        target = _generated_filename(source_filename)
        path = c00_dir / target
        path.write_text(_render_generated_document(source_filename, document, state, readiness), encoding="utf-8")
        written.append(str(Path("C00-PRD") / target))

    handoff_path = c00_dir / "C00_Handoff_Report.md"
    handoff_path.write_text(_render_handoff_report(readiness), encoding="utf-8")
    written.append(str(Path("C00-PRD") / "C00_Handoff_Report.md"))

    return C00EmitResult(folder=str(root), files=written, readiness=readiness)


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


def _generated_filename(source_filename: str) -> str:
    if not source_filename.endswith(".md"):
        raise C00TemplateError(f"C00 document filename must end with .md: {source_filename}")
    return source_filename.removesuffix(".md") + ".generated.md"


def _render_generated_document(source_filename: str, document: dict[str, Any], state: dict[str, Any], readiness: C00ReadinessResult) -> str:
    title = source_filename.removesuffix(".md").replace("_", " ")
    lines = [
        f"# {title}",
        "",
        "Status: generated-from-answer-state",
        f"Project: {state.get('project_name') or '{missing}'}",
        f"C00 readiness: {readiness.readiness_pct}% ({readiness.status})",
        "Human approved: false",
        "",
        "This Markdown is generated from `C00-PRD/answer_state.json`. Missing, drafted, external-needed, blocked, and accepted-risk fields remain visible; no hidden defaults are applied.",
        "",
    ]
    sections = document.get("sections") if isinstance(document, dict) else None
    if not isinstance(sections, list):
        raise C00TemplateError(f"C00 answer_state document {source_filename} sections must be a list")
    for section in sections:
        lines.extend(_render_generated_section(section))
    return "\n".join(lines).rstrip() + "\n"


def _render_generated_section(section: dict[str, Any]) -> list[str]:
    section_id = section.get("id", "")
    lines = [
        f"## {section.get('title', section_id)}",
        "",
        f"Section ID: `{section_id}`",
        f"Section state: `{section.get('state', 'missing')}`",
        "",
        "### Fields",
    ]
    fields = section.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise C00TemplateError(f"C00 answer_state section {section_id or '<unknown>'} fields must be a non-empty object")
    for name, field in fields.items():
        lines.extend(_render_generated_field(name, field))
    targets = section.get("handoff_targets") or []
    if targets:
        lines.extend(["", "### Handoff Targets"])
        lines.extend([f"- {target}" for target in targets])
    lines.append("")
    return lines


def _render_generated_field(name: str, field: Any) -> list[str]:
    if not isinstance(field, dict):
        raise C00TemplateError(f"C00 answer_state field {name} must be an object")
    state = field.get("state") or "missing"
    value = _field_value_markdown(field.get("value"), state)
    owner = field.get("owner") or "user"
    source = field.get("source") or "unspecified"
    lines = [
        f"- `{name}`: {value}",
        f"  - state: `{state}`",
        f"  - owner: `{owner}`",
        f"  - source: `{source}`",
    ]
    targets = field.get("handoff_targets") or []
    if targets:
        lines.append(f"  - handoff_targets: {', '.join(str(target) for target in targets)}")
    return lines


def _field_value_markdown(value: Any, state: str) -> str:
    if value is None or value == "":
        return "{missing}"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    if state in {"drafted", "external-needed", "blocked", "accepted-risk"}:
        return f"{text} _[{state}]_"
    return text


def _render_handoff_report(readiness: C00ReadinessResult) -> str:
    lines = [
        "# C00 Handoff Report",
        "",
        f"Readiness: {readiness.readiness_pct}% ({readiness.status})",
        f"Next question: {readiness.next_question}",
        "Human approved: false",
        "",
        "## Field Counts",
        "",
    ]
    for key, value in readiness.field_counts.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Document Gates", ""])
    for gate in readiness.document_gates:
        blockers = gate.get("blocking_sections") or []
        lines.append(f"- `{gate.get('gate', '')}`: {gate.get('status', '')}; blockers: {', '.join(blockers) if blockers else 'none'}")
    lines.extend(["", "## Downstream Handoff Gates", ""])
    for gate in readiness.downstream_handoff_gates:
        blockers = gate.get("blocking_sections") or []
        lines.append(f"- `{gate.get('target', '')}`: {gate.get('status', '')}; blockers: {', '.join(blockers) if blockers else 'none'}")
    return "\n".join(lines).rstrip() + "\n"


def _read_answer_state(path: Path) -> dict[str, Any]:
    data = _read_json_object(path)
    if data.get("schema") != "bodesign.c00.answer_state.v1":
        raise C00TemplateError(f"C00 answer_state.json has unsupported schema: {path}")
    documents = data.get("documents")
    if not isinstance(documents, dict) or not documents:
        raise C00TemplateError(f"C00 answer_state.json documents must be a non-empty object: {path}")
    return data


def _assess_sections(
    state: dict[str, Any],
    complete_states: set[str],
    partial_states: set[str],
    blocking_states: set[str],
) -> list[dict[str, Any]]:
    assessed: list[dict[str, Any]] = []
    for filename, document in state["documents"].items():
        sections = document.get("sections") if isinstance(document, dict) else None
        if not isinstance(sections, list):
            raise C00TemplateError(f"C00 answer_state document {filename} sections must be a list")
        for section in sections:
            if not isinstance(section, dict):
                raise C00TemplateError(f"C00 answer_state document {filename} section must be an object")
            fields = section.get("fields")
            if not isinstance(fields, dict) or not fields:
                raise C00TemplateError(f"C00 answer_state section {section.get('id', '<unknown>')} fields must be a non-empty object")
            field_items = [_assess_field(name, value, complete_states, partial_states, blocking_states) for name, value in fields.items()]
            assessed.append({
                "document": filename,
                "id": section.get("id", ""),
                "title": section.get("title", ""),
                "status": _section_status(field_items),
                "fields": field_items,
                "consultant_prompts": section.get("consultant_prompts") or [],
                "handoff_targets": section.get("handoff_targets") or [],
            })
    return assessed


def _assess_field(
    name: str,
    value: Any,
    complete_states: set[str],
    partial_states: set[str],
    blocking_states: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise C00TemplateError(f"C00 answer_state field {name} must be an object")
    state = value.get("state")
    if not isinstance(state, str) or not state:
        raise C00TemplateError(f"C00 answer_state field {name} has invalid state")
    if state in complete_states:
        status = "complete"
    elif state in partial_states:
        status = "partial"
    elif state in blocking_states:
        status = "blocking"
    else:
        raise C00TemplateError(f"C00 answer_state field {name} has unknown state: {state}")
    return {
        "key": name,
        "state": state,
        "status": status,
        "owner": value.get("owner"),
        "source": value.get("source"),
        "handoff_targets": value.get("handoff_targets") or [],
    }


def _section_status(fields: list[dict[str, Any]]) -> str:
    statuses = {field["status"] for field in fields}
    if statuses == {"complete"}:
        return "ready"
    if "blocking" in statuses:
        return "blocked"
    return "partial"


def _field_counts(sections: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"total": 0, "complete": 0, "partial": 0, "blocking": 0}
    for section in sections:
        for field in section["fields"]:
            counts["total"] += 1
            counts[field["status"]] += 1
    return counts


def _next_question(sections: list[dict[str, Any]]) -> str:
    for section in sections:
        if section["status"] != "blocked":
            continue
        prompts = section.get("consultant_prompts") or []
        if prompts:
            return str(prompts[0])
        for field in section["fields"]:
            if field["status"] == "blocking":
                return f"Please provide C00 field `{field['key']}` for section `{section['id']}`."
    return "All C00 fields are complete enough for the current rubric."


def _assess_document_gates(gates: list[dict[str, Any]], section_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    assessed = []
    for gate in gates:
        required = gate.get("required_sections") or []
        statuses = [_status_for_section(section_by_id, section_id) for section_id in required]
        assessed.append({
            "gate": gate.get("gate", ""),
            "status": _gate_status(statuses),
            "required_sections": required,
            "blocking_sections": [section_id for section_id, status in zip(required, statuses) if status in {"blocked", "missing"}],
            "description": gate.get("description", ""),
        })
    return assessed


def _assess_downstream_gates(gates: list[dict[str, Any]], section_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    assessed = []
    for gate in gates:
        required = gate.get("source_sections") or []
        statuses = [_status_for_section(section_by_id, section_id) for section_id in required]
        assessed.append({
            "target": gate.get("target", ""),
            "status": _gate_status(statuses),
            "source_sections": required,
            "blocking_sections": [section_id for section_id, status in zip(required, statuses) if status in {"blocked", "missing"}],
            "ready_when": gate.get("ready_when") or [],
        })
    return assessed


def _status_for_section(section_by_id: dict[str, dict[str, Any]], section_id: str) -> str:
    section = section_by_id.get(section_id)
    return section["status"] if section else "missing"


def _gate_status(statuses: list[str]) -> str:
    if statuses and all(status == "ready" for status in statuses):
        return "ready"
    if any(status in {"blocked", "missing"} for status in statuses):
        return "blocked"
    return "partial"


def _sections_for(data: dict[str, Any], filename: str) -> list[dict[str, Any]]:
    for document in data.get("documents", []):
        if isinstance(document, dict) and document.get("file") == filename:
            sections = document.get("sections")
            return sections if isinstance(sections, list) else []
    return []
