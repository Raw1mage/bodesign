# Spec: c03_host-block-diagram-emitter

## Purpose

提供一個 deterministic emitter，把 host/MCU-centric 功能方塊圖 MODEL 投影成分層、可編輯的 SVG
(+ gated PNG/PPTX)，補齊 bodesign concept-diagram router 目前缺少的「放射狀 host 架構圖」形態。
所有契約鏡射既有 `emit_c03_partition_diagram`，確保行為一致、可預期。

## Requirements

### Requirement: Host-centric block diagram emission

核心能力：把 center part + 周邊 block 投影成放射狀功能方塊圖。

#### Scenario: 完整 MODEL 產出分層 SVG
- **GIVEN** 一個合法 MODEL：`center_part` 含 `name`（+ optional `mpn`），`peripherals` 為非空陣列，
  每個 peripheral 含 `name`、`side`（top|bottom|left|right）、optional `mpn`/`bus`/`type`
- **WHEN** 呼叫 `emit_c03_host_block_diagram(folder, model)`
- **THEN** 在 `C03-EE/block/Host_Block_Diagram.svg` 產出 SVG
- **AND** SVG 含 named layers：`center`、`peripherals`、`buses`、`legend`、`annotations`
- **AND** center part 為 `<g id="center-<name>">`，每個 peripheral 為 `<g id="peripheral-<name>">`，
  每條 bus 為 `<g id="bus-<peripheral>">`
- **AND** 回傳 `status="ok"` + `svg_path` + `layers` + `peripherals_count` + `boundary`

#### Scenario: 放射狀佈局是 deterministic
- **GIVEN** 同一個 MODEL
- **WHEN** 連續呼叫兩次（不同 folder）
- **THEN** 兩次產出的 SVG bytes 完全相同（no RNG；peripheral 排列由 side + 宣告順序決定）

#### Scenario: center 置中、peripherals 依 side 分佈
- **GIVEN** MODEL 的 peripherals 分散在 top/bottom/left/right
- **WHEN** emit
- **THEN** center part box 位於 canvas 中央
- **AND** 各 peripheral 依其 `side` 放在對應方位，bus 連線從 center 邊緣正交連到 peripheral

### Requirement: Fail-fast validation（no silent fallback）

#### Scenario: 缺 required 欄位回 missing
- **GIVEN** MODEL 缺 `center_part.name`，或 `peripherals` 為空，或某 peripheral 缺 `name`/`side`
- **WHEN** emit
- **THEN** 回傳 `status="missing"` + `missing_fields`（列出每個缺漏的具名路徑）
- **AND** 不產生任何 SVG 檔，不以預設值替代

#### Scenario: side 非法值被拒
- **GIVEN** 某 peripheral 的 `side` 不在 {top,bottom,left,right}
- **WHEN** emit
- **THEN** `missing_fields` 含 `peripherals[i].side(invalid:<value>)`

### Requirement: 未知 type → named placeholder（不靜默丟棄）

#### Scenario: 未知 peripheral type 渲染為 placeholder
- **GIVEN** 某 peripheral 的 `type` 不在 glyph library
- **WHEN** emit
- **THEN** 該 block 以 dashed 邊框 + 「(placeholder)」標籤渲染
- **AND** 其 name 列入回傳的 `placeholders[]` 與 `warnings[]`

### Requirement: Honest-boundary footer 常開

#### Scenario: footer 永遠存在且不可關閉
- **GIVEN** 任何合法 MODEL
- **WHEN** emit
- **THEN** SVG 的 annotations layer 含 honest-boundary 標語
  （functional block diagram, not a netlist / no RefDes.Pin→net / no DRC-SI claim）
- **AND** 無參數可關閉此 footer

### Requirement: Reference-baseline diff annotation（derived product）

#### Scenario: 標示 derived-from + 差異 + sourcing gates
- **GIVEN** MODEL 含 optional `reference_baseline`：`{name, diffs:[...], sourcing_gates:[...]}`
- **WHEN** emit
- **THEN** annotations layer 額外渲染「derived from <name>」+ 每條 diff + 每條 sourcing gate
- **AND** 回傳含 `reference_baseline` echo（name + diff/gate 數）

#### Scenario: 無 reference_baseline 時不渲染 diff 區
- **GIVEN** MODEL 無 `reference_baseline`
- **WHEN** emit
- **THEN** SVG 不含 derived-from 區塊（不憑空編造 baseline）

### Requirement: Toolchain-gated raster / pptx（無 phantom）

#### Scenario: cairosvg 缺席時不產生 PNG
- **GIVEN** 執行環境無 cairosvg
- **WHEN** emit
- **THEN** `png_rendered=false`，PNG 不列入 `files`，`warnings` 說明 SVG 已交付、PNG skipped

#### Scenario: emit_pptx 經 docxmcp bridge
- **GIVEN** `emit_pptx=true` 且 docxmcp bridge 不可達
- **WHEN** emit
- **THEN** `pptx_status="unavailable"` + reason，絕不偽造 .pptx

### Requirement: MCP tool 註冊 + GUIDE/router 文件同步

#### Scenario: server 暴露新 tool
- **GIVEN** bodesign MCP server 啟動
- **WHEN** 查 tools 清單
- **THEN** 含 `bodesign_c03_emit_host_block_diagram`，description 載明 MODEL schema、layers、
  fail-fast、placeholder、honest-boundary、determinism、gated raster

#### Scenario: concept-diagram router 列入新 emitter
- **GIVEN** 讀 `skills/bodesign/SKILL.md` concept-diagram router 表
- **THEN** 含一列「MCU/host-centric functional block diagram → bodesign_c03_emit_host_block_diagram」

#### Scenario: GUIDE 責任邊界補強
- **GIVEN** 讀 `stages/c01-id/GUIDE.md`
- **THEN** 明列 host block diagram / board-partition 屬 C03-EE 責任，非 C01
- **AND** `stages/c03-ee/GUIDE.md` 的 block-diagram 段落指向新 emitter（不再隱含手刻）

## Acceptance Checks

- [ ] `tests/test_c03_host_block_diagram.py` 全綠（鏡射 partition test：valid/missing/placeholder/determinism/boundary/reference-diff）
- [ ] emitter 對 test-vectors.json 的每個 case 產出符合預期
- [ ] 同 MODEL 兩次 emit byte-identical
- [ ] server 啟動後 `bodesign_c03_emit_host_block_diagram` 可被列出與呼叫
- [ ] SKILL.md router + 兩份 GUIDE 文字更新落地
- [ ] 不改動 `emit_c03_partition_diagram` 既有行為（partition test 仍全綠）
