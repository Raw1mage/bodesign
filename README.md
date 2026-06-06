# bodesign

**bodesign** is an AI PCB-design copilot, delivered as a **standalone MCP server**.
Driven by conversation and raw input files, it walks the full KiCad design lifecycle —
schematic → layout → fab — and produces a manufacturer-ready document package, while
*demonstrating* reliability (cross-check against a known-good reference + KiCad/SPICE/EMC)
rather than asserting it.

It is **host-agnostic and independently operable**: any MCP-capable client (IDE, agent, or
your own HTTP caller) drives it over a Unix socket (local) or a TCP port (external). No host
shell or gateway is required.

## What it does

- **Ingest** a whole project tree (datasheets, schematics, BOM, Gerbers) read-only.
- **Plan** requirements from a natural-language spec (with clarifying questions).
- **Generate** KiCad symbols + a `kicad-cli`-validated schematic from reference-grounded evidence.
- **Lay out** (footprint placement + DRC via `pcbnew`) and **export fab** outputs (gerbers/drill/pos/STEP).
- **Verify** in four layers: ERC/DRC · reference cross-check (control group) · SPICE · EMC/thermal.
- **Track readiness** and emit shareable docs (docx/pdf) + readable companions for every engineering file.

Architecture overview: [IDEF0 functional decomposition](plans/product_pcb_ai_viewer/idef0.svg) ·
[GRAFCET runtime](plans/product_pcb_ai_viewer/grafcet.svg) · full spec in
[`plans/product_pcb_ai_viewer/`](plans/product_pcb_ai_viewer/README.md).

## Run

**Docker (portable, recommended)** — bundles KiCad 9 (`kicad-cli` + `pcbnew`) + LibreOffice + the toolchain:

```bash
./mcpctl.sh start     # build image + start container (UDS at ./.run/bodesign.sock + TCP :8077)
./mcpctl.sh status    # health + socket
./mcpctl.sh log       # follow logs
./mcpctl.sh stop
```

**Host (no Docker)** — needs `kicad-cli` + `pcbnew` + `soffice` + `ngspice` on PATH:

```bash
pip install -r services/mcp/requirements.txt
python services/mcp/server.py --transport http --uds .run/bodesign.sock --port 8077
# or --transport stdio for direct IDE/agent use
```

## Connect (MCP)

MCP **Streamable HTTP**, served concurrently over UDS (local) and TCP (external):

- Local: `unix:///…/.run/bodesign.sock:/mcp/`
- External: `http://<host>:8077/mcp/`

See [`mcp.json`](mcp.json) for the registration manifest. Open `/` (or `http://<host>:8077/`)
for the live, self-documenting guide — install, the file model, the circuit-design workflow,
and the full tool-call schemas at `/tools` and `/tools/{name}`.

## File model (docxmcp-style)

bodesign ships **no working data**. Upload a project tree as a tarball → a **token**; pass the
token to any tool (path args resolve inside the token's `doc_dir`); download produced files by token.
Server-side session data is TTL-garbage-collected. Tools also accept plain host paths for local use.

```bash
tar -C myproject -cf - . | curl --unix-socket .run/bodesign.sock \
     -X POST -H 'Content-Type: application/x-tar' --data-binary @- http://bd/files
curl --unix-socket .run/bodesign.sock http://bd/files/{token}/blob/{rel}
```

## Skill suite

bodesign generates; it orchestrates a mature **EDA skill suite** for analysis/docs/sim/sourcing/fab
(`kicad`, `kidoc`, `spice`, `emc`, `datasheets`, `bom`, distributors, fab). The suite is downloadable
from the running service at `/skills/` (bundle + per-skill); install under your skill location.

## Layout

- `services/mcp/` — the MCP server (`server.py`), token file store, requirements, the skill-pack assets.
- `packages/` — the generic capability libraries (ingest, compose, layout, fab, BOM, verify, …).
- `plans/product_pcb_ai_viewer/` — the design spec (proposal / design / tasks / IDEF0 / GRAFCET).

## Reliability boundary

Cross-check + SPICE/EMC are **pre-silicon risk layers** — they catch problems before prototyping.
They do not replace accredited EMC / EVT / DVT at the lab/factory, and bodesign emits no send-to-fab
output without deterministic validation + explicit approval.
