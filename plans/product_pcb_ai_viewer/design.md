# Design: bodesign — AI PCB Design Copilot (MCP)

> The build queue, full-lifecycle node table, and per-gap status live in `tasks.md` §1–7 (authoritative). This file holds the architecture and the decision record.

## Architecture

- **Core engine = KiCad's circuit-design capability** across the full lifecycle (schematic → layout → simulation/verification). Principle: *whatever KiCad can do, wrap it in.*
- **Surface = docxmcp-style file/folder processor.** Ingest a whole client folder, operate via MCP tools, emit files back. No web UI (retired).
- **State = the folder itself.** No separate state file to drift; `package_readiness` computes the compass on demand from folder contents.
- **Interaction = prompt-driven, agent-as-wizard.** Loop: read compass → one next step → ask for raw data/decision → harvest/compose → emit + readable companion → validate (`kicad-cli` + reference cross-check) → recompute compass.
- **Division of labour:** bodesign builds the forward-generation/surface/state/trust layer; orchestrates mature skills (`kicad`/`kidoc`/`emc`/`spice`/`datasheets`/`bom`/distributors/fab) for analysis/docs/sim/sourcing/fab.
- **Verification & trust (for a non-EE owner):** (1) deterministic `kicad-cli` ERC/DRC + netlist; (2) reference cross-check vs a known-good shipped product (control group) with provenance; (3) analysis skills + EE/user approval for novel parts. "Submittable" = readiness% + cross-check coverage + skill checks + approval.

The full-lifecycle node→tool→owner→status map (N1–N19) is in `tasks.md` §3.

## Decisions

- **DD-1** No web UI; docxmcp-style file/folder surface, prompt-driven. The earlier FastAPI web dashboard is retired/legacy. *Rationale: the owner produces documents via conversation + raw data, not a GUI; the web layer was mostly placeholder.*
- **DD-2** bodesign builds only the forward-generation gap; everything else orchestrates existing skills. *Rationale: `kicad`/`kidoc`/`emc`/`spice`/`datasheets`/`bom` already cover analysis/docs/sim/sourcing/fab; no analysis tool does spec→schematic generation.*
- **DD-3** Reliability is demonstrated by reference cross-check against a known-good shipped product (control group), not asserted. *Rationale: a non-EE owner cannot judge EE correctness; agreement with a shipping board is evidence they can act on; divergences are surfaced with provenance.*
- **DD-4** AI does not synthesize pin-level netlists from scratch; it starts from dev-board datasheets/reference designs and composes subsystems. *Rationale: from-scratch netlist synthesis is unsolved and unverifiable; reference-grounded reuse is high-confidence.*
- **DD-5** The package folder is the state (no separate `.state.json` for deliverable status). *Rationale: one source of truth, no drift; the readiness compass is computed.*
- **DD-6** Format policy: any non-readable engineering file ships with a readable companion (pdf/png/svg/xlsx); md/csv/html/docx/pdf/xlsx/png/pptx acceptable. *Rationale: the owner must be able to view every artifact in native apps; professional vendor files (.kicad_sch/Gerber) still generated but paired with a viewable version.*
- **DD-7** V1 of the driving product is OpenMV-derived (single corpus, WiFi/BLE); cellular (Nordic nRF9151) deferred to V2. *Rationale: OpenMV already provides complete WiFi/BLE + NPU + camera + mic + power; single-reference V1 is the strongest candidate for a complete, verifiable design.*
- **DD-8** No send-to-fab output without deterministic validation + explicit approval. *Safety invariant.*

## Code anchors

- `packages/reverse-core/bodesign_reverse_core/project_ingest.py` — N1 folder ingest.
- `packages/reverse-core/bodesign_reverse_core/companion_render.py` — N3 companion rendering (G1).
- `packages/reverse-core/bodesign_reverse_core/doc_emit.py` — N5 md → docx/pdf doc emitter (G4).
- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py` — N11 schematic emit + `kicad-cli` validation (multi-source `load_symbol`).
- `packages/eda-bridge/bodesign_eda_bridge/composer.py` — N10 generalized subsystem composer (G3).
- `packages/eda-bridge/bodesign_eda_bridge/pin_allocation.py` — N13 pin/GPIO allocation table (G5).
- `packages/eda-bridge/bodesign_eda_bridge/kicad_symbol.py` — N8 symbol generation (`emit_kicad_symbol` generic + ST pin-table variant) (G6).
- `packages/eda-bridge/bodesign_eda_bridge/footprint_map.py` — N9 footprint mapping (R3).
- `packages/eda-bridge/bodesign_eda_bridge/layout.py` — N14 layout via pcbnew + DRC + render (G8).
- `packages/eda-bridge/bodesign_eda_bridge/fab.py` — N15 fab outputs via kicad-cli (G9).
- `packages/eda-bridge/bodesign_eda_bridge/bom_export.py` — N12 BOM + netlist export via kicad-cli (G12).
- `packages/eda-bridge/bodesign_eda_bridge/simulate.py` — N16 SPICE orchestration (kicad analyzer + spice skill).
- `packages/workflow-core/bodesign_workflow_core/requirement_planning.py` — N4 requirements→plan (R5).
- `packages/workflow-core/bodesign_workflow_core/evidence_sourcing.py` — N6 evidence sourcing (R6).
- `packages/workflow-core/bodesign_workflow_core/package_readiness.py` — N18 readiness compass (G2).
- `packages/workflow-core/bodesign_workflow_core/reference_crosscheck.py` — N19 reference cross-check / trust (G7).
- `packages/workflow-core/bodesign_workflow_core/gap_report.py` — N18 gap report (R1).

## Deployment — MCP server (mirrors docxmcp)

bodesign is delivered as an **MCP server**, packaged like `docxmcp`:
- **DD-9** Primary delivery = an MCP server exposing the bodesign tools; the FastAPI web app (`services/api`) is legacy/optional (the surface is MCP + files, not a UI). Built on the `mcp` Python SDK (`mcp.server.Server`) + starlette/uvicorn — the docxmcp stack.
- **DD-10** Transport = MCP Streamable HTTP. **Local: UDS** (`uvicorn --uds <sock>`, the docxmcp default); **external: TCP** `--host/--port`. Also `stdio` for direct IDE/agent use.
- **DD-11** File transfer = token-based upload/download over the same endpoint (clients submit whole project folders / datasheets; tool results reference produced files by token), mirroring docxmcp's `/files` + `stage_dir`.
- **DD-12** Packaged as a **per-user Docker container** (`Dockerfile` + `docker-compose.yml`): image bundles KiCad 9 (`kicad-cli` + `pcbnew`) + LibreOffice + pygerber + the `mcp` SDK; `./.run/<sock>` bind for the UDS rendezvous + named volumes for cache/sessions; socket healthcheck. Image is heavy (~GB) because KiCad/LibreOffice are required by the tools — accepted for portability.
- **DD-13** Operated by **`mcpctl.sh`** (start / stop / reload / status / log), docker-compose-backed (the FastAPI `webctl.sh` is superseded).
- **DD-14** File model has **full docxmcp parity (G11)**: the client's project tree is uploaded as a **tarball** (`POST /files`, `application/x-tar`/gzip) or via a **`bodesign_stage_dir`** tool (inline `{relpath:{content,encoding}}` map) into a fresh **token** namespace whose `doc_dir` *is* the project tree inside the container; tools accept a `token` and operate inside its `doc_dir` (path args resolved relative to it), with no host data bind mount; produced files are surfaced as `{token, rel}` + a `GET /files/{token}/blob/{rel}` URL (snapshot-diff of the token dir, like docxmcp DD-10). Host-path mode stays for the local same-host UDS case.

## Pending design (build queue, see tasks.md §4)

G6/G3 execution on the V1 device; G10 MCP server packaging (server + mcpctl.sh + Docker + mcp.json). Orchestration wiring: `spice`/`emc`, `kidoc` doc packages (unlocked by G8), `datasheets` extraction.
