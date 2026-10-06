"""S2 human presentation ingestion -- policy half (DD-13, AC17).

``ingest_human_presentation`` is the body behind the existing formal entrypoint
``bodesign_emit_multisheet`` when ``presentation_baseline`` is supplied.  It is
inspect/derive only:

* the native set is read as immutable bytes (eda-bridge ``human_presentation``);
* netlist / ERC / BOM / SVG companions are derived as SEPARATE sidecars, each with
  an export receipt;
* declared topology is compared to the native export; any disagreement becomes a
  P1 ``ChangeProposal`` bound to the baseline manifest and declared revision;
* value / footprint / annotation / label requests become proposals too;
* APPLY IS NOT IMPLEMENTED.  A proposal is not approval, and nothing here claims an
  atomic compare-and-apply.

Source ``human`` conveys editing authority only -- never readable / electrically
approved status.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from bodesign_design_ir.rebuild_contracts import DependencyRef
from bodesign_workflow_core.rebuild_compat import check_baseline_preconditions
from bodesign_workflow_core.rebuild_contracts import (
    ChangeProposal,
    OperationOutcome,
)


APPLY_STATUS = "NOT_IMPLEMENTED"

#: Edit classes a human may REQUEST as proposals.  None is performable in S2.
REQUESTABLE_EDIT_CLASSES = ("set_value", "set_footprint", "set_annotation", "add_label")
TOPOLOGY_EDIT_CLASS = "reconcile_topology"
SUPPORTED_EDIT_CLASSES = (TOPOLOGY_EDIT_CLASS,) + REQUESTABLE_EDIT_CLASSES

#: Legacy emit kwargs that would restyle / repartition / re-place; refused with a baseline.
_EMIT_ONLY_ARGS = ("paper", "connection_style", "power_ports", "subsystem_views",
                   "view_local_max_nodes", "trim_small_replicas", "symbol_dirs")

DOES_NOT_AUTHORIZE = ["electrical_correctness", "readability", "manufacturing_release",
                      "human_source_is_not_approval"]

_NODE_RE = re.compile(r"^[^\s.]+\.\S+$")


def _err(code: str, message: str, gaps: list[dict] | None = None):
    from bodesign_eda_bridge.human_presentation import HumanPresentationError
    return HumanPresentationError(code, message, gaps)


# ---------------------------------------------------------------------------
# Declared circuit validation (separate topology authority)
# ---------------------------------------------------------------------------

def validate_declared_circuit(declared: Any) -> dict:
    """Normalise the declared circuit or refuse with named gaps.  Never infers."""
    if not isinstance(declared, dict):
        raise _err("E_DECLARED_CIRCUIT_MISSING", "declared_circuit is required with presentation_baseline",
                   [{"kind": "missing_field", "field": "declared_circuit"}])
    gaps: list[dict] = []
    rev = declared.get("revision")
    if not isinstance(rev, str) or not rev.strip():
        gaps.append({"kind": "missing_field", "field": "declared_circuit.revision"})
    nets_raw = declared.get("nets", [])
    nc_raw = declared.get("nc", [])
    iso_raw = declared.get("isolated", [])
    if not isinstance(nets_raw, list):
        gaps.append({"kind": "malformed_field", "field": "declared_circuit.nets"})
        nets_raw = []
    for fld, val in (("nc", nc_raw), ("isolated", iso_raw)):
        if not isinstance(val, list):
            gaps.append({"kind": "malformed_field", "field": f"declared_circuit.{fld}"})
    # An all-NC / all-isolated circuit (nets == []) is a supported bounded case; a circuit
    # that declares nothing at all is not a declaration.
    if (not nets_raw and not (isinstance(nc_raw, list) and nc_raw)
            and not (isinstance(iso_raw, list) and iso_raw)):
        gaps.append({"kind": "missing_field", "field": "declared_circuit.nets",
                     "detail": "declare at least one net, nc pin or isolated pin"})
    names = [str(n.get("name", f"net{i}")) for i, n in enumerate(nets_raw) if isinstance(n, dict)]
    for dup in sorted({x for x in names if names.count(x) > 1}):
        gaps.append({"kind": "malformed_field", "field": "declared_circuit.nets", "value": dup,
                     "detail": "duplicate declared net name; names are never merged or used as identity"})
    nets: list[dict] = []
    seen: dict[str, str] = {}

    def _take(node: Any, role: str) -> str | None:
        if not isinstance(node, str) or not _NODE_RE.match(node):
            gaps.append({"kind": "malformed_field", "field": f"declared_circuit.{role}", "value": node,
                         "detail": "node must be 'REF.PIN'"})
            return None
        if node in seen:
            gaps.append({"kind": "malformed_field", "field": f"declared_circuit.{role}", "value": node,
                         "detail": f"node already declared as {seen[node]}"})
            return None
        seen[node] = role
        return node

    for i, net in enumerate(nets_raw):
        if not isinstance(net, dict) or not isinstance(net.get("nodes"), list):
            gaps.append({"kind": "malformed_field", "field": f"declared_circuit.nets[{i}]"})
            continue
        nodes = [n for n in (_take(x, f"net:{net.get('name', i)}") for x in net["nodes"]) if n]
        if len(nodes) < 2:
            gaps.append({"kind": "malformed_field", "field": f"declared_circuit.nets[{i}]",
                         "detail": "a declared net needs >= 2 nodes; single pins belong in nc / isolated"})
            continue
        nets.append({"name": str(net.get("name", f"net{i}")), "nodes": sorted(nodes)})
    nc = sorted(n for n in (_take(x, "nc") for x in (nc_raw if isinstance(nc_raw, list) else [])) if n)
    iso = sorted(n for n in (_take(x, "isolated") for x in (iso_raw if isinstance(iso_raw, list) else [])) if n)
    if gaps:
        raise _err("E_DECLARED_CIRCUIT_MALFORMED", "declared_circuit refused; named gaps: "
                   + str(sorted({g['kind'] for g in gaps})), gaps)
    out = {"revision": rev.strip(), "nets": sorted(nets, key=lambda n: n["nodes"]),
           "nc": nc, "isolated": iso}
    out["sha256"] = declared_circuit_sha256(out)
    return out


def declared_circuit_sha256(declared: dict) -> str:
    """Canonical digest of the declared topology authority (revision, nets, nc, isolated)."""
    payload = {k: declared[k] for k in ("revision", "nets", "nc", "isolated")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Topology comparison: declared vs native export.  Neither side is edited.
# ---------------------------------------------------------------------------

def compare_topology(declared: dict, native: dict) -> list[dict]:
    """Return mismatch records (kinds: missing, split, fused, nc, isolated, undeclared_native)."""
    out: list[dict] = []
    native_all = set(native["all_nodes"])
    nc_native = set(native["nc_nodes"])
    cls_of: dict[str, int] = {}
    cls_nodes: dict[int, list[str]] = {}
    for idx, net in enumerate(native["nets"]):
        cls_nodes[idx] = list(net["nodes"])
        for n in net["nodes"]:
            cls_of[n] = idx

    def state(node: str) -> str:
        if node in nc_native:
            return "nc"
        return "connected" if len(cls_nodes[cls_of[node]]) >= 2 else "isolated"

    # Identity of a declared net is its unique partition cell (index), NEVER its display
    # name: validate_declared_circuit refuses duplicate names, and fused/split below are
    # computed on cell ids so labels cannot hide or fabricate a merge.
    net_cell: dict[str, int] = {}
    cell_name: dict[int, str] = {}
    for ci, net in enumerate(declared["nets"]):
        cell_name[ci] = net["name"]
        for n in net["nodes"]:
            net_cell[n] = ci
    net_label = {n: cell_name[c] for n, c in net_cell.items()}
    role = {n: "net" for n in net_cell}
    role.update({n: "nc" for n in declared["nc"]})
    role.update({n: "isolated" for n in declared["isolated"]})

    for node in sorted(role):
        if node not in native_all:
            out.append({"kind": "missing", "affected_nodes": [node],
                        "before": {"native": None},
                        "after": {"declared_role": role[node],
                                  "declared_net": net_label.get(node)},
                        "detail": "declared pin does not exist in the native export"})

    for net in declared["nets"]:
        present = [n for n in net["nodes"] if n in native_all]
        groups: dict[int, list[str]] = {}
        for n in present:
            st = state(n)
            if st == "connected":
                groups.setdefault(cls_of[n], []).append(n)
            else:
                out.append({"kind": "nc" if st == "nc" else "isolated", "affected_nodes": [n],
                            "before": {"native_state": st},
                            "after": {"declared_role": "net", "declared_net": net["name"],
                                      "declared_nodes": net["nodes"]},
                            "detail": f"declared connected on {net['name']}, native pin is {st}"})
        if len(groups) > 1:
            out.append({"kind": "split", "affected_nodes": sorted(n for g in groups.values() for n in g),
                        "before": {"native_nets": [sorted(g) for g in groups.values()]},
                        "after": {"declared_net": net["name"], "declared_nodes": net["nodes"]},
                        "detail": "declared net is split across separate native nets"})

    for idx, nodes in cls_nodes.items():
        if len(nodes) < 2:
            continue
        cells = sorted({net_cell[n] for n in nodes if n in net_cell})
        if len(cells) > 1:
            out.append({"kind": "fused", "affected_nodes": sorted(n for n in nodes if n in net_cell),
                        "before": {"native_net": sorted(nodes)},
                        "after": {"declared_nets": [cell_name[c] for c in cells],
                                  "declared_partition_cells": [sorted(declared["nets"][c]["nodes"]) for c in cells]},
                        "detail": "native net fuses nodes of distinct declared nets"})

    for node in sorted(n for n, r in role.items() if r in ("nc", "isolated") and n in native_all):
        st = state(node)
        want = role[node]
        if st == want:
            continue
        out.append({"kind": want, "affected_nodes": [node],
                    "before": {"native_state": st,
                               "native_net": sorted(cls_nodes[cls_of[node]]) if st == "connected" else None},
                    "after": {"declared_role": want},
                    "detail": f"declared {want}, native pin is {st}"})

    extra = sorted(native_all - set(role))
    if extra:
        out.append({"kind": "undeclared_native", "affected_nodes": extra,
                    "before": {"native_states": {n: state(n) for n in extra}},
                    "after": {"declared_role": None},
                    "detail": "native pins absent from the declared circuit; partition is never inferred"})
    return out


# ---------------------------------------------------------------------------
# Proposal construction.  A proposal is NOT approval and is never applied here.
# ---------------------------------------------------------------------------

def topology_operations(mismatches: list[dict], declared_revision: str) -> list[dict]:
    ops = []
    for i, m in enumerate(mismatches):
        ops.append({
            "op_id": f"topology-{i:03d}-{m['kind']}",
            "edit_class": TOPOLOGY_EDIT_CLASS,
            "target_id": m["affected_nodes"][0],
            "mismatch_kind": m["kind"],
            "affected_ids": list(m["affected_nodes"]),
            "before": m["before"],
            "after": m["after"],
            "detail": m["detail"],
            "declared_circuit_revision": declared_revision,
            "origin": "native_vs_declared_reconciliation",
        })
    return ops


def requested_operations(raw: Any, declared_revision: str) -> list[dict]:
    """Normalise caller-requested metadata operations.  Default empty.  Never applied."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise _err("E_OPERATION_MALFORMED", "requested_operations must be a list",
                   [{"kind": "malformed_field", "field": "requested_operations"}])
    gaps, ops = [], []
    for i, op in enumerate(raw):
        if (not isinstance(op, dict) or not isinstance(op.get("edit_class"), str)
                or not isinstance(op.get("target_id"), str) or not op.get("target_id")
                or op.get("target_kind") not in TARGET_KINDS or "after" not in op):
            gaps.append({"kind": "malformed_field", "field": f"requested_operations[{i}]",
                         "detail": f"needs edit_class, target_id, target_kind in {list(TARGET_KINDS)} and after"})
            continue
        ops.append({"op_id": f"requested-{i:03d}-{op['edit_class']}", "edit_class": op["edit_class"],
                    "target_id": op["target_id"], "target_kind": op["target_kind"],
                    "affected_ids": [op["target_id"]],
                    "before": op.get("before"), "after": op["after"],
                    "declared_circuit_revision": declared_revision, "origin": "caller_request"})
    if gaps:
        raise _err("E_OPERATION_MALFORMED", "requested_operations refused; named gaps", gaps)
    return ops


#: Typed semantic targets.  A target is resolved ONLY as the kind it declares; there is no
#: "try object, then pin, then component" cascade.
#:   object    -> '<relative sheet path>#<uuid>' of a placed SYMBOL (bare uuid never resolves)
#:   component -> a reference designator that exists exactly once in the native export
#:   pin       -> 'REF.PIN' that exists in the native export
TARGET_KINDS = ("object", "component", "pin")
ALLOWED_TARGET_KINDS = {
    "set_value": ("object", "component"),
    "set_footprint": ("object", "component"),
    "set_annotation": ("object", "component"),
    "add_label": ("pin",),
}


def target_conflicts(ops: list[dict], symbol_ids: set, native_nodes: set,
                     component_counts: dict) -> list[dict]:
    out = []
    for op in ops:
        if op["origin"] != "caller_request":
            continue
        kind, tid, ec = op.get("target_kind"), op["target_id"], op["edit_class"]
        allowed = ALLOWED_TARGET_KINDS.get(ec)
        if allowed is not None and kind not in allowed:
            out.append({"type": "TARGET_KIND_UNSUPPORTED", "target_id": tid, "target_kind": kind,
                        "edit_class": ec, "message": f"edit class {ec!r} accepts target kinds {list(allowed)}"})
            continue
        if kind == "object":
            found = tid in symbol_ids
        elif kind == "component":
            n = component_counts.get(tid, 0)
            if n > 1:
                out.append({"type": "TARGET_AMBIGUOUS", "target_id": tid, "target_kind": kind,
                            "message": f"reference {tid!r} resolves to {n} components"})
                continue
            found = n == 1
        elif kind == "pin":
            found = tid in native_nodes
        else:
            found = False
        if not found:
            out.append({"type": "TARGET_NOT_FOUND", "target_id": tid, "target_kind": kind,
                        "message": "target does not resolve as its declared kind; object targets must be "
                                   "scoped '<sheet path>#<uuid>' symbols (a bare uuid is not resolved)"})
    return out


# ---------------------------------------------------------------------------
# Entrypoint body
# ---------------------------------------------------------------------------

def _refusal(error, out: Path | None = None, receipts: dict | None = None) -> dict:
    """A contract violation is DATA (ok:false + machine code), never a partial success.

    ``files`` lists what THIS invocation actually left on disk.  It is ``[]`` only when
    nothing was written (``out`` is None); a failure after the workspace exists reports
    the real files and any receipts already earned.
    """
    from bodesign_eda_bridge.human_presentation import list_files
    details = dict(error.details)
    receipts = receipts if receipts is not None else details.get("receipts")
    res = {"ok": False,
           "error": {"code": error.code, "message": error.message, "details": details},
           "files": list_files(out) if out is not None else [], "emit_mode": None,
           "apply": {"status": APPLY_STATUS}}
    if receipts is not None:
        res["receipts"] = receipts
    return res


def _write_json(path: Path, payload: dict) -> dict:
    """Exclusive, no-follow create inside the fresh workspace; never overwrites anything."""
    from bodesign_eda_bridge.human_presentation import exclusive_write, sha256_file
    exclusive_write(path, (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    return {"path": str(path), "sha256": sha256_file(path), "byte_size": path.stat().st_size}


def _out_dir_guard(out_dir: Any, source_dir: Path) -> Path:
    if not isinstance(out_dir, str) or not out_dir or not os.path.isabs(out_dir):
        raise _err("E_OUTPUT_DIR", "out_dir must be an absolute path",
                   [{"kind": "missing_field", "field": "out_dir"}])
    real = Path(os.path.realpath(out_dir))
    src = Path(os.path.realpath(source_dir))
    if real == src or src in real.parents or real in src.parents:
        raise _err("E_OUTPUT_DIR", "out_dir must be disjoint from the human source directory",
                   [{"kind": "path_traversal", "path": str(real), "source_dir": str(src)}])
    # The workspace must not exist AT ALL (file, directory, dangling or live symlink).
    if os.path.lexists(out_dir) or os.path.lexists(real):
        raise _err("E_OUTPUT_EXISTS", "out_dir already exists; a fresh workspace is required",
                   [{"kind": "output_exists", "path": out_dir,
                     "detail": "existing output targets (incl. symlink/hardlink aliases) are never reused"}])
    return real


def ingest_human_presentation(a: dict) -> dict:
    """Inspect/derive a human native set.  Writes only under ``out_dir``; never to the source."""
    from collections import Counter
    from bodesign_eda_bridge.human_presentation import (
        HumanPresentationError, assert_unchanged, create_fresh_workspace, derive_sidecars, inventory,
        list_files,         load_native_set, native_pin_population, parse_native_connectivity,
        reconcile_pin_population, refuse)
    out: Path | None = None
    created = False
    try:
        baseline = a["presentation_baseline"]
        spec = a.get("spec")
        if spec:
            raise _err("E_BASELINE_SPEC_CONFLICT",
                       "presentation_baseline replaces spec; a non-empty spec would imply regeneration",
                       [{"kind": "malformed_field", "field": "spec"}])
        stray = [k for k in _EMIT_ONLY_ARGS if a.get(k) is not None]
        if stray:
            raise _err("E_BASELINE_EMIT_ARGS",
                       "restyle / repartition / re-place arguments are refused with a human baseline",
                       [{"kind": "malformed_field", "field": k} for k in stray])
        ns = load_native_set(baseline)
        declared = validate_declared_circuit(a.get("declared_circuit"))
        requested = requested_operations(a.get("requested_operations"), declared["revision"])
        out = _out_dir_guard(a.get("out_dir"), ns.source_dir)
        # `manifest` = native bytes + caller-declared libraries + revision (what a caller can
        # pre-compute and claim).  `subject` additionally binds the canonical declared-circuit
        # digest; proposals, outcome and report are bound to `subject`.
        manifest = ns.manifest(declared["revision"])
        subject = ns.manifest(declared["revision"], extra_dependencies=(
            DependencyRef(kind="source", name="declared_circuit", version=declared["revision"],
                          digest=declared["sha256"]),))
        claimed = baseline.get("baseline_manifest_sha256")
        if claimed is not None and str(claimed).lower() != manifest.manifest_sha256:
            raise _err("E_BASELINE_CHANGED", "declared baseline_manifest_sha256 does not match the native set",
                       [{"kind": "baseline_changed", "declared_sha256": str(claimed).lower(),
                         "actual_sha256": manifest.manifest_sha256}])
        create_fresh_workspace(out)
        created = True
        derived = derive_sidecars(ns, out)
    except HumanPresentationError as error:
        return _refusal(error, out if created else None)
    except (OSError, subprocess.SubprocessError) as exc:
        return _refusal(_err("E_DERIVE_FAILED", f"derive failed: {type(exc).__name__}: {exc}",
                             [{"kind": "derive_incomplete", "detail": f"{type(exc).__name__}: {exc}"}]),
                        out if created else None)

    receipts = derived["receipts"]
    if derived["derive_status"] == "failed":
        # Real files + receipts exist: report them, never files=[].
        return _refusal(_err("E_DERIVE_FAILED", "native netlist export failed; topology cannot be compared",
                             [{"kind": "derive_incomplete", "failed_sidecars": derived["failed_sidecars"]}]),
                        out, receipts)
    try:
        native = parse_native_connectivity(Path(derived["netlist_path"]))
        inv = inventory(ns)
        pop = native_pin_population(ns)
    except (OSError, ValueError) as exc:
        err = exc if isinstance(exc, HumanPresentationError) else _err(
            "E_DERIVE_FAILED", f"derived output unreadable: {type(exc).__name__}: {exc}",
            [{"kind": "derive_incomplete", "detail": f"{type(exc).__name__}: {exc}"}])
        return _refusal(err, out, receipts)
    pin_gaps = reconcile_pin_population(pop, native)
    if pin_gaps:
        # An incomplete pin population is never completed by calling the omitted pins NC/isolated.
        return _refusal(refuse(pin_gaps, "expected native pin population does not match the kicad-cli export"),
                        out, receipts)
    pinned = list(inv["pinned_object_ids"])
    symbol_ids = {f"{p}#{s['uuid']}" for p, sh in inv["sheets"].items() for s in sh["symbols"]}
    mismatches = compare_topology(declared, native)
    ops = topology_operations(mismatches, declared["revision"]) + requested
    for op in ops:
        op["declared_circuit_sha256"] = declared["sha256"]
    extra_conflicts = target_conflicts(ops, symbol_ids, set(native["all_nodes"]),
                                       Counter(native["components"]))

    proposal = None
    gate = None
    if ops:
        proposal = ChangeProposal(
            baseline_manifest_sha256=subject.manifest_sha256,   # native bytes + libs + declared circuit
            supported_edit_classes=list(SUPPORTED_EDIT_CLASSES),
            operations=ops,
            locked_object_ids=pinned,          # source=human pins ALL existing objects
            approval_ref=None,                  # a proposal is NOT approval
            conflicts=extra_conflicts,
        )
        # adapter_capabilities is the EMPTY set: S2 has no apply adapter, so every
        # operation carries an explicit ADAPTER_CAPABILITY_MISSING conflict.
        gate = check_baseline_preconditions(subject, subject.manifest_sha256, proposal, frozenset())

    topology_status = "consistent" if not mismatches and not requested else "proposal_pending"
    derive_status = derived["derive_status"]            # complete | partial (failed returned above)
    if derive_status != "complete":
        status = "derive_partial"
        outcome = OperationOutcome(
            module="A1", outcome="indeterminate", code="DERIVE_PARTIAL",
            subject_ref=subject.manifest_sha256,
            details={"failed_sidecars": derived["failed_sidecars"],
                     "output_validation_failures": derived["output_validation_failures"],
                     "topology_status": topology_status})
    elif topology_status == "consistent":
        status = "consistent"
        outcome = OperationOutcome(module="A1", outcome="ok", subject_ref=subject.manifest_sha256,
                                   details={"mismatch_count": 0, "requested_operation_count": 0})
    else:
        status = "proposal_pending"
        outcome = OperationOutcome(
            module="A1", outcome="indeterminate", code="PROPOSAL_PENDING_APPROVAL",
            subject_ref=subject.manifest_sha256,
            details={"mismatch_count": len(mismatches), "requested_operation_count": len(requested)})

    try:
        hashes_final = assert_unchanged(ns, Path(derived["baseline_copy"]))
        report = {
            "schema_version": "1.0",
            "source": "human",
            "mode": "inspect_derive",
            "status": status,
            "derive_status": derive_status,
            "topology_status": topology_status,
            "declared_circuit_revision": declared["revision"],
            "declared_circuit_sha256": declared["sha256"],
            "library_identity_note": "library identities are CALLER-DECLARED and unverified against files on "
                                     "disk; embedded lib_symbols are covered by the sheet hashes",
            "native_manifest": manifest.to_dict(),
            "subject_manifest": subject.to_dict(),
            "native_hashes": hashes_final,
            "native_kicad_cli": {"path": ns.kicad_cli, "version": ns.kicad_cli_version},
            "receipts": receipts,
            "erc_findings": derived["erc_findings"],
            "output_validation_failures": derived["output_validation_failures"],
            "inventory": inv,
            "native_connectivity": native,
            "pin_population": {"expected_pins": len(pop["expected"]), "exported_nodes": len(native["all_nodes"])},
            "declared_circuit": declared,
            "topology_mismatches": mismatches,
            "proposal": proposal.to_dict() if proposal else None,
            "precondition_gate": gate,
            "apply": {"status": APPLY_STATUS,
                      "note": "S2 is proposal-only; no atomic compare-and-apply exists or is claimed"},
            "does_not_authorize": list(DOES_NOT_AUTHORIZE),
            "synthetic_fixture_note": "a synthetic native set proves the ingestion contract only; "
                                      "it does not satisfy real-user-draft AC17",
        }
        report_ref = _write_json(out / "ingestion_report.json", report)
        proposal_ref = _write_json(out / "change_proposal.json", proposal.to_dict()) if proposal else None
        hashes_after_write = assert_unchanged(ns, Path(derived["baseline_copy"]))
    except HumanPresentationError as error:
        return _refusal(error, out, receipts)
    except OSError as exc:
        return _refusal(_err("E_DERIVE_FAILED", f"report write failed: {type(exc).__name__}: {exc}",
                             [{"kind": "derive_incomplete", "detail": f"{type(exc).__name__}: {exc}"}]),
                        out, receipts)
    result = {
        "ok": derive_status == "complete",   # a partial derive is NOT a success; topology is a separate field
        "emit_mode": "human_inspect_derive",
        "status": status,
        "derive_status": derive_status,
        "topology_status": topology_status,
        "failed_sidecars": derived["failed_sidecars"],
        "output_validation_failures": derived["output_validation_failures"],
        "erc_findings": derived["erc_findings"],
        "source": "human",
        "files": list_files(out),                       # this invocation's own fresh workspace only
        "out_dir": str(out),
        "baseline_manifest_sha256": manifest.manifest_sha256,
        "subject_manifest_sha256": subject.manifest_sha256,
        "declared_circuit_revision": declared["revision"],
        "declared_circuit_sha256": declared["sha256"],
        "native_hashes_before": derived["hashes_before"],
        "native_hashes_after": hashes_after_write,
        "native_unchanged": derived["hashes_before"] == hashes_after_write == hashes_final,
        "receipts": receipts,
        "topology_mismatches": mismatches,
        "proposal": proposal.to_dict() if proposal else None,
        "precondition_gate": gate,
        "operation_outcome": outcome.to_dict(),
        "ingestion_report": report_ref,
        "change_proposal_artifact": proposal_ref,
        "apply": {"status": APPLY_STATUS},
        "does_not_authorize": list(DOES_NOT_AUTHORIZE),
    }
    if derive_status != "complete":
        result["error"] = {"code": "E_DERIVE_PARTIAL",
                           "message": "one or more sidecars failed; written files and receipts are reported",
                           "details": {"failed_sidecars": derived["failed_sidecars"]}}
    return result
