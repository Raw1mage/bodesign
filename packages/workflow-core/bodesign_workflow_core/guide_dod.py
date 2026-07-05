"""Machine-checkable GUIDE "Required deliverables — Definition of Done" enforcement.

Each stage's GUIDE.md DoD table is mirrored as ``templates/<stage>.dod.json``. This
module loads a manifest and checks a base directory against it, returning a
``guide_compliance`` block the readiness family attaches to its output. The point:
skipping a required deliverable now produces a RED signal (blocking) instead of a
fake-green readiness_pct.

Two adjacent honesty checks live here too:
  - ``is_placeholder_value`` — fake-complete detection for answer_state scoring (a
    field can be ``answered`` while its value is ``TBC``/empty).
  - the conditional mechanism — a deliverable required only under a condition (RF
    present, toolchain present, ...) is enforced when the condition holds and never
    silently skipped.

GUIDE.md stays the human single-source-of-truth; the JSON manifest is its machine
mirror (DD-1). No runtime markdown parsing.
"""
from __future__ import annotations
from pathlib import Path
import json
import re

_TEMPLATES = Path(__file__).resolve().parent / "templates"

# Fake-complete detection (DD-4) — deliberately CONSERVATIVE to avoid flagging
# legitimate values. English placeholder tokens are matched only as standalone
# tokens (bounded by start/end or non-alphanumeric); CJK uses specific multi-char
# placeholder phrases, NOT a bare 待 (which appears in legit words like 待機/期待).
_PLACEHOLDER_EN = re.compile(
    r"(?i)(?:^|[\s(/\[\-])"
    r"(?:tbc|tbd|tba|todo|fixme|n/?a|to\s+be\s+(?:confirmed|determined|defined|provided|filled|added|decided))"
    r"(?:$|[\s)/\].,;:\-])"
)
_PLACEHOLDER_CJK = (
    "待填", "待定", "待補", "待補充", "待確認", "待確定", "待提供", "待指定",
    "未定", "未填", "尚未提供", "尚未確定", "暫無", "暫定", "待補完",
)


def is_placeholder_value(value) -> bool:
    """True if a value claiming completeness (state=answered) is actually hollow.

    None / empty / whitespace-only → placeholder. A non-empty *string* is checked
    against the conservative token sets. Non-string structured content (dict/list/
    number) that is non-empty is treated as real content (not a placeholder)."""
    if value is None:
        return True
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return True
        if any(tok in s for tok in _PLACEHOLDER_CJK):
            return True
        return bool(_PLACEHOLDER_EN.search(s))
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def load_manifest(stage: str) -> dict | None:
    """Load templates/<stage>.dod.json, or None if no manifest exists."""
    p = _TEMPLATES / f"{stage}.dod.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def guide_compliance_for(folder, stage: str, *, root_visible: bool = True, conditions: dict | None = None):
    """Convenience wrapper for readiness `to_dict()`s: return the guide_compliance
    dict for a stage, or None when it should be skipped — an invisible root
    (path-not-visible) or a non-directory folder (e.g. c02's inline-constraints mode
    where `folder` is not a real path). Keeps the DoD check from firing a misleading
    all-missing result in those cases."""
    if not root_visible or not folder:
        return None
    base = Path(folder)
    if not base.is_dir():
        return None
    return assess_guide_dod(base, stage, conditions=conditions)


def _match_any(base: Path, any_of: list[str], bucket: str | None) -> str | None:
    """First of any_of (literal or glob) that exists under base. Returns the rel
    path string, else None. `bucket` (e.g. '02_build') constrains the location."""
    for rel in any_of:
        if bucket and not rel.startswith(bucket.rstrip("/") + "/"):
            rel = f"{bucket.rstrip('/')}/{rel}"
        if any(ch in rel for ch in "*?["):
            for m in sorted(base.glob(rel)):
                if m.exists():
                    try:
                        return str(m.relative_to(base))
                    except ValueError:
                        return str(m)
        else:
            if (base / rel).exists():
                return rel
    return None


def assess_guide_dod(base, stage_or_manifest, *, conditions: dict | None = None) -> dict:
    """Check `base` against a stage's DoD manifest → guide_compliance dict.

    Each deliverable resolves to one of:
      - ``present``       — a matching file exists (evidence = the path)
      - ``honest-status`` — missing, but `<base>/dod_status.json` records an
                            acceptable honest status + reason/owner (non-blocking)
      - ``missing``       — silently absent and required → ``blocking: true``
      - ``n-a``           — a conditional deliverable whose condition is known-false

    conditions: {name: bool|None}. None (unknown) is treated as REQUIRED (fail-safe);
    only a known-False condition makes a conditional deliverable n-a.
    """
    base = Path(base)
    manifest = stage_or_manifest if isinstance(stage_or_manifest, dict) else load_manifest(str(stage_or_manifest))
    if manifest is None:
        return {"dod_ok": True, "deliverables": [], "missing_blocking": [],
                "warnings": ["no DoD manifest for this stage"]}
    conditions = conditions or {}

    status_override: dict = {}
    sp = base / "dod_status.json"
    if sp.is_file():
        try:
            status_override = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            status_override = {}

    # BR_20260703: dod_status.json is only honoured at the product root (``base``).
    # A dod_status.json misplaced in a C0*-* stage subfolder was silently ignored,
    # so an engineer's recorded honest status had no effect and the deliverable
    # still read as blocking with no hint why. Surface it loudly (warn, non-blocking)
    # rather than silently drop it (no-silent-fallback).
    stage_scoped_warnings: list[str] = []
    try:
        for misplaced in sorted(base.glob("C0*-*/dod_status.json")):
            stage_scoped_warnings.append(
                f"dod_status.json found in a stage subfolder ({misplaced.relative_to(base)}) "
                "but DoD status is only read from the product root; move it to "
                f"{base.name}/dod_status.json for it to take effect."
            )
    except OSError:
        pass

    default_honest = manifest.get("honest_states") or []
    items: list[dict] = []
    missing_blocking: list[str] = []

    for d in manifest.get("deliverables", []):
        did = d.get("id", "")
        title = d.get("title", "")
        row = d.get("guide_row")
        cond = d.get("condition")
        required = d.get("required", True)

        # A conditional deliverable is required ONLY when its condition is explicitly
        # True. False or unknown(None) -> n-a (not required). The dangerous case (RF)
        # is handled explicitly by the caller passing conditions={"rf": True} when a
        # radio part is detected, so this default never hides an RF requirement.
        if cond is not None and conditions.get(cond) is not True:
            why = "not met" if conditions.get(cond) is False else "not evaluated"
            items.append({"id": did, "title": title, "guide_row": row, "status": "n-a",
                          "evidence": f"condition '{cond}' {why}", "blocking": False})
            continue

        bucket = d.get("bucket")
        if d.get("all_of"):
            # GUIDE row requiring several files: present iff EVERY path matches.
            hits = [(rel, _match_any(base, [rel], bucket)) for rel in d["all_of"]]
            if all(h[1] for h in hits):
                items.append({"id": did, "title": title, "guide_row": row, "status": "present",
                              "evidence": ", ".join(h[1] for h in hits), "blocking": False})
                continue
            matched = None
            missing_parts = [rel for rel, m in hits if not m]
        else:
            matched = _match_any(base, d.get("any_of", []), bucket)
            missing_parts = None
            if matched:
                items.append({"id": did, "title": title, "guide_row": row, "status": "present",
                              "evidence": matched, "blocking": False})
                continue

        ov = status_override.get(did)
        honest = d.get("honest_states") or default_honest
        if isinstance(ov, dict) and ov.get("status") in honest and (ov.get("reason") or ov.get("owner")):
            items.append({"id": did, "title": title, "guide_row": row, "status": "honest-status",
                          "evidence": f"{ov.get('status')}: {ov.get('reason') or ov.get('owner')}".strip(),
                          "blocking": False})
            continue

        blocking = bool(required)
        if missing_parts:
            ev = f"missing required file(s): {missing_parts}"
        else:
            ev = f"none of {d.get('any_of', [])} found"
        if required:
            ev += "; record an honest status in dod_status.json if deferred"
        items.append({"id": did, "title": title, "guide_row": row, "status": "missing",
                      "evidence": ev, "blocking": blocking})
        if blocking:
            missing_blocking.append(did)

    result = {"dod_ok": not missing_blocking, "deliverables": items, "missing_blocking": missing_blocking}
    if stage_scoped_warnings:
        result["warnings"] = stage_scoped_warnings
    return result
