# Tasks: aiguard_refs-ssot-build

## 1. Harvest existing SSOT into 01_refs/

- [x] 1.1 Define per-layer manifest schema (`refs_manifest.json`: `layer`, `status` ∈
      {`frozen`,`blocked_missing_source`}, `authority_tier` ∈ {`user_prd`,`datasheet`,`human_seed`,`mixed`},
      `files[]` real-only, `required_authority`, `source_anchors[]`). Encode in data-schema.json.
- [x] 1.2 Harvest C00 SSOT: extract the `source:user` fields from
      `C00-PRD/answer_state.json` (12 sections + RF) into `01_refs/C00/prd.json`, each
      value anchored to its `{document, section_id, field}`. Freeze.
- [x] 1.3 Harvest C01 SSOT: extract real values from `Interface_Constraints.json` +
      the 2 C01 PDFs (`Product_UIUX_Flow.pdf`, `Product_CMF_Direction.pdf`) into
      `01_refs/C01/` with anchors. Drop the immature `drafted` derivation.
- [x] 1.4 Harvest C02 SSOT: extract real/committed values (18650 envelope, IP54/65,
      board outline provenance) from `Mechanical_Constraints.json` into `01_refs/C02/`;
      separate `source:user`/committed from `assumption`/`drafted`.
- [x] 1.5 Harvest C04 SSOT: extract real placement intent + committed values from
      `Layout_Constraints.json` into `01_refs/C04/`; drop immature draft coordinates.
- [x] 1.6 Write top manifest listing all layers with harvested status.

## 2. Reuse vault + expand datasheet SSOT (DD-3/DD-4)

- [x] 2.1 List PRD-named parts (STM32N657L0, BQ24075, LM66200/66100, CYW43439/LBEE5KL1YN,
      MX25UM NOR, APS512 PSRAM, TPS62824, TLV7xx, touch-OLED/CTP, MIPI 5→2 mux).
- [x] 2.2 For each, `bodesign_vault_spec_check` — reuse the 26 already-ingested datasheets
      where present (BQ24075, TPS62824, TCR2LE33, TLV75733/TLV74018, W25Q128 …). Link into
      the relevant layer's `source_anchors[]` as tier=`datasheet`.
- [x] 2.3 For PRD-named parts NOT in the vault, `bodesign_datasheet_lookup` +
      `bodesign_vault_ingest` to pull real datasheets (provenance `01_refs/datasheets/<MPN>.pdf`),
      then spec-check. Every grounded value page-anchored `{MPN, page}` (天条 4).
      Honest rank-0 if no real datasheet found — no substring-fabricated match.
- [x] 2.4 Fold datasheet-grounded electrical/mechanical values into `01_refs/C02` +
      `01_refs/C03` SSOT.

## 3. Kill-and-regen immature C00~C04 products + new C03-EE (DD-7)

- [x] 3.1 Create `.work/aiguard/C03-EE/` stage; ground its EE definition from
      `01_refs/C00` electrical section + datasheet SSOT (pin map, power tree, module-socket ICD).
- [x] 3.2 Regenerate C01/C02/C04 products refs-derived from the frozen `01_refs/`
      (replace the immature `drafted` versions; old real SSOT already harvested in phase 1).
- [x] 3.3 For any field with genuinely-absent SSOT (owner-only final coordinates,
      unassigned approvers, external compliance), mark `blocked_missing_source` +
      named `required_authority` (天条 2: flag, no phantom file). Only legitimate BLOCKED case.

## 4. refs-derived regression

- [x] 4.1 Run `refs_ingest` against `.work/aiguard`; confirm each frozen layer loads and
      any genuinely-absent-SSOT field fail-fasts `REFS_SSOT_MISSING` (天条 1 verify).
- [x] 4.2 Drive the chain refs-derived; capture per-layer result + which SSOT (PRD field /
      vault datasheet / newly-pulled datasheet) grounds each.
- [x] 4.3 Write `.work/aiguard/01_refs/REGRESSION.md`: per-layer pass/block, SSOT citations,
      and the exact owner source each residual BLOCKED field needs.

## 5. Sync + closeout

- [x] 5.1 event_record open + close (scope `aiguard/refs-ssot-build`).
- [x] 5.2 Architecture sync check (`specs/architecture.md`): add aiguard refs-regression
      note or record `Verified (No doc changes)`.
- [x] 5.3 Report readiness for `verified`; do NOT self-graduate (user-only gate).
