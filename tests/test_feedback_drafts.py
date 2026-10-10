"""Fleet retrospective drafts (plan mcp_fleet-telemetry-feedback, task 4.1)."""
import datetime
import importlib.util
import json
import os
import socket
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.mcp import feedback_drafts as fd

REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "bodesign-fleet-tests"


def _load_script(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _TmpDirCase(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._tmp = tempfile.TemporaryDirectory(dir=PRIVATE_BASE)
        self.dir = Path(self._tmp.name)
        self.db = self.dir / "feedback_drafts.db"
        # No sidecar: point the wake socket at a path nobody binds.
        self._env = patch.dict(os.environ, {"FLEET_SIDECAR_SOCKET": str(self.dir / "absent.sock")})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def rows(self):
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute("SELECT * FROM retrospective_drafts")]
        finally:
            conn.close()


class SubmitRetrospectiveTest(_TmpDirCase):
    def test_persists_pending_draft_and_returns_uuid7(self):
        r = fd.submit_retrospective(intent="Auto-route power rail", friction="Track overlap on layer 2",
                                    db_path=self.db)
        self.assertEqual({"ok", "draftId"}, set(r))
        self.assertTrue(r["ok"])
        rows = self.rows()
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual(r["draftId"], row["draft_id"])
        self.assertEqual("pending", row["status"])
        self.assertEqual(0, row["attempts"])
        for value in (row["draft_id"], row["event_id"]):
            self.assertEqual(7, __import__("uuid").UUID(value).version)
        self.assertNotEqual(row["draft_id"], row["event_id"])

    def test_event_id_prefix_matches_event_created_at_ms(self):
        fd.submit_retrospective(intent="i", friction="f", db_path=self.db)
        row = self.rows()[0]
        created = datetime.datetime.strptime(row["event_created_at"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=datetime.timezone.utc)
        created_ms = int(round(created.timestamp() * 1000))
        self.assertEqual(created_ms, fd.uuid7_ms(row["event_id"]))
        self.assertRegex(row["event_created_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")

    def test_body_is_frozen_wire_schema(self):
        fd.submit_retrospective(intent="設計", friction="f", trajectory="t", db_path=self.db)
        row = self.rows()[0]
        body = json.loads(row["body"])
        self.assertEqual({"eventCreatedAt", "draftId", "intent", "trajectory", "friction", "suggestion"}, set(body))
        self.assertEqual(row["event_created_at"], body["eventCreatedAt"])
        self.assertEqual(row["draft_id"], body["draftId"])
        self.assertEqual("設計", body["intent"])
        self.assertEqual("", body["suggestion"])  # optional absent -> "" (wire requires string)

    def test_field_limits_exact_boundary(self):
        for name, limit in fd.FIELD_LIMITS.items():
            args = {"intent": "i", "friction": "f", name: "x" * limit}
            self.assertTrue(fd.submit_retrospective(db_path=self.db, **args)["ok"], name)
            args[name] = "x" * (limit + 1)
            r = fd.submit_retrospective(db_path=self.db, **args)
            self.assertFalse(r["ok"], name)
            self.assertEqual("FIELD_TOO_LARGE", r["error_code"])
            self.assertEqual(name, r["field"])
        self.assertEqual(len(fd.FIELD_LIMITS), len(self.rows()), "rejected calls must persist nothing")

    def test_payload_too_large(self):
        with patch.object(fd, "MAX_BODY_BYTES", 64):
            r = fd.submit_retrospective(intent="i" * 100, friction="f", db_path=self.db)
        self.assertEqual({"ok": False, "error_code": "PAYLOAD_TOO_LARGE"},
                         {k: r[k] for k in ("ok", "error_code")})
        self.assertFalse(self.db.exists() and self.rows())

    def test_missing_required_and_bad_type(self):
        r = fd.submit_retrospective(intent="i", friction="   ", db_path=self.db)
        self.assertEqual("MISSING_FIELD", r["error_code"])
        self.assertEqual(["friction"], r["missing"])
        r = fd.submit_retrospective(intent="i", friction="f", suggestion=3, db_path=self.db)
        self.assertEqual("INVALID_FIELD", r["error_code"])

    def test_forbidden_db_path(self):
        with patch.dict(os.environ, {"FLEET_DRAFTS_DB": "/tmp/feedback_drafts.db"}):
            with self.assertRaises(ValueError):
                fd.resolve_db_path()


class WakeSocketTest(_TmpDirCase):
    def test_absent_sidecar_does_not_fail(self):
        self.assertEqual("not_delivered", fd.wake_sidecar())
        self.assertTrue(fd.submit_retrospective(intent="i", friction="f", db_path=self.db)["ok"])

    def test_wake_datagram_delivered(self):
        sock_path = self.dir / "sidecar.sock"
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.bind(str(sock_path))
        s.settimeout(2)
        try:
            with patch.dict(os.environ, {"FLEET_SIDECAR_SOCKET": str(sock_path)}):
                self.assertTrue(fd.submit_retrospective(intent="i", friction="f", db_path=self.db)["ok"])
            self.assertEqual(b"1", s.recv(16))
        finally:
            s.close()

    def test_tmp_socket_refused(self):
        with patch.dict(os.environ, {"FLEET_SIDECAR_SOCKET": "/tmp/fleet/sidecar.sock"}):
            self.assertIsNone(fd.resolve_wake_socket())
            self.assertEqual("no_socket_path", fd.wake_sidecar())

    def test_xdg_runtime_default(self):
        env = {k: v for k, v in os.environ.items() if k != "FLEET_SIDECAR_SOCKET"}
        env["XDG_RUNTIME_DIR"] = str(self.dir)
        with patch.dict(os.environ, env, clear=True), patch.object(fd.Path, "is_dir", return_value=False):
            self.assertEqual(self.dir / "fleet-telemetry" / "sidecar.sock", fd.resolve_wake_socket())


class AdapterTest(_TmpDirCase):
    def setUp(self):
        super().setUp()
        self.ad = _load_script("bodesign_fleet_outbox_adapter", "deploy/fleet-outbox-adapter.py")

    def _adapter(self, responses):
        calls = []

        def post(url, body, headers):
            calls.append((body, headers))
            r = responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        a = self.ad.Adapter(db_path=self.db, callback_url="https://mother.invalid/api/v1/fleet/events",
                            node_id="dockerlab-bodesign-01", deployment_id="019273b0-0000-7000-8000-000000000001",
                            key_id="k1", secret=bytes(32), outbox=self.dir / "outbox", post=post,
                            sleep=lambda s: None)
        return a, calls

    def test_self_test_vector(self):
        self.assertEqual(0, self.ad.self_test())

    def test_delivered_on_202_after_retry(self):
        fd.submit_retrospective(intent="i", friction="f", db_path=self.db)
        a, calls = self._adapter([OSError("down"), (202, {"status": "mother_accepted", "receiptId": "rcpt_x"})])
        self.assertEqual({"delivered": 1, "dead_letter": 0}, a.drain())
        row = self.rows()[0]
        self.assertEqual(("delivered", 2, "rcpt_x"), (row["status"], row["attempts"], row["receipt_id"]))
        self.assertEqual(calls[0][0], calls[1][0])  # body bytes unchanged across attempts
        self.assertEqual(row["body"].encode("utf-8"), calls[0][0])
        self.assertEqual(row["event_id"], calls[0][1]["X-Fleet-Event-Id"])

    def test_duplicate_200_is_delivered(self):
        fd.submit_retrospective(intent="i", friction="f", db_path=self.db)
        a, _ = self._adapter([(200, {"duplicate": True, "receiptId": "rcpt_d", "status": "mother_accepted"})])
        self.assertEqual(1, a.drain()["delivered"])

    def test_deterministic_refusal_dead_letters_then_requeue(self):
        fd.submit_retrospective(intent="i", friction="f", db_path=self.db)
        a, calls = self._adapter([(409, {"error": "EVENT_ID_COLLISION"})])
        self.assertEqual({"delivered": 0, "dead_letter": 1}, a.drain())
        self.assertEqual(1, len(calls))
        row = self.rows()[0]
        self.assertEqual("dead_letter", row["status"])
        self.assertTrue((self.dir / "outbox" / "dead-letter" / f"{row['event_id']}.json").is_file())

        rc = _load_script("bodesign_fleet_outbox_reconcile", "scripts/fleet-outbox-reconcile.py")
        with patch.dict(os.environ, {"FLEET_OUTBOX_DIR": str(self.dir / "outbox"),
                                     "FLEET_DRAFTS_DB": str(self.db)}):
            self.assertEqual(0, rc.main(["--list"]))
            self.assertEqual(0, rc.main(["--show", row["event_id"]]))
            self.assertEqual(0, rc.main(["--requeue", row["event_id"]]))
        self.assertEqual("pending", self.rows()[0]["status"])

    def test_retry_exhaustion_is_five_attempts(self):
        fd.submit_retrospective(intent="i", friction="f", db_path=self.db)
        a, calls = self._adapter([(503, {})] * 5)
        self.assertEqual(1, a.drain()["dead_letter"])
        self.assertEqual(5, len(calls))


class ServerRegistrationTest(unittest.TestCase):
    def test_tool_and_alias_registered(self):
        from services.mcp import server
        self.assertIn("bodesign_submit_retrospective", server.TOOLS_BY_NAME)
        self.assertEqual("bodesign_submit_retrospective", server.TOOL_ALIASES["submit_retrospective"])

    def test_run_tool_alias_returns_wire_contract(self):
        from services.mcp import server
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(dir=PRIVATE_BASE) as d, patch.dict(
                os.environ, {"FLEET_DRAFTS_DB": str(Path(d) / "f.db"),
                             "FLEET_SIDECAR_SOCKET": str(Path(d) / "absent.sock")}):
            for name in ("submit_retrospective", "bodesign_submit_retrospective"):
                r = server.run_tool(name, {"intent": "i", "friction": "f"})
                self.assertEqual({"ok", "draftId"}, set(r), name)
            r = server.run_tool("submit_retrospective", {"intent": "x" * 4097, "friction": "f"})
            self.assertEqual("FIELD_TOO_LARGE", r["error_code"])


if __name__ == "__main__":
    unittest.main()
