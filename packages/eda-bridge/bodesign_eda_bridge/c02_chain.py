"""C02' chain tools: bodesign_c02_chain_check (section 2.3 SSOT) and bodesign_c02_view_coverage (DD-19(a)).

``c04_board_manifest`` is the authoritative section 2.2 packet. The chain check recomputes that tool's own
``exported_outline_sha256`` / ``exported_mounting_holes_sha256`` from the board and compares them with the
C02' manifest's ``consumed_*`` values; a mismatch names which side is stale. Nothing is defaulted: a missing
input or an absent ``consumed_*`` value is an error / ``unmeasured``, never a pass.

View coverage: required views are matched by file name ``<prefix><view>-v<N>.png`` (default prefix ``02.c02p-``,
i.e. ``NN.c02p-<view>-vN.png`` with NN = 02); the highest vN per view is examined. A file counts as present only
when it is a non-empty PNG (signature + IHDR with matching CRC) at least ``min_px`` wide and high. Missing or
invalid views fail the check. Pixel size only: image CONTENT (what the view shows) is not assessed.
"""
from __future__ import annotations

import json
import os
import re
import struct
import zlib
from typing import Any

from .c04_gate import C04GateInputError, _sha256
from .c04_manifest import c04_board_hashes, canonical_sha256

DEFAULT_VIEWS = ("iso", "exploded", "section-usb", "exterior-usb-end", "plan", "section-lid-ui")
DEFAULT_PREFIX = "02.c02p-"
DEFAULT_MIN_PX = (800, 600)
_PNG_SIG = b"\x89PNG\r\n\x1a\n"


class C02ChainInputError(ValueError):
    """Explicit fail-fast input error."""


def _json(path: Any, arg: str) -> dict:
    if not isinstance(path, str) or not path or not os.path.isfile(path):
        raise C02ChainInputError(f"C02_CHAIN_INPUT_NOT_FOUND: {arg}={path!r} does not exist or is not a file")
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError) as e:
        raise C02ChainInputError(f"C02_CHAIN_INPUT_FORMAT: {arg}={path!r} is not readable JSON: {e}") from None
    if not isinstance(d, dict):
        raise C02ChainInputError(f"C02_CHAIN_INPUT_FORMAT: {arg}={path!r} top level is not an object")
    return d


def _link(name: str, recomputed: str, consumed: Any) -> dict:
    if not isinstance(consumed, str) or not consumed:
        return {"status": "unmeasured", "recomputed": recomputed, "consumed": consumed,
                "reason": f"C02' manifest has no consumed_{name}_sha256"}
    if consumed == recomputed:
        return {"status": "pass", "recomputed": recomputed, "consumed": consumed}
    return {"status": "fail", "recomputed": recomputed, "consumed": consumed, "stale_side": "c02_manifest",
            "kind": "STALE_UPSTREAM_MANIFEST",
            "detail": f"C02' consumed {consumed[:8]}... but the board recomputes {recomputed[:8]}... (bodesign c04_board_manifest)"}


def c02_chain_check(board_path: str, c02_manifest_path: str, board_manifest_path: str | None = None) -> dict:
    for nm, v in (("board_path", board_path), ("c02_manifest_path", c02_manifest_path)):
        if not isinstance(v, str) or not v:
            raise C02ChainInputError(f"C02_CHAIN_INPUT_MISSING: {nm} is required")
    try:
        rc = c04_board_hashes(board_path)
    except C04GateInputError as e:
        raise C02ChainInputError(str(e)) from None
    c02 = _json(c02_manifest_path, "c02_manifest_path")
    links = {"outline": _link("board_outline", rc["exported_outline_sha256"], c02.get("consumed_board_outline_sha256")),
             "mounting_holes": _link("mounting_holes", rc["exported_mounting_holes_sha256"], c02.get("consumed_mounting_holes_sha256"))}
    inputs = {"board_sha256": rc["board_sha256"], "c02_manifest_sha256": _sha256(c02_manifest_path)}
    bm = None
    if board_manifest_path is not None:
        b = _json(board_manifest_path, "board_manifest_path")
        inputs["board_manifest_sha256"] = _sha256(board_manifest_path)
        stale = []
        for key, tag in (("exported_outline_sha256", "outline"), ("exported_mounting_holes_sha256", "mounting_holes")):
            if b.get(key) != rc[key]:
                stale.append({"field": key, "file": b.get(key), "recomputed": rc[key]})
        own = canonical_sha256(b["outline"]) if isinstance(b.get("outline"), dict) else None
        if own is not None and own != b.get("exported_outline_sha256"):
            stale.append({"field": "outline (content vs its own exported_outline_sha256)", "file": b.get("exported_outline_sha256"), "recomputed": own})
        if b.get("schema") != "c04_board_manifest/1":
            stale.append({"field": "schema", "file": b.get("schema"), "recomputed": "c04_board_manifest/1"})
        bm = {"status": "fail" if stale else "pass", "stale_side": "board_manifest_file" if stale else None,
              "kind": "STALE_BOARD_MANIFEST" if stale else None, "offenders": stale}
    statuses = [l["status"] for l in links.values()] + ([bm["status"]] if bm else [])
    return {"ok": "fail" not in statuses and "unmeasured" not in statuses, "links": links, "board_manifest_file": bm,
            "unmeasured": sorted(k for k, l in links.items() if l["status"] == "unmeasured"),
            "inputs": inputs,
            "note": "ok requires every link measured and equal; an absent consumed_* value is unmeasured and never pass."}


# ------------------------------------------------------------------------------------------ view coverage
def _png_info(path: str) -> tuple[dict | None, str | None]:
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as e:
        return None, f"unreadable: {e}"
    if not data:
        return None, "zero-byte file"
    if data[:8] != _PNG_SIG:
        return None, "not a PNG (bad signature)"
    if len(data) < 33 or data[12:16] != b"IHDR":
        return None, "no IHDR chunk"
    w, h = struct.unpack(">II", data[16:24])
    if struct.unpack(">I", data[29:33])[0] != (zlib.crc32(data[12:29]) & 0xFFFFFFFF):
        return None, "IHDR CRC mismatch"
    if w <= 0 or h <= 0:
        return None, f"non-positive size {w}x{h}"
    return {"width": w, "height": h, "bytes": len(data)}, None


def c02_view_coverage(c02_manifest_path: str | None = None, human_dir: str | None = None, stage_prefix: str = DEFAULT_PREFIX,
                      required_views: list | None = None, min_px: list | None = None) -> dict:
    views = list(DEFAULT_VIEWS) if required_views is None else required_views
    if not isinstance(views, list) or not views or not all(isinstance(v, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", v) for v in views):
        raise C02ChainInputError("C02_VIEWS_INPUT_FIELD: required_views must be a non-empty list of lowercase view names")
    mpx = list(DEFAULT_MIN_PX) if min_px is None else min_px
    if (not isinstance(mpx, list) or len(mpx) != 2 or any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in mpx)):
        raise C02ChainInputError("C02_VIEWS_INPUT_FIELD: min_px must be [width, height] positive integers")
    if not isinstance(stage_prefix, str) or not stage_prefix:
        raise C02ChainInputError("C02_VIEWS_INPUT_FIELD: stage_prefix must be a non-empty string")
    src = {}
    if c02_manifest_path is not None:
        m = _json(c02_manifest_path, "c02_manifest_path")
        d = human_dir or m.get("human_tree_dir")
        if not d:
            raise C02ChainInputError("C02_VIEWS_INPUT_MISSING: the C02' manifest has no human_tree_dir and human_dir was not given")
        human_dir = d
        src["c02_manifest_sha256"] = _sha256(c02_manifest_path)
    if not isinstance(human_dir, str) or not human_dir:
        raise C02ChainInputError("C02_VIEWS_INPUT_MISSING: human_dir (or c02_manifest_path carrying human_tree_dir) is required")
    if not os.path.isdir(human_dir):
        raise C02ChainInputError(f"C02_VIEWS_INPUT_NOT_FOUND: human_dir={human_dir!r} is not a directory")
    names = sorted(os.listdir(human_dir))
    report, missing, invalid = {}, [], []
    for v in views:
        pat = re.compile(re.escape(stage_prefix) + re.escape(v) + r"-v(\d+)\.png")
        cands = sorted(((int(pat.fullmatch(n).group(1)), n) for n in names if pat.fullmatch(n)), reverse=True)
        if not cands:
            report[v] = {"status": "missing"}
            missing.append(v)
            continue
        ver, fn = cands[0]
        info, why = _png_info(os.path.join(human_dir, fn))
        if info is None:
            report[v] = {"status": "invalid", "file": fn, "version": ver, "reason": why}
            invalid.append({"view": v, "file": fn, "reason": why})
        elif info["width"] < mpx[0] or info["height"] < mpx[1]:
            why = f"{info['width']}x{info['height']} below min_px {mpx[0]}x{mpx[1]}"
            report[v] = {"status": "invalid", "file": fn, "version": ver, "reason": why, **info}
            invalid.append({"view": v, "file": fn, "reason": why})
        else:
            report[v] = {"status": "present", "file": fn, "version": ver, **info}
    ok = not missing and not invalid
    return {"ok": ok, "status": "pass" if ok else "fail", "views": report, "missing": missing, "invalid": invalid,
            "required_views": views, "min_px": mpx, "stage_prefix": stage_prefix, "human_dir": human_dir, "inputs": src,
            "note": "filename convention + non-empty PNG + pixel size only; what a view SHOWS is not assessed (needs review)."}
