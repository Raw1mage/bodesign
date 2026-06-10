"""Thin vault API layer (R9): request validation -> VaultRepository -> response mapping.

Shared by the MCP tools (bodesign_vault_*) and the HTTP endpoints
(POST /vault/ingest, GET /vault/components/{key}, /vault/search,
/vault/queue, /vault/spec-check) so both surfaces carry the SAME
contract: explicit absent (never empty-success), VAULT-Exxx error
codes, fail-fast storage errors (R10 — corrupt DB is VAULT-E001,
never recreated).

NO business logic lives here: validate -> repository call -> map.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from typing import Any, Iterator

from bodesign_component_kb.repository import VaultRepository, VaultRepositoryError
from bodesign_component_kb.storage import VaultError, open_vault
from bodesign_component_kb.vault import spec_check as _spec_check

# HTTP status mapping for VAULT-Exxx codes (errors.md):
#   storage fail-fast (E001/E002/E003) -> 503 (service cannot serve; operator action)
#   explicit absent (E901)             -> 404 (absent semantics, not an error state)
#   everything else                    -> 400 (caller input)
_STORAGE_CODES = ("VAULT-E001", "VAULT-E002", "VAULT-E003")


def http_status(code: str) -> int:
    if code in _STORAGE_CODES:
        return 503
    if code == "VAULT-E901":
        return 404
    return 400


def error_payload(error: VaultError) -> dict[str, Any]:
    return {"error_code": error.code, "message": error.message}


@contextmanager
def open_repository(vault_dir: str | None = None) -> Iterator[VaultRepository]:
    """Open the server vault (BODESIGN_VAULT_DIR env, else explicit dir).

    Storage errors propagate untranslated: VAULT-E001 (corrupt — never
    recreated), VAULT-E002 (unwritable/unconfigured), VAULT-E003 (version).
    """
    storage = open_vault(vault_dir)
    try:
        yield VaultRepository(storage)
    finally:
        storage.close()


# -- R9 ingest: L1 -> L4 pipeline (identity -> document dedup -> chunks -> specs) --

def vault_ingest(payload: dict[str, Any]) -> dict[str, Any]:
    """POST /vault/ingest | bodesign_vault_ingest.

    payload: {actor, component?{mpn,...}, mpns?[], document?{path,doc_type,
    provenance,...}, document_id?, chunks?[], specs?[], vault_dir?}.
    Returns a write summary + the explicit gap list per touched MPN.
    """
    actor = payload.get("actor")
    component_spec = payload.get("component") or None
    document_spec = payload.get("document") or None
    chunks = payload.get("chunks") or []
    specs = payload.get("specs") or []
    if not component_spec and not document_spec and not specs:
        raise VaultRepositoryError(
            "VAULT-E101", "Empty or invalid MPN: ingest payload must include component, document, or specs"
        )
    mpns: list[str] = list(payload.get("mpns") or [])
    if component_spec and component_spec.get("mpn") and component_spec["mpn"] not in mpns:
        mpns.insert(0, component_spec["mpn"])
    summary: dict[str, Any] = {"component": None, "document": None, "chunks": None, "specs_written": 0}
    with open_repository(payload.get("vault_dir")) as repo:
        if component_spec:
            summary["component"] = repo.upsert_component(
                component_spec.get("mpn", ""),
                manufacturer=component_spec.get("manufacturer"),
                category=component_spec.get("category"),
                description=component_spec.get("description"),
                actor=actor,
            )
        document_id = payload.get("document_id")
        if document_spec:
            ingest = repo.ingest_document(
                document_spec.get("path", ""),
                document_spec.get("doc_type", ""),
                document_spec.get("provenance"),
                mpns,
                revision=document_spec.get("revision"),
                revision_date=document_spec.get("revision_date"),
                provenance_detail=document_spec.get("provenance_detail"),
                actor=actor,
            )
            document_id = ingest.document_id
            summary["document"] = asdict(ingest)
        if chunks:
            if document_id is None:
                raise VaultRepositoryError(
                    "VAULT-E301", "Chunk references unknown document id None (ingest a document first)"
                )
            chunk_result = repo.ingest_chunks(int(document_id), chunks, actor=actor)
            summary["chunks"] = asdict(chunk_result)
        for spec in specs:
            spec_mpn = spec.get("mpn") or (mpns[0] if mpns else "")
            repo.write_spec(
                spec_mpn,
                spec.get("field_path", ""),
                value_num=spec.get("value_num"),
                value_text=spec.get("value_text"),
                unit=spec.get("unit"),
                condition=spec.get("condition"),
                min_val=spec.get("min_val"),
                typ_val=spec.get("typ_val"),
                max_val=spec.get("max_val"),
                evidence_chunk_id=spec.get("evidence_chunk_id"),
                source_note=spec.get("source_note"),
                confidence=spec.get("confidence", "unverified"),
                actor=actor,
            )
            summary["specs_written"] += 1
            if spec_mpn not in mpns:
                mpns.append(spec_mpn)
        gaps = {mpn: repo.component_completeness(mpn) for mpn in mpns}
    return {"status": "ok", "summary": summary, "gaps": gaps}


# -- R9 query: by MPN / full text / queue — always explicit absent ------------

def vault_component(key: str, vault_dir: str | None = None) -> dict[str, Any]:
    """GET /vault/components/{key}: canonical record + completeness + documents."""
    with open_repository(vault_dir) as repo:
        resolved = repo.resolve(key)
        if resolved.status == "absent":
            return {"status": "absent", "query": key,
                    "advice": "Component not in the server vault; ingest it via /vault/ingest."}
        return {
            "status": "found",
            "canonical_key": resolved.canonical_key,
            "component": resolved.component,
            "hit_alias_type": resolved.hit_alias_type,
            "completeness": repo.component_completeness(key),
            "documents": repo.list_documents(key),
        }


def vault_search(query: str, limit: int = 20, include_stale: bool = False,
                 vault_dir: str | None = None) -> dict[str, Any]:
    """GET /vault/search: FTS5 BM25 hits with MPN/document/page anchors. No-hit -> []."""
    with open_repository(vault_dir) as repo:
        hits = repo.search_chunks(query, limit=limit, include_stale=include_stale)
    return {"status": "ok", "query": query, "hits": [asdict(hit) for hit in hits]}


def vault_queue(limit: int = 80, vault_dir: str | None = None) -> dict[str, Any]:
    """GET /vault/queue: DD-9 priority-ranked knowledge queue."""
    with open_repository(vault_dir) as repo:
        return {"status": "ok", "queue": repo.knowledge_queue(limit=limit)}


def vault_query(payload: dict[str, Any]) -> dict[str, Any]:
    """bodesign_vault_query: {mpn} -> component view; {query} -> full-text search."""
    mpn = (payload.get("mpn") or "").strip()
    query = (payload.get("query") or "").strip()
    if mpn:
        return vault_component(mpn, vault_dir=payload.get("vault_dir"))
    if query:
        return vault_search(query, limit=int(payload.get("limit", 20)),
                            include_stale=bool(payload.get("include_stale", False)),
                            vault_dir=payload.get("vault_dir"))
    raise VaultRepositoryError("VAULT-E101", "Empty or invalid MPN: vault_query requires 'mpn' or 'query'")


def vault_spec_check(mpn: str, field: str, claimed_value: Any = None,
                     vault_root: str | None = None, vault_dir: str | None = None) -> dict[str, Any]:
    """GET /vault/spec-check | bodesign_vault_spec_check.

    Server vault consulted FIRST (origin='server-vault'); the optional
    client cache (vault_root) is the fallback (origin='client-cache').
    Four-state semantics (verified/unverified/no-field/absent) hold.
    """
    with open_repository(vault_dir) as repo:
        return _spec_check(mpn, field, claimed_value=claimed_value, root=vault_root, repository=repo)
