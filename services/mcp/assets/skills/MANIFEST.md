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

**2. Vendored EDA companion bundles.** The 13 archives listed under `bundles`
(`bodesign-eda-skills-bundle.tar.gz` and the per-skill tarballs) are NOT advertised
as R9 skills — their names are not declared in `mcp.json skillPaths`. Fetch them by
filename: `GET /skills/<file>.tar.gz`. They split two ways:

- **`kicad.tar.gz` / `kidoc.tar.gz` are PROJECTED from this repo**, from
  `skills/bodesign/engines/{kicad,kidoc}`, packed on demand exactly like the
  declared skills. (BR_20260730 round 4, D4: this file previously claimed all 13
  "have no source tree in this repo" — false for these two, and the frozen copies
  being served had drifted 12 files and 9 byte-differences behind the live tree,
  the same shape and the same 7-week staleness this BR opened on. The frozen copies
  can no longer be reached; there is no second artifact left to rot.)
- **The other 11 are static files** with genuinely no in-repo source, so they cannot
  be rebuilt on demand and carry no R9 source-parity claim.

All are reviewed and cleaned for distribution (no secrets — all distributor API
keys are read from environment variables; no `__pycache__`/personal paths/internal
ticket refs; no symlinks).

> **`kicad` and `kidoc` are folded into the unified `bodesign` skill** (as
> `engines/kicad` and `engines/kidoc`), and **are no longer standalone-installable
> skills.** They are ENGINE TREES: they carry `ENGINE.md`, not `SKILL.md`, so a
> skill manager that keys on `SKILL.md` will find nothing. Install
> `bodesign.zip` — it contains both engines at `bodesign/engines/{kicad,kidoc}`.
> (BR_20260730 round 5, Z2: the frozen copies shipped a `kicad/SKILL.md` that the
> live tree does not have, so making them current — correctly — also made them
> non-installable. Both facts were true at once and only one was written down.
> Synthesizing a `SKILL.md` during projection was rejected: it would manufacture
> a declaration no source makes, which is the failure this BR family exists to
> stop. `kicad.tar.gz` / `kidoc.tar.gz` stay reachable — a published URL should
> not 404 on an unrelated fix — but as engine trees, not as skills.)
>
> The MCP's verification tools resolve the analyzer via `BODESIGN_KICAD_SKILL`
> (`~/.claude/skills/bodesign/engines/kicad` on a host install). The bodesign
> **container image self-bundles** the kicad/spice/emc analyzer engines (under
> `/opt/bodesign-engines`) and sets `BODESIGN_KICAD_SKILL` / `BODESIGN_SPICE_SKILL`
> / `BODESIGN_EMC_SKILL`, so C06 simulate/EMC/thermal run without a host skill
> install.
>
> **Known stale copy, disclosed rather than hidden:** the composite
> `bodesign-eda-skills-bundle.tar.gz` still embeds the 2026-06-07 snapshot of
> `kicad/` and `kidoc/` (12 files behind, 9 byte-differences). It has no in-repo
> source, so it cannot be projected like the two above. For current engine
> content use `bodesign.zip`, or `kicad.tar.gz` / `kidoc.tar.gz`, both of which
> are packed live. A test asserts this shadow set does not GROW.

## Install

`bodesign.zip` and `bodesign-kb.zip` are Claude **skills** — extract them under
your skill location (default `~/.claude/skills/`). The vendored `.tar.gz` bundles
are a mixed bag: some carry a `SKILL.md` and install the same way, while the
engine trees (`kicad`, `kidoc`) carry `ENGINE.md` and are NOT installable skills
(see the note above). Check for a `SKILL.md` before treating an archive as one:

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

# engine trees — NOT skills. Packed live from the bodesign skill's engines/.
# They hold ENGINE.md, not SKILL.md; a skill manager will not see them.
curl -fO <base>/skills/kicad.tar.gz
tar -xzf kicad.tar.gz -C /wherever/you/keep/engines
```

Archives wrap their contents in a `<name>/` directory, so extracting straight into
your skills dir lands `~/.claude/skills/bodesign/SKILL.md`.

No install script is bundled by design — extract where your skill manager expects them.

### What the installed skill can and cannot do on its own

`bodesign.zip` ships the guidance (`SKILL.md`, `doctrine.md`, the stage guides) and
the landing dispatcher (`scripts/gate.py`). It does **not** ship the Python packages
the verbs execute — `packages/workflow-core`, `packages/component-kb`,
`packages/eda-bridge`, `packages/reverse-core` live in the bodesign repo, not in the
archive. So from a bare install:

```
python3 gate.py --list          # works — static registry, 0 dependencies
python3 gate.py <verb> ...      # LANDING_PACKAGES_NOT_FOUND unless bootstrapped or BODESIGN_SRC is set
```

To execute landing verbs on a **repo-less client host**, run the Companion CLI's
self-contained bootstrap once — it fetches `/skills/bodesign-runtime.tar.gz` (packed
live from the server's `packages/*` tree), extracts it into
`~/.local/share/bodesign/runtime` (a built-in literal candidate), and verifies every
module via `--doctor`:

```
python3 ~/.claude/skills/bodesign/scripts/gate.py --bootstrap --server <base>
python3 ~/.claude/skills/bodesign/scripts/gate.py --doctor
```

Alternatively, if you already have a local `bodesign` checkout outside the default
candidates (`~/projects/bodesign` or `~/.local/share/bodesign/runtime`), point
`BODESIGN_SRC` at it:

```
BODESIGN_SRC=/path/to/bodesign-repo \
  python3 ~/.claude/skills/bodesign/scripts/gate.py <verb> --repo /abs/project
```

The error is typed and names the fix (`LANDING_PACKAGES_NOT_FOUND`, with a hint
carrying `--bootstrap` and `BODESIGN_SRC`), so this fails loudly rather than
degrading — and the requirement belongs here, at the install step, not only in the
error you hit afterwards (BR_20260730 round 6, Y1).

## Contents

| Name | Installable skill? | Role |
|---|---|---|
| **bodesign** | yes (`SKILL.md`) | Canonical C00–C07 hardware product-design lifecycle: PRD → ID → ME → EE → Layout → FW → Verify → MFG. |
| **kicad** | **no — engine tree** (`ENGINE.md`) | Schematic/PCB/Gerber analysis — ERC/DRC, netlist, power tree, subcircuit detection, design review. The hub the others feed. |
| **kidoc** | **no — engine tree** (`ENGINE.md`) | Engineering doc packages — HDD, CE technical file, ICD, design-review, manufacturing-transfer; schematic/PCB renders + block/power-tree diagrams. |
| **spice** | yes (`SKILL.md`) | ngspice simulation of detected subcircuits (filters, dividers, op-amp gain, LC/crystal). |
| **emc** | yes (`SKILL.md`) | EMC pre-compliance risk analysis (FCC/CISPR) on schematic + PCB. |
| **datasheets** | yes (`SKILL.md`) | Extract pinouts/specs from datasheet PDFs; consumed by the analyzers (import-only modules). |
| **bom** | yes (`SKILL.md`) | BOM orchestrator — coordinates the distributor + fab skills; create/enrich/price/order BOMs. |
| **digikey / lcsc / element14 / mouser** | yes (`SKILL.md`) | Part search, pricing, stock, datasheet download per distributor. |
| **jlcpcb / pcbway** | yes (`SKILL.md`) | Fabrication + assembly: design rules, capabilities, ordering workflow (doc-only). |

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
