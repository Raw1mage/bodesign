# bodesign EDA skill pack

The mature EDA skills that the **bodesign** MCP server orchestrates (analysis · docs ·
simulation · sourcing · fabrication). bodesign *generates* the design; these skills
*verify, source, and document* it. Reviewed and cleaned for distribution
(no secrets — all distributor API keys are read from environment variables;
no `__pycache__`/personal paths/internal ticket refs).

> **`kicad` and `kidoc` are now folded into the unified `bodesign` skill** (as `engines/kicad`
> and `engines/kidoc`). Prefer installing the `bodesign` skill — it carries the C00–C07 workflow,
> drives this MCP's `bodesign_*` generation tools, and the MCP's verification tools resolve its
> analyzer via `BODESIGN_KICAD_SKILL` (default `~/.claude/skills/bodesign/engines/kicad`). The
> standalone `kicad.tar.gz` / `kidoc.tar.gz` below remain for legacy/standalone use only.

## Install

These are Claude **skills**. Place each skill directory under your skill location
(default `~/.claude/skills/`):

```
tar -xzf bodesign-eda-skills-bundle.tar.gz -C ~/.claude/skills/
# or a single skill:
tar -xzf kicad.tar.gz -C ~/.claude/skills/
```

No install script is bundled by design — extract where your skill manager expects them.

## Contents

| Skill | Role |
|---|---|
| **kicad** | Schematic/PCB/Gerber analysis — ERC/DRC, netlist, power tree, subcircuit detection, design review. The hub the others feed. |
| **kidoc** | Engineering doc packages — HDD, CE technical file, ICD, design-review, manufacturing-transfer; schematic/PCB renders + block/power-tree diagrams. |
| **spice** | ngspice simulation of detected subcircuits (filters, dividers, op-amp gain, LC/crystal). |
| **emc** | EMC pre-compliance risk analysis (FCC/CISPR) on schematic + PCB. |
| **datasheets** | Extract pinouts/specs from datasheet PDFs; consumed by the analyzers (import-only modules). |
| **bom** | BOM orchestrator — coordinates the distributor + fab skills; create/enrich/price/order BOMs. |
| **digikey / lcsc / element14 / mouser** | Part search, pricing, stock, datasheet download per distributor. |
| **jlcpcb / pcbway** | Fabrication + assembly: design rules, capabilities, ordering workflow (doc-only). |

## Environment variables (sourcing skills)

Only set what you use; nothing is hardcoded:

- **digikey**: `DIGIKEY_CLIENT_ID`, `DIGIKEY_CLIENT_SECRET` (OAuth)
- **mouser**: `MOUSER_SEARCH_API_KEY`
- **element14**: `ELEMENT14_API_KEY`
- **lcsc**: none (community API)

## Notes

- Several skills cross-reference each other (e.g. `bom` drives the distributors; `emc`/`spice`
  consume the `kicad` analyzer's JSON; `datasheets` is imported by `kicad`). Install the ones
  you need plus their referenced siblings.
- OAuth tokens are cached in an XDG-private dir (`$XDG_RUNTIME_DIR`/`$XDG_CACHE_HOME`), not `/tmp`.
- Pairs with the bodesign MCP server (see the `/` landing page of the bodesign service).
