#!/usr/bin/env python3
"""Fleet outbox adapter — deployment-owned harness sidecar.

Plan: mcp_fleet-telemetry-feedback (bodesign), task 2.1; ported from the
patentmcp pilot (devops_mcp-fleet-telemetry-feedback). This file belongs to the
deploy harness, not to the MCP application: it is the ONLY place that knows
FLEET_CALLBACK_URL / FLEET_NODE_SECRET and the signing contract.

Flow (no polling):
  1. On start: catch-up scan of every draft in `pending` or `in_flight`.
  2. Block on the protected wake socket (AF_UNIX datagram) until the MCP app
     pokes it after committing a draft; then drain pending drafts.
  3. Per draft: persist ~/.cache/fleet-outbox/<eventId>.json (0600, status
     locally_saved), mark the draft in_flight, then push with exactly 5 attempts
     total (backoff 1s, 2s, 4s, 8s). Each attempt signs with a FRESH timestamp;
     draftId / eventId / eventCreatedAt and the body bytes never change.
  4. 202 or 200(duplicate) -> draft `delivered` + receiptId. 5 failures ->
     dead_letter, outbox file moved to ~/.cache/fleet-outbox/dead-letter/.

Paths: never /tmp or /var/tmp. Wake socket is FLEET_SIDECAR_SOCKET, else
/run/fleet/sidecar.sock (container), else $XDG_RUNTIME_DIR/fleet-telemetry/sidecar.sock.

Environment:
  FLEET_CALLBACK_URL   https://<gateway>/api/v1/fleet/events (https only)
  FLEET_NODE_ID        registered node id
  FLEET_DEPLOYMENT_ID  registered deployment UUID
  FLEET_KEY_ID         key id (default k1)
  FLEET_NODE_SECRET    64-char lowercase hex (decoded to 32 bytes)
  FLEET_DRAFTS_DB      path of feedback_drafts.db shared with the MCP app
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import hmac
import json
import logging
import os
import socket
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

log = logging.getLogger("fleet.outbox")

MAX_ATTEMPTS = 5
BACKOFF_SECONDS = (1, 2, 4, 8)
FORBIDDEN_ROOTS = ("/tmp", "/var/tmp")


class ConfigError(Exception):
    pass


def _forbidden(path: Path) -> bool:
    resolved = str(path.resolve(strict=False))
    return any(resolved == r or resolved.startswith(r + "/") for r in FORBIDDEN_ROOTS)


def outbox_root() -> Path:
    explicit = os.environ.get("FLEET_OUTBOX_DIR", "").strip()
    if explicit:
        root = Path(explicit)  # same override the reconcile CLI honours
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache"))
        root = base / "fleet-outbox"
    if _forbidden(root):
        raise ConfigError(f"outbox root {root} is under a forbidden temp directory")
    return root


def wake_socket_path() -> Path:
    explicit = os.environ.get("FLEET_SIDECAR_SOCKET", "").strip()
    if explicit:
        p = Path(explicit)
    elif Path("/run/fleet").is_dir():
        p = Path("/run/fleet/sidecar.sock")
    elif os.environ.get("XDG_RUNTIME_DIR"):
        p = Path(os.environ["XDG_RUNTIME_DIR"]) / "fleet-telemetry" / "sidecar.sock"
    else:
        raise ConfigError("no protected runtime dir: set FLEET_SIDECAR_SOCKET or XDG_RUNTIME_DIR")
    if _forbidden(p):
        raise ConfigError(f"wake socket {p} is under a forbidden temp directory")
    return p


def decode_secret(hex_secret: str) -> bytes:
    if len(hex_secret) != 64 or any(c not in "0123456789abcdef" for c in hex_secret):
        raise ConfigError("INVALID_KEY_LENGTH: FLEET_NODE_SECRET must be 64 lowercase hex chars")
    key = bytes.fromhex(hex_secret)
    if len(key) != 32:
        raise ConfigError("INVALID_KEY_LENGTH")
    return key


def iso_now() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def body_hash_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_string(timestamp: str, node_id: str, deployment_id: str, event_id: str, body_hash: str) -> str:
    return f"{timestamp}.{node_id}.{deployment_id}.{event_id}.{body_hash}"


def sign_headers(
    *, body: bytes, event_id: str, timestamp: str, node_id: str, deployment_id: str, key_id: str, secret: bytes
) -> Dict[str, str]:
    canonical = canonical_string(timestamp, node_id, deployment_id, event_id, body_hash_hex(body))
    mac = hmac.new(secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Fleet-Node-Id": node_id,
        "X-Fleet-Deployment-Id": deployment_id,
        "X-Fleet-Event-Id": event_id,
        "X-Fleet-Timestamp": timestamp,
        "X-Fleet-Signature": f"t={timestamp},k={key_id},v1={mac}",
    }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def http_post(url: str, body: bytes, headers: Dict[str, str], timeout: float = 15.0) -> Tuple[int, Dict]:
    """HTTPS only, certificate verification on, redirects refused."""
    if not url.startswith("https://"):
        raise ConfigError("FLEET_CALLBACK_URL must be https://")
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), _NoRedirect())
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read() or b"{}")
        except Exception:
            payload = {}
        return e.code, payload


class Adapter:
    def __init__(
        self,
        *,
        db_path: Path,
        callback_url: str,
        node_id: str,
        deployment_id: str,
        key_id: str,
        secret: bytes,
        outbox: Optional[Path] = None,
        post: Callable[[str, bytes, Dict[str, str]], Tuple[int, Dict]] = http_post,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], str] = iso_now,
    ):
        self.db_path = db_path
        self.callback_url = callback_url
        self.node_id = node_id
        self.deployment_id = deployment_id
        self.key_id = key_id
        self.secret = secret
        self.outbox = outbox or outbox_root()
        self.post = post
        self.sleep = sleep
        self.clock = clock
        self.outbox.mkdir(parents=True, exist_ok=True, mode=0o700)
        (self.outbox / "dead-letter").mkdir(parents=True, exist_ok=True, mode=0o700)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _write_outbox(self, path: Path, record: Dict) -> None:
        tmp = path.with_suffix(".json.part")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)

    def claim(self) -> list:
        """Atomically move pending drafts to in_flight; return every in_flight draft."""
        conn = self._conn()
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "UPDATE retrospective_drafts SET status = 'in_flight', updated_at = ? WHERE status = 'pending'",
                    (self.clock(),),
                )
                rows = conn.execute(
                    "SELECT draft_id, event_id, event_created_at, body, attempts FROM retrospective_drafts "
                    "WHERE status = 'in_flight' ORDER BY created_at"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _finish(self, draft_id: str, status: str, receipt: Optional[str], error: Optional[str], attempts: int) -> None:
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    "UPDATE retrospective_drafts SET status = ?, receipt_id = ?, last_error = ?, attempts = ?, "
                    "updated_at = ? WHERE draft_id = ?",
                    (status, receipt, error, attempts, self.clock(), draft_id),
                )
        finally:
            conn.close()

    def push(self, draft: Dict) -> str:
        event_id = draft["event_id"]
        body = draft["body"].encode("utf-8")
        path = self.outbox / f"{event_id}.json"
        record = {
            "draftId": draft["draft_id"],
            "eventId": event_id,
            "eventCreatedAt": draft["event_created_at"],
            "body": draft["body"],
            "status": "locally_saved",
            "attempts": [],
        }
        if path.exists():
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        self._write_outbox(path, record)

        last_error = None
        for attempt in range(MAX_ATTEMPTS):
            if attempt:
                self.sleep(BACKOFF_SECONDS[attempt - 1])
            timestamp = self.clock()
            headers = sign_headers(
                body=body,
                event_id=event_id,
                timestamp=timestamp,
                node_id=self.node_id,
                deployment_id=self.deployment_id,
                key_id=self.key_id,
                secret=self.secret,
            )
            try:
                status, payload = self.post(self.callback_url, body, headers)
            except ConfigError:
                raise
            except Exception as e:  # network fault: retry
                status, payload = 0, {"error": type(e).__name__}
            record["attempts"].append({"at": timestamp, "status": status, "error": payload.get("error")})
            accepted = (status == 202 and payload.get("status") == "mother_accepted") or (
                status == 200 and payload.get("duplicate") is True)
            if accepted:
                record["status"] = "delivered"
                record["receiptId"] = payload.get("receiptId")
                self._write_outbox(path, record)
                self._finish(draft["draft_id"], "delivered", record["receiptId"], None, attempt + 1)
                path.unlink(missing_ok=True)
                return "delivered"
            last_error = f"{status}:{payload.get('error')}"
            self._write_outbox(path, record)
            if status in (400, 401, 403, 404, 409, 413):
                break  # deterministic refusal: retrying the same bytes cannot succeed
        record["status"] = "dead_letter"
        record["lastError"] = last_error
        self._write_outbox(path, record)
        os.replace(path, self.outbox / "dead-letter" / path.name)
        self._finish(draft["draft_id"], "dead_letter", None, last_error, len(record["attempts"]))
        log.error("fleet event %s dead-lettered: %s", event_id, last_error)
        return "dead_letter"

    def drain(self) -> Dict[str, int]:
        counts = {"delivered": 0, "dead_letter": 0}
        for draft in self.claim():
            counts[self.push(draft)] += 1
        return counts

    def serve(self) -> None:
        sock_path = wake_socket_path()
        sock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(sock_path.parent, 0o700)
        if sock_path.exists():
            sock_path.unlink()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.bind(str(sock_path))
        os.chmod(sock_path, 0o600)
        log.info("catch-up scan: %s", self.drain())
        try:
            while True:
                sock.recv(64)  # blocks until the MCP app pokes; no polling
                log.info("wake: %s", self.drain())
        finally:
            sock.close()
            sock_path.unlink(missing_ok=True)


def from_env() -> Adapter:
    def need(name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            raise ConfigError(f"{name} is required")
        return value

    url = need("FLEET_CALLBACK_URL")
    if not url.startswith("https://"):
        raise ConfigError("FLEET_CALLBACK_URL must be https://")
    return Adapter(
        db_path=Path(need("FLEET_DRAFTS_DB")),
        callback_url=url,
        node_id=need("FLEET_NODE_ID"),
        deployment_id=need("FLEET_DEPLOYMENT_ID"),
        key_id=os.environ.get("FLEET_KEY_ID", "k1").strip() or "k1",
        secret=decode_secret(need("FLEET_NODE_SECRET")),
    )


SELF_TEST_VECTOR = {
    "secret": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "nodeId": "dockerlab-patentmcp-01",
    "deploymentId": "019273a0-0000-7000-8000-000000000001",
    "eventId": "01a123ee-9240-7000-8000-000000000002",
    "timestamp": "2026-10-10T03:50:00.000Z",
    "body": '{"eventCreatedAt":"2026-10-10T03:50:00.000Z","intent":"test","trajectory":"step1","friction":"err","suggestion":"fix"}',
    "bodyHashHex": "d60fb23f2714056d077e0694fdbe2d14c6715f6196868a41b785017be4096aeb",
    "header": "t=2026-10-10T03:50:00.000Z,k=k1,v1=e5350547773c7dc9060c117a4ba76c226ab6f1db133ddde8de78cb7ed0eedc42",
}


def self_test() -> int:
    """Offline: signing matches the plan wire vector byte-for-byte."""
    v = SELF_TEST_VECTOR
    body = v["body"].encode("utf-8")
    headers = sign_headers(
        body=body,
        event_id=v["eventId"],
        timestamp=v["timestamp"],
        node_id=v["nodeId"],
        deployment_id=v["deploymentId"],
        key_id="k1",
        secret=decode_secret(v["secret"]),
    )
    ok_hash = body_hash_hex(body) == v["bodyHashHex"]
    ok_sig = headers["X-Fleet-Signature"] == v["header"]
    print(f"bodyHashHex {'PASS' if ok_hash else 'FAIL'}")
    print(f"X-Fleet-Signature {'PASS' if ok_sig else 'FAIL'}")
    return 0 if ok_hash and ok_sig else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--self-test", action="store_true", help="verify signing against the plan vector and exit")
    parser.add_argument("--once", action="store_true", help="drain pending drafts once and exit (no wake loop)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.self_test:
        return self_test()
    try:
        adapter = from_env()
    except ConfigError as e:
        log.error("%s", e)
        return 2
    if args.once:
        print(json.dumps(adapter.drain()))
        return 0
    adapter.serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
