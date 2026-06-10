"""Component Vault storage foundation (Phase 1).

SQLite connection management, schema migrations, blob store, and the
startup blob/DB consistency scan. Schema SSOT is
plans/feature_component_vault/data-schema.json; only the Phase-1 tables
(components, manufacturers, component_aliases, documents,
component_documents, audit_log) are created here. Later phases append
new Migration entries — never edit an already-shipped migration.

Red lines honored here:
- corrupt/unreadable DB -> fail fast with VAULT-E001, never recreate.
- vault dir resolution: env BODESIGN_VAULT_DIR, else explicit argument;
  no cwd guessing (VAULT-E002 on missing/unwritable).
- schema version beyond known migrations -> VAULT-E003, no overwrite.
- audit_log append-only enforced by DB triggers (VAULT-E701 semantics).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

VAULT_DIR_ENV = "BODESIGN_VAULT_DIR"
DB_FILENAME = "vault.db"
BLOB_DIR_NAME = "blobs"


class VaultError(Exception):
    """Base class for vault errors carrying a VAULT-Exxx code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class VaultStorageError(VaultError):
    """Storage-layer errors (VAULT-E0xx, VAULT-E2xx blob ordering)."""


@dataclass(slots=True, frozen=True)
class Migration:
    version: int
    statements: tuple[str, ...]


_PHASE1_DDL: tuple[str, ...] = (
    """
    CREATE TABLE manufacturers (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        aliases TEXT
    )
    """,
    """
    CREATE TABLE components (
        id INTEGER PRIMARY KEY,
        canonical_key TEXT NOT NULL UNIQUE,
        mpn TEXT NOT NULL,
        manufacturer_id INTEGER REFERENCES manufacturers(id),
        category TEXT,
        lifecycle_status TEXT CHECK(lifecycle_status IN ('active','nrnd','eol','obsolete','unknown')) DEFAULT 'unknown',
        lifecycle_checked_at TEXT,
        description TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX idx_components_category ON components(category)",
    """
    CREATE TABLE component_aliases (
        id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
        alias TEXT NOT NULL,
        alias_key TEXT NOT NULL,
        alias_type TEXT NOT NULL CHECK(alias_type IN ('family-variant','manufacturer-alias','distributor','legacy-pn')),
        distributor TEXT,
        note TEXT
    )
    """,
    "CREATE UNIQUE INDEX idx_alias_key ON component_aliases(alias_key, alias_type, COALESCE(distributor,''))",
    "CREATE INDEX idx_alias_component ON component_aliases(component_id)",
    """
    CREATE TABLE documents (
        id INTEGER PRIMARY KEY,
        sha256 TEXT NOT NULL UNIQUE,
        blob_path TEXT NOT NULL,
        filename TEXT NOT NULL,
        doc_type TEXT NOT NULL CHECK(doc_type IN ('datasheet','app-note','reference-design','errata','package-drawing','other')),
        revision TEXT,
        revision_date TEXT,
        page_count INTEGER,
        provenance TEXT NOT NULL CHECK(provenance IN ('user-provided','distributor-api','docxmcp-chunk','client-cache-import')),
        provenance_detail TEXT,
        ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE component_documents (
        component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
        document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        is_primary INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (component_id, document_id)
    )
    """,
    """
    CREATE TABLE audit_log (
        id INTEGER PRIMARY KEY,
        actor TEXT NOT NULL,
        action TEXT NOT NULL CHECK(action IN ('insert','update','import','resolve-gap')),
        table_name TEXT NOT NULL,
        row_id INTEGER NOT NULL,
        field TEXT,
        old_value TEXT,
        new_value TEXT,
        evidence_ref TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE TRIGGER trg_audit_no_update BEFORE UPDATE ON audit_log BEGIN SELECT RAISE(ABORT,'audit_log is append-only'); END",
    "CREATE TRIGGER trg_audit_no_delete BEFORE DELETE ON audit_log BEGIN SELECT RAISE(ABORT,'audit_log is append-only'); END",
)

_PHASE2_DDL: tuple[str, ...] = (
    """
    CREATE TABLE chunks (
        id INTEGER PRIMARY KEY,
        document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        chunk_kind TEXT NOT NULL CHECK(chunk_kind IN ('text','table','figure-caption','section-heading')),
        page_number INTEGER,
        anchor TEXT,
        content TEXT NOT NULL,
        extractor TEXT NOT NULL,
        stale INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX idx_chunks_document ON chunks(document_id, stale)",
    "CREATE VIRTUAL TABLE chunks_fts USING fts5(content, content='chunks', content_rowid='id', tokenize='unicode61')",
    """
    CREATE TRIGGER trg_chunks_fts_insert AFTER INSERT ON chunks BEGIN
        INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
    END
    """,
    """
    CREATE TRIGGER trg_chunks_fts_delete AFTER DELETE ON chunks BEGIN
        INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
    END
    """,
    """
    CREATE TRIGGER trg_chunks_fts_update AFTER UPDATE OF content ON chunks BEGIN
        INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
        INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
    END
    """,
)

_PHASE3_DDL: tuple[str, ...] = (
    """
    CREATE TABLE spec_values (
        id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
        field_path TEXT NOT NULL,
        value_num REAL,
        value_text TEXT,
        unit TEXT,
        condition TEXT,
        min_val REAL,
        typ_val REAL,
        max_val REAL,
        evidence_chunk_id INTEGER REFERENCES chunks(id),
        source_note TEXT,
        confidence TEXT NOT NULL CHECK(confidence IN ('verified','unverified')) DEFAULT 'unverified',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        CHECK(value_num IS NOT NULL OR value_text IS NOT NULL OR min_val IS NOT NULL OR typ_val IS NOT NULL OR max_val IS NOT NULL)
    )
    """,
    "CREATE INDEX idx_spec_component_field ON spec_values(component_id, field_path)",
    "CREATE INDEX idx_spec_field ON spec_values(field_path)",
    # DD-4: verified spec requires evidence — enforced on INSERT and UPDATE.
    # (data-schema.json lists the INSERT trigger; the UPDATE twin closes the
    # downgrade-then-upgrade loophole, same DD-4 rule.)
    """
    CREATE TRIGGER trg_spec_verified_needs_evidence BEFORE INSERT ON spec_values
    WHEN NEW.confidence='verified' AND NEW.evidence_chunk_id IS NULL AND (NEW.source_note IS NULL OR NEW.source_note='')
    BEGIN SELECT RAISE(ABORT, 'verified spec requires evidence_chunk_id or source_note'); END
    """,
    """
    CREATE TRIGGER trg_spec_verified_needs_evidence_update BEFORE UPDATE ON spec_values
    WHEN NEW.confidence='verified' AND NEW.evidence_chunk_id IS NULL AND (NEW.source_note IS NULL OR NEW.source_note='')
    BEGIN SELECT RAISE(ABORT, 'verified spec requires evidence_chunk_id or source_note'); END
    """,
    """
    CREATE TABLE packages (
        id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
        package_name TEXT NOT NULL,
        body_size_mm TEXT,
        pitch_mm REAL,
        pin_count INTEGER,
        exposed_pad INTEGER NOT NULL DEFAULT 0,
        land_pattern TEXT,
        evidence_chunk_id INTEGER REFERENCES chunks(id),
        confidence TEXT NOT NULL CHECK(confidence IN ('verified','unverified')) DEFAULT 'unverified'
    )
    """,
    "CREATE UNIQUE INDEX idx_pkg ON packages(component_id, package_name)",
    """
    CREATE TABLE pins (
        id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
        package_id INTEGER REFERENCES packages(id) ON DELETE CASCADE,
        pin_number TEXT NOT NULL,
        pin_name TEXT NOT NULL,
        role TEXT,
        electrical_type TEXT,
        interface_group TEXT,
        evidence_chunk_id INTEGER REFERENCES chunks(id),
        confidence TEXT NOT NULL CHECK(confidence IN ('verified','unverified')) DEFAULT 'unverified'
    )
    """,
    "CREATE UNIQUE INDEX idx_pins ON pins(component_id, COALESCE(package_id,0), pin_number)",
    """
    CREATE TABLE knowledge_gaps (
        id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
        gap_kind TEXT NOT NULL,
        description TEXT NOT NULL,
        resolved INTEGER NOT NULL DEFAULT 0,
        resolved_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX idx_gaps ON knowledge_gaps(component_id, resolved)",
    # DD-9 views. Phase 3 scope: usage (L8) and eda_assets (L5) tables do not
    # exist yet, so occurrence_count and has_eda_asset are constant 0 here;
    # Phase 5/6 migrations recreate these views over the real tables.
    """
    CREATE VIEW component_completeness AS
    SELECT
        c.id AS component_id,
        c.canonical_key,
        c.mpn,
        EXISTS(SELECT 1 FROM pins p WHERE p.component_id = c.id) AS has_pinout,
        EXISTS(SELECT 1 FROM packages k WHERE k.component_id = c.id) AS has_package,
        EXISTS(SELECT 1 FROM spec_values s WHERE s.component_id = c.id) AS has_electrical,
        0 AS has_eda_asset,
        (SELECT COUNT(*) FROM knowledge_gaps g WHERE g.component_id = c.id AND g.resolved = 0) AS unresolved_gaps,
        (EXISTS(SELECT 1 FROM pins p WHERE p.component_id = c.id)
         + EXISTS(SELECT 1 FROM packages k WHERE k.component_id = c.id)
         + EXISTS(SELECT 1 FROM spec_values s WHERE s.component_id = c.id)
         + 0) AS extraction_score
    FROM components c
    """,
    """
    CREATE VIEW knowledge_queue AS
    SELECT
        c.id AS component_id,
        c.canonical_key,
        c.mpn,
        0 AS occurrence_count,
        (SELECT COUNT(*) FROM knowledge_gaps g WHERE g.component_id = c.id AND g.resolved = 0) AS unresolved_gaps,
        CASE
            WHEN upper(c.mpn) LIKE 'MDBT%' OR upper(c.mpn) LIKE 'W25Q%'
                 OR upper(c.mpn) LIKE 'STM%' OR upper(c.mpn) LIKE 'NRF%' THEN 'high'
            WHEN 0 >= 8 THEN 'high'
            WHEN 0 >= 3 THEN 'normal'
            ELSE 'low'
        END AS priority,
        CASE
            WHEN upper(c.mpn) LIKE 'MDBT%' OR upper(c.mpn) LIKE 'W25Q%'
                 OR upper(c.mpn) LIKE 'STM%' OR upper(c.mpn) LIKE 'NRF%' THEN 0
            WHEN 0 >= 8 THEN 0
            WHEN 0 >= 3 THEN 1
            ELSE 2
        END AS priority_rank
    FROM components c
    WHERE EXISTS (SELECT 1 FROM knowledge_gaps g WHERE g.component_id = c.id AND g.resolved = 0)
    """,
)

_PHASE5_DDL: tuple[str, ...] = (
    """
    CREATE TABLE usage (
        id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
        project_id TEXT NOT NULL,
        refdes TEXT,
        occurrence_count INTEGER NOT NULL DEFAULT 0,
        workflow TEXT,
        recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE UNIQUE INDEX idx_usage ON usage(component_id, project_id)",
    """
    CREATE TABLE sourcing_snapshots (
        id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
        distributor TEXT NOT NULL,
        distributor_pn TEXT,
        stock INTEGER,
        moq INTEGER,
        price_breaks TEXT,
        lifecycle_note TEXT,
        snapshot_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX idx_sourcing ON sourcing_snapshots(component_id, distributor, snapshot_at DESC)",
    """
    CREATE TABLE substitutions (
        id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
        substitute_component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
        compatibility TEXT NOT NULL CHECK(compatibility IN ('drop-in','functional','partial')),
        differences TEXT,
        evidence_ref TEXT,
        confidence TEXT NOT NULL CHECK(confidence IN ('verified','unverified')) DEFAULT 'unverified'
    )
    """,
    "CREATE UNIQUE INDEX idx_subst ON substitutions(component_id, substitute_component_id)",
    # DD-9: knowledge_queue now reads real cross-project occurrence totals
    # from the usage table (Phase 3 shipped it with constant 0).
    # component_completeness keeps has_eda_asset=0 until Phase 6 rebuilds it
    # over eda_assets.
    "DROP VIEW knowledge_queue",
    """
    CREATE VIEW knowledge_queue AS
    SELECT
        component_id,
        canonical_key,
        mpn,
        occurrence_count,
        unresolved_gaps,
        CASE
            WHEN is_priority_prefix OR occurrence_count >= 8 THEN 'high'
            WHEN occurrence_count >= 3 THEN 'normal'
            ELSE 'low'
        END AS priority,
        CASE
            WHEN is_priority_prefix OR occurrence_count >= 8 THEN 0
            WHEN occurrence_count >= 3 THEN 1
            ELSE 2
        END AS priority_rank
    FROM (
        SELECT
            c.id AS component_id,
            c.canonical_key,
            c.mpn,
            COALESCE((SELECT SUM(u.occurrence_count) FROM usage u WHERE u.component_id = c.id), 0) AS occurrence_count,
            (SELECT COUNT(*) FROM knowledge_gaps g WHERE g.component_id = c.id AND g.resolved = 0) AS unresolved_gaps,
            (upper(c.mpn) LIKE 'MDBT%' OR upper(c.mpn) LIKE 'W25Q%'
             OR upper(c.mpn) LIKE 'STM%' OR upper(c.mpn) LIKE 'NRF%') AS is_priority_prefix
        FROM components c
        WHERE EXISTS (SELECT 1 FROM knowledge_gaps g WHERE g.component_id = c.id AND g.resolved = 0)
    )
    """,
)

_PHASE6_DDL: tuple[str, ...] = (
    """
    CREATE TABLE eda_assets (
        id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
        asset_kind TEXT NOT NULL CHECK(asset_kind IN ('kicad-symbol','kicad-footprint','3d-model')),
        library_ref TEXT NOT NULL,
        package_id INTEGER REFERENCES packages(id),
        verification_status TEXT NOT NULL CHECK(verification_status IN ('unverified','pin-checked','drc-passed')) DEFAULT 'unverified',
        verified_in TEXT,
        pin_map TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX idx_eda_component ON eda_assets(component_id, asset_kind)",
    """
    CREATE TABLE app_knowledge (
        id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
        knowledge_type TEXT NOT NULL CHECK(knowledge_type IN ('layout-rule','reference-circuit','companion-part','design-rule')),
        title TEXT NOT NULL,
        payload TEXT NOT NULL,
        companion_component_id INTEGER REFERENCES components(id),
        evidence_chunk_id INTEGER REFERENCES chunks(id),
        source_note TEXT,
        confidence TEXT NOT NULL CHECK(confidence IN ('verified','unverified')) DEFAULT 'unverified',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX idx_appk_component ON app_knowledge(component_id, knowledge_type)",
    # DD-9: component_completeness now reads real eda_assets coverage
    # (Phase 3 shipped it with has_eda_asset as constant 0).
    "DROP VIEW component_completeness",
    """
    CREATE VIEW component_completeness AS
    SELECT
        c.id AS component_id,
        c.canonical_key,
        c.mpn,
        EXISTS(SELECT 1 FROM pins p WHERE p.component_id = c.id) AS has_pinout,
        EXISTS(SELECT 1 FROM packages k WHERE k.component_id = c.id) AS has_package,
        EXISTS(SELECT 1 FROM spec_values s WHERE s.component_id = c.id) AS has_electrical,
        EXISTS(SELECT 1 FROM eda_assets e WHERE e.component_id = c.id) AS has_eda_asset,
        (SELECT COUNT(*) FROM knowledge_gaps g WHERE g.component_id = c.id AND g.resolved = 0) AS unresolved_gaps,
        (EXISTS(SELECT 1 FROM pins p WHERE p.component_id = c.id)
         + EXISTS(SELECT 1 FROM packages k WHERE k.component_id = c.id)
         + EXISTS(SELECT 1 FROM spec_values s WHERE s.component_id = c.id)
         + EXISTS(SELECT 1 FROM eda_assets e WHERE e.component_id = c.id)) AS extraction_score
    FROM components c
    """,
)

MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, statements=_PHASE1_DDL),
    Migration(version=2, statements=_PHASE2_DDL),
    Migration(version=3, statements=_PHASE3_DDL),
    Migration(version=4, statements=_PHASE5_DDL),
    Migration(version=5, statements=_PHASE6_DDL),
)

SCHEMA_VERSION = MIGRATIONS[-1].version


@dataclass(slots=True)
class ConsistencyReport:
    """VAULT-E004 semantics: non-fatal blob/DB gap report."""

    records_without_blobs: list[str] = field(default_factory=list)
    blobs_without_records: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.records_without_blobs and not self.blobs_without_records

    def summary(self) -> str:
        return (
            f"VAULT-E004: Blob/DB consistency gap: {len(self.records_without_blobs)} records without blobs, "
            f"{len(self.blobs_without_records)} blobs without records"
        )


@dataclass(slots=True)
class VaultStorage:
    vault_dir: Path
    db_path: Path
    conn: sqlite3.Connection

    def close(self) -> None:
        self.conn.close()


def resolve_vault_dir(explicit_path: str | Path | None = None) -> Path:
    """Resolve vault directory: env BODESIGN_VAULT_DIR, else explicit argument.

    No cwd guessing. Missing or unwritable -> VAULT-E002.
    """
    raw = os.environ.get(VAULT_DIR_ENV) or explicit_path
    if not raw:
        raise VaultStorageError(
            "VAULT-E002",
            f"Vault directory is not writable: no directory configured (set {VAULT_DIR_ENV} or pass an explicit path)",
        )
    vault_dir = Path(raw)
    try:
        vault_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise VaultStorageError("VAULT-E002", f"Vault directory is not writable: {vault_dir} ({error})") from error
    if not vault_dir.is_dir() or not os.access(vault_dir, os.W_OK):
        raise VaultStorageError("VAULT-E002", f"Vault directory is not writable: {vault_dir}")
    return vault_dir


def apply_migrations(conn: sqlite3.Connection, db_path: Path) -> None:
    """Apply pending migrations keyed by PRAGMA user_version, in a transaction."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise VaultStorageError("VAULT-E003", f"Schema version mismatch: db={current} expected={SCHEMA_VERSION}")
    pending = [migration for migration in MIGRATIONS if migration.version > current]
    if not pending:
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        for migration in pending:
            for statement in migration.statements:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {int(migration.version)}")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def open_vault(explicit_path: str | Path | None = None) -> VaultStorage:
    """Open (or initialize) the vault database.

    - New DB file: initialize schema via migrations.
    - Existing DB file: integrity-check first; corrupt/unreadable raises
      VAULT-E001 and the file is NEVER overwritten or recreated.
    """
    vault_dir = resolve_vault_dir(explicit_path)
    db_path = vault_dir / DB_FILENAME
    existed = db_path.exists()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        if existed:
            try:
                result = conn.execute("PRAGMA quick_check").fetchone()[0]
            except sqlite3.DatabaseError as error:
                raise VaultStorageError(
                    "VAULT-E001", f"Vault database is corrupted or unreadable: {db_path} ({error})"
                ) from error
            if result != "ok":
                raise VaultStorageError(
                    "VAULT-E001", f"Vault database is corrupted or unreadable: {db_path} (quick_check: {result})"
                )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        apply_migrations(conn, db_path)
    except BaseException:
        conn.close()
        raise
    return VaultStorage(vault_dir=vault_dir, db_path=db_path, conn=conn)


def blob_relative_path(sha256_hex: str, extension: str) -> str:
    safe_extension = extension.lower().lstrip(".") or "bin"
    return f"{BLOB_DIR_NAME}/{sha256_hex[:2]}/{sha256_hex}.{safe_extension}"


def write_blob(vault_dir: Path, source_path: Path) -> tuple[str, str]:
    """Write a file into the content-addressed blob store.

    Layout: <vault_dir>/blobs/<sha256[0:2]>/<sha256>.<ext>. Returns
    (sha256, relative_path). Dedup: existing blob is never rewritten.
    Write is temp-file + atomic rename. Must be called BEFORE the DB
    transaction commits (DD-6 ordering). OS failures -> VAULT-E203.
    """
    try:
        digest = hashlib.sha256()
        with source_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
        sha256_hex = digest.hexdigest()
        relative_path = blob_relative_path(sha256_hex, source_path.suffix)
        target = vault_dir / relative_path
        if target.exists():
            return sha256_hex, relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target.with_name(target.name + ".tmp")
        with source_path.open("rb") as stream, temp_path.open("wb") as out:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp_path, target)
    except OSError as error:
        raise VaultStorageError("VAULT-E203", f"Blob write failed before DB commit: {error}") from error
    return sha256_hex, relative_path


def consistency_scan(storage: VaultStorage) -> ConsistencyReport:
    """Startup scan comparing documents.blob_path records against blob files.

    Non-fatal (VAULT-E004 semantics): returns the gap report; the service
    keeps running and gap components answer absent with a gap note.
    """
    report = ConsistencyReport()
    recorded_paths: set[str] = set()
    for row in storage.conn.execute("SELECT blob_path FROM documents"):
        blob_path = row["blob_path"]
        recorded_paths.add(blob_path)
        if not (storage.vault_dir / blob_path).is_file():
            report.records_without_blobs.append(blob_path)
    blob_root = storage.vault_dir / BLOB_DIR_NAME
    if blob_root.is_dir():
        for blob_file in sorted(blob_root.rglob("*")):
            if not blob_file.is_file() or blob_file.suffix == ".tmp":
                continue
            relative = blob_file.relative_to(storage.vault_dir).as_posix()
            if relative not in recorded_paths:
                report.blobs_without_records.append(relative)
    return report
