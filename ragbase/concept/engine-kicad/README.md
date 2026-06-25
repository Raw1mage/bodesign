---
slug: concept/engine-kicad
title: KiCad analysis engine (the deterministic verifier)
layer: ragbase
type: concept
confidence: verified
---
# KiCad analysis engine (the deterministic verifier)

The KiCad analysis engine (`engines/kicad/scripts/`) is the deterministic verifier behind C03/C04/C06. You do not eyeball a design and assert it correct — you run a script, read structured JSON, and carry every finding with its `confidence` (`deterministic`/`heuristic`/`datasheet-backed`) + `evidence_source`. The output envelope carries the honesty model: each finding has `rule_id`, `detector`, `severity`, `confidence`, `evidence_source`, and a `trust_summary` rolls up `trust_level` + `provenance_coverage_pct`.

Key scripts: `analyze_schematic.py` (components/BOM, full nets, subcircuit detection, IC pinout, power analysis, ERC; `--lifecycle`, `--schema`, `--stage/--audience`), `analyze_pcb.py --full` (copper presence at every pad — catches the floating-part bug — fanout, per-net length, DFM), `cross_verify.py` / `cross_analysis.py` (schematic-intent ↔ PCB implementation, the C06 control-group check), `fab_release_gate.py` (structured PASS/WARN/FAIL/INCOMPLETE; `--strict`), `lifecycle_audit.py` (component obsolescence/temp), `what_if.py` (recompute divider/filter/Vout), `diff_analysis.py` (revision deltas). Bridges to sibling `datasheets`/`emc` engines via symlinks. The bodesign MCP's `simulate`/`analyze_emc`/`analyze_thermal` call these very scripts back — the analyzer logic lives once, here.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/engines/kicad/engine/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.engines.kicad.engine.md]] @ engines/kicad/ENGINE.md — source_weight 6

## Related

- ← `references` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- ← `references` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]
- ← `references` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]
- ← `references` [[concept/skill-mcp-relationship|Skill ↔ MCP server relationship (generation vs validation)]]

