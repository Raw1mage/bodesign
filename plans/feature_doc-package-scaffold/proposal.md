# Proposal: Document-package scaffold (C0* blank architecture → fill incrementally)

## Why

Today bodesign generates individual artifacts (schematic, BOM, companions) but there is **no
blank document-architecture skeleton** that a new project starts from. The requirement question
bank (`requirement_planning.REQUIREMENT_FIELDS`) is hand-coded and disjoint from any document
template; the C0* package architecture (proven on the 01.ROCKBOX shipped product) lives only in
reference materials and is merely *detected* by `project_ingest`, never lifted into a reusable
template. So every project re-improvises its structure.

This feature makes the **C0* document architecture a first-class template in the MCP server**:
when a new project request arrives, bodesign first scaffolds the **blank C0* skeleton** into the
client's token folder (folders + section stubs + per-section question prompts), then fills each
section's content incrementally as the workflow proceeds. This mirrors **docxmcp's decompose-src
flow**: establish the structural skeleton first, then populate — the structure is the contract.

## Original Requirement Wording (Baseline)

- "開一個 template plan，目的是在 mcp server 裏建一個空白文件架構，每當有新專案要求的時候，就先把架構骨架建在 client 端，再開始一一的填入內容。這是仿照 docxmcp 拆解 src 的流程邏輯。"
- "以 RockBox 文件為範本，抽取出架構 template src，做為後續範本。" / RPF（C00/C07 PRD）深度要擴充。

## Effective Requirement Description

1. Lift the **C0* document architecture** (C00/C07 PRD · C01 ID · C02 ME · C03 電路 · C04 Layout · C05 FW(SW-spec) · C06 驗證) into a single declarative **template src** (the skeleton + per-section role + question prompts + required fields + the four-capability bindings).
2. Add an MCP tool that **scaffolds the blank skeleton** into a client token folder: C0* section folders + a stub doc per section (front-matter + headings + open questions), nothing fabricated.
3. **Fill incrementally**: subsequent tools (requirement_planning, compose/emit, verify, kidoc) write into the matching section; `package_readiness` computes the compass from which sections are still stubs.
4. The same template src drives **all three consumers**: the elicitation question bank, the scaffold, and the `kidoc` document output — so "題庫 ≡ 文件架構".
5. **De-product**: the template is generic (RockBox/TheSmartAI are exemplars only); no client content ships in the program.
6. **Each layer declares its four-capability chain** — `elicit_with` / `generate_with` / `verify_with` (+ a `coverage` status) — so the MCP+skills *know*, per layer, what to fill, how to ask, what generates it, and what verifies it. Only C03 is `full` today; the rest are explicit `partial`/`gap`.
7. **FW (C05) is an extension of the PRD, realized as a software-development spec — not code.** bodesign does NOT write firmware; it stands up + maintains a **plan-builder-like SW-dev architecture spec** inside C05 (functional spec from the PRD's functional description + module/interface/state-machine + task breakdown, with its own IDEF0/GRAFCET), bridged to the C03 pin map. bodesign owns the *spec*, the FW team owns the *code*.
8. **The MCP is a thin orchestrator across a very large professional span.** Each C0* layer **references a specialized external skill** (per-section `skill` binding) to do its domain work — C03→kicad/kidoc/spice/emc/datasheets/bom/distributors/fab, C05→plan-builder/software-architect, C00→plan-builder/kidoc, etc. bodesign owns the scaffold, the cross-layer contract, and the readiness compass — not every domain's expertise.

## Scope

### IN
- A generic `doc_architecture.json` template src (the C0* skeleton, roles, prompts, required fields).
- An MCP scaffold tool: token folder → blank C0* package (folders + section stubs).
- Wiring: `requirement_planning` reads the template's question bank; `package_readiness` reads section fill-state; `kidoc` gains a doc_type per section (starting with the PRD/RFP).
- Deepening the **PRD/RFP (C00/C07)** section depth (the requirements front-end).

### OUT
- Actually authoring section *content* (that is the existing generation/orchestration tools' job).
- Producing C01/C02/C04/C05 deliverables (bodesign supplies constraints/interface only — unchanged boundary).
- A GUI (the surface stays MCP + files).

## Non-Goals

- Not replacing `requirement_planning`'s extraction logic — only changing where its fields come from (template, not hard-coded).
- Not graduating into a new product; this extends bodesign's existing forward-generation layer.

## Constraints

- Mirror docxmcp's decompose-src logic (skeleton first, byte-faithful structure, fill in place).
- No working data in the repo; the template is structure-only (generic section taxonomy, not client content).
- Deterministic scaffold output (stable ordering) for reproducibility + cross-check.

## What Changes

- New `doc_architecture.json` template src + a `scaffold_doc_package` MCP tool.
- `requirement_planning.REQUIREMENT_FIELDS` moves from hard-coded to template-derived.
- `package_readiness` learns the C0* section model (stub vs filled).
- `kidoc` gains a PRD/RFP doc_type (and later one per C0* section).

## Capabilities

### New Capabilities
- **C0* scaffold**: blank document-package skeleton created in the client token folder on project start.
- **Template-driven question bank**: the RFP/PRD elicitation questions come from the template, deepenable in one place.

### Modified Capabilities
- **requirement_planning**: same contract, fields sourced from the template.
- **package_readiness**: compass now reflects C0* section fill-state.

## Impact

- `packages/workflow-core` (requirement_planning, package_readiness), `services/mcp/server.py` (new tool), the `kidoc` skill (new doc_type), and the new template src. No change to the program↔data isolation boundary.
