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
import os
import sys
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

SERVER_NAME = "bodesign"
SERVER_VERSION = "0.1.0"
INSTRUCTIONS = (
    "bodesign is an AI PCB design copilot exposed as MCP tools. It ingests a client project "
    "folder, plans requirements, sources reference evidence, generates KiCad symbols/schematics, "
    "lays out + exports fab files, and tracks readiness — validating against KiCad and a known-good "
    "reference (control group).\n\n"
    "FILE MODEL (docxmcp-style): upload a whole project tree as a tarball to POST /files "
    "(Content-Type application/x-tar or gzip) or call bodesign_stage_dir with an inline "
    "{relpath:{content,encoding}} map -> {token, doc_dir, files}. Pass `token` to any tool: its path "
    "args resolve inside the token's doc_dir and the result lists produced files as {rel, url}; fetch "
    "via GET /files/{token}/blob/{rel}. Tools also accept plain host paths (local same-host UDS).\n\n"
    "No send-to-fab output without deterministic validation + explicit approval."
)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


# ── Tool registry ──────────────────────────────────────────────────────
# Each handler takes a dict of arguments and returns a JSON-serializable result.
# Imports are lazy so a missing optional package fails only that tool.

def _h_ingest(a: dict) -> Any:
    from bodesign_reverse_core import ingest_project_folder
    idx = ingest_project_folder(a["folder"])
    d = idx.to_dict()
    d["files"] = d.get("files", [])[:200]  # keep payload bounded
    return d


def _h_plan(a: dict) -> Any:
    from bodesign_workflow_core import plan_design_intent
    return plan_design_intent(a.get("spec", ""), a.get("answers")).to_dict()


def _h_evidence(a: dict) -> Any:
    from bodesign_workflow_core import build_design_evidence_manifest, extract_part_candidates
    parts = a.get("parts") or extract_part_candidates(a.get("spec", ""))
    return build_design_evidence_manifest(parts, a.get("corpus_dir"))


def _h_emit_symbol(a: dict) -> Any:
    from bodesign_eda_bridge import emit_kicad_symbol
    r = emit_kicad_symbol(a["symbol_name"], a["pins"], a["output_path"],
                          footprint_filter=a.get("footprint_filter", ""), datasheet=a.get("datasheet", ""))
    return asdict(r)


def _h_compose(a: dict) -> Any:
    from bodesign_eda_bridge import compose_schematic
    r = compose_schematic(a["out_dir"], a["project_name"], a["spec"],
                          symbol_dirs=a.get("symbol_dirs", "/usr/share/kicad/symbols"),
                          validate=a.get("validate", True))
    return {"placed": r.placed, "nets": r.nets, "schematic": r.emit.schematic_path,
            "unresolved_pins": r.emit.unresolved_pins, "warnings": r.warnings,
            "validation": _jsonable(r.validation) if r.validation else None}


def _h_pin_alloc(a: dict) -> Any:
    from bodesign_eda_bridge import build_pin_allocation, render_pin_allocation_csv
    alloc = build_pin_allocation(a["nets"], tuple(a.get("mcu_refs", [])))
    return {"refs": alloc.refs, "net_count": alloc.net_count, "csv": render_pin_allocation_csv(alloc)}


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


def _h_readiness(a: dict) -> Any:
    from bodesign_workflow_core import assess_package_readiness
    return assess_package_readiness(a["folder"], a.get("milestone", "POC")).to_dict()


def _h_c01_emit(a: dict) -> Any:
    from bodesign_workflow_core import emit_c01_rockbox_package
    return emit_c01_rockbox_package(a["out_dir"], a.get("c00"), a.get("answers")).to_dict()


def _h_c00_scaffold_prd(a: dict) -> Any:
    from bodesign_workflow_core import scaffold_c00_prd_package
    return scaffold_c00_prd_package(a["out_dir"], a.get("project_name"), bool(a.get("include_rf", False))).to_dict()


def _h_c00_readiness(a: dict) -> Any:
    from bodesign_workflow_core import assess_c00_prd_readiness
    return assess_c00_prd_readiness(a["folder"]).to_dict()


def _h_c00_emit_prd(a: dict) -> Any:
    from bodesign_workflow_core import emit_c00_prd_markdown
    return emit_c00_prd_markdown(a["folder"]).to_dict()


def _h_c00_update_answers(a: dict) -> Any:
    from bodesign_workflow_core import c00_update_answers
    return c00_update_answers(a["folder"], a["answers"], regenerate=a.get("regenerate", True)).to_dict()


def _h_c01_readiness(a: dict) -> Any:
    from bodesign_workflow_core import assess_c01_package_readiness
    return assess_c01_package_readiness(a["folder"]).to_dict()


def _h_c01_next_question(a: dict) -> Any:
    from bodesign_workflow_core import c01_next_question
    return c01_next_question(a["folder"]).to_dict()


def _h_c01_update_answers(a: dict) -> Any:
    from bodesign_workflow_core import c01_update_answers
    return c01_update_answers(a["folder"], a["answers"], a.get("c00")).to_dict()


def _h_c01_generate_concept_image(a: dict) -> Any:
    from bodesign_workflow_core import generate_c01_concept_image
    return generate_c01_concept_image(a["out_dir"], a["prompt"], a.get("model")).to_dict()


def _h_c01_emit_concept_prompts(a: dict) -> Any:
    from bodesign_workflow_core import emit_c01_concept_prompts
    return emit_c01_concept_prompts(a["out_dir"], a.get("c00"), a.get("answers")).to_dict()


def _h_c01_add_reference_image(a: dict) -> Any:
    from bodesign_workflow_core import c01_add_reference_image
    return c01_add_reference_image(a["folder"], a["source_image"], a["cue_type"], a["observed_cue"],
                                   a.get("target_artifact", "Ai file"), a.get("notes", "")).to_dict()


def _h_c01_confirm_reference_cue(a: dict) -> Any:
    from bodesign_workflow_core import c01_confirm_reference_cue
    return c01_confirm_reference_cue(a["folder"], a["cue_id"], a["confirmation"], a.get("note", "")).to_dict()


def _h_c02_readiness(a: dict) -> Any:
    from bodesign_workflow_core import assess_c02_constraint_readiness
    return assess_c02_constraint_readiness(a.get("constraints"), a.get("folder")).to_dict()


def _h_c02_emit(a: dict) -> Any:
    from bodesign_workflow_core import emit_c02_enclosure_package
    return emit_c02_enclosure_package(a["out_dir"], a.get("constraints"), a.get("project_summary"), a.get("prototype_intent"), a.get("printer_profile")).to_dict()


def _h_c02_generate_openscad(a: dict) -> Any:
    from bodesign_workflow_core import generate_c02_openscad
    return generate_c02_openscad(a["out_dir"], a.get("constraints"), a.get("wall_thickness_mm"), a.get("clearance_mm"), a.get("lid_clearance_mm")).to_dict()


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


def _h_c03_export_mech_constraints(a: dict) -> Any:
    from bodesign_workflow_core import export_c03_mechanical_constraints
    return export_c03_mechanical_constraints(a["out_dir"], a.get("circuit")).to_dict()


# ── Datasheet vault (lazy, MPN-keyed, provenance-tracked) ──────────────
# The anti-hallucination spec store for RCA: ground an electrical-spec claim in a real
# datasheet/source before asserting it, or label it unverified. Lazy by design — call
# at the moment a bug investigation needs a part's spec, not as a bulk BOM import.
def _h_datasheet_lookup(a: dict) -> Any:
    from bodesign_component_kb import lookup
    entry = lookup(a["mpn"], root=a.get("vault_root"))
    if entry is None:
        return {"status": "absent", "mpn": a["mpn"],
                "advice": "Not in the datasheet vault. Before stating any spec for this part, "
                          "acquire its datasheet (bodesign_datasheet_register with a real PDF "
                          "or cited vendor/distributor URL). Do not assert specs from memory."}
    fields = a.get("fields")
    if fields:
        specs = {k: v for k, v in entry.get("specs", {}).items() if k in fields}
        entry = {**entry, "specs": specs}
    return {"status": "present", **entry}


def _h_datasheet_register(a: dict) -> Any:
    import datetime
    from bodesign_component_kb import register
    return register(
        a["mpn"], vendor=a.get("vendor"), source_url=a.get("source_url"),
        pdf_path=a.get("pdf_path"), specs=a.get("specs"), aliases=a.get("aliases"),
        description=a.get("description"), note=a.get("note"),
        now=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        root=a.get("vault_root"))


def _h_spec_check(a: dict) -> Any:
    from bodesign_component_kb import spec_check
    return spec_check(a["mpn"], a["field"], claimed_value=a.get("claimed_value"),
                      root=a.get("vault_root"))


def _h_rca_spec_audit(a: dict) -> Any:
    from bodesign_component_kb import audit_claims
    return audit_claims(a["claims"], root=a.get("vault_root"))


# ── Orchestration spine (C00 dispatch / blocker backflow) ──────────────
def _h_agent_registry(a: dict) -> Any:
    from bodesign_workflow_core import load_agent_registry
    return load_agent_registry().to_dict()


def _h_dispatch_work_packet(a: dict) -> Any:
    from bodesign_workflow_core import dispatch_work_packet
    return dispatch_work_packet(
        a["folder"], a["target_layer"], a["objective"],
        sections=a.get("sections"), fields=a.get("fields"), generated_docs=a.get("generated_docs"),
        inputs=a.get("inputs"), expected_outputs=a.get("expected_outputs"),
    ).to_dict()


def _h_list_work_packets(a: dict) -> Any:
    from bodesign_workflow_core import list_work_packets
    return {"work_packets": [w.to_dict() for w in list_work_packets(a["folder"])]}


def _h_return_blocker(a: dict) -> Any:
    from bodesign_workflow_core import return_blocker
    return return_blocker(
        a["folder"], a["packet_id"],
        severity=a["severity"], summary=a["summary"], question_for_user=a["question_for_user"],
        affected_c00_fields=a.get("affected_c00_fields"), affected_downstream_layers=a.get("affected_downstream_layers"),
        options=a.get("options"), recommended_owner=a.get("recommended_owner", "user"),
        proposed_state=a.get("proposed_state", "blocked"), evidence=a.get("evidence"),
    ).to_dict()


def _h_list_blockers(a: dict) -> Any:
    from bodesign_workflow_core import list_blockers
    return {"blockers": [b.to_dict() for b in list_blockers(a["folder"], unresolved_only=a.get("unresolved_only", False))]}


def _h_ingest_blocker(a: dict) -> Any:
    from bodesign_workflow_core import ingest_blocker
    return ingest_blocker(
        a["folder"], a["blocker_id"],
        resolved_state=a["resolved_state"], decision=a["decision"], decided_by=a.get("decided_by", "user"),
    ).to_dict()


def _h_enter_c01_mode(a: dict) -> Any:
    from bodesign_workflow_core import enter_c01_mode
    return enter_c01_mode(a["folder"], c00=a.get("c00"), answers=a.get("answers"), objective=a.get("objective")).to_dict()


def _h_c00_orchestration_status(a: dict) -> Any:
    from bodesign_workflow_core import c00_orchestration_status
    return c00_orchestration_status(a["folder"]).to_dict()


def _h_c00_orchestration_tick(a: dict) -> Any:
    from bodesign_workflow_core import c00_orchestration_tick
    return c00_orchestration_tick(a["folder"], auto_dispatch=a.get("auto_dispatch", True)).to_dict()


def _h_c04_emit_layout_package(a: dict) -> Any:
    from bodesign_workflow_core import emit_c04_layout_package
    return emit_c04_layout_package(a["out_dir"], a.get("c01"), a.get("c03")).to_dict()


def _h_c04_readiness(a: dict) -> Any:
    from bodesign_workflow_core import assess_c04_layout_readiness
    return assess_c04_layout_readiness(a["folder"]).to_dict()


def _h_c05_scaffold_fw_spec(a: dict) -> Any:
    from bodesign_workflow_core import scaffold_c05_fw_spec
    return scaffold_c05_fw_spec(a["out_dir"], a.get("software"), a.get("pin_map")).to_dict()


def _h_c05_readiness(a: dict) -> Any:
    from bodesign_workflow_core import assess_c05_fw_readiness
    return assess_c05_fw_readiness(a["folder"]).to_dict()


def _h_c06_assemble_test_plan(a: dict) -> Any:
    from bodesign_workflow_core import assemble_c06_test_plan
    return assemble_c06_test_plan(a["out_dir"], a.get("verdicts"), a.get("certification_targets")).to_dict()


def _h_c06_readiness(a: dict) -> Any:
    from bodesign_workflow_core import assess_c06_readiness
    return assess_c06_readiness(a["folder"]).to_dict()


def _h_crosscheck(a: dict) -> Any:
    from bodesign_workflow_core import crosscheck_nets
    return crosscheck_nets(set(a["generated_nets"]), set(a["reference_nets"]),
                           a.get("label", "interface"), a.get("provenance")).to_dict()


def _h_simulate(a: dict) -> Any:
    from bodesign_eda_bridge import simulate_schematic
    return asdict(simulate_schematic(a["schematic_path"], a["out_dir"], simulator=a.get("simulator", "ngspice"), types=a.get("types")))


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


def _h_stage_dir(a: dict) -> Any:
    from token_store import default_store
    return default_store().stage_files(a["files"])


def _h_mcp_call(a: dict) -> Any:
    from mcp_delegate import call_external_mcp_tool
    return call_external_mcp_tool(a["server"], a["tool"], a.get("arguments"))


def _h_impedance_solve(a: dict) -> Any:
    from bodesign_eda_bridge import solve_impedance
    return solve_impedance(a["stackup"], a["targets"])


def _h_route_net2pcb(a: dict) -> Any:
    from bodesign_eda_bridge import net2pcb_board
    return net2pcb_board(a["netlist_path"], a["out_path"], layers=a.get("layers", 2),
                         plane_layers=a.get("plane_layers"), track_mm=a.get("track_mm"),
                         placement=a.get("placement"), fpdir=a.get("fpdir"),
                         clearance_mm=a.get("clearance_mm", 0.13),
                         connectors=a.get("connectors"))


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
                       stitch_pad_mm=a.get("stitch_pad_mm", 0.6))


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
    return drc_gate(a["board_path"])


def _h_si_check(a: dict) -> Any:
    from bodesign_eda_bridge import si_check
    return si_check(a["board_path"], a["nets"], z0=a.get("z0", 50.0), rs=a.get("rs", 22.0),
                    vdd=a.get("vdd", 1.8), rdrv=a.get("rdrv", 17.0), cload=a.get("cload", 3e-12),
                    edge_ns=a.get("edge_ns", 0.3),
                    overshoot_pass_pct=a.get("overshoot_pass_pct", 10.0),
                    overshoot_warn_pct=a.get("overshoot_warn_pct", 20.0))


def _h_autoroute(a: dict) -> Any:
    from bodesign_eda_bridge import autoroute
    return autoroute(a["board_path"], a["out_path"], passes=a.get("passes", 40))


def _h_render_gerber_preview(a: dict) -> Any:
    from bodesign_gerber_core import render_gerber_preview
    return render_gerber_preview(a["gerber_dir"], a["out_path"], a["mode"],
                                 drill_dir=a.get("drill_dir"), layer_glob=a.get("layer_glob"))


_STR = {"type": "string"}
TOOLS: list[dict] = [
    {"name": "bodesign_impedance_solve", "handler": _h_impedance_solve,
     "description": "Pure-python C04 impedance estimate: solve microstrip class widths and delay constants from explicit stackup and target impedances. Differential targets require gap_mm or width_mm; outputs are guidance only and require fab field-solver confirmation.",
     "schema": {"type": "object", "properties": {"stackup": {"type": "object"}, "targets": {}}, "required": ["stackup", "targets"]}},
    {"name": "bodesign_route_net2pcb", "handler": _h_route_net2pcb,
     "description": "C04 routing: build a netted .kicad_pcb from a KiCad netlist — load+place footprints, assign nets, set copper-layer count / reserved plane layers (LT_POWER, signals stay on outer layers) / default track width, draw the board outline. Connector pin expansion (one symbol pin -> several pads, e.g. USB-C VBUS -> A4/A9/B4/B9) is caller-overridable via `connectors`={refdes:{net:[pads]}} and applies to any USB-C footprint on ANY refdes (not just J1). Returns placed/nets/pads_assigned/unmapped plus applied_pinmaps and unmapped_connectors (a USB-C/declared connector that matched no net name is reported, not silently skipped); unmapped>0 means a footprint's pad names don't match the symbol (floating part).",
     "schema": {"type": "object", "properties": {"netlist_path": _STR, "out_path": _STR, "layers": {"type": "integer"}, "plane_layers": {"type": "array", "items": _STR}, "track_mm": {"type": "number"}, "placement": {"type": "object"}, "fpdir": _STR, "clearance_mm": {"type": "number"}, "connectors": {"type": "object", "description": "{refdes: {net_name: [pad ids]}} explicit connector pin expansion; omit to use the built-in USB-C table for USB-C footprints"}}, "required": ["netlist_path", "out_path"]}},
    {"name": "bodesign_via_in_pad", "handler": _h_via_in_pad,
     "description": "Fine-pitch BGA via-in-pad fanout: drop a through-via through each netted ball pad of the given refs (except the outer keep_rings rings, which escape on the surface) so inner balls reach inner signal layers. via geometry is caller-overridable (drill_mm/pad_mm/keep_rings); defaults (0.2/0.3mm, 2 rings) are a JLCPCB-advanced filled+capped (POFV) process reference — tune for other pad pitches/processes.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_path": _STR, "refs": {"type": "array", "items": _STR}, "drill_mm": {"type": "number"}, "pad_mm": {"type": "number"}, "keep_rings": {"type": "integer"}}, "required": ["in_path", "out_path", "refs"]}},
    {"name": "bodesign_pour_planes", "handler": _h_pour_planes,
     "description": "Pour filled copper plane zones (e.g. ['In1.Cu:GND','In4.Cu:V3V3']) + optional stitching vias, giving high-speed nets a solid impedance reference plane. Stitch net + grid/via geometry are caller-overridable (stitch_net/stitch_pitch_mm/stitch_drill_mm/stitch_pad_mm); defaults (GND, 14mm, 0.3/0.6mm) are a JLCPCB-class process reference, not a hidden assumption.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_path": _STR, "planes": {"type": "array", "items": _STR}, "stitch": {"type": "boolean"}, "stitch_net": _STR, "stitch_pitch_mm": {"type": "number"}, "stitch_drill_mm": {"type": "number"}, "stitch_pad_mm": {"type": "number"}}, "required": ["in_path", "out_path", "planes"]}},
    {"name": "bodesign_widen_bus_tracks", "handler": _h_widen_bus_tracks,
     "description": "Clearance-safe C04 bus finishing: widen selected routed bus tracks to target_mm only where foreign copper/pads keep clearance_mm; writes a new .kicad_pcb and returns widened/kept counts.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_path": _STR, "nets": {"type": "array", "items": _STR}, "target_mm": {"type": "number"}, "clearance_mm": {"type": "number"}}, "required": ["in_path", "out_path", "nets", "target_mm"]}},
    {"name": "bodesign_length_match_bus", "handler": _h_length_match_bus,
     "description": "Clearance-aware C04 bus length matching: add safe serpentine detours to short routed nets when possible; writes a new .kicad_pcb and returns per-net lengths, skew, budget status, tuned count, and explicit untuned statuses.",
     "schema": {"type": "object", "properties": {"in_path": _STR, "out_path": _STR, "nets": {"type": "array", "items": _STR}, "budget_ps": {"type": "number"}, "ps_per_mm": {"type": "number"}, "report_path": _STR, "clearance_mm": {"type": "number"}}, "required": ["in_path", "out_path", "nets", "budget_ps", "ps_per_mm"]}},
    {"name": "bodesign_layout_drc_gate", "handler": _h_layout_drc_gate,
     "description": "Honest DRC gate: copper + unconnected violation counts (hard fail) reported separately from silkscreen overlaps (cosmetic), plus clean=bool.",
     "schema": {"type": "object", "properties": {"board_path": _STR}, "required": ["board_path"]}},
    {"name": "bodesign_si_check", "handler": _h_si_check,
     "description": "ngspice signal-integrity gate: per net builds a series-terminated transmission-line testbench from the routed length; returns overshoot/undershoot and pass/warn/fail with a worst rollup. Driver/load/edge/thresholds (rdrv/cload/edge_ns/overshoot_pass_pct/overshoot_warn_pct) are caller-overridable — defaults are a documented STM32-class CMOS reference, not a hidden assumption; the result echoes the effective values under `effective`.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "nets": {"type": "array", "items": _STR}, "z0": {"type": "number"}, "rs": {"type": "number"}, "vdd": {"type": "number"}, "rdrv": {"type": "number"}, "cload": {"type": "number"}, "edge_ns": {"type": "number"}, "overshoot_pass_pct": {"type": "number"}, "overshoot_warn_pct": {"type": "number"}}, "required": ["board_path", "nets"]}},
    {"name": "bodesign_autoroute", "handler": _h_autoroute,
     "description": "Autoroute a netted board with Freerouting when java+freerouting.jar are present in the worker; otherwise returns routed=false with the netted board for external routing.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "out_path": _STR, "passes": {"type": "integer"}}, "required": ["board_path", "out_path"]}},
    {"name": "bodesign_render_gerber_preview", "handler": _h_render_gerber_preview,
     "description": "C04 Gerber preview evidence: render a real Gerber layer through the gerber-core pygerber raster path. Unsupported composite modes return render-unavailable instead of drawing a decorative fallback.",
     "schema": {"type": "object", "properties": {"gerber_dir": _STR, "out_path": _STR, "mode": _STR, "drill_dir": _STR, "layer_glob": _STR}, "required": ["gerber_dir", "out_path", "mode"]}},
    {"name": "bodesign_mcp_call", "handler": _h_mcp_call,
     "description": "MCP-to-MCP delegation: call a tool on an external MCP server registered by name (via BODESIGN_MCP_SERVERS or BODESIGN_MCP_<NAME>_URL) and return its result. Use to drive docxmcp/drawmiat/other MCP servers through bodesign. Degrades cleanly: an unconfigured server is worker_unavailable, a configured-but-unreachable one is worker_starting (retryable); never fabricates a result.",
     "schema": {"type": "object", "properties": {"server": _STR, "tool": _STR, "arguments": {"type": "object"}},
                "required": ["server", "tool"]}},
    {"name": "bodesign_stage_dir", "handler": _h_stage_dir,
     "description": "Stage an inline file tree {relpath:{content,encoding}} into a token namespace; returns {token, doc_dir, files}. Pass the token to other tools to operate inside that tree (docxmcp-style).",
     "schema": {"type": "object", "properties": {"files": {"type": "object"}}, "required": ["files"]}},
    {"name": "bodesign_ingest_project", "handler": _h_ingest,
     "description": "Ingest a KiCad/EDA project folder read-only; classify files, detect C0* sections, flag non-readable files needing a companion.",
     "schema": {"type": "object", "properties": {"folder": _STR}, "required": ["folder"]}},
    {"name": "bodesign_plan_design_intent", "handler": _h_plan,
     "description": "Plan a DesignIntent from a natural-language spec (+ optional answers): requirements, clarifying questions, subsystems.",
     "schema": {"type": "object", "properties": {"spec": _STR, "answers": {"type": "object"}}, "required": ["spec"]}},
    {"name": "bodesign_evidence_manifest", "handler": _h_evidence,
     "description": "Build a design-evidence sourcing manifest for the spec's parts (local-corpus-first; distributor pointers otherwise).",
     "schema": {"type": "object", "properties": {"spec": _STR, "parts": {"type": "array", "items": _STR}, "corpus_dir": _STR}}},
    {"name": "bodesign_emit_symbol", "handler": _h_emit_symbol,
     "description": "Generate a KiCad .kicad_sym symbol from a pin list [{number,name,type}].",
     "schema": {"type": "object", "properties": {"symbol_name": _STR, "pins": {"type": "array"}, "output_path": _STR,
                "footprint_filter": _STR, "datasheet": _STR}, "required": ["symbol_name", "pins", "output_path"]}},
    {"name": "bodesign_compose_schematic", "handler": _h_compose,
     "description": "Compose a schematic from a design spec (components + REF.PIN nets); auto-place + emit + kicad-cli validate.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "project_name": _STR, "spec": {"type": "object"},
                "symbol_dirs": {}, "validate": {"type": "boolean"}}, "required": ["out_dir", "project_name", "spec"]}},
    {"name": "bodesign_pin_allocation", "handler": _h_pin_alloc,
     "description": "Build a pin/GPIO allocation table (C03->FW interface) from a net list; returns CSV.",
     "schema": {"type": "object", "properties": {"nets": {"type": "array"}, "mcu_refs": {"type": "array", "items": _STR}}, "required": ["nets"]}},
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
    {"name": "bodesign_render_companion", "handler": _h_companion,
     "description": "Render a readable companion (pdf/png) for a non-readable engineering file (.kicad_sch/.kicad_pcb/gerber).",
     "schema": {"type": "object", "properties": {"path": _STR, "out_dir": _STR}, "required": ["path", "out_dir"]}},
    {"name": "bodesign_emit_doc", "handler": _h_doc,
     "description": "Render a markdown deliverable to shareable docx + pdf.",
     "schema": {"type": "object", "properties": {"md_path": _STR, "out_dir": _STR, "formats": {"type": "array", "items": _STR}}, "required": ["md_path", "out_dir"]}},
    {"name": "bodesign_package_readiness", "handler": _h_readiness,
     "description": "Assess a product folder against the POC deliverable checklist; per-deliverable status + next step (the compass).",
     "schema": {"type": "object", "properties": {"folder": _STR, "milestone": _STR}, "required": ["folder"]}},
    {"name": "bodesign_c00_scaffold_prd", "handler": _h_c00_scaffold_prd,
     "description": "Scaffold a blank C00 PRD source package from the committed template: Project_Requirements.md, answer_state.json, and optional RF_Requirements.md. Initializes every required field as missing and does not compute readiness or emit final PRD prose.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "project_name": _STR, "include_rf": {"type": "boolean"}}, "required": ["out_dir"]}},
    {"name": "bodesign_c00_readiness", "handler": _h_c00_readiness,
     "description": "Assess C00 PRD answer_state.json against the committed rubric. Computes field/section/gate readiness and next question; does not emit PRD prose or mark human approval.",
     "schema": {"type": "object", "properties": {"folder": _STR}, "required": ["folder"]}},
    {"name": "bodesign_c00_emit_prd", "handler": _h_c00_emit_prd,
     "description": "Render Markdown-first C00 PRD outputs from answer_state.json: generated Project/RF requirements and C00_Handoff_Report. Preserves missing/drafted/external-needed/blocked/accepted-risk markers and never marks human approval.",
     "schema": {"type": "object", "properties": {"folder": _STR}, "required": ["folder"]}},
    {"name": "bodesign_c00_update_answers", "handler": _h_c00_update_answers,
     "description": "Record user/consultant answers into the C00 PRD answer-state, recompute readiness, and regenerate the PRD Markdown. `answers` maps a field key (or qualified `section_id.field`) to a value, or to {value, state} where state ∈ missing/drafted/answered/external-needed/blocked/accepted-risk. Unknown keys → not_found; an unqualified key in multiple sections → ambiguous (not guessed). Never marks human approval. This is how C00 field answers get recorded (the consultant's intake), without hand-editing answer_state.json.",
     "schema": {"type": "object", "properties": {"folder": _STR, "answers": {"type": "object"}, "regenerate": {"type": "boolean"}},
                "required": ["folder", "answers"]}},
    {"name": "bodesign_c01_emit_package", "handler": _h_c01_emit,
     "description": "Emit a Rockbox-like C01 ID package: Ai file/Design_Direction.md, CMF/CMF_Direction.md, Display UIUX/UIUX_Requirements.md, Interface_Constraints.json, and ID handoff, with draft/decision markers.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "c00": {}, "answers": {"type": "object"}}, "required": ["out_dir"]}},
    {"name": "bodesign_c01_readiness", "handler": _h_c01_readiness,
     "description": "Check whether the Rockbox-like C01 package has non-empty scripts for Ai file, CMF, Display UI/UX, constraints JSON, and ID handoff.",
     "schema": {"type": "object", "properties": {"folder": _STR}, "required": ["folder"]}},
    {"name": "bodesign_c01_next_question", "handler": _h_c01_next_question,
     "description": "Return the next C01 industrial-design preference question from C01-ID/answer_state.json. If no state exists, returns the first bootstrap question without writing files.",
     "schema": {"type": "object", "properties": {"folder": _STR}, "required": ["folder"]}},
    {"name": "bodesign_c01_update_answers", "handler": _h_c01_update_answers,
     "description": "Update C01-ID/answer_state.json with user/design preferences, then regenerate the Rockbox-like C01 package and return the next question. Does not mark ID approval or create final .ai/Figma/CAD artifacts.",
     "schema": {"type": "object", "properties": {"folder": _STR, "answers": {"type": "object"}, "c00": {}}, "required": ["folder", "answers"]}},
    {"name": "bodesign_c01_emit_concept_prompts", "handler": _h_c01_emit_concept_prompts,
     "description": "Persist reference-only C01 concept/moodboard/UI prompt artifacts (Concept_Image_Prompts.md, Moodboard_Prompts.md, UI_Concept_Prompts.md) derived from accumulated C00/C01 intent. Generalized design language; not final art and not a copy of any product/brand.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "c00": {}, "answers": {"type": "object"}}, "required": ["out_dir"]}},
    {"name": "bodesign_c01_add_reference_image", "handler": _h_c01_add_reference_image,
     "description": "Record a reference-image cue (form/cmf/ui/component/mood) into C01-ID/reference_cues.json: source image path, observed cue (generalized — what to borrow/avoid), target artifact, notes. The cue stays `reference-derived` until the user confirms it; never auto-promoted to an approved preference, never a copy of the source.",
     "schema": {"type": "object", "properties": {"folder": _STR, "source_image": _STR, "cue_type": _STR,
                "observed_cue": _STR, "target_artifact": _STR, "notes": _STR},
                "required": ["folder", "source_image", "cue_type", "observed_cue"]}},
    {"name": "bodesign_c01_confirm_reference_cue", "handler": _h_c01_confirm_reference_cue,
     "description": "Explicitly confirm or reject a C01 reference cue by cue_id. Only the user may move a cue out of `reference-derived`; confirmed cues remain generalized design intent (copyright-safe).",
     "schema": {"type": "object", "properties": {"folder": _STR, "cue_id": _STR, "confirmation": _STR, "note": _STR},
                "required": ["folder", "cue_id", "confirmation"]}},
    {"name": "bodesign_c01_generate_concept_image", "handler": _h_c01_generate_concept_image,
     "description": "Optional C01 add-on: generate a reference-only concept image via Google AI Studio from a C01 concept prompt. Credential source is server-side only: BODESIGN_GOOGLE_API_KEY/GEMINI_API_KEY/GOOGLE_API_KEY env first, then active API account from opencode accounts.json (default family gemini-cli). Does not affect C01 readiness.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "prompt": _STR, "model": _STR}, "required": ["out_dir", "prompt"]}},
    {"name": "bodesign_c02_readiness", "handler": _h_c02_readiness,
     "description": "Assess C02 mechanical/enclosure constraint readiness before CAD generation. Reports missing board outline, heights, holes, connector openings, heat, RF, battery, and environment targets without guessing dimensions.",
     "schema": {"type": "object", "properties": {"folder": _STR, "constraints": {"type": "object"}}}},
    {"name": "bodesign_c02_emit_enclosure_package", "handler": _h_c02_emit,
     "description": "Emit a C02-ME mechanical enclosure support package without generating CAD/STL/SKP/STEP or ME approval. Missing geometry is preserved as engineering_pending with owner/reason.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "constraints": {"type": "object"}, "project_summary": {}, "prototype_intent": _STR, "printer_profile": {}}, "required": ["out_dir"]}},
    {"name": "bodesign_c02_generate_openscad", "handler": _h_c02_generate_openscad,
     "description": "Generate C02-ME/Enclosure.scad prototype source from explicit board outline, component height constraints, wall thickness, clearance, and lid clearance. Missing dimensions return source_blocked; does not export STL/SKP/STEP or imply ME approval.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "constraints": {"type": "object"}, "wall_thickness_mm": {"type": "number"}, "clearance_mm": {"type": "number"}, "lid_clearance_mm": {"type": "number"}}, "required": ["out_dir"]}},
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
    {"name": "bodesign_c03_export_mechanical_constraints", "handler": _h_c03_export_mech_constraints,
     "description": "Export C03 circuit/spec data that affects C02/C04 mechanical work: component heights, external connectors/openings, heat sources, antenna/RF keepouts, battery envelope, and ESD/EMC notes. Does not infer board outline or placement coordinates.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "circuit": {"type": "object"}}, "required": ["out_dir"]}},
    {"name": "bodesign_datasheet_lookup", "handler": _h_datasheet_lookup,
     "description": "Look up a part (by MPN) in the project datasheet vault. RCA anti-hallucination guard: call this BEFORE stating an electrical spec for a part. Returns the stored specs with provenance (verified=cited source vs unverified=model memory), or status 'absent' (acquire the datasheet first — do NOT state the value from memory as if confirmed). Lazy: the vault holds only parts someone has investigated. Pass vault_root = the project's datasheets dir (e.g. <project>/datasheets); the vault is project-scoped, not a global library.",
     "schema": {"type": "object", "properties": {"mpn": _STR, "fields": {"type": "array", "items": _STR}, "vault_root": _STR}, "required": ["mpn"]}},
    {"name": "bodesign_datasheet_register", "handler": _h_datasheet_register,
     "description": "Register/update a part in the project datasheet vault: copies a datasheet PDF (pdf_path) into <vault>/<mpn>/ and/or records a cited source_url, vendor, aliases, and specs. specs is {field: value} (bare value = recorded UNVERIFIED) or {field: {value, unit, source, confidence}} (with a real source = VERIFIED). Use at RCA time to capture a part's real spec from its datasheet so future claims are grounded, not guessed. Pass vault_root = <project>/datasheets so the part stays with the project it documents.",
     "schema": {"type": "object", "properties": {"mpn": _STR, "vendor": _STR, "source_url": _STR, "pdf_path": _STR, "specs": {"type": "object"}, "aliases": {"type": "array", "items": _STR}, "description": _STR, "note": _STR, "vault_root": _STR}, "required": ["mpn"]}},
    {"name": "bodesign_spec_check", "handler": _h_spec_check,
     "description": "Check whether a specific spec field of a part is backed by the project datasheet vault (verified | unverified | no-field | absent), optionally comparing a claimed_value to the stored one. The RCA discipline gate: if 'absent'/'unverified', acquire/cite the datasheet before relying on the value. Pass vault_root = <project>/datasheets.",
     "schema": {"type": "object", "properties": {"mpn": _STR, "field": _STR, "claimed_value": {}, "vault_root": _STR}, "required": ["mpn", "field"]}},
    {"name": "bodesign_rca_spec_audit", "handler": _h_rca_spec_audit,
     "description": "Gate a whole RCA before publishing: pass the list of spec values the analysis asserts (claims=[{mpn, field, asserted_value}]) and get back which are datasheet-grounded and which are BLOCKING — absent (part not in vault), unverified (no source = model memory), or contradicting the datasheet. Returns publishable=false if any blocker. Run this before stating spec-dependent conclusions so RCA rides on real datasheets, not guesses. Pass vault_root = <project>/datasheets.",
     "schema": {"type": "object", "properties": {"claims": {"type": "array", "items": {"type": "object"}}, "vault_root": _STR}, "required": ["claims"]}},
    {"name": "bodesign_c04_emit_layout_package", "handler": _h_c04_emit_layout_package,
     "description": "Assemble the C04 layout constraint package (Layout_Constraints.json + Placement_Constraints.md) from C01 interface constraints + C03 mechanical constraints. Constraint-first for the layout engineer; board outline, mounting holes, placement coordinates, and stackup stay open and are never fabricated. Auto-loads C01/C03 exports from the folder if not passed.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "c01": {"type": "object"}, "c03": {"type": "object"}}, "required": ["out_dir"]}},
    {"name": "bodesign_c04_readiness", "handler": _h_c04_readiness,
     "description": "Report C04 layout-constraint readiness: which upstream constraint groups are present and what remains layout-owned (board outline, mounting, placement, stackup). Never claims board/Gerber/layout approval.",
     "schema": {"type": "object", "properties": {"folder": _STR}, "required": ["folder"]}},
    {"name": "bodesign_c05_scaffold_fw_spec", "handler": _h_c05_scaffold_fw_spec,
     "description": "Scaffold the C05 firmware software-development spec sub-package (Functional_Spec / Module_Architecture / State_Machine / Task_Breakdown + Pin_Map_Bridge.json) from PRD §7 software intent and the C03 pin map. bodesign owns the SPEC; the FW team owns the firmware code. No firmware code is generated; absent inputs stay pending, never fabricated.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "software": {"type": "object"}, "pin_map": {}}, "required": ["out_dir"]}},
    {"name": "bodesign_c05_readiness", "handler": _h_c05_readiness,
     "description": "Report C05 FW SW-spec readiness: which spec sections exist, whether PRD §7 functions and the C03 pin map are bridged, and what is pending. Never claims firmware code or completion.",
     "schema": {"type": "object", "properties": {"folder": _STR}, "required": ["folder"]}},
    {"name": "bodesign_c06_assemble_test_plan", "handler": _h_c06_assemble_test_plan,
     "description": "Assemble the C06 verification package (Verification_Summary.json + Test_Plan.md + Bring_Up_Checklist.md) from the verify-tool verdicts {simulate, emc, thermal, crosscheck}. Checks with no verdict are recorded `not-run`; no pass is fabricated. EVT/DVT and certification stay external-lab gates and are never marked certified.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "verdicts": {"type": "object"}, "certification_targets": {"type": "array"}}, "required": ["out_dir"]}},
    {"name": "bodesign_c06_readiness", "handler": _h_c06_readiness,
     "description": "Report C06 verification readiness: per-check status, how many verify tools have produced verdicts, which are not-run, and whether any failed. Never claims certified/EVT-DVT-passed.",
     "schema": {"type": "object", "properties": {"folder": _STR}, "required": ["folder"]}},
    {"name": "bodesign_reference_crosscheck", "handler": _h_crosscheck,
     "description": "Cross-check a generated net set vs a reference product's nets (control group): matched/missing/extra + coverage.",
     "schema": {"type": "object", "properties": {"generated_nets": {"type": "array", "items": _STR},
                "reference_nets": {"type": "array", "items": _STR}, "label": _STR, "provenance": {"type": "object"}},
                "required": ["generated_nets", "reference_nets"]}},

    # ── Orchestration spine ──────────────────────────────────────────
    {"name": "bodesign_agent_registry", "handler": _h_agent_registry,
     "description": "Return the C00–C06 agent registry (derived from the document architecture): each layer's role, target_role, owning team, skills, human approval gate, and allowed/forbidden actions. C00 is the requirement-contract owner; C01–C06 are downstream workers.",
     "schema": {"type": "object", "properties": {}}},
    {"name": "bodesign_dispatch_work_packet", "handler": _h_dispatch_work_packet,
     "description": "C00 dispatches a scoped work packet (bodesign.c00.work_packet.v1) to a downstream layer (C01–C06). The packet inherits the target layer's authority from the registry; it cannot target C00 itself. Persists under <folder>/_orchestration/work_packets/.",
     "schema": {"type": "object", "properties": {"folder": _STR, "target_layer": _STR, "objective": _STR,
                "sections": {"type": "array", "items": _STR}, "fields": {"type": "array", "items": _STR},
                "generated_docs": {"type": "array", "items": _STR}, "inputs": {"type": "object"},
                "expected_outputs": {"type": "array", "items": _STR}},
                "required": ["folder", "target_layer", "objective"]}},
    {"name": "bodesign_list_work_packets", "handler": _h_list_work_packets,
     "description": "List all C00 work packets dispatched in a project folder, with their target layer and status (ready/partial/blocked).",
     "schema": {"type": "object", "properties": {"folder": _STR}, "required": ["folder"]}},
    {"name": "bodesign_return_blocker", "handler": _h_return_blocker,
     "description": "A downstream layer returns a blocker (bodesign.c00.blocker_return.v1) against its work packet to C00. The source layer is taken from the packet; this marks the packet blocked. severity ∈ {decision, external-needed, blocked, accepted-risk-request}.",
     "schema": {"type": "object", "properties": {"folder": _STR, "packet_id": _STR, "severity": _STR,
                "summary": _STR, "question_for_user": _STR, "affected_c00_fields": {"type": "array", "items": _STR},
                "affected_downstream_layers": {"type": "array", "items": _STR}, "options": {"type": "array"},
                "recommended_owner": _STR, "proposed_state": _STR, "evidence": {"type": "object"}},
                "required": ["folder", "packet_id", "severity", "summary", "question_for_user"]}},
    {"name": "bodesign_list_blockers", "handler": _h_list_blockers,
     "description": "List blockers returned to C00 in a project folder; set unresolved_only=true for the open ones C00 still owes the user a decision on.",
     "schema": {"type": "object", "properties": {"folder": _STR, "unresolved_only": {"type": "boolean"}}, "required": ["folder"]}},
    {"name": "bodesign_ingest_blocker", "handler": _h_ingest_blocker,
     "description": "C00 records the human/owner resolution of a blocker and closes it. Does NOT silently mutate the PRD — it records the decision and the C00 field-state to apply via the C00 update/emit step. Requires a non-empty decision (no auto-resolution).",
     "schema": {"type": "object", "properties": {"folder": _STR, "blocker_id": _STR, "resolved_state": _STR,
                "decision": _STR, "decided_by": _STR}, "required": ["folder", "blocker_id", "resolved_state", "decision"]}},
    {"name": "bodesign_enter_c01_mode", "handler": _h_enter_c01_mode,
     "description": "C00 → C01 mode contract (C01-I3): dispatch a C01 work packet scoped to the PRD sections that hand off to C01, emit the Rockbox-like C01 package, and return the next C01 preference question. C01 may ask preference questions directly; product-level decisions return to C00 as blockers. C01 does not mutate the PRD or claim ID approval.",
     "schema": {"type": "object", "properties": {"folder": _STR, "c00": {}, "answers": {"type": "object"}, "objective": _STR},
                "required": ["folder"]}},
    {"name": "bodesign_c00_orchestration_status", "handler": _h_c00_orchestration_status,
     "description": "Read-only orchestration board: per-layer (C01–C06) gate status (ready/partial/blocked), whether it has been dispatched + packet status, open blockers, plus the C00 PRD overall status and next question. Mutates nothing.",
     "schema": {"type": "object", "properties": {"folder": _STR}, "required": ["folder"]}},
    {"name": "bodesign_c00_orchestration_tick", "handler": _h_c00_orchestration_tick,
     "description": "Advance the C00-driven loop one step: returns the single highest-value next action (scaffold_c00 / resolve_blocker / ask_c00 / dispatch / waiting / done) over the spine. May auto-dispatch a ready, undispatched layer (set auto_dispatch=false for a recommendation-only dry run). Never auto-answers a PRD field, resolves a blocker, or marks approval — those return to the user.",
     "schema": {"type": "object", "properties": {"folder": _STR, "auto_dispatch": {"type": "boolean"}}, "required": ["folder"]}},
]
TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}

# ── Toolchain worker grouping/routing (Batch E) ────────────────────────
# Tools are grouped by C0x responsibility / toolchain so heavy deps can live in
# dedicated worker containers (see plans/.../toolchain_workers.md). The default
# served group is "all" (monolith — every tool runs in-process, zero behaviour
# change). A worker runs e.g. `--tools me`; the core runs `--tools core` and
# forwards a non-local tool to its worker URL, or reports it unavailable.
_ME_GROUP_TOOLS = {
    "bodesign_c02_generate_openscad",
    "bodesign_c02_export_stl",
    "bodesign_c02_export_skp",
    "bodesign_c02_export_step",
    "bodesign_render_board_model",
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
    "bodesign_export_bom",
    "bodesign_export_netlist",
    "bodesign_render_companion",
    # C04 routing / layout-finishing (pcbnew + ngspice; autoroute needs freerouting in the worker)
    "bodesign_route_net2pcb",
    "bodesign_via_in_pad",
    "bodesign_pour_planes",
    "bodesign_widen_bus_tracks",
    "bodesign_length_match_bus",
    "bodesign_layout_drc_gate",
    "bodesign_si_check",
    "bodesign_autoroute",
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
PATH_ARG_KEYS = ("folder", "out_dir", "path", "md_path", "board_path", "in_path", "out_path", "output_path", "report_path", "corpus_dir", "schematic_path", "pcb_path", "gerber_dir", "drill_dir")


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
    ("1. Ingest", "Upload your project tree (tarball→token) or point at a folder; <code>bodesign_ingest_project</code> classifies files + flags non-readable ones.",
     "1. 匯入", "上傳專案樹（tarball→token）或指定資料夾；<code>bodesign_ingest_project</code> 分類檔案並標記不可讀者。"),
    ("2. Plan", "<code>bodesign_plan_design_intent</code> turns a natural-language spec into requirements, clarifying questions, and subsystems.",
     "2. 規劃", "<code>bodesign_plan_design_intent</code> 把自然語言規格轉成需求、釐清問題與子系統。"),
    ("3. Source evidence", "<code>bodesign_evidence_manifest</code> grounds each part in a reference (local corpus first), so design = faithful reuse of known-good boards.",
     "3. 蒐集證據", "<code>bodesign_evidence_manifest</code> 將每個零件對應到參考設計（本地語料優先），使設計＝忠實重用良品。"),
    ("4. Symbols", "<code>bodesign_emit_symbol</code> turns a datasheet pinout into a KiCad symbol (harvest via the datasheets skill).",
     "4. 符號", "<code>bodesign_emit_symbol</code> 把 datasheet 腳位轉成 KiCad 符號（透過 datasheets skill 採集）。"),
    ("5. Compose + ERC", "<code>bodesign_compose_schematic</code> auto-places components + nets → a kicad-cli-validated schematic (0 ERC).",
     "5. 組成＋ERC", "<code>bodesign_compose_schematic</code> 自動佈點＋接線 → 經 kicad-cli 驗證的原理圖（0 ERC）。"),
    ("6. BOM + pins", "<code>bodesign_export_bom</code> (grouped, MPN) + <code>bodesign_pin_allocation</code> (the C03↔firmware interface).",
     "6. BOM＋腳位", "<code>bodesign_export_bom</code>（分組、MPN）＋ <code>bodesign_pin_allocation</code>（C03↔韌體介面）。"),
    ("7. Layout", "<code>bodesign_emit_layout</code> places footprints via pcbnew + DRC + an SVG companion (a starting board to route).",
     "7. 佈局", "<code>bodesign_emit_layout</code> 以 pcbnew 擺放 footprint＋DRC＋SVG 伴隨檔（待繞線的起手板）。"),
    ("8. Fab", "<code>bodesign_emit_fab</code> exports gerbers/drill/pos/STEP/PDF for the factory.",
     "8. 製造", "<code>bodesign_emit_fab</code> 匯出 gerber／鑽孔／pos／STEP／PDF 給工廠。"),
    ("9. Verify", "Four layers: ERC/DRC · <code>reference_crosscheck</code> vs a control group · <code>simulate</code> (SPICE) · <code>analyze_emc</code>/<code>analyze_thermal</code>.",
     "9. 驗證", "四層：ERC/DRC・對照組 <code>reference_crosscheck</code>・SPICE <code>simulate</code>・<code>analyze_emc</code>／<code>analyze_thermal</code>。"),
    ("10. Track", "<code>bodesign_package_readiness</code> recomputes the compass + next step until the package is factory-submittable.",
     "10. 追蹤", "<code>bodesign_package_readiness</code> 重算羅盤與下一步，直到文件包可送廠。"),
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
    "skills_intro": ("bodesign generates; mature skills verify/source/document. These run agent-side (or on the server host via <code>BODESIGN_*_SKILL</code> / <code>~/.claude/skills</code>); install the ones you need:",
                     "bodesign 負責生成；成熟 skills 負責驗證／採購／文件。它們在 agent 端執行（或在 server 主機，透過 <code>BODESIGN_*_SKILL</code> / <code>~/.claude/skills</code>）；按需安裝："),
    "skills_dl": ("Download skill packages", "下載 skill 套件"),
    "skills_dl_bundle": ("Full EDA skill bundle", "完整 EDA skill 套件包"),
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
    """(filename, label, human_size) for vendored skill tarballs; bundle first."""
    d = _assets_dir() / "skills"
    if not d.is_dir():
        return []
    files = sorted(d.glob("*.tar.gz"), key=lambda p: (not p.name.startswith("bodesign-eda"), p.name))
    out = []
    for p in files:
        label = "bundle" if p.name.startswith("bodesign-eda") else p.name[:-len(".tar.gz")]
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
        bundle = next((d for d in dl if d[1] == "bundle"), None)
        per = [d for d in dl if d[1] != "bundle"]
        links = " · ".join(f'<a href="{b}/skills/{esc(fn)}">{esc(lb)}</a> <span style="color:var(--muted)">({sz})</span>'
                           for fn, lb, sz in per)
        bundle_link = (f'<a href="{b}/skills/{esc(bundle[0])}" style="color:var(--accent);font-weight:700">⬇ {L("skills_dl_bundle")}</a> '
                       f'<span style="color:var(--muted)">({bundle[2]})</span> · <a href="{b}/skills/MANIFEST.md">MANIFEST</a>' if bundle else "")
        dl_html = f'<p style="margin-top:10px"><b>{L("skills_dl")}:</b> {bundle_link}</p><p style="font-size:.9rem">{links}</p>'
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
        return [Tool(name=t["name"], description=t["description"], inputSchema=t["schema"]) for t in TOOLS]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list:
        result = await asyncio.to_thread(run_tool, name, arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

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

    async def healthz(request: Request) -> Response:
        return JSONResponse({"status": "ok", "service": SERVER_NAME, "tools": len(TOOLS),
                             "served_groups": sorted(SERVED_GROUPS)})

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

    app = Starlette(routes=[
        Route("/", landing),
        Route("/tools", tools_index),
        Route("/tools/{name}", tool_detail),
        Route("/idef0.svg", idef0_svg),
        Route("/skills/{name}", skill_download),
        Route("/healthz", healthz),
        Route("/invoke", invoke, methods=["POST"]),
        Route("/files", upload_file, methods=["POST"]),
        Route("/files/{token}/blob/{rel:path}", get_blob),
        Mount("/mcp", app=handle_mcp),
    ])

    # Serve UDS (local) and/or TCP (external) concurrently from one process,
    # sharing a single session manager + app. session_manager.run() is entered
    # once and held open while both uvicorn binds serve.
    binds = []
    if uds:
        binds.append(uvicorn.Server(uvicorn.Config(app, uds=uds)).serve())
    if port is not None:
        binds.append(uvicorn.Server(uvicorn.Config(app, host=host, port=port)).serve())
    if not binds:
        raise ValueError("run_http needs at least one of --uds / --port")
    async with session_manager.run():
        await asyncio.gather(*binds)


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
