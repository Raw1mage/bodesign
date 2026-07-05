# Proposal: aiguard_refs-ssot-build

## Why

- The graduated EPIC `capability/refs-derived-design` makes every C00~C04 generation
  stage **refs-derived**: it calls `require_refs(folder, layer)` and consumes a frozen
  `01_refs/<layer>/` SSOT instead of generating from nothing.
- aiguard is a **mature, SSOT-rich project** — NOT a greenfield. On disk today:
  - **C00** `answer_state.json` = a **complete, user-authored PRD SSOT** (12 sections +
    RF, every field `source:user`), naming **real parts**: STM32N657L0 SoC, BQ24075
    charger, LM66200/LM66100 power-path, Murata LBEE5KL1YN / CYW43439 radio, MX25UM-class
    octal NOR, APS512-class octal PSRAM, TPS62824 / TLV7xx rails.
  - **C01/C02/C04/C05** each already have constraint artifacts
    (`Interface_Constraints.json`, `Mechanical_Constraints.json`, `Layout_Constraints.json`,
    `Pin_Map_Bridge.json`) — currently in `drafted`/`draft` state (immature).
  - The **component vault** (`.run/vault/vault.db` + 26 datasheet PDFs) already holds
    **real ingested datasheets**, including PRD-named parts (BQ24075, TPS62824, TCR2LE33,
    TLV75733/TLV74018, W25Q128, nRF7002 …), harvested from
    `thesmart_products/.../c03-ee/01_refs/datasheets` + `refs/02.OpenMV`.
- The problem is NOT missing SSOT. It is that **C00~C04 have immature `drafted` products**
  and **no consolidated `01_refs/` SSOT** for the refs-derived gate to consume. This plan
  **harvests the existing SSOT, expands it with real datasheets, and redoes (kill+regen)
  the immature C00~C04 products refs-derived** — so aiguard can run a real full-chain
  regression.

## Original Requirement Wording (Baseline)

- "你可以先把plan建起來，我再去開新session工作"
- "aiguard/01_refs/下面的所有資料就是目前所有的人類提供的ssot"
- "執行過程中你完全有權去擴充ssot，例如去拉電子元件的datasheet"
- "aiguard這個資料夾是已經發展了一陣子的資料夾，只是在C00~C04各層都還不成熟而已，
  你要做的是把做不好的舊版砍掉重做，而不是放棄原本就有的ssot，尤其是寶貴的datasheet"

## Requirement Revision History

- 2026-07-04: initial draft created via plan-init.ts
- 2026-07-05 (v1, SUPERSEDED): wrongly framed aiguard as having only 2 real sources
  (C01 PDFs) and auto-blocked all other layers.
- 2026-07-05 (v2, SUPERSEDED): added Tier-1/Tier-2 authority model + datasheet expansion,
  but still under-counted existing SSOT.
- 2026-07-05 (v3, EFFECTIVE): corrected against full disk reality — aiguard is a mature
  project with a complete user PRD, existing (immature) C01/C02/C04/C05 constraints, and
  a 26-datasheet vault. Scope = **harvest existing SSOT + expand via datasheet +
  kill-and-regen the immature C00~C04 products**, never discard existing SSOT.

## Effective Requirement Description

1. **Harvest** existing SSOT into a consolidated `.work/aiguard/01_refs/<layer>/` frozen
   root: the C00 user PRD (`answer_state.json`), the 2 C01 PDFs, and the real values held
   in the existing C01/C02/C04/C05 constraint files (keep their `source:user` /
   datasheet-grounded values; drop the immature/`drafted` derivation).
2. **Reuse the vault**: link the already-ingested datasheets (`bodesign_vault_spec_check`)
   for every part the PRD names that is already in the vault (BQ24075, TPS62824, TLV7xx …).
3. **Expand SSOT**: for PRD-named parts NOT yet in the vault (STM32N657L0, CYW43439/
   LBEE5KL1YN, MX25UM NOR, APS512 PSRAM …), pull real datasheets via
   `bodesign_datasheet_lookup` / `bodesign_vault_ingest` — every value page-anchored.
   This is SSOT expansion (天条 4), the OPPOSITE of fabrication.
4. **Kill + regenerate** the immature C00~C04 products (the `drafted`/`draft` constraint
   JSONs, `.generated.md`) refs-derived from the harvested+expanded `01_refs/` — do NOT
   preserve the做不好的舊版 as-is, and do NOT re-invent from nothing.
5. Add the missing **C03-EE** stage (aiguard has no C03-EE dir), grounded from the PRD's
   electrical section + vault/datasheet specs.
6. Run the refs-derived full-chain regression; report per-layer pass/block and cite which
   SSOT (PRD field / vault datasheet / newly-pulled datasheet) grounds each layer.

## Scope

### IN
- Consolidated `01_refs/<layer>/` SSOT harvested from existing C00 PRD + C01/C02/C04/C05
  constraints + 2 C01 PDFs, with a per-layer manifest.
- Vault reuse for already-ingested PRD-named datasheets.
- Datasheet expansion (pull + ingest) for PRD-named parts not yet in the vault.
- Kill-and-regen of the immature `drafted` C00~C04 products, refs-derived.
- New C03-EE stage, grounded from PRD electrical + datasheet SSOT.
- Full-chain regression with per-layer SSOT-cited pass/block report.

### OUT
- Discarding any existing user-sourced SSOT or vault datasheet (explicit user constraint).
- Fabricating a spec value from nothing (天条 2) — every value traces to PRD / datasheet.
- Modifying the graduated EPIC's core modules (`refs_gate.py`, `upstream_constraints.py`,
  `board_surgery.py`, `dod_traceback.py`) — `living`, consumed as-is.
- Send-to-fab / deterministic-validation-gated fab output (天条 3).
- `quality_deterministic-preplacement` placement-quality algorithm (separate plan, DD-8).

## Non-Goals

- A green end-to-end chain this iteration. Some fields (final coordinates, compliance,
  approvals) are legitimately owner/external-gated and stay open.
- LLM-invented electrical/mechanical specs (天条 4: PRD- or datasheet-grounded only).

## Constraints

- **No silent fallback (天条 1)**: a layer whose SSOT is genuinely absent fail-fasts
  `REFS_SSOT_MISSING`, never defaults.
- **No fabrication (天条 2)**: `files[]` lists only real on-disk artifacts; every frozen
  value carries a `{source, page}` anchor (PRD field id, or datasheet page).
- **Never discard existing SSOT** (user天条 for this project): existing user PRD +
  constraints + vault datasheets are harvested and reused, not dropped.
- `.work/aiguard` is a bodesign-gitignored work dir with no independent git/.specbase.
- Datasheet expansion follows the existing vault provenance convention
  (`01_refs/datasheets/<MPN>.pdf`).

## What Changes

- New consolidated `.work/aiguard/01_refs/` SSOT (harvested + datasheet-expanded).
- New `.work/aiguard/C03-EE/` stage.
- Immature `drafted` C00~C04 products regenerated refs-derived (old versions killed).
- Vault may gain newly-ingested datasheets for PRD-named parts.
- No production code change in bodesign packages (consumer-side execution of the EPIC).

## Capabilities

### New Capabilities
- Consolidated `01_refs/` SSOT for aiguard: a single frozen root that unifies user PRD,
  layer constraints, and vault datasheets for the refs-derived gate.

### Modified Capabilities
- aiguard C00~C04: from immature `drafted` generate-from-nothing products to refs-derived
  products grounded in a harvested+expanded SSOT.
- aiguard full-chain run: from "no `01_refs/` to consume" to "runs refs-derived against a
  real consolidated SSOT".

## Impact

- `.work/aiguard/**` (work dir only; gitignored) + `.run/vault` (new datasheet ingests).
- Exercises `refs_gate.require_refs`, `refs_ingest`, `bodesign_vault_spec_check` /
  `bodesign_datasheet_lookup`, and the retained `prd_bom_crosscheck` BR when C04 is redone.
- No change to `specs/architecture.md` production modules; may add an aiguard regression note.
