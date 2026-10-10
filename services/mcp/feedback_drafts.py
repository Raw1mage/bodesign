"""Fleet retrospective drafts (plan mcp_fleet-telemetry-feedback, task 1.1).

Transport-neutral by contract (DD-1, SEC-01): this module holds ZERO network
code, ZERO signing logic, ZERO callback URLs and never reads FLEET_NODE_SECRET.
It persists an immutable draft (draftId / eventId / eventCreatedAt + frozen
body bytes) to SQLite and pokes the deployment sidecar's wake socket. A missing
sidecar never fails the call: the sidecar's startup catch-up scan delivers the
draft later.

Paths:
  draft DB     FLEET_DRAFTS_DB, else <repo>/.artifacts/feedback_drafts.db
  wake socket  FLEET_SIDECAR_SOCKET, else /run/fleet/sidecar.sock (container),
               else $XDG_RUNTIME_DIR/fleet-telemetry/sidecar.sock.
               Never /tmp or /var/tmp.
"""
from __future__ import annotations

import datetime
import json
import os
import socket
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

FIELD_LIMITS = {"intent": 4096, "trajectory": 16384, "friction": 8192, "suggestion": 4096}
REQUIRED_FIELDS = ("intent", "friction")
MAX_BODY_BYTES = 1024 * 1024
STATUSES = ("pending", "in_flight", "delivered", "dead_letter")
FORBIDDEN_ROOTS = ("/tmp", "/var/tmp")

SCHEMA = """
CREATE TABLE IF NOT EXISTS retrospective_drafts (
    draft_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    event_created_at TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'in_flight', 'delivered', 'dead_letter')),
    attempts INTEGER NOT NULL DEFAULT 0,
    receipt_id TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_retro_drafts_status ON retrospective_drafts(status);
"""


def _forbidden(path: Path) -> bool:
    resolved = str(path.resolve(strict=False))
    return any(resolved == r or resolved.startswith(r + "/") for r in FORBIDDEN_ROOTS)


def uuid7(ms: Optional[int] = None) -> str:
    """RFC 9562 UUIDv7 (stdlib uuid.uuid7 exists only from Python 3.14)."""
    if ms is None:
        ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= ((rand >> 62) & 0xFFF) << 64
    value |= 0b10 << 62
    value |= rand & ((1 << 62) - 1)
    return str(uuid.UUID(int=value))


def uuid7_ms(value: str) -> int:
    """Unix-ms timestamp carried in the first 48 bits of a UUIDv7."""
    return uuid.UUID(value).int >> 80


def iso_ms(ms: int) -> str:
    created = datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc)
    return created.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def resolve_db_path() -> Path:
    explicit = os.environ.get("FLEET_DRAFTS_DB", "").strip()
    p = Path(explicit) if explicit else Path(__file__).resolve().parents[2] / ".artifacts" / "feedback_drafts.db"
    if _forbidden(p):
        raise ValueError(f"FORBIDDEN_PATH: draft DB {p} is under /tmp or /var/tmp")
    return p


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target = Path(db_path) if db_path is not None else resolve_db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def resolve_wake_socket() -> Optional[Path]:
    """Protected wake socket path, or None when no protected location exists."""
    explicit = os.environ.get("FLEET_SIDECAR_SOCKET", "").strip()
    if explicit:
        p = Path(explicit)
    elif Path("/run/fleet").is_dir():
        p = Path("/run/fleet/sidecar.sock")
    elif os.environ.get("XDG_RUNTIME_DIR", "").strip():
        p = Path(os.environ["XDG_RUNTIME_DIR"]) / "fleet-telemetry" / "sidecar.sock"
    else:
        return None
    return None if _forbidden(p) else p


def wake_sidecar() -> str:
    """Non-blocking datagram poke. Returns sent | no_socket_path | not_delivered.
    Never raises: the draft is already committed and the catch-up scan covers it."""
    sock_path = resolve_wake_socket()
    if sock_path is None:
        return "no_socket_path"
    s = None
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.setblocking(False)
        s.sendto(b"1", str(sock_path))
        return "sent"
    except OSError:
        return "not_delivered"
    finally:
        if s is not None:
            s.close()


def submit_retrospective(
    *,
    intent: Any = None,
    friction: Any = None,
    trajectory: Any = None,
    suggestion: Any = None,
    db_path: Optional[Path] = None,
    wake: bool = True,
) -> Dict[str, Any]:
    """Persist one caller-agent retrospective as an immutable local draft.

    The caller's narrative is stored verbatim; only type, presence and size
    bounds are enforced. Optional fields absent from the call are frozen as ""
    because the wire body schema requires all four keys as strings.
    """
    given = {"intent": intent, "trajectory": trajectory, "friction": friction, "suggestion": suggestion}
    missing = [f for f in REQUIRED_FIELDS if not isinstance(given[f], str) or not given[f].strip()]
    if missing:
        return {"ok": False, "error_code": "MISSING_FIELD", "missing": missing,
                "message": f"required non-empty string field(s): {', '.join(missing)}"}
    fields: Dict[str, str] = {}
    for name, limit in FIELD_LIMITS.items():
        value = given[name]
        if value is None:
            value = ""
        if not isinstance(value, str):
            return {"ok": False, "error_code": "INVALID_FIELD", "field": name, "message": f"{name} must be a string"}
        if len(value) > limit:
            return {"ok": False, "error_code": "FIELD_TOO_LARGE", "field": name,
                    "message": f"{name} has {len(value)} chars; limit is {limit}"}
        fields[name] = value

    now_ms = time.time_ns() // 1_000_000
    event_id = uuid7(now_ms)
    draft_id = uuid7(now_ms)
    event_created_at = iso_ms(now_ms)
    # Frozen body: every sidecar retry hashes and signs these exact bytes.
    body = json.dumps({"eventCreatedAt": event_created_at, "draftId": draft_id, **fields},
                      ensure_ascii=False, separators=(",", ":"))
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        return {"ok": False, "error_code": "PAYLOAD_TOO_LARGE",
                "message": f"serialized retrospective exceeds {MAX_BODY_BYTES} bytes"}

    conn = connect(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO retrospective_drafts (draft_id, event_id, event_created_at, body, status, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
                (draft_id, event_id, event_created_at, body, event_created_at, event_created_at),
            )
    finally:
        conn.close()
    if wake:
        wake_sidecar()
    return {"ok": True, "draftId": draft_id}


TOOL_DESCRIPTION = (
    "Report a retrospective about using this MCP server back to its maintainers (fleet telemetry). "
    "Records an immutable local draft and returns {ok:true, draftId:<UUIDv7>}; a deployment sidecar "
    "delivers it asynchronously. Fields: intent (required, <=4096 chars) what you tried to achieve; "
    "friction (required, <=8192) the error or limitation hit; trajectory (optional, <=16384) the tool "
    "calls and observed outputs; suggestion (optional, <=4096) the recommended fix. Oversize input "
    "returns FIELD_TOO_LARGE / PAYLOAD_TOO_LARGE; nothing is truncated."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "maxLength": FIELD_LIMITS["intent"]},
        "trajectory": {"type": "string", "maxLength": FIELD_LIMITS["trajectory"]},
        "friction": {"type": "string", "maxLength": FIELD_LIMITS["friction"]},
        "suggestion": {"type": "string", "maxLength": FIELD_LIMITS["suggestion"]},
    },
    "required": ["intent", "friction"],
}
