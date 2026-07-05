"""Basic-auth identity + per-owner WebDAV credential store for the
deliverable-cache mount (plan mcp_r13-landing-webdav-cache, DD-6 — ported
from docxmcp bin/_auth_provider.py, Basic-auth-only首發).

One identity path resolves a request to an ``owner_identity`` (the
multi-tenant key a deliverable-cache is bound to): **Basic auth** — the
path real WebDAV mount clients (davfs2 / rclone / macOS Finder) use.
They send ``Authorization: Basic base64(username:password)``; bodesign
mints a per-owner long-lived WebDAV credential at provision time and
this verifies it (constant-time).

No-silent-fallback (天條): every failure raises ``AuthError`` → typed
401. We NEVER fall back to a default / first / global-active identity.
An unknown owner is an error, never a shared cache.

The ``AuthProvider`` base class keeps identity resolution pluggable so
a differently-fronted deployment can swap the impl without touching the
WebDAV layer.
"""
from __future__ import annotations

import base64
import binascii
import dataclasses
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Optional

_log = logging.getLogger("bodesign.auth")

_PBKDF2_ROUNDS = 200_000
_WEBDAV_TOKEN_BYTES = 24  # 192-bit password


def _default_cred_path() -> str:
    """Credential file location: ``BODESIGN_WEBDAV_CRED_PATH`` or a dotfile
    sibling INSIDE the sessions root (DD-6). The token-store reaper only
    globs ``tok_*`` entries, so a dotfile in the sessions root is never
    scanned or reclaimed — it persists on the ``bodesign-sessions`` volume.
    """
    explicit = os.environ.get("BODESIGN_WEBDAV_CRED_PATH")
    if explicit:
        return explicit
    from token_store import sessions_root
    return str(sessions_root() / ".webdav-creds.json")


class AuthError(Exception):
    """Identity resolution failed. `code` is a stable envelope surface.

    Callers map this to HTTP 401 with a ``WWW-Authenticate`` challenge.
    Never swallow into a fallback identity (天條).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message)
        self.code = code
        self.message = message


@dataclasses.dataclass(frozen=True)
class Identity:
    owner_identity: str          # the multi-tenant key (== Basic username)
    method: str                  # "basic" — how it was proven, for audit


# ── per-owner WebDAV credential store ───────────────────────────────────

class WebDavCredentialStore:
    """Persistent per-owner WebDAV Basic-auth credentials.

    bodesign mints a long-lived random password per owner_identity at
    provision time; WebDAV mount clients authenticate with it. Only the
    PBKDF2 hash + salt are stored — never the plaintext. Verification is
    constant-time.
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = Path(path or _default_cred_path())
        self._lock = threading.RLock()
        self._creds: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                self._creds = {k: v for k, v in data.items() if isinstance(v, dict)}
        except json.JSONDecodeError:
            _log.warning("webdav_cred_store_corrupt path=%s (starting empty)", self._path)

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + f".tmp-{secrets.token_hex(4)}")
        tmp.write_text(json.dumps(self._creds), encoding="utf-8")
        os.replace(tmp, self._path)
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _hash(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)

    def issue(self, owner_identity: str) -> str:
        """Mint (or rotate) the owner's WebDAV password; return plaintext ONCE."""
        if not owner_identity:
            raise AuthError("AUTH_NO_OWNER", "issue requires a non-empty owner_identity")
        password = secrets.token_urlsafe(_WEBDAV_TOKEN_BYTES)
        salt = secrets.token_bytes(16)
        with self._lock:
            self._creds[owner_identity] = {
                "salt": base64.b64encode(salt).decode("ascii"),
                "hash": base64.b64encode(self._hash(password, salt)).decode("ascii"),
                "issued_at": str(time.time()),
            }
            self._persist()
        _log.info("webdav_cred_issued owner=%s", owner_identity)
        return password

    def verify(self, owner_identity: str, password: str) -> bool:
        """Constant-time verify. Missing owner still runs a dummy hash so
        timing doesn't reveal owner existence."""
        with self._lock:
            rec = self._creds.get(owner_identity)
        salt = base64.b64decode(rec["salt"]) if rec else secrets.token_bytes(16)
        expected = base64.b64decode(rec["hash"]) if rec else b"\x00" * 32
        got = self._hash(password or "", salt)
        ok = hmac.compare_digest(expected, got)
        return bool(rec) and ok

    def revoke(self, owner_identity: str) -> bool:
        with self._lock:
            existed = self._creds.pop(owner_identity, None) is not None
            if existed:
                self._persist()
        if existed:
            _log.info("webdav_cred_revoked owner=%s", owner_identity)
        return existed


# ── AuthProvider base + builtin (Basic-only) impl ───────────────────────

class AuthProvider:
    """Resolve a request to an Identity + adjudicate ownership.

    The WebDAV layer depends only on this interface, never on a specific
    identity backend — so the impl can be swapped without touching routes.
    """

    def resolve_identity(
        self, *, auth_header: Optional[str], cookies: dict[str, str]
    ) -> Identity:
        raise NotImplementedError

    def owns(self, identity: Identity, owner_identity: str) -> bool:
        """True iff `identity` owns a cache tagged with `owner_identity`.

        The multi-tenant isolation boundary. Never returns a constant True
        (that would collapse isolation)."""
        return bool(identity.owner_identity) and identity.owner_identity == owner_identity


class BuiltinAuthProvider(AuthProvider):
    """Standalone Basic-auth identity (DD-6: Basic-auth-only 首發).

    Supports ONLY the Basic-auth path, backed entirely by the built-in
    ``WebDavCredentialStore``: bodesign mints a per-owner WebDAV credential
    at provision time and this verifies it (constant-time). There is
    deliberately NO cookie path and NO fallback identity (天條) — an
    unknown owner is a typed 401, never a shared/default cache.
    """

    def __init__(self, credential_store: Optional[WebDavCredentialStore] = None) -> None:
        self._creds = credential_store or WebDavCredentialStore()

    @property
    def credentials(self) -> WebDavCredentialStore:
        return self._creds

    def resolve_identity(
        self, *, auth_header: Optional[str], cookies: dict[str, str]
    ) -> Identity:
        # Basic auth is the ONLY path. A cookie is ignored — its presence
        # never grants access; absent Basic credentials fail closed.
        if auth_header and auth_header.lower().startswith("basic "):
            try:
                decoded = base64.b64decode(auth_header[6:].strip()).decode("utf-8")
            except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
                raise AuthError("AUTH_BASIC_MALFORMED", f"bad Basic header: {exc}") from exc
            username, sep, password = decoded.partition(":")
            if not sep or not username:
                raise AuthError("AUTH_BASIC_MALFORMED", "Basic auth needs username:password")
            if not self._creds.verify(username, password):
                raise AuthError("AUTH_BASIC_REJECTED", "invalid WebDAV credential")
            return Identity(owner_identity=username, method="basic")

        raise AuthError(
            "AUTH_REQUIRED",
            "no Basic auth present; a WebDAV credential is required",
        )


# ── per-host provision state (fleet standard R14.5) ────────────────────

def host_provision_state() -> dict:
    """Explicit per-host WebDAV provision state (fleet standard R14.5,
    BR_20260706).

    "Capability compiled in" ≠ "mount provisioned on this host" — the
    service MUST report which state it is in, so callers decide
    webdav-mount vs R14.7 stage-inline fallback from an explicit field,
    never by implication.

    bodesign ships ONLY the builtin Basic-auth provider (DD-6 — no
    gateway variant), so a correctly configured host is always
    ``provisioned``. Deterministic, pure observability, NO behaviour
    change and NO new fallback mechanism (天條 11). An unknown
    ``BODESIGN_AUTH_PROVIDER`` value fails fast — never silently
    coerced to builtin.
    """
    raw = os.environ.get("BODESIGN_AUTH_PROVIDER")
    explicit = raw is not None
    kind = raw if explicit else "builtin"
    if kind != "builtin":
        raise AuthError(
            "AUTH_PROVIDER_UNKNOWN",
            f"BODESIGN_AUTH_PROVIDER={kind!r} is not supported: bodesign "
            "ships only the builtin Basic-auth provider (DD-6); fix the "
            "deployment env — no silent fallback (天條 11)")
    return {
        "state": "provisioned",
        "provider": "builtin",
        "explicit": explicit,
        "basis": ("auth provider builtin: standalone Basic-auth; credentials "
                  "issuable via the MCP rail with issue_webdav_credential "
                  "(R14.6) or rotated on HTTP /caches provision"),
    }


# Module-level singleton.
_default_provider: Optional[AuthProvider] = None


def default_provider() -> AuthProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = BuiltinAuthProvider()
    return _default_provider


def reset_default_provider_for_testing() -> None:
    global _default_provider
    _default_provider = None
