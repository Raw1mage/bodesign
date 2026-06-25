---
slug: concept/skill-mcp-relationship
title: Skill ↔ MCP server relationship (generation vs validation)
layer: ragbase
type: concept
confidence: verified
---
# Skill ↔ MCP server relationship (generation vs validation)

The bodesign **skill** is the workflow brain + analysis/doc engines; the optional bodesign **MCP server** (separate Docker/stdio service) is the generation half. The split is bidirectional: **skill → MCP for generation** (when tools prefixed `bodesign_` are reachable, use them to *create* KiCad artifacts instead of hand-authoring); **MCP → skill for analysis** (`bodesign_simulate`/`analyze_emc`/`analyze_thermal` call the very engines under `engines/kicad` + spice/emc, via `BODESIGN_*_SKILL`). So analyzer logic lives once, in the skill.

**Generation is not validation.** Whatever the MCP emits is still `draft`/`pending` until you run the local analyzers (`analyze_schematic.py`/`analyze_pcb.py`) and gates over it. The MCP refuses send-to-fab output without deterministic validation + explicit approval — mirror that. The server is self-describing: open `/tools` and `/tools/{name}` for current schemas; never hardcode tool schemas from the skill's router table.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/skill/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.skill.md]] @ SKILL.md spine: lifecycle table, router, DoD, design-review G2, debug-cost G6, MCP relationship — source_weight 5

## Related

- → `references` [[concept/engine-kicad|KiCad analysis engine (the deterministic verifier)]]

