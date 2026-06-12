# 01 — DC 七大關鍵能力（§2.1）

DC 被設計來實現以下能力。每一項都是「長程自主 agent 做晶片設計」的必要條件，對任何 EDA 類自主系統（含 bodesign）具參考價值。

## 1. 穩定長程執行（Stable Long-horizon Execution）

- 任務跨越**數百億 token**，必須持續朝目標收斂。
- 目標不是單一的，而是多目標組合：PPA（power / performance / area）+ 功能約束 + 架構輸入。
- 核心要求：**所有目標必須被持續記住並同時滿足**，不能在長程執行中遺忘任一需求。

## 2. Context 管理（Context Management）

- 必須給底層 LLM「做好決策所需的資訊」——不只是塞資料。
- 嚴格管理 context window 用量：不只防 overflow，更是**為了最大化輸出品質**（context 品質 > context 數量）。
- 由獨立的 context management module 監控所有 in-flight sessions。

## 3. 技術專精（Technical Mastery）

- 晶片設計需要特定領域的極深知識：資深 CPU 設計師的「tricks」與「recipes」。
- DC 必須達到能與領域專家順暢協作的知識水位。
- 實證：DC 自行實作出 Booth-Wallace 乘法器、early forwarding、early branch resolution——這些都不在輸入 spec 內。

## 4. 正確性與驗證（Correctness & Verification）

- 原文：「"Vibe chip design" is not an option when shipping millions of units.」
- 必須交付**可驗證正確**的設計，驗證成本在人類流程中常佔總支出 50% 以上。
- 對應手段：golden reference 對照（詳見 `04-verification-loop.md`）。

## 5. 探索與速度的平衡（Balancing Exploration & Speed）

- 設計空間巨大，必須探索才能達到最佳性能。
- 同時必須避免「rabbit hole」——在無止盡的局部優化中錯失整體目標。
- 要求**有紀律地管理 search/exploration**：每個探索分支都要有明確的評估終點（DC 的做法是把變體做到 GDSII 用真實數據裁決）。

## 6. 端到端操作（End-to-end operation）

- 人類晶片流程最痛的環節：tape-out 前夕為了 timing 或 corner-case bug 而**回頭改 RTL**——要撕掉先前的工作且引入新 bug 風險。
- DC 必須能做同樣的「晚期回改」，同時**保持對先前工作的完整記憶與 context**。
- 含義：工作流不是單向 pipeline，而是允許下游證據（P&R timing）反寫上游產物（design proposal、RTL）的迴圈。

## 7. 基礎設施（Infra）

- 晶片設計極度資源密集：VCD trace 動輒數百 GB、EDA 工具吃大量 DRAM。
- 可能需要多個 subagent instance 並行工作。
- Infra 必須具備世界級的**可擴展性與可靠性**——任務跑 12 小時以上，任何 infra 故障都會中斷長程任務。
