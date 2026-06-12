"""Component Vault repository (Phase 1: identity + documents + audit).

Every write goes through a single audited transaction helper that
REQUIRES an actor (VAULT-E702 when missing) and appends audit_log rows.
Canonical key normalization is delegated to contracts.component_knowledge_key()
— never reimplemented here (handoff red line).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contracts import component_knowledge_key
from .storage import VaultError, VaultStorage, write_blob
from .vault import FIELD_ALIASES

_VALID_PROVENANCE = ("user-provided", "distributor-api", "docxmcp-chunk", "client-cache-import")
_VALID_DOC_TYPES = ("datasheet", "app-note", "reference-design", "errata", "package-drawing", "other")
_VALID_ALIAS_TYPES = ("family-variant", "manufacturer-alias", "distributor", "legacy-pn")
_VALID_CHUNK_KINDS = ("text", "table", "figure-caption", "section-heading")
_EMPTY_KEY = component_knowledge_key("")

# L4 field_path registry (data-schema.json field_path_namespace.roots).
# DB stores canonical dotted paths only; friendly aliases resolve here
# (API layer), never in SQL.
FIELD_PATH_ROOTS = (
    "absolute_maximum_ratings",
    "recommended_operating_conditions",
    "electrical_characteristics",
    "thermal_characteristics",
    "timing_characteristics",
    "power_topology",
    # spice_model.* (knowledge/datasheet-spice-models, DD-3) — closed v1 list.
    # Derived L4 namespace for datasheet-grounded SPICE model parameters.
    "spice_model.diode",
    "spice_model.ldo",
    "spice_model.passive",
)

# Closed v1 field registry per spice_model category (DD-3). Used by spice_card
# ingest (SPX_FIELD_UNKNOWN) and model-card generation (SPX_PARAMS_MISSING).
# required flag mirrors data-schema.json field_path_namespace.roots.
SPICE_MODEL_FIELDS: dict[str, dict[str, dict[str, object]]] = {
    "diode": {
        "is_a": {"required": True, "unit": "A"},
        "n": {"required": True, "unit": "1"},
        "rs_ohm": {"required": False, "unit": "ohm"},
        "cj0_f": {"required": False, "unit": "F"},
        "bv_v": {"required": False, "unit": "V"},
        "ibv_a": {"required": False, "unit": "A"},
    },
    "ldo": {
        "vout_v": {"required": True, "unit": "V"},
        "dropout_v": {"required": True, "unit": "V"},
        "iout_max_a": {"required": True, "unit": "A"},
        "iq_a": {"required": False, "unit": "A"},
        "psrr_db": {"required": False, "unit": "dB"},
    },
    "passive": {
        # required is conditional on passive sub-category (resistor/capacitor/
        # inductor); enforced at card-generation, not ingest.
        "c_f": {"required": False, "unit": "F"},
        "l_h": {"required": False, "unit": "H"},
        "r_ohm": {"required": False, "unit": "ohm"},
        "esr_ohm": {"required": False, "unit": "ohm"},
        "esl_h": {"required": False, "unit": "H"},
    },
}


def resolve_field_path(field: str) -> str:
    """Resolve a friendly alias or dotted path to a canonical field_path.

    Unknown paths raise VAULT-E401 with nearby registry candidates —
    never an empty result (design.md risk table).
    """
    field = (field or "").strip()
    resolved = FIELD_ALIASES.get(field, field)
    # Longest-prefix root match: roots may be single-segment
    # ("electrical_characteristics") or multi-segment ("spice_model.diode").
    # A valid path is "<root>.<leaf...>" with a non-empty leaf.
    for root in sorted(FIELD_PATH_ROOTS, key=len, reverse=True):
        if resolved == root:
            break  # root with no leaf is invalid -> fall through to error
        if resolved.startswith(root + ".") and len(resolved) > len(root) + 1:
            return resolved
    candidates = sorted(set(list(FIELD_ALIASES)[:6]) | set(FIELD_PATH_ROOTS))
    raise VaultRepositoryError(
        "VAULT-E401",
        f"Unknown field_path: {field!r} (not in registry); nearby candidates: {', '.join(candidates)}",
    )


class VaultRepositoryError(VaultError):
    """Repository-layer errors (identity/documents/audit VAULT-Exxx)."""


@dataclass(slots=True)
class ResolveResult:
    status: str
    canonical_key: str | None = None
    component: dict[str, Any] | None = None
    hit_alias_type: str | None = None


@dataclass(slots=True)
class IngestResult:
    document_id: int
    sha256: str
    dedup_hit: bool
    links_added: int
    blob_path: str


@dataclass(slots=True)
class ChunkIngestResult:
    document_id: int
    chunks_added: int
    stale_marked: int


@dataclass(slots=True)
class ChunkSearchHit:
    chunk_id: int
    document_id: int
    filename: str
    page_number: int
    anchor: str
    chunk_kind: str
    extractor: str
    content: str
    mpns: list[str]
    bm25: float


@dataclass(slots=True)
class VaultRepository:
    storage: VaultStorage
    _audit_pending: list[tuple[str, str, int, str | None, str | None, str | None, str | None]] = field(
        default_factory=list, repr=False
    )

    @property
    def conn(self) -> sqlite3.Connection:
        return self.storage.conn

    # -- audited transaction helper -------------------------------------

    def _require_actor(self, actor: str | None) -> str:
        if not actor or not str(actor).strip():
            raise VaultRepositoryError("VAULT-E702", "Write attempted without audit context (actor missing)")
        return str(actor).strip()

    def _audit(
        self,
        action: str,
        table_name: str,
        row_id: int,
        field_name: str | None = None,
        old_value: str | None = None,
        new_value: str | None = None,
        evidence_ref: str | None = None,
    ) -> None:
        self._audit_pending.append((action, table_name, row_id, field_name, old_value, new_value, evidence_ref))

    class _Transaction:
        def __init__(self, repository: "VaultRepository", actor: str) -> None:
            self.repository = repository
            self.actor = actor

        def __enter__(self) -> "VaultRepository._Transaction":
            self.repository._audit_pending.clear()
            self.repository.conn.execute("BEGIN IMMEDIATE")
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            conn = self.repository.conn
            if exc_type is not None:
                conn.execute("ROLLBACK")
                self.repository._audit_pending.clear()
                return
            for action, table_name, row_id, field_name, old_value, new_value, evidence_ref in self.repository._audit_pending:
                conn.execute(
                    "INSERT INTO audit_log (actor, action, table_name, row_id, field, old_value, new_value, evidence_ref)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (self.actor, action, table_name, row_id, field_name, old_value, new_value, evidence_ref),
                )
            self.repository._audit_pending.clear()
            conn.execute("COMMIT")

    def _transaction(self, actor: str | None) -> "VaultRepository._Transaction":
        return VaultRepository._Transaction(self, self._require_actor(actor))

    # -- L1: identity ----------------------------------------------------

    def upsert_component(
        self,
        mpn: str,
        manufacturer: str | None = None,
        category: str | None = None,
        description: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        mpn = (mpn or "").strip()
        canonical_key = component_knowledge_key(mpn)
        if not mpn or canonical_key == _EMPTY_KEY:
            raise VaultRepositoryError("VAULT-E101", f"Empty or invalid MPN: {mpn!r}")
        with self._transaction(actor):
            manufacturer_id = self._upsert_manufacturer(manufacturer) if manufacturer else None
            existing = self.conn.execute(
                "SELECT * FROM components WHERE canonical_key = ?", (canonical_key,)
            ).fetchone()
            if existing is None:
                cursor = self.conn.execute(
                    "INSERT INTO components (canonical_key, mpn, manufacturer_id, category, description)"
                    " VALUES (?,?,?,?,?)",
                    (canonical_key, mpn, manufacturer_id, category, description),
                )
                row_id = int(cursor.lastrowid)
                self._audit("insert", "components", row_id, "canonical_key", None, canonical_key)
            else:
                row_id = int(existing["id"])
                updates: list[tuple[str, Any, Any]] = []
                if manufacturer_id is not None and existing["manufacturer_id"] != manufacturer_id:
                    updates.append(("manufacturer_id", existing["manufacturer_id"], manufacturer_id))
                if category is not None and existing["category"] != category:
                    updates.append(("category", existing["category"], category))
                if description is not None and existing["description"] != description:
                    updates.append(("description", existing["description"], description))
                set_clauses = [f"{column} = ?" for column, _, _ in updates]
                set_clauses.append("updated_at = datetime('now')")
                self.conn.execute(
                    f"UPDATE components SET {', '.join(set_clauses)} WHERE id = ?",
                    tuple(new for _, _, new in updates) + (row_id,),
                )
                for column, old, new in updates:
                    self._audit("update", "components", row_id, column, _text(old), _text(new))
                if not updates:
                    self._audit("update", "components", row_id, "updated_at", None, None)
        return dict(self.conn.execute("SELECT * FROM components WHERE id = ?", (row_id,)).fetchone())

    def _upsert_manufacturer(self, name: str) -> int:
        row = self.conn.execute("SELECT id FROM manufacturers WHERE name = ?", (name,)).fetchone()
        if row is not None:
            return int(row["id"])
        cursor = self.conn.execute("INSERT INTO manufacturers (name) VALUES (?)", (name,))
        manufacturer_id = int(cursor.lastrowid)
        self._audit("insert", "manufacturers", manufacturer_id, "name", None, name)
        return manufacturer_id

    def add_alias(
        self,
        mpn: str,
        alias: str,
        alias_type: str,
        distributor: str | None = None,
        note: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        if alias_type not in _VALID_ALIAS_TYPES:
            raise VaultRepositoryError("VAULT-E101", f"Invalid alias_type: {alias_type!r}")
        alias = (alias or "").strip()
        alias_key = component_knowledge_key(alias)
        if not alias or alias_key == _EMPTY_KEY:
            raise VaultRepositoryError("VAULT-E101", f"Empty or invalid alias: {alias!r}")
        canonical_key = component_knowledge_key(mpn)
        component = self.conn.execute(
            "SELECT id FROM components WHERE canonical_key = ?", (canonical_key,)
        ).fetchone()
        if component is None:
            raise VaultRepositoryError("VAULT-E101", f"Component not registered for MPN: {mpn!r}")
        component_id = int(component["id"])
        conflict = self.conn.execute(
            "SELECT ca.component_id, c.canonical_key FROM component_aliases ca"
            " JOIN components c ON c.id = ca.component_id"
            " WHERE ca.alias_key = ? AND ca.alias_type = ? AND COALESCE(ca.distributor,'') = COALESCE(?, '')",
            (alias_key, alias_type, distributor),
        ).fetchone()
        if conflict is not None:
            if int(conflict["component_id"]) == component_id:
                return dict(
                    self.conn.execute(
                        "SELECT * FROM component_aliases WHERE alias_key = ? AND alias_type = ?"
                        " AND COALESCE(distributor,'') = COALESCE(?, '')",
                        (alias_key, alias_type, distributor),
                    ).fetchone()
                )
            raise VaultRepositoryError(
                "VAULT-E102",
                f"Alias conflict: {alias!r} already maps to {conflict['canonical_key']}",
            )
        with self._transaction(actor):
            cursor = self.conn.execute(
                "INSERT INTO component_aliases (component_id, alias, alias_key, alias_type, distributor, note)"
                " VALUES (?,?,?,?,?,?)",
                (component_id, alias, alias_key, alias_type, distributor, note),
            )
            row_id = int(cursor.lastrowid)
            self._audit("insert", "component_aliases", row_id, "alias_key", None, alias_key)
        return dict(self.conn.execute("SELECT * FROM component_aliases WHERE id = ?", (row_id,)).fetchone())

    def resolve(self, query: str) -> ResolveResult:
        key = component_knowledge_key((query or "").strip())
        row = self.conn.execute("SELECT * FROM components WHERE canonical_key = ?", (key,)).fetchone()
        if row is not None:
            return ResolveResult(status="found", canonical_key=row["canonical_key"], component=dict(row))
        alias_row = self.conn.execute(
            "SELECT ca.alias_type, c.* FROM component_aliases ca"
            " JOIN components c ON c.id = ca.component_id WHERE ca.alias_key = ?"
            " ORDER BY ca.id LIMIT 1",
            (key,),
        ).fetchone()
        if alias_row is not None:
            component = {column: alias_row[column] for column in alias_row.keys() if column != "alias_type"}
            return ResolveResult(
                status="found",
                canonical_key=component["canonical_key"],
                component=component,
                hit_alias_type=alias_row["alias_type"],
            )
        return ResolveResult(status="absent")

    # -- L2: documents ---------------------------------------------------

    def ingest_document(
        self,
        path: str | Path,
        doc_type: str,
        provenance: str | None,
        mpns: list[str],
        revision: str | None = None,
        revision_date: str | None = None,
        provenance_detail: str | None = None,
        actor: str | None = None,
    ) -> IngestResult:
        if provenance not in _VALID_PROVENANCE:
            raise VaultRepositoryError(
                "VAULT-E201",
                "Document provenance is required (user-provided / distributor-api / docxmcp-chunk / client-cache-import)",
            )
        if doc_type not in _VALID_DOC_TYPES:
            raise VaultRepositoryError("VAULT-E204", f"Unsupported document type: {doc_type!r}")
        source = Path(path)
        if not source.is_file():
            raise VaultRepositoryError("VAULT-E204", f"Document file not found: {source}")
        actor_name = self._require_actor(actor)
        # DD-6 ordering: blob is written (and fsynced) BEFORE the DB transaction commits.
        sha256_hex, blob_path = write_blob(self.storage.vault_dir, source)
        with self._transaction(actor_name):
            existing = self.conn.execute("SELECT id FROM documents WHERE sha256 = ?", (sha256_hex,)).fetchone()
            dedup_hit = existing is not None
            if dedup_hit:
                document_id = int(existing["id"])
            else:
                cursor = self.conn.execute(
                    "INSERT INTO documents (sha256, blob_path, filename, doc_type, revision, revision_date,"
                    " provenance, provenance_detail) VALUES (?,?,?,?,?,?,?,?)",
                    (sha256_hex, blob_path, source.name, doc_type, revision, revision_date, provenance, provenance_detail),
                )
                document_id = int(cursor.lastrowid)
                self._audit("insert", "documents", document_id, "sha256", None, sha256_hex)
            links_added = 0
            for mpn in mpns:
                component = self._component_for_link(mpn)
                linked = self.conn.execute(
                    "SELECT 1 FROM component_documents WHERE component_id = ? AND document_id = ?",
                    (component["id"], document_id),
                ).fetchone()
                if linked is None:
                    self.conn.execute(
                        "INSERT INTO component_documents (component_id, document_id) VALUES (?,?)",
                        (component["id"], document_id),
                    )
                    self._audit("insert", "component_documents", document_id, "component_id", None, str(component["id"]))
                    links_added += 1
        return IngestResult(
            document_id=document_id,
            sha256=sha256_hex,
            dedup_hit=dedup_hit,
            links_added=links_added,
            blob_path=blob_path,
        )

    def _component_for_link(self, mpn: str) -> sqlite3.Row:
        mpn = (mpn or "").strip()
        canonical_key = component_knowledge_key(mpn)
        if not mpn or canonical_key == _EMPTY_KEY:
            raise VaultRepositoryError("VAULT-E101", f"Empty or invalid MPN: {mpn!r}")
        row = self.conn.execute("SELECT * FROM components WHERE canonical_key = ?", (canonical_key,)).fetchone()
        if row is not None:
            return row
        cursor = self.conn.execute(
            "INSERT INTO components (canonical_key, mpn) VALUES (?,?)", (canonical_key, mpn)
        )
        row_id = int(cursor.lastrowid)
        self._audit("insert", "components", row_id, "canonical_key", None, canonical_key)
        return self.conn.execute("SELECT * FROM components WHERE id = ?", (row_id,)).fetchone()

    def list_documents(self, mpn: str, doc_type: str | None = None) -> list[dict[str, Any]]:
        """Documents for a component, latest revision first (R2 revision chain)."""
        canonical_key = component_knowledge_key((mpn or "").strip())
        sql = (
            "SELECT d.* FROM documents d"
            " JOIN component_documents cd ON cd.document_id = d.id"
            " JOIN components c ON c.id = cd.component_id"
            " WHERE c.canonical_key = ?"
        )
        params: list[Any] = [canonical_key]
        if doc_type is not None:
            sql += " AND d.doc_type = ?"
            params.append(doc_type)
        sql += (
            " ORDER BY (d.revision_date IS NULL), d.revision_date DESC,"
            " (d.revision IS NULL), d.revision DESC, d.ingested_at DESC, d.id DESC"
        )
        return [dict(row) for row in self.conn.execute(sql, params)]

    def latest_document(self, mpn: str, doc_type: str | None = None) -> dict[str, Any] | None:
        documents = self.list_documents(mpn, doc_type=doc_type)
        return documents[0] if documents else None

    # -- L3: source chunks + FTS ------------------------------------------

    def ingest_chunks(
        self,
        document_id: int,
        chunks: list[dict[str, Any]],
        extractor: str | None = None,
        actor: str | None = None,
    ) -> ChunkIngestResult:
        """Ingest extracted chunks for a document (R3).

        Each chunk dict: chunk_kind, content, extractor (or call-level
        ``extractor`` fallback) are REQUIRED (VAULT-E302); page_number and
        anchor are optional per data-schema.json. Re-ingesting the same
        document with a NEW extractor marks previously active chunks of
        other extractors stale=1 — never deletes (TV-R3-3).
        """
        document = self.conn.execute("SELECT id FROM documents WHERE id = ?", (document_id,)).fetchone()
        if document is None:
            raise VaultRepositoryError("VAULT-E301", f"Chunk references unknown document id {document_id!r}")
        if not chunks:
            raise VaultRepositoryError("VAULT-E302", "Chunk missing required field: chunks (empty batch)")
        prepared: list[tuple[str, int | None, str | None, str, str]] = []
        incoming_extractors: set[str] = set()
        for chunk in chunks:
            chunk_kind = chunk.get("chunk_kind")
            if chunk_kind not in _VALID_CHUNK_KINDS:
                raise VaultRepositoryError("VAULT-E302", f"Chunk missing required field: chunk_kind ({chunk_kind!r})")
            content = chunk.get("content")
            if not content or not str(content).strip():
                raise VaultRepositoryError("VAULT-E302", "Chunk missing required field: content")
            chunk_extractor = chunk.get("extractor") or extractor
            if not chunk_extractor or not str(chunk_extractor).strip():
                raise VaultRepositoryError("VAULT-E302", "Chunk missing required field: extractor")
            chunk_extractor = str(chunk_extractor).strip()
            incoming_extractors.add(chunk_extractor)
            anchor = chunk.get("anchor")
            if anchor is not None and not isinstance(anchor, str):
                anchor = json.dumps(anchor, ensure_ascii=False, sort_keys=True)
            page_number = chunk.get("page_number")
            prepared.append((chunk_kind, page_number, anchor, str(content), chunk_extractor))
        with self._transaction(actor):
            placeholders = ",".join("?" for _ in incoming_extractors)
            stale_rows = self.conn.execute(
                f"SELECT id, extractor FROM chunks WHERE document_id = ? AND stale = 0"
                f" AND extractor NOT IN ({placeholders})",
                (document_id, *sorted(incoming_extractors)),
            ).fetchall()
            for row in stale_rows:
                self.conn.execute("UPDATE chunks SET stale = 1 WHERE id = ?", (int(row["id"]),))
                self._audit("update", "chunks", int(row["id"]), "stale", "0", "1")
            chunks_added = 0
            for chunk_kind, page_number, anchor, content, chunk_extractor in prepared:
                cursor = self.conn.execute(
                    "INSERT INTO chunks (document_id, chunk_kind, page_number, anchor, content, extractor)"
                    " VALUES (?,?,?,?,?,?)",
                    (document_id, chunk_kind, page_number, anchor, content, chunk_extractor),
                )
                self._audit("insert", "chunks", int(cursor.lastrowid), "extractor", None, chunk_extractor)
                chunks_added += 1
        return ChunkIngestResult(
            document_id=document_id,
            chunks_added=chunks_added,
            stale_marked=len(stale_rows),
        )

    def ingest_source_chunks(
        self,
        document_id: int,
        source_chunks: list[Any],
        extractor: str,
        actor: str | None = None,
    ) -> ChunkIngestResult:
        """Adapter: ingest doc-core ``DocumentSourceChunk`` objects (task 2.2).

        Maps kind→chunk_kind ('pdf-text'/'text'→'text'), page_hint→page_number,
        and packs chunk_id/char range/evidence target into the anchor JSON.
        ``extractor`` is mandatory — DocumentSourceChunk carries none.
        """
        kind_map = {"pdf-text": "text", "text": "text"}
        chunks: list[dict[str, Any]] = []
        for source_chunk in source_chunks:
            anchor: dict[str, Any] = {
                "chunk_id": source_chunk.chunk_id,
                "char_start": source_chunk.char_start,
                "char_end": source_chunk.char_end,
            }
            evidence = getattr(source_chunk, "evidence", None)
            if evidence is not None:
                anchor["target_path"] = evidence.target_path
            chunks.append(
                {
                    "chunk_kind": kind_map.get(source_chunk.kind, "text"),
                    "page_number": source_chunk.page_hint,
                    "anchor": anchor,
                    "content": source_chunk.text,
                    "extractor": extractor,
                }
            )
        return self.ingest_chunks(document_id, chunks, actor=actor)

    def search_chunks(self, query: str, limit: int = 20, include_stale: bool = False) -> list[ChunkSearchHit]:
        """FTS5 BM25 full-text search over chunks (R3, TV-R3-2).

        Returns hits carrying MPN(s), document id/filename, and page anchor.
        Stale chunks are excluded unless ``include_stale``. No-hit -> [].
        """
        query = (query or "").strip()
        if not query:
            raise VaultRepositoryError("VAULT-E302", "Chunk search query is empty")
        sql = (
            "SELECT ch.id AS chunk_id, ch.document_id, ch.chunk_kind, ch.page_number, ch.anchor,"
            " ch.content, ch.extractor, d.filename, bm25(chunks_fts) AS rank"
            " FROM chunks_fts"
            " JOIN chunks ch ON ch.id = chunks_fts.rowid"
            " JOIN documents d ON d.id = ch.document_id"
            " WHERE chunks_fts MATCH ?"
        )
        if not include_stale:
            sql += " AND ch.stale = 0"
        sql += " ORDER BY rank LIMIT ?"
        hits: list[ChunkSearchHit] = []
        for row in self.conn.execute(sql, (query, int(limit))):
            mpn_rows = self.conn.execute(
                "SELECT c.mpn FROM components c"
                " JOIN component_documents cd ON cd.component_id = c.id"
                " WHERE cd.document_id = ? ORDER BY c.mpn",
                (row["document_id"],),
            ).fetchall()
            hits.append(
                ChunkSearchHit(
                    chunk_id=int(row["chunk_id"]),
                    document_id=int(row["document_id"]),
                    filename=row["filename"],
                    page_number=row["page_number"],
                    anchor=row["anchor"],
                    chunk_kind=row["chunk_kind"],
                    extractor=row["extractor"],
                    content=row["content"],
                    mpns=[mpn_row["mpn"] for mpn_row in mpn_rows],
                    bm25=float(row["rank"]),
                )
            )
        return hits


    # -- L4: normalized specs (EAV) + L7 gaps ------------------------------

    def write_spec(
        self,
        mpn: str,
        field_path: str,
        value_num: float | None = None,
        value_text: str | None = None,
        unit: str | None = None,
        condition: str | None = None,
        min_val: float | None = None,
        typ_val: float | None = None,
        max_val: float | None = None,
        evidence_chunk_id: int | None = None,
        source_note: str | None = None,
        confidence: str = "unverified",
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Write one spec value (R4).

        field_path accepts a friendly alias or canonical dotted path; DB
        stores canonical only (VAULT-E401 on unknown). No evidence ->
        confidence is forced to 'unverified' (TV-R4-1) — the DD-4 trigger
        is the backstop, this is the API-layer rule. Same field with a
        different condition coexists (TV-R4-4).
        """
        canonical_path = resolve_field_path(field_path)
        if value_num is None and value_text is None and min_val is None and typ_val is None and max_val is None:
            raise VaultRepositoryError(
                "VAULT-E403", "Spec value has no value (num/text/min/typ/max all null)"
            )
        has_evidence = evidence_chunk_id is not None or bool(source_note and str(source_note).strip())
        stored_confidence = confidence if (confidence == "verified" and has_evidence) else "unverified"
        actor_name = self._require_actor(actor)
        with self._transaction(actor_name):
            component = self._component_for_link(mpn)
            cursor = self.conn.execute(
                "INSERT INTO spec_values (component_id, field_path, value_num, value_text, unit, condition,"
                " min_val, typ_val, max_val, evidence_chunk_id, source_note, confidence)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    component["id"], canonical_path, value_num, value_text, unit, condition,
                    min_val, typ_val, max_val, evidence_chunk_id, source_note, stored_confidence,
                ),
            )
            row_id = int(cursor.lastrowid)
            evidence_ref = (
                f"chunk:{evidence_chunk_id}" if evidence_chunk_id is not None
                else (source_note or None)
            )
            self._audit("insert", "spec_values", row_id, canonical_path, None, _text(value_num if value_num is not None else value_text), evidence_ref)
        return dict(self.conn.execute("SELECT * FROM spec_values WHERE id = ?", (row_id,)).fetchone())

    def read_spec(self, mpn: str, field: str, condition: str | None = None) -> dict[str, Any]:
        """Read spec values for (mpn, field) (R4 / TV-R4-5).

        Returns {status, resolved_path, values:[…]} — status is absent
        (component unknown), no-field (no rows), or found. Alias resolution
        happens here; unknown paths raise VAULT-E401.
        """
        canonical_path = resolve_field_path(field)
        resolved = self.resolve(mpn)
        if resolved.status == "absent":
            return {"status": "absent", "mpn": mpn, "resolved_path": canonical_path, "values": []}
        sql = "SELECT * FROM spec_values WHERE component_id = ? AND field_path = ?"
        params: list[Any] = [resolved.component["id"], canonical_path]
        if condition is not None:
            sql += " AND condition = ?"
            params.append(condition)
        sql += " ORDER BY (confidence='verified') DESC, id"
        rows = [dict(row) for row in self.conn.execute(sql, params)]
        if not rows:
            return {"status": "no-field", "mpn": mpn, "resolved_path": canonical_path, "values": []}
        return {"status": "found", "mpn": mpn, "resolved_path": canonical_path, "values": rows}

    def register_package(
        self,
        mpn: str,
        package_name: str,
        body_size_mm: str | None = None,
        pitch_mm: float | None = None,
        pin_count: int | None = None,
        exposed_pad: bool = False,
        land_pattern: str | None = None,
        evidence_chunk_id: int | None = None,
        confidence: str = "unverified",
        actor: str | None = None,
    ) -> dict[str, Any]:
        package_name = (package_name or "").strip()
        if not package_name:
            raise VaultRepositoryError("VAULT-E403", "Package name is required")
        stored_confidence = confidence if (confidence == "verified" and evidence_chunk_id is not None) else "unverified"
        actor_name = self._require_actor(actor)
        with self._transaction(actor_name):
            component = self._component_for_link(mpn)
            existing = self.conn.execute(
                "SELECT * FROM packages WHERE component_id = ? AND package_name = ?",
                (component["id"], package_name),
            ).fetchone()
            if existing is not None:
                return dict(existing)
            cursor = self.conn.execute(
                "INSERT INTO packages (component_id, package_name, body_size_mm, pitch_mm, pin_count,"
                " exposed_pad, land_pattern, evidence_chunk_id, confidence) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    component["id"], package_name, body_size_mm, pitch_mm, pin_count,
                    1 if exposed_pad else 0, land_pattern, evidence_chunk_id, stored_confidence,
                ),
            )
            row_id = int(cursor.lastrowid)
            self._audit("insert", "packages", row_id, "package_name", None, package_name)
        return dict(self.conn.execute("SELECT * FROM packages WHERE id = ?", (row_id,)).fetchone())

    def write_pins(
        self,
        mpn: str,
        pins: list[dict[str, Any]],
        package_name: str | None = None,
        actor: str | None = None,
    ) -> list[dict[str, Any]]:
        """Write pin definitions (R4 pinout scenario).

        Uniqueness is (component, package, pin_number) — duplicate insert
        raises VAULT-E404 with the existing row. Pins for different
        packages of the same component coexist.
        """
        if not pins:
            raise VaultRepositoryError("VAULT-E403", "Pin batch is empty")
        actor_name = self._require_actor(actor)
        with self._transaction(actor_name):
            component = self._component_for_link(mpn)
            package_id: int | None = None
            if package_name is not None:
                package_row = self.conn.execute(
                    "SELECT id FROM packages WHERE component_id = ? AND package_name = ?",
                    (component["id"], package_name.strip()),
                ).fetchone()
                if package_row is None:
                    raise VaultRepositoryError(
                        "VAULT-E404", f"Package not registered for pins: {package_name!r} (register_package first)"
                    )
                package_id = int(package_row["id"])
            written: list[int] = []
            for pin in pins:
                pin_number = str(pin.get("pin_number") or "").strip()
                pin_name = str(pin.get("pin_name") or "").strip()
                if not pin_number or not pin_name:
                    raise VaultRepositoryError("VAULT-E403", "Pin requires pin_number and pin_name")
                evidence_chunk_id = pin.get("evidence_chunk_id")
                confidence = pin.get("confidence", "unverified")
                stored_confidence = confidence if (confidence == "verified" and evidence_chunk_id is not None) else "unverified"
                try:
                    cursor = self.conn.execute(
                        "INSERT INTO pins (component_id, package_id, pin_number, pin_name, role,"
                        " electrical_type, interface_group, evidence_chunk_id, confidence)"
                        " VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            component["id"], package_id, pin_number, pin_name, pin.get("role"),
                            pin.get("electrical_type"), pin.get("interface_group"),
                            evidence_chunk_id, stored_confidence,
                        ),
                    )
                except sqlite3.IntegrityError as error:
                    raise VaultRepositoryError(
                        "VAULT-E404",
                        f"Pin uniqueness violation: (component={component['mpn']}, package={package_name},"
                        f" pin_number={pin_number}) exists",
                    ) from error
                row_id = int(cursor.lastrowid)
                self._audit("insert", "pins", row_id, "pin_number", None, pin_number)
                written.append(row_id)
        placeholders = ",".join("?" for _ in written)
        return [
            dict(row)
            for row in self.conn.execute(f"SELECT * FROM pins WHERE id IN ({placeholders}) ORDER BY id", written)
        ]

    def record_gap(self, mpn: str, gap_kind: str, description: str, actor: str | None = None) -> dict[str, Any]:
        actor_name = self._require_actor(actor)
        with self._transaction(actor_name):
            component = self._component_for_link(mpn)
            cursor = self.conn.execute(
                "INSERT INTO knowledge_gaps (component_id, gap_kind, description) VALUES (?,?,?)",
                (component["id"], gap_kind, description),
            )
            row_id = int(cursor.lastrowid)
            self._audit("insert", "knowledge_gaps", row_id, "gap_kind", None, gap_kind)
        return dict(self.conn.execute("SELECT * FROM knowledge_gaps WHERE id = ?", (row_id,)).fetchone())

    def resolve_gap(self, gap_id: int, actor: str | None = None) -> dict[str, Any]:
        actor_name = self._require_actor(actor)
        row = self.conn.execute("SELECT * FROM knowledge_gaps WHERE id = ?", (gap_id,)).fetchone()
        if row is None:
            raise VaultRepositoryError("VAULT-E403", f"Knowledge gap not found: {gap_id}")
        with self._transaction(actor_name):
            self.conn.execute("UPDATE knowledge_gaps SET resolved = 1 WHERE id = ?", (gap_id,))
            self._audit("resolve-gap", "knowledge_gaps", gap_id, "resolved", "0", "1")
        return dict(self.conn.execute("SELECT * FROM knowledge_gaps WHERE id = ?", (gap_id,)).fetchone())

    def component_completeness(self, mpn: str) -> dict[str, Any]:
        """Explicit completeness report (R7 gaps scenario): score + gap list."""
        resolved = self.resolve(mpn)
        if resolved.status == "absent":
            return {"status": "absent", "mpn": mpn}
        row = self.conn.execute(
            "SELECT * FROM component_completeness WHERE component_id = ?", (resolved.component["id"],)
        ).fetchone()
        gaps = [
            dict(gap)
            for gap in self.conn.execute(
                "SELECT * FROM knowledge_gaps WHERE component_id = ? AND resolved = 0 ORDER BY id",
                (resolved.component["id"],),
            )
        ]
        return {"status": "found", "mpn": mpn, **dict(row), "gaps": gaps}

    def knowledge_queue(self, limit: int = 80) -> list[dict[str, Any]]:
        """Open-gap components ranked by DD-9 priority rules (view-backed)."""
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM knowledge_queue ORDER BY priority_rank, occurrence_count DESC, lower(mpn) LIMIT ?",
                (int(limit),),
            )
        ]


    # -- L8: usage footprints + sourcing snapshots + substitutions ---------

    def record_usage(
        self,
        mpn: str,
        project_id: str,
        refdes: list[str] | None = None,
        workflow: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Record a project's usage of a component (R8, TV-R8-1).

        One row per (component, project_id) — re-recording the same project
        replaces refdes/count, never duplicates. occurrence_count = number
        of distinct refdes.
        """
        project_id = (project_id or "").strip()
        if not project_id:
            raise VaultRepositoryError("VAULT-E801", "Usage record missing project_id")
        refdes_values = sorted({str(r).strip() for r in (refdes or []) if str(r).strip()})
        refdes_json = json.dumps(refdes_values, ensure_ascii=False)
        occurrence_count = len(refdes_values)
        actor_name = self._require_actor(actor)
        with self._transaction(actor_name):
            component = self._component_for_link(mpn)
            existing = self.conn.execute(
                "SELECT * FROM usage WHERE component_id = ? AND project_id = ?",
                (component["id"], project_id),
            ).fetchone()
            if existing is None:
                cursor = self.conn.execute(
                    "INSERT INTO usage (component_id, project_id, refdes, occurrence_count, workflow)"
                    " VALUES (?,?,?,?,?)",
                    (component["id"], project_id, refdes_json, occurrence_count, workflow),
                )
                row_id = int(cursor.lastrowid)
                self._audit("insert", "usage", row_id, "project_id", None, project_id)
            else:
                row_id = int(existing["id"])
                self.conn.execute(
                    "UPDATE usage SET refdes = ?, occurrence_count = ?, workflow = ?,"
                    " recorded_at = datetime('now') WHERE id = ?",
                    (refdes_json, occurrence_count, workflow, row_id),
                )
                self._audit(
                    "update", "usage", row_id, "occurrence_count",
                    _text(existing["occurrence_count"]), _text(occurrence_count),
                )
        return dict(self.conn.execute("SELECT * FROM usage WHERE id = ?", (row_id,)).fetchone())

    def occurrences(self, mpn: str) -> dict[str, Any]:
        """Cross-project occurrence aggregation for a component (R8)."""
        resolved = self.resolve(mpn)
        if resolved.status == "absent":
            return {"status": "absent", "mpn": mpn}
        rows = [
            dict(row)
            for row in self.conn.execute(
                "SELECT project_id, refdes, occurrence_count, workflow, recorded_at"
                " FROM usage WHERE component_id = ? ORDER BY project_id",
                (resolved.component["id"],),
            )
        ]
        for row in rows:
            row["refdes"] = json.loads(row["refdes"]) if row["refdes"] else []
        return {
            "status": "found",
            "mpn": mpn,
            "total_occurrences": sum(row["occurrence_count"] for row in rows),
            "project_count": len(rows),
            "projects": rows,
        }

    def record_sourcing_snapshot(
        self,
        mpn: str,
        distributor: str,
        distributor_pn: str | None = None,
        stock: int | None = None,
        moq: int | None = None,
        price_breaks: list[dict[str, Any]] | None = None,
        lifecycle_note: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Store a timestamped distributor snapshot (R8). Never live data."""
        distributor = (distributor or "").strip()
        if not distributor:
            raise VaultRepositoryError(
                "VAULT-E802", "Sourcing snapshot rejected: live-query semantics not supported (distributor required)"
            )
        actor_name = self._require_actor(actor)
        with self._transaction(actor_name):
            component = self._component_for_link(mpn)
            cursor = self.conn.execute(
                "INSERT INTO sourcing_snapshots (component_id, distributor, distributor_pn, stock, moq,"
                " price_breaks, lifecycle_note) VALUES (?,?,?,?,?,?,?)",
                (
                    component["id"], distributor, distributor_pn, stock, moq,
                    json.dumps(price_breaks, ensure_ascii=False) if price_breaks is not None else None,
                    lifecycle_note,
                ),
            )
            row_id = int(cursor.lastrowid)
            self._audit("insert", "sourcing_snapshots", row_id, "distributor", None, distributor)
        return dict(self.conn.execute("SELECT * FROM sourcing_snapshots WHERE id = ?", (row_id,)).fetchone())

    def sourcing_snapshots(self, mpn: str, distributor: str | None = None) -> dict[str, Any]:
        """Snapshots for a component, newest first. Explicitly point-in-time."""
        resolved = self.resolve(mpn)
        if resolved.status == "absent":
            return {"status": "absent", "mpn": mpn, "snapshots": []}
        sql = "SELECT * FROM sourcing_snapshots WHERE component_id = ?"
        params: list[Any] = [resolved.component["id"]]
        if distributor is not None:
            sql += " AND distributor = ?"
            params.append(distributor)
        sql += " ORDER BY snapshot_at DESC, id DESC"
        snapshots = [dict(row) for row in self.conn.execute(sql, params)]
        for snapshot in snapshots:
            if snapshot["price_breaks"]:
                snapshot["price_breaks"] = json.loads(snapshot["price_breaks"])
        return {
            "status": "found",
            "mpn": mpn,
            "point_in_time": True,
            "note": "Snapshot data (point-in-time, not live).",
            "snapshots": snapshots,
        }

    def record_substitution(
        self,
        mpn: str,
        substitute_mpn: str,
        compatibility: str,
        differences: str | None = None,
        evidence_ref: str | None = None,
        confidence: str = "unverified",
        actor: str | None = None,
    ) -> dict[str, Any]:
        if compatibility not in ("drop-in", "functional", "partial"):
            raise VaultRepositoryError("VAULT-E403", f"Invalid substitution compatibility: {compatibility!r}")
        has_evidence = bool(evidence_ref and str(evidence_ref).strip())
        stored_confidence = confidence if (confidence == "verified" and has_evidence) else "unverified"
        actor_name = self._require_actor(actor)
        with self._transaction(actor_name):
            component = self._component_for_link(mpn)
            substitute = self._component_for_link(substitute_mpn)
            existing = self.conn.execute(
                "SELECT * FROM substitutions WHERE component_id = ? AND substitute_component_id = ?",
                (component["id"], substitute["id"]),
            ).fetchone()
            if existing is not None:
                return dict(existing)
            cursor = self.conn.execute(
                "INSERT INTO substitutions (component_id, substitute_component_id, compatibility,"
                " differences, evidence_ref, confidence) VALUES (?,?,?,?,?,?)",
                (component["id"], substitute["id"], compatibility, differences, evidence_ref, stored_confidence),
            )
            row_id = int(cursor.lastrowid)
            self._audit("insert", "substitutions", row_id, "compatibility", None, compatibility)
        return dict(self.conn.execute("SELECT * FROM substitutions WHERE id = ?", (row_id,)).fetchone())

    def substitutions(self, mpn: str) -> list[dict[str, Any]]:
        resolved = self.resolve(mpn)
        if resolved.status == "absent":
            return []
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT s.*, c.mpn AS substitute_mpn FROM substitutions s"
                " JOIN components c ON c.id = s.substitute_component_id"
                " WHERE s.component_id = ? ORDER BY s.id",
                (resolved.component["id"],),
            )
        ]

    # -- L5: EDA assets (R5) ------------------------------------------------

    _EDA_LADDER = ("unverified", "pin-checked", "drc-passed")
    _VALID_ASSET_KINDS = ("kicad-symbol", "kicad-footprint", "3d-model")

    def register_eda_asset(
        self,
        mpn: str,
        asset_kind: str,
        library_ref: str,
        package_name: str | None = None,
        verification_status: str = "unverified",
        verified_in: dict[str, Any] | None = None,
        pin_map: dict[str, Any] | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Register a symbol/footprint/3d-model mapping (R5, TV-R5-1).

        Initial status above 'unverified' requires verified_in provenance
        (VAULT-E502) — every claimed verification records where it happened.
        """
        if asset_kind not in self._VALID_ASSET_KINDS:
            raise VaultRepositoryError("VAULT-E501", f"Invalid asset_kind: {asset_kind!r}")
        library_ref = (library_ref or "").strip()
        if not library_ref:
            raise VaultRepositoryError("VAULT-E501", "EDA asset library_ref is required")
        if verification_status not in self._EDA_LADDER:
            raise VaultRepositoryError(
                "VAULT-E502",
                f"Invalid verification status transition: <new> -> {verification_status!r}",
            )
        if verification_status != "unverified" and not verified_in:
            raise VaultRepositoryError(
                "VAULT-E502",
                f"Invalid verification status transition: 'unverified' -> {verification_status!r}"
                " without verified_in provenance",
            )
        actor_name = self._require_actor(actor)
        with self._transaction(actor_name):
            component = self._component_for_link(mpn)
            package_id: int | None = None
            if package_name is not None:
                package_row = self.conn.execute(
                    "SELECT id FROM packages WHERE component_id = ? AND package_name = ?",
                    (component["id"], package_name.strip()),
                ).fetchone()
                if package_row is None:
                    raise VaultRepositoryError(
                        "VAULT-E404", f"Package not registered: {package_name!r} (register_package first)"
                    )
                package_id = int(package_row["id"])
            existing = self.conn.execute(
                "SELECT * FROM eda_assets WHERE component_id = ? AND asset_kind = ? AND library_ref = ?",
                (component["id"], asset_kind, library_ref),
            ).fetchone()
            if existing is not None:
                return dict(existing)
            cursor = self.conn.execute(
                "INSERT INTO eda_assets (component_id, asset_kind, library_ref, package_id,"
                " verification_status, verified_in, pin_map) VALUES (?,?,?,?,?,?,?)",
                (
                    component["id"], asset_kind, library_ref, package_id, verification_status,
                    json.dumps(verified_in, ensure_ascii=False, sort_keys=True) if verified_in else None,
                    json.dumps(pin_map, ensure_ascii=False, sort_keys=True) if pin_map else None,
                ),
            )
            row_id = int(cursor.lastrowid)
            self._audit(
                "insert", "eda_assets", row_id, "library_ref", None, library_ref,
                json.dumps(verified_in, ensure_ascii=False, sort_keys=True) if verified_in else None,
            )
        return dict(self.conn.execute("SELECT * FROM eda_assets WHERE id = ?", (row_id,)).fetchone())

    def upgrade_eda_asset(
        self,
        asset_id: int,
        to_status: str,
        verified_in: dict[str, Any],
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Advance the verification ladder one rung (R5).

        Only unverified->pin-checked->drc-passed, one rung at a time;
        downgrades and rung-skips raise VAULT-E502. Every upgrade records
        verification provenance (verified_in + audit evidence).
        """
        row = self.conn.execute("SELECT * FROM eda_assets WHERE id = ?", (asset_id,)).fetchone()
        if row is None:
            raise VaultRepositoryError("VAULT-E501", f"EDA asset mapping not found for id {asset_id}")
        if to_status not in self._EDA_LADDER:
            raise VaultRepositoryError(
                "VAULT-E502", f"Invalid verification status transition: {row['verification_status']!r} -> {to_status!r}"
            )
        current_rank = self._EDA_LADDER.index(row["verification_status"])
        target_rank = self._EDA_LADDER.index(to_status)
        if target_rank != current_rank + 1:
            raise VaultRepositoryError(
                "VAULT-E502",
                f"Invalid verification status transition: {row['verification_status']!r} -> {to_status!r}"
                f" (ladder: {' -> '.join(self._EDA_LADDER)})",
            )
        if not verified_in:
            raise VaultRepositoryError(
                "VAULT-E502",
                f"Invalid verification status transition: {row['verification_status']!r} -> {to_status!r}"
                " without verified_in provenance",
            )
        verified_in_json = json.dumps(verified_in, ensure_ascii=False, sort_keys=True)
        actor_name = self._require_actor(actor)
        with self._transaction(actor_name):
            self.conn.execute(
                "UPDATE eda_assets SET verification_status = ?, verified_in = ? WHERE id = ?",
                (to_status, verified_in_json, asset_id),
            )
            self._audit(
                "update", "eda_assets", asset_id, "verification_status",
                row["verification_status"], to_status, verified_in_json,
            )
        return dict(self.conn.execute("SELECT * FROM eda_assets WHERE id = ?", (asset_id,)).fetchone())

    def query_eda_asset(self, mpn: str, asset_kind: str) -> dict[str, Any]:
        """EDA asset mappings for (mpn, kind) (R5, TV-R5-2).

        No mapping (or unknown component) -> explicit absent (VAULT-E501
        semantics) — consumers must never guess.
        """
        if asset_kind not in self._VALID_ASSET_KINDS:
            raise VaultRepositoryError("VAULT-E501", f"Invalid asset_kind: {asset_kind!r}")
        resolved = self.resolve(mpn)
        if resolved.status == "absent":
            return {"status": "absent", "mpn": mpn, "asset_kind": asset_kind, "assets": []}
        assets = []
        for row in self.conn.execute(
            "SELECT * FROM eda_assets WHERE component_id = ? AND asset_kind = ? ORDER BY id",
            (resolved.component["id"], asset_kind),
        ):
            asset = dict(row)
            for json_field in ("verified_in", "pin_map"):
                if asset[json_field]:
                    asset[json_field] = json.loads(asset[json_field])
            assets.append(asset)
        if not assets:
            return {"status": "absent", "mpn": mpn, "asset_kind": asset_kind, "assets": []}
        return {"status": "found", "mpn": mpn, "asset_kind": asset_kind, "assets": assets}

    # -- L6: application knowledge (R6) --------------------------------------

    _VALID_KNOWLEDGE_TYPES = ("layout-rule", "reference-circuit", "companion-part", "design-rule")

    def write_app_knowledge(
        self,
        mpn: str,
        knowledge_type: str,
        title: str,
        payload: dict[str, Any] | list[Any] | str,
        companion_mpn: str | None = None,
        evidence_chunk_id: int | None = None,
        source_note: str | None = None,
        confidence: str = "unverified",
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Write one application-knowledge entry (R6, TV-R6-1).

        payload must be JSON (dict/list or a valid JSON string) — VAULT-E602
        otherwise. companion-part requires companion_mpn (VAULT-E601). Same
        trust discipline as spec_values: no evidence -> forced unverified.
        """
        if knowledge_type not in self._VALID_KNOWLEDGE_TYPES:
            raise VaultRepositoryError("VAULT-E602", f"Invalid knowledge_type: {knowledge_type!r}")
        title = (title or "").strip()
        if not title:
            raise VaultRepositoryError("VAULT-E602", f"app_knowledge title is required for type {knowledge_type!r}")
        if isinstance(payload, str):
            try:
                json.loads(payload)
            except json.JSONDecodeError as error:
                raise VaultRepositoryError(
                    "VAULT-E602", f"app_knowledge payload is not valid JSON for type {knowledge_type!r}"
                ) from error
            payload_json = payload
        elif isinstance(payload, (dict, list)):
            payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        else:
            raise VaultRepositoryError(
                "VAULT-E602", f"app_knowledge payload is not valid JSON for type {knowledge_type!r}"
            )
        if knowledge_type == "companion-part" and not (companion_mpn or "").strip():
            raise VaultRepositoryError(
                "VAULT-E601", "companion-part knowledge requires companion_component_id"
            )
        has_evidence = evidence_chunk_id is not None or bool(source_note and str(source_note).strip())
        stored_confidence = confidence if (confidence == "verified" and has_evidence) else "unverified"
        actor_name = self._require_actor(actor)
        with self._transaction(actor_name):
            component = self._component_for_link(mpn)
            companion_id: int | None = None
            if companion_mpn and companion_mpn.strip():
                companion_id = int(self._component_for_link(companion_mpn)["id"])
            cursor = self.conn.execute(
                "INSERT INTO app_knowledge (component_id, knowledge_type, title, payload,"
                " companion_component_id, evidence_chunk_id, source_note, confidence)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    component["id"], knowledge_type, title, payload_json,
                    companion_id, evidence_chunk_id, source_note, stored_confidence,
                ),
            )
            row_id = int(cursor.lastrowid)
            evidence_ref = (
                f"chunk:{evidence_chunk_id}" if evidence_chunk_id is not None else (source_note or None)
            )
            self._audit("insert", "app_knowledge", row_id, "title", None, title, evidence_ref)
        return dict(self.conn.execute("SELECT * FROM app_knowledge WHERE id = ?", (row_id,)).fetchone())

    def app_knowledge(self, mpn: str, knowledge_type: str | None = None) -> dict[str, Any]:
        """Application knowledge for a component, optionally by type (R6).

        Entries carry parsed payload + evidence anchors; companion-part rows
        include the companion's MPN. Unknown component -> explicit absent.
        """
        if knowledge_type is not None and knowledge_type not in self._VALID_KNOWLEDGE_TYPES:
            raise VaultRepositoryError("VAULT-E602", f"Invalid knowledge_type: {knowledge_type!r}")
        resolved = self.resolve(mpn)
        if resolved.status == "absent":
            return {"status": "absent", "mpn": mpn, "entries": []}
        sql = (
            "SELECT ak.*, comp.mpn AS companion_mpn FROM app_knowledge ak"
            " LEFT JOIN components comp ON comp.id = ak.companion_component_id"
            " WHERE ak.component_id = ?"
        )
        params: list[Any] = [resolved.component["id"]]
        if knowledge_type is not None:
            sql += " AND ak.knowledge_type = ?"
            params.append(knowledge_type)
        sql += " ORDER BY ak.id"
        entries = []
        for row in self.conn.execute(sql, params):
            entry = dict(row)
            entry["payload"] = json.loads(entry["payload"])
            entries.append(entry)
        if not entries:
            return {"status": "absent", "mpn": mpn, "entries": []}
        return {"status": "found", "mpn": mpn, "entries": entries}

    # -- client cache import (DD-8, R9 import scenario) ---------------------

    _IMPORT_NOTE_PREFIX = "client-cache-import"

    def import_client_cache(self, cache_root: str | Path, actor: str | None = None) -> dict[str, Any]:
        """One-way import of a `datasheets` skill cache into the vault (task 5.1).

        Reads <cache_root>/extracted/manifest.json (legacy index.json
        accepted, vault.py convention). Every imported value carries
        provenance 'client-cache-import' in source_note; values whose
        extraction has no real source are ALWAYS unverified (DD-8).
        Conflicts with existing vault rows keep BOTH sides and are
        reported (VAULT-E903 semantics, non-blocking). Idempotent:
        re-importing the same manifest adds no duplicate rows.
        """
        from .vault import FIELD_ALIASES as _  # noqa: F401  (namespace SSOT lives in vault.py)

        extract_dir = Path(cache_root) / "extracted"
        manifest_path = None
        for name in ("manifest.json", "index.json"):
            candidate = extract_dir / name
            if candidate.is_file():
                manifest_path = candidate
                break
        if manifest_path is None:
            raise VaultRepositoryError(
                "VAULT-E902", f"Import manifest unreadable or schema-unknown: {extract_dir / 'manifest.json'}"
            )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            raise VaultRepositoryError(
                "VAULT-E902", f"Import manifest unreadable or schema-unknown: {manifest_path} ({error})"
            ) from error
        extractions = manifest.get("extractions")
        if not isinstance(extractions, dict):
            raise VaultRepositoryError(
                "VAULT-E902", f"Import manifest unreadable or schema-unknown: {manifest_path} (no 'extractions')"
            )
        actor_name = self._require_actor(actor)
        imported_components = 0
        specs_written = 0
        skipped_duplicates = 0
        conflicts: list[dict[str, Any]] = []
        for entry in extractions.values():
            mpn = str(entry.get("mpn") or "").strip()
            if not mpn:
                continue
            extraction_file = extract_dir / str(entry.get("file") or "")
            if not extraction_file.is_file():
                continue
            try:
                extraction = json.loads(extraction_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            meta = extraction.get("extraction_metadata", {}) or {}
            real_source = (meta.get("source_pdf") or meta.get("source_note") or "").strip()
            source_note = (
                f"{self._IMPORT_NOTE_PREFIX}:{real_source}" if real_source else self._IMPORT_NOTE_PREFIX
            )
            self.upsert_component(mpn, category=extraction.get("category"), actor=actor_name)
            imported_components += 1
            component = self.conn.execute(
                "SELECT id FROM components WHERE canonical_key = ?", (component_knowledge_key(mpn),)
            ).fetchone()
            for root in FIELD_PATH_ROOTS:
                section = extraction.get(root)
                if not isinstance(section, dict):
                    continue
                for key, value in section.items():
                    if value is None or isinstance(value, (dict, list)):
                        continue
                    field_path = f"{root}.{key}"
                    value_num = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
                    value_text = None if value_num is not None else str(value)
                    duplicate = self.conn.execute(
                        "SELECT 1 FROM spec_values WHERE component_id = ? AND field_path = ?"
                        " AND COALESCE(value_num, -1e308) = COALESCE(?, -1e308)"
                        " AND COALESCE(value_text,'') = COALESCE(?, '')"
                        " AND source_note LIKE ?",
                        (component["id"], field_path, value_num, value_text, f"{self._IMPORT_NOTE_PREFIX}%"),
                    ).fetchone()
                    if duplicate is not None:
                        skipped_duplicates += 1
                        continue
                    existing_rows = self.conn.execute(
                        "SELECT id, value_num, value_text, confidence FROM spec_values"
                        " WHERE component_id = ? AND field_path = ?",
                        (component["id"], field_path),
                    ).fetchall()
                    row = self.write_spec(
                        mpn,
                        field_path,
                        value_num=value_num,
                        value_text=value_text,
                        source_note=source_note,
                        confidence="verified" if real_source else "unverified",
                        actor=actor_name,
                    )
                    specs_written += 1
                    for existing in existing_rows:
                        existing_value = (
                            existing["value_num"] if existing["value_num"] is not None else existing["value_text"]
                        )
                        imported_value = value_num if value_num is not None else value_text
                        if existing_value != imported_value:
                            conflicts.append(
                                {
                                    "mpn": mpn,
                                    "field_path": field_path,
                                    "existing_row_id": int(existing["id"]),
                                    "existing_value": existing_value,
                                    "existing_confidence": existing["confidence"],
                                    "imported_row_id": int(row["id"]),
                                    "imported_value": imported_value,
                                    "imported_confidence": row["confidence"],
                                }
                            )
        result: dict[str, Any] = {
            "status": "ok",
            "manifest": str(manifest_path),
            "imported_components": imported_components,
            "specs_written": specs_written,
            "skipped_duplicates": skipped_duplicates,
            "conflicts": conflicts,
        }
        if conflicts:
            result["error_code"] = "VAULT-E903"
            result["conflict_note"] = (
                f"Import conflict report: {len(conflicts)} conflicts kept side-by-side"
            )
        return result


def _text(value: Any) -> str | None:
    return None if value is None else str(value)
