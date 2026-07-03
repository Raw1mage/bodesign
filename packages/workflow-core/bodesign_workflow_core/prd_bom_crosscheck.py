"""PRD-BOM crosscheck gate (plans/quality_prd-bom-crosscheck L1, DD-1..DD-5).

Deterministic fulfilment check of the C00 `main_components` role manifest
against the C03 exported KiCad netlist (.net S-expr). The LLM participates
only upstream (one-shot extraction of ``main_components_structured.json``,
human-audited on disk); this module is a pure function — same inputs, same
outputs, byte-identical serialized reports.

Error codes (see plans/quality_prd-bom-crosscheck/errors.md):
- MANIFEST_MISSING      manifest file absent
- MANIFEST_INVALID      manifest unparseable / schema violations (all reported in one pass)
- NETLIST_MISSING       netlist file absent
- NETLIST_PARSE_ERROR   netlist unparseable or zero components
GATE_FAIL is a normal return (``gate: "FAIL"``), never an exception.
MANIFEST_STALE is a warn-level report field, never an exception.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

MANIFEST_SCHEMA = "bodesign.c00.main_components_structured.v1"
REPORT_SCHEMA = "bodesign.crosscheck.prd_bom.v1"
REPORT_FILENAME = "prd_bom_crosscheck.report.json"


# ── report dataclasses (fields are the data-schema.json contract) ──────────

@dataclass
class Verdict:
    role: str
    status: str                      # 'present' | 'substituted' | 'missing'
    matched_refs: list[str] = field(default_factory=list)
    in_envelope: bool | None = None  # for substituted: matched an allowed_alternative
    approved: bool | None = None     # for out-of-envelope substituted: approvals[] entry exists
    blocking: bool = False


@dataclass
class CrosscheckResult:
    schema: str = REPORT_SCHEMA
    gate: str = "PASS"               # 'PASS' | 'FAIL'
    verdicts: list[Verdict] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)
    netlist_components: int = 0
    manifest_stale: bool | None = None


# ── lightweight S-expr parser (KiCad .net) ─────────────────────────────────

def _tokenize_sexpr(text: str) -> list[str]:
    tokens: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "()":
            tokens.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            buf: list[str] = []
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                    continue
                if text[j] == '"':
                    break
                buf.append(text[j])
                j += 1
            if j >= n:
                raise ValueError("unterminated string literal")
            tokens.append('"' + "".join(buf))
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()"':
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def _parse_sexpr(text: str):
    tokens = _tokenize_sexpr(text)
    pos = 0

    def parse():
        nonlocal pos
        if pos >= len(tokens):
            raise ValueError("unexpected end of input")
        tok = tokens[pos]
        if tok == "(":
            pos += 1
            lst = []
            while pos < len(tokens) and tokens[pos] != ")":
                lst.append(parse())
            if pos >= len(tokens):
                raise ValueError("unbalanced parentheses")
            pos += 1  # consume ')'
            return lst
        pos += 1
        if tok == ")":
            raise ValueError("unexpected ')'")
        return tok[1:] if tok.startswith('"') else tok

    node = parse()
    if pos != len(tokens):
        raise ValueError(f"trailing tokens at position {pos}")
    return node


def _child(node: list, name: str):
    for item in node:
        if isinstance(item, list) and item and item[0] == name:
            return item
    return None


def _children(node: list, name: str) -> list:
    return [item for item in node if isinstance(item, list) and item and item[0] == name]


def _atom_after(node: list | None) -> str:
    """First non-list element after the head atom, else ''."""
    if not node:
        return ""
    for item in node[1:]:
        if not isinstance(item, list):
            return str(item)
    return ""


def _parse_netlist_components(netlist_path: str) -> list[dict]:
    try:
        text = Path(netlist_path).read_text(encoding="utf-8")
        root = _parse_sexpr(text)
    except ValueError as exc:
        raise ValueError(f"NETLIST_PARSE_ERROR: cannot parse {netlist_path}: {exc}") from exc
    components_node = _child(root, "components") if isinstance(root, list) else None
    if components_node is None:
        raise ValueError(f"NETLIST_PARSE_ERROR: no (components ...) section in {netlist_path}")
    comps: list[dict] = []
    for comp in _children(components_node, "comp"):
        ref = _atom_after(_child(comp, "ref"))
        value = _atom_after(_child(comp, "value"))
        # footprint: direct (footprint "...") child, else (field (name "Footprint") "...")
        footprint = _atom_after(_child(comp, "footprint"))
        if not footprint:
            fields_node = _child(comp, "fields")
            if fields_node:
                for f_node in _children(fields_node, "field"):
                    name_node = _child(f_node, "name")
                    if name_node and _atom_after(name_node) == "Footprint":
                        footprint = _atom_after(f_node)
                        break
        libsymbol = ""
        libsource = _child(comp, "libsource")
        if libsource:
            lib = _atom_after(_child(libsource, "lib"))
            part = _atom_after(_child(libsource, "part"))
            libsymbol = f"{lib}:{part}" if (lib or part) else ""
        comps.append({"ref": ref, "value": value, "footprint": footprint, "libsymbol": libsymbol})
    if not comps:
        raise ValueError(f"NETLIST_PARSE_ERROR: zero components parsed from {netlist_path}")
    return comps


# ── manifest loading + fail-fast validation (all violations in one pass) ───

def _load_manifest(manifest_path: str) -> dict:
    p = Path(manifest_path)
    if not p.is_file():
        raise ValueError(
            f"MANIFEST_MISSING: {manifest_path} not found — extract "
            "main_components_structured.json from the C00 answer_state (LLM one-shot) "
            "and have a human audit it before running this gate."
        )
    try:
        manifest = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"MANIFEST_INVALID: {manifest_path} is not valid JSON: {exc}") from exc

    violations: list[str] = []
    if not isinstance(manifest, dict):
        raise ValueError(f"MANIFEST_INVALID: {manifest_path}: top level must be a JSON object")
    roles = manifest.get("roles")
    if not isinstance(roles, list) or not roles:
        violations.append("roles: must be a non-empty array")
        roles = []
    for i, role in enumerate(roles):
        where = f"roles[{i}]"
        if not isinstance(role, dict):
            violations.append(f"{where}: must be an object")
            continue
        rid = role.get("role")
        if not isinstance(rid, str) or not rid.strip():
            violations.append(f"{where}.role: must be a non-empty string")
        qty = role.get("qty_min")
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1:
            violations.append(f"{where}.qty_min: must be a positive integer (got {qty!r})")
        patterns = role.get("patterns")
        if not isinstance(patterns, list):
            violations.append(f"{where}.patterns: must be an array of regex strings")
        else:
            for j, pat in enumerate(patterns):
                try:
                    re.compile(pat, re.IGNORECASE)
                except (re.error, TypeError):
                    violations.append(f"{where}.patterns[{j}]: invalid regex {pat!r}")
        alts = role.get("allowed_alternatives", [])
        if not isinstance(alts, list):
            violations.append(f"{where}.allowed_alternatives: must be an array")
        else:
            for k, alt in enumerate(alts):
                aw = f"{where}.allowed_alternatives[{k}]"
                if not isinstance(alt, dict):
                    violations.append(f"{aw}: must be an object with name + patterns")
                    continue
                apats = alt.get("patterns")
                if not isinstance(apats, list) or not apats:
                    violations.append(f"{aw}.patterns: must be a non-empty array of regex strings")
                else:
                    for j, pat in enumerate(apats):
                        try:
                            re.compile(pat, re.IGNORECASE)
                        except (re.error, TypeError):
                            violations.append(f"{aw}.patterns[{j}]: invalid regex {pat!r}")
    approvals = manifest.get("approvals", [])
    if not isinstance(approvals, list):
        violations.append("approvals: must be an array")
    if violations:
        raise ValueError(
            f"MANIFEST_INVALID: {manifest_path}: " + "; ".join(violations)
        )
    return manifest


def _check_manifest_stale(manifest: dict, manifest_path: str) -> bool | None:
    """True when the recorded answer_state hash differs from the file next to the
    manifest; None when there is nothing to compare against (no hash recorded, or
    no answer_state.json sibling)."""
    recorded = manifest.get("source_answer_state_sha256")
    if not isinstance(recorded, str) or not recorded:
        return None
    sibling = Path(manifest_path).parent / "answer_state.json"
    if not sibling.is_file():
        return None
    actual = hashlib.sha256(sibling.read_bytes()).hexdigest()
    return actual != recorded


# ── deterministic matching ─────────────────────────────────────────────────

def _match_refs(patterns: list[str], components: list[dict]) -> list[str]:
    """Sorted refs of components whose value|footprint|libsymbol matches ANY pattern."""
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    hits: set[str] = set()
    for comp in components:
        haystacks = (comp["value"], comp["footprint"], comp["libsymbol"])
        for rx in compiled:
            if any(rx.search(h) for h in haystacks if h):
                hits.add(comp["ref"])
                break
    return sorted(hits)


def prd_bom_crosscheck(
    manifest_path: str,
    netlist_path: str,
    out_dir: str | None = None,
) -> CrosscheckResult:
    """Deterministic per-role fulfilment verdicts of the PRD component manifest
    against a KiCad netlist. Pure function: no LLM, no fallback — missing inputs
    raise, blocking findings return normally as gate=FAIL."""
    manifest = _load_manifest(manifest_path)
    if not os.path.isfile(netlist_path):
        raise ValueError(f"NETLIST_MISSING: {netlist_path} not found — run C03 export_netlist first.")
    components = _parse_netlist_components(netlist_path)

    approvals_by_role: dict[str, dict] = {}
    for entry in manifest.get("approvals", []):
        if isinstance(entry, dict) and isinstance(entry.get("role"), str):
            approvals_by_role[entry["role"]] = entry

    verdicts: list[Verdict] = []
    blocking_roles: list[str] = []
    for role in manifest["roles"]:
        rid = role["role"]
        qty_min = role["qty_min"]
        primary = _match_refs(role.get("patterns", []), components) if role.get("patterns") else []
        alt_refs: list[str] = []
        for alt in role.get("allowed_alternatives", []) or []:
            alt_refs.extend(_match_refs(alt["patterns"], components))
        alt_refs = sorted(set(alt_refs))

        if len(primary) >= qty_min:
            verdict = Verdict(role=rid, status="present", matched_refs=primary,
                              in_envelope=None, approved=None, blocking=False)
        elif len(alt_refs) >= qty_min:
            verdict = Verdict(role=rid, status="substituted", matched_refs=alt_refs,
                              in_envelope=True, approved=None, blocking=False)
        elif rid in approvals_by_role:
            verdict = Verdict(role=rid, status="substituted",
                              matched_refs=sorted(set(primary) | set(alt_refs)),
                              in_envelope=False, approved=True, blocking=False)
        else:
            verdict = Verdict(role=rid, status="missing",
                              matched_refs=sorted(set(primary) | set(alt_refs)),
                              in_envelope=None, approved=None, blocking=True)
            blocking_roles.append(rid)
        verdicts.append(verdict)

    stale = _check_manifest_stale(manifest, manifest_path)
    if stale:
        print(
            f"[prd_bom_crosscheck] warn: MANIFEST_STALE — answer_state.json next to "
            f"{manifest_path} no longer matches source_answer_state_sha256; re-extract "
            "the manifest to realign with the revised PRD.",
            file=sys.stderr,
        )

    result = CrosscheckResult(
        schema=REPORT_SCHEMA,
        gate="FAIL" if blocking_roles else "PASS",
        verdicts=verdicts,
        blocking=blocking_roles,
        netlist_components=len(components),
        manifest_stale=stale,
    )

    if out_dir is not None:
        os.makedirs(out_dir, exist_ok=True)
        report_path = os.path.join(out_dir, REPORT_FILENAME)
        with open(report_path, "w", encoding="utf-8") as fp:
            json.dump(asdict(result), fp, sort_keys=True, indent=2, ensure_ascii=False)
            fp.write("\n")
    return result
