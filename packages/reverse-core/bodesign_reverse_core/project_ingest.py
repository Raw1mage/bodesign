"""Ingest a whole KiCad/EDA project folder — the docxmcp-style surface.

Given a client project folder (like 01.ROCKBOX), walk it read-only, classify
every file by EDA role/format, and produce a structured index plus a readable
summary. Flags every *non-readable* engineering file (schematic/PCB/Gerber/
OrCAD/3D) that needs a readable companion, and detects companions that already
exist beside it (e.g. an OrCAD `.DSN` next to a `.png`).

This is the "ingest" stage of the KiCad lifecycle MCP: understand the folder
before operating on it. It never mutates the folder.
"""

from dataclasses import dataclass, field
from pathlib import Path

READABLE_EXTS = {
    ".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg", ".gif", ".bmp",
    ".xlsx", ".xls", ".csv", ".tsv", ".md", ".html", ".htm", ".txt", ".svg", ".json",
}
ROLE_BY_EXT = {
    ".kicad_pro": "kicad-project", ".kicad_sch": "schematic", ".kicad_pcb": "pcb-layout",
    ".kicad_sym": "symbol-lib", ".kicad_mod": "footprint", ".net": "netlist",
    ".dsn": "orcad-schematic", ".opj": "orcad-project", ".brd": "pcb-layout",
    ".art": "gerber", ".gbr": "gerber", ".gtl": "gerber", ".gbl": "gerber", ".gto": "gerber",
    ".gbo": "gerber", ".gts": "gerber", ".gbs": "gerber", ".gko": "gerber", ".gm1": "gerber",
    ".drl": "drill", ".xln": "drill", ".nc": "drill",
    ".ipc": "ipc-netlist", ".rou": "routing-report",
    ".step": "3d-model", ".stp": "3d-model", ".stl": "3d-model", ".wrl": "3d-model",
    ".xlsx": "spreadsheet", ".xls": "spreadsheet", ".csv": "table", ".tsv": "table",
    ".pdf": "document", ".docx": "document", ".pptx": "document",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".svg": "image",
    ".c": "firmware-source", ".h": "firmware-source", ".cpp": "firmware-source",
    ".conf": "config", ".cfg": "config", ".mk": "config",
    ".zip": "archive", ".7z": "archive", ".rar": "archive", ".tar": "archive", ".gz": "archive",
    ".ai": "vector-art", ".ps": "vector-art", ".eps": "vector-art",
}
# Engineering roles whose readable companion bodesign can auto-render via KiCad/pygerber.
COMPANION_RENDERABLE = {"schematic", "pcb-layout", "gerber", "symbol-lib", "footprint"}
# Engineering roles that need the original tool (or an existing sibling) for a readable view.
COMPANION_EXTERNAL = {"orcad-schematic", "orcad-project", "3d-model", "vector-art"}


@dataclass(slots=True)
class IngestedFile:
    rel_path: str
    role: str
    ext: str
    readable: bool
    bytes: int
    needs_companion: bool
    companion: str = ""  # existing readable sibling, if any
    note: str = ""


@dataclass(slots=True)
class ProjectFolderIndex:
    root: str
    file_count: int = 0
    role_counts: dict[str, int] = field(default_factory=dict)
    sections: list[str] = field(default_factory=list)  # C01.. style top folders if present
    files: list[IngestedFile] = field(default_factory=list)
    needs_companion: list[IngestedFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "file_count": self.file_count,
            "role_counts": self.role_counts,
            "sections": self.sections,
            "needs_companion": [
                {"rel_path": f.rel_path, "role": f.role, "companion": f.companion, "note": f.note}
                for f in self.needs_companion
            ],
            "files": [
                {
                    "rel_path": f.rel_path, "role": f.role, "ext": f.ext, "readable": f.readable,
                    "bytes": f.bytes, "needs_companion": f.needs_companion, "companion": f.companion,
                }
                for f in self.files
            ],
            "warnings": self.warnings,
        }


def _classify(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in ROLE_BY_EXT:
        return ROLE_BY_EXT[ext]
    name = path.name.lower()
    if "bom" in name:
        return "bom"
    return "other"


def ingest_project_folder(root: str | Path, max_files: int = 20000) -> ProjectFolderIndex:
    base = Path(root)
    index = ProjectFolderIndex(root=str(base))
    if not base.exists():
        index.warnings.append(f"Folder not found: {base}")
        return index

    # Top-level C0* style sections (reference/product document architecture).
    index.sections = sorted(
        p.name for p in base.iterdir() if p.is_dir() and p.name[:1] == "C" and p.name[1:3].isdigit()
    )

    # Index readable siblings by stem for companion detection.
    by_stem: dict[str, list[Path]] = {}
    all_files: list[Path] = []
    for path in base.rglob("*"):
        if path.is_file():
            all_files.append(path)
            by_stem.setdefault(path.stem, []).append(path)
            if len(all_files) >= max_files:
                index.warnings.append(f"File scan capped at {max_files}; index is partial.")
                break

    for path in all_files:
        ext = path.suffix.lower()
        role = _classify(path)
        readable = ext in READABLE_EXTS
        needs = (not readable) and (role in COMPANION_RENDERABLE or role in COMPANION_EXTERNAL)
        companion = ""
        note = ""
        if needs:
            siblings = [s for s in by_stem.get(path.stem, []) if s != path and s.suffix.lower() in READABLE_EXTS]
            if siblings:
                companion = str(siblings[0].relative_to(base))
            elif role in COMPANION_RENDERABLE:
                note = "auto-render a readable companion via KiCad/pygerber"
            else:
                note = "needs the originating tool (or a supplied export) for a readable view"
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        item = IngestedFile(
            rel_path=str(path.relative_to(base)), role=role, ext=ext, readable=readable,
            bytes=size, needs_companion=needs, companion=companion, note=note,
        )
        index.files.append(item)
        index.role_counts[role] = index.role_counts.get(role, 0) + 1
        if needs and not companion:
            index.needs_companion.append(item)

    index.file_count = len(index.files)
    return index


def render_index_markdown(index: ProjectFolderIndex) -> str:
    lines = [f"# Project folder index: {index.root}", ""]
    lines.append(f"- Files indexed: **{index.file_count}**")
    if index.sections:
        lines.append(f"- Document sections: {', '.join(index.sections)}")
    lines.append("")
    lines.append("## Files by role")
    lines.append("| Role | Count |")
    lines.append("|---|---|")
    for role, count in sorted(index.role_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {role} | {count} |")
    lines.append("")
    lines.append("## Non-readable engineering files needing a readable companion")
    if index.needs_companion:
        lines.append("| File | Role | How to make it viewable |")
        lines.append("|---|---|---|")
        for f in index.needs_companion[:200]:
            lines.append(f"| `{f.rel_path}` | {f.role} | {f.note or 'companion'} |")
    else:
        lines.append("- none (every engineering file already has a readable companion)")
    lines.append("")
    if index.warnings:
        lines.append("## Warnings")
        lines.extend(f"- {w}" for w in index.warnings)
        lines.append("")
    return "\n".join(lines)
