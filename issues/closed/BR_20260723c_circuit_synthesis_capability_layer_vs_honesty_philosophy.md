# BR_20260723c — bodesign 要不要長「circuit-synthesis 能力層」（代價：動搖 honesty 哲學）

- **狀態**: ACCEPTED（使用者 2026-07-23 拍板 **方案 C（有據建議）** + 授權 graduate 正式軌 C plan；consumer round=26 轉達）— 原為產品決策 BR，已收斂
- **severity**: strategic（不是缺陷，是能力方向 + 哲學紅線取捨）
- **owning repo**: bodesign
- **相關 plan**: `plans/knowledge_c03-ee-design-kb/`（校驗層軌 B + KB 軌 A，本 BR 的守哲學前置已在 implementing）
- **提出脈絡**: aiguard C03 consumer session（`ses_073a93d09ffe...`）與 bodesign platform-owner session（`ses_0c87bab06ffe...`）cowork 3 回合的產物；consumer 使用者已拍板「校驗層先上，合成層同步走 BR 決策」

---

## 1. 觸發痛點（consumer 使用者原話）

consumer 產出 aiguard MCU core 一頁原理圖後，使用者一眼判定：

> 「這是非常糟糕的產出物、內容是錯的、**沒有任何 circuit design 行為、不管怎麼改它只會畫元件原生 pinout 加 label**」

截圖具體症狀：52 個去耦電容排成規則網格、每個頂上 +1V8 底下 GND、**彼此零 wire 連線**；U1（STM32N657）是右邊一個空框、框內全空只有邊緣冒出零星 pin label。

## 2. 技術根因（已 RCA 坐實，非臆測）

bodesign 的 eda-bridge 引擎是 **net renderer，不是 circuit designer**。grep composer.py / kicad_emit.py / preplace.py 全部 `decoupl|pull.?up|topology|design_intent|obligation` 命中（42 處）：

- 所有 `decoupling`/`topology` 命中**全是幾何**：satellite snap（composer.py:564）、force-directed compaction（669）、gap_topology、L5 topology-preserving balance。
- `preplace.py:32 DECAP_MAX_F=1µF` 只是「≤1µF 算去耦」的**分類閾值**（擺位用），不是生成。
- **沒有任何一處**是「哪個 VDD 配幾顆去耦 / pull-up 選什麼值 / XSPI 串阻拓撲」的推導。datasheet 引擎 / block_drafter / symbol_index 也**無**半成品 design-intent 能力。

「circuit design intent → concrete net topology + passive 選型」這層推導，現在**完全落在 consumer（spec 作者）頭上**，引擎沒有這層。這一層就是使用者要的「circuit design 能力」。

## 3. 核心取捨（本 BR 要使用者拍的）

這層能力**撞 bodesign 核心天條**（AGENTS.md §2、`references/honesty-model.md`）：

> **「LLM only does upstream extraction / adjudication；驗證與比對全程不參與。」**
> bodesign 的價值是**展示**可靠度（對照良品 + 確定性驗證），**不宣稱**設計。

「引擎替人決定配 8×0.1µF + 2×10µF bulk、擺這裡」＝**引擎做設計決策**＝天條禁止的那類動作。做了就不再是「展示可靠度、不宣稱」的 bodesign。**這不是「做不做得出來」，是「做了還算不算 bodesign」。**

## 4. 三個候選方案（供使用者評）

### 方案 A：不做合成，只做校驗層（守哲學，最保守）
- passive-completeness gate（軌 B，**已在 implementing**）：校驗已起草的圖，active IC 零必要被動件 = HARD FAIL + gap 清單，但**補件的還是人**。
- **優點**：完全守哲學紅線，零風險。
- **缺點**：不解決使用者痛點的**目標態**——使用者要的是「從 intent 走到真正串好的電路」，校驗層只告訴他「缺什麼」，不幫他生。校驗是他能接受的**第一步**，不是終點。

### 方案 B：完整合成（intent → 引擎生 topology + passive 選值 + commit）
- 引擎替人拍板選型並直接寫進 spec。
- **優點**：直接命中使用者目標態，真正的 automation。
- **缺點**：**明確跨天條**。引擎宣稱了它沒驗證的設計。與 bodesign「不宣稱」的立身之本衝突。**不建議**，除非使用者願意重新定義 bodesign 的哲學。

### 方案 C：有據的建議合成（consumer 提出，可能是紅線內的合成）★
consumer 的關鍵洞見——**也許不是「引擎替人拍板選型」，而是「引擎依 KB graded 規則*建議* topology + 選值，標記為 draft/suggested、附 evidence source，人 review 後才 commit」**：

- 引擎輸出「建議」不是「決定」：每個建議的 passive（去耦 cascade、pull-up 值、load cap）都標 `draft`/`suggested` + 逐條 evidence source（KB 規則錨點 + datasheet 段）。
- **人 review 後才 commit** 進 spec——決策權留在人手上，引擎只做「有據的提案」。
- 合成的是「**有據的建議**」不是「**被宣稱的設計**」。
- **這可能是哲學紅線內的合成**：因為它從不宣稱設計已驗證，只說「依這條 KB 規則，這裡建議這樣，證據在此，你決定」——這正是 honesty-model 的 `draft`/`pending` + provenance 語義（honesty rule 2/3）。
- **依賴**：方案 C 需要軌 A（KB graded 規則可查詢）+ 軌 B（校驗 gate 知道缺什麼）當前置地基——這兩軌**已在 implementing**，所以方案 C 是它們的自然延伸，不是從零。

## 4b. 方案 C 活體 PoC 證據（cowork 已實作 + 閉環坐實，2026-07-23）

方案 C 不再是紙上提案——platform-owner session 已實作**第一個切片**並與 consumer 完成**完整活體閉環**，證明「有據建議」是可執行且守哲學的：

### 切片：I2C pull-up「有據建議」生成器
- 落地：`packages/eda-bridge/bodesign_eda_bridge/design_suggest.py::suggest_i2c_pullups`（純函式，deterministic、不 mutate、不寫檔），`tests/test_design_suggest.py` 13/13 綠。
- 對 consumer 真實缺口（aiguard SHARED_I2C，SCL/SDA 各只有 MCU 一端、零 pull-up）跑：
  - intent（4-device 開漏 I2C @ 400kHz / 150pF / +1V8）→ 算 `Rp_min=466.7Ω, Rp_max=2360.4Ω`（tr=300ns）→ chosen `2.2k`（窗內）
  - evidence 錨 `control.sch.pullup-termination-sizing` + 公式 `Rp_min=(VCC-VOL)/IOL, Rp_max=tr/(0.8473*Cb)` + provenance NXP UM10204（bus-spec grade）
  - `status=suggested`、`review_required=true`、`spec_fragment`（R_SCL_PU/R_SDA_PU 兩顆 Device:R 2.2k，可 review-then-paste）

### 完整活體閉環（consumer 雙重驗證：自數 + subagent 數）
**intent → 生成器算值（2.2k，錨 NXP UM10204）→ spec_fragment → 人 review → merge → wire compose → SHARED_I2C 首次有 pull-up 對接 + 有線**

| net | before（零 pull-up）| after（生成器建議 merge 後）|
|---|---|---|
| SHARED_I2C_SCL | `['U1.P2']` 1 node | `['U1.P2','R_SCL_PU.1']` 2 nodes |
| SHARED_I2C_SDA | `['U1.R1']` 1 node | `['U1.R1','R_SDA_PU.1']` 2 nodes |
| +1V8 | 48 nodes | 50 nodes（+R_SCL_PU.2, +R_SDA_PU.2）|

- compose: placed 52→54、nets:18、warnings:0；wire: 58→63（+5，pull-up 兩端接線）
- R_SCL_PU/R_SDA_PU 各 2 處真 symbol 引用、value=2.2k、footprint R_0402——標準開漏匯流排 pull-up 拓撲
- 產物：`~/GoogleDrive/Projects/thesmart_products/03.aiguard/C03-EE/03_output/aiguard_mcu_core_i2c_pullup.pdf`（287,667 bytes）+ 同目錄 `.kicad_sch`（91,582 bytes）+ merged spec `/run/user/1000/mcu-core-compose/spec_i2c.json`（54 元件，原 spec 未覆蓋）

### 為什麼這證明方案 C 守哲學（而非跨紅線）
每一步都守 honesty-model：生成器**只建議**（status=suggested，永不 committed）、值是**算的**（Rp 窗內，非硬編）、evidence 逐條錨 KB + datasheet provenance、**人決定 merge**（決策權留人）、引擎**不宣稱**設計已驗證。這正是「有據建議」而非「被宣稱的設計」——honesty rule 2/3 的 `draft`/`pending` + provenance 語義的活體實現。

### 誠實邊界（PoC 自標）
pull-up 到 +1V8 的連接可能部分走 label（power star net 慣例，非缺陷）；但 SHARED_I2C **訊號側** net node 確實 1→2、真 symbol 進圖、+5 wire——閉環電氣連接成立。這是「生成器建議被真正接進電路」的證明，不是紙上談兵。

### 後續切片（同範式，pattern 優先序 consumer 認同）
crystal load cap（verify+suggest 兩模式，對真 X1 載體）+ series termination（demo 待高速 interface 頁）——都走同一「compute + anchor + draft + spec_fragment」範式。這些是方案 C 的**能力擴展**，本身仍守哲學（建議非決定）；**是否把它們沉澱成正式的第三軌能力（軌 C），仍是本 BR 待使用者拍板的方向決策。**

## 5. 建議（platform-owner 視角）

- **短期**：軌 A（KB）+ 軌 B（校驗 gate）**繼續跑到底**——無論使用者選 A/B/C，這兩軌都是共用地基（合成也需先知缺什麼、依什麼規則）。這條**不 blocked、不需本 BR 拍板**。
- **方案 C 是最可能兼顧「使用者目標態」與「honesty 哲學」的路**，值得使用者認真評。它把「合成」重新定義為「有據的建議」，決策權留人，引擎不宣稱。若使用者選 C，它會是軌 A/B 之上的第三軌（新 plan）。
- **方案 B（完整合成）需要使用者明示願意動搖哲學才碰**——否則預設不做。

## 6. 待使用者裁決

1. bodesign 要不要長 circuit-synthesis 能力？（要/不要/只要方案 C 的有據建議版）
2. 若要，走方案 C（有據建議、人 commit）還是方案 B（引擎決定）？
3. 方案 C 若採納，是否另開 plan（軌 C），排在軌 A/B verified 之後？

---

## Fix venue
- 軌 A/B（守哲學前置）：`plans/knowledge_c03-ee-design-kb/`（implementing 中，本 session 執行）。
- 方案 C（若採納）：NEW plan，待使用者拍板後開。
- 本 BR：升使用者，不 agent 立案。
