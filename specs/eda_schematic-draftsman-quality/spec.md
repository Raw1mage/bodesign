# Spec: eda_schematic-draftsman-quality

## Purpose

讓 `bodesign_compose_schematic` 從「ERC-clean 但視覺空白的 netlist 傾倒物」升級為「工程師看得懂的 draftsman 品質電路圖」：相關元件聚在一起、點對點 net 有實體導線、sheet fit 內容、且著墨率可量化回歸。電氣正確性不退步。

## Requirements

### Requirement: 子系統分群 placement

#### Scenario: spec 元件帶 group 宣告
- **GIVEN** 一份 compose spec，部分／全部 component 帶 `group`（或 `subsystem`）欄位
- **WHEN** 呼叫 `compose_schematic`（未提供 explicit x/y）
- **THEN** 同 group 的元件被擺在相鄰區塊、不同 group 區塊彼此分離
- **AND** 群內以確定性 force-directed 微調，被動件靠近其相連主 IC，避免 symbol bbox 重疊
- **AND** result 回報每群的元件數與群中心座標

#### Scenario: spec 無 group 宣告（net-degree 推導）
- **GIVEN** 一份 compose spec，component 皆無 `group` 欄位
- **WHEN** 呼叫 `compose_schematic`
- **THEN** 以 net 鄰接（net-degree clustering）自動推導分群後擺放，而非 `index % columns` 網格
- **AND** 推導出的分群在 result 中可見（哪些 ref 落同群）

#### Scenario: 呼叫者提供 explicit placement
- **GIVEN** component 已帶 `x` / `y` 座標
- **WHEN** 呼叫 `compose_schematic`
- **THEN** 沿用呼叫者座標，不套用分群演算法（維持既有 AI-owns-placement 契約）

### Requirement: 點對點實體導線（opt-in draftsman 模式）

#### Scenario: 2-node net
- **GIVEN** 一個恰有兩個可解析節點的 net（非 power / 非 bus）
- **WHEN** 以 draftsman 模式 compose
- **THEN** 兩 pin 間畫實體 orthogonal wire（複用既有 `_orthogonal_route`），net 名以 local label 標在線段中點
- **AND** 不為此 net 產生 global-label

#### Scenario: 多節點 / bus / power net
- **GIVEN** 一個 3+ 節點 net，或標記為 power / bus / 跨 sheet 的 net
- **WHEN** compose
- **THEN** 3+ 節點 net 走既有 channel route（wire + junction）；power / 單 pin / 無法解析者退回 global-label（維持 ERC-valid）
- **AND** 退回 label 的 net 在 result warnings / 統計中可見，不靜默

### Requirement: Sheet 自適應

#### Scenario: 內容遠小於 A4
- **GIVEN** placement 完成後內容 bbox 遠小於預設 sheet
- **WHEN** emit schematic
- **THEN** sheet 尺寸 fit 內容 bbox（含合理邊距）或內容置中填滿，消除大片空白
- **AND** 內容不溢出 sheet 邊界

### Requirement: Ink/bbox 量化驗收

#### Scenario: 量測 draftsman 產出
- **GIVEN** 一張 draftsman 模式產出的 `.kicad_sch` 已轉 PDF（pdftoppm）
- **WHEN** 跑 ink/bbox 度量（PIL）
- **THEN** 回報著墨率（ink %）與內容佔版面比
- **AND** 著墨率相對舊 label-grid 基準明顯提升（目標區間參考真實手繪 15-40%，下限門檻於 design.md 定）

#### Scenario: 渲染 toolchain 缺失
- **GIVEN** 量測環境缺 pdftoppm / poppler / PIL
- **WHEN** 呼叫量測
- **THEN** 顯式回報 measurement-unavailable + 缺失工具清單，不偽造度量值（no silent fallback）

### Requirement: 電氣正確性與向後相容不破壞

#### Scenario: draftsman 產出仍 ERC-clean
- **GIVEN** 任一可成功 compose 的 spec
- **WHEN** 以 draftsman 模式 compose 並 `kicad-cli validate`
- **THEN** 通過 validate，pin→net 連接與 label 模式等價（無 phantom short、無 unconnected pin）

#### Scenario: 既有 label-grid 呼叫者不受影響
- **GIVEN** 既有呼叫者明確要求 `connection_style="label"`（或舊預設行為）
- **WHEN** compose
- **THEN** 行為與升級前一致（naive grid + global label），不被新預設強制改變

### Requirement: 缺項 fail-fast

#### Scenario: symbol / net 無法解析
- **GIVEN** spec 引用的 symbol 找不到，或 net 節點 ref.pin 無法解析
- **WHEN** compose
- **THEN** 顯式列出缺失 symbol / unresolved pin（沿用既有 warnings + unresolved_pins），不以預設件靜默替代

## Acceptance Checks

- [ ] 帶 group 的 spec：同群相鄰、群間分離，群內無 bbox 重疊。
- [ ] 無 group 的 spec：net-degree 分群生效，非 index%columns。
- [ ] 2-node net 有實體 wire + local label，無 global-label。
- [ ] power/bus/單pin/unresolved 正確退回 label 且可見統計。
- [ ] sheet fit 內容、無溢出。
- [ ] ink% 相對基準明顯提升並有回歸測試；缺 toolchain 時顯式 unavailable。
- [ ] draftsman 產出 `kicad-cli validate` 通過、與 label 模式電氣等價。
- [ ] `connection_style="label"` 舊行為保留。
- [ ] 確定性：相同輸入 → 穩定產出（force-directed 固定初始化）。
