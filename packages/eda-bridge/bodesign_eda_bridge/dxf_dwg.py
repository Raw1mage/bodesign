"""Local DXF <-> DWG conversion (LibreDWG dxf2dwg/dwg2dxf + optional ezdxf normalize).

No-fallback contract: if the LibreDWG binaries are absent we fail fast with an
explicit error telling the operator to rebuild the image. We never silently
degrade to a partial / lossy conversion.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

# dwgread JSON _subclass markers -> friendly entity-count keys.
_SUBCLASS_COUNT_KEYS = {
    "AcDbPolyline": "lwpolyline",
    "AcDb2dPolyline": "polyline2d",
    "AcDb2dVertex": "vertex2d",
    "AcDbVertex": "vertex",
    "AcDbText": "text",
    "AcDbMText": "mtext",
    "AcDbLine": "line",
    "AcDbCircle": "circle",
    "AcDbArc": "arc",
}


def _count_entities(dwg_path: str) -> dict[str, int]:
    """Parse `dwgread -O JSON` and count entities by AcDb _subclass."""
    dwgread = shutil.which("dwgread")
    if not dwgread:
        return {}
    proc = subprocess.run(
        [dwgread, "-O", "JSON", dwg_path],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return {}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}
    counts: dict[str, int] = {}
    objects = data.get("OBJECTS") or data.get("objects") or []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        subclass = obj.get("_subclass")
        if isinstance(subclass, str) and subclass in _SUBCLASS_COUNT_KEYS:
            key = _SUBCLASS_COUNT_KEYS[subclass]
            counts[key] = counts.get(key, 0) + 1
    return counts


def _normalize_dxf(in_path: str, version: str, dst: str) -> list[str]:
    """Re-read in_path with ezdxf and rewrite a clean `version` DXF to dst.

    Preserves LWPOLYLINE/TEXT/layers/colors via ezdxf's native model. Returns
    a list of warnings (empty on a clean rewrite).
    """
    import ezdxf

    warnings: list[str] = []
    doc = ezdxf.readfile(in_path)
    try:
        doc.dxfversion = ezdxf.const.acad_release_to_dxf_version.get(version, version)
    except Exception:
        doc.dxfversion = version
    doc.saveas(dst)
    return warnings


def dxf_to_dwg(in_path: str, out_dir: str, version: str = "R2000", normalize: bool = True) -> dict[str, Any]:
    dxf2dwg = shutil.which("dxf2dwg")
    if not dxf2dwg:
        return {"ok": False, "error": "libredwg dxf2dwg not found; rebuild image"}

    src = Path(in_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dwg_path = out / f"{src.stem}.dwg"
    warnings: list[str] = []

    feed = str(src)
    tmp_dxf: str | None = None
    if normalize:
        try:
            fd = tempfile.NamedTemporaryFile(suffix=".dxf", delete=False, dir=str(out))
            tmp_dxf = fd.name
            fd.close()
            warnings += _normalize_dxf(str(src), version, tmp_dxf)
            feed = tmp_dxf
        except ModuleNotFoundError:
            return {"ok": False, "error": "ezdxf not installed; rebuild image (normalize=True requires ezdxf)"}
        except Exception as error:  # ezdxf read/write failure is fatal under no-fallback
            return {"ok": False, "error": f"dxf normalize failed: {type(error).__name__}: {error}"}

    proc = subprocess.run(
        [dxf2dwg, "-y", "-o", str(dwg_path), feed],
        capture_output=True,
        text=True,
    )
    if tmp_dxf:
        Path(tmp_dxf).unlink(missing_ok=True)

    if proc.returncode != 0 or not dwg_path.exists():
        return {"ok": False, "error": f"dxf2dwg failed (rc={proc.returncode}): {proc.stderr.strip()}"}

    if proc.stderr.strip():
        warnings.append(proc.stderr.strip())

    return {
        "ok": True,
        "dwg_path": str(dwg_path),
        "version": "AC1015",
        "entities": _count_entities(str(dwg_path)),
        "warnings": warnings,
    }


def dwg_to_dxf(in_path: str, out_dir: str) -> dict[str, Any]:
    dwg2dxf = shutil.which("dwg2dxf")
    if not dwg2dxf:
        return {"ok": False, "error": "libredwg dwg2dxf not found; rebuild image"}

    src = Path(in_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dxf_path = out / f"{src.stem}.dxf"
    warnings: list[str] = []

    entities = _count_entities(str(src))

    proc = subprocess.run(
        [dwg2dxf, "-y", "-o", str(dxf_path), str(src)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not dxf_path.exists():
        return {"ok": False, "error": f"dwg2dxf failed (rc={proc.returncode}): {proc.stderr.strip()}"}

    if proc.stderr.strip():
        warnings.append(proc.stderr.strip())

    return {
        "ok": True,
        "dxf_path": str(dxf_path),
        "entities": entities,
        "warnings": warnings,
    }
