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
import os
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import Path


class TokenError(Exception):
    pass


class TokenNotFoundError(TokenError):
    pass


def sessions_root() -> Path:
    root = Path(os.environ.get("BODESIGN_SESSIONS_ROOT",
                               str(Path(__file__).resolve().parents[2] / ".run" / "sessions")))
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass(slots=True)
class TokenStore:
    root: Path

    def new_token(self) -> tuple[str, Path]:
        token = "tok_" + uuid.uuid4().hex[:16]
        doc_dir = self.root / token
        doc_dir.mkdir(parents=True, exist_ok=True)
        return token, doc_dir

    def resolve(self, token: str) -> Path:
        doc_dir = (self.root / token)
        if not token.startswith("tok_") or not doc_dir.is_dir():
            raise TokenNotFoundError(f"token not found: {token}")
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


def default_store() -> TokenStore:
    return TokenStore(root=sessions_root())
