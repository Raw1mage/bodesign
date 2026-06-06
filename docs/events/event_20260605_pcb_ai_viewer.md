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
- Published Web checkpoint: fixed opencms visibility by adding a `bodesign` entry to `~/.config/web_registry.json`, publishing gateway route `/bodesign -> 127.0.0.1:8765`, adding repo `webctl.sh`, and starting the FastAPI upstream on port 8765. Root cause: app routes existed inside FastAPI, but opencms Published Web only lists gateway-published routes with matching user registry entries。
- Workspace viewer checkpoint: replaced the single-board mock with a multi-tab file workspace covering Source Documents, Board View, Gerber Layers, IPC/Nets, Components, BoardDesign IR, and Reconstruction Report. This explicitly marks the board drawing as placement-summary only and moves correctness-sensitive evidence into file/type-specific views。
- Project browser checkpoint: added a web Projects tab and `GET /bodesign/api/projects` builtin project registry. Rockbox is now listed as an already-imported fixture project with artifact/component/net counts and an Open/Browse entry instead of being only an implicit demo page。
- Board View correction checkpoint: removed the decorative placement-sketch canvas from Board View because it was visually misleading and not a valid schematic, circuit diagram, or Gerber render. Board View now shows an explicit “PCB layout rendering is not available yet” state and points users to Gerber Layers, IPC/Nets, and Components for verified evidence。
- Roadmap checkpoint: expanded the plan from T1–T12 scaffold work into T13–T27 functional gap tasks. The next capability sequence is real project workspace, source-file viewers, Gerber/drill geometry reconstruction, component-pad-net fusion, component knowledge extraction, KiCad bridge evaluation, AI reference-board workflow, and generated design candidate approval UI。
- T13-T15 checkpoint: added per-project workspace route `/bodesign/projects/{project_id}`, artifact browser route `/bodesign/projects/{project_id}/artifacts/{artifact_id}`, project artifact APIs, fixture-backed Rockbox artifact records, and basic type-aware artifact preview pages. T13/T14 remain partial because durable DB/file storage and upload/drop import are still pending; T15 basic file viewers are complete for current fixture evidence.
- T16-T19 checkpoint: added a lightweight gerber-core geometry parser for Rockbox-style RS-274X `.art` files and Excellon `.drl` files. `/bodesign/` Board View now renders evidence-based SVG from `L1_top.art` draw/flash operations plus `ROCKBOX_V2-1-6.drl` drill hits, and artifact pages show Gerber/Drill geometry summaries instead of raw text only. This is a parser/render spike, not full EDA editing.
- Viewer backend checkpoint: evaluated pygerber as the first third-party Gerber renderer. Raw Allegro `.art` headers are not accepted directly, but gerber-core now normalizes Allegro compatibility blocks (`IR/IP/OFA/MI/SF`) and renders Rockbox `L1_top.art` through pygerber SVG when the dependency is installed. The internal geometry SVG remains a fallback only.
- Board View viewport checkpoint: changed Board View from page-expanding CSS zoom to a fixed-height viewport with SVG viewBox zoom/pan controls. The pygerber SVG is now focused to percentile-bounded visible Gerber flash positions so sparse corner/tooling marks no longer dominate the default fit.
- Board View mouse interaction checkpoint: added mouse-wheel zoom at cursor and drag-to-pan behavior inside the fixed Board View viewport. Interaction updates the SVG viewBox rather than expanding the page scroll area.
- Board View component overlay checkpoint: added a placement-derived component overlay on top of the pygerber preview. Default markers focus on major ICs/connectors/antenna/crystals/switches, optional toggles reveal passives/test points, and clicking a marker opens an inspector with placement, footprint, side, XY, and IPC-derived pin/net evidence. This is not yet exact footprint geometry; it is an evidence overlay from Allegro placement and IPC-356 data.
- Board View copper flash checkpoint: identified the confusing green dots as pygerber-rendered Gerber flash apertures from the selected copper layer, not synthetic component markers. Board View now hides SVG `<use>` flash apertures by default and provides a `Toggle copper pads/flashes` control so users can inspect them intentionally without confusing the default single-layer preview for a shorted net view.
- Board View overlay coordinate checkpoint: disabled placement overlay by default because Allegro placement coordinates are not yet calibrated to exact pygerber/Gerber footprint geometry. When explicitly toggled on, markers are now reprojected point-by-point from the current SVG viewBox during pan/zoom instead of moving as a separately scaled HTML layer.
- Workspace layout checkpoint: fixed full-width tab layout by forcing the tab panel container to occupy a full flex row, constraining the app shell to `minmax(0, 1fr)`, and adding overflow guards for panels, grids, cards, tables, code, and JSON previews.
- Plan checkpoint: promoted Board View stabilization into the active plan before T20. The next required slice is pygerber raster-only rendering with no hand-written SVG fallback, explicit render-failure UI/API states, synchronized tests/docs, and a restored green validation baseline before component-pad-net reconstruction starts.

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
- Published Web validation: local upstream `http://127.0.0.1:8765/bodesign/` returned `200 text/html`; gateway route `http://127.0.0.1:1080/bodesign/` returned `200 text/html`; opencode `webctl.sh list-routes` shows `/bodesign 127.0.0.1:8765 uid=1000`; `python3 -m json.tool /home/pkcs12/.config/web_registry.json` validates the registry after adding the entry。
- Workspace viewer validation: `python3 -m compileall services/api/main.py tests packages services` and `PYTHONPATH="packages/shared:packages/design-ir:packages/reverse-core:packages/component-kb:packages/doc-core:packages/source-core:packages/gerber-core:." python3 -m unittest discover -s tests` passed; route tests now assert the viewer contains the file workspace tabs and warns that the board view is not yet a true schematic/Gerber render。
- Project browser validation: `python3 -m compileall services/api/main.py tests packages services` and `PYTHONPATH="packages/shared:packages/design-ir:packages/reverse-core:packages/component-kb:packages/doc-core:packages/source-core:packages/gerber-core:." python3 -m unittest discover -s tests` passed; route tests now assert Rockbox appears in both the web Projects tab and project API as `imported-fixture`。
- Board View correction validation: `python3 -m compileall services/api/main.py tests packages services`, `PYTHONPATH="packages/shared:packages/design-ir:packages/reverse-core:packages/component-kb:packages/doc-core:packages/source-core:packages/gerber-core:." python3 -m unittest discover -s tests`, and gateway checks for `PCB layout rendering is not available yet` / `decorative placement sketch` passed after restarting bodesign。
- Roadmap validation: planning-only update; synchronized `implementation-spec.md`, `tasks.md`, `specs/architecture.md`, and this event log. Architecture Sync: updated immediate capability gaps and preserved Board View no-fake-rendering rule。
- T13-T15 validation: `python3 -m compileall services/api/main.py tests packages services` and `PYTHONPATH="packages/shared:packages/design-ir:packages/reverse-core:packages/component-kb:packages/doc-core:packages/source-core:packages/gerber-core:." python3 -m unittest discover -s tests` passed; route tests now assert project workspace routes, artifact APIs, and Rockbox artifact preview pages.
- T16-T19 validation: `python3 -m compileall -f packages services tests` and `PYTHONPATH="packages/component-kb:packages/design-ir:packages/doc-core:packages/gerber-core:packages/reverse-core:packages/shared:packages/source-core:services/mcp" python3 -B -m unittest discover -s tests` passed; parser tests assert Rockbox `L1_top.art` produces >1000 draw segments, >800 flashes, 40+ apertures, and `ROCKBOX_V2-1-6.drl` exposes 789 explicit drill hits plus four tool records with plated/non-plated hints.
- Viewer backend validation: `python3 -m compileall -f packages services tests` and system-Python unittest passed with pygerber render skipped when unavailable; `.venv/bin/python -m unittest tests.test_gerber_geometry.GerberGeometryTests.test_pygerber_adapter_renders_normalized_rockbox_layer_when_available` rendered the normalized Rockbox top layer to SVG successfully.
- Board View overlay validation: `python3 -m compileall -f services/api/main.py tests` and `PYTHONPATH="packages/shared:packages/design-ir:packages/component-kb:packages/doc-core:packages/reverse-core:packages/gerber-core:packages/source-core:services/api:services/mcp" python3 -m unittest discover -s tests` passed; local bodesign upstream `http://127.0.0.1:8765/bodesign/projects/rockbox` returned component overlay markers including `U401 MDBT53-P1M`, category toggles, and IPC pin/net inspector markup.
- Board View copper flash validation: `python3 -m compileall -f services/api/main.py tests` and full unittest discovery passed; local bodesign upstream `http://127.0.0.1:8765/bodesign/projects/rockbox` returned CSS that hides `svg use` flash apertures unless `.show-copper-flashes` is enabled and includes the `Toggle copper pads/flashes` control.
- Board View overlay coordinate validation: `python3 -m compileall -f services/api/main.py tests` and full unittest discovery passed; local bodesign upstream returned `Toggle placement overlay`, the default-off overlay warning, and point-by-point SVG viewBox projection code without the previous `overlay.style.transform` layer transform.
- Workspace layout validation: `python3 -m compileall -f services/api/main.py tests` and full unittest discovery passed; local bodesign upstream returned `.panels { flex: 0 0 100% }`, `grid-template-columns: 300px minmax(0, 1fr)`, and `table-layout: fixed` CSS for full-width workspace stability.
- Plan update validation: synchronized `tasks.md`, `implementation-spec.md`, `specs/architecture.md`, and this event log so raster-only Board View stabilization is the gate before T20.
- Raster-only stabilization validation: `python3 -m compileall -f packages/gerber-core services/api/main.py tests` and `PYTHONPATH="packages/shared:packages/design-ir:packages/component-matcher:packages/reverse-core:packages/gerber-core:services/api" python3 -m unittest tests.test_api_routes tests.test_gerber_geometry` passed after aligning Board View copy/tests to the `pygerber-raster` + fail-fast contract.
- T20 first-pass fusion validation: `PYTHONPATH="packages/shared:packages/design-ir:packages/component-knowledge:packages/source-core:packages/reverse-core:packages/gerber-core:services/api" python3 -m unittest tests.test_api_routes tests.test_gerber_geometry` passed; geometry API now exposes `fusion_summary` with Rockbox component/net coverage and Board View shows a component-net fusion preview from placement + IPC evidence. Architecture Sync: first-pass fusion is documented as non-spatial; Gerber pad/flash/via/drill spatial fusion remains pending.

## Remaining

- Extend Rockbox reconstruction from first-pass placement/IPC component-net summaries into spatial Gerber/drill fusion: board outline, copper tracks, zones, apertures, drill hits, pad/via matching, and drill-to-copper relationships。
- Replace remaining MCP/server/web placeholders for source ingestion, knowledge normalization, Gerber export, and layout generation with persistent job-backed implementations。
- Replace placeholder component knowledge ingestion with real PDF/text extraction, source trust checks, and persistent storage。
- Decide GPL integration posture for KiCad/freerouting before embedding either directly。
- Keep detailed Rockbox parsing and debug/test guidance for later phases。
