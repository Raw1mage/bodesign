"""C00 PRD docx-package renderer (bodesign.c00.docx_architecture.v1).

Turns a scaffolded C00 answer_state into a docxmcp-assemblable package
(body.md + outline.md + manifest.json + template/template.dotx) whose layout
matches the stored Rockbox-derived PRD Word architecture. The renderer is
deterministic and honest: missing / drafted / external-needed / blocked /
accepted-risk field states stay visible in the rendered output; it never
fabricates content, fills defaults, or marks human approval.

It only produces the package on disk. Feeding the package to docxmcp
``assemble`` (to build the final styled .docx) is the tool layer's job.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any

from .c00_prd_template import C00TemplateError, _read_answer_state, _read_json_object

DEFAULT_C00_ARTIFACT_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_C00_DOCX_ARCH_PATH = DEFAULT_C00_ARTIFACT_DIR / "c00_prd.docx_architecture.json"

# answer_state source filename -> descriptor document file key
_DOC_FILE_MAP = {
    "Project_Requirements.md": "Project_Requirements.md",
    "RF_Requirements.md": "RF_Requirements.md",
}

# field states that, when present, append a visible "_[state]_" tag (honesty).
_TAGGED_STATES = {"drafted", "external-needed", "blocked", "accepted-risk"}


class C00DocxArchitectureError(C00TemplateError):
    """Raised when the C00 docx architecture descriptor is missing or invalid."""


@dataclass(slots=True)
class C00DocxArchitecture:
    path: str
    data: dict[str, Any]
    documents: list[dict[str, Any]]

    def document_for(self, source_filename: str) -> dict[str, Any] | None:
        key = _DOC_FILE_MAP.get(source_filename, source_filename)
        for document in self.documents:
            if document.get("file") == key:
                return document
        return None


@dataclass(slots=True)
class C00DocxPackage:
    document_file: str
    stem: str
    package_dir: str
    body_md: str
    outline_md: str
    manifest_path: str
    template_dotx: str
    files: list[str] = dataclass_field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "document_file": self.document_file,
            "stem": self.stem,
            "package_dir": self.package_dir,
            "files": list(self.files),
            "template_dotx": self.template_dotx,
        }


@dataclass(slots=True)
class C00DocxRenderResult:
    folder: str
    packages: list[C00DocxPackage]
    status: str = "docx_packages_rendered"

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "status": self.status,
            "packages": [pkg.to_dict() for pkg in self.packages],
            "human_approved": False,
        }


def load_c00_docx_architecture(path: str | Path | None = None) -> C00DocxArchitecture:
    arch_path = Path(path) if path is not None else DEFAULT_C00_DOCX_ARCH_PATH
    data = _read_json_object(arch_path)
    if data.get("schema") != "bodesign.c00.docx_architecture.v1":
        raise C00DocxArchitectureError(
            f"C00 docx architecture has unsupported schema: {arch_path}"
        )
    documents = data.get("documents")
    if not isinstance(documents, list) or not documents:
        raise C00DocxArchitectureError(
            f"C00 docx architecture documents must be a non-empty list: {arch_path}"
        )
    for document in documents:
        _validate_arch_document(document, arch_path)
    return C00DocxArchitecture(str(arch_path), data, documents)


def _validate_arch_document(document: Any, path: Path) -> None:
    if not isinstance(document, dict):
        raise C00DocxArchitectureError(f"C00 docx architecture document must be an object: {path}")
    for key in ("file", "template_dotx"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            raise C00DocxArchitectureError(
                f"C00 docx architecture document missing non-empty {key}: {path}"
            )
    sections = document.get("sections")
    if not isinstance(sections, list) or not sections:
        raise C00DocxArchitectureError(
            f"C00 docx architecture document {document.get('file')} sections must be a non-empty list: {path}"
        )
    for section in sections:
        if not isinstance(section, dict):
            raise C00DocxArchitectureError(f"C00 docx architecture section must be an object: {path}")
        for key in ("id", "title", "body_layout"):
            if not isinstance(section.get(key), str) or not section[key].strip():
                raise C00DocxArchitectureError(
                    f"C00 docx architecture section missing non-empty {key}: {path}"
                )


def render_c00_prd_docx_package(
    folder: str | Path,
    architecture: C00DocxArchitecture | None = None,
) -> C00DocxRenderResult:
    """Render docxmcp-assemblable packages for every C00 document present in the
    scaffolded answer_state. Fails fast if C00 has not been scaffolded or a
    referenced .dotx template is missing."""
    root = Path(folder)
    c00_dir = root / "C00-PRD"
    state = _read_answer_state(c00_dir / "answer_state.json")  # fail-fast if absent
    arch = architecture or load_c00_docx_architecture()

    build_root = c00_dir / "docx_build"
    build_root.mkdir(parents=True, exist_ok=True)

    project_name = state.get("project_name")
    packages: list[C00DocxPackage] = []

    for source_filename, document_state in state["documents"].items():
        arch_document = arch.document_for(source_filename)
        if arch_document is None:
            # An answer_state document with no docx architecture mapping is a
            # descriptor gap — surface it, do not silently skip.
            raise C00DocxArchitectureError(
                f"no docx architecture mapping for answer_state document {source_filename!r}"
            )
        packages.append(
            _render_document_package(
                build_root, source_filename, document_state, arch_document, state, project_name
            )
        )

    return C00DocxRenderResult(folder=str(root), packages=packages)


def _render_document_package(
    build_root: Path,
    source_filename: str,
    document_state: dict[str, Any],
    arch_document: dict[str, Any],
    state: dict[str, Any],
    project_name: str | None,
) -> C00DocxPackage:
    stem = source_filename.removesuffix(".md")
    package_dir = build_root / stem
    template_dir = package_dir / "template"
    template_dir.mkdir(parents=True, exist_ok=True)

    field_index = _index_fields(document_state)

    body_md = _render_body_md(arch_document, field_index, state, project_name)
    outline_md = _render_outline_md(arch_document)

    dotx_name = arch_document["template_dotx"]
    dotx_src = DEFAULT_C00_ARTIFACT_DIR / dotx_name
    if not dotx_src.exists():
        raise C00DocxArchitectureError(f"C00 .dotx template not found: {dotx_src}")
    dotx_dst = template_dir / "template.dotx"
    shutil.copyfile(dotx_src, dotx_dst)

    (package_dir / "body.md").write_text(body_md, encoding="utf-8")
    (package_dir / "outline.md").write_text(outline_md, encoding="utf-8")
    manifest = _render_manifest(stem)
    manifest_path = package_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    files = [
        str(Path("C00-PRD") / "docx_build" / stem / "body.md"),
        str(Path("C00-PRD") / "docx_build" / stem / "outline.md"),
        str(Path("C00-PRD") / "docx_build" / stem / "manifest.json"),
        str(Path("C00-PRD") / "docx_build" / stem / "template" / "template.dotx"),
    ]
    return C00DocxPackage(
        document_file=source_filename,
        stem=stem,
        package_dir=str(package_dir),
        body_md=body_md,
        outline_md=outline_md,
        manifest_path=str(manifest_path),
        template_dotx=str(dotx_dst),
        files=files,
    )


def _index_fields(document_state: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    """section_id -> {field_name -> field_record}."""
    index: dict[str, dict[str, dict[str, Any]]] = {}
    sections = document_state.get("sections")
    if not isinstance(sections, list):
        raise C00TemplateError("C00 answer_state document sections must be a list")
    for section in sections:
        if not isinstance(section, dict):
            raise C00TemplateError("C00 answer_state section must be an object")
        fields = section.get("fields")
        if not isinstance(fields, dict):
            raise C00TemplateError(f"C00 answer_state section {section.get('id')} fields must be an object")
        index[section.get("id", "")] = fields
    return index


def _render_manifest(stem: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "format": "docx",
        "package_type": "text-document",
        "renderer": "docx",
        "workflow_state": "decomposed",
        "stem": stem,
        "capabilities": {
            "can_assemble": True,
            "supports_front_matter": True,
            "supports_template_token": True,
        },
        "artifacts": [
            {"path": "outline.md", "kind": "outline", "required_for": ["assemble"]},
            {"path": "template/template.dotx", "kind": "template", "required_for": ["assemble"]},
        ],
        "files": [{"path": "body.md", "kind": "body"}],
    }


def _render_outline_md(arch_document: dict[str, Any]) -> str:
    lines = ["# 文件大綱", ""]
    for section in arch_document["sections"]:
        style = section.get("style", "Heading 1")
        lines.append(f"<!-- cover heading: {section['title']} (style: {style}) -->")
    return "\n".join(lines) + "\n"


def _render_body_md(
    arch_document: dict[str, Any],
    field_index: dict[str, dict[str, dict[str, Any]]],
    state: dict[str, Any],
    project_name: str | None,
) -> str:
    lines: list[str] = []
    lines.extend(_render_cover(arch_document.get("cover"), project_name, field_index))
    lines.extend(_render_revision_history(arch_document.get("revision_history"), field_index))
    for section in arch_document["sections"]:
        lines.extend(_render_section(section, field_index.get(section["id"], {})))
    return "\n".join(lines).rstrip() + "\n"


def _render_cover(cover: Any, project_name: str | None, field_index: dict[str, Any]) -> list[str]:
    if not isinstance(cover, dict):
        return []
    lines: list[str] = []
    for block in cover.get("blocks", []):
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if text is None:
            value = _lookup_top_field(block.get("source_field"), project_name, field_index)
            prefix = block.get("prefix", "")
            if value:
                text = f"{prefix}{value}"
            else:
                text = block.get("fallback", "")
        text = str(text).strip()
        if text:
            lines.append(text)
            lines.append("")
    return lines


def _lookup_top_field(name: Any, project_name: str | None, field_index: dict[str, Any]) -> str:
    if name == "project_name" and project_name:
        return str(project_name)
    if not isinstance(name, str):
        return ""
    # search every section's fields for a top-level cover field
    for fields in field_index.values():
        if isinstance(fields, dict) and name in fields:
            record = fields[name]
            if isinstance(record, dict):
                value = record.get("value")
                if value:
                    return str(value)
    return ""


def _render_revision_history(rev: Any, field_index: dict[str, Any]) -> list[str]:
    if not isinstance(rev, dict):
        return []
    heading = rev.get("heading", "Revision History")
    table = rev.get("table") or {}
    columns = table.get("columns") or ["Version", "Description of change(s)", "Date"]
    rows = _collect_rows(table.get("source"), table.get("row_fields") or [], field_index)
    lines = [f"# {heading}", ""]
    if not rows:
        rows = [["{version}", "{description}", "{date}"][: len(columns)]]
    lines.extend(_gfm_table(columns, rows))
    lines.append("")
    return lines


def _render_section(section: dict[str, Any], fields: dict[str, dict[str, Any]]) -> list[str]:
    title = section["title"]
    layout = section["body_layout"]
    lines = [f"# {title}", ""]
    renderer = _LAYOUT_RENDERERS.get(layout, _render_prose_layout)
    body = renderer(section, fields)
    lines.extend(body)
    if not body:
        lines.append("{section content pending}")
    lines.append("")
    return lines


# --- per-layout renderers -------------------------------------------------

def _render_prose_layout(section: dict[str, Any], fields: dict[str, dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for name in section.get("prose_fields", []):
        for paragraph in _field_paragraphs(name, fields):
            lines.append(paragraph)
            lines.append("")
    slot = section.get("diagram_slot")
    if isinstance(slot, dict):
        value = _field_value(slot.get("source_field"), fields)
        lines.append(value or slot.get("fallback", "{diagram pending}"))
        lines.append("")
    return lines


def _render_objective_table_layout(section: dict[str, Any], fields: dict[str, dict[str, Any]]) -> list[str]:
    cfg = section.get("objective_table") or {}
    prefix = cfg.get("label_prefix", "OBJECTIVE")
    items = _collect_items(cfg.get("source_fields") or [], fields)
    if not items:
        items = ["{objective pending}"]
    rows = [[f"{prefix} {i}", text] for i, text in enumerate(items, start=1)]
    return _gfm_table(["", ""], rows)


def _render_bullet_table_layout(section: dict[str, Any], fields: dict[str, dict[str, Any]]) -> list[str]:
    cfg = section.get("bullet_table") or {}
    items = _collect_items(cfg.get("source_fields") or [], fields)
    if not items:
        items = ["{requirement pending}"]
    rows = [[text] for text in items]
    return _gfm_table([""], rows)


def _render_bullet_list_layout(section: dict[str, Any], fields: dict[str, dict[str, Any]]) -> list[str]:
    items = _collect_items(section.get("bullet_fields") or [], fields)
    if not items:
        return ["- {item pending}"]
    return [f"- {text}" for text in items]


def _render_raci_table_layout(section: dict[str, Any], fields: dict[str, dict[str, Any]]) -> list[str]:
    cfg = section.get("raci_table") or {}
    row_label = cfg.get("row_label_column", "Service Requirement")
    owner_cols = _field_list(cfg.get("owner_columns_source_field"), fields) or cfg.get(
        "owner_columns_fallback"
    ) or ["Company", "Vendor"]
    columns = [row_label, *owner_cols]
    raw_rows = _field_structured(cfg.get("rows_source_field"), fields)
    rows: list[list[str]] = []
    for entry in raw_rows:
        if isinstance(entry, dict):
            label = str(entry.get("service_requirement", entry.get("label", "")))
            assignments = entry.get("assignments")
            if isinstance(assignments, dict):
                cells = [str(assignments.get(col, "")) for col in owner_cols]
            elif isinstance(assignments, list):
                cells = [str(c) for c in assignments][: len(owner_cols)]
                cells += [""] * (len(owner_cols) - len(cells))
            else:
                cells = [str(assignments or "")] + [""] * (len(owner_cols) - 1)
            rows.append([label, *cells])
        else:
            rows.append([str(entry), *[""] * len(owner_cols)])
    if not rows:
        rows = [["{service requirement pending}", *[""] * len(owner_cols)]]
    return _gfm_table(columns, rows)


def _render_schedule_list_layout(section: dict[str, Any], fields: dict[str, dict[str, Any]]) -> list[str]:
    cfg = section.get("schedule_list") or {}
    entries = _field_structured(cfg.get("source_field"), fields)
    rows: list[list[str]] = []
    for entry in entries:
        if isinstance(entry, dict):
            rows.append([str(entry.get("activity", "")), str(entry.get("date", ""))])
        else:
            rows.append([str(entry), ""])
    if not rows:
        rows = [["{activity pending}", "{date}"]]
    lines = _gfm_table(["Activity", "Date"], rows)
    for name in cfg.get("supporting_fields", []):
        for paragraph in _field_paragraphs(name, fields):
            lines.append("")
            lines.append(paragraph)
    return lines


def _render_contact_cards_layout(section: dict[str, Any], fields: dict[str, dict[str, Any]]) -> list[str]:
    cfg = section.get("contact_cards") or {}
    card_rows = cfg.get("card_rows") or ["Title", "AUTHOR", "PHONE", "EMAIL", "Functional Role"]
    card_fields = cfg.get("card_fields") or ["title", "name", "phone", "email", "functional_role"]
    sources = [cfg.get("source_field"), *(cfg.get("additional_sources") or [])]
    contacts: list[Any] = []
    for src in sources:
        contacts.extend(_field_structured(src, fields))
    lines: list[str] = []
    if not contacts:
        contacts = [{}]
    for contact in contacts:
        rows: list[list[str]] = []
        for label, key in zip(card_rows, card_fields):
            value = ""
            if isinstance(contact, dict):
                value = str(contact.get(key, ""))
            elif label == card_rows[0]:
                value = str(contact)
            rows.append([label, value])
        lines.extend(_gfm_table(["Field", "Value"], rows))
        lines.append("")
    return lines


_LAYOUT_RENDERERS = {
    "prose": _render_prose_layout,
    "prose_with_diagram_slot": _render_prose_layout,
    "objective_table": _render_objective_table_layout,
    "bullet_table": _render_bullet_table_layout,
    "bullet_list": _render_bullet_list_layout,
    "raci_table": _render_raci_table_layout,
    "schedule_list": _render_schedule_list_layout,
    "contact_cards": _render_contact_cards_layout,
}


# --- value helpers (honesty-preserving) -----------------------------------

def _field_record(name: Any, fields: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not isinstance(name, str):
        return None
    record = fields.get(name)
    return record if isinstance(record, dict) else None


def _tag(text: str, record: dict[str, Any] | None) -> str:
    if record is None:
        return text
    state = record.get("state")
    if state in _TAGGED_STATES:
        return f"{text} _[{state}]_"
    return text


def _field_value(name: Any, fields: dict[str, dict[str, Any]]) -> str:
    record = _field_record(name, fields)
    if record is None:
        return ""
    value = record.get("value")
    if value is None or value == "":
        state = record.get("state")
        if state and state != "missing":
            return _tag(f"{{{name}}}", record)
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    return _tag(text, record)


def _field_paragraphs(name: Any, fields: dict[str, dict[str, Any]]) -> list[str]:
    record = _field_record(name, fields)
    if record is None:
        return []
    value = record.get("value")
    if value is None or value == "":
        state = record.get("state")
        if state and state != "missing":
            return [_tag(f"{{{name}}}", record)]
        return []
    if isinstance(value, list):
        return [_tag(str(item), record) for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [_tag(json.dumps(value, ensure_ascii=False), record)]
    text = str(value).strip()
    return [_tag(text, record)] if text else []


def _field_list(name: Any, fields: dict[str, dict[str, Any]]) -> list[str]:
    record = _field_record(name, fields)
    if record is None:
        return []
    value = record.get("value")
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []


def _field_structured(name: Any, fields: dict[str, dict[str, Any]]) -> list[Any]:
    record = _field_record(name, fields)
    if record is None:
        return []
    value = record.get("value")
    if isinstance(value, list):
        return list(value)
    if value:
        return [value]
    return []


def _collect_items(field_names: list[str], fields: dict[str, dict[str, Any]]) -> list[str]:
    items: list[str] = []
    for name in field_names:
        items.extend(_field_paragraphs(name, fields))
    return items


def _collect_rows(
    source: Any, row_fields: list[str], field_index: dict[str, Any]
) -> list[list[str]]:
    entries: list[Any] = []
    for fields in field_index.values():
        if isinstance(fields, dict) and isinstance(source, str) and source in fields:
            record = fields[source]
            if isinstance(record, dict):
                value = record.get("value")
                if isinstance(value, list):
                    entries.extend(value)
                elif value:
                    entries.append(value)
            break
    rows: list[list[str]] = []
    for entry in entries:
        if isinstance(entry, dict):
            rows.append([str(entry.get(rf, "")) for rf in row_fields])
        elif isinstance(entry, list):
            rows.append([str(c) for c in entry])
        else:
            rows.append([str(entry)] + [""] * (len(row_fields) - 1))
    return rows


def _gfm_table(columns: list[str], rows: list[list[str]]) -> list[str]:
    width = len(columns)
    header = "| " + " | ".join(_escape_cell(c) for c in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for row in rows:
        cells = [_escape_cell(c) for c in row]
        cells += [""] * (width - len(cells))
        lines.append("| " + " | ".join(cells[:width]) + " |")
    return lines


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()
