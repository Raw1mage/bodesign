"""_skill_nudge — single source of the fail-loud "you skipped the contract" remedy
affordance (plan mcp_r17-r06-conformance DD-5; mcp-integration-standard R0.6).

Why this module exists
──────────────────────
R0.6 root cause: the harness tells agents "load skill(bodesign) before touching a
board/token" only as PROSE (AGENTS.md / server instructions), and prose cannot stop
a reflex. An agent that never read the companion-skill contract walks straight into
a wall the skill would have prevented, then — having hit the wall — tends to bypass
the tool entirely (hand-edit the underlying KiCad/OOXML/Gerber, shell out) rather
than read the contract. bodesign CANNOT observe whether the caller loaded a skill:
that state lives in another process's SkillLayerRegistry, and a cross-process
handshake to query it is REJECTED (R0.6.1 定海神針 — couples the service to one host,
R0.2 defect). What bodesign CAN observe is the toolcall behaviour fingerprint of a
caller who never read the contract: the wall itself.

The design (定海神針):
    Do NOT judge the caller. Append a corrective nudge to the message the caller
    ALREADY hit at the wall. A reader who read the contract rarely hits these walls;
    if they do, the extra nudge is harmless. So bodesign's inability to know "did
    they read the skill" is SIDESTEPPED — we only ever add a hint at an observable
    wall, and the asymmetry ("readers rarely wall") filters it. No false accusation
    is possible because the nudge is only ever added at a real wall.

Two force levels (R0.6.3)
─────────────────────────
- ``hard`` — the action is genuinely wrong (bad-shape id, grain-mismatch zero-element
  edit). The tool already fails; we ENRICH the failure with the correct primitive +
  ``skill(bodesign)``. A grain-mismatch that previously returned a silent ``ok=true``
  no-op MUST be converted to a loud failure (a silent no-op reporting success is
  itself an R0.2 defect — the caller believes the edit landed).
- ``advisory`` — the action is suspicious but not wrong (first unbounded sweep of a
  large workspace with no prior recon). We attach a NON-blocking hint; the result is
  returned as normal. Never converts a success into a failure. When the fingerprint
  is ambiguous, prefer advisory (定海神針: a false hard-block is worse than a hint).

Transport (R0.6.4)
──────────────────
This module only BUILDS the structured ``remedy`` dict + classifies the wall. The
server's ``_render_remedy_line`` projects the dict onto MCP's only portable error
surface — the ``content`` text line (R0.5) — so a bare client's model AND the
opencode runtime both see it. The dict shape is ``{note: str}`` (note-only: a
skill-nudge has no host command to run), which the renderer already supports.

天條 11 (no fabricated fallback): a nudge is only ever ADDED to a wall the caller
genuinely hit; it never invents a wall, never guesses caller state, and never
silently rewrites a byte-identical success into a failure.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

# The one canonical companion identity (single-source; R17.5 parity reads this too).
COMPANION_SKILL = "bodesign"

# The one canonical instruction. Every wall points the agent at the same place.
_LOAD_SKILL = (
    f"load skill({COMPANION_SKILL}) first — it is the C00-C07 workflow contract you skipped"
)


def skill_nudge_note(*, correct_primitive: Optional[str] = None,
                     why: Optional[str] = None) -> str:
    """Build the human-readable nudge sentence for a wall.

    ``why`` states what the caller did wrong (the observable fingerprint);
    ``correct_primitive`` names the bodesign primitive that is the real next step.
    Both optional so a caller can nudge with only what it knows. The sentence is a
    single self-contained line so it reads well in a bare MCP client and is trivially
    liftable by a host (R0.5).
    """
    parts: list[str] = []
    if why and why.strip():
        parts.append(why.strip())
    parts.append(_LOAD_SKILL)
    if correct_primitive and correct_primitive.strip():
        parts.append(f"the correct primitive here is {correct_primitive.strip()}")
    return "; ".join(parts)


def skill_nudge_remedy(*, correct_primitive: Optional[str] = None,
                       why: Optional[str] = None) -> dict:
    """Build the structured ``remedy`` fragment for a HARD wall (R0.6.3 hard).

    Returns ``{"note": <sentence>}`` — consumed by the server's remedy renderer into
    a portable ``remedy:`` line. Placed by the caller under ``error.remedy`` at the
    raise site (rich dict stays for programmatic consumers; the text projection
    reaches bare clients).
    """
    return {"note": skill_nudge_note(correct_primitive=correct_primitive, why=why)}


def skill_nudge_advisory(*, why: Optional[str] = None,
                         correct_primitive: Optional[str] = None) -> str:
    """Build a NON-blocking advisory string for a SUSPICIOUS-but-not-wrong action
    (R0.6.3 advisory). Returned as a plain warning the caller appends to a SUCCESSFUL
    result's warnings — it must never convert success into failure.
    """
    return skill_nudge_note(correct_primitive=correct_primitive, why=why)


# ── R0.6.2 wall-fingerprint detector (pure function of the request) ──────

# A recon-emitted token/id shape. bodesign's workspace-inspect / stage tools emit
# token dirs named ``tok_...`` and rel paths inside them; an id that is neither a
# real rel in the workspace nor a tok_ token is "bad-shape" (fed from a hand-unpacked
# part, not from a recon step).
def _looks_like_bad_shape_id(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return False
    # Heuristic (pure, no host consult): an id that carries an OOXML/internal-part
    # shape (``document.xml``-style bookmark, ``p_`` scout id, ``rId`` rel id) — a
    # namespace bodesign's recon never emits — is bad-shape.
    bad_markers = ("document.xml", "word/", "ppt/", "rId", "/_rels/")
    return any(m in v for m in bad_markers)


def detect_wall(name: str, args: Optional[dict], doc_dir: Optional[Path] = None,
                *, workspace_files: Optional[list] = None,
                prior_recon: bool = False) -> Optional[dict]:
    """Fingerprint a skipped-companion-skill wall from the toolcall itself (R0.6.2).

    Returns None when there is no wall, else a dict::

        {force: "hard"|"advisory", why: str, correct_primitive: str, remedy?: {note}}

    PURE function of the request — it never consults the host / caller skill-state
    (R0.6.1 定海神針). Inputs it may use: the tool name, its args, the resolved
    workspace file listing (``workspace_files``), and whether a recon (workspace
    inspect) already happened this session (``prior_recon``, a purely local flag the
    server tracks — NOT a skill-registry query).

    Fingerprints (each purely decidable from the request):
      1. bad-shape id (HARD): a token/target/path arg whose shape belongs to a
         namespace recon never emits → the caller fed a hand-unpacked part.
      2. grain-mismatch zero-element edit (HARD): an edit whose target matches zero
         workspace files → it would silently change nothing. Converted to loud.
      3. first unbounded sweep with no prior recon (ADVISORY): a large-workspace
         unbounded scan before any inspect → suspicious, not wrong.
    """
    args = args or {}
    files = workspace_files or []

    # (1) bad-shape id — HARD. Check the common id-carrying arg keys.
    for key in ("target", "id", "shape_id", "part_id", "anchor_id", "path", "token"):
        val = args.get(key)
        if isinstance(val, str) and _looks_like_bad_shape_id(val):
            return {
                "force": "hard",
                "why": (f"arg '{key}'={val!r} has an internal-part shape bodesign's "
                        "recon never emits — you fed a hand-unpacked id, not a "
                        "workspace-inspect result"),
                "correct_primitive": "bodesign_workspace_inspect",
                "remedy": skill_nudge_remedy(
                    correct_primitive="bodesign_workspace_inspect",
                    why=(f"arg '{key}'={val!r} is a bad-shape id (internal part, not a "
                         "recon-emitted workspace rel)")),
            }

    # (2) grain-mismatch zero-element edit — HARD. An edit whose target matches
    # nothing in the workspace would silently change zero elements.
    is_edit = name in ("edit", "revise") or "edit" in name
    target = args.get("target") or args.get("rel") or args.get("path")
    if is_edit and isinstance(target, str) and files:
        if target not in files and not any(f.endswith(target) for f in files):
            return {
                "force": "hard",
                "why": (f"edit target {target!r} matches zero workspace files — it "
                        "would silently change nothing (grain mismatch)"),
                "correct_primitive": "bodesign_workspace_inspect",
                "remedy": skill_nudge_remedy(
                    correct_primitive="bodesign_workspace_inspect",
                    why=(f"edit target {target!r} matches zero files; a silent "
                         "zero-element edit is not a success")),
            }

    # (3) first unbounded sweep with no prior recon — ADVISORY (never blocks).
    is_sweep = args.get("bounded") is False or args.get("unbounded") is True
    large = len(files) > 50 or bool(args.get("large"))
    if is_sweep and large and not prior_recon:
        return {
            "force": "advisory",
            "why": ("first unbounded sweep of a large workspace with no prior "
                    "recon — consider inspecting first"),
            "correct_primitive": "bodesign_workspace_inspect",
            "advisory": skill_nudge_advisory(
                correct_primitive="bodesign_workspace_inspect",
                why="first unbounded sweep of a large workspace with no prior recon"),
        }

    return None
