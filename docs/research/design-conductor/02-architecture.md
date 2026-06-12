# 02 — DC 系統架構（§2.2）

## 架構組成

```
┌─────────────────────────────────────────────────┐
│                   DC Core（頂層編排）              │
│   - 管理 subagents                               │
│   - 管理高階演算法（如 evolutionary search）        │
│   - 決定能力模組的組合方式（流程可由 DC 自行客製）     │
└──────────────┬──────────────────────────────────┘
               │
┌──────────────▼──────────────┐   ┌───────────────────┐
│  Worker Servers             │←→│  中央 DB（同步）     │
│  （管理 LLM sessions）        │   └───────────────────┘
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐   ┌───────────────────┐
│  Tool Servers               │   │ Context Management │
│  （VM / container 執行環境）  │   │ Module（監控所有    │
│   EDA 工具、模擬器在這層       │   │ in-flight sessions │
└─────────────────────────────┘   │ 的 context 用量）   │
                                  └───────────────────┘
┌─────────────────────────────────────────────────┐
│  Memory System（含 Knowledge Base）               │
│  - 記憶永久保存、全自主管理                          │
│  - onboarding codebase / ingest 需求時寫入          │
│  - 確保長程執行中所有需求不被遺忘                     │
│  - per-customer 隔離（單一 DC instance 服務單一客戶） │
└─────────────────────────────────────────────────┘
```

## 關鍵設計選擇

1. **工具極簡主義**：基本上只需要 **Bash、Edit、Subagent** 三種工具。複雜度放在編排層（DC Core）與知識層（memory），而非工具層。客製化版本與額外工具僅用於「提升品質」，不是必要條件。

2. **雲端分散式**：跑在分散式檔案系統上；LLM sessions 由 worker servers 管理、全部同步到中央 DB。執行環境（VM/container）與 LLM session 解耦——EDA 工具的重資源需求（數百 GB VCD、大量 DRAM）由 tool server 層吸收。

3. **Context 管理是一等公民模組**：獨立模組監控與控制所有 in-flight sessions 的 context window 使用，目標不只是防 overflow，而是**最大化決策品質**。

4. **記憶庫驅動需求遵循**：design requirements 進入 memory 後成為長程執行的「合約」，memory 是 DC「在數百億 token 中不忘記任何一條需求」的機制。

5. **流程本身是可塑的**：論文明確說 Figure 3 的流程「ultimately under DC's control, and DC can customize or modify it」。能力（capabilities）由系統提供，**組合方式（composition）由 DC Core 動態決定**——不是寫死的 pipeline。

## 對 bodesign 的啟示（指針，詳見 06）

- bodesign 目前是「MCP 工具 + client 編排」：工具層豐富但**沒有對應 DC Core 的長程編排層**，也沒有 per-project 的需求記憶合約。
- DC 的「工具極簡 + 編排智慧」與 bodesign 的「工具豐富 + 編排在 client」是兩種光譜端點；bodesign 的 workflow-core 可朝「宣告式 plan + 證據驅動 composition」演化。
