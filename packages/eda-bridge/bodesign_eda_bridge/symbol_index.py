"""KiCad official symbol-library index (eda_draftsman-v2 task 0.3).

DD-1: v2 does NOT generate symbol geometry. It resolves a lib_id
("LibNickname:SymbolName") to the real four-edge symbol shipped by KiCad's
official library, loaded via kiutils. Missing MPN/symbol → caller records a
SymbolGap (no-fallback); this module never fabricates geometry.

Default library root is KiCad's system install (/usr/share/kicad/symbols),
overridable via KICAD_SYMBOL_DIR for pinned/vendored libraries.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from kiutils.symbol import Symbol, SymbolLib

DEFAULT_SYMBOL_DIR = Path(
    os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")
)


class SymbolNotFound(LookupError):
    """Raised when a lib_id cannot be resolved to an official symbol (SYMBOL_GAP)."""


def symbol_dir() -> Path:
    return DEFAULT_SYMBOL_DIR


def lib_path(nickname: str, root: Path | None = None) -> Path:
    """Map a library nickname (e.g. 'MCU_ST_STM32H7') to its .kicad_sym file."""
    base = root or symbol_dir()
    p = base / f"{nickname}.kicad_sym"
    return p


@lru_cache(maxsize=64)
def _load_lib(path_str: str) -> SymbolLib:
    return SymbolLib.from_file(path_str)


def resolve(lib_id: str, root: Path | None = None) -> tuple[Path, Symbol]:
    """Resolve 'Nickname:SymbolName' → (symbol_file_path, kiutils Symbol).

    Raises SymbolNotFound (→ SYMBOL_GAP) if the library or symbol is absent.
    """
    if ":" not in lib_id:
        raise ValueError(f"lib_id must be 'Nickname:SymbolName', got {lib_id!r}")
    nickname, name = lib_id.split(":", 1)
    p = lib_path(nickname, root)
    if not p.exists():
        raise SymbolNotFound(f"library not found: {nickname} ({p})")
    lib = _load_lib(str(p))
    for s in lib.symbols:
        if s.entryName == name:
            return p, s
    raise SymbolNotFound(f"symbol {name!r} not in {nickname}")


def search(term: str, root: Path | None = None) -> list[str]:
    """Grep-level scan: return lib_ids whose symbol name contains `term`.

    Used for coverage estimation (e.g. 'is there a STM32N657 symbol?').
    """
    base = root or symbol_dir()
    hits: list[str] = []
    term_l = term.lower()
    for lib_file in sorted(base.glob("*.kicad_sym")):
        try:
            txt = lib_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if term_l not in txt.lower():
            continue
        lib = _load_lib(str(lib_file))
        nick = lib_file.stem
        for s in lib.symbols:
            if term_l in s.entryName.lower():
                hits.append(f"{nick}:{s.entryName}")
    return hits
