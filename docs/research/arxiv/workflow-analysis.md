# arXiv PCB/EDA Autonomous Agent 論文 Workflow 借鏡分析

> 日期：2026-06-12 · 來源：17 篇 e-print src（見本目錄各子資料夾）
> 目的：對照 bodesign 架構（MCP server + BoardDesign IR + Component Vault + KiCad bridge + 四層驗證），萃取可直接借鏡的 workflow 設計。

---

## 1. 各論文核心 Workflow 摘要

### 1.1 pcbGPT (2606.01188) — 最接近 bodesign 的競品

三元件架構：**Synthesis Agent + Component Tools + Validation Stage**，組成 generate → execute → repair 迴圈。

- **Component Search Tool**：NL query → 本地 KiCad library 的 symbol/pin/footprint 候選（embedding + lexical 混合檢索）。Prompt 強制查「元件類別」而非具體參數字串，促進 symbol 重用。
- **Component Information Tool**：datasheet → 300 DPI 逐頁渲染 + 文字抽取 → 45 頁/批 的 page-local 設計摘要 → 二階段 merge + dedup → 磁碟快取。**抽取失敗時回報「元件不可用」而非編造**，讓 agent 改選替代元件。
- **兩層驗證**：(1) 確定性——DSL 執行 + ERC（無效 symbol、非法 pin、缺 footprint、短路）；(2) 機率性——validation agent 以 datasheet 摘要為據做語意審查（缺 pull-up/decoupling、介面接錯、電壓域錯誤），回傳 **structured root-cause issue list** 餵下一輪修復。
- **AI-oriented DSL**（Circuit/Component/Net/Pin + `&` 運算子）關鍵特性：
  - pin 引用錯誤時**回傳該元件全部合法 pin 清單**（錯誤即修復指引）
  - 被動元件 value 格式強制正規化；非被動件禁用 value
  - footprint 立即驗證、fail-fast
  - `optional` 元件標記（區分必要結構與容許附加）
  - `FlexiblePin`（等效 GPIO 集合，評估時任一皆可）
- **Reference-first 確定性比對器**：required/optional 兩段式元件匹配 → pin 鄰域簽名 + Hungarian 全域指派 → 三項子分數 `S = 0.4·S_comp(Dice) + 0.2·S_attr + 0.4·S_conn`；對稱兩腳被動件 pin 正規化為 `__sym__`。
- **Web workflow**：persistent session、tool-call streaming、DSL/schematic 雙視圖、本地 KiCad 編輯後可續跑。

### 1.2 SchGen (2605.30345) — 表示法工程

- 5 個編輯操作 API（add_symbol / add_label / get_pin_location / connect_pins / write_out_all_wires）取代 raw s-expression。
- **相對座標**（錨定 center symbol）+ **pin-name 連線**；用 MDL / LZ complexity / val-loss 三指標量化「表示法可學性」，相對座標 + pin-name 全勝絕對座標與 wire-segment。
- 資料管線：多模態 LLM 從參考設計圖片 sketch 程式碼（迭代至無錯）→ 人工 20 秒校對 → schematic-to-code 反向轉換器（s-expression → graph → code）。

### 1.3 HWE-Bench (2603.18102) — 分階段生成 + 雙重驗證

- **四段認知管線**（模仿人類工程師，避免一次吐整張 netlist 的局部邏輯斷裂）：模組劃分（JSON schema）→ 元件指派（signal chain + pin 對映）→ 模組級 netlist → 系統級整合。
- 密集連線輸出改用**嚴格純文字語法** `netX: Component|Pin|Function`（regex 解析），避免 JSON 格式幻覺。
- 驗證 = 靜態規則（netlist → topology graph，pin 屬性 + 介面協定一致性閉環比對）+ **動態 SPICE 暫態模擬**（測試點電壓/電流須落在邏輯閾值窗，無過壓/過流/deadlock）。

### 1.4 PCBSchemaGen (2602.00510) — KG 壓縮 + 多階段驗證

- **Datasheet → Knowledge Graph**：36 種 pin role + 屬性 + 約束 + 隔離邊界，每顆 IC 從 ~16k tokens 壓到 ~300 tokens（30–70×）。
- 多階段驗證：syntax → ERC → bipartite graph（component–net）→ **VF2 子圖同構**比對 rule graph（拓樸骨架語意）。
- **Feedback 粒度 ablation**：detailed（精確到 pin/net/value）≫ concise（僅錯誤類型）≫ binary（pass/fail）。
- **已驗證 subcircuit library**：簡單任務通過的模組入庫，複雜任務檢索重用，顯著提升成功率。

### 1.5 CircuitLM (2601.04505) — 五段 multi-agent + OOD 護欄

- Identification（NER → 元件類別 JSON）→ Retrieval（vector KB + fuzzy 同義件查詢；**查無元件 → OOD flag → 停機要求人工**，嚴防幻覺接線）→ Electronics Expert（least-to-most CoT 文件：功能目標/電源/安全/pin 級接線邏輯）→ Circuit Generation（CircuitJSON：結構連接與 `attrs` 參數分離）→ Visualizer（force-directed + Manhattan 佈線，human-in-the-loop 拖拽）。
- **自製確定性 ERC engine**（networkx 拓樸圖 + pathfinding）：故障分級 Critical/Major/Minor/Warning；檢查器註冊表——短路、LED 限流電阻、pull-up、飛輪二極體、邏輯電平匹配、浮空輸入。

### 1.6 AnalogAgent (2603.23910) — 自我演化記憶

- 三 agent MAS：Code Generator / Design Optimizer（五段檢查：規格合規→DC 可行→DC-sweep→功能測試→波形 sanity）/ **Knowledge Curator**。
- **Self-Evolving Memory = Adaptive Design Playbook**：從成功與失敗萃取 compact 規則 → 衝突檢查（interface 約束 Ω）→ filter → dedup → 增量寫入；檢索按 task type 精確匹配，fallback 子字串匹配。動機：對抗長迭代的 **context attrition**（LLM 自行壓縮上下文導致細節流失）。

### 1.7 AnaFlow (2511.03697) — 成本感知升級階梯

四相位，**便宜檢查先行、昂貴工具後援**：

1. 理解相位：Circuit Explainer → Matching Finder（對稱/匹配約束標注）→ DC Goal Setter → Initial Designer
2. DC-OP 迴圈（只跑廉價 `.op`，限 5–10 輪）
3. Reasoning-only 全模擬迴圈（限 20 次 full sim）
4. Optimizer-equipped：**Advisor Reviewer 偵測停滯**（連續無改善 pattern）才升級呼叫 BO/RL，agent 自行配置 initial points 與模擬預算。

### 1.8 EEschematic (2510.17002) — Visual CoT 佈圖優化

- 四模態共享上下文：NL 描述 + SPICE netlist + schematic 圖片 + JSON 座標。
- 少樣本子結構範例集（差動對、電流鏡、cascode…）支撐 LLM 子結構辨識 → 初始擺放；**接線由確定性演算法**完成（net 分組 + 優先序 VDD→GND→Gate→Drain→…）。
- **Visual CoT 內迴圈**：渲染現圖 → MLLM 對照好/壞參考範例判斷是否需改 → 生成修改推理鏈 → 重渲染迭代。

### 1.9 PhIDO (2508.14123) — DSL 中繼 + 段界人工介入

- 四段：Interpreter（entity 抽取 + 既往設計 template 檢索）→ Designer（PDK 元件匹配 exact/partial/poor 三級評分 + 參數配置 + port 級 schematic）→ Layout（Graphviz DOT 擺放 + river router → GDSII → DRC）→ Circuit verification（SAX 模擬）。
- **YAML DSL** 為 NL 與工具碼之間的中繼表示；**每段邊界使用者可檢視/修改後再放行**。
- 系統提示五要素範式：角色定義 / 結構化上下文輸入 / 任務指令與規則 / 內嵌範例 / 輸出格式（Pydantic schema 強制）。
- PDK PCell 帶**標準化 docstring**（功能/port/用例/製程/關鍵參數）支撐 LLM 檢索。

### 1.10 MuaLLM (2508.08137) — 多模態混合 RAG

- 圖片不用 CLIP，改用 **LLM 生成描述再嵌入**（descriptive embeddings：內容類型/元件標籤/電路功能）。
- Hybrid 檢索：semantic + BM25 並行 → 加權合併 → Cohere rerank；contextual caching 降 API 成本。
- ReAct agent + 工具：search_db / paper_fetcher（自主抓 arXiv/Scholar 擴充知識庫）/ 動態 DB 更新 / YOLO+OpenCV schematic 圖片→netlist。

### 1.11 ORFS-agent (2506.08332) — LLM 指揮數值優化器

- 工具四類：**INSPECT**（檢視既有數據免逐值入 context）/ **OPTIMIZE**（GP surrogate 等模型）/ **AGGLOM**（從候選超參數中再篩選）/ **RETRIEVAL**（有界、可稽核的網路查詢）。
- Observe → Query → Alter 迭代；LLM 不取代 BO，而是**指揮** BO；支援平行 flow runs 與部分指標收集。

### 1.12 ChatEDA (2308.10204) — 開山之作

- `<requirement, decomposition, script>` 三元組 self-instruction 造 ~1500 筆資料 → QLoRA 微調；prompt 內固化 EDA flow 順序依賴（Setup→Synthesis→…→Final Report，前步未跑不得跑後步）。

### 1.13 SmartonAI (2307.14740) — KiCad 插件橋

- MainGPT/SubGPT 層級任務路由（20 個宏任務類別）→ DocHelper RAG → **JSON-RPC bridge 抽象 KiCad Python API**；插件以 YAML schema 描述，自動生成參數表單 + 型別驗證 + 結構化錯誤回饋給 LLM 摘要。

### 1.14 佈局/繞線 RL 三篇（2602.23540 / 2110.03939 / 1906.08809）

DRL 元件擺放、演化式繞線成本排序、DRL global routing——皆為單點演算法，無 agent workflow 可借，但確認：**佈局側的 LLM-agent 文獻幾乎空白**，bodesign 的 layout agent 沒有現成範式可抄，最近的類比是 ORFS-agent 的「LLM 指揮確定性工具 + 數值優化器」模式。

---

## 2. 對 bodesign 的借鏡建議（按優先級）

### P0 — 直接補強現有四層驗證與 IR

| # | 借鏡 | 來源 | 落點 |
|---|---|---|---|
| 1 | **錯誤即修復指引**：IR patch 驗證失敗時回傳「合法替代清單」（非法 pin → 列出該元件全部 pin；非法 footprint → 列出候選），讓 repair loop 一輪收斂 | pcbGPT DSL | `packages/source-core` patch validation、`packages/design-ir` |
| 2 | **Feedback 粒度鐵律**：所有 validator 輸出必須到 pin/net/value 級的 structured root-cause list；ablation 證明 binary pass/fail 幾乎無修復價值 | PCBSchemaGen | 四層驗證全部 validator 的錯誤契約（`errors.md`） |
| 3 | **Reference-first comparator 演算法**：required/optional 元件二段匹配 + pin 鄰域簽名 + Hungarian 全域指派 + Dice/attr/connectivity 加權分數（0.4/0.2/0.4）+ 對稱被動件 pin 正規化 + FlexiblePin 展開——這正是 bodesign「對照已知良品交叉檢核」缺的具體算法 | pcbGPT comparator | 交叉檢核層（驗證第 2 層） |
| 4 | **OOD halt 護欄**：元件知識庫查無 → 顯式停機 + 人工審查，絕不幻覺接線。與 bodesign fail-fast 天條完全同構，應寫入 workflow-core 的 blocker 語意 | CircuitLM | `workflow-core` blocker gates、vault `explicit absent` |

### P1 — 生成迴圈與知識管線

| # | 借鏡 | 來源 | 落點 |
|---|---|---|---|
| 5 | **Datasheet → 緊湊整合規則**：在 vault L3 chunks 之上增加 derived artifact——每顆 IC 的 pin-role 標注（~36 roles）+ 必要支援電路 + 約束，~300 tokens 可注入 prompt；原始 chunk 留作 evidence 回溯 | PCBSchemaGen KG + pcbGPT info tool | `packages/component-kb` L4/L6 |
| 6 | **Datasheet 摘要管線規格**：逐頁 300 DPI 渲染 + 文字、45 頁/批 page-local 摘要、二階段 merge+dedup、磁碟快取、逾時重試一次、**失敗回報不可用而非編造** | pcbGPT info tool | `packages/doc-core` 抽取管線 |
| 7 | **分階段生成**：模組劃分 → 元件指派 → 模組級 netlist → 系統整合；每段獨立 schema 驗證。bodesign forward-design（datasheet/參考設計 → 子系統組合 → IR）應固化此四段切分，禁止 one-shot 全板生成 | HWE-Bench | `workflow-core` 生成計畫 |
| 8 | **已驗證 subcircuit library**：通過驗證的子電路（IR 片段 + 證據）入 vault L6 reference-circuits，複雜設計時檢索重用——與「以參考設計為依據」哲學互補 | PCBSchemaGen + PhIDO template retrieval | vault L6 |
| 9 | **兩層驗證的語意層**：在確定性 ERC/DRC 之後加 LLM validation agent（以 vault 整合規則為據），抓 ERC 抓不到的「缺 decoupling / 介面 net 對調 / 電壓域錯接」；明確定位為 design-assistance，非 formal verification | pcbGPT validation agent | 驗證第 1↔2 層之間 |

### P2 — 長程運行與佈局側

| # | 借鏡 | 來源 | 落點 |
|---|---|---|---|
| 10 | **成本感知升級階梯**：驗證/優化順序固定為 廉價確定性檢查 → LLM 推理修復（限輪次）→ 數值優化器/全模擬（偵測停滯才升級）；每層有明確迭代預算 | AnaFlow | 佈局優化、SPICE/EMC 層調度 |
| 11 | **Adaptive Design Playbook**：驗證失敗/成功的教訓經 curator 整理（衝突檢查 + dedup）成增量規則庫，跨任務檢索注入——vault `knowledge_queue` 的天然下游 | AnalogAgent SEM | vault L6 + L8 |
| 12 | **LLM 指揮確定性工具**（佈局側範式）：placement/routing 不讓 LLM 直接吐座標，LLM 負責 Observe（INSPECT 工具讀指標摘要）→ Query（OPTIMIZE/AGGLOM）→ Alter（改 config/constraint），freerouting/pcbnew 做實際工作——與「AI 不直接 route copper」紅線完全一致 | ORFS-agent | C04 EDA bridge 工具設計 |
| 13 | **Visual CoT 審圖迴圈**：渲染 schematic/board 圖 + 好/壞參考範例 → MLLM 判斷是否需改 → 推理鏈 → 重渲染；適合 bodesign 已有的 render 能力做擺放品質迭代 | EEschematic | `/bodesign/` render + 佈局審查 |
| 14 | **段界人工介入範式**：每個 pipeline 段輸出皆可被使用者檢視/修改後續跑（非只有最終 approval）——對應 bodesign proposal/approval 流，建議擴展到中間 artifact | PhIDO | `workflow-core` + Candidates UI |
| 15 | **密集連線輸出用約束純文字語法**而非 JSON（`netX: Comp|Pin|Function`），regex 驗證後再轉 JSON——降低大 netlist 的格式幻覺 | HWE-Bench | AI→IR 操作的 wire 表示 |
| 16 | **多模態 RAG 細節**：datasheet 圖片用 LLM 描述後嵌入（非 CLIP）；hybrid semantic+BM25+rerank——vault L3 已有 FTS5/BM25，補語意側即成 hybrid | MuaLLM | vault L3 檢索 |

---

## 3. 定位確認（文獻空白）

- 17 篇中**沒有任何一篇**覆蓋 schematic → layout → manufacturing 全生命週期；最完整的 PhIDO（photonic）到 GDSII + DRC + 模擬為止，PCB 側全部停在 schematic。
- 「展示可靠度」路線（reference cross-check + 確定性比對器 + 多階段驗證）與 pcbGPT/PCBSchemaGen 的趨勢一致，但兩者皆無製造輸出與 fab 驗證——bodesign 的端到端 + Gerber 驗證定位在文獻上仍是空白區。
- 風險提示：pcbGPT 已做出 KiCad-native DSL + datasheet grounding + web session 工作流，與 bodesign 原理圖段重疊度最高，值得持續追蹤其 benchmark（含 failure taxonomy）作為對標。

## 4. 後續動作建議

1. 將 P0-3（comparator 演算法）立為獨立 spec：輸入兩份 BoardDesign IR，輸出三項子分數 + 匹配明細，作為交叉檢核層的核心。✅ **已落地**（2026-06-12，併入 `workflow_verification-discipline` P5/G7，`packages/design-ir/compare/`）
2. P0-1/P0-2 合併為「驗證錯誤契約 v2」：全 validator 錯誤結構統一帶 `valid_alternatives` 與 pin/net 級定位。（部分落地：P2 CrossCheckDiff + structured root-cause；`valid_alternatives` 仍待做）
3. P1-5 KG 壓縮做 spike：取 vault 現有一顆 IC 的 chunks，產 300-token 整合規則卡，量測對 emit 流程 prompt 的效益。

---

## 5. 補充檢索（2026-06-12 第二輪）— PCB 領域知識型論文

> 第一輪聚焦 agent workflow；本輪檢索 DFM / PI / EMC / datasheet 抽取 / schematic 辨識等**領域知識**方向。新增 2 篇 source（`2506.10577_gnn-optimizing-components`、`2601.22114_sina`），其餘以摘要評估。

### 5.1 值得納入（建議優先序）

| # | 論文 | 核心知識 | bodesign 落點 | 評級 |
|---|---|---|---|---|
| K1 | **GNN 自動補強元件**（2506.10577，已拆 src） | PCB schematic → 二部圖（net 節點 ↔ symbol 節點，pin 為邊；節點名用 sentence-transformer 嵌入，**無需人工標元件類型**）。三個監督任務直接是 EE best practice：補 pull-up/pull-down、reset pin 加 RC filter、電源 pin 加 decoupling cap。pre-filter MLP + node-pair 預測控制計算量 | 與 P1-9（LLM 語意審查層）互補：語意審查抓「缺 decoupling/pull-up」可以用此**確定性圖表示法**做候選生成，LLM 只做裁決。bipartite graph 表示法也可直接強化 comparator 的 pin 鄰域簽名 | **P1** |
| K2 | **D2S-FLOW**（2502.16540）+ **DocEDA**（2412.05301） | datasheet → 電氣參數抽取 → SPICE model 自動生成；DocEDA 加 layout-analysis 模型處理文件版面 | vault L3→L4 spec 抽取管線的直接參考；bodesign 的 SPICE 驗證層（第 3 層）目前無自動 model 來源——這是缺口 | **P1** |
| K3 | **SINA**（2601.22114，已拆 src） | schematic 圖片 → netlist：YOLO 偵測元件 + **CCL 連通域抽 wire**（遮罩元件後對剩餘線路做 connected-component labeling）+ OCR refdes + VLM 只做語意裁決。**雙系統 concordance 信心分數**（YOLO vs VLM 不一致即 flag 人工） | 參考設計匯入管線：bodesign「以參考設計為依據」需要把 datasheet 內 reference schematic 圖片轉 IR——SINA 的「確定性視覺處理 + VLM 只裁決」分工與 bodesign 紅線一致；concordance 信心分數可直接借鏡 | **P1** |
| K4 | **AMSnet-KG**（2411.13560） | schematic-netlist 配對資料集 + **知識圖譜 RAG**：電路結構知識（topology→功能標注）入 KG，LLM 設計時檢索 | vault L6 reference-circuits 的知識組織參考：subcircuit topology + 功能標注 + KG 檢索，比純 FTS5 更結構化 | P2 |
| K5 | **Fast PDN Impedance**（2106.10693）+ **Power Plane Gen**（2210.16314）+ **Hierarchical Decap RL**（2407.04737） | PDN 阻抗 DL 預測（任意板形/疊構）、GA+MLP 自動電源平面生成、decap 配置 RL 優化 | 佈局側 PI 驗證的長期參考——bodesign 目前 SI 檢查有 si_check，**PI（電源完整性）層完全空白**。屬第 4 層 EMC/熱分析的鄰接領域 | P2 |
| K6 | **DevFormer**(2205.13225) | decap placement 的 transformer 解法：相對位置嵌入 + 動作置換對稱性等 inductive bias 對抗資料稀缺 | 若未來做 learning-based 佈局優化的方法論參考；近期不動 | P3 |

### 5.2 不納入（評估後排除）

- **PhysEDA**（2605.10547）：IC 級 placement/routing 的物理先驗注意力——晶片尺度，與 PCB 佈局的耦合太弱。
- **PDNPulse**（2204.02482）：PCB 異常**偵測**（安全/供應鏈），非設計知識。
- **AnaFlow/AnalogAgent 系**已在第一輪涵蓋；AMSnet 2.0/AMSnet-q 是資料集工程，KG 版（K4）才有方法論價值。
- EMC 檢索結果均為量測硬體論文（近場探頭等），無設計規則知識可借。

### 5.3 結論

- **真正的新知識集中在三條線**：(1) 圖表示法上的 EE best-practice 補強（K1）、(2) datasheet→SPICE/參數自動抽取（K2）、(3) schematic 圖片→netlist 的確定性視覺管線（K3）。三者都直接對應 bodesign 已知缺口（語意審查候選生成、SPICE model 來源、參考設計圖片匯入）。
- **PI（電源完整性）是文獻有、bodesign 沒有的驗證維度**（K5）——第 4 層分析的擴充候選，但依賴佈局側成熟度，不急。
- 與第一輪結論一致：**沒有任何論文覆蓋製造輸出側**，bodesign 的端到端定位依然是空白區。
