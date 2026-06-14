# Spec: c02_voice-to-design

## Purpose

讓使用者用自然語言口述產品結構需求，系統反問補全缺失約束後，產出可渲染的 3D 外殼設計稿（渲染圖 + STL + 可選 STEP），全程不猜尺寸。

## Requirements

### Requirement: 口述抽取成 C02 約束草稿

#### Scenario: 自然語言含可抽取約束
- **GIVEN** 使用者口述「我要一個 50×30mm 的盒子，側面開 USB-C，室內用」
- **WHEN** 呼叫 C02 口述抽取
- **THEN** 抽出 board_outline(50×30)、connector_openings(usb-c, side)、environment_targets(indoor) 為 `stated` 約束
- **AND** 對未提及的關鍵約束（壁厚/間隙）標 `missing` 並產生澄清問題
- **AND** 抽取結果對齊 c03_export_mechanical_constraints 的 schema 欄位

#### Scenario: 數字+單位的自由語句
- **GIVEN** 口述含「最高的元件大概 12 公釐」
- **WHEN** 抽取
- **THEN** component_heights 以 regex 輔助抽出 12mm，標 `stated`
- **AND** 抽不到明確值的約束不臆測，轉為澄清問題

### Requirement: 反問補全保留 fail-fast

#### Scenario: 缺阻擋生 source 的關鍵約束
- **GIVEN** 抽取後 board_outline 或壁厚仍 missing
- **WHEN** 走生 source 流程
- **THEN** 不生 source，回傳下一個澄清問題（仿 c01_next_question 模式）
- **AND** 系統不以預設壁厚靜默續跑

#### Scenario: 使用者答覆澄清問題
- **GIVEN** 系統問了「壁厚要幾 mm？」
- **WHEN** 使用者答「2mm」並呼叫 update_answers
- **THEN** 約束併入、重算 readiness、回傳下一題或「約束齊備待確認」
- **AND** 顯式尺寸來自此答覆，非系統臆測

#### Scenario: 次要約束缺失不擋草稿
- **GIVEN** board_outline/壁厚/間隙齊備，但 heat_sources/antenna_keepouts missing
- **WHEN** 走生 source
- **THEN** 仍 can_generate_cad_source（對齊實跑：38% 即可生），但 readiness 未滿、標出缺項
- **AND** 不因次要約束缺失而 fail

### Requirement: 約束確認閘

#### Scenario: readiness 達生成門檻
- **GIVEN** 關鍵約束齊備
- **WHEN** 準備生 source
- **THEN** 先呈現完整約束集請使用者確認（尊重既有 approval gate）
- **AND** 未確認前不自動生 CAD source

### Requirement: enclosure 渲染成設計稿

#### Scenario: STL 渲染
- **GIVEN** c02_export_stl 已產出 Enclosure.stl
- **WHEN** 呼叫 c02_render_enclosure
- **THEN** 用 trimesh 載入 STL、經既有 pyrender 機制產出 top + iso PNG
- **AND** 回傳 ModelRenderResult（images/bounds/status）

#### Scenario: worker 無 GL
- **GIVEN** worker 缺 EGL/GL 或渲染依賴
- **WHEN** 呼叫 c02_render_enclosure
- **THEN** 回 no-deps/no-gl 狀態（沿用既有 degrade 行為），不造假圖

#### Scenario: 既有 board 渲染不回歸
- **GIVEN** 渲染後段已重構為共用函式
- **WHEN** 呼叫既有 render_board_model（glb）
- **THEN** 行為與重構前一致，回相同 ModelRenderResult 結構

### Requirement: 口述→設計稿閉環

#### Scenario: 完整一條龍
- **GIVEN** 使用者口述完整需求並答完澄清問題、確認約束
- **WHEN** 走完整 pipeline
- **THEN** 依序產出 OpenSCAD source → STL → 渲染設計稿圖
- **AND** 每段尊重各自 gate（缺則反問、未確認不生、無 GL 不假圖）

## Acceptance Checks

- [ ] 口述自然語言能抽出對齊 c03 schema 的 C02 約束草稿
- [ ] 缺關鍵約束時反問補全，系統不猜尺寸
- [ ] 次要約束缺失不擋 source 草稿（對齊 38% 實跑行為）
- [ ] 約束齊備時有確認閘，未確認不自動生 CAD
- [ ] STL 能渲染成 top/iso 設計稿圖
- [ ] 既有 board 渲染不回歸
- [ ] 口述→設計稿全鏈閉環可走通（PoC 實測一個真實口述案例）
