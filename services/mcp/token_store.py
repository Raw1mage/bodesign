"""Token file store (G11a) — docxmcp-style client-tree ingest over the file API.

A token names a directory (``doc_dir``) that holds an uploaded/staged file tree.
The whole project tree is uploaded as a tarball (or staged inline) into a fresh
token namespace; tools then operate inside ``doc_dir`` and produced files are
fetched back by ``{token}/blob/{rel}``. No host data bind mount required — this
is the portable/container path (the local same-host case can still use host
paths directly).

Traversal-defended: tar members and staged relpaths that escape the token dir
are rejected.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import shutil
import tarfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

_log = logging.getLogger("bodesign.token_store")

KIND_EPHEMERAL = "ephemeral"
KIND_DELIVERABLE_CACHE = "deliverable-cache"

_META_SUFFIX = ".meta.json"


def _ttl_seconds() -> int:
    """Token-dir TTL; 0/negative disables GC. Default 1h (docxmcp-style)."""
    try:
        return int(os.environ.get("BODESIGN_TOKEN_TTL_SECONDS", "3600"))
    except ValueError:
        return 3600


def _safety_net_ttl_seconds() -> int:
    """Deliverable-cache safety-net TTL (DD-7); 0/negative disables. Default 7d."""
    try:
        return int(os.environ.get("BODESIGN_CACHE_SAFETY_TTL_SECONDS", str(7 * 24 * 3600)))
    except ValueError:
        return 7 * 24 * 3600


def _safety_net_warn_seconds() -> int:
    """Warn-first window before the safety-net floor. Default 1d."""
    try:
        return int(os.environ.get("BODESIGN_CACHE_SAFETY_WARN_SECONDS", str(24 * 3600)))
    except ValueError:
        return 24 * 3600


class TokenError(Exception):
    pass


class TokenNotFoundError(TokenError):
    pass


class StoreOpError(TokenError):
    """Typed store operation failure carrying a machine-readable code
    (e.g. MKCOL_NOT_DIR, MOVE_SRC_MISSING, CACHE_META_CORRUPT)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class CacheMeta:
    """Sidecar record for a deliverable-cache token (DD-5/DD-7).

    Persisted as ``<token>.meta.json`` next to the token dir so it survives
    restart; the filesystem is the source of truth (no in-memory registry,
    matching the rest of this store).
    """
    token: str
    kind: str
    owner_identity: str
    subject_id: str
    created_at: float
    last_used_at: float
    last_export_at: Optional[float] = None


def sessions_root() -> Path:
    root = Path(os.environ.get("BODESIGN_SESSIONS_ROOT",
                               str(Path(__file__).resolve().parents[2] / ".run" / "sessions")))
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass(slots=True)
class TokenStore:
    root: Path

    def reap(self) -> int:
        """Class-aware GC (DD-7): ephemeral token dirs keep the mtime-LRU TTL
        exactly as before; deliverable-caches are exempt from idle reap and only
        fall to the long safety-net floor (warn-first). Returns total removed."""
        return self._reap_ephemeral() + self.reap_safety_net()

    def _reap_ephemeral(self) -> int:
        """Today's TTL/LRU reap, restricted to ephemeral tokens (no sidecar
        deliverable-cache meta)."""
        ttl = _ttl_seconds()
        if ttl <= 0:
            return 0
        cutoff = time.time() - ttl
        removed = 0
        for d in self.root.glob("tok_*"):
            try:
                if not d.is_dir() or d.stat().st_mtime >= cutoff:
                    continue
                meta_path = self._meta_path(d.name)
                if meta_path.exists():
                    continue  # deliverable-cache: governed by safety-net, not idle reap
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
            except OSError:
                pass
        return removed

    def reap_safety_net(self) -> int:
        """Safety-net floor for deliverable-caches: warn inside the window
        (``reaper_safety_net_warn``), reclaim only past the full TTL.
        Reactivation (resolve/touch bumps dir mtime or last_used_at) resets the
        clock. Returns count reclaimed."""
        ttl = _safety_net_ttl_seconds()
        if ttl <= 0:
            return 0
        warn_window = _safety_net_warn_seconds()
        now = time.time()
        removed = 0
        for meta_path in self.root.glob(f"tok_*{_META_SUFFIX}"):
            meta = self._parse_meta(meta_path)
            if meta.kind != KIND_DELIVERABLE_CACHE:
                continue
            d = self.root / meta.token
            if not d.is_dir():
                _log.info("reaper_orphan_meta_removed token=%s", meta.token)
                meta_path.unlink(missing_ok=True)
                continue
            try:
                effective = max(meta.last_used_at, d.stat().st_mtime)
            except OSError:
                continue
            idle = now - effective
            if idle >= ttl:
                shutil.rmtree(d, ignore_errors=True)
                meta_path.unlink(missing_ok=True)
                removed += 1
                _log.info(
                    "reaper_safety_net_reap token=%s owner=%s subject=%s idle_s=%.0f",
                    meta.token, meta.owner_identity, meta.subject_id, idle,
                )
            elif idle >= ttl - warn_window:
                _log.warning(
                    "reaper_safety_net_warn token=%s owner=%s subject=%s idle_s=%.0f ttl_s=%d",
                    meta.token, meta.owner_identity, meta.subject_id, idle, ttl,
                )
        return removed

    def new_token(self) -> tuple[str, Path]:
        self.reap()  # opportunistic GC on each new session
        token = "tok_" + uuid.uuid4().hex[:16]
        doc_dir = self.root / token
        doc_dir.mkdir(parents=True, exist_ok=True)
        return token, doc_dir

    def resolve(self, token: str) -> Path:
        doc_dir = (self.root / token)
        if not token.startswith("tok_") or not doc_dir.is_dir():
            raise TokenNotFoundError(f"token not found: {token}")
        try:
            os.utime(doc_dir, None)  # touch → keep active tokens alive (LRU)
        except OSError:
            pass
        return doc_dir.resolve()

    def safe_join(self, doc_dir: Path, rel: str) -> Path:
        root = doc_dir.resolve()
        target = (root / rel.lstrip("/")).resolve()
        target.relative_to(root)  # raises ValueError on escape
        return target

    def list_files(self, doc_dir: Path) -> list[str]:
        root = doc_dir.resolve()
        return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())

    # ── ingest paths ────────────────────────────────────────────────
    def stage_tarball(self, data: bytes, gz: bool = False) -> dict:
        token, doc_dir = self.new_token()
        root = doc_dir.resolve()
        mode = "r:gz" if gz else "r:*"
        with tarfile.open(fileobj=io.BytesIO(data), mode=mode) as tar:
            for member in tar.getmembers():
                if not (member.isfile() or member.isdir()):
                    continue
                dest = (root / member.name.lstrip("/")).resolve()
                try:
                    dest.relative_to(root)
                except ValueError:
                    raise TokenError(f"tar member escapes token dir: {member.name}")
            tar.extractall(root, filter="data")
        return {"token": token, "doc_dir": str(root), "files": self.list_files(root)}

    def stage_raw(self, data: bytes, filename: str = "upload.bin") -> dict:
        token, doc_dir = self.new_token()
        target = self.safe_join(doc_dir, filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {"token": token, "doc_dir": str(doc_dir.resolve()), "files": self.list_files(doc_dir)}

    def stage_files(self, files: dict) -> dict:
        token, doc_dir = self.new_token()
        for rel, spec in (files or {}).items():
            target = self.safe_join(doc_dir, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = spec.get("content", "") if isinstance(spec, dict) else str(spec)
            encoding = spec.get("encoding", "utf-8") if isinstance(spec, dict) else "utf-8"
            if encoding == "base64":
                target.write_bytes(base64.b64decode(content))
            else:
                target.write_text(content, encoding="utf-8")
        return {"token": token, "doc_dir": str(doc_dir.resolve()), "files": self.list_files(doc_dir)}

    # ── deliverable-cache metadata (DD-5/DD-7, task 4.1) ────────────

    def _meta_path(self, token: str) -> Path:
        return self.root / (token + _META_SUFFIX)

    @staticmethod
    def _parse_meta(meta_path: Path) -> CacheMeta:
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            return CacheMeta(**data)
        except (OSError, ValueError, TypeError) as exc:
            raise StoreOpError(
                "CACHE_META_CORRUPT", f"unreadable cache sidecar {meta_path.name}: {exc}"
            ) from exc

    def _write_meta(self, meta: CacheMeta) -> None:
        self._meta_path(meta.token).write_text(
            json.dumps(asdict(meta), indent=1), encoding="utf-8")

    def cache_meta(self, token: str) -> CacheMeta:
        """Load the sidecar record for ``token``; TokenNotFoundError if the
        token dir or its meta is absent (already reaped / not a cache)."""
        self.resolve(token)  # raises TokenNotFoundError; touches (reactivation)
        meta_path = self._meta_path(token)
        if not meta_path.exists():
            raise TokenNotFoundError(f"no deliverable-cache metadata for token: {token}")
        return self._parse_meta(meta_path)

    def provision_cache(self, owner_identity: str, subject_id: str) -> CacheMeta:
        """Find-or-mint, idempotent per (owner_identity, subject_id) (DD-5).
        Empty owner/subject is a hard error — never a shared/default cache."""
        if not owner_identity or not isinstance(owner_identity, str):
            raise StoreOpError("CACHE_OWNER_REQUIRED",
                               "provision_cache requires a non-empty owner_identity")
        if not subject_id or not isinstance(subject_id, str):
            raise StoreOpError("CACHE_SUBJECT_REQUIRED",
                               "provision_cache requires a non-empty subject_id")
        for meta_path in self.root.glob(f"tok_*{_META_SUFFIX}"):
            meta = self._parse_meta(meta_path)
            if (meta.kind == KIND_DELIVERABLE_CACHE
                    and meta.owner_identity == owner_identity
                    and meta.subject_id == subject_id
                    and (self.root / meta.token).is_dir()):
                meta.last_used_at = time.time()
                self._write_meta(meta)
                _log.info("cache_provision_idempotent token=%s owner=%s subject=%s",
                          meta.token, owner_identity, subject_id)
                return meta
        token, _ = self.new_token()
        now = time.time()
        meta = CacheMeta(token=token, kind=KIND_DELIVERABLE_CACHE,
                         owner_identity=owner_identity, subject_id=subject_id,
                         created_at=now, last_used_at=now, last_export_at=None)
        self._write_meta(meta)
        _log.info("cache_provisioned token=%s owner=%s subject=%s",
                  token, owner_identity, subject_id)
        return meta

    def cache_dirty_files(self, token: str) -> list[str]:
        """Rel paths modified since last export; last_export_at=None → every
        file counts as dirty (never exported)."""
        meta = self.cache_meta(token)
        root = (self.root / token).resolve()
        ref = meta.last_export_at
        out = []
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            if ref is None or p.stat().st_mtime > ref:
                out.append(str(p.relative_to(root)))
        return out

    def is_cache_clean(self, token: str) -> bool:
        """True iff no file mtime is newer than last_export_at (close gate)."""
        return not self.cache_dirty_files(token)

    def mark_exported(self, token: str) -> CacheMeta:
        """Stamp last_export_at=now (tree clean relative to this point)."""
        meta = self.cache_meta(token)
        now = time.time()
        meta.last_export_at = now
        meta.last_used_at = now
        self._write_meta(meta)
        _log.info("cache_exported token=%s owner=%s subject=%s at=%.0f",
                  meta.token, meta.owner_identity, meta.subject_id, now)
        return meta

    def touch_cache(self, token: str) -> CacheMeta:
        """Reactivation: bump last_used_at (resets the safety-net clock)."""
        meta = self.cache_meta(token)
        meta.last_used_at = time.time()
        self._write_meta(meta)
        return meta

    # ── WebDAV structure helpers: MKCOL / MOVE / COPY (task 4.2) ────
    #
    # Every path routes through safe_join, so a `../escape` rel raises the
    # same ValueError the store already uses for traversal rejection.

    def mkdir(self, token: str, rel: str) -> Path:
        """Create a directory at ``rel`` (WebDAV MKCOL). Parents created;
        idempotent. A file at that path → StoreOpError('MKCOL_NOT_DIR')."""
        doc_dir = self.resolve(token)
        target = self.safe_join(doc_dir, rel)
        if target.exists() and not target.is_dir():
            raise StoreOpError("MKCOL_NOT_DIR",
                               f"cannot MKCOL {rel!r}: a file already exists at that path")
        target.mkdir(parents=True, exist_ok=True)
        _log.info("session_mkdir token=%s rel=%s", token, rel)
        return target

    @staticmethod
    def _clear_dest(dst_path: Path, rel: str, *, overwrite: bool, code_prefix: str) -> bool:
        """Shared MOVE/COPY destination handling. Returns True iff the
        destination is NEW (did not exist) — DAV maps new→201, overwrite→204."""
        if not dst_path.exists():
            return True
        if not overwrite:
            raise StoreOpError(f"{code_prefix}_DEST_EXISTS",
                               f"destination already exists: {rel!r} (overwrite=False)")
        if dst_path.is_dir():
            shutil.rmtree(dst_path, ignore_errors=True)
        else:
            dst_path.unlink(missing_ok=True)
        return False

    def move(self, token: str, src: str, dst: str, *, overwrite: bool = True) -> tuple[Path, bool]:
        """Rename ``src`` → ``dst`` inside the token dir (WebDAV MOVE). Atomic
        (os.replace). Returns (new_path, created) — created=False means an
        existing destination was overwritten."""
        doc_dir = self.resolve(token)
        src_path = self.safe_join(doc_dir, src)
        dst_path = self.safe_join(doc_dir, dst)
        if not src_path.exists():
            raise StoreOpError("MOVE_SRC_MISSING", f"MOVE source not found: {src!r}")
        created = self._clear_dest(dst_path, dst, overwrite=overwrite, code_prefix="MOVE")
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src_path, dst_path)
        _log.info("session_move token=%s src=%s dst=%s created=%s", token, src, dst, created)
        return dst_path, created

    def copy(self, token: str, src: str, dst: str, *, overwrite: bool = True) -> tuple[Path, bool]:
        """Copy ``src`` → ``dst`` inside the token dir (WebDAV COPY); source is
        preserved (copy2/copytree). Same overwrite semantics as move; returns
        (new_path, created)."""
        doc_dir = self.resolve(token)
        src_path = self.safe_join(doc_dir, src)
        dst_path = self.safe_join(doc_dir, dst)
        if not src_path.exists():
            raise StoreOpError("COPY_SRC_MISSING", f"COPY source not found: {src!r}")
        created = self._clear_dest(dst_path, dst, overwrite=overwrite, code_prefix="COPY")
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.is_dir():
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)
        _log.info("session_copy token=%s src=%s dst=%s created=%s", token, src, dst, created)
        return dst_path, created


def default_store() -> TokenStore:
    return TokenStore(root=sessions_root())
