"""R9 skill-shipping remote half — companion-skill listing + archive download.

owning spec: ``specs/mcp-integration-standard/`` (opencode repo, living)
    R9.1  ``mcp.json.skillPaths`` declares in-repo skill dirs (local half)
    R9.2  ``GET /skills`` + ``GET /skills/<name>.zip`` (remote half)
    R9.4  the two halves are ONE contract — half counts as a violation
    R9.7.1 producer: no absolute paths, no ``..`` segments, no symlinks
    R9.9  a listed ``name`` is a bare skill NAME, never a filename
    R9.11 the served source and the declared source MUST be provably the same

WHY THIS MODULE EXISTS (BR_20260730). The previous implementation listed
``services/mcp/assets/skills/*.tar.gz`` — 14 hand-frozen tarballs — and
advertised their FILENAMES. Three defects followed from that one choice:

  1. a conformant consumer reads ``name`` and appends ``.zip`` (R9.8/R9.9.2),
     so it dialled ``bodesign-eda-skills-bundle.tar.gz.zip`` -> 404. Every
     companion was unreachable while ``GET /skills`` answered 200.
  2. ``.tar.gz`` is not ``.zip``. R9.2 pins the format; there is no content
     negotiation in the consumer.
  3. the served tree (``assets/skills/``) was not the declared tree
     (``mcp.json skillPaths`` -> repo ``skills/``). By 2026-07-30 they HAD
     drifted: the frozen ``bodesign.tar.gz`` was 7 weeks stale, missing
     ``doctrine.md`` and the whole ``scripts/`` dir (``gate.py`` — the sole
     entrypoint for ~52 landing verbs), and carried 2 symlinks that R9.7.1
     forbids outright.

The fix is structural, not cosmetic: archives are built ON THE FLY from the
tree ``mcp.json`` declares. R9.11.3 names this the preferred implementation
because it makes the two halves the same bytes BY CONSTRUCTION — there is no
second artifact left to drift. ``assert_skill_source_parity()`` additionally
fails the process at startup if the declaration and the served root ever stop
agreeing, so a silent divergence cannot survive a restart (天條 1: fail fast,
never a silent fallback).
"""
from __future__ import annotations

import io
import json
import os
import re
import tarfile
import zipfile
from pathlib import Path

# <repo>/services/mcp/skill_shipping.py -> <repo>
REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "mcp.json"

# R9.9.1 — a bare skill name: no extension, no separator, no `..`. Anchored,
# so a name containing a slash cannot match at all (first traversal guard;
# the route pattern is the zeroth, the containment check below is the third).
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# Never shipped: editor/VCS noise, byte-code caches, per-run artifacts. Dotted
# entries are excluded wholesale (leading "."), these are the non-dotted ones.
_EXCLUDED_DIRS = {"__pycache__", "analysis", "node_modules"}

# Reproducible archives: a fixed DOS-epoch timestamp on every member, so the
# same tree always yields the same bytes regardless of checkout mtimes. Without
# this, "did the shipped skill change?" is unanswerable by hash.
_FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
_FIXED_MTIME = 315532800  # 1980-01-01T00:00:00Z, tar's epoch-seconds form


class SkillShippingError(Exception):
    """Typed failure carrying the HTTP status the route must return.

    R9.6.2 — each of these is an explicit failure, never a 200 with an empty
    archive. A consumer cannot tell "no such skill" from "here is nothing"
    unless the producer says so in the status line.
    """

    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def declared_skill_paths() -> list[str]:
    """The R9.1 declaration, read from ``mcp.json`` — the SINGLE source.

    Fails loud rather than defaulting to ``["skills"]``: a guessed default is
    exactly the silent fallback that let the served and declared trees drift
    apart unnoticed for 7 weeks (天條 1 / 天條 11).
    """
    if not MANIFEST_PATH.is_file():
        raise SkillShippingError(
            "SKILL_MANIFEST_MISSING",
            f"mcp.json not found at {MANIFEST_PATH}. The R9.2 remote half derives "
            f"its source tree from the R9.1 declaration, so the manifest MUST be "
            f"present (in the container image too: `COPY mcp.json /app/mcp.json`).",
            500,
        )
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkillShippingError(
            "SKILL_MANIFEST_UNREADABLE", f"mcp.json is not valid JSON: {exc}", 500
        ) from exc
    paths = manifest.get("skillPaths")
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
        raise SkillShippingError(
            "SKILL_MANIFEST_NO_SKILLPATHS",
            "mcp.json declares no usable `skillPaths`. R9.4 makes the local and "
            "remote halves one contract — without the declaration there is no "
            "source of truth for the remote half to serve.",
            500,
        )
    return paths


def skills_root() -> Path:
    """The tree ``mcp.json`` declares, resolved against the repo root.

    This IS the served source (R9.11.3 by construction). bodesign declares a
    single path; a multi-path declaration is rejected loudly rather than
    silently serving the first one.
    """
    paths = declared_skill_paths()
    if len(paths) != 1:
        raise SkillShippingError(
            "SKILL_MANIFEST_MULTI_PATH",
            f"mcp.json declares {len(paths)} skillPaths ({paths}); the remote half "
            f"resolves exactly one. Picking the first would be a silent fallback.",
            500,
        )
    return (REPO_ROOT / paths[0]).resolve()


def _is_shippable_member(root: Path, path: Path) -> bool:
    """A regular file, under ``root``, in no excluded/dotted directory.

    Symlinks are excluded at every level (R9.7.1): a symlink either escapes the
    archive (a traversal primitive) or dangles for the consumer. opencode's
    consumer hard-rejects any symlink after extraction, so shipping one turns
    the whole skill into a failed materialization.
    """
    if path.is_symlink() or not path.is_file():
        return False
    rel = path.relative_to(root)
    return not any(part.startswith(".") or part in _EXCLUDED_DIRS for part in rel.parts)


def _walk_skill_files(skill_dir: Path) -> list[Path]:
    """Every shippable file under ``skill_dir``, sorted for deterministic output.

    ``followlinks=False`` keeps the walk inside the real tree; symlinked dirs
    are pruned along with dotted/excluded ones so we never descend into them.
    """
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(skill_dir, followlinks=False):
        here = Path(dirpath)
        dirnames[:] = sorted(
            d
            for d in dirnames
            if not d.startswith(".") and d not in _EXCLUDED_DIRS and not (here / d).is_symlink()
        )
        for fn in sorted(filenames):
            p = here / fn
            if _is_shippable_member(skill_dir, p):
                out.append(p)
    return sorted(out)


def list_shippable_skills() -> list[dict]:
    """R9.2 listing: every skill dir under the declared tree, by BARE name.

    A directory counts as a skill iff it holds a ``SKILL.md`` — the same file
    the consumer requires to consider a materialization successful, so the
    listing cannot advertise something that would fail on arrival (R9.10.2:
    a listing whose names are not each served is itself the violation).
    """
    root = skills_root()
    if not root.is_dir():
        raise SkillShippingError(
            "SKILL_ROOT_MISSING",
            f"declared skillPaths tree {root} does not exist. R9.4.2: declaring is "
            f"not shipping — a pointer to nothing serves no client.",
            500,
        )
    items: list[dict] = []
    for child in sorted(root.iterdir()):
        if child.is_symlink() or not child.is_dir() or child.name.startswith("."):
            continue
        if not (child / "SKILL.md").is_file():
            continue
        items.append(
            {
                "name": child.name,  # BARE (R9.9.1) — `.zip` belongs to the endpoint
                "file_count": len(_walk_skill_files(child)),
                "url": f"/skills/{child.name}.zip",
            }
        )
    return items


def resolve_skill_dir(name: str) -> Path:
    """Name -> directory, with defence in depth against traversal.

    Three independent guards, because any single one has a known bypass class:
      1. ``_SAFE_NAME_RE`` rejects separators, ``..``, absolute forms;
      2. post-``resolve()`` containment catches symlink and unicode escapes
         that survive a textual check;
      3. the ``SKILL.md`` requirement keeps an arbitrary directory (say a
         resolved-but-unrelated dir) from being packaged as a "skill".
    """
    if not _SAFE_NAME_RE.match(name):
        # R9.7.1 pins the STATUS as well as the shape: an unservable name MUST
        # answer `404`. The typed code stays `SKILL_NAME_INVALID` so a diagnosing
        # human still learns *why*, but the status line a conformant consumer
        # branches on is the same 404 it gets for an unknown-but-well-formed
        # name. BR_20260730 external verification (V4): this used to answer 400,
        # so `bodesign%00.zip` and `bodesign.zip` failed in two different
        # vocabularies -- and a malformed name is not a *protocol* error the
        # client can fix by retrying differently, it is simply not a skill.
        raise SkillShippingError(
            "SKILL_NAME_INVALID",
            f"{name!r} is not a bare skill name (R9.9.1: no extension, no path "
            f"separator, no `..`).",
            404,
        )
    root = skills_root()
    # Every filesystem probe below is inside the `try`, because a stat can fail
    # for reasons the textual guard above cannot see. BR_20260730 round-2 (W1):
    # `_SAFE_NAME_RE` happily matches 300 `a`s -- the name is *well-formed*, it
    # is merely longer than NAME_MAX (255 bytes on Linux), so `is_dir()` raised
    # a bare OSError(ENAMETOOLONG) that left this function untyped and surfaced
    # as a 500. A name the OS cannot even look up is not a server fault and not
    # a new vocabulary: it is one more name we do not serve, and R9.7.1 pins
    # that to 404. Note `resolve()` itself is NOT the raiser (it is pure path
    # arithmetic on a non-strict path) -- the raiser is the stat, which is why
    # guarding only the resolve would have left this defect alive.
    try:
        candidate = (root / name).resolve()
        if candidate.parent != root or not candidate.is_dir():
            raise SkillShippingError("SKILL_NOT_FOUND", f"no such skill: {name}", 404)
        if not (candidate / "SKILL.md").is_file():
            raise SkillShippingError(
                "SKILL_NOT_FOUND", f"no such skill: {name} (directory has no SKILL.md)", 404
            )
    except OSError as exc:  # ENAMETOOLONG, ELOOP, ENOTDIR, EACCES on a path component
        raise SkillShippingError(
            "SKILL_NOT_FOUND", f"no such skill: {name} ({exc.strerror})", 404
        ) from exc
    return candidate


def pack_skill_zip(name: str) -> bytes:
    """R9.2 payload: a deterministic zip whose members live under ``<name>/``.

    Layout matches the fleet's reference producer (docxmcp) and the consumer's
    preferred shape: ``bodesign/SKILL.md``, ``bodesign/stages/…``. opencode's
    ``pickSkillRoot`` also accepts a flat archive, but the wrapped form is what
    the standard's precedent ships, and it survives a naive ``unzip`` into a
    skills parent dir without scattering files.
    """
    skill_dir = resolve_skill_dir(name)
    files = _walk_skill_files(skill_dir)
    if not files:
        # R9.6.2 — never hand back a 200 with an empty archive.
        raise SkillShippingError(
            "SKILL_EMPTY", f"skill {name} has no shippable files", 500
        )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            arcname = f"{name}/{p.relative_to(skill_dir).as_posix()}"
            info = zipfile.ZipInfo(arcname, date_time=_FIXED_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, p.read_bytes())
    return buf.getvalue()


def resolve_static_asset(root: Path, name: str) -> Path | None:
    """The OTHER ``/skills/<name>`` branch: vendored bundles + ``MANIFEST.md``.

    Returns the servable file, or ``None`` meaning "404" — never raises for a
    hostile or malformed name. It lives here, beside ``resolve_skill_dir``,
    for one reason: BOTH branches decide the same question ("is this a name I
    serve?") and BR_20260730 has now twice been a case of the two branches
    answering it differently.

    Round 1: the dynamic branch said 400 (`SKILL_NAME_INVALID`) where this one
    said 403 (`path_escape`) and a plain unknown said 404 — one condition, three
    vocabularies. Round 2: both branches let an over-long name escape as a bare
    ``OSError`` and become a 500.

    The recurrence is the real finding. The route handler was a closure inside
    ``run_http``, so nothing could construct it without starlette + a live app,
    and it carried ZERO test coverage while holding half the decision. Both
    defects lived in exactly that unlit half. Extracting the decision to a pure
    function is the structural fix: the branch is now reachable by a plain
    ``unittest`` with no server, no sockets, and no HTTP client.
    """
    try:
        target = (root / name).resolve()
        target.relative_to(root)
        if not target.is_file():
            return None
    except (ValueError, OSError):
        # ValueError: escaped the root. OSError: the OS refused to even look the
        # name up (ENAMETOOLONG past NAME_MAX, ELOOP, ENOTDIR, a NUL byte). A
        # name we cannot look up is a name we do not serve — not a server fault.
        return None
    if target.name != "MANIFEST.md" and not target.name.endswith(".tar.gz"):
        return None
    return target


def pack_skill_targz(name: str) -> bytes:
    """Back-compat ``.tar.gz`` of the SAME tree, built the SAME way.

    Kept because the landing page has published these links since 2026-06-07
    and a live URL should not 404 on an unrelated fix. Critically it is no
    longer a SEPARATE artifact: both formats project the one declared tree, so
    the format choice can no longer encode a content difference (the exact
    trap BR_20260730 found — a stale tarball beside a fresh source tree).
    """
    skill_dir = resolve_skill_dir(name)
    files = _walk_skill_files(skill_dir)
    if not files:
        raise SkillShippingError("SKILL_EMPTY", f"skill {name} has no shippable files", 500)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for p in files:
            data = p.read_bytes()
            info = tarfile.TarInfo(f"{name}/{p.relative_to(skill_dir).as_posix()}")
            info.size = len(data)
            info.mtime = _FIXED_MTIME
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def assert_skill_source_parity(companion: str) -> None:
    """R9.11.1 startup gate: declaration and service MUST agree.

    By construction they read the same tree, so this asserts the construction
    itself still holds — the manifest is present and parseable, the declared
    tree exists, it yields at least one skill, and the companion this server
    names in its own identity constant is among them. Any of these failing
    means the local half (``skillPaths``) and the remote half (``GET /skills``)
    have stopped describing the same thing, which is precisely the
    ``MCPSTD_SKILL_HALF_SHIPPED`` shape.

    Raises so the process dies at startup rather than serving a half-contract:
    a server that boots green while shipping nothing is the failure mode the
    whole R9.12 clause exists to catch.
    """
    declared = declared_skill_paths()
    root = skills_root()
    if not root.is_dir():
        raise RuntimeError(
            f"R9.11 parity violation: mcp.json declares skillPaths={declared} but "
            f"{root} does not exist. The local half points at nothing while the "
            f"remote half would serve nothing."
        )
    names = [s["name"] for s in list_shippable_skills()]
    if not names:
        raise RuntimeError(
            f"R9.11 parity violation: declared skillPaths={declared} resolves to "
            f"{root}, which contains no directory with a SKILL.md. Both halves of "
            f"the R9 contract would ship zero companions."
        )
    if companion not in names:
        raise RuntimeError(
            f"R9.11 parity violation: COMPANION_SKILL={companion!r} is absent from "
            f"the declared tree {root} (found: {names}). mcp.json, GET /skills and "
            f"the server's own companion identity must name the same skill."
        )
