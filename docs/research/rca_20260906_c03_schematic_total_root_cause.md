# RCA — C03 為什麼「總是畫不好電路原理圖」（總根因分析）

- **日期**: 2026-09-06
- **類型**: 研究型交付（唯讀分析，未改任何 code、未跑任何引擎驗證）
- **分析者**: BRNS handler `ses_f8a9e2c35ffewY7uZ5UDWQi7xw`（葉節點），dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`
- **判決權**: dispatcher / 使用者。本文只列選項與代價，不裁示修法。

---

## 0. 一句話結論

**三個月、39 張 BR 修的是「把一份已經設計完的 netlist 畫成圖」這一段；而使用者交辦的 C03 是「從 datasheet 設計出被動網路，再用工程標準格式出圖」。設計那一段在 bodesign 裡沒有任何 verb、沒有任何契約、沒有任何 gate——它是一個被 KB 明文記載為「刻意留白」的洞。所以不是修得不夠好，是修錯了段。**

而在被修的那一段（畫圖）裡，還疊了三個獨立的結構缺陷：可讀性從未被定義成可驗證契約、存在**兩條互不相通的出圖管線**、以及唯一的品質 gate（fidelity）量的是拓撲而非可讀性。

---

## 1. 使用者定義的 C03 vs 引擎實作的 C03（並排）

使用者原話定義的 C03：

```
輸入契約                     設計段                        繪製段
電路需求                                                  用工程標準格式
晶片型號(MPN)      ──→   設計 RC/RLC/LC/RL 被動網路  ──→   繪製圖紙
datasheet
pinout datasheet
```

bodesign 實際實作的 C03（`compose_schematic` 的輸入契約，`packages/eda-bridge/bodesign_eda_bridge/composer.py:437`）：

```python
KNOWN_KEYS = ("components", "nets", "nc", "all_label", "l6_avoidance")
```

即：

```
輸入契約                     設計段                        繪製段
{components, nets}    ──→   （不存在）              ──→   composer + kicad_emit
（已設計完的 netlist）
```

**落差**：`compose_schematic` 收的 `nets` **就是設計的產物**。它的輸入契約假設設計已經完成。輸入端沒有 MPN、沒有 datasheet、沒有 pinout、沒有電路需求——這五個欄位一個都沒有。

驗證（判別力：控制組同時執行）：

```
grep -c "datasheet" packages/eda-bridge/bodesign_eda_bridge/composer.py   → 0
grep -c "def "      packages/eda-bridge/bodesign_eda_bridge/composer.py   → 41   ← 控制組，證明檔案讀得到
```

composer 全檔 2678 行，**「datasheet」一詞出現零次**。`bodesign_datasheet_lookup` / `bodesign_vault_spec_check` 與 `compose_schematic` 之間**沒有任何資料流**。

這與 AGENTS.md §2.4「Datasheet-grounded electrical claims」的天條並不矛盾——因為那條天條約束的是「陳述規格前要查 datasheet」，而 C03 的**連接與元件值決策從來不經過 bodesign 的任何 verb**，所以它根本不在那條天條的射程內。天條沒有被違反，它只是**打不到這裡**。

---

## 2. 39 張 BR 的分群：它們修的是哪一層的什麼

BR 家族清單（檔名關鍵字比對 `issues/` + `issues/closed/`，控制組 `zzz_no_such_marker` 回 0）：

| 年月 | 張數 |
|---|---|
| 2026-06 | 1 |
| 2026-07 | 18 |
| 2026-08 | 14 |
| 2026-09 | 6 |
| **合計** | **39** |

時間軸：`20260618` → `20260905`。最早一張 `issues/closed/issue_20260618_compose_schematic_draftsman_quality.md` 的標題已經是「產不出 draftsman 品質的原理圖（只是 ERC-clean 的 netlist 傾倒物）」——**三個月前的第一張 BR，與今天的症狀逐字相同**。

按「修的是哪一層」分群：

| 群 | 張數（約） | 代表 BR | 修的東西 |
|---|---|---|---|
| **G1 幾何/排版** | ~12 | `BR_20260706_symbol_geometry_two_side_only_no_four_edge_pin_placement`、`BR_20260802_dd20_opposing_flag_separation_moves_label_anchor_off_pin_ungated`、`BR_20260804g_guard_c_pin_tip_fallback_box_is_degenerate` | 符號幾何、pin 座標、label 錨點、text extent、頁面尺寸 |
| **G2 連線/熔合** | ~8 | `BR_20260706_draftsman_collinear_wire_fusion_shorts`、`BR_20260723e_draftsman_cannot_wire_basic_series_divider_collinear_fusion`、`BR_20260905_router_corner_and_stacked_pins_short_declared_no_connect_pins` | 畫線造成電氣短路 → guard 攔截 |
| **G3 gate 自身缺陷** | ~9 | `BR_20260802_c03_gate_green_conflates_connectivity_with_circuit_correctness`、`BR_20260802_fidelity_gate_cannot_report_open_circuit_and_hardcodes_a_diagnosis`、`BR_20260804j_the_verification_layer_has_no_verification_layer` | 驗證層自己沒有判別力 |
| **G4 介面/契約** | ~6 | `BR_20260730b_compose_facade_arg_encoding`、`BR_20260723_compose_symbol_dirs_stdlib_merge`、`BR_20260901d_power_ports_unreachable_from_mcp_layer` | MCP schema、參數傳輸、verb 可達性 |
| **G5 設計完整性** | **1** | `BR_20260723_c03_composer_accepts_pinout_only_no_passive_completeness_gate` | **唯一一張打到設計段的** |
| **G6 harness/非 C03** | ~3 | `BR_20260802_reset_hard_*`、`BR_20260802_stale_pyc_*` | 工作樹、快取（與 C03 無關，因關鍵字誤命中） |

**分群的結論**：39 張裡有 **38 張在畫圖層與驗證層**，**只有 1 張（G5）觸及「這張圖上的電路本身完不完整」**。而那一張的 fix（見 §5）落在了**另一條管線**上。

---

## 3. 分層根因

### 根因 A｜產品/契約層：C03 承諾的是「畫」，使用者要的是「設計+畫」——而這個落差從未被寫成契約

**依據**：
- `packages/eda-bridge/bodesign_eda_bridge/composer.py:437` — `KNOWN_KEYS` 只有五個鍵，`nets` 是輸入不是輸出。
- `skills/bodesign/stages/c03-ee/references/pinout-to-circuit-method.md:1-8` — 明白寫著「**it is the most AI-heavy part of the stage, because it is reasoning, not a tool call**」。設計段被**明文指派給 LLM 推論**，不是指派給任何確定性機制。
- `ragbase` object `concept.bodesign.netlist-synthesis-gap`（confidence: `partial`）逐字：「bodesign 無法從 PRD 直接畫出板，因為 **subsystem→pin-level netlist 的合成引擎從未實作**。這是**刻意留白**」。

**判讀**：這不是疏漏，是一個**有意識的產品邊界決定**，而且理由是誠實的（「netlist 對錯是唯一無法用確定性方法保證的環節，故團隊寧可擋在 gate 後也不冒 silent-fabrication 險」）。問題在於**這個邊界從未被向使用者揭露成「C03 不含設計段」**。使用者交辦 C03 時預期的是兩段，拿到的是一段，而中間那段的缺席不會報錯——它表現為「畫出來的圖沒有電路」。

**可證偽條件**：若存在任何 verb 其輸入包含 MPN/datasheet 且輸出為 `{components, nets}`，則此根因不成立。實測 57 個 `bodesign_*` MCP tool（`grep -c '{"name": "bodesign_' services/mcp/server.py` → 57）中無此形狀。

### 根因 B｜設計能力層：知識齊備、接線中空（「有知識沒接線」）

使用者說「技術知識素材應該給得夠了」——**這句話是對的，而且比預期更對**。KB 裡確實有被動網路設計知識：

| KB object | 內容 | 是否被任何 pipeline 消費 |
|---|---|---|
| `control.sch.pullup-termination-sizing` | I2C 上拉/終端阻抗計算（NXP UM10204） | ✅ `design_suggest.py:29` |
| `control.si.crystal-oscillator-layout` | 晶振負載電容（NXP AN1706 + Microchip AN826） | ✅ `design_suggest.py:561` |
| `control.si.interface-requirements` | C03 交給 C04 的 SI 需求 | ✅ `design_suggest.py:288` |
| `control.power.decoupling-pdn-strategy` | 去耦 / PDN 目標阻抗三層策略 | ⚠️ 只被 C04 layout checker 消費（`packages/workflow-core/.../checkers/decoupling_pdn.py:1`） |
| `concept.pcb-decoupling-pdn-rules`、`concept.sch.pin-level-datasheet-contract`、`step.sch.dcdc-review-checklist`、`workflow.sch.datasheet-contract-review`、`step.sch.mcu-adc-frontend-review` 等 | 去耦數值、pin 級 datasheet 契約、DC/DC 審查清單 | ❌ **零程式碼引用** |

量測（控制組併行）：`grep -rn "control\.sch\.\|control\.pcb\.\|concept\.pcb\|control\.si\.\|control\.power\."` 在 `packages/` + `services/` 命中 **5 個檔**；控制組 `compose_schematic` 命中 **7 個檔**（證明 grep 有判別力）。5 個裡有 **3 個是 C04 layout checker**，1 個是 `server.py:1249` 的一句 schema 說明字串，**只有 `design_suggest.py` 一個是 C03 設計段**。

而 `design_suggest.py` 本身——**它沒有被暴露成任何 verb**：

```
grep -rn "design_suggest" services/mcp/server.py skills/bodesign/scripts/gate.py skills/bodesign/SKILL.md  → 零命中
grep -rn "design_suggest" 全 repo *.py（排除自身）                                                        → 只有 tests/test_design_suggest.py:14
```

**它唯一的呼叫者是它自己的單元測試。** 這是本 RCA 最尖銳的一格：bodesign **寫過**一個 datasheet/KB 錨定的被動網路設計建議引擎（756 行，commit `d1ab7fd`「C03 evidence-backed design-suggestion layer (軌C)」），每個建議值帶 `evidence` 區塊指回 KB object、帶公式、帶 provenance、`status` 恆為 `suggested` 且 `review_required=True`——**完全符合 bodesign 的誠實哲學**——然後**沒有接到任何對外介面上**。

**判讀**：根因 A 說「設計段沒有 verb」，根因 B 進一步說「設計段的**引擎已經存在**，只是沒有插頭」。這比純粹的缺席更值得注意，因為它意味著補這一格的成本遠低於從零建。

**可證偽條件**：若 `design_suggest` 的任何函式能從 MCP tool list 或 `gate.py --list` 被呼叫到，則此根因不成立。

### 根因 C｜驗證層：可讀性從來不是 gate，唯一的 gate 量的是拓撲

`fidelity.py` 的自述（`packages/eda-bridge/bodesign_eda_bridge/fidelity.py:9-14`）：

> 「Principle: compare by PARTITION, not by net NAME. The electrical truth a schematic must preserve is *which pins share a net*.」

它量的是**拓撲一致性**：spec 宣告的 net partition 是否等於 KiCad 匯出的 netlist partition。它**不量**任何與「這張圖人看不看得懂」有關的東西。

而 `check_c03` 的 `_NOT_CHECKED_BASE`（`packages/workflow-core/bodesign_workflow_core/check_c03.py:1010-1022`）自己把邊界列得很誠實——**這份清單是本 repo 誠實文化的模範，也正是本根因的證據**：

```
decoupling_adequacy   — 「A board with zero decoupling caps passes this gate.」
component_values      — 「a 10k where 100k belongs passes.」
loop_compensation / sequencing_networks / thermal_and_current /
protection_and_esd / analog_signal_integrity
```

**七項未檢查全部落在「電路設計對不對」這一軸。** 而「圖可不可讀」連在這份未檢查清單裡都沒有出現——因為它從來不在 `check_c03` 的射程內。

可讀性量測**存在**但**不是 gate**：
- `ink_metrics.py`（151 行）算 `ink_pct` / `content_fill_pct`，全檔**零 `raise`**，是純量測。
- `render_qa.py:97 qa_svg_text` 有 PASS/FAIL 概念，但作用域是**文字重疊**，不是「這張圖有沒有畫出電路」。
- `compose_schematic` 全部 14 處 `raise` 中（`composer.py:178..2677`），只有 `:2677 FidelityError` 是品質 gate，其餘是輸入合法性。**沒有一處因為「產出不可讀」而失敗。**

**這解釋了本 RCA 要回答的核心現象**：真板 fidelity gate PASS（拓撲一致）而圖仍是 label farm（wired=11 / labelled=16 / junctions=7），**不是 gate 壞了，是 gate 從設計上就不看那一軸**。gate 綠燈是誠實的，它只是回答了一個不是使用者在問的問題。

**可證偽條件**：若存在任何會因可讀性指標不達標而 `raise` / 回 `gate=FAIL` 的路徑，則此根因不成立。

### 根因 D｜架構層：**兩條互不相通的出圖管線**，而文件横跨兩者

這是本次分析最意外的發現，也是「修了 39 張還是畫不好」的結構性解釋之一。

**管線 1（MCP 引擎）**：`bodesign_compose_schematic` → `composer.py` → `kicad_emit.py` → `fidelity.py`。
**管線 2（skill 引擎）**：`symbol_4edge.py` → `host_from_pinmap.py` → `netlist_to_kicad_sch.py` → `render_hybrid_sch.sh`。

兩者**沒有任何程式碼關聯**：

```
grep "^import|^from" skills/bodesign/engines/kicad/scripts/netlist_to_kicad_sch.py
  → import re,sys,uuid,os / import math      （零 eda-bridge 引用）
grep -rln "compose_schematic" skills/               → 只有 6 個檔，全部是 markdown 文件 + gate.py facade，
                                                      無一是出圖腳本
控制組：grep -rln "analyze_schematic" skills/     → 28 個檔（證明 grep 有判別力）
```

而 `skills/bodesign/stages/c03-ee/references/schematic-drawing-rules.md` ——**那份全 repo 唯一寫下「可讀電路圖該長什麼樣」的文件**（106 行，8 條規則）——它管的是**管線 2**：

> `.net + symbols/ --netlist_to_kicad_sch.py--> hybrid .kicad_sch`（該檔 line 8-14）
> 「All scripts live in `engines/kicad/scripts/`」

其中第 4 條「Connection style — hybrid（discrete = wires, buses = labels）」逐字寫著：

> 「Discrete networks drawn as real wired networks: decoupling `Vrail → C → GND`, series `label → R → label`, pull-up `Vrail → R → label`… **Never the third option — generic boxes with bare pad numbers and no topology ("worse than a spreadsheet")**。」

**這正是 BR_20260905 label-farm 描述的症狀。規則早就寫下來了，只是它管不到真正在跑的那條管線。**

同樣的分裂證據在 PC-001 上更決定性（見 §5）。

**判讀**：39 張 BR 重於管線 1（MCP 引擎），而品質規則寫在管線 2。兩邊各自演化，沒有任何機制保證一致——這就是使用者看到的「每次修完一個，下一個又冒出來」。

**可證偽條件**：若 `composer.py` / `kicad_emit.py` 引用了 `schematic-drawing-rules.md` 的任何規則編號，或 `netlist_to_kicad_sch.py` import 了 eda-bridge，則兩條管線並非互不相通。

### 根因 E｜演算法層：anti-fusion guard 把「避免短路」買在「不畫電路」上

這一條的證據已由 `issues/BR_20260905_draftsman_connection_strategy_degenerates_to_label_farm_on_non_label_friendly_topology.md` 完成，本 RCA 只補程式碼錨點與結構定位。

降級發生在兩個地方：
- `composer.py:2623` — `"anti-fusion guard down-graded {n} net(s) to label to avoid cross-net collinear wire fusion"`
- `kicad_emit.py:1560` — 「重試 ≤ 3 次，否則該 net 降級為 label fallback」；`:1777` / `:1846` 記錄 `reason="anti-fusion"`

另一個獨立的降級來源在 `composer.py:2148-2153`（M6-8d cross-IC bus policy）：當 ≥2 條訊號跨同一對 IC，**該 IC 對的每一條訊號全部強制成 global label**。加上 `:2144` 的 `MULTI_NODE_DRAW_MAX_FANOUT = 6`（`:1762`）與 `:2140` 的 power-rail 降級，**一張典型子電路的 net 有四條獨立路徑可以被降級成 label，而畫線只有一條路徑**。預設偏向結構性地倒向 label。

值得記一筆的是 `composer.py:2129-2135` 的修正注解——BR_20260905 把原本的 `len(nodes) >= 3 ⇒ label` 改成只降級 power rail 與 high-fanout，並明寫「a 3..MULTI_NODE_DRAW_MAX_FANOUT signal star — decoupling, pull-up, divider, **RC/RL/LC** — is DRAWN with junctions」。**這正是使用者要的那四種網路，引擎在 09-05 才刚把它們從「一律掛 label」改回「畫出來」。**

**判讀**：演算法層確實有缺陷，且正在被修。但它是 **根因 C 的下游**：因為可讀性不是 gate，所以「降級成 label」對引擎而言是**免費的**——它避開了一個會 raise 的錯（fusion short），換來一個不會 raise 的錯（圖不可讀）。**在這個激勵結構下，任何理性的實作都會選擇降級。**

**可證偽條件**：若存在一條路徑使「降級成 label」也會觸發失敗或阻止交付，則「降級是免費的」不成立。

### 根因 F｜工具暴露層：`spec` 是一個不透明的 `{"type": "object"}`，使用者無法表達意圖

`services/mcp/server.py:1133`：

```python
"spec": {"type": "object"}
```

**沒有任何內層欄位描述。** 而 compose 實際讀的五個鍵中，`all_label` 與 `l6_avoidance` 這兩個**直接控制出圖風格的開關**，在整份 `server.py` 裡**一次都沒出現**（控制組：`connection_style` 出現 3 次，證明 grep 有判別力）。

意味：一個只看 MCP schema 的消費端，**無從得知 `all_label` 這個選項存在**，也不知道 spec 要怎麼寫。它只能從錯誤訊息逆向推（`composer.py:437` 的 `KNOWN_KEYS` 錯誤提示）。

同層的其他缺口：
- **無 C03 專用 cli**。`scripts/` 只有 `run_tests.sh` / `sync_engine.sh` / `ingest_thesmart_products.py` / `bodesign-self-heal.sh` / `check_issue_headers.sh` / `hooks`。消費端要跨圖、要改一行、要重跑，沒有任何本地入口——只能呼 MCP 或**自寫腳本**。已知硬事實：peer 自寫 `mk_sch.py` / `mk_sch2.py`、自寫 `verify_net.py`（帶兩個判別力缺陷）。**這不是消費端不守規矩，是工具層沒給入口。**
- **形狀覆蓋缺口已立案但未裁示**：`issues/issue_20260903_c00_arch_and_c03_power_tree_emitter_verbs_missing.md` 記載客人是「**在 61 個 verb 裡找不到對應形狀之後**才換路徑的」——這張的診斷與本 RCA 同形：**不是不知道有工具，是工具家族的形狀覆蓋有缺口**。

**可證偽條件**：若 MCP schema 描述了 spec 的內層欄位，或 `scripts/` 存在一支可驅動 C03 出圖的 cli，則此根因不成立。

---

## 4. 根因之間的上下游關係

```
根因 A（契約：C03 不含設計段）
   │
   ├──→ 根因 B（設計引擎寫了但沒接線）
   │
   └──→ 因為設計段不存在，所有注意力集中到畫圖段
            │
            ├──→ 根因 C（可讀性不是 gate）
            │        └──→ 根因 E（降級成 label 是免費的）
            ├──→ 根因 D（兩條管線各自演化）
            └──→ 根因 F（使用者無法表達意圖）
```

**A 是最上游。** 即使 C、D、E、F 全部修好（可讀性有 gate、兩條管線合一、不再降級、schema 透明），得到的仍然只是**把人手寫的 netlist 畫得很漂亮**。離使用者交辦的「給我 datasheet，你設計 RC/RLC/LC/RL 並出圖」還隔一整段。

**回答派工單的核心問題「三個月修的是不是錯的那一段」：**

**是。** 但需要精確限定：那三個月修的是**真缺陷**（短路、幾何崩壞、gate 自身沒判別力都是真的），不是白做工。但它們全部落在一個**即使全部修完也不會達成使用者目標**的段落。這是典型的「在路燈下找鑰匙」：畫圖層的缺陷**會報錯**（FidelityError、ERC、視覺 QA 看得到），所以它們持續產生 BR；設計層的缺席**不會報錯**，所以三個月只有 1 張 BR 打到它。

**39 張裡 38 張在修一個會叫的病，1 張打到那個不會叫的。**

---

## 5. 決定性實例：PC-001 落在了另一條管線上

這一節把根因 A、B、D 三條縫在一個可驗證的事件上，是本 RCA 最硬的一格證據。

`BR_20260723_c03_composer_accepts_pinout_only_no_passive_completeness_gate`（已在 `issues/closed/`）是 39 張裡**唯一**打到設計完整性的一張。它的症狀逐字（該檔 line 16）：

> 「你真的只是把所有的元件純 pinout 畫出來。但是完全沒有電路設計。」

實測數據（該檔 line 20-32）：整個 aiguard C03 只有 3 顆電阻（預期 50–150）；`02_mcu_core`（STM32N657）的 U/R/C/L = **1/0/0/0**。這張 BR 自己的 RCA 寫得完全正確（line 50）：

> 「**The gap is the enforcement seam, not the knowledge.** … **The method is load-bearing prose with no machine backstop**」

它被修了（commit `68bdde1`，「C03 passive-completeness gate PC-001 — machine backstop for the pinout-to-circuit obligation table」）。**但修在哪裡？**

```
git show --stat 68bdde1:
  skills/bodesign/engines/kicad/scripts/validation_detectors.py   +220
  skills/bodesign/engines/kicad/scripts/analyze_schematic.py        +7
  skills/bodesign/engines/kicad/scripts/finding_schema.py           +1
  skills/bodesign/engines/kicad/scripts/kicad_types.py              +1
  tests/test_passive_completeness.py                              +202
  specs/architecture.md                                             +5
```

全部落在 **`skills/`（管線 2）**。確認（控制組併行）：

```
grep -rln "PC-001|passive_completeness|passive_gaps" --include=*.py .
  → tests/test_passive_completeness.py
  → skills/bodesign/engines/kicad/scripts/{validation_detectors,analyze_schematic,finding_schema}.py
  → packages/ 零命中、services/ 零命中
控制組：grep -rln "R7_MANDATED_PASSIVE" --include=*.py .
  → packages/workflow-core/bodesign_workflow_core/check_c03.py（證明同一支 grep 確實搜得到 packages/）
```

**從 `bodesign_compose_schematic` 這條路走，PC-001 永遠不會被執行。** 它只在消費端另外呼叫 skill 的 `analyze_schematic.py` 時才跑。

而 MCP 側唯一的同類 gate 是 `check_c03` 的 R7，它的覆蓋面是 `_MANDATED_PASSIVES`（`packages/workflow-core/bodesign_workflow_core/check_c03.py:744-762`）——**實際內容只有兩筆：`tps62088` 與 `tps62824`**。兩題對一題的写死型號表，不是一個通用的 pin-class 義務引擎。

**這一格同時證實三件事**：
1. 設計完整性問題被正確識別過（BR 的 RCA 寫得很準）；
2. 修復落在了**使用者實際不走的那條管線**上（根因 D）；
3. 於是 BR 被歸檔進 `closed/`，**帳面上它被修好了**，而實際交付路徑上的洞還在。

> **這就是「逐張修掉之後仍然畫不出可用電路圖」的機制：修復是真的，只是它不在交付路徑上。**

---

## 6. 對帳 2026-07 postmortem

KB object `workflow.eda.schematic-engine-postmortem`（四代演進：occupancy-ledger → scale-coherence → draftsman-v2 → layered-pipeline）逐字結論：

> 「核心結論：產能瓶頸不是排版演算法，而是 (1) 使用者品味是唯一知識源（每輪審圖才長出新規則）；(2) 稽核工具與交付物不同源（假紅假綠反覆燒工單）。」

（注：`source.engine.plan.group.failure.postmortem.2026.07.…` 這個 object 的 `body_md` 長度為 **0**——它是一個空的 source 登記，實質內容在上面那個 workflow object。這本身是一個小型揭露缺陷，見 §8。）

| postmortem 的診斷 | 三個月後的判定 | 依據 |
|---|---|---|
| **(1) 「產能瓶頸不是排版演算法」** | **對，且低估了**。不只不是排版演算法，連「畫圖」都不是真正的瓶頸——設計段才是。postmortem 当時還在畫圖層內部找瓶頸，射程未及根因 A。 | §1、§3-A |
| **(2) 「使用者品味是唯一知識源，每輪審圖才長出新規則」** | **對，且仍然成立**。但根本原因已可命名：可讀性從未被寫成可驗證契約，所以規則只能後驗式地從審圖長出來。 | §3-C |
| **(3) 「稽核工具與交付物不同源」** | **對，而且這個診斷被低估成一個工具問題**。它實際上是一個**架構分裂**：兩條出圖管線。PC-001 落錯邊就是它的直接後果。 | §3-D、§5 |
| **四代重寫的方法論（換演算法 / 從零重寫 / 分層）** | **被證偽**。四代全部失敗且使用者裁決廢止；第四代 layered-pipeline 至今仍是**骨架**——`pipeline.py:11-14` 自述「各 stage 內部**尚未**接管 composer/emit 邏輯，現行 render 仍走 compose_schematic 原路（行為 byte-identical）」；`composer.py` 的 import 清單中**沒有 `pipeline`**。M7-1 之後的逐層遷移未發生。 | `pipeline.py:11-14`、`composer.py:24-50` |
| **沒被執行的那一項** | postmortem 識別出「規則只能從審圖長出來」，但**沒有得出「那就把規則寫成 gate」這個行動**。規則確實被寫下來了（`schematic-drawing-rules.md`，8 條）——但寫成了**散文**，而且是給**另一條管線**的散文。 | §3-C、§3-D |

**對帳總結**：postmortem 的三條診斷**全部成立**，且三個月後一條都沒失效。它錯在**射程**：它把問題定位在「畫圖引擎的知識來源與稽核工具」，沒有問「這條 pipeline 的起點那份 netlist 是誰設計的」。且它開出的藥（layered-pipeline）**從未真正上線**。

---

## 7. 修復路線選項與代價（不裁示，供 dispatcher / 使用者決定）

四個選項不互斥，但**優先序有差**。

### 選項 1｜產品層：把 C03 拆成兩個可分別承諾的任務

把「C03 = 設計 + 繪製」明寫成兩個階段（例如 C03a 電路合成 / C03b 圖紙繪製），各自有 DoD。
- **代價**：最低（文件與契約變更）。
- **效果**：不增加任何能力，但**立即消除預期落差**。使用者交辦 C03 時會知道設計段需要人/LLM 自備。
- **風險**：這是誠實地承認能力邊界，不是解決問題。若使用者要的就是設計段，這個選項等於回答「做不到」。

### 選項 2｜設計段：把 `design_suggest.py` 接到介面上

引擎已存在（756 行、KB 錨定、evidence 區塊齊備、`suggested` 不越級），缺的是一個 verb 把它接出來，並擴充目前的三類（I2C 上拉 / SI / 晶振）到 `pinout-to-circuit-method.md` 的九類 pin 義務表。
- **代價**：中。主要工作是擴充規則覆蓋面（去耦層級 / 上拉 / 負載電容 / 分壓 / 濾波），而 KB 已有多數知識（§3-B 表）。
- **效果**：直接打到根因 A/B。這是唯一能讓「給 datasheet → 得到被動網路」成立的選項。
- **風險**：碰到 KB `concept.bodesign.netlist-synthesis-gap` 當初刻意避開的那條紅線（避免 silent fabrication）。**但 `design_suggest` 的設計已經回答了這個顧慮**：它 SUGGEST 不 
DECIDE、`review_required=True`、每個值帶 KB 錨點。需要裁示的是「建議而非決定」這個姿態是否足以跨過那條紅線。

### 選項 3｜驗證層：把可讀性寫成 gate

把 `schematic-drawing-rules.md` 的 8 條散文投影成可量測判準（例如：drawn-wire 比例下限、短樁比例上限、junction 數、每個 2-pin 被動件至少一端有實線），失敗則 `raise` 或 `gate=FAIL`。
- **代價**：中。技術上不難（`route_stats` 已經在算 wired/labelled/junctions），難在**訂閾值**——而門檻值本身是品味問題（postmortem 診斷 2）。
- **效果**：打到根因 C、連帶拆掉根因 E 的激勵結構（降級不再免費）。
- **風險（重要）**：這是一個**形式軸**判準。依 AGENTS.md「內容邏輯先於格式結構」，它不授權任何「電路對了」的宣稱。若先做這個而不做選項 2，**會得到一張畫得很漂亮、電路仍然不完整的圖**——而且 gate 會是綠的。

### 選項 4｜架構層：兩條出圖管線合一

決定哪一條是交付路徑，另一條廢止或降為內部工具；規則與 gate 只挂在交付那條上。
- **代價**：高。兩條管線各自累積了三個月的修復（MCP 側 39 張 BR；skill 側 PC-001 + 4-edge symbol + host_from_pinmap）。合一意味著放棄一邊的累積或做一次真正的整合。
- **效果**：打到根因 D。**不做這一項，選項 2 與 3 都有可能再次落在錯的那條管線上**（PC-001 就是前例）。
- **風險**：屠龍式重構已經失敗過四次（§6 對帳）。任何合一方案應該是**漸進的**，且先回答「哪一條是交付路徑」這個產品問題。

### 建議的優先序（推薦而非裁示）

**選項 1（即刻，成本最低）→ 選項 4 的「先決定哪條是交付路徑」那半步 → 選項 2 → 選項 3。**

理由：選項 3（可讀性 gate）看起來最直接呼應「畫不好」，但它是**全場最容易做、最容易驗、最容易給出綠燈的一個**——而它回答的問題（圖好不好看）不是使用者最終要的那個（電路對不對）。先做它會重演 §3-C 描述的同一個模式：**一目綠燈，沒一格回答電路對不對**。

---

## 8. 誠實列出未量邊界

本 RCA 是**讀與綜合**，未跑任何引擎、未跑測試、未重新量測任何幾何數字。以下是明確的邊界：

**推論而非量測**：
1. **BR 分群的張數是近似值**。我依檔名與已讀的十餘張內容分群，**未逐張讀完 39 張**。G1–G6 的張數不應被當成精確計數；而「G5 只有 1 張」這個關鍵斷言是基於**檔名語意 + 已讀內容**，若有另一張 BR 在內文裡談設計完整性而檔名看不出來，我會漏掉。
2. **「39 張」本身是關鍵字匹配結果**（派工單說約 38）。其中至少 3 張（`reset_hard`、`stale_pyc`）與 C03 無關，是被 `guard` / `compose` 等詞誤命中的。反向也可能存在：真屬 C03 但檔名不帶這些詞的 BR 會被漏掉。
3. **「兩條管線互不相通」是從 import 關係與 grep 推得**。我證明了 `netlist_to_kicad_sch.py` 不 import eda-bridge、skill 出圖腳本不呼 `compose_schematic`。我**沒有**追蹤過消費端實際怎麼交替使用這兩條（例如先 compose 再用 skill 腳本後製）。
4. **`design_suggest` 的實際能力邊界未實測**。我讀了它的 docstring 與前 60 行 + KB 錨點常數，**未讀完 756 行**，未驗證它的三類建議（I2C/SI/晶振）實際輸出品質。「擴充到九類 pin 義務表的成本是中等」是**估計，不是量測**。

**未讀 / 未查**：
5. `kicad_emit.py` 3752 行——只 grep 了 anti-fusion / label 相關行，**未讀完**。`routing.py`（1905 行）、`preplace.py`、`placement_rules.py`、`occupancy.py` **完全未讀**。演算法層（根因 E）的論證因此主要依賴 BR_20260905 已量的數據而非我自己的代碼分析。
6. `skills/bodesign/doctrine.md`（17775 bytes）只 grep 了四個關鍵字，**未通讀**。若它裡面有對設計段的表態，我會漏掉。
7. `skills/bodesign/stages/c03-ee/GUIDE.md` 568 行，**讀了約 140 行**（purpose / DoD / inputs / SOP 0–2）。SOP 步驟 3–8（分析、datasheet 驗證、交叉比對、匯出、橋接）未讀完。
8. `~/.local/share/opencode/skills/bodesign-kb/SKILL.md`（已發佈版）**未讀**，只確認了目錄只有一個檔。
9. `packages/component-kb`（vault / spice_card / repository）**未讀內容**，只列了檔名。它是否藏有可用於設計段的元件知識，未評估。
10. **526 個 KB object 中我只實際讀了 2 個的 `body_md`**（postmortem 與 netlist-synthesis-gap），其餘只看標題與 id。§3-B 的「有知識」判斷是**基於標題**，未驗證每個 object 的內容深度是否足以支撐自動化設計。

**已撤回的工作**：
11. 派工單補充 2 曾要求爬 thesmart_products session `ses_f8cfa6affffe5eoejSmzJq71W5` 全 443 則，補充 3 撤回。我實際只讀到 **60 則**（read cap 分頁的第一頁）就停手，**這 60 則的內容未進入本報告任何一行**。派工單補充 3 提供的硬事實（peer 自寫 mk_sch2.py / design.py 人手寫 / verify_net.py 兩個判別力缺陷 / bodesign 只有 fidelity gate 協助 / 交付物自陳電氣軸為零）我**直接引用未重量**，它們在 §3-F 當旁證使用。
12. **未訪談 peer**。消費端視角的證詞由 dispatcher 負責取得，本報告的四面（tool / skill / KB / 引擎）全部是 bodesign 自身的静態分析。

**小型揭露缺陷（順手發現，未立案）**：
13. KB object `source.engine.plan.group.failure.postmortem.2026.07.…` 的 `body_md` 長度為 **0**。`ragbase_query` 會把它當命中回傳（排在第一），但拉不到任何內容——「有這篇 postmortem」與「這篇 postmortem 是空的」共用同一個命中輸出。實質內容在 `workflow.eda.schematic-engine-postmortem`（356 字元）。若 dispatcher 認為值得，可另立 BR。
14. `ragbase_query` 的 and-tokens → or-tokens 降級會讓**任何胡亂查詢都回非空結果**（我的控制組 `zzqqxx nonexistent marker token` 回了 repo=5 user=5）。它有誠實標示 `fallbackApplied: true` + 一行警告，**所以不是缺陷**——但讀結果時必須看那一格，否則會把「零命中」讀成「有相關知識」。

---

## 9. 引用清單（全部經 grep/read 確認，未靠記憶）

| 錨點 | 內容 |
|---|---|
| `packages/eda-bridge/bodesign_eda_bridge/composer.py:437` | `KNOWN_KEYS = ("components","nets","nc","all_label","l6_avoidance")` |
| `composer.py:1762` | `MULTI_NODE_DRAW_MAX_FANOUT = 6` |
| `composer.py:2124-2153` | all_label / power-rail / high-fanout / cross-IC bus 四條 label 降級路徑 |
| `composer.py:2623` | anti-fusion guard 降級警告文字 |
| `composer.py:2677` | `raise FidelityError` — 唯一的品質 gate |
| `kicad_emit.py:1560, 1777, 1846` | 重試≤3 次後降級為 label；`reason="anti-fusion"` |
| `fidelity.py:9-14` | 「compare by PARTITION, not by net NAME」 |
| `packages/workflow-core/bodesign_workflow_core/check_c03.py:1010-1022` | `_NOT_CHECKED_BASE` 七項未檢查 |
| `check_c03.py:744-762` | `_MANDATED_PASSIVES` — 只有 tps62088 / tps62824 兩筆 |
| `services/mcp/server.py:1133` | `"spec": {"type": "object"}` — 零內層描述 |
| `packages/eda-bridge/bodesign_eda_bridge/design_suggest.py:1-29, 288, 561` | 設計建議引擎 + 三個 KB 錨點 |
| `packages/eda-bridge/bodesign_eda_bridge/pipeline.py:11-14` | 分層 pipeline 自述「尚未接管」 |
| `skills/bodesign/stages/c03-ee/references/pinout-to-circuit-method.md:1-8, 32-47` | 設計段是 reasoning 不是 tool call；九類 pin 義務表 |
| `skills/bodesign/stages/c03-ee/references/schematic-drawing-rules.md:8-14, §4` | 管線 2 的圖示；hybrid 連線規則 |
| `issues/closed/issue_20260618_compose_schematic_draftsman_quality.md` | 最早一張 BR，症狀與今相同 |
| `issues/closed/BR_20260723_c03_composer_accepts_pinout_only_no_passive_completeness_gate.md:16, 20-32, 50` | 唯一一張設計完整性 BR |
| `issues/BR_20260905_draftsman_connection_strategy_degenerates_to_label_farm…md` | label farm 四格實驗 |
| `issues/issue_20260903_c00_arch_and_c03_power_tree_emitter_verbs_missing.md` | 形狀覆蓋缺口 |
| commit `68bdde1` | PC-001 落在 `skills/`，非 `packages/` |
| commit `d1ab7fd` | design_suggest 落地 |
| commit `5599793`、`b612a43` | multi_unit / router-corner 修復（派工單引用，已驗 sha） |
| KB `concept.bodesign.netlist-synthesis-gap` | 「合成引擎從未實作…刻意留白」 |
| KB `workflow.eda.schematic-engine-postmortem` | 四代演進三條結論 |

---

## 10. 消費端證詞對帳（round 2）

證詞來源：thesmart_products 值星官 `ses_f8cfa6affffe5eoejSmzJq71W5`（2026-09-06，dispatcher A2A 訪談）。
本節**不讀 peer repo 任何檔案**——peer 側事實一律標 `peer-testimony Qn` 直接引用；
bodesign 側每一格都帶本 repo 的 file:line，是本輪新量的。

證詞對 v1 六條根因的總判決：**四條證實、一條修正、一條新增**。修正的那條最重要——
根因 F 我在 v1 寫成「skill 面缺 stage→verb 對應表」，證詞顯示**對應表其實存在**
（`GUIDE.md:467`），缺的是**投影後拿不到執行體**。方向相反，修復動作也相反。

### 10.1 vault 三張表空、datasheet verb 零呼叫 → 證實根因 A、加強根因 B

`peer-testimony Q1`：`.bodesign/vault/vault.db` 的 `spec_values=0 packages=0 pins=0`，
`bodesign_datasheet_lookup` / `bodesign_vault_spec_check` 在整個 btdongle C03 零呼叫。

bodesign 側，三格全部量到，且**三格都指向同一個結構事實：vault 與 C03 之間沒有任何一條線**。

| 問 | 量到的 | 證據 |
|---|---|---|
| C03 stage guide 有沒有把 datasheet→vault→元件值寫成必經步驟？ | **沒有。** 整份 42,960-byte 的 GUIDE.md 對 `datasheet_lookup` / `vault_spec_check` / `spec_values` **零命中** | `grep` 於 `skills/bodesign/stages/c03-ee/GUIDE.md` rc=1；控制組同檔 `compose_schematic` 命中 3 行（`:141` `:488` `:544`），證明探針有判別力 |
| 有沒有 gate 在 vault 空表時擋下後續 verb？ | **沒有。** `_vault_guard`（`services/mcp/server.py:354-360`）只捕捉 `VaultError`——那是 vault **開不起來**；「開得起來但三張表是空的」不是 `VaultError`，走的是正常回傳路徑 | `services/mcp/server.py:354` |
| C03 的兩個主 verb 有沒有讀 vault？ | **都沒有。** `composer.py` 全檔 `vault` 零命中；`check_c03.py` 全檔 `vault` 零命中 | 兩處 grep rc=1；控制組 `net` 在 composer.py 命中 162 次 |

**這推翻了 GUIDE.md 自己的宣稱**。`GUIDE.md:185-186` 寫著

> Datasheets are what turn a *consistency* check into a *correctness* check. Without them
> the engine can only confirm the design agrees with itself.

這句話是對的，而且是本報告根因 A 的完整表述。但它接下來給的方法是
`GUIDE.md:189` 的 `sync_datasheets_digikey.py`——**把 PDF 抓到 `datasheets/` 目錄**，
不是灌進 vault。於是 `GUIDE.md:194-197` 的下文寫「extractions land in
`datasheets/extracted/<MPN>.json` and are reused across runs」——那是**另一個
儲存體**，與 `bodesign_vault_spec_check` 查的 `component-kb` SQLite
（`packages/component-kb/bodesign_component_kb/storage.py:163` `CREATE TABLE spec_values`）
沒有任何一行程式碼連著。

所以 peer 的「沒有 stage→verb 對應表」在這一格上**比它自己說的更嚴重**：
不是 agent 不知道該叫哪個 verb，是 **C03 的 datasheet 路徑與 vault 的 datasheet 路徑
是兩套互不相識的儲存**，把 stage→verb 表補上去也不會讓 `spec_values` 長出一列。

**對回根因 A（電氣真值無錨點）**：v1 說「C03 沒有任何一步強制電氣宣稱回溯 datasheet」，
本節把它從「沒有強制」收緊成「**連可回溯的儲存都沒接上**」。
**對回根因 B（design_suggest 孤兒）**：`design_suggest.py` 的三個 `suggest_*` 用的是
KB 規則（`control.sch.pullup-termination-sizing` 等）不是 vault，所以它**即使被接上也
不會消費 vault**——vault 空表這條缺口，在目前架構裡沒有任何一個 C03 消費者會發現。

### 10.2 「宣告限制但不發訊號」類別 → 證實根因 C，並給出它的普查

`peer-testimony Q2`：`kicad_emit.py:18` 明寫 multi-unit 不支援，但 emit 照跑；
D1.3/D1.4 消失、D1.5（宣告 NC）被吸進 GND。`5599793f` 已修此一例。

bodesign 側普查結果——**這不是一個 bug，是一個文體**。

`kicad_emit.py:18-19` 的原文：

> Only single-unit symbols and rotation-0 placement are supported in this slice;
> multi-unit symbols and rotated placement are explicit future work.

這句話寫在**模組 docstring** 裡。查遍全檔 3752 行，`unit` 的每一個命中都是
**實作**多單元排版的程式碼（`:408-414` `_stack_units`、`:504-599` 單元堆疊步距），
**沒有任何一行是「輸入含 unit>1 就報錯」的 guard**。也就是說：

- 2026-09-05 之前：docstring 說不支援，程式碼靜默丟棄 unit>1 的 pin（peer 實測 D1.3/D1.4 消失）
- 2026-09-05 `5599793f` 之後：程式碼開始支援，**docstring 那句話沒有跟著改，至今仍在 `:18`**

兩個時期共用同一句宣告，而那句宣告在兩個時期**分別是「真的且無執行力」與「假的」**。
讀者無論在哪一天讀它，都得不到當天的真相。

同一形狀在三檔的分佈（本輪量測，`grep -n` 於三個檔案）：

| 位置 | 宣告的限制 | 執行時行為 |
|---|---|---|
| `kicad_emit.py:18-19` | multi-unit / rotation 不支援 | 無 guard；先靜默丟棄，後靜默支援，宣告從未更新 |
| `kicad_emit.py:190` | `status: str = "skipped-no-kicad-cli"` | **這一格是對的**——它把「沒跑」做成一個可讀的狀態值，不是沉默 |
| `kicad_emit.py:1467` | 「Degenerate boxes (zero span) are skipped」 | skip，無計數、無回報欄位 |
| `kicad_emit.py:3093` | 「a zero-length segment silently opts itself OUT」 | 自述 silently，無 opt-out 清單 |
| `composer.py:871` | 「silently discarded the ... largest-bbox cell」 | 註解描述的是**已修的舊行為**（過去式，安全） |
| `composer.py:958-959` | 「the compaction is silently skipped」 | 現在式，描述**當前**行為，無訊號 |

結構性佐證：`kicad_emit.py` 有 **7 個 `raise`、31 個裸 `continue`**；
`composer.py` 有 21 個 `raise`；`fidelity.py` 只有 1 個 `raise`
（`FidelityError.__init__`，`fidelity.py:141-155`）。
比例本身不是缺陷——迴圈裡的 `continue` 多數合法。但它標定了搜尋面：
**31 個 `continue` 中每一個「跳過了什麼」都沒有出口欄位承接**，
而 `kicad_emit.py:190` 證明這個 codebase **知道**怎麼做對（把 skip 做成 status 值），
只是沒有把它當成通則。

**對回根因 C（畫圖層修的是症狀）**：v1 說 38 張 BR 在畫圖層打轉。本節給出為什麼打不完——
**每一個「宣告即豁免」的位置都是一張未來 BR 的種子**，而它們的共同缺陷不在幾何，
在於「這一步沒做」與「這一步做了」共用同一個輸出。這是 AGENTS.md 天條 1
（no silent fallback）的變體，且違反處在**引擎內部**，不是消費端。

**對回 `code-thinker` §12（產出狀態 codomain）**：`kicad_emit` 的結束狀態集合裡
缺的正是 `not-run`——`_stack_units` 跳過一個 degenerate box 之後，
呼叫端拿到的東西與「沒有 degenerate box」完全相同。

### 10.3 fidelity gate 與 emitter 綁死 → 證實根因 D，peer 的三個判準全部命中

`peer-testimony Q5`：提出獨立 verb `bodesign_verify_netlist_fidelity`，
輸入 spec/emitted `.net`/nc_declared，輸出 FUSED/SPLIT/NODE_DIFF/NC_WIRED 四類獨立欄位，
exit 0/1/2 三態（parsed 0 nets 不得回「無差異」）。

逐項對照 `fidelity.py` 現況（本輪讀完全檔 473 行）：

**(a) 能否脫離 `compose_schematic` 單獨吃 `.net`？——不能，而且是兩層阻斷。**

- **MCP 層**：`fidelity` 在 `services/mcp/server.py` 只出現 4 次，全部是
  `compose_schematic` 的參數或描述（`:162` `:173-174` `:1138`）。
  `grep '"name": "bodesign_[a-z_]*fidelity'` **零命中**；
  控制組 `'"name": "bodesign_[a-z_]*check'` 命中 5 個已註冊 verb。
  57 個註冊工具裡沒有一個是 fidelity。
- **函式層**：`fidelity.py` 有 `parse_net_file(path)`（`:181`）——它**本來就是**
  peer 要的「吃一個 `.net`」的原語，而且是 public。但唯一的完整入口
  `verify_partition_fidelity(expected_nets, sch_path)`（`:454`）的第二參數是
  **`.kicad_sch` 路徑**（`:467` `p.rglob("*.kicad_sch")`），
  內部 `:470-471` 自己開 tempdir 呼叫 `kicad-cli` 導出。
  **一個持有 `.net` 的呼叫端無法從這個入口進去**，即使 `parse_net_file` 就在隔壁。

  更精確地說：`compare_partitions(expected, candidate_classes, power_refs)`（`:380`）
  **已經是** peer 要的那個純函式——它吃兩個 partition，不碰檔案系統。
  缺的只是一層 30 行的 `.net`→classes adapter 加上 MCP 註冊。
  這與根因 B（`design_suggest.py` 寫好了沒接線）**是同一個形狀**：
  能力已存在於 package 內，缺的是暴露。

**(b) `NC_WIRED` 有沒有獨立輸出？——沒有，而且 `fidelity.py` 全檔不認識 NC 這個概念。**

`grep 'nc_\|no_connect\|NC\b\|not_connected' fidelity.py` **rc=1（零命中）**；
控制組同 pattern 在 `kicad_emit.py` 命中 8 次——**emitter 認識 NC，gate 不認識**。

後果精確可推：一個 spec 宣告 NC 的 pin，若 emitter 把它接進 GND（peer 的 D1.5），
在 `compare_partitions` 眼裡它是「baseline 有這個 node、candidate 也有、
但 peer 集合變了」⇒ 落進 `fused`（`:437`）。
**「NC 被誤接」與「兩條真訊號被短路」在輸出上完全同型**，
而它們的修法一個是刪一條線、一個是重畫一頁。

`FidelityReport` 有 12 個欄位（`:31-63`），其中 `disconnected`/`fused`/`regrouped`
是 BR_20260802 為了分辨開路與短路而加的——**那次修復做對了方向**
（`:42-48` 的註解明寫「an OPEN CIRCUIT and a SHORT read identically」）。
NC_WIRED 是同一條軸上的第四格，只是還沒有人發現它缺席。

**(c) parsed-zero 是 exit 2 還是「無差異」？——是「無差異」，且路徑上有一個吞掉錯誤的 `continue`。**

`sch_union_classes`（`:194`）的 `:216-221`：

```python
r = subprocess.run(["kicad-cli", "sch", "export", "netlist", ...])
if r.returncode != 0 or not out.exists():
    continue
```

**每一張 sheet 的匯出失敗都被 `continue` 吞掉**，沒有計數、沒有欄位、沒有 raise。
若全部 sheet 都失敗，`parent` 是空 dict，`comps` 是空，回傳 `[]`。
接著 `compare_partitions`：`c_idx` 空 ⇒ `c_nodes` 空 ⇒ `shared` 空 ⇒
`moved` 空。而 `only_b`（`:398`）只收「baseline peer 數 >1」的 node——
**若 spec 的 net 全是多 pin 的，它們確實會落進 `only_b`，`ok` 為 False**。

所以這一格的判決要分兩態，而**兩態共用同一條程式路徑**：

| 情境 | `ok` | 讀起來像 |
|---|---|---|
| spec 有多 pin net，且 kicad-cli 全失敗 | False（`only_baseline` 非空） | 「所有 node 都從圖裡消失了」——**誤導**：真相是圖從未被讀取 |
| spec 只有單 pin net（或 spec 本身空） | **True** | 「FIDELITY PASS diff 0/0」——**假綠燈** |

`FidelityReport.summary()`（`:108`）會印 `candidate nets=0 nodes=0`，
所以資訊**在輸出裡**——但 `ok` 這個布林、以及 `compose_schematic` 回傳的
`fidelity.ok` 欄位，**不區分這兩態**。`GUIDE.md:488` 又把驗收判準寫成
「returns `fidelity.ok` / diff 0/0」——**判準綁在那個不區分的布林上**。

peer 的 exit 2 提案（對應其 `verify_net.py:110-114`
`FATAL: parsed ZERO nets … Refusing to report 'no differences' from an empty read.`）
**正是修這一格**。peer 在消費端自建的工具，在這一點上比引擎嚴格。

**對回根因 D（gate 不可獨立取用）**：證實，且比 v1 寫的更具體——
不是「沒有做」，是**做好了、放在 public 函式裡、沒有暴露**。
**對回根因 C**：(c) 是根因 C 在驗證層的複本——引擎修了 emitter 的靜默 skip 之後，
gate 自己的 `:220` 還留著同一個形狀。

### 10.4 封裝：published skill 不帶 `packages/` → **修正根因 F 的方向**

`peer-testimony Q2`：`gate.py` 預設回 `could not find bodesign packages/`，
peer 必須 `export BODESIGN_SRC` 或在 `mk_sch_bodesign.py:25-29` 把 sys.path 寫死
到 `/home/pkcs12/projects/bodesign/packages/{eda-bridge,workflow-core}`。

bodesign 側量測：

| 問 | 量到的 | 證據 |
|---|---|---|
| published skill 有沒有 `packages/`？ | **沒有**。`~/.local/share/opencode/skills/bodesign/` 有 8 個項目（SKILL.md / doctrine.md / engines / openmv / references / scripts / stages / thesmart_products），無 `packages` | `test -d` rc=1 |
| repo checkout 有沒有？ | **有** | 同一支探針 `test -d` rc=0——**控制組決定性**：探針本身有判別力，rc=1 只可能是「投影副本真的沒有」 |
| `gate.py` 怎麼找？ | `_resolve_src()`（`skills/bodesign/scripts/gate.py:75-102`）：先 `$BODESIGN_SRC`（`:81`），再從 gate.py 位置往上走找 `packages/workflow-core`（`:92`），都找不到就丟 `LANDING_PACKAGES_NOT_FOUND`（`:99-102`），帶 hint `export BODESIGN_SRC=…` | `gate.py:75-102` |

**判決：這是部署債，不是 skill 面根因——而且 `gate.py` 這一格做得對。**

`gate.py:820-860` 是本輪讀到**最好**的一段揭露設計。`:829-844` 把
`packages_resolved` / `packages_root` / `packages_error` 三個欄位獨立輸出，
`:838-840` 的 `impact` 字串明講

> roster is accurate but nothing in it is runnable until packages/ resolves

而 `:849` 的註解直接寫下判準：

> TRUE PROVES ONLY THAT packages/workflow-core RESOLVED

這正是 `code-thinker` §12 要求的「不同結果不得混在同一個輸出」——
`gate.py --list` 在兩種情況下都回 `ok:true`（roster 讀得到），
但 `packages_resolved` 這一格分辨了「verb 存在」與「verb 跑得動」。
`GUIDE.md:49-54` 也把這件事寫成 **Landing-verb prerequisite (BR_20260903a)**，
明講「read the field, not `count`」。

**所以 v1 §根因 F 的方向是錯的，本節修正**：

- v1 寫：skill 面缺 stage→verb 對應表，agent 不知道該叫什麼。
- 證詞 + 本輪量測顯示：**對應表存在**（`GUIDE.md:454-490` 的 Gate/done-criteria
  逐條列出 `bodesign_prd_bom_crosscheck`、`bodesign_check_c03`、
  `compose_schematic(fidelity=True)`、`render_qa.qa_svg_text`，
  且每條都寫了「report 缺席 = gate 沒跑，不得推定 PASS」），
  **錯誤訊息也存在且說得很清楚**。缺的是**投影機制沒把執行體帶過去**。

修復動作因此完全不同：v1 隱含的動作是「寫一份表」（skill 面工作），
實際需要的是「投影時帶 `packages/`，或讓 `gate.py` 在 XDG 安裝下自動找到 repo」
（部署面工作，AGENTS.md §3.2 的 capability projection 契約）。
**寫一份已經存在的表，三個月後這一格還是紅的。**

一個仍屬缺陷的殘留：`peer-testimony Q2` 顯示 peer 最終選擇
**在消費端 sys.path 寫死絕對路徑**（`mk_sch_bodesign.py:25-29`），
而不是用 `BODESIGN_SRC`。錯誤訊息的 hint 給的是後者。
兩者都能跑，但前者把 bodesign 的 repo 路徑烙進 peer 的原始碼——
這是 `specs/architecture.md:75` 記載的 **consumer fork drift** 的入口形狀。

### 10.5 `bodesign_check_c03` 是不是 MCP verb → **是，證詞的「找不到入口」有第三個解釋**

`peer-testimony Q3`：peer 只在 `KB_Hierarchical_Schematics_and_DFM.md:135` 看到它被規劃要求，
不知道是否實作。

bodesign 側量測，**兩處都在**：

- handler：`services/mcp/server.py:485` `def _h_check_c03(a: dict)`，`:486` 從
  `bodesign_workflow_core` 匯入 `check_c03`，`:494` 呼叫
- schema：`services/mcp/server.py:1170` `{"name": "bodesign_check_c03", "handler": _h_check_c03,`
- 描述（`:1171`）長達一整段，逐條說明 R1–R8，並且**以 `READ not_checked FIRST` 開頭警語**，
  明講「A PASS means 'the wiring agrees with the paperwork', NOT 'this circuit is correct'」

所以派工單的二分法（存在⇒為何 stage guide 沒帶人去用／不存在⇒KB 引用了不存在的 verb）
**兩邊都不成立**——存在，**且 stage guide 有帶人去用**：
`GUIDE.md:47`（交付物表第 10 列，`check_c03.report.json`，`gate: PASS` required）、
`GUIDE.md:467-471`（Gate 段，含「A missing report means the entry gate has not run: say so;
never presume PASS」）、`GUIDE.md:472-476`（要求 `out_dir=<project>/C03-EE`）。

**第三個解釋，而且它是可量的**：peer 讀的是 **published skill**，而 published skill
**不帶 `packages/`**（§10.4）。`check_c03` 的 handler 第一行就是
`from bodesign_workflow_core import check_c03`（`server.py:486`）。
`specs/architecture.md:75` 記載這個 verb 曾經因為 eager import 鏈
（`__init__.py` → `.checkers` → `registry.py` → `copper_clearance.py` → `bodesign_design_ir`）
在沒有 ee worker 的 repo 裡直接 `ModuleNotFoundError`——那次已用 PEP 562 `__getattr__` 修好。
但**投影缺 `packages/` 是同一個症狀的另一個成因**，而且它更早發作：
連 import 都到不了。

於是 peer 的「不知道是否實作」是**準確的觀察**：從它站的位置，
「這個 verb 不存在」與「這個 verb 存在但我這個安裝拿不到執行體」
**共用同一個輸出**。這是 §10.4 部署債的直接下游後果，也是本報告
根因 F 修正後的完整表述。

**對回根因 F（修正後）**：不是缺文件，是**投影缺執行體，導致「不存在」與
「拿不到」不可分辨**。歸類 G13-harness-disclosure。

### 10.6 C03 交付物定義 → **新增根因 G：bodesign 自己就把 C03 定義成文件階段**

`peer-testimony Q6`：peer 交 `C03_電路原理圖與設計規格書_v2.4.docx`（commit a0434d3）；
repo 內 `.docx` 3 個、`.kicad_sch` 12 個、`.net` 6 個、ERC 13 份、PDF 3 個，
而 **`.kicad_sch` / `.net` / 5 支腳本全部 untracked**，tracked 的只有第一代 6 支。
peer 自承 C03 被當「文件產出階段」而非「設計凍結階段」，
並認為應該是「凍結、可重現、電氣上獨立驗證過的 netlist，說明書是投影」。

派工單問的是二分法：定義本身文件導向 ⇒ peer 的顛倒是 bodesign 教的；
定義是 netlist 而 peer 沒照做 ⇒ stage guide 可教性問題。

**量測結果：是第一項。而且不是語氣問題，是 MANDATORY 標記的分佈。**

`GUIDE.md` 全檔只有 **4 處** 標了 `MANDATORY`（`grep -n 'MANDATORY'`，四行全列）：

| 行 | 標題 | 管的是 |
|---|---|---|
| `:199` | Vault-Absent Substitution Protocol | 選型（設計） |
| `:229` | BOM 提案必讀清單 + SSOT 衝突自查段 | BOM↔pin allocation 一致性（文書一致性） |
| `:399` | **Document consolidation rule（單一 docx + `img/`）** | **文件排版** |
| `:437` | **File-naming rule — `C03_` prefix** | **檔名** |

**四個 MANDATORY 裡有兩個管的是文件的樣子。**
而 `:396` 的交付物表把 `<product>_電路設計文件.docx` 這一列
**用粗體標成 generated**，是全表唯一加粗的一列：

> | **Consolidated EE document** | **`<product>_電路設計文件.docx` / `C03_Circuit_Design.docx`** | **generated** | **ONE merged Word doc** |

`:399-435` 這 37 行寫的全是 docx 生產細節：docxmcp facade 的 `doc_dir` vs `token`
參數陷阱、`cht_template` 的 `numPr` 自動編號會與 markdown 的「第 N 章」雙重編號、
封面樣式名 `置中大大` / `置中大` / `置中`、TOC 用 `TOC Heading`。
**這是本檔關於任何單一交付物最長、最具體、最可執行的一段。**

對照 netlist 的待遇：`:392` 交付物表一列（`..._網路表.xlsx` / `.net`，
kind = exported，備註 "full, or honest subset"），
`:44` 一列 `Netlist_Status.md`（**required iff a full netlist is not recoverable**）。
沒有 MANDATORY，沒有加粗，沒有「netlist 必須 tracked」，
**沒有任何一句要求 netlist 進版控或凍結**。

`GUIDE.md:447-450` 的 `C03_` 前綴規則甚至**明確把 `02_build/` 排除在外**：

> **Out of scope:** build/intermediate artifacts under `02_build/`

而 peer 的腳本與中間 `.kicad_sch` 正是住在那裡。GUIDE 把它們定義成
**非 user-facing**，於是它們 untracked 完全符合 GUIDE 的教導。

`specs/architecture.md` 側同樣：`:100` 描述 C03→C04 gate 讀的是 netlist，
`:101-104` 描述 PC-001 / design_suggest / kb_query，
但**沒有任何一行把「凍結的 netlist」列為 C03 的交付終點**；
架構文件裡 C03 的終點是**兩份 report JSON**
（`prd_bom_crosscheck.report.json` + `check_c03.report.json`，`:100` `GUIDE.md:472-476`）。

**判決：peer 的顛倒是 bodesign 教的。** peer 完全照著 GUIDE 做了——
交一份合併的、圖都在 `img/`、檔名帶 `C03_` 前綴的 docx，
把 build 產物留在 `02_build/` 不進版控。**它是模範生。**

**新增根因 G（C03 交付物定義文件導向）**，並且它與根因 A 是**同一件事的兩面**：

- 根因 A：C03 沒有電氣真值的錨點（vault 空、datasheet 不接）
- 根因 G：C03 的交付物定義裡**電氣真值不是交付物**——交付物是 docx

有 G 才會有 A。一個把「一份好看的說明書」定義為終點的階段，
**不會**長出 datasheet→vault→元件值的必經步驟，因為那條路徑對終點沒有貢獻。
`GUIDE.md:185-186` 那句「Without them the engine can only confirm the design
agrees with itself」寫得完全正確，然後被 `:399-435` 的 37 行 docx 細則
**在同一份文件裡實質推翻**——不是靠論證，是靠篇幅與 MANDATORY 標記的分佈。

這也回答了使用者的原題「C03 交辦至今仍然做不出來」：
**做出來了，只是做出來的是 bodesign 定義的那個 C03。**
使用者要的是「設計 RC/RLC/LC/RL 並用工程標準格式繪製圖紙」，
bodesign 的 C03 定義是「產出一份合併的電路設計說明書 docx」。
peer 100% 達成了後者。**落差不在執行，在定義。**

### 10.7 附帶：ERC 報告消費 verb → **not-run（無此 verb）**

`peer-testimony Q4`：peer 的 13 份 ERC 報告從 51 降到 1，下降靠**關掉**
`lib_symbol_issues` 與 warnings；唯一剩下的 error
`U2 Pin3 GND–Pin33 AGND pin_to_pin` 未裁決。

bodesign 側：**沒有任何 verb 消費 ERC 報告。**

- `grep '"name": "bodesign_[a-z_]*erc' services/mcp/server.py` **rc=1（零命中）**
- 控制組 `'"name": "bodesign_[a-z_]*check'` 命中 5 個（`si_check` / `prd_bom_crosscheck` /
  `check_c03` / `vault_spec_check` / `analyzer_selfcheck`），證明 pattern 形狀有效
- 全檔 57 個註冊工具中，`erc` 只出現在**描述文字**裡（`:1138` `:1899` `:1918-1919` `:1926-1927`），
  即 ERC 是被**提及**的概念，不是被**讀取**的資料

`compose_schematic` 內部會跑 kicad-cli 的 ERC（`GUIDE.md:141-143` 的 `validate=true`），
但那是**產出時**的自檢，回傳一個 validation block；
**沒有任何 verb 吃一份既有的 ERC 報告並對它的設定表態**。
於是「51 個 violation」與「1 個 violation，因為關掉了 46 條規則」
在 bodesign 這一側**無法分辨**——它從來沒看過那份報告。

這是 `code-thinker` §8 的教科書案例，且缺陷在**缺席**而非錯誤：
沒有探針，就沒有假綠燈，但也沒有任何東西阻止一個消費端用調設定的方式
把數字降到 1 然後宣告收斂。

**標記 not-run**：本輪未量「ERC 設定被關掉後 kicad-cli 是否仍在某處被 bodesign 讀取」——
只量了 MCP verb 層。若 `skills/bodesign/engines/kicad/scripts/analyze_schematic.py`
有讀 ERC 報告，本節的結論在 skill 管線那一側可能不成立；**本輪未查那條路徑**。

### 10.8 六點對根因表的淨效果

| 證詞點 | 對 v1 根因的效果 | 新的精確表述 |
|---|---|---|
| 1 vault 空表 | **證實 A、加強 B** | 不只「沒強制錨定」——datasheet 有兩套互不相識的儲存，補 stage→verb 表不會讓 `spec_values` 長出資料 |
| 2 宣告即豁免 | **證實 C** | 給出普查：`kicad_emit.py:18` 的宣告在修復前後**分別是真的且無執行力／假的**，從未更新 |
| 3 fidelity 綁死 | **證實 D** | `compare_partitions:380` 已是要的純函式；NC_WIRED 概念在 gate 中零命中；parsed-zero 走 `:220` 的 `continue` 且 `ok` 不分辨 |
| 4 封裝 | **修正 F 的方向** | 不是缺表（表在 `GUIDE.md:454-490`），是投影缺執行體。`gate.py:829-860` 的揭露設計是對的 |
| 5 check_c03 | **修正派工單的二分法** | 兩處都註冊、guide 也有帶——peer 的「不知道」是 §10.4 的下游：「不存在」與「拿不到」共用輸出 |
| 6 交付物定義 | **新增根因 G** | 4 個 MANDATORY 有 2 個管文件樣子；docx 那列是交付物表唯一加粗；netlist 無 MANDATORY、無版控要求。**peer 是模範生** |
| 附帶 ERC | 新增觀察 | 零 verb 消費 ERC 報告（控制組命中 5）；關規則降 violation 在 bodesign 側不可見 |

**根因 G 進入上游序列**，v1 §4 的鏈條因此要改寫為：

```
G（C03 交付物定義 = docx）
  └→ A（電氣真值無錨點：既然終點是文件，datasheet 路徑對終點無貢獻）
       └→ B（design_suggest 孤兒：設計建議層對「產出 docx」無用，所以沒人接線）
            └→ C/D/E（畫圖與驗證層的 38 張 BR：在為一份說明書裡的插圖修幾何）
  └→ F（投影缺執行體：即使有人想走 A/B，verb 也拿不到執行體）
```

v1 §0 的結論「三個月修的是錯的那一段」**成立且要往上再推一層**：
不只修錯了層，**是連目標都定義成了另一件事**。
38 張畫圖層 BR 每一張都是**為了讓那份 docx 裡的插圖好看一點**——
就 bodesign 對 C03 的定義而言，那些修復**方向完全正確**。

### 10.9 round 2 的未量邊界（追加，不取代 §8）

§8 的 14 條全部仍成立。本輪新增：

1. **peer 側零量測**——§10 的所有 peer 事實均為證詞引用，未讀 peer repo 任何檔案（依派工單）。
   `mk_sch2.py:10-32`、`verify_net.py:93-94`、`design.py` 的 27 nets 等行號**未經我驗證**。
2. **§10.7 只量 MCP verb 層**——未查 `skills/bodesign/engines/kicad/scripts/analyze_schematic.py`
   是否讀 ERC 報告。若它讀，結論在 skill 管線那側可能不成立。
3. **§10.2 的普查不完整**——只 grep 了三個檔案的固定關鍵字集
   （`not supported|unsupported|only single|future work|silently|skipped|assumes`）。
   一個用其他措辭寫的「宣告即豁免」不會被這支探針抓到。31 個裸 `continue`
   **未逐一讀**，所以「每一個都沒有出口欄位承接」是**從抽樣推論**，不是普查。
4. **§10.3(c) 的兩態表是靜態推論，未執行**——未真的造一個 kicad-cli 失敗的情境跑 fidelity。
   推論鏈（`:220 continue` → `parent` 空 → `c_nodes` 空 → `moved` 空 → `only_b` 依 spec 而定）
   逐行讀過，但**沒有 mutation proof**。這正是 `AGENTS.md §6.3` 警告的位置：
   若要驗，必須先清 `__pycache__`。
5. **§10.6 的 MANDATORY 計數是 GUIDE.md 單檔**——未查 `SKILL.md` / `doctrine.md` /
   `references/` 是否另有 C03 交付物定義與此矛盾。`specs/architecture.md` 只 grep 了 `C03`
   命中的 12 行，**未通讀**。
6. **§10.4 的「published skill 不帶 packages/」只量了當下狀態**——未查
   `opencode skill status bodesign` 回報 current/stale/drifted 哪一格，
   也未查投影機制是**刻意**排除 `packages/` 還是**漏了**。這決定修法是改投影清單還是改契約。
7. **根因 G 的因果方向未做反事實檢驗**——我論證「G 導致 A」，
   但「A 與 G 同為第三個原因的結果」同樣相容於觀察到的證據。
   可證偽條件：若在 C03 定義不變的前提下把 vault 接上、而 datasheet 路徑仍無人走，
   則 G→A 成立；若接上後自然被使用，則 G 不是 A 的成因。**本輪未做。**
