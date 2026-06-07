# C00 Downstream Work-Packet Contract

Status: planned contract source

Purpose: define how C00 sends scoped work to C01-C06 specialist agents and how blockers return to C00 without allowing downstream layers to mutate the product requirement contract directly.

## Principles

- C00 is the input SSOT and requirement contract owner.
- Downstream agents may propose, refine, and report blockers, but product-direction changes return to C00.
- Work packets carry source traceability to C00 fields and emitted PRD sections.
- Missing information remains explicit; no downstream agent may invent hidden defaults.
- Human/external approvals remain gates, not AI-completed states.

## Work Packet Schema

```json
{
  "schema": "bodesign.c00.work_packet.v1",
  "packet_id": "C00-WP-0001",
  "target_layer": "C01|C02|C03|C04|C05|C06",
  "target_role": "industrial_design|mechanical|electrical|layout|firmware|verification",
  "source": {
    "c00_folder": "C00-PRD",
    "answer_state_path": "C00-PRD/answer_state.json",
    "sections": ["s05_id_me_requirements"],
    "fields": ["s05_id_me_requirements.dimensions"],
    "generated_docs": ["C00-PRD/Project_Requirements.generated.md"]
  },
  "objective": "What this downstream layer should produce or diagnose.",
  "inputs": {
    "answered": [],
    "drafted": [],
    "accepted_risks": [],
    "external_needed": [],
    "blocked": []
  },
  "allowed_actions": ["diagnose", "ask_followup", "draft_artifact", "run_tool", "return_blocker"],
  "forbidden_actions": ["change_product_direction", "mark_human_approved", "silently_fill_missing", "claim_professional_signoff"],
  "expected_outputs": ["layer-specific artifact paths or report names"],
  "return_to_c00_when": ["product decision needed", "scope conflict", "external approval needed", "accepted-risk required"],
  "status": "ready|partial|blocked"
}
```

## Blocker Return Schema

```json
{
  "schema": "bodesign.c00.blocker_return.v1",
  "packet_id": "C00-WP-0001",
  "source_layer": "C01|C02|C03|C04|C05|C06",
  "blocker_id": "C01-BLOCK-0001",
  "severity": "decision|external-needed|blocked|accepted-risk-request",
  "summary": "User-answerable summary of the issue.",
  "evidence": {
    "artifact_paths": [],
    "field_refs": [],
    "tool_results": []
  },
  "affected_c00_fields": ["s05_id_me_requirements.dimensions"],
  "affected_downstream_layers": ["C02", "C04"],
  "question_for_user": "One focused C00-level question.",
  "options": [],
  "recommended_owner": "user|external_expert|downstream_agent|ai_draft",
  "proposed_state": "missing|drafted|answered|external-needed|blocked|accepted-risk"
}
```

## Layer Defaults

- `C01`: external appearance, CMF, Display UI/UX, exposed-interface preference, ID handoff.
- `C02`: mechanical constraints, enclosure, assembly, printability, ME/vendor handoff.
- `C03`: schematic, BOM, GPIO/pin map, component constraints, EE review package.
- `C04`: board outline, placement/routing, stackup, Gerber/fab handoff, DFM constraints.
- `C05`: firmware requirements, state machine, program SOP, image/source handoff.
- `C06`: bring-up, validation plan, test evidence, compliance/EVT/DVT gates.

## Runtime Boundary

This contract is a schema source for future dispatch. The current MVP stores the contract in the plan package only; it does not yet implement autonomous dispatch or blocker ingestion tools.
