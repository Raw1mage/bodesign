# Proposal: eda-bridge_draftsman-series-divider-wireable

## Why

bodesign 是一個「提供 MCP / tool / CLI / skill / KB **讓 agent 設計電路**」的 harness。
盤點 2026-09-07 的 verb 表面：**61 個 verb，讓 agent 宣告電路拓樸的入口 0 個。**

```
compose_schematic        吃一份現成的 {components, nets} spec
export_netlist           把已存在的圖匯出
verify_netlist_fidelity  事後比對兩份已存在的東西
design_suggest           只回單點數值，且 assert 明文禁止它說 "committed"
```

**沒有任何一個 verb 的輸入是「電路長什麼樣」。** 每一個都假設那份東西已經存在。
於是 consumer 只能在 bodesign 外面自己寫：`thesmart_products/04.btdongle/C03-EE/02_build/sch_gen/`
下有 10 支 python，`NETS` 手刻在 `design.py` 裡。**btdongle v2.4 交付的四張圖就是這麼來的。**

### 這個空缺的代價，用本 repo 的 issue 帳本量

```
issues/ 全部 BR（含 closed/）                        146
落在原理圖／連線／畫圖層（檔名關鍵詞）                 42
   sch|wire|route|label|junction|net|compose|draftsman|placement|symbol|pin
時間跨度  2026-07-06 → 2026-09-06                     三個月
判定為「輸入不完整導致的引擎退化」                     13 張（+ 3 張存疑）
```

逐張判定見 §附錄 A。**13 張不是 42 張**——其餘是引擎自己的幾何缺陷、文件漂移、
C04 層問題，補上入口不會讓它們消失。但那 13 張裡有 **6 張已經 CLOSED，而症狀在
2026-09-05 的新產品線上原封不動復現**（`BR_20260905_schematic_emitter_...` §5 逐張列出）。

**復發本身就是證據：前幾次修的是症狀。** 每一次修法都落在「引擎拿到不完整輸入之後
該怎麼退化得體面一點」，而沒有人在入口處問「這份輸入完整嗎」。於是每個下游關卡各自
發明自己的容錯，而**每一種容錯的失效各自長成一張 BR**。

### 為什麼現在做

2026-09-06 的實測（round 1 診斷，engine handler `ses_f884168d5ffe`）把退化的形狀量出來了：

| 量測 | 值 | 意義 |
|---|---|---|
| 27 條 net 進 router 之前就被判 label | **13 條** | 一半的電路在畫之前就放棄了 |
| router 實際呼叫 / 接受 | 21 / 18（86%） | **router 是健康的**，它只是沒東西可畫 |
| 116 條 wire 中，power glyph 短樁 | **64 條** | GND 的 49 個節點散成 49 顆獨立符號 |
| 交付圖（人工）的 `#PWR` glyph | **0 顆** | 同一塊板，GND 畫成 copper daisy-chain，36 個 junction |

**引擎不是畫不出來，是沒有人告訴它要畫什麼。** router 拿到 14 條 net，畫成了 11 條。
缺的是那 13 條——以及「GND 該就地成群還是全域掛旗」這種**只有設計者知道、而目前無處可說**的決定。

### 這不是新需求

- 2026-07-07 使用者：「我覺得生成原理圖是非常單純的事情，為什麼會花幾十個小時燒 token 原地踏步？」
- 2026-07-16 使用者：「目前這個專案已經開過一堆 plan 了，但都半途而廢。」
- 2026-09-07 使用者：「這個問題不是只卡了幾小時，而是好幾個月的無數 BR 家族」

**本包自己就是證據**：slug 逐字是 series（串聯）· divider（分壓）· wireable（可佈線），
建於 2026-07-23，`proposed`，history 只有 initial 一筆，13 個檔全是 placeholder。
**有人六週前看見了這個缺口、開了包、然後停手。**

## Original Requirement Wording (Baseline)

- 2026-09-07：「我認知的『設計電路』，就是把電阻、電感、電容、地線、火線、各種被動元件，透過並聯、串聯、各種組合，畫在圖紙上。這樣的功能定義應該不難懂吧？為何一直設計不出來」
- 2026-09-07：「bodesign 就是一個提供 mcp, tool, cli, skill, KB 讓 agent 設計電路的 harness，搞半天沒有人設計電路！」
- 2026-09-07：「這個問題不是只卡了幾小時，而是好幾個月的無數 BR 家族」
- 2026-09-07：「你查一下關於這件事應該開過無數 plan 了。你隨便挑一個把它寫清楚，再進入實作」
- 2026-07-16：「目前這個專案已經開過一堆 plan 了，但都半途而廢。大部份 plan 的目標是一致的，就是根據 C00 定義的內容，產出 C01~C04 的交付物。但是 AI 目前還做不到。」
- 2026-07-07：「我覺得生成原理圖是非常單純的事情，為什麼會花幾十個小時燒 token 原地踏步？」

## Requirement Revision History

- 2026-07-23: initial draft created via plan-init.ts（全 placeholder，未推進）
- 2026-09-07: 由 round 1 診斷 + 使用者框架換位重寫。射程從「修 draftsman 的串聯分壓」
  擴為「補上 agent 宣告電路拓樸的入口」——原 slug 的三個詞（series/divider/wireable）
  是這個缺口的**症狀**，不是它本身。

## Effective Requirement Description

1. bodesign 必須提供一個 verb，讓 agent 用電路設計者的語彙**宣告**電路拓樸：
   兩點連接、被動件跨接兩個 net、串聯鏈、分壓、去耦、上拉、限流、接地、電源。
2. 該 verb 的輸出是既有 `compose_schematic` 已經吃的 `{components, nets, nc}` spec，
   **不是新的 emit 路徑**。
3. 該 verb 必須在入口處做**完整性檢查**並 fail-fast：每一支已宣告元件的每一支腳，
   必須落在某條 net 或 `no_connect` 裡；不然報缺項清單，不靜默續跑。
4. 每一個輸出的 net node 必須可回溯到唯一一條 agent 宣告（provenance），
   使「系統沒有自己發明電路」成為**可機檢的事實**而非宣稱。

## Scope

### IN
- 新 verb `bodesign_declare_circuit`：宣告 → 展開 → 完整性 gate → spec。
- 宣告原語：`connect` / `bridge` / `series` / `divider` / `rail` / `no_connect`。
- `rail` 攜帶 render hint（`global_label` / `local_star` / `daisy_chain`），
  這是 round 1 那 61 顆 power glyph 問題的入口側解法。
- provenance map：net node → 產生它的宣告。
- 完整性 gate 與其錯誤碼（見 `errors.md`）。

### OUT
- **不做電路合成**。系統不從「我要一個 3V3 buck」推導出元件與連接。
  那正是 KB `netlist-synthesis-gap` 明文擋下的 silent-fabrication 風險，本包不推翻它。
- 不改 `compose_schematic` / `kicad_emit` 的既有 emit 幾何路徑。
- 不做 constraint solver / auto-picking（atopile 有，我們刻意不抄，理由見 `design.md` §Prior Art）。
- 不做 `.ato` 那種需要 parser 的語言層。輸入是 JSON over MCP。
- 不處理 round 1 發現的 `try_reserve` 71/71 失敗（那是引擎自己的缺陷，另案）。

## Non-Goals

- 不追求一次涵蓋全部 btdongle 45 元件 / 27 net。Phase 1 只要能跑通一個分壓 + 一組去耦。
- 不保證產出的圖「好看」。本包管的是**圖上有沒有電路**，不是版面美學。
- 不接管 multi-unit symbol 支援（`BR_20260905_compose_schematic_lacks_multi_unit_symbol_support`），
  但 schema 會**預留 `unit` 欄**，因為現行 spec 無法表達它正是那張 BR 的成因之一。

## Constraints

- **No silent fallback**（repo 天條 §2.1）：缺欄位／缺 pin ⇒ fail fast + 缺項清單。
- **No fabrication**（repo 天條 §2.2）：每個 net node 必須有 provenance，
  沒有 provenance 的 node 不得出現在輸出裡。
- KB `netlist-synthesis-gap` 的禁令維持：**程式不自動合成 netlist**。
  本包做的是「agent 想好了，系統負責落地＋檢查」，與該禁令不衝突（辨析見 `design.md` §Context）。
- 產出必須是既有 spec 格式，才能不動既有四層驗證（ERC / fidelity / crosscheck / SPICE）。

## What Changes

- `services/mcp/server.py`：新增 handler + schema（新 verb = 兩處註冊）。
- `packages/eda-bridge/`（或 `workflow-core`）新增一個純函式模組：
  宣告 → spec 的展開器 + 完整性 gate。**不碰 `composer.py` / `kicad_emit.py`。**
- consumer（thesmart_products btdongle）從手刻 `design.py::NETS` 改為呼叫新 verb。

## Capabilities

### New Capabilities
- `declare_circuit`：把設計者語彙的拓樸宣告展開成 compose spec，附 provenance 與完整性判定。
- `circuit_completeness_gate`：回答「這份宣告完整嗎」——目前沒有任何 verb 回答這個問題。

### Modified Capabilities
- `compose_schematic`：**行為不變**，但多了一個上游來源。既有呼叫端 byte-stable。
- `rail` render hint 若採納，`composer.py` 的 power net 處理需要讀這個欄位——
  這是本包唯一會碰到既有繪圖決策的地方，列為 Phase 3，不在第一刀。

## Impact

- 受影響程式碼：`services/mcp/server.py`、新模組、（Phase 3）`composer.py` power net 分支。
- 受影響 consumer：thesmart_products `04.btdongle` C03 線（目前阻斷中，等本包）。
- 受影響文件：`specs/architecture.md`（新增一層「宣告層」在 C03 上游）。
- 不受影響：C04 以後全部路徑、既有 fidelity/ERC gate 的判準。

## 附錄 A — 42 張圖層 BR 的逐張判定

判準：**這張 BR 修的是「引擎對著不完整輸入的退化行為」（HIT），
還是「引擎自己的缺陷」（MISS）？** 只有前者是本包的下游。

### HIT — 13 張

| BR | 為什麼是這個空缺的下游 |
|---|---|
| `BR_20260723e_draftsman_cannot_wire_basic_series_divider_collinear_fusion` | 本包 slug 的字面來源。畫不出串聯分壓，因為沒有地方宣告「這是一組分壓」 |
| `BR_20260905_draftsman_connection_strategy_degenerates_to_label_farm...` | 「degenerate」就是退化。引擎面對只有 net 清單的輸入，只能猜哪些該畫 |
| `BR_20260905_schematic_emitter_produces_pin_label_stubs_only...` | consumer 自寫 emitter 的直接產物；它存在的原因就是引擎沒有入口 |
| `closed/BR_20260708_draftsman_wire_routing_no_obstacle_avoidance_label_only_fallback` | 止血法是全頁退回 label-only。**該 fallback 從未回收，成為系統預設形態** |
| `closed/BR_20260723_c03_composer_accepts_pinout_only_no_passive_completeness_gate` | **最純的一張**：composer 接受「只有 pinout」的輸入而不報錯 |
| `closed/issue_20260618_compose_schematic_draftsman_quality` | 「只是 ERC-clean 的 netlist 傾倒物」——輸入只有 netlist，輸出就只能是傾倒物 |
| `BR_20260802_spec_declares_six_pins_in_multiple_nets...` | **決定性**：spec 自我矛盾（6 個 pin 宣告在多條 net），入口逐字照收，gate 把它報成 emitter 缺陷 |
| `closed/BR_20260723d_compose_silent_empty_box_on_active_ic_symbol_not_found` | 輸入缺 symbol，引擎靜默產空框而非報缺項 |
| `BR_20260905_compose_schematic_lacks_multi_unit_symbol_support` | spec **沒有 `unit` 欄**，呼叫端無法宣告「D1 要放四個 unit」——輸入表達力缺口 |
| `closed/BR_20260730b_compose_facade_arg_encoding_empty_spec_and_zombie_busy_gate` | 部分命中：其中「**空 spec 四閘齊綠**」那一格正是缺完整性 gate |
| `BR_20260802_real_product_pages_carry_dozens_of_open_circuit_nodes_cause_untraced` | 宣告同 net 的節點失去連接，且成因未追出——provenance 缺失的直接後果 |
| `closed/BR_20260706_placement_no_sheet_fill_planning_20pct_utilization_center_strip` | 較弱：版面擠成一團是「連接只有 5.08mm」的下游，元件之間本來就不需要空間 |
| `BR_20260906_kb_has_no_fallback_ladder_when_compose_is_rejected_by_fidelity` | 較弱：fallback ladder 之所以需要，是因為輸入不完整時引擎只能猜 |

### 存疑 — 3 張

| BR | 存疑理由 |
|---|---|
| `BR_20260905_router_corner_and_stacked_pins_short_declared_no_connect_pins` | 宣告的 NO_CONNECT 被違反 = 輸入被忽略；但根因是 router 幾何，兩者都說得通 |
| `closed/BR_20260730_platform_gate_unreachable_drives_consumer_fork...` | consumer fork 的形狀與 `mk_sch.py` 完全相同，但那次成因是 gate 不可執行不是輸入缺口 |
| `closed/BR_20260706_symbol_geometry_two_side_only_no_four_edge_pin_placement` | 「側邊電源符號擁擠的結構根因」與 61 顆 power glyph 同族；但它是符號幾何缺陷 |

### MISS — 26 張（列舉不逐條說明）

引擎自己的幾何／熔合缺陷（`collinear_wire_fusion_shorts`、`one_wire_emitted_three_times`、
`guard_c_pin_tip_fallback_box`、`dd20_opposing_flag_separation`、`left_pin_stub_orientation`、
`occupancy_ledger_wire_reserves`）、文件漂移（`bus_route_docstring`、`load_symbol_signature`）、
回報誠實度（`compose_reports_no_provenance`、`readability_gate_scores_a_live_composed_sheet`、
`export_netlist_line_count_zero`、`render_companion_pdf_only`）、C04 佈線層
（`net2pcb_*`、`route_dsn_*`、`autoroute_*`、`castellated`）、以及流程／帳本類。

**補上入口不會讓這 26 張消失。** 這是本包的成本論證邊界：它處理 13 張的成因，不是 42 張。
