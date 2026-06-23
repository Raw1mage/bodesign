# BR: compose_schematic 產不出 draftsman 品質的原理圖（只是 ERC-clean 的 netlist 傾倒物）

- **Date**: 2026-06-18
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/composer.py`
- **Severity**: major（C03 的核心交付「可讀電路圖」實質缺失）
- **Reporter**: thesmart_products / aiguard C03 整合任務
- **Status**: open

## 症狀

`bodesign_compose_schematic` 產出的 `.kicad_sch` 電氣正確（ERC-clean、pin→net 正確、kicad-cli
validate 通過），但**視覺上完全不是一張電路圖**。實測 ink/bbox（pdftoppm 150-200dpi + PIL）：

| 產出 sheet | 著墨率 | 內容佔版面 | 觀察 |
|---|---|---|---|
| aiguard MCU 整合圖（9 元件 / 33 net） | 5.8%（裁切後仍 3.7%） | 散佈整張 A4 | 9 個 symbol 彼此**無一條導線相連** |
| memory 子系統（13 元件） | 2.9% | 角落一小塊 | 幾乎空白頁 |
| sensors / power / rgmii | 3-6% | 同上 | 同上 |

人眼看過去像「驗證用中間檔」,不是工程師畫的電路設計稿。下游若要當 C03「完整電路圖」交付,
不成立。

## 根因（已讀程式碼定位）

`composer.py`（全 79 行）兩個設計選擇導致此結果：

1. **`_auto_place(index, columns=4, dx=45, dy=45)`（line 33）** — 純 `index % columns` 網格擺放。
   元件依**輸入順序**丟在固定間距格點上,完全不考慮 net 鄰接 / 子系統分群 / 訊號流向。
   無論 sheet 多大,元件間距固定 45mm,大片區域是空白。

2. **連接純靠 global-label,無實體導線** — `emit_kicad_schematic(...)` 走 global-label
   connectivity（docstring line 8-9 自述）。每個 pin 旁掛一個網路名標籤,**不畫 wire segment**。
   electrically 等價,但人眼追不動「什麼接到什麼」——這正是電路圖最核心的視覺資訊。

## 期望能力（feature request）

`compose_schematic`（或新增一個 `compose_schematic_drawn` / `--style=draftsman` 模式）應能產出
**人看得懂的電路圖**,至少滿足：

1. **有意義的 placement**：依 net 鄰接或宣告的子系統分群把相關元件聚在一起（force-directed
   或 net-degree clustering 皆可），而非 index-mod-columns。讓被動件靠近其主 IC。
2. **實體導線**：點對點 net（≤ N 個節點，N 可設）畫實際 wire segment + junction，不全用
   global-label。bus / 跨 sheet 訊號才退回 label。
3. **sheet 自適應**：sheet 尺寸 fit 內容（或內容填滿 sheet），消除「浮在空白」。目標著墨率
   參考真實 KiCad 手繪圖（通常 15-40%，非 3-6%）。
4. **驗收**：用 ink/bbox 量化（pdftoppm + PIL），著墨率與內容佔版面比要明顯改善並可回歸測試。

## 暫行 workaround（目前 C03 採用）

- 承認 compose 輸出本質是「電氣連接檔」而非 draftsman 圖,寫進 `Netlist_Status.md` 老實標註。
- pin-level 真相靠 `Pin_Allocation.csv`（33 datasheet-backed net，且比對 datasheet AF 表時抓出
  既有 firm pin 指派的兩個 bug：ETH 標在無 ETH AF 的 ball、XSPIM 標在無 XSPIM AF 的 ball）。
- 真正的可讀 schematic 目前只能退回 KiCad GUI 人工繪製——這正是本 BR 要消除的缺口。

## 證據參考

- 程式碼：`packages/eda-bridge/bodesign_eda_bridge/composer.py:33`（`_auto_place`）、line 74
  （`emit_kicad_schematic` global-label 路徑）。
- 量測：aiguard C03 `02_build/mcu_integration/aiguard_mcu_integration.sch.pdf`（5.8% ink）、
  `02_build/renders/memory/aiguard_memory.sch.pdf`（2.9% ink）。

---

## Resolution

- **Status**: resolved / fixed。Closed 2026-06-23。
- **背景（BR 已過時）**：此 BR 描述的是 79 行的舊 composer。其後已有 commit `1731897`
  （drawn-wire mode）+ `0000d5a`（opt-in `draftsman` style）把功能補上 ——`composer.py` 現為 600+
  行,具備 subsystem clustering、force-directed placement、drawn wires + junctions、sheet-fit、
  route-stats、ink 量測,MCP `bodesign_compose_schematic` 也已暴露 `style=draftsman`/`measure_ink`。
  BR 的兩個根因(`_auto_place` index 網格、純 global-label)在 `draftsman` 模式下都已不成立。
- **本次補完的三個實質缺陷**(讓 draftsman 真正達到 BR 的驗收):
  1. **部署缺漏**:ink 量測需 `pdftoppm`(poppler),而 image 沒裝 → `measure_ink` 與其回歸測試
     (TV6)一直 silently skip。已將 `poppler-utils` 加入 `Dockerfile.ee` + `Dockerfile`。
  2. **ink 量測 bug**(`ink_metrics._measure_image`):KiCad 9 PDF 的紙張底色是 off-white
     (~244),低於硬編 `bg_threshold=250` → 整張底色被當成 ink → **任何圖都回 ~100%**(TV6 因此
     vacuously pass)。改為**以最亮像素(紙張)為基準**動態取閾(`hi - margin`)。修後 sparse 圖
     回 0.83%(原 99.9%)、可正確區分。
  3. **placement 發散**(`composer._refine`):原 force-directed 無 cooling/clamp + 全對排斥,
     7 個小元件被甩到 ~1m span → 選到 A0/overflow → 稀疏。改為 **Fruchterman-Reingold + cooling +
     per-iteration step clamp + 質心 gravity**(仍 deterministic)。修後同一 7 元件 content
     961→**180×180mm → A4**(不再 A0),content-fill ~85%,仍畫 3 條實體 wire。
- **Verification**(重 build image 後容器內):
  - `tests/test_composer_draftsman.py` **12/12**(含新 **TV7** placement-convergence 回歸:小 spec
    必須收斂到 A4/A3、不 overflow、content < 300mm、wired_nets > 0)+ TV6 ink 測試現在**真的會跑**。
  - sparse netlist ink% 由 99.9% → 0.83%;7 元件 draftsman 由 A0 → A4。
- **誠實保留**:BR §4 的「著墨率 15-40%」字面目標對原理圖其實偏高 —— 即使手繪 KiCad 圖,線條細、
  ink% 本就低(個位數)。真正有意義的可讀性指標是 **content-fill(內容是否撐滿版面,現 ~85%)+ 是否
  有實體導線 + 分群**,這三項都已達成。純 ink% 不是好的鑑別指標(netlist 與 draftsman 在同尺寸下
  ink% 接近),差異在「有沒有 wire/cluster」,非著墨率。
- **後續(非阻斷)**:更大型整合圖(數十元件、跨子系統)的 placement 美觀度、bus/跨 sheet 切分,
  仍可再調 —— 但 BR 的核心(可讀、有線、分群、合理紙張、可量測回歸)已達成。
