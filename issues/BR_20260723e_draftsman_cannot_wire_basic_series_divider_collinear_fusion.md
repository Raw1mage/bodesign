# BR_20260723e — draftsman 畫不出最基本的串聯分壓（collinear-wire fusion 殘留漏洞）

- **Severity**: HIGH（立身能力缺陷 · 連最基本電路都無法以「視覺有連線 + 電氣正確」交付）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`（draftsman drawn-wire emission + anti-fusion guard）／`composer.py`（style=draftsman 路徑）
- **Status**: open
- **Filed**: 2026-07-23
- **Scope / venue**: bodesign repo 內修（electrical design capability 主線）；**BRNS — 開新 session rooted in bodesign 反覆調試，本 BR 只做 RCA + fix plan，不在產出 session 內聯修**（遵 `BR_20260706_methodology_in_session_engine_rnd_antipattern` 的教訓：引擎層問題不在呼叫層打地鼠）
- **Related（同族根因，全 CLOSED）**:
  - `issues/closed/BR_20260706_draftsman_collinear_wire_fusion_shorts.md` — **同一根因**（collinear 共線熔合成短路），當時 fix = `fusion_registry` anti-fusion guard，但未覆蓋「最小串聯鏈」case
  - `issues/closed/BR_20260706_methodology_in_session_engine_rnd_antipattern.md` — 警告「短路修好一處重產又冒一處，因為根因在引擎層，session 卻在呼叫層打地鼠」→ 本 BR 走 BRNS 正是為此
  - `issues/closed/BR_20260708_draftsman_wire_routing_no_obstacle_avoidance_label_only_fallback.md` — draftsman 全頁退回 label-only 的相鄰缺陷
  - `issues/closed/BR_20260703_e2e_workflow_gaps_nc_paths_env.md` §T3 — ≥3 節點 net wire 不可靠

---

## Symptom（verbatim 觀測）

平台自證「能設計電路」時，用真實引擎產最基本的分壓電路：一顆 LDO（U1=AMS1117-3.3）輸出腳 →
R1(20k) → Vout 節點 → R2(10k) → GND。

**路徑一 `style=netlist`（預設）**：compose「成功」，但渲染出來是**三個孤立元件（U1/R1/R2）各自帶 net
label 殘腳、彼此零 drawn wire**。電氣連通（SPICE 驗證 Vout=1.1V 正確、fidelity ok），但**視覺上不是一張
電路圖**——沒有任何一條線把三件串起來。這正是 `BR_20260723c` 記錄的核心 defect：「不管怎麼改它只會畫
元件原生 pinout 加 label」。

**路徑二 `style=draftsman`（想畫真實 wire）**：compose 直接 fail：

```
FidelityError: schematic fidelity gate FAILED — net partition diverged from spec
(collinear-wire fusion / label collision):
baseline nets=4 nodes=7 | candidate nets=2 nodes=6 | shared=6
FIDELITY FAIL moved=4 only_baseline=0 only_candidate=0
  MOVED (partition class changed): ['R1.2', 'R2.1', 'R2.2', 'U1.1']
```

MOVED 節點 = VOUT 網（`R1.2`/`R2.1`）+ GND 網（`R2.2`/`U1.1`）→ **VOUT 被熔進 GND**（分壓中點對地
短路，分壓器物理上壞掉 Vout=0）。baseline 4 nets → candidate 2 nets（VOUT 與 GND 塌成一個）。

repro spec（tok_c83e50e0a6154773，divider_wired）：
```json
{"components":[{"ref":"U1","symbol":"Regulator_Linear:AMS1117-3.3"},
               {"ref":"R1","symbol":"Device:R","value":"20k"},
               {"ref":"R2","symbol":"Device:R","value":"10k"}],
 "nets":[{"name":"VO","nodes":["U1.2","R1.1"]},
         {"name":"VOUT","nodes":["R1.2","R2.1"]},
         {"name":"GND","nodes":["R2.2","U1.1"]},
         {"name":"VIN","nodes":["U1.3"]}]}
```
`style=draftsman, validate=true, fidelity=true` → FidelityError（上）。

**淨結論**：兩條路徑都交不出「視覺有連線 + 電氣正確」的最基本分壓——能畫線的（draftsman）有 fusion
bug，不會壞的（netlist）根本沒畫線。

---

## RCA（evidence-anchored，讀真實 source 定根因，非臆測）

### 根因（HIGH）：anti-fusion guard 對「最小串聯鏈」有殘留漏洞

KiCad 的 wire 連通語意是**幾何的**——兩條共線重疊的 wire segment（或一端點落在他 net 的 wire 上）
＝電氣熔合成同一 net（`kicad_emit.py:2444-2452` 註解自述）。draftsman 的 wire 幾何生成器
(`_orthogonal_route` / `_bus_route` / power stub) **只保證端點正確，不保證不同 net 的 segment 不
共線/不共點**。

已有 anti-fusion guard 應對此（`kicad_emit.py:2470-2523`：`_collinear_overlap` / `_point_on_segment`
/ `_segment_fuses`）+ 2-node 走線路徑的 guard + ledger gate + label 降級（`1362-1406`）。**但它在
「三件式串聯分壓」這個最基本拓撲上仍讓 fusion 發生**：

- 串聯鏈 U1—R1—R2 在 draftsman force-directed 佈局下高機率落在**同一 column**（垂直堆疊）。R1 底
  (R1.2) 與 R2 頂 (R2.1)＝VOUT，R2 底 (R2.2) 與 U1 某腳＝GND；兩段短 stub 沿**同一 x 直線**上下相鄰
  → 共線/共點。
- guard 是**增量式**（`_segment_fuses(seg, other_net_segs)` 只比對「已註冊」的他 net segment，
  `1411 _other_net_segments`）→ net emission 順序決定誰先註冊；短鏈上兩段幾乎共線時，
  `_collinear_overlap` 的 `overlap > _FUSION_EPS`（`2490`）判斷可能因端點恰好首尾相接（間隔=0）而
  漏判，但 KiCad 實際仍熔合（端點相接即連接）。**guard 的幾何 fusion 模型與 KiCad 真實連通語意之間
  有殘留 gap**，fidelity gate（node-set 比對，非 net 名）才在事後抓到。
- 結果：guard 沒攔（沒降級 label），wire 照畫、照熔合，fidelity gate fail-loud → **compose 硬失敗，
  使用者一張圖都拿不到**。

**證據 anchor**：
- `kicad_emit.py:1362-1406`（2-node drawn-wire：`_orthogonal_route` → `_guard_route` → `_route_clears_ledger` → 否則降級 label）
- `kicad_emit.py:2444-2523`（anti-fusion guard 全體：`_collinear_overlap`/`_point_on_segment`/`_segment_fuses`，`_FUSION_EPS=1e-4`）
- symptom：MOVED=`['R1.2','R2.1','R2.2','U1.1']`、baseline 4→candidate 2 nets（VOUT 併 GND）

### 次因（MEDIUM）：netlist style 對 2-node net 一律走 label，非「電路圖」

`style=netlist`（預設）對 2-node net 走 global label（`composer.py` docstring `1638-1642`：
netlist→"label"）。電氣正確但**視覺不是電路**。這不是 bug（byte-equivalent 舊行為、no-silent-change
rail），但意味**預設 style 永遠交不出人眼可讀的電路圖**——要嘛用會 fuse 的 draftsman，要嘛接受一張
label 圖。使用者要的「最基本電路」兩者都給不了。

---

## 明確標「不是 bug / 不要動」（守 code-thinker §3）

- **fidelity gate fail-loud 是對的**：它正確擋下了會短路的圖，**不要為了「讓 compose 成功」而關掉或
  放寬 fidelity gate**——那是把電氣短路偷渡出去，違反天條。fix 要讓 guard 真正防熔合（治本），不是
  繞過 gate。
- **netlist→label 是 by-design**（no-silent-change rail），不要改預設 style 語意。
- **BR_20260723d 的 wire honour 邏輯無誤**（consumer 已交叉坐實 `connection_style="wire"` 生效），
  不要動 wire 渲染的 honour 判斷；本 BR 是 guard 覆蓋不足，非 wire 路徑失效。
- SPICE/fidelity/ERC 驗證鏈本身正確，不要動。

---

## Fix proposal（治本，待新 session 反覆調試收斂）

1. **guard 幾何模型對齊 KiCad 真實連通語意**：`_segment_fuses` 補「端點首尾相接（間隔=0）即熔合」
   的判定——目前 `_collinear_overlap` 要求 `overlap > _FUSION_EPS`（正重疊），但 KiCad 連兩段**端點
   相接**（overlap=0）也連。短串聯鏈正踩這個邊界。需分辨「合法 T/corner 共點」（同 net）vs「他 net
   端點相接」（熔合）。
2. **串聯鏈確定性 jog**：guard 偵測到同 column 相鄰短 stub 共線 → 按 net-hash 把其中一段橫向偏移
   1-3 grid step（`_guard_route` 已有 jog 機制，確認它對 2-node 短 stub 生效），讓 VOUT 與 GND 的
   wire 物理分離。
3. **佈局層預防**：force-directed placement 對串聯鏈避免把相鄰件塞進同一 x column（給最小水平 gutter），
   從源頭降低共線機率。
4. **收斂判準（最小可畫電路）**：上述 repro spec 以 `style=draftsman, fidelity=true` compose →
   `ok=true`、fidelity `ok=true`、render 出來**肉眼看得到 U1→R1→R2→GND 的連線**、SPICE Vout=1.1V。
   這是「能畫最基本電路」的驗收線。

## Validation plan

- **回歸 fixture**（釘死，防再退化）：三件式串聯分壓（U1+R1+R2，2-node VOUT/GND 共 column）→
  draftsman compose `fidelity ok`、`wired_nets≥2`（VOUT/GND 各一條 drawn wire、非 label 降級）、
  `_other_net_segments` 無跨 net 熔合。落 `tests/test_kicad_emit.py` collinear-series fixture。
- **render-layer QA**（rule 3，delivery-layer 先行）：`render_qa` 掃出的 SVG 有 ≥2 條可見 wire
  連接三件，非三根浮空柱子。
- **既有回歸不退化**：aiguard CCM 各頁 wire 數（01_power=78 / 02_mcu=57 …）維持，stamp 頁 all_label
  不受影響。
- **engine_rev стамп**：每輪改動後回報 `__engine_rev__` + `sync_engine.sh` 驗 live copy。

## Fix venue

**NEW session rooted in `/home/pkcs12/projects/bodesign`**（BRNS）。理由：引擎層 collinear-fusion 是
`BR_20260706_methodology` 白紙黑字警告的「呼叫層打地鼠」高風險區——必須在乾淨的、有 checkpoint
instrumentation 的新 session 裡按 plan-builder lifecycle 反覆調試（先寫回歸 fixture→改 guard→驗
fidelity→render QA），直到最基本電路可畫。本產出 session 只產此 BR，不內聯修以免 scope 污染。

**收斂目標（使用者定調）**：反覆調試直到最基本分壓電路能以「視覺有連線 + 電氣正確」畫出並通過
fidelity + render QA——**這是談任何專案產品的前置門檻**。
