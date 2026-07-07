"""BOM MPN → KiCad official symbol resolution (eda_draftsman-v2 task 1.1, IDEF0 A1).

DD-1: v2 does NOT generate symbol geometry. Each BOM MPN is resolved to a real
four-edge symbol shipped by KiCad's official library (via symbol_index). Any MPN
that cannot be confidently resolved becomes a SymbolGap (no-fallback天條); this
module NEVER fabricates geometry and NEVER guesses a lib_id it is unsure of.

Two distinct gap causes are tracked (both disposition='pending' until the user
rules on them at the task-1.2 stop gate):
  - "unresolved_mpn"     : the BOM itself carries a placeholder/undecided MPN
                           (e.g. "... (TBC)", "UNDECIDED", "class", "family",
                           "generic", "various") — nothing to resolve yet.
  - "no_official_symbol" : a concrete MPN whose device family has no symbol in
                           KiCad's official library.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pathlib import Path as _Path

from .symbol_index import SymbolNotFound, resolve as _resolve_lib_id, search as _search

# ---- vendor CAD symbols (DD-7) ---------------------------------------------
# Concrete MPNs with no official KiCad symbol but a manufacturer-backed vendor
# CAD symbol imported into vendor_symbols/ (provenance recorded there). Keyed by
# the aiguard C03 BOM MPN → (vendor lib_id, vendor library root). Entries here
# are only added AFTER ballout cross-check confirms pin fidelity (no-fallback).
_VENDOR_ROOT = _Path(__file__).resolve().parent.parent / "vendor_symbols"
_VENDOR_MAP: dict[str, str] = {
    # STM32N657L0Q3 (aiguard main MCU) ← LCSC C42457345 STM32N657L0H3Q, same die
    # / same VFBGA223; 222/222 common balls matched authoritative ballout, 0
    # mismatch (PROVENANCE.md + ballout_crosscheck.json).
    "STM32N657L0Q3": "ST_vendor:STM32N657L0H3Q",
}


def _resolve_vendor(mpn: str) -> ResolvedSymbol | None:
    """Resolve an MPN against the vendor_symbols/ library (DD-7). Returns a
    ResolvedSymbol with lib_source='vendor_cad', or None if not vendored."""
    lib_id = _VENDOR_MAP.get(mpn.strip())
    if not lib_id:
        return None
    try:
        _resolve_lib_id(lib_id, _VENDOR_ROOT)
    except (SymbolNotFound, ValueError):
        return None
    return ResolvedSymbol(mpn=mpn, lib_id=lib_id, lib_source="vendor_cad")

# ---- placeholder / undecided MPN detectors (BOM-level gaps) -----------------
_PLACEHOLDER_RE = re.compile(
    r"\b(tbc|tbd|tbe|undecided|generic|various|class|family|holder|n/?a)\b"
    r"|castellated|half-hole|headers|test\s*points|^\s*$",
    re.IGNORECASE,
)


@dataclass
class ResolvedSymbol:
    mpn: str
    lib_id: str
    lib_source: str = "official"
    pin_map: dict = field(default_factory=dict)
    refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mpn": self.mpn,
            "lib_id": self.lib_id,
            "lib_source": self.lib_source,
            "pin_map": self.pin_map,
            "refs": self.refs,
        }


@dataclass
class SymbolGap:
    mpn: str
    package: str = ""
    pin_count: int = 0
    disposition: str = "pending"
    cause: str = "no_official_symbol"  # unresolved_mpn | no_official_symbol
    refs: list[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "mpn": self.mpn,
            "package": self.package,
            "pin_count": self.pin_count,
            "disposition": self.disposition,
            "cause": self.cause,
            "refs": self.refs,
            "note": self.note,
        }


def _is_placeholder(mpn: str) -> bool:
    """A BOM MPN that is not yet a concrete orderable part number."""
    if not mpn or not mpn.strip():
        return True
    return bool(_PLACEHOLDER_RE.search(mpn))


def _core_mpn(mpn: str) -> str:
    """Strip trailing qualifiers like '(TBC)' / 'class' to get the concrete core."""
    s = re.sub(r"\(.*?\)", "", mpn)
    s = re.sub(r"\b(class|family)\b", "", s, flags=re.IGNORECASE)
    return s.strip()


def _family_terms(mpn: str) -> list[str]:
    """Candidate search terms, longest→shortest, for official-lib family match."""
    core = _core_mpn(mpn)
    terms: list[str] = []
    if core:
        terms.append(core)
        # progressively shorten an alnum head (e.g. STM32N657L0Q3 → STM32N657 → STM32N6)
        m = re.match(r"([A-Za-z]+\d+[A-Za-z]*\d*)", core)
        if m:
            head = m.group(1)
            for n in range(len(head), 4, -1):
                cand = head[:n]
                if cand not in terms:
                    terms.append(cand)
    # de-dup preserving order
    seen: set[str] = set()
    out = []
    for t in terms:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            out.append(t)
    return out


def resolve_mpn(mpn: str, root: Path | None = None) -> tuple[ResolvedSymbol | None, SymbolGap | None]:
    """Resolve ONE MPN. Returns (ResolvedSymbol, None) on a confident hit,
    else (None, SymbolGap). Never fabricates or guesses (no-fallback)."""
    if _is_placeholder(mpn):
        return None, SymbolGap(mpn=mpn, cause="unresolved_mpn",
                               note="BOM MPN 為未定案/佔位料號，無可解析對象")
    # DD-7: a manufacturer-backed vendor CAD symbol (ballout-verified) takes
    # precedence over official-library family matching for MPNs the official
    # KiCad library does not cover (e.g. STM32N657).
    vendored = _resolve_vendor(mpn)
    if vendored is not None:
        return vendored, None
    # search official library for the device family.
    # DD-1 no-fallback: only accept a hit whose symbol name matches the concrete
    # core MPN closely enough. A family-shortened search term (e.g. STM32N657 →
    # STM32) can grep-hit an unrelated part (STM32C0), so we score the actual
    # symbol name against the core MPN and reject weak matches as low-confidence
    # gaps rather than silently mis-resolving.
    core = _core_mpn(mpn).lower()
    best_lib_id = None
    best_score = -1
    for term in _family_terms(mpn):
        for h in _search(term, root):
            name = h.split(":", 1)[1].lower()
            score = _common_prefix_len(name, core)
            if score > best_score:
                best_score, best_lib_id = score, h
        if best_lib_id is not None:
            break
    # acceptance threshold: symbol name must share a meaningful prefix with the
    # core MPN. Require at least 6 leading chars in common (e.g. "stm32n") — a
    # bare "stm32" family collision scores 5 and is rejected.
    MIN_PREFIX = 6
    if best_lib_id is None:
        return None, SymbolGap(mpn=mpn, cause="no_official_symbol",
                               note="官方 symbol 庫查無此料號家族")
    if best_score < MIN_PREFIX:
        return None, SymbolGap(
            mpn=mpn, cause="low_confidence",
            note=f"最接近的官方 symbol 為 {best_lib_id}（共同前綴僅 {best_score} 字），"
                 f"低於門檻不自動採用，交人工確認 substitute")
    # verify the lib_id actually loads (guards against stale grep hits)
    try:
        _resolve_lib_id(best_lib_id, root)
    except (SymbolNotFound, ValueError) as e:
        return None, SymbolGap(mpn=mpn, cause="no_official_symbol",
                               note=f"grep 命中但載入失敗: {e}")
    return ResolvedSymbol(mpn=mpn, lib_id=best_lib_id, lib_source="official"), None


def _common_prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def resolve_bom(bom_rows: list[dict], root: Path | None = None) -> dict:
    """Resolve a BOM (list of {mpn, ref, package?, ...}) into resolved/gaps.

    Rows are grouped by MPN so one physical part → one resolution. Returns a
    dict with 'resolved', 'gaps', 'coverage' and 'generated_geometry' (always 0
    — DD-1 no-fallback invariant, asserted by tests)."""
    by_mpn: dict[str, list[dict]] = {}
    for row in bom_rows:
        mpn = (row.get("mpn") or "").strip()
        by_mpn.setdefault(mpn, []).append(row)

    resolved: list[ResolvedSymbol] = []
    gaps: list[SymbolGap] = []
    for mpn, rows in by_mpn.items():
        refs = [str(r.get("ref") or "").strip() for r in rows if r.get("ref")]
        pkg = str(rows[0].get("package") or rows[0].get("footprint") or "")
        rs, gp = resolve_mpn(mpn, root)
        if rs is not None:
            rs.refs = refs
            resolved.append(rs)
        else:
            assert gp is not None
            gp.refs = refs
            if not gp.package:
                gp.package = pkg
            gaps.append(gp)

    total = len(by_mpn)
    coverage = (len(resolved) / total) if total else 0.0
    return {
        "resolved": [r.to_dict() for r in resolved],
        "gaps": [g.to_dict() for g in gaps],
        "coverage": coverage,
        "total_distinct_mpn": total,
        "generated_geometry": 0,  # DD-1 invariant: v2 never fabricates geometry
    }
