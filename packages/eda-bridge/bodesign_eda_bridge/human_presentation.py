"""S2 human presentation ingestion -- native I/O half (DD-13, AC17).

Scope: read a human-authored KiCad schematic set as IMMUTABLE bytes, validate the
scoped manifest, inventory every object, and derive netlist / ERC / BOM / SVG
sidecars with kicad-cli.  This module never edits, renumbers, repartitions,
restyles or fits any source byte; the original set and the retained copy are
hashed before and after every derive step.

Policy (topology comparison, ChangeProposal construction, entrypoint sequencing)
lives in ``bodesign_workflow_core.human_presentation``.  This module imports no
workflow-core code and raises ``HumanPresentationError`` carrying named gaps.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bodesign_design_ir.rebuild_contracts import (
    ArtifactManifest,
    ArtifactRef,
    DependencyRef,
)

HUMAN_PRESENTATION_SCHEMA_VERSION = "1.0"

#: KiCad file-format version stamp -> KiCad release it belongs to.  Only stamps that
#: were actually exercised against the installed kicad-cli are listed; any other
#: stamp is an unsupported-syntax refusal, not a best-effort parse.
SUPPORTED_NATIVE_VERSIONS: dict[int, str] = {20250114: "9.0"}

SUPPORTED_KICAD_RELEASES = frozenset({"9.0"})

_MAX_DEPTH = 128
_KICAD_TIMEOUT_S = 120


class HumanPresentationError(ValueError):
    """Refusal carrying machine ``code`` and a list of named ``gaps``."""

    def __init__(self, code: str, message: str, gaps: list[dict] | None = None, **details):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.gaps = list(gaps or [])
        self.details = dict(details)
        if self.gaps:
            self.details["gaps"] = self.gaps


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Span-preserving s-expression reader.  Text is decoded latin-1 so every char
# offset IS a byte offset; display strings are re-decoded to UTF-8 on demand.
# ---------------------------------------------------------------------------

class Atom(str):
    quoted: bool = False


class Node:
    __slots__ = ("items", "start", "end")

    def __init__(self, start: int):
        self.items: list = []
        self.start = start
        self.end = -1

    @property
    def head(self) -> str:
        return str(self.items[0]) if self.items and isinstance(self.items[0], Atom) else ""

    def children(self, name: str) -> list["Node"]:
        return [c for c in self.items[1:] if isinstance(c, Node) and c.head == name]

    def child(self, name: str) -> "Node | None":
        found = self.children(name)
        return found[0] if found else None

    def atoms(self) -> list[str]:
        return [str(c) for c in self.items[1:] if isinstance(c, Atom)]


def _display(atom: str) -> str:
    try:
        return str(atom).encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return str(atom)


def parse_sexpr(text: str) -> Node:
    """Parse exactly one top-level form.  Raises ValueError on any malformation."""
    stack: list[Node] = []
    root: Node | None = None
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "(":
            if root is not None:
                raise ValueError(f"trailing top-level form at offset {i}")
            node = Node(i)
            if stack:
                stack[-1].items.append(node)
            stack.append(node)
            if len(stack) > _MAX_DEPTH:
                raise ValueError(f"nesting deeper than {_MAX_DEPTH} at offset {i}")
            i += 1
        elif c == ")":
            if not stack:
                raise ValueError(f"unbalanced ')' at offset {i}")
            node = stack.pop()
            node.end = i + 1
            if not stack:
                root = node
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            if j >= n:
                raise ValueError(f"unterminated string at offset {i}")
            atom = Atom("".join(buf))
            atom.quoted = True
            if not stack:
                raise ValueError(f"atom outside any form at offset {i}")
            stack[-1].items.append(atom)
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            if not stack:
                raise ValueError(f"atom outside any form at offset {i}")
            stack[-1].items.append(Atom(text[i:j]))
            i = j
    if stack:
        raise ValueError("unbalanced '(': form never closed")
    if root is None:
        raise ValueError("empty file: no top-level form")
    return root


# ---------------------------------------------------------------------------
# Scoped manifest -> NativeSet (all refusals happen here, before any write)
# ---------------------------------------------------------------------------

_GAP_CODES = {
    "baseline_changed": "E_BASELINE_CHANGED",
    "path_traversal": "E_PATH_TRAVERSAL",
    "symlink_escape": "E_PATH_ESCAPE",
    "missing_sheet": "E_MISSING_SHEET",
    "missing_file": "E_MISSING_SHEET",
    "unreferenced_file": "E_SHEET_PARTITION_AMBIGUOUS",
    "ambiguous_instance_mapping": "E_SHEET_PARTITION_AMBIGUOUS",
    "sheet_cycle": "E_SHEET_PARTITION_AMBIGUOUS",
    "unsupported_syntax": "E_UNSUPPORTED_SYNTAX",
    "unsupported_version": "E_UNSUPPORTED_SYNTAX",
    "undeclared_library": "E_UNRESOLVED_LIBRARY",
    "unresolved_symbol_definition": "E_UNRESOLVED_LIBRARY",
    "invalid_library_declaration": "E_UNRESOLVED_LIBRARY",
    "unresolved_identity": "E_UNRESOLVED_IDENTITY",
    "duplicate_identity": "E_UNRESOLVED_IDENTITY",
    "duplicate_uuid": "E_UNRESOLVED_IDENTITY",
    "unsupported_kicad_version": "E_KICAD_VERSION",
    "tool_version_mismatch": "E_KICAD_VERSION",
    "tool_unavailable": "E_TOOL_UNAVAILABLE",
    "missing_field": "E_BASELINE_MALFORMED",
    "malformed_field": "E_BASELINE_MALFORMED",
    "output_exists": "E_OUTPUT_EXISTS",
    "derive_incomplete": "E_DERIVE_FAILED",
    "pin_missing_from_export": "E_PIN_POPULATION_INCOMPLETE",
    "pin_not_in_native_symbols": "E_PIN_POPULATION_INCOMPLETE",
    "unresolved_pin_population": "E_PIN_POPULATION_INCOMPLETE",
}

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def refuse(gaps: list[dict], message: str | None = None) -> "HumanPresentationError":
    code = _GAP_CODES.get(gaps[0]["kind"], "E_BASELINE_MALFORMED") if gaps else "E_BASELINE_MALFORMED"
    kinds = sorted({g["kind"] for g in gaps})
    return HumanPresentationError(
        code, message or f"baseline refused before any write; named gaps: {kinds}", gaps)


def rel_path_error(path: Any) -> str | None:
    """Return the reason a manifest path is not a scoped relative POSIX path, else None."""
    if not isinstance(path, str) or not path:
        return "path must be a non-empty string"
    if "\x00" in path or "\\" in path:
        return "path contains NUL or backslash"
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return "absolute path"
    for seg in path.split("/"):
        if seg in ("", ".", ".."):
            return f"traversal or empty segment {seg!r}"
    return None


def find_kicad_cli() -> str | None:
    return shutil.which("kicad-cli")


def kicad_cli_version(cli: str) -> str:
    try:
        proc = subprocess.run([cli, "version"], capture_output=True, text=True,
                              timeout=_KICAD_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError) as exc:
        raise HumanPresentationError(
            "E_TOOL_UNAVAILABLE", f"kicad-cli version probe failed: {type(exc).__name__}: {exc}",
            [{"kind": "tool_unavailable", "tool": "kicad-cli", "detail": f"{type(exc).__name__}: {exc}"}])
    return proc.stdout.strip()


@dataclass
class NativeSheet:
    path: str
    abs_path: Path
    data: bytes
    sha256: str
    version: int
    node: Node
    text: str
    sheet_refs: list = field(default_factory=list)  # [{uuid,name,file(resolved rel),declared}]


@dataclass
class NativeSet:
    source_dir: Path
    root: str
    sheets: dict
    libraries: list
    kicad_version_declared: str
    kicad_cli: str
    kicad_cli_version: str

    def file_hashes(self) -> dict[str, str]:
        return {p: s.sha256 for p, s in self.sheets.items()}

    def manifest(self, revision_id: str, extra_dependencies: tuple = ()) -> ArtifactManifest:
        """Native bytes + CALLER-DECLARED library identities (+ any extra bound subjects).

        Library entries are not re-resolved against files on disk; only the embedded
        ``lib_symbols`` are covered, and those are covered by the sheet hashes.
        """
        refs = [ArtifactRef(role="native_root" if p == self.root else "native_sheet",
                            path=p, sha256=s.sha256, byte_size=len(s.data))
                for p, s in self.sheets.items()]
        return ArtifactManifest(schema_version="1.0", revision_id=revision_id,
                                artifacts=tuple(refs),
                                dependencies=tuple(self.libraries) + tuple(extra_dependencies))


def _text_of(node: Node, text: str) -> str:
    return text[node.start:node.end]


def _prop(node: Node, name: str) -> str | None:
    for p in node.children("property"):
        a = p.atoms()
        if len(a) >= 2 and a[0] == name:
            return a[1]
    return None


def _uuid_of(node: Node) -> str | None:
    u = node.child("uuid")
    if u is None:
        return None
    a = u.atoms()
    return a[0] if a else None


def _check_manifest_shape(baseline: Any) -> list[dict]:
    gaps: list[dict] = []
    if not isinstance(baseline, dict):
        raise HumanPresentationError("E_BASELINE_MALFORMED", "presentation_baseline must be an object",
                                     [{"kind": "malformed_field", "field": "presentation_baseline"}])
    sv = baseline.get("schema_version")
    if not isinstance(sv, str) or not sv.startswith("1."):
        gaps.append({"kind": "malformed_field", "field": "schema_version", "value": sv,
                     "detail": "unsupported major version (expected 1.x)"})
    for f_ in ("source_dir", "root", "kicad_version"):
        if not isinstance(baseline.get(f_), str) or not baseline.get(f_):
            gaps.append({"kind": "missing_field", "field": f_})
    for f_ in ("files", "libraries"):
        if not isinstance(baseline.get(f_), list):
            gaps.append({"kind": "missing_field", "field": f_})
    if isinstance(baseline.get("files"), list) and not baseline["files"]:
        gaps.append({"kind": "missing_field", "field": "files", "detail": "empty file set"})
    return gaps


def _inside(root: str, candidate: str) -> bool:
    try:
        return os.path.commonpath([root, candidate]) == root
    except ValueError:
        return False


def _parse_libraries(raw: list) -> tuple[list, list[dict]]:
    libs, gaps = [], []
    for i, entry in enumerate(raw):
        try:
            if not isinstance(entry, dict):
                raise ValueError("library entry must be an object")
            libs.append(DependencyRef(kind="library", name=entry.get("name"),
                                      version=entry.get("version"), digest=entry.get("digest")))
        except (ValueError, TypeError) as exc:
            gaps.append({"kind": "invalid_library_declaration", "index": i, "detail": str(exc)})
    names = [d.name for d in libs]
    for dup in sorted({n for n in names if names.count(n) > 1}):
        gaps.append({"kind": "invalid_library_declaration", "library": dup, "detail": "duplicate name"})
    return libs, gaps


def load_native_set(baseline: Any, *, require_tool: bool = True) -> NativeSet:
    """Validate the scoped manifest and read the native set.  READ ONLY.

    Collects every named gap it can see and raises one ``HumanPresentationError``;
    nothing is written anywhere.  The sheet partition is whatever the root's own
    ``sheet`` blocks say -- it is never inferred or completed.
    """
    gaps = _check_manifest_shape(baseline)
    if baseline.get("source") != "human":
        gaps.append({"kind": "malformed_field", "field": "source", "value": baseline.get("source"),
                     "detail": "presentation_baseline.source must be 'human' for this entrypoint"})
    declared_release = str(baseline.get("kicad_version", ""))
    if declared_release and declared_release not in SUPPORTED_KICAD_RELEASES:
        gaps.append({"kind": "unsupported_kicad_version", "value": declared_release,
                     "supported": sorted(SUPPORTED_KICAD_RELEASES)})
    libs, lib_gaps = _parse_libraries(baseline.get("libraries") if isinstance(baseline.get("libraries"), list) else [])
    gaps += lib_gaps
    if gaps:
        raise refuse(gaps)

    src = Path(baseline["source_dir"])
    if not src.is_absolute() or not src.is_dir():
        raise refuse([{"kind": "missing_file", "path": str(src), "detail": "source_dir is not an existing absolute directory"}])
    real_root = os.path.realpath(src)

    declared: dict[str, dict] = {}
    for i, entry in enumerate(baseline["files"]):
        p = entry.get("path") if isinstance(entry, dict) else None
        why = rel_path_error(p)
        if why:
            gaps.append({"kind": "path_traversal", "index": i, "path": p, "detail": why})
            continue
        if p in declared:
            gaps.append({"kind": "malformed_field", "field": "files", "path": p, "detail": "duplicate path"})
            continue
        if not p.endswith(".kicad_sch"):
            gaps.append({"kind": "unsupported_syntax", "path": p, "detail": "only .kicad_sch files are in scope"})
            continue
        if not isinstance(entry.get("sha256"), str) or not _HEX64.match(entry["sha256"]):
            gaps.append({"kind": "missing_field", "field": "files[].sha256", "path": p})
            continue
        declared[p] = entry
    root = baseline["root"]
    why = rel_path_error(root)
    if why:
        gaps.append({"kind": "path_traversal", "path": root, "detail": why})
    elif root not in declared:
        gaps.append({"kind": "missing_sheet", "path": root, "detail": "root is not in the declared file set"})

    sheets: dict[str, NativeSheet] = {}
    for p, entry in declared.items():
        abs_p = src / p
        real = os.path.realpath(abs_p)
        if not _inside(real_root, real):
            gaps.append({"kind": "symlink_escape", "path": p, "resolves_to": real})
            continue
        if not os.path.isfile(real):
            gaps.append({"kind": "missing_sheet", "path": p, "detail": "declared file does not exist"})
            continue
        data = Path(real).read_bytes()
        digest = sha256_bytes(data)
        if digest != entry["sha256"].lower():
            gaps.append({"kind": "baseline_changed", "path": p, "declared_sha256": entry["sha256"].lower(),
                         "actual_sha256": digest})
            continue
        text = data.decode("latin-1")
        try:
            node = parse_sexpr(text)
        except ValueError as exc:
            gaps.append({"kind": "unsupported_syntax", "path": p, "detail": f"unparseable: {exc}"})
            continue
        if node.head != "kicad_sch":
            gaps.append({"kind": "unsupported_syntax", "path": p, "detail": f"top-level form is {node.head!r}"})
            continue
        ver_node = node.child("version")
        try:
            ver = int(ver_node.atoms()[0])
        except (AttributeError, IndexError, ValueError):
            gaps.append({"kind": "unsupported_version", "path": p, "detail": "no readable (version N)"})
            continue
        if ver not in SUPPORTED_NATIVE_VERSIONS:
            gaps.append({"kind": "unsupported_version", "path": p, "version": ver,
                         "supported": sorted(SUPPORTED_NATIVE_VERSIONS)})
            continue
        sheets[p] = NativeSheet(path=p, abs_path=Path(real), data=data, sha256=digest, version=ver,
                                node=node, text=text)
    if gaps:
        raise refuse(gaps)

    gaps += _resolve_sheet_graph(sheets, root, set(declared))
    gaps += _check_identity_and_libraries(sheets, {d.name for d in libs})
    cli = find_kicad_cli()
    cli_ver = ""
    if cli is None:
        if require_tool:
            gaps.append({"kind": "tool_unavailable", "tool": "kicad-cli"})
    else:
        cli_ver = kicad_cli_version(cli)
        if not cli_ver.startswith(declared_release + "."):
            gaps.append({"kind": "tool_version_mismatch", "declared": declared_release, "kicad_cli": cli_ver})
    if gaps:
        raise refuse(gaps)
    return NativeSet(source_dir=Path(real_root), root=root, sheets=sheets, libraries=libs,
                     kicad_version_declared=declared_release, kicad_cli=cli or "", kicad_cli_version=cli_ver)


def _resolve_sheet_graph(sheets: dict, root: str, declared: set) -> list[dict]:
    """Every referenced sheet must be declared; every declared sheet must be referenced.

    Partition is read from the sheet blocks themselves.  A file reached by two sheet
    blocks (reused leaf) is refused as ambiguous instance mapping, not mapped.
    """
    gaps: list[dict] = []
    reached: dict[str, str] = {}
    stack, seen = [root], set()
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        sheet = sheets[cur]
        for blk in sheet.node.children("sheet"):
            fname = _prop(blk, "Sheetfile")
            sname = _prop(blk, "Sheetname")
            uid = _uuid_of(blk)
            if not fname:
                gaps.append({"kind": "unresolved_identity", "path": cur, "sheet": sname,
                             "detail": "sheet block has no Sheetfile property"})
                continue
            why = rel_path_error(fname)
            if why:
                gaps.append({"kind": "path_traversal", "path": cur, "sheet_file": fname, "detail": why})
                continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(cur), fname))
            if target.startswith(".."):
                gaps.append({"kind": "path_traversal", "path": cur, "sheet_file": fname,
                             "detail": "resolves outside the scoped set"})
                continue
            if target not in declared:
                gaps.append({"kind": "missing_sheet", "path": target, "referenced_by": cur,
                             "sheet": sname, "detail": "referenced sheet is not in the declared file set"})
                continue
            if target in reached:
                gaps.append({"kind": "ambiguous_instance_mapping", "path": target,
                             "detail": f"referenced by more than one sheet block ({reached[target]} and {cur}:{sname})"})
                continue
            if target == root or target == cur:
                gaps.append({"kind": "sheet_cycle", "path": target, "referenced_by": cur})
                continue
            reached[target] = f"{cur}:{sname}"
            sheet.sheet_refs.append({"uuid": uid, "name": sname, "file": target})
            stack.append(target)
    for p in sorted(declared - seen):
        gaps.append({"kind": "unreferenced_file", "path": p,
                     "detail": "declared but not reachable from the root; partition is never inferred"})
    return gaps


def _check_identity_and_libraries(sheets: dict, declared_libs: set) -> list[dict]:
    gaps: list[dict] = []
    uuids: dict[str, str] = {}
    refs: dict[tuple, str] = {}
    for p, sh in sheets.items():
        embedded = set()
        ls = sh.node.child("lib_symbols")
        if ls is not None:
            embedded = {c.atoms()[0] for c in ls.children("symbol") if c.atoms()}
        for obj in sh.node.items[1:]:
            if not isinstance(obj, Node):
                continue
            u = _uuid_of(obj)
            if u:
                if u in uuids:
                    gaps.append({"kind": "duplicate_uuid", "uuid": u, "paths": [uuids[u], p]})
                uuids[u] = p
            if obj.head != "symbol":
                continue
            for pin in obj.children("pin"):
                pu = _uuid_of(pin)
                if pu:
                    if pu in uuids:
                        gaps.append({"kind": "duplicate_uuid", "uuid": pu, "paths": [uuids[pu], p]})
                    uuids[pu] = p
            lib_node = obj.child("lib_id")
            lib_id = lib_node.atoms()[0] if lib_node is not None and lib_node.atoms() else ""
            ref = _prop(obj, "Reference")
            if not ref or not lib_id:
                gaps.append({"kind": "unresolved_identity", "path": p, "uuid": u,
                             "detail": "symbol without Reference or lib_id"})
                continue
            prefix = lib_id.split(":", 1)[0] if ":" in lib_id else ""
            if prefix not in declared_libs:
                gaps.append({"kind": "undeclared_library", "path": p, "ref": ref, "lib_id": lib_id,
                             "library": prefix})
            if lib_id not in embedded:
                gaps.append({"kind": "unresolved_symbol_definition", "path": p, "ref": ref, "lib_id": lib_id})
            unit_node = obj.child("unit")
            key = (ref, unit_node.atoms()[0] if unit_node is not None and unit_node.atoms() else "1")
            if key in refs:
                gaps.append({"kind": "duplicate_identity", "ref": ref, "paths": [refs[key], p]})
            refs[key] = p
    return gaps


# ---------------------------------------------------------------------------
# Object inventory (read-only): every UUID is pinned, nothing is selected by caller
# ---------------------------------------------------------------------------

def _at(node: Node) -> list[float] | None:
    a = node.child("at")
    if a is None:
        return None
    try:
        return [float(x) for x in a.atoms()]
    except ValueError:
        return None


def inventory(ns: NativeSet) -> dict:
    """Inventory every top-level object of every sheet.  Unknown heads are listed, not dropped."""
    sheets: dict[str, dict] = {}
    pinned: list[str] = []
    for p, sh in sorted(ns.sheets.items()):
        heads: dict[str, int] = {}
        symbols, wires, labels, no_connects = [], [], [], []
        for obj in sh.node.items[1:]:
            if not isinstance(obj, Node):
                continue
            heads[obj.head] = heads.get(obj.head, 0) + 1
            u = _uuid_of(obj)
            if u:
                pinned.append(f"{p}#{u}")
            if obj.head == "uuid" and obj.atoms():
                pinned.append(f"{p}#{obj.atoms()[0]}")  # the sheet's own identity is pinned too
            if obj.head == "symbol":
                lib = obj.child("lib_id")
                symbols.append({
                    "uuid": u, "lib_id": lib.atoms()[0] if lib is not None and lib.atoms() else None,
                    "ref": _display(_prop(obj, "Reference") or ""), "value": _display(_prop(obj, "Value") or ""),
                    "footprint": _display(_prop(obj, "Footprint") or ""), "at": _at(obj),
                    "pins": {pn.atoms()[0]: _uuid_of(pn) for pn in obj.children("pin") if pn.atoms()},
                })
                pinned.extend(f"{p}#{_uuid_of(pn)}" for pn in obj.children("pin") if _uuid_of(pn))
            elif obj.head == "wire":
                wires.append({"uuid": u})
            elif obj.head in ("label", "global_label", "hierarchical_label"):
                labels.append({"uuid": u, "kind": obj.head, "text": _display(obj.atoms()[0]) if obj.atoms() else "",
                               "at": _at(obj)})
            elif obj.head == "no_connect":
                no_connects.append({"uuid": u, "at": _at(obj)})
        sheets[p] = {"sha256": sh.sha256, "byte_size": len(sh.data), "native_version": sh.version,
                     "heads": heads, "symbols": symbols, "wires": wires, "labels": labels,
                     "no_connects": no_connects, "sheet_blocks": list(sh.sheet_refs)}
    return {"sheets": sheets, "pinned_object_ids": sorted(set(pinned))}


# ---------------------------------------------------------------------------
# Immutable retention + hash assertions
# ---------------------------------------------------------------------------

def assert_unchanged(ns: NativeSet, where: Path | None = None) -> dict[str, str]:
    """Re-hash the originals (and the retained copy under ``where``); raise on any drift."""
    gaps = []
    for p, sh in ns.sheets.items():
        for label, path in (("source", sh.abs_path),) + ((("retained_copy", where / p),) if where else ()):
            actual = sha256_file(path) if path.is_file() and not (label == "retained_copy" and path.is_symlink()) else None
            if actual != sh.sha256:
                gaps.append({"kind": "baseline_changed", "path": p, "location": label,
                             "declared_sha256": sh.sha256, "actual_sha256": actual})
    if gaps:
        raise refuse(gaps, "native bytes changed during inspect/derive")
    return ns.file_hashes()


def exclusive_write(path: Path, data: bytes) -> None:
    """Create ``path`` exclusively and without following a final-component symlink.

    O_EXCL on a path that already exists (file, hardlink or symlink, even a dangling
    one) raises FileExistsError, so an alias planted in an output location can never
    be written through.  Callers only use it inside a workspace they created fresh.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def create_fresh_workspace(out_dir: Path) -> None:
    """Exclusively create ``out_dir``.  An existing path of ANY kind is refused."""
    if os.path.lexists(out_dir):
        raise HumanPresentationError(
            "E_OUTPUT_EXISTS", f"output workspace already exists: {out_dir}",
            [{"kind": "output_exists", "path": str(out_dir),
              "detail": "a fresh workspace is required; existing files, symlinks and hardlinks are never reused"}])
    out_dir.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.mkdir(out_dir, 0o700)
    except FileExistsError:
        raise HumanPresentationError(
            "E_OUTPUT_EXISTS", f"output workspace appeared concurrently: {out_dir}",
            [{"kind": "output_exists", "path": str(out_dir)}])


def retain_copy(ns: NativeSet, dest: Path) -> dict[str, str]:
    """Write the exact bytes of every sheet into a NEW directory and verify by hash."""
    if os.path.lexists(dest):
        raise HumanPresentationError(
            "E_OUTPUT_EXISTS", f"retention dir already exists: {dest}",
            [{"kind": "output_exists", "path": str(dest), "detail": "refusing to reuse"}])
    os.mkdir(dest, 0o700)
    for p, sh in ns.sheets.items():
        target = dest / p
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        exclusive_write(target, sh.data)
    return assert_unchanged(ns, dest)


# ---------------------------------------------------------------------------
# kicad-cli derivation -> SEPARATE sidecar artifacts, each with an export receipt
# ---------------------------------------------------------------------------

def _run_export(ns: NativeSet, kind: str, argv: list[str], out_path: Path, inputs: dict[str, str],
                expected_files: int) -> dict:
    """Run one export.  NEVER raises for a tool failure: a failed export is a receipt.

    ``succeeded`` needs rc == 0 AND exactly ``expected_files`` non-empty regular output
    files.  A directory that merely exists (created before the run) proves nothing.
    """
    receipt = {
        "kind": kind, "command": argv, "command_text": " ".join(argv),
        "kicad_cli": ns.kicad_cli, "kicad_cli_version": ns.kicad_cli_version,
        "input_hashes": dict(inputs), "returncode": None,
        "stdout_excerpt": "", "stderr_excerpt": "", "status": "failed", "failure": None,
        "coverage": {"expected_files": expected_files, "actual_nonempty_files": 0},
        "output": None,
    }
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=_KICAD_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError) as exc:
        receipt["failure"] = f"{type(exc).__name__}: {exc}"
        return receipt
    receipt.update(returncode=proc.returncode, stdout_excerpt=proc.stdout.strip()[:300],
                   stderr_excerpt=proc.stderr.strip()[:300])
    try:
        if out_path.is_dir():
            files = sorted(f for f in out_path.rglob("*") if f.is_file() and not f.is_symlink())
        elif out_path.is_file() and not out_path.is_symlink():
            files = [out_path]
        else:
            files = []
        listed = [{"path": str(f), "sha256": sha256_file(f), "byte_size": f.stat().st_size} for f in files]
    except OSError as exc:
        receipt["failure"] = f"output unreadable: {type(exc).__name__}: {exc}"
        return receipt
    nonempty = [o for o in listed if o["byte_size"] > 0]
    receipt["coverage"]["actual_nonempty_files"] = len(nonempty)
    if listed:
        receipt["output"] = ({"path": str(out_path), **listed[0]} if out_path.is_file()
                             else {"path": str(out_path), "files": listed})
    if proc.returncode != 0:
        receipt["failure"] = f"kicad-cli returned {proc.returncode}"
    elif len(nonempty) != expected_files or len(listed) != len(nonempty):
        receipt["failure"] = (f"expected {expected_files} non-empty output file(s), found "
                              f"{len(nonempty)} non-empty of {len(listed)}")
    else:
        receipt["status"] = "succeeded"
    return receipt


def erc_findings(erc_json: Path) -> dict:
    """Count ERC violations by severity.  These are FINDINGS, not execution failure, not approval."""
    def invalid(detail: str) -> HumanPresentationError:
        return HumanPresentationError(
            "E_OUTPUT_INVALID", f"ERC output is not usable evidence: {detail}",
            [{"kind": "output_validation", "tool": "erc", "path": str(erc_json), "detail": detail}])

    try:
        data = json.loads(Path(erc_json).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:    # ValueError covers JSONDecodeError / UnicodeDecodeError
        raise invalid(f"unreadable or invalid JSON: {type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise invalid(f"top-level JSON is {type(data).__name__}, expected an object")
    sheets = data.get("sheets")
    if not isinstance(sheets, list):
        raise invalid("missing 'sheets' list (an absent schema is never 'zero findings')")
    counts: dict[str, int] = {}
    for si, sh in enumerate(sheets):
        if not isinstance(sh, dict) or not isinstance(sh.get("violations"), list):
            raise invalid(f"sheets[{si}] is not an object with a 'violations' list")
        for vi, v in enumerate(sh["violations"]):
            if not isinstance(v, dict) or not isinstance(v.get("severity"), str) or not v["severity"]:
                raise invalid(f"sheets[{si}].violations[{vi}] lacks a string 'severity'")
            counts[v["severity"]] = counts.get(v["severity"], 0) + 1
    return {"by_severity": counts, "total": sum(counts.values()),
            "meaning": "findings only; not an execution failure and not an approval"}


def derive_sidecars(ns: NativeSet, work_dir: Path) -> dict:
    """Retain the exact bytes, then derive netlist / ERC / BOM / SVG companions from the copy.

    The tool runs on the retained copy, never on the caller's files.  Source and copy are
    hash-asserted before and after.  Every receipt records inputs, outputs and the exact argv.
    """
    if not ns.kicad_cli:
        raise HumanPresentationError("E_TOOL_UNAVAILABLE", "kicad-cli is not available",
                                     [{"kind": "tool_unavailable", "tool": "kicad-cli"}])
    # work_dir is a workspace the CALLER just created exclusively (create_fresh_workspace).
    if work_dir.is_symlink() or not work_dir.is_dir() or any(work_dir.iterdir()):
        raise HumanPresentationError(
            "E_OUTPUT_EXISTS", f"derive workspace must be a fresh empty directory: {work_dir}",
            [{"kind": "output_exists", "path": str(work_dir)}])
    copy_dir = work_dir / "baseline_copy"
    side = work_dir / "sidecars"
    before = assert_unchanged(ns)
    retain_copy(ns, copy_dir)
    os.mkdir(side, 0o700)
    for sub in ("netlist", "erc", "bom", "companion_svg"):
        os.mkdir(side / sub, 0o700)
    root = str(copy_dir / ns.root)
    cli = ns.kicad_cli
    n_sheets = len(ns.sheets)
    jobs = {
        "netlist": ([cli, "sch", "export", "netlist", "--format", "kicadsexpr", "-o",
                     str(side / "netlist" / "native.net"), root], side / "netlist" / "native.net", 1),
        "erc": ([cli, "sch", "erc", "--format", "json", "--severity-all", "-o",
                 str(side / "erc" / "erc.json"), root], side / "erc" / "erc.json", 1),
        "bom": ([cli, "sch", "export", "bom", "-o", str(side / "bom" / "bom.csv"), root],
                side / "bom" / "bom.csv", 1),
        # one SVG per sheet of the (unreused) hierarchy
        "companion_svg": ([cli, "sch", "export", "svg", "-o", str(side / "companion_svg"), root],
                          side / "companion_svg", n_sheets),
    }
    receipts = {k: _run_export(ns, k, argv, out, before, n) for k, (argv, out, n) in jobs.items()}
    try:
        after = assert_unchanged(ns, copy_dir)
        if after != before:  # defence in depth; assert_unchanged already raises
            raise refuse([{"kind": "baseline_changed", "detail": "hash map differs after derive"}])
    except HumanPresentationError as exc:
        exc.details["receipts"] = receipts      # keep what was actually produced
        raise
    failed = {k for k, r in receipts.items() if r["status"] != "succeeded"}
    findings = None
    output_validation: dict[str, str] = {}
    if receipts["erc"]["status"] == "succeeded":
        try:
            findings = erc_findings(Path(receipts["erc"]["output"]["path"]))
        except HumanPresentationError as exc:
            # Execution succeeded (rc=0 receipt and the file are preserved) but the evidence is unusable.
            output_validation["erc"] = exc.message
            failed.add("erc")
            findings = {"unusable": exc.message,
                        "meaning": "ERC ran but its output failed schema validation; NOT zero findings"}
    failed = sorted(failed)
    derive_status = ("failed" if "netlist" in failed else "partial" if failed else "complete")
    return {"work_dir": str(work_dir), "baseline_copy": str(copy_dir), "receipts": receipts,
            "hashes_before": before, "hashes_after": after, "unchanged": True,
            "derive_status": derive_status, "failed_sidecars": failed, "erc_findings": findings,
            "output_validation_failures": output_validation,
            "netlist_path": (receipts["netlist"]["output"]["path"]
                             if receipts["netlist"]["status"] == "succeeded" else None)}


def list_files(root: Path) -> list[str]:
    """Regular, non-symlink files actually present under ``root`` (a fresh workspace)."""
    if not root.is_dir():
        return []
    return sorted(str(p) for p in root.rglob("*") if p.is_file() and not p.is_symlink())


# ---------------------------------------------------------------------------
# Expected native pin population (symbol / embedded lib_symbols), independent of the export
# ---------------------------------------------------------------------------

_SUBSYM = re.compile(r"^(.*)_(\d+)_(\d+)$")


def native_pin_population(ns: NativeSet) -> dict:
    """Pins every placed symbol instance SHOULD expose, read from its embedded definition.

    Power symbols and ``#``-references are not components and are excluded.  A symbol
    whose definition cannot be read is reported in ``unresolved`` -- never skipped.
    """
    expected: dict[str, str] = {}
    unresolved: list[dict] = []
    for p, sh in sorted(ns.sheets.items()):
        ls = sh.node.child("lib_symbols")
        defs = {c.atoms()[0]: c for c in (ls.children("symbol") if ls is not None else []) if c.atoms()}
        for obj in sh.node.children("symbol"):
            lib = obj.child("lib_id")
            lib_id = lib.atoms()[0] if lib is not None and lib.atoms() else ""
            ref = _prop(obj, "Reference") or ""
            d = defs.get(lib_id)
            if ref.startswith("#") or (d is not None and d.child("power") is not None):
                continue
            if d is None or d.child("extends") is not None:
                unresolved.append({"path": p, "ref": ref, "lib_id": lib_id,
                                   "detail": "no readable embedded definition"})
                continue
            unit_node = obj.child("unit")
            try:
                unit = int(unit_node.atoms()[0]) if unit_node is not None and unit_node.atoms() else 1
            except ValueError:
                unit = 1
            numbers = {n.atoms()[0] for pin in d.children("pin") for n in pin.children("number") if n.atoms()}
            for sub in d.children("symbol"):
                m = _SUBSYM.match(sub.atoms()[0]) if sub.atoms() else None
                if m is None:
                    unresolved.append({"path": p, "ref": ref, "lib_id": lib_id,
                                       "detail": f"unrecognised sub-symbol name {sub.atoms()[:1]}"})
                    continue
                if int(m.group(2)) in (0, unit):
                    numbers |= {n.atoms()[0] for pin in sub.children("pin")
                                for n in pin.children("number") if n.atoms()}
            if not numbers:
                unresolved.append({"path": p, "ref": ref, "lib_id": lib_id, "detail": "definition lists no pins"})
                continue
            for n in numbers:
                expected[f"{_display(ref)}.{n}"] = f"{p}#{_uuid_of(obj)}"
    return {"expected": expected, "unresolved": unresolved}


def reconcile_pin_population(pop: dict, native: dict) -> list[dict]:
    """Compare expected symbol pins with the exported node population.  Refuse, never assign."""
    gaps: list[dict] = []
    exported = set(native["all_nodes"])
    expected = set(pop["expected"])
    missing = sorted(expected - exported)
    extra = sorted(exported - expected)
    if missing:
        gaps.append({"kind": "pin_missing_from_export", "pins": missing,
                     "symbols": sorted({pop["expected"][m] for m in missing}),
                     "detail": "present on placed symbols but absent from the kicad-cli export; "
                               "not treated as NC or isolated"})
    if extra:
        gaps.append({"kind": "pin_not_in_native_symbols", "pins": extra,
                     "detail": "exported nodes with no matching placed-symbol pin"})
    for u in pop["unresolved"]:
        gaps.append({"kind": "unresolved_pin_population", **u})
    return gaps


def parse_native_connectivity(netlist_path: Path) -> dict:
    """Read the kicad-cli netlist into declared-comparable form.  Names are kept, not trusted."""
    def bad(detail: str) -> HumanPresentationError:
        return HumanPresentationError(
            "E_OUTPUT_INVALID", f"native netlist is not usable evidence: {detail}",
            [{"kind": "output_validation", "tool": "netlist", "path": str(netlist_path), "detail": detail}])

    try:
        root = parse_sexpr(Path(netlist_path).read_bytes().decode("latin-1"))
    except ValueError as exc:
        raise bad(f"unparseable s-expression: {exc}") from exc
    if root.head != "export":
        raise bad(f"root form is '{root.head}', expected 'export'")
    nets_node = root.child("nets")
    comps = root.child("components")
    if nets_node is None or comps is None:
        raise bad("missing required 'nets' and/or 'components' section")
    nets, nc, isolated, all_nodes = [], [], [], []
    for ni, net in enumerate(nets_node.children("net")):
        name_node = net.child("name")
        if name_node is None or not name_node.atoms():
            raise bad(f"net[{ni}] has no name atom")
        name = _display(name_node.atoms()[0])
        nodes = []
        for di, nd in enumerate(net.children("node")):
            ref = nd.child("ref")
            pin = nd.child("pin")
            ptype = nd.child("pintype")
            if ref is None or not ref.atoms() or pin is None or not pin.atoms():
                raise bad(f"net[{ni}] ({name!r}) node[{di}] lacks a ref and/or pin atom")
            ident = f"{ref.atoms()[0]}.{pin.atoms()[0]}"
            nodes.append(ident)
            all_nodes.append(ident)
            if ptype is not None and ptype.atoms() and "no_connect" in ptype.atoms()[0]:
                nc.append(ident)
        if name.startswith("unconnected-") and len(nodes) == 1 and nodes[0] not in nc:
            isolated.append(nodes[0])
        nets.append({"name": name, "nodes": sorted(nodes)})
    refs = []
    for ci, c in enumerate(comps.children("comp")):
        r = c.child("ref")
        if r is None or not r.atoms():
            raise bad(f"components.comp[{ci}] has no ref atom")
        refs.append(r.atoms()[0])
    refs.sort()
    return {"nets": sorted(nets, key=lambda n: n["nodes"]), "nc_nodes": sorted(nc),
            "isolated_nodes": sorted(isolated), "all_nodes": sorted(all_nodes), "components": refs}
