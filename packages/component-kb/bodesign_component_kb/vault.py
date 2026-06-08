"""Local, MPN-keyed datasheet vault — the anti-hallucination spec store.

Why this exists: during RCA an agent is tempted to state an electrical spec from
memory (e.g. "W25Q128JV is 2.7-3.6V"). That is a *guess* until it is grounded in a
real datasheet. This vault makes the distinction explicit and persistent:

  * a spec is **verified** only when it carries a real source (a registered datasheet
    file, or a cited vendor/distributor page) recorded in this vault;
  * otherwise it is **unverified** (model memory) and callers must label it so.

Design constraints (from the user):
  * **Local folder management, keyed by manufacturer part number (MPN).** Each part is
    a directory ``<root>/<normalized-mpn>/`` holding the datasheet file (if acquired)
    plus ``meta.json`` (vendor, source URL, sha256, and per-field specs w/ provenance).
  * **Lazy loading.** Entries are created on demand when a bug/RCA needs a part's spec,
    NOT bulk-fetched from a BOM. ``lookup`` on a missing part returns ``absent`` with a
    handle to acquire it, rather than fabricating a value.

The vault is project-agnostic on purpose: a datasheet is identical across projects, so
one shared root (default ``$BODESIGN_DATASHEET_VAULT`` or ``<work>/.bodesign-datasheets``)
is reused everywhere. No network is required to register — a user-dropped PDF or a cited
URL both count; auto-extraction of fields is best-effort and always flagged as such.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any


def vault_root(work_dir: str | os.PathLike | None = None) -> Path:
    """Resolve the vault root: env override, else <work>/.bodesign-datasheets."""
    env = os.environ.get("BODESIGN_DATASHEET_VAULT")
    if env:
        return Path(env)
    base = Path(work_dir) if work_dir else Path(os.environ.get("BODESIGN_WORK_DIR", "/work"))
    return base / ".bodesign-datasheets"


def _norm(mpn: str) -> str:
    slug = "".join(c.lower() if c.isalnum() else "-" for c in (mpn or "")).strip("-")
    return slug or "unknown-part"


def _entry_dir(root: Path, mpn: str) -> Path:
    return Path(root) / _norm(mpn)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _norm_spec(field: str, value: Any) -> dict:
    """Normalize one spec into {value, unit?, source, confidence, method}.

    Accepts a bare scalar (-> unverified model memory) or a dict carrying provenance.
    A spec is only ``verified`` when it has a non-empty ``source``.
    """
    if isinstance(value, dict):
        src = (value.get("source") or "").strip()
        rec = {
            "value": value.get("value"),
            "source": src,
            "confidence": float(value.get("confidence", 0.9 if src else 0.3)),
            "method": value.get("method") or ("cited" if src else "unverified"),
        }
        if value.get("unit"):
            rec["unit"] = value["unit"]
        rec["verified"] = bool(src)
        return rec
    return {"value": value, "source": "", "confidence": 0.3,
            "method": "unverified", "verified": False}


def lookup(mpn: str, root: str | os.PathLike | None = None,
           work_dir: str | os.PathLike | None = None) -> dict | None:
    """Return the vault entry for ``mpn`` (resolving aliases), or None if absent."""
    r = Path(root) if root else vault_root(work_dir)
    d = _entry_dir(r, mpn)
    meta = d / "meta.json"
    if meta.is_file():
        return json.loads(meta.read_text(encoding="utf-8"))
    # alias scan: a part registered under another MPN may list this as an alias
    if r.is_dir():
        target = (mpn or "").strip().lower()
        for sub in r.iterdir():
            m = sub / "meta.json"
            if not m.is_file():
                continue
            data = json.loads(m.read_text(encoding="utf-8"))
            aliases = [a.lower() for a in data.get("aliases", [])] + [data.get("mpn", "").lower()]
            if target in aliases:
                return data
    return None


def register(mpn: str, *, vendor: str | None = None, source_url: str | None = None,
             pdf_path: str | None = None, specs: dict[str, Any] | None = None,
             aliases: list[str] | None = None, description: str | None = None,
             note: str | None = None, now: str | None = None,
             root: str | os.PathLike | None = None,
             work_dir: str | os.PathLike | None = None) -> dict:
    """Create/update a vault entry. Merges specs over any existing record.

    ``pdf_path`` (if given and readable) is copied into the entry as ``datasheet.pdf``
    and hashed. ``specs`` values may be bare scalars (recorded as *unverified*) or
    dicts ``{value, unit?, source, confidence?, method?}`` (recorded as *verified* when
    a source is present). Auto-extraction is not done here — provenance is explicit.
    """
    r = Path(root) if root else vault_root(work_dir)
    d = _entry_dir(r, mpn)
    d.mkdir(parents=True, exist_ok=True)
    meta_path = d / "meta.json"
    data: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}

    data["mpn"] = mpn
    data["normalized"] = _norm(mpn)
    if vendor:
        data["vendor"] = vendor
    if description:
        data["description"] = description
    if source_url:
        data.setdefault("sources", [])
        if source_url not in data["sources"]:
            data["sources"].append(source_url)
    if aliases:
        merged = set(data.get("aliases", [])) | set(aliases)
        data["aliases"] = sorted(merged)
    if note:
        data.setdefault("notes", []).append(note)

    warnings: list[str] = []
    if pdf_path:
        src = Path(pdf_path)
        if src.is_file():
            dest = d / "datasheet.pdf"
            shutil.copyfile(src, dest)
            data["datasheet_file"] = dest.name
            data["datasheet_sha256"] = _sha256(dest)
            data["acquired"] = True
        else:
            warnings.append(f"pdf_path not found, not copied: {pdf_path}")

    spec_store: dict[str, Any] = data.get("specs", {})
    for field, value in (specs or {}).items():
        spec_store[field] = _norm_spec(field, value)
    data["specs"] = spec_store
    if now:
        data["updated_at"] = now

    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "registered", "mpn": mpn, "path": str(d),
            "entry": data, "warnings": warnings}


def spec_check(mpn: str, field: str, claimed_value: Any = None,
               root: str | os.PathLike | None = None,
               work_dir: str | os.PathLike | None = None) -> dict:
    """The RCA guard. Is ``field`` for ``mpn`` backed by the vault?

    Returns status:
      * ``absent``       — the part isn't in the vault at all (acquire it first);
      * ``no-field``     — part exists but this spec was never recorded;
      * ``unverified``   — a value exists but has no source (model memory);
      * ``verified``     — a value exists with a real source.
    When ``claimed_value`` is given, also reports whether it matches the vault value.
    """
    entry = lookup(mpn, root=root, work_dir=work_dir)
    if entry is None:
        return {"status": "absent", "mpn": mpn, "field": field,
                "advice": "Not in datasheet vault. Acquire it (bodesign_datasheet_register "
                          "with a real datasheet/source) before asserting this spec; do not "
                          "state the value from memory as if confirmed."}
    rec = entry.get("specs", {}).get(field)
    if rec is None:
        return {"status": "no-field", "mpn": mpn, "field": field,
                "known_fields": sorted(entry.get("specs", {}).keys()),
                "advice": "Part is in the vault but this field is unrecorded; register it with a source."}
    out = {"status": "verified" if rec.get("verified") else "unverified",
           "mpn": mpn, "field": field, "value": rec.get("value"),
           "unit": rec.get("unit"), "source": rec.get("source"),
           "confidence": rec.get("confidence"), "method": rec.get("method")}
    if claimed_value is not None:
        out["claimed_value"] = claimed_value
        try:
            out["matches"] = float(claimed_value) == float(rec.get("value"))
        except (TypeError, ValueError):
            out["matches"] = str(claimed_value).strip().lower() == str(rec.get("value")).strip().lower()
    return out


def audit_claims(claims: list[dict], root: str | os.PathLike | None = None,
                 work_dir: str | os.PathLike | None = None) -> dict:
    """Gate the spec values an RCA is about to state, against the vault.

    Each claim: ``{mpn, field, asserted_value?, note?}`` where ``asserted_value`` is the
    spec value the agent intends to write (e.g. flash ``vcc_min_v`` = 2.7). A claim is
    **blocking** — i.e. must be resolved or explicitly labelled before the RCA ships — when
    its spec is ``absent`` (part not acquired), ``no-field``/``unverified`` (no datasheet
    source), or ``verified`` but the asserted value *contradicts* the datasheet (a
    hallucinated spec). Returns the per-claim verdicts, the blocking subset, and
    ``publishable`` = no blockers.

    This is the discipline gate: RCA conclusions ride on real specs, not guesses.
    """
    verdicts: list[dict] = []
    blocking: list[dict] = []
    for c in claims:
        asserted = c.get("asserted_value", c.get("claimed_value"))
        res = spec_check(c["mpn"], c["field"], claimed_value=asserted,
                         root=root, work_dir=work_dir)
        block_reason = None
        if res["status"] in ("absent", "no-field"):
            block_reason = res["status"]
        elif res["status"] == "unverified":
            block_reason = "unverified (no datasheet source)"
        elif res["status"] == "verified" and asserted is not None and res.get("matches") is False:
            block_reason = "contradicts datasheet (asserted {} vs vault {})".format(
                asserted, res.get("value"))
        v = {**res, "blocking": bool(block_reason)}
        if block_reason:
            v["block_reason"] = block_reason
            blocking.append(v)
        verdicts.append(v)
    return {"publishable": not blocking, "claim_count": len(claims),
            "blocking_count": len(blocking), "claims": verdicts, "blocking": blocking,
            "advice": ("All asserted specs are datasheet-grounded." if not blocking else
                       "Resolve blockers before publishing: acquire/cite the datasheet for "
                       "absent/unverified specs, or correct claims that contradict the vault.")}


def list_entries(root: str | os.PathLike | None = None,
                 work_dir: str | os.PathLike | None = None) -> list[dict]:
    """One-line summary per vault entry (for an overview / audit)."""
    r = Path(root) if root else vault_root(work_dir)
    if not r.is_dir():
        return []
    out = []
    for sub in sorted(r.iterdir()):
        m = sub / "meta.json"
        if not m.is_file():
            continue
        data = json.loads(m.read_text(encoding="utf-8"))
        specs = data.get("specs", {})
        out.append({
            "mpn": data.get("mpn"),
            "vendor": data.get("vendor"),
            "acquired": bool(data.get("acquired")),
            "spec_fields": sorted(specs.keys()),
            "verified_fields": sorted(k for k, v in specs.items() if v.get("verified")),
        })
    return out


# Best-effort, ALWAYS-flagged datasheet text scan. Proposes a VCC range for a human/agent
# to confirm; never writes it as verified on its own.
_VCC_RE = re.compile(
    r"(?:VCC|VDD|supply\s*voltage|operating\s*voltage)\D{0,40}?"
    r"(\d\.\d{1,2})\s*(?:V|volts)?\s*(?:to|[-~–—]|\.\.)\s*(\d\.\d{1,2})\s*V",
    re.IGNORECASE)


def propose_vcc_from_text(text: str) -> dict | None:
    """Scan datasheet text for a 'VCC a to b V' pattern. Returns a *proposed* (unverified)
    spec the caller must confirm against the real datasheet before marking verified."""
    m = _VCC_RE.search(text or "")
    if not m:
        return None
    lo, hi = float(m.group(1)), float(m.group(2))
    return {"vcc_min_v": lo, "vcc_max_v": hi,
            "method": "auto-extracted", "confidence": 0.5,
            "caveat": "Regex-scanned from datasheet text; confirm against the PDF before trusting."}
