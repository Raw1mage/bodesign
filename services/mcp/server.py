"""bodesign MCP server (G10a) — exposes the bodesign tools over MCP.

Transports (``--transport``):
  * ``stdio`` (default) — JSON-RPC over stdin/stdout (IDE/agent direct).
  * ``http``            — MCP Streamable HTTP on ``/mcp``; bind a TCP
                          ``--host/--port`` (external) or a ``--uds`` socket
                          (local), plus a token file API (``/files``) and
                          ``/healthz``.

Mirrors the docxmcp stack: ``mcp.server.Server`` + Starlette + uvicorn, with a
tool registry mapping MCP tool names onto the bodesign capability functions.
Tools operate on host paths (the local-UDS, files-land-in-the-client-folder
model); the token ``/files`` API is the portable upload/download primitive for
the containerised case.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable


def _bootstrap_packages() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    packages_dir = repo_root / "packages"
    if packages_dir.is_dir():
        roots = [str(d) for d in sorted(packages_dir.iterdir()) if d.is_dir()]
        for s in reversed(roots):
            if s not in sys.path:
                sys.path.insert(0, s)
        existing = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
        merged = roots + [p for p in existing if p not in roots]
        os.environ["PYTHONPATH"] = os.pathsep.join(merged)


_bootstrap_packages()

SERVER_NAME = "bodesign"
SERVER_VERSION = "0.3.0"

# R17.5 / R0.6 companion-skill identity — SINGLE SOURCE. mcp.json.skillPaths,
# GET /skills, bodesign_init.capabilities and _skill_nudge all resolve the same
# companion from this one constant (parity/drift test asserts the three faces).
COMPANION_SKILL = "bodesign"
INSTRUCTIONS = (
    "bodesign is an AI PCB design copilot. Since v0.2.0 its surface has THREE classes (R13.5):\n\n"
    "1) COMPUTE TOOLS (this MCP server, prefix bodesign_): the heavy toolchain a host cannot run — "
    "KiCad schematic/layout/fab (emit_symbol, compose_schematic, emit_layout, route_net2pcb, "
    "via_in_pad, pour_planes, widen_bus_tracks, length_match_bus, layout_drc_gate, autoroute, "
    "emit_fab, export_bom, export_netlist), verification (simulate, si_check, analyze_emc, "
    "analyze_thermal, analyzer_selfcheck), CAD/render (c02_export_stl/skp/step, c02_render_enclosure, "
    "c02_project_svg, c02_voice_to_design, render_board_model, render_gerber_preview, "
    "render_companion, emit_doc, dxf_to_dwg/dwg_to_dxf), the server-side component vault (vault_*), "
    "spice_model_card, c01_generate_concept_image, MCP delegation (mcp_call), the token file API "
    "(stage_dir), and the deliverable-cache lifecycle (cache_provision/export/close). "
    "GET /tools and /tools/{name} for the authoritative, current schemas.\n\n"
    "2) LANDING VERBS (NOT MCP tools — run them on the HOST): the deterministic project-folder "
    "verbs — C00 PRD family, C01 ID family, C02 analysis, C03 emitters, C04/C05/C06 "
    "scaffold+readiness, the whole orchestration spine, ingest_project/package_readiness/datasheet "
    "gates, and pure functions (impedance_solve, pin_allocation, reference_crosscheck, "
    "plan_design_intent, evidence_manifest) — run directly on the caller's machine via the bodesign "
    "skill's gate.py, writing straight into the project repo with zero token round-trip:\n"
    "  python3 <bodesign-skill>/scripts/gate.py <verb> --repo /abs/project [--json '{...}' | --arg k=v]\n"
    "  python3 <bodesign-skill>/scripts/gate.py --list   # enumerate every landing verb\n"
    "Calling a landed name as an MCP tool returns a typed TOOL_LANDED error carrying the equivalent "
    "gate.py command — it is not an unknown tool.\n\n"
    "3) CACHE LIFECYCLE (batch file exchange for heavy flows): bodesign_cache_provision "
    "(idempotent per owner+subject; returns cache token + /dav/{token}/ mount URL + a WebDAV Basic "
    "credential) -> mount with rclone/davfs2 or PUT over WebDAV -> run compute tools against the "
    "cache tree -> bodesign_cache_export (land the whole tree to a host dir) -> bodesign_cache_close "
    "(dirty-gated: typed WORKSPACE_CLOSE_DIRTY unless exported or force=true). For small one-shot "
    "trees the token file model still works: POST /files (tarball) or bodesign_stage_dir -> pass "
    "`token` to any tool (path args resolve inside its doc_dir) -> GET /files/{token}/blob/{rel}.\n\n"
    "PAIRS WITH the companion `bodesign` skill (the C00-C07 workflow brain + the kicad/kidoc "
    "analysis+doc engines + gate.py): the skill drives these tools to generate, and the verification "
    "tools (bodesign_simulate / analyze_emc / analyze_thermal) call the skill's engines back via "
    "BODESIGN_KICAD_SKILL / BODESIGN_SPICE_SKILL / BODESIGN_EMC_SKILL. The container image "
    "self-bundles these analyzer engines (under /opt/bodesign-engines) and sets those env vars, so "
    "C06 simulate/EMC/thermal run out of the box.\n\n"
    "No send-to-fab output without deterministic validation + explicit approval.\n\n"
    "DOMAIN KB (R16 self-shipped knowledge): bodesign self-ships its PCB-design domain KB — call "
    "bodesign_kb_query(q) before judgment-heavy design steps (layout, EMC, SI, derating) to recall "
    "distilled design rules, IPC tables and failure modes; bodesign_kb_get(id) returns the full "
    "body. Read-only serving of the repo's ragbase store; a missing KB fails fast with "
    "KB_UNAVAILABLE + remedy, never empty hits.\n\n"
    "USAGE GUIDE: this service self-ships its full usage doctrine — call bodesign_init "
    "(or prompts/get bodesign_init) for the two-plane routing model (landing verbs via "
    "gate.py vs bodesign_ compute tools), the honesty/no-fallback contract, pre-call "
    "disciplines (refs_ingest step 0, DoD self-verify), organ coordination (bodesign "
    "skill + container + UDS/TCP transport + cache 3-tier + webdav), and counter-intuitive "
    "gotchas before first use."
)


# ── R15 (self-describing organism) — canonical usage-doctrine one-source ─
#
# plans/mcp_r15-self-describing-guide DD-1..DD-3 / DD-7: bodesign ships its full
# usage doctrine on the portable MCP surface (the `bodesign_init` tool AND the
# `bodesign_init` prompts/get entry), so an agent receives it in-band at the
# action boundary as DELIVERED context, not remembered host-side prose.
#
# Both faces project this SINGLE source file (R15.5 no-drift). It is the portable
# condensate of skills/bodesign/SKILL.md (DD-2a): SKILL.md is 32 KB and the raw
# skills/ tree is deliberately NOT copied into the image (Dockerfile ships only
# scrubbed engine tarballs) — so the guide serves skills/bodesign/doctrine.md,
# the four-category (cross-tool tradeoffs / pre-call disciplines / organ
# coordination / gotchas) condensate, which the Dockerfile COPYs explicitly.
#
# DD-3: loaded once at import; a missing OR empty source FAILS FAST (天條 11 — an
# empty-doctrine guide is byte-identical to no contract, so we refuse to serve
# rather than silently return nothing).
_DOCTRINE_PATH = Path(__file__).resolve().parents[2] / "skills" / "bodesign" / "doctrine.md"


def _load_doctrine() -> str:
    """Read the canonical usage doctrine, fail-fast on missing/empty source."""
    try:
        text = _DOCTRINE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"DOCTRINE_SOURCE_MISSING: R15 usage doctrine not found at "
            f"{_DOCTRINE_PATH}. The bodesign_init surface cannot serve an empty "
            f"contract (天條 11). Ensure the image COPYs skills/bodesign/doctrine.md "
            f"(Dockerfile) and the file exists."
        ) from exc
    if not text.strip():
        raise RuntimeError(
            f"DOCTRINE_SOURCE_EMPTY: R15 usage doctrine at {_DOCTRINE_PATH} is "
            f"empty/whitespace. An empty-doctrine guide == no contract (天條 11); "
            f"refusing to serve."
        )
    return text


BODESIGN_GUIDE_DOCTRINE = _load_doctrine()


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


# ── Tool registry ──────────────────────────────────────────────────────
# Each handler takes a dict of arguments and returns a JSON-serializable result.
# Imports are lazy so a missing optional package fails only that tool.


def _h_emit_symbol(a: dict) -> Any:
    from bodesign_eda_bridge import emit_kicad_symbol
    r = emit_kicad_symbol(a["symbol_name"], a["pins"], a["output_path"],
                          footprint_filter=a.get("footprint_filter", ""), datasheet=a.get("datasheet", ""))
    return asdict(r)


def _h_compose(a: dict) -> Any:
    import bodesign_eda_bridge as _eb
    from bodesign_eda_bridge import compose_schematic
    # symbol_dirs pass-through: compose_schematic ALWAYS merges the KiCad standard
    # library itself (BR_20260723), so the facade must NOT inject a stdlib default
    # that would override a caller's custom dir. Absent → composer's own default
    # (stdlib only); present → caller's dirs, merged with stdlib downstream.
    r = compose_schematic(a["out_dir"], a["project_name"], a["spec"],
                          **({"symbol_dirs": a["symbol_dirs"]} if a.get("symbol_dirs") is not None else {}),
                          validate=a.get("validate", True),
                          connection_style=a.get("connection_style"),
                          style=a.get("style", "netlist"),
                          measure_ink=a.get("measure_ink", False),
                          fidelity=a.get("fidelity", False),
                          **({"expect_sha": a["expect_sha"]} if a.get("expect_sha") else {}))
    # BR_20260802: `inputs` rides on EVERY response, never behind a flag. A caller
    # who has to ask for provenance does not have it at the moment the question
    # finally arises -- which is always after the fact, when the numbers are
    # already suspect and the only remaining option is to discard them.
    out = {"placed": r.placed, "nets": r.nets, "schematic": r.emit.schematic_path,
           "style": r.style, "engine_rev": _eb.__engine_rev__,
           "unresolved_pins": r.emit.unresolved_pins, "warnings": r.warnings,
           "inputs": r.inputs,
           "validation": _jsonable(r.validation) if r.validation else None}
    if r.fidelity is not None:
        out["fidelity"] = _jsonable(r.fidelity)
    if r.clusters:
        out["clusters"] = [c.to_dict() for c in r.clusters]
    if r.route_stats is not None:
        out["route_stats"] = r.route_stats.to_dict()
    if r.sheet_fit is not None:
        out["sheet_fit"] = r.sheet_fit.to_dict()
    if r.ink_metrics is not None:
        out["ink_metrics"] = r.ink_metrics
    return out


def _h_emit_multisheet(a: dict) -> Any:
    if a.get("presentation_baseline") is not None:
        # DD-13: a supplied human baseline is never bypassed; no fall-through to emit_multisheet.
        from bodesign_workflow_core.human_presentation import ingest_human_presentation
        return ingest_human_presentation(a)
    # Direct submodule import for the same reason `_h_declare_circuit` uses one:
    # this path needs kicad_emit but not the whole package surface.
    from bodesign_eda_bridge.hierarchical import (HierarchicalEmitError,
                                                  PartitionError,
                                                  emit_multisheet)
    kwargs: dict = {}
    if a.get("symbol_dirs") is not None:
        kwargs["symbol_dir"] = a["symbol_dirs"]
    for key in ("paper", "connection_style", "power_ports", "subsystem_views", "view_local_max_nodes", "trim_small_replicas"):
        if a.get(key) is not None:
            kwargs[key] = a[key]
    try:
        result = emit_multisheet(a["out_dir"], a["project_name"], a["spec"], **kwargs)
    except (PartitionError, HierarchicalEmitError) as error:
        # A contract violation is returned as DATA, not raised: the caller needs the
        # machine code to branch on, and `ok:false` keeps it distinguishable from a
        # transport failure. `files: []` states that nothing was written.
        return {"ok": False, "error": {"code": error.code, "message": error.message,
                                       "details": error.details},
                "files": [], "emit_mode": None}
    out = result.to_dict()
    out["ok"] = True
    out["sheet_count"] = len(result.leaf_paths)
    out["leaf_component_counts"] = {
        name: leaf.component_count for name, leaf in result.leaf_results.items()}
    out["unresolved_pins"] = {
        name: leaf.unresolved_pins for name, leaf in result.leaf_results.items()
        if leaf.unresolved_pins}
    return out


def _h_declare_circuit(a: dict) -> Any:
    # Direct submodule import, NOT `from bodesign_eda_bridge import ...`: the
    # package __init__ pulls in kiutils-dependent modules, while declare.py is
    # pure python (its one kicad_emit import is lazy and inside a function). A
    # caller who only wants to declare topology must not need a KiCad install.
    from bodesign_eda_bridge.declare import declare_circuit
    return declare_circuit(
        components=a.get("components"),
        declarations=a.get("declarations"),
        symbol_dirs=a.get("symbol_dirs"),
        strict=a.get("strict", True),
    )


def _h_ato_build(a: dict) -> Any:
    from bodesign_eda_bridge.ato_bridge import run_ato_build
    r = run_ato_build(a["project_path"],
                      component_source=a.get("component_source", "vault"),
                      target=a.get("target"))
    return _jsonable(asdict(r))


def _h_layout(a: dict) -> Any:
    from bodesign_eda_bridge import emit_layout
    r = emit_layout(a["out_dir"], a["project_name"], a["components"],
                    board_mm=tuple(a.get("board_mm", [60, 40])),
                    columns=a.get("columns", 4),
                    place_start_mm=a.get("place_start_mm", 15.0),
                    place_pitch_mm=a.get("place_pitch_mm", 12.0),
                    margin_mm=a.get("margin_mm", 10.0))
    return asdict(r)


def _h_fab(a: dict) -> Any:
    from bodesign_eda_bridge import emit_fab_outputs
    r = emit_fab_outputs(a["board_path"], a["out_dir"], tuple(a.get("formats", ["gerbers", "drill", "pos", "step", "pdf"])),
                         pdf_layers=a.get("pdf_layers"))
    return asdict(r)


def _h_companion(a: dict) -> Any:
    from bodesign_reverse_core import render_companion
    return asdict(render_companion(a["path"], a["out_dir"]))


def _h_doc(a: dict) -> Any:
    from bodesign_reverse_core import emit_document
    return asdict(emit_document(a["md_path"], a["out_dir"], tuple(a.get("formats", ["docx", "pdf"]))))


def _h_c00_emit_prd_docx(a: dict) -> Any:
    """Render the C00 PRD as docxmcp-assemblable package(s) matching the stored
    Rockbox Word architecture. Default is client-side orchestration (the MVP per
    specs/architecture.md): bodesign renders the package(s) only, and the calling
    client drives docxmcp `document.assemble` over its own docxmcp connection — so
    bodesign does not depend on docxmcp runtime/accounts/permissions or require
    cross-container network reachability. Set assemble=true to opt into the
    internal MCP bridge (requires a configured docxmcp server via
    BODESIGN_MCP_SERVERS / BODESIGN_MCP_DOCXMCP_URL); when unconfigured the
    bridge degrades honestly to worker_unavailable and never fabricates a .docx.
    Honest: missing/drafted/etc. field states stay visible; never marks human
    approval."""
    from bodesign_workflow_core import render_c00_prd_docx_package

    render = render_c00_prd_docx_package(a["folder"])
    result = render.to_dict()

    # Default: render-only (client-side orchestration). The client assembles each
    # package via its own docxmcp connection using the returned package_dir.
    if not a.get("assemble", False):
        result["assembled"] = []
        result["assemble_hint"] = {
            "orchestration": "client-side",
            "instruction": "For each package, call docxmcp document.assemble with "
                           "doc_dir=<package_dir> and out=<package_dir>/<stem>.docx. "
                           "doc_dir MUST be the absolute path docxmcp sees for the "
                           "uploaded package (e.g. /var/cache/docxmcp/sessions/<token>); "
                           "a relative path resolves against /app and fails.",
        }
        return result

    # Opt-in internal bridge: assemble via the configured external docxmcp MCP.
    from mcp_delegate import call_external_mcp_tool

    assembled: list[dict] = []
    for pkg in render.packages:
        out_path = str(Path(pkg.package_dir) / f"{pkg.stem}.docx")
        call = call_external_mcp_tool(
            "docxmcp",
            "document",
            {"action": "assemble", "doc_dir": pkg.package_dir, "out": out_path},
        )
        assembled.append({
            "document_file": pkg.document_file,
            "stem": pkg.stem,
            "doc_dir": pkg.package_dir,
            "out_path": out_path,
            "assemble": call,
        })
    result["assembled"] = assembled
    return result


def _h_c01_generate_concept_image(a: dict) -> Any:
    from bodesign_workflow_core import generate_c01_concept_image
    return generate_c01_concept_image(a["out_dir"], a["prompt"], a.get("model")).to_dict()


def _h_c02_export_stl(a: dict) -> Any:
    from bodesign_workflow_core import export_c02_stl
    return export_c02_stl(a["out_dir"], a.get("openscad_bin")).to_dict()


def _h_c02_export_skp(a: dict) -> Any:
    from bodesign_workflow_core import export_c02_skp
    return export_c02_skp(a["out_dir"]).to_dict()


def _h_c02_export_step(a: dict) -> Any:
    from bodesign_workflow_core import export_c02_step
    return export_c02_step(a["out_dir"], a.get("constraints"),
                           a.get("wall_thickness_mm"), a.get("clearance_mm"), a.get("lid_clearance_mm")).to_dict()


def _h_render_board_model(a: dict) -> Any:
    from bodesign_eda_bridge import render_board_model
    return render_board_model(a["glb_path"], a["out_dir"],
                              views=tuple(a.get("views", ["top", "iso"])),
                              width=a.get("width", 1700), height=a.get("height", 1300)).to_dict()


def _h_c02_render_enclosure(a: dict) -> Any:
    from bodesign_eda_bridge import render_enclosure_model
    return render_enclosure_model(a["stl_path"], a["out_dir"],
                                  views=tuple(a.get("views", ["top", "iso"])),
                                  width=a.get("width", 1700), height=a.get("height", 1300),
                                  color=a.get("color")).to_dict()


def _h_c02_voice_to_design(a: dict) -> Any:
    from bodesign_workflow_core import voice_to_design
    result = voice_to_design(a["out_dir"], a["spec_text"], a.get("answers"), bool(a.get("approve", False)))
    if result.get("status") != "approved":
        return result
    from bodesign_eda_bridge import render_enclosure_model
    stl_rel = (result.get("stl") or {}).get("stl_path")
    if not stl_rel:
        return {**result, "render": {"status": "error", "note": "approved but no stl_path to render"}}
    stl_abs = str(Path(a["out_dir"]) / stl_rel)
    # CMF colour: explicit handler arg wins, else the colour the voice plan extracted.
    cmf_color = a.get("color")
    if cmf_color is None:
        cmf_color = ((result.get("plan") or {}).get("gen_params") or {}).get("cmf_color")
    render = render_enclosure_model(stl_abs, str(Path(a["out_dir"]) / "C02-ME" / "render"),
                                    views=tuple(a.get("views", ["top", "iso"])),
                                    width=a.get("width", 1700), height=a.get("height", 1300),
                                    color=cmf_color).to_dict()
    pipeline = list(result.get("pipeline", []))
    if render.get("status") == "rendered":
        pipeline.append("rendered")
    return {**result, "pipeline": pipeline, "render": render, "images": render.get("images", [])}


def _h_c02_project_svg(a: dict) -> Any:
    from bodesign_workflow_core import export_c02_projection_svg
    return export_c02_projection_svg(a["out_dir"], a.get("openscad_bin"), bool(a.get("cut", False))).to_dict()


# ── Server-side Component Vault (R9) ───────────────────────────────────
# Thin layer over vault_api (shared with the HTTP /vault/* endpoints): same
# inputs/outputs/VAULT-Exxx codes on both surfaces. VaultError is returned as
# a structured {status:'error', error_code, message} result — never swallowed,
# never an empty-success.

def _vault_api():
    try:
        import vault_api  # container / services-mcp-on-path case
    except ImportError:  # repo-root namespace-package case (tests)
        from services.mcp import vault_api
    return vault_api


def _vault_guard(fn) -> Any:
    from bodesign_component_kb.storage import VaultError
    try:
        return fn()
    except VaultError as error:
        api = _vault_api()
        return {"status": "error", **api.error_payload(error), "http_status": api.http_status(error.code)}


def _h_vault_ingest(a: dict) -> Any:
    return _vault_guard(lambda: _vault_api().vault_ingest(a))


def _h_vault_query(a: dict) -> Any:
    return _vault_guard(lambda: _vault_api().vault_query(a))


def _h_vault_spec_check(a: dict) -> Any:
    return _vault_guard(lambda: _vault_api().vault_spec_check(
        a["mpn"], a["field"], claimed_value=a.get("claimed_value"),
        vault_root=a.get("vault_root"), vault_dir=a.get("vault_dir")))


def _h_vault_queue(a: dict) -> Any:
    return _vault_guard(lambda: _vault_api().vault_queue(
        limit=int(a.get("limit", 80)), vault_dir=a.get("vault_dir")))


def _h_vault_diagnostics(a: dict) -> Any:
    return _vault_guard(lambda: _vault_api().vault_diagnostics(
        limit=int(a.get("limit", 20)), vault_dir=a.get("vault_dir")))


def _h_analyzer_selfcheck(a: dict) -> Any:
    from bodesign_eda_bridge import analyzer_engine_status
    engines = analyzer_engine_status()
    role = ("monolith" if "all" in SERVED_GROUPS
            else "ee" if "ee" in SERVED_GROUPS
            else sorted(SERVED_GROUPS)[0] if SERVED_GROUPS else "core")
    return {
        "ok": True,
        "image_role": role,
        "engines": engines,
        "summary": {e["engine"]: e["can_run"] for e in engines},
        "all_runnable": all(e["can_run"] for e in engines),
    }


def _h_simulate(a: dict) -> Any:
    from bodesign_eda_bridge import simulate_schematic
    return asdict(simulate_schematic(a["schematic_path"], a["out_dir"], simulator=a.get("simulator", "ngspice"), types=a.get("types")))


def _h_spice_model_card(a: dict) -> Any:
    """Generate a datasheet-grounded SPICE model card from vault L4 state.

    SpiceCardError (SPX_*) is passed through as a structured error result —
    never swallowed, never an empty success (DD-6/DD-9). When materialize is
    requested, the card is smoke-tested and written into the project's
    spice/models/ cascade tier-1 cache.
    """
    from dataclasses import asdict as _asdict
    from bodesign_component_kb import (
        SpiceCardError,
        generate_model_card,
        materialize_model_cards,
    )
    from bodesign_component_kb.storage import open_vault
    from bodesign_component_kb.repository import VaultRepository

    mpn = a["mpn"]
    category = a["category"]
    vault_dir = a.get("vault_dir")
    storage = open_vault(vault_dir) if vault_dir else open_vault()
    try:
        repo = VaultRepository(storage)
        try:
            card = generate_model_card(repo, mpn, category)
        except SpiceCardError as error:
            return {"status": "error", "error_code": error.code,
                    "message": error.message, "payload": error.payload}

        result: dict[str, Any] = {"status": "ok", "card": card.to_dict()}
        if a.get("materialize") and a.get("project_dir"):
            try:
                mat = materialize_model_cards(
                    a["project_dir"], [mpn], repo, category_of={mpn: category}
                )
                result["materialize"] = _asdict(mat)
            except SpiceCardError as error:
                return {"status": "error", "error_code": error.code,
                        "message": error.message, "payload": error.payload}
        return result
    finally:
        storage.close()


def _h_analyze_emc(a: dict) -> Any:
    from bodesign_eda_bridge import analyze_emc
    return asdict(analyze_emc(a["schematic_path"], a["pcb_path"], a["out_dir"], standard=a.get("standard", "fcc-class-b")))


def _h_analyze_thermal(a: dict) -> Any:
    from bodesign_eda_bridge import analyze_thermal
    return asdict(analyze_thermal(a["schematic_path"], a["pcb_path"], a["out_dir"], ambient=a.get("ambient", 25.0)))


def _h_export_bom(a: dict) -> Any:
    from bodesign_eda_bridge import export_bom
    # BR_20260730c: exclude_dnp / include_excluded_from_bom MUST be forwarded.
    # They decide which parts reach a purchasing document; leaving them
    # unreachable makes both filters unconditional for every MCP caller (the
    # §O facade-reachability defect, one tool over).
    return asdict(export_bom(
        a["schematic_path"], a["out_dir"],
        group_by=a.get("group_by", "Value"),
        exclude_dnp=a.get("exclude_dnp", True),
        include_excluded_from_bom=a.get("include_excluded_from_bom", False),
        xlsx=a.get("xlsx", False)))


def _h_export_netlist(a: dict) -> Any:
    from bodesign_eda_bridge import export_netlist
    return asdict(export_netlist(a["schematic_path"], a["out_dir"], fmt=a.get("format", "kicadsexpr")))


def _h_prd_bom_crosscheck(a: dict) -> Any:
    from bodesign_workflow_core import prd_bom_crosscheck
    return asdict(prd_bom_crosscheck(a["manifest_path"], a["netlist_path"], out_dir=a.get("out_dir")))


def _h_verify_netlist_fidelity(a: dict) -> Any:
    from bodesign_eda_bridge.fidelity import FidelityInputError, verify_netlist_fidelity
    try:
        return verify_netlist_fidelity(a.get("spec"), a.get("emitted"),
                                       nc_declared=a.get("nc_declared"))
    except FidelityInputError as error:
        # A named-but-absent .net is a CALLER error with a fixable cause, not an
        # inconclusive comparison. Keeping it off the `status` axis is the point:
        # `indeterminate` sends a reader to look at the schematic, and this one
        # should send them to look at the path they typed.
        out = {"ok": False, "error": {"code": error.code, "message": error.message}}
        if error.hint:
            out["error"]["hint"] = error.hint
        return out


def _h_readability_gate(a: dict) -> Any:
    from bodesign_eda_bridge.readability_gate import (ScoredSubjectError,
                                                      readability_gate)
    try:
        return readability_gate(
            a.get("route_stats"),
            spec=a.get("spec"),
            n=a.get("n"),
            scored_subject=a.get("scored_subject"),
            subject_source=a.get("subject_source"),
        )
    except ScoredSubjectError as error:
        # A subject this gate cannot vouch for is a CALLER error, deliberately
        # kept OFF the `status` axis for the same reason NETLIST_MISSING is:
        # `indeterminate` tells a reader the drawing was inconclusive, while
        # this tells them their own claim was unbackable. Conflating the two
        # would recreate BR_20260906 one layer up.
        return {"ok": False, "error": {"code": "READABILITY_SUBJECT_INVALID",
                                       "message": str(error)}}
    except ValueError as error:
        # missing denominator (neither spec nor n) — same channel, same reason
        return {"ok": False, "error": {"code": "READABILITY_ARGS_INVALID",
                                       "message": str(error)}}


def _h_design_suggest(a: dict) -> Any:
    from bodesign_eda_bridge.design_suggest import (DesignSuggestInputError,
                                                    design_suggest)
    try:
        return design_suggest(mpn=a.get("mpn"), pin_class=a.get("pin_class"),
                              context=a.get("context"))
    except DesignSuggestInputError as error:
        # Off the `status` axis on purpose (errors.md WP5): a caller who mistyped
        # a class name or omitted the pin list has learned nothing about KB
        # coverage, and `no-rule` would send them to write a rule they do not need.
        out = {"ok": False, "error": {"code": error.code, "message": error.message}}
        if error.hint:
            out["error"]["hint"] = error.hint
        return out


def _h_check_c03(a: dict) -> Any:
    from bodesign_workflow_core import check_c03
    # netlist_path / covers_boards MUST be forwarded: BR_20260730 F2 added R5
    # (BOM<->netlist) and R6 (pin polarity) to the function but never exposed them
    # here, so the whole rule pair was unreachable through the facade — every MCP
    # caller silently got netlist_crosscheck={"status":"not_run"} and could read a
    # PASS as "every part is drawn". That is the SAME defect class this BR opened
    # with (§3: a gate that cannot execute where the caller stands), one layer over:
    # §3 was import-reachability, this is facade-reachability.
    return asdict(check_c03(a["bom_csv"], pin_allocation_csv=a.get("pin_allocation_csv"),
                            netlist_path=a.get("netlist_path"),
                            covers_boards=a.get("covers_boards"),
                            frozen_pad_counts=a.get("frozen_pad_counts"),
                            out_dir=a.get("out_dir")))


def _h_stage_dir(a: dict) -> Any:
    from token_store import default_store
    return default_store().stage_files(a["files"])


def _h_workspace_inspect(a: dict) -> Any:
    """R17.2.3 workspace inspection: enumerate a token namespace tree so a caller
    can PROVE expected assets exist before a mutation/render. Pure read — never
    mutates. Optional `subpath` filters to a subtree (rejected if it escapes the
    token dir). Returns {token, doc_dir, files[], count}."""
    from token_store import TokenError, default_store
    store = default_store()
    token = a["token"]
    try:
        doc_dir = store.resolve(token)
    except TokenError as error:
        return {"ok": False, "error": f"token: {error}"}
    files = store.list_files(doc_dir)
    subpath = a.get("subpath")
    if isinstance(subpath, str) and subpath.strip():
        try:
            store.safe_join(doc_dir, subpath)  # traversal guard (raises on escape)
        except ValueError:
            return {"ok": False, "error": "WORKSPACE_SUBPATH_ESCAPE",
                    "message": f"subpath {subpath!r} escapes the token namespace"}
        prefix = subpath.strip("/")
        files = [f for f in files if f == prefix or f.startswith(prefix + "/")]
    return {"token": token, "doc_dir": str(doc_dir), "files": files, "count": len(files)}


def _h_mcp_call(a: dict) -> Any:
    from mcp_delegate import call_external_mcp_tool
    return call_external_mcp_tool(a["server"], a["tool"], a.get("arguments"))


def _h_route_net2pcb(a: dict) -> Any:
    from bodesign_eda_bridge import net2pcb_board
    return net2pcb_board(a["netlist_path"], a["out_path"], layers=a.get("layers", 2),
                         plane_layers=a.get("plane_layers"), track_mm=a.get("track_mm"),
                         placement=a.get("placement"), fpdir=a.get("fpdir"),
                         fp_dirs=a.get("fp_dirs"),
                         clearance_mm=a.get("clearance_mm", 0.13),
                         connectors=a.get("connectors"),
                         strategy=a.get("strategy", "grid"), seed=a.get("seed", 42),
                         board_mm=a.get("board_mm"))


def _h_via_in_pad(a: dict) -> Any:
    from bodesign_eda_bridge import via_in_pad
    return via_in_pad(a["in_path"], a["out_path"], a["refs"], drill_mm=a.get("drill_mm", 0.2),
                      pad_mm=a.get("pad_mm", 0.3), keep_rings=a.get("keep_rings", 2))


def _h_pour_planes(a: dict) -> Any:
    from bodesign_eda_bridge import pour_planes
    return pour_planes(a["in_path"], a["out_path"], a["planes"], stitch=a.get("stitch", True),
                       stitch_net=a.get("stitch_net", "GND"),
                       stitch_pitch_mm=a.get("stitch_pitch_mm", 14.0),
                       stitch_drill_mm=a.get("stitch_drill_mm", 0.3),
                       stitch_pad_mm=a.get("stitch_pad_mm", 0.6),
                       pad_connection=a.get("pad_connection", "thermal"))


def _h_widen_bus_tracks(a: dict) -> Any:
    from bodesign_eda_bridge import widen_bus_tracks
    return widen_bus_tracks(a["in_path"], a["out_path"], a["nets"], a["target_mm"],
                            clearance_mm=a.get("clearance_mm", 0.13))


def _h_length_match_bus(a: dict) -> Any:
    from bodesign_eda_bridge import length_match_bus
    return length_match_bus(a["in_path"], a["out_path"], a["nets"], a["budget_ps"], a["ps_per_mm"],
                            report_path=a.get("report_path"), clearance_mm=a.get("clearance_mm", 0.13))


def _h_layout_drc_gate(a: dict) -> Any:
    from bodesign_eda_bridge import drc_gate
    return drc_gate(a["board_path"], classify_intrinsic=a.get("classify_intrinsic", False),
                    pad_adjacency=a.get("pad_adjacency"))


def _h_clean_micro_stubs(a: dict) -> Any:
    from bodesign_eda_bridge import clean_micro_stubs
    return clean_micro_stubs(a["in_path"], a["out_path"], min_len_mm=a.get("min_len_mm", 0.02))


def _h_apply_pad_intrinsic_overrides(a: dict) -> Any:
    from bodesign_eda_bridge import apply_pad_intrinsic_overrides
    return apply_pad_intrinsic_overrides(a["in_path"], a["out_path"],
                                         override_mm=a.get("override_mm", 0.09),
                                         sidecar_path=a.get("sidecar_path"))


def _h_si_check(a: dict) -> Any:
    from bodesign_eda_bridge import si_check
    return si_check(a["board_path"], a["nets"], z0=a.get("z0", 50.0), rs=a.get("rs", 22.0),
                    vdd=a.get("vdd", 1.8), rdrv=a.get("rdrv", 17.0), cload=a.get("cload", 3e-12),
                    edge_ns=a.get("edge_ns", 0.3),
                    overshoot_pass_pct=a.get("overshoot_pass_pct", 10.0),
                    overshoot_warn_pct=a.get("overshoot_warn_pct", 20.0))


def _h_autoroute(a: dict) -> Any:
    # BR_20260729 §J/V4-c: do NOT re-declare the passes default here. It is owned by
    # DEFAULT_AUTOROUTE_PASSES in routing.py (the value the router actually applies AND the one
    # echoed back as `passes_limit_default`); a hand-copied 40 would silently drift from it.
    from bodesign_eda_bridge import autoroute, DEFAULT_AUTOROUTE_PASSES
    return autoroute(a["board_path"], a["out_path"],
                     passes=a.get("passes", DEFAULT_AUTOROUTE_PASSES),
                     netclasses=a.get("netclasses"),
                     default_width_mm=a.get("default_width_mm", 0.2),
                     default_clearance_mm=a.get("default_clearance_mm", 0.2))


def _h_placement_preflight(a: dict) -> Any:
    from bodesign_eda_bridge import placement_preflight
    return placement_preflight(a["board_path"],
                              min_utilization=a.get("min_utilization", 0.40),
                              board_mm=a.get("board_mm"),
                              courtyard_margin_mm=a.get("courtyard_margin_mm", 0.0))


def _h_c04_placement_geometry_gate(a: dict) -> Any:
    from bodesign_eda_bridge.c04_gate import C04GateInputError, c04_placement_geometry_gate
    for req in ("board_path", "netlist_path", "keepouts"):
        if req not in a:
            return {"ok": False, "error": f"C04_GATE_INPUT_MISSING: {req} is required"}
    try:
        return c04_placement_geometry_gate(a["board_path"], a["netlist_path"], a["keepouts"],
                                  edge_margin_mm=a.get("edge_margin_mm"),
                                  expected_ref_count=a.get("expected_ref_count"),
                                  silk_clearance_mm=a.get("silk_clearance_mm"),
                                  courtyard_gap_mm=a.get("courtyard_gap_mm"),
                                  ref_text_layers=a.get("ref_text_layers"))
    except C04GateInputError as e:
        return {"ok": False, "error": str(e)}


def _h_c04_board_manifest(a: dict) -> Any:
    from bodesign_eda_bridge.c04_gate import C04GateInputError
    from bodesign_eda_bridge.c04_manifest import c04_board_manifest
    for req in ("board_path", "connector_refs"):
        if req not in a:
            return {"ok": False, "error": f"C04_MANIFEST_INPUT_MISSING: {req} is required"}
    try:
        return c04_board_manifest(a["board_path"], a["connector_refs"], mating_normals=a.get("mating_normals"),
                                  height_envelope_mm=a.get("height_envelope_mm"))
    except C04GateInputError as e:
        return {"ok": False, "error": str(e)}


def _h_c02_mesh_gate(a: dict) -> Any:
    from bodesign_eda_bridge.c02_mesh_gate import C02MeshInputError, c02_mesh_gate
    paths = a.get("stl_paths", a.get("stl_path"))
    if paths is None:
        return {"ok": False, "error": "C02_MESH_INPUT_MISSING: stl_path (string) or stl_paths (array) is required"}
    try:
        return c02_mesh_gate(paths, a.get("wall_min_mm"), board_manifest_path=a.get("board_manifest_path"),
                             c02_manifest_path=a.get("c02_manifest_path"), clearance_min_mm=a.get("clearance_min_mm"),
                             expected_bbox_mm=a.get("expected_bbox_mm"), bbox_tol_mm=a.get("bbox_tol_mm"),
                             board_placement_mm=a.get("board_placement_mm"), wall_samples=a.get("wall_samples"))
    except C02MeshInputError as e:
        return {"ok": False, "error": str(e)}


def _h_c02_chain_check(a: dict) -> Any:
    from bodesign_eda_bridge.c02_chain import C02ChainInputError, c02_chain_check
    for req in ("board_path", "c02_manifest_path"):
        if req not in a:
            return {"ok": False, "error": f"C02_CHAIN_INPUT_MISSING: {req} is required"}
    try:
        return c02_chain_check(a["board_path"], a["c02_manifest_path"], a.get("board_manifest_path"))
    except C02ChainInputError as e:
        return {"ok": False, "error": str(e)}


def _h_c02_view_coverage(a: dict) -> Any:
    from bodesign_eda_bridge.c02_chain import C02ChainInputError, c02_view_coverage
    try:
        kw = {}
        if a.get("stage_prefix") is not None:
            kw["stage_prefix"] = a["stage_prefix"]
        return c02_view_coverage(a.get("c02_manifest_path"), a.get("human_dir"), required_views=a.get("required_views"),
                                 min_px=a.get("min_px"), **kw)
    except C02ChainInputError as e:
        return {"ok": False, "error": str(e)}


def _h_bga_escape_capacity(a: dict) -> Any:
    from bodesign_eda_bridge.routing import bga_escape_capacity
    return bga_escape_capacity(a["board_path"],
                               track_mm=a.get("track_mm"),
                               clearance_mm=a.get("clearance_mm"),
                               traces_per_gap=a.get("traces_per_gap"),
                               power_nets=a.get("power_nets"))


def _h_autoroute_preflight(a: dict) -> Any:
    from bodesign_eda_bridge import autoroute_preflight
    return autoroute_preflight()


def _h_component_search(a: dict) -> Any:
    from bodesign_eda_bridge import search_components
    return search_components(a["keyword"], limit=int(a.get("limit", 8)))


def _h_component_fetch(a: dict) -> Any:
    ids = a.get("lcsc_ids")
    one = a.get("lcsc_id")
    has_many = ids is not None
    has_one = one is not None
    if has_many == has_one:
        return {"ok": False,
                "reason": "must provide exactly one of lcsc_id (single) or lcsc_ids (batch)"}
    from bodesign_eda_bridge import fetch_component, fetch_components
    overwrite = a.get("overwrite", True)
    if has_many:
        return fetch_components(ids, a["output_lib"], overwrite=overwrite)
    return fetch_component(one, a["output_lib"], overwrite=overwrite)


def _h_render_gerber_preview(a: dict) -> Any:
    from bodesign_gerber_core import render_gerber_preview
    return render_gerber_preview(a["gerber_dir"], a["out_path"], a["mode"],
                                 drill_dir=a.get("drill_dir"), layer_glob=a.get("layer_glob"))


def _h_dxf_to_dwg(a: dict) -> Any:
    from bodesign_eda_bridge import dxf_to_dwg
    return dxf_to_dwg(a["in_path"], a["out_dir"],
                      version=a.get("version", "R2000"), normalize=a.get("normalize", True))


def _h_dwg_to_dxf(a: dict) -> Any:
    from bodesign_eda_bridge import dwg_to_dxf
    return dwg_to_dxf(a["in_path"], a["out_dir"])


# ── Deliverable-cache lifecycle core (plan mcp_r13, tasks 5.3/5.5) ───────
# Shared by the HTTP lifecycle routes (build_cache_dav_routes) and the MCP
# tools below. Typed errors per plans/mcp_r13-landing-webdav-cache/errors.md.

_cache_log = logging.getLogger("bodesign.cache")
_tools_log = logging.getLogger("bodesign.tools")


def _cache_soft_cap_limits() -> tuple[int, int]:
    """(count_cap, bytes_cap) — WARN-FIRST per-owner usage ceilings; never block."""
    try:
        count_cap = int(os.environ.get("BODESIGN_CACHE_SOFT_CAP_COUNT", "8"))
    except ValueError:
        count_cap = 8
    try:
        bytes_cap = int(os.environ.get("BODESIGN_CACHE_SOFT_CAP_BYTES", str(2 * 1024 ** 3)))
    except ValueError:
        bytes_cap = 2 * 1024 ** 3
    return count_cap, bytes_cap


def _cache_list_by_owner(store, owner_identity: str) -> list[dict]:
    """All live deliverable-cache records owned by ``owner_identity``."""
    from token_store import KIND_DELIVERABLE_CACHE, _META_SUFFIX, StoreOpError
    out = []
    for meta_path in store.root.glob(f"tok_*{_META_SUFFIX}"):
        try:
            meta = store._parse_meta(meta_path)
        except StoreOpError:
            continue  # corrupt sidecar is the reaper's problem, not the lister's
        if meta.kind != KIND_DELIVERABLE_CACHE or meta.owner_identity != owner_identity:
            continue
        d = store.root / meta.token
        if not d.is_dir():
            continue
        size = sum(p.stat().st_size for p in d.rglob("*") if p.is_file())
        out.append({"token": meta.token, "subject_id": meta.subject_id,
                    "created_at": meta.created_at, "last_used_at": meta.last_used_at,
                    "last_export_at": meta.last_export_at, "bytes": size})
    return sorted(out, key=lambda r: r["token"])


def _cache_soft_cap_status(store, owner_identity: str) -> dict:
    """Per-owner soft-cap signal (docxmcp owner_soft_cap_status pattern):
    WARN-FIRST, NON-BLOCKING (天條). Returns an observable dict; callers log a
    WARNING when over but never refuse the operation."""
    count_cap, bytes_cap = _cache_soft_cap_limits()
    items = _cache_list_by_owner(store, owner_identity)
    count = len(items)
    total = sum(i["bytes"] for i in items)
    over_count = count > count_cap
    over_bytes = total > bytes_cap
    return {"count": count, "count_cap": count_cap, "bytes": total, "bytes_cap": bytes_cap,
            "over_count": over_count, "over_bytes": over_bytes,
            "over": over_count or over_bytes}


def _cache_export_tree(store, token: str, target: Path) -> dict:
    """Copy the cache tree to a host-visible ``target`` dir + mark_exported.

    The target's PARENT must already exist — ancestors are never auto-created
    and no alternative target is guessed (typed EXPORT_TARGET_UNREACHABLE).
    The leaf target dir itself is created if absent (docxmcp semantics)."""
    import shutil
    from token_store import StoreOpError
    if not target.is_absolute():
        raise StoreOpError("EXPORT_TARGET_UNREACHABLE",
                           f"export target must be an absolute path: {target}")
    if not target.parent.is_dir():
        raise StoreOpError("EXPORT_TARGET_UNREACHABLE",
                           f"export target parent does not exist: {target.parent} "
                           "(ancestors are never auto-created)")
    root = store.resolve(token)
    try:
        target.mkdir(exist_ok=True)
    except OSError as exc:
        raise StoreOpError("EXPORT_TARGET_UNREACHABLE",
                           f"export target not writable: {target}: {exc}") from exc
    count = 0
    try:
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root)
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
            count += 1
    except OSError as exc:
        raise StoreOpError("EXPORT_TARGET_UNREACHABLE",
                           f"export write failed under {target}: {exc}") from exc
    store.mark_exported(token)
    _cache_log.info("cache_export_ok token=%s target=%s files=%d", token, target, count)
    return {"target": str(target), "count": count}


def _cache_close(store, token: str, *, force: bool = False) -> dict:
    """Close a deliverable cache behind the dirty-gate (DD-5).

    Dirty (files newer than last export) and not force → typed
    WORKSPACE_CLOSE_DIRTY carrying the unexported list. Clean (or force) →
    remove the token dir + sidecar, freeing the (owner, subject) namespace."""
    import shutil
    from token_store import StoreOpError
    dirty = store.cache_dirty_files(token)
    if dirty and not force:
        exc = StoreOpError(
            "WORKSPACE_CLOSE_DIRTY",
            "cache has files modified since last export: " + ", ".join(dirty)
            + " — export first, or close with force=true to discard")
        exc.unexported = dirty
        raise exc
    meta = store.cache_meta(token)
    shutil.rmtree(store.root / token, ignore_errors=True)
    store._meta_path(token).unlink(missing_ok=True)
    _cache_log.info("cache_close_ok token=%s owner=%s subject=%s forced=%s",
                    token, meta.owner_identity, meta.subject_id, force)
    return {"closed": True, "forced": force, "token": token, "subject_id": meta.subject_id}


# ── Deliverable-cache lifecycle handlers (plan mcp_r13, task 5.5) ────────
# Agents drive the cache over these tools; humans mount over WebDAV. The
# cache token arg is named `cache_token` (NOT `token`) on purpose: `token`
# is the generic file-model arg that run_tool pops + rewrites paths with.

def _h_cache_provision(a: dict) -> Any:
    import importlib
    from token_store import StoreOpError, default_store
    ap = importlib.import_module("_auth_provider")
    owner = a["owner_identity"]
    subject = a["subject_id"]
    store = default_store()
    try:
        meta = store.provision_cache(owner, subject)
    except StoreOpError as exc:
        return {"error": exc.code, "message": str(exc)}
    # R14.5 (BR_20260706): explicit per-host provision state — additive
    # observability so the caller decides webdav-mount vs stage-inline
    # (R14.7) from an explicit signal, never by implication.
    out = {"token": meta.token, "subject_id": meta.subject_id, "owner": meta.owner_identity,
           "mount_url": f"{_base()}/dav/{meta.token}/",
           "soft_cap": _cache_soft_cap_status(store, owner),
           "host_provision": ap.host_provision_state()}
    # R14.6 (BR_20260706): credential issuance over the MCP rail is OPT-IN.
    # Holding the MCP socket IS the capability, but rotation is destructive
    # (each issue() invalidates the previous password — it would break a
    # live mount), so the default payload carries NO credential (天條 11:
    # no silent extra side effects). Aligned with the docxmcp reference
    # issue_webdav_credential flag.
    if bool(a.get("issue_webdav_credential")):
        password = ap.default_provider().credentials.issue(owner)
        out["webdav_username"] = owner
        out["webdav_password"] = password
    return out


def _h_cache_export(a: dict) -> Any:
    from token_store import StoreOpError, default_store
    store = default_store()
    meta = store.cache_meta(a["cache_token"])  # TokenNotFoundError → typed error via run_tool
    if meta.owner_identity != a["owner_identity"]:
        return {"error": "CACHE_FORBIDDEN",
                "message": "cache belongs to another owner; cross-owner access is never granted"}
    try:
        result = _cache_export_tree(store, a["cache_token"], Path(a["target"]))
    except StoreOpError as exc:
        return {"error": exc.code, "message": str(exc)}
    return {"exported": True, **result}


def _h_cache_close(a: dict) -> Any:
    from token_store import StoreOpError, default_store
    store = default_store()
    meta = store.cache_meta(a["cache_token"])
    if meta.owner_identity != a["owner_identity"]:
        return {"error": "CACHE_FORBIDDEN",
                "message": "cache belongs to another owner; cross-owner access is never granted"}
    try:
        return _cache_close(store, a["cache_token"], force=bool(a.get("force", False)))
    except StoreOpError as exc:
        out = {"error": exc.code, "message": str(exc)}
        unexported = getattr(exc, "unexported", None)
        if unexported is not None:
            out["unexported"] = unexported
        return out


# ── Domain KB serving (plan mcp_r16-domain-kb, R16) ─────────────────────
# Read-only in-band serving of the repo ragbase KB (.specbase/ragbase.sqlite,
# host-side producer: specbase producer.ts ragbase_distill). DD-3: the mount is
# rw (WAL side files need a writable dir) but read-only is enforced at the
# CONNECTION layer — URI mode=ro + PRAGMA query_only=ON, per-request, zero
# write tools on the MCP surface. DD-4/DD-6: fail-fast typed errors, no path
# guessing, no empty-hits masquerade.


class KbError(Exception):
    """Typed KB serving error — str() is the full content text; the first line
    carries the error code (KB_UNAVAILABLE / KB_BAD_QUERY / KB_OBJECT_NOT_FOUND)
    per plans/mcp_r16-domain-kb/errors.md."""


_KB_REMEDY = ("remedy: KB lives host-side at <repo>/.specbase/ragbase.sqlite; "
              "distill via specbase producer.ts (ragbase_distill); mount is live, "
              "no restart needed.")
# ragbase FTS5 uses the trigram tokenizer (specbase ragbase-schema): only runs
# of ≥3 codepoints are indexed, so a shorter token can NEVER match via FTS.
_KB_MIN_TRIGRAM = 3


def _kb_connect():
    """Per-request read-only sqlite connection (DD-3/DD-6). Env-located; any
    unavailability raises KB_UNAVAILABLE with the remedy line — never a guessed
    path, never a silent empty store."""
    import sqlite3
    db_path = (os.environ.get("BODESIGN_KB_DB") or "").strip()
    if not db_path:
        raise KbError("KB_UNAVAILABLE: BODESIGN_KB_DB env is not set\n" + _KB_REMEDY)
    if not Path(db_path).is_file():
        raise KbError(f"KB_UNAVAILABLE: KB sqlite not found at {db_path}\n" + _KB_REMEDY)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise KbError(f"KB_UNAVAILABLE: cannot open KB at {db_path}: {exc}\n" + _KB_REMEDY) from exc
    try:
        conn.execute("PRAGMA query_only=ON")
    except sqlite3.Error as exc:
        conn.close()
        raise KbError(f"KB_UNAVAILABLE: cannot open KB at {db_path}: {exc}\n" + _KB_REMEDY) from exc
    conn.row_factory = sqlite3.Row
    return conn


def _kb_match_plan(q: str, match_mode: str = "any") -> dict:
    """DD-2 + A1(BR_A Fix1): FTS query planning.

    Multi-word English queries default to OR-ranked recall (`match_mode='any'`,
    bm25 order) so an in-store object reachable by one word is not dropped the
    moment a co-occurring word is added (the implicit-AND crash BR_A recorded:
    `crystal oscillator load capacitor` → 0 while the object matches `crystal`).
    Exact conjunction is opt-in via `match_mode='all'` (no silent widening).

    Tokens ≥３ codepoints join the FTS expression; shorter tokens degrade to a
    LIKE scan. matchMode is self-describing: `fts-or` / `fts-and` when FTS runs,
    `like-scan` when only short tokens, `hybrid-or` / `hybrid-and` when mixed.
    """
    want_and = str(match_mode).strip().lower() == "all"
    joiner = " AND " if want_and else " OR "
    tokens = [t for t in q.split() if t]
    fts_tokens = [t for t in tokens if len(t) >= _KB_MIN_TRIGRAM]
    like_tokens = [t for t in tokens if len(t) < _KB_MIN_TRIGRAM]
    # per-token quoted phrases: operator-injection guard (fail-loud, a:b literal)
    fts_expr = joiner.join('"' + t.replace('"', '""') + '"' for t in fts_tokens) or None
    op = "and" if want_and else "or"
    if fts_expr is None:
        mode = "like-scan"
    elif not like_tokens:
        mode = f"fts-{op}"
    else:
        mode = f"hybrid-{op}"
    return {"fts_expr": fts_expr, "like_tokens": like_tokens, "mode": mode}


def _kb_like_pattern(token: str) -> str:
    escaped = "".join("\\" + c if c in ("\\", "%", "_") else c for c in token)
    return f"%{escaped}%"


def _kb_source_weight(conn, obj_id: str):
    """Max source_weight (1-7) over the object's distilled_from/extracted_from
    lineage edges (specbase DD-14 metadata); None when ungraded — never fabricated."""
    weights = []
    for r in conn.execute(
            "SELECT metadata_json FROM ragbase_lineage WHERE source_id = ? "
            "AND edge_type IN ('distilled_from','extracted_from') "
            "AND metadata_json != ''", (obj_id,)).fetchall():
        try:
            w = json.loads(r["metadata_json"]).get("source_weight")
        except (ValueError, AttributeError):
            continue
        if isinstance(w, (int, float)):
            weights.append(w)
    return max(weights) if weights else None


_KB_LIKE_COND = "(o.title LIKE ? ESCAPE '\\' OR o.body_md LIKE ? ESCAPE '\\')"


def _h_kb_query(a: dict) -> Any:
    q = (a.get("q") or "").strip()
    if not q:
        raise KbError("KB_BAD_QUERY: empty query")
    type_filter = (a.get("type") or "").strip() or None
    try:
        limit = int(a.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10
    limit = min(max(limit, 1), 50)
    # A1/DD-5: opt-in exact conjunction. `mode='all'` must reach _kb_match_plan
    # (which defaults to OR-ranked recall) or the AND request is silently widened
    # to OR — the exact regression BR_A's DD-5 forbids. Accept `mode` (public arg)
    # or `match_mode` (alias).
    match_mode = (a.get("mode") or a.get("match_mode") or "any")
    plan = _kb_match_plan(q, match_mode)
    conn = _kb_connect()
    try:
        where: list[str] = []
        params: list = []
        if plan["mode"] == "like-scan":
            base_from = "FROM ragbase_objects o"
            select_score = "0 AS score"
            order = "o.updated_at DESC"
        else:
            base_from = "FROM ragbase_fts JOIN ragbase_objects o ON o.rowid = ragbase_fts.rowid"
            select_score = "bm25(ragbase_fts) AS score"
            order = "bm25(ragbase_fts)"
            where.append("ragbase_fts MATCH ?")
            params.append(plan["fts_expr"])
        for t in plan["like_tokens"]:
            where.append(_KB_LIKE_COND)
            p = _kb_like_pattern(t)
            params.extend([p, p])
        if type_filter:
            where.append("o.type = ?")
            params.append(type_filter)
        where_sql = " AND ".join(where) or "1=1"
        total = conn.execute(f"SELECT count(*) {base_from} WHERE {where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT o.id, o.type, o.title, o.confidence, {select_score} "
            f"{base_from} WHERE {where_sql} ORDER BY {order} LIMIT ?",
            [*params, limit]).fetchall()
        hits = [{"id": r["id"], "type": r["type"], "title": r["title"],
                 "score": r["score"], "confidence": r["confidence"],
                 "source_weight": _kb_source_weight(conn, r["id"])} for r in rows]
        return {"query": q, "matchMode": plan["mode"], "hits": hits,
                "total": total, "limit": limit}
    finally:
        conn.close()


def _h_kb_get(a: dict) -> Any:
    obj_id = (a.get("id") or "").strip()
    if not obj_id:
        raise KbError("KB_BAD_QUERY: id is required")
    conn = _kb_connect()
    try:
        row = conn.execute(
            "SELECT id, type, title, batch_id, locator, confidence, extraction_status, "
            "body_md, metadata_json, captured_at, updated_at, scope "
            "FROM ragbase_objects WHERE id = ?", (obj_id,)).fetchone()
        if row is None:
            raise KbError(f"KB_OBJECT_NOT_FOUND: {obj_id}\nconsider: bodesign_kb_query")
        provenance = []
        for r in conn.execute(
                "SELECT target_id, edge_type, metadata_json FROM ragbase_lineage "
                "WHERE source_id = ? AND edge_type IN ('distilled_from','extracted_from')",
                (obj_id,)).fetchall():
            weight = None
            if r["metadata_json"]:
                try:
                    w = json.loads(r["metadata_json"]).get("source_weight")
                    if isinstance(w, (int, float)):
                        weight = w
                except (ValueError, AttributeError):
                    pass
            provenance.append({"edge_type": r["edge_type"], "derived_from": r["target_id"],
                               "source_weight": weight})
        out = {k: row[k] for k in row.keys()}
        out["source_weight"] = _kb_source_weight(conn, obj_id)
        out["provenance"] = provenance
        return out
    finally:
        conn.close()


_STR = {"type": "string"}

# Imported rather than restated: the nine pin classes are declared once, in the
# module that routes on them. A hand-copied enum here would drift silently, and
# the drift would surface as a schema advertising a class the router refuses --
# i.e. the tool description itself would become the false statement.
try:
    from bodesign_eda_bridge.design_suggest import PIN_CLASSES as _SUGGEST_PIN_CLASSES
except ImportError:  # pragma: no cover - packages/ unresolvable in this process
    # Fail LOUD at schema-build time rather than shipping a tool whose enum is
    # an empty list (which would reject every call with an unhelpful message).
    raise

TOOLS: list[dict] = [
    # R15 self-describing guide (plans/mcp_r15-self-describing-guide DD-1/DD-5):
    # served IN-PROCESS by run_tool (no registry handler); handler=None is a
    # marker. annotations mark it read-only / closed-world. Listed first so it is
    # the first thing an agent discovers.
    {"name": "bodesign_init", "handler": None,
     "description": "bodesign's full usage doctrine (R15 self-describing organism): the two-plane routing model (landing verbs via gate.py vs bodesign_ compute tools), the honesty/no-fallback contract, pre-call disciplines (refs_ingest step 0, DoD self-verify), organ coordination (skill + container + UDS/TCP transport + cache 3-tier + webdav), and counter-intuitive gotchas. Same content as the bodesign_init prompts/get entry. Call it before first use. No arguments.",
     "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
     "schema": {"type": "object", "properties": {"section": {"type": "string", "description": "optional hint; the doctrine is served whole regardless (no silent truncation of the contract)"}}}},
    {"name": "bodesign_route_net2pcb", "handler": _h_route_net2pcb,
     "description": "C04 routing: build a netted .kicad_pcb from a KiCad netlist — load+place footprints, assign nets, set copper-layer count / reserved plane layers (LT_POWER, signals stay on outer layers) / default track width, draw the board outline. Board outline semantics: pass board_mm=[W,H] to draw the Edge.Cuts rectangle at exactly (0,0)-(W,H) on ANY strategy (this is the single source of truth and matches the deterministic preplace R_edge boundary); when board_mm is omitted the outline auto-frames from pad extents + 3mm margin. The result reports outline_source='board_mm'|'pad_extent'. Connector pin expansion (one symbol pin -> several pads, e.g. USB-C VBUS -> A4/A9/B4/B9) is caller-overridable via `connectors`={refdes:{net:[pads]}} and applies to any USB-C footprint on ANY refdes (not just J1). Returns placed/nets/pads_assigned/unmapped plus applied_pinmaps and unmapped_connectors (a USB-C/declared connector that matched no net name is reported, not silently skipped); unmapped>0 means a footprint's pad names don't match the symbol (floating part). Footprint search dirs MERGE fp_dirs (project .pretty parents) with stock — a component whose footprint resolves in NONE is reported in dropped_components + ok:false (never silently skipped); expected_components vs placed surfaces the gap (BR_20260729 §B). Placement strategy: 'grid' (default, naive 8mm baseline) or 'deterministic' — electrically-aware pure-python pre-placement (main-IC anchoring, decap/crystal pin-affinity clustering, largest-first greedy per R4, fixed-seed SA) plus R1/R8 post-place checks; returns source-anchored placement_violations, hpwl_mm, anchor and echoed effective params. deterministic REQUIRES board_mm and FAILS FAST on missing footprint geometry — it never falls back to grid.",
     "schema": {"type": "object", "properties": {"netlist_path": _STR, "out_path": _STR, "layers": {"type": "integer"}, "plane_layers": {"type": "array", "items": _STR, "description": "inner copper layers to reserve as power planes (LT_POWER). Accepts 'In1', 'In1.Cu' or 'In1.Cu:GND' (layer[.Cu][:NET]); layer must be In1..In6. An unrecognised spec FAILS LOUD with PLANE_LAYER_UNKNOWN instead of being silently skipped (BR_20260729 \u00a7D) \u2014 the result echoes plane_layers_applied[{spec,layer,net,type}] as proof each requested plane was really created"}, "track_mm": {"type": "number"}, "placement": {"type": "object"}, "fpdir": _STR, "fp_dirs": {"type": "array", "items": _STR, "description": "project footprint .pretty parent dirs, MERGED with stock (not exclusive); a netlist component whose footprint resolves in none of them is reported in dropped_components with ok:false, never silently skipped (BR_20260729 §B)"}, "clearance_mm": {"type": "number"}, "connectors": {"type": "object", "description": "{refdes: {net_name: [pad ids]}} explicit connector pin expansion; omit to use the built-in USB-C table for USB-C footprints"}, "strategy": {"type": "string", "enum": ["grid", "deterministic"], "description": "placement strategy; default grid (baseline). deterministic = electrically-aware anchoring/clustering/greedy/SA + R1/R8 anchored checks"}, "seed": {"type": "integer", "description": "SA seed for strategy=deterministic (default 42); echoed in result.effective"}, "board_mm": {"type": "array", "items": {"type": "number"}, "description": "[width, height] mm board outline — required for strategy=deterministic"}}, "required": ["netlist_path", "out_path"]}},
    {"name": "bodesign_via_in_pad", "handler": _h_via_in_pad,
     "description": "Fine-pitch BGA via-in-pad fanout: drop a through-via through each netted ball pad of the given refs (except the outer keep_rings rings, which escape on the surface) so inner balls reach inner signal layers. via geometry is caller-overridable (drill_mm/pad_mm/keep_rings); defaults (0.2/0.3mm, 2 rings) are a JLCPCB-advanced filled+capped (POFV) process reference — tune for other pad pitches/processes.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_path": _STR, "refs": {"type": "array", "items": _STR}, "drill_mm": {"type": "number"}, "pad_mm": {"type": "number"}, "keep_rings": {"type": "integer"}}, "required": ["in_path", "out_path", "refs"]}},
    {"name": "bodesign_pour_planes", "handler": _h_pour_planes,
     "description": "Pour filled copper plane zones + optional stitching vias, giving high-speed nets a solid impedance reference plane. Each plane spec is a \"LAYER:NET\" string (e.g. 'B.Cu:GND', 'In1.Cu:GND', 'In4.Cu:V3V3') \u2014 layer first, net second; a malformed spec (wrong colon count, swapped fields, non-pcbnew layer) fails fast with POUR_PLANES_BAD_SPEC rather than a misleading pcbnew AttributeError. Stitch net + grid/via geometry are caller-overridable (stitch_net/stitch_pitch_mm/stitch_drill_mm/stitch_pad_mm); defaults (GND, 14mm, 0.3/0.6mm) are a JLCPCB-class process reference, not a hidden assumption. pad_connection='thermal' (default) keeps thermal-relief spokes; 'solid' bonds zone-net pads FULLY (ZONE_CONNECTION_FULL) to avoid starved_thermal DRC errors on isolated PTH/plane-net pads.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_path": _STR, "planes": {"type": "array", "items": _STR, "description": "list of \"LAYER:NET\" specs, e.g. ['B.Cu:GND','In4.Cu:V3V3']"}, "stitch": {"type": "boolean"}, "stitch_net": _STR, "stitch_pitch_mm": {"type": "number"}, "stitch_drill_mm": {"type": "number"}, "stitch_pad_mm": {"type": "number"}, "pad_connection": {"type": "string", "enum": ["thermal", "solid"], "description": "zone-net pad bonding; 'thermal' (default) keeps relief spokes, 'solid' = ZONE_CONNECTION_FULL to avoid starved_thermal on isolated pads"}}, "required": ["in_path", "out_path", "planes"]}},
    {"name": "bodesign_widen_bus_tracks", "handler": _h_widen_bus_tracks,
     "description": "Clearance-safe C04 bus finishing: widen selected routed bus tracks to target_mm only where foreign copper/pads keep clearance_mm; writes a new .kicad_pcb and returns widened/kept counts. post_widen_drc (BR_20260708 Ask #3): after the geometric-clearance widen pass, run a real kicad-cli DRC and REVERT any widening that introduced a NEW copper violation the fast geometric pre-check missed (e.g. near a teardropped/tented via — the CHG_STAT vs USB_CC2 symptom). Reverted count + copper_after are reported so nothing silently stays over-wide or silently fails the gate.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_path": _STR, "nets": {"type": "array", "items": _STR}, "target_mm": {"type": "number"}, "clearance_mm": {"type": "number"}, "post_widen_drc": {"type": "boolean", "description": "run post-widen DRC and revert widths that introduce new copper violations the pre-check missed"}}, "required": ["in_path", "out_path", "nets", "target_mm"]}},
    {"name": "bodesign_apply_pad_intrinsic_overrides", "handler": _h_apply_pad_intrinsic_overrides,
     "description": "C04 finish (BR_20260708 Ask #1): auto-resolve package-intrinsic pad-gap DRC violations with pad-level SetLocalClearance overrides. A clearance violation whose two items are pads OF THE SAME footprint is the land pattern's own geometry (USB-C 0.10mm pad gaps, LGA 0.10mm) — not a routing error and unfixable by routing; the honest resolution is a pad-level override (default 0.09mm, below the 0.10mm gap) on exactly those pads, recorded to a sidecar for audit. Only same-footprint pad pairs are touched; TRUE copper violations are left untouched so they still fail the gate. Returns applied count + per-override audit (ref/pads/new clearance); nothing is silently changed.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_path": _STR, "override_mm": {"type": "number"}, "sidecar_path": _STR}, "required": ["in_path", "out_path"]}},
    {"name": "bodesign_length_match_bus", "handler": _h_length_match_bus,
     "description": "Clearance-aware C04 bus length matching: add safe serpentine detours to short routed nets when possible; writes a new .kicad_pcb and returns per-net lengths, skew, budget status, tuned count, and explicit untuned statuses.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_path": _STR, "nets": {"type": "array", "items": _STR}, "budget_ps": {"type": "number"}, "ps_per_mm": {"type": "number"}, "report_path": _STR, "clearance_mm": {"type": "number"}}, "required": ["in_path", "out_path", "nets", "budget_ps", "ps_per_mm"]}},
    {"name": "bodesign_layout_drc_gate", "handler": _h_layout_drc_gate,
     "description": "Honest DRC gate: copper + unconnected violation counts (hard fail) reported separately from silkscreen overlaps (cosmetic), plus clean=bool. classify_intrinsic (BR_20260708): further split copper clearance violations into package_intrinsic (same-footprint adjacent pads at the land-pattern's own spacing — USB-C/LGA pad gaps that a pad-level clearance override resolves, NOT a routing error) vs true copper. When on, `copper` EXCLUDES intrinsic ones, and package_intrinsic + package_intrinsic_items (evidence: refs + description) are reported; clean still requires zero TRUE copper + unconnected, so intrinsic gaps neither silently pass nor masquerade as routing errors. Gate values are never relaxed to pass — reclassified with evidence, not waved through. consider: bodesign_kb_query.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "classify_intrinsic": {"type": "boolean", "description": "split package-intrinsic pad-gap clearance from true copper errors"}, "pad_adjacency": {"type": "object", "description": "optional {REF: true} for footprints known to have intrinsic sub-rule pad gaps"}}, "required": ["board_path"]}},
    {"name": "bodesign_clean_micro_stubs", "handler": _h_clean_micro_stubs,
     "description": "C04 finish (BR_20260708): remove track segments shorter than min_len_mm (default 0.02mm) left by freerouting SES import — the <0.01mm fragments that read as false unconnected / false clearance (the MIC1 GND 0.0001mm-track symptom). Strips ONLY true micro-stubs below the threshold; vias/zones untouched. Returns removed count + each removed stub's net+length so the cleanup is auditable and never silently drops real routing.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_path": _STR, "min_len_mm": {"type": "number"}}, "required": ["in_path", "out_path"]}},
    {"name": "bodesign_si_check", "handler": _h_si_check,
     "description": "ngspice signal-integrity gate: per net builds a series-terminated transmission-line testbench from the routed length; returns overshoot/undershoot and pass/warn/fail with a worst rollup. Driver/load/edge/thresholds (rdrv/cload/edge_ns/overshoot_pass_pct/overshoot_warn_pct) are caller-overridable — defaults are a documented STM32-class CMOS reference, not a hidden assumption; the result echoes the effective values under `effective`. consider: bodesign_kb_query.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "nets": {"type": "array", "items": _STR}, "z0": {"type": "number"}, "rs": {"type": "number"}, "vdd": {"type": "number"}, "rdrv": {"type": "number"}, "cload": {"type": "number"}, "edge_ns": {"type": "number"}, "overshoot_pass_pct": {"type": "number"}, "overshoot_warn_pct": {"type": "number"}}, "required": ["board_path", "nets"]}},
    {"name": "bodesign_autoroute", "handler": _h_autoroute,
     "description": "Autoroute a netted board with Freerouting when java+freerouting.jar are present in the worker; otherwise returns routed=false with the netted board for external routing. NET-CLASS RULES (BR_20260708): pass `netclasses`=[{name,width_mm,clearance_mm,nets?:[exact],match?:[substrings]}] (ORDERED; a net joins the FIRST class that claims it) to inject per-class width/clearance into the exported Specctra DSN — so a 0.5mm-pitch BGA escape region can route at 0.1/0.1mm while signal/power nets keep their own widths, instead of KiCad's single global 0.2mm rule that makes BGA escape impossible. Unclaimed nets fall into a synthesized default class (default_width_mm/default_clearance_mm). Run bodesign_via_in_pad (BGA fanout) BEFORE autoroute so escape stubs exist. Result adds `netclasses` (per-class net counts + DSN-unit widths + dropped-empty warnings) and structured completion (`unconnected`/`complete`) so a router that converged short is visible here, not only at downstream DRC.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "out_path": _STR, "passes": {"type": "integer", "description": "freerouting -mp: UPPER LIMIT of auto-router passes (default 40). Lowering it buys speed for a weaker search, and the returned `unconnected` then measures the board AND your budget — a throttled run is NOT evidence the geometry cannot be routed. The response echoes passes_limit/throttled and advises re-running at the default before concluding infeasibility."}, "default_via": {"type": "string", "description": "padstack name (from the DSN's own `(padstack ...)` declarations, e.g. 'Via[0-7]_300:150_um') for the synthesized fall-through class. BR_20260729 §K: on a fine-pitch BGA the VIA size gates layer changes more than track width does — a router that may not open a small enough via cannot reach the inner layers at all, so widening tracks changes nothing. Without this, unclaimed nets were stranded on the board's original via while named classes could each override theirs. Result reports used_vias/declared_vias/undeclared_vias; freerouting silently IGNORES an unknown use_via, so an undeclared name is reported rather than assumed applied."}, "netclasses": {"type": "array", "items": {"type": "object", "properties": {"name": _STR, "width_mm": {"type": "number"}, "clearance_mm": {"type": "number"}, "nets": {"type": "array", "items": _STR}, "match": {"type": "array", "items": _STR}}, "required": ["name", "width_mm", "clearance_mm"]}, "description": "ordered per-class DSN rules; a net joins the first class claiming it (exact `nets` or `match` substring)"}, "default_width_mm": {"type": "number"}, "default_clearance_mm": {"type": "number"}}, "required": ["board_path", "out_path"]}},
    {"name": "bodesign_autoroute_preflight", "handler": _h_autoroute_preflight,
     "description": "C04 route-step diagnostic gate (BR_20260708): probe the ee worker for freerouting prerequisites and say EXACTLY what is missing instead of leaving the route step to die on a raw Java HeadlessException. Checks four things: freerouting.jar on disk, java on PATH, a HEADFUL JRE (freerouting v1.9.0 CLI still calls Toolkit.getScreenSize(), so a *-headless JRE lacking libawt_xawt.so throws HeadlessException even under xvfb), and xvfb-run/DISPLAY. Returns {ready, missing:[...], reason, remedy:[...], probe:{...}} — ready=true ONLY when jar+java+headful-JRE+xvfb/DISPLAY are all present. Call this before bodesign_autoroute on a fresh worker; on ready=false do NOT claim a routed board, fix the named gap (or route interactively in KiCad). No arguments. consider: bodesign_kb_query.",
     "schema": {"type": "object", "properties": {}}},
    {"name": "bodesign_placement_preflight", "handler": _h_placement_preflight,
     "description": "C04 pre-route placement gate (BR_20260708): read a placed .kicad_pcb and fail fast on a doomed floorplan BEFORE routing, from REAL footprint courtyards (no guessing). Two conditions: (1) courtyard_overlap — any two footprint courtyards that intersect (optionally grown by courtyard_margin_mm) are listed in `overlaps` with the measured mm² (route would inherit a wall of clearance DRC — the 65-violation symptom); (2) sheet_under_filled — total courtyard area / usable board area below min_utilization (default 0.40) means everything is crammed into a strip (the 20%% center-strip symptom). Returns passed=true ONLY when zero overlaps AND utilization meets the floor, plus utilization, overlap_pairs, parts/board areas, board_mm (read from Edge.Cuts unless overridden) and human-readable `reasons`. Never mutates the board and never routes: the caller checks passed and, on failure, re-places (strategy='deterministic') rather than routing into overlap. consider: bodesign_kb_query.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "min_utilization": {"type": "number", "description": "floor for parts-courtyard-area / usable-board-area (default 0.40); below it = sheet_under_filled fail"}, "board_mm": {"type": "array", "items": {"type": "number"}, "description": "[width, height] mm override; omit to read board size from Edge.Cuts"}, "courtyard_margin_mm": {"type": "number", "description": "grow each courtyard by this margin before the overlap test (default 0)"}}, "required": ["board_path"]}},
    {"name": "bodesign_c04_placement_geometry_gate", "handler": _h_c04_placement_geometry_gate,
     "description": "C04 placement GEOMETRY gate (GATE-C04-01..07, c04-entry-freeze section 4.4; distinct from the landed gate.py verb c04_placement_gate): judge a PLACED .kicad_pcb against its .net. 01 parity: refs + per-ref pad/net assignment board vs netlist (missing/extra/mismatch lists; optional expected_ref_count). 02 courtyard: kicad-cli pcb drc courtyards_overlap count; kicad-cli absent or unusable => status unmeasured with a reason, NEVER pass. 03 keepout: any pad/courtyard/footprint bbox touching a keepout box {name,x,y,w,h[,layer]} (x,y = min corner, mm); keepouts=[] is unmeasured, not a vacuous pass. 04 edge margin: courtyard POLYGON vs Edge.Cuts, min distance >= edge_margin_mm (default 0.40), min measured + offenders reported (AABB only for refs listed in aabb_fallback_refs). 05 copper connectivity/Gerber parity: ALWAYS unmeasured here (placement-only). 06 silkscreen: visible reference-designator text box (KiCad 9.0.9 stroke-font model fitted to pcbnew; rotation handled) vs pad bboxes and courtyard polygons on the same side, clearance silk_clearance_mm (default 0.15); glyphs outside the measured table or bold/italic text are listed as unmeasured_items per ref, never skipped; offenders {ref, against_ref, kind pad|courtyard, clearance_mm}. 07 courtyard gap: pairwise courtyard POLYGON distance >= courtyard_gap_mm (default 0.25), smallest three pairs reported. Courtyard polygons are outset by stroke_width-0.005 mm exactly as pcbnew builds them. Returns {ok, gates:{id:{status pass|fail|unmeasured, measured, offenders}}, unmeasured_gates, inputs:{board_sha256, netlist_sha256}}; ok is true only when every measured gate (01-04, 06, 07) passes and never implies copper/Gerber parity. Missing board/netlist/keepouts fields, a footprint without courtyard geometry, or a board without an Edge.Cuts outline => {ok:false, error} fail-fast; geometry is never defaulted. Never mutates the board. consider: bodesign_placement_preflight, bodesign_layout_drc_gate.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "netlist_path": _STR, "keepouts": {"type": "array", "description": "keepout boxes; x,y = min corner, w,h extents (mm); [] = none declared (gate unmeasured)", "items": {"type": "object", "properties": {"name": _STR, "x": {"type": "number"}, "y": {"type": "number"}, "w": {"type": "number"}, "h": {"type": "number"}, "layer": {"type": "string", "enum": ["F.Cu", "B.Cu"]}}, "required": ["name", "x", "y", "w", "h"]}}, "edge_margin_mm": {"type": "number", "description": "minimum courtyard-to-Edge.Cuts distance (default 0.40)"}, "expected_ref_count": {"type": "integer", "description": "optional exact footprint count the board must have"}, "silk_clearance_mm": {"type": "number", "description": "GATE-06 minimum clearance between visible reference text and pads/courtyards (default 0.15)"}, "courtyard_gap_mm": {"type": "number", "description": "GATE-07 minimum pairwise courtyard polygon distance (default 0.25)"}, "ref_text_layers": {"type": "array", "items": {"type": "string", "enum": ["F.SilkS", "B.SilkS", "F.Fab", "B.Fab"]}, "description": "layers whose reference text GATE-06 examines (default all four; the btdongle r1 board keeps references on F.Fab)"}}, "required": ["board_path", "netlist_path", "keepouts"]}},
    {"name": "bodesign_c04_board_manifest", "handler": _h_c04_board_manifest,
     "description": "C04 board geometry packet (c04-entry-freeze section 2.2) from a placed .kicad_pcb: Edge.Cuts outline polygon (lines + arcs flattened; arc = 24 chords, circle = 48-gon, declared in outline.arc_flatten), thickness from (general (thickness ..)) (absent => fail-fast, never defaulted), mounting_holes (drilled pads of H*/MH* footprints that are through_hole or carry an NP pad; [] is a MEASURED empty, see measured.mounting_holes; other drilled NP pads such as connector pegs are listed in measured.other_drilled_np_pads, not dropped), connectors keyed by the required connector_refs list {origin, rotation_deg, side, courtyard_bbox, pad_bbox}, plus exported_outline_sha256 / exported_mounting_holes_sha256 = sha256 of canonical JSON (sorted keys, compact, floats rounded 1e-6) of the outline object / mounting_holes list as emitted (section 2.3 chain). Coordinates stay in the board file frame (y down). Missing connector ref, open Edge.Cuts chain, multiple disjoint outer loops or a connector without courtyard/pads => {ok:false, error}. Never mutates the board. Also emits connectors[*].mating_normal (declared via mating_normals, else null + mating_normal_status unmeasured) and component_height_envelope per board ref (declared via height_envelope_mm with evidence, else status unmeasured) so C02' need not hand-write a sibling schema. consider: bodesign_c04_placement_geometry_gate, bodesign_c02_mesh_gate, bodesign_c02_chain_check.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "connector_refs": {"type": "array", "items": _STR, "description": "reference designators to export as connectors, e.g. [J1,J2,SW1,SW2,SW3,D2,D3,D4,D5]"}, "mating_normals": {"type": "object", "description": "optional {ref:[x,y,z]} mating-plane normal per connector (normalised); absent => mating_normal null, status unmeasured"}, "height_envelope_mm": {"type": "object", "description": "optional {ref:{z_max_above_board_top_mm, z_min_below_board_top_mm?, evidence}} per-ref height input slot; evidence string required; refs not given stay status unmeasured"}}, "required": ["board_path", "connector_refs"]}},
    {"name": "bodesign_c02_mesh_gate", "handler": _h_c02_mesh_gate,
     "description": "C02 printable-enclosure mesh gates (DD-19), pure python, per STL part: M-01 nonempty valid mesh (triangle/degenerate/non-finite counts); M-02 half-edge topology after 1e-5 mm vertex weld: manifold (each edge shared by exactly 2 faces), watertight (no boundary edge), consistent orientation (no same-direction twin) and positive signed volume (inverted shell fails); M-03 bbox extents vs expected_bbox_mm within bbox_tol_mm (axis-ordered, no rotation; units assumed mm); M-04 wall thickness: ray from sampled face centroids along -normal, first-hit distance vs wall_min_mm (sampled normal-direction distance, NOT a true minimum thickness; limits are returned in measured.limits; unmeasured unless M-02 passes). Assembly: M-05 board clearance needs board_manifest_path + clearance_min_mm + explicit board_placement_mm [dx,dy,dz] (registration is never guessed) and tests that the extruded board outline vertices sit inside the cavity at >= clearance; translation only, component heights not modelled, necessary-not-sufficient; otherwise unmeasured with a reason, never pass. M-06 chain: c02_manifest_path consumed_board_outline_sha256 == board manifest exported_outline_sha256 (absent => unmeasured). trimesh, if importable, is a cross-check only and never changes a verdict. Returns {ok, parts:{name:{M-01..M-04}}, assembly:{M-05,M-06}, unmeasured_gates, inputs}. Watertight is not printable: no slicer/process/fit/strength claim. consider: bodesign_c04_board_manifest.",
     "schema": {"type": "object", "properties": {"stl_path": _STR, "stl_paths": {"type": "array", "items": _STR}, "wall_min_mm": {"type": "number"}, "clearance_min_mm": {"type": "number"}, "expected_bbox_mm": {"description": "[x,y,z] extents for every part, or {basename:[x,y,z]}"}, "bbox_tol_mm": {"type": "number", "description": "required when expected_bbox_mm is given"}, "board_manifest_path": _STR, "c02_manifest_path": _STR, "board_placement_mm": {"type": "array", "items": {"type": "number"}, "description": "[dx,dy,dz] mm translating board manifest coordinates into STL coordinates"}, "wall_samples": {"type": "integer"}}, "required": ["wall_min_mm"]}},
    {"name": "bodesign_c02_chain_check", "handler": _h_c02_chain_check,
     "description": "C02' chain SSOT check (c04-entry-freeze section 2.3): recompute bodesign_c04_board_manifest's own exported_outline_sha256 / exported_mounting_holes_sha256 from a placed .kicad_pcb and compare with the C02' manifest's consumed_board_outline_sha256 / consumed_mounting_holes_sha256. A mismatch fails and names the stale side (c02_manifest = the producer consumed a different packet than this tool emits, e.g. a hand-written sibling schema). Optional board_manifest_path: a board manifest file whose exported hashes or schema differ from the recompute is flagged STALE_BOARD_MANIFEST. An absent consumed_* value is unmeasured, never pass; ok requires every link measured and equal. Returns {ok, links:{outline,mounting_holes}, board_manifest_file, unmeasured, inputs}. Never mutates anything. consider: bodesign_c04_board_manifest, bodesign_c02_mesh_gate.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "c02_manifest_path": _STR, "board_manifest_path": _STR}, "required": ["board_path", "c02_manifest_path"]}},
    {"name": "bodesign_c02_view_coverage", "handler": _h_c02_view_coverage,
     "description": "DD-19(a) C02' view-coverage check: for each required view (default iso, exploded, section-usb, exterior-usb-end, plan, section-lid-ui) find the highest-versioned file '<stage_prefix><view>-v<N>.png' (default prefix '02.c02p-', i.e. NN.c02p-<view>-vN.png) in human_dir (or the human_tree_dir carried by c02_manifest_path) and require a non-empty PNG (signature + IHDR CRC) of at least min_px [w,h] (default 800x600). Missing or invalid (zero-byte, not a PNG, undersized) views => status fail with the missing/invalid lists; never pass by default. Filename + pixel size only: what a view shows is NOT assessed (blind review still required). consider: bodesign_c02_chain_check.",
     "schema": {"type": "object", "properties": {"c02_manifest_path": _STR, "human_dir": _STR, "stage_prefix": _STR, "required_views": {"type": "array", "items": _STR}, "min_px": {"type": "array", "items": {"type": "integer"}}}}},
    {"name": "bodesign_bga_escape_capacity", "handler": _h_bga_escape_capacity,
     "description": "C04 pre-route STACKUP gate: answer at PLACEMENT time whether the fine-pitch grid parts on a board can physically escape their signals, instead of discovering it after a 16-minute autoroute that lands 27/111 nets (BR_20260729 \u00a7H, aiguard C04). Model: every escaping trace squeezes between two outer balls, so the ceiling is perimeter_channels \u00d7 traces_per_gap \u00d7 signal_layers, where perimeter_channels = 2*(rows+cols)-4 and signal_layers EXCLUDES LT_POWER planes. That ceiling only BINDS when the part has nowhere else to go: with via-in-pad fanout AND at least one inner SIGNAL layer, balls drop to an inner layer instead. So blocking=true is asserted ONLY when need > ceiling AND there is no inner-signal escape route \u2014 aiguard's board is the instructive case (it HAS 128 fanout vias, but In1/In2 are both LT_POWER, so the vias land on power planes and 167 signal balls still face a 144 ceiling). Returns per-part {rows, cols, pitch_mm, ball_gap_mm, signal_balls, perimeter_channels, capacity, fanout_vias, has_escape_route, blocking} plus suggested_signal_layers and a reason saying re-placing will NOT fix it. Power/signal split is a heuristic on net names and is therefore ALWAYS reported (power_nets/signal_nets/classification); override it with power_nets=[...] when the rails are non-standard. Deliberately NOT folded into placement_preflight's passed: an overlap is fixed by re-placing, an escape shortfall is fixed by adding layers \u2014 one boolean would hide which action to take. Never mutates the board. consider: bodesign_placement_preflight, bodesign_via_in_pad.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "track_mm": {"type": "number", "description": "trace width mm; omit to read the board's Default netclass"}, "clearance_mm": {"type": "number", "description": "clearance mm; omit to read the board's Default netclass"}, "traces_per_gap": {"type": "integer", "description": "traces that fit between two adjacent balls; omit for the OPTIMISTIC 1 (the width/clearance computation is razor-sensitive at 0.5mm pitch and is reported as traces_per_gap_computed rather than used to fail a gate)"}, "power_nets": {"type": "array", "items": _STR, "description": "explicit rail net names, overriding the name heuristic (e.g. ['GND','+1V8','+3V3','VDDA']); every ball on a net NOT listed counts as a signal that must escape"}}, "required": ["board_path"]}},
    {"name": "bodesign_component_search", "handler": _h_component_search,
     "description": "Search the LCSC/EasyEDA vendor component library by MPN or keyword; returns real candidate parts [{mpn, lcsc_id, package, manufacturer, stock, rohs, price1}] for the 100%-fidelity source gate. No fabrication: an empty vendor result is reported found=0, never padded with guesses. Pair with bodesign_component_fetch to pull the chosen lcsc_id's authoritative symbol/footprint/3D.",
     "schema": {"type": "object", "properties": {"keyword": _STR, "limit": {"type": "integer"}}, "required": ["keyword"]}},
    {"name": "bodesign_component_fetch", "handler": _h_component_fetch,
     "description": "Fetch a real component's AUTHORITATIVE KiCad symbol + footprint + 3D STEP model from the LCSC/EasyEDA vendor library by LCSC id (e.g. C2869036), via the pinned easyeda2kicad CLI. Returns on-disk paths {kicad_sym, footprint, step_model, wrl_model, has_3d, lib_nickname}. BATCH: pass lcsc_ids (array) INSTEAD of lcsc_id to pull many parts into one shared output_lib in a single call \u2014 fetched sequentially (they share the CLI + library; never parallelised), continue-on-error, returning {fetched, failed, results:[per-part ok/paths|reason]} so all source-data gaps surface at once. Provide EXACTLY ONE of lcsc_id / lcsc_ids. This is the 100%-fidelity source-data path: use it INSTEAD of scaling a generic package as a stand-in body. No-fallback/honest: has_3d=false when the vendor carries no STEP (a real source-data gap to surface, not a substituted model); ok=false with 'rebuild image' when the CLI is absent.",
     "schema": {"type": "object", "properties": {"lcsc_id": _STR, "lcsc_ids": {"type": "array", "items": _STR}, "output_lib": _STR, "overwrite": {"type": "boolean"}}, "required": ["output_lib"]}},
    {"name": "bodesign_render_gerber_preview", "handler": _h_render_gerber_preview,
     "description": "C04 Gerber preview evidence: render a real Gerber layer through the gerber-core pygerber raster path. Unsupported composite modes return render-unavailable instead of drawing a decorative fallback.",
      "schema": {"type": "object", "properties": {"gerber_dir": _STR, "out_path": _STR, "mode": _STR, "drill_dir": _STR, "layer_glob": _STR}, "required": ["gerber_dir", "out_path", "mode"]}},
    {"name": "bodesign_dxf_to_dwg", "handler": _h_dxf_to_dwg,
     "description": "Local lossless DXF->DWG conversion via LibreDWG dxf2dwg, with optional ezdxf normalization (default on) that rewrites the input as a clean version DXF (LWPOLYLINE/TEXT/layers/colors preserved) for best DWG roundtrip fidelity. Output is AC1015 (AutoCAD 2000) DWG. No-fallback: if the LibreDWG binaries are missing it returns ok=false with 'rebuild image' rather than degrading. Returns dwg_path + dwgread-verified entity counts + warnings.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_dir": _STR, "version": _STR, "normalize": {"type": "boolean"}}, "required": ["in_path", "out_dir"]}},
    {"name": "bodesign_dwg_to_dxf", "handler": _h_dwg_to_dxf,
     "description": "Local DWG->DXF conversion via LibreDWG dwg2dxf. No-fallback: missing LibreDWG binary returns ok=false with 'rebuild image' rather than degrading. Returns dxf_path + dwgread-verified entity counts + warnings.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_dir": _STR}, "required": ["in_path", "out_dir"]}},
    {"name": "bodesign_mcp_call", "handler": _h_mcp_call,
     "description": "MCP-to-MCP delegation: call a tool on an external MCP server registered by name (via BODESIGN_MCP_SERVERS or BODESIGN_MCP_<NAME>_URL) and return its result. Use to drive docxmcp/drawmiat/other MCP servers through bodesign. Degrades cleanly: an unconfigured server is worker_unavailable, a configured-but-unreachable one is worker_starting (retryable); never fabricates a result.",
     "schema": {"type": "object", "properties": {"server": _STR, "tool": _STR, "arguments": {"type": "object"}},
                "required": ["server", "tool"]}},
    {"name": "bodesign_stage_dir", "handler": _h_stage_dir,
     "description": "Stage an inline file tree {relpath:{content,encoding}} into a token namespace; returns {token, doc_dir, files}. Pass the token to other tools to operate inside that tree (docxmcp-style).",
     "schema": {"type": "object", "properties": {"files": {"type": "object"}}, "required": ["files"]}},
    {"name": "bodesign_workspace_inspect", "handler": _h_workspace_inspect,
     "description": "R17.2.3 workspace inspection: enumerate a token namespace tree and PROVE expected assets exist BEFORE a transform (render/emit/assemble). Pure read — never mutates. Returns {token, doc_dir, files[], count}; optional subpath filters to a subtree (traversal-guarded). Run this before a render/emit call to confirm the inputs you staged are present, and to feed the R0.6 recon step so a first unbounded operation is not flagged as a skipped-contract wall.",
     "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
     "schema": {"type": "object", "properties": {"token": _STR, "subpath": _STR}, "required": ["token"]}},
    {"name": "bodesign_emit_symbol", "handler": _h_emit_symbol,
     "description": "Generate a KiCad .kicad_sym symbol from a pin list [{number,name,type}].",
     "schema": {"type": "object", "properties": {"symbol_name": _STR, "pins": {"type": "array"}, "output_path": _STR,
                "footprint_filter": _STR, "datasheet": _STR}, "required": ["symbol_name", "pins", "output_path"]}},
    {"name": "bodesign_declare_circuit", "handler": _h_declare_circuit,
     "description": "C03 topology DECLARATION layer: say what the circuit IS (\"R13/R14 form a divider off BATT, tapped into U2.31\") and get back a compose_schematic spec plus a COMPLETENESS verdict. Six primitives: connect | bridge (decoupling/pull-up/current-limit all share this shape) | series (chain with auto-named intermediate nodes <decl_id>_nN) | divider | rail | no_connect. This is the entry that asks the question nothing downstream asked -- is this input complete? -- so an under-specified spec is rejected AT THE ENTRY instead of each later stage inventing its own tolerance for it. status is a CLOSED five-value codomain: ok | rejected | not_run (schema/ref error, expander never ran) | empty (zero declarations -- deliberately NOT ok) | indeterminate (a symbol could not be read, so pin completeness is unknowable). Every emitted node carries provenance back to the declaration id that produced it, making \"the engine invented a node\" a single assertion rather than a review task. IMPORTANT: ok means THIS DECLARATION IS INTERNALLY CONSISTENT AND COMPLETE, not that the circuit is correct -- a pull-up tied to GND and a 5V rail on a 3V3 pin both pass here; the result field is named `completeness`, not `valid`, for that reason. Pure python: needs no KiCad unless symbol_dirs is given for the pin-completeness gate.",
     "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
     "schema": {"type": "object", "properties": {
                "components": {"type": "array", "items": {"type": "object"},
                               "description": "same shape as compose_schematic spec.components: [{ref, symbol, value?, footprint?, group?}]"},
                "declarations": {"type": "array", "items": {"type": "object"},
                                 "description": "[{id, kind, ...per-kind fields}]. kind is one of connect|bridge|series|divider|rail|no_connect. Order does not affect the result. An EMPTY array yields status=empty, never ok."},
                "symbol_dirs": {"type": "array", "items": _STR,
                                "description": "custom KiCad symbol dir(s), as an ARRAY (single-type declaration deliberately, per BR_20260730b: an anyOf/untyped argument gets stringified in transit). Omit it and the pin-completeness gate cannot read pin lists, so the verdict degrades to indeterminate rather than pretending to pass."},
                "strict": {"type": "boolean", "description": "default true. false downgrades E_PIN_UNASSIGNED to a warning for incremental migration; E_PIN_MULTI_NET is NEVER downgraded -- a pin on two nets is an electrical contradiction, not an incompleteness."}},
                "required": ["components", "declarations"]}},
    {"name": "bodesign_ato_build", "handler": _h_ato_build,
     "description": "C03 declarative verification front-end: compile an atopile .ato project (pinned toolchain, ee worker) — unit typing + tolerance intervals + assert constraint solving + parametric component picks checked at COMPILE TIME, before anything reaches KiCad. ok=true returns pcb_path (.kicad_pcb, feeds the C04 finishing chain directly — no netlist bridge) + constraint_solve evidence (5th trust layer). ok=false returns a structured deficiency list [{kind: compile_error|unsat_constraint|pick_failure|component_wrapper_missing|toolchain_missing, detail, source_anchor}] — fail-fast, no silent fallback, no constraint relaxation. component_source default 'vault' (Component Vault only; no cloud registry calls); 'registry'/'vault_then_registry' are explicit opt-ins. Raw build log lands at build_log_path in the workspace, not in this response.",
     "schema": {"type": "object", "properties": {"project_path": _STR, "component_source": {"type": "string", "enum": ["vault", "registry", "vault_then_registry"]}, "target": _STR}, "required": ["project_path"]}},
    {"name": "bodesign_compose_schematic", "handler": _h_compose,
     "description": "Compose a schematic from a design spec (components + REF.PIN nets); place + emit + kicad-cli validate. style='netlist' (default, unchanged) uses a naive index grid + global labels (back-compat). style='draftsman' (opt-in) does subsystem-clustered deterministic force-directed placement + drawn wires + sheet-fit for engineer-readable schematics. connection_style overrides the style-derived default when given ('label' global labels; 'wire' orthogonal wires). Components may carry group (subsystem cluster) and x/y (caller-supplied placement). measure_ink=true (draftsman only) renders + measures ink%/content-fill% (toolchain-gated).",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "project_name": _STR, "spec": {"type": "object"},
                "symbol_dirs": {"type": "array", "items": _STR,
                                 "description": "custom KiCad symbol .kicad_sym parent dir(s), as an ARRAY of paths. The KiCad standard library is ALWAYS merged in downstream (BR_20260723), so listing a custom dir never costs you stock passives. A single bare path STRING is still accepted at runtime (back-compat) — the schema is deliberately NARROWER than the runtime. BR_20260730b N1+§P: this argument first declared no type at all, then an anyOf union; BOTH shapes make an MCP client serialise the array to TEXT, so '[\"/work/symbols\"]' arrives as a 'directory' that can never exist and every custom symbol silently fails to resolve while stdlib parts still load. Only a SINGLE-type array declaration transports a real list (proven A/B: covers_boards, a plain array, survives the same request in which an anyOf argument is stringified). compose raises SymbolDirsEncodingError on a JSON-encoded string rather than treating it as a path."},
                "validate": {"type": "boolean"}, "style": {"type": "string", "enum": ["netlist", "draftsman"]},
                "connection_style": {"type": "string", "enum": ["label", "wire", "auto"]}, "measure_ink": {"type": "boolean"},
                 "fidelity": {"type": "boolean", "description": "post-emit partition-fidelity gate: compare the spec's expected net partition vs the kicad-cli-exported netlist partition by node-set (net names ignored). Catches collinear-wire net FUSION that ERC is blind to; raises FidelityError (fail-loud) on divergence. Recommended true for connector-dense boards."},
                 "expect_sha": {"type": "object", "description": "BR_20260802, optional {path: sha256}: assert the bytes on disk BEFORE composing; a mismatch raises COMPOSE_INPUT_SHA_MISMATCH instead of returning a structurally perfect result that describes a version you already replaced. Every response carries `inputs` (symbol libraries actually read, with sha256/mtime/bytes, plus spec_sha256) whether or not you declare this \u2014 but reading that record is your discipline, while declaring the digest moves the check into the tool. Use it whenever the inputs live somewhere they can change underneath you (a container copy, a network mount, another session's worktree)."}}, "required": ["out_dir", "project_name", "spec"]}},
    {"name": "bodesign_emit_multisheet", "handler": _h_emit_multisheet,
     "description": "Emit a HIERARCHICAL schematic \u2014 one root `.kicad_sch` carrying a sheet block per subsystem, plus one leaf `.kicad_sch` per sheet \u2014 from a spec whose components carry an explicit `sheet` field. This is the multi-page counterpart of bodesign_compose_schematic, which always emits ONE flat page no matter how many subsystems the spec describes. ROUTE SELECTION IS BY DECLARATION, NOT BY COUNT: no `sheet` on any component takes the original flat path unchanged; ANY explicit declaration \u2014 INCLUDING exactly one distinct sheet name \u2014 takes the root+N-leaf path. The two are never equated, so asking for one sheet explicitly is distinguishable from asking for nothing. `sheet` is the ONLY assignment channel: it is never inferred from `group`, from net topology, or from a catch-all, and it is ALL-OR-NOTHING (a partially declared spec raises E_UNASSIGNED_REFS rather than inventing a bucket for the remainder). `group` keeps its cluster meaning and is scoped PER SHEET \u2014 the cluster key is the ordered pair (sheet, group), so equal group strings on different sheets are independent clusters. Each sheet name is used VERBATIM as the leaf filename stem and is validated against ^[A-Za-z0-9_][A-Za-z0-9_-]{0,63}$ with NO silent sanitization (E_SHEET_NAME_INVALID / E_SHEET_NAME_EMPTY), and a stem equal to project_name is refused (E_SHEET_NAME_COLLISION) because the leaf write would otherwise truncate the root while the file set still looked complete. CROSS-SHEET NETS: a net whose nodes span sheets is emitted on every leaf holding at least one of its nodes, under its own name, forced onto global_label connectivity \u2014 same-named global labels on two leaves join into one net (measured on real kicad-cli 9.0.9). No endpoint is ever dropped; node accounting is re-checked against the input and a node whose ref is on no sheet is reported as an orphan warning rather than silently discarded. FAILURE CLEANUP removes ONLY paths this call created: a path that already exists raises E_OUTPUT_PATH_OCCUPIED before anything is written, so a pre-existing user file can never be in the rollback set. `files` lists real files on disk only \u2014 a phantom entry raises E_FILES_MANIFEST_PHANTOM rather than shipping a manifest that names something absent. Contract violations return ok:false with a machine `error.code` and files:[] (nothing written), NOT a partial success. Needs KiCad symbol libraries to resolve pins; it does not run ERC \u2014 arbitrate the output with kicad-cli or bodesign_export_netlist.",
     "schema": {"type": "object", "properties": {
                "out_dir": _STR, "project_name": _STR,
                "spec": {"type": "object",
                         "description": "compose_schematic spec shape PLUS the `sheet` field: {components: [{ref, symbol, value?, footprint?, group?, sheet?, x?, y?}], nets: [{name, nodes: ['REF.PIN', ...]}], nc?: ['REF.PIN', ...]}. A component carrying BOTH x and y keeps them; otherwise it gets a deterministic per-sheet grid slot (partial coordinates are NOT completed \u2014 inventing the missing half would be a fabricated placement). A net node that is not REF.PIN raises E_NET_NODE_MALFORMED instead of being filtered out, because dropping it deletes a declared endpoint while the net still looks complete."},
                "symbol_dirs": {"type": "array", "items": _STR,
                                "description": "custom KiCad symbol .kicad_sym parent dir(s), as an ARRAY (single-type declaration per BR_20260730b: an anyOf/untyped argument gets stringified in transit)."},
                "paper": {"type": "string", "description": "page size for every sheet, default A4."},
                "connection_style": {"type": "string", "enum": ["label", "wire", "auto"],
                                     "description": "within-leaf connectivity. Cross-sheet nets are ALWAYS forced to label regardless, because a drawn wire cannot cross a file boundary."},
                "power_ports": {"type": "boolean"},
                "subsystem_views": {"type": "object", "description": "sheet name -> list of net names to expand as local replica views on that sheet (presentation-only; home sheet keeps BOM/netlist identity)"},
                "view_local_max_nodes": {"type": "integer"},
                "presentation_baseline": {"type": "object", "description": "S2 human ingestion: {schema_version:'1.x', source:'human', source_dir, root, files:[{path,sha256}], libraries:[{name,version|digest}], kicad_version:'9.0'}. Inspect/derive only; proposal-only; apply NOT IMPLEMENTED."},
                "declared_circuit": {"type": "object", "description": "{revision, nets:[{name,nodes:['R1.1',..]}], nc:[..], isolated:[..]} (required with presentation_baseline)."},
                "requested_operations": {"type": "array", "items": {"type": "object"}, "description": "default []; each becomes a ChangeProposal operation, never applied."}},
                "required": ["out_dir", "project_name", "spec"]}},
    {"name": "bodesign_emit_layout", "handler": _h_layout,
     "description": "Place footprints on a board via pcbnew, run DRC, render an SVG companion. Placement grid + outline margin are caller-overridable (board_mm/columns/place_start_mm/place_pitch_mm/margin_mm); defaults suit a small ~60x40mm prototype board — pass larger values for bigger/denser layouts instead of the small-board grid. consider: bodesign_kb_query.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "project_name": _STR, "components": {"type": "array"},
                "board_mm": {"type": "array"}, "columns": {"type": "integer"}, "place_start_mm": {"type": "number"}, "place_pitch_mm": {"type": "number"}, "margin_mm": {"type": "number"}}, "required": ["out_dir", "project_name", "components"]}},
    {"name": "bodesign_emit_fab", "handler": _h_fab,
     "description": "Export fab outputs (gerbers/drill/pos/step/pdf) from a .kicad_pcb via kicad-cli. The PDF layer set is caller-overridable via pdf_layers; the default (F.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts) suits 2/4-layer boards — pass inner copper layers for 6+ layer stacks so they are not omitted.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "out_dir": _STR, "formats": {"type": "array", "items": _STR}, "pdf_layers": _STR}, "required": ["board_path", "out_dir"]}},
    {"name": "bodesign_simulate", "handler": _h_simulate,
     "description": "Simulate a schematic's analog subcircuits (dividers/filters/opamp/crystal) via the kicad analyzer + spice skill (ngspice); returns per-subcircuit pass/warn/fail. The analog-behaviour trust layer. consider: bodesign_kb_query.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "out_dir": _STR, "simulator": _STR, "types": _STR}, "required": ["schematic_path", "out_dir"]}},
    {"name": "bodesign_spice_model_card", "handler": _h_spice_model_card,
     "description": "Generate a datasheet-grounded SPICE model card (diode/ldo/passive) from vault L4 spice_model.* params — deterministic, byte-identical, provenance-stamped. Optional materialize writes the smoke-tested card into <project>/spice/models/ (cascade tier-1, source=vault-grounded). SPX_* errors (missing/ambiguous params, unsupported category) pass through structured; never fabricates parameters.",
     "schema": {"type": "object", "properties": {"mpn": _STR, "category": _STR, "vault_dir": _STR, "materialize": {"type": "boolean"}, "project_dir": _STR}, "required": ["mpn", "category"]}},
    {"name": "bodesign_analyze_emc", "handler": _h_analyze_emc,
     "description": "EMC pre-compliance risk analysis on a schematic + .kicad_pcb (via kicad analyzers + emc skill): severity-bucketed findings (ground plane, decoupling, return paths, stitching, …). Pre-silicon risk, not certification. consider: bodesign_kb_query.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "pcb_path": _STR, "out_dir": _STR, "standard": _STR}, "required": ["schematic_path", "pcb_path", "out_dir"]}},
    {"name": "bodesign_analyze_thermal", "handler": _h_analyze_thermal,
     "description": "Thermal hotspot estimate on a schematic + .kicad_pcb (kicad analyze_thermal); per-component temps + thermal score. consider: bodesign_kb_query.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "pcb_path": _STR, "out_dir": _STR, "ambient": {"type": "number"}}, "required": ["schematic_path", "pcb_path", "out_dir"]}},
    {"name": "bodesign_export_bom", "handler": _h_export_bom,
     "description": "Export a grouped Bill of Materials (CSV, qty + MPN) from a schematic; optional xlsx companion. TWO filters silently shrink this document unless you change them: DNP symbols are dropped (exclude_dnp, default true) and symbols marked 'Exclude from BOM' are dropped (include_excluded_from_bom, default false). line_count counts only what SURVIVED them, so the result also carries the rules in force plus excluded_dnp/excluded_from_bom naming every omitted refdes, and exclusion_audit ('run' vs 'failed:...') so an empty casualty list can never be mistaken for an unrun check. The downstream reader is purchasing: a part omitted here is a part never ordered while its footprint still sits on the board (BR_20260730c).",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "out_dir": _STR, "group_by": _STR, "xlsx": {"type": "boolean"},
                "exclude_dnp": {"type": "boolean", "description": "drop Do-Not-Populate symbols (default TRUE). Correct for a clean purchasing BOM, but the omission must stay visible — see excluded_dnp in the result."},
                "include_excluded_from_bom": {"type": "boolean", "description": "keep symbols marked 'Exclude from BOM' (default FALSE, i.e. they are dropped). This filter is opt-IN to disable, so the default quietly omits them; excluded_from_bom in the result names which."}}, "required": ["schematic_path", "out_dir"]}},
    {"name": "bodesign_export_netlist", "handler": _h_export_netlist,
     "description": "Export a netlist from a schematic via kicad-cli.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "out_dir": _STR, "format": _STR}, "required": ["schematic_path", "out_dir"]}},
    {"name": "bodesign_prd_bom_crosscheck", "handler": _h_prd_bom_crosscheck,
     "description": "C00→C03 fulfilment gate (quality/prd-bom-crosscheck L1): deterministically crosscheck the human-audited main_components_structured.json role manifest against the C03 KiCad netlist (.net). Per-role verdicts present/substituted/missing with matched_refs audit trail; missing roles and out-of-envelope substitutions without a recorded user approval are BLOCKING (gate=FAIL — refuse C04 entry). Fail-fast on absent/invalid manifest or netlist (MANIFEST_MISSING/MANIFEST_INVALID/NETLIST_MISSING/NETLIST_PARSE_ERROR); never silently passes. Pure python, runs in core.",
     "schema": {"type": "object", "properties": {"manifest_path": _STR, "netlist_path": _STR, "out_dir": _STR}, "required": ["manifest_path", "netlist_path"]}},
    {"name": "bodesign_verify_netlist_fidelity", "handler": _h_verify_netlist_fidelity,
     "description": "ELECTRICAL-axis gate: compare a design's spec net partition against the FROZEN KiCad `.net` export(s), by node-set (net NAMES are discarded \u2014 power ports rename endpoints, so name alignment is unreliable). Netlist-only: it needs no .kicad_sch, no kicad-cli and no emitter, so it adjudicates a frozen deliverable exported anywhere. Catches the defect class ERC is structurally blind to: net FUSION (two nets welded into one reads as FEWER nets and no dangling pins, so ERC looks CLEANER) and its inverse, a cut net. Reports FOUR INDEPENDENT difference axes, never merged: `fused` (nodes that gained peers \u2014 short), `split` (nodes that lost peers \u2014 open circuit), `node_diff.spec_only` / `node_diff.emitted_only` (a node in one side only), and `nc_wired` (a pin the design DECLARES not-connected that the export wires into a multi-node net \u2014 a defect even when the partition otherwise matches, which is why it is not folded into `fused`). READ `status` BEFORE any field: `ok` = parsed >0 nets, every input readable, all five axes empty; `failed` = >=1 axis non-empty; `not-run` = precondition unmet before any read (no spec, or an empty `emitted` list) so NO comparison was attempted; `indeterminate` = `nets_parsed == 0` or an input could not be parsed \u2014 set BEFORE comparison and NOT reachable from `ok`, because an empty export and a board with no nets are the same bytes. A spec of single-pin nets against an empty export previously returned a PASS through exactly that hole. A named `.net` that does not EXIST is a separate channel (`ok:false`, code `NETLIST_MISSING`), not `indeterminate`: one sends you to fix a path, the other to inspect the drawing. Same-named nets on different sheets merge only when they SHARE a node (union-find); disclosure fields (`regrouped`, `spec_overlapping_nodes`, `singleton_only_*`) are carried on `ok` as well as on `failed`, because an exemption a reader cannot see is indistinguishable from a check never made. Pure python, runs in core.",
     "schema": {"type": "object", "properties": {
         "spec": {"type": "object",
                  "description": "the electrical SSOT partition: {net_name: [[ref, pin], ...]}. A node may also be the string \"REF.PIN\". Net names are used only as labels for the classes \u2014 the comparison is by node-set, so a name mismatch between spec and export is NOT a finding. A node the spec declares in more than one net makes the spec not-a-partition; that is reported in `spec_overlapping_nodes` rather than raised, because whether those are aliases or a missing component is a design decision.",
                  "additionalProperties": {"type": "array", "items": {}}},
         "emitted": {"type": "array", "items": _STR,
                     "description": "paths to exported KiCad `.net` file(s). Several sheets may be passed; classes are merged across files by SHARED NODE. An empty list is `not-run` (nothing was read), a listed path that does not exist is `NETLIST_MISSING`, and a path that exists but yields no parseable nets is `indeterminate` \u2014 three distinct outcomes that must not be collapsed."},
         "nc_declared": {"type": "array", "items": {},
                         "description": "pins the design DECLARES not-connected, as [[ref, pin], ...]. Any of these found on a multi-node net in the export is reported in `nc_wired`. Omit it and `nc_wired` is always empty \u2014 which means absent, NOT verified-clean."}},
         "required": ["spec", "emitted"]}},
    {"name": "bodesign_readability_gate", "handler": _h_readability_gate,
     "description": "FORM-axis gate (plan c03_delivery_contract_and_engine_seams WP6): score how a schematic is DRAWN. `gate_axis` is literally 'form' and every report carries `does_not_authorize: [electrical_correctness, fidelity]` as a DATA FIELD in every status, pass and fail alike \u2014 because BR_20260905 \u00a78.5.2 measured a change that improved EVERY geometric criterion at once (junctions 5\u219243, stub share 73.0%\u219232.7%, subcircuits 3\u219211) while raising fidelity `moved` from 10 to 67, because it wired an OPEN CIRCUIT. Every threshold here would have gone green on that change. A PASS from this verb authorizes NOTHING about whether the circuit is correct; run `bodesign_verify_netlist_fidelity` for that axis and report both. \u26a0 WHAT IT SCORES, and this is the whole of BR_20260906: it scores the `route_stats` of a LIVE COMPOSE \u2014 NOT the `.kicad_sch` sitting on disk. There is no `.kicad_sch` reader in this module. Read `scored_subject` before quoting any verdict: `live-compose` (a spec was composed; `source` names it) or `frozen-stats` (frozen numbers replayed with an explicit denominator `n`; nothing was composed). The third enumerated value `on-disk` is RESERVED AND REFUSED (READABILITY_SUBJECT_INVALID) precisely so this verb cannot CLAIM a measurement it cannot make. `not_scored` states the same fact positively: the delivered schematic's readability is `not-run` here, NEVER `failed`. The defect this prevents: a `ratio 0.2222 FAIL` on btdongle read as a verdict on the DELIVERED drawing, while the two populations differ by an order of magnitude (delivered 426 wires / 56 junctions across 3 sheets vs the scored 116 / 6, single sheet). Do NOT confuse `scored_subject` with `measure_run`: the latter is the historical run the THRESHOLDS were calibrated from (identical in every report ever emitted) and carries a spec path that reads like a subject; it is labelled `what` for that reason. THRESHOLDS ARE SCALE-DEPENDENT (task 6.3): junction > 20, stub share < 40%, drawn_subcircuits/N >= 0.50, all pinned on a live-compose run of the real 45-component/27-net btdongle spec \u2014 BR_20260905 \u00a78.5.5 measured a synthetic 28/21 corpus reporting an apparent near-miss where the same code on the real board passed clearly, so a synthetic corpus may supplement the acceptance corpus and may never decide it. These numbers do NOT transfer to a hand-drawn sheet without recalibration. Status codomain: `ok` / `failed` (>=1 threshold unmet, `unmet` names which) / `not-run` (no route_stats, or route_stats missing the task-6.0 emissions \u2014 absence is NEVER a pass) / `empty` (ran, nothing to score: zero nets, or N==0 so the ratio has no denominator and was not evaluated) / `indeterminate` (the emitter predates task 6.0, so its stats cannot be reconciled against what was drawn). N is spec-derived per DD-09 and reported beside the ratio, so a low ratio is distinguishable from a small denominator. Pure python, runs in core.",
     "schema": {"type": "object", "properties": {
         "route_stats": {"type": "object",
                         "description": "the `RouteStats.to_dict()` from a compose result. null/absent is `not-run`, never a pass. A dict lacking `stub_share` or `drawn_subcircuits` is also `not-run` with `missing_fields` naming them \u2014 a missing key is absent input, not a measured zero, and defaulting it to 0 would let 'no stubs were measured' pass the stub criterion."},
         "spec": {"type": "object",
                  "description": "the design spec the stats came from. Supplying it derives N per DD-09 AND sets `scored_subject` to `live-compose` with the spec as its source. Supply either this or `n`; supplying neither is READABILITY_ARGS_INVALID, because N=0 would then mean both 'no eligible nets' and 'the caller forgot the denominator'."},
         "n": {"type": "integer",
               "description": "explicit denominator, to replay a frozen fixture. Sets `scored_subject` to `frozen-stats`: no spec was composed, so this is a DIFFERENT subject and not a weaker form of the same one."},
         "scored_subject": {"type": "string",
                            "description": "override the derived subject. Closed enumeration: live-compose | frozen-stats | on-disk. Normally OMIT it \u2014 the derived value comes from the branch actually taken and so cannot disagree with what was scored. `on-disk` is refused (no .kicad_sch reader exists); an unenumerated value is refused rather than coerced."},
         "subject_source": {"type": "object",
                            "description": "evidence for the subject claim. Derived from `spec` when omitted. Passing it EXPLICITLY EMPTY is refused, so 'no source was supplied' and 'the source is empty' never share an output."}},
         "required": []}},
    {"name": "bodesign_design_suggest", "handler": _h_design_suggest,
     "description": "Evidence-backed DRAFT suggestion for one pin class — it SUGGESTS, it never DECIDES. Every returned value is computed from a KB rule and stamped with `evidence.kb_object`; `review_required` is true on EVERY path including the ones that suggest nothing, and `committed` is not a member of the status codomain, so no code path can mark a suggestion as adopted (plan c03_delivery_contract_and_engine_seams DD-02). READ `status` FIRST, and note that THREE of its outcomes return zero suggestions for three DIFFERENT reasons: `suggested` = a KB rule covers this class and produced >=1 value, each carrying its own evidence; `no-rule` WITH AN EMPTY `evidence` block = the class has NO KB anchor at all (nothing ran, so no value could exist — distil a rule into KB before expecting an answer here); `no-rule` WITH A POPULATED `evidence` block = a rule DID run and the supplied context named zero pins of that class (ran, nothing to do); `indeterminate` = a rule covers the class but cannot yield a value — either a required electrical input is unresolvable, or (analog-reference today) the anchor states an OBLIGATION without a value. Which classes are answerable is decided by MEASURED KB coverage, not by plausibility: `power` uses control.power.decoupling-pdn-strategy (0.1uF per 2 power pins, ~15uF bulk per 10, placement <=1.25cm, TI SPRABV2, confidence=verified); `analog-reference` maps to step.sch.mcu-adc-frontend-review, whose entire VREF content is the sentence 'VREF/analog-supply pins get required filtering and grounding' — an obligation with NO capacitance, formula or window, so that class returns `indeterminate` with the obligation named rather than the customary 100nF, because attaching a real KB id to a value the object does not contain is worse than no answer. `ground`, `reset-en`, `boot-strapping` and `nc-dnc` returned no class-specific anchor when queried on 2026-09-06 and therefore return `no-rule`; `clock`, `io-gpio` and `high-speed` are served today by the dedicated suggest_* entry points. A malformed call (unknown pin_class, missing pin list) is `ok:false` with code DESIGN_SUGGEST_INPUT_INVALID, NOT a status — a typo teaches you nothing about KB coverage. Deterministic, side-effect free: the input is never mutated and no file is written.",
     "schema": {"type": "object", "properties": {
         "mpn": {"type": "string",
                 "description": "the part this pin belongs to; echoed into the result for traceability. It does NOT select a rule — rules are chosen by pin_class — so an unknown MPN never degrades the answer."},
         "pin_class": {"type": "string",
                       "enum": list(_SUGGEST_PIN_CLASSES),
                       "description": "one of the nine classes from skills/bodesign/stages/c03-ee/references/pinout-to-circuit-method.md:32-47. A class with no KB anchor returns `no-rule` and an empty suggestion list — NEVER a guessed value. An unsupported class is not an error: it is the honest answer that no rule exists."},
         "context": {"type": "object",
                     "description": "per-class inputs. pin_class='power' requires context.power_pins (a list of pin ids — the cap count IS ceil(pins/2), so an absent list has no honest default) and accepts rail, ref, ground_net. pin_class='analog-reference' requires context.vref_pins and accepts ref. A missing required key is DESIGN_SUGGEST_INPUT_INVALID rather than a zero-count answer, because 'you gave me no pins' and 'this part has no such pins' must not share an output."}},
         "required": ["pin_class"]}},
    {"name": "bodesign_check_c03", "handler": _h_check_c03,
     "description": "C03→C04 STAGE-ENTRY gate (BR_20260707): deterministic machine check that C03 (EE) delivery is complete BEFORE C04 layout may start — the entry counterpart to check_c04's output gate. Reads the BOM csv (+ optional Pin_Allocation.csv SSOT + frozen_pad_counts) and HARD-FAILS (gate=FAIL, refuse C04 entry) on: R1 BOM schema lint (column-count/quoting breakage, bad status enum, duplicate (board,ref)); R2 readiness (any draft/blocked row; a finalized row whose mpn carries TBC/TBD/UNDECIDED); R3 drawability (every row needs a symbol-source marker: official|vendor+LCSC|manual|N-A); R4 SSOT crosscheck (active parts U/J/Y/SW must appear in Pin_Allocation.csv — catches the U4 wireless-scheme conflict class; J_* pad counts must match frozen_pad_counts when provided); R5 BOM<->netlist (every BOM row must exist as a drawn symbol) and R6 pin-spec polarity, both requiring netlist_path; R7 datasheet-mandated passives (an adjustable buck missing its feedforward cap / FB divider — an ABSENT PART, which no connectivity rule and no ERC can express) and R8 switch-node shorts (a switching or feedback pin sitting on a power rail — electrically LEGAL, so ERC is silent while the converter is destroyed), both requiring netlist_path with pinfunction annotations; PC-001 passive completeness (an active IC whose power rails carry ZERO rail→GND decoupling — a pinout-only placement that cannot physically work, and that passes ERC, DRC and every connectivity rule; relocated into this delivery path by plan c03_delivery_contract_and_engine_seams DD-01/DD-08, reported under passive_completeness, PRESENCE only and subject set selected by a U* refdes-prefix proxy, with ICs whose supply pins could not be identified named in ics_without_identifiable_rail rather than folded into the green). stock=0 is a non-blocking warn. READ not_checked FIRST: it is ALWAYS non-empty, in BOTH pass and fail, and lists the defect classes this gate structurally does NOT examine (decoupling adequacy BEYOND rail→GND presence — PC-001 checks that at least one decoupling cap exists per identified rail, never its value/count/placement; loop compensation, component VALUES, sequencing, thermal, ESD, analog SI). A PASS means 'the wiring agrees with the paperwork', NOT 'this circuit is correct' — two board-killing defects once passed every rule AND ERC and were caught only because a human happened to read a datasheet (BR_20260802). Each of R4–R8 also reports status='run'|'not_run' so a caller can never mistake 'never looked' for 'looked, clean'. Fail-fast on absent/empty inputs (BOM_MISSING/BOM_EMPTY/PIN_ALLOC_MISSING). Gate values NEVER relaxed to pass (check_c04 floating-PSRAM false-pass lesson). Pure python, runs in core.",
     "schema": {"type": "object", "properties": {"bom_csv": _STR, "pin_allocation_csv": _STR,
                "netlist_path": {"type": "array", "items": _STR,
                                  "description": "KiCad .net export(s) covering the schematic(s) this BOM is drawn in, as an ARRAY of paths. A single bare path STRING is still accepted at runtime (back-compat) — the schema is deliberately NARROWER than the runtime, because declaring the union is what BREAKS multi-value calls: an anyOf argument gets serialised to TEXT by MCP clients, so ['a.net','b.net'] arrives as one impossible path and R5/R6 die on NETLIST_MISSING (BR_20260730b §P; proven by A/B in ONE request — covers_boards, a plain array, survived while this argument did not). ENABLES R5 (every BOM row must exist as a schematic symbol) and R6 (BOM pin-spec vs wiring polarity). WITHOUT it both rules are skipped and the report carries netlist_crosscheck.status='not_run': a gate=PASS then does NOT mean every part is drawn, it means nobody looked (BR_20260730 F2 — a verdict must carry the scope that produced it)."},
                "covers_boards": {"type": "array", "items": _STR,
                                   "description": "which `board` column values the supplied netlists actually cover, e.g. ['PRODUCT','CORE']. A product BOM spans every board while one .net covers one schematic, so rows on a board with NO netlist have no baseline and are reported under rows_unassessable_board_not_captured rather than as findings. Omit and coverage is INFERRED from which refs resolved — an inference that cannot tell 'no netlist covers this board' from 'every row on it is undrawn', so the report always states which mechanism was used (board_coverage_basis). Declaring it NARROWS the exempt set but can never WIDEN it past what was observed: a board these netlists actually draw stays assessable even if you omit it here, and the contradiction is reported under board_coverage_conflicts (BR_20260730b §Q — otherwise this argument is a mute button that turns the gate green)."},
                "frozen_pad_counts": {"type": "object", "description": "{ref: expected_pad_count} for J_* freeze crosscheck"}, "out_dir": _STR}, "required": ["bom_csv"]}},
    {"name": "bodesign_render_companion", "handler": _h_companion,
     "description": "Render a readable companion (pdf/png) for a non-readable engineering file (.kicad_sch/.kicad_pcb/gerber).",
     "schema": {"type": "object", "properties": {"path": _STR, "out_dir": _STR}, "required": ["path", "out_dir"]}},
    {"name": "bodesign_emit_doc", "handler": _h_doc,
     "description": "Render a markdown deliverable to shareable docx + pdf.",
     "schema": {"type": "object", "properties": {"md_path": _STR, "out_dir": _STR, "formats": {"type": "array", "items": _STR}}, "required": ["md_path", "out_dir"]}},
    {"name": "bodesign_c00_emit_prd_docx", "handler": _h_c00_emit_prd_docx,
     "description": "BORDERLINE keep (R13/DD-3): the render-only path of this verb is ALSO landed (gate.py c00_emit_prd_docx); this container tool remains chiefly for assemble=true, which needs the docxmcp MCP bridge. Renders the C00 PRD as a docxmcp-assemblable package matching the stored Rockbox Word architecture (cover + revision history + 12 sections with per-section table layouts; conditional RF document) — body.md + outline.md + manifest.json + template/template.dotx built from answer_state. DEFAULT is client-side orchestration: bodesign returns the package(s) + an assemble_hint and the CALLING CLIENT drives docxmcp document.assemble itself. Set assemble=true to opt into the internal MCP bridge (BODESIGN_MCP_SERVERS / BODESIGN_MCP_DOCXMCP_URL); when unconfigured it degrades honestly to worker_unavailable and never fabricates a .docx. Honest: missing/drafted/external-needed/blocked/accepted-risk field states stay visible; never marks human approval.",
     "schema": {"type": "object", "properties": {"folder": _STR, "assemble": {"type": "boolean"}}, "required": ["folder"]}},
    {"name": "bodesign_c01_generate_concept_image", "handler": _h_c01_generate_concept_image,
     "description": "Optional C01 add-on: generate a reference-only concept image via Google AI Studio from a C01 concept prompt. Credential source is server-side only: BODESIGN_GOOGLE_API_KEY/GEMINI_API_KEY/GOOGLE_API_KEY env first, then active API account from opencode accounts.json (default family gemini-cli). Does not affect C01 readiness.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "prompt": _STR, "model": _STR}, "required": ["out_dir", "prompt"]}},
    {"name": "bodesign_c02_export_stl", "handler": _h_c02_export_stl,
     "description": "Export C02-ME/Enclosure.stl from Enclosure.scad using local OpenSCAD CLI when available; returns export_unavailable instead of creating fake STL when missing. `out_dir` is the PRODUCT ROOT, never the C02-ME/ stage dir (the stage prefix is already carried internally). status is one of stl_exported | export_failed | export_unavailable | source_missing | folder_missing | folder_is_stage_dir \u2014 the last three used to be a single source_missing, and their fixes differ (generate the source / create the dir / drop the stage segment from out_dir). Every result carries probed_source_path, the absolute path actually stat'ed. openscad_bin_path is the OpenSCAD EXECUTABLE and is the literal string \"not_probed\" (not null) when the call returned before it ever looked for the binary. DEPRECATED: `openscad_path` is a misleadingly-named alias of `source_path` (the .scad SOURCE, not the binary) kept for existing consumers \u2014 read `source_path` / `openscad_bin_path` instead.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "openscad_bin": _STR}, "required": ["out_dir"]}},
    {"name": "bodesign_c02_export_skp", "handler": _h_c02_export_skp,
     "description": "Report native SketchUp SKP export as unavailable unless an explicit SketchUp-capable toolchain is later configured; updates SketchUp_Import_Guide.md and never fabricates Enclosure.skp.",
     "schema": {"type": "object", "properties": {"out_dir": _STR}, "required": ["out_dir"]}},
    {"name": "bodesign_c02_export_step", "handler": _h_c02_export_step,
     "description": "Export a real draft STEP via the build123d/OCP CAD kernel when present AND explicit wall/clearance/lid_clearance dimensions are given (it builds the enclosure solid from the same constraints as the OpenSCAD path); otherwise reports step_export_unavailable and updates STEP_Draft_Handoff.md. Never fabricates Enclosure.step; output is marked draft_unapproved, not ME approval.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "constraints": {"type": "object"},
                "wall_thickness_mm": {"type": "number"}, "clearance_mm": {"type": "number"}, "lid_clearance_mm": {"type": "number"}},
                "required": ["out_dir"]}},
    {"name": "bodesign_render_board_model", "handler": _h_render_board_model,
     "description": "Render a published 3D board model (glTF/.glb, incl. KHR_draco_mesh_compression) to board-view PNGs (top/iso). For open-hardware whose REAL board is published as a 3D model (e.g. OpenMV's OPENMV_N6.glb), this renders the actual board — not an auto-generated layout. Decodes Draco in-process (DracoPy), applies node transforms, colours by material, rasterises offscreen via pyrender/EGL on the me worker. Degrades to no-deps/no-gl rather than crashing.",
     "schema": {"type": "object", "properties": {"glb_path": _STR, "out_dir": _STR,
                "views": {"type": "array", "items": _STR}, "width": {"type": "integer"}, "height": {"type": "integer"}},
                "required": ["glb_path", "out_dir"]}},
    {"name": "bodesign_c02_render_enclosure", "handler": _h_c02_render_enclosure,
     "description": "Render a generated C02 enclosure STL (Enclosure.stl from c02_export_stl) to top/iso design-sketch PNGs — closes the 'voice-to-design' loop so a generated draft is *viewable*. Loads the STL natively via trimesh and rasterises offscreen via pyrender/EGL on the me worker (same backend as render_board_model). STL is already in mm. SINGLE-COLOUR BY DESIGN — this is a stated limitation, not a bug: the STL container carries NO colour, so any color() declaration in Enclosure.scad is DISCARDED at the c02_export_stl step and editing those colours has NO effect on this render. Every face therefore takes ONE colour for the WHOLE model: a neutral enclosure grey, or the optional CMF `color` (hex #RRGGBB[AA] / named EN+中文 e.g. white/黑/silver/銀 / RGB(A) array). PER-PART COLOURING IS NOT SUPPORTED — `color` is a single value, never a per-part colour map, and there is no way to colour base/lid/head separately through this tool (BR_20260901 c02 render per-part colour: needs upstream per-part identity that C02 does not yet emit). Output is marked prototype draft, not ME approval. Degrades to no-deps/no-gl rather than crashing.",
     "schema": {"type": "object", "properties": {"stl_path": _STR, "out_dir": _STR,
                "views": {"type": "array", "items": _STR}, "width": {"type": "integer"}, "height": {"type": "integer"},
                "color": _STR},
                "required": ["stl_path", "out_dir"]}},
    {"name": "bodesign_c02_voice_to_design", "handler": _h_c02_voice_to_design,
     "description": "Orchestrate the full voice-to-design loop: spoken intent → clarify → approval gate → enclosure source → STL → top/iso render. Calls plan_c02_intent; if constraints are incomplete returns the clarifying plan (no CAD); if ready and approve!=true returns the constraint set for confirmation (no CAD). Only with approve=true AND complete constraints+wall/clearance does it run generate_openscad → export_stl → render_enclosure, returning {status:approved, pipeline, images}. The render leg is the SAME engine as c02_render_enclosure and inherits its limitation: SINGLE-COLOUR BY DESIGN — the STL container carries NO colour, so any color() declaration in the generated Enclosure.scad is DISCARDED at the c02_export_stl step and editing those colours has NO effect on the images returned here. Every face takes ONE colour for the WHOLE model: a neutral enclosure grey, or the CMF `color` (this tool's own `color` arg, else the plan's gen_params.cmf_color). PER-PART COLOURING IS NOT SUPPORTED — `color` is a single value, never a per-part colour map, and base/lid/head cannot be coloured separately through this loop (BR_20260901 c02 render per-part colour: needs upstream per-part identity C02 does not yet emit). Honours the C02 approval gate and the no-guess-dimensions rule; degrades honestly when OpenSCAD CLI or GL is absent.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "spec_text": _STR, "answers": {"type": "object"},
                "approve": {"type": "boolean"}, "views": {"type": "array", "items": _STR},
                "width": {"type": "integer"}, "height": {"type": "integer"}, "color": _STR},
                "required": ["out_dir", "spec_text"]}},
    {"name": "bodesign_c02_project_svg", "handler": _h_c02_project_svg,
     "description": "Project the generated 3D enclosure (Enclosure.stl from c02_export_stl) to a clean 2D vector SVG via OpenSCAD projection() — the 2D drawing is DERIVED from the 3D model (same source, no drift), so it is exact geometric paths, not a messy raster trace. Writes a wrapper .scad doing projection(cut=<cut>) import(Enclosure.stl) then runs openscad -o Enclosure.svg on the me worker. cut=false gives the outline silhouette (design view); cut=true a planar z=0 cross-section. Fails fast (no fake SVG) when the STL or OpenSCAD CLI is absent. Returns {status (source_missing|export_unavailable|export_failed|svg_exported), svg_path, wrapper_path, vector_ready}.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "openscad_bin": _STR, "cut": {"type": "boolean"}},
                "required": ["out_dir"]}},
    {"name": "bodesign_vault_ingest", "handler": _h_vault_ingest,
     "description": "Write into the server-side Component Vault (SQLite+FTS5, persistent across projects): upsert component identity, ingest a document (sha256 dedup + blob store), index chunks, and write evidence-backed spec values in one audited call. Every write needs `actor`; specs without evidence are stored unverified (never verified). Returns a write summary + the explicit knowledge-gap list per touched MPN. Contract identical to POST /vault/ingest.",
     "schema": {"type": "object", "properties": {"actor": _STR, "component": {"type": "object"}, "mpns": {"type": "array", "items": _STR}, "document": {"type": "object"}, "document_id": {"type": "integer"}, "chunks": {"type": "array", "items": {"type": "object"}}, "specs": {"type": "array", "items": {"type": "object"}}, "vault_dir": _STR}, "required": ["actor"]}},
    {"name": "bodesign_vault_query", "handler": _h_vault_query,
     "description": "Query the server-side Component Vault: pass `mpn` for the canonical component view (record + alias hit + completeness/gaps + document revision chain) or `query` for FTS5 BM25 full-text search over datasheet chunks (hits carry MPN, document, page anchor). Unknown MPN returns explicit status 'absent' — never an empty success. Contract identical to GET /vault/components/{key} and /vault/search.",
     "schema": {"type": "object", "properties": {"mpn": _STR, "query": _STR, "limit": {"type": "integer"}, "include_stale": {"type": "boolean"}, "vault_dir": _STR}}},
    {"name": "bodesign_vault_spec_check", "handler": _h_vault_spec_check,
     "description": "Trust-gate a spec field against the server vault FIRST (origin='server-vault'), falling back to the project's client datasheet cache (origin='client-cache', pass vault_root). Four-state verdict: verified / unverified / no-field / absent; optionally compares a claimed_value. Contract identical to GET /vault/spec-check.",
     "schema": {"type": "object", "properties": {"mpn": _STR, "field": _STR, "claimed_value": {}, "vault_root": _STR, "vault_dir": _STR}, "required": ["mpn", "field"]}},
    {"name": "bodesign_vault_queue", "handler": _h_vault_queue,
     "description": "Server vault knowledge queue: components with open knowledge gaps ranked by DD-9 priority (usage frequency x gap severity). The 'what to research next' worklist. Contract identical to GET /vault/queue.",
     "schema": {"type": "object", "properties": {"limit": {"type": "integer"}, "vault_dir": _STR}}},
    {"name": "bodesign_vault_diagnostics", "handler": _h_vault_diagnostics,
     "description": "Diagnose the live server-side Component Vault through the supported storage boundary: reports configured vault dir, db presence/size, queue_count, queue preview, and the safe compose-run diagnostic command. It never falls back to a temporary vault or Docker host volume path. Contract identical to GET /vault/diagnostics.",
     "schema": {"type": "object", "properties": {"limit": {"type": "integer"}, "vault_dir": _STR}}},
    {"name": "bodesign_analyzer_selfcheck", "handler": _h_analyzer_selfcheck,
     "description": "Deployment self-check for the C06 analyzer engines (kicad/spice/emc): per engine reports engine_resolvable (the analyzer SCRIPTS are bundled + resolvable via BODESIGN_*_SKILL) and binary_present (kicad-cli / ngspice on PATH), plus can_run, resolved_path, image_role (monolith/ee/core), and all_runnable. Answers 'can simulate/analyze_emc/analyze_thermal actually run in this process?' without a docker exec probe. Distinguishes a missing engine script (would cause skipped-no-skills) from a missing binary (skipped-no-simulator). EE-group: runs on the monolith locally, or forwards to the bodesign-ee worker; the lean core reports image_role=core (engines absent by design — it forwards EE).",
     "schema": {"type": "object", "properties": {}}},

    # ── Domain KB serving (plan mcp_r16-domain-kb, R16) ──
    {"name": "bodesign_kb_query", "handler": _h_kb_query,
     "description": "READ-ONLY, no side effects: query bodesign's self-shipped PCB-design domain KB (the repo ragbase store — distilled, evidence-graded design rules, IPC tables, derating curves, EMC/SI failure modes, workflow controls). Query semantics: whitespace tokens ≥3 codepoints run over FTS; by default a multi-word query is OR-ranked (bm25) so an in-store object reachable by one word is not dropped when a co-occurring word is added (matchMode 'fts-or') — pass mode='all' for exact conjunction (matchMode 'fts-and'). Short CJK tokens (<3) → LIKE scan over title/body, score=0, recency-ordered ('like-scan'); mixed → 'hybrid-or'/'hybrid-and'. Payload always carries matchMode (0 hits is self-describing), hits[] (id/type/title/score/confidence/source_weight) and total. Fail-fast: missing/unmounted KB → KB_UNAVAILABLE + remedy, never empty hits masquerading as no knowledge. Call before judgment-heavy design steps (layout, EMC, SI, derating); bodesign_kb_get(id) returns a hit's full body.",
     "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
     "schema": {"type": "object", "properties": {"q": {"type": "string", "description": "search query; whitespace-tokenized"}, "mode": {"type": "string", "enum": ["any", "all"], "description": "multi-word FTS combination: 'any' (default, OR-ranked recall) or 'all' (exact AND conjunction)"}, "type": {"type": "string", "description": "optional object-type filter: concept|control|workflow|failure-mode|source|extract|asset|issue|role|step"}, "limit": {"type": "integer", "description": "max hits; default 10, cap 50"}}, "required": ["q"]}},
    {"name": "bodesign_kb_get", "handler": _h_kb_get,
     "description": "READ-ONLY, no side effects: fetch ONE domain-KB object's full distilled body (body_md) plus evidence grading (confidence, source_weight) and provenance (its distilled_from/extracted_from lineage edges with per-edge source_weight). Unknown id → KB_OBJECT_NOT_FOUND (consider: bodesign_kb_query to find the right id).",
     "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
     "schema": {"type": "object", "properties": {"id": {"type": "string", "description": "KB object id, e.g. control.pcb.emc-decoupling-placement"}}, "required": ["id"]}},

    # ── Deliverable-cache lifecycle (plan mcp_r13-landing-webdav-cache, DD-5/DD-6) ──
    {"name": "bodesign_cache_provision", "handler": _h_cache_provision,
     "description": "Provision (find-or-mint, idempotent per owner+subject) a per-deliverable WebDAV working cache. Returns the cache token, the /dav/{token}/ mount URL, and host_provision (explicit per-host provision state — decide webdav-mount vs stage-inline from this field). Set issue_webdav_credential=true to ALSO mint the owner's WebDAV Basic credential: the password is returned plaintext ONCE and ROTATED on every issuance (stored salted-hashed; rotation invalidates the previous password, so don't re-issue under a live mount). Default payload carries NO credential. soft_cap is a WARN-FIRST per-owner usage signal; it never blocks. Mount with rclone/davfs2 (class-2 DAV), let heavy tools read/write the same namespace, then bodesign_cache_export + bodesign_cache_close.",
     "schema": {"type": "object", "properties": {"owner_identity": _STR, "subject_id": _STR, "issue_webdav_credential": {"type": "boolean", "description": "opt-in: mint+rotate the owner's WebDAV Basic credential and include it in the payload (R14.6)"}},
                "required": ["owner_identity", "subject_id"]}},
    {"name": "bodesign_cache_export", "handler": _h_cache_export,
     "description": "Export (land) a deliverable cache's whole tree to an absolute host-visible target directory and stamp last_export_at (the close dirty-gate reference). The target's PARENT must already exist — ancestors are never auto-created and no alternative target is guessed (typed EXPORT_TARGET_UNREACHABLE otherwise). Cross-owner access returns typed CACHE_FORBIDDEN. `cache_token` is the cache token from bodesign_cache_provision (do NOT pass it as the generic file-model `token` arg).",
     "schema": {"type": "object", "properties": {"cache_token": _STR, "owner_identity": _STR, "target": _STR},
                "required": ["cache_token", "owner_identity", "target"]}},
    {"name": "bodesign_cache_close", "handler": _h_cache_close,
     "description": "Close a deliverable cache and free its namespace. Dirty-gated: files modified since the last export return typed WORKSPACE_CLOSE_DIRTY plus the unexported list unless force=true (which discards them). Cross-owner access returns typed CACHE_FORBIDDEN.",
     "schema": {"type": "object", "properties": {"cache_token": _STR, "owner_identity": _STR, "force": {"type": "boolean"}},
                "required": ["cache_token", "owner_identity"]}},
]
TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}


def tool_detail_status(name: str) -> int:
    """HTTP status for ``GET /tools/<name>``. Pure; module-scope so it is testable.

    BR_20260730 round 4 (D6). Round 3 fixed the STATUS (200 for an unknown tool
    became 404) but left the decision inside the ``run_http`` closure, where no
    test can reach it -- the exact structural condition this BR named twice as
    the root cause of the two preceding defects. Reverting the fix left every
    test green, which is the definition of an unguarded fix. The decision now
    lives where ``tests/test_mcp_server.py`` already imports (the server module
    itself), so a regression is a red test rather than a silent 200.
    """
    return 200 if name in TOOLS_BY_NAME else 404

# ── Landed tools (plan mcp_r13, task 6.1 / R3) ─────────────────────────
# Bucket-2 verbs moved to the landing plane (skills/bodesign/scripts/gate.py):
# they run on the HOST, writing directly into the caller's repo. A call to a
# removed bodesign_<verb> tool returns a typed TOOL_LANDED error carrying the
# equivalent gate.py command — never an anonymous unknown-tool error. This set
# mirrors gate.py's VERBS registry 1:1 (drift-guarded by tests). Borderline
# (DD-3): c00_emit_prd_docx is in BOTH — gate.py lands the render-only path,
# while the container KEEPS the registered tool for the assemble path (docxmcp
# bridge); a registered name always dispatches normally (registry wins).
LANDED_VERBS = frozenset({
    # C00 PRD family
    "c00_scaffold_prd", "c00_readiness", "c00_emit_prd", "c00_update_answers", "c00_emit_prd_docx",
    # C01 family
    "c01_emit_package", "c01_readiness", "c01_next_question", "c01_update_answers",
    "c01_emit_concept_prompts", "c01_add_reference_image", "c01_confirm_reference_cue",
    "c01_emit_id_visual_package", "c01_emit_cmf_package", "c01_emit_uiux_package",
    # C02 analysis-only
    "c02_readiness", "c02_emit_enclosure_package", "c02_generate_openscad", "c02_plan_intent",
    # C03 emitters
    "c03_export_mechanical_constraints", "c03_emit_partition_diagram", "c03_emit_host_block_diagram",
    # C04/C05/C06 scaffold + readiness
    "c04_emit_layout_package", "c04_readiness", "c05_scaffold_fw_spec", "c05_readiness",
    "c06_assemble_test_plan", "c06_readiness",
    # Orchestration spine
    "agent_registry", "dispatch_work_packet", "list_work_packets", "return_blocker",
    "list_blockers", "ingest_blocker", "wrap_validation_evidence", "return_evidence",
    "list_evidence_returns", "ingest_evidence", "enter_c01_mode", "c00_orchestration_status",
    "c00_orchestration_tick", "reference_board_workflow",
    # Read / gate
    "ingest_project", "package_readiness", "datasheet_lookup", "spec_check", "rca_spec_audit",
    "refs_ingest", "c04_face_placement", "c04_castellation", "c04_dod_traceback",
    # Pure functions
    "plan_design_intent", "evidence_manifest", "pin_allocation", "reference_crosscheck",
    "impedance_solve",
})


def _landing_command(verb: str) -> str:
    return (f"python3 skills/bodesign/scripts/gate.py {verb} --repo <abs-project-dir> "
            "[--json '{...}' | --arg k=v]  (gate.py --list enumerates all landing verbs)")

# ── Toolchain worker grouping/routing (Batch E) ────────────────────────
# Tools are grouped by C0x responsibility / toolchain so heavy deps can live in
# dedicated worker containers (see plans/.../toolchain_workers.md). The default
# served group is "all" (monolith — every tool runs in-process, zero behaviour
# change). A worker runs e.g. `--tools me`; the core runs `--tools core` and
# forwards a non-local tool to its worker URL, or reports it unavailable.
_ME_GROUP_TOOLS = {
    "bodesign_c02_export_stl",
    "bodesign_c02_export_skp",
    "bodesign_c02_export_step",
    "bodesign_render_board_model",
    "bodesign_c02_render_enclosure",
    "bodesign_c02_voice_to_design",
    "bodesign_c02_project_svg",
}
# Electronics engineering (C03/C04/C06): tools whose handlers need KiCad
# (kicad-cli/pcbnew) or ngspice. Pure-python EE-adjacent tools (pin_allocation,
# ingest, crosscheck, the cNN readiness/constraint emitters) stay in core, as does
# emit_doc (LibreOffice → moves to the docs worker in E-5).
_EE_GROUP_TOOLS = {
    "bodesign_emit_symbol",
    "bodesign_compose_schematic",
    "bodesign_emit_layout",
    "bodesign_emit_fab",
    "bodesign_simulate",
    "bodesign_analyze_emc",
    "bodesign_analyze_thermal",
    "bodesign_analyzer_selfcheck",
    "bodesign_export_bom",
    "bodesign_export_netlist",
    "bodesign_render_companion",
    # C04 routing / layout-finishing (pcbnew + ngspice; autoroute needs freerouting in the worker)
    "bodesign_route_net2pcb",
    "bodesign_via_in_pad",
    "bodesign_pour_planes",
    "bodesign_widen_bus_tracks",
    "bodesign_apply_pad_intrinsic_overrides",
    "bodesign_length_match_bus",
    "bodesign_layout_drc_gate",
    "bodesign_si_check",
    "bodesign_autoroute",
    "bodesign_clean_micro_stubs",
    # C04 preflight gates: probe the SAME worker env the gated action runs in
    # (freerouting/pcbnew live in the ee image, NOT the lean facade). Omitting
    # these routed them to `core` -> facade-local probe -> always ready:false
    # (BR_20260729 §A). The gate and the gated action MUST evaluate in one env.
    "bodesign_autoroute_preflight",
    "bodesign_placement_preflight",
    "bodesign_bga_escape_capacity",
    # Authentic component data (LCSC/EasyEDA vendor lib; the 100%-fidelity source gate)
    "bodesign_component_search",
    "bodesign_component_fetch",
    # C03 declarative front-end (atopile toolchain lives in the ee image; DD-2)
    "bodesign_ato_build",
    # NOTE: bodesign_declare_circuit is deliberately NOT in the EE group. It is
    # pure python -- its only KiCad touch is an optional pin-list read, whose
    # absence degrades the verdict to `indeterminate` rather than failing. Put
    # it behind the EE worker and a caller without a KiCad install could not
    # declare topology at all, which is the one thing this layer exists to allow.
}


# NOTE: there is intentionally NO bodesign-docs worker. Final docx/pdf/pptx rendering
# is docxmcp's job — it already ships LibreOffice and the full decompose/assemble
# system. bodesign emits markdown (the source of truth); bodesign_emit_doc is only an
# optional in-process companion renderer that gates gracefully (skipped-no-soffice)
# where LibreOffice is absent (e.g. the lean core), at which point the agent renders
# via docxmcp. So emit_doc stays in `core` — we do not duplicate LibreOffice.


def _group_of(name: str) -> str:
    if name in _ME_GROUP_TOOLS:
        return "me"
    if name in _EE_GROUP_TOOLS:
        return "ee"
    return "core"


for _t in TOOLS:
    _t["group"] = _group_of(_t["name"])

# Tool groups this process executes locally. Set from --tools; default monolith.
SERVED_GROUPS: set[str] = {"all"}

# When a configured worker is briefly unreachable (booting/warming), tell the caller
# to retry after this many seconds instead of treating it as permanently absent.
WORKER_RETRY_AFTER_SECONDS: int = int(os.environ.get("BODESIGN_WORKER_RETRY_AFTER", "5") or 5)


def _serves_locally(group: str) -> bool:
    return "all" in SERVED_GROUPS or group in SERVED_GROUPS


def _worker_url_for_group(group: str) -> str | None:
    return os.environ.get(f"BODESIGN_{group.upper()}_WORKER_URL") or None


def _route_tool(name: str) -> tuple[str, str | None]:
    """Decide how to run a tool: ('local', None) | ('forward', url) | ('unavailable', group)."""
    spec = TOOLS_BY_NAME.get(name)
    if spec is None:
        return ("local", None)  # unknown name handled (as an error) by run_tool
    group = spec.get("group", "core")
    if _serves_locally(group):
        return ("local", None)
    url = _worker_url_for_group(group)
    return ("forward", url) if url else ("unavailable", group)


def _forward_to_worker(url: str, name: str, arguments: dict, group: str = "?") -> dict:
    """Forward a tool call to its worker over the compose network. Worker resolves
    the token on the shared session volume, so we forward the raw arguments.

    The worker URL is configured, so the worker is EXPECTED: a transport failure
    means it is booting/warming or briefly down → return a retryable `worker_starting`
    status (not `worker_unavailable`, which is reserved for "not in this deployment")."""
    import httpx
    try:
        resp = httpx.post(url.rstrip("/") + "/invoke",
                          json={"name": name, "arguments": arguments},
                          timeout=httpx.Timeout(180.0, connect=10.0))
        resp.raise_for_status()
        return resp.json()
    except Exception as error:
        return {"ok": False, "status": "worker_starting", "worker_starting": True,
                "retry_after_seconds": WORKER_RETRY_AFTER_SECONDS, "group": group,
                "error": f"worker '{group}' for '{name}' not reachable yet at {url} "
                         f"({type(error).__name__}); it may be starting — retry in "
                         f"{WORKER_RETRY_AFTER_SECONDS}s"}


# Path-like arg keys resolved inside a token's doc_dir when a tool call carries
# a `token` (docxmcp-style; G11b). Without a token they stay host paths (the
# local same-host UDS mode).
PATH_ARG_KEYS = ("folder", "out_dir", "path", "md_path", "board_path", "in_path", "out_path", "output_path", "report_path", "corpus_dir", "schematic_path", "pcb_path", "gerber_dir", "drill_dir", "project_path", "stl_path", "glb_path")


def _resolve_token_path(doc_dir: Path, raw: str) -> str:
    """Resolve ONE path arg against a token's doc_dir.

    This is the single reference frame shared with ``preflight._classify_one``.
    Both layers MUST agree: preflight decides whether a declared asset resolves
    inside the token namespace, and this decides what the handler is actually
    handed. When they disagreed, preflight said "resolved" while the handler got
    a bare relative string it then resolved against the container CWD — the call
    was neither blocked nor served (BR_20260901 c02_render_enclosure).

    Absolute inputs are returned resolved, NOT grafted under doc_dir: an absolute
    path is legitimate here only when it already lives inside the token namespace
    (preflight rejects the rest with PREFLIGHT_HOST_ONLY_ABSOLUTE), and
    ``lstrip('/')`` on such a path would build a location that exists nowhere.
    This matches the symbol_dirs convention already used below.
    """
    if os.path.isabs(raw):
        return str(Path(raw).resolve())
    return str((doc_dir / raw.lstrip("/")).resolve())

# ── Schema steering for the container boundary (client-behavior fix) ──────────
# Transfer is solved by /files; the residual problem is CLIENT BEHAVIOR — an agent
# must know, AT CALL TIME, that a bodesign path arg has to be container-visible and
# that an unmounted tree goes through the file-model `token`. The server INSTRUCTIONS
# and the skill say this, but neither is guaranteed to be in context when the model
# fills a call; the per-tool inputSchema IS. So every path-taking tool advertises an
# optional `token` (the dispatch above already resolves it generically) and carries a
# described `folder`. This is injected centrally rather than in 32 literals.
_FOLDER_DESC = (
    "Project folder. MUST be visible to the bodesign container: a path under a container mount "
    "(.run / sessions / vault), OR — for a tree that is NOT mounted (a host / Google-Drive / FUSE "
    "path) — set `token` (from bodesign_stage_dir or POST /files) and give this RELATIVE to that "
    "token's tree (\".\" = tree root). A raw unmounted host path is INVISIBLE here; readiness then "
    "returns root_visible:false. Do NOT pass a bare token as folder — pass it in the `token` arg."
)
_TOKEN_PROP = {
    "type": "string",
    "description": (
        "Optional file-model token from bodesign_stage_dir / POST /files. When set, every path arg "
        "(folder, out_dir, …) resolves INSIDE the token's uploaded tree (doc_dir), and produced "
        "files are returned as /files/{token}/blob/{rel}. Use this for ANY tree not under a "
        "container mount — it is how you operate on host/Google-Drive trees the container can't see."
    ),
}


def _steer_path_schemas() -> None:
    """Add the boundary-aware `folder` description + optional `token` to every path-taking tool."""
    for spec in TOOLS:
        schema = spec.get("schema")
        props = schema.get("properties") if isinstance(schema, dict) else None
        if not isinstance(props, dict) or not any(k in props for k in PATH_ARG_KEYS):
            continue
        folder = props.get("folder")
        if isinstance(folder, dict) and "description" not in folder:
            props["folder"] = {**folder, "description": _FOLDER_DESC}
        props.setdefault("token", _TOKEN_PROP)


_steer_path_schemas()


def _snapshot(doc_dir: Path) -> dict:
    snap = {}
    for p in doc_dir.rglob("*"):
        if p.is_file():
            st = p.stat()
            snap[str(p.relative_to(doc_dir))] = (st.st_size, st.st_mtime_ns)
    return snap


def _produced(doc_dir: Path, before: dict) -> list[str]:
    out = []
    for p in doc_dir.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(doc_dir))
            st = p.stat()
            if before.get(rel) != (st.st_size, st.st_mtime_ns):
                out.append(rel)
    return sorted(out)


# Handler-declared statuses that are a FAILURE of the requested operation. A
# handler returning one of these did not do the thing it was asked to do, so the
# envelope MUST NOT say ok:true (BR_20260901: c02_render_enclosure shipped
# ok:true wrapped around result.status="error" / note="STL not found", which
# reads as success to every caller that branches on the envelope).
#
# Deliberately NARROW. `no-deps` / `no-gl` / `empty` / `skipped-*` are HONEST
# DEGRADATION — the tool ran, reached a real boundary, and said so; they keep
# ok:true and are distinguishable via the `result_status` mirror below. Widening
# this set would collapse "the toolchain is absent here" into "this call failed",
# which is the same absent-vs-failed conflation in the other direction.
_HANDLER_ERROR_STATUSES = frozenset({"error"})


def _apply_result_status(envelope: dict) -> dict:
    """Make the envelope `ok` agree with the handler's own declared status.

    Predicate answered: "did the handler report that the requested operation
    FAILED?" When it did, ok flips to False and the handler's status/note are
    lifted to the envelope so a caller that only reads the envelope cannot mistake
    a failure for a success. The inner `result` is left byte-identical — nothing is
    swallowed, rewritten, or defaulted.

    `result_status` is mirrored for EVERY dict result (not only failures) so the
    four render outcomes — rendered / degraded (no-deps, no-gl) / empty / error —
    stay mutually distinguishable at the envelope without re-reading `result`.
    """
    inner = envelope.get("result")
    if not isinstance(inner, dict):
        return envelope
    status = inner.get("status")
    if not isinstance(status, str):
        return envelope
    envelope["result_status"] = status
    if status in _HANDLER_ERROR_STATUSES:
        envelope["ok"] = False
        note = inner.get("note") or inner.get("message") or ""
        envelope["error"] = "TOOL_REPORTED_ERROR"
        envelope["message"] = (
            f"handler reported status={status!r}: {note}" if note
            else f"handler reported status={status!r}"
        )
    return envelope


# R17.2.4/.2.5 typed asset preflight + content assertion (pure functions) and
# R0.6 companion-skill wall-nudge (single-source generator + fingerprint). Both
# live in sibling modules so the SAME logic drives run_tool AND the pytest suite.
try:
    import preflight as _preflight
    import _skill_nudge
    import skill_shipping
except ImportError:  # pragma: no cover - direct-module import path (tests add sys.path)
    from services.mcp import preflight as _preflight  # type: ignore
    from services.mcp import _skill_nudge  # type: ignore
    from services.mcp import skill_shipping  # type: ignore

# R17.2 tools whose declared asset paths are preflighted before dispatch and whose
# produced artifacts are content-asserted after. Maps tool name -> the arg keys
# that name an INPUT asset that must resolve inside the token namespace. Only the
# render/emit/assemble mutation entries (design DD-4 接入點); pure landing/verify
# tools are unaffected (additive, no behaviour change on the success path).
_RENDER_EMIT_ASSET_KEYS = {
    "bodesign_emit_fab": ("board_path",),
    "bodesign_emit_doc": ("md_path",),
    "bodesign_render_companion": ("path",),
    "bodesign_render_board_model": ("glb_path",),
    "bodesign_c02_render_enclosure": ("stl_path",),
}


def _endpoint(url: str, transport: str, *, host_executable: bool) -> dict:
    """One capability-summary endpoint row. host_executable=False marks a
    container/service endpoint that MUST NOT be presented as host-runnable
    (R17.1.1) — a bare client reads this flag instead of guessing from the URL."""
    return {"url": url, "transport": transport, "host_executable": host_executable}


def _build_capabilities() -> dict:
    """R17.1.1 machine-readable capability summary returned alongside the prose
    doctrine by bodesign_init. Compact + actionable; a conformance test executes
    a decision from it (R17.1.2) — e.g. branches on
    transport.service_endpoints[].host_executable being False for a container
    UDS path. Endpoint values come from mcp.json / the running config, never
    hard-coded prose."""
    uds = os.environ.get("BODESIGN_UDS") or str(
        Path(__file__).resolve().parents[2] / ".run" / "bodesign.sock")
    port = os.environ.get("BODESIGN_TCP_PORT", "8077")
    host = os.environ.get("BODESIGN_TCP_HOST", "")
    # The UDS endpoint is a container/service socket: NOT host-executable as a
    # bare shell command (R17.6 (b) — init must not recommend a UDS command that
    # is only a container-side socket path). The TCP endpoint is host-visible.
    service_endpoints = [
        _endpoint(f"unix://{uds}:/mcp/", "streamable-http", host_executable=False),
    ]
    host_endpoints = []
    if host:
        host_endpoints.append(
            _endpoint(f"http://{host}:{port}/mcp/", "streamable-http", host_executable=True))
    return {
        "transport": {
            "service_endpoints": service_endpoints,
            "host_endpoints": host_endpoints,
        },
        "file_ingress": {
            "tools": ["bodesign_stage_dir"],
            "token_model": True,
            "http": "POST /files (tarball)",
        },
        "file_egress": {
            "resources_read": True,
            "uri_scheme": "bodesign://files/<token>/<rel>",
            "http_blob": "/files/{token}/blob/{rel}",
        },
        "webdav_state": {
            "writable": True,
            "lifecycle": ["bodesign_cache_provision", "bodesign_cache_export",
                          "bodesign_cache_close"],
        },
        "companion_skill": COMPANION_SKILL,
        "conditional_tool_families": [
            {"group": "me", "available": bool(os.environ.get("BODESIGN_ME_WORKER_URL")),
             "tools": sorted(_ME_GROUP_TOOLS)},
            {"group": "ee", "available": bool(os.environ.get("BODESIGN_EE_WORKER_URL")),
             "tools": sorted(_EE_GROUP_TOOLS)},
        ],
    }


def render_remedy_line(result: dict) -> str | None:
    """R0.6.4 / R0.5: project a structured ``error.remedy`` dict onto MCP's only
    portable error surface — a ``remedy:`` text line — so a bare client's model
    sees the fix with zero parsing. Returns None when there is no remedy to
    project (byte-identical to before — 天條 11, no fabricated affordance).

    Mirrors docxmcp bin/mcp_server.py _render_remedy_line: a plain-string remedy
    is emitted verbatim; a dict remedy surfaces its ``note`` (+ first runnable
    ``command`` when present)."""
    if not isinstance(result, dict):
        return None
    err = result.get("error")
    if not isinstance(err, dict):
        return None
    remedy = err.get("remedy")
    if remedy is None:
        return None
    if isinstance(remedy, str):
        body = remedy.strip()
        return f"remedy: {body}" if body else None
    if not isinstance(remedy, dict):
        return None
    parts: list[str] = []
    note = remedy.get("note")
    if isinstance(note, str) and note.strip():
        parts.append(note.strip())
    commands = remedy.get("commands")
    if isinstance(commands, list):
        for cmd in commands:
            if isinstance(cmd, dict) and isinstance(cmd.get("cmd"), str) and cmd["cmd"].strip():
                parts.append(f"run on host: {cmd['cmd'].strip()}")
                break
    if not parts:
        return None
    return f"remedy: {'; '.join(parts)}"


def run_tool(name: str, arguments: dict) -> dict:
    # Landed tool (v0.2.0 R13 split): typed TOOL_LANDED + the equivalent gate.py
    # command line — never a silent 404 / anonymous unknown-tool error (R3).
    # A name still in the registry always dispatches normally (the DD-3
    # borderline case: bodesign_c00_emit_prd_docx stays for the assemble path).
    if (name not in TOOLS_BY_NAME and name.startswith("bodesign_")
            and name[len("bodesign_"):] in LANDED_VERBS):
        verb = name[len("bodesign_"):]
        _tools_log.info("tool_landed_hit tool=%s", name)
        return {"ok": False, "error": "TOOL_LANDED",
                "message": f"'{name}' moved to the landing plane in v0.2.0: it is a deterministic "
                           "project-folder verb that runs on the HOST via the bodesign skill's "
                           "gate.py (zero token round-trip), not an MCP tool",
                "landing_command": _landing_command(verb)}
    # R15 self-describing guide (plans/mcp_r15-self-describing-guide DD-1/DD-5):
    # bodesign_init is served IN-PROCESS, not via a registry handler or a worker.
    # Return the single-source doctrine loaded at import (BODESIGN_GUIDE_DOCTRINE);
    # the prompts/get bodesign_init entry projects the SAME constant, so both faces
    # are byte-identical (R15.5 no-drift). Optional `section` is accepted but the
    # doctrine is served whole (no silent truncation of the contract).
    if name == "bodesign_init":
        _tools_log.info("bodesign_init_hit")
        # R17.1.1: prose doctrine preserved byte-for-byte (three existing keys);
        # `capabilities` is ADDITIVE and machine-readable so a conformance test
        # can execute a decision from it (R17.1.2), e.g. branch on a container
        # UDS endpoint carrying host_executable=False.
        return {"ok": True, "doctrine": BODESIGN_GUIDE_DOCTRINE,
                "source": "skills/bodesign/doctrine.md",
                "capabilities": _build_capabilities()}
    # R17.2.3 workspace inspection is served IN-PROCESS (like bodesign_init): its
    # handler resolves the token itself, so it must NOT go through the generic
    # token-pop / path-resolution dispatch below (which would strip `token` before
    # the handler sees it). Pure read; never mutates.
    if name == "bodesign_workspace_inspect":
        return _h_workspace_inspect(dict(arguments or {}))
    # Worker routing: forward a non-local tool to its worker, or report it
    # unavailable when no worker is configured (the build123d gate, generalized).
    decision, target = _route_tool(name)
    if decision == "forward":
        group = (TOOLS_BY_NAME.get(name) or {}).get("group", "?")
        return _forward_to_worker(target, name, arguments or {}, group=group)
    if decision == "unavailable":
        # No worker configured for this group: a deliberate slim deployment that
        # cannot do this here. Permanent (do not retry) — distinct from worker_starting.
        return {"ok": False, "status": "worker_unavailable", "worker_unavailable": True, "group": target,
                "error": f"tool '{name}' is served by the '{target}' worker, which is not configured "
                         f"in this deployment (no BODESIGN_{target.upper()}_WORKER_URL); this deployment "
                         f"cannot run it"}
    spec = TOOLS_BY_NAME.get(name)
    if spec is None:
        return {"error": f"unknown tool: {name}"}
    args = dict(arguments or {})
    token = args.pop("token", None)
    # R17.2.5 content assertions ride as an opt-in `assert` arg, popped so it never
    # reaches the handler; None means no assertion requested (delivery_ready default).
    assertions = args.pop("assert", None)
    doc_dir = before = None
    if token:
        from token_store import TokenError, default_store
        try:
            doc_dir = default_store().resolve(token)
        except TokenError as error:
            return {"ok": False, "error": f"token: {error}"}
        # R17.2.4 typed asset preflight: BEFORE the handler runs, reject unresolved /
        # missing-media / out-of-namespace / host-only-absolute asset paths for the
        # render/emit/assemble mutation entries — fail-fast + typed code + R0.5 remedy,
        # never a silent continue (design DD-4). Uses the pre-resolution rel args so
        # the token namespace is the reference frame.
        asset_keys = _RENDER_EMIT_ASSET_KEYS.get(name)
        if asset_keys:
            asset_paths = [args[k] for k in asset_keys if isinstance(args.get(k), str)]
            verdict = _preflight.preflight_assets(doc_dir, asset_paths, in_token=True)
            if not verdict["ok"]:
                _tools_log.info("preflight_reject tool=%s reasons=%s", name,
                                [f["reason"] for f in verdict["failures"]])
                return {"ok": False, "error": verdict["error"]["code"],
                        "message": verdict["error"]["message"],
                        "preflight": verdict, "remedy": verdict["error"]["remedy"]}
        for key in PATH_ARG_KEYS:
            if isinstance(args.get(key), str):
                args[key] = _resolve_token_path(doc_dir, args[key])
        # symbol_dirs is NOT a plain PATH_ARG_KEYS entry (it may be a str OR a
        # list, and absolute/stdlib entries must be left untouched). A caller
        # staging a custom symbol lib under a token and passing a RELATIVE
        # symbol_dirs (e.g. "symbols") needs each relative entry resolved against
        # the token's doc_dir — otherwise the composer's stdlib merge produces a
        # dir list whose custom entry resolves against the container CWD, never
        # finds the staged lib, and every custom-symbol component collapses to
        # placed:0 (BR_20260723 compose-symbol-dirs round 2). Absolute entries
        # (the KiCad stdlib, or a caller's own absolute path) pass through as-is.
        _sd = args.get("symbol_dirs")
        if _sd is not None:
            def _resolve_sd(v):
                if isinstance(v, str) and not os.path.isabs(v):
                    return _resolve_token_path(doc_dir, v)
                return v
            if isinstance(_sd, str):
                args["symbol_dirs"] = _resolve_sd(_sd)
            elif isinstance(_sd, (list, tuple)):
                args["symbol_dirs"] = [_resolve_sd(v) for v in _sd]
        before = _snapshot(doc_dir)
    try:
        result = {"ok": True, "result": _jsonable(spec["handler"](args))}
        _apply_result_status(result)
    except KbError as error:
        # R16 typed KB errors: content first line IS the code (KB_UNAVAILABLE /
        # KB_BAD_QUERY / KB_OBJECT_NOT_FOUND) — no exception-class prefix.
        return {"ok": False, "isError": True, "error": str(error)}
    except Exception as error:  # surface tool errors as data, not transport failures
        return _maybe_nudge({"ok": False, "error": f"{type(error).__name__}: {error}"},
                            name, args, doc_dir)
    if token:
        result["token"] = token
        result["doc_dir"] = str(doc_dir)
        produced = [{"rel": r, "url": f"/files/{token}/blob/{r}"} for r in _produced(doc_dir, before)]
        result["produced"] = produced
        # R17.2.5: when the caller asked for content assertions, a transport-valid
        # but EMPTY / short artifact is NOT delivery-ready — refuse it loudly.
        if assertions is not None:
            produced_meta = _produced_meta(doc_dir, [p["rel"] for p in produced])
            averdict = _preflight.assert_content(produced_meta, assertions)
            result["content_assertion"] = averdict
            if not averdict["delivery_ready"]:
                _tools_log.info("assertion_not_delivery_ready tool=%s code=%s",
                                name, averdict["error"]["code"])
                return {"ok": False, "error": averdict["error"]["code"],
                        "message": averdict["error"]["message"],
                        "delivery_ready": False, "content_assertion": averdict,
                        "produced": produced}
    return _maybe_nudge(result, name, args, doc_dir)


def _produced_meta(doc_dir: Path, rels: list) -> list:
    """Build the {rel,size,text?} list assert_content consumes from produced rels.
    Text is only read for small text-like artifacts (required_text checks); binary
    / large files carry size only (never loaded into memory)."""
    out = []
    for rel in rels:
        p = (Path(doc_dir) / rel)
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        meta = {"rel": rel, "size": size}
        if p.suffix.lower() in (".md", ".txt", ".csv", ".json", ".xml", ".svg") and size <= 1_000_000:
            try:
                meta["text"] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        out.append(meta)
    return out


def _maybe_nudge(result: dict, name: str, args: dict, doc_dir) -> dict:
    """R0.6 companion-skill wall-nudge. Fingerprint a skipped-companion-skill wall
    from the toolcall itself (never caller skill-state — R0.6.1 定海神針) and, on
    the message the caller ALREADY hit, attach a single-source remedy.

    - hard: enrich the (already-failing) result's error.remedy; a silent ok=True
      no-op at a hard wall is converted to a loud failure (R0.6.3 hard).
    - advisory: append a NON-blocking hint to warnings; success is preserved.

    The structured remedy also gets projected onto the portable content-text line
    by render_remedy_line when the transport serialises the error (R0.6.4)."""
    if not isinstance(result, dict):
        return result
    workspace_files = None
    if doc_dir is not None:
        try:
            from token_store import default_store
            workspace_files = default_store().list_files(Path(doc_dir))
        except Exception:  # pragma: no cover - inspection best-effort, never blocks
            workspace_files = None
    wall = _skill_nudge.detect_wall(name, args, doc_dir, workspace_files=workspace_files)
    if wall is None:
        return result
    if wall["force"] == "hard":
        # Convert a silent ok=True no-op into a loud failure; enrich an existing one.
        if result.get("ok") is not False:
            result = {"ok": False, "error": "WALL_SKIPPED_CONTRACT",
                      "message": wall["why"], "was_silent_noop": True}
        result.setdefault("error", "WALL_SKIPPED_CONTRACT")
        result["remedy"] = wall["remedy"]
        _tools_log.info("wall_nudge_attached tool=%s force=hard why=%s", name, wall["why"])
    else:  # advisory — never converts success to failure
        result.setdefault("warnings", [])
        if isinstance(result["warnings"], list):
            result["warnings"].append(wall["advisory"])
        _tools_log.info("wall_nudge_attached tool=%s force=advisory why=%s", name, wall["why"])
    return result


# ── Self-documenting landing page ──────────────────────────────────────
# Orchestrated skills (run agent-side / on the server host; not bundled in the
# container image) that bodesign drives for analysis / docs / sim / sourcing / fab.
# (name, en, zh-Hant)
ORCHESTRATED_SKILLS = [
    ("kicad", "Schematic/PCB/Gerber analysis — ERC/DRC, netlist, power tree, subcircuit detection. Consumed by simulate/EMC.", "原理圖／PCB／Gerber 分析 — ERC/DRC、網表、電源樹、子電路偵測。供 simulate/EMC 使用。"),
    ("kidoc", "Engineering doc packages — HDD, CE technical file, ICD, design-review, manufacturing-transfer; renders + diagrams.", "工程文件包 — HDD、CE 技術文件、ICD、設計審查、製造移轉；含渲染與框圖。"),
    ("spice", "ngspice simulation of detected subcircuits (filters, dividers, opamp, crystal). Driven by bodesign_simulate.", "以 ngspice 模擬偵測到的子電路（濾波、分壓、運放、晶振）。由 bodesign_simulate 驅動。"),
    ("emc", "EMC pre-compliance risk analysis (FCC/CISPR). Driven by bodesign_analyze_emc.", "EMC 預兼容風險分析（FCC/CISPR）。由 bodesign_analyze_emc 驅動。"),
    ("datasheets", "Extract pinouts/specs from datasheet PDFs → feeds symbol generation (N7).", "從 datasheet PDF 抽取腳位／規格 → 供符號生成（N7）。"),
    ("bom / digikey / lcsc / element14 / mouser", "Part sourcing, pricing, stock, datasheet download.", "零件採購、報價、庫存、datasheet 下載。"),
    ("jlcpcb / pcbway", "Fabrication + assembly ordering, DFM rules.", "製造＋組裝下單、DFM 規則。"),
]

# (en_head, en_body, zh_head, zh_body)
WORKFLOW_STEPS = [
    ("1. Ingest", "Run <code>gate.py ingest_project</code> on the host (landing verb) — it classifies files + flags non-readable ones right in your project folder.",
     "1. 匯入", "在主機執行 <code>gate.py ingest_project</code>（landing verb）— 直接在專案資料夾分類檔案並標記不可讀者。"),
    ("2. Plan", "<code>gate.py plan_design_intent</code> (landing verb) turns a natural-language spec into requirements, clarifying questions, and subsystems.",
     "2. 規劃", "<code>gate.py plan_design_intent</code>（landing verb）把自然語言規格轉成需求、釐清問題與子系統。"),
    ("3. Source evidence", "<code>gate.py evidence_manifest</code> (landing verb) grounds each part in a reference (local corpus first), so design = faithful reuse of known-good boards.",
     "3. 蒐集證據", "<code>gate.py evidence_manifest</code>（landing verb）將每個零件對應到參考設計（本地語料優先），使設計＝忠實重用良品。"),
    ("4. Symbols", "<code>bodesign_emit_symbol</code> turns a datasheet pinout into a KiCad symbol (harvest via the datasheets skill).",
     "4. 符號", "<code>bodesign_emit_symbol</code> 把 datasheet 腳位轉成 KiCad 符號（透過 datasheets skill 採集）。"),
    ("5. Compose + ERC", "<code>bodesign_compose_schematic</code> auto-places components + nets → a kicad-cli-validated schematic (0 ERC).",
     "5. 組成＋ERC", "<code>bodesign_compose_schematic</code> 自動佈點＋接線 → 經 kicad-cli 驗證的原理圖（0 ERC）。"),
    ("6. BOM + pins", "<code>bodesign_export_bom</code> (grouped, MPN) + <code>gate.py pin_allocation</code> (landing verb; the C03↔firmware interface).",
     "6. BOM＋腳位", "<code>bodesign_export_bom</code>（分組、MPN）＋ <code>gate.py pin_allocation</code>（landing verb；C03↔韌體介面）。"),
    ("7. Layout", "<code>bodesign_emit_layout</code> places footprints via pcbnew + DRC + an SVG companion (a starting board to route).",
     "7. 佈局", "<code>bodesign_emit_layout</code> 以 pcbnew 擺放 footprint＋DRC＋SVG 伴隨檔（待繞線的起手板）。"),
    ("8. Fab", "<code>bodesign_emit_fab</code> exports gerbers/drill/pos/STEP/PDF for the factory.",
     "8. 製造", "<code>bodesign_emit_fab</code> 匯出 gerber／鑽孔／pos／STEP／PDF 給工廠。"),
    ("9. Verify", "Four layers: ERC/DRC · <code>reference_crosscheck</code> vs a control group · <code>simulate</code> (SPICE) · <code>analyze_emc</code>/<code>analyze_thermal</code>.",
     "9. 驗證", "四層：ERC/DRC・對照組 <code>reference_crosscheck</code>・SPICE <code>simulate</code>・<code>analyze_emc</code>／<code>analyze_thermal</code>。"),
    ("10. Track", "<code>gate.py package_readiness</code> (landing verb) recomputes the compass + next step until the package is factory-submittable.",
     "10. 追蹤", "<code>gate.py package_readiness</code>（landing verb）重算羅盤與下一步，直到文件包可送廠。"),
]

# UI string table (en / zh-Hant). i18n: lang from ?lang= or Accept-Language.
I18N = {
    "lead": ("An AI PCB-design copilot, delivered as an MCP server (docxmcp-style). Drive the full KiCad lifecycle — schematic → layout → fab — by conversation + raw data: ingest a project tree, plan, generate symbols/schematics, lay out, export fab files, and verify, all validated against KiCad and a known-good reference.",
             "AI 電路設計副駕，以 MCP server 形式交付（比照 docxmcp）。透過對談與提交原始資料，驅動完整 KiCad 生命週期 — 原理圖 → 佈局 → 製造：匯入專案樹、規劃、生成符號／原理圖、佈局、匯出製造檔、驗證，全程以 KiCad 與已知良品對照驗證。"),
    "pill_tools": ("tools", "工具"),
    "sec_arch": ("Architecture — IDEF0 functional decomposition", "架構總覽 — IDEF0 功能分解"),
    "sec_endpoints": ("Endpoints", "連線端點"),
    "sec_install": ("Install &amp; run", "安裝與啟動"),
    "sec_filemodel": ("File model (docxmcp-style)", "檔案模型（docxmcp 風格）"),
    "sec_workflow": ("Circuit-design workflow", "電路設計工作流"),
    "sec_skills": ("Skill packages it orchestrates", "編排的 skill 套件"),
    "sec_tools": ("Tools", "工具"),
    "install_docker": ("<b>Docker (portable, recommended)</b> — bundles KiCad 9 + LibreOffice + pygerber + the mcp SDK:",
                       "<b>Docker（可攜，建議）</b> — 內建 KiCad 9 + LibreOffice + pygerber + mcp SDK："),
    "install_host": ("<b>Host (no Docker)</b> — needs kicad-cli + pcbnew + soffice + ngspice on PATH:",
                     "<b>本機（免 Docker）</b> — 需 PATH 上有 kicad-cli + pcbnew + soffice + ngspice："),
    "install_register": ("<b>Register in an MCP client</b> (see <code>mcp.json</code>): transport <code>streamable-http</code>, url <code>unix://…/bodesign.sock:/mcp/</code>. The container does not publish a TCP port; for remote access put a gateway in front of the socket.",
                         "<b>在 MCP client 註冊</b>（見 <code>mcp.json</code>）：transport <code>streamable-http</code>，url <code>unix://…/bodesign.sock:/mcp/</code>。容器不對外 publish TCP port；遠端存取請在 socket 前面擺 gateway。"),
    "file_body": ("Upload your whole project tree as a tarball → a <b>token</b> whose <code>doc_dir</code> is your tree; pass <code>token</code> to any tool (its path args resolve inside it) and download produced files by token. No host bind mount needed.",
                  "把整個專案樹以 tarball 上傳 → 取得 <b>token</b>（其 <code>doc_dir</code> 即你的樹）；將 <code>token</code> 傳給任何工具（路徑參數在樹內解析），再依 token 下載產物。免主機 bind mount。"),
    "file_stage": ("Or stage inline with the <a href=\"{b}/tools/bodesign_stage_dir\"><code>bodesign_stage_dir</code></a> tool. Tools also accept plain host paths for the local same-host case.",
                   "或用 <a href=\"{b}/tools/bodesign_stage_dir\"><code>bodesign_stage_dir</code></a> 工具以 inline 方式上傳。工具也接受本機路徑（同機 UDS）。"),
    "caveat": ("Reliability is <b>shown, not asserted</b>: bodesign cross-checks against a known-good shipped board (control group) and runs SPICE/EMC. These are pre-silicon risk layers — they do not replace accredited EMC / EVT / DVT at the lab/factory, and no send-to-fab output is emitted without validation + explicit approval.",
               "可靠度是「<b>展示，而非宣稱</b>」：bodesign 以已量產良品（對照組）交叉檢核並執行 SPICE/EMC。這些是矽前風險層，無法取代實驗室／工廠的 EMC／EVT／DVT 認證；未經驗證與明確批准不會輸出送廠檔案。"),
    "skills_intro": ("Install the bodesign lifecycle skill for the C00–C07 workflow; install the EDA companion bundle for verification/source/document engines. These run agent-side (or on the server host via <code>BODESIGN_*_SKILL</code> / <code>~/.claude/skills</code>):",
                     "安裝 bodesign lifecycle skill 取得 C00–C07 工作流；安裝 EDA companion bundle 取得驗證／採購／文件引擎。它們在 agent 端執行（或在 server 主機，透過 <code>BODESIGN_*_SKILL</code> / <code>~/.claude/skills</code>）："),
    "skills_dl": ("Download skill packages", "下載 skill 套件"),
    "tools_full": ("full call schemas →", "完整呼叫 schema →"),
    "idx_crumb": ("tools", "工具"),
    "idx_title": ("Tool catalog", "工具目錄"),
    "idx_lead": ("Click a tool for its full MCP <code>inputSchema</code> and a ready-to-send <code>tools/call</code> payload.",
                 "點擊工具以檢視完整 MCP <code>inputSchema</code> 與可直接送出的 <code>tools/call</code> 範例。"),
    "th_tool": ("Tool", "工具"), "th_desc": ("Description", "說明"), "th_required": ("Required", "必填"),
    "th_name": ("Name", "名稱"), "th_type": ("Type", "型別"),
    "det_params": ("Parameters", "參數"),
    "det_schema": ("inputSchema (JSON Schema)", "inputSchema（JSON Schema）"),
    "det_payload": ("tools/call payload", "tools/call 範例"),
    "det_back": ("← back to catalog", "← 返回目錄"),
    "req": ("required", "必填"), "opt": ("optional", "選填"),
    "unknown": ("Unknown tool", "未知工具"),
    "unknown_body": ("is not registered.", "未註冊。"),
}


def _t(key: str, lang: str) -> str:
    pair = I18N[key]
    return pair[1] if lang == "zh" else pair[0]


def _lang_of(request) -> str:
    q = (request.query_params.get("lang") or "").lower()
    if q.startswith("zh"):
        return "zh"
    if q == "en":
        return "en"
    return "zh" if "zh" in request.headers.get("accept-language", "").lower() else "en"


_CSS = """
:root{color-scheme:dark;--bg:#0e1116;--panel:#161b22;--panel2:#1c232c;--line:#30363d;--text:#e6edf3;--muted:#9aa7b4;--accent:#7ee787;--accent2:#79c0ff}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,sans-serif;margin:0;background:var(--bg);color:var(--text);line-height:1.55}
main{max-width:1080px;margin:0 auto;padding:40px 22px 80px}
h1{font-size:2.2rem;margin:0 0 6px}h2{margin:34px 0 12px;font-size:1.3rem;border-bottom:1px solid var(--line);padding-bottom:6px}
.lead{color:var(--muted);font-size:1.05rem;max-width:760px}.crumb{color:var(--muted);font-size:.9rem;margin-bottom:18px}
code{background:var(--panel2);padding:1px 6px;border-radius:6px;font-family:ui-monospace,monospace;font-size:.9em}
pre{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:14px;overflow:auto;font-family:ui-monospace,monospace;font-size:.85rem}
a{color:var(--accent2);text-decoration:none}a:hover{text-decoration:underline}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.tool{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.tname{font-weight:700;font-family:ui-monospace,monospace}.tname a{color:var(--accent)}.tdesc{color:var(--text);font-size:.9rem;margin:5px 0}.treq{color:var(--muted);font-size:.8rem}
.step{display:flex;gap:14px;padding:9px 0;border-bottom:1px dashed var(--line)}.sh{flex:0 0 150px;color:var(--accent2);font-weight:600}.sb{color:var(--muted)}
ul{color:var(--muted)}.pill{display:inline-block;background:var(--panel2);border:1px solid var(--line);border-radius:999px;padding:2px 10px;margin:2px;font-size:.8rem;color:var(--accent)}
.warn{border-left:3px solid #d29922;padding-left:12px;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:.9rem}td,th{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}.req{color:var(--accent2)}.opt{color:var(--muted)}
"""


def _base() -> str:
    """Public URL base for in-page links (e.g. '/bodesign' behind a gateway).

    A prefix-stripping gateway means the server's *routes* stay unprefixed while
    browser-facing *links* must carry the prefix. Set BODESIGN_HTTP_BASE ONLY
    when such a gateway is actually deployed in front of this socket.

    BR_20260730 round 4 (D1). The compose file set this unconditionally, so the
    landing page rendered 75 links that the same server answered 404 for over
    the only live entry path -- a generated surface asserting an intermediary
    nobody had verified exists. This is the same class as round 3's D1 (a
    runtime-generated claim contradicting reality, invisible to grep), so the
    declaration is now opt-in and its truth is the deployer's explicit act.
    """
    import os
    return os.environ.get("BODESIGN_HTTP_BASE", "").rstrip("/")


def _assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets"


def _human_size(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if f < 1024 or unit == "GB":
            return f"{f:.0f}{unit}" if unit == "B" else f"{f:.1f}{unit}"
        f /= 1024
    return f"{f:.1f}GB"


def _skill_downloads() -> list[tuple[str, str, str]]:
    """(filename, label, human_size) for the landing page's download links.

    Two sources, deliberately distinguishable (BR_20260730):

    * the DECLARED skills, built live from the tree ``mcp.json skillPaths`` names.
      Their size is measured by packing them, because there is no file on disk to
      stat — that absence is the point: nothing can go stale.
    * the vendored EDA companion bundles, which have no in-repo source and so
      remain static files (and are NOT advertised as R9 skills for that reason).

    A declared skill SHADOWS any same-named leftover tarball in assets/, so the
    page can never link a retired frozen copy of something served live.
    """
    out: list[tuple[str, str, str]] = []
    live: set[str] = set()
    try:
        for item in skill_shipping.list_shippable_skills():
            name = item["name"]
            live.add(name)
            label = "bodesign lifecycle" if name == COMPANION_SKILL else name
            size = _human_size(len(skill_shipping.pack_skill_targz(name)))
            out.append((f"{name}.tar.gz", label, size))
    except skill_shipping.SkillShippingError:
        # The landing page is cosmetic; the parity gate in run_http is what makes
        # a broken declaration fatal. Degrading here would hide nothing.
        pass
    d = _assets_dir() / "skills"
    if d.is_dir():
        for p in sorted(d.glob("*.tar.gz"), key=lambda p: (not p.name.startswith("bodesign-eda"), p.name)):
            if p.name[:-len(".tar.gz")] in live:
                continue
            label = "EDA bundle" if p.name.startswith("bodesign-eda") else p.name[:-len(".tar.gz")]
            out.append((p.name, label, _human_size(p.stat().st_size)))
    return out


def _page(title: str, inner: str, lang: str = "en") -> str:
    htmllang = "zh-Hant" if lang == "zh" else "en"
    on = ' style="color:var(--accent);font-weight:700"'
    toggle = ('<div style="text-align:right;font-size:.85rem;margin-bottom:6px">'
              f'<a href="?lang=en"{on if lang != "zh" else ""}>EN</a> · '
              f'<a href="?lang=zh"{on if lang == "zh" else ""}>繁中</a></div>')
    return (f'<!doctype html><html lang="{htmllang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>'
            f'<style>{_CSS}</style></head><body><main>{toggle}{inner}</main></body></html>')


def _landing_html(uds_path: str | None = None, tcp_port: int | None = None, lang: str = "en") -> str:
    import html

    def esc(x):
        return html.escape(str(x))

    def L(k):
        return _t(k, lang)

    uds = uds_path or "<server>.run/bodesign.sock"
    port = tcp_port or 8077
    b = _base()
    req_label = L("th_required")

    tool_cards = []
    for t in TOOLS:
        req = ", ".join(f"<code>{esc(r)}</code>" for r in (t["schema"].get("required") or [])) or "—"
        tool_cards.append(
            f'<div class="tool"><div class="tname"><a href="{b}/tools/{esc(t["name"])}">{esc(t["name"])}</a></div>'
            f'<div class="tdesc">{esc(t["description"])}</div>'
            f'<div class="treq">{req_label}: {req}</div></div>'
        )
    skills = "".join(f"<li><b>{esc(n)}</b> — {esc(zh if lang == 'zh' else en)}</li>"
                     for n, en, zh in ORCHESTRATED_SKILLS)
    dl = _skill_downloads()
    dl_html = ""
    if dl:
        featured = [d for d in dl if d[1] in {"bodesign lifecycle", "EDA bundle"}]
        per = [d for d in dl if d not in featured]
        featured_links = " · ".join(
            f'<a href="{b}/skills/{esc(fn)}" style="color:var(--accent);font-weight:700">⬇ {esc(lb)}</a> '
            f'<span style="color:var(--muted)">({sz})</span>'
            for fn, lb, sz in featured
        )
        links = " · ".join(f'<a href="{b}/skills/{esc(fn)}">{esc(lb)}</a> <span style="color:var(--muted)">({sz})</span>'
                           for fn, lb, sz in per)
        manifest = f'<a href="{b}/skills/MANIFEST.md">MANIFEST</a>'
        dl_html = f'<p style="margin-top:10px"><b>{L("skills_dl")}:</b> {featured_links} · {manifest}</p><p style="font-size:.9rem">{links}</p>'
    workflow = "".join(
        f'<div class="step"><div class="sh">{esc(zh_h if lang == "zh" else eh)}</div>'
        f'<div class="sb">{zb if lang == "zh" else eb}</div></div>'
        for eh, eb, zh_h, zb in WORKFLOW_STEPS)

    inner = f"""
<h1>bodesign <span style="color:var(--accent)">MCP</span></h1>
<p class="lead">{L('lead')}</p>
<p><span class="pill">{len(TOOLS)} {L('pill_tools')}</span><span class="pill">v{esc(SERVER_VERSION)}</span><span class="pill">MCP Streamable HTTP</span><span class="pill">UDS + TCP</span><span class="pill">token file API</span></p>

<h2>{L('sec_arch')}</h2>
<div class="card"><img src="{b}/idef0.svg" alt="bodesign IDEF0" style="width:100%;background:#fff;border-radius:10px;padding:10px"></div>

<h2>{L('sec_endpoints')}</h2>
<div class="card">
<p>MCP: <code>POST /mcp/</code> · Files: <code>POST /files</code>, <code>GET /files/{{token}}/blob/{{rel}}</code> · Health: <code>GET /healthz</code></p>
<p><b>Local (UDS):</b> <code>unix://{esc(uds)}:/mcp/</code><br><b>External:</b> put a gateway in front of the socket — the container binds TCP <code>:{port}</code> <i>inside</i> the compose network only and does <b>not</b> publish it to the host (BR_20260730d: publishing it exposed an unauthenticated <code>POST /invoke</code> on every interface).</p>
</div>

<h2>{L('sec_install')}</h2>
<div class="card">
<p>{L('install_docker')}</p>
<pre>./mcpctl.sh start        # build image + start container (UDS only; no published port)
./mcpctl.sh status
./mcpctl.sh log
./mcpctl.sh stop</pre>
<p>{L('install_host')}</p>
<pre>pip install -r services/mcp/requirements.txt
python services/mcp/server.py --transport http --uds .run/bodesign.sock --port {port}</pre>
<p>{L('install_register').format(port=port)}</p>
</div>

<h2>{L('sec_filemodel')}</h2>
<div class="card">
<p>{L('file_body')}</p>
<pre>tar -C myproject -cf - . | curl --unix-socket .run/bodesign.sock \\
     -X POST -H 'Content-Type: application/x-tar' --data-binary @- http://bd/files
curl --unix-socket .run/bodesign.sock http://bd/files/{{token}}/blob/{{rel}}</pre>
<p>{L('file_stage').format(b=b)}</p>
</div>

<h2>{L('sec_workflow')}</h2>
<div class="card">{workflow}</div>
<p class="warn">{L('caveat')}</p>

<h2>{L('sec_skills')}</h2>
<div class="card"><p>{L('skills_intro')}</p>
<ul>{skills}</ul>{dl_html}</div>

<h2>{L('sec_tools')} ({len(TOOLS)}) — <a href="{b}/tools">{L('tools_full')}</a></h2>
<div class="grid">{''.join(tool_cards)}</div>
"""
    return _page("bodesign MCP", inner, lang)


def _tools_index_html(lang: str = "en") -> str:
    import html

    def esc(x):
        return html.escape(str(x))

    def L(k):
        return _t(k, lang)

    b = _base()
    rows = []
    for t in TOOLS:
        req = ", ".join(f"<code>{esc(r)}</code>" for r in (t["schema"].get("required") or [])) or "—"
        rows.append(f'<tr><td><a href="{b}/tools/{esc(t["name"])}">{esc(t["name"])}</a></td>'
                    f'<td>{esc(t["description"])}</td><td>{req}</td></tr>')
    inner = (f'<p class="crumb"><a href="{b}/">bodesign MCP</a> / {L("idx_crumb")}</p>'
             f'<h1>{L("idx_title")} <span style="color:var(--muted);font-size:1rem">({len(TOOLS)})</span></h1>'
             f'<p class="lead">{L("idx_lead")}</p>'
             f'<div class="card"><table><tr><th>{L("th_tool")}</th><th>{L("th_desc")}</th><th>{L("th_required")}</th></tr>{"".join(rows)}</table></div>')
    return _page("bodesign MCP — tools", inner, lang)


def _tool_detail_html(name: str, lang: str = "en") -> str:
    import html

    def esc(x):
        return html.escape(str(x))

    def L(k):
        return _t(k, lang)

    b = _base()
    spec = TOOLS_BY_NAME.get(name)
    if spec is None:
        inner = (f'<p class="crumb"><a href="{b}/">bodesign MCP</a> / <a href="{b}/tools">{L("idx_crumb")}</a> / {esc(name)}</p>'
                 f'<h1>{L("unknown")}</h1><p class="lead"><code>{esc(name)}</code> {L("unknown_body")} '
                 f'<a href="{b}/tools">{L("det_back")}</a></p>')
        return _page("bodesign MCP — unknown tool", inner, lang)

    schema = spec["schema"]
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    prop_rows = []
    for pname, pdef in props.items():
        typ = pdef.get("type", "any") if isinstance(pdef, dict) else "any"
        tag = (f'<span class="req">{L("req")}</span>' if pname in required
               else f'<span class="opt">{L("opt")}</span>')
        prop_rows.append(f"<tr><td><code>{esc(pname)}</code></td><td>{esc(typ)}</td><td>{tag}</td></tr>")
    schema_json = esc(json.dumps(schema, indent=2, ensure_ascii=False))
    example_args = {p: "…" for p in list(required)[:4]} or {"…": "…"}
    call_payload = esc(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                   "params": {"name": name, "arguments": example_args}}, indent=2, ensure_ascii=False))
    inner = (f'<p class="crumb"><a href="{b}/">bodesign MCP</a> / <a href="{b}/tools">{L("idx_crumb")}</a> / {esc(name)}</p>'
             f'<h1 style="font-family:ui-monospace,monospace;color:var(--accent)">{esc(name)}</h1>'
             f'<p class="lead">{esc(spec["description"])}</p>'
             f'<h2>{L("det_params")}</h2><div class="card"><table><tr><th>{L("th_name")}</th><th>{L("th_type")}</th><th></th></tr>{"".join(prop_rows) or "<tr><td>—</td></tr>"}</table></div>'
             f'<h2>{L("det_schema")}</h2><pre>{schema_json}</pre>'
             f'<h2>{L("det_payload")}</h2><pre>{call_payload}</pre>'
             f'<p class="crumb"><a href="{b}/tools">{L("det_back")}</a></p>')
    return _page(f"bodesign MCP — {name}", inner, lang)


# ── MCP server wiring ──────────────────────────────────────────────────

def build_server():
    from mcp.server import Server
    from mcp.types import TextContent, Tool

    server = Server(SERVER_NAME, version=SERVER_VERSION, instructions=INSTRUCTIONS)

    @server.list_tools()
    async def list_tools() -> list:
        from mcp.types import ToolAnnotations
        out = []
        for t in TOOLS:
            ann = t.get("annotations")
            out.append(Tool(
                name=t["name"], description=t["description"], inputSchema=t["schema"],
                annotations=ToolAnnotations(**ann) if ann else None,
            ))
        return out

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list:
        result = await asyncio.to_thread(run_tool, name, arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    # R15 self-describing guide (plans/mcp_r15-self-describing-guide DD-1/DD-6):
    # bodesign had NO prompts handler; this is the new prompts/list + prompts/get
    # surface. The single R15 `bodesign_init` entry projects the SAME source
    # constant as the bodesign_init TOOL (BODESIGN_GUIDE_DOCTRINE), so both faces
    # are byte-identical (R15.5 no-drift). Reachable by bare MCP clients that only
    # speak prompts/*. No arguments.
    from mcp.types import GetPromptResult, Prompt, PromptMessage

    @server.list_prompts()
    async def list_prompts() -> list:
        return [Prompt(
            name="bodesign_init",
            description=(
                "bodesign's full usage doctrine (R15 self-describing organism): "
                "two-plane routing (landing verbs vs compute tools), the "
                "honesty/no-fallback contract, pre-call disciplines, organ "
                "coordination, and gotchas. Same content as the bodesign_init "
                "tool; this prompts/get face is reachable by bare MCP clients. "
                "No arguments."
            ),
            arguments=[],
        )]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
        if name != "bodesign_init":
            raise KeyError(f"unknown prompt: {name!r}")
        return GetPromptResult(
            description="bodesign R15 usage doctrine (single-source, byte-identical to the bodesign_init tool).",
            messages=[PromptMessage(
                role="user",
                content=TextContent(type="text", text=BODESIGN_GUIDE_DOCTRINE),
            )],
        )

    # R17.2.2 portable resource egress (plan mcp_r17-r06-conformance DD-2): expose
    # every token-produced blob as bodesign://files/<token>/<rel> so a BARE MCP
    # client (stdio-only; no HTTP blob route / WebDAV / UDS curl) retrieves
    # deliverables through the standard resources/* floor (R0.1). Same permission
    # model as the HTTP blob route: the caller must hold the token (a capability),
    # and TokenStore.safe_join guards traversal — no new exposure surface.
    from mcp.types import Resource
    from pydantic import AnyUrl

    _RES_SCHEME = "bodesign"

    def _parse_resource_uri(uri: str) -> tuple[str, str]:
        # bodesign://files/<token>/<rel...>
        s = str(uri)
        prefix = f"{_RES_SCHEME}://files/"
        if not s.startswith(prefix):
            raise ValueError(f"not a bodesign files resource: {uri}")
        rest = s[len(prefix):]
        token, _, rel = rest.partition("/")
        if not token or not rel:
            raise ValueError(f"resource uri needs <token>/<rel>: {uri}")
        return token, rel

    @server.list_resources()
    async def list_resources() -> list:
        from token_store import default_store
        store = default_store()
        out: list = []
        root = store.root
        try:
            token_dirs = [d for d in root.glob("tok_*") if d.is_dir()]
        except OSError:
            token_dirs = []
        for d in token_dirs:
            token = d.name
            for rel in store.list_files(d):
                out.append(Resource(
                    uri=AnyUrl(f"{_RES_SCHEME}://files/{token}/{rel}"),
                    name=f"{token}/{rel}",
                    description=f"token-produced artifact {rel} in {token}",
                    mimeType=_mime_for(rel),
                ))
        return out

    @server.read_resource()
    async def read_resource(uri) -> bytes:
        from token_store import TokenError, default_store
        store = default_store()
        try:
            token, rel = _parse_resource_uri(uri)
        except ValueError as error:
            raise KeyError(f"RESOURCE_NOT_FOUND: {error}")
        try:
            doc_dir = store.resolve(token)
            target = store.safe_join(doc_dir, rel)
        except (TokenError, ValueError) as error:
            raise KeyError(f"RESOURCE_NOT_FOUND: {error}")
        if not target.is_file():
            raise KeyError(f"RESOURCE_NOT_FOUND: {token}/{rel}")
        _tools_log.info("resource_read token=%s rel=%s", token, rel)
        return target.read_bytes()

    return server


def _mime_for(rel: str) -> str:
    import mimetypes
    mt, _ = mimetypes.guess_type(rel)
    return mt or "application/octet-stream"


async def run_stdio() -> None:
    from mcp.server.stdio import stdio_server
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


# Minimal token file store (portable upload/download primitive).
def _sessions_root() -> Path:
    import os
    root = Path(os.environ.get("BODESIGN_SESSIONS_ROOT", str(Path(__file__).resolve().parents[2] / ".run" / "sessions")))
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_cache_dav_routes() -> list:
    """Deliverable-cache lifecycle + WebDAV class-2 routes as a module-level
    factory (plan mcp_r13, tasks 5.3/5.4 — ported from docxmcp
    build_cache_dav_routes) so a Starlette TestClient can build an app from
    just these routes. Every handler is AuthProvider-gated + owner-checked;
    failures are typed 401/403/404 per errors.md — never a fallback identity
    or first-available cache (DD-6 / 天條).
    """
    import importlib
    import shutil
    from urllib.parse import unquote, urlsplit

    from starlette.requests import Request
    from starlette.responses import FileResponse, JSONResponse, Response
    from starlette.routing import Route

    from token_store import StoreOpError, TokenNotFoundError, default_store
    _dav = importlib.import_module("_webdav")
    ap = importlib.import_module("_auth_provider")

    _dav_locks = _dav.LockTable()

    def _put_max_bytes() -> int:
        try:
            return int(os.environ.get("BODESIGN_DAV_MAX_PUT_BYTES", str(64 * 1024 * 1024)))
        except ValueError:
            return 64 * 1024 * 1024

    # ── shared auth + ownership helpers ──

    class _CacheForbidden(Exception):
        def __init__(self, token: str, who: str):
            super().__init__(token, who)
            self.token, self.who = token, who

        def response(self) -> Response:
            return JSONResponse(
                {"error": "CACHE_FORBIDDEN",
                 "message": "cache belongs to another owner; cross-owner access is never granted"},
                status_code=403)

    def _auth_identity(request: Request):
        return ap.default_provider().resolve_identity(
            auth_header=request.headers.get("authorization"),
            cookies=dict(request.cookies),
        )

    def _auth_error_response(exc) -> Response:
        _cache_log.warning("cache_auth_reject code=%s", exc.code)
        return JSONResponse(
            {"error": exc.code, "message": exc.message},
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="bodesign-webdav"'},
        )

    def _require_owned_cache(store, identity, token):
        """cache_meta (→ 404) then owns() (→ 403). Identity + ownership resolve
        BEFORE any filesystem work on the token."""
        meta = store.cache_meta(token)  # TokenNotFoundError → 404
        if not ap.default_provider().owns(identity, meta.owner_identity):
            raise _CacheForbidden(token, identity.owner_identity)
        return meta

    def _mount_url(request: Request, token: str) -> str:
        return f"{str(request.base_url).rstrip('/')}{_base()}/dav/{token}/"

    # ── cache lifecycle handlers (task 5.3) ──

    async def cache_provision(request: Request) -> Response:
        try:
            identity = _auth_identity(request)
        except ap.AuthError as exc:
            return _auth_error_response(exc)
        try:
            payload = await request.json()
        except (json.JSONDecodeError, ValueError):
            payload = {}
        subject_id = (payload or {}).get("subject_id") or ""
        if not subject_id:
            return JSONResponse(
                {"error": "MISSING_SUBJECT_ID", "message": "subject_id is required"},
                status_code=400)
        store = default_store()
        try:
            meta = await asyncio.to_thread(
                store.provision_cache, identity.owner_identity, subject_id)
        except StoreOpError as exc:
            return JSONResponse({"error": exc.code, "message": str(exc)}, status_code=400)
        password = await asyncio.to_thread(
            ap.default_provider().credentials.issue, identity.owner_identity)
        # Per-owner soft cap: WARN-FIRST, NON-BLOCKING (天條). Provision already
        # succeeded; over-cap still returns 201 with an observable signal.
        soft_cap = await asyncio.to_thread(
            _cache_soft_cap_status, store, identity.owner_identity)
        if soft_cap.get("over"):
            _cache_log.warning(
                "cache_soft_cap_exceeded owner=%s count=%d/%d bytes=%d/%d",
                identity.owner_identity, soft_cap["count"], soft_cap["count_cap"],
                soft_cap["bytes"], soft_cap["bytes_cap"])
        _cache_log.info("cache_provision_ok token=%s owner=%s subject=%s",
                        meta.token, identity.owner_identity, subject_id)
        return JSONResponse(
            {"token": meta.token, "subject_id": meta.subject_id,
             "owner": meta.owner_identity,
             "mount_url": _mount_url(request, meta.token),
             "mount_path": f"{_base()}/dav/{meta.token}",
             "webdav_username": identity.owner_identity,
             "webdav_password": password,
             "soft_cap": soft_cap,
             # R14.5 (BR_20260706): explicit per-host provision state.
             "host_provision": ap.host_provision_state()},
            status_code=201)

    async def cache_list_mine(request: Request) -> Response:
        try:
            identity = _auth_identity(request)
        except ap.AuthError as exc:
            return _auth_error_response(exc)
        store = default_store()
        items = await asyncio.to_thread(_cache_list_by_owner, store, identity.owner_identity)
        return JSONResponse({"ok": True, "owner": identity.owner_identity,
                             "caches": items, "count": len(items)})

    async def cache_export(request: Request) -> Response:
        try:
            identity = _auth_identity(request)
        except ap.AuthError as exc:
            return _auth_error_response(exc)
        token = request.path_params["token"]
        try:
            payload = await request.json()
        except (json.JSONDecodeError, ValueError):
            payload = {}
        target = (payload or {}).get("target") or ""
        if not target:
            return JSONResponse(
                {"error": "MISSING_TARGET", "message": "target host path is required"},
                status_code=400)
        store = default_store()
        try:
            await asyncio.to_thread(_require_owned_cache, store, identity, token)
        except TokenNotFoundError:
            return JSONResponse({"error": "CACHE_NOT_FOUND"}, status_code=404)
        except _CacheForbidden as exc:
            return exc.response()
        try:
            result = await asyncio.to_thread(_cache_export_tree, store, token, Path(target))
        except StoreOpError as exc:
            status = 502 if exc.code == "EXPORT_TARGET_UNREACHABLE" else 400
            _cache_log.warning("cache_export_reject token=%s code=%s", token, exc.code)
            return JSONResponse({"error": exc.code, "message": str(exc)}, status_code=status)
        return JSONResponse({"ok": True, **result})

    async def cache_close(request: Request) -> Response:
        try:
            identity = _auth_identity(request)
        except ap.AuthError as exc:
            return _auth_error_response(exc)
        token = request.path_params["token"]
        try:
            payload = await request.json()
        except (json.JSONDecodeError, ValueError):
            payload = {}
        force = bool((payload or {}).get("force", False))
        store = default_store()
        try:
            await asyncio.to_thread(_require_owned_cache, store, identity, token)
        except TokenNotFoundError:
            return JSONResponse({"error": "CACHE_NOT_FOUND"}, status_code=404)
        except _CacheForbidden as exc:
            return exc.response()
        try:
            result = await asyncio.to_thread(_cache_close, store, token, force=force)
        except StoreOpError as exc:
            status = 409 if exc.code == "WORKSPACE_CLOSE_DIRTY" else 400
            _cache_log.warning("cache_close_reject token=%s code=%s", token, exc.code)
            body = {"error": exc.code, "message": str(exc)}
            if getattr(exc, "unexported", None) is not None:
                body["unexported"] = exc.unexported
            return JSONResponse(body, status_code=status)
        return JSONResponse({"ok": True, **result})

    # ── WebDAV class-2 adapter (task 5.4) ──

    def _dav_prefix(token: str) -> str:
        return f"{_base()}/dav/{token}"

    def _dav_dest_parse(destination: str) -> tuple[str | None, str | None]:
        """Destination header → (dest_token, rel). (None, None) = unparseable."""
        if not destination:
            return None, None
        path = urlsplit(destination).path or destination
        path = unquote(path)
        marker = "/dav/"
        idx = path.find(marker)
        if idx < 0:
            return None, None
        rest = path[idx + len(marker):]
        tok, _, rel = rest.partition("/")
        rel = rel.strip("/")
        return (tok or None), (rel or None)

    def _dest_rel_or_response(request: Request, token: str) -> tuple[str | None, Response | None]:
        """Same-token rel from the Destination header, or the typed error
        response: cross-token → 403 CACHE_FORBIDDEN, unparseable → 400."""
        dest_token, dst_rel = _dav_dest_parse(request.headers.get("destination", ""))
        if dest_token is None:
            return None, Response(status_code=400)
        if dest_token != token:
            _cache_log.warning("dav_dest_cross_token token=%s dest_token=%s", token, dest_token)
            return None, JSONResponse(
                {"error": "CACHE_FORBIDDEN",
                 "message": "MOVE/COPY Destination must stay inside the same cache token"},
                status_code=403)
        if dst_rel is None:
            return None, Response(status_code=400)
        return dst_rel, None

    async def _dav_resolve_owned(request: Request, token: str):
        identity = _auth_identity(request)  # AuthError → 401
        store = default_store()
        meta = await asyncio.to_thread(_require_owned_cache, store, identity, token)
        return identity, meta, store

    def _dav_auth_fail(exc) -> Response:
        if isinstance(exc, ap.AuthError):
            return Response(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="bodesign-webdav"',
                         "DAV": _dav.DAV_COMPLIANCE})
        if isinstance(exc, _CacheForbidden):
            return exc.response()
        return Response(status_code=404)  # TokenNotFoundError

    def _store_op_status(exc: StoreOpError) -> int:
        code = exc.code
        if "DEST_EXISTS" in code:
            return 412
        if "SRC_MISSING" in code:
            return 404
        if code == "MKCOL_NOT_DIR":
            return 405
        return 400

    async def dav_dispatch(request: Request) -> Response:
        method = request.method.upper()
        token = request.path_params["token"]
        rel = (request.path_params.get("rel") or "").strip("/")

        if method == "OPTIONS":
            # identity-free capability probe (davfs2/rclone probe pre-auth)
            return Response(status_code=200, headers=_dav.options_headers())

        try:
            identity, meta, store = await _dav_resolve_owned(request, token)
        except (ap.AuthError, _CacheForbidden, TokenNotFoundError) as exc:
            _cache_log.warning("dav_auth_reject method=%s token=%s", method, token)
            return _dav_auth_fail(exc)
        doc_dir = store.root / token

        if method == "PROPFIND":
            depth = _dav.normalise_depth(request.headers.get("depth"))
            try:
                resources = await asyncio.to_thread(
                    _dav.build_propfind, _dav_prefix(token), doc_dir, rel, depth)
            except _dav.PropfindNotFound:
                _cache_log.info("dav_propfind_404 token=%s rel=%s", token, rel)
                return Response(status_code=404)
            xml = _dav.multistatus_xml(resources)
            _cache_log.info("dav_propfind_ok token=%s rel=%s depth=%s n=%d",
                            token, rel, depth, len(resources))
            return Response(xml, status_code=207,
                            media_type="application/xml; charset=utf-8",
                            headers={"DAV": _dav.DAV_COMPLIANCE})

        if method in ("GET", "HEAD"):
            if not rel:
                return Response(status_code=403)
            try:
                target = store.safe_join(doc_dir, rel)
            except (ValueError, OSError):
                _cache_log.warning("dav_traversal_reject method=%s token=%s rel=%s", method, token, rel)
                return JSONResponse({"error": "DAV_TRAVERSAL_REJECTED"}, status_code=403)
            if not target.is_file():
                return Response(status_code=404)
            _cache_log.info("dav_%s_ok token=%s rel=%s", method.lower(), token, rel)
            if method == "HEAD":
                return Response(status_code=200, headers={
                    "Content-Length": str(target.stat().st_size),
                    "Content-Type": "application/octet-stream"})
            return FileResponse(path=str(target), filename=target.name,
                                media_type="application/octet-stream")

        if method == "PUT":
            if not rel:
                return Response(status_code=403)
            blocking = _dav_locks.check(token, rel, identity.owner_identity)
            if blocking is not None:
                _cache_log.warning("dav_put_locked token=%s rel=%s", token, rel)
                return JSONResponse({"error": "DAV_LOCKED"}, status_code=423)
            max_bytes = _put_max_bytes()
            body = b""
            async for chunk in request.stream():
                if chunk:
                    body += chunk
                    if len(body) > max_bytes:
                        _cache_log.warning("dav_put_too_large token=%s rel=%s", token, rel)
                        return JSONResponse({"error": "PAYLOAD_TOO_LARGE"}, status_code=413)
            try:
                target = store.safe_join(doc_dir, rel)
            except (ValueError, OSError):
                _cache_log.warning("dav_traversal_reject method=PUT token=%s rel=%s", token, rel)
                return JSONResponse({"error": "DAV_TRAVERSAL_REJECTED"}, status_code=403)
            def _write() -> None:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
            await asyncio.to_thread(_write)
            await asyncio.to_thread(store.touch_cache, token)
            _cache_log.info("dav_put_ok token=%s rel=%s bytes=%d", token, rel, len(body))
            return Response(status_code=201)

        if method == "DELETE":
            if not rel:
                return Response(status_code=403)
            blocking = _dav_locks.check(token, rel, identity.owner_identity)
            if blocking is not None:
                return JSONResponse({"error": "DAV_LOCKED"}, status_code=423)
            try:
                target = store.safe_join(doc_dir, rel)
            except (ValueError, OSError):
                return JSONResponse({"error": "DAV_TRAVERSAL_REJECTED"}, status_code=403)
            if not target.exists():
                return Response(status_code=404)
            def _delete() -> None:
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    target.unlink(missing_ok=True)
            await asyncio.to_thread(_delete)
            _cache_log.info("dav_delete_ok token=%s rel=%s", token, rel)
            return Response(status_code=204)

        if method == "MKCOL":
            if not rel:
                return Response(status_code=405)
            try:
                await asyncio.to_thread(store.mkdir, token, rel)
            except ValueError:
                return JSONResponse({"error": "DAV_TRAVERSAL_REJECTED"}, status_code=403)
            except StoreOpError as exc:
                return Response(status_code=_store_op_status(exc))
            _cache_log.info("dav_mkcol_ok token=%s rel=%s", token, rel)
            return Response(status_code=201)

        if method == "MOVE":
            if not rel:
                return Response(status_code=403)
            dst_rel, err = _dest_rel_or_response(request, token)
            if err is not None:
                return err
            # source AND destination locks both matter for a rename
            for guarded in (rel, dst_rel):
                if _dav_locks.check(token, guarded, identity.owner_identity) is not None:
                    _cache_log.warning("dav_move_locked token=%s rel=%s", token, guarded)
                    return JSONResponse({"error": "DAV_LOCKED"}, status_code=423)
            overwrite = request.headers.get("overwrite", "T").upper() != "F"
            try:
                _, created = await asyncio.to_thread(
                    store.move, token, rel, dst_rel, overwrite=overwrite)
            except ValueError:
                return JSONResponse({"error": "DAV_TRAVERSAL_REJECTED"}, status_code=403)
            except StoreOpError as exc:
                return Response(status_code=_store_op_status(exc))
            _cache_log.info("dav_move_ok token=%s src=%s dst=%s created=%s",
                            token, rel, dst_rel, created)
            # RFC 4918: 201 when the destination is new, 204 on overwrite.
            return Response(status_code=201 if created else 204)

        if method == "COPY":
            if not rel:
                return Response(status_code=403)
            dst_rel, err = _dest_rel_or_response(request, token)
            if err is not None:
                return err
            # COPY only reads the source; the lock that matters is on the
            # DESTINATION (we are about to write it), mirroring PUT.
            if _dav_locks.check(token, dst_rel, identity.owner_identity) is not None:
                _cache_log.warning("dav_copy_locked token=%s dst=%s", token, dst_rel)
                return JSONResponse({"error": "DAV_LOCKED"}, status_code=423)
            overwrite = request.headers.get("overwrite", "T").upper() != "F"
            try:
                _, created = await asyncio.to_thread(
                    store.copy, token, rel, dst_rel, overwrite=overwrite)
            except ValueError:
                return JSONResponse({"error": "DAV_TRAVERSAL_REJECTED"}, status_code=403)
            except StoreOpError as exc:
                return Response(status_code=_store_op_status(exc))
            _cache_log.info("dav_copy_ok token=%s src=%s dst=%s created=%s",
                            token, rel, dst_rel, created)
            return Response(status_code=201 if created else 204)

        if method == "LOCK":
            ttl = _dav.parse_timeout_header(request.headers.get("timeout"))
            lock = _dav_locks.acquire(token, rel, identity.owner_identity, ttl=ttl)
            if lock is None:
                _cache_log.warning("dav_lock_conflict token=%s rel=%s", token, rel)
                return JSONResponse({"error": "DAV_LOCKED"}, status_code=423)
            _cache_log.info("dav_lock_ok token=%s rel=%s", token, rel)
            return Response(
                _dav_locks.lockdiscovery_xml(lock), status_code=200,
                media_type="application/xml; charset=utf-8",
                headers={"Lock-Token": f"<{lock.token}>"})

        if method == "UNLOCK":
            locktoken = request.headers.get("lock-token", "").strip().lstrip("<").rstrip(">")
            removed = _dav_locks.release(token, rel, locktoken)
            _cache_log.info("dav_unlock token=%s rel=%s removed=%s", token, rel, removed)
            return Response(status_code=204 if removed else 409)

        return Response(status_code=405, headers={"Allow": ", ".join(_dav.ALLOWED_METHODS)})

    return [
        Route("/caches", endpoint=cache_provision, methods=["POST"]),
        Route("/caches", endpoint=cache_list_mine, methods=["GET"]),
        Route("/caches/{token}/export", endpoint=cache_export, methods=["POST"]),
        Route("/caches/{token}/close", endpoint=cache_close, methods=["POST"]),
        Route("/dav/{token}", endpoint=dav_dispatch, methods=list(_dav.ALLOWED_METHODS)),
        Route("/dav/{token}/{rel:path}", endpoint=dav_dispatch, methods=list(_dav.ALLOWED_METHODS)),
    ]


async def run_http(host: str, port: int, uds: str | None = None) -> None:
    import contextlib
    import uvicorn
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import FileResponse, JSONResponse, Response
    from starlette.routing import Mount, Route

    # R9.11.1 startup gate (BR_20260730). The two halves of the skill-shipping
    # contract (mcp.json.skillPaths locally, GET /skills remotely) must describe
    # the SAME tree. Assert it before binding: a server that boots green while
    # serving a companion nobody declared — or declaring one nobody serves — is
    # the MCPSTD_SKILL_HALF_SHIPPED shape, and it stayed invisible for 7 weeks
    # precisely because nothing checked at startup. Raises → the process dies
    # loudly rather than half-shipping (天條 1: fail fast, no silent fallback).
    skill_shipping.assert_skill_source_parity(COMPANION_SKILL)

    server = build_server()
    session_manager = StreamableHTTPSessionManager(app=server, event_store=None, json_response=False, stateless=False)

    async def handle_mcp(scope, receive, send):
        await session_manager.handle_request(scope, receive, send)

    def _health_payload() -> dict:
        # `skill_source` makes the shipped tree's identity REMOTELY OBSERVABLE.
        # BR_20260730 round 4 (D3): the running image served 169 files while a
        # clean clone of the same commit yields 164 -- five untracked working
        # -tree files that `COPY skills` swept in. A consumer had no way to see
        # that: the archive it fetched could not be reproduced from the commit
        # the server claims to be. The fix is not to hide the difference (those
        # files belong to work in progress, not to me) but to publish the digest
        # so a mismatch is detectable rather than invisible.
        payload = {"status": "ok", "service": SERVER_NAME, "version": SERVER_VERSION,
                   "tools": len(TOOLS), "served_groups": sorted(SERVED_GROUPS)}
        try:
            payload["skill_source"] = skill_shipping.skill_source_digest()
        except Exception as error:  # never let observability break liveness
            payload["skill_source"] = {"error": f"{type(error).__name__}: {error}"}
        return payload

    async def healthz(request: Request) -> Response:
        # /healthz kept for back-compat; /health is the MCP-Integration-Standard
        # canonical liveness/readiness endpoint (R8.3).
        return JSONResponse(_health_payload())

    async def health(request: Request) -> Response:
        return JSONResponse(_health_payload())

    async def skills_index(request: Request) -> Response:
        # R8.2 / R9.2 — the remote half of the skill-shipping contract. `skills`
        # carries BARE names (R9.9.1) drawn from the tree mcp.json.skillPaths
        # declares, so a tolerant consumer (R9.8) that appends `.zip` lands on a
        # route that exists. BR_20260730: this used to advertise the FILENAMES of
        # pre-frozen tarballs, which made every conformant client dial
        # `<file>.tar.gz.zip` -> 404 while this endpoint answered 200.
        #
        # `bundles` is deliberately a SEPARATE key: the 12 vendored EDA companion
        # archives have no source tree in this repo, so they can never satisfy the
        # R9.11 parity requirement. Listing them as R9 skills would advertise names
        # whose provenance we cannot assert. Extra keys are explicitly welcome
        # (R9.9.4) — a generic consumer reads `skills` and ignores the rest.
        try:
            items = skill_shipping.list_shippable_skills()
        except skill_shipping.SkillShippingError as exc:
            return JSONResponse({"error": exc.code, "message": exc.message},
                                status_code=exc.status)
        bundles: list[dict] = []
        assets = _assets_dir() / "skills"
        served = {s["name"] for s in items}
        if assets.is_dir():
            for f in sorted(assets.glob("*.tar.gz")):
                if f.name[:-len(".tar.gz")] in served:
                    continue  # served live from source; the frozen copy is retired
                bundles.append({"file": f.name, "bytes": f.stat().st_size,
                                "url": f"/skills/{f.name}"})
        return JSONResponse({"service": SERVER_NAME, "count": len(items), "skills": items,
                             "bundles": bundles, "manifest": "/skills/MANIFEST.md"})

    async def invoke(request: Request) -> Response:
        # Internal worker entrypoint: the core forwards a tool call here. Runs the
        # tool locally on this (worker) process against the shared session volume.
        body = await request.json()
        return JSONResponse(run_tool(body.get("name", ""), body.get("arguments") or {}))

    async def idef0_svg(request: Request) -> Response:
        svg = _assets_dir() / "idef0.zh.svg"
        if not svg.is_file():
            return JSONResponse({"error": "not_found"}, status_code=404)
        return Response(svg.read_text(encoding="utf-8"), media_type="image/svg+xml",
                        headers={"Cache-Control": "no-store"})

    async def skill_download(request: Request) -> Response:
        # R9.2 mandates `GET /skills/<name>.zip`. The suffix belongs to the
        # ENDPOINT, not to the skill's name, so it is stripped here to recover the
        # bare name and the archive is built on the fly from the declared tree
        # (R9.11.3 — by construction the served bytes and the declared source are
        # the same thing; there is no second artifact left to go stale).
        #
        # `.tar.gz` stays reachable for the landing-page links published since
        # 2026-06-07, but for a DECLARED skill it is now projected from that same
        # tree — the format can no longer encode a content difference. Only the
        # vendored EDA bundles (no in-repo source) still stream a static file.
        name = request.path_params["name"]

        async def _packed(bare: str, fmt: str) -> Response:
            packer = {"zip": skill_shipping.pack_skill_zip,
                      "targz": skill_shipping.pack_skill_targz,
                      "engine": skill_shipping.pack_engine_targz}[fmt]
            media = "application/zip" if fmt == "zip" else "application/gzip"
            suffix = ".zip" if fmt == "zip" else ".tar.gz"
            blob = await asyncio.to_thread(packer, bare)
            return Response(blob, media_type=media, headers={
                "Content-Disposition": f'attachment; filename="{bare}{suffix}"',
                "Cache-Control": "no-store",
            })

        # The routing decision (suffix -> format, and the membership gate that
        # decides whether a `.tar.gz` is a declared skill or a vendored bundle)
        # lives in `skill_shipping.classify_skill_request` -- a pure function a
        # plain unittest can call. BR_20260730 round 3 (D4): round 2 extracted
        # only the static-asset half and declared the structural problem solved,
        # leaving THIS half in the closure -- the same untestable place that
        # produced both earlier defects. Half a structural fix leaves the other
        # half free to drift.
        try:
            action, bare = skill_shipping.classify_skill_request(name)
            if action == skill_shipping.SERVE_ZIP:
                return await _packed(bare, "zip")
            if action == skill_shipping.SERVE_TARGZ:
                return await _packed(bare, "targz")
            if action == skill_shipping.SERVE_ENGINE_TARGZ:
                # BR_20260730 round 4 (D4): a vendored bundle name that DOES
                # have an in-repo source is projected from it, so the frozen
                # 2026-06-07 copy beside it can never be what a client gets --
                # the same "let the second artifact not exist" fix the declared
                # skills already received, applied to the half that was skipped.
                return await _packed(bare, "engine")
        except skill_shipping.SkillShippingError as exc:
            # Typed + honest: a 404 says "no such skill", never a 200 holding an
            # empty archive (R9.6.2 — the two must stay distinguishable).
            return JSONResponse({"error": exc.code, "message": exc.message},
                                status_code=exc.status)

        # Static assets: MANIFEST.md and the vendored EDA companion bundles.
        #
        # Every unservable name leaves by the SAME door (404). BR_20260730 V4:
        # this branch used to answer 403 `path_escape` for a name the OS refuses
        # to resolve (a NUL byte raises OSError here), so `bodesign%00.zip` -> 400,
        # `bodesign%00` -> 403 and `nosuch` -> 404 were three vocabularies for one
        # condition. A consumer branches on the status line, and "this is not a
        # thing I serve" is one condition. 403 also leaked a distinction an
        # attacker can probe: it confirmed the name reached the filesystem layer.
        # The decision itself lives in `skill_shipping.resolve_static_asset` --
        # a pure function -- so it is reachable by a plain unittest without a
        # server. BR_20260730 landed TWO defects in this branch (round 1: 403
        # where the other branch said 400 and a plain miss said 404; round 2: an
        # over-long name escaping as a bare OSError -> 500), and both survived a
        # green suite for the same structural reason: as an inline closure inside
        # `run_http`, nothing could construct it to test it. This handler is now
        # only transport; the guard is tested code.
        target = skill_shipping.resolve_static_asset(
            (_assets_dir() / "skills").resolve(), name)
        if target is None:
            return JSONResponse({"error": "not_found"}, status_code=404)
        if target.name == "MANIFEST.md":
            return Response(target.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")
        return FileResponse(str(target), media_type="application/gzip", filename=target.name)

    async def landing(request: Request) -> Response:
        return Response(_landing_html(uds, port, _lang_of(request)), media_type="text/html; charset=utf-8")

    async def tools_index(request: Request) -> Response:
        return Response(_tools_index_html(_lang_of(request)), media_type="text/html; charset=utf-8")

    async def tool_detail(request: Request) -> Response:
        # BR_20260730 round 3 (D3). This answered 200 for a tool that does not
        # exist, while a name containing an encoded `/` answered 404 -- one
        # condition ("this is not a thing I serve") spoken in two status codes,
        # the exact defect the /skills routes just spent three rounds removing.
        # A human reading the page could tell; a client branching on the status
        # line could not, and would cache an "Unknown tool" page as a real one.
        #
        # The page BODY stays: it is genuinely useful to a human who mistyped,
        # and R9.6.2's principle is about the status being honest, not about
        # withholding help. Only the status line changes.
        name = request.path_params["name"]
        status = tool_detail_status(name)
        return Response(_tool_detail_html(name, _lang_of(request)),
                        media_type="text/html; charset=utf-8", status_code=status)

    async def upload_file(request: Request) -> Response:
        """POST /files — ingest a file tree into a fresh token namespace.

        Content-Type discriminates: application/x-tar / application/gzip = a
        directory tarball (the docxmcp client-tree path); else raw single file
        (set x-filename). Returns {token, doc_dir, files}.
        """
        from token_store import TokenError, default_store
        store = default_store()
        ctype = request.headers.get("content-type", "")
        body = await request.body()
        try:
            if ctype.startswith("application/x-tar") or ctype.startswith("application/gzip"):
                result = store.stage_tarball(body, gz=ctype.startswith("application/gzip"))
            else:
                result = store.stage_raw(body, request.headers.get("x-filename", "upload.bin"))
        except TokenError as error:
            return JSONResponse({"error": "stage_failed", "message": str(error)}, status_code=400)
        return JSONResponse(result)

    async def get_blob(request: Request) -> Response:
        from token_store import TokenNotFoundError, default_store
        store = default_store()
        token = request.path_params["token"]
        rel = request.path_params["rel"]
        try:
            doc_dir = store.resolve(token)
            target = store.safe_join(doc_dir, rel)
        except TokenNotFoundError:
            return JSONResponse({"error": "token_not_found"}, status_code=404)
        except (ValueError, OSError):
            return JSONResponse({"error": "path_escape"}, status_code=403)
        if not target.is_file():
            return JSONResponse({"error": "not_found"}, status_code=404)
        return FileResponse(str(target))

    # ── Component Vault HTTP endpoints (R9) — same contract as the MCP
    # bodesign_vault_* tools, via the shared vault_api thin layer.
    # VAULT-Exxx -> HTTP status: storage fail-fast 503, absent 404, input 400.
    def _vault_http(fn) -> Response:
        from bodesign_component_kb.storage import VaultError
        api = _vault_api()
        try:
            result = fn(api)
        except VaultError as error:
            return JSONResponse(api.error_payload(error), status_code=api.http_status(error.code))
        if isinstance(result, dict) and result.get("status") == "absent":
            return JSONResponse(result, status_code=404)
        return JSONResponse(result)

    async def vault_ingest_ep(request: Request) -> Response:
        body = await request.json()
        return await asyncio.to_thread(lambda: _vault_http(lambda api: api.vault_ingest(body)))

    async def vault_component_ep(request: Request) -> Response:
        key = request.path_params["key"]
        return await asyncio.to_thread(lambda: _vault_http(lambda api: api.vault_component(key)))

    async def vault_search_ep(request: Request) -> Response:
        q = request.query_params.get("q", "")
        limit = int(request.query_params.get("limit", "20"))
        include_stale = request.query_params.get("include_stale", "") in ("1", "true", "yes")
        return await asyncio.to_thread(lambda: _vault_http(
            lambda api: api.vault_search(q, limit=limit, include_stale=include_stale)))

    async def vault_queue_ep(request: Request) -> Response:
        limit = int(request.query_params.get("limit", "80"))
        return await asyncio.to_thread(lambda: _vault_http(lambda api: api.vault_queue(limit=limit)))

    async def vault_spec_check_ep(request: Request) -> Response:
        mpn = request.query_params.get("mpn", "")
        spec_field = request.query_params.get("field", "")
        claimed = request.query_params.get("claimed_value")
        vault_root = request.query_params.get("vault_root")
        return await asyncio.to_thread(lambda: _vault_http(
            lambda api: api.vault_spec_check(mpn, spec_field, claimed_value=claimed, vault_root=vault_root)))

    async def vault_diagnostics_ep(request: Request) -> Response:
        limit = int(request.query_params.get("limit", "20"))
        return await asyncio.to_thread(lambda: _vault_http(lambda api: api.vault_diagnostics(limit=limit)))

    app = Starlette(routes=[
        Route("/", landing),
        Route("/tools", tools_index),
        Route("/tools/{name}", tool_detail),
        Route("/idef0.svg", idef0_svg),
        Route("/skills", skills_index),
        Route("/skills/{name}", skill_download),
        Route("/health", health),
        Route("/healthz", healthz),
        Route("/invoke", invoke, methods=["POST"]),
        Route("/files", upload_file, methods=["POST"]),
        Route("/files/{token}/blob/{rel:path}", get_blob),
        Route("/vault/ingest", vault_ingest_ep, methods=["POST"]),
        Route("/vault/components/{key}", vault_component_ep),
        Route("/vault/search", vault_search_ep),
        Route("/vault/queue", vault_queue_ep),
        Route("/vault/spec-check", vault_spec_check_ep),
        Route("/vault/diagnostics", vault_diagnostics_ep),
        Mount("/mcp", app=handle_mcp),
    ])

    # Serve UDS (local) and/or TCP (external) concurrently from one process,
    # sharing a single session manager + app. session_manager.run() is entered
    # once and held open while both uvicorn binds serve.
    binds = []
    if uds:
        binds.append(uvicorn.Server(uvicorn.Config(app, uds=uds)).serve())
        binds.append(_ensure_socket_perms(uds))
    if port is not None:
        binds.append(uvicorn.Server(uvicorn.Config(app, host=host, port=port)).serve())
    if not binds:
        raise ValueError("run_http needs at least one of --uds / --port")
    async with session_manager.run():
        await asyncio.gather(*binds)


async def _ensure_socket_perms(uds: str) -> None:
    """Enforce the MCP-Integration-Standard socket-permission rule (R7.3) so any
    local user (and the rootful-docker gateway) can connect: parent dir 0755,
    socket file 0666. uvicorn creates the socket on bind with a restrictive mode;
    we relax it once it appears. Idempotent, best-effort, never fatal."""
    sock = Path(uds)
    for _ in range(50):  # ~5s: poll until uvicorn has bound the socket
        if sock.exists():
            try:
                os.chmod(sock.parent, 0o755)
            except OSError:
                pass
            try:
                os.chmod(sock, 0o666)
            except OSError:
                pass
            return
        await asyncio.sleep(0.1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="bodesign MCP server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None, help="serve HTTP on this TCP port (external)")
    parser.add_argument("--uds", default=None, help="serve HTTP on this unix socket (local)")
    parser.add_argument("--tools", default="all",
                        help="comma-separated tool groups this process serves locally "
                             "(e.g. 'me' for a worker, 'core' for the front); default 'all' (monolith)")
    args = parser.parse_args(argv)
    global SERVED_GROUPS
    SERVED_GROUPS = {g.strip() for g in args.tools.split(",") if g.strip()} or {"all"}
    if args.transport == "stdio":
        asyncio.run(run_stdio())
    else:
        # UDS and TCP can run together; default to TCP 8077 if neither is given.
        port = args.port
        if not args.uds and port is None:
            port = 8077
        asyncio.run(run_http(args.host, port, args.uds))


if __name__ == "__main__":
    main()
