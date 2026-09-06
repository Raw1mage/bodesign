# Design: eda-bridge_draftsman-series-divider-wireable

## Context

### 現況

`compose_schematic(out_dir, project_name, spec, ...)` 吃的 `spec` 是：

```json
{"components": [{"ref","symbol","value","footprint","group"}],
 "nets":       [{"name","nodes":["R1.2","C3.1"],"kind?"}],
 "nc":         ["U2.35"]}
```

這是一份**已經完成的 netlist**。它不表達「為什麼 R1.2 和 C3.1 在一起」，
也不表達「這兩顆電阻是一組分壓」或「GND 在這個 cluster 裡應該畫成一條 rail」。
**設計意圖在進入 bodesign 之前就已經被壓扁成一張平表。**

round 1 實測的後果（`ses_f884168d5ffe`，2026-09-06）：composer 拿到 27 條 net，
其中 13 條在進 router 之前就被判成 label（cross-IC 8 / power-rail 3 / high-fanout 2）。
那些判定是**啟發式猜測**——引擎在猜哪些 net 該畫、哪些該掛旗，因為沒有人告訴它。
router 本身健康（21 呼叫 / 18 接受 / 86%），它只是拿到 14 條。

### 這一層與 KB 禁令的關係（必讀，否則本包會被誤讀成推翻禁令）

KB `netlist-synthesis-gap` 逐字：

> netlist 對錯是唯一無法用確定性方法保證的環節…故團隊寧可擋在 gate 後也不冒
> silent-fabrication 險。同領域 SKiDL / atopile / agentic 流程全繞開此步——
> **都是人已想好連接用 code 表達**。

**那條禁令針對的是「程式自動合成 netlist」，不是「agent 宣告 netlist」。**

| | 誰決定電路 | fabrication 風險 |
|---|---|---|
| 程式自動合成 | 演算法／LLM 自由發揮 | **有** ← 禁令針對這個，本包維持 |
| agent 宣告 | **agent 想好了，系統只負責落地＋驗證** | **零** ← 本包補的是這格 |

KB 那句「SKiDL / atopile 都是人已想好連接用 code 表達」講的正是本包要提供的東西。
**它們沒有「繞開」這一步，它們把這一步做成了產品的主介面。**

## Goals / Non-Goals

**Goals**

- 讓 agent 用設計者語彙宣告拓樸，而不是手刻一張 net 平表。
- 在入口處回答「這份輸入完整嗎」——目前沒有任何 verb 回答這個問題。
- 讓「系統沒有發明電路」成為可機檢事實（provenance），而非宣稱。
- 把「這條 net 該怎麼畫」從引擎的猜測變成宣告者的決定（`render` hint）。

**Non-Goals**

- 不做 constraint solver（atopile 有；理由見 §Prior Art DD-7）。
- 不做 parser／語言層。輸入是 JSON over MCP。
- 不改既有 emit 幾何。router、anti-fusion、ledger 全部原封不動。
- 不做元件選型／auto-picking。

## Decisions

### DD-1：新入口是 spec 的**產生器**，不是 compose 的替代品

`declare_circuit` 的輸出**就是** `compose_schematic` 今天吃的那個 spec dict。
資料流：

```
agent 宣告 (declarations[])
   → declare_circuit          ← 本包唯一新增的一層
   → {components, nets, nc} + provenance + completeness verdict
   → compose_schematic        ← 不動
   → export_netlist / verify_netlist_fidelity / ERC / SPICE   ← 不動
```

**理由**：既有四層驗證全部建立在 spec 格式上。若新入口另開 emit 路徑，
那四層要重寫一遍，而且會產生第二套「什麼算正確」的定義——那正是
`BR_20260905` §6.5 記載的 composer/emitter drift 成因。

**被否決的替代案**：讓 `compose_schematic` 直接吃宣告（多型輸入）。
否決理由：它已經是 800 行、22 個參數的函式，再加一個輸入形態會讓
「這次跑的是哪條路徑」變得不可判定。分開的函式讓 spec 可以被 dump 出來人工檢查。

### DD-2：六個宣告原語，覆蓋使用者列舉的全部形狀

使用者原話列舉：「電阻、電感、電容、地線、火線、各種被動元件，透過並聯、串聯、各種組合」。

| 原語 | 覆蓋 | 展開為 |
|---|---|---|
| `connect` | 兩點連接 | 一條 net，兩個 node |
| `bridge` | 被動件跨兩個 net（去耦／上拉／限流） | 兩條既有 net 各加一個 node |
| `series` | 串聯鏈（含 LED 限流） | N-1 條 net，中間節點自動命名 |
| `divider` | 分壓（抽頭） | 3 條 net（top / tap / bottom） |
| `rail` | 電源／地，含**畫法 hint** | 一條 net + render 策略 |
| `no_connect` | 刻意不接 | `nc[]` 條目 |

**並聯**不是獨立原語：兩顆元件並聯 = 兩個 `bridge` 掛在同一對 net 上。
這是刻意的——並聯在 netlist 層沒有獨立表徵，硬給它一個原語會產生
「宣告了並聯但展開後看不出來」的不可判定狀態。

### DD-3：中間節點**自動具名**，不留匿名（與兩個先例都相反）

SKiDL 的 `vcc & r1 & r2 & gnd` 產生 `N$1`；atopile 的 `power.hv ~> r ~> led ~> power.lv`
中間節點**沒有名字**。兩者都需要 escape hatch 才能命名（SKiDL 插一個 Net、
atopile 插一個 interface 或 `override_net_name`）。

本包一律產生**穩定的衍生名**：`<decl_id>_n1`、`<decl_id>_n2`…

**理由**：匿名節點無法被下游引用。而下游正是我們要修的地方——
`fidelity` 要比對它、`render` hint 要指涉它、BR 要能指名它。
`N$1` 這種序號名在 spec 重跑後會漂移，於是 diff 全紅而看不出真正改了什麼。

### DD-4：`rail` 攜帶 render hint —— 這是 61 顆 power glyph 問題的入口側解法

round 1 量到：bodesign 把 GND 的 49 個節點展開成 49 顆獨立 port glyph，
各配一根 2.54mm 短樁，彼此零 copper；而人工交付圖 `#PWR glyph = 0`，
GND 畫成 copper daisy-chain，36 個 junction。

**兩種畫法都對，差別是設計者的意圖，而目前無處可說。**

```json
{"kind":"rail","name":"GND","render":"daisy_chain","scope":["U1","C2","C3"]}
{"kind":"rail","name":"GND","render":"global_label"}
```

`render` 三值：
- `global_label` — 每個節點掛旗（今天的行為，維持為預設）
- `local_star` — 該 scope 內共用一顆 port glyph，實線連到它
- `daisy_chain` — 該 scope 內串成一條實線 rail

**這是本包唯一會影響繪圖決策的欄位**，因此列在 Phase 3 而非第一刀：
它需要 `composer.py` 的 power net 分支讀這個欄位，而那正是
`BR_20260905` §8.5.2 記載的 power clustering 修法失敗的地方
（`moved` 從 10 爆到 67）。**在 `try_reserve` 71/71 失敗那格修好之前，
不要重做 clustering** —— 那格是 round 1 的發現，屬另案。

### DD-5：完整性 gate 是**入口的職責**，fail-fast，不靜默放行

```
對每一支已宣告元件的每一支腳：
  該腳必須恰好出現在 (a) 某條 net 的 nodes 中，或 (b) nc[] 中，二擇一。
  出現 0 次  → E_PIN_UNASSIGNED   （blocking）
  出現 >1 次 → E_PIN_MULTI_NET    （blocking）
```

`E_PIN_MULTI_NET` 直接對應 `BR_20260802_spec_declares_six_pins_in_multiple_nets...`：
那張 BR 的 6 個 pin 被宣告在 2–3 條 net 裡，入口逐字照收，
於是 fidelity gate 的「基準分割」不是分割，而它把 spec 的自我矛盾報成 emitter 缺陷。
**在入口擋掉它，那張 BR 的整個因果鏈就不會啟動。**

### DD-6：每個 net node 帶 provenance，且它是**輸出的一部分**不是 log

```json
"provenance": {"VBAT_SENSE.R13.2": "decl_007", "VBAT_SENSE.R14.1": "decl_007"}
```

**理由**：repo 天條 §2.2「No fabrication」目前只能靠人工審查。
有了 provenance，「系統有沒有自己發明 node」變成一行斷言：
`set(all_nodes) == set(provenance.keys())`。任何無主 node 是 blocking error。

這同時關掉 `BR_20260802_compose_reports_no_provenance_of_the_bytes_it_consumed`
的姊妹格——那張講的是輸入位元組的 provenance，這裡講的是 node 的 provenance，
不同格但同一個誠實度缺口。

### DD-7：**不抄** atopile 的 constraint solver

atopile 的 `assert v_out is v_in * ratio`（不寫電阻值，由 solver 解出）很強，
但它讓「這份宣告是否確定」變成 solver 的性質而非輸入的性質。
solver 無解時要回報什麼、部分解算什麼、以及 solver 版本變動導致同一份輸入
產出不同電路——這三件事各自都是一個 BR 家族。

**本包要求 agent 直接給值。** 值的合理性由既有 `design_suggest` /
`datasheet_lookup` / SPICE 負責，那些已經存在且已經接地。

## Prior Art

（來源：subagent `ses_f882c7acbffe` 2026-09-06 實地抓取，每則附 URL；
**注意**：`docs.atopile.io` 的散文文件已全數 404，官方說法是
「The docs live in the editor now」，故 atopile 證據全部來自 repo 原始碼。）

### atopile — 抄它的「interface bundle」

```ato
module VoltageDivider:
    power = new ElectricPower
    output = new ElectricSignal
    r_bottom = new Resistor
    r_top = new Resistor
    power.hv ~> r_top ~> output.line ~> r_bottom ~> power.lv
```
— `examples/equations/equations.ato`

```ato
interface ElectricPower:
    hv = new Electrical
    lv = new Electrical
```
— `.cursor/rules/ato.mdc`

**抄什麼**：`ElectricPower{hv,lv}` 這種 bundle，讓 `power_3v3 ~ mcu.power`
一句話同時接好電源與地。**對 agent 驅動的入口這特別重要**：
它把「接了 vcc 忘了 gnd」這個最常見的 LLM 錯誤變成**不可表達**。

**不抄什麼**：`~>` 的匿名中間節點（見 DD-3）、constraint solver（見 DD-7）、
以及 `.ato` 語言層本身（我們是 JSON over MCP，不需要 parser）。

**一個決定性的邊界**：**atopile 完全沒有繪圖 hint，因為它不畫原理圖**——
它的流程是 source → netlist → `.kicad_pcb`，沒有 schematic 這一步。
所以「local rail vs global」這個概念在 atopile 裡不存在。
（subagent 查了全部 8 個 examples + `.cursor/rules/ato.mdc` 的完整 G4 grammar，
grammar 裡沒有任何 drawing/placement production。這是「查過且沒有」，不是「沒查」。）

### SKiDL — 抄它的 `stub` 與 fanout 門檻

```python
vcc, gnd = Net('VCC'), Net('GND')
r1, r2, r3, r4 = Part('Device', 'R', dest=TEMPLATE) * 4
ser_ntwk = vcc & r1 & r2 & r3 & r4 & gnd
```
```python
inp, outp = Net('INPUT'), Net('OUTPUT')
ntwk_ce = vcc & r1 & outp & q1['C,E'] & gnd   # 插一個 Net 來命名中間節點
```
— https://devbisme.github.io/skidl/ §Making Serial, Parallel, and Tee Networks

**決定性的一格 —— SKiDL 是兩者中唯一有繪圖 hint 的：**

```python
vcc.stub = True          # 這條 net 在每個接點畫成 label，不畫線
generate_schematic(auto_stub=True)
```
> *"converts the nets that would be hardest to route into labels instead of wires,
> emits power nets (GND, VCC, etc.) as proper KiCad power symbols"*
> —— 附 `auto_stub_fanout`（預設 3）：*"Nets with more pins than this are turned
> into labels before routing"*

**這逐字就是 bodesign `MULTI_NODE_DRAW_MAX_FANOUT = 6` 在做的事**，
差別在 SKiDL 讓使用者可以逐 net 覆寫（`vcc.stub = True`），
而 bodesign 只有一個全域常數且無法覆寫。**DD-4 的 `render` 欄就是補這個。**

**抄什麼**：per-net 的畫法覆寫 + 一個 fanout 預設。
**不抄什麼**：`+=` 是唯一連接運算子（文件自陳 `=` 有時會靜默做錯事）、
`pic10[2:4]` 端點包含式切片（文件自陳 *"Perhaps it is a mistake to do it this way."*）。

**兩者都沒有做到、而我們需要的**：把**電氣身分**與**繪圖身分**分開。
SKiDL 把 hint 塗在 Net 物件上（於是 net 相等性與畫法糾纏），atopile 沒有。
這是一個真實的空缺，不是我們在重新發明輪子。

### 驗證能力對照

| | 結構檢查 | 型別檢查 | 值檢查 |
|---|---|---|---|
| SKiDL | `ERC()`：未接腳、單腳 net、drive 衝突 | 無 | **無**（Net 沒有電壓概念，5V 接 3V3 不會被擋） |
| atopile | 未列舉（未讀 `errors.py`，**未確立**） | interface 同型才可連（**名目型別**，擋 I2C↔Power） | 有，但**只在有人寫 `assert` 的地方** |
| **本包** | 完整性 gate（DD-5）+ 既有 ERC | net kind 檢查 | 委由既有 SPICE / datasheet gate |

**注意 atopile 那格的弱點**：interface 型別檢查是**名目**的——
它擋得住 I2C 接到 Power，擋不住 5V 接到 3V3 pin。
所以「宣告通過型別檢查」是比看起來弱得多的證據。

## Risks / Trade-offs

- **入口自己變成第 41 張 BR 的源頭** — 緩解：`errors.md` §Outcome Codomain
  在實作前先宣告完整結束狀態集合，含「沒抓到」這個狀態。
- **`render` hint 讓繪圖決策分散到兩處**（宣告 + 引擎啟發式）— 緩解：
  hint 缺席時**顯式落到今天的行為**並在 result 標明 `render_source: "default"`，
  不讓兩者共用同一個輸出。
- **consumer 要改寫** — 緩解：Phase 1 只做 btdongle 的一個分壓 + 一組去耦，
  其餘維持手刻 spec，兩條路徑並存，不強制一次遷移。
- **agent 宣告錯誤而系統照做** — 這是本設計的**接受風險**：系統的職責是
  忠實落地 + 盡力檢查，不是替 agent 判斷電路對錯。
  誰抓得到、誰抓不到逐格寫在 `errors.md`。

## Critical Files

- `packages/eda-bridge/bodesign_eda_bridge/composer.py:1887` — `compose_schematic`
  簽名；本包的輸出必須符合它的 `spec` 契約。**不改這個檔**（Phase 1-2）。
- `packages/eda-bridge/bodesign_eda_bridge/composer.py:2181-2231` — 現行的
  label/wire 判定（power-rail / high-fanout / cross-IC）。DD-4 的 `render`
  hint 若採納，Phase 3 動這裡。
- `packages/eda-bridge/bodesign_eda_bridge/composer.py:1809` —
  `MULTI_NODE_DRAW_MAX_FANOUT = 6`，SKiDL `auto_stub_fanout` 的對應物。
- `services/mcp/server.py` — 新 verb 的 handler + schema 兩處註冊。
- `packages/eda-bridge/bodesign_eda_bridge/fidelity.py:223` —
  `expected_partition_from_nets`，DD-5 的 `E_PIN_MULTI_NET` 就是在保護它的前提。
