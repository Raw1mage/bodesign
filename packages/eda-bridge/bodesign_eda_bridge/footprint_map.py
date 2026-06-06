"""Map generated-symbol packages to candidate KiCad footprints (R3).

Given a component's verified package evidence (ball count, array, body, pitch),
search the installed KiCad footprint libraries for candidate footprints and
score them, emitting project-local metadata with confidence and explicit gaps.

It never claims an exact footprint it cannot substantiate: a candidate is only
flagged as a `match` when the ball count agrees and the score clears a
threshold, and every entry records the verification still required (pad
geometry / pitch / body / depopulated-ball handling). Flagship-new packages
with no stdlib footprint (e.g. VFBGA-223) are reported as a gap, mirroring the
symbol-generation posture.
"""

from dataclasses import dataclass, field
from pathlib import Path
import os
import re

DEFAULT_FOOTPRINT_DIR = os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
BGA_LIB = "Package_BGA"
_BALL_RE = re.compile(r"BGA-(\d+)")
_LAYOUT_RE = re.compile(r"Layout(\d+x\d+)")
_PITCH_RE = re.compile(r"P([\d.]+)mm")
_BODY_RE = re.compile(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm")
MATCH_THRESHOLD = 0.6


@dataclass(slots=True)
class PackageQuery:
    component_ref: str
    mpn: str
    package: str
    ball_count: int | None = None
    array: str | None = None
    body_mm: tuple[float, float] | None = None
    pitch_mm: float | None = None


@dataclass(slots=True)
class FootprintCandidate:
    lib_id: str
    ball_count: int | None
    layout: str | None
    body_mm: str | None
    pitch_mm: float | None
    score: float
    is_match: bool


def _parse_footprint(name: str) -> dict[str, object]:
    stem = name[:-len(".kicad_mod")] if name.endswith(".kicad_mod") else name
    ball = _BALL_RE.search(stem)
    layout = _LAYOUT_RE.search(stem)
    pitch = _PITCH_RE.search(stem)
    body = _BODY_RE.search(stem)
    return {
        "stem": stem,
        "ball_count": int(ball.group(1)) if ball else None,
        "layout": layout.group(1) if layout else None,
        "pitch_mm": float(pitch.group(1)) if pitch else None,
        "body_mm": (float(body.group(1)), float(body.group(2))) if body else None,
    }


def _score(query: PackageQuery, parsed: dict[str, object]) -> float:
    score = 0.0
    if query.ball_count is not None and parsed["ball_count"] == query.ball_count:
        score += 0.5
    if query.array is not None and parsed["layout"] == query.array:
        score += 0.2
    if query.pitch_mm is not None and parsed["pitch_mm"] == query.pitch_mm:
        score += 0.15
    if query.body_mm is not None and parsed["body_mm"] == query.body_mm:
        score += 0.15
    return round(min(score, 0.95), 3)


def match_footprints(query: PackageQuery, footprint_dir: str | Path = DEFAULT_FOOTPRINT_DIR, limit: int = 4) -> list[FootprintCandidate]:
    library = Path(footprint_dir) / f"{BGA_LIB}.pretty"
    if not library.exists():
        return []
    candidates: list[FootprintCandidate] = []
    for path in sorted(library.glob("*.kicad_mod")):
        parsed = _parse_footprint(path.name)
        score = _score(query, parsed)
        if score <= 0.0:
            continue
        ball_match = query.ball_count is not None and parsed["ball_count"] == query.ball_count
        body = f"{parsed['body_mm'][0]}x{parsed['body_mm'][1]}mm" if parsed["body_mm"] else None
        candidates.append(
            FootprintCandidate(
                lib_id=f"{BGA_LIB}:{parsed['stem']}",
                ball_count=parsed["ball_count"],
                layout=parsed["layout"],
                body_mm=body,
                pitch_mm=parsed["pitch_mm"],
                score=score,
                is_match=bool(ball_match and score >= MATCH_THRESHOLD),
            )
        )
    candidates.sort(key=lambda candidate: (candidate.is_match, candidate.score), reverse=True)
    return candidates[:limit]


def build_footprint_map(queries: list[PackageQuery], footprint_dir: str | Path = DEFAULT_FOOTPRINT_DIR) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for query in queries:
        candidates = match_footprints(query, footprint_dir)
        matches = [candidate for candidate in candidates if candidate.is_match]
        gaps: list[str] = []
        if matches:
            status = "candidate-match-needs-verification"
            gaps.append(
                f"Best candidate {matches[0].lib_id} matches ball count; confirm exact pad geometry, pitch, body, "
                "and any depopulated balls against the package drawing before footprint emission."
            )
        else:
            status = "no-stdlib-footprint-gap"
            gaps.append(
                f"No installed KiCad footprint matches {query.package} ({query.ball_count}-ball); a project-local "
                "footprint must be generated from the package drawing (deferred, like the symbol)."
            )
        entries.append(
            {
                "component_ref": query.component_ref,
                "mpn": query.mpn,
                "package": query.package,
                "ball_count": query.ball_count,
                "array": query.array,
                "body_mm": list(query.body_mm) if query.body_mm else None,
                "pitch_mm": query.pitch_mm,
                "status": status,
                "best_match": matches[0].lib_id if matches else None,
                "candidates": [
                    {
                        "lib_id": candidate.lib_id,
                        "ball_count": candidate.ball_count,
                        "layout": candidate.layout,
                        "body_mm": candidate.body_mm,
                        "pitch_mm": candidate.pitch_mm,
                        "score": candidate.score,
                        "is_match": candidate.is_match,
                    }
                    for candidate in candidates
                ],
                "gaps": gaps,
            }
        )
    return {
        "artifact_id": "footprint-map",
        "footprint_library": BGA_LIB,
        "library_scope": "project-local-only",
        "global_kicad_library_mutation": "forbidden",
        "entries": entries,
    }


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_body(value) -> tuple[float, float] | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)", value)
    return (float(match.group(1)), float(match.group(2))) if match else None
