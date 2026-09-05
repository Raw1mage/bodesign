# BR_20260905 — schematic emitter 產出的是「pin 掛 label」的接線表，不是電路原理圖：pin-to-pin 實線 0 條、junction 0 個

- **Status**: OPEN — **修法已落地（bodesign `95d6241`）但消費端零效果。見 §10，本 BR 存在 venue 誤判**
- **Severity**: **P0 — 立身能力缺陷**。交付物在客戶眼中不是原理圖，這是本產品線 C03 的核心可交付物
- **Filed**: 2026-09-05 by `ses_f95148a02ffenF83aJE6hX1paA`（thesmart_products handler，04.btdongle C03 交付線）
- **Filed for**: bodesign 值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH`（`[★]main`）
- **Family**: `schematic-engine`（owner `ses_03408d1faffeKuPkQZ9Zj6gWO2`，依 `issues/OWNERS.md`）
- **Reporter venue**: 消費端 repo `thesmart_products`，產物 `04.btdongle/C03-EE/02_build/generated/sch/`
- **Fix venue**: bodesign repo 內修。**本 BR 只做取證與規格定義，不含修法**

---

## §0 使用者原話

> 「C03 的交付物中，電路原理圖是一團屎。它無法正確表達元件對元件之間的 pinout 相關性，以及中間必要的各種 RC、RL、LC、LRC 電路，它只能繪製每個單元件的單獨存在，甚至還畫歪爆框，整張紙只有角落擠一小塊圖，其他地方一片空白。**這是我回報了數百次都修不好的 bug。**」

同一位使用者另外交付了一張他認定為業界標準的原理圖作為基準，本 BR §3 把那張圖蒸餾成可驗收的數值規格。

**「數百次都修不好」這句話本身是本 BR 最重要的一格輸入。** 本 repo `issues/` 內同族前例至少六張，跨越 2026-07-06 到 2026-08-02，全部 CLOSED 或 OPEN 未結，而症狀在 2026-09-05 的新產品線上原封不動復現。**復發本身就是證據：前幾次修的是症狀。**

---

## §1 一句話

`compose_schematic` 產出的 `.kicad_sch`，**每一條 wire 都是「單一 pin 拉 5.08 mm 到一個 global_label」的短樁**；全圖 pin-to-pin 實線 0 條、junction 0 個、被動件全部單腳懸掛。它是一份用 KiCad 格式書寫的接線表，不是原理圖。

---

## §2 取證（04.btdongle C03，2026-09-05 實測）

量測對象：`04.btdongle/C03-EE/02_build/generated/sch/btdongle_{mcu,power,io}.kicad_sch`。

### §2.1 決定性的一格：wire 數恰等於 global_label 數

| 分頁 | symbols | wire | global_label | junction | 被動件 R/C/L |
|---|---|---|---|---|---|
| `btdongle_mcu` | 9 | 29 | **29** | **0** | 6 |
| `btdongle_power` | 27 | 69 | **69** | **0** | 14 |
| `btdongle_io` | 14 | 26 | **26** | **0** | 8 |

wire 與 global_label 三頁三組完全相等，不是巧合。

### §2.2 逐條 wire 的端點分類

把每個 `global_label` 的 `(at x y)` 收集成座標集合，再比對每條 wire 的兩個端點：

| 分頁 | 兩端都是 label | **一端是 label（短樁）** | 兩端都不是 label（pin-to-pin 候選） |
|---|---|---|---|
| `btdongle_mcu` | 0 | **29** | **0** |
| `btdongle_power` | 0 | **69** | **0** |
| `btdongle_io` | 0 | **26** | **0** |

**124 條 wire，124 條是短樁，0 條 pin-to-pin。**

wire 長度分布佐證同一件事：三頁的 median 全部是 **5.08 mm**，恰為 KiCad 預設格距的兩格（2.54 × 2）。`mcu` 與 `io` 兩頁的 min = max = 5.08 mm，**全部 55 條長度完全相同**——這是「每支腳往外拉一格再貼 label」的機械輸出特徵，不是佈線。

### §2.3 junction = 0 的結構後果

RC、RL、LC、LRC 這幾類網路的共同必要條件是**至少一個節點有三個以上的連接端**（元件 A 的腳、元件 B 的腳、以及往下游的線）。在 KiCad 的表述裡，那個節點必須是一個 `junction`。

**junction 全域為 0 ⇒ 結構上不可能存在任何 RC / RL / LC / LRC 子電路。** 這不是「畫得不好」，是使用者點名的那一整類東西在檔案裡不存在。

### §2.4 被動件全部單腳懸掛

三頁合計 28 顆 R/C/L。依 §2.2，每一顆的每一支腳都只連到自己的 label 短樁。**沒有任何一顆被動件的兩支腳分別接到兩個不同的節點**，而那正是「串聯」的定義。

### §2.5 懸空網路

以 global_label 文字出現次數統計，出現一次者代表該網路只有單一端點，不構成連接：

| 分頁 | unique nets | **只有單一端點的 net** |
|---|---|---|
| `btdongle_mcu` | 10 | **4** |
| `btdongle_io` | 11 | **3** |
| `btdongle_power` | 16 | 0 |

`mcu` 頁四成的網路是單端的。

### §2.6 版面與爆框（**這是格式軸，優先序低於上面五節**）

| 分頁 | 電路本體 bbox | 占 A3 面積 | 越過 10 mm 圖框 |
|---|---|---|---|
| `btdongle_mcu` | 231.1 × 90.2 mm | **16.7 %** | **是**（2 個元件 y = 6.3 mm） |
| `btdongle_io` | 221.0 × 94.0 mm | **16.6 %** | 否 |
| `btdongle_power` | 236.2 × 188.0 mm | 35.6 % | 否 |

**版面低占比是 §2.2 的下游症狀，不是獨立缺陷。** 當每個連接都只有 5.08 mm 時，元件之間本來就不需要空間，佈局器把它們擠成一團是它自己那層的「正確」行為。**先修連線，版面問題會自己縮小；先修版面，只會得到一張攤得比較開的接線表。**

（註：SVG 層量到的 87.7 % 是把 KiCad 圖框與標題欄算進去的結果，那個數字沒有判別力，因為邊框本來就撐滿整張紙。上表以 `.kicad_sch` 的 mm 座標重量，排除圖框。）

### §2.7 上游 spec 帶完整網路拓樸，遺失發生在 emitter（2026-09-05 補量）

**這一節回答 §6 第三題，而答案推翻了那一題的懸念。根因不在 spec schema。**

上游 SSOT 是 `04.btdongle/C03-EE/02_build/sch_gen/design.py`，`mk_sch.py` 與 C04 的 PCB builder 都讀它。它的頂層有一個 `NETS` dict，註解逐字寫著 `# Nets:  name -> [(ref, pin_number), ...]`。**那就是「哪些 pin 屬於同一個 net」的完整表達。**

需要 junction 的節點（三端點以上）在上游是明確存在的：

```
"SW_NODE": [("U1","3"), ("U1","4"), ("L1","1")]                                        3 端點
"BATT":    [("U1","14"),("U1","16"),("C5","1"),("Q1","3"),("R13","1"),("TP2","1"),("SW1","3")]   7 端點
"SYS":     [("L1","2"),("U1","1"),("U1","15"),("C4","1"),("R6","1"),("U2","39"),
            ("C8","1"),("C9","1"),("TP1","1")]                                         9 端點
"GND"                                                                                  約 50 端點
```

同檔另有 `NO_CONNECT` 明列刻意不接的 pin，以及 `PWR_FLAG_NETS`。**這份 spec 該有的東西一項不缺。**

emitter 側 `mk_sch.py` 第 5 至 6 行自陳設計意圖，逐字是「connectivity is expressed with net LABELS on short wire stubs attached to real pins, rather than hand-routed wire geometry」。全檔 `junction` 出現 **0 次**（控制組：同檔 `wire` 出現 8 次）；`design.py` 同樣 `junction` 0 次（控制組 `NETS` 2 次）。發射器只有 `wire()` 與 `global_label()` 兩個 primitive，而 `sh.wire(ex, ey, lx, ly)` 永遠是 pin 到 label 的短樁。

**所以拓樸資訊在 spec 層完好，在 emitter 的渲染策略層被丟棄。修法落在 emitter，或落在「要不要求圖面呈現串並聯」這個需求本身，不落在 spec schema。** §6 第三題不需要 owner 重跑。

（附註，`Pin_Allocation.csv` 確實有 `net` 欄，欄位為 `pin,module_signal,net,status,function`，但它只涵蓋 U2 模組四十餘支腳，是衍生輸出的平表，不是 SSOT。不要拿它當上游。）

### §2.8 junction 探針的正控制組（2026-09-05 補量，§9 缺口已關）

同一支探針、同一輪執行，跨四條產品線：

| 檔案 | wire | junction | global_label | pin_to_pin |
|---|---|---|---|---|
| `04.btdongle/…/btdongle.kicad_sch`（root） | 0 | **0** | 0 | 0 |
| `04.btdongle/…/btdongle_io.kicad_sch` | 26 | **0** | 26 | 0 |
| `04.btdongle/…/btdongle_mcu.kicad_sch` | 29 | **0** | 29 | 0 |
| `04.btdongle/…/btdongle_power.kicad_sch` | 69 | **0** | 69 | 0 |
| `03.aiguard/C03-EE/03_output/aiguard_mcu_core_wire.kicad_sch` | 5 | **2** | 91 | 0 |
| `03.aiguard/C03-EE/03_output/aiguard_mcu_core_wire2.kicad_sch` | 58 | **46** | 110 | 58 |
| `03.aiguard/C03-EE/03_output/aiguard_mcu_core_i2c_pullup.kicad_sch` | 63 | **48** | 112 | 63 |

**探針在確實有 junction 的檔案上回 2 / 46 / 48。缺席態與失敗態已分離，btdongle 的 0 是真實測量值，不是探針失效。**

`pin_to_pin` 這一欄同樣有判別力，它在 `01.openmv` 的 `*_hybrid` 系列回 89 / 36 / 25 / 36 / 18 / 24，在 `03.aiguard` 其餘頁回 18 至 152。**它不是恆為 0 的欄位。**

另跑一份人工合成檔（2 junction、2 wire、1 global_label），探針回 `junction=2 wire=2 pin_to_pin=1`，四個計數器都能回非 0。

`02.rockbox` 無任何 `.kicad_sch`，該線的母體不存在，這是資訊不是量測失敗。

---

## §3 基準規格：使用者提供的業界標準原理圖

使用者交付了一張工業變頻器功率級的原理圖作為「專業設計稿長什麼樣」的基準。以下把它蒸餾成**可驗收的數值規格**，每一項都是本 BR 的驗收判準。

### §3.1 基準圖的實測形態

| 面向 | 基準圖 |
|---|---|
| 電路占版面 | 85～90 %，四角皆有內容，無空白大區塊 |
| 連線形態 | **實線約 95 %，net label 約 5 %** |
| label 的用途 | 只給 `V+` 這種扇出極多的全域電源節點，共 6～8 處 |
| junction 實心點 | **45～60 處**，密集在母線正負兩條匯流排與端子匯集處 |
| 走線 | 100 % 正交，只有 90 度轉角，不穿過任何元件本體 |
| 交叉不連接 | 直接跨越，不加點 |
| 功能分區 | 以位置實現，左緣端子、上緣突波與連接器、中央整流與母線、右緣溫度、下半 IGBT 與閘極 |
| 被動件擺放 | 緊貼所屬元件，snubber 距模組一到兩格，閘極網路直接畫在模組腳位正下方 |
| 標註 | 每件標「參考標號＋數值或料號」兩行，例如 `CB1 0.1µ/500VAC`、`R2 15Ω 60W`、`R7 4K75` |

### §3.2 基準圖上可辨識的被動子電路，逐項可數

這一節是本 BR 的核心，因為它列的每一項在 btdongle 都是零。

| 子電路類型 | 基準圖的實例 | 數量 |
|---|---|---|
| 突波吸收網路 | RV1/RV2/RV3 線間三角接 + RV4 對 PE + CB1/CB2/CB3 線間電容 | 4 MOV + 3 C |
| 預充串聯電阻 | R2 15Ω 60W 串在整流輸出正端與母線之間 | 1 |
| 母線電容陣列 | 3300µ 400V 兩串兩並 | 4 |
| **均壓分壓** | 47K 5W 各並在一顆串聯電容上 | 1 組 2 顆 |
| **snubber 吸收電容** | 1µ5 850V 貼在 M2/M3/M4 的 P/N 端 | 3 |
| **閘極保護網路** | 每組 2 顆背對背齊納 + 1 顆 4K75 閘極電阻 + 1 顆二極體 | **7 組** |
| **去耦電容對** | HNC-161 電流感測每顆的 ±V 腳各配 2 顆 | 3 對 6 顆 |

**每一顆被動件都是「串在兩個明確節點之間」，沒有任何一顆是單腳懸掛的。**

### §3.3 一句話的驗收定義

> **合格圖**＝元件依功能就近成群，被動件實體串接在兩個明確節點之間，95 % 以上的連接以正交實線直接畫出並在交會處加實心接點，net label 只保留給全域電源這一類扇出極多的節點。
>
> **不合格圖**＝元件平均散佈，被動件單腳懸掛，所有連接改由同名 label 虛擬連通，圖上實線連接數趨近於零。

**btdongle 的三張分頁逐字命中不合格那一段的每一個字。**

---

## §4 差距對照

| 判準 | 基準圖 | btdongle C03 | 差距 |
|---|---|---|---|
| pin-to-pin 實線 | 約 95 % 的連接 | **0 條** | 全缺 |
| junction 實心點 | 45～60 處 | **0 處** | 全缺 |
| 被動件形態 | 串在兩節點之間 | 28 顆全部單腳掛 label | 全缺 |
| 可辨識子電路 | 分壓、預充、均壓、snubber、閘極、去耦，逐項可數 | **結構上不可能存在** | 全缺 |
| label 用途 | 只給全域電源，約 5 % | **承擔 100 % 的連通** | 角色顛倒 |
| 電路占版面 | 85～90 % | 16.6 / 16.7 / 35.6 % | 下游症狀 |
| 圖框 | 內容不越界 | mcu 頁 2 件越界 | 下游症狀 |

**前五列是內容軸，後兩列是格式軸。依 thesmart_products `AGENTS.md` §6 與使用者 2026-09-03 的裁示，內容軸的每一項都必須先於格式軸處理。** 使用者本輪的原話是「爆框問題是格式問題，但是現在內容問題更嚴重，應該先解決」。

---

## §5 為什麼這不是「再修一次佈線」

本 repo 的 `issues/` 有六張同族前例，跨越兩個月：

| BR | 症狀 | 狀態 |
|---|---|---|
| `closed/BR_20260706_placement_no_sheet_fill_planning_20pct_utilization_center_strip` | 圖紙利用率約 20 %，元件擠中央窄帶 | CLOSED |
| `closed/BR_20260706_draftsman_collinear_wire_fusion_shorts` | 共線熔合成短路 | CLOSED |
| `closed/BR_20260708_draftsman_wire_routing_no_obstacle_avoidance_label_only_fallback` | 走線穿件的止血法是全頁退回 label-only | CLOSED |
| `closed/BR_20260723_c03_composer_accepts_pinout_only_no_passive_completeness_gate` | 「你真的只是把所有的元件純 pinout 畫出來」 | CLOSED |
| `BR_20260723e_draftsman_cannot_wire_basic_series_divider_collinear_fusion` | 畫不出最基本的串聯分壓 | **OPEN** |
| `BR_20260802_real_product_pages_carry_dozens_of_open_circuit_nodes_cause_untraced` | 真實產品頁 38 個開路節點 | **OPEN** |

**`BR_20260708` 那張把根因講得最清楚，而它的止血法就是今天的病灶。** 該 BR 記錄 draftsman 的實線走線會穿過元件本體，止血方式是把全頁強制退回 `connection_style="label"`。**那個 fallback 從未被移除，於是「畫不出線」變成了系統的預設輸出形態。**

換句話說，兩個月前為了避免走線穿件而關掉的開關，今天仍然關著，而所有人都在修開關後面的東西。

**這解釋了使用者「回報了數百次都修不好」的體感**：每一次回報得到的都是佈局、熔合、開路節點這些**開關後面**的修正，而開關本身沒有人動。

`BR_20260706_methodology_in_session_engine_rnd_antipattern` 早就寫過這件事的形狀：「短路修好一處重產又冒一處，因為根因在引擎層，session 卻在呼叫層打地鼠。」

---

## §6 給 RCA 的四個問題

本 BR 不含修法。以下是交給 `schematic-engine` owner 的取證方向，每一題都要求三態回答，證實、推翻、未定。

**第一題，`connection_style="label"` 的 fallback 現在還在不在生效路徑上。**
`BR_20260708` 的止血法寫在 `gen_ccm_pages.py:695-703`。btdongle 這條線用的是哪一個入口、走的是 `style=netlist` 還是 `style=draftsman`、有沒有落進同一個強制退回。**若它已被移除，那 124 條短樁是另一個成因，那比它還在更值得知道。**

**第二題，`style=draftsman` 對 btdongle 這份 spec 跑不跑得起來。**
`BR_20260723e` 記錄 draftsman 路徑直接 fail。若今天仍然 fail，則「畫實線」這條路在系統裡是不存在的，不是選項沒被選。

**第三題，spec 到 emitter 之間，被動件的串接關係在哪一層消失。**
**本題已於 2026-09-05 補量，答案是證實：拓樸完整存在於上游，遺失發生在 emitter 的渲染策略層。見 §2.7。** 原題保留於此以存續問題脈絡，但它已不再是待答項，`schematic-engine` owner 不需要重跑這一格。

**第四題，junction 的產生條件。**
現行 emitter 在什麼情況下會發出 `(junction ...)`？若程式碼裡根本沒有這個 emit 路徑，那 §2.3 的結論就從「這次沒產生」升級為「結構上不會產生」。

---

## §7 建議的驗收判準

修法落地後，用下面這組數字驗收，每一項都可機器量測。判準取自 §3 的基準圖，不是我發明的。

```
pin-to-pin wire 數                    > 0，且應占全部 wire 的多數
junction 數                            > 0
被動件兩腳接不同節點的比例              應接近 100 %
label 承擔的連通比例                    < 20 %（基準圖約 5 %）
可辨識子電路                            至少列舉得出去耦、上下拉、限流三類
```

**每一項都要配控制組。** 例如 `junction > 0` 這一格，控制組是拿一份已知會產生 junction 的參考 spec 跑同一支探針，必須非零；否則「回 0」分不出是「這張圖真的沒有」還是「探針壞了」。

---

## §8 Related

- `BR_20260723e_draftsman_cannot_wire_basic_series_divider_collinear_fusion` — **同一根因族**。該 BR 的 symptom 段落逐字描述本 BR 的現象：「渲染出來是三個孤立元件各自帶 net label 殘腳、彼此零 drawn wire」。同一個缺陷在 2026-07-23 與 2026-09-05 兩條不同產品線上出現。
- `closed/BR_20260708_draftsman_wire_routing_no_obstacle_avoidance_label_only_fallback` — **今天的病灶就是這張 BR 的止血法**。它把「走線穿件」修成「無走線」，該 fallback 從未回收。
- `closed/BR_20260723_c03_composer_accepts_pinout_only_no_passive_completeness_gate` — 同一個消費端、同一句抱怨，該 BR 的 gate 只數被動件數量，數不出被動件有沒有接上。**btdongle 有 28 顆被動件，數量 gate 會過。**
- `closed/BR_20260706_placement_no_sheet_fill_planning_20pct_utilization_center_strip` — §2.6 的版面症狀與該 BR 同型。本 BR 主張它是下游而非獨立缺陷。
- `BR_20260802_real_product_pages_carry_dozens_of_open_circuit_nodes_cause_untraced` — 相鄰。該 BR 量的是「宣告同 net 的節點失去連接」，本 BR 量的是「從頭到尾就沒有 pin-to-pin 連接」，兩者在同一條路徑上但不是同一格。
- `closed/BR_20260706_methodology_in_session_engine_rnd_antipattern` — 方法論警告：引擎層問題不在呼叫層打地鼠。**本 BR 主張前六張的修法全部落在呼叫層。**

---

## §9 取證邊界

以下是本 BR **沒有**量的東西，明列以免被讀成已驗證。

- **沒有讀 bodesign 的原始碼。** 本 BR 全部量在消費端產物上，`connection_style` fallback 是否仍在生效路徑、`style=draftsman` 今天跑不跑得起來，都是推論不是量測。§6 四題正是為此而列。
- ~~**沒有量上游 spec。**~~ **已於 2026-09-05 補量，見 §2.7。上游 `design.py` 帶完整 `NETS` 拓樸，根因確定在 emitter 不在 schema。**
- ~~**junction 探針沒有跑正控制組。**~~ **已於 2026-09-05 補上，見 §2.8。探針在 `03.aiguard` 三個檔回 2 / 46 / 48，缺席態與失敗態已分離，btdongle 的 0 是真實測量值。**
- **沒有跑 KiCad 自己的 netlist / ERC。** 本 BR 全部量在檔案文字結構上，**沒有證明「同名 global_label 在 eeschema 語意下是否真的匯流成同一個 net」**。所以本 BR 主張的是**圖面不可讀、不表達拓樸**，不是主張最終 netlist 錯誤。若要斷言後者，需跑 `kicad-cli sch export netlist` 與 `design.NETS` 比對。**這是本 BR 最大的未驗證邊界，不得被讀成已排除。**
- **`pin_to_pin` 判準的已知寬鬆處。** 判定方式是「wire 兩端座標皆不落在任一 label 的 `(at x y)` 上」。它不區分「端點落在某個 symbol pin 上」與「端點懸空」，也未處理 grid 誤差；本 repo 未觀察到誤差，且若有誤差會使 `pin_to_pin` 反向膨脹而非縮小，故不影響「btdongle 為 0」這個方向的結論。
- **沒有判斷修法。** 本 BR 是取證與規格定義，修法歸 `schematic-engine` owner。

---

## §10 修法後複驗：消費端零效果，且本 BR 存在 venue 誤判（2026-09-05 實測）

bodesign 於 `95d6241` 落地修法並通知複驗。**複驗結果是不通過，而根因不在那次修法。**

### §10.1 §7 判準複驗，四項全部維持修法前的數值

在 `04.btdongle/C03-EE/02_build/sch_gen` 重跑 `mk_sch.py`（`rc=0`，輸出 `OK: 3 sheets, 45 components, 27 nets`），再對產物量 §7：

| 分頁 | wire | junction | global_label | 短樁 | pin-to-pin |
|---|---|---|---|---|---|
| `btdongle_io` | 26 | **0** | 26 | 26 | **0** |
| `btdongle_mcu` | 29 | **0** | 29 | 29 | **0** |
| `btdongle_power` | 69 | **0** | 69 | 69 | **0** |
| 合計 | 124 | **0** | 124 | **124** | **0** |

正控制組（同一支探針、同一輪執行）：`03.aiguard` 三檔回 junction **2 / 46 / 48**，pin-to-pin **0 / 63 / 58**。探針有判別力，btdongle 的 0 是測量值。

**§7 四項判準逐項未達成**：`pin_to_pin > 0` 未達成、`junction > 0` 未達成、被動件兩腳跨接未達成、label 承擔連通比例仍為 100 %（目標 < 20 %）。

### §10.2 產物在結構上零改變，不只是「數字碰巧一樣」

把重跑產物與 committed 版各自做 UUID 正規化後逐位元比對：

```
btdongle_power   uuid_normalised_identical = True
btdongle_mcu     uuid_normalised_identical = True
btdongle_io      uuid_normalised_identical = True
CONTROL (mcu vs io，應為 False) = False
```

**除了每次執行必然重生的 UUID 之外，重跑產物與修法前逐位元相同。** 所以這不是「修法有效但這份 spec 剛好不觸發」，是這條路徑完全沒有經過修法。

### §10.3 根因：btdongle C03 不經過 bodesign 引擎，本 BR 的 fix venue 判錯了

**這一格是我 filed 這張 BR 時的錯誤，不是 bodesign 的。**

`04.btdongle/C03-EE/02_build/sch_gen/mk_sch.py` 是**本地自寫的 emitter**，證據三路：

- AST 列舉全部 import：`{os, re, sys, uuid, design, symlib}`，其中 `design` 與 `symlib` 解析到同目錄本地 `.py`。
- AST 掃 escape call（`system`/`popen`/`exec`/`spawn`/`run`/`Popen`/`urlopen`/`import_module` 等）：命中三處，逐行檢視全部是 `dict.get`（`mk_sch.py:77,80,229`）。無 subprocess、無網路、無容器呼叫。控制組：同一次走訪找得到已知存在的 `wire` / `write` 呼叫共 5 處。
- `bodesign_eda_bridge` 在本機 python 環境 `ModuleNotFoundError`（控制組 `import json` 成功）。

檔案時間也一致：`mk_sch.py` mtime `2026-09-05 01:58`，`95d6241` 的 commit time 是 `2026-09-05 14:18`。**修法落地時，這支 emitter 已經十二小時沒被動過，之後也沒有。**

而 `95d6241` 改的是 `packages/eda-bridge/bodesign_eda_bridge/{composer,kicad_emit}.py`。**那兩支檔案與 btdongle 這條產線之間沒有任何呼叫關係。**

所以 §1 那句「`compose_schematic` 產出的 `.kicad_sch`」是錯的。**產出它的是消費端 repo 內的本地腳本。** §2 的全部量測仍然成立（那些是對產物量的），§3 的基準規格仍然成立，錯的是 §0 抬頭的 **Fix venue** 那一行。

### §10.4 bodesign 的修法在它自己的軌上是有效的，這一格要分開講

不要因為消費端零效果就推論修法無效，兩者是不同的問題。

- `tests/test_kicad_emit.py`：**46 passed**，其中含本次新增、逐字寫明「BR_20260905 §7 acceptance: `pin_to_pin > 0` AND `junction > 0`」的驗收測試。
- `tests/test_composer_draftsman.py`：11 failed / 64 passed。**但這 11 個不是本次造成的** —— 用 `git archive 95d6241^` 匯出父 commit 到 scratch 跑同一支測試，得 **11 failed / 63 passed**。既有紅燈，與本次修法無關。

**所以 bodesign 側的判定是：修法在引擎軌上有效且帶驗收測試；它對 btdongle 無效的原因是 btdongle 從來不呼叫那個引擎。**

### §10.5 `check_c03` gate 的結果，以及它為什麼不能拿來判本 BR

依指示跑了 gate（`PYTHONPATH=<bodesign>/packages/workflow-core`）：

```
GATE: FAIL
blocking: R3_DRAWABILITY — no symbol-source column found in BOM header
          (looked for: symbol_source, symbol, sym_source, drawability, deck_status)
bom_rows=45  active_parts=8  ssot_checked=False
netlist_crosscheck / pin_polarity / mandated_passives / switch_node_shorts = not_run
  （理由一致：netlist_path 未提供）
```

**這個 FAIL 與本 BR 無關**，它擋的是 BOM 表頭缺欄位。而且它有五格 `not_run`，gate 自己逐格寫明「a PASS here does not mean …」——**即使它回 PASS，也不構成 §7 判準的通過證據，因為它根本不量 junction 與 pin-to-pin。**

### §10.6 我這一輪的兩個探針缺陷，一併記錄

第一次量測時我的 label 正則寫成 `\(global_label "[^"]*" [^)]*?\(at ...`，`[^)]*?` 跨不過 `(shape bidirectional)` 裡的 `)`，於是 label 座標集合是空的，**每條 wire 都被誤判為 pin-to-pin，回報 `pin_to_pin=124`**。那個數字看起來正是「修好了」的樣子。

抓到它的是同一輪輸出裡的矛盾：`pin_to_pin` 從 0 跳到 124 的同時 `global_label` 從 124 掉到 0，**兩個數字共用同一個成因**。再回頭數原始位元組，`global_label` 字串出現 69 次而 `junction` 出現 0 次，才確認是探針壞了不是產物變了。

教訓寫在這裡供後續複驗者參考：**在這份檔案上，`pin_to_pin` 與 `label 計數` 必須一起看。** 只看 `pin_to_pin > 0` 會把「正則沒命中」讀成「修好了」，而那正是本 BR 從頭到尾在防的那種假綠燈。

### §10.7 尚待裁決

本 BR 的 §2 / §3 / §7 全部有效，錯的只有 fix venue。三條路可走，**選哪一條是 bodesign 與消費端共同的決定，不是我單方面可裁的**：

**其一，btdongle 改為呼叫 bodesign 引擎。** `design.py` 的 `NETS` 已是完整拓樸（§2.7），理論上可以餵給 `compose_schematic`。這樣 `95d6241` 的修法立即生效，且未來同族修法自動涵蓋這條線。代價是要接一層轉換，且要驗 45 個元件的 symbol 對應。

**其二，修消費端的本地 emitter。** 在 `mk_sch.py` 內實作 pin-to-pin 走線與 junction。代價是把同一個問題在第二個地方再解一次，而這正是 §5「引擎層問題不在呼叫層打地鼠」警告的形狀。

**其三，本 BR 在 bodesign 側改判為 partially-invalid 並結案，另在消費端 repo 開一張新 BR。** 這一條最誠實但最慢。

**我的建議是其一**，理由是 §2.7 已證實上游拓樸完整，且 bodesign 引擎現在有帶驗收測試的實線能力，而本地 emitter 沒有也不會有。但這是建議不是裁決。

