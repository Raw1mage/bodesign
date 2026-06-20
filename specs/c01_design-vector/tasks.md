# Tasks: c01_design-vector (extended for C01 Rockbox-style ID deliverable BR)

> 來源：`issues/issue_20260617_c01_rockbox_style_id_deliverables.md`（BR）。
> v1 原訂 `c01_emit_design_vector` 已併入 Phase 2 的 `emit_c01_id_visual_package`（Ai file bucket）。

## 1. 共用基礎 (shared infra)

- [x] 1.1 在 `c01_id_package.py` 新增 bucket rel-path 常數（`C01-ID/Ai file/`、`C01-ID/CMF/`、`C01-ID/Display UI_UX/`）與 `_DRAFT_MARKINGS` 文字常數
- [x] 1.2 新增共用輸入讀取 helper：讀 `Interface_Constraints.json`（主）+ answer_state（補），回傳 per-bucket 欄位完整度與缺欄清單（fail-fast，no silent fallback）
- [x] 1.3 新增共用 `BucketResult` dataclass（status/bucket/out_dir/files/draft_markings/missing_fields/validation_errors）+ `to_dict()`
- [x] 1.4 新增 draft-marking helper（往 SVG 注入可見浮水印文字；往 markdown/PDF 來源注入標記段落）

## 2. Ai file bucket emitter

- [x] 2.1 建立確定性 SVG 圖元庫（外殼原型 shell-* + 外露元件 comp-*；未覆蓋者 placeholder），對齊 `EXPOSED_COMPONENT_KEYWORDS`
- [x] 2.2 實作分層 SVG 組裝（outline/panel/cmf-fill/components/annotations；每元件包成 `component-<type>-<n>` group）+ S2 受控組裝
- [x] 2.3 實作 SVG schema validator（五類圖層齊全、元件 group 存在、SVG 合法）
- [x] 2.4 實作 `emit_c01_id_visual_package`：產 `<product>_ID_skeleton.svg` + `figma_import_spec.json` + `README.md`；缺欄 fail-fast；不偽造 .ai；回 `BucketResult`

## 3. CMF bucket emitter

- [x] 3.1 建立 CMF token 推導表（cmf_direction → material_family/finish/color_routes/rf_transparent_zones/gasket/sample_gates）
- [x] 3.2 實作 `cmf_tokens.json` 產出（approval_state 恆 not-approved）
- [x] 3.3 實作 `<product>_CMF_Direction` markdown → PDF（經 `bodesign_emit_doc`/docxmcp）+ `README.md`；標 not CMF approval
- [x] 3.4 實作 `emit_c01_cmf_package`：缺 `cmf_direction` fail-fast；回 `BucketResult`

## 4. Display UI_UX bucket emitter

- [x] 4.1 建立 UIUX 狀態詞彙表（OLED screens/states、LED vocabulary、insert-remove、privacy/local-only、charging/connectivity/error）+ 無 display→LED/status/button 映射
- [x] 4.2 實作 `uiux_wireframes.svg`（狀態 wireframe 圖元）
- [x] 4.3 實作 `<product>_UIUX_Flow` markdown → PDF（經 docxmcp）+ `README.md`；標 not UI sign-off
- [x] 4.4 實作 `emit_c01_uiux_package`：缺 `display_uiux`/status 描述 fail-fast；回 `BucketResult`

## 5. Readiness 雙軌

- [x] 5.1 擴充 `assess_c01_package_readiness`：保留既有 core companion 語意（向後相容），新增 `companion_readiness` + `id_native_readiness` 兩 track
- [x] 5.2 確認 ID-native 產出不讓 package 從 draft 升 approved（`human_approved` 恆 False）

## 6. MCP 註冊

- [x] 6.1 新增 3 個 handler（`_h_c01_emit_id_visual_package` / `_h_c01_emit_cmf_package` / `_h_c01_emit_uiux_package`）
- [x] 6.2 註冊 3 個 tool schema（`bodesign_c01_emit_id_visual_package` / `_emit_cmf_package` / `_emit_uiux_package`）

## 7. 測試與驗證

- [x] 7.1 三 bucket emitter 測試：正常輸出（檔案齊全、draft_markings 非空）
- [x] 7.2 fail-fast 測試：各 bucket 缺關鍵欄位回 missing/external-needed，不產檔（no silent fallback）
- [x] 7.3 Ai file SVG schema 測試（圖層齊全、元件 group、placeholder 告知）
- [x] 7.4 不偽造測試：無 Illustrator path 時 ai_emitted=false、無 .ai；無 Figma 時產 figma_import_spec.json
- [x] 7.5 readiness 雙軌測試：companion 與 id_native 分軌、向後相容、不升 approved
- [x] 7.6 跑全測試套件綠燈
- [x] 7.7 同步 `specs/architecture.md`（C01 能力邊界）+ event log 收尾
