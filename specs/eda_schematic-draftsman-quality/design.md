# Design: eda_schematic-draftsman-quality

## Context

`compose_schematic`（`packages/eda-bridge/bodesign_eda_bridge/composer.py`，79 行）把宣告式 design spec（components + named-net）轉成 `EmitComponent`/`EmitNet` IR，再交給 `kicad_emit.py` 的 `emit_kicad_schematic` 產 `.kicad_sch`。

**關鍵現況（讀碼確認）**：
- `kicad_emit.py` **已實作** `connection_style="wire"`：2-pin 走 `_orthogonal_route`（L-route，line 386）、3+ pin 走 `_bus_route`（channel + junction，line 406）、所有件先 `_snap_grid` 到 1.27mm 連接格點（line 254-261），確保 wire 端點與 pin 真正 merge。
- 但 `composer.py` 預設 `connection_style="label"`（line 49），placement 走 `_auto_place(index % columns)`（line 33）naive grid。
- `composer.py` 已有 Level-1 AI/tool split（line 62-68）：呼叫者給 `x/y` 就採用，否則退回 naive grid。

因此 BR 抱怨的「無實體導線」其實引擎已就緒，**真正缺口**只剩三項：(1) meaningful placement、(2) 預設切到 drawn-wire、(3) sheet-fit；外加 (4) ink/bbox 量化驗收。

## Goals / Non-Goals

### Goals
- 不碰 `kicad_emit.py` 幾何引擎正確性，在其上補 placement + 預設切換 + sheet-fit。
- placement 確定性可回歸；no silent fallback。
- ink/bbox 可量測、可回歸，缺 toolchain 時顯式 unavailable。

### Non-Goals
- 不做商用 EDA 等級美學自動佈局。
- 不引入隨機性（force-directed 須確定性初始化）。
- 不碰 layout/fab（C04）。

## Decisions

- **DD-1**（A5 Emit Validated Schematic）複用既有 `kicad_emit.py` wire 引擎，不新寫幾何。本 plan 的程式改動集中在 `composer.py`（placement + 預設）與一個新的 ink/bbox 度量模組。理由：引擎已 grid-snap + ERC-valid，重寫風險高且無必要。

- **DD-2**（A1 Cluster Components By Subsystem + A2 Refine Placement Within Cluster）**Placement 採兩階段：先分群、群內 force-directed 微調**（使用者確認方向）。
  - **階段 A — 分群（cluster）**：
    - 若 component 帶 `group`/`subsystem` 欄位 → 直接用宣告分群（顯式優先）。
    - 否則 → net-degree clustering：以 net 鄰接建無向圖，用確定性連通分量 / greedy modularity 推導群（不靠隨機 seed 的演算法）。
    - 群在 sheet 上以確定性網格排列（群數 → row/col），群間留固定 gutter。
  - **階段 B — 群內 force-directed 微調**：
    - 確定性 spring 模型：node=component（質點，斥力）、edge=共 net（彈力吸引），被動件被拉向相連主 IC。
    - **確定性鐵律**：初始座標用群內 deterministic 排列（依 ref 排序的網格），固定迭代次數、固定步長、無 RNG。相同輸入 → 相同輸出。
    - 終局座標再 `_snap_grid`（交給 emit 時引擎也會 snap，這裡先 snap 讓重疊判定一致）。
    - 重疊偵測：以 symbol bbox（估算，見 DD-4）做 AABB 重疊檢查，spring 收斂後若仍重疊則加大群內 gutter 重排（確定性，非隨機抖動）。

- **DD-3** **opt-in style 切換策略（預設不破壞既有行為，使用者 2026-06-19 決策）**：`composer.py` 新增 `style` 參數（`"draftsman"` | `"netlist"`），**預設 `"netlist"`（既有行為）**。
  - `"netlist"`（預設）→ 既有行為（naive grid + global label），與升級前 byte-equivalent，零破壞。
  - `"draftsman"`（opt-in）→ 套用 DD-2 placement + `connection_style="wire"`（A3 Route Connectivity As Wires）+ DD-5 sheet-fit。
  - 呼叫者明確給 `connection_style` 時尊重之（style 不覆蓋顯式 connection_style）。MCP schema 同步加 `style`（預設 netlist）。
  - 理由（使用者決策）：no-silent-change——既有呼叫者依賴 label+grid 預設，不得被靜默改變。要 draftsman 品質的圖必須**顯式** `style=draftsman`，符合 repo no-silent-fallback / no-silent-change 精神。下游若要好看圖，明確傳旗標。

- **DD-4** **Symbol bbox 來源**：placement 重疊判定需要每個 symbol 的尺寸。
  - 一階：用 `kicad_emit.py` 的 `load_symbol` 取 pin endpoints，以 pin 外接矩形 + 固定 margin 估 bbox（pin-extent proxy）。
  - 不另解析 symbol graphic body（KiCad symbol 的 rectangle/polyline），避免擴大打擊半徑；pin-extent proxy 對 placement 間距足夠。
  - bbox 估算失敗（symbol 載入失敗）→ 沿用既有 warnings，該件不參與 force-directed（fail-visible），不以預設尺寸靜默塞入。

- **DD-5**（A4 Fit Sheet To Content）**Sheet-fit 策略**：placement 完成後計算內容 AABB，sheet 尺寸 = 內容 bbox + 對稱邊距，並把內容平移到邊距原點。
  - KiCad `.kicad_sch` 的 `(paper "A4")` 是離散頁規格 → 採「選最小可容納的標準頁（A4/A3/A2…）並置中」而非任意連續尺寸，避免產出非標準頁讓 KiCad 顯示異常。
  - 若內容超過最大標準頁 → 顯式 warning（建議拆 sheet），不靜默裁切。
  - 著墨率提升主要靠 placement 聚攏 + wire；sheet-fit 解決「浮在空白」。

- **DD-6**（A6 Measure Ink Coverage）**Ink/bbox 量化驗收模組**（新檔，pure-python core 側）：
  - 輸入：一張 `.kicad_sch` 轉出的 PDF/PNG（pdftoppm 150-200dpi）。
  - 輸出：ink%（非背景像素比）、內容 bbox 佔版面比。
  - **toolchain gating**：缺 pdftoppm/poppler/PIL → 回 `measurement_unavailable` + 缺項清單，不偽造度量（repo 天條）。pdftoppm 渲染本身依賴 KiCad CLI/poppler，屬 worker 側能力；度量純像素統計屬 core。
  - 驗收門檻：design 暫定「draftsman ink% ≥ 2× 同 spec netlist 模式基準，且絕對 ink% ≥ 10%」。確切門檻在 planned 階段配 test-vectors 定案（避免過度擬合單一 spec）。

- **DD-7** **回歸測試確定性**：測試用固定小 spec（few-component + few-net），assert placement 座標穩定（byte-stable IR）+ ink% 在區間。force-directed 無 RNG 保證可回歸。PYTHONPATH 需含所有 package 子目錄（repo 慣例）。

### Extend 2026-07-06（BR_20260706 batch：aiguard C03 實戰缺口收編）

來源：`issues/BR_20260706_draftsman_collinear_wire_fusion_shorts.md`（短路）與
`issues/BR_20260706_schematic_text_render_qa_gap.md`（疊字）。新增三個 IDEF0 活動：
**A7 Lint Page Density Budget**（前置治本）、**A8 Verify Net Partition Fidelity**（post-emit
保真閘）、**A9 QA Rendered Text Overlap**（渲染層交付判準）；A3 增一條 control（異 net wire
共線/共點即 fail 的防熔合 guard）。部分能力（fidelity.py / render_qa.py / composer 接線）已在
交付 session 內實戰驗證並隨 BR 收編進 repo，本 extend 補齊其規格地位、未競項目與回歸基線。

- **DD-8**（A8）**保真閘比對「劃分」不比對「命名」**：spec 期望 net 劃分（union-find 建節點集）vs
  kicad-cli 匯出 netlist 的連通分量，兩側對共享節點宇宙做等價類比對；power port 改名端點使名稱對齊
  不可靠。ERC 對 net 融合天然盲（net 數變少、無 dangling，ERC 反而更乾淨），故 `validate=True`
  不能替代此閘。實作：`fidelity.py verify_partition_fidelity`，`compose_schematic(fidelity=True)`
  接線，diff!=0/0 即 raise `FidelityError`（fail-loud，絕不出貨靜默短路的圖）。實戰抑止 GND(141)/
  BAT_SENSE(177)/+3V3_PB(189) 三次短路。
- **DD-9**（A9）**渲染層才是交付判準**：模型層（錨點座標）QA 對 IC pin-name/pin-number、refdes/
  value、power-port Value 等四類渲染文字有結構盲區；`render_qa.qa_svg_text` 掃 kicad-cli SVG 全部
  `<text>` bbox，交疊>15% 即 violation，`violation=0` 才允許宣稱呈現層完成。回歸基線（aiguard CCM
  5 頁）：01_power=13 / 02_mcu=6 / 03_memory=18 / 04_wireless=3 / 05_stamp=2，引擎文字改動只准降不准升。
- **DD-10**（A7）**密度預算是疊字的治本層**：文字疊字上游是 placement 密度（per-page pin 子集、元件
  cluster 間距、頁面 net 數）；emit 層防疊位移超過臨界密度後無解（同一引擎，04_wireless v=3 vs
  product 單頁 v=231，唯一差異是密度）。compose 前置 lint：頁面 net 數/元件數/單 symbol pin 數超閾值
  即 raise `DENSITY_BUDGET_EXCEEDED`（fail-fast，建議分頁），閾值以 aiguard 實測標定（04_wireless=PASS
  上限參考、03_memory=FAIL 下限參考）。emit 全域 occupancy 保留但降級為「密度合格頁面的精修」。
- **DD-11**（A3 control）**wire 防熔合 guard**：KiCad wire 連通語意是幾何的（共線重疊=電氣連接）；
  emit 產生任何 wire segment 前對全局 wire 集合做共線/共點檢查，異 net segment 共線重疊或端點落他
  net wire 上 → 確定性 jog 錯開（按 net hash）或 fail；連接密集頁面 `all_label` 自動判定。本項為
  未竟實作（交付 session 僅以 all_label 繞過），搭配 A8 保真閘兑底。

## Risks / Trade-offs

- **R1** force-directed 收斂不穩 / 仍重疊 → 緩解：固定迭代 + 收斂後 AABB 檢查 + 確定性 gutter 重排兜底（非隨機）。
- **R2** sheet-fit 選頁邏輯讓既有下游假設 A4 的工具出錯 → 緩解：netlist 模式維持 A4；draftsman 模式才動態選頁，並在 result 標明選用頁。
- **R3** ink 門檻過度擬合單一 spec → 緩解：multi-spec test-vectors，門檻用相對倍數 + 絕對下限雙條件。
- **R4** net-degree clustering 在 star 拓撲（一顆 MCU 連所有件）退化成單一大群 → 緩解：允許 group 宣告覆蓋；clustering 對高 degree hub 做 degree-capping 切分（planned 階段細化）。
- **R5**（extend）密度閾值過度擬合 aiguard 單一案例 → 緩解：閾值取實測 PASS/FAIL 兩點中間帶 + 可參數化 override（顯式、非靘默）；後續案例回饋再校。
- **R6**（extend）防熔合 jog 錯開改變 wire 幾何可能影響既有 TV3/TV8 byte-stable 回歸 → 緩解：guard 只在偵測到跨 net 共線時介入（無衝突輸入 byte-equivalent），回歸閘釘住。

## Critical Files

- `packages/eda-bridge/bodesign_eda_bridge/composer.py` — placement 兩階段 + style 預設 + sheet-fit（主改）；extend：density lint（A7）+ fidelity 接線（A8）。
- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py` — 複用 `emit_kicad_schematic` / `_orthogonal_route` / `_bus_route` / `load_symbol` / `_snap_grid`；extend：防熔合 guard（A3 control，DD-11）解除「不改幾何」限制但僅限 guard 介入路徑。
- `packages/eda-bridge/bodesign_eda_bridge/ink_metrics.py` — ink/bbox 度量，toolchain-gated。
- `packages/eda-bridge/bodesign_eda_bridge/fidelity.py` — A8 保真閘（DD-8，已落地）。
- `packages/eda-bridge/bodesign_eda_bridge/render_qa.py` — A9 渲染層文字 QA（DD-9，已落地）。
- `services/mcp/server.py` — `compose_schematic` handler + schema：`style`、`fidelity` 參數、`engine_rev` 回報。
- `skills/bodesign/scripts/gate.py` — extend：`qa_svg_text` landing verb（渲染層 QA 不需容器）。
- `tests/` — placement 單元 + ink 回歸；extend：`test_fidelity_gate.py`（已落地）+ density lint + 防熔合回歸。

## Code Anchors

- `composer.py:33` `_auto_place`（待取代）
- `composer.py:49` 預設 `connection_style="label"`（待加 style 切換）
- `composer.py:62-68` Level-1 AI/tool placement split（保留語意）
- `kicad_emit.py:212` `emit_kicad_schematic`（connection_style taxonomy）
- `kicad_emit.py:386` `_orthogonal_route`、`kicad_emit.py:406` `_bus_route`（複用）
- `kicad_emit.py:254-261` grid-snap
- `fidelity.py:224` `verify_partition_fidelity`（extend DD-8）
- `render_qa.py:97` `qa_svg_text`（extend DD-9）
- `composer.py:728-749` fidelity 接線（extend DD-8）
