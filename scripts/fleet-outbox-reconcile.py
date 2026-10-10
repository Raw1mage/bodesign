#!/usr/bin/env python3
"""Operator CLI for the fleet outbox dead-letter queue.

Plan: mcp_fleet-telemetry-feedback (bodesign), task 2.2; ported from the
patentmcp pilot. Manual only: nothing here
runs on a schedule. Re-queueing never rewrites draftId / eventId /
eventCreatedAt or the signed body bytes; it moves the outbox record back and
marks the draft `pending`, so the next sidecar wake retries it with a fresh
timestamp and signature.

Commands:
  list                 show dead-lettered events (outbox dir + draft DB)
  show <eventId>       print one dead-letter record
  requeue <eventId>    move it back to the live outbox and mark the draft pending
  requeue --all        requeue every dead-lettered event

Flag forms (spec REQ-RECON-04): --list | --show <eventId> | --requeue <eventId>.

Paths: FLEET_OUTBOX_DIR (default ~/.cache/fleet-outbox), FLEET_DRAFTS_DB.
Never /tmp or /var/tmp.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

EVENT_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
FORBIDDEN_ROOTS = ("/tmp", "/var/tmp")


def _forbidden(path: Path) -> bool:
    resolved = str(path.resolve(strict=False))
    return any(resolved == r or resolved.startswith(r + "/") for r in FORBIDDEN_ROOTS)


def outbox_root() -> Path:
    explicit = os.environ.get("FLEET_OUTBOX_DIR", "").strip()
    root = Path(explicit) if explicit else Path.home() / ".cache" / "fleet-outbox"
    if _forbidden(root):
        raise SystemExit(f"refusing outbox under /tmp or /var/tmp: {root}")
    return root


def drafts_db() -> Path | None:
    value = os.environ.get("FLEET_DRAFTS_DB", "").strip()
    return Path(value) if value else None


def dead_records(root: Path) -> list[Path]:
    dl = root / "dead-letter"
    return sorted(dl.glob("*.json")) if dl.is_dir() else []


def cmd_list(root: Path) -> int:
    rows = []
    for path in dead_records(root):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            rows.append({"file": path.name, "error": f"unreadable: {e}"})
            continue
        rows.append(
            {
                "eventId": rec.get("eventId"),
                "draftId": rec.get("draftId"),
                "eventCreatedAt": rec.get("eventCreatedAt"),
                "attempts": len(rec.get("attempts", [])),
                "lastError": rec.get("lastError"),
            }
        )
    print(json.dumps({"deadLetter": rows, "count": len(rows)}, indent=2, ensure_ascii=False))
    return 0


def cmd_show(root: Path, event_id: str) -> int:
    path = root / "dead-letter" / f"{event_id}.json"
    if not path.is_file():
        print(f"not in dead-letter: {event_id}", file=sys.stderr)
        return 1
    print(path.read_text(encoding="utf-8"))
    return 0


def requeue_one(root: Path, event_id: str, db: Path | None) -> bool:
    src = root / "dead-letter" / f"{event_id}.json"
    if not src.is_file():
        print(f"not in dead-letter: {event_id}", file=sys.stderr)
        return False
    rec = json.loads(src.read_text(encoding="utf-8"))
    rec["status"] = "locally_saved"
    rec.setdefault("requeues", 0)
    rec["requeues"] += 1
    dst = root / f"{event_id}.json"
    fd = os.open(str(dst), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False)
    src.unlink()
    if db is not None:
        conn = sqlite3.connect(str(db), timeout=5)
        try:
            with conn:
                conn.execute(
                    "UPDATE retrospective_drafts SET status = 'pending', last_error = NULL "
                    "WHERE event_id = ? AND status = 'dead_letter'",
                    (event_id,),
                )
        finally:
            conn.close()
    print(f"requeued {event_id}")
    return True


def _flags_to_subcommand(argv: list[str]) -> list[str]:
    """Map the spec's flag forms onto the subcommand grammar."""
    mapping = {"--list": "list", "--show": "show", "--requeue": "requeue"}
    if argv and argv[0] in mapping:
        return [mapping[argv[0]], *argv[1:]]
    return argv


def main(argv=None) -> int:
    argv = _flags_to_subcommand(list(sys.argv[1:] if argv is None else argv))
    parser = argparse.ArgumentParser(description="Fleet outbox dead-letter reconciliation")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    show = sub.add_parser("show")
    show.add_argument("event_id")
    rq = sub.add_parser("requeue")
    rq.add_argument("event_id", nargs="?")
    rq.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)

    root = outbox_root()
    if args.cmd == "list":
        return cmd_list(root)
    if args.cmd == "show":
        if not EVENT_ID.match(args.event_id):
            print("eventId must be a UUIDv7", file=sys.stderr)
            return 2
        return cmd_show(root, args.event_id)
    db = drafts_db()
    if db is None:
        print("warning: FLEET_DRAFTS_DB unset; draft row will stay dead_letter", file=sys.stderr)
    if args.all:
        ids = [p.stem for p in dead_records(root)]
    elif args.event_id and EVENT_ID.match(args.event_id):
        ids = [args.event_id]
    else:
        print("requeue needs a UUIDv7 eventId or --all", file=sys.stderr)
        return 2
    ok = all(requeue_one(root, i, db) for i in ids)
    print("next sidecar wake (or restart catch-up scan) will retry the requeued events")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
