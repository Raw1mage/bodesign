from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import subprocess


_BALL_RE = re.compile(r"^[A-Z][0-9]+$")
_SOURCE_TYPES = {"I/O", "I", "O", "A", "S", "-"}


@dataclass(slots=True)
class PinEvidenceRef:
    source_id: str
    page_start: int
    page_end: int
    table: str
    extraction_method: str


@dataclass(slots=True)
class NormalizedPinRow:
    ball: str
    pin_name: str
    pin_type: str
    functions: list[str] = field(default_factory=list)
    package: str = ""
    evidence: PinEvidenceRef | None = None


@dataclass(slots=True)
class PinTableValidation:
    passed: bool
    expected_count: int
    actual_count: int
    unique_ball_count: int
    missing_balls: list[str] = field(default_factory=list)
    duplicate_balls: list[str] = field(default_factory=list)
    missing_required_pins: list[str] = field(default_factory=list)
    rows_without_evidence: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


def normalize_pin_table_text(
    text: str,
    *,
    source_id: str = "",
    page_start: int = 89,
    page_end: int = 130,
    package: str = "",
) -> list[NormalizedPinRow]:
    rows: list[NormalizedPinRow] = []
    pending_pin_name = ""
    for line in text.splitlines():
        if not _line_starts_with_package_columns(line):
            pending_pin_name = _pending_pin_name_from_line(line) or pending_pin_name
        row = _normalize_st_pin_line(
            line,
            source_id=source_id,
            page_start=page_start,
            page_end=page_end,
            package=package,
            pending_pin_name=pending_pin_name,
        )
        if row is not None:
            rows.append(row)
            pending_pin_name = ""
    return rows


def extract_pin_table_from_pdf(
    pdf_path: str,
    *,
    source_id: str = "",
    page_start: int = 89,
    page_end: int = 130,
    package: str = "",
) -> list[NormalizedPinRow]:
    text = _pdftotext_page_span(Path(pdf_path), page_start, page_end)
    return normalize_pin_table_text(
        text,
        source_id=source_id,
        page_start=page_start,
        page_end=page_end,
        package=package,
    )


def validate_pin_table(
    rows: list[NormalizedPinRow],
    *,
    expected_balls: set[str] | None = None,
    required_pins: set[str] | None = None,
) -> PinTableValidation:
    expected = expected_balls or expected_bga_balls()
    required = required_pins or {"NRST", "BOOT0", "PDR_ON", "VDD", "VSS", "VDDCORE"}
    balls = [row.ball for row in rows]
    unique_balls = set(balls)
    duplicate_balls = sorted({ball for ball in unique_balls if balls.count(ball) > 1}, key=_ball_sort_key)
    missing_balls = sorted(expected - unique_balls, key=_ball_sort_key)
    row_pin_names = {_base_pin_name(row.pin_name) for row in rows if row.pin_name}
    missing_required_pins = sorted(required - row_pin_names)
    rows_without_evidence = sorted(row.ball for row in rows if row.evidence is None or not row.evidence.source_id)
    blockers: list[str] = []
    if len(rows) != len(expected):
        blockers.append(f"Expected {len(expected)} {rows[0].package if rows else 'BGA'} rows, found {len(rows)}.")
    if duplicate_balls:
        blockers.append("Duplicate ball coordinates are present.")
    if missing_balls:
        blockers.append("Missing ball coordinates prevent KiCad symbol generation.")
    if missing_required_pins:
        blockers.append("Required power/reset/boot pins are missing.")
    if rows_without_evidence:
        blockers.append("Every pin row must carry source/page/table evidence.")
    return PinTableValidation(
        passed=not blockers,
        expected_count=len(expected),
        actual_count=len(rows),
        unique_ball_count=len(unique_balls),
        missing_balls=missing_balls,
        duplicate_balls=duplicate_balls,
        missing_required_pins=missing_required_pins,
        rows_without_evidence=rows_without_evidence,
        blockers=blockers,
    )


def build_pin_table_gap_report(rows: list[NormalizedPinRow], validation: PinTableValidation) -> dict:
    return {
        "artifact_id": "pin-table-validation-v1",
        "status": "blocked" if not validation.passed else "validated",
        "pin_table_output": None if not validation.passed else "pin-table.json",
        "raw_pdf_text_committed": False,
        "package": "",
        "expected_count": validation.expected_count,
        "actual_count": validation.actual_count,
        "unique_ball_count": validation.unique_ball_count,
        "missing_balls": validation.missing_balls,
        "duplicate_balls": validation.duplicate_balls,
        "missing_required_pins": validation.missing_required_pins,
        "blockers": validation.blockers,
        "parsed_row_summary": {
            "power_or_supply_rows": sum(1 for row in rows if row.pin_type == "S"),
            "io_rows": sum(1 for row in rows if row.pin_type == "I/O"),
            "input_rows": sum(1 for row in rows if row.pin_type == "I"),
            "output_rows": sum(1 for row in rows if row.pin_type == "O"),
            "analog_rows": sum(1 for row in rows if row.pin_type == "A"),
        },
    }


def expected_bga_balls() -> set[str]:
    rows = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "R", "T", "U", "V", "W"]
    excluded = {
        "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11", "C12", "C13", "C14", "C15", "C16",
        "D3", "D17", "E3", "E5", "E6", "E7", "E8", "E9", "E10", "E11", "E12", "E13", "E14", "E15", "E17", "F3", "F5", "F15", "F17", "G3", "G5", "G7", "G8", "G9", "G10", "G11", "G12", "G13", "G15", "G17",
        "H3", "H5", "H7", "H8", "H9", "H10", "H11", "H12", "H13", "H15", "H17",
        "J6", "J7", "J8", "J9", "J10", "J11", "J12", "J13", "J15", "J17",
        "K6", "K7", "K8", "K9", "K10", "K11", "K12", "K13", "K15", "K17",
        "L6", "L7", "L8", "L9", "L10", "L11", "L12", "L13", "L15", "L17",
        "M3", "M5", "M7", "M8", "M9", "M10", "M11", "M12", "M13", "M15", "M17",
        "N3", "N5", "N7", "N8", "N9", "N10", "N11", "N12", "N13", "N15", "N17",
        "P3", "P5", "P15", "P17", "R3", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15", "R17",
        "T3", "T17", "U4", "U5", "U6", "U7", "U8", "U9", "U10", "U11", "U12", "U13", "U14", "U15", "U16",
    }
    all_balls = {f"{row}{column}" for row in rows for column in range(1, 20)}
    return all_balls - excluded


def _normalize_st_pin_line(
    line: str,
    *,
    source_id: str,
    page_start: int,
    page_end: int,
    package: str,
    pending_pin_name: str = "",
) -> NormalizedPinRow | None:
    tokens = line.split()
    if len(tokens) < 8:
        return None
    package_tokens = tokens[:6]
    if not all(token == "-" or _BALL_RE.match(token) for token in package_tokens):
        return None
    ball = package_tokens[4]
    if ball == "-":
        return None
    name_tokens: list[str] = []
    pin_type = ""
    pin_type_index = -1
    for index, token in enumerate(tokens[6:], start=6):
        if token in _SOURCE_TYPES and (name_tokens or token != "-"):
            pin_type = token
            pin_type_index = index
            break
        name_tokens.append(token)
    if not pin_type:
        return None
    function_tokens = tokens[pin_type_index + 1 :] if pin_type_index >= 0 else []
    functions = _normalize_functions(function_tokens)
    pin_name = " ".join(name_tokens) if name_tokens else (pending_pin_name or (functions[0] if functions else ""))
    if not pin_name:
        return None
    return NormalizedPinRow(
        ball=ball,
        pin_name=pin_name,
        pin_type=pin_type,
        functions=functions,
        package=package,
        evidence=PinEvidenceRef(
            source_id=source_id,
            page_start=page_start,
            page_end=page_end,
            table="Table 18. Pin description",
            extraction_method="pdftotext-layout-tokenized-package-columns",
        ),
    )


def _normalize_functions(tokens: list[str]) -> list[str]:
    joined = " ".join(token for token in tokens if token != "-")
    if not joined:
        return []
    return [part.strip() for part in re.split(r",|\s{2,}", joined) if part.strip()]


def _pending_pin_name_from_line(line: str) -> str:
    tokens = line.split()
    if not tokens:
        return ""
    for token in tokens:
        if re.match(r"^P[A-N][0-9]+$", token) or token in {"NRST", "BOOT0", "PDR_ON"}:
            return token
    return ""


def _line_starts_with_package_columns(line: str) -> bool:
    tokens = line.split()
    return len(tokens) >= 6 and all(token == "-" or _BALL_RE.match(token) for token in tokens[:6])


def _pdftotext_page_span(path: Path, page_start: int, page_end: int) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return subprocess.check_output(
            ["pdftotext", "-layout", "-f", str(page_start), "-l", str(page_end), str(path), "-"],
            text=True,
            errors="ignore",
            timeout=120,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def _base_pin_name(pin_name: str) -> str:
    return pin_name.split()[0]


def _ball_sort_key(ball: str) -> tuple[str, int]:
    match = re.match(r"^([A-Z]+)([0-9]+)$", ball)
    if not match:
        return (ball, 0)
    return (match.group(1), int(match.group(2)))
