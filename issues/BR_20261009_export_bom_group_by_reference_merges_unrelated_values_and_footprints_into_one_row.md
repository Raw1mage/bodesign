---
id: BR_20261009_export_bom_group_by_reference_merges_unrelated_values_and_footprints_into_one_row
title: bodesign_export_bom with group_by:"Reference" merges components with different value/footprint into one CSV row, so per-ref BOM coverage cannot be decided from the served output
date: 2026-10-09
status: open
severity: medium
priority: P2
component: services/mcp/server.py (_h_export_bom), packages/eda-bridge BOM export
reporter_session: ses_04db7a1c5ffelvbxyLP1p6xlRH
edges:
  - to: plans/eda-bridge_unified-collaborative-rebuild/tasks.md#3.5
    type: surfaced-by
  - to: plans/eda-bridge_unified-collaborative-rebuild/s3-formalisation-receipt-20261009.md
    type: evidence
---

## Symptom

Served `bodesign_export_bom` on the S36 six-leaf set (`experiments/s3-formal/c03_engine-v1/`,
repo HEAD `f8148a2`) returns `status: ok` on every leaf, yet with `group_by: "Reference"` the
CSV still aggregates components whose value AND footprint differ. Raw `power_rail` row:

```
"C2-C5","10uF/16V,1uF/10V,22uF/10V","Capacitor_SMD:C_0402_1005Metric,Capacitor_SMD:C_0805_2012Metric","4",""
```

R3/R4/R6 likewise merge `2k` and `100k`. Every success response also carries
`component_count: 0`, so neither the row count nor the metadata can answer "does the BOM
cover the 45 declared refs with the right value/footprint". Raw SSE + CSV per leaf are
retained in `~/products/bodesign/outputs/btdongle_ms/c03_engine-v1/bundle/bom/`.

## Why it matters

Task 3.5 requires a same-revision BOM cross-checked against the declared spec. The served
tool is the formal path; a success that cannot support the cross-check is success-but-lossy,
which is the shape AGENTS.md §2.1 forbids (the output looks complete while the decision it is
meant to support is undecidable). The 3.5 bundle therefore carries a per-ref BOM normalized
from the root native netlist with the method named (`bom_crosscheck.json`: 45/45, 0 missing,
0 extra, 0 mismatch) and keeps the served CSVs only as raw evidence.

## Expected

- `group_by: "Reference"` → one row per reference designator, no range collapsing.
- Grouping by value (the default) must only merge rows whose value AND footprint are equal.
- `component_count` reflects the components actually exported, not 0.

## Not measured

Whether the merge happens in the exporter or in the CSV writer; whether `kicad-cli sch
export bom` is involved. Reproduce: `bom-response-power_rail.sse` in the bundle.
