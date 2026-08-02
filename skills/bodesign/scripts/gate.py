#!/usr/bin/env python3
"""bodesign landing-plane verb runner (R13.2/R13.6).

Runs the ~50 deterministic Bucket-2 verbs directly on the host, writing into
the caller's repo under the agent's own uid — zero token round-trip, zero
container dependency. Heavy/compute verbs are hard-refused with a typed
``VERB_NOT_LANDING`` pointing at the container MCP tool.

Usage:
    python3 gate.py <verb> --repo /abs/project [--json '{...}' | --arg k=v ...]
    python3 gate.py --list

Contract (plans/mcp_r13-landing-webdav-cache):
  * stdout = exactly one JSON envelope {ok, verb, result | error:{code,message,hint?}}
  * exit code != 0 iff ok=false
  * logs go to stderr only (landing_verb_start / landing_verb_ok / landing_verb_error)
  * NO fallback to the container — ever (repo 天條 2)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

MIN_PYTHON = (3, 10)

# ── typed error codes (errors.md, BINDING) ─────────────────────────────
LANDING_PYTHON_TOO_OLD = "LANDING_PYTHON_TOO_OLD"
LANDING_PACKAGES_NOT_FOUND = "LANDING_PACKAGES_NOT_FOUND"
VERB_UNKNOWN = "VERB_UNKNOWN"
VERB_NOT_LANDING = "VERB_NOT_LANDING"
VERB_ARGS_INVALID = "VERB_ARGS_INVALID"
VERB_RUNTIME_ERROR = "VERB_RUNTIME_ERROR"


class LandingError(Exception):
    def __init__(self, code, message, hint=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


def _log(line):
    print(line, file=sys.stderr)


def _emit(envelope):
    """Print the single stdout JSON envelope; return the process exit code."""
    print(json.dumps(envelope, ensure_ascii=False))
    return 0 if envelope.get("ok") else 1


def _fail(verb, code, message, hint=None):
    _log(f"landing_verb_error verb={verb or '-'} code={code}")
    err = {"code": code, "message": message}
    if hint:
        err["hint"] = hint
    return _emit({"ok": False, "verb": verb or "", "error": err})


def _check_python():
    if sys.version_info[:2] < MIN_PYTHON:
        raise LandingError(
            LANDING_PYTHON_TOO_OLD,
            "landing verbs require python >= %d.%d (found %d.%d); install a newer "
            "python3 or run the container MCP tools instead"
            % (MIN_PYTHON + tuple(sys.version_info[:2])),
        )


def _resolve_src():
    """Resolve the bodesign source root (a dir containing packages/workflow-core).

    Order: explicit $BODESIGN_SRC, else walk up from gate.py's location (the
    skill-shipped-in-tree case). Failure is typed — never a container fallback.
    """
    tried = []
    env = os.environ.get("BODESIGN_SRC")
    if env:
        cand = os.path.realpath(env)
        tried.append(cand)
        if os.path.isdir(os.path.join(cand, "packages", "workflow-core")):
            return cand
    else:
        here = os.path.dirname(os.path.realpath(__file__))
        cur = here
        while True:
            tried.append(cur)
            if os.path.isdir(os.path.join(cur, "packages", "workflow-core")):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    raise LandingError(
        LANDING_PACKAGES_NOT_FOUND,
        "could not find bodesign packages/ (looked for packages/workflow-core); "
        "tried: " + ", ".join(tried) + ". Set BODESIGN_SRC=/path/to/bodesign repo.",
        hint="export BODESIGN_SRC=<bodesign repo root containing packages/*>",
    )


def _prepend_packages(src_root):
    pkg_root = os.path.join(src_root, "packages")
    dirs = sorted(
        os.path.join(pkg_root, d)
        for d in os.listdir(pkg_root)
        if os.path.isdir(os.path.join(pkg_root, d))
    )
    for d in reversed(dirs):
        if d not in sys.path:
            sys.path.insert(0, d)


# ── Heavy / container-only verbs: hard-guard blacklist (DD-2, R13.6) ───
# verb → the bodesign_* container MCP tool to call instead.
NOT_LANDING = {
    "emit_symbol": "bodesign_emit_symbol",
    "compose_schematic": "bodesign_compose_schematic",
    "emit_layout": "bodesign_emit_layout",
    "emit_fab": "bodesign_emit_fab",
    "simulate": "bodesign_simulate",
    "si_check": "bodesign_si_check",
    "analyze_emc": "bodesign_analyze_emc",
    "analyze_thermal": "bodesign_analyze_thermal",
    "analyzer_selfcheck": "bodesign_analyzer_selfcheck",
    "export_bom": "bodesign_export_bom",
    "export_netlist": "bodesign_export_netlist",
    "render_companion": "bodesign_render_companion",
    "emit_doc": "bodesign_emit_doc",
    "route_net2pcb": "bodesign_route_net2pcb",
    "via_in_pad": "bodesign_via_in_pad",
    "pour_planes": "bodesign_pour_planes",
    "widen_bus_tracks": "bodesign_widen_bus_tracks",
    "length_match_bus": "bodesign_length_match_bus",
    "layout_drc_gate": "bodesign_layout_drc_gate",
    "autoroute": "bodesign_autoroute",
    "render_gerber_preview": "bodesign_render_gerber_preview",
    "dxf_to_dwg": "bodesign_dxf_to_dwg",
    "dwg_to_dxf": "bodesign_dwg_to_dxf",
    "c02_export_stl": "bodesign_c02_export_stl",
    "c02_export_skp": "bodesign_c02_export_skp",
    "c02_export_step": "bodesign_c02_export_step",
    "c02_render_enclosure": "bodesign_c02_render_enclosure",
    "c02_voice_to_design": "bodesign_c02_voice_to_design",
    "c02_project_svg": "bodesign_c02_project_svg",
    "render_board_model": "bodesign_render_board_model",
    "spice_model_card": "bodesign_spice_model_card",
    "stage_dir": "bodesign_stage_dir",
    "mcp_call": "bodesign_mcp_call",
    "vault_ingest": "bodesign_vault_ingest",
    "vault_query": "bodesign_vault_query",
    "vault_spec_check": "bodesign_vault_spec_check",
    "vault_queue": "bodesign_vault_queue",
    "vault_diagnostics": "bodesign_vault_diagnostics",
    "c01_generate_concept_image": "bodesign_c01_generate_concept_image",
}

# ── Verb registry (DD-2): verb → (module, callable, required_args, summary) ──
# 1:1 with the Bucket-2 _h_* handlers in services/mcp/server.py.
_WC = "bodesign_workflow_core"
_RC = "bodesign_reverse_core"
_CK = "bodesign_component_kb"
_EB = "bodesign_eda_bridge"

VERBS = {
    # C00 PRD family
    "c00_scaffold_prd": (_WC, "scaffold_c00_prd_package", ("out_dir",),
                         "Scaffold a blank C00 PRD source package from the committed template."),
    "c00_readiness": (_WC, "assess_c00_prd_readiness", ("folder",),
                      "Assess C00 PRD answer_state against the rubric; next question included."),
    "c00_emit_prd": (_WC, "emit_c00_prd_markdown", ("folder",),
                     "Render Markdown-first C00 PRD outputs from answer_state.json."),
    "c00_update_answers": (_WC, "c00_update_answers", ("folder", "answers"),
                           "Record answers into the C00 answer-state, recompute readiness, regenerate PRD."),
    "c00_emit_prd_docx": (_WC, "render_c00_prd_docx_package", ("folder",),
                          "Render the C00 PRD docxmcp-assemblable package(s) (render-only; assemble=容器 tool)."),
    # C01 family (10)
    "c01_emit_package": (_WC, "emit_c01_rockbox_package", ("out_dir",),
                         "Emit the Rockbox-like C01 ID package with draft/decision markers."),
    "c01_readiness": (_WC, "assess_c01_package_readiness", ("folder",),
                      "Check the C01 package has non-empty scripts for each deliverable."),
    "c01_next_question": (_WC, "c01_next_question", ("folder",),
                          "Return the next C01 industrial-design preference question."),
    "c01_update_answers": (_WC, "c01_update_answers", ("folder", "answers"),
                           "Update C01 answer_state, regenerate the package, return the next question."),
    "c01_emit_concept_prompts": (_WC, "emit_c01_concept_prompts", ("out_dir",),
                                 "Persist reference-only C01 concept/moodboard/UI prompt artifacts."),
    "c01_add_reference_image": (_WC, "c01_add_reference_image",
                                ("folder", "source_image", "cue_type", "observed_cue"),
                                "Record a reference-image cue into C01-ID/reference_cues.json."),
    "c01_confirm_reference_cue": (_WC, "c01_confirm_reference_cue",
                                  ("folder", "cue_id", "confirmation"),
                                  "Explicitly confirm or reject a C01 reference cue by cue_id."),
    "c01_emit_id_visual_package": (_WC, "emit_c01_id_visual_package", ("folder",),
                                   "Emit the C01 ID-native Ai-file bucket (layered SVG + figma spec)."),
    "c01_emit_cmf_package": (_WC, "emit_c01_cmf_package", ("folder",),
                             "Emit the C01 CMF draft bucket (cmf_tokens.json + direction doc)."),
    "c01_emit_uiux_package": (_WC, "emit_c01_uiux_package", ("folder",),
                              "Emit the C01 Display UI/UX draft bucket (wireframes + flow doc)."),
    # C02 analysis-only (4)
    # `folder` is REQUIRED, not optional: REPO_DEFAULT_KEYS only seeds a key the
    # verb declares required, so an empty tuple meant `gate.py c02_readiness
    # --repo <A>` silently passed folder=None. _load_constraints(None) then
    # returned {} and every constraint read as missing -- byte-identical to a
    # package that genuinely has none (BR_20260719 c02).
    "c02_readiness": (_WC, "assess_c02_constraint_readiness", ("folder",),
                      "Assess C02 mechanical/enclosure constraint readiness (no CAD)."),
    "c02_emit_enclosure_package": (_WC, "emit_c02_enclosure_package", ("out_dir",),
                                   "Emit the C02-ME enclosure support package (no CAD/STL/STEP)."),
    "c02_generate_openscad": (_WC, "generate_c02_openscad", ("out_dir",),
                              "Generate C02-ME/Enclosure.scad source text from explicit constraints."),
    "c02_plan_intent": (_WC, "plan_c02_intent", ("spec_text",),
                        "Extract C02 enclosure constraints from natural language (pure analysis)."),
    # C03 emitters (3)
    "c03_export_mechanical_constraints": (_WC, "export_c03_mechanical_constraints", ("out_dir",),
                                          "Export C03 circuit/spec data affecting C02/C04 mechanical work."),
    "c03_emit_partition_diagram": (_WC, "emit_c03_partition_diagram", ("folder", "model"),
                                   "Project a partition MODEL into a layered breakout SVG (pptx=容器 tool)."),
    "c03_emit_host_block_diagram": (_WC, "emit_c03_host_block_diagram", ("folder", "model"),
                                    "Project a host/MCU MODEL into a layered block-diagram SVG (pptx=容器 tool)."),
    # C03->C04 stage-entry gates (2). BR_20260707: c04_readiness REFUSES entry
    # until both reports exist under <folder>/C03-EE, so these two must be
    # reachable from the landing plane or the C04 gate blocks every project.
    # `out_dir` is deliberately NOT required: it is a REPO_DEFAULT_KEY, so
    # requiring it would silently default it to the repo ROOT and write the
    # report one directory above where the gate reads it -- a green verb and a
    # still-blocked gate. The handlers default it to <folder>/C03-EE instead.
    "check_c03": (_WC, "check_c03", ("folder", "bom_csv"),
                  "C03->C04 stage-entry gate: BOM schema/readiness/drawability/SSOT. "
                  "Writes check_c03.report.json to out_dir (default <folder>/C03-EE). "
                  "Pass netlist_path (str or list) + covers_boards to exercise R5/R6; "
                  "omitting netlist_path yields netlist_crosscheck=not_run, which the "
                  "C04 gate treats as BLOCKING (a PASS without it does not mean every "
                  "BOM row is drawn)."),
    "prd_bom_crosscheck": (_WC, "prd_bom_crosscheck", ("folder", "manifest_path", "netlist_path"),
                           "Per-role fulfilment of the PRD component manifest against a KiCad "
                           "netlist. Writes prd_bom_crosscheck.report.json to out_dir "
                           "(default <folder>/C03-EE); the C04 entry gate requires it."),
    # C04/C05/C06 scaffold + readiness (6)
    "c04_emit_layout_package": (_WC, "emit_c04_layout_package", ("out_dir",),
                                "Assemble the C04 layout constraint package from C01+C03 exports."),
    "c04_readiness": (_WC, "assess_c04_layout_readiness", ("folder",),
                      "Report C04 layout-constraint readiness."),
    "c04_placement_review": (_WC, "emit_c04_placement_review", ("board_pcb", "out_dir", "board_name"),
                             "Emit the placement review package (renders + manifest + PLACEMENT_REVIEW.md) for owner approval."),
    "c04_placement_gate": (_WC, "assess_c04_placement_approval", ("folder",),
                           "Check PLACEMENT_APPROVED.json (owner-authorised) before routing is allowed."),
    "c05_scaffold_fw_spec": (_WC, "scaffold_c05_fw_spec", ("out_dir",),
                             "Scaffold the C05 firmware SW-spec sub-package (spec only, no code)."),
    "c05_readiness": (_WC, "assess_c05_fw_readiness", ("folder",),
                      "Report C05 FW SW-spec readiness."),
    "c06_assemble_test_plan": (_WC, "assemble_c06_test_plan", ("out_dir",),
                               "Assemble the C06 verification package from verify-tool verdicts."),
    "c06_readiness": (_WC, "assess_c06_readiness", ("folder",),
                      "Report C06 verification readiness."),
    # Orchestration spine (14)
    "agent_registry": (_WC, "load_agent_registry", (),
                       "Return the C00–C06 agent registry."),
    "dispatch_work_packet": (_WC, "dispatch_work_packet", ("folder", "target_layer", "objective"),
                             "C00 dispatches a scoped work packet to a downstream layer."),
    "list_work_packets": (_WC, "list_work_packets", ("folder",),
                          "List C00 work packets with target layer and status."),
    "return_blocker": (_WC, "return_blocker",
                       ("folder", "packet_id", "severity", "summary", "question_for_user"),
                       "A downstream layer returns a blocker against its work packet to C00."),
    "list_blockers": (_WC, "list_blockers", ("folder",),
                      "List blockers returned to C00 (unresolved_only supported)."),
    "ingest_blocker": (_WC, "ingest_blocker",
                       ("folder", "blocker_id", "resolved_state", "decision"),
                       "C00 records the human/owner resolution of a blocker and closes it."),
    "wrap_validation_evidence": (_WC, "wrap_validation_evidence", ("tool", "raw_result"),
                                 "Wrap a native validation result into the ValidationEvidence envelope."),
    "return_evidence": (_WC, "return_evidence", ("folder", "packet_id", "envelope"),
                        "A downstream layer returns measured validation evidence to C00."),
    "list_evidence_returns": (_WC, "list_evidence_returns", ("folder",),
                              "List evidence returns in the orchestration spine."),
    "ingest_evidence": (_WC, "ingest_evidence", ("folder", "evidence_id"),
                        "C00 consumes an evidence return, recording per-requirement verdicts."),
    "enter_c01_mode": (_WC, "enter_c01_mode", ("folder",),
                       "C00→C01 mode contract: dispatch + emit the C01 package + next question."),
    "c00_orchestration_status": (_WC, "c00_orchestration_status", ("folder",),
                                 "Read-only orchestration board (per-layer gates, blockers, PRD status)."),
    "c00_orchestration_tick": (_WC, "c00_orchestration_tick", ("folder",),
                               "Advance the C00-driven loop one step (may auto-dispatch)."),
    "reference_board_workflow": (_WC, "derive_workflow_plan",
                                 ("project_id", "board_design_id", "folder"),
                                 "Reference-board workflow plan derived from the orchestration spine."),
    # Read / gate
    "ingest_project": (_RC, "ingest_project_folder", ("folder",),
                       "Ingest a project folder read-only; classify files, detect C0* sections."),
    "package_readiness": (_WC, "assess_package_readiness", ("folder",),
                          "Assess a product folder against the POC deliverable checklist."),
    "datasheet_lookup": (_CK, "lookup", ("mpn",),
                         "Look up a part's cached datasheet extraction (<project>/datasheets/extracted/)."),
    "spec_check": (_CK, "spec_check", ("mpn", "field"),
                   "Check whether a spec field is grounded in the project datasheet cache."),
    "rca_spec_audit": (_CK, "audit_claims", ("claims",),
                       "Gate an RCA's spec claims against the project datasheet cache."),
    # Pure functions
    "plan_design_intent": (_WC, "plan_design_intent", ("spec",),
                           "Plan a DesignIntent from a natural-language spec."),
    "evidence_manifest": (_WC, "build_design_evidence_manifest", (),
                          "Build a design-evidence sourcing manifest for the spec's parts."),
    "pin_allocation": (_EB, "build_pin_allocation", ("nets",),
                       "Build a pin/GPIO allocation table from a net list; returns CSV."),
    "reference_crosscheck": (_WC, "crosscheck_nets", ("generated_nets", "reference_nets"),
                             "Cross-check generated nets vs a reference product's nets."),
    "impedance_solve": (_EB, "solve_impedance", ("stackup", "targets"),
                        "Pure-python C04 impedance estimate from stackup + targets."),
    "qa_svg_text": (_EB, "qa_svg_text", ("svg_path",),
                    "Render-layer text-overlap QA: scan every <text> bbox in a "
                    "kicad-cli-exported SVG; >15% intersection = violation. "
                    "violation=0 required for presentation-done claims."),
    # refs-first gate (EPIC refs-derived-design, 切面 1)
    "refs_ingest": (_WC, "ingest_refs", ("folder",),
                    "Scan a stage's 01_refs/ SSOT into a manifest (classify sources, "
                    "parse authority order, flag rich media as unadjudicated). Read-only; "
                    "root not visible → root_visible:false (loud, not a false-empty)."),
    # constraint-driven placement / castellated (EPIC refs-derived-design, 切面 2/3/4)
    "c04_face_placement": (_WC, "solve_face_placement", ("face_layout",),
                           "Deterministic constraint-driven placement: bind each connector to its "
                           "FROZEN upstream C01 face/edge (DD-4: face is not a C04 degree of freedom). "
                           "Same input → same output. Requires a parsed face_layout dict."),
    "c04_castellation": (_WC, "build_castellation", ("spec", "board_outline"),
                         "Build castellated (stamp-module) edge pads as segfault-free S-expression "
                         "injection (DD-5); refuses the known-unsafe pcbnew mutation paths. "
                         "Deterministic; provenance-gated (no-fabrication)."),
    "c04_dod_traceback": (_WC, "dod_refs_traceback", ("deliverable_items", "ssot_required_refs"),
                          "DoD refs-traceback (切面 5): upgrade DoD from surface-existence to SSOT "
                          "traceability. Every delivered item must trace to an SSOT anchor "
                          "(untraceable=憑空發明); every SSOT-required ref must appear "
                          "(unfulfilled=漏做). Either non-empty → blocking. Deterministic, no LLM."),
}

# Path-like arg keys resolved against --repo when relative; folder/out_dir
# default to the repo root itself when the verb requires them but the caller
# did not pass them (the `gate.py <verb> --repo <abs>` short form).
PATH_KEYS = ("folder", "out_dir", "corpus_dir", "source_image", "ai_export_path", "vault_root", "svg_path",
             "bom_csv", "pin_allocation_csv", "manifest_path")
REPO_DEFAULT_KEYS = ("folder", "out_dir")


def _jsonable(value):
    from dataclasses import asdict, is_dataclass
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


# ── Verb handlers (glue mirrors services/mcp/server.py _h_* bodies) ────

def _v_c00_scaffold_prd(a):
    from bodesign_workflow_core import scaffold_c00_prd_package
    return scaffold_c00_prd_package(a["out_dir"], a.get("project_name"), bool(a.get("include_rf", False))).to_dict()


def _v_refs_ingest(a):
    from bodesign_workflow_core import ingest_refs
    return ingest_refs(a["folder"]).to_dict()


def _v_c04_face_placement(a):
    from bodesign_workflow_core import parse_face_layout, solve_face_placement
    fl = parse_face_layout(a["face_layout"])
    return {"schema": "bodesign.c04.face_placement.v1",
            "placements": [p.to_dict() for p in solve_face_placement(fl)]}


def _v_c04_castellation(a):
    from bodesign_workflow_core import build_castellation, parse_castellation_request
    req = parse_castellation_request(a["spec"])
    return build_castellation(req, a["board_outline"], path=a.get("path", "sexpr_injection"))


def _v_c04_dod_traceback(a):
    from bodesign_workflow_core import dod_refs_traceback
    return dod_refs_traceback(a["deliverable_items"], a["ssot_required_refs"],
                              ssot_anchors=a.get("ssot_anchors")).to_dict()


def _v_c00_readiness(a):
    from bodesign_workflow_core import assess_c00_prd_readiness
    return assess_c00_prd_readiness(a["folder"]).to_dict()


def _v_c00_emit_prd(a):
    from bodesign_workflow_core import emit_c00_prd_markdown
    return emit_c00_prd_markdown(a["folder"]).to_dict()


def _v_c00_update_answers(a):
    from bodesign_workflow_core import c00_update_answers
    return c00_update_answers(a["folder"], a["answers"], regenerate=a.get("regenerate", True)).to_dict()


def _v_c00_emit_prd_docx(a):
    # Landing = render-only path. The assemble path needs the docxmcp MCP
    # bridge which lives in the container — refuse explicitly, never degrade.
    if a.get("assemble"):
        raise LandingError(
            VERB_ARGS_INVALID,
            "assemble=true is not a landing path (needs the docxmcp MCP bridge)",
            hint="call the container tool bodesign_c00_emit_prd_docx with assemble=true",
        )
    from bodesign_workflow_core import render_c00_prd_docx_package
    result = render_c00_prd_docx_package(a["folder"]).to_dict()
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


def _v_c01_emit_package(a):
    from bodesign_workflow_core import emit_c01_rockbox_package
    return emit_c01_rockbox_package(a["out_dir"], a.get("c00"), a.get("answers")).to_dict()


def _v_c01_readiness(a):
    from bodesign_workflow_core import assess_c01_package_readiness
    return assess_c01_package_readiness(a["folder"]).to_dict()


def _v_c01_next_question(a):
    from bodesign_workflow_core import c01_next_question
    return c01_next_question(a["folder"]).to_dict()


def _v_c01_update_answers(a):
    from bodesign_workflow_core import c01_update_answers
    return c01_update_answers(a["folder"], a["answers"], a.get("c00")).to_dict()


def _v_c01_emit_concept_prompts(a):
    from bodesign_workflow_core import emit_c01_concept_prompts
    return emit_c01_concept_prompts(a["out_dir"], a.get("c00"), a.get("answers")).to_dict()


def _v_c01_add_reference_image(a):
    from bodesign_workflow_core import c01_add_reference_image
    return c01_add_reference_image(a["folder"], a["source_image"], a["cue_type"], a["observed_cue"],
                                   a.get("target_artifact", "Ai file"), a.get("notes", "")).to_dict()


def _v_c01_confirm_reference_cue(a):
    from bodesign_workflow_core import c01_confirm_reference_cue
    return c01_confirm_reference_cue(a["folder"], a["cue_id"], a["confirmation"], a.get("note", "")).to_dict()


def _v_c01_emit_id_visual_package(a):
    from bodesign_workflow_core import emit_c01_id_visual_package
    return emit_c01_id_visual_package(a["folder"], a.get("answer_state"),
                                      figma_available=bool(a.get("figma_available", False)),
                                      ai_export_path=a.get("ai_export_path")).to_dict()


def _v_c01_emit_cmf_package(a):
    from bodesign_workflow_core import emit_c01_cmf_package
    return emit_c01_cmf_package(a["folder"], a.get("answer_state")).to_dict()


def _v_c01_emit_uiux_package(a):
    from bodesign_workflow_core import emit_c01_uiux_package
    return emit_c01_uiux_package(a["folder"], a.get("answer_state")).to_dict()


def _v_c02_readiness(a):
    from bodesign_workflow_core import assess_c02_constraint_readiness
    return assess_c02_constraint_readiness(a.get("constraints"), a.get("folder")).to_dict()


def _v_c02_emit_enclosure_package(a):
    from bodesign_workflow_core import emit_c02_enclosure_package
    return emit_c02_enclosure_package(a["out_dir"], a.get("constraints"), a.get("project_summary"),
                                      a.get("prototype_intent"), a.get("printer_profile")).to_dict()


def _v_c02_generate_openscad(a):
    from bodesign_workflow_core import generate_c02_openscad
    return generate_c02_openscad(a["out_dir"], a.get("constraints"), a.get("wall_thickness_mm"),
                                 a.get("clearance_mm"), a.get("lid_clearance_mm")).to_dict()


def _v_c02_plan_intent(a):
    from bodesign_workflow_core import plan_c02_intent
    return plan_c02_intent(a["spec_text"], a.get("answers"))


def _v_c03_export_mechanical_constraints(a):
    from bodesign_workflow_core import export_c03_mechanical_constraints
    return export_c03_mechanical_constraints(a["out_dir"], a.get("circuit")).to_dict()


def _reject_pptx(a, container_tool):
    if a.get("emit_pptx"):
        raise LandingError(
            VERB_ARGS_INVALID,
            "emit_pptx=true is not a landing path (needs the docxmcp MCP bridge)",
            hint=f"call the container tool {container_tool} with emit_pptx=true",
        )


def _v_c03_emit_partition_diagram(a):
    _reject_pptx(a, "bodesign_c03_emit_partition_diagram")
    from bodesign_workflow_core import emit_c03_partition_diagram
    return emit_c03_partition_diagram(a["folder"], a["model"], emit_pptx=False, mcp_call=None).to_dict()


def _v_c03_emit_host_block_diagram(a):
    _reject_pptx(a, "bodesign_c03_emit_host_block_diagram")
    from bodesign_workflow_core import emit_c03_host_block_diagram
    return emit_c03_host_block_diagram(a["folder"], a["model"], emit_pptx=False, mcp_call=None).to_dict()


def _v_c04_emit_layout_package(a):
    from bodesign_workflow_core import emit_c04_layout_package
    return emit_c04_layout_package(
        a["out_dir"], a.get("c01"), a.get("c03"),
        feasibility_signals=a.get("feasibility_signals"),
    ).to_dict()


def _v_c04_readiness(a):
    from bodesign_workflow_core import assess_c04_layout_readiness
    return assess_c04_layout_readiness(
        a["folder"], feasibility_signals=a.get("feasibility_signals"),
    ).to_dict()


def _c03_out_dir(a):
    """Default out_dir to <folder>/C03-EE -- the ONE path the C04 entry gate reads.

    Deliberately not a search: `c04_layout_constraints` pins
    `C03-EE/check_c03.report.json`, and a search chain would itself be the
    fallback this repo forbids. Callers may still pass out_dir explicitly.
    """
    out_dir = a.get("out_dir")
    if out_dir:
        return out_dir
    return os.path.join(a["folder"], "C03-EE")


def _abs_under(folder, value):
    """Resolve a path (or list of paths) against `folder` when relative.

    _build_args only rewrites scalar PATH_KEYS, so a list-valued netlist_path
    would otherwise arrive relative and silently resolve against the process
    cwd -- which is NOT the project. check_c03 raises on a missing netlist, but
    a wrong-but-existing cwd-relative match would be worse than a raise.
    """
    if isinstance(value, str):
        return value if os.path.isabs(value) else os.path.join(folder, value)
    if isinstance(value, (list, tuple)):
        return [_abs_under(folder, v) for v in value]
    return value


def _v_check_c03(a):
    from bodesign_workflow_core import check_c03
    folder = a["folder"]
    result = check_c03(
        _abs_under(folder, a["bom_csv"]),
        pin_allocation_csv=_abs_under(folder, a.get("pin_allocation_csv")),
        netlist_path=_abs_under(folder, a.get("netlist_path")),
        covers_boards=a.get("covers_boards"),
        frozen_pad_counts=a.get("frozen_pad_counts"),
        out_dir=_c03_out_dir(a),
    )
    from dataclasses import asdict
    return asdict(result)


def _v_prd_bom_crosscheck(a):
    from bodesign_workflow_core import prd_bom_crosscheck
    folder = a["folder"]
    result = prd_bom_crosscheck(
        _abs_under(folder, a["manifest_path"]),
        _abs_under(folder, a["netlist_path"]),
        out_dir=_c03_out_dir(a),
    )
    from dataclasses import asdict
    return asdict(result)


def _v_c04_placement_review(a):
    from bodesign_workflow_core import emit_c04_placement_review
    return emit_c04_placement_review(
        a["board_pcb"], a["out_dir"], a["board_name"],
    ).to_dict()


def _v_c04_placement_gate(a):
    from bodesign_workflow_core import assess_c04_placement_approval
    return assess_c04_placement_approval(a["folder"]).to_dict()


def _v_c05_scaffold_fw_spec(a):
    from bodesign_workflow_core import scaffold_c05_fw_spec
    return scaffold_c05_fw_spec(a["out_dir"], a.get("software"), a.get("pin_map")).to_dict()


def _v_c05_readiness(a):
    from bodesign_workflow_core import assess_c05_fw_readiness
    return assess_c05_fw_readiness(a["folder"]).to_dict()


def _v_c06_assemble_test_plan(a):
    from bodesign_workflow_core import assemble_c06_test_plan
    return assemble_c06_test_plan(a["out_dir"], a.get("verdicts"), a.get("certification_targets")).to_dict()


def _v_c06_readiness(a):
    from bodesign_workflow_core import assess_c06_readiness
    return assess_c06_readiness(a["folder"]).to_dict()


def _v_agent_registry(a):
    from bodesign_workflow_core import load_agent_registry
    return load_agent_registry().to_dict()


def _v_dispatch_work_packet(a):
    from bodesign_workflow_core import dispatch_work_packet
    return dispatch_work_packet(
        a["folder"], a["target_layer"], a["objective"],
        sections=a.get("sections"), fields=a.get("fields"), generated_docs=a.get("generated_docs"),
        inputs=a.get("inputs"), expected_outputs=a.get("expected_outputs"),
    ).to_dict()


def _v_list_work_packets(a):
    from bodesign_workflow_core import list_work_packets
    return {"work_packets": [w.to_dict() for w in list_work_packets(a["folder"])]}


def _v_return_blocker(a):
    from bodesign_workflow_core import return_blocker
    return return_blocker(
        a["folder"], a["packet_id"],
        severity=a["severity"], summary=a["summary"], question_for_user=a["question_for_user"],
        affected_c00_fields=a.get("affected_c00_fields"),
        affected_downstream_layers=a.get("affected_downstream_layers"),
        options=a.get("options"), recommended_owner=a.get("recommended_owner", "user"),
        proposed_state=a.get("proposed_state", "blocked"), evidence=a.get("evidence"),
        simple_fix_candidates=a.get("simple_fix_candidates"),
    ).to_dict()


def _v_list_blockers(a):
    from bodesign_workflow_core import list_blockers
    return {"blockers": [b.to_dict() for b in list_blockers(a["folder"], unresolved_only=a.get("unresolved_only", False))]}


def _v_ingest_blocker(a):
    from bodesign_workflow_core import ingest_blocker
    return ingest_blocker(
        a["folder"], a["blocker_id"],
        resolved_state=a["resolved_state"], decision=a["decision"], decided_by=a.get("decided_by", "user"),
    ).to_dict()


def _v_wrap_validation_evidence(a):
    from bodesign_workflow_core import wrap_validation_evidence
    return wrap_validation_evidence(
        a["tool"], a["raw_result"],
        inputs=a.get("inputs"), requirement_refs=a.get("requirement_refs"),
    ).to_dict()


def _v_return_evidence(a):
    from bodesign_workflow_core import return_evidence
    return return_evidence(
        a["folder"], a["packet_id"],
        envelope=a["envelope"], requirement_verdicts=a.get("requirement_verdicts"),
    ).to_dict()


def _v_list_evidence_returns(a):
    from bodesign_workflow_core import list_evidence_returns
    return {"evidence_returns": [e.to_dict() for e in list_evidence_returns(a["folder"], unresolved_only=a.get("unresolved_only", False))]}


def _v_ingest_evidence(a):
    from bodesign_workflow_core import ingest_evidence
    return ingest_evidence(a["folder"], a["evidence_id"])


def _v_enter_c01_mode(a):
    from bodesign_workflow_core import enter_c01_mode
    return enter_c01_mode(a["folder"], c00=a.get("c00"), answers=a.get("answers"), objective=a.get("objective")).to_dict()


def _v_c00_orchestration_status(a):
    from bodesign_workflow_core import c00_orchestration_status
    return c00_orchestration_status(a["folder"]).to_dict()


def _v_c00_orchestration_tick(a):
    from bodesign_workflow_core import c00_orchestration_tick
    return c00_orchestration_tick(a["folder"], auto_dispatch=a.get("auto_dispatch", True)).to_dict()


def _v_reference_board_workflow(a):
    from bodesign_workflow_core import derive_workflow_plan
    return derive_workflow_plan(
        a["project_id"], a["board_design_id"], a["folder"],
        artifact_count=a.get("artifact_count", 0), component_count=a.get("component_count", 0),
        net_count=a.get("net_count", 0), knowledge_queue_count=a.get("knowledge_queue_count", 0),
    ).to_dict()


def _v_ingest_project(a):
    from bodesign_reverse_core import ingest_project_folder
    idx = ingest_project_folder(a["folder"])
    d = idx.to_dict()
    d["files"] = d.get("files", [])[:200]  # keep payload bounded (server parity)
    return d


def _v_package_readiness(a):
    from bodesign_workflow_core import assess_package_readiness
    return assess_package_readiness(a["folder"], a.get("milestone", "POC")).to_dict()


def _v_datasheet_lookup(a):
    from bodesign_component_kb import lookup
    entry = lookup(a["mpn"], root=a.get("vault_root"))
    if entry is None:
        return {"status": "absent", "mpn": a["mpn"],
                "advice": "No cached datasheet extraction. Acquire the PDF into "
                          "<project>/datasheets/ and run the `datasheets` skill before stating "
                          "any spec for this part. Do not assert specs from memory."}
    return {"status": "present", **entry}


def _v_spec_check(a):
    from bodesign_component_kb import spec_check
    return spec_check(a["mpn"], a["field"], claimed_value=a.get("claimed_value"),
                      root=a.get("vault_root"))


def _v_rca_spec_audit(a):
    from bodesign_component_kb import audit_claims
    return audit_claims(a["claims"], root=a.get("vault_root"))


def _v_plan_design_intent(a):
    from bodesign_workflow_core import plan_design_intent
    return plan_design_intent(a.get("spec", ""), a.get("answers")).to_dict()


def _v_evidence_manifest(a):
    from bodesign_workflow_core import build_design_evidence_manifest, extract_part_candidates
    parts = a.get("parts") or extract_part_candidates(a.get("spec", ""))
    return build_design_evidence_manifest(parts, a.get("corpus_dir"))


def _v_pin_allocation(a):
    from bodesign_eda_bridge import build_pin_allocation, render_pin_allocation_csv
    alloc = build_pin_allocation(a["nets"], tuple(a.get("mcu_refs", [])))
    return {**alloc.to_dict(), "csv": render_pin_allocation_csv(alloc)}


def _v_reference_crosscheck(a):
    from bodesign_workflow_core import crosscheck_nets
    return crosscheck_nets(set(a["generated_nets"]), set(a["reference_nets"]),
                           a.get("label", "interface"), a.get("provenance")).to_dict()


def _v_impedance_solve(a):
    from bodesign_eda_bridge import solve_impedance
    return solve_impedance(a["stackup"], a["targets"])


def _v_qa_svg_text(a):
    from bodesign_eda_bridge.render_qa import qa_svg_text
    report = qa_svg_text(a["svg_path"])
    if hasattr(report, "to_dict"):
        return report.to_dict()
    # TextQAReport has no to_dict — assemble the report envelope by hand.
    return {
        "path": report.path,
        "texts": report.texts,
        "violations": [
            {"a": a_, "b": b_, "x": x_, "y": y_, "overlap_ratio": r_}
            for (a_, b_, x_, y_, r_) in report.violations
        ],
        "violation_count": len(report.violations),
        "ok": report.ok,
    }


HANDLERS = {}
for _name in VERBS:
    _fn = globals().get(f"_v_{_name}")
    if _fn is None:  # registry/handler drift is a programming error — fail loud
        raise RuntimeError(f"gate.py registry error: no handler _v_{_name}")
    HANDLERS[_name] = _fn


# ── CLI ─────────────────────────────────────────────────────────────────

def _list_envelope():
    verbs = [
        {"verb": name, "module": mod, "callable": fn, "required_args": list(req), "summary": summary}
        for name, (mod, fn, req, summary) in sorted(VERBS.items())
    ]
    return {"ok": True, "verb": "--list",
            "result": {"count": len(verbs), "verbs": verbs,
                       # BR_20260730 round 7: `--repo` is enforced for EVERY verb
                       # (_build_args, unconditionally, before per-verb checks),
                       # but it never appears in any `required_args` -- so a caller
                       # reading this roster alone satisfies the listed args and
                       # still gets VERB_ARGS_INVALID. A roster that omits a
                       # universal requirement is an incomplete declaration, which
                       # is what this BR family is about. Stated once, here, rather
                       # than injected into all 59 arg lists: it is a property of
                       # the CLI, not of any verb's signature.
                       "always_required": {
                           "--repo": "absolute path to an EXISTING project directory; "
                                     "required for every verb including pure functions "
                                     "(it seeds folder/out_dir defaults and resolves "
                                     "relative path args). Not listed per-verb because "
                                     "it is a CLI-level requirement, not a verb argument."
                       },
                       "not_landing": dict(sorted(NOT_LANDING.items()))}}


def _build_args(ns, verb):
    args = {}
    if ns.json_args:
        try:
            parsed = json.loads(ns.json_args)
        except ValueError as error:
            raise LandingError(VERB_ARGS_INVALID, f"--json is not valid JSON: {error}")
        if not isinstance(parsed, dict):
            raise LandingError(VERB_ARGS_INVALID, "--json must be a JSON object")
        args.update(parsed)
    for kv in ns.arg or []:
        if "=" not in kv:
            raise LandingError(VERB_ARGS_INVALID, f"--arg expects k=v, got: {kv!r}")
        k, _, v = kv.partition("=")
        try:
            args[k] = json.loads(v)
        except ValueError:
            args[k] = v

    if not ns.repo:
        raise LandingError(VERB_ARGS_INVALID, "--repo <absolute project dir> is required")
    if not os.path.isabs(ns.repo):
        raise LandingError(VERB_ARGS_INVALID, f"--repo must be an absolute path, got: {ns.repo!r}")
    if not os.path.isdir(ns.repo):
        raise LandingError(VERB_ARGS_INVALID, f"--repo is not an existing directory: {ns.repo!r}")
    repo = os.path.realpath(ns.repo)

    required = VERBS[verb][2]
    for key in REPO_DEFAULT_KEYS:
        if key in required and key not in args:
            args[key] = repo
    for key in PATH_KEYS:
        val = args.get(key)
        if isinstance(val, str) and val and not os.path.isabs(val):
            args[key] = os.path.join(repo, val)

    missing = [k for k in required if args.get(k) is None]
    if missing:
        raise LandingError(VERB_ARGS_INVALID,
                           f"verb '{verb}' missing required arg(s): {', '.join(missing)}",
                           hint="pass them via --json '{...}' or --arg k=v")
    return args


def main(argv=None):
    # (1) python version — before anything else
    try:
        _check_python()
    except LandingError as error:
        return _fail("", error.code, error.message, error.hint)

    parser = argparse.ArgumentParser(
        prog="gate.py", description="bodesign landing-plane verb runner", add_help=True)
    parser.add_argument("verb", nargs="?", help="landing verb name (see --list)")
    parser.add_argument("--repo", help="absolute path to the caller's project folder")
    parser.add_argument("--json", dest="json_args", help="verb arguments as a JSON object")
    parser.add_argument("--arg", action="append", default=[],
                        help="single k=v argument (value parsed as JSON when possible); repeatable")
    parser.add_argument("--list", dest="list_verbs", action="store_true",
                        help="enumerate landing verbs and exit")
    ns = parser.parse_args(argv)

    if ns.list_verbs:
        return _emit(_list_envelope())

    verb = ns.verb or ""
    try:
        # (2)+(3) resolve packages + sys.path — no container fallback
        src = _resolve_src()
        _prepend_packages(src)

        # (4) verb lookup: unknown vs known-heavy
        if not verb:
            raise LandingError(VERB_ARGS_INVALID, "no verb given; run --list to enumerate landing verbs")
        if verb in NOT_LANDING:
            raise LandingError(
                VERB_NOT_LANDING,
                f"'{verb}' is a heavy/container verb and does not run on the landing plane",
                hint=f"call the container MCP tool {NOT_LANDING[verb]} instead",
            )
        if verb not in VERBS:
            raise LandingError(VERB_UNKNOWN,
                               f"unknown verb: {verb!r}; run gate.py --list to enumerate landing verbs")

        # (5) arg validation
        args = _build_args(ns, verb)
    except LandingError as error:
        return _fail(verb, error.code, error.message, error.hint)

    _log(f"landing_verb_start verb={verb} repo={ns.repo}")
    try:
        result = _jsonable(HANDLERS[verb](args))
    except LandingError as error:  # handler-level typed refusal (e.g. assemble/emit_pptx)
        return _fail(verb, error.code, error.message, error.hint)
    except Exception as error:  # (6) runtime error — traceback to stderr only
        traceback.print_exc(file=sys.stderr)
        return _fail(verb, VERB_RUNTIME_ERROR, f"{type(error).__name__}: {error}")
    _log(f"landing_verb_ok verb={verb}")
    return _emit({"ok": True, "verb": verb, "result": result})


if __name__ == "__main__":
    sys.exit(main())
