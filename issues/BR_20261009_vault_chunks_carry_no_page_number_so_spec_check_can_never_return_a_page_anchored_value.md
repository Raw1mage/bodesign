---
id: BR_20261009_vault_chunks_carry_no_page_number_so_spec_check_can_never_return_a_page_anchored_value
title: Vault chunks carry no page_number and spec_values no evidence_chunk_id, so vault_spec_check can never return a page-anchored value
date: 2026-10-09
status: open
severity: medium
priority: P2
component: packages/component-kb (vault schema + ingest), bodesign_vault_spec_check
reporter_session: ses_04db7a1c5ffelvbxyLP1p6xlRH
edges:
  - to: issues/closed/BR_20261006_dockerlab_compose_omits_vault_dir_so_served_vault_tools_return_e002.md
    type: surfaced-by
    reason: Measured while verifying the vault deployment; §7(b) accepted it as out of that BR's scope.
  - to: plans/eda-bridge_unified-collaborative-rebuild/tasks.md
    type: references-spec
    reason: Task 3.7 (sourced physical calculations, DS findings into release policy) depends on page-anchored evidence.
---
# Vault has no page anchors, so "datasheet-grounded" claims cannot be grounded

- **Status**: OPEN — data/schema gap measured 2026-10-09 on the deployed vault (109 components)

## 1. Symptom (measured, read-only SQL on the checkpointed copy and in-container)

- `chunks`: 16156 rows, `page_number IS NOT NULL` count = **0**.
- `spec_values JOIN chunks` on page number → **0 rows**.
- Sampled spec (`W25Q128JVSIQ recommended_operating_conditions.vin_min_v`): `source =
  "client-cache-import:Digi-Key spec table (W25Q128JVSIQ): VCC 2.7-3.6V, verified 2026-06-08.
  Full datasheet PDF not yet acquired."`, no `evidence_chunk_id`.
- Served `bodesign_vault_spec_check` returns `status: verified … matches: true` for that field.
  The verdict is honest about its source, but the tool name and AGENTS.md §2.4 ("Datasheet-grounded
  electrical claims … via vault_spec_check") read as datasheet evidence.

## 2. Impact

- AGENTS.md §2.4 mandates `vault_spec_check` before any electrical claim; today every claim it
  "verifies" traces to a distributor spec table import, never to a datasheet page. The policy
  promise and the deliverable differ in kind, not in degree.
- `bodesign_spice_model_card` advertises "page-anchor evidence per parameter"; with this vault
  no card can carry one.
- Rebuild task 3.7 (DS physical calculations → release policy) has no evidence substrate.

## 3. RCA (observed + hypothesis)

Observed: the 109-component vault was seeded 2026-06-08/11 by a client-cache import of
distributor spec tables; no datasheet PDF ingestion ran. The chunk table has the `page_number`
column but the import path never populates it.
Hypothesis, unverified: the PDF ingest path (`vault_ingest`) does populate `page_number`, so the
gap is data, not schema. Needs one real ingest to confirm.

## 4. Proposed remediation (owner ruling needed on scope)

1. **Disclosure first (small, this repo)**: `vault_spec_check` result gains an explicit
   `evidence_kind: distributor_table | datasheet_page | none` field and `page_anchor: null`
   when absent; `status: verified` is reserved for `datasheet_page`; distributor-only matches
   return `status: consistent_with_distributor_table`. No silent upgrade of the current data.
2. **Ingest proof**: ingest ONE real datasheet (candidate: PESDXL4UF_G_W.pdf already held in
   scratch per the closed BR §5.4) and show `page_number` populated + `evidence_chunk_id` bound.
3. **Backfill policy**: decide whether the 109 distributor-only entries are re-grounded by PDF
   ingest or left as disclosed lower-tier evidence. Tie to task 3.7.

## 5. Acceptance

- `vault_spec_check` on a distributor-only entry no longer returns bare `verified`; the result
  names the evidence kind.
- After one PDF ingest, `vault_spec_check` on a field from that datasheet returns a non-null
  page anchor that resolves to a chunk with `page_number`.
- Control: a synthetic spec_value with `evidence_chunk_id` pointing to a chunk whose
  `page_number` is NULL must fail the gate, not pass as page-anchored.
