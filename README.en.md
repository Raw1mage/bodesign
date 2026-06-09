# bodesign

_Language: [繁體中文](./README.md) · **English**_

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

## Architecture diagrams

Full spec in [`specs/product/pcb_ai_viewer/`](specs/product/pcb_ai_viewer/README.md).

**IDEF0 functional decomposition (A0)**

![IDEF0 functional decomposition](specs/product/pcb_ai_viewer/idef0.svg)

**GRAFCET runtime (generation loop)**

![GRAFCET runtime](specs/product/pcb_ai_viewer/grafcet.svg)

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

## Skill pairing

bodesign (the MCP) is the **generation half**; its companion **`bodesign` skill** is the workflow
brain (the C00–C07 lifecycle, honesty contract, stage SOPs) **and** the analysis/doc engines —
`kicad` (schematic/PCB/Gerber analysis) and `kidoc` (engineering docs) now live there as
`engines/kicad` and `engines/kidoc`, so install the `bodesign` skill rather than the standalone
`kicad`/`kidoc` skills. The split is bidirectional: the skill drives this MCP's `bodesign_*` tools to
*generate*, and the MCP's verification tools (`bodesign_simulate` / `analyze_emc` / `analyze_thermal`)
call the skill's engines to *analyse* (resolved via `BODESIGN_KICAD_SKILL`, default
`~/.claude/skills/bodesign/engines/kicad`).

The remaining mature EDA skills for sim/sourcing/fab (`spice`, `emc`, `datasheets`, `bom`,
distributors, fab) plus the standalone `kicad`/`kidoc` (legacy, now folded into the `bodesign` skill)
are downloadable from the running service at `/skills/` (bundle + per-skill); install under your skill
location.

Above the execution layer the skill adds a **design-judgment** layer (per-stage references: C01
reduction-lens + Ashby material selection, C02 DFM/DFA/IP-sealing + a geometry-authoring loop, C03 EE
advisory + a pinout→circuit synthesis method, C04 stackup/HDI/SI). A cross-stage budget that doesn't
close (area / thermal / height, or a C06 verdict-fail) routes *back* to the owning stage via the
existing `BlockerReturn` and blocks the downstream all-clear (recursive self-correction). A
**feasibility triage** classifies the product from C00 up front (Tier 1 fab-ready · 2 human-SI
sign-off · 3 HDI-class → pro-EDA) so "give C00, get C01–C04" is honest per-product; Tier-3 emits a
neutral SI constraint package (`emit_si_constraint_export`: JSON + CSV + per-tool mapping) so the
routing wall is a clean handoff, not a dead-end.

## Layout

```text
bodesign/
├── services/mcp/                 MCP server — the product's only outward surface
│   ├── server.py                 tool dispatch, token path resolution, dual UDS+TCP binds, self-documenting pages
│   ├── token_store.py            docxmcp-style token file store + TTL/GC
│   ├── requirements.txt
│   └── assets/skills/            EDA skill suite (13 tarballs + bundle + MANIFEST.md)
├── packages/                     generic capability libraries (no product-specific code)
│   ├── shared/                   shared contracts + data_root() (program↔working-data isolation boundary)
│   ├── design-ir/                DesignIntent and other intermediate representations (IR)
│   ├── component-kb/             reusable component knowledge (datasheet harvest)
│   ├── doc-core/                 pin-table / document generation
│   ├── source-core/              source / evidence contracts
│   ├── reverse-core/             project ingest, companion render, doc emit, board reconstruct
│   ├── gerber-core/              Gerber / drill parsing + preview
│   ├── eda-bridge/               KiCad bridge: symbol / schematic / layout / fab / BOM / SPICE / EMC
│   ├── workflow-core/            requirement planning, evidence sourcing, readiness compass, cross-check,
│   │                             feasibility triage (C04 delivery tier), cross-stage reconciliation gate, SI handoff
│   ├── storage-core/             client-owned project registry
│   └── kicad-plugin/             in-KiCad Action Plugin contract (roadmap)
├── specs/                        spec / knowledge base (plan-builder)
│   ├── architecture.md           cross-cutting architecture index
│   ├── product/pcb_ai_viewer/    living product design spec + IDEF0/GRAFCET SVGs + Chinese README
│   └── feature/eda-mcp-toolchain/  living C04 EDA toolchain spec (routing/finishing MCP tools)
├── tests/                        test suite (green on a clean clone; data-dependent tests skip)
├── Dockerfile · docker-compose.yml · mcpctl.sh   container packaging + ops
├── mcp.json                      MCP registration manifest
└── README.md · README.en.md      this document (zh-Hant / English)
```

> bodesign ships **no working data**; client project trees enter only at runtime via the token store, or are read from an external `data_root()` (`BODESIGN_DATA_DIR`).

## Reliability boundary

Cross-check + SPICE/EMC are **pre-silicon risk layers** — they catch problems before prototyping.
They do not replace accredited EMC / EVT / DVT at the lab/factory, and bodesign emits no send-to-fab
output without deterministic validation + explicit approval.
