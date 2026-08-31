"""String-aware s-expression block scanning (BR_20260901f).

Why this module exists
----------------------
Three independent hand-written copies of a "walk forward until the parens
balance" loop existed in this package (``kicad_emit._balanced_block``,
``kicad_emit._extract_symbol_block``, ``fidelity._balanced_block``). None of
them tracked quoted strings, so a ``(`` or ``)`` inside a KiCad property VALUE
desynchronised the depth counter and the scan ran past the true end of the
block — silently. Measured consequence: every one of the 150 "Symbol not found"
load failures in the KiCad stdlib was this defect (the marker WAS present in
all 150), plus 182 symbols that parsed to the wrong length without erroring.

The three call sites have genuinely different semantics (take child nodes /
take a named block / reverse-search for an enclosing block) and, more
importantly, three different not-found return values that their callers already
depend on. So this module deliberately exposes only the SCANNING primitive;
each wrapper keeps its own signature and its own not-found behaviour.

KiCad s-expressions quote with ``"`` and escape with ``\\``. Both are handled:
a ``\\"`` inside a string does NOT end the string.
"""
from __future__ import annotations


def balanced_end(s: str, start: int) -> int | None:
    """Exclusive end index of the parenthesised block beginning at ``start``.

    ``s[start]`` is expected to be ``'('``. Returns the index one past the
    matching ``')'``, or ``None`` if the block never closes (unbalanced input,
    or ``start`` does not begin a block).

    Parens inside double-quoted strings are literal text and do not affect
    depth; ``\\`` escapes the next character inside a string.
    """
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(s)):
        char = s[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
    return None
