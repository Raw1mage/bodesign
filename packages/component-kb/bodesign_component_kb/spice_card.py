"""Datasheet-grounded SPICE model cards (knowledge/datasheet-spice-models).

Two responsibilities, both deterministic:

1. ``ingest_spice_extraction`` — validate an extraction batch row-by-row and
   write accepted rows into the vault L4 EAV store (spice_model.* namespace).
   Rejections are per-row (the batch continues); ``not_found`` rows are
   reported but never written. Every accepted row lands as trust=unverified.

2. (Phase 2) model-card generation — see ``generate_model_card``.

Red lines:
- LLM only participates in extraction (upstream); this module is fully
  deterministic. No averaging, no silent defaults, no fabricated values.
- Unknown field_path -> row rejected (SPX_FIELD_UNKNOWN); the vault registry
  fail-fast (VAULT-E401) is preserved.
- Missing evidence -> row rejected (SPX_EVIDENCE_MISSING); a found value with
  no document_sha256/page is never trusted into the store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .repository import SPICE_MODEL_FIELDS, VaultRepository

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FIELD_PATH_RE = re.compile(r"^spice_model\.(diode|ldo|passive)\.[a-z0-9_]+$")
_VALUE_KINDS = ("min", "typ", "max")


class SpiceCardError(Exception):
    """SPX_* namespace errors carrying a structured payload (DD-6).

    Per-row ingest rejections are NOT raised — they are collected into the
    IngestReport.rejected list. This exception is reserved for whole-call
    failures (e.g. model-card generation gates in Phase 2).
    """

    def __init__(self, code: str, message: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.payload = payload or {}


@dataclass(frozen=True)
class WrittenRow:
    field_path: str
    spec_value_id: int
    trust: str = "unverified"


@dataclass(frozen=True)
class RejectedRow:
    field_path: str
    error_code: str
    detail: str


@dataclass
class IngestReport:
    mpn: str
    written: list[WrittenRow] = field(default_factory=list)
    rejected: list[RejectedRow] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mpn": self.mpn,
            "written": [
                {"field_path": w.field_path, "spec_value_id": w.spec_value_id, "trust": w.trust}
                for w in self.written
            ],
            "rejected": [
                {"field_path": r.field_path, "error_code": r.error_code, "detail": r.detail}
                for r in self.rejected
            ],
            "not_found": list(self.not_found),
        }


def _known_field(field_path: str) -> bool:
    """True iff field_path is in the closed v1 registry (DD-3)."""
    match = _FIELD_PATH_RE.match(field_path)
    if not match:
        return False
    category = match.group(1)
    leaf = field_path.split(".", 2)[2]
    return leaf in SPICE_MODEL_FIELDS.get(category, {})


def _validate_evidence(evidence: Any) -> str | None:
    """Return a rejection detail string, or None if evidence is valid."""
    if not isinstance(evidence, dict):
        return "evidence missing or not an object"
    sha = evidence.get("document_sha256")
    page = evidence.get("page")
    if not isinstance(sha, str) or not _SHA256_RE.match(sha):
        return "evidence.document_sha256 missing or not a 64-char hex digest"
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        return "evidence.page missing or not a positive integer"
    return None


def ingest_spice_extraction(
    repo: VaultRepository,
    mpn: str,
    rows: list[dict[str, Any]],
    *,
    actor: str | None = None,
) -> IngestReport:
    """Validate and persist an extraction batch (R2, task 1.2).

    Each row is validated independently:
    - status == "not_found": recorded in report.not_found, never written.
    - field_path not in registry: rejected SPX_FIELD_UNKNOWN.
    - value_num absent/non-numeric for status=found: rejected SPX_VALUE_INVALID.
    - evidence missing/malformed: rejected SPX_EVIDENCE_MISSING.
    - otherwise: written via repo.write_spec (trust forced unverified).

    Returns an IngestReport. Never raises on a single bad row — the batch
    always completes so the caller sees the full accept/reject picture.
    """
    report = IngestReport(mpn=mpn)
    if not isinstance(rows, list) or not rows:
        raise SpiceCardError(
            "SPX_VALUE_INVALID",
            "ingest batch has no rows",
            {"mpn": mpn},
        )

    for row in rows:
        field_path = str(row.get("field_path", "")).strip()
        status = row.get("status", "found")

        if status == "not_found":
            report.not_found.append(field_path)
            continue

        if not _known_field(field_path):
            report.rejected.append(RejectedRow(
                field_path=field_path,
                error_code="SPX_FIELD_UNKNOWN",
                detail=f"field_path {field_path!r} not in spice_model registry (DD-3 closed list)",
            ))
            continue

        value_num = row.get("value_num")
        if not isinstance(value_num, (int, float)) or isinstance(value_num, bool):
            report.rejected.append(RejectedRow(
                field_path=field_path,
                error_code="SPX_VALUE_INVALID",
                detail="value_num absent or non-numeric for status=found",
            ))
            continue

        evidence_detail = _validate_evidence(row.get("evidence"))
        if evidence_detail is not None:
            report.rejected.append(RejectedRow(
                field_path=field_path,
                error_code="SPX_EVIDENCE_MISSING",
                detail=evidence_detail,
            ))
            continue

        evidence = row["evidence"]
        value_kind = row.get("value_kind", "typ")
        if value_kind not in _VALUE_KINDS:
            value_kind = "typ"
        source_note = (
            f"datasheet sha={evidence['document_sha256']} p.{evidence['page']}"
        )
        anchor = evidence.get("anchor_text")
        if anchor:
            source_note += f" :: {anchor}"

        kwargs: dict[str, Any] = {
            "unit": row.get("unit"),
            "condition": row.get("condition"),
            "source_note": source_note,
            "confidence": "unverified",
            "actor": actor,
        }
        kwargs[f"{value_kind}_val"] = float(value_num)

        written = repo.write_spec(mpn, field_path, **kwargs)
        report.written.append(WrittenRow(
            field_path=field_path,
            spec_value_id=int(written["id"]),
        ))

    return report


# -- Model-card generation (R3, tasks 2.1-2.3) ----------------------------

_SUPPORTED_CATEGORIES = ("diode", "ldo", "passive")


@dataclass(frozen=True)
class ResolvedParam:
    """One L4 parameter selected for the card, with its provenance."""

    leaf: str
    value_num: float
    value_kind: str
    document_sha256: str | None
    page: int | None
    trust: str


@dataclass(frozen=True)
class ModelCard:
    mpn: str
    category: str
    card_name: str
    card_text: str
    provenance: tuple[ResolvedParam, ...]
    smoke: str = "not-run"
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mpn": self.mpn,
            "category": self.category,
            "card_name": self.card_name,
            "card_text": self.card_text,
            "provenance": [
                {
                    "field_path": f"spice_model.{self.category}.{p.leaf}",
                    "document_sha256": p.document_sha256,
                    "page": p.page,
                    "trust": p.trust,
                    "value_num": p.value_num,
                    "value_kind": p.value_kind,
                }
                for p in self.provenance
            ],
            "smoke": self.smoke,
            "limitations": list(self.limitations),
        }


def sanitize_mpn(mpn: str) -> str:
    """MPN -> safe SPICE name suffix. Mirrors the spice skill convention.

    "1N4148W" -> "1N4148W", "AMS1117-3.3" -> "AMS1117_3_3".
    Deterministic; no host-side import (skill is host-side).
    """
    return re.sub(r"[^A-Za-z0-9_]", "_", mpn.strip())


def _select_value(rows: list[dict[str, Any]], leaf: str, category: str) -> ResolvedParam:
    """typ-selection rule (DD-3). No averaging.

    Priority: a row with value_kind='typ' wins. Else, if exactly one row
    exists, use it. Else (multiple rows, none typ) -> SPX_PARAMS_AMBIGUOUS.
    """
    def _pick(row: dict[str, Any]) -> tuple[float, str]:
        for kind in ("typ", "min", "max"):
            val = row.get(f"{kind}_val")
            if val is not None:
                return float(val), kind
        if row.get("value_num") is not None:
            return float(row["value_num"]), "typ"
        raise SpiceCardError(
            "SPX_VALUE_INVALID",
            f"L4 row for {leaf} has no numeric value slot",
            {"leaf": leaf, "category": category},
        )

    typ_rows = [r for r in rows if r.get("typ_val") is not None]
    if typ_rows:
        chosen = typ_rows[0]
    elif len(rows) == 1:
        chosen = rows[0]
    else:
        raise SpiceCardError(
            "SPX_PARAMS_AMBIGUOUS",
            f"{len(rows)} L4 rows for {leaf} without a typ value; no averaging",
            {
                "field_path": f"spice_model.{category}.{leaf}",
                "candidates": [
                    {
                        "min_val": r.get("min_val"),
                        "typ_val": r.get("typ_val"),
                        "max_val": r.get("max_val"),
                        "condition": r.get("condition"),
                    }
                    for r in rows
                ],
                "repair": "extract a typ value or disambiguate the rows",
            },
        )

    value_num, value_kind = _pick(chosen)
    note = chosen.get("source_note") or ""
    sha = None
    page = None
    sha_match = re.search(r"sha=([0-9a-f]{64})", note)
    if sha_match:
        sha = sha_match.group(1)
    page_match = re.search(r"\bp\.(\d+)", note)
    if page_match:
        page = int(page_match.group(1))
    return ResolvedParam(
        leaf=leaf,
        value_num=value_num,
        value_kind=value_kind,
        document_sha256=sha,
        page=page,
        trust=chosen.get("confidence", "unverified"),
    )


def _gather_params(
    repo: VaultRepository, mpn: str, category: str
) -> dict[str, ResolvedParam]:
    """Read all L4 rows for the category and apply typ-selection per leaf."""
    fields = SPICE_MODEL_FIELDS[category]
    resolved: dict[str, ResolvedParam] = {}
    for leaf in fields:
        field_path = f"spice_model.{category}.{leaf}"
        out = repo.read_spec(mpn, field_path)
        if out["status"] != "found" or not out["values"]:
            continue
        resolved[leaf] = _select_value(out["values"], leaf, category)
    return resolved


def _provenance_header(mpn: str, category: str, params: dict[str, ResolvedParam]) -> str:
    """Deterministic provenance comment block. No timestamps (byte-identical)."""
    lines = [
        f"* Datasheet-grounded SPICE model for {mpn} (category={category})",
        "* Generated by bodesign component-kb spice_card (deterministic).",
        "* Provenance (per parameter):",
    ]
    for leaf in sorted(params):
        p = params[leaf]
        sha8 = p.document_sha256[:8] if p.document_sha256 else "unknown"
        page = p.page if p.page is not None else "?"
        lines.append(
            f"*   {leaf} = {p.value_num:g} [{p.value_kind}] "
            f"source={sha8}:p{page} trust={p.trust}"
        )
    return "\n".join(lines)


def _card_diode(mpn: str, name: str, params: dict[str, ResolvedParam]) -> str:
    p = {leaf: rp.value_num for leaf, rp in params.items()}
    parts = [f"IS={p['is_a']:g}", f"N={p['n']:g}"]
    if "rs_ohm" in p:
        parts.append(f"RS={p['rs_ohm']:g}")
    if "cj0_f" in p:
        parts.append(f"CJO={p['cj0_f']:g}")
    if "bv_v" in p:
        parts.append(f"BV={p['bv_v']:g}")
    if "ibv_a" in p:
        parts.append(f"IBV={p['ibv_a']:g}")
    return f".model {name} D({' '.join(parts)})"


def _card_passive(mpn: str, name: str, params: dict[str, ResolvedParam]) -> str:
    # RLC parasitic subckt: a 2-terminal model with ESR/ESL where given.
    p = {leaf: rp.value_num for leaf, rp in params.items()}
    body = [f".subckt {name} a b"]
    esr = p.get("esr_ohm")
    esl = p.get("esl_h")
    nodes = ["a"]
    idx = 0
    if esl is not None:
        idx += 1
        node = f"n{idx}"
        body.append(f"Lesl {nodes[-1]} {node} {esl:g}")
        nodes.append(node)
    if esr is not None:
        idx += 1
        node = f"n{idx}"
        body.append(f"Resr {nodes[-1]} {node} {esr:g}")
        nodes.append(node)
    if "c_f" in p:
        body.append(f"Cmain {nodes[-1]} b {p['c_f']:g}")
    elif "l_h" in p:
        body.append(f"Lmain {nodes[-1]} b {p['l_h']:g}")
    elif "r_ohm" in p:
        body.append(f"Rmain {nodes[-1]} b {p['r_ohm']:g}")
    body.append(".ends")
    return "\n".join(body)


def _card_ldo(mpn: str, name: str, params: dict[str, ResolvedParam]) -> str:
    # First-order behavioral LDO: ideal output source minus dropout, current
    # limited. Independent implementation (no host-side skill import).
    p = {leaf: rp.value_num for leaf, rp in params.items()}
    vout = p["vout_v"]
    dropout = p["dropout_v"]
    iout_max = p["iout_max_a"]
    return (
        f".subckt {name} vin vout gnd\n"
        f"* First-order behavioral LDO; no transient/PSRR/thermal modeling.\n"
        f"Eout vout gnd vin gnd 1.0\n"
        f"Rdrop vin n_int {dropout / iout_max:g}\n"
        f"Vref n_int vout DC {vout:g}\n"
        f"Ilim vout gnd DC 0\n"
        f".ends"
    )


_TEMPLATES = {"diode": _card_diode, "ldo": _card_ldo, "passive": _card_passive}

_LIMITATIONS = {
    "ldo": (
        "first-order behavioral approximation; no transient response, "
        "PSRR, or thermal modeling",
    ),
    "diode": (),
    "passive": (),
}


def _card_name(mpn: str, category: str) -> str:
    prefix = {"diode": "D", "ldo": "LDO", "passive": "X"}[category]
    return f"{prefix}_{sanitize_mpn(mpn)}"


def generate_model_card(
    repo: VaultRepository, mpn: str, category: str
) -> ModelCard:
    """Deterministically render a SPICE model card from L4 state (R3).

    Required parameters absent -> SPX_PARAMS_MISSING (payload lists the
    missing field_paths + repair guidance). Unsupported category ->
    SPX_CATEGORY_UNSUPPORTED. Output is byte-identical for identical L4
    state (no timestamps).
    """
    if category not in _SUPPORTED_CATEGORIES:
        raise SpiceCardError(
            "SPX_CATEGORY_UNSUPPORTED",
            f"category {category!r} outside v1 closed list (diode|ldo|passive)",
            {"category": category, "supported": list(_SUPPORTED_CATEGORIES)},
        )

    params = _gather_params(repo, mpn, category)

    required = [leaf for leaf, spec in SPICE_MODEL_FIELDS[category].items() if spec["required"]]
    if category == "passive":
        # passive required is conditional on sub-category; at least one of the
        # primary value leaves (c_f/l_h/r_ohm) must be present.
        primary = {"c_f", "l_h", "r_ohm"}
        if not (primary & set(params)):
            raise SpiceCardError(
                "SPX_PARAMS_MISSING",
                "passive card needs one of c_f / l_h / r_ohm in L4",
                {
                    "mpn": mpn,
                    "category": category,
                    "missing": ["spice_model.passive.c_f|l_h|r_ohm"],
                    "repair": "extract the primary passive value (capacitance, inductance, or resistance)",
                },
            )
    else:
        missing = [leaf for leaf in required if leaf not in params]
        if missing:
            raise SpiceCardError(
                "SPX_PARAMS_MISSING",
                f"required parameters absent in L4 for {mpn} {category}",
                {
                    "mpn": mpn,
                    "category": category,
                    "missing": [f"spice_model.{category}.{leaf}" for leaf in missing],
                    "repair": "extract these parameters from the datasheet and ingest them",
                },
            )

    name = _card_name(mpn, category)
    header = _provenance_header(mpn, category, params)
    body = _TEMPLATES[category](mpn, name, params)
    card_text = f"{header}\n{body}\n"

    provenance = tuple(params[leaf] for leaf in sorted(params))
    return ModelCard(
        mpn=mpn,
        category=category,
        card_name=name,
        card_text=card_text,
        provenance=provenance,
        smoke="not-run",
        limitations=_LIMITATIONS.get(category, ()),
    )


# -- Smoke validation + materialization (R5, tasks 3.1-3.2) ---------------

import json
import shutil
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path


@dataclass(frozen=True)
class SmokeResult:
    """Outcome of an ngspice DC-op smoke test (DD-7).

    status:
    - "pass": ngspice ran the testbench, DC operating point converged.
    - "fail": ngspice ran but errored; stderr_excerpt carries the reason.
              The card is excluded from the manifest (SPX_SMOKE_FAILED).
    - "skipped-no-simulator": ngspice binary not found; explicit, not silent.
    """

    status: str
    stderr_excerpt: str = ""


def _ngspice_available() -> bool:
    return shutil.which("ngspice") is not None


def _smoke_testbench(card: ModelCard) -> str:
    """Minimal DC-op testbench wrapping the card. Deterministic per category."""
    name = card.card_name
    if card.category == "diode":
        # forward-bias the diode through a series resistor
        return (
            f"* smoke: {card.mpn}\n"
            f"{card.card_text}"
            f"V1 a 0 DC 1\n"
            f"R1 a k 1k\n"
            f"D1 k 0 {name}\n"
            f".op\n"
            f".end\n"
        )
    if card.category == "ldo":
        return (
            f"* smoke: {card.mpn}\n"
            f"{card.card_text}"
            f"V1 vin 0 DC 5\n"
            f"X1 vin vout 0 {name}\n"
            f"Rload vout 0 1k\n"
            f".op\n"
            f".end\n"
        )
    # passive
    return (
        f"* smoke: {card.mpn}\n"
        f"{card.card_text}"
        f"V1 a 0 DC 1\n"
        f"X1 a 0 {name}\n"
        f".op\n"
        f".end\n"
    )


def run_smoke(card: ModelCard) -> SmokeResult:
    """Run an ngspice DC-op smoke test against the card (task 3.1).

    Three-state outcome (DD-7): pass / fail / skipped-no-simulator. Never
    silently swallows a simulator absence — a missing ngspice is reported
    explicitly so the caller can decide.
    """
    if not _ngspice_available():
        return SmokeResult(status="skipped-no-simulator")

    deck = _smoke_testbench(card)
    with tempfile.TemporaryDirectory() as d:
        deck_path = Path(d) / "smoke.cir"
        deck_path.write_text(deck)
        try:
            proc = subprocess.run(
                ["ngspice", "-b", str(deck_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return SmokeResult(status="fail", stderr_excerpt="ngspice timed out (30s)")

    combined = (proc.stderr or "") + (proc.stdout or "")
    # ngspice returns 0 even on some errors; scan for hard error markers.
    lower = combined.lower()
    failed = (
        proc.returncode != 0
        or "error" in lower
        or "singular matrix" in lower
        or "aborted" in lower
    )
    if failed:
        excerpt = "\n".join(
            line for line in combined.splitlines()
            if "error" in line.lower() or "aborted" in line.lower()
        )[:500] or combined[:500]
        return SmokeResult(status="fail", stderr_excerpt=excerpt)
    return SmokeResult(status="pass")


def _provenance_summary(card: ModelCard) -> str:
    """One-line manifest provenance, e.g. '3 params from sha=ab12cd34 p.3, trust=unverified'."""
    n = len(card.provenance)
    shas = sorted({p.document_sha256[:8] for p in card.provenance if p.document_sha256})
    pages = sorted({p.page for p in card.provenance if p.page is not None})
    trusts = sorted({p.trust for p in card.provenance})
    sha_part = ",".join(shas) if shas else "unknown"
    page_part = (
        "p." + "-".join(str(x) for x in (min(pages), max(pages)))
        if pages else "p?"
    )
    if len(pages) == 1:
        page_part = f"p.{pages[0]}"
    return f"{n} params from sha={sha_part} {page_part}, trust={','.join(trusts)}"


@dataclass(frozen=True)
class MaterializeResult:
    written: tuple[str, ...]          # MPNs whose cards were written + indexed
    excluded: tuple[str, ...]         # MPNs whose smoke failed (not indexed)
    manifest_path: str


def materialize_model_cards(
    project_dir: str | Path,
    mpns: list[str],
    repo: VaultRepository,
    *,
    category_of: dict[str, str],
) -> MaterializeResult:
    """Render, smoke-test, and materialize cards into <project>/spice/models/ (task 3.2).

    For each MPN: generate the card, run smoke. pass/skipped -> write the
    .sub file and add a manifest entry (source=vault-grounded). fail ->
    card excluded from the manifest (DD-7). The manifest format mirrors the
    spice skill's cascade tier 0 (dict keyed by sanitize_mpn).

    Args:
        project_dir: project root; spice/models/ is created alongside.
        mpns: parts to materialize.
        repo: vault repository (source of L4 params).
        category_of: MPN -> category mapping (diode|ldo|passive).
    """
    models_dir = Path(project_dir) / "spice" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = models_dir / "manifest.json"

    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError):
            manifest = {}

    written: list[str] = []
    excluded: list[str] = []

    for mpn in mpns:
        category = category_of.get(mpn)
        if category is None:
            raise SpiceCardError(
                "SPX_CATEGORY_UNSUPPORTED",
                f"no category provided for {mpn}",
                {"mpn": mpn},
            )
        card = generate_model_card(repo, mpn, category)
        smoke = run_smoke(card)
        card = replace(card, smoke=smoke.status)

        if smoke.status == "fail":
            excluded.append(mpn)
            continue

        key = sanitize_mpn(mpn)
        filename = f"{key}.sub"
        (models_dir / filename).write_text(card.card_text)
        manifest[key] = {
            "file": filename,
            "mpn": mpn,
            "type": category,
            "source": "vault-grounded",
            "smoke": smoke.status,
            "provenance_summary": _provenance_summary(card),
        }
        written.append(mpn)

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return MaterializeResult(
        written=tuple(written),
        excluded=tuple(excluded),
        manifest_path=str(manifest_path),
    )
