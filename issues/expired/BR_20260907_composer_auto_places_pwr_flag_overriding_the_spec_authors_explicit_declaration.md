# BR_20260907 — composer 自動擺放 PWR_FLAG，覆蓋 spec 作者已寫下理由的顯式決定，產生 3 個 ERC pin_to_pin error

- **Status**: OPEN（未修 · 本單只立案取證，未動 code）
- **Severity**: MEDIUM（產出可用，但 ERC 不乾淨；且屬「自動化覆蓋顯式宣告」類，
  修法牽涉契約而非單點）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:2201-2203`
  （「Each distinct power net also gets ONE PWR_FLAG on its first port」）、
  `:2209` `flagged_nets`、`:2278-2287` 實際擺放
- **Filed**: 2026-09-07 by handler `ses_f87134d36ffe7Bgm4z5GclPidc`，
  依 btdongle 真板 baseline 量測 session `ses_f871fc491ffeUC3rImkn99fop4` §Issues-4 取證立案
- **Family**: schematic-engine
- **HEAD at filing**: `ded8b95`
- **Related**:
  - `issues/BR_20260905_router_corner_and_stacked_pins_short_declared_no_connect_pins.md` §4.2 —
    **同一判準的另一次適用**。該單對 `D1.5` 的結論逐字是：「**兩者都是 owner 的設計決定，
    不該由 emitter 代為裁決**」。本單是同一句話的另一個違反點：`PWR_FLAG_NETS` 是 owner
    已經做出並寫下理由的決定，emitter 不看就覆蓋。**該單建立的判準，本單援引。**
  - `issues/BR_20260905_compose_schematic_lacks_multi_unit_symbol_support.md` §4.6 —
    **同一未量邊界的兌現**。該單自陳「**ERC 告警內容未逐條讀**：只證明 kicad-cli 未拒絕檔案，
    未審視個別 violation」。本單是第一次真的逐條讀 ERC 的結果，補上該單留空的那格。

---

## 1. 症狀

btdongle 真板 ERC：**3 errors, 106 warnings**。三個 error 全屬 `pin_to_pin`：

```
pin_to_pin  #FLG0002 ↔ U2.3
pin_to_pin  #FLG0001 ↔ U2.36
pin_to_pin  U2.3     ↔ U2.33
```

`#FLGxxxx` 是 composer 自動擺放的 PWR_FLAG。它們落在 **`U2` 本來就以 power-output
驅動的軌**上，於是 KiCad 判定「兩個 power output 短在一起」。

---

## 2. 這張單的 framing 是「自動化覆蓋顯式宣告」，不是「ERC 有 error」

**spec 作者已經做過這個決定，而且寫下了為什麼。** `design.py:297-305` 逐字：

```python
# PWR_FLAG marks a rail whose source is OUTSIDE the schematic. It must go ONLY
# on nets that have no power-output pin of their own -- putting one on a rail
# that a chip already drives makes ERC report two power outputs shorted
# together (measured: 5 pin_to_pin errors when flags sat on SYS/BATT/+3V3/GND,
# which are driven by U1 pin 1, U1 pin 14, U2 pin 36 and U2 pin 3/33).
#
# VBUS_CON enters from the USB connector and VBUS sits behind the fuse; every
# pin on both is passive, so these two are the only rails needing a flag.
PWR_FLAG_NETS = ["VBUS_CON", "VBUS"]
```

三件事同時成立，這是本單的全部重點：

1. **作者做了決定**：只有 `VBUS_CON` / `VBUS` 要 flag。
2. **作者寫下了理由**，而且**那個理由本身是量出來的**（「measured: 5 pin_to_pin errors
   when flags sat on SYS/BATT/+3V3/GND」）——作者已經踩過這個坑並記錄。
3. **我方引擎不看，直接覆蓋**：`kicad_emit.py:2201-2203` 的策略是
   「Each distinct power net also gets ONE PWR_FLAG on its first port」——
   **每一條** power net，無條件。

**注意作者記載的 pin 與 ERC 報出的 pin 逐字對上**：作者寫「driven by ... U2 pin 36 and
U2 pin 3/33」，ERC 報的正是 `#FLG0001↔U2.36`、`#FLG0002↔U2.3`、`U2.3↔U2.33`。
⇒ **這不是一個新問題，是作者三個月前就量過並主動避開的那個問題，被引擎重新製造出來。**

`U2.3 ↔ U2.33` 這一格值得單獨看：它**不含 `#FLG`**，是 `U2` 自己兩支 power-output pin
之間的衝突。作者的註解已涵蓋它（`U2 pin 3/33`），且它在作者的配置下不會被報成 error
——因為沒有第三方 flag 把它們拉進同一個 driver 衝突判定。**這一格能否單靠移除 flag 消除，
本單未量**（見 §5）。

---

## 3. 為什麼「ERC 有 error」是錯的 framing

若把本單寫成「ERC 有 3 個 error，去修掉」，下一個 handler 最可能的動作是
**調整 ERC 規則或加豁免**——那會重蹈 `BR_20260905_router_corner...` §5 記載的死路
（該單實測：加豁免後 gate 轉綠、而短路仍實際存在，是**真的假綠燈**）。

正確的讀法是：**引擎有一個無條件策略，它踩掉了一個使用者可宣告的意圖。**
ERC error 只是這件事的**症狀**。修 ERC 而不修覆蓋關係，下一塊板會以另一種形式再爆。

---

## 4. Proposed（**方向，不是實作** — 本單未動任何 code）

**核心**：`PWR_FLAG` 的擺放要能被 spec 顯式指定，且顯式宣告優先於自動策略。

1. **spec 支援 `pwr_flag_nets` 欄位**：作者給了 ⇒ **只**在這些 net 上擺 flag，
   自動策略完全不介入。
2. **作者沒給 ⇒ 維持現行自動策略**（不改變既有行為，避免回歸）。
3. **自動策略本身可以更聰明，但那是次要**：現行「每條 power net 都給」可改為
   「只給**沒有任何 power-output pin** 的 net」——那正是 `design.py:297-299` 寫的規則，
   而且引擎有能力判斷（它讀得到 pin 的 electrical type）。
   **但這不能取代第 1 點**：即使自動策略正確，作者仍必須能覆寫它。
4. **不得靜默**：若自動策略被顯式宣告覆寫，或自動策略跳過了某條 net，
   應在 `route_stats` 或等價的揭露欄位留下記錄
   （對齊 code-thinker §12：每個狀態要指名它的排放點）。

### 4.1 修法必須自帶的控制組

- **正控制**：btdongle spec 帶 `pwr_flag_nets=["VBUS_CON","VBUS"]` ⇒
  ERC `pin_to_pin` error 數必須下降，且 `#FLG` glyph 數必須 = 2。
- **負控制**：不帶該欄位的既有 spec ⇒ `#FLG` 數與修改前**逐字相同**（61 個 `#PWR` /
  3 個 `#FLG`，量測 session §⑤）。證明沒有誤傷既有路徑。
- **回歸控制**：`tests/test_kicad_emit.py` 維持綠，判別欄位取 `Ran N` 而非 rc
  （AGENTS.md §5），跑前清 `__pycache__`（AGENTS.md §6.3）。
- **反向控制**：一條真的沒有 driver 的 power net，在**帶** `pwr_flag_nets` 但未列入它的情況下
  ⇒ 應出現 `power_pin_not_driven`。證明關掉自動策略確實會讓該報的照報，
  而不是把兩種錯都一起消音。

---

## 5. 明確排除項：105 個 `lib_symbol_issues` 不立案

同一份 ERC 另有 **105 個 `lib_symbol_issues`** 與 1 個 `same_local_global_label`。

**`lib_symbol_issues` ×105 是環境問題，不是引擎缺陷**：輸出目錄沒有 `sym-lib-table`，
KiCad 因而無法把嵌入的符號定義對回庫。**本單不涵蓋、不立案。**
（若未來要處理，那是輸出目錄結構的議題，與 PWR_FLAG 無關。）

`same_local_global_label` ×1 **本單未查**，不主張它與本單相關。

---

## 6. 邊界宣告（引用本批讀數者必須一併帶走）

本單引用的讀數來自 btdongle fixture。**這塊板沒有被製造、組裝或量測過**——
`design.py:44-46` 自陳：「no board here has been fabricated, assembled, or measured.
Charge current, buck output and antenna performance are design targets computed from
datasheet formulae, never bench results.」

這批讀數是有效的**幾何／連通性**回歸母體，**不是**已驗證的電氣行為基準。
**任何電氣宣稱不得引用它。**

本單特別需要這條：ERC 是**規則檢查**，不是量測。「ERC 乾淨」不代表電路會work，
「ERC 有 error」也不代表板子不能動。本單主張的是**引擎覆蓋了作者意圖**，
不是「這塊板有電氣缺陷」。

---

## 7. 量了什麼 / 沒量什麼

**一手量測（本單 handler）**：
- `design.py:297-305` 的 `PWR_FLAG_NETS` 宣告與其完整理由註解（逐字引用）
- `design.py:44-46` 的邊界自陳（逐字引用）
- `kicad_emit.py:2201-2203` 的自動擺放策略自陳、`:2209` `flagged_nets`、`:2278-2287` 擺放點
- 作者註解記載的 pin（`U2 pin 36`、`U2 pin 3/33`）與 ERC 報出的 pin 逐字對應

**轉述（來源 `ses_f871fc491ffeUC3rImkn99fop4` §Issues-4 與 §⑤，本單 handler **未**複現）**：
- ERC 結果：3 errors / 106 warnings、三條 `pin_to_pin` 的具體配對
- `lib_symbol_issues` ×105 與其歸因（無 sym-lib-table）
- `same_local_global_label` ×1
- `#FLG` glyph 數 = 3、`#PWR` = 61

**本單 handler 的推論（標明為推論，非量測）**：
- §2「這不是新問題，是作者已量過並主動避開的問題被重新製造」——
  依據是 pin 編號逐字吻合，但**未實際跑「照作者配置擺 flag」的對照組**去確認 error 會消失。
- §4 的修法方向與 spec 欄位設計。

**沒量**：
- **未跑對照組**：沒有實測「只在 `VBUS_CON`/`VBUS` 擺 flag」是否真的把 3 個 error 降到 0。
  **這是本單最該補的一格**，修法落地前應先做。
- **`U2.3 ↔ U2.33` 是否單靠移除 flag 即可消除，未量。** 它不含 `#FLG`，
  有可能是獨立成因（兩支 power-output pin 直接相連），移除 flag 後仍在。
  **不要假設三個 error 是同一個原因。**
- **未量作者所稱「5 pin_to_pin errors」的可複現性**——那是 `design.py` 註解裡的歷史記載，
  本單直接引用，未驗證。
- **未盤查其他 fixture** 是否也被自動 flag 策略覆蓋。母體未知。
- **視覺軸完全未量**。
