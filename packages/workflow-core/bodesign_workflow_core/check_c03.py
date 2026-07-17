"""C03→C04 stage-entry readiness gate (BR_20260707).

Deterministic machine check that C03 (EE) delivery is complete BEFORE C04 layout
may start. The pre-existing bodesign lifecycle only had a C04 *output* gate
(check_c04: copper/unconnected/SI); there was no C04 *entry* gate on C03
deliverable completeness — so an incomplete BOM (draft/blocked rows, BOM↔SSOT
conflicts, unfrozen pad counts) leaked into C04 and was only found by downstream
collisions. This module is that entry gate.

Design (matches prd_bom_crosscheck): pure function, no LLM, no fallback. Missing
inputs raise (typed); blocking findings return normally as gate="FAIL". Gate
thresholds are NEVER relaxed to pass (check_c04 floating-PSRAM false-pass lesson,
AGENTS.md §3).

Hard-fail conditions (BR acceptance criteria R1–R4):
  R1 BOM schema lint   — inconsistent column count (quoting breakage) / bad status
                         enum / duplicate (board, ref)
  R2 BOM readiness     — any draft/blocked row; a finalized row whose mpn carries
                         TBC/TBD/UNDECIDED
  R3 drawability       — every row needs a symbol-source marker
                         (official | vendor+LCSC id | manual | N-A)
  R4 SSOT crosscheck   — active BOM parts vs Pin_Allocation.csv agree (no
                         wireless/interface-scheme conflict); J_* pad counts match
                         a frozen tally when provided
Warn (non-blocking): stock=0, mechanical MPN TBC — procurement notes.

Error codes:
  BOM_MISSING          bom csv absent
  BOM_EMPTY            zero data rows
  PIN_ALLOC_MISSING    pin-allocation csv named but absent
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

REPORT_SCHEMA = "bodesign.c03.stage_entry_gate.v1"
REPORT_FILENAME = "check_c03.report.json"

# Allowed BOM row lifecycle states.
_STATUS_ENUM = {"finalized", "draft", "blocked", "proposed", "alternate"}
# States that block C04 entry outright.
_BLOCKING_STATUS = {"draft", "blocked"}
# Placeholder tokens forbidden in a finalized part's mpn (case-insensitive).
_FORBIDDEN_MPN = ("tbc", "tbd", "undecided", "todo", "xxx", "???")
# Recognised symbol-source markers (R3 drawability).
_SYMBOL_SOURCES = ("official", "vendor", "lcsc", "manual", "n-a", "n/a")
# Reference prefixes considered "active" for the SSOT crosscheck (drive interfaces).
_ACTIVE_PREFIXES = ("U", "J", "Y", "SW")


@dataclass
class RowFinding:
    board: str
    ref: str
    code: str            # R1_SCHEMA | R2_READINESS | R3_DRAWABILITY | R4_SSOT
    detail: str


@dataclass
class CheckC03Result:
    schema: str = REPORT_SCHEMA
    gate: str = "PASS"                       # 'PASS' | 'FAIL'
    blocking: list[RowFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    bom_rows: int = 0
    active_parts: int = 0
    ssot_checked: bool = False


# ── CSV loading (quoting-破損 surfaces as a schema finding, not a crash) ─────

def _read_csv_rows(path: str) -> tuple[list[str], list[list[str]]]:
    """Return (header, raw_rows) with each raw row kept as a list so a row whose
    physical column count differs from the header (quoting breakage) is detectable.
    Uses csv so quoted commas are honoured; a genuinely malformed quote still yields
    a mismatched-length row rather than an exception."""
    text = Path(path).read_text(encoding="utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if r and any(c.strip() for c in r)]
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _col_index(header: list[str], *names: str) -> int | None:
    low = [_norm(h) for h in header]
    for n in names:
        if n in low:
            return low.index(n)
    return None


# ── individual checks (pure) ────────────────────────────────────────────────

def _check_schema(header: list[str], raw_rows: list[list[str]],
                  status_i: int | None, board_i: int | None, ref_i: int | None) -> list[RowFinding]:
    findings: list[RowFinding] = []
    ncol = len(header)
    seen: set[tuple[str, str]] = set()
    for n, row in enumerate(raw_rows, start=2):  # line 1 = header
        board = row[board_i].strip() if (board_i is not None and board_i < len(row)) else ""
        ref = row[ref_i].strip() if (ref_i is not None and ref_i < len(row)) else ""
        if len(row) != ncol:
            findings.append(RowFinding(board, ref or f"line{n}", "R1_SCHEMA",
                                       f"column count {len(row)} != header {ncol} "
                                       "(likely CSV quoting breakage)"))
            continue
        if status_i is not None:
            st = _norm(row[status_i])
            if st and st not in _STATUS_ENUM:
                findings.append(RowFinding(board, ref or f"line{n}", "R1_SCHEMA",
                                           f"unknown status {row[status_i]!r} "
                                           f"(allowed: {sorted(_STATUS_ENUM)})"))
        if ref:
            key = (board, ref)
            if key in seen:
                findings.append(RowFinding(board, ref, "R1_SCHEMA",
                                           "duplicate (board, ref)"))
            seen.add(key)
    return findings


def _check_readiness(rows: list[dict], status_i_name: str, mpn_i_name: str) -> list[RowFinding]:
    findings: list[RowFinding] = []
    for r in rows:
        st = _norm(r.get(status_i_name, ""))
        board, ref = r.get("_board", ""), r.get("_ref", "")
        if st in _BLOCKING_STATUS:
            findings.append(RowFinding(board, ref, "R2_READINESS",
                                       f"row status={st or 'unset'} blocks C04 entry"))
        if st == "finalized":
            mpn = _norm(r.get(mpn_i_name, ""))
            if any(tok in mpn for tok in _FORBIDDEN_MPN):
                findings.append(RowFinding(board, ref, "R2_READINESS",
                                           f"finalized row mpn carries placeholder ({r.get(mpn_i_name)!r})"))
    return findings


def _check_drawability(rows: list[dict], symbol_i_name: str | None) -> list[RowFinding]:
    findings: list[RowFinding] = []
    for r in rows:
        board, ref = r.get("_board", ""), r.get("_ref", "")
        marker = _norm(r.get(symbol_i_name, "")) if symbol_i_name else ""
        if not marker or not any(s in marker for s in _SYMBOL_SOURCES):
            findings.append(RowFinding(board, ref, "R3_DRAWABILITY",
                                       "no symbol source marker "
                                       "(official | vendor+LCSC | manual | N-A)"))
    return findings


def _load_pin_alloc_refs(path: str) -> set[str]:
    """Refs present in the Pin_Allocation.csv SSOT (component/ref column)."""
    header, raw = _read_csv_rows(path)
    ci = _col_index(header, "ref", "refdes", "component", "reference")
    refs: set[str] = set()
    if ci is None:
        return refs
    for row in raw:
        if ci < len(row) and row[ci].strip():
            refs.add(row[ci].strip())
    return refs


def _check_ssot(active_rows: list[dict], pin_alloc_refs: set[str]) -> list[RowFinding]:
    """Every active BOM part (drive interface: U/J/Y/SW) must appear in the
    Pin_Allocation SSOT. A BOM-only active ref means the BOM proposes a part the
    pin allocation never accounted for (the U4 wireless-scheme conflict class)."""
    findings: list[RowFinding] = []
    for r in active_rows:
        ref = r.get("_ref", "")
        if ref and ref not in pin_alloc_refs:
            findings.append(RowFinding(r.get("_board", ""), ref, "R4_SSOT",
                                       "active part not in Pin_Allocation.csv SSOT "
                                       "(BOM↔SSOT conflict — owner must reconcile)"))
    return findings


# ── top level ───────────────────────────────────────────────────────────────

def check_c03(bom_csv: str, *, pin_allocation_csv: str | None = None,
              frozen_pad_counts: dict | None = None,
              out_dir: str | None = None) -> CheckC03Result:
    """C03→C04 stage-entry gate. Deterministic; missing inputs raise, blocking
    findings return normally as gate=FAIL. Never relaxes a threshold to pass.

    frozen_pad_counts: optional {ref: expected_pad_count}; when a BOM row for that
    ref carries a pad-count column, a mismatch is a R4_SSOT blocker (J_* freeze).
    """
    if not os.path.isfile(bom_csv):
        raise ValueError(f"BOM_MISSING: {bom_csv} not found — run C03 BOM export first.")
    header, raw_rows = _read_csv_rows(bom_csv)
    if not raw_rows:
        raise ValueError(f"BOM_EMPTY: {bom_csv} has a header but zero data rows.")

    board_i = _col_index(header, "board", "board_id")
    ref_i = _col_index(header, "ref", "refdes", "reference")
    status_i = _col_index(header, "status", "state")
    mpn_i = _col_index(header, "mpn", "manufacturer_part_number", "part_number")
    symbol_i = _col_index(header, "symbol_source", "symbol", "sym_source", "drawability")
    pad_i = _col_index(header, "pad_count", "pads", "pad_qty")
    stock_i = _col_index(header, "stock", "in_stock")

    findings: list[RowFinding] = []
    # R1 schema (uses raw rows for column-count breakage)
    findings += _check_schema(header, raw_rows, status_i, board_i, ref_i)

    # Build dict rows only from well-formed rows for R2–R4.
    ncol = len(header)
    dict_rows: list[dict] = []
    for row in raw_rows:
        if len(row) != ncol:
            continue
        d = {header[i]: row[i] for i in range(ncol)}
        d["_board"] = row[board_i].strip() if board_i is not None else ""
        d["_ref"] = row[ref_i].strip() if ref_i is not None else ""
        dict_rows.append(d)

    status_name = header[status_i] if status_i is not None else "status"
    mpn_name = header[mpn_i] if mpn_i is not None else "mpn"
    symbol_name = header[symbol_i] if symbol_i is not None else None

    findings += _check_readiness(dict_rows, status_name, mpn_name)
    findings += _check_drawability(dict_rows, symbol_name)

    active_rows = [r for r in dict_rows
                   if r.get("_ref", "").upper().startswith(_ACTIVE_PREFIXES)]

    ssot_checked = False
    if pin_allocation_csv:
        if not os.path.isfile(pin_allocation_csv):
            raise ValueError(f"PIN_ALLOC_MISSING: {pin_allocation_csv} not found.")
        pin_refs = _load_pin_alloc_refs(pin_allocation_csv)
        findings += _check_ssot(active_rows, pin_refs)
        ssot_checked = True

    # frozen pad-count crosscheck (J_* freeze)
    if frozen_pad_counts and pad_i is not None:
        for r in dict_rows:
            ref = r.get("_ref", "")
            if ref in frozen_pad_counts:
                raw_pad = r.get(header[pad_i], "").strip()
                try:
                    actual = int(float(raw_pad)) if raw_pad else None
                except ValueError:
                    actual = None
                expect = frozen_pad_counts[ref]
                if actual is None or actual != expect:
                    findings.append(RowFinding(r.get("_board", ""), ref, "R4_SSOT",
                                               f"pad_count {raw_pad!r} != frozen {expect}"))

    # Warnings (non-blocking): stock=0.
    warnings: list[str] = []
    if stock_i is not None:
        for r in dict_rows:
            sv = _norm(r.get(header[stock_i], ""))
            if sv in ("0", "0.0", "out", "oos"):
                warnings.append(f"{r.get('_ref','?')}: stock=0 (procurement warn)")

    result = CheckC03Result(
        schema=REPORT_SCHEMA,
        gate="FAIL" if findings else "PASS",
        blocking=findings,
        warnings=warnings,
        bom_rows=len(dict_rows),
        active_parts=len(active_rows),
        ssot_checked=ssot_checked,
    )

    if out_dir is not None:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, REPORT_FILENAME), "w", encoding="utf-8") as fp:
            json.dump(asdict(result), fp, sort_keys=True, indent=2, ensure_ascii=False)
            fp.write("\n")
    return result
