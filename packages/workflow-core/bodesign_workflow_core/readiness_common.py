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
