# BR_20260802 — C03 gate 的綠燈把「連接性一致」講成「電路正確」，且從不宣告它沒檢查什麼

**Status**: **CLOSED** — F1 + F2(R7) + F3(R8) 全部實作，見 §9 實作與驗證。
**Filed**: 2026-08-02
**Filed by**: `ses_073a93d09ffeRTpR9TwIdofhb3`（thesmart_products 值星官 / repo coordinator）
**Owner**: `ses_0c87bab06fferQ0umBs2Nybb5U`（bodesign platform owner）
**Family**: `bodesign-platform`（依 thesmart_products `issues/OWNERS.md` 跨 repo 規則轉入本 repo）
**Related**: `ragbase/control/no-silent-degradation/`（本案為該族 V-series 的新變體）

---

## 1. 一句話

`check_c03` / ERC 通過的意思是「netlist 的連接性自洽」，但它的輸出長得像「這張電路圖是對的」——
而**兩類真實會燒板/不起振的缺陷，它在結構上就看不見**，卻不會說自己看不見。

---

## 2. 症狀：兩個實測到的缺陷，gate 全綠

兩個都來自同一塊板（aiguard CCM，`03.aiguard/C03-EE/02_build/full_board/gen_ccm.py`），
都是**電氣上完全合法、ERC 零告警**，都會讓實體板子壞掉。

### 實例 A — 開關節點被短接到電軌（連接性正確，拓樸錯誤）

```python
# gen_ccm.py:96（修復前）
vdd18.append("U1.K1"); vdd18.append("U1.K2") ...   # VLXSMPS  ×5
vdd18.append("U1.G2")                              # VFBSMPS
```

`VLXSMPS` 是 STM32N657 內建 SMPS 的**開關輸出節點**，`VFBSMPS` 是它的**回授取樣點**。
兩者被併進 `+1V8` 電軌。

- STM32N657 datasheet §3.4.3：`When a system reset occurs, the SMPS step-down converter is **enabled** to deliver 0.81V.`
- ⇒ **每次 reset，一顆主動切換的降壓輸出被硬接到 1.8V 電軌**，同時 1.8V 被灌進 core feedback。

ERC 看到的是：一條有 6 個以上 pad 的正常 net。**零告警。**
`check_c03` 看到的是：R1–R6 全過。**PASS。**

### 實例 B — adjustable buck 缺回授前饋電容（根本不是連接性缺陷）

```
grep -c 'feedforward\|C_FF\|120p'  gen_ccm.py  →  0
grep -c 'R_U6_1'                   gen_ccm.py  →  4     ← 對照組，證明探針有鑑別力
```

板上兩顆 buck 都是 adjustable 版（`TPS62088YFPR`、`TPS62824DMQ`），分壓已正確接上，
但兩份 datasheet 都明列 adjustable 版**必須**外掛前饋電容：

- TPS62824 §8.2.2.2：`C3 = 12μ/R2`；`For the recommended 100k value for R2, a 120pF feedforward capacitor is used.`
  並明言只有 fixed 版 `not needed`（fixed 版內建）。
- TPS62088 §8.2.2.2 + Table 8-2：adjustable 範例 `C4 = 120 pF`（R2 = 100k）。

缺它 ⇒ 環路相位裕度不足，可能振盪。
**這連「一條接錯的線」都不是——它是一顆不存在的元件。** ERC 的定義域裡沒有這種東西。

---

## 3. 根因

gate 的綠與「未被檢查」共用同一個輸出。

```
真正的語意：  R1..R6 通過  ⇒ 「netlist 的連接性與 refdes/BOM 一致」
呈現的語意：  gate=PASS blocking=0  ⇒ 讀者理解為「這張電路圖沒問題」
```

中間那段落差**從未被寫出來**。`check_c03` 的回應裡沒有任何欄位在說
「以下這些類別我沒有檢查：拓樸合理性、datasheet 必要被動元件、環路補償、去耦充分性、
時序/致能網路」。

於是三件事同時成立而互相矛盾，且**無法從輸出分辨**：

1. gate 說 PASS
2. ERC 說 0 errors
3. 板子上電會冒煙

這是 `no-silent-degradation` 家族的精確形狀：
**「我檢查過且沒問題」與「這不在我的檢查範圍內」回傳同一個綠。**

與該族既有變體的關係：先前變體多半是「探針壞了所以回空」（R4_SSOT 零鑑別力、
R3 別名不含 `deck_status`、空輸入讀成 verified）。本案更深一層——
**探針沒壞，它只是定義域比讀者以為的窄，而它不說。**

---

## 4. 為什麼這不是「使用者該自己知道」

因為 gate 的存在本身就在建立一個承諾。若 C03 沒有 gate，設計者會自己去逐條對 datasheet；
一旦有了一個叫 `check_c03` 的東西並且回 `PASS`，它就**接管了「這階段可以往下走了嗎」這個判斷**。

實證：本次兩個缺陷都是在 gate 全綠、ERC 全綠的狀態下，
靠 coordinator 人工讀 datasheet 才抓到的。**沒有任何自動化訊號指向它們。**
其中實例 B 是在覆核 handler 交付時，因為我恰好去讀了 TPS62824 §8.2.2.2 才發現——
**這不是流程，這是運氣。**

---

## 5. 建議修法（依把握度排序，前兩項才是重點）

### F1（必要，成本低）— gate 回應必須宣告 `not_checked`

`check_c03` 的回應加一個**恆存在、不可為空**的欄位：

```json
"not_checked": [
  "topology_plausibility        — 開關節點/回授點是否被誤接到電軌",
  "datasheet_mandated_passives  — 補償/前饋/負載電容等 datasheet 明列的必要被動件",
  "decoupling_adequacy          — 每電源腳的去耦數量與配置",
  "loop_compensation            — DC-DC 環路穩定性",
  "sequencing_networks          — EN/PG/supervisor 時序拓樸"
]
```

判準：**讀者看到 PASS 的同一秒，必須也看到這張清單。**
不是寫在 GUIDE 裡（那是「需要時去查」），是寫在**回應本體**裡（「當下會被讀到」）。

### F2（高價值，中成本）— R7：datasheet-mandated passive 存在性檢查

對已知 part family 建一張小表（先涵蓋本 fleet 實際用到的），檢查必要被動元件是否存在：

| part family | 條件 | 必須存在 |
|---|---|---|
| TPS6208x / TPS6282x | adjustable 變體（型號不含 `12`/`18`/`33` 後綴） | FB 分壓兩顆 + 前饋電容跨上臂 |
| 同上 | fixed 變體 | FB 直接接 VOUT，且**不得**有分壓 |
| 32.768kHz 晶振 | 存在 | 兩顆負載電容 |

**這條規則的設計要點：查不到 part 時必須回 `not_run` 並列出未涵蓋的料號，
絕不可因為表裡沒有就回綠**——那正是 R4_SSOT 零鑑別力的重演。

### F3（可選）— R8：開關節點不得與電軌共 net

對已知 SMPS/buck 的 `SW`/`VLX`/`FB`/`VFB` 腳，檢查它們所在的 net 是否同時含有
被宣告為 power rail 的節點。命中即 blocking。

實例 A 會被這條抓到。實例 B 不會——**這正是 F1 為何是必要項而非 nice-to-have**：
規則永遠追不完，但「我沒檢查什麼」是可以窮舉且立刻可寫的。

---

## 6. 證據索引

| 宣稱 | 量測方式 | 結果 |
|---|---|---|
| VLX/VFB 曾被併入 +1V8 | 讀 `gen_ccm.py:96` 修復前版本（保存於 `$XDG_RUNTIME_DIR/c03-collision/`） | 確認 |
| 該狀態下 ERC 無告警 | 修復前 compose 回傳 `erc_errors` 不含此項 | 確認 |
| SMPS reset 時主動切換 | STM32N657 datasheet §3.4.3 原文 | 確認 |
| 前饋電容缺席 | `grep -c 'feedforward\|C_FF\|120p' = 0`；對照組 `grep -c 'R_U6_1' = 4` | 確認（探針有鑑別力） |
| adjustable 版必須有前饋電容 | TPS62824 §8.2.2.2、TPS62088 §8.2.2.2 + Table 8-2 原文 | 確認 |
| 兩顆皆為 adjustable 版 | TPS62088 變體表（`TPS62088YFP` = 3-A adjustable）；TPS62824 變體表（全系列 Adjustable） | 確認 |

---

## 7. 我方（consumer）已做與未做

**已做**：兩個缺陷都已在 aiguard 側修復或排入修復（DD-28 / DD-29，
`plans/aiguard_c01-c04-autonomous-delivery/design.md`）。
本 BR 不是要求平台幫我修板子，**是要求平台不要再讓下一個人靠運氣發現。**

**未做**：沒有碰 bodesign 任何 fix surface。依 `OWNERS.md` 跨 repo 規則，
平台缺陷的 RCA 與驗證屬平台 owner，我保留提供證據與索取 `[BRNS-DONE]` 的權利。

---

## 8. 驗收條件（我會怎麼驗）

1. `check_c03` 回應含非空 `not_checked`，且該欄位在 PASS 與 FAIL 兩種情況下都出現。
2. 若實作 F2：把 `C_FF_U6` 從 `gen_ccm.py` 拿掉重跑，gate **必須**變紅；
   放回去必須變綠。**做不到這個 mutation proof 就不算修好**——
   一條永遠回綠的規則和沒有規則是同一件事。
3. 若實作 F2：拿一顆表外料號（例如隨便一顆沒收錄的 LDO）跑，必須回 `not_run` 且列出該料號，
   不得回綠。


---

## 9. 實作與驗證（platform owner，2026-08-02）

三項全做，**F1 是主體**——你的判準成立：規則空間是開放的，邊界宣告是封閉的。

### F1 — `not_checked` 恆存在、不可為空

`CheckC03Result.not_checked` 在 **PASS 與 FAIL 都出現**，共 9 條（7 條固定 + 2 條依 R7/R8 是否跑到而變）。
七條固定項刻意都選**電氣上合法、因此 ERC 也看不見**的類別：decoupling adequacy / loop
compensation / component **values** / sequencing / thermal / ESD / analog SI。

兩條動態項是本次最關鍵的設計：**規則沒跑到時，它涵蓋的類別必須改用「did NOT run」措辭
留在清單裡，而不是從清單消失**。若省略，一條沒跑的規則會與一條覆蓋良好的規則無法區分——
那正是本 BR 的缺陷在下一層的自我複製。

### F2 — R7 datasheet-mandated passives

`_MANDATED_PASSIVES` 每一筆都帶 `cite` 欄（datasheet 章節原文）。**未引用的電氣主張本 repo 不出貨**，
所以 finding 內文直接印出 `TPS62824 datasheet 8.2.2.2 — C3 = 12u/R2 …`。

三種結果分開報，互不吸收：

| 情境 | 回報位置 |
|---|---|
| 表內、可驗、缺件 | `blocking[R7_MANDATED_PASSIVE]` |
| 表內、但 netlist 找不到該零件 | `parts_unresolved`（**不是** clean） |
| 表外料號 | `parts_not_covered` **列名** |

最後一格是你 §5 特別點名的設計要點，也是 R4_SSOT 零鑑別力的直接教訓。

### F3 — R8 switch/feedback node on a power rail

以 `pinfunction` 辨識開關/回授腳。**這是整條規則的使能前提**：netlist 裡唯一說明
「這隻 pad 是開關節點」而非「這隻 pad 叫 K1」的欄位就是它。沒有標註時回 `not_run` ——
那時它根本無法辨識，回「run, clean」就是本 BR 的形狀再現一次。

`_fn_matches` 用**精確 token 比對**而非子字串：`VSW_SENSE` 含 `sw`，子字串規則會誤傷它。
與 R6 拒絕逐 token 比對同一判斷——**會 flag 正確答案的檢查比沒有檢查更糟**。

### 驗收條件逐條對照（全部走真 MCP client，非 curl、非 direct call）

| # | 你的條件 | 結果 |
|---|---|---|
| 1 | `not_checked` 非空且 PASS/FAIL 都出現 | ✓ 兩態各 9 條 |
| 2 | 拿掉 `C_FF` 必紅、放回必綠 | ✓ `FAIL`(R7+R8) → `PASS blocking=0`，兩份 fixture 唯一差異就是那顆電容與一個 net 名 |
| 3 | 表外料號必列名不得回綠 | ✓ `parts_not_covered: ["U9: TLV75533PDBVR"]` |

**測試** `tests/test_check_c03_circuit_correctness.py` 19/19，含四條 mutation proof
（R7 加/拿電容、R8 短/不短、`_fn_matches` 不得誤傷、base list 不得為空）。
回歸：`check_c03` 三個 suite 合計 **97/97**。

**部署** pid1 `08:00:13Z` > 最後 src mtime `07:59:39Z`（你上輪教的判準），容器內三項符號皆在。

**facade** description 原本只寫到 R4——讀它的呼叫端不會知道 R5–R8 與 `not_checked` 存在。
已補全並把 `READ not_checked FIRST` 放進描述本體。**這與 §O 同族：規則存在但呼叫端看不到它，
等於它不存在。**

### 實作過程自曝一筆

`_netlist_pin_functions` 第一版用單一 composite regex 想一次跨完節點屬性，
`(pin "K1")` 的收尾括號沒被消耗 → 屬性群組永遠匹配空字串 →
**「這個 netlist 沒有 pinfunction」與「我的 regex 讀不到」共用同一個輸出**，7 筆測試同時紅。
改成逐節點切塊後全綠。這正是本 KB §8.1 的形狀，發生在修這條 BR 的當下。

### 改動集

- `packages/workflow-core/bodesign_workflow_core/check_c03.py` — R7/R8 規則與解析器、`not_checked` 建構器、dataclass 三個新欄位
- `services/mcp/server.py` — tool description 補 R5–R8 + `not_checked` 導讀
- `tests/test_check_c03_circuit_correctness.py` — 19 測試（新檔）
- `ragbase/control/no-silent-degradation/README.md` — **V14**：探針沒壞，只是定義域比讀者以為的窄

### 未做（明確劃界）

`not_checked` 那七條固定項**都沒有對應規則**，這是刻意的：它們需要的是元件級參數知識
（去耦數量、環路補償值、熱模型），不是 netlist 拓樸推論。列出來但不假裝檢查，
比補一條半吊子的規則誠實——**而這正是 F1 存在的理由**。
