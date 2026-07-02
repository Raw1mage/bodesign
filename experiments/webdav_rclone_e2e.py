"""Real-server WebDAV E2E: uvicorn + real BuiltinAuthProvider + rclone client
(plan mcp_r13-landing-webdav-cache, task 5.7 / AC-5 — ported from docxmcp
experiments/webdav_rclone_e2e.py).

Not a unit test — a genuine transport proof. Boots a temporary bodesign
Starlette server (localhost TCP, daemon thread, torn down on exit; this is
NOT the deployed container — no lifecycle rule is touched), wires the REAL
build_cache_dav_routes() with the REAL BuiltinAuthProvider (Basic-auth
path, DD-6), then drives it with the real `rclone` webdav backend so every
verb crosses a real socket from a real WebDAV client.

Requires on the invoking interpreter: starlette, uvicorn, httpx
(the repo .venv has all three); requires `rclone` on PATH.

Run:  .venv/bin/python experiments/webdav_rclone_e2e.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "services" / "mcp"))


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _rclone_env(env, *args, check=True, input_bytes=None, raw=False):
    r = subprocess.run(["rclone", *args], capture_output=True, env=env, input=input_bytes)
    if raw:
        return r.stdout.decode().strip()
    if check and r.returncode != 0:
        raise RuntimeError(
            f"rclone {' '.join(args)} failed ({r.returncode})\n"
            f"STDOUT: {r.stdout.decode(errors='replace')}\n"
            f"STDERR: {r.stderr.decode(errors='replace')}"
        )
    return r


def main() -> int:
    # ── prechecks: fail loud, never silently degrade ──
    if shutil.which("rclone") is None:
        print("FAIL: rclone not on PATH (command -v rclone) — install rclone to run this E2E")
        return 2
    try:
        import uvicorn
        from starlette.applications import Starlette
    except ImportError as exc:
        print(f"FAIL: interpreter lacks starlette/uvicorn ({exc}) — run with .venv/bin/python")
        return 2

    # ── fresh store + provider env, THEN import server modules ──
    work = Path(tempfile.mkdtemp(prefix="bodesign-dav-e2e-"))
    os.environ["BODESIGN_SESSIONS_ROOT"] = str(work / "sessions")
    os.environ["BODESIGN_WEBDAV_CRED_PATH"] = str(work / ".webdav-creds.json")

    import _auth_provider as ap
    import server as bd_server

    ap.reset_default_provider_for_testing()
    provider = ap.default_provider()
    owner = "alice"
    password = provider.credentials.issue(owner)  # pre-seed the Basic credential

    # ── boot the real routes on localhost ──
    app = Starlette(routes=bd_server.build_cache_dav_routes())
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    if not server.started:
        print("FAIL: server did not start")
        return 1
    base_url = f"http://127.0.0.1:{port}"
    print(f"server up on {base_url}")

    rc = 0
    try:
        import httpx

        auth = (owner, password)

        # 1. provision via real Basic auth (real provider verifies the credential)
        r = httpx.post(f"{base_url}/caches",
                       json={"subject_id": "e2e-fab"}, auth=auth, timeout=10)
        assert r.status_code == 201, (r.status_code, r.text)
        prov = r.json()
        token = prov["token"]
        # provision rotates the owner's WebDAV credential (issue is mint-or-
        # rotate); the LIVE mount password is the one returned here.
        mount_password = prov["webdav_password"]
        print(f"[provision] token={token} (credential rotated by provision)")

        dav_url = f"{base_url}/dav/{token}"

        # ── configure rclone webdav remote via env (no config file needed) ──
        obscured = _rclone_env(os.environ.copy(), "obscure", mount_password, raw=True)
        env = {
            **os.environ,
            "RCLONE_CONFIG_DAV_TYPE": "webdav",
            "RCLONE_CONFIG_DAV_URL": dav_url,
            "RCLONE_CONFIG_DAV_VENDOR": "other",
            "RCLONE_CONFIG_DAV_USER": owner,
            "RCLONE_CONFIG_DAV_PASS": obscured,
        }
        # httpx export/close below must also use the rotated credential.
        auth = (owner, mount_password)

        # 2. PUT via rclone copyto (upload side)
        src = Path(tempfile.mkdtemp()) / "body.md"
        src.write_bytes(b"# E2E Fab\n")
        _rclone_env(env, "copyto", str(src), "dav:body.md")
        print("[PUT] rclone copyto body.md OK")

        # nested path (rclone MKCOLs intermediate dirs)
        src2 = Path(tempfile.mkdtemp()) / "top.gbr"
        src2.write_bytes(b"G04 e2e*")
        _rclone_env(env, "copyto", str(src2), "dav:gerbers/top.gbr")
        print("[PUT nested] rclone copyto gerbers/top.gbr OK")

        # 3. PROPFIND (listing) via rclone lsf
        out = _rclone_env(env, "lsf", "-R", "dav:").stdout.decode()
        assert "body.md" in out, out
        assert "gerbers/" in out and "top.gbr" in out, out
        print(f"[PROPFIND] rclone lsf -R:\n{out.strip()}")

        # 4. GET via rclone cat
        got = _rclone_env(env, "cat", "dav:body.md").stdout
        assert got == b"# E2E Fab\n", got
        print("[GET] rclone cat body.md matches")

        # 5. MKCOL via rclone mkdir
        _rclone_env(env, "mkdir", "dav:media")
        assert (work / "sessions" / token / "media").is_dir()
        print("[MKCOL] rclone mkdir media OK")

        # 6. MOVE via rclone moveto (rename)
        _rclone_env(env, "moveto", "dav:body.md", "dav:body-final.md")
        got = _rclone_env(env, "cat", "dav:body-final.md").stdout
        assert got == b"# E2E Fab\n"
        out = _rclone_env(env, "lsf", "dav:").stdout.decode()
        assert "body-final.md" in out and "body.md\n" not in out, out
        print("[MOVE] rclone moveto body.md -> body-final.md OK")

        # 7. DELETE via rclone deletefile
        _rclone_env(env, "deletefile", "dav:gerbers/top.gbr")
        out = _rclone_env(env, "lsf", "-R", "dav:").stdout.decode()
        assert "top.gbr" not in out, out
        print("[DELETE] rclone deletefile gerbers/top.gbr OK")

        # 8. wrong-password client is rejected (real constant-time verify)
        bad_env = {**env, "RCLONE_CONFIG_DAV_PASS": _rclone_env(env, "obscure", "wrongpass", raw=True)}
        r2 = subprocess.run(["rclone", "lsf", "dav:"], capture_output=True, env=bad_env)
        assert r2.returncode != 0, "wrong password should fail"
        print("[AUTH] wrong password rejected (rclone lsf non-zero)")

        # 9. export (land) + close via httpx
        land = Path(tempfile.mkdtemp()) / "landing"
        r = httpx.post(f"{base_url}/caches/{token}/export",
                       json={"target": str(land)}, auth=auth, timeout=10)
        assert r.status_code == 200, r.text
        assert (land / "body-final.md").read_bytes() == b"# E2E Fab\n"
        print(f"[export] landed to {land}")

        r = httpx.post(f"{base_url}/caches/{token}/close",
                       json={}, auth=auth, timeout=10)
        assert r.status_code == 200 and r.json()["closed"] is True, r.text
        print("[close] clean close OK")

        print("\nALL rclone WebDAV E2E GREEN")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"\nE2E FAILED: {exc}")
        rc = 1
    finally:
        server.should_exit = True
        th.join(timeout=5)
        shutil.rmtree(work, ignore_errors=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
