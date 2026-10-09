# BR_20260905: draftsman connection strategy degenerates to a label-farm on non-label-friendly topology (independent of multi-unit flatten & collinear fusion)

- **Status**: OPEN
- **Severity**: P1 (blocks any consumer needing a真-schematic deliverable, not just a netlist connectivity dump)
- **Filed by**: thesmart_products C03 line (guest) — session `ses_038683542ffeGuJMbvxiu9eYXI`
- **Engine**: `bodesign_eda_bridge.compose_schematic` (`packages/eda-bridge/`), rev `603d784542e9` (container `bodesign-pkcs12-bodesign-ee-1`)
- **Related (NOT duplicates — see §6)**:
  - `BR_20260905_compose_schematic_lacks_multi_unit_symbol_support.md` (缺陷一 multi-unit flatten)
  - `BR_20260723e_draftsman_cannot_wire_basic_series_divider_collinear_fusion.md` (缺陷二 collinear fusion)
  - `BR_20260905_schematic_emitter_produces_pin_label_stubs_only_zero_pin_to_pin_wires_and_zero_junctions.md` (消費端 emitter，已改判 venue)

---

## 1. 一句話

即使**繞過**已立案的兩個缺陷（關閉 fidelity gate，避開 multi-unit flatten 與 collinear fusion 的攔截），`compose_schematic` 的 draftsman 連線策略對 btdongle 這類「多小元件 + 串聯鏈 + 高扇出 GND」的載板拓樸，仍退化成 **label farm**——110 條 wire 裡 74% 是 ≤5.2mm 的 pin→label 短樁，只有 5 個 junction，沒有任何一組被畫成可辨識的連通子電路。這是**獨立於前兩個缺陷**的第三個問題，且不是消費端能修的。

## 2. 為什麼這是使用者「回報數百次修不好」的真根因

thesmart_products 的 owner 反覆回報「C03 電路原理圖畫不出真電路、只是接線表」。前手一直在消費端繞道（自寫 `mk_sch.py` → `mk_sch_bodesign.py` bridge → `mk_sch2.py`），或等引擎修那兩個 gate 缺陷。但**真正卡住的是引擎的畫線策略本身對此類設計不畫子電路**——那不是消費端能修的，也不是修好 gate 缺陷就會消失的。這張 BR 把那第三層剝出來。

## 3. 決定性實驗（矩陣四格，把 btdongle design.py 直接餵引擎）

`connection_style` 全程未傳（讓 style 自行推導，避開 explicit_conn 陷阱）。產物落 `/run/user/1000/btdongle-draftsman-exp/`（scratch，未入任何 repo）。

| 變體 | style | validate | fidelity | 結果 | wired | labelled | junctions | ERC |
|---|---|---|---|---|---|---|---|---|
| v1 | draftsman | T | **T** | **FidelityError 擋下** | — | — | — | — |
| v2 | draftsman | T | **F** | 通過 | 11 | 16 | 7(route)/5(emit) | 3 |
| v3 | draftsman | F | F | 通過（與 v2 byte 同） | 11 | 16 | 7/5 | — |
| v4 | **netlist** | T | F | 通過 | — | — | **0** | 3 |

## 4. 關鍵證據：第三缺陷獨立於前兩個

**(a) v1 gate 擋下的正是前兩個已立案缺陷，不是本 BR。** v1 FidelityError 原文：
```
FIDELITY FAIL moved=10 only_baseline=2 only_candidate=2
  MOVED: D1.1 F1.1 J1.A4 J1.A5 J1.A9 J1.B4 J1.B5 J1.B9 R1.1 R2.1   ← VBUS/CC 熔合（BR_20260723e 家族）
  ONLY_BASELINE: D1.3 D1.4                                          ← multi-unit 壓平（multi_unit BR）
```

**(b) 關掉 gate（v2/v3）繞過前兩缺陷後，退化仍在，這是本 BR 的本體。** v2/v3 的 warnings 明載：
```
anti-fusion guard down-graded 3 net(s) to label to avoid cross-net collinear wire fusion:
  ['CHG_LED_A', 'LED_WIFI', 'VBAT_SENSE']
```
gate 已關，但連線策略**自己主動**把 3 個串聯鏈 net 降級回 label 來避免共線熔合。這證明：即使沒有 gate 攔截，引擎面對串聯結構的預設反應就是「放棄畫線、改掛 label」。

**(c) 幾何量測坐實 label farm（v2 draftsman sch）：**
- wire=110，但 **74%（81/110）是 ≤5.2mm 的 pin→label 短樁**
- 真正的長線只有幾條：1104mm / 1065mm / 615mm — 都是**橫跨整張圖的 GND/SYS/BATT 匯流排**，不是局部子電路走線
- junction 只有 **5 個**（route_stats 報 7，emit 落地 5，內部/落地落差 2，一併列為邊界）
- **沒有一組 RC / 分壓梯 / LED+電阻串聯被畫成連通子電路**

**(d) netlist style（v4）更純粹：junction=0，每個連接都是 label 旗標，零條元件對元件實線。** 這是設計上的純網表連通圖，不是缺陷——列出只為對照 draftsman 沒比它好多少。

## 5. 對照組戳破「引擎能畫專業圖」的假象

- **對照 A：aiguard C03（同一引擎，netlist style，「看起來專業」）** — 機制與 btdongle netlist **完全相同**（大 IC + 每根 pin 掛 label + 整齊去耦電容陣列各自掛 +3V3/GND）。它看起來專業**不是因為引擎會畫子電路**，是因為 **aiguard 的拓樸天生適合 label farm**：一顆巨大規則 IC + 電容陣列，沒有串聯/分壓結構要畫。把同一引擎餵給有串聯鏈的 btdongle，專業感立刻消失。**這條線索否證了「aiguard 證明引擎能畫好 draftsman 圖」。**
- **對照 B：btdongle mk_sch2 自寫版（消費端，視覺 QA 判 FAIL）** — 反而畫了最多真實長線（一堆平行匯流排），但纏成鼠窩、label 堆疊。兩頭不到岸。

## 6. 為何不是前三張 BR 的重複件

| BR | 追蹤的缺陷 | 與本 BR 的關係 |
|---|---|---|
| multi_unit_symbol_support | `EmitComponent.unit` 從未被讀，multi-unit pin 展平重合 | 本 BR 在**它被繞過後**仍成立（gate off，D1 崩塌不再攔截，退化照舊） |
| BR_20260723e collinear_fusion | anti-fusion guard 對串聯鏈的共線重疊漏洞 → FidelityError | 那是「guard 攔截後報錯」；本 BR 是「guard 為了避免熔合，**主動放棄畫線改掛 label**」——同一 guard 的另一個後果面 |
| stubs_only（消費端 emitter） | `mk_sch.py` 硬編碼短樁 | 那是消費端腳本、已改判 venue；本 BR 是**引擎原生**產物 |

本 BR 的獨特命題：**anti-fusion guard 的降級策略把「避免短路」買在「不畫電路」上，對 label-unfriendly 拓樸退化成 label farm。** 這是連線策略的設計問題，不是某個 pin 座標的 bug。

## 6.5 QA 獨立驗證的修法方向（消費端兩顆 fresh-eyes QA 各自提出，收斂一致）

消費端對 mk_sch2.py 產物跑的**三顆獨立 fresh-eyes QA**（power/mcu/io 各一，看不同 sheet、互不通訊），各自獨立提出**同一個**繞線策略修法方向，與本 BR 同一格（消費端調不動、屬引擎繞線層）：

> **二端點被動件必須就地放在它旁路的那支 pin 邊、另一端接本地 GND 符號，完全不進 trunk；只有 3+ 端點且跨遠距的 net 才上 trunk。**

現況根因：`route_net_on_row()` 的結構是「每個 net 一律先落 trunk 再分配」——這對二端點被動件（去耦、限流、分壓）是過度泛化，它們本該就地直連。trunk-bus 觀感即源於此。io QA 還點出一個直接成因：GND/+3V3/SYS/BATT 目前是右側六角 net-label 旗標，非放在使用點的接地/電源符號——每個零件的接地回路都是一條 1200px 水平線跑去角落旗標。**三顆 QA 彼此獨立、看不同 sheet、互不通訊，卻收斂到同一修法方向，這一格的證據強度比任何單顆都高。** 這是繞線策略層的變更，供 schematic-engine owner 修復時參考。

## 6.6 探針盲區更正（消費端誠實回報，補強「退化被結構性漏看」的證據）

消費端先前回報的「true ink crossings 0（帶控制組）」是**比表面更窄的問題**——那支 per-primitive 探針的障礙物集合只有 symbol 的**圖形**圖元（graphics_bbox），文字欄位（reference/value/global label 本體與字面）從不在集合裡。所以那個 0 的正確讀法是「沒有走線穿過符號的圖形筆畫」，不是「沒有走線壓過任何可讀的東西」。

**三張 sheet 全中**。三顆 QA 在渲染圖上實測到大量**文字穿越**，探針結構上看不到：
- mcu：垂直 trunk 穿過 `RaspberryPi_Pico_2W` 字面（2 處）；6~7 條垂直線穿過 6 個 label 框內與字面；水平 trunk 穿過 `C11`/`100nF` 字面。
- power：8 條 trunk 直接穿過 `J4 / USB_C_16P` 的字，2 個 junction 圓點落在字裡。
- io（三顆裡量測最硬的一份）：逐 label 數出垂直走線穿過字面的條數（LED_WIFI 5、BATT 4、VBAT_SENSE 3、SYS 2、GND 1），附反鎖齒混色像素數（37/12/55/28/39）證明是**覆寫字形**非擦邊，控制組三格齊全（空白區 0px、已知走線帶 2288px、label 區 3812px）。

這是「缺席態與失敗態共用同一輸出」的又一例：**0 是探針沒看，不是沒有**。對本 BR 的意義：label farm 退化不只讓子電路消失，還讓 trunk 與 junction **壓在可讀文字上**——這在純幾何 junction 計數上量不到，是本 BR §7 判準之外需要視覺軸補的一格。

## 7. 可機測驗收判準（修好後 consumer 端可驗）

以 btdongle design.py（45 元件 / 27 net，含串聯鏈與 multi-unit D1）為驗收語料，draftsman style、fidelity gate ON：

1. **junction > 20**（目前 5；label farm 的定量反面）
2. **短樁（≤5.2mm pin→label）佔 wire 比例 < 40%**（目前 74%）
3. **anti-fusion guard 降級回 label 的 net 數 = 0**，或降級後仍保留可辨識子電路實線（目前降級 3 個串聯鏈 net 且無實線替代）
4. **至少能數出 N 組可辨識子電路**（current-limit / decoupling / 分壓）被畫成連通實線 + junction，而非各 pin 掛 label
5. fidelity gate 必須同時 PASS（不得靠關 gate 換取 junction）

## 8. 邊界（誠實列，這些沒量）

1. **視覺 QA 非獨立第三方**：定讞實驗的 subagent 無 task 權限，親自單一觀察者看圖，強度低於三顆獨立 fresh-eyes。
2. **只渲染整板單 sheet**：未套消費端的三 sheet 拆分 + SHEET_REMAP。三 sheet 拆分後 draftsman 是否對「sheet-local 小網路」畫得較好，未測——這是 H2 殘留的一絲可能性（sheet 拆分是消費端可控的），但不改變「引擎預設對整板不畫子電路」的主結論。
3. **未測其他 style / 參數**（macro_compact、page_fill、density_budget）是否能誘使引擎多畫 junction——只測矩陣四格。
4. **route_stats junctions=7 vs emit 落地 5** 的 2 個落差未深究來源。
5. **未獨立重證前兩個已知缺陷**（採信 bodesign 值星官既有裁決）。

## 8.5 真板實驗結論（2026-09-05，engine handler `ses_f8e7c4f04ffe`，dispatcher 裁決後定案）

這一節是**給未來 handler 的路標**。上面 §3-§7 是立案時的觀察；這一節是拿真 spec
（`04.btdongle/C03-EE/02_build/sch_gen/design.py` — **注意有 `sch_gen/` 一層**，
少這層會 rc=1，而「查錯路徑」與「檔案不存在」共用同一個輸出）實測後的裁決。

### 8.5.1 探針與語料的正控制組（先證明量測本身可信）

HEAD 引擎 + 真 spec + fidelity OFF（＝§3 v2/v3 的方法學），獨立重現 §4(c) 四格：

| 量 | 本輪實測 | §4(c) 原文 |
|---|---|---|
| wire | 111 | 110 |
| junction | 5 | 5 |
| 短樁佔比 | 73.0% | 74% |
| anti-fusion 降級 net | 3 | 3 |

四格獨立吻合 ⇒ 探針有判別力、語料是對的。**後續數字才有資格拿來比。**

### 8.5.2 被否決的修法：power clustering（open-circuit 缺陷）

嘗試過的修法：把同一 power net 的 pin 依鄰近度分群，每群畫成實線 daisy-chain
共用一顆 port glyph（意圖直接對應 §6.5 QA 提的「本地 GND 符號」方向）。

**幾何上全面成功，電氣上把電路接錯：**

| | junction | 短樁% | 子電路 | fidelity `moved` |
|---|---|---|---|---|
| HEAD | 5 | 73.0% | 3 | **10** |
| clustering 開 | 43 | 32.7% | 11 | **67**（多出 `open circuit` 機制）|

決定性隔離（同一份 code，只切 `_POWER_CLUSTER_MM`）：
- `R=0`（clustering 關）→ `moved=10`，與 HEAD **逐字相同**
- `R=200`（clustering 開）→ `moved=67`

⇒ regression **100% 來自 power clustering**，signal 片段化無辜。

**RCA（根因，留給未來那一單）**：cluster hop 只對其他 net 的**已註冊 wire segment**
做防護（`_guard_route` / `fusion_registry`），對其他 net 的 **pin 座標**沒有防護。
一個還沒長出 wire 的 pin 對 fusion registry 是隱形的，但 **KiCad 仍會把穿過該 pin 的
wire 熔進那個 net**。所以「沒有已註冊線段相撞」與「電氣上安全」**不是同一個謂詞**，
而合約要的是後者。試加 foreign-pin guard（拒絕穿過任何非本 net pin 的 hop）後
`moved 67→58`，仍遠差於 10 ⇒ **殘餘成因未定位，需要動 anti-fusion 幾何本身**。

**這一格的教訓比修法本身重要**：這個缺陷讓**每一個幾何判準都變漂亮**
（§7 判準 1/2/4 全部大幅達標）**同時把 net 接錯**。若驗收只看 §7 的 1/2/4，
這會是一份漂亮的綠燈交付。**判準 5（fidelity）是唯一擋住它的東西**——
這正是「格式/幾何綠燈不授權任何內容/電氣正確性宣稱」的實例。

### 8.5.3 被保留的修法：signal 多節點片段化

`_bus_route` 消費端路徑原本是 all-or-nothing：**一個 hop 被擋就丟棄整個 net**
（含已成功繞出的其他 hop），退回 per-pin label。改為斷點切片段、每片段掛 net 名
local label（未進任何片段的 pin 保留 per-pin label）。net partition 與舊 fallback
**完全相同**（都靠同名連通），差別只在可繞的結構被保留成實線。

真板實測：`moved=10`（與 HEAD 逐字相同，**不引入 regression**），
junction 5→6、短樁 73.0%→70.4%、子電路 3→4。**效果小但乾淨。**

附帶的判別力改善：`fusion_label_fallbacks` 新增 `drawn_fragments` 欄，
把「整個 net 丟光」（=0）與「只丟一個 hop」（>0）分成不同輸出——
兩者需要不同的修法，原本共用同一則 warning。

### 8.5.4 真板 fidelity 永遠不會因本 BR 轉綠

**HEAD 在真板上本來就 fidelity FAIL**（`moved=10`），signature 是
`MOVED: D1.1 F1.1 J1.A4/A5/A9 J1.B4/B5/B9 R1.1 R2.1`（VBUS/CC 熔合）
+ `ONLY_BASELINE: D1.3 D1.4`（multi-unit 壓平）——**逐字就是 §4(a) 的 v1**，
也就是**另外兩張 BR**（`multi_unit_symbol_support` 與 `BR_20260723e`）。

⇒ **§7 判準 5 在真板上與本 BR 的修法無關，必須先解掉那兩張 BR 才可能轉綠。**
未來 handler 不要試圖在本 BR 範圍內讓真板 fidelity PASS，那不是本 BR 能達成的。
本 BR 的幾何數字（判準 1/2/4）在真板上一律是 **fidelity OFF** 下量的。

### 8.5.5 門檻的 scale 依賴（立案時未預期）

§7 門檻（junction>20、短樁<40%）是照真板 45/27 校的。用 28/21 的合成語料測會得到
**假未達標**（clustering 版：合成 junction 21/短樁 41.5% 看似擦邊未達，真板卻是
43/32.7% 大幅達標）。**驗收語料規模不對，會讓判準說謊。**
未來驗收一律用真 spec，合成語料只能當補充。

## 9. 建議

這是引擎 `schematic-engine` 的連線策略問題，不是消費端能修的。thesmart_products C03 交付依 owner 裁決**暫時阻斷、等引擎修**，不在消費端繞道、不粉飾。修好後 consumer 端會依 §7 判準跑驗收（每項配控制組）。

---

## 附：證據檔

- `/run/user/1000/btdongle-draftsman-exp/matrix_results.json`（矩陣四格完整 kwargs + gate 原文 + stats）
- `/run/user/1000/btdongle-draftsman-exp/png/{v2_draftsman_fid_off,v4_netlist,refA_aiguard_netlist,refB_btdongle_mk_sch2}.png`（四張並排圖）
- btdongle SSOT: `04.btdongle/C03-EE/02_build/design.py`（45 COMPONENTS / 27 NETS）
