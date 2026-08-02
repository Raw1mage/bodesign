"""Shared root-visibility guard for the readiness family (fail-loud-on-invisible-path).

The bodesign MCP server runs containerized; its only mounts are `.run`, the sessions
volume, and the vault volume. A caller can pass a host path the container cannot see — an
unmounted Google-Drive FUSE mount, or simply a typo'd/absent path. When that happens the
readiness family must fail **loud and distinguishable**: it must never return a syntactically
clean `readiness_pct: 0` with every deliverable `missing`, which is indistinguishable from a
genuinely-empty folder and silently misleads the agent into regenerating real deliverables.

This module is the single chokepoint every readiness entrypoint calls first. The unified
contract (DD-4, structured form): when the root is not visible, the readiness result carries
`root_visible: false` + a `warnings` list + a boundary-specific `next_step`, rather than a
deliverable next-step or a false score. No fallback, no guessing, no auto-mount.
"""

from __future__ import annotations

from pathlib import Path

# ── Stage folder map (SINGLE SOURCE) ────────────────────────────────────────
# Every C0x stage's product-root-relative folder. This is the ONE copy: both the
# roll-up (``package_readiness``) and the refs gate (``refs_gate.require_refs``)
# take it from here.
#
# Why it lives here rather than in either consumer: the readiness family's whole
# contract is that a ``folder`` argument is the PRODUCT ROOT and stage placement
# is derived, never pre-joined by a caller. That derivation needs exactly this
# map, so it belongs with the root guard, not inside one consumer that another
# consumer then has to reach into.
STAGE_FOLDER: dict[str, str] = {
    "c00": "C00-PRD",
    "c01": "C01-ID",
    "c02": "C02-ME",
    "c03": "C03-EE",
    "c04": "C04-Layout",
    "c05": "C05-FW",
    "c06": "C06-Verification",
    "c07": "C07-MFG",
}


class UnknownStageError(KeyError):
    """A stage label that is not in ``STAGE_FOLDER``. Never defaulted."""


def stage_folder_for(layer: str) -> str:
    """Map a stage label (``C01`` / ``c01``) to its product-root-relative folder.

    Case is normalised HERE, explicitly and in one place, because the two families
    of caller spell it differently (the refs gate passes ``"C01"``, the roll-up
    keys on ``"c01"``). Doing it at each call site is how the two spellings drift
    apart unnoticed.

    Fails LOUD on an unknown label (天條 1): returning a default folder here would
    make "this stage does not exist" and "this stage's SSOT is missing" produce the
    same downstream result — a missing-refs error naming a folder nobody asked for.
    """
    key = str(layer).strip().lower()
    if key not in STAGE_FOLDER:
        raise UnknownStageError(
            f"unknown stage label {layer!r}; known stages: {sorted(STAGE_FOLDER)}"
        )
    return STAGE_FOLDER[key]


def cross_track_inconsistency(
    *,
    all_missing: bool,
    all_present: bool,
    dod_ok: bool,
    has_blocking_gaps: bool = False,
) -> str | None:
    """Detect the two states a readiness verb must never return silently.

    A readiness verb reports on the same package through two independent tracks:
    the ARTIFACT track (does each deliverable file exist?) and the DoD track (does
    the GUIDE's Definition-of-Done manifest resolve?). They must agree, because
    they are two views of one filesystem.

    Measured at HEAD on a real package (BR_20260719 c01): ``readiness_pct: 0`` with
    every artifact ``missing`` WHILE ``dod_ok: true`` — the tracks were resolving
    different candidate paths for the same deliverables. The output was clean,
    well-formed, warning-free, and impossible. Nothing noticed for two weeks.

    Returns a human-readable description, or None when the tracks are consistent.
    ``has_blocking_gaps`` suppresses the all-present direction, because a refs /
    provenance gap legitimately forces ``dod_ok=false`` on a package whose files
    are all present — that is the gate working, not a disagreement.
    """
    if all_missing and dod_ok:
        return (
            "artifact track reports every deliverable missing while the DoD track "
            "reports dod_ok=true — the two tracks resolved different paths for the "
            "same package"
        )
    if all_present and not dod_ok and not has_blocking_gaps:
        return (
            "artifact track reports every deliverable present while the DoD track "
            "reports dod_ok=false with no blocking gap — the two tracks resolved "
            "different paths for the same package"
        )
    return None


BOUNDARY_NEXT_STEP = (
    "Folder not visible to the bodesign container: {path}. bodesign MCP runs in Docker and only "
    "mounts .run / sessions / vault — a host path resolves only if it is inside that mount "
    "namespace. Pass a mounted path, or upload the tree via the file model "
    "(tar -> token -> doc_dir) and call the tool with the returned token."
)


def root_guard(folder: str | Path) -> tuple[Path, bool, str | None]:
    """Return ``(root, visible, warning)`` for a readiness target folder.

    ``visible`` is False when the path does not exist / is not reachable inside the container.
    ``warning`` is a human-readable string in that case, else ``None``. Pure and read-only.
    """
    root = Path(folder)
    if root.exists():
        return root, True, None
    return root, False, f"Folder not found / not visible to the bodesign container: {root}"


def boundary_next_step(path: str | Path) -> str:
    """The next_step instruction to surface when the root is not visible."""
    return BOUNDARY_NEXT_STEP.format(path=path)


def resolve_stage_json(stage_dir: str | Path, filename: str) -> Path:
    """Resolve an AI-facing stage JSON with an explicit new-then-legacy order.

    Owner ruling (2026-07-17): the stage root holds only human-facing deliverables;
    AI/machine JSON lives under ``03_output/``. Read order is an explicit contract
    (new location first, legacy root second) — NOT a silent fallback:

      1. ``<stage_dir>/03_output/<filename>`` (canonical new position)
      2. ``<stage_dir>/<filename>`` (legacy root, back-compat)

    When neither exists, returns the canonical new-position path so write-side
    scaffolding lands in the right place. Read-side callers still hit their existing
    fail-fast on a genuinely-absent file.
    """
    base = Path(stage_dir)
    new_pos = base / "03_output" / filename
    if new_pos.exists():
        return new_pos
    legacy = base / filename
    if legacy.exists():
        return legacy
    return new_pos
