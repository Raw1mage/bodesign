"""refs-first decomposition gate (EPIC capability_refs-derived-design, 切面 1).

The paradigm inversion's core: before ANY C00~C04 downstream generation verb
runs, the owning stage's ``01_refs/`` SSOT must exist and be traceable to an
owner authority source. When it is absent — or a source lacks a provenance
anchor — the gate raises a typed ``RefsGateError`` (fail-fast, never a silent
default). This is the machine enforcement of repo 天條 1 (No silent fallback)
and 天條 2 (No fabrication): an agent can no longer fabricate placement /
component / pin data with no design root and slip past honesty-model, because
placement coordinates are not "IC/net facts" but ARE now gated on refs.

Pure-python, core-side (no worker dependency). Read-only except when the
caller explicitly asks to persist the manifest.

Data taxonomy (BINDING — every abstract name below is a contract, not decoration):
  * RefsSource        — one classified file under a stage's ``01_refs/``.
                        input: a Path; output: {path, category, media_type,
                        authority_rank, adjudicated}; NOT a design deliverable.
  * RefsManifest      — the full inventory of a stage's ``01_refs/`` +
                        authority order parsed from Reference_Baseline.md.
                        Complete IFF ``sources`` non-empty. NOT a substitute
                        for the sources themselves.
  * RefsGateError     — typed fail-fast signal (code + structured detail).
                        NOT a warning; the caller MUST act on ``detail``.
  * require_refs      — the single chokepoint a downstream verb calls first.
                        Returns a RefsManifest on pass; raises on any miss.
                        Done IFF the stage's ``01_refs/`` has ≥1 source.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── typed error codes (errors.md, BINDING; mirrors plan errors.md) ──────────
REFS_SSOT_MISSING = "REFS_SSOT_MISSING"
REFS_ANCHOR_MISSING = "REFS_ANCHOR_MISSING"
REFS_MANIFEST_INVALID = "REFS_MANIFEST_INVALID"

# The canonical refs bucket every stage consumes (skills/bodesign references/
# stage-structure.md: "01_refs/ — external inputs this stage CONSUMES").
REFS_DIRNAME = "01_refs"
BASELINE_FILENAME = "Reference_Baseline.md"
MANIFEST_SCHEMA = "bodesign.refs.manifest.v1"

# Source classification — category is inferred from directory/name cues, never
# guessed into a fact. An unclassifiable source is category "unclassified"
# (surfaced, not silently dropped).
_CATEGORY_CUES: tuple[tuple[str, str], ...] = (
    ("formal_requirement", "需求書"),
    ("formal_requirement", "requirement"),
    ("formal_requirement", "正式需求"),
    ("datasheet", "datasheet"),
    ("datasheet", "規格書"),
    ("heritage", "heritage"),
    ("heritage", "參考"),
    ("heritage", "reference"),
    ("concept", "concept"),
    ("concept", "sketch"),
    ("concept", "moodboard"),
)

_MEDIA_BY_SUFFIX: dict[str, str] = {
    ".pdf": "pdf", ".pptx": "pptx", ".ppt": "pptx",
    ".docx": "docx", ".doc": "docx", ".xlsx": "spreadsheet", ".csv": "spreadsheet",
    ".md": "markdown", ".txt": "text", ".json": "json",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".svg": "image",
    ".step": "cad", ".stp": "cad", ".stl": "cad",
}

# Rich media that a deterministic scan cannot itself read — flags the source as
# NOT yet adjudicated (a reader-subagent must interpret it before its content
# can be asserted). Markdown/text/json are machine-readable → adjudicated.
_RICH_MEDIA = {"pdf", "pptx", "docx", "spreadsheet", "image", "cad"}


class RefsGateError(ValueError):
    """Deterministic fail-fast error for the REFS_* family.

    Attributes:
      code: stable error code (REFS_SSOT_MISSING / REFS_ANCHOR_MISSING / ...).
      detail: structured payload (e.g. {"layer": "C04", "refs_root": "..."}).
        Never a free-form default substitution — the caller must act on it.
    """

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        self.code = code
        self.detail: dict[str, Any] = dict(detail)
        super().__init__(f"{code}: {message}")


@dataclass(slots=True)
class RefsSource:
    path: str
    category: str
    media_type: str
    authority_rank: int  # 1 = highest authority; 0 = not ranked in baseline
    adjudicated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "category": self.category,
            "media_type": self.media_type,
            "authority_rank": self.authority_rank,
            "adjudicated": self.adjudicated,
        }


@dataclass(slots=True)
class RefsManifest:
    schema: str
    refs_root: str
    root_visible: bool
    authority_order: list[str]
    sources: list[RefsSource]
    warnings: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """A refs SSOT is complete IFF it is visible and has ≥1 source."""
        return self.root_visible and bool(self.sources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "refs_root": self.refs_root,
            "root_visible": self.root_visible,
            "complete": self.complete,
            "authority_order": list(self.authority_order),
            "source_count": len(self.sources),
            "sources": [s.to_dict() for s in self.sources],
            "unadjudicated": [s.path for s in self.sources if not s.adjudicated],
            "warnings": list(self.warnings),
        }


def _classify(rel_path: str) -> str:
    # Classify on the FULL relative path, not just the basename: refs are
    # commonly bucketed by folder (e.g. ``01_正式需求書/deck.pptx``) where the
    # category cue lives in the parent directory, not the filename.
    low = rel_path.lower()
    for category, cue in _CATEGORY_CUES:
        if cue.lower() in low:
            return category
    return "unclassified"


def _media_type(suffix: str) -> str:
    return _MEDIA_BY_SUFFIX.get(suffix.lower(), "other")


def _parse_authority_order(baseline: Path) -> list[str]:
    """Extract the authority order lines from Reference_Baseline.md.

    Recognises a line literally starting with 'authority order:' and returns
    the remainder split on '>' (highest-first). Absent baseline → empty list
    (surfaced as a warning by the caller; NOT an error — a stage may legitimately
    have no explicit ranking, but then every source is authority_rank 0).
    """
    try:
        text = baseline.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("authority order:"):
            payload = stripped.split(":", 1)[1]
            return [part.strip() for part in payload.split(">") if part.strip()]
    return []


def _rank_for(source_name: str, authority_order: list[str]) -> int:
    """Map a source to its 1-based authority rank via substring match against
    the baseline order, else 0 (unranked). Deterministic, first-match wins."""
    low = source_name.lower()
    for idx, token in enumerate(authority_order, start=1):
        # token like "formal deck" / "X01/BOM" — match on any word ≥3 chars.
        for word in token.replace("/", " ").split():
            if len(word) >= 3 and word.lower() in low:
                return idx
    return 0


def ingest_refs(refs_root: str | Path) -> RefsManifest:
    """Scan a stage's ``01_refs/`` (or an explicit refs root) into a manifest.

    ``refs_root`` may point either at the stage folder (we append ``01_refs/``)
    or directly at an ``01_refs`` directory. Read-only; never writes.

    Fail-loud on an invisible/absent root: returns a manifest with
    ``root_visible=False`` and a warning (the CALLER decides whether that is a
    gate failure — see ``require_refs``). This mirrors readiness_common's
    root-guard discipline: never a clean empty result indistinguishable from a
    genuinely-empty folder.
    """
    root = Path(refs_root)
    if root.name != REFS_DIRNAME:
        # STRICT resolution (review F7): a stage folder ALWAYS resolves to its
        # 01_refs/ child. The old "treat the given path as-is when the child is
        # missing" fallback silently scanned the whole stage tree, so scaffolded
        # PRD files masqueraded as refs sources and the gate passed with a
        # fabricated manifest — the exact silent fallback the 天條 forbids.
        root = root / REFS_DIRNAME

    if not root.exists() or not root.is_dir():
        return RefsManifest(
            schema=MANIFEST_SCHEMA,
            refs_root=str(root),
            root_visible=False,
            authority_order=[],
            sources=[],
            warnings=[f"refs root not found / not a directory: {root}"],
        )

    authority_order = _parse_authority_order(root / BASELINE_FILENAME)
    warnings: list[str] = []
    if not authority_order:
        warnings.append(
            f"no '{BASELINE_FILENAME}' authority order found under {root}; "
            "every source ranked 0 (unranked)"
        )

    sources: list[RefsSource] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name == BASELINE_FILENAME:
            continue
        media = _media_type(path.suffix)
        rel = str(path.relative_to(root))
        sources.append(
            RefsSource(
                path=rel,
                category=_classify(rel),
                media_type=media,
                authority_rank=_rank_for(rel, authority_order),
                adjudicated=media not in _RICH_MEDIA,
            )
        )

    if not sources:
        warnings.append(f"refs root visible but holds no source files: {root}")

    return RefsManifest(
        schema=MANIFEST_SCHEMA,
        refs_root=str(root),
        root_visible=True,
        authority_order=authority_order,
        sources=sources,
        warnings=warnings,
    )


def require_refs(folder: str | Path, layer: str) -> RefsManifest:
    """Gate chokepoint: a downstream verb calls this FIRST.

    Returns the RefsManifest on pass. Raises RefsGateError (fail-fast) when the
    stage's ``01_refs/`` SSOT is missing or empty — the caller MUST NOT proceed
    to generate anything. ``layer`` is a label (e.g. "C04") carried into the
    error detail so the surface names the offending stage.

    No silent fallback, no default, no auto-mount (repo 天條 1/2).
    """
    manifest = ingest_refs(folder)
    if not manifest.root_visible:
        raise RefsGateError(
            REFS_SSOT_MISSING,
            f"{layer}: no {REFS_DIRNAME}/ SSOT visible at {manifest.refs_root} — "
            "reverse-decompose the owner authority source into the stage's "
            f"{REFS_DIRNAME}/ before any downstream generation.",
            layer=layer,
            refs_root=manifest.refs_root,
            reason="root_not_visible",
        )
    if not manifest.sources:
        raise RefsGateError(
            REFS_SSOT_MISSING,
            f"{layer}: {REFS_DIRNAME}/ SSOT is empty at {manifest.refs_root} — "
            "no owner authority source has been decomposed into it.",
            layer=layer,
            refs_root=manifest.refs_root,
            reason="no_sources",
        )
    return manifest
