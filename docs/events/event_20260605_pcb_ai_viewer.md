# Event: PCB AI Viewer Planning

## 需求

建立 `bodesign` host-agnostic MCP server + web server：agent/IDE 透過 MCP 提供檔案或設計指令；網站註冊在 `/bodesign/`，顯示 Rockbox 電路/PCB view。畫面可來自 Gerber/IPC 逆向重建，也可來自 datasheet/component knowledge 經 AI 生成的 `BoardDesign IR`。MCP server 本身必須能吸收 datasheet/reference documents 成為知識庫，擴大各種晶片與元件資料，以便被要求時能拿出來畫電路。

## 範圍 IN

- Host-agnostic MCP server；opencms、Cursor、Claude Desktop、VS Code 等 IDE/agent client 都可串接。
- `/bodesign/` web server/viewer。
- FastAPI/Python EDA service。
- OpenMV schematic/datasheet/reference document ingestion into design evidence。
- Rockbox Gerber/artwork、drill、IPC netlist、routing/report artifact upload and detection。
- `BoardDesign IR` generation/reconstruction with confidence scores and evidence refs。
- Datasheet/component knowledge normalization for PDFs and heterogeneous documents as Day 1 core capability。
- `/bodesign/` rendering for Rockbox reconstructed circuit/PCB view, original Gerber, generated Gerber, component knowledge, evidence, and confidence overlays。
- MCP knowledge ingestion for datasheets/reference documents so component/chip knowledge can be reused in later design requests。
- Gerber generation/export from `BoardDesign IR` with deterministic validation and user approval gate。

## 範圍 OUT

- 第一版不支援 silent automatic modification。
- 第一版不保證完整取代專業 EDA/DFM 工具。
- 第一版不保證復原原始 schematic、原始 EDA project、原始 constraints 或完整原始設計意圖。
- 出廠測試/debug 指引、任兩點理論電壓/電阻計算延後到後續研究，不納入本階段 MVP。
- 第一版不處理多人協作、付款、組織權限。

## 任務清單

- T1 Define source-ingestion taxonomy and evidence schemas。
- T2 Define ComponentKnowledge, DesignIntent, and BoardDesign IR schemas。
- T3 Scaffold MCP server, FastAPI service, and `/bodesign/` web viewer。
- T4 Implement upload, artifact/document detection, and job model。
- T5 Add OpenMV document-to-knowledge/design planning interfaces。
- T6 Add Rockbox component, Gerber, drill, and IPC-to-IR interfaces。
- T7 Render Rockbox BoardDesign IR and Gerber layers at `/bodesign/`。
- T8 Add Gerber generation and validation from BoardDesign IR。
- T9 Add MCP AI planning tools for OpenMV and Rockbox flows。
- T10 Produce design/reconstruction reports for generated outputs。
- T11 Add datasheet knowledge ingestion and reuse tests。
- T12 Add targeted backend, MCP, and frontend verification。

## Key Decisions

- MVP scope selected: complete viewing → AI proposal → approval → export loop。
- Stack selected: React frontend + FastAPI backend。
- AI mode selected: assisted modification with explicit user approval。
- Persistence selected: Postgres。
- Renderer selected: Canvas 2D first。
- Parser strategy selected: Python library first。
- User requested GitHub open-source background research before scaffold。
- Product direction changed again: user likely has only Gerber/manufacturing outputs, so AI should reverse-engineer an editable source-layout model from Gerber/drill/IPC evidence。
- Editing strategy changed: AI proposals should patch reconstructed source objects, then regenerate Gerber outputs and report confidence/deltas。
- Scope narrowed: debug/test guidance is deferred; MVP focuses only on OpenMV docs → layout/Gerber, Rockbox Gerber → layout, and browser layout rendering。
- Source of truth changed: `BoardDesign IR` becomes the product-owned source for both generated and reconstructed layouts。
- EDA kernel decision: `pygerber` is retained for Gerber ingestion/validation only; core PCB layout design must be based on product-owned `BoardDesign IR` plus EDA bridge adapters。
- EDA bridge direction: KiCad is the first practical bridge candidate; `freerouting` is the first autorouting candidate after IR/constraints exist; `skidl` may help convert OpenMV docs into circuit/netlist evidence。
- Component knowledge decision: datasheet ingestion and normalized component records must be Day 1 architecture, because AI layout analysis requires pinouts, package, power/interface roles, and layout guidelines。
- Responsibility decision: source ingestion and normalization is the first responsibility area; display, analysis, and design authoring depend on normalized core data rather than raw PDFs/Gerbers directly。
- Host decision: opencms/opencode is the base infrastructure for dialog, file explorer, agent harness, approval flow, and fileview; EDA/Gerber should be delivered as MCP/plugin capability instead of a standalone app shell。
- Gateway decision: richer EDA web surfaces can register directly on the opencms gateway, keeping viewer deployment inside the host instead of launching an unrelated standalone web app。
- Product boundary decision: bodesign should now be host-agnostic MCP + web server; opencms is an optional first-class integration, not the required shell。
- MVP vision decision: first visible milestone is `/bodesign/` showing Rockbox circuit/PCB view after agent-provided files or instructions, backed by reconstruction or datasheet-derived generation。
- Knowledge-base decision: MCP server must include knowledge ingestion so datasheets/reference documents can be absorbed and reused for future chip/component design requests。

## GitHub Research Summary

- `KiCad/kicad-source-mirror`: active GPL-3.0 EDA reference and bridge candidate for file/export/DRC semantics。
- `freerouting/freerouting`: active GPL-3.0 DSN/SPECCTRA autorouter candidate for deterministic routing experiments。
- `skidl`: MIT Python code-first circuit/netlist tool; useful for OpenMV docs → structured circuit evidence, not layout engine。
- `kinparse`: MIT KiCad V5-V9 netlist parser; useful if KiCad netlist becomes interchange evidence。
- `Argmaster/pygerber`: recommended primary backend candidate; MIT, Python, PyPI package, supports Gerber X3/X2/RS-274X/RS-274D, API + CLI rendering。
- `tracespace/tracespace`: strong TypeScript web visualization reference with parser/plotter/renderer packages, but maintainer states the project is on indefinite hiatus; avoid hard dependency initially。
- `gerbv/gerbv`: mature maintained Gerber viewer/reference tool, but GPL/native dependency makes product embedding risky without license review。
- `curtacircuitos/pcb-tools`: archived Python project; use only as historical reference。
- `xingrz/GerberViewer`: Apache-2.0 web viewer reference, Vue-based; useful for UX comparison, not ideal as React core。
- Reverse reconstruction research is now required; `.art`, `.drl`, `.ipc`, and `.rou` packages should be treated as primary inputs。

## Debug Checkpoints

- Planning checkpoint: repository had no existing source, specs, or docs at task start。
- Safety checkpoint: no fallback or automatic design modification is allowed in the proposed workflow。
- Research checkpoint: `gh` and `curl` were available; GitHub searches found viable parser/viewer candidates, but generic `pcb drc gerber` searches returned no strong dedicated DRC candidate。
- License checkpoint: GPL tools should remain reference/comparison tools until license review is complete。
- Reverse-source checkpoint: Gerber is not original source, but Gerber plus drill plus IPC netlist can be used to infer a confidence-scored editable layout model。
- Local data checkpoint: `01.ROCKBOX` contains a high-value Allegro 22.1 manufacturing package with RS-274X `.art`, `.drl`, IPC-D-356A `.ipc`, `.rou`, stackup spreadsheet, and panel PDF。
- IPC evidence checkpoint: Rockbox IPC-D-356A includes layer metadata, padstack data, named nets, refdes, pin numbers, coordinates, pad sizes, side markers, and via records; this is sufficient to design an initial reconstruction spike。
- Component evidence checkpoint: Rockbox `cds2f_ROCKBOX_V2.txt` exposes refdes, part number/value, package symbol, side, rotation, and XY placement; examples include `MDBT53-P1M`, `AN7002Q`, `W25Q128JVSIQ`, `RT9471DGQW`, and `TCK106AG_LF`。
- OpenMV checkpoint: `02.OpenMV` currently contains schematic PDF and datasheets for target subsystems, but no Gerber/source package was found in the scanned folder。
- EDA kernel checkpoint: current environment does not have `kicad-cli`/`pcbnew`, so scaffold must abstract EDA bridge interfaces and not require KiCad on day one。
- Scaffold checkpoint: initial host-agnostic MCP/server/web skeleton created with `apps/web`, `services/api`, `services/mcp`, core package placeholders, optional `integrations/opencms`, root README, FastAPI placeholder endpoints, and MCP planned tool manifest。
- Contract checkpoint: added minimal Python dataclass contracts for `EvidenceSource`, `EvidenceRef`, `InputArtifact`, `ProjectSummary`, `ComponentKnowledge`, and `BoardDesign`; added a Rockbox reconstruction placeholder that returns an empty `BoardDesign` with evidence/confidence placeholders and performs no real parsing。
- T4 checkpoint: added deterministic artifact type detection for datasheet/reference PDFs, schematic names, BOM/placement files, Gerber/artwork, drill, IPC-356, routing reports, and unknown files; added in-memory project/job placeholder APIs without persistence or real file storage。
- T5 checkpoint: added OpenMV document-to-knowledge/design planning placeholders with `DesignIntent`, explicit knowledge gaps, component hints from document names, and `POST /api/projects/{project_id}/openmv/plan`; no PDF parsing or external lookup is implemented。
- T6 checkpoint: added Rockbox input manifest placeholder for component placement/BOM files, Gerber/artwork, drill, IPC-356, routing reports, and unknown files; added manifest and reconstruction API endpoints that return artifact-count confidence summaries without real geometry parsing。
- T7 checkpoint: upgraded `/bodesign/` from text placeholder to a visual Rockbox viewer mock showing a board canvas, representative components/traces, six-layer labels, BoardDesign IR identity, artifact-count evidence, and placeholder confidence status。
- T8 checkpoint: added Gerber export and validation placeholders with source-core export plans, gerber-core validation warnings, and API endpoints for `POST /api/projects/{project_id}/export/gerber` and `POST /api/projects/{project_id}/export/gerber/validate`; no real Gerber files are generated or inspected。
- T9 checkpoint: added `services/mcp/bodesign_mcp.py` placeholder handlers for `ingest_sources`, `ingest_knowledge`, `normalize_sources`, `reconstruct_board`, `generate_board`, `validate_design`, `export_gerber`, and `open_viewer`; handlers call existing deterministic placeholder contracts and do not provide full MCP transport yet。
- T10 checkpoint: exposed `DesignReport` through `POST /api/projects/{project_id}/reports/design`, MCP `produce_report`, and the MCP tool manifest; reports summarize reconstruction/export assumptions, artifact references, warnings, and send-to-fab caveats。
- T11 checkpoint: added component-kb datasheet ingestion and reuse placeholders with reusable component keys, source evidence refs, explicit extraction knowledge gaps, `POST /api/projects/{project_id}/knowledge/datasheets`, MCP `reuse_knowledge`, and unit coverage for ingestion/reuse。
- T12 checkpoint: completed targeted backend/MCP verification for artifact ingestion, component knowledge ingestion/reuse, Rockbox reconstruction placeholder, Gerber export placeholder, report generation, and `/bodesign/` viewer URL generation。
- Route checkpoint: registered bodesign-facing web/API aliases under `/bodesign/`, `/bodesign/health`, and `/bodesign/api/*` while keeping legacy `/api/*` aliases for scaffold compatibility。
- Rockbox summary checkpoint: upgraded reverse-core from artifact-count placeholder to fixture-backed summary reconstruction. It parses Allegro `cds2f_ROCKBOX_V2.txt` into 327 component instances, IPC-D-356A into 208 named nets, 938 component pads, and 817 vias, and preserves six copper layer labels from the Gerber manifest。
- Viewer checkpoint: `/bodesign/` now renders fixture-derived component/net/layer counts, selected placed components such as `U401 MDBT53-P1M`, and top IPC net summaries instead of only static mock data. Exact Gerber geometry remains pending。
- Visible route checkpoint: added `/` redirect to `/bodesign/`, HTML route index at `/bodesign/routes`, JSON route registry at `/bodesign/api/routes`, and a `python3 -m services.api` uvicorn entrypoint so the web surface has an explicit launch path。

## Verification

- Planning artifacts created under `plans/product_pcb_ai_viewer/`。
- Architecture baseline created at `specs/architecture.md`。
- Technology research updated at `plans/product_pcb_ai_viewer/technology-research.md`。
- Architecture Sync: Updated from source-first assumption to Gerber/drill/IPC reverse-to-source copilot with confidence-scored reconstructed model。
- Scaffold validation: FastAPI app exposes `GET /health`, `GET /bodesign/`, and `GET /api/projects`; syntax/import validation attempted without installing dependencies。
- Contract validation: FastAPI app now exposes `GET /api/schema-summary` and `GET /api/projects/{project_id}/board-design`; Python compile validation covers the touched service and contract modules。
- T4 validation: Python compile validation covers API and shared detection modules; deterministic detection smoke test covers Rockbox-style `.art`, `.drl`, `.ipc`, `.rou`, `cds2f` placement, schematic PDF, datasheet PDF, and unknown files。
- T5 validation: Python compile validation covers API and doc-core modules; import smoke test covers `plan_openmv_document_ingestion` returning a placeholder `DesignIntent` with knowledge gaps。
- T6 validation: Python compile validation covers API and reverse-core modules; Rockbox smoke test covers `.art`, `.drl`, `.ipc`, `.rou`, and `cds2f` manifest classification plus placeholder `BoardDesign` confidence counts。
- T7 validation: Python compile validation covers `/bodesign/` viewer route; viewer remains manifest-backed and intentionally does not parse real Gerber geometry yet。
- T8 validation: Python compile validation covers API, source-core, and gerber-core modules; smoke test covers placeholder export plan output paths and placeholder Gerber validation warnings。
- T9/T10 validation: Python compile validation covers API, MCP handler module, and source-core report contracts; MCP smoke test covers `produce_report`, `export_gerber`, and `validate_design` placeholder outputs。
- T11 validation: Python compile validation covers component-kb, API, MCP handlers, and component tests; `unittest` covers datasheet ingestion creating `component:mdbt53-p1m` and reusing `W25Q128JVSIQ` knowledge; MCP smoke test covers `ingest_knowledge` and `reuse_knowledge`。
- T12 validation: `python3 -m compileall packages services tests`, `python3 -m unittest discover -s tests`, and MCP end-to-end smoke for ingest → knowledge → reconstruct → export → report → viewer all passed。
- Route validation: `python3 -m compileall services/api/main.py tests packages services` and `python3 -m unittest discover -s tests` passed; route-table smoke uses a FastAPI stub to verify `/bodesign`, `/bodesign/`, `/bodesign/health`, and `/bodesign/api/*` aliases without requiring FastAPI to be installed locally。
- Rockbox summary validation: `python3 -m compileall packages services tests`, `PYTHONPATH="packages/shared:packages/design-ir:packages/reverse-core:packages/component-kb:packages/doc-core:packages/source-core:packages/gerber-core" python3 -m unittest discover -s tests`, and MCP `reconstruct_board`/`open_viewer` smoke test passed. The new reverse-core fixture test fixes expected Rockbox counts at 327 components, 208 nets, 6 layers, 938 IPC pads, and 817 vias。
- Viewer validation: FastAPI is not installed locally, so `/bodesign/` helper validation used the existing FastAPI stub approach and confirmed the HTML contains `MDBT53-P1M`, `Top Nets`, and `327` from fixture-derived data。
- Architecture Sync: Updated `specs/architecture.md` to distinguish current placement/IPC summary reconstruction from pending Gerber/drill geometry extraction。
- Visible route validation: `python3 -m compileall services/api/main.py services/api/__main__.py tests packages services` and `PYTHONPATH="packages/shared:packages/design-ir:packages/reverse-core:packages/component-kb:packages/doc-core:packages/source-core:packages/gerber-core" python3 -m unittest discover -s tests` passed; tests now assert `/`, `/bodesign/routes`, and `/bodesign/api/routes` registration and route-index content without requiring FastAPI to be installed locally。

## Remaining

- Extend Rockbox reconstruction from placement/IPC summaries into real Gerber/drill geometry: board outline, copper tracks, zones, apertures, drill hits, and drill-to-copper relationships。
- Replace remaining MCP/server/web placeholders for source ingestion, knowledge normalization, Gerber export, and layout generation with persistent job-backed implementations。
- Replace placeholder component knowledge ingestion with real PDF/text extraction, source trust checks, and persistent storage。
- Decide GPL integration posture for KiCad/freerouting before embedding either directly。
- Keep detailed Rockbox parsing and debug/test guidance for later phases。
