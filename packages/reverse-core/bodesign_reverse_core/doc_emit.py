"""Emit shareable document formats from a markdown deliverable (G4 / N5).

Turns a readable markdown deliverable (PRD, readiness report, design definition)
into shareable **docx**/**pdf** via LibreOffice, so the same source can be handed
to vendors/stakeholders in their preferred format. Markdown stays the editable
source of truth; docx/pdf are generated companions.

Pipeline: markdown → minimal HTML (headings/tables/lists/inline) → `soffice
--convert-to`. Each format is a separate `soffice` call with its own profile
dir (avoids the LibreOffice single-profile lock that silently dropped the docx
in an earlier ad-hoc attempt), and each output is verified to exist.
"""

from dataclasses import dataclass, field
from pathlib import Path
import html as _html
import re
import shutil
import subprocess
import tempfile

_FORMAT_EXT = {"docx": "docx", "pdf": "pdf", "html": "html", "odt": "odt"}
# Explicit LibreOffice export filters (html→docx needs the filter named, or soffice
# errors "no export filter for ...docx").
_CONVERT_TARGET = {"docx": "docx:MS Word 2007 XML", "pdf": "pdf", "odt": "odt"}


@dataclass(slots=True)
class DocEmitResult:
    source: str
    outputs: dict[str, str] = field(default_factory=dict)   # format -> path
    status: str = "ok"                                       # ok | partial | skipped-no-soffice | failed
    warnings: list[str] = field(default_factory=list)


def markdown_to_html(md_text: str) -> str:
    out = ['<html><head><meta charset="utf-8"><style>'
           'body{font-family:sans-serif;line-height:1.4}'
           'table{border-collapse:collapse}td,th{border:1px solid #888;padding:4px 8px}'
           'code{background:#eee;padding:0 2px}</style></head><body>']

    def inline(s: str) -> str:
        s = _html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        return s

    lines = md_text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        if re.match(r"^\s*\|.*\|\s*$", ln):  # pipe table
            rows = []
            while i < n and re.match(r"^\s*\|.*\|\s*$", lines[i]):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
            out.append("<table>")
            for ri, r in enumerate(rows):
                tag = "th" if ri == 0 else "td"
                out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in r) + "</tr>")
            out.append("</table>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", ln)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if ln.startswith("> "):
            out.append(f"<blockquote>{inline(ln[2:])}</blockquote>")
            i += 1
            continue
        if re.match(r"^\s*[-*]\s+", ln):
            out.append("<ul>")
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                out.append("<li>" + inline(re.sub(r"^\s*[-*]\s+", "", lines[i])) + "</li>")
                i += 1
            out.append("</ul>")
            continue
        if re.match(r"^\s*\d+\.\s+", ln):
            out.append("<ol>")
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                out.append("<li>" + inline(re.sub(r"^\s*\d+\.\s+", "", lines[i])) + "</li>")
                i += 1
            out.append("</ol>")
            continue
        if ln.strip() in ("", "---"):
            i += 1
            continue
        out.append(f"<p>{inline(ln)}</p>")
        i += 1
    out.append("</body></html>")
    return "\n".join(out)


def emit_document(md_path: str | Path, out_dir: str | Path, formats: tuple[str, ...] = ("docx", "pdf")) -> DocEmitResult:
    source = Path(md_path)
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    result = DocEmitResult(source=str(source))

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        result.status = "skipped-no-soffice"
        result.warnings.append("LibreOffice (soffice) not found; cannot emit docx/pdf.")
        return result

    html_text = markdown_to_html(source.read_text(encoding="utf-8", errors="ignore"))
    html_path = out_root / f"{source.stem}.html"
    html_path.write_text(html_text, encoding="utf-8")

    for fmt in formats:
        ext = _FORMAT_EXT.get(fmt, fmt)
        if fmt == "html":
            result.outputs["html"] = str(html_path)
            continue
        target = _CONVERT_TARGET.get(fmt, ext)
        with tempfile.TemporaryDirectory(prefix="bodesign-lo-") as profile:
            proc = subprocess.run(
                [soffice, "--headless", f"-env:UserInstallation=file://{profile}",
                 "--convert-to", target, "--outdir", str(out_root), str(html_path)],
                capture_output=True, text=True,
            )
        produced = out_root / f"{source.stem}.{ext}"
        if produced.exists():
            result.outputs[fmt] = str(produced)
        else:
            result.warnings.append(f"{fmt}: {(proc.stderr or proc.stdout or 'soffice produced no output').strip()[:160]}")

    wanted = [f for f in formats if f != "html"]
    got = [f for f in wanted if f in result.outputs]
    result.status = "ok" if len(got) == len(wanted) else ("partial" if got else "failed")
    return result
