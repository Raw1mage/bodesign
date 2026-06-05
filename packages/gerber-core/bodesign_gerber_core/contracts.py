from dataclasses import dataclass, field
from pathlib import Path
import re


COORDINATE_RE = re.compile(r"X(?P<x>-?\d+)?Y(?P<y>-?\d+)?(?:D(?P<op>0[123]))?\*")
APERTURE_RE = re.compile(r"%ADD(?P<code>\d+)(?P<shape>[A-Z][A-Z0-9]*),?(?P<params>[^*%]*)\*%")
FORMAT_RE = re.compile(r"%FSLAX(?P<xi>\d)(?P<xd>\d)Y(?P<yi>\d)(?P<yd>\d)\*M(?P<unit>OIN|MOMM)\*%")
DRILL_RE = re.compile(r"X(?P<x>-?\d+)Y(?P<y>-?\d+)")
HOLE_SIZE_RE = re.compile(r"Holesize\s+(?P<index>\d+)\.\s+=\s+(?P<size>[0-9.]+).*?(?P<plating>NON_PLATED|PLATED)", re.IGNORECASE)


@dataclass(slots=True)
class GeometryBounds:
    min_x: float | None = None
    min_y: float | None = None
    max_x: float | None = None
    max_y: float | None = None

    def include(self, x: float, y: float) -> None:
        self.min_x = x if self.min_x is None else min(self.min_x, x)
        self.min_y = y if self.min_y is None else min(self.min_y, y)
        self.max_x = x if self.max_x is None else max(self.max_x, x)
        self.max_y = y if self.max_y is None else max(self.max_y, y)

    def width(self) -> float:
        if self.min_x is None or self.max_x is None:
            return 0.0
        return self.max_x - self.min_x

    def height(self) -> float:
        if self.min_y is None or self.max_y is None:
            return 0.0
        return self.max_y - self.min_y


@dataclass(slots=True)
class GerberAperture:
    code: str
    shape: str
    params: str = ""
    use_count: int = 0


@dataclass(slots=True)
class GerberDrawSegment:
    x1: float
    y1: float
    x2: float
    y2: float
    aperture: str | None = None


@dataclass(slots=True)
class GerberFlash:
    x: float
    y: float
    aperture: str | None = None


@dataclass(slots=True)
class GerberGeometrySummary:
    source_path: str
    unit: str = "inch"
    coordinate_decimals: int = 5
    apertures: list[GerberAperture] = field(default_factory=list)
    bounds: GeometryBounds = field(default_factory=GeometryBounds)
    draw_count: int = 0
    flash_count: int = 0
    move_count: int = 0
    region_count: int = 0
    polarity_changes: int = 0
    sample_draws: list[GerberDrawSegment] = field(default_factory=list)
    sample_flashes: list[GerberFlash] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DrillTool:
    index: str
    size_mil: float
    plating: str
    quantity_hint: int | None = None
    hit_count: int = 0


@dataclass(slots=True)
class DrillHit:
    x: float
    y: float
    tool: str | None = None


@dataclass(slots=True)
class DrillGeometrySummary:
    source_path: str
    unit: str = "inch"
    coordinate_decimals: int = 5
    tools: list[DrillTool] = field(default_factory=list)
    bounds: GeometryBounds = field(default_factory=GeometryBounds)
    hit_count: int = 0
    sample_hits: list[DrillHit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GerberValidationResult:
    project_id: str
    output_paths: list[str] = field(default_factory=list)
    status: str = "pending"
    warnings: list[str] = field(default_factory=list)
    blocking_errors: list[str] = field(default_factory=list)


def parse_gerber_file(path: str | Path, sample_limit: int = 500) -> GerberGeometrySummary:
    source = Path(path)
    summary = GerberGeometrySummary(source_path=str(source))
    apertures: dict[str, GerberAperture] = {}
    selected_aperture: str | None = None
    current_x: float | None = None
    current_y: float | None = None
    coordinate_scale = 10 ** summary.coordinate_decimals

    for line in source.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        format_match = FORMAT_RE.match(stripped)
        if format_match:
            summary.coordinate_decimals = int(format_match.group("xd"))
            coordinate_scale = 10 ** summary.coordinate_decimals
            summary.unit = "inch" if format_match.group("unit") == "OIN" else "mm"
            continue

        aperture_match = APERTURE_RE.match(stripped)
        if aperture_match:
            code = aperture_match.group("code")
            apertures[code] = GerberAperture(code=code, shape=aperture_match.group("shape"), params=aperture_match.group("params"))
            continue

        if stripped.startswith("%LP"):
            summary.polarity_changes += 1
            continue
        if stripped in {"G36*", "G36"}:
            summary.region_count += 1
            continue
        if stripped.startswith("D") and stripped.endswith("*") and stripped[1:-1].isdigit():
            selected_aperture = stripped[1:-1]
            continue

        coordinate_match = COORDINATE_RE.match(stripped)
        if not coordinate_match:
            continue
        next_x = _decode_coordinate(coordinate_match.group("x"), current_x, coordinate_scale)
        next_y = _decode_coordinate(coordinate_match.group("y"), current_y, coordinate_scale)
        operation = coordinate_match.group("op") or "01"
        if next_x is None or next_y is None:
            continue
        summary.bounds.include(next_x, next_y)
        if operation == "01" and current_x is not None and current_y is not None:
            summary.draw_count += 1
            _count_aperture_use(apertures, selected_aperture)
            if len(summary.sample_draws) < sample_limit:
                summary.sample_draws.append(GerberDrawSegment(current_x, current_y, next_x, next_y, selected_aperture))
        elif operation == "02":
            summary.move_count += 1
        elif operation == "03":
            summary.flash_count += 1
            _count_aperture_use(apertures, selected_aperture)
            if len(summary.sample_flashes) < sample_limit:
                summary.sample_flashes.append(GerberFlash(next_x, next_y, selected_aperture))
        current_x = next_x
        current_y = next_y

    summary.apertures = sorted(apertures.values(), key=lambda aperture: int(aperture.code))
    if summary.draw_count == 0 and summary.flash_count == 0:
        summary.warnings.append("No D01/D03 geometry operations were parsed from this Gerber file.")
    return summary


def parse_drill_file(path: str | Path, sample_limit: int = 500) -> DrillGeometrySummary:
    source = Path(path)
    summary = DrillGeometrySummary(source_path=str(source))
    tools: dict[str, DrillTool] = {}
    current_tool = "1"
    for line in source.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        hole_match = HOLE_SIZE_RE.search(stripped)
        if hole_match:
            index = hole_match.group("index")
            quantity_match = re.search(r"Quantity\s+=\s+(\d+)", stripped)
            tools[index] = DrillTool(
                index=index,
                size_mil=float(hole_match.group("size")),
                plating=hole_match.group("plating").upper(),
                quantity_hint=int(quantity_match.group(1)) if quantity_match else None,
            )
            continue
        if stripped == "M00":
            current_tool = str(int(current_tool) + 1)
            continue
        drill_match = DRILL_RE.match(stripped)
        if not drill_match:
            continue
        x = int(drill_match.group("x")) / 100000
        y = int(drill_match.group("y")) / 100000
        summary.bounds.include(x, y)
        summary.hit_count += 1
        if current_tool in tools:
            tools[current_tool].hit_count += 1
        if len(summary.sample_hits) < sample_limit:
            summary.sample_hits.append(DrillHit(x=x, y=y, tool=current_tool))
    summary.tools = sorted(tools.values(), key=lambda tool: int(tool.index))
    if summary.hit_count == 0:
        summary.warnings.append("No drill hit coordinates were parsed from this drill file.")
    return summary


def render_geometry_svg(gerber: GerberGeometrySummary | None = None, drill: DrillGeometrySummary | None = None, width: int = 980, height: int = 620) -> str:
    bounds = GeometryBounds()
    for source_bounds in [gerber.bounds if gerber else None, drill.bounds if drill else None]:
        if source_bounds is None or source_bounds.min_x is None or source_bounds.min_y is None or source_bounds.max_x is None or source_bounds.max_y is None:
            continue
        bounds.include(source_bounds.min_x, source_bounds.min_y)
        bounds.include(source_bounds.max_x, source_bounds.max_y)
    if bounds.min_x is None or bounds.min_y is None or bounds.max_x is None or bounds.max_y is None:
        return '<svg role="img" viewBox="0 0 980 620" xmlns="http://www.w3.org/2000/svg"><text x="30" y="60" fill="#9aacb4">No geometry parsed.</text></svg>'
    margin = 28
    scale = min((width - margin * 2) / max(bounds.width(), 0.001), (height - margin * 2) / max(bounds.height(), 0.001))

    def project(x: float, y: float) -> tuple[float, float]:
        return (margin + (x - bounds.min_x) * scale, height - margin - (y - bounds.min_y) * scale)

    parts = [f'<svg role="img" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">', '<rect width="100%" height="100%" fill="#07100d"/>']
    parts.append(f'<rect x="{margin}" y="{margin}" width="{width - margin * 2}" height="{height - margin * 2}" fill="#0d171d" stroke="#293943"/>')
    if gerber is not None:
        for segment in gerber.sample_draws[:900]:
            x1, y1 = project(segment.x1, segment.y1)
            x2, y2 = project(segment.x2, segment.y2)
            parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#5de4c7" stroke-width="1.25" stroke-linecap="round" opacity="0.78"/>')
        for flash in gerber.sample_flashes[:500]:
            x, y = project(flash.x, flash.y)
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.4" fill="#ffc857" opacity="0.8"/>')
    if drill is not None:
        for hit in drill.sample_hits[:700]:
            x, y = project(hit.x, hit.y)
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.6" fill="none" stroke="#9bd8ff" stroke-width="1" opacity="0.8"/>')
    parts.append('</svg>')
    return "".join(parts)


def _decode_coordinate(value: str | None, previous: float | None, coordinate_scale: int) -> float | None:
    if value is None:
        return previous
    return int(value) / coordinate_scale


def _count_aperture_use(apertures: dict[str, GerberAperture], selected_aperture: str | None) -> None:
    if selected_aperture is not None and selected_aperture in apertures:
        apertures[selected_aperture].use_count += 1


def validate_gerber_export_placeholder(project_id: str, output_paths: list[str]) -> GerberValidationResult:
    warnings = [
        "Placeholder validation only; real Gerber parsing and geometry checks are pending.",
        "Generated output paths are not inspected or opened in this scaffold.",
    ]
    if not output_paths:
        warnings.append("No output paths were provided for validation.")

    return GerberValidationResult(
        project_id=project_id,
        output_paths=output_paths,
        status="placeholder-warning",
        warnings=warnings,
        blocking_errors=[],
    )
