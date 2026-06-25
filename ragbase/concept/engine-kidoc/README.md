---
slug: concept/engine-kidoc
title: kidoc documentation engine
layer: ragbase
type: concept
confidence: verified
---
# kidoc documentation engine

The kidoc documentation engine (`engines/kidoc/scripts/`) generates formal engineering documents + styled PDFs for any stage emitting a deliverable doc (C03/C04/C06/C07). Report types: HDD (hardware design description), CE technical file, ICD (interface control document), design_review, manufacturing (transfer package), plus power-analysis and schematic-review packages. It renders schematic/PCB SVGs and block/power-tree/bus diagrams.

Entry points: `kidoc_scaffold.py --project-dir <dir> --type <hdd|ce_technical_file|icd|design_review|manufacturing|power_analysis> --analyze --output <md>` (auto-runs the available analyses and emits a structured markdown scaffold pre-filled from real data) then `kidoc_generate.py` for the styled PDF. The markdown is the human-editable source of truth; the PDF is regenerable. Preserve every finding's `confidence` + `evidence_source` from the analyzers through the document — never launder them into bare assertions. `--analyze` is required on a first run; on a pure draft with no board file there is nothing to analyze, so hand-author from the template instead.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/engines/kidoc/engine/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.engines.kidoc.engine.md]] @ engines/kidoc/ENGINE.md — source_weight 5

## Related

- ← `references` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- ← `references` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]
- ← `references` [[workflow/c07-mfg|C07 MFG — manufacturing-transfer readiness]]

