# Reference Amendment Validation — 2026-10-06

Scope: reference evaluation and ECAD-MCAD target design, not implementation.
Source inventory is recorded in reference-evaluation.md with five immutable
upstream commits, license anchors and code/test-source/document distinctions.
No upstream source was copied, no dependency installed and no CAD/API test run.

## Checks Performed

- Dedicated `specbase_diagram_validate` on the amended idef0.json content returned
  isError=false: `IDEF0 validation passed: 1 level(s), 4 activities, 16 arrows in total; root node_reference='A0' has 4 activities, 16 arrows.`
- GRAFCET bytes are unchanged from design-validation.md's successful dedicated
  validation (6 steps, 6 explicit gates, 16 explicit edges). Its A1-A4 contract
  remains applicable: applicability includes frame/license prerequisites; required
  checks include mechanical policy; unknown CAD outcomes cannot produce build_ok.
- Command: `bun /home/pkcs12/.local/share/opencode/skills/plan-builder/scripts/plan-validate.ts /home/pkcs12/projects/bodesign/plans/eda-bridge_unified-collaborative-rebuild --target-state planned --placeholders block`.
  Exit 0; PASS, 12 required and 1 optional artifact contract entries; actual state
  was designed. Generic execution-contract layer NOT RUN (not opted in).
- State read-back confirms designed; no duplicate promotion, graduation or
  implementation transition was performed for this additive design revision.

## Content Coverage

- All five references have capability-level integration choices and license limits.
- R8-R11 and AC10-AC15 cover adoption, native annotation/escaping, feature DAG,
  exact mechanical evidence, physical-input gaps and uncertain CAD jobs.
- Schemas add six reference/bridge/calculation/job contracts; these are field
  and invariant designs, not executable JSON Schema or deployed APIs.
- TV-17 through TV-25 add nine cases; all 25 vectors remain not-run.
- Local ME implementation is separated from optional proprietary/cloud adapters.
- P0 remains inventory-only, with explicit external permission and installation limits.

## Fingerprints

Measured using sha256sum (exit 0), before receipt/task bookkeeping:

| File | SHA-256 |
| --- | --- |
| idef0.json | 243386f12685e2ddc92552681a8a1bbd226360a2a32f701e0b359b2606c8dac4 |
| grafcet.json | 1e08464a16539ca523507d37de3ecfe529f0efb94b39eb0906b07a37b93b118b |
| data-schema.json | a2817393300cd4d30e88f77a829f61fb3509d5cddad2e666cc61453640d300ee |
| test-vectors.json | d0f1a6be7c126e7a0f569b448e159baf92232081c6ae34c3476e5fdb1e6c14a9 |
| reference-evaluation.md | 3273c808a5d195ce40e231a962e07e0d32e8904210909f35432c275ed94bea81 |

## Remaining Authority and Limits

DD-9..DD-12, R8-R11 and AC10-AC15 were formally ratified in the officer's
BRNS-CONFIRM topic=external-reference-ingestion on 2026-10-06. Task 0.6 is complete
and P0 HOLD explicitly released by that decision, not by lint or the designed label.
See design.md for the decision-ID cross-reference correction. Runtime, vendor support, physical clearance,
license compatibility clearance and upstream numerical claims remain unmeasured.
No rendered diagram or visual acceptance is claimed. Existing child files and
active seam work were not modified.
