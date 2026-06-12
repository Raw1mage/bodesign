# 05 — 結果、LLM 弱點與未來流程（§4–§6）

## 結果數據（§4）

| 指標 | 數值 |
|---|---|
| CoreMark | 3261（≈ 2011 年 Intel Celeron SU2300 @1.2 GHz） |
| Clock rate | 1.48 GHz（目標 1.6，未完全達標但接近；人為 token 預算終止） |
| 面積（不含 cache） | 2809 µm²（ASAP7） |
| 時程 | 12 小時，全自主 |
| 輸入 | 219 字需求文件 |
| 最終 pipeline 特徵 | early branch resolution、early forwarding、4 級 Booth-Wallace 乘法器（單獨 2.57 GHz）——皆非輸入指定，DC 自行發現 |

## LLM 弱點清單（§5）— 「LLM hang-ups」

這些是論文觀察到的 frontier model 系統性弱點，**結論是仍需資深人類架構師在架構層引導**：

### 5.1 架構推理不足
- forwarding 初版常造成過長 critical path——只有看到 timing 結果後才理解並修正。這類知識人類靠經驗累積。
- 低估問題複雜度的反面案例：timing 不過時，第一反應是**大改（加深 pipeline）**而不是先找簡單解釋——浪費大量 token 的探索。
- 含義：**模型缺乏「先便宜假設、後昂貴重構」的成本排序直覺**，需要工作流層面強制（先檢查簡單原因的 gate）。

### 5.2 RTL/timing 心智模型錯位
- 模型會把 Verilog（事件驅動）當**循序程式**推理。
- 經典錯誤：以為「減少相依程式行數 = 縮短晶片 critical path」。
- 不影響功能正確性（因為有 oracle 校正），但拖慢 timing debug、燒 token。
- 推測成因：pre/post-training 中軟體程式碼佔比過重。
- 含義：**領域語義（物理/時序 vs 程式碼文本）的錯位要靠真實工具報告閉環校正**，不能信模型的領域直覺。

### 5.3 Spec 撰寫要求
- spec 必須「extremely deliberate, tight, and verifiable/measurable」。
- 實證：沒寫 CPI 要求 → 生出 branch/forwarding 顯著較差的處理器；寫了 → DC 自己加 cycle counter 對 Spike trace 自我量測 CPI。
- 含義：**spec 中每個品質目標都需要：(a) 數值門檻 (b) 量測方法 (c) oracle**。沒寫的目標等於不存在。

## 未來流程（§6）

### 擴展性（§6.1）
- 百萬行 Verilog codebase 不構成問題（13-stage OoO processor 測試通過）——靠 memory 中的 codebase 結構化資訊。
- 真正瓶頸：**需要該設計領域的資深架構師來操作 DC** 才能得到好結果。

### 組織重構（§6.2）
- 100 人做一個設計 → 多個小團隊**並行探索多個完整設計**（每個從概念到 GDSII）。
- 18–36 個月 → 3–6 個月。
- 專家角色轉變：從 tool-jockey → 架構與目標層面的判斷者；「experiment without guesswork」。
- **流程變革預言：verification 前置（front-load）**——先給 DC 整合測試，讓測試引導 RTL 實作（test-first 在晶片設計的版本）。
- 工具廠商影響：DC 吸收工具互動複雜度 → 降低切換成本與 lock-in，廠商回歸演算法品質競爭。
