# Tasks: knowledge_datasheet-spice-models

## 1. L4 命名空間 + 抽取入庫契約（R1 + R2）

- [x] 1.1 `repository.py` FIELD_PATH_ROOTS 擴充 `spice_model.{diode,ldo,passive}` roots（DD-3 封閉清單；含必要/選配欄位註記）
- [x] 1.2 新模組 `spice_card.py`：`ingest_spice_extraction(repo, mpn, rows) -> IngestReport`（per-row 驗證：registry / evidence sha256+page / 數值；SPX_EVIDENCE_MISSING、SPX_FIELD_UNKNOWN、SPX_VALUE_INVALID per-row 拒絕；not_found 只入 report 不落 DB；全寫 trust=unverified）
- [x] 1.3 P1 測試：registry 寫入/未註冊 fail-fast/verified-needs-evidence 回歸 + ingest 合法批次/缺 evidence per-row 拒絕/not_found 不落 DB（test-vectors TV-R1-*, TV-R2-*）

## 2. 確定性 model 卡生成（R3）

- [x] 2.1 `spice_card.py`：L4 參數查詢 + typ-selection 規則（typ 優先 → 唯一值 → 多值無 typ 拋 SPX_PARAMS_AMBIGUOUS，不平均）
- [x] 2.2 三類別確定性模板 `_card_diode` / `_card_ldo` / `_card_passive`（f-string；provenance 註解卡頭；LDO 帶第一階近似限制聲明；無時間戳）
- [x] 2.3 `generate_model_card(repo, mpn, category) -> ModelCard`：缺必要參數 SPX_PARAMS_MISSING（payload 列缺項 field_path + 修復指引）；SPX_CATEGORY_UNSUPPORTED
- [x] 2.4 P2 測試：三類別 fixture 生成 + byte-identical 確定性 + 缺參數/歧義 fail-fast（TV-R3-*）

## 3. 物化 + smoke 驗證（R5 前半 + DD-2/DD-7）

- [x] 3.1 smoke runner：類別對應最小 testbench + `ngspice -b` DC-op；pass / fail（SPX_SMOKE_FAILED 含 stderr 摘要）/ skipped-no-simulator 三態
- [x] 3.2 `materialize_model_cards(project_dir, mpns, repo)`：smoke pass/skipped → 寫卡檔 + manifest entry（source=vault-grounded + provenance_summary + smoke 狀態）；fail 卡不進 manifest
- [x] 3.3 manifest round-trip fixture：鎖定 spice skill `spice_model_cache.py` 現行 manifest 格式（R-A 風險緩解）
- [x] 3.4 P3 測試：smoke 三態（ngspice 不在則 mock/skip 標注）+ 物化 manifest 內容 + fail 卡排除（TV-R5-*）

## 4. simulate 接線 + MCP 工具（R4 + DD-8/DD-9）

- [x] 4.1 `simulate.py`：SimResult.results[] 加 `model_source`（確定性 manifest 查表：子電路元件 MPN 命中 vault-grounded entry 才標 grounded，否則 generic-default）
- [x] 4.2 `services/mcp/server.py`：`bodesign_spice_model_card` 工具（args: folder/mpn/category/materialize?；回傳 ModelCard JSON；SPX_* 透傳 run_tool 包裝層）
- [x] 4.3 ValidationEvidence 接線驗證：smoke / simulate 結果可包 `wrap_validation_evidence(tool="spice")` 回流 spine（沿用 P3 既有 envelope，不新增 schema）
- [x] 4.4 P4 測試：model_source 兩種值 fixture + MCP 工具 happy path / SPX 錯誤透傳（TV-R4-*）

## 5. 收尾驗證

- [x] 5.1 全 suite 回歸（484+ 既有測試全綠）
- [x] 5.2 `specs/architecture.md` 同步（vault L4 spice_model 命名空間 + 驗證第 3 層資料流 + component-kb 模組描述）
- [x] 5.3 event log 收尾記錄 + promote 到 verified
