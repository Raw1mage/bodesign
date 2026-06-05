# Technology Research: Gerber-to-Source Reconstruction and Validation

## Recommended Starting Stack

- Core design engine: product-owned `BoardDesign IR`, not `pygerber`.
- EDA bridge: KiCad file/CLI ecosystem should be the first practical export/validation bridge, even if KiCad is not the user-facing UI.
- Autorouting candidate: `freerouting/freerouting` for DSN/SPECCTRA-based routing experiments after IR and placement constraints exist.
- Circuit/netlist helper candidate: `skidl` for code-first schematic/netlist generation and ERC-style checks when OpenMV documents need to become structured circuit evidence.
- Original source files are not assumed. The product reconstructs an editable source-layout model from Gerber/artwork, drill, IPC netlist, routing/report files, and user annotations.
- Backend Gerber inspection/render adapter: `pygerber` from `Argmaster/pygerber`.
- IPC-356 netlist and drill parsing are first-class inputs for recovering net and hole evidence.
- Frontend renderer: custom Canvas 2D viewer driven by original manufacturing geometry, reconstructed source objects, confidence overlays, and regenerated Gerber/SVG layers.
- Reference viewer pipeline: `tracespace/tracespace` for Gerber layer identification, parsing/rendering concepts, SVG pipeline, and fixture inspiration.
- DFM/rule checks: start with deterministic checks on normalized source objects and generated Gerbers; treat mature tools such as `gerbv` as reference/optional CLI comparison, not core dependency.
- Persistence: Postgres for project/job/finding/proposal state.

## Candidate Projects

| Project | Role | Evidence | Fit | Risk |
| --- | --- | --- | --- | --- |
| `KiCad/kicad-source-mirror` | EDA reference implementation and export bridge | GPL-3.0, active, 2746 stars, PCB/schematic/Gerber ecosystem | Best practical bridge for `.kicad_pcb`, DRC/export semantics, and later CLI integration | GPL/runtime dependency and local install complexity; not present in current environment |
| `freerouting/freerouting` | PCB autorouter | GPL-3.0, active, 1732 stars, DSN/SPECCTRA, KiCad-related topics | Best open-source autorouting candidate after placement/constraints exist | GPL and routing quality constraints; not a replacement for our IR/kernel |
| `skidl` | Code-first circuit/netlist generation | MIT, PyPI 2.2.3, supports KiCad 9 netlist/schematic generation, ERC, reusable circuit modules | Strong candidate for OpenMV docs → structured circuit/netlist evidence | Schematic/circuit layer, not PCB layout engine |
| `kinparse` | KiCad netlist parser | MIT, PyPI 1.2.4, supports KiCad V5-V9 netlists | Useful if KiCad netlists become an interchange format | Does not solve layout/routing |
| `sexpdata` | S-expression parser/serializer | BSD, PyPI 1.0.2 | Useful for direct KiCad `.kicad_pcb`/`.kicad_sch` file manipulation if needed | Generic parser only; schema handling remains ours |
| `Argmaster/pygerber` | Python Gerber parser/render toolkit | MIT, Python, PyPI `pygerber` 2.4.3, supports X3/X2/RS-274X/RS-274D, API + CLI, PNG/SVG rendering | Best backend fit for FastAPI MVP | Need verify geometry/introspection APIs expose enough primitives for DRC and patching |
| `tracespace/tracespace` | JS PCB visualization pipeline | MIT, TypeScript, 941 stars, packages for parser/plotter/renderer/layer identification | Strong reference for browser-oriented rendering and layer semantics | Maintainer states project is on indefinite hiatus; avoid hard dependency for core product |
| `gerbv/gerbv` | Mature Gerber viewer engine | GPL-2.0, C, maintained fork, 249 stars | Useful reference and possible local comparison tool | GPL and native dependency make it risky as embedded product dependency |
| `elephantech/PyGerbv` | Python wrapper for libgerbv | MIT wrapper, Python | Possible bridge to gerbv rendering/conversion | Still depends on libgerbv/GPL ecosystem; needs license review |
| `curtacircuitos/pcb-tools` | Legacy Python PCB/Gerber tools | Apache-2.0, 312 stars | Historical reference only | Archived; avoid as primary dependency |
| `xingrz/GerberViewer` | Browser Gerber viewer | Apache-2.0, Vue, 99 stars | UI inspiration and behavior reference | Vue-specific, not ideal for React architecture |

## Reverse-to-source Plan Change

The product should be framed as reconstructing a useful editable source-layout model from manufacturing outputs. Gerber is analogous to a manufacturing print/export and cannot fully preserve original schematic/layout intent, but Gerber plus drill plus IPC netlist can provide enough evidence to infer pads, vias, tracks, zones, nets, and component clusters. AI-assisted layout planning should modify the reconstructed model through constrained typed operations, then regenerate Gerbers for validation and delivery.

## Local Data Assessment

- Rockbox is an excellent first reconstruction fixture: Allegro-generated RS-274X `.art` layers identify `ROCKBOX_V2.brd`, Cadence Allegro 22.1, 6 copper layers, inch units, and format 5.5.
- Rockbox IPC-D-356A is especially valuable because it includes board/layer metadata, padstack tables, named nets, component reference designators, pin numbers, coordinates, pad sizes, side indicators, and vias.
- Rockbox drill output includes plated and non-plated hole sizes/counts plus absolute drill coordinates, useful for via and mechanical-hole reconstruction.
- Rockbox `.rou` appears to describe routing/profile paths and can help with slots/routes or panel/mechanical features.
- OpenMV currently appears to be a reference/design-target folder with schematic PDF and datasheets, not a Gerber/source reconstruction fixture.

## Selection Rationale

### EDA Kernel

Use our own `BoardDesign IR` as the core EDA kernel because neither `pygerber` nor KiCad should own the product's reasoning model. The IR should model components, footprints, pads, nets, traces, vias, zones, stackup, constraints, placement intent, routing intent, evidence, and confidence. This keeps OpenMV document generation and Rockbox reverse reconstruction converging into one middle layer.

### KiCad Bridge

Use KiCad as the first practical EDA bridge, not the core product model. KiCad gives a mature file format, DRC/export semantics, Gerber generation path, and ecosystem compatibility. The product should generate/import KiCad-compatible artifacts only through adapters so the IR remains independent.

### Routing

Do not build routing around AI text output. Routing should be deterministic or constraint-driven. `freerouting` is the best initial open-source autorouting candidate because it uses DSN/SPECCTRA and is actively maintained, but it should be introduced only after the IR can emit placement, nets, keepouts, design rules, and routing constraints.

### Circuit Evidence

Use `skidl` as an optional circuit/netlist evidence layer for the OpenMV path. It can turn extracted component/pin/net intent into structured code-first circuits and KiCad netlists, but it does not replace layout/placement/routing.

### Parser

Use `pygerber` first for Gerber/artwork inspection because it aligns with the chosen FastAPI backend and offers a maintained Python package with parser, tokenizer, rendering, SVG support, and language-server/introspection tooling. Add drill and IPC parsers to recover hole and net evidence. Build a product-owned reconstructed source model rather than depending on original EDA source files.

### Viewer

Use Canvas 2D in React for MVP because it gives direct control over original layer toggles, reconstructed object selection, confidence overlays, measurements, findings, and proposed patch previews. SVG output from original/regenerated Gerbers can supplement the reconstructed-source viewer.

### DRC / Error Detection

Start with deterministic backend checks on normalized manufacturing evidence, reconstructed objects, and regenerated Gerbers rather than relying on AI or external DRC. First rules should include missing net evidence, low-confidence component grouping, file/layer completeness, parse warnings, board outline detection, drill proximity checks, suspicious clearance thresholds, and proposal operation validation.

### AI Modification Workflow

AI should never modify files directly. It should generate typed reconstructed-source patch proposals, each validated by deterministic code and previewed in the UI before user approval. Gerbers should be regenerated from approved reconstructed-source changes whenever possible.

## Recommended First Experiments

1. Use Rockbox as the first private reconstruction fixture and classify all `.art`, `.drl`, `.ipc`, `.rou`, stackup, and PDF artifacts.
2. Install `pygerber[svg]` in a backend sandbox and inspect Rockbox Gerber/artwork layers.
3. Parse Rockbox IPC-D-356A and drill files into evidence schemas.
4. Build a normalized reconstructed PCB source model independent from parser internals.
5. Reconstruct board outline, pads, vias, tracks, zones, and net assignments with confidence scores.
6. Render original outputs plus reconstructed source objects in React Canvas.
7. Use OpenMV schematic/datasheets to define subsystem heuristics for NPU/processor, flash, PSRAM, camera/MIPI, mic, comms, and power layout review.
8. Implement one reverse-layout check end-to-end: low-confidence net/component inference → finding → AI explanation → typed proposal → user preview.

## Open Risks

- KiCad and freerouting are GPL, so embedding/linking/distribution strategy needs license review. Running external user-installed tools or service-side tools may be acceptable, but must be decided deliberately.
- KiCad CLI is not available in the current environment, so early scaffold should abstract the EDA bridge behind interfaces and not require KiCad installed on day one.
- Autorouting without strong placement and constraints will produce poor boards; AI must first generate constraints and placement intent.
- Reconstruction cannot guarantee the original schematic, original constraints, or original EDA project fidelity.
- IPC netlist availability heavily affects net reconstruction quality.
- Component recognition from Gerber alone will need confidence scoring and user annotation.
- Regenerating Gerbers requires a product-owned exporter or a chosen export target such as KiCad.
- Direct Gerber patching should be limited to fallback/low-risk cases; the main path should be reconstructed-source edits.
- `tracespace` is attractive but should remain reference-only unless we accept maintenance risk.
- GPL dependencies such as `gerbv` should not be embedded without license review.
