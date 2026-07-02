"""WebDAV class-2 protocol helpers for the deliverable-cache mount
(plan mcp_r13-landing-webdav-cache, DD-4 — ported from docxmcp bin/_webdav.py).

This module is deliberately **pure + HTTP-agnostic**: it turns a token's
file listing into WebDAV wire artefacts (PROPFIND 207 multistatus XML,
OPTIONS headers, lock tokens) without importing Starlette or touching a
socket. That keeps the protocol logic unit-testable in isolation; the
async request handlers in ``server.py`` are then thin adapters that
(1) authenticate + owner-check, (2) call the store, (3) call these
composers.

WebDAV surface targeted (enough for davfs2 / rclone / Finder to mount a
token as a normal folder):

  OPTIONS   -> advertise ``DAV: 1, 2`` + Allow
  PROPFIND  -> 207 multistatus, Depth 0 (self) / 1 (self + children)
  GET/PUT   -> read/write one file inside the token dir
  DELETE    -> delete one file (or a collection)
  MKCOL     -> store.mkdir
  MOVE/COPY -> store.move / store.copy
  LOCK      -> in-memory lock table (class 2), opaque locktoken + TTL
  UNLOCK    -> drop the lock

The href space a client sees is ``<mount_prefix>/<rel>`` where
``mount_prefix`` is ``/dav/{token}``; the collection root maps to the
token dir and each descendant file to its ``rel``.
"""
from __future__ import annotations

import dataclasses
import secrets
import threading
import time
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape as _xml_escape

# ── constants ───────────────────────────────────────────────────────────

DAV_COMPLIANCE = "1, 2"
# Methods a client may issue against a mounted token. OPTIONS advertises
# this so davfs2 knows the collection is class-2 (LOCK-capable).
ALLOWED_METHODS = (
    "OPTIONS", "PROPFIND", "GET", "HEAD", "PUT", "DELETE",
    "MKCOL", "MOVE", "COPY", "LOCK", "UNLOCK",
)

# RFC 4918 uses ISO-8601 for creationdate and RFC 1123 for getlastmodified.
_RFC1123 = "%a, %d %b %Y %H:%M:%S GMT"
_ISO8601 = "%Y-%m-%dT%H:%M:%SZ"

# Default lock lifetime when a client sends `Timeout: Infinite` or omits it.
DEFAULT_LOCK_TTL_SECONDS = 3600
MAX_LOCK_TTL_SECONDS = 24 * 3600


def _fmt_rfc1123(ts: float) -> str:
    return time.strftime(_RFC1123, time.gmtime(ts))


def _fmt_iso8601(ts: float) -> str:
    return time.strftime(_ISO8601, time.gmtime(ts))


# ── PROPFIND resource model ─────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class DavResource:
    """One WebDAV resource line for a multistatus response.

    href is the full client-visible path (mount_prefix + rel, already
    percent-safe-ish — callers pass rels that came from the filesystem).
    is_collection distinguishes a directory (token root / subdir) from a
    file. size/mtime/ctime feed the DAV: live properties.
    """
    href: str
    is_collection: bool
    size: int = 0
    mtime: float = 0.0
    ctime: float = 0.0
    display_name: str = ""


class PropfindNotFound(Exception):
    """The PROPFIND target rel does not exist under the token dir → 404."""


def _resource_for(prefix: str, dir_path: Path, rel: str, meta_name: str) -> DavResource:
    """Build a DavResource for one existing path (``rel``) under ``dir_path``."""
    target = (dir_path / rel) if rel else dir_path
    st = target.stat()
    is_dir = target.is_dir()
    href = prefix if not rel else f"{prefix}/{rel}"
    if is_dir:
        href = href.rstrip("/") + "/"
    name = target.name if rel else ""
    return DavResource(
        href=href,
        is_collection=is_dir,
        size=0 if is_dir else st.st_size,
        mtime=st.st_mtime,
        ctime=st.st_ctime,
        display_name=name,
    )


def build_propfind(
    mount_prefix: str,
    dir_path: Path,
    rel: str,
    depth: str,
    *,
    meta_name: str = ".bodesign-meta.json",
) -> list[DavResource]:
    """Compose the DavResource list for a PROPFIND, honouring the target ``rel``
    and scanning the real filesystem (so MKCOL-created empty dirs show up).

    ``mount_prefix`` = ``/dav/{token}`` (no trailing slash).
    ``dir_path`` = the token's directory on disk.
    ``rel`` = the path inside the mount the client asked about ("" = root).
    ``depth`` = "0" (target only) or "1" (target + immediate members).

    Semantics (RFC 4918 §9.1):
      * rel names a FILE  -> just that file (depth ignored; a file has no members).
      * rel names a DIR   -> the dir itself, plus its immediate children when
        depth=="1" (NOT recursive — that is depth infinity, which we cap to 1).
      * rel does not exist -> PropfindNotFound (handler maps to 404). This is
        what lets a client probe "does body.md exist?" before a PUT.
    The sidecar meta file is never surfaced.
    """
    prefix = mount_prefix.rstrip("/")
    rel = rel.strip("/")
    target = (dir_path / rel) if rel else dir_path
    if not target.exists():
        raise PropfindNotFound(rel)

    self_res = _resource_for(prefix, dir_path, rel, meta_name)
    out: list[DavResource] = [self_res]
    # Only a collection has members; a file (or depth 0) returns just itself.
    if not self_res.is_collection or depth == "0":
        return out

    for child in sorted(target.iterdir(), key=lambda p: p.name):
        if child.name == meta_name:
            continue
        child_rel = f"{rel}/{child.name}" if rel else child.name
        out.append(_resource_for(prefix, dir_path, child_rel, meta_name))
    return out


def _prop_block(res: DavResource) -> str:
    """The <D:prop> body for one resource's 200 propstat."""
    name = _xml_escape(res.display_name)
    if res.is_collection:
        restype = "<D:resourcetype><D:collection/></D:resourcetype>"
        # Collections omit getcontentlength (davfs tolerates either; we omit).
        length = ""
        ctype = ""
    else:
        restype = "<D:resourcetype/>"
        length = f"<D:getcontentlength>{res.size}</D:getcontentlength>"
        ctype = "<D:getcontenttype>application/octet-stream</D:getcontenttype>"
    return (
        "<D:prop>"
        f"<D:displayname>{name}</D:displayname>"
        f"{restype}"
        f"{length}"
        f"{ctype}"
        f"<D:getlastmodified>{_fmt_rfc1123(res.mtime)}</D:getlastmodified>"
        f"<D:creationdate>{_fmt_iso8601(res.ctime)}</D:creationdate>"
        "<D:supportedlock>"
        "<D:lockentry><D:lockscope><D:exclusive/></D:lockscope>"
        "<D:locktype><D:write/></D:locktype></D:lockentry>"
        "</D:supportedlock>"
        "</D:prop>"
    )


def multistatus_xml(resources: list[DavResource]) -> str:
    """Render a 207 Multistatus body for a PROPFIND (RFC 4918 §9.1)."""
    responses = []
    for res in resources:
        responses.append(
            "<D:response>"
            f"<D:href>{_xml_escape(res.href)}</D:href>"
            "<D:propstat>"
            f"{_prop_block(res)}"
            "<D:status>HTTP/1.1 200 OK</D:status>"
            "</D:propstat>"
            "</D:response>"
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<D:multistatus xmlns:D="DAV:">'
        + "".join(responses)
        + "</D:multistatus>"
    )


def options_headers() -> dict[str, str]:
    """Response headers for an OPTIONS on a mounted collection."""
    return {
        "DAV": DAV_COMPLIANCE,
        "Allow": ", ".join(ALLOWED_METHODS),
        "MS-Author-Via": "DAV",
        "Content-Length": "0",
    }


def normalise_depth(raw: Optional[str]) -> str:
    """Map a Depth header to '0' or '1' ('infinity' -> '1', default '1')."""
    if raw is None:
        return "1"
    v = raw.strip().lower()
    if v == "0":
        return "0"
    return "1"


def parse_timeout_header(raw: Optional[str]) -> int:
    """Parse a WebDAV ``Timeout`` header into a bounded TTL in seconds.

    Accepts ``Second-600`` / ``Infinite`` / comma lists (first wins).
    Unknown / infinite -> DEFAULT; everything is capped at MAX.
    """
    if not raw:
        return DEFAULT_LOCK_TTL_SECONDS
    first = raw.split(",")[0].strip().lower()
    if first.startswith("second-"):
        try:
            secs = int(first[len("second-"):])
        except ValueError:
            return DEFAULT_LOCK_TTL_SECONDS
        return max(1, min(secs, MAX_LOCK_TTL_SECONDS))
    # "infinite" or anything else
    return DEFAULT_LOCK_TTL_SECONDS


# ── lock table (class-2) ────────────────────────────────────────────────

@dataclasses.dataclass
class Lock:
    token: str          # opaque locktoken, "opaquelocktoken:<hex>"
    resource: str       # "{token}/{rel}" key the lock guards
    owner: str          # owner_identity that holds it
    depth: str          # "0" | "infinity"
    expires_at: float

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at


class LockTable:
    """In-memory WebDAV lock registry (class-2, exclusive write locks).

    Keyed by ``"{token}/{rel}"``. Locks carry a TTL; an expired lock is
    treated as absent (lazy sweep on access). This is intentionally
    process-local: on restart every lock is gone and a well-behaved
    client simply re-LOCKs. Never blocks the owner that holds the lock —
    only *other* identities are refused (423).
    """

    def __init__(self) -> None:
        self._locks: dict[str, Lock] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _key(token: str, rel: str) -> str:
        return f"{token}/{rel.strip('/')}"

    def acquire(
        self,
        token: str,
        rel: str,
        owner: str,
        *,
        depth: str = "0",
        ttl: int = DEFAULT_LOCK_TTL_SECONDS,
    ) -> Optional[Lock]:
        """Acquire an exclusive lock. Returns the Lock on success, or None
        if a live lock held by someone else already guards the resource."""
        key = self._key(token, rel)
        now = time.time()
        with self._lock:
            existing = self._locks.get(key)
            if existing and not existing.is_expired(now):
                if existing.owner != owner:
                    return None
                # Same owner re-locking: refresh TTL, keep the token.
                existing.expires_at = now + ttl
                return existing
            lock = Lock(
                token=f"opaquelocktoken:{secrets.token_hex(16)}",
                resource=key,
                owner=owner,
                depth=depth,
                expires_at=now + ttl,
            )
            self._locks[key] = lock
            return lock

    def check(self, token: str, rel: str, owner: str) -> Optional[Lock]:
        """Return a *blocking* lock (live, held by someone else) or None.

        None means the caller ``owner`` may write ``rel`` — either no lock,
        an expired one, or a lock they themselves hold.
        """
        key = self._key(token, rel)
        now = time.time()
        with self._lock:
            existing = self._locks.get(key)
            if existing is None:
                return None
            if existing.is_expired(now):
                self._locks.pop(key, None)
                return None
            if existing.owner == owner:
                return None
            return existing

    def release(self, token: str, rel: str, locktoken: str) -> bool:
        """UNLOCK: drop the lock iff the presented locktoken matches.
        Returns True if a lock was removed."""
        key = self._key(token, rel)
        with self._lock:
            existing = self._locks.get(key)
            if existing is not None and existing.token == locktoken:
                self._locks.pop(key, None)
                return True
        return False

    def lockdiscovery_xml(self, lock: Lock) -> str:
        """The <D:prop><D:lockdiscovery> body returned by a LOCK response."""
        timeout_secs = max(0, int(lock.expires_at - time.time()))
        return (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<D:prop xmlns:D="DAV:"><D:lockdiscovery><D:activelock>'
            "<D:locktype><D:write/></D:locktype>"
            "<D:lockscope><D:exclusive/></D:lockscope>"
            f"<D:depth>{_xml_escape(lock.depth)}</D:depth>"
            f"<D:owner>{_xml_escape(lock.owner)}</D:owner>"
            f"<D:timeout>Second-{timeout_secs}</D:timeout>"
            "<D:locktoken>"
            f"<D:href>{_xml_escape(lock.token)}</D:href>"
            "</D:locktoken>"
            "</D:activelock></D:lockdiscovery></D:prop>"
        )
