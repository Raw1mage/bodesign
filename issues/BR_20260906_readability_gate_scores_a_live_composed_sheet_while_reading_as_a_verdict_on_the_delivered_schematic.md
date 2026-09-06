# BR_20260906 — readability_gate 評的是 live-compose 的另一張圖，讀起來卻像對交付圖的判決

- **Status**: OPEN
- **Severity**: P1 — 它汙染的不是某個數值，是「這個 FAIL 在講哪一塊板子」
- **Family**: `G13-harness-disclosure` — 兩個不同母體的量測結果共用同一份輸出，沒有任何欄位區分
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/readability_gate.py`,
  `packages/eda-bridge/bodesign_eda_bridge/composer.py`
- **Filed**: 2026-09-06，由 `plans/c03_delivery_contract_and_engine_seams` WP6 落地後的
  下游複驗（thesmart_products 值星官）提出，本 repo handler 獨立覆核。

---

## 1. 一句話

`readability_gate` 對 btdongle 回 `drawn_subcircuits=4 / N=18 / ratio=0.2222 FAIL`。
**這個分數量的是「假如用 bodesign 引擎現場重畫 btdongle」的那張圖，不是 btdongle 現行交付的
`.kicad_sch`。** 報告裡沒有任何欄位說得出這件事。

---

## 2. Fail mode（讀者會讀成什麼）

報告長這樣（`readability_gate.py:216-273` 組出的 dict）：

```
status=failed  code=READABILITY_THRESHOLD_UNMET
N=18  drawn_subcircuits=4  subcircuit_ratio=0.2222  junctions=6
unmet=[{criterion: subcircuit_ratio, observed: "4/18 = 0.2222", ...}]
gate_axis=form  does_not_authorize=[electrical_correctness, fidelity]
```

`does_not_authorize` 擋住了**軸**的誤讀（form 不授權 electrical）。它擋不住**母體**的誤讀：
讀者看到 `failed` + 板子名字，得到的結論是「**這塊板子的交付圖不合格**」。

實際上現行交付圖**從未被這支 gate 評過**，而且它的線/接點密度比被評的那張高一個量級。

---

## 3. RCA（機制層）

### 3.1 gate 結構上沒有讀 `.kicad_sch` 的入口

獨立覆核（不照抄上游結論），2026-09-06：

```
問：readability_gate.py 全檔有無 .kicad_sch / open( / Path( / read_text / glob / os.path？
  grep -n "kicad_sch\|open(\|Path(\|read_text\|glob\|os\.path" readability_gate.py  → rc=1（零命中）
CONTROL（同一支 grep、同一個檔、確定存在的 token）：
  grep -c "route_stats" readability_gate.py                                          → 10
```

控制組非零，所以那個零是真缺席，不是探針沒跑。

全檔只有兩條 import（`readability_gate.py:30`、`:93`）：

```
30: from __future__ import annotations
93:     from .kicad_emit import _power_net_kind      # 純函式，不碰檔案系統
```

唯一的資料入口是函式參數（`readability_gate.py:125-126`）：

```python
def readability_gate(route_stats, *, spec: dict | None = None,
                     n: int | None = None, emit=None) -> dict:
```

- `route_stats` — 來自 compose 結果
- `spec` — dict，用來算 N（`compute_n`，`:79-113`）
- `emit` — `SchematicEmitResult`，只用來偵測 emitter 版本（`:184-193`）

**沒有一個參數是磁碟路徑。** 這一格與上游的判斷一致，但這是我自己量的。

### 3.2 `route_stats` 只在 live compose 途中存在

`composer.py:2653-2660`：

```python
route_stats: RouteStats | None = None
if style == "draftsman":
    placements = {c.ref: c for c in components}
    route_stats = _build_route_stats(nets, net_kinds, placements, _pin_resolvable, emit, ...)
```

`_build_route_stats`（`composer.py:1837`）的參數全是**記憶體中的 compose 中間態**
（`nets` / `placements` / `emit`），沒有一個是磁碟檔。
而 `compose_schematic`（`composer.py:1887-1890`）的輸入是 `spec: dict`，
**不是** 一份既有的 `.kicad_sch`。

⇒ 要拿到 `route_stats`，**必須跑一次 live compose**；而那次 compose 產出的是**一張新圖**，
不是磁碟上那張。兩者的關係只有「同一份 spec」，沒有「同一份 bytes」。

### 3.3 缺的那格：報告裡沒有母體欄位

report dict（`readability_gate.py:216-227`）攜帶 `N` / `drawn_subcircuits` / `stub_share` /
`junctions` / `thresholds` / `measure_run`。

`measure_run`（`:48-60`）記的是**閾值當初釘在哪一次量測**，不是**本次評的是哪一張圖**。
兩者形狀相似而語意相反，反而更容易被讀成後者。

**沒有任何欄位回答「這份 route_stats 是誰產的、對應磁碟上哪個路徑（如果有的話）」。**
於是「評了現場 compose 出來的圖」與「評了交付圖」共用同一份輸出。

這正是 `issues/BR_20260802_compose_reports_no_provenance_of_the_bytes_it_consumed.md`
指出的同一個缺口，**沿著 compose → route_stats → gate 這條鏈往下游傳了一層**：
compose 不說它讀了什麼，gate 於是也說不出它評了什麼。

---

## 4. 產出狀態 codomain 的違反

`plans/c03_delivery_contract_and_engine_seams/errors.md:108-113` 為這支 gate 定了五格
（`ok` / `failed` / `not-run` / `empty` / `indeterminate`）。那張表是**對「被評的那張圖」**
定的，而它是完備的。

問題出在**它沒有涵蓋的那個對象**：

| 對象 | 應有狀態 | 實際 |
|---|---|---|
| 現場 compose 出的圖 | `failed`（ratio 0.2222 < 0.50） | `failed` ✔ 正確 |
| **btdongle 現行交付 `.kicad_sch`** | **`not-run`** — gate 結構上讀不到它 | **沒有這一格**；讀者從 `failed` 推得它被評過了 |

`not-run` 這個類別存在、定義正確、且在 `readability_gate.py:157-172` 有兩個排放點
（`route_stats is None`、缺 task-6.0 欄位）。**但那兩個排放點都是對「這次 compose」講的。**
「有一份磁碟交付圖，而我沒有評它」這件事，**沒有任何排放點**。

⇒ 現行交付圖的可讀性至今是 **undecidable**，不是 `fail`。而 undecidable 沒有被排放出來，
就會被最近的一個已排放狀態吸收——這裡是 `failed`。

---

## 5. Detection（怎麼看出它發生了）

比對**量級**。被評的那張與磁碟上那份差一個數量級：

```
問：btdongle 現行交付 generated/sch/ 各 sheet 的 wire / junction 數？
  （2026-09-06 獨立計數，非引用）

  btdongle.kicad_sch         wire=0     junction=0     mtime=09-05 17:26  (root sheet)
  btdongle_io.kicad_sch      wire=84    junction=7     mtime=09-05 17:26
  btdongle_mcu.kicad_sch     wire=94    junction=13    mtime=09-05 17:26
  btdongle_power.kicad_sch   wire=248   junction=36    mtime=09-05 17:26
  ──────────────────────────────────────────────────────────
  合計                       wire=426   junction=56

CONTROL（同一支 grep、同一批檔、確定不存在的 s-expr）：四檔皆 zzprobe=0
CONTROL（路徑存在性）：generated/sch_bodesign → ABSENT；generated/sch → PRESENT

gate 評的那張（readability_gate.py:53-55 MEASURE_RUN，單張，live compose）：
  junctions=6, drawn_subcircuits=4, N=18, stub_share=0.7155
  （BR_20260905 §8.5.1 對應的 wire=111，c3019f68 後 116）
```

**wire 426 vs 116、junction 56 vs 6** — 三 sheet 對單張、且 junction 差 9 倍。
若 gate 真的在評交付圖，這兩組數字不可能長這樣。

一般化的判準：**看到這支 gate 的 `failed`，先問「它手上那份 route_stats 是哪一次 compose 產的、
磁碟上有沒有對應檔案」。答不出來 ⇒ 這個 verdict 不指向任何交付物。**

（注意路徑：正確位置是 `C03-EE/02_build/generated/sch/`，
不是 `C03-EE/sch/` —— 後者 `test -d` 回 ABSENT。上游反饋給的是簡寫。）

---

## 6. 已採納的裁決（範圍限定，非本 BR 提出）

`0.222` **不**作為「btdongle 現行交付不合格」的依據；它是
「**若改走 bodesign 引擎路徑，該路徑當下的產出不合格**」的依據。

本 BR 要求的是：**讓報告自己說得出這句話**，而不是靠讀者記得。

---

## 7. 建議修法（不在本輪實作，待裁決）

最小修法是**加欄位，不是加能力**：report 帶一個 `scored_subject`，值域至少要分得出
`live-compose`（附 spec 來源）與 `on-disk`（附路徑 + sha256）。
在「沒有磁碟入口」的當下，它恆為 `live-compose` —— 這不是廢話，
**恆定值正是要排放的那格**：它把「我評的不是磁碟上那張」寫成資料，讀者不必推理。

要不要進一步給 gate 一個讀 `.kicad_sch` 的入口，見 §8。

---

## 8. 附帶判定：要不要給 gate 一個讀 `.kicad_sch` 的入口

**要，但那是獨立工作包，且不是本 BR 的修法。**

理由：現在的形狀讓「引擎自評」與「交付驗收」變成同一支工具的同一個輸出，
而這兩件事的母體不同、對象不同、失敗的意義也不同——引擎自評 FAIL 是**引擎的待辦**，
交付驗收 FAIL 是**這塊板子的待辦**。一支只能做前者的工具，
在報告裡卻長得像後者，缺陷不會停在數字上。

技術上不難：`wire` / `junction` / `label` 都是 `.kicad_sch` 的頂層 s-expr，
`engines/kicad/scripts/sexp_parser.py` 已經在 repo 裡（也已投影進 published 樹）。
真正的成本在**閾值**：現有三條閾值全部釘在 live-compose 的量測上
（`readability_gate.py:33-44`，`MEASURE_RUN` 記在 `:48-60`），
`MIN_SUBCIRCUIT_RATIO=0.50` 是對 compose 出的圖校準的。
直接把它們套到 426-wire 的人工圖上，得到的會是一個**沒有校準過的判決**——
就是本 BR 這個缺陷換一個方向再犯一次。

⇒ 先做 §7 的欄位（讓現況誠實），讀交付圖的入口另開包，且該包的第一件事是**重新校準**，
不是接上 parser。

---

## 9. What is NOT claimed here

- **沒有**主張現行交付圖可讀性不合格。它是 `not-run`；我沒有評過它。
- **沒有**主張 `0.222` 這個數字算錯。`readability_gate` 的 29 個測試在 HEAD 全綠
  （`./scripts/run_tests.sh test_readability_gate` → `Ran 29 tests / OK`，2026-09-06），
  gate 對它拿到的那份 `route_stats` 的計算是對的。錯的是**沒有人說得出那份 stats 是誰的**。
- **沒有**跑 live compose 重現 `0.222`。本 BR 的 §5 只重現了**磁碟側**的計數；
  live 側的數字引自 `MEASURE_RUN`（程式碼內建的量測紀錄），未重跑。

---

## Related

每一條邊都附「這條邊的依據是什麼」。

- **`issues/BR_20260802_compose_reports_no_provenance_of_the_bytes_it_consumed.md`** —
  **同一個缺口的上游**。該 BR：`compose_schematic()` 回報 `placed`/`nets`/`warnings`，
  但不說它讀了哪個路徑、哪個版本的位元組。本 BR 是它沿 `compose → route_stats → gate`
  往下傳一層的結果：compose 不排放來源，於是 gate 的 report 也無從攜帶。
  依據：該檔 §1 逐字（「**不回報它實際讀了哪個路徑、哪個版本的位元組**」）；
  對應本 BR §3.3。

- **`issues/BR_20260906_gate_unit_fixtures_blind_to_emission_site_mutation.md`** —
  **同一支 gate、同一個 seam 的另一側**。該 BR 記的是「23 個測試全綠，而生產端把值換成常數 0」，
  Component 逐字包含 `tests/test_readability_gate.py` 與 `composer.py:2740`。
  兩張 BR 談的是同一條 producer↔consumer 縫：那張講**縫的上游壞了測不出來**，
  這張講**縫的上游是誰、報告裡沒說**。
  依據：該檔 header 的 Component 欄與 "The finding" 段。

- **`plans/c03_delivery_contract_and_engine_seams/errors.md:108-113`** —
  本 BR §4 的對照基準。該表定義了 gate 的五格 codomain，**且該表是正確的**；
  本 BR 指的是它的**射程**（對「被評的那張」完備，對「磁碟上那張」無格）。
  依據：該檔 108-113 行五個 `readability_gate` 條目逐行。

- **`packages/eda-bridge/bodesign_eda_bridge/readability_gate.py:53-55`（`MEASURE_RUN.observed`）** —
  §5 中「gate 評的那張」的數字出處。它是程式碼內建的量測紀錄，不是我重跑的。

- **`issues/BR_20260802_probe_ambiguity_is_the_one_defect_family_no_guard_scans_and_it_fired_16_times_today.md`** —
  **家族根**（`G13-harness-disclosure`）。該 BR §2 把這個家族的形狀寫成
  「判準自己壞掉，而它的壞掉態與健康態產生同一個輸出」。本 BR 是它的一個變體：
  判準沒壞，但**它的作用對象**與讀者以為的對象共用同一個輸出。
  依據：該檔 §2 逐字。

- **`issues/BR_20260905_draftsman_connection_strategy_degenerates_to_label_farm_on_non_label_friendly_topology.md`** —
  `readability_gate` 三條閾值的**校準來源**（§7 criterion 1/2/4，逐條被
  `readability_gate.py:37-44` 的註解引用）。列在此處是因為 §8 的「重新校準」成本直接來自它：
  那些閾值是對 draftsman live-compose 的產出釘的。
  依據：`readability_gate.py:33-44` 註解對該 BR 的逐條引用。
