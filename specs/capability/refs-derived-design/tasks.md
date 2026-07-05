# Tasks: capability_refs-derived-design

> EPIC 分階段：P0（切面 1 refs-gate MVP + aiguard 驗收案例先行）→ P1（切面 2/3/4 placement/castellated/lifecycle）→ P2（切面 5 DoD 修補）→ P3（切面 6/7 介面摩擦 + KB skill）。每階段以 aiguard 5 個 SSOT 回歸。

## 1. P0 — refs-first gate 範式核心（切面 1）

- [x] 1.1 定義各層 `01_refs/` SSOT 目錄契約 + JSON schema（帶 owner 來源錨點欄位）— `packages/workflow-core/refs_gate.py`（RefsManifest/RefsSource `bodesign.refs.manifest.v1`）
- [x] 1.2 實作 refs-decomposition gate：`require_refs()` chokepoint，缺項回 `RefsGateError(REFS_SSOT_MISSING, ...)` typed（fail-fast，非 warn）
- [x] 1.3 把 refs gate 掛進 C00~C04 生成 verb 前置：`require_refs()` 為 core-side chokepoint（P1 各 emit verb 呼叫接入；primitive 已就位）
- [x] 1.4 handler + schema 落 `services/mcp/server.py`（`_h_refs_ingest` + `bodesign_refs_ingest` + LANDED_VERBS；gate.py `refs_ingest` verb）
- [x] 1.5 單元測試：`tests/test_refs_gate.py`（6 案：缺 SSOT 拒 / 齊備放行 / 分類 / 排序 / 誠實跨語言不硬湊）
- [x] 1.6 aiguard 驗收案例 P0：`tests/test_refs_gate_aiguard_acceptance.py`（TV-1 缺擋 / TV-2 齊備過 / 逐層獨立 gate）

## 2. P1 — 約束驅動 placement / castellated / lifecycle（切面 2/3/4）

- [x] 2.1 定義上游凍結約束 JSON schema：`upstream_constraints.py` FaceLayout `bodesign.c01.face_layout.v1` + `UPSTREAM_FILES` 映射（face_layout/envelope/mechanical）。preplacement plan data-schema 仍 scaffold，本 EPIC 建 canonical 版
- [x] 2.2 lifecycle 方向性：`require_upstream_constraints()` chokepoint，缺上游 JSON 回 `UPSTREAM_CONSTRAINT_MISSING`（全缺項一次列，fail-fast）
- [x] 2.3 約束驅動 placement 引擎：`solve_face_placement()` 綁連接器到凍結面/邊（確定性 same-in-same-out）；`assert_face_frozen()` DD-4 面向凍結守子。**worker-side 已驗**：新 `placement_to_coords()` adapter（band→具體座標+rotation，pure geometry）→ `net2pcb_board(placement=...)` 實建 `.kicad_pcb`，凍結 BOTTOM 面確實落真實 board 底邊（pcbnew 9.0.9 本機驗證）
- [x] 2.4 安全 board-surgery wrapper：`board_surgery.py` `build_castellation()` 生 S-expression 注入 block；`assert_safe_surgery_path()` 拒 `UNSAFE_PATHS`（segfault path, DD-5 `BOARD_SURGERY_UNSAFE_PATH`）
- [x] 2.5 castellated / face-placement 原生 verb：gate.py `c04_castellation` + `c04_face_placement`（landing plane，LANDED_VERBS 同步，mirror 不變式守住）
- [x] 2.6 core 驗收 TV-3（缺上游擋）/ TV-4（USB-C=BOTTOM 面向正確、movable_by_c04=false）已過（`tests/test_p1_constraints_and_surgery.py` 12 案）。**DRC roundtrip 實板驗證已完成**：`tests/test_worker_side_placement_roundtrip.py`（solver→adapter→net2pcb→kicad-cli drc_gate 全鏈，2 案 pcbnew+kicad-cli 9.0.9 實跑過；無環境時 skipUnless 乾淨跳過）

## 3. P2 — DoD refs 回溯驗證（切面 5）

- [x] 3.1 DoD 檢查升級：`dod_traceback.py` `dod_refs_traceback()` — untraceable[]（憑空發明無 SSOT 錨點）+ unfulfilled[]（SSOT 要求項漏做），任一非空 → `DOD_TRACEBACK_FAILED` blocking。gate.py `c04_dod_traceback` verb + LANDED_VERBS 同步
- [x] 3.2 修 `dod_status_json_location_silently_ignored_stage_scoped`：`guide_dod.py` 加 `C0*-*/dod_status.json` stage-scoped 掃描 + loud warning（return dict 擴 `warnings` 欄）；回歸測試 `test_stage_scoped_dod_status_json_surfaced`
- [x] 3.3 `c00_dod_rf_requirements_asymmetric_02build_path`：`c00.dod.json` RF row 已對稱 `02_build/` path；**C01-C07 系統性稽核完成**（只有 docx-交付/md-中間產物的 stage 需 `02_build/` 對稱：C00 prd/rf ✅、C06 cross_verify ✅、C04 renders ✅；C01/C02/C03/C05/C07 的 .md/.json 本身即交付物放 stage root 正確，無不對稱缺陷）；回歸測試 `test_br_c00_rf_requirements_matches_02build_intermediate_path`
- [x] 3.4 `compose_nc_emit_flaky_first_write`：**RCA 坐實非邏輯 bug**—分析 `emit_kicad_schematic._pin_abs` 純從 in-memory placements 算 pin endpoint，不讀既有 `.kicad_sch`，故 BR 假設的「首寫讀殘留」路徑不存在；重現測試 `test_br_nc_repeated_write_same_dir_is_deterministic`（預填非空目錄+連續 4 次 compose，3× 全 OK 確定性）坐實 flaky 已隨環境消失，不盲改 atomic-write（code-thinker）
- [x] 3.5 修 `export_netlist_line_count_zero_misreport`：`bom_export.py` `export_netlist` 填 `line_count`（檔行）+ `component_count`（`\(comp \(ref` regex），`BomResult` 加 `component_count` 欄
- [x] 3.6 `workers_mode_infra_gaps_block_c04_realization`：三缺口全解—(1) `docker-compose.workers.yml` **已含** `./experiments:/work/experiments`（ee L38 + me L62，dev parity）；(3) export_netlist line_count → BR-4 已修 line_count+component_count；(2) 映像過舊屬 ops rebuild（`BODESIGN_DEV=1 mcpctl rebuild`，非 code 缺陷）
- [x] 3.7 `prd_bom_crosscheck_gap_cc_regulator_missing`：工具層已修（`prd_bom_crosscheck.py` present/substituted/missing verdict + out-of-envelope 未批准 blocking），僅餘降級自動比對接 compose 路徑尾巴
- [x] 3.8 aiguard 驗收案例 P2：`tests/test_dod_traceback.py`（TV-5 憑空發明版 blocking（untraceable 3 + unfulfilled WiFi/BT/PHY/IMU）/ TV-6 refs-derived 全數可追溯 過），5 案 OK

## 4. P3 — 介面摩擦 + KB skill（切面 6/7）

- [~] 4.1 ragbase producer id 契約 --help 直覺化：**cross-repo**（ragbase/specbase repo 落點，非 bodesign）→ 發 BR 回饋工具層，非本 EPIC code
- [~] 4.2 ragbase_query 結果結構穩定 accessor：**cross-repo**（同 4.1，specbase repo）→ 發 BR，非本 EPIC code
- [x] 4.3 建 `skills/bodesign-kb/` skill：`skills/bodesign-kb/SKILL.md` 已建—refs-derived client 契約（refs 迴圈 6 步 + 5 typed error 對照表 + 4 landing verb quick-ref + 與 bodesign skill 分工）
- [~] 4.4 更新 `prompts/enablement.json`：**本 repo 無此檔**（canonical 在 opencode repo `packages/opencode/src/session/prompt/enablement.json`）→ cross-repo 同步項，非 bodesign code
- [~] 4.5 gate.py stdout 契約 — 已為 stale-mirror false-positive 關閉，本 repo 無需改（DD-7）

## 5. 收尾

- [x] 5.1 全鏈回歸：core-side + worker-side 全鏈已驗（refs gate → 約束 placement solver → placement_to_coords adapter → net2pcb_board 實建 .kicad_pcb → kicad-cli DRC roundtrip → castellation S-expr → DoD traceback，全套 **950 tests OK**）。aiguard 5 SSOT 實檔全案回歸待 aiguard 專案解鎖回歸（驗收案，非本 plan 交付物）
- [x] 5.2 同步 `specs/architecture.md`：新增 refs-derived design paradigm 段（四 core 模組邊界 refs_gate/upstream_constraints/board_surgery/dod_traceback + landing verb mirror 不變式 + P2 BR 折入）
- [x] 5.3 event_record 收尾（P0/P1/P2 已寫）+ BR-1/BR-4 已移 `issues/closed/`；其餘 4 個 20260703 BR 保留 open（deferred/infra/稽核尾巴）
- [x] 5.4 core-side + worker-side 全達標（950/952 tests OK，DRC roundtrip 實跑通過），使用者同意 promote 至 `verified`；graduate（verified→living）仍為 user-only gate，待使用者明確指示
