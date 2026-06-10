"""RCA spec gate over the `datasheets` skill's per-project extraction cache.

Why this exists: during RCA an agent is tempted to state an electrical spec from memory
(e.g. "W25Q128JV is 2.7-3.6V"). That is a *guess* until it is grounded in a real
datasheet. This module makes the distinction explicit — but it does **not** own a parallel
datasheet store. The canonical owner is the **`datasheets` skill**, whose convention is:

    <project>/datasheets/
      <MPN>.pdf                       # downloaded by distributor skills (digikey/mouser/…)
      extracted/
        manifest.json                 # cache index
        <MPN>_<hash>.json             # structured extraction (the datasheets skill's output)

So bodesign is a **reader/gate** here: ``lookup`` resolves an MPN's cached extraction via
that manifest; ``spec_check``/``audit_claims`` report whether a spec value an RCA asserts is
**grounded** (present in a cached extraction that carries a real source — a ``source_pdf`` or
a cited ``source_note``) or **absent/unverified** (acquire+extract the datasheet first; do
not assert from memory). Capturing a NEW datasheet is the `datasheets` skill's job
(extract from ``<project>/datasheets/<MPN>.pdf``), not bodesign's.

``vault_root`` points at the project's ``datasheets/`` dir — in the bodesign C00–C07 tree
that is a C03 consumed-input: ``<track>/c03-ee/01_refs/datasheets``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# A spec is "grounded enough to assert" when its extraction carries a real source.
# We key off source presence + field presence, NOT the skill's completeness score
# (which measures how *complete* the extraction is, a different axis from per-field trust).


def vault_root(work_dir: str | os.PathLike | None = None) -> Path:
    """Resolve the project datasheets dir (the `datasheets` skill's per-project root).

    Precedence: ``$BODESIGN_DATASHEET_VAULT`` env; else ``<work_dir>/datasheets``; else
    ``<cwd>/datasheets``. In the bodesign stage tree, pass ``vault_root`` =
    ``<track>/c03-ee/01_refs/datasheets`` (datasheets are a C03 consumed input).
    """
    env = os.environ.get("BODESIGN_DATASHEET_VAULT")
    if env:
        return Path(env)
    base = Path(work_dir) if work_dir else Path.cwd()
    return base / "datasheets"


def _extract_dir(root: Path) -> Path:
    return Path(root) / "extracted"


def _load_manifest(extract_dir: Path) -> dict:
    for name in ("manifest.json", "index.json"):  # new name preferred, legacy fallback
        p = extract_dir / name
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
    return {}


def lookup(mpn: str, root: str | os.PathLike | None = None,
           work_dir: str | os.PathLike | None = None) -> dict | None:
    """Return the cached extraction dict for ``mpn`` (via the skill's manifest), or None.

    Resolution: match the manifest entry whose ``mpn`` equals (case-insensitively) the
    query and read its ``file``; fall back to scanning ``extracted/*.json`` by ``mpn``.
    """
    r = Path(root) if root else vault_root(work_dir)
    ed = _extract_dir(r)
    if not ed.is_dir():
        return None
    target = (mpn or "").strip().lower()
    manifest = _load_manifest(ed)
    for entry in manifest.get("extractions", {}).values():
        if str(entry.get("mpn", "")).strip().lower() == target:
            f = ed / entry.get("file", "")
            if f.is_file():
                try:
                    return json.loads(f.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    return None
    # fallback: scan extraction files directly
    for f in ed.glob("*.json"):
        if f.name in ("manifest.json", "index.json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if str(data.get("mpn", "")).strip().lower() == target:
            return data
    return None


# Friendly spec name -> dotted path into the skill's extraction schema. Callers may also
# pass a raw dotted path (e.g. "electrical_characteristics.vref_v") directly.
FIELD_ALIASES: dict[str, str] = {
    "vcc_min_v": "recommended_operating_conditions.vin_min_v",
    "vcc_max_v": "recommended_operating_conditions.vin_max_v",
    "vin_min_v": "recommended_operating_conditions.vin_min_v",
    "vin_max_v": "recommended_operating_conditions.vin_max_v",
    "vout_min_v": "recommended_operating_conditions.vout_min_v",
    "vout_max_v": "recommended_operating_conditions.vout_max_v",
    "vout_v": "electrical_characteristics.vref_v",
    "vref_v": "electrical_characteristics.vref_v",
    "dropout_mv": "electrical_characteristics.dropout_mv",
    "iout_max_ma": "electrical_characteristics.output_current_max_ma",
    "output_current_max_ma": "electrical_characteristics.output_current_max_ma",
}


def _resolve_path(field: str) -> str:
    return FIELD_ALIASES.get(field, field)


def _get_path(d: dict, dotted: str) -> Any:
    cur: Any = d
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _source_of(extraction: dict) -> str:
    meta = extraction.get("extraction_metadata", {}) or {}
    return (meta.get("source_pdf") or meta.get("source_note") or "").strip()


def _match_claim(out: dict, claimed_value: Any, value: Any) -> None:
    out["claimed_value"] = claimed_value
    try:
        out["matches"] = float(claimed_value) == float(value)
    except (TypeError, ValueError):
        out["matches"] = str(claimed_value).strip().lower() == str(value).strip().lower()


def _server_spec_check(repository: Any, mpn: str, field: str, claimed_value: Any) -> dict | None:
    """Check the server vault (Phase 3, R7). Returns a verdict dict for
    found rows (origin=server-vault), a no-field/absent marker dict, or
    None when the field is outside the vault registry (client cache may
    still know it — fall through, never block on registry coverage)."""
    try:
        server = repository.read_spec(mpn, field)
    except Exception as error:  # VAULT-E401 unknown registry path — client cache may still resolve it
        if getattr(error, "code", None) == "VAULT-E401":
            return None
        raise
    if server["status"] != "found":
        return {"status": server["status"], "mpn": mpn, "field": field,
                "resolved_path": server["resolved_path"], "origin": "server-vault"}
    row = server["values"][0]  # verified rows ordered first
    value = row["value_num"] if row["value_num"] is not None else row["value_text"]
    source = (f"chunk:{row['evidence_chunk_id']}" if row["evidence_chunk_id"] is not None
              else (row["source_note"] or ""))
    out = {"status": "verified" if row["confidence"] == "verified" else "unverified",
           "mpn": mpn, "field": field, "resolved_path": server["resolved_path"],
           "value": value, "unit": row["unit"], "condition": row["condition"],
           "source": source, "origin": "server-vault"}
    if claimed_value is not None:
        _match_claim(out, claimed_value, value)
    return out


def spec_check(mpn: str, field: str, claimed_value: Any = None,
               root: str | os.PathLike | None = None,
               work_dir: str | os.PathLike | None = None,
               repository: Any = None) -> dict:
    """The RCA guard. Is ``field`` for ``mpn`` grounded in a real datasheet source?

    Status:
      * ``absent``     — no cached extraction (acquire the PDF + run the datasheets skill);
      * ``no-field``   — extraction exists but this spec is unrecorded/null;
      * ``unverified`` — value present but the extraction carries no source (untrustworthy);
      * ``verified``   — value present and the extraction cites a real source (PDF or note).
    ``field`` accepts a friendly alias (vcc_min_v, vout_v, dropout_mv, iout_max_ma, …) or a
    raw dotted schema path. With ``claimed_value`` it also reports match/mismatch.

    Verification sources (R7): when ``repository`` (a server-vault
    VaultRepository) is given it is consulted FIRST; hits carry
    ``origin='server-vault'``. The client cache path is unchanged and its
    verdicts carry ``origin='client-cache'``. Four-state semantics hold
    for both origins.
    """
    server_marker: dict | None = None
    if repository is not None:
        server = _server_spec_check(repository, mpn, field, claimed_value)
        if server is not None:
            if server["status"] in ("verified", "unverified"):
                return server
            server_marker = server
    extraction = lookup(mpn, root=root, work_dir=work_dir)
    if extraction is None:
        if server_marker is not None and server_marker["status"] == "no-field":
            server_marker["advice"] = ("Part is in the server vault but this field is unrecorded; "
                                       "extend the vault with an evidence-backed spec write.")
            return server_marker
        return {"status": "absent", "mpn": mpn, "field": field, "origin": "client-cache",
                "advice": "No cached datasheet extraction. Acquire the datasheet PDF into "
                          "<project>/datasheets/ and run the `datasheets` skill before asserting "
                          "this spec; do not state the value from memory as if confirmed."}
    path = _resolve_path(field)
    value = _get_path(extraction, path)
    source = _source_of(extraction)
    if value is None:
        return {"status": "no-field", "mpn": mpn, "field": field, "resolved_path": path,
                "origin": "client-cache",
                "advice": "Part is extracted but this field is null; extend the extraction with a source."}
    out = {"status": "verified" if source else "unverified",
           "mpn": mpn, "field": field, "resolved_path": path, "value": value,
           "source": source, "category": extraction.get("category"), "origin": "client-cache"}
    if claimed_value is not None:
        _match_claim(out, claimed_value, value)
    return out


def audit_claims(claims: list[dict], root: str | os.PathLike | None = None,
                 work_dir: str | os.PathLike | None = None) -> dict:
    """Gate the spec values an RCA is about to state, against the datasheet cache.

    Each claim: ``{mpn, field, asserted_value?}``. Blocking when ``absent``/``no-field``/
    ``unverified`` or ``verified`` but the asserted value contradicts the datasheet. Returns
    per-claim verdicts, the blocking subset, and ``publishable`` = no blockers.
    """
    verdicts: list[dict] = []
    blocking: list[dict] = []
    for c in claims:
        asserted = c.get("asserted_value", c.get("claimed_value"))
        res = spec_check(c["mpn"], c["field"], claimed_value=asserted, root=root, work_dir=work_dir)
        block_reason = None
        if res["status"] in ("absent", "no-field"):
            block_reason = res["status"]
        elif res["status"] == "unverified":
            block_reason = "unverified (extraction has no source)"
        elif res["status"] == "verified" and asserted is not None and res.get("matches") is False:
            block_reason = "contradicts datasheet (asserted {} vs cached {})".format(asserted, res.get("value"))
        v = {**res, "blocking": bool(block_reason)}
        if block_reason:
            v["block_reason"] = block_reason
            blocking.append(v)
        verdicts.append(v)
    return {"publishable": not blocking, "claim_count": len(claims),
            "blocking_count": len(blocking), "claims": verdicts, "blocking": blocking,
            "advice": ("All asserted specs are datasheet-grounded." if not blocking else
                       "Resolve blockers before publishing: acquire/extract the datasheet for "
                       "absent/unverified specs, or correct claims that contradict the cache.")}


def list_entries(root: str | os.PathLike | None = None,
                 work_dir: str | os.PathLike | None = None) -> list[dict]:
    """One-line summary per cached extraction (from the skill's manifest)."""
    r = Path(root) if root else vault_root(work_dir)
    ed = _extract_dir(r)
    manifest = _load_manifest(ed)
    out = []
    for entry in manifest.get("extractions", {}).values():
        out.append({
            "mpn": entry.get("mpn"),
            "category": entry.get("category"),
            "source_pdf": entry.get("source_pdf") or None,
            "extraction_score": entry.get("extraction_score"),
        })
    return sorted(out, key=lambda e: str(e.get("mpn")))
