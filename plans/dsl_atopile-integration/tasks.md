# Tasks: dsl_atopile-integration

## 1. Toolchain（ee worker）

- [x] 1.1 `Dockerfile.ee` 新增 pinned atopile（`pip install atopile==0.12.5`）+ `ato --version` fail-loud 驗證（插入點：`:36` pip install 之後、`COPY packages` 之前）
- [x] 1.2 rebuild ee image，容器內 `ato --version`=0.12.5 通過（注：atopile 要求 Py3.13，用 uv tool 隔離 venv，系統 3.12/pcbnew 不受影響）

## 2. ato_bridge（eda-bridge package）

- [x] 2.1 新模組 `packages/eda-bridge/bodesign_eda_bridge/ato_bridge.py`：`ato build` subprocess 包裝（timeout、workspace 路徑約束、build log 落盤）
- [x] 2.2 錯誤解析器：atopile 輸出 → `deficiency[]`（kind/detail/source_anchor，見 data-schema.json；DD-6）
- [x] 2.3 constraint_solve 證據組裝：build 輸出 → `constraint_solve_evidence`（solver_verdict、picks rated⊆spec、atopile_version）
- [x] 2.4 vault component wrapper 最小可用集：R/C/L 的 `.ato` wrapper 生成；缺 wrapper 顯式招 `ComponentWrapperMissing`（DD-5；常用 IC 屬後續增量）

## 3. MCP 工具註冊（server.py）

- [x] 3.1 `_h_ato_build` handler + `TOOLS` schema 條目（`project_path`/`component_source`/`target`，照 `_h_compose` 模式）
- [x] 3.2 `ato_build` 加入 `_EE_GROUP_TOOLS` set（`server.py:860-881`）；`project_path` 加入 `PATH_ARG_KEYS`（`server.py:956`）
- [x] 3.3 monolith（無 ee worker）呼叫回顯式 `toolchain_missing`/`worker_unavailable`（TV-5 實跑驗證 toolchain_missing；core-only 走既有 `_route_tool` worker_unavailable 語義，零新增 code）

## 4. 第五層信任證據（workflow-core）

- [x] 4.1 `constraint_solve` 加入 `ORACLE_TOOLS`（`requirement_planning.py:101`）
- [x] 4.2 `_ADAPTERS` 新增 ato build adapter（`validation_evidence.py:162`）
- [x] 4.3 `c06_test_plan.py:29` `_CHECKS` 聚合納入 constraint_solve + label

## 5. 驗證（test-vectors）

- [x] 5.1 測試專案 A（合法分壓器 `.ato`）：`ato_build` 產出 `.kicad_pcb`（實測 in-container OK；DRC gate 可跑但未 clean——ato 產物未佈線，clean 屬 C04 鏈職責，見 test-vectors TV-1 note）
- [x] 5.2 測試專案 B（恆假 assert）：回 `unsat_constraint` 且無 pcb 產物（實機校準：0.12.5 真實輸出為 Pick Error/Contradiction 區塊，解析器已鎖回歸）
- [~] 5.3 測試專案 C：`pick_failure` 分類已實測（真實 registry miss）；「無 registry 網路呼叫」部分**未達成**——0.12.5 picking 內建呼叫 cloud registry，vault-only 模式待 vault adapter（2.4 增量）；離線失敗=compile_error 已鎖回歸
- [x] 5.4 unittest：錯誤解析器 + 證據組裝（tests/test_ato_bridge.py，29 tests OK）
- [x] 5.5 monolith 環境顯式錯誤：host（無 ato）實跑 run_ato_build → toolchain_missing，無 fallback

## 6. 文件同步

- [x] 6.1 `specs/architecture.md` 全貌同步（新資料流：ato 路徑 + 第五層證據）
- [~] 6.2 README/CHANGELOG 更新（綁 push 前置門檳；本輪未指示 push，push 時再執行）
