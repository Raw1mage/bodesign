# BR: drawmiat C4 container 圖 render 退化成 legend-only（多 container 時主畫布空白）

- **Date**: 2026-06-24
- **Reporter**: TheSmartAI (orchestrator)
- **Target**: drawmiat 維護者（C4 render 路徑）
- **Type**: bug（render 輸出退化，無報錯）
- **Severity**: **medium** — 不影響 honesty model，但讓「C00 架構圖一指令到位」這條官方路徑產不出可用圖，逼使用者退回手寫 graphviz。
- **Origin task**: 完備 `thesmart_products/01.openmv` (aiguard) C00 — 要為 PRD 產一張 C4 系統架構圖嵌入 `C00_產品需求規格書.docx`。

---

## 1. 一句話

`drawmiat_generate_diagram(diagram_type="c4", ...)` 對一個含**多個 container** 的合法 payload（已先過 `drawmiat_validate_diagram` 回 valid）渲染時，產出的 SVG **主畫布空白、只剩右側 legend**（檔案 <2KB），不報錯也不回 warning — render 靜默退化。

---

## 2. 證據（本 session 實測）

| 步驟 | 工具 | 結果 |
|---|---|---|
| 1 | `drawmiat_validate_diagram(c4, container-level payload)` | **valid**（無 error） |
| 2 | `drawmiat_generate_diagram(c4, 同 payload, output_dir=C00 root)` | 回 ok，但產出 SVG 只含 legend，container/relationship 節點全未繪 |
| 3 | 改用本地 `graphviz dot`（13 節點）手繪 | 正常產出 `C00_系統架構圖.{png,pdf}`，已嵌入 docx（image1 237KB） |

對照組：同 session 的 IDEF0/Grafcet render 正常；只有 **C4 多-container** 這條路徑退化。

---

## 3. 影響

- 「C00 架構圖經 drawmiat 一指令到位」是 bodesign one-pass recipe 寫進 skill 的官方視覺路徑之一（`stage-structure.md` recipe：C00 drawmiat → graphviz fallback）。C4 render 退化使該路徑對任何**真實多模組產品**（aiguard 有 13 個節點）失效，只能走 fallback。
- 因為 render **不報錯**（回 ok + 一個空 SVG），一個信工具回值的 agent 會把空 legend 當成「圖已產出」直接嵌進交付 docx —— 與已修的「靜默假成功」同類風險模式。

---

## 4. 建議修復方向

1. **C4 container/component render**：定位多-container 時主畫布節點未繪的根因（疑似 layout/viewport 計算把節點排到畫布外，或 container 分組未進 draw loop）。
2. **fail-loud**：render 後若主畫布節點數 = 0 但 payload 有 ≥1 container，應回 `warning: empty-canvas` 而非乾淨 ok。
3. **迴歸測試**：加一個多-container C4 fixture（≥3 container + relationship），斷言輸出 SVG 含對應節點數。

---

## 5. 誠實邊界

- 本 BR 不阻塞 aiguard 交付（已用 graphviz fallback 產出合格架構圖並嵌入 docx）。
- 未提供 drawmiat 內部 code anchor（render 實作在 drawmiat repo，非本次勘查範圍）；symptom + 重現 payload 形狀已具足。維護者可用第 2 節重現步驟定位。
