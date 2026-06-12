# 06 — 差距分析：DC 工作流 vs bodesign workflow

> 對照基準：`specs/architecture.md`（2026-06 現況）、`specs/product/pcb_ai_viewer/`（living）、`specs/feature/eda-mcp-toolchain/`（living）。
> 目的：找出 DC 方法論中 bodesign 尚未制度化的部分，作為 workflow 強化與工具擴充的依據。

## 0. 兩者的同構與差異

**同構**（bodesign 已具備的 DC 式 DNA）：

- Spec 先行、living document（plan-builder lifecycle）
- Golden reference 對照（已知良品參考板交叉檢核——但見下方 oracle 不對等警告）
- 確定性驗證 gate 每個操作（ERC/DRC/SI/EMC 四層驗證 ≈ DC 的四層 oracle）
- 工具報告當 oracle（kicad-cli erc / DRC gate / pygerber 比對）
- 「展示可靠度而非宣稱可靠度」≈ DC 的「no vibe chip design」

**⚠️ Oracle 不對等（本分析的根本前提修正，2026-06-12 補）**：

DC 的領域專業（RTL/timing/PDK/Spike/OpenROAD）與 PCB 設計**零轉移**，且 DC 全自主能力的核心前提在 PCB 領域**不存在**：

- DC 有 Spike——一個**可執行的、cycle-accurate 的整體 golden model**，每條指令逐筆對答案；這是它能 12 小時無人閉環迭代的根本原因。
- bodesign 的參考板交叉檢核是**結構比對**（net 集合 matched/missing/extra），不是**行為驗證**——比 Spike 弱數個量級。
- SPICE 只覆蓋子電路，不是整板 oracle。
- PCB 最致命的失效模式（EMC、熱、機構干涉、bring-up）**無法在軟體迴圈內閉環**——要打板才知道。

因此「DC 式全自主」對 bodesign 是**結構性不成立**，不只是產品安全選擇。本文件的 G1–G7 全部站在 bodesign 自身程式碼缺口上（行號證據見 `07-architecture-improvements.md`），不依賴與 DC 的類比成立；論文僅是觸發偵查的透鏡。

**根本差異**：

| 維度 | DC | bodesign 現況 |
|---|---|---|
| 編排權 | DC Core 自主長程編排（12hr 不間斷） | client-orchestrated：workflow plan 只回報 blockers/gates，不自主執行 |
| 需求合約 | memory 中的需求合約，數百億 token 不忘 | spec 文件存在，但無「需求 → 量測 → oracle」的機器可查合約 |
| 迭代閉環 | 下游證據（P&R timing）自動反寫上游（proposal、RTL） | 驗證結果是報告，不自動驅動 IR 修改提案 |
| 變體探索 | 多變體全做到 GDSII 用真實數據裁決 | 單一候選 → 人審 → approve |
| Debug 資料化 | VCD→CSV→pandas，分歧點驅動 | 證據 overlay/cross-probe 偏人眼檢視 |

bodesign 的「user approval gate、AI 不直接出 final 檔」是**產品安全選擇**，不是落後——差距分析應聚焦在「approval gate 以內的自主性與證據品質」，不是移除 gate。

## 1. 可借鏡點（按 ROI 排序）

### G1 — 需求即合約：Requirement Contract（高 ROI，低成本）

DC §5.3 實證：**沒寫成可量測的目標就等於不存在**。bodesign 的自然語言規格 → 結構化計畫流程目前沒有強制「每個品質目標附 (a) 數值門檻 (b) 量測方法 (c) oracle」。

借鏡做法：

- 在 plan/requirements 結構中定義 `RequirementContract`：`{id, statement, metric, threshold, measurement_method, oracle_tool, status}`。
- 規劃階段的反問釐清（已有）強制收斂到此 schema；無法量測的需求標記 `unverifiable` 並要求使用者決策。
- 每輪驗證自動產出 per-requirement 的 pass/fail 表 —— 對應 DC 的「CPI counter 對 Spike trace」自我量測。
- 落點：`workflow-core` + design-ir 的 plan schema。

### G2 — 實作前設計審查（Design Review Gate）（高 ROI，純流程）

DC 在寫 RTL 前由 subagent 做「manual and painstaking」的情境推演審查（7 情境 cycle-by-cycle trace、CRITICAL/MAJOR/MINOR 分級、APPROVE 裁決）。

bodesign 對應：在 IR 生成 / subsystem composition 之前，對 layout plan / 子系統設計做**紙上審查**：

- 情境清單（電源時序、reset 鏈、I2C 位址衝突、電平相容、差分對拓撲…）
- 逐情境推演 + 分級結論 + 裁決，產出 review 文檔作為 evidence
- 落點：workflow-core 的 plan 節點之間插入 `design-review` 節點；可先純 prompt/skill 化（skills/bodesign），不需要新工具。

### G3 — 分歧點驅動的對照 debug（Diff-first Cross-check）（高 ROI，中成本）

DC 的 debug 鏈：golden trace vs actual trace → **第一筆分歧** → 帶時間戳的因果證據鏈 → root cause 四段式報告。

bodesign 的交叉檢核目前產出 confidence/overlay，但缺「結構化 diff + 第一分歧點」機制：

- 對照已知良品時輸出**結構化差異清單**（net-by-net、pad-by-pad、rule-by-rule），排序後從第一筆關鍵分歧開始分析。
- Root cause 報告標準化（methodology / findings / evidence / fix）—— 寫入 events。
- 落點：`gerber-core` 輸出比對已有雛形（output comparison）；缺的是 IR-level diff 工具與報告 schema。

### G4 — 驗證證據資料化（人眼產物 → 可程式查詢）（中 ROI，中成本）

DC 把 VCD 轉 CSV 用 pandas 分析。bodesign 對應：DRC/ERC/SI 報告、Gerber 比對結果應有**機器可查的結構化輸出**（JSON），讓 agent 能寫 ad-hoc 分析腳本，而不是讀 log 文字。

- 現況：部分工具已回傳結構化結果（si_check 的 effective values 等），但跨工具沒有統一 evidence schema。
- 落點：定義跨工具的 `ValidationEvidence` envelope（tool、inputs、findings[]、severity、anchors）。

### G5 — 多變體並行探索（Variant Race）（中 ROI，高成本）

DC 把 1-cycle/2-cycle branch penalty 變體全部做到 GDSII 再用真實數據裁決。bodesign 對應：對 layout plan 的關鍵取捨（2 層 vs 4 層、via-in-pad vs dogbone、不同 placement 策略）**各自完整跑到 DRC/SI/Gerber 再比較**，而不是事前用直覺挑一個。

- 前置依賴：G1 的 metric 合約（沒有量測標準就無法裁決變體）。
- 落點：workflow-core 的 candidate 機制天然支援多候選；缺的是「同 plan 多 variant 自動展開 + 評分比較表」。

### G6 — 反「大改衝動」的成本排序 gate（低成本，純紀律）

DC §5.1：timing 不過時模型先想大改 pipeline 而非找簡單原因。對應 bodesign：DRC/SI 失敗時，工作流應強制「先檢查簡單解釋（規則參數、單一 net、footprint 錯誤）→ 才允許結構性重佈局」。

- 落點：skills/bodesign 的 debug 紀律段落 + workflow blocker 分類（`simple-fix-candidates` 先列出）。

### G7 — 需求記憶與長程編排（低優先；架構級）

DC Core 式的自主長程編排與 per-project memory 是大工程，且與 bodesign 的 client-orchestrated 安全模型衝突。短期不建議做 agent 自主迴圈；**G1 的 Requirement Contract 已能拿到 80% 的「不忘需求」效益**（每輪驗證對表）。

## 2. 不建議借鏡的部分

- **移除 approval gate 走全自主**：DC 場景是「終止前人不介入」；bodesign 的產品價值之一就是 user approval 與 client-owned storage，保留。
- **自建分散式 infra**：DC 的 worker/tool server 架構為晶片 EDA 的資源規模服務；bodesign 的 MCP + docker 足夠。
- **evolutionary search**：在 PCB 場景的變體數量遠小於晶片微架構空間，G5 的有限變體競賽即可。

## 3. 建議落地順序

| 階段 | 項目 | 形式 |
|---|---|---|
| P1 | G1 Requirement Contract + G6 debug 紀律 | schema + skill 文字，幾乎零工具成本 |
| P2 | G2 Design Review Gate + G3 結構化 diff/root-cause 報告 | workflow 節點 + 報告 schema + IR diff 工具 |
| P3 | G4 ValidationEvidence envelope 統一 | 跨 package 重構 |
| P4 | G5 Variant Race | candidate 機制擴充 |
