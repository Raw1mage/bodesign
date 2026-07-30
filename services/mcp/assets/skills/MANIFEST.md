# bodesign skill downloads

The **bodesign** MCP server publishes two skill layers, and they are served by two
different mechanisms — the distinction matters when you automate a download.

**1. Declared skills — built live, always current.** `bodesign` (the canonical
C00–C07 lifecycle skill) and `bodesign-kb` (the refs-derived client contract) are
packed ON DEMAND from the repo tree `mcp.json skillPaths` declares. Enumerate and
fetch them through the MCP-Integration-Standard R9 endpoints:

```
GET /skills                 -> {"skills":[{"name":"bodesign", ...}], "bundles":[...]}
GET /skills/<name>.zip      -> the archive        <- `.zip` is the ENDPOINT's suffix
GET /skills/<name>.tar.gz   -> same tree, gzip    <- convenience, same bytes
```

The listed `name` is a **bare skill name**, never a filename — append `.zip`
yourself. (Before 2026-07-30 this listing advertised filenames and served only
`.tar.gz` from a hand-frozen snapshot; a conformant client dialled
`bodesign.tar.gz.zip` and got a 404 while the snapshot silently rotted 7 weeks out
of date. Both halves are now one source, asserted at startup.)

**2. Vendored EDA companion bundles — static files.** The 13 archives listed under
`bundles` (`bodesign-eda-skills-bundle.tar.gz` and the per-skill tarballs) have no
source tree in this repo, so they cannot be rebuilt on demand and are NOT
advertised as R9 skills. Fetch them by filename: `GET /skills/<file>.tar.gz`.

All are reviewed and cleaned for distribution (no secrets — all distributor API
keys are read from environment variables; no `__pycache__`/personal paths/internal
ticket refs; no symlinks).

> **`kicad` and `kidoc` are folded into the unified `bodesign` skill** (as
> `engines/kicad` and `engines/kidoc`). Prefer installing the live `bodesign`
> skill (`GET /skills/bodesign.zip`): it
> carries the C00–C07 workflow, drives this MCP's `bodesign_*` generation tools,
> and the MCP's verification tools resolve its analyzer via `BODESIGN_KICAD_SKILL`
> (`~/.claude/skills/bodesign/engines/kicad` on a host install). The bodesign
> **container image self-bundles** the kicad/spice/emc analyzer engines (under
> `/opt/bodesign-engines`) and sets `BODESIGN_KICAD_SKILL` / `BODESIGN_SPICE_SKILL`
> / `BODESIGN_EMC_SKILL`, so C06 simulate/EMC/thermal run without a host skill
> install — these tarballs are for host/standalone use. The standalone
> `kicad.tar.gz` / `kidoc.tar.gz` below remain for legacy/standalone use only.

## Install

These are Claude **skills**. Place each skill directory under your skill location
(default `~/.claude/skills/`):

`<base>` below is the HTTP base URL of whatever gateway fronts this service.
The container does **not** publish a TCP port to the host (BR_20260730d), so
there is no `http://<host>:8077` to dial directly.

```
# declared skills — always current, fetched by BARE NAME + the endpoint's suffix
curl -fO <base>/skills/bodesign.zip && unzip -d ~/.claude/skills/ bodesign.zip
curl -fO <base>/skills/bodesign-kb.zip && unzip -d ~/.claude/skills/ bodesign-kb.zip

# vendored EDA bundles — fetched by FILENAME
curl -fO <base>/skills/bodesign-eda-skills-bundle.tar.gz
tar -xzf bodesign-eda-skills-bundle.tar.gz -C ~/.claude/skills/
# or a single one:
tar -xzf kicad.tar.gz -C ~/.claude/skills/
```

Archives wrap their contents in a `<name>/` directory, so extracting straight into
your skills dir lands `~/.claude/skills/bodesign/SKILL.md`.

No install script is bundled by design — extract where your skill manager expects them.

## Contents

| Skill | Role |
|---|---|
| **bodesign** | Canonical C00–C07 hardware product-design lifecycle: PRD → ID → ME → EE → Layout → FW → Verify → MFG. |
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
