"""AC26 deterministic PRD evidence checks; no rendering or approval claims."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


class C00PrdInputError(ValueError):
    """Malformed or unsupported gate inputs, never a guessed schema."""


def _error(message):
    raise C00PrdInputError("C00_PRD_INPUT: " + message)


def _read(path):
    try:
        return Path(path).read_bytes()
    except (OSError, TypeError, ValueError) as e:
        _error(f"cannot read {path!r}: {e}")


def _json(path):
    try:
        value = json.loads(_read(path))
    except (ValueError, UnicodeError) as e:
        _error(f"invalid JSON {path!r}: {e}")
    if not isinstance(value, dict):
        _error(f"JSON object required: {path!r}")
    return value


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _strings(value, key):
    if (not isinstance(value, list)
            or any(not isinstance(s, str) or not s.strip() for s in value)
            or len(set(value)) != len(value)):
        _error(f"{key} requires unique nonempty strings")
    return value


def _text(data, key):
    try:
        return data.decode("utf-8-sig")
    except UnicodeError as e:
        _error(f"{key} requires UTF-8: {e}")


def _gate(bad, detail, status=None):
    return {"status": status or ("fail" if bad else "pass"),
            "offenders": bad, "detail": detail}


def _ids(text, universe):
    # Derive requirement families only from bridge/manifest IDs, not unrelated JSON IDs.
    prefixes = {match[1] for rid in universe if (match := re.fullmatch(r"(.+)-\d+", rid))}
    found = set()
    for prefix in prefixes:
        found.update(re.findall(r"(?<![\w-])" + re.escape(prefix) + r"-\d+(?![\w-])", text))
    for rid in universe:
        if re.search(r"(?<![\w-])" + re.escape(rid) + r"(?![\w-])", text):
            found.add(rid)
    return found


def _coverage(expected, actual, where):
    return ([{"id": rid, "where": where, "reason": "missing"} for rid in sorted(expected - actual)]
            + [{"id": rid, "where": where, "reason": "orphan"} for rid in sorted(actual - expected)])


def c00_prd_gate(manifest_path, requirements_bridge_path, decision_log_path,
                 bom_csv_path=None, board_manifest_path=None):
    """Return measured consistency only; unmeasured is not stage acceptance.

    PDF method counts uncompressed explicit /Type /Page indirect objects, not
    /Pages nodes or stream content. Object-stream PDFs are explicitly unmeasured.
    """
    m = _json(manifest_path)
    base = Path(manifest_path).resolve().parent
    inputs = {"manifest_sha256": _sha(_read(manifest_path))}
    for key in ("source_docx_sha256", "source_body_md_sha256", "decision_log_sha256",
                "requirements_bridge_sha256", "output_docx_sha256", "output_pdf_sha256"):
        if not isinstance(m.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", m[key]):
            _error(f"{key} must be lowercase SHA256")
    req_decl = set(_strings(m.get("requirement_ids"), "requirement_ids"))
    dec_decl = set(_strings(m.get("decision_ids"), "decision_ids"))
    if type(m.get("page_count")) is not int or m["page_count"] <= 0:
        _error("page_count must be a positive integer")
    pipeline = m.get("pipeline")
    if (not isinstance(pipeline, dict) or not isinstance(pipeline.get("tool"), str)
            or not isinstance(pipeline.get("version"), str) or not pipeline["version"].strip()
            or not any(k in pipeline for k in ("served", "repo-function"))):
        _error("pipeline requires tool, version and served or repo-function provenance")
    bad, data, paths = [], {}, {}
    for key in ("source_docx_path", "source_body_md_path", "decision_log_path",
                "requirements_bridge_path", "output_docx_path", "output_pdf_path", "markdown_path"):
        value = m.get(key)
        if not isinstance(value, str) or not value.strip():
            bad.append({"field": key, "reason": "missing path"})
            continue
        path = base / value
        paths[key] = path.resolve()
        if not path.is_file():
            bad.append({"field": key, "path": str(path), "reason": "missing file"})
            continue
        data[key] = _read(path)
        inputs[key.removesuffix("_path") + "_sha256"] = _sha(data[key])
        hashkey = key.removesuffix("_path") + "_sha256"
        if hashkey in m and inputs[hashkey] != m[hashkey]:
            bad.append({"field": hashkey, "declared": m[hashkey], "actual": inputs[hashkey]})
    if pipeline["tool"] not in {"bodesign_emit_doc", "docxmcp"}:
        bad.append({"field": "pipeline.tool", "reason": "unapproved pipeline", "actual": pipeline["tool"]})
    for key, arg in (("requirements_bridge_path", requirements_bridge_path),
                     ("decision_log_path", decision_log_path)):
        raw = _read(arg)
        inputs["argument_" + key.removesuffix("_path") + "_sha256"] = _sha(raw)
        if _sha(raw) != m[key.removesuffix("_path") + "_sha256"]:
            bad.append({"field": key, "reason": "argument SHA mismatch"})
        if key in paths and Path(arg).resolve() != paths[key]:
            bad.append({"field": key, "reason": "argument path differs from manifest"})
    p01 = _gate(bad, {"pipeline": pipeline, "provenance": "declared, not execution-attested"})

    bridge = _json(requirements_bridge_path)
    required = set()
    for key in ("functional_requirements", "non_functional_requirements", "enclosure_requirements"):
        rows = bridge.get(key)
        if (not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get("id"), str)
                                             or not row["id"].strip() for row in rows)):
            _error(f"bridge schema mismatch: {key} must be an array of objects with id")
        ids = [row["id"] for row in rows]
        if len(set(ids)) != len(ids) or required.intersection(ids):
            _error(f"bridge schema mismatch: duplicate requirement id in {key}")
        required.update(ids)
    if not required:
        _error("bridge schema mismatch: empty requirement universe")
    md = _text(data["markdown_path"], "markdown_path") if "markdown_path" in data else ""
    doc = ""
    bad = _coverage(required, req_decl, "manifest.requirement_ids")
    if "output_docx_path" in data:
        try:
            with zipfile.ZipFile(io.BytesIO(data["output_docx_path"])) as z:
                root = ET.fromstring(z.read("word/document.xml"))
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            doc = "\n".join("".join(p.itertext()) for p in root.iter(ns + "p"))
        except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError) as e:
            _error(f"malformed DOCX: {e}")
    else:
        bad.append({"field": "output_docx_path", "reason": "coverage unavailable"})
    for where, text in (("markdown", md), ("docx", doc)):
        bad.extend(_coverage(required, _ids(text, required | req_decl), where))
    p02 = _gate(bad, {"requirement_ids": sorted(required), "method": "bounded ID tokens; DOCX document.xml paragraph text"})

    log = _text(_read(decision_log_path), "decision_log_path")
    decisions = set(re.findall(r"^###[ \t]+((?:D|PO)-\d+)(?=[ \t]|$)", log, re.M))
    if not decisions:
        _error("decision log schema mismatch: no level-3 D-n/PO-n headings")
    cited = set(re.findall(r"(?<![\w-])(?:D|PO)-\d+(?![\w-])", md))
    bad = _coverage(decisions, dec_decl, "manifest.decision_ids")
    bad.extend(_coverage(decisions, cited, "markdown"))
    p03 = _gate(bad, {"decision_ids": sorted(decisions), "method": "level-3 heading IDs, including repealed decisions"})

    bad, detail, measured, unmeasured = [], {}, ["P-01", "P-02", "P-03"], []
    if bom_csv_path is None:
        unmeasured.append("P-04 BOM consistency: bom_csv_path not supplied")
    else:
        present = _strings(m.get("expects_in_bom"), "expects_in_bom")
        absent = _strings(m.get("expects_absent_from_bom"), "expects_absent_from_bom")
        raw = _read(bom_csv_path)
        inputs["bom_csv_sha256"] = _sha(raw)
        try:
            rows = list(csv.reader(io.StringIO(_text(raw, "bom_csv_path")), strict=True))
        except csv.Error as e:
            _error(f"malformed BOM CSV: {e}")
        cells = [cell for row in rows for cell in row]
        def contains(token):
            return any(re.search(r"(?<![\w-])" + re.escape(token) + r"(?![\w-])", cell) for cell in cells)
        bad.extend({"token": t, "reason": "missing from BOM"} for t in present if not contains(t))
        bad.extend({"token": t, "reason": "forbidden in BOM"} for t in absent if contains(t))
        detail["bom"] = {"rows": len(rows), "expects_in_bom": present, "expects_absent_from_bom": absent}
        measured.append("P-04 BOM consistency")
    if board_manifest_path is None:
        unmeasured.append("P-04 outline consistency: board_manifest_path not supplied")
    else:
        expected = m.get("expects_board_outline_mm")
        def number(n):
            return type(n) in (int, float) and math.isfinite(n)
        if not isinstance(expected, list) or len(expected) != 2 or any(not number(n) or n <= 0 for n in expected):
            _error("expects_board_outline_mm requires positive finite [width,height]")
        board = _json(board_manifest_path)
        inputs["board_manifest_sha256"] = _sha(_read(board_manifest_path))
        outline = board.get("outline")
        polygon = outline.get("polygon") if isinstance(outline, dict) else None
        if (not isinstance(outline, dict) or outline.get("units") != "mm"
                or not isinstance(polygon, list) or len(polygon) < 3
                or any(not isinstance(p, list) or len(p) != 2 or any(not number(n) for n in p) for p in polygon)):
            _error("board outline schema mismatch: mm polygon with finite XY vertices required")
        actual = [max(p[i] for p in polygon) - min(p[i] for p in polygon) for i in (0, 1)]
        if any(abs(a - e) > 0.01 + 1e-12 for a, e in zip(actual, expected)):
            bad.append({"field": "expects_board_outline_mm", "expected": expected, "actual": actual})
        detail["outline"] = {"actual_mm": actual, "expected_mm": expected, "tolerance_mm": 0.01}
        measured.append("P-04 outline consistency")
    p04 = _gate(bad, detail, "fail" if bad else ("pass" if bom_csv_path is not None and board_manifest_path is not None else "unmeasured"))

    pdf = data.get("output_pdf_path", b"")
    bad = []
    if not pdf or not pdf.startswith(b"%PDF-") or not pdf.rstrip().endswith(b"%%EOF"):
        bad.append({"field": "output_pdf_path", "reason": "empty or invalid PDF header/trailer"})
    # Strip streams before interpreting dictionaries; page-like text in content is not a page.
    objects = re.findall(rb"\b\d+\s+\d+\s+obj\b(.*?)\bendobj\b", pdf, re.S)
    dictionaries = [re.split(rb"\bstream\b", obj, maxsplit=1)[0] for obj in objects]
    unsupported = any(re.search(rb"/Type\s*/ObjStm\b", obj) for obj in dictionaries)
    count = sum(bool(re.search(rb"/Type\s*/Page(?![A-Za-z0-9])", obj)) for obj in dictionaries)
    if not unsupported and count != m["page_count"]:
        bad.append({"field": "page_count", "expected": m["page_count"], "actual": count})
    measured.append("P-05 PDF header/trailer")
    if unsupported:
        unmeasured.append("P-05 page count: compressed object streams unsupported")
    else:
        measured.append("P-05 page count")
    p05 = _gate(bad, {"page_count": None if unsupported else count,
                     "method": "explicit indirect /Type /Page objects; stream bodies excluded",
                     "object_streams_supported": False}, "fail" if bad else ("unmeasured" if unsupported else "pass"))
    unmeasured.extend(["P-05 fonts-embedded", "P-05 rendered overflow", "visual readability/comprehension",
                       "pipeline execution attestation", "upstream requirement availability timing", "human approval"])
    gates = dict(zip(("P-01", "P-02", "P-03", "P-04", "P-05"), (p01, p02, p03, p04, p05)))
    return {"ok": all(g["status"] != "fail" for g in gates.values()), "gates": gates,
            "measured": measured, "unmeasured": unmeasured, "inputs": inputs}
