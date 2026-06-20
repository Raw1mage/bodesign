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
