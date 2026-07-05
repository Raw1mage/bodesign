# Handoff: aiguard_refs-ssot-build

## Execution Contract

- Deliver `.work/aiguard/01_refs/` as the frozen human-SSOT boundary: a top manifest +
  per-layer `refs_manifest.json`, with C01 `frozen` (2 real PDFs extracted to page-anchored
  JSON) and C00/C02/C03/C04 `blocked_missing_source` + named `required_authority`.
- Create the `.work/aiguard/C03-EE/` stage dir (structurally present, BLOCKED).
- Run the refs-derived regression bounded by available SSOT and deliver
  `.work/aiguard/01_refs/REGRESSION.md` with honest per-layer pass/block + the owner
  source each blocked layer needs.
- **Done** = all 6 Acceptance Checks in spec.md tick; regression report written;
  readiness for `verified` reported to the user (NOT self-graduated).

## Required Reads

- This package: `proposal.md`, `design.md` (DD-1..5), `spec.md`, `data-schema.json`.
- `packages/workflow-core/bodesign_workflow_core/refs_gate.py` — `require_refs` contract.
- `packages/workflow-core/bodesign_workflow_core/upstream_constraints.py` — refs→constraint adapter.
- `services/mcp/gate.py` — `refs_ingest` verb (`_v_*` handler) + `_v_c04_readiness`.
- The 2 real sources: `.work/aiguard/C01-ID/Display UI_UX/Product_UIUX_Flow.pdf`,
  `.work/aiguard/C01-ID/CMF/Product_CMF_Direction.pdf`.
- Prior EPIC (context): `specs/capability/refs-derived-design/` (graduated, `living`).

## Stop Gates In Force

- **User-only graduate gate**: never call `plan_graduate`; report `verified` readiness only.
- **No fabrication (天条 2)**: if a PDF has no extractable structured spec for a section,
  mark it thin/absent — do NOT invent values. Blocked layers get a status flag, no phantom file.
- **No silent fallback (天条 1)**: missing refs must fail-fast, not default.
- **Datasheet-grounded (天条 4)**: every frozen electrical/mechanical value carries a page anchor.

## Execution-Ready Checklist

- [ ] SSOT boundary confirmed = `01_refs/` (user decision 2026-07-05)
- [ ] The 2 real C01 PDFs confirmed on disk; no other owner sources assumed
- [ ] EPIC core modules (`refs_gate` etc.) treated read-only (`living`)
- [ ] PDF extraction toolchain available (docxmcp / markitdown / pdftotext) verified before start
