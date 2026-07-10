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

SERVER_NAME = "bodesign"
SERVER_VERSION = "0.2.0"
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
    "2) LANDING VERBS (NOT MCP tools — run them on the HOST): the ~52 deterministic project-folder "
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
    r = compose_schematic(a["out_dir"], a["project_name"], a["spec"],
                          symbol_dirs=a.get("symbol_dirs", "/usr/share/kicad/symbols"),
                          validate=a.get("validate", True),
                          connection_style=a.get("connection_style"),
                          style=a.get("style", "netlist"),
                          measure_ink=a.get("measure_ink", False),
                          fidelity=a.get("fidelity", False))
    out = {"placed": r.placed, "nets": r.nets, "schematic": r.emit.schematic_path,
           "style": r.style, "engine_rev": _eb.__engine_rev__,
           "unresolved_pins": r.emit.unresolved_pins, "warnings": r.warnings,
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
    return asdict(export_bom(a["schematic_path"], a["out_dir"], group_by=a.get("group_by", "Value"), xlsx=a.get("xlsx", False)))


def _h_export_netlist(a: dict) -> Any:
    from bodesign_eda_bridge import export_netlist
    return asdict(export_netlist(a["schematic_path"], a["out_dir"], fmt=a.get("format", "kicadsexpr")))


def _h_prd_bom_crosscheck(a: dict) -> Any:
    from bodesign_workflow_core import prd_bom_crosscheck
    return asdict(prd_bom_crosscheck(a["manifest_path"], a["netlist_path"], out_dir=a.get("out_dir")))


def _h_check_c03(a: dict) -> Any:
    from bodesign_workflow_core import check_c03
    return asdict(check_c03(a["bom_csv"], pin_allocation_csv=a.get("pin_allocation_csv"),
                            frozen_pad_counts=a.get("frozen_pad_counts"),
                            out_dir=a.get("out_dir")))


def _h_stage_dir(a: dict) -> Any:
    from token_store import default_store
    return default_store().stage_files(a["files"])


def _h_mcp_call(a: dict) -> Any:
    from mcp_delegate import call_external_mcp_tool
    return call_external_mcp_tool(a["server"], a["tool"], a.get("arguments"))


def _h_route_net2pcb(a: dict) -> Any:
    from bodesign_eda_bridge import net2pcb_board
    return net2pcb_board(a["netlist_path"], a["out_path"], layers=a.get("layers", 2),
                         plane_layers=a.get("plane_layers"), track_mm=a.get("track_mm"),
                         placement=a.get("placement"), fpdir=a.get("fpdir"),
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
    from bodesign_eda_bridge import autoroute
    return autoroute(a["board_path"], a["out_path"], passes=a.get("passes", 40),
                     netclasses=a.get("netclasses"),
                     default_width_mm=a.get("default_width_mm", 0.2),
                     default_clearance_mm=a.get("default_clearance_mm", 0.2))


def _h_placement_preflight(a: dict) -> Any:
    from bodesign_eda_bridge import placement_preflight
    return placement_preflight(a["board_path"],
                              min_utilization=a.get("min_utilization", 0.40),
                              board_mm=a.get("board_mm"),
                              courtyard_margin_mm=a.get("courtyard_margin_mm", 0.0))


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


_STR = {"type": "string"}
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
     "description": "C04 routing: build a netted .kicad_pcb from a KiCad netlist — load+place footprints, assign nets, set copper-layer count / reserved plane layers (LT_POWER, signals stay on outer layers) / default track width, draw the board outline. Board outline semantics: pass board_mm=[W,H] to draw the Edge.Cuts rectangle at exactly (0,0)-(W,H) on ANY strategy (this is the single source of truth and matches the deterministic preplace R_edge boundary); when board_mm is omitted the outline auto-frames from pad extents + 3mm margin. The result reports outline_source='board_mm'|'pad_extent'. Connector pin expansion (one symbol pin -> several pads, e.g. USB-C VBUS -> A4/A9/B4/B9) is caller-overridable via `connectors`={refdes:{net:[pads]}} and applies to any USB-C footprint on ANY refdes (not just J1). Returns placed/nets/pads_assigned/unmapped plus applied_pinmaps and unmapped_connectors (a USB-C/declared connector that matched no net name is reported, not silently skipped); unmapped>0 means a footprint's pad names don't match the symbol (floating part). Placement strategy: 'grid' (default, naive 8mm baseline) or 'deterministic' — electrically-aware pure-python pre-placement (main-IC anchoring, decap/crystal pin-affinity clustering, largest-first greedy per R4, fixed-seed SA) plus R1/R8 post-place checks; returns source-anchored placement_violations, hpwl_mm, anchor and echoed effective params. deterministic REQUIRES board_mm and FAILS FAST on missing footprint geometry — it never falls back to grid.",
     "schema": {"type": "object", "properties": {"netlist_path": _STR, "out_path": _STR, "layers": {"type": "integer"}, "plane_layers": {"type": "array", "items": _STR}, "track_mm": {"type": "number"}, "placement": {"type": "object"}, "fpdir": _STR, "clearance_mm": {"type": "number"}, "connectors": {"type": "object", "description": "{refdes: {net_name: [pad ids]}} explicit connector pin expansion; omit to use the built-in USB-C table for USB-C footprints"}, "strategy": {"type": "string", "enum": ["grid", "deterministic"], "description": "placement strategy; default grid (baseline). deterministic = electrically-aware anchoring/clustering/greedy/SA + R1/R8 anchored checks"}, "seed": {"type": "integer", "description": "SA seed for strategy=deterministic (default 42); echoed in result.effective"}, "board_mm": {"type": "array", "items": {"type": "number"}, "description": "[width, height] mm board outline — required for strategy=deterministic"}}, "required": ["netlist_path", "out_path"]}},
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
     "description": "Honest DRC gate: copper + unconnected violation counts (hard fail) reported separately from silkscreen overlaps (cosmetic), plus clean=bool. classify_intrinsic (BR_20260708): further split copper clearance violations into package_intrinsic (same-footprint adjacent pads at the land-pattern's own spacing — USB-C/LGA pad gaps that a pad-level clearance override resolves, NOT a routing error) vs true copper. When on, `copper` EXCLUDES intrinsic ones, and package_intrinsic + package_intrinsic_items (evidence: refs + description) are reported; clean still requires zero TRUE copper + unconnected, so intrinsic gaps neither silently pass nor masquerade as routing errors. Gate values are never relaxed to pass — reclassified with evidence, not waved through.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "classify_intrinsic": {"type": "boolean", "description": "split package-intrinsic pad-gap clearance from true copper errors"}, "pad_adjacency": {"type": "object", "description": "optional {REF: true} for footprints known to have intrinsic sub-rule pad gaps"}}, "required": ["board_path"]}},
    {"name": "bodesign_clean_micro_stubs", "handler": _h_clean_micro_stubs,
     "description": "C04 finish (BR_20260708): remove track segments shorter than min_len_mm (default 0.02mm) left by freerouting SES import — the <0.01mm fragments that read as false unconnected / false clearance (the MIC1 GND 0.0001mm-track symptom). Strips ONLY true micro-stubs below the threshold; vias/zones untouched. Returns removed count + each removed stub's net+length so the cleanup is auditable and never silently drops real routing.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_path": _STR, "min_len_mm": {"type": "number"}}, "required": ["in_path", "out_path"]}},
    {"name": "bodesign_si_check", "handler": _h_si_check,
     "description": "ngspice signal-integrity gate: per net builds a series-terminated transmission-line testbench from the routed length; returns overshoot/undershoot and pass/warn/fail with a worst rollup. Driver/load/edge/thresholds (rdrv/cload/edge_ns/overshoot_pass_pct/overshoot_warn_pct) are caller-overridable — defaults are a documented STM32-class CMOS reference, not a hidden assumption; the result echoes the effective values under `effective`.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "nets": {"type": "array", "items": _STR}, "z0": {"type": "number"}, "rs": {"type": "number"}, "vdd": {"type": "number"}, "rdrv": {"type": "number"}, "cload": {"type": "number"}, "edge_ns": {"type": "number"}, "overshoot_pass_pct": {"type": "number"}, "overshoot_warn_pct": {"type": "number"}}, "required": ["board_path", "nets"]}},
    {"name": "bodesign_autoroute", "handler": _h_autoroute,
     "description": "Autoroute a netted board with Freerouting when java+freerouting.jar are present in the worker; otherwise returns routed=false with the netted board for external routing. NET-CLASS RULES (BR_20260708): pass `netclasses`=[{name,width_mm,clearance_mm,nets?:[exact],match?:[substrings]}] (ORDERED; a net joins the FIRST class that claims it) to inject per-class width/clearance into the exported Specctra DSN — so a 0.5mm-pitch BGA escape region can route at 0.1/0.1mm while signal/power nets keep their own widths, instead of KiCad's single global 0.2mm rule that makes BGA escape impossible. Unclaimed nets fall into a synthesized default class (default_width_mm/default_clearance_mm). Run bodesign_via_in_pad (BGA fanout) BEFORE autoroute so escape stubs exist. Result adds `netclasses` (per-class net counts + DSN-unit widths + dropped-empty warnings) and structured completion (`unconnected`/`complete`) so a router that converged short is visible here, not only at downstream DRC.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "out_path": _STR, "passes": {"type": "integer"}, "netclasses": {"type": "array", "items": {"type": "object", "properties": {"name": _STR, "width_mm": {"type": "number"}, "clearance_mm": {"type": "number"}, "nets": {"type": "array", "items": _STR}, "match": {"type": "array", "items": _STR}}, "required": ["name", "width_mm", "clearance_mm"]}, "description": "ordered per-class DSN rules; a net joins the first class claiming it (exact `nets` or `match` substring)"}, "default_width_mm": {"type": "number"}, "default_clearance_mm": {"type": "number"}}, "required": ["board_path", "out_path"]}},
    {"name": "bodesign_autoroute_preflight", "handler": _h_autoroute_preflight,
     "description": "C04 route-step diagnostic gate (BR_20260708): probe the ee worker for freerouting prerequisites and say EXACTLY what is missing instead of leaving the route step to die on a raw Java HeadlessException. Checks four things: freerouting.jar on disk, java on PATH, a HEADFUL JRE (freerouting v1.9.0 CLI still calls Toolkit.getScreenSize(), so a *-headless JRE lacking libawt_xawt.so throws HeadlessException even under xvfb), and xvfb-run/DISPLAY. Returns {ready, missing:[...], reason, remedy:[...], probe:{...}} — ready=true ONLY when jar+java+headful-JRE+xvfb/DISPLAY are all present. Call this before bodesign_autoroute on a fresh worker; on ready=false do NOT claim a routed board, fix the named gap (or route interactively in KiCad). No arguments.",
     "schema": {"type": "object", "properties": {}}},
    {"name": "bodesign_placement_preflight", "handler": _h_placement_preflight,
     "description": "C04 pre-route placement gate (BR_20260708): read a placed .kicad_pcb and fail fast on a doomed floorplan BEFORE routing, from REAL footprint courtyards (no guessing). Two conditions: (1) courtyard_overlap — any two footprint courtyards that intersect (optionally grown by courtyard_margin_mm) are listed in `overlaps` with the measured mm² (route would inherit a wall of clearance DRC — the 65-violation symptom); (2) sheet_under_filled — total courtyard area / usable board area below min_utilization (default 0.40) means everything is crammed into a strip (the 20%% center-strip symptom). Returns passed=true ONLY when zero overlaps AND utilization meets the floor, plus utilization, overlap_pairs, parts/board areas, board_mm (read from Edge.Cuts unless overridden) and human-readable `reasons`. Never mutates the board and never routes: the caller checks passed and, on failure, re-places (strategy='deterministic') rather than routing into overlap.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "min_utilization": {"type": "number", "description": "floor for parts-courtyard-area / usable-board-area (default 0.40); below it = sheet_under_filled fail"}, "board_mm": {"type": "array", "items": {"type": "number"}, "description": "[width, height] mm override; omit to read board size from Edge.Cuts"}, "courtyard_margin_mm": {"type": "number", "description": "grow each courtyard by this margin before the overlap test (default 0)"}}, "required": ["board_path"]}},
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
    {"name": "bodesign_emit_symbol", "handler": _h_emit_symbol,
     "description": "Generate a KiCad .kicad_sym symbol from a pin list [{number,name,type}].",
     "schema": {"type": "object", "properties": {"symbol_name": _STR, "pins": {"type": "array"}, "output_path": _STR,
                "footprint_filter": _STR, "datasheet": _STR}, "required": ["symbol_name", "pins", "output_path"]}},
    {"name": "bodesign_ato_build", "handler": _h_ato_build,
     "description": "C03 declarative verification front-end: compile an atopile .ato project (pinned toolchain, ee worker) — unit typing + tolerance intervals + assert constraint solving + parametric component picks checked at COMPILE TIME, before anything reaches KiCad. ok=true returns pcb_path (.kicad_pcb, feeds the C04 finishing chain directly — no netlist bridge) + constraint_solve evidence (5th trust layer). ok=false returns a structured deficiency list [{kind: compile_error|unsat_constraint|pick_failure|component_wrapper_missing|toolchain_missing, detail, source_anchor}] — fail-fast, no silent fallback, no constraint relaxation. component_source default 'vault' (Component Vault only; no cloud registry calls); 'registry'/'vault_then_registry' are explicit opt-ins. Raw build log lands at build_log_path in the workspace, not in this response.",
     "schema": {"type": "object", "properties": {"project_path": _STR, "component_source": {"type": "string", "enum": ["vault", "registry", "vault_then_registry"]}, "target": _STR}, "required": ["project_path"]}},
    {"name": "bodesign_compose_schematic", "handler": _h_compose,
     "description": "Compose a schematic from a design spec (components + REF.PIN nets); place + emit + kicad-cli validate. style='netlist' (default, unchanged) uses a naive index grid + global labels (back-compat). style='draftsman' (opt-in) does subsystem-clustered deterministic force-directed placement + drawn wires + sheet-fit for engineer-readable schematics. connection_style overrides the style-derived default when given ('label' global labels; 'wire' orthogonal wires). Components may carry group (subsystem cluster) and x/y (caller-supplied placement). measure_ink=true (draftsman only) renders + measures ink%/content-fill% (toolchain-gated).",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "project_name": _STR, "spec": {"type": "object"},
                "symbol_dirs": {}, "validate": {"type": "boolean"}, "style": {"type": "string", "enum": ["netlist", "draftsman"]},
                "connection_style": {"type": "string", "enum": ["label", "wire", "auto"]}, "measure_ink": {"type": "boolean"},
                "fidelity": {"type": "boolean", "description": "post-emit partition-fidelity gate: compare the spec's expected net partition vs the kicad-cli-exported netlist partition by node-set (net names ignored). Catches collinear-wire net FUSION that ERC is blind to; raises FidelityError (fail-loud) on divergence. Recommended true for connector-dense boards."}}, "required": ["out_dir", "project_name", "spec"]}},
    {"name": "bodesign_emit_layout", "handler": _h_layout,
     "description": "Place footprints on a board via pcbnew, run DRC, render an SVG companion. Placement grid + outline margin are caller-overridable (board_mm/columns/place_start_mm/place_pitch_mm/margin_mm); defaults suit a small ~60x40mm prototype board — pass larger values for bigger/denser layouts instead of the small-board grid.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "project_name": _STR, "components": {"type": "array"},
                "board_mm": {"type": "array"}, "columns": {"type": "integer"}, "place_start_mm": {"type": "number"}, "place_pitch_mm": {"type": "number"}, "margin_mm": {"type": "number"}}, "required": ["out_dir", "project_name", "components"]}},
    {"name": "bodesign_emit_fab", "handler": _h_fab,
     "description": "Export fab outputs (gerbers/drill/pos/step/pdf) from a .kicad_pcb via kicad-cli. The PDF layer set is caller-overridable via pdf_layers; the default (F.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts) suits 2/4-layer boards — pass inner copper layers for 6+ layer stacks so they are not omitted.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "out_dir": _STR, "formats": {"type": "array", "items": _STR}, "pdf_layers": _STR}, "required": ["board_path", "out_dir"]}},
    {"name": "bodesign_simulate", "handler": _h_simulate,
     "description": "Simulate a schematic's analog subcircuits (dividers/filters/opamp/crystal) via the kicad analyzer + spice skill (ngspice); returns per-subcircuit pass/warn/fail. The analog-behaviour trust layer.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "out_dir": _STR, "simulator": _STR, "types": _STR}, "required": ["schematic_path", "out_dir"]}},
    {"name": "bodesign_spice_model_card", "handler": _h_spice_model_card,
     "description": "Generate a datasheet-grounded SPICE model card (diode/ldo/passive) from vault L4 spice_model.* params — deterministic, byte-identical, provenance-stamped. Optional materialize writes the smoke-tested card into <project>/spice/models/ (cascade tier-1, source=vault-grounded). SPX_* errors (missing/ambiguous params, unsupported category) pass through structured; never fabricates parameters.",
     "schema": {"type": "object", "properties": {"mpn": _STR, "category": _STR, "vault_dir": _STR, "materialize": {"type": "boolean"}, "project_dir": _STR}, "required": ["mpn", "category"]}},
    {"name": "bodesign_analyze_emc", "handler": _h_analyze_emc,
     "description": "EMC pre-compliance risk analysis on a schematic + .kicad_pcb (via kicad analyzers + emc skill): severity-bucketed findings (ground plane, decoupling, return paths, stitching, …). Pre-silicon risk, not certification.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "pcb_path": _STR, "out_dir": _STR, "standard": _STR}, "required": ["schematic_path", "pcb_path", "out_dir"]}},
    {"name": "bodesign_analyze_thermal", "handler": _h_analyze_thermal,
     "description": "Thermal hotspot estimate on a schematic + .kicad_pcb (kicad analyze_thermal); per-component temps + thermal score.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "pcb_path": _STR, "out_dir": _STR, "ambient": {"type": "number"}}, "required": ["schematic_path", "pcb_path", "out_dir"]}},
    {"name": "bodesign_export_bom", "handler": _h_export_bom,
     "description": "Export a grouped Bill of Materials (CSV, qty + MPN, DNP excluded) from a schematic; optional xlsx companion.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "out_dir": _STR, "group_by": _STR, "xlsx": {"type": "boolean"}}, "required": ["schematic_path", "out_dir"]}},
    {"name": "bodesign_export_netlist", "handler": _h_export_netlist,
     "description": "Export a netlist from a schematic via kicad-cli.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "out_dir": _STR, "format": _STR}, "required": ["schematic_path", "out_dir"]}},
    {"name": "bodesign_prd_bom_crosscheck", "handler": _h_prd_bom_crosscheck,
     "description": "C00→C03 fulfilment gate (quality/prd-bom-crosscheck L1): deterministically crosscheck the human-audited main_components_structured.json role manifest against the C03 KiCad netlist (.net). Per-role verdicts present/substituted/missing with matched_refs audit trail; missing roles and out-of-envelope substitutions without a recorded user approval are BLOCKING (gate=FAIL — refuse C04 entry). Fail-fast on absent/invalid manifest or netlist (MANIFEST_MISSING/MANIFEST_INVALID/NETLIST_MISSING/NETLIST_PARSE_ERROR); never silently passes. Pure python, runs in core.",
     "schema": {"type": "object", "properties": {"manifest_path": _STR, "netlist_path": _STR, "out_dir": _STR}, "required": ["manifest_path", "netlist_path"]}},
    {"name": "bodesign_check_c03", "handler": _h_check_c03,
     "description": "C03→C04 STAGE-ENTRY gate (BR_20260707): deterministic machine check that C03 (EE) delivery is complete BEFORE C04 layout may start — the entry counterpart to check_c04's output gate. Reads the BOM csv (+ optional Pin_Allocation.csv SSOT + frozen_pad_counts) and HARD-FAILS (gate=FAIL, refuse C04 entry) on: R1 BOM schema lint (column-count/quoting breakage, bad status enum, duplicate (board,ref)); R2 readiness (any draft/blocked row; a finalized row whose mpn carries TBC/TBD/UNDECIDED); R3 drawability (every row needs a symbol-source marker: official|vendor+LCSC|manual|N-A); R4 SSOT crosscheck (active parts U/J/Y/SW must appear in Pin_Allocation.csv — catches the U4 wireless-scheme conflict class; J_* pad counts must match frozen_pad_counts when provided). stock=0 is a non-blocking warn. Fail-fast on absent/empty inputs (BOM_MISSING/BOM_EMPTY/PIN_ALLOC_MISSING). Gate values NEVER relaxed to pass (check_c04 floating-PSRAM false-pass lesson). Pure python, runs in core.",
     "schema": {"type": "object", "properties": {"bom_csv": _STR, "pin_allocation_csv": _STR, "frozen_pad_counts": {"type": "object", "description": "{ref: expected_pad_count} for J_* freeze crosscheck"}, "out_dir": _STR}, "required": ["bom_csv"]}},
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
     "description": "Export C02-ME/Enclosure.stl from Enclosure.scad using local OpenSCAD CLI when available; returns export_unavailable instead of creating fake STL when missing.",
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
     "description": "Render a generated C02 enclosure STL (Enclosure.stl from c02_export_stl) to top/iso design-sketch PNGs — closes the 'voice-to-design' loop so a generated draft is *viewable*. Loads the STL natively via trimesh and rasterises offscreen via pyrender/EGL on the me worker (same backend as render_board_model). STL is already in mm; faces get a neutral enclosure grey since STL carries no colour, unless an optional CMF `color` (hex #RRGGBB[AA] / named EN+中文 e.g. white/黑/silver/銀 / RGB(A) array) is given for a single-colour design sketch. Output is marked prototype draft, not ME approval. Degrades to no-deps/no-gl rather than crashing.",
     "schema": {"type": "object", "properties": {"stl_path": _STR, "out_dir": _STR,
                "views": {"type": "array", "items": _STR}, "width": {"type": "integer"}, "height": {"type": "integer"},
                "color": _STR},
                "required": ["stl_path", "out_dir"]}},
    {"name": "bodesign_c02_voice_to_design", "handler": _h_c02_voice_to_design,
     "description": "Orchestrate the full voice-to-design loop: spoken intent → clarify → approval gate → enclosure source → STL → top/iso render. Calls plan_c02_intent; if constraints are incomplete returns the clarifying plan (no CAD); if ready and approve!=true returns the constraint set for confirmation (no CAD). Only with approve=true AND complete constraints+wall/clearance does it run generate_openscad → export_stl → render_enclosure, returning {status:approved, pipeline, images}. Honours the C02 approval gate and the no-guess-dimensions rule; degrades honestly when OpenSCAD CLI or GL is absent.",
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
    # Authentic component data (LCSC/EasyEDA vendor lib; the 100%-fidelity source gate)
    "bodesign_component_search",
    "bodesign_component_fetch",
    # C03 declarative front-end (atopile toolchain lives in the ee image; DD-2)
    "bodesign_ato_build",
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
PATH_ARG_KEYS = ("folder", "out_dir", "path", "md_path", "board_path", "in_path", "out_path", "output_path", "report_path", "corpus_dir", "schematic_path", "pcb_path", "gerber_dir", "drill_dir", "project_path")

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
        return {"ok": True, "doctrine": BODESIGN_GUIDE_DOCTRINE,
                "source": "skills/bodesign/doctrine.md"}
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
    doc_dir = before = None
    if token:
        from token_store import TokenError, default_store
        try:
            doc_dir = default_store().resolve(token)
        except TokenError as error:
            return {"ok": False, "error": f"token: {error}"}
        for key in PATH_ARG_KEYS:
            if isinstance(args.get(key), str):
                args[key] = str((doc_dir / args[key].lstrip("/")).resolve())
        before = _snapshot(doc_dir)
    try:
        result = {"ok": True, "result": _jsonable(spec["handler"](args))}
    except Exception as error:  # surface tool errors as data, not transport failures
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    if token:
        result["token"] = token
        result["doc_dir"] = str(doc_dir)
        result["produced"] = [{"rel": r, "url": f"/files/{token}/blob/{r}"} for r in _produced(doc_dir, before)]
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
    "install_register": ("<b>Register in an MCP client</b> (see <code>mcp.json</code>): transport <code>streamable-http</code>, url <code>unix://…/bodesign.sock:/mcp/</code> (local) or <code>http://&lt;host&gt;:{port}/mcp/</code> (TCP).",
                         "<b>在 MCP client 註冊</b>（見 <code>mcp.json</code>）：transport <code>streamable-http</code>，url <code>unix://…/bodesign.sock:/mcp/</code>（本機）或 <code>http://&lt;host&gt;:{port}/mcp/</code>（TCP）。"),
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
    """Public URL base for in-page links (e.g. '/bodesign' behind the gateway).

    The gateway strips the prefix for UDS routes, so the server's *routes* stay
    unprefixed, but browser-facing *links* must carry the prefix. Set via
    BODESIGN_HTTP_BASE; empty for direct access.
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
    """(filename, label, human_size) for vendored skill tarballs; lifecycle first."""
    d = _assets_dir() / "skills"
    if not d.is_dir():
        return []
    files = sorted(d.glob("*.tar.gz"), key=lambda p: (p.name != "bodesign.tar.gz", not p.name.startswith("bodesign-eda"), p.name))
    out = []
    for p in files:
        if p.name == "bodesign.tar.gz":
            label = "bodesign lifecycle"
        elif p.name.startswith("bodesign-eda"):
            label = "EDA bundle"
        else:
            label = p.name[:-len(".tar.gz")]
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
<p><b>Local (UDS):</b> <code>unix://{esc(uds)}:/mcp/</code><br><b>External (TCP):</b> <code>http://&lt;host&gt;:{port}/mcp/</code></p>
</div>

<h2>{L('sec_install')}</h2>
<div class="card">
<p>{L('install_docker')}</p>
<pre>./mcpctl.sh start        # build image + start container (UDS + TCP :{port})
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

    return server


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

    server = build_server()
    session_manager = StreamableHTTPSessionManager(app=server, event_store=None, json_response=False, stateless=False)

    async def handle_mcp(scope, receive, send):
        await session_manager.handle_request(scope, receive, send)

    def _health_payload() -> dict:
        return {"status": "ok", "service": SERVER_NAME, "version": SERVER_VERSION,
                "tools": len(TOOLS), "served_groups": sorted(SERVED_GROUPS)}

    async def healthz(request: Request) -> Response:
        # /healthz kept for back-compat; /health is the MCP-Integration-Standard
        # canonical liveness/readiness endpoint (R8.3).
        return JSONResponse(_health_payload())

    async def health(request: Request) -> Response:
        return JSONResponse(_health_payload())

    async def skills_index(request: Request) -> Response:
        # R8.2 / R9.2 — list the companion skill bundles this service ships so a
        # non-opencode host can discover + download them via /skills/<name>.
        skills_dir = (_assets_dir() / "skills")
        items: list[dict] = []
        if skills_dir.is_dir():
            for f in sorted(skills_dir.glob("*.tar.gz")):
                items.append({"name": f.name,
                              "skill": f.name[:-len(".tar.gz")],
                              "bytes": f.stat().st_size,
                              "url": f"/skills/{f.name}"})
        return JSONResponse({"service": SERVER_NAME, "count": len(items), "skills": items,
                             "manifest": "/skills/MANIFEST.md"})

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
        name = request.path_params["name"]
        root = (_assets_dir() / "skills").resolve()
        try:
            target = (root / name).resolve()
            target.relative_to(root)
        except (ValueError, OSError):
            return JSONResponse({"error": "path_escape"}, status_code=403)
        if not target.is_file() or not (target.name.endswith(".tar.gz") or target.name == "MANIFEST.md"):
            return JSONResponse({"error": "not_found"}, status_code=404)
        if target.name == "MANIFEST.md":
            return Response(target.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")
        return FileResponse(str(target), media_type="application/gzip", filename=target.name)

    async def landing(request: Request) -> Response:
        return Response(_landing_html(uds, port, _lang_of(request)), media_type="text/html; charset=utf-8")

    async def tools_index(request: Request) -> Response:
        return Response(_tools_index_html(_lang_of(request)), media_type="text/html; charset=utf-8")

    async def tool_detail(request: Request) -> Response:
        return Response(_tool_detail_html(request.path_params["name"], _lang_of(request)), media_type="text/html; charset=utf-8")

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
