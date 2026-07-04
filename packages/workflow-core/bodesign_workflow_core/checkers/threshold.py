"""M1-5 — threshold-block resolution layer (DD-3: knowledge↔code runtime coupling).

The whole point of skillification is that a checker's numeric gate is NOT
hard-coded: it is read at run time from the owning ragbase `control.*` object,
so a knowledge update (re-distilled threshold) propagates to the checker with
zero code change. This module is that read path.

Contract (no-fabrication + no-silent-fallback):
- A control carries its machine-readable gate as a `threshold_block` JSON object
  inside `metadata_json` under the key ``"threshold_block"`` (or a list of them
  under ``"threshold_blocks"`` keyed by ``metric``).
- If the control has NO structured threshold_block, the resolver FAILS FAST
  (CHK_THRESHOLD_UNBOUND). It NEVER parses the human-readable ``body_md`` prose
  to invent a number — prose-parsing a value the distiller did not structure
  would fabricate an electrical threshold, violating the datasheet-grounded天條.
- A threshold_block with no ``source_anchor`` is rejected
  (CHK_SOURCE_ANCHOR_MISSING): an electrical gate with no traceable citation is
  not allowed to gate a design.

Determinism: the resolver is a pure read over sqlite + json.loads; same DB row
-> byte-identical block dict.
"""

import json
import sqlite3
from typing import Any

from .errors import CheckerError


def _load_metadata(db_path: str, control_id: str) -> dict[str, Any]:
    """Read + parse a control's metadata_json from the ragbase DB.

    Taxonomy:
      - name: _load_metadata
      - represents: the single sqlite read for one control's structured metadata.
      - input: absolute ragbase.sqlite path, a control.* id.
      - output: the parsed metadata_json dict (``{}`` when the column is empty).
      - must NOT be read as: reading body_md prose — only the structured
        metadata_json column is consulted.
      - complete when: the row is found and metadata_json parsed, or a typed
        CheckerError is raised (control missing / metadata not an object).
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json, confidence FROM ragbase_objects WHERE id = ?",
            (control_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise CheckerError(
            "CHK_CONTROL_NOT_FOUND",
            f"control {control_id!r} not found in ragbase",
            control_id=control_id,
        )
    raw = row["metadata_json"] or ""
    if not raw.strip():
        return {"__confidence__": row["confidence"]}
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CheckerError(
            "CHK_THRESHOLD_UNBOUND",
            f"control {control_id!r} metadata_json is not valid JSON: {exc}",
            control_id=control_id,
        ) from exc
    if not isinstance(meta, dict):
        raise CheckerError(
            "CHK_THRESHOLD_UNBOUND",
            f"control {control_id!r} metadata_json is not a JSON object",
            control_id=control_id,
        )
    meta["__confidence__"] = row["confidence"]
    return meta


def resolve_threshold_block(
    db_path: str,
    control_id: str,
    *,
    metric: str | None = None,
) -> dict[str, Any]:
    """Read the structured threshold_block a checker must gate on (DD-3).

    Args:
      db_path: absolute path to the repo's ragbase.sqlite.
      control_id: the ragbase control.* id whose threshold to resolve.
      metric: when the control carries several blocks (``threshold_blocks`` list),
        the ``metric`` selecting which one; ignored for a single ``threshold_block``.

    Returns:
      The threshold_block dict: at minimum ``{"metric", "value", "unit",
      "source_anchor"}``. Read at run time so knowledge updates flow through.

    Raises:
      CheckerError(CHK_CONTROL_NOT_FOUND): the control id is absent from ragbase.
      CheckerError(CHK_THRESHOLD_UNBOUND): the control carries no structured
        threshold_block (the resolver refuses to parse body_md prose).
      CheckerError(CHK_SOURCE_ANCHOR_MISSING): the block has no source_anchor.
    """
    meta = _load_metadata(db_path, control_id)

    block: dict[str, Any] | None = None
    if isinstance(meta.get("threshold_block"), dict):
        block = meta["threshold_block"]
    elif isinstance(meta.get("threshold_blocks"), list):
        blocks = [b for b in meta["threshold_blocks"] if isinstance(b, dict)]
        if metric is not None:
            block = next((b for b in blocks if b.get("metric") == metric), None)
        elif len(blocks) == 1:
            block = blocks[0]
        elif len(blocks) > 1:
            raise CheckerError(
                "CHK_THRESHOLD_UNBOUND",
                f"control {control_id!r} carries {len(blocks)} threshold blocks; "
                f"a metric selector is required",
                control_id=control_id,
            )

    if block is None or "value" not in block:
        raise CheckerError(
            "CHK_THRESHOLD_UNBOUND",
            f"control {control_id!r} has no structured threshold_block "
            f"(refusing to parse body_md prose — no-fabrication)",
            control_id=control_id,
        )
    if not block.get("source_anchor"):
        raise CheckerError(
            "CHK_SOURCE_ANCHOR_MISSING",
            f"threshold_block for control {control_id!r} has no source_anchor",
            control_id=control_id,
        )
    return dict(block)
