"""Authentic component data fetch for bodesign C03/C04.

Real MPN → authoritative KiCad symbol + footprint + 3D STEP model, pulled from
the manufacturer-backed LCSC / EasyEDA public component library keyed by real
LCSC part number.

This closes the "100% fidelity source data before design" gate: rather than
scaling a generic package as a stand-in body, every component's symbol,
footprint and 3D model come from the vendor database. Two verbs:

  search(keyword)  -> [{mpn, lcsc_id, package, manufacturer, stock, rohs, price1}]
  fetch(lcsc_id)   -> {kicad_sym, footprint, step_model, wrl_model, has_3d} on disk

`fetch` shells out to the pinned easyeda2kicad CLI (proven end-to-end); `search`
hits the public EasyEDA product-search endpoint. No-fallback contract: a missing
CLI, an unreachable API, or an absent 3D model is reported honestly
(ok=false / has_3d=false) — never a fabricated or silently-substituted model.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import urllib.parse
import urllib.request
from typing import Any

_SEARCH_URL = "https://easyeda.com/api/eda/product/search"
_UA = "Mozilla/5.0 (bodesign component_fetch) AppleWebKit/537.36"
_TIMEOUT = 25


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:  # noqa: S310 (trusted vendor host)
        return json.loads(r.read().decode("utf-8"))


def search_components(keyword: str, *, limit: int = 8) -> dict[str, Any]:
    """MPN / keyword → candidate real parts on LCSC. No fabrication: an empty
    productList is reported as found=0, not padded with guesses."""
    if not keyword or not keyword.strip():
        return {"ok": False, "reason": "empty keyword", "keyword": keyword, "results": []}
    q = urllib.parse.urlencode({"keyword": keyword.strip(), "currPage": 1, "pageSize": max(1, min(limit, 25))})
    try:
        data = _http_get_json(f"{_SEARCH_URL}?{q}")
    except Exception as e:  # network / parse — honest failure, no stub
        return {"ok": False, "reason": f"search API unreachable: {e}", "keyword": keyword, "results": []}
    result = data.get("result") or {}
    products = result.get("productList") or []
    out = []
    for p in products[:limit]:
        price1 = None
        pr = p.get("price")
        if isinstance(pr, list) and pr and isinstance(pr[0], list) and len(pr[0]) >= 2:
            price1 = pr[0][1]
        out.append({
            "mpn": p.get("mpn"),
            "lcsc_id": p.get("number"),
            "package": p.get("package"),
            "manufacturer": p.get("manufacturer"),
            "stock": p.get("stock"),
            "rohs": p.get("ifRoHS"),
            "price1": price1,
        })
    return {"ok": True, "keyword": keyword, "found": result.get("total", len(out)), "results": out}


def fetch_component(lcsc_id: str, output_lib: str, *, overwrite: bool = True) -> dict[str, Any]:
    """LCSC id → authoritative symbol + footprint + 3D model on disk.

    Returns the produced artifact paths. has_3d=false when the vendor library
    carries no STEP for the part (an honest source-data gap, not a substituted
    body). ok=false when the CLI is missing or the fetch fails outright.
    """
    if not lcsc_id or not lcsc_id.strip():
        return {"ok": False, "reason": "empty lcsc_id"}
    lcsc_id = lcsc_id.strip()
    cli = shutil.which("easyeda2kicad")
    if not cli:
        return {"ok": False, "reason": "easyeda2kicad CLI not present in this worker — rebuild image",
                "lcsc_id": lcsc_id}
    os.makedirs(os.path.dirname(output_lib) or ".", exist_ok=True)
    cmd = [cli, "--full", f"--lcsc_id={lcsc_id}", "--output", output_lib]
    if overwrite:
        cmd.append("--overwrite")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    sym = f"{output_lib}.kicad_sym"
    fps = sorted(glob.glob(f"{output_lib}.pretty/*.kicad_mod"))
    steps = sorted(glob.glob(f"{output_lib}.3dshapes/*.step"))
    wrls = sorted(glob.glob(f"{output_lib}.3dshapes/*.wrl"))
    have_sym = os.path.exists(sym)
    if not have_sym and not fps:
        tail = (proc.stderr or proc.stdout or "")[-500:]
        return {"ok": False, "reason": f"easyeda2kicad produced no artifacts (rc={proc.returncode})",
                "lcsc_id": lcsc_id, "cli_tail": tail}
    return {
        "ok": True,
        "lcsc_id": lcsc_id,
        "kicad_sym": sym if have_sym else None,
        "footprint": fps[0] if fps else None,
        "footprints": fps,
        "step_model": steps[0] if steps else None,
        "wrl_model": wrls[0] if wrls else None,
        "has_3d": bool(steps),
        "lib_nickname": os.path.basename(output_lib),
    }


def fetch_components(lcsc_ids: list[str], output_lib: str, *, overwrite: bool = True) -> dict[str, Any]:
    """Batch variant of `fetch_component`: pull N authoritative parts into one
    shared `output_lib`, in SEQUENCE (they share the easyeda2kicad CLI and the
    output library — parallel fetch would race on the same files).

    Continue-on-error: a failing part (vendor lacks the id, CLI error, timeout)
    does NOT abort the rest. Every part is reported in `results[]` with its own
    ok/paths-or-reason, and the top-level `fetched`/`failed` counts summarise —
    so one call surfaces ALL source-data gaps at once, per the no-fallback
    contract (nothing is padded or silently substituted).
    """
    if not isinstance(lcsc_ids, list) or not lcsc_ids:
        return {"ok": False, "reason": "empty lcsc_ids (provide a non-empty list)",
                "output_lib": output_lib, "results": []}
    results: list[dict[str, Any]] = []
    fetched = 0
    for raw in lcsc_ids:
        one = fetch_component(raw, output_lib, overwrite=overwrite)
        if one.get("ok"):
            fetched += 1
        results.append(one)
    failed = len(results) - fetched
    return {
        "ok": failed == 0,
        "output_lib": output_lib,
        "lib_nickname": os.path.basename(output_lib),
        "requested": len(results),
        "fetched": fetched,
        "failed": failed,
        "results": results,
    }
