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

- **DD-1** 複用既有 `kicad_emit.py` wire 引擎，不新寫幾何。本 plan 的程式改動集中在 `composer.py`（placement + 預設）與一個新的 ink/bbox 度量模組。理由：引擎已 grid-snap + ERC-valid，重寫風險高且無必要。

- **DD-2** **Placement 採兩階段：先分群、群內 force-directed 微調**（使用者確認方向）。
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
  - `"draftsman"`（opt-in）→ 套用 DD-2 placement + `connection_style="wire"` + DD-5 sheet-fit。
  - 呼叫者明確給 `connection_style` 時尊重之（style 不覆蓋顯式 connection_style）。MCP schema 同步加 `style`（預設 netlist）。
  - 理由（使用者決策）：no-silent-change——既有呼叫者依賴 label+grid 預設，不得被靜默改變。要 draftsman 品質的圖必須**顯式** `style=draftsman`，符合 repo no-silent-fallback / no-silent-change 精神。下游若要好看圖，明確傳旗標。

- **DD-4** **Symbol bbox 來源**：placement 重疊判定需要每個 symbol 的尺寸。
  - 一階：用 `kicad_emit.py` 的 `load_symbol` 取 pin endpoints，以 pin 外接矩形 + 固定 margin 估 bbox（pin-extent proxy）。
  - 不另解析 symbol graphic body（KiCad symbol 的 rectangle/polyline），避免擴大打擊半徑；pin-extent proxy 對 placement 間距足夠。
  - bbox 估算失敗（symbol 載入失敗）→ 沿用既有 warnings，該件不參與 force-directed（fail-visible），不以預設尺寸靜默塞入。

- **DD-5** **Sheet-fit 策略**：placement 完成後計算內容 AABB，sheet 尺寸 = 內容 bbox + 對稱邊距，並把內容平移到邊距原點。
  - KiCad `.kicad_sch` 的 `(paper "A4")` 是離散頁規格 → 採「選最小可容納的標準頁（A4/A3/A2…）並置中」而非任意連續尺寸，避免產出非標準頁讓 KiCad 顯示異常。
  - 若內容超過最大標準頁 → 顯式 warning（建議拆 sheet），不靜默裁切。
  - 著墨率提升主要靠 placement 聚攏 + wire；sheet-fit 解決「浮在空白」。

- **DD-6** **Ink/bbox 量化驗收模組**（新檔，pure-python core 側）：
  - 輸入：一張 `.kicad_sch` 轉出的 PDF/PNG（pdftoppm 150-200dpi）。
  - 輸出：ink%（非背景像素比）、內容 bbox 佔版面比。
  - **toolchain gating**：缺 pdftoppm/poppler/PIL → 回 `measurement_unavailable` + 缺項清單，不偽造度量（repo 天條）。pdftoppm 渲染本身依賴 KiCad CLI/poppler，屬 worker 側能力；度量純像素統計屬 core。
  - 驗收門檻：design 暫定「draftsman ink% ≥ 2× 同 spec netlist 模式基準，且絕對 ink% ≥ 10%」。確切門檻在 planned 階段配 test-vectors 定案（避免過度擬合單一 spec）。

- **DD-7** **回歸測試確定性**：測試用固定小 spec（few-component + few-net），assert placement 座標穩定（byte-stable IR）+ ink% 在區間。force-directed 無 RNG 保證可回歸。PYTHONPATH 需含所有 package 子目錄（repo 慣例）。

## Risks / Trade-offs

- **R1** force-directed 收斂不穩 / 仍重疊 → 緩解：固定迭代 + 收斂後 AABB 檢查 + 確定性 gutter 重排兜底（非隨機）。
- **R2** sheet-fit 選頁邏輯讓既有下游假設 A4 的工具出錯 → 緩解：netlist 模式維持 A4；draftsman 模式才動態選頁，並在 result 標明選用頁。
- **R3** ink 門檻過度擬合單一 spec → 緩解：multi-spec test-vectors，門檻用相對倍數 + 絕對下限雙條件。
- **R4** net-degree clustering 在 star 拓撲（一顆 MCU 連所有件）退化成單一大群 → 緩解：允許 group 宣告覆蓋；clustering 對高 degree hub 做 degree-capping 切分（planned 階段細化）。

## Critical Files

- `packages/eda-bridge/bodesign_eda_bridge/composer.py` — placement 兩階段 + style 預設 + sheet-fit（主改）。
- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py` — 複用 `emit_kicad_schematic` / `_orthogonal_route` / `_bus_route` / `load_symbol` / `_snap_grid`（唯讀複用，不改幾何）。
- `packages/eda-bridge/bodesign_eda_bridge/<new>_ink_metrics.py`（暫名）— ink/bbox 度量，toolchain-gated。
- `services/mcp/server.py` — `compose_schematic` handler + schema 加 `style` 參數。
- `tests/` — placement 單元 + ink 回歸。

## Code Anchors

- `composer.py:33` `_auto_place`（待取代）
- `composer.py:49` 預設 `connection_style="label"`（待加 style 切換）
- `composer.py:62-68` Level-1 AI/tool placement split（保留語意）
- `kicad_emit.py:212` `emit_kicad_schematic`（connection_style taxonomy）
- `kicad_emit.py:386` `_orthogonal_route`、`kicad_emit.py:406` `_bus_route`（複用）
- `kicad_emit.py:254-261` grid-snap
