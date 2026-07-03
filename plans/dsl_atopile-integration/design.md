# Design: dsl_atopile-integration

## Context

bodesign 的 C03（原理圖）→ C04（佈局）路徑目前由 LLM 直接產出 KiCad 工件：`compose_schematic`（`services/mcp/server.py:90` → `packages/eda-bridge/bodesign_eda_bridge/composer.py:454`）產 `.kicad_sch`，經 `export_netlist`（`server.py:385`）→ `route_net2pcb`（`server.py:400`）進入 `.kicad_pcb` finishing 鏈。正確性把關全靠**事後**驗證（ERC/DRC/crosscheck/SPICE/EMC）；連接性、單位、公差、約束在進 KiCad 前沒有任何靜態檢查。

本設計引入 **atopile 編譯器**作為 C03 的**宣告式驗證前端**：AI 生成 `.ato` 原始碼（單位型別 + 公差區間 + `assert` 約束），`ato build` 在編譯期把 LLM 幻覺攔在 KiCad 之前，產出 `.kicad_pcb` 直接進既有 C04 pipeline。選型依據見 proposal.md（2026-07-03 四候選調查，使用者定案）。

## Goals / Non-Goals

**Goals**

- 新 MCP 工具 `ato_build`：編譯 `.ato` 專案 → `.kicad_pcb` + 結構化編譯期驗證結果（ee worker 執行）。
- 編譯期驗證（constraint_solve）成為第五層信任證據，接入 `validation_evidence.v1` 信封與 readiness 聚合。
- atopile toolchain 進 `Dockerfile.ee`，pin 穩定版，fail-loud 驗證。
- 選料來源策略明確化：離線/自架場景不靜默退 cloud registry。

**Non-Goals**

- 不取代既有 compose_schematic 直接生成路徑（兩路並存）。
- 不做 spec→ato→kicad 與 spec→kicad 雙路徑交叉驗證（中期 extend，另案）。
- 不整合 tscircuit / circuit-synth；SKiDL 僅列備援。
- 不自動佈線（atopile 不做 layout；C04 維持現路徑）。

## Decisions

- **DD-1: 選 atopile，pin 0.12.x stable，不追 0.14.x pre-release。** 0.14 core 大改版 API 未穩；0.12.5 為最新 stable。升版走 spec `revise`。*（2026-07-03 implementing 補註）*：atopile 0.12.x 要求 Python 3.13（ee 系統 venv 是 3.12，apt pcbnew 依賴），故用 `uv tool install --python 3.13` 裝進獨立 toolchain venv，僅 `ato` CLI 曝露到 /usr/local/bin；兩個 Python 互不干擾。替代方案 circuit-synth（無約束求解）、SKiDL（無單位系統）、tscircuit（KiCad 輸出僅 library 級）均落選——編譯期驗證是本案核心動機，只有 atopile 具備。
- **DD-2: `ato_build` 歸 ee worker group（`_EE_GROUP_TOOLS`，`server.py:860-881`）。** atopile 是重 toolchain（依賴 KiCad 生態），依 core/worker 邊界原則進 ee；core 僅 forwarding（`_route_tool`，`server.py:919`）。monolith 環境缺 atopile → 顯式 `worker_unavailable` / toolchain-missing 錯誤，不靜默降級。
- **DD-3: `ato build` 產出 `.kicad_pcb` 直接進 C04 finishing 鏈，跳過 netlist 橋。** C04 工具（`via_in_pad`/`pour_planes`/`layout_drc_gate` 等，`server.py:409-438`）一律吃 `.kicad_pcb` 路徑（`in_path`/`out_path`/`board_path`），無專案目錄假設；atopile 輸出可無縫接入。`export_netlist` 橋僅為 compose_schematic 路徑保留。
- **DD-4: 第五層證據 oracle 名為 `constraint_solve`，同步三處註冊。** (1) `ORACLE_TOOLS` 白名單（`requirement_planning.py:101`）——否則信封 `__post_init__`（`validation_evidence.py:54`）拋 ENV_TOOL_UNKNOWN；(2) `_ADAPTERS` 註冊表（`validation_evidence.py:162`）新增 ato build 輸出 adapter；(3) `c06_test_plan.py:29` `_CHECKS` 聚合納入。缺一即為不完整整合。
- **DD-5: 選料策略 fail-fast 三態。** `ato_build` 增加 `component_source` 參數：`vault`（僅 bodesign Component Vault；pick 無解 → 缺項清單）/ `registry`（atopile cloud registry，需網路；不可達 → 顯式報錯）/ `vault_then_registry`（**僅在使用者請求時顯式啟用**，回應中標明每個零件的來源）。預設 `vault`。任何模式都不靜默跨源——遵守 no-silent-fallback 天條。Vault↔atopile 零件橋接格式（`.ato` component wrapper 生成）在 implementing 期以最小可用集起步（R/C/L + 常用 IC），缺 wrapper 的零件顯式報 `component_wrapper_missing`。
- **DD-6: 編譯錯誤回傳結構化缺項清單，不回傳原始 stderr dump。** `ato build` 的錯誤輸出解析為 `{kind: compile_error|unsat_constraint|pick_failure|toolchain_missing, detail, source_anchor}` 陣列；LLM 憑此修 `.ato` 原始碼迭代。原始 log 存 workspace 供 debug，不進 MCP 回應主體。
- **DD-7: `.ato` 電氣參數仍受 datasheet 證據鏈約束。** LLM 寫入 `.ato` 的元件規格值必須先經 `bodesign_datasheet_lookup` / `vault_spec_check`；atopile 的編譯期驗證檢查**一致性與可滿足性**，不檢查**參數來源真實性**——兩層互補，缺一不可。

## Risks / Trade-offs

- **atopile docs repo 已 archived（2026-04-29）** — mitigation: 以主 repo + pin 版實測行為為準；integration test 覆蓋 build 語義，升版時重跑。
- **cloud registry 離線不可用** — mitigation: DD-5 預設 `vault` 模式，registry 為顯式 opt-in；implementing 期驗證 `ato build --offline`（或等價 flag）行為。
- **`.ato` LLM 生成品質未知（新語言，語料少）** — mitigation: 錯誤迭代閉環（DD-6 結構化錯誤 → LLM 修正）；bodesign skill 補 `.ato` authoring 指引（另案）；先以簡單電路（分壓器、LED driver、buck converter 參考設計）建立 test-vectors。
- **ee image 變大** — mitigation: atopile 為純 Python wheel（+pint/numpy 級依賴），增量可控；BODESIGN_DEV=1 dev loop 不受影響。
- **雙路徑（ato vs compose_schematic）造成使用者困惑** — mitigation: 工具描述明確分工——ato 路徑適合「從規格新建、需編譯期保證」；compose 路徑適合「參考設計對照重建」。readiness 報告標記使用路徑。

## Critical Files

- `services/mcp/server.py:83-110` — handler 模式範本（`_h_emit_symbol`/`_h_compose`）；新增 `_h_ato_build`。
- `services/mcp/server.py:646-` — `TOOLS` list schema 註冊；`server.py:956` `PATH_ARG_KEYS`（新路徑參數 key 須加入）。
- `services/mcp/server.py:860-881` — `_EE_GROUP_TOOLS` set；`ato_build` 加入此處。
- `services/mcp/server.py:919-950` — `_route_tool` / `_forward_to_worker`（沿用，不改）。
- `Dockerfile.ee:36` 之後 — atopile pip install 插入點 + `ato --version` fail-loud 驗證（模式同 kicad-cli 檢查）。
- `packages/workflow-core/bodesign_workflow_core/validation_evidence.py:54,162` — 信封 oracle 檢查 + `_ADAPTERS` 註冊。
- `packages/workflow-core/bodesign_workflow_core/requirement_planning.py:101` — `ORACLE_TOOLS` 白名單。
- `packages/workflow-core/bodesign_workflow_core/c06_test_plan.py:29` — `_CHECKS` readiness 聚合。
- `packages/eda-bridge/bodesign_eda_bridge/` — 新模組 `ato_bridge.py`（ato build subprocess 包裝 + 錯誤解析 + vault wrapper 生成）擬落此 package（與 composer.py 同層，同為 KiCad adapter 邊界）。

## Code Anchors

- `services/mcp/server.py:931` — `_forward_to_worker(url, name, arguments, group)` core→ee 轉發。
- `packages/eda-bridge/bodesign_eda_bridge/composer.py:454` — `compose_schematic` 既有 C03 入口（並存路徑）。
- `services/mcp/server.py:400` — `_h_route_net2pcb`（netlist 橋路徑，ato 路徑跳過此步）。
- `services/mcp/server.py:436` — `layout_drc_gate`（ato 產出 `.kicad_pcb` 的下游 gate）。
