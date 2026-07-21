"""preflight — typed asset preflight + content assertion (R17.2.4 / R17.2.5).

Why this module exists
──────────────────────
mcp-integration-standard R17.2 §4/§5: a file-producing service MUST, before a
mutation/render/assemble, reject unresolved paths / missing media / paths outside
the token namespace / host-only absolute references (R17.2.4), and delivery-oriented
operations MUST evaluate machine-checkable content assertions so a transport-valid
but EMPTY artifact is never reported as delivery-ready (R17.2.5).

Design (plan mcp_r17-r06-conformance DD-4): two families of PURE functions — no I/O
side effects beyond stat/read of already-resolved paths — so the same logic drives
`run_tool` (real dispatch) AND the pytest suite (branch assertions) without standing
up a server. Every rejection is fail-fast + typed code + the missing-item list +
an R0.5 remedy dict (bodesign no-silent-fallback 天條; 天條 11 — no fabricated
affordance: a remedy is only ever added to a real defect).
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional


# ── R17.2.4 typed asset preflight ────────────────────────────────────────

# Failure reasons (single-source; tests + server branch on these strings).
REASON_UNRESOLVED = "unresolved"
REASON_OUT_OF_NAMESPACE = "out_of_namespace"
REASON_HOST_ONLY_ABSOLUTE = "host_only_absolute"
REASON_MISSING_MEDIA = "missing_media"

# Typed preflight error codes.
CODE_UNRESOLVED = "PREFLIGHT_UNRESOLVED"
CODE_OUT_OF_NAMESPACE = "PREFLIGHT_OUT_OF_NAMESPACE"
CODE_HOST_ONLY_ABSOLUTE = "PREFLIGHT_HOST_ONLY_ABSOLUTE"
CODE_MISSING_MEDIA = "PREFLIGHT_MISSING_MEDIA"

_REASON_TO_CODE = {
    REASON_UNRESOLVED: CODE_UNRESOLVED,
    REASON_OUT_OF_NAMESPACE: CODE_OUT_OF_NAMESPACE,
    REASON_HOST_ONLY_ABSOLUTE: CODE_HOST_ONLY_ABSOLUTE,
    REASON_MISSING_MEDIA: CODE_MISSING_MEDIA,
}

# Media extensions whose absence is classified missing_media (not merely unresolved),
# so a render call that references an image gets the sharper diagnosis.
_MEDIA_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".tif", ".tiff", ".webp"}


def _remedy(note: str) -> dict:
    """R0.5 remedy dict; projected to the portable content text by the server."""
    return {"note": note}


def _classify_one(doc_dir: Path, asset: str, *, in_token: bool) -> Optional[str]:
    """Return a failure reason for one declared asset path, or None if resolved.

    `in_token` marks a portable (token-carrying) call: an absolute host path is a
    hard `host_only_absolute` defect there. In the same-host token-less case the
    caller passes in_token=False, where an absolute host path is legitimate (the
    server still records the advisory reason but does not hard-block — DD-4 R1).
    """
    if asset is None or not str(asset).strip():
        return REASON_UNRESOLVED
    raw = str(asset)
    root = doc_dir.resolve()

    if Path(raw).is_absolute():
        # An absolute path is host-only unless it actually lives inside the token dir.
        try:
            Path(raw).resolve().relative_to(root)
        except ValueError:
            return REASON_HOST_ONLY_ABSOLUTE
        target = Path(raw).resolve()
    else:
        # Relative → must resolve inside the token namespace (traversal guard).
        target = (root / raw.lstrip("/")).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return REASON_OUT_OF_NAMESPACE

    if not target.exists():
        ext = target.suffix.lower()
        return REASON_MISSING_MEDIA if ext in _MEDIA_EXTS else REASON_UNRESOLVED
    return None


def preflight_assets(
    doc_dir, asset_paths: Iterable[str], *, in_token: bool = True
) -> dict:
    """Resolve every declared asset path against the token namespace (R17.2.4).

    Returns a verdict dict::

        {ok, resolved[], failures[{path,reason}], error?{code,message,failures,remedy}}

    ok is True iff every path resolved. On any failure the verdict carries a typed
    error (the FIRST failure's reason drives the code) + the full failing-item list
    + a single remedy line — never a silent continue.

    host_only_absolute in a token-less same-host call (in_token=False) is reported
    as a failure row for observability but does NOT flip ok to False (DD-4 R1):
    legitimate local UDS calls that pass a real host path keep working.
    """
    root = Path(doc_dir).resolve()
    resolved: list[str] = []
    failures: list[dict] = []
    for asset in asset_paths or []:
        reason = _classify_one(root, asset, in_token=in_token)
        if reason is None:
            resolved.append(str(asset))
        else:
            failures.append({"path": str(asset), "reason": reason})

    # host_only_absolute is only blocking in the portable (token) case.
    blocking = [
        f for f in failures
        if not (f["reason"] == REASON_HOST_ONLY_ABSOLUTE and not in_token)
    ]
    if not blocking:
        return {"ok": True, "resolved": resolved, "failures": failures}

    first = blocking[0]
    code = _REASON_TO_CODE[first["reason"]]
    missing = ", ".join(f["path"] for f in blocking)
    note = (
        f"asset preflight failed ({first['reason']}): {missing}. "
        "Stage the asset inside the token (bodesign_stage_dir) or pass a rel path "
        "inside the token namespace; do not reference host-only or out-of-namespace paths."
    )
    return {
        "ok": False,
        "resolved": resolved,
        "failures": failures,
        "error": {"code": code, "message": note, "failures": blocking,
                   "remedy": _remedy(note)},
    }


# ── R17.2.5 content assertion ────────────────────────────────────────────

CODE_ASSERTION_EMPTY = "ASSERTION_EMPTY"
CODE_ASSERTION_MISSING_FILE = "ASSERTION_MISSING_FILE"
CODE_ASSERTION_MISSING_MEDIA = "ASSERTION_MISSING_MEDIA"
CODE_ASSERTION_MISSING_TEXT = "ASSERTION_MISSING_TEXT"


def _produced_index(produced: Iterable) -> dict:
    """Normalise a produced list into {rel: {size, text?}}.

    Each entry may be a dict ({rel,size?,text?}) or a bare rel string. When size
    is absent we treat it as unknown (None) — an explicit size==0 is what triggers
    the empty verdict, so callers that cannot cheaply size a blob should omit it
    rather than guess.
    """
    idx: dict = {}
    for item in produced or []:
        if isinstance(item, dict):
            rel = item.get("rel")
            if rel is None:
                continue
            idx[str(rel)] = {"size": item.get("size"), "text": item.get("text")}
        else:
            idx[str(item)] = {"size": None, "text": None}
    return idx


def assert_content(produced: Iterable, assertions: Optional[dict]) -> dict:
    """Evaluate machine-checkable content assertions on produced artifacts (R17.2.5).

    `assertions` keys (all optional):
      - non_empty (bool): every produced artifact with a known size MUST be > 0 bytes.
      - expected_files (list[str]): each rel MUST be present in produced.
      - expected_media (list[str]): like expected_files, sharper code for media.
      - required_text (list[str]): each string MUST appear in some produced text.

    Returns::

        {delivery_ready, checked{...}, error?{code,message}}

    A transport-valid but EMPTY artifact is NOT delivery-ready — the core R17.2.5
    guarantee. When no assertions are requested the verdict is delivery_ready=True
    (assertions are opt-in; absence is not a defect).
    """
    assertions = assertions or {}
    idx = _produced_index(produced)
    checked: dict = {}

    # non_empty: any known-size-0 artifact fails.
    if assertions.get("non_empty"):
        empties = [rel for rel, meta in idx.items()
                   if meta["size"] is not None and meta["size"] <= 0]
        checked["non_empty"] = {"empties": empties, "pass": not empties}
        if empties:
            return {
                "delivery_ready": False,
                "checked": checked,
                "error": {"code": CODE_ASSERTION_EMPTY,
                          "message": f"transport-valid but EMPTY artifact(s): {', '.join(empties)} "
                                     "— an empty artifact is NOT delivery-ready (R17.2.5)"},
            }

    # expected_files / expected_media presence.
    for key, code in (("expected_files", CODE_ASSERTION_MISSING_FILE),
                      ("expected_media", CODE_ASSERTION_MISSING_MEDIA)):
        want = assertions.get(key)
        if want:
            missing = [rel for rel in want if rel not in idx]
            checked[key] = {"missing": missing, "pass": not missing}
            if missing:
                return {
                    "delivery_ready": False,
                    "checked": checked,
                    "error": {"code": code,
                              "message": f"expected artifact(s) not produced: {', '.join(missing)}"},
                }

    # required_text: each marker must appear in some produced text blob.
    want_text = assertions.get("required_text")
    if want_text:
        haystack = "\n".join(str(meta["text"]) for meta in idx.values()
                             if meta["text"] is not None)
        missing = [t for t in want_text if t not in haystack]
        checked["required_text"] = {"missing": missing, "pass": not missing}
        if missing:
            return {
                "delivery_ready": False,
                "checked": checked,
                "error": {"code": CODE_ASSERTION_MISSING_TEXT,
                          "message": f"required text not found in any produced artifact: {', '.join(missing)}"},
            }

    return {"delivery_ready": True, "checked": checked}
