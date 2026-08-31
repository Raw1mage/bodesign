# BR_20260802 — 保真閘無法回報斷路，且對任何偏離都硬編同一個病因

- **Status**: FIXED — Fix proposal 三點全數落地且**逐點以 mutation proof 釘住**。
  經三輪實測（round 1 / 2 / 3皆 2026-08-31）：**M1~M8 8/8 KILLED、N4 / N5b / P4 / P7 皆 KILLED、
  19 個測項全綠**。round 2 與 round 3 各拆穿一個「自己剛造的假防線」，見 §第三輪。
  修復 commit `cedc262`；測試補強見 §「落地與殘留」§第二輪。**已無 remainder。**
- **Closed**: 2026-09-01 by `ses_fa72d47feffeTZNnlOw08pgCgS`（BRNS handler，closeout_three_debts）—
  依據：修復 commit `cedc262`（`git merge-base --is-ancestor cedc262 HEAD` rc=0）＋ 測試補強 `aa016db`；
  `tests.test_fidelity_instrument_reports_measured_mechanism` 在 HEAD `Ran 19 tests … OK`
  （先清 `__pycache__`；負控制組 `tests.test_NON_EXISTENT_MODULE_CONTROL` → `FAILED (errors=1)`）。
  本張自陳「已無 remainder」，M9~M12 為明確標示的範圍外，非未結殘留。
- **Scheduled**: 已授權 `ses_0c87bab06fferQ0umBs2Nybb5U` 執行（單張授權，非 family）
- **Owner**: `(default)`（值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH`）
- **Family**: `G13-harness-disclosure` × `schematic-engine`（驗收儀器）
- **Severity**: **high** — 這不是「閘漏抓」，是**閘抓到了卻指認錯病因**，而兩個獨立 agent 都被它導向錯誤假設
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/fidelity.py`
- **Filed at**: 2026-08-02
- **時區**: Asia/Taipei (UTC+08:00)

## 一句話

`sch_union_classes` 的 union-find **結構上不可能**把單節點 net 放進宇宙，所以斷路缺陷永遠不會以
`only_candidate` 呈現；而 `FidelityError` 的訊息**硬編**「collinear-wire fusion / label collision」
這個病因，對任何一種偏離都印同一句。**儀器判定出的病症與它宣告的病因無關。**

## Symptom（實測）

`tests.test_fidelity_gate` 紅燈時的報告：

```
baseline  nets=9  nodes=24
candidate nets=6  nodes=18
ONLY_BASELINE missing: J1.1 J1.2 J1.5 R1.1 R2.1 R5.1
only_candidate=0   moved=0
FidelityError: schematic fidelity gate FAILED — net partition diverged
               from spec (collinear-wire fusion / label collision)
```

**實際的缺陷是斷路，不是熔接。** raw netlist 的節點宇宙是 24 個（與 baseline 相同），
沒有任何兩條 net 被熔在一起：

```
N1  ['J1.1']                    ← 只剩連接器側
N2  ['J1.2']
N5  ['J1.5']
N3  ['J1.3','R3.1']             ← 正常對照
unconnected-(R1-Pad1)  ['R1.1'] ← 電阻側被踢成孤立節點
unconnected-(R2-Pad1)  ['R2.1']
unconnected-(R5-Pad1)  ['R5.1']
```

一條 net 被剪成兩個各自孤立的單節點 net。

## RCA

### 缺陷 1 — `only_candidate` 結構上恆為 0（`fidelity.py:104-140`）

`sch_union_classes` 的 union 迴圈：

```python
for cls in parse_net_file(out):
    nodes = list(cls)
    for n in nodes[1:]:        # ← 單節點 net 的 nodes[1:] 是空的
        union(nodes[0], n)
```

`parent` dict 只在 `union()` 被呼叫時透過 `find()` 的 `setdefault` 建立條目。
**單節點 net 的唯一節點永遠不進 `parent`**，於是不出現在回傳的 classes 裡。

隔離環境重現（值星官獨立跑，非轉述）：

```
nets = [{J1.3,R3.1}, {R1.1}, {J1.1}]
→ parent universe = ['J1.3','R3.1']
  R1.1 in universe?  False
  J1.3 in universe?  True     ← 控制組：2 節點 net 成員必須在
```

量測對照：

```
parse_net_file      universe = 24 nodes   R1.1 在裡面（class size 1）
sch_union_classes   universe = 18 nodes   R1.1 不在
DROPPED: ['J1.1','J1.2','J1.5','R1.1','R2.1','R5.1']
```

斷路節點不是以「跑到別的 class」被偵測，而是以「從宇宙裡消失」被偵測，
再由 `compare_partitions` 的 `only_baseline` 撿回來（`fidelity.py:195-202`）。

**這條路徑目前有效**（紅燈確實亮了），但它讓 `only_candidate` 恆為 0——
而 `only_candidate=0` 讀起來像「沒有節點跑錯 net」這個**有資訊的陰性結果**，
實際上它是**沒有鑑別力的常數**。

> 注意 `singleton_only_baseline`（`fidelity.py:38, 202`）刻意忽略「兩側都孤立」的 pin，
> 那個設計是對的且與本缺陷無關——本案的節點在 baseline 側**有** peer。

### 缺陷 2 — 錯誤訊息硬編病因（`fidelity.py:63-65`）

```python
super().__init__("schematic fidelity gate FAILED — net partition diverged "
                 "from spec (collinear-wire fusion / label collision):\n"
                 + report.summary())
```

括號裡那句是**字面常數**，不由 report 推導。無論實際判定出的是斷路、熔接、還是座標偏移，
印出來的都是「collinear-wire fusion / label collision」。

## 為什麼這一張比它修的紅燈更重要

**兩個獨立的 agent（peer handler 與值星官），各自取證，都被這兩格導向「熔接」假設。**

值星官在授權書裡明確要求「把 `only_candidate=0 / moved=0` 當**起點假設**驗證，不要當前提」——
那條要求救了這次。**但下一個人不會有那句話。** 他會看到 `only_candidate=0` 加上訊息裡的
「collinear-wire fusion」，然後去查一個不存在的病。

G13 判準：**那一格的資訊，系統當下有沒有？**

**有。** `parse_net_file` 的宇宙是 24 個節點，`sch_union_classes` 出來是 18 個——
**差集就在函式內部**。它知道自己丟了 6 個節點，它不說。而錯誤訊息不但不說，
還主動宣告了一個它沒有驗證過的病因。

> 一個會說謊的驗收儀器比沒有驗收儀器更糟，因為它讓人停止懷疑。

## Fix proposal（已授權執行，範圍如下）

1. **`sch_union_classes` 保留單節點 net**，讓 `only_candidate` 恢復鑑別力。
   **必須帶 mutation proof**：改回丟棄，斷言「斷路節點被偵測為 `only_candidate`」的測試轉紅。
2. **`FidelityError` 訊息改為由 report 推導**，不得硬編病因。至少要能區分：
   節點消失（斷路）/ 節點跨 class（熔接）/ 節點座標偏移。
   **判準：訊息裡出現的病因名稱，必須是這次真的判定出來的那個。**
3. **一個測試釘住這件事**：餵一份已知斷路的 netlist，斷言 report 指認「斷路」而非「熔接」。

**排序理由**：這一層優先於底層 geometry 的止血修法。修好儀器之後，
epsilon 那類修法才有辦法被正確驗收。**先修錶，再修引擎。**

## Validation plan

- **控制組先行**：確認新的斷路偵測**對真斷路會響**，且**對正常 netlist 不響**。
  沒有這一格，偵測器可能只是常回 True。
- **Mutation proof**（必要，非加分）：把保留單節點 net 的改動 revert，對應測試必須轉紅。
- 訊息推導的測試：三種偏離各餵一份，斷言印出的病因名稱各不相同且正確。

## Explicitly NOT bugs

- **`singleton_only_baseline` 忽略兩側皆孤立的 pin** — 刻意設計且正確（`fidelity.py:199-202`），
  與本缺陷無關。本案節點在 baseline 側有 peer。
- **`_drop_power_flags`** — 未涉入。
- **紅燈本身** — 閘確實亮了，這張修的是「亮的時候說了什麼」。

## Cross-ref

- 觸發本張的紅燈：`BR_20260802_fidelity_gate_is_red_after_restore_and_never_ran_at_head.md`
  （根因為浮點等值比較落在刀鋒上；層次 3 的契約衝突已升使用者裁決）
- 同族形狀：`issues/BR_20260802_event_record_returns_ok_true_while_storing_shell_injected_content.md`
  （工具握有完整性證據卻回 `ok:true`）
- `AGENTS.md §6.1` 的 pathspec 陷阱 / 快照歧義 / `git log -S` 回空

---

## 落地與殘留（2026-08-31）

### 修復點

```
cedc262d32443afff79a8c4acba9be12d24639a7  2026-08-02
fix(fidelity): report the mechanism it measured, stop asserting one
```

`cedc262` 中**本輪選取**的 8 個可變異修復點。

**這不是窮舉**（措辭修正於 round 2）。選取準則：取 BR §Fix proposal 第 1/2 點**直接點名**的
兩條邏輯（seeding、cause 推導），加上它們在本案實測情境（斷路 / 熔接）下會被執行到的分支。
**沒有被本案情境踏到的分支不在選取內**，它們列於 §誠實邊界的「M9~M12」。
`cedc262` 的可變異點**至少 12 個**，不是 8 個。

| # | 修復點 | 位置 | 對應 Fix proposal |
| --- | --- | --- | --- |
| 1 | union-find 對每個節點先 `find(n)` seed | `fidelity.py:231-232` | 第 1 點 |
| 2 | `FidelityError` 的 cause 由 `diagnosis()` 推導 | `fidelity.py:149-150` | 第 2 點 |
| 3 | `diagnosis()` 的 `disconnected` 分支（open circuit） | `fidelity.py:72-74` | 第 2/3 點 |
| 4 | `diagnosis()` 的 `fused` 分支（fusion / short） | `fidelity.py:75-85` | 第 2/3 點 |
| 5 | `lost`/`gained` 的方向分類（disconnected vs fused） | `fidelity.py:428-435` | 第 2/3 點 |
| 6 | `summary()` 的 `MEASURED MECHANISM` 區塊 | `fidelity.py:115-123` | 第 2 點（reader-facing 面） |
| 7 | candidate 側 singleton 豁免 `only_c = ... len>1` | `fidelity.py:412-413` | 第 1 點的對稱面 |
| 8 | `diagnosis()` 的 `only_candidate` 分支 | `fidelity.py:93-95` | 第 2 點 |

### 第一輪 mutation proof（2026-08-31 上午，本輪實測，非轉述）

對 8 個修復點各做一次變異（就地 mutate → 每次跑前 `find . -name __pycache__ -prune -exec rm -rf {} +`
→ 跑 `tests.test_fidelity_instrument_reports_measured_mechanism` 與 `tests.test_fidelity_gate`
→ 逐 byte 還原並 `cmp`）。每個 mutant **落地本身帶控制組**：變異前字串的出現次數必須 `1→0`，
同時一個必然存在的對照字串（`def compare_partitions(`）必須仍為 1——證明 0 是「真的被改掉」
而非「pattern 寫錯」。

```
M1 drop union-find seeding             rc=1  KILLED
M2 hardcode cause                      rc=1  KILLED
M3 diagnosis drops open circuit        rc=1  KILLED
M4 diagnosis drops fusion              rc=1  KILLED
M5 swap disconnected/fused             rc=1  KILLED
M6 summary drops MECHANISM block       rc=0  SURVIVED   ← 缺口
M7 revert singleton_only_candidate     rc=0  SURVIVED   ← 缺口
M8 diagnosis drops only_candidate      rc=0  SURVIVED   ← 缺口
```

**BR 前一版自述「全數 survived」已過時**：5/8 其實已被釘住。真正的缺口是 3 個，且都不是
「訊息推導」本身，而是它的三個外圍面——**reader-facing 的 `summary()`、對稱的 candidate 側豁免、
以及 `only_candidate` 這條診斷分支**。

> 這三個共用同一個形狀：**機制被推導出來了，但讀者看不到**。
> M6 讓 `diagnosis()` 仍正確卻不印；M8 讓一種偏離被判定卻不被命名；M7 讓一個豁免消失
> 而報告不會說。三者都回到 BR 開頭那句「儀器判定出的病症與它宣告的病因無關」。

### 第二輪（補測試後，同一組 mutant 重跑）

新增 9 個測項（`tests/test_fidelity_instrument_reports_measured_mechanism.py`）。
**測項數演進：8 → 17（round 1）→ 19（round 2）→ 19（round 3，只重寫不新增）。**
下表是 round 1 那 9 個；round 2 / 3 的變動見 §第三輪。

| 新測項 | 殺哪個 mutant | 正向控制組 | 反向控制組 |
| --- | --- | --- | --- |
| `test_failing_summary_prints_the_mechanism_it_measured` | M6, M3, M5 | 斷路輸入必印 `MEASURED MECHANISM` + `open circuit` | `test_passing_summary_names_no_mechanism`：通過的板子**不得**出現該區塊 |
| `test_passing_summary_names_no_mechanism` | （控制組本身） | 通過必含 `FIDELITY PASS` | 若無條件印，上一項即成 vacuous |
| `test_every_diagnosis_line_reaches_the_summary` | M6, M3 | `diagnosis()` 每一行必**逐字**出現在 `summary()` | 先斷言 `dx` 非空（precondition），空表則此測項本身無判別力 |
| `test_raised_message_body_contains_the_summary_block` | M6 | 拋出的訊息 body 必含該區塊 | 與上一項綁定 `summary()` 兩側 |
| `test_isolated_extra_pin_is_exempt_and_stays_visible` | M7 | 孤立額外 pin → `only_candidate==[]` 且 `singleton_only_candidate==['J1.3']` | `test_connected_extra_pins_are_not_exempt` |
| `test_connected_extra_pins_are_not_exempt` | M7 | 相連額外 pin → `only_candidate==['X1.1','X1.2']`、`ok` 為假 | 證明豁免不是「對所有 extra 都放行」 |
| `test_the_two_inputs_do_not_produce_the_same_verdict` | M7 | 兩種形狀的 `ok` 必不相等 | 防止上兩項同時對常數為真 |
| `test_extra_connected_nodes_are_named_absent_from_spec` | M8 | `only_candidate` 非空時診斷必含 `absent from spec` | 並斷言**不**含 `open circuit`（沒有節點失去 peer） |
| `test_a_report_with_no_extra_nodes_names_nothing` | （M8 的反向控制組） | 忠實板子 `only_candidate==[]` | 診斷**不得**含 `absent from spec` |

無任何 `skipUnless`（skip 與 pass 在輸出上無法區分）。

同一支 harness、同一組 mutant 重跑：

```
M1 KILLED   M2 KILLED   M3 KILLED   M4 KILLED
M5 KILLED   M6 KILLED   M7 KILLED   M8 KILLED     8/8
```

M3 與 M5 的紅面同時擴大（各多兩個/一個斷言轉紅），且**紅在不同斷言**——紅的位置本身帶診斷資訊。

### Fix proposal 逐點結案

- **第 1 點**（`sch_union_classes` 保留單節點 net）：**已落地且已釘住**。前一版寫「本輪未獨立量測，
  不得推定」——本輪量了：M1 把 seeding 拿掉，`test_open_circuit_pin_is_not_dropped_from_the_universe`
  與 `test_universe_matches_the_raw_netlist_exactly` 轉紅。
- **第 2 點**（訊息由 report 推導）：**已落地且已釘住**（M2/M3/M4/M5/M6/M8）。
- **第 3 點**（餵已知斷路 netlist，斷言指認斷路而非熔接）：**已落地**
  （`test_open_circuit_is_named_open_circuit` 同時斷言 `assertNotIn("fusion")`）。

### 誠實邊界

#### 已量測且 SURVIVED 的**未涵蓋面**（M9~M12，VANS `ses_fa7702282` 於 round 2 獨立量得）

上表的 8 個是選取，不是窮舉。同一個 commit 至少還有四個可變異點，**四個全部 SURVIVED**：

| # | 未列入的修復點 | 位置 | mutation 形式 | 結果 |
| --- | --- | --- | --- | --- |
| M9 | `diagnosis()` 的 `regrouped` 分支 | `fidelity.py:86-88` | `if False and self.regrouped:` | **SURVIVED** |
| M10 | `diagnosis()` 的 `only_baseline` 分支 | `fidelity.py:89-92` | `if False and self.only_baseline:` | **SURVIVED** |
| M11 | `summary()` 的 else「unclassified」分支 | `fidelity.py:120-123` | 刪除該 append | **SURVIVED** |
| M12 | `lost and gained → regrouped` 分類分支 | `fidelity.py:430-431` | `if False and lost and gained:` | **SURVIVED** |

**M11 尤其要注意**：那正是 §Fix proposal 第 2 點「說 mechanism unclassified 而非硬編病因」的**本體**。
把它拿掉，一個無法分類的偏離就回到什麼都不說——而沒有任何東西會紅。

**這四個本輪未補殺，是明確的範圍外，不是已處理。** 待另一個工作包。

> 為什麼這一格必須寫在帳上：前一版把選取寫成窮舉（「`git show` 逐項列出的……8 個」），
> 下一個讀者會以為 `cedc262` 已被完整釘住。**而這正是本 BR 在治的病——儀器讓人停止懷疑。**
> 一張治「假確信」的 BR 自己製造假確信，不能結案。

#### 其他

- 量了：上述 8 個修復點的 mutation kill/survive、每個 mutant 的落地控制組、19 個測項全綠、
  `fidelity.py` 還原逐 byte 一致（`cmp` rc=0、sha256 相同、`git status` 該檔為空）。
- **沒**量：`tests/test_fidelity_gate.py` 全程 rc=0，本輪**沒有任何 mutant 使它轉紅**——
  它跑的是 kicad-cli 端到端路徑，對本 BR 的八個修復點**沒有判別力**。這不是缺陷，
  但也不得被讀成「gate 測試在保護這些修復點」。
- **沒**量：Fix proposal 第 3 點提到的第三種偏離「座標偏移」未單獨餵入——現行分類器
  只有 `disconnected`/`fused`/`regrouped` 三格，座標偏移在本儀器中不是獨立機制，
  會落在其中一格。若日後要它成為獨立診斷，那是新的 scope。

---

## 第三輪（round 2 + round 3，2026-08-31）

前一節的帳面停在 round 1。這一節補齊其後兩輪——**兩輪各拆穿了一個「修正動作自己造出來的假防線」**。

### round 2：兩個測項宣稱守的事，它們守不住

VANS `ses_fa7702282` 獨立量得，本 handler 逐項重現成立（未只信轉述）：

| 測項 | 它宣稱守什麼 | 實測守不住什麼 | 探針 |
| --- | --- | --- | --- |
| `test_error_message_differs_between_the_two_mechanisms` | 註解寫「一個同時含兩病因詞的硬編常數會被抓到」 | **抓不到**。訊息 body 帶 `summary()`，兩份 report 的 summary 本就不同，`assertNotEqual` 靠 summary 差異即滿足，**完全沒測到 cause 是否被推導** | `N4`：cause 換成 `"open circuit / net fusion / short (hardcoded)"` → **SURVIVED** |
| `test_multi_node_net_still_merges` | docstring 寫「seeding 不得阻止 net 合併」的反向控制組 | **測的是 parser 不是 union**。它呼叫 `_parse()`（即 `parse_net_file`），從未碰 `sch_union_classes` | `N5b`：`for n in nodes[1:]: pass` → **SURVIVED**，17 項全綠 |

兩者都是本 BR 開頭那句話的同一個形狀——**儀器判定出的病症與它宣告的病因無關**——只是這次長在測試自己身上。

**修法與重構**：

1. **`_cause()` scoping**（新增 staticmethod）：`str(err).split(":\n", 1)[0]`，只取 `FidelityError` 真正**推導**的 cause 段。`test_error_message_differs_between_the_two_mechanisms` 改比 cause 段，並加三層——precondition（切片須含 `(`）、cause 段不等、各自只准含自身病因詞（單靠不等式，一個同時含兩詞的常數在夠長輸入上仍可能滿足）。N4 由 SURVIVED 轉 **KILLED @257**。
2. **`_classes()` / `_universe()` 拆分**：`_classes()` 回傳 partition，`_universe()` 才扁平化。`test_multi_node_net_still_merges` 改讀 `_classes()`。新增 `test_merging_is_what_makes_the_two_fixtures_differ` 釘住 class 數（忠實=2、斷路=3）作為控制組的控制組。N5b 轉 **KILLED @172, @180**。

測項數 17 → 19。

### 機制：**扁平化殺不掉 N5b**——union 只在 class 結構裡可觀測

這一格是本輪最值錢的發現，獨立成段記載。

改 `test_multi_node_net_still_merges` 時的直覺修法是「改用 `_universe()` 讀 `sch_union_classes` 的輸出」——**那樣仍然殺不掉 N5b**。原因：

> `cedc262` 的 seeding fix 已經讓**每個節點**都進入 `parent` dict。
> 因此當 union 被拿掉時，**扁平化後的節點宇宙完全不變**——少的不是節點，是節點之間的**歸屬關係**。
> union 的效果只存在於「哪些節點落在同一個 class」這個**結構**裡；
> 一旦 `set().union(*classes)` 把 class 邊界壓平，這個資訊就被銷毀了。

**推論（界線已收窄，見下方 M1 反例）**：扁平集合只能證明**成員資格**（seeding 的效果），
不能證明**節點歸屬**（union 的效果）。**任何以扁平集合斷言「節點歸屬」的測試，判別力恆為零**
——而它讀起來與正確版本一模一樣。

**不可過度推廣**：這**不是**說「扁平斷言一律無判別力」。反例是實測的——`M1`（拿掉 seeding）之下，
`test_open_circuit_pin_is_not_dropped_from_the_universe`（`:144`）與
`test_universe_matches_the_raw_netlist_exactly`（`:153`）**都會紅**。
這兩個正是以扁平集合斷言、且**判別力非零**的測項，因為它們問的是**成員資格**
（「這個節點在不在宇宙裡」），而那正是 seeding 負責的事。
界線落在**問題**上而非工具上：扁平集合對成員資格有牙，對節點歸屬沒有。

三格控制組背書（VANS 獨立餵入）：

| | 設定 | 結果 | 它排除了什麼 |
| --- | --- | --- | --- |
| Q2 | 扁平斷言 + N5b | **GREEN** | 這就是缺陷本體 |
| Q3 | 扁平斷言 + 無 mutation | **GREEN** | 排除「扁平測試根本跑不起來」 |
| Q4 | class 斷言 + N5b | **RED** | 排除「N5b 這個 mutant 無效」 |

Q3 與 Q4 缺任一格，Q2 的 GREEN 都無法區分「測試沒判別力」與「探針壞了」——**缺席態與失敗態共用輸出**。

### round 3：修 FINDING-2 的動作，自己造了一個同形狀的假防線

`test_whole_message_comparison_is_not_what_pins_the_cause`（round 2 新增，用意是解釋「為何 `_cause()` 要 scoped」）**零判別力**：

- 第一段比較兩個**字面常數**（`same_cause + "summary A"` vs `+ "summary B"`），與被測程式碼無關。
- 第二段 `assertEqual(self._cause(err), str(err).split(":\n",1)[0])` —— `_cause()` 的 body 就是右式，**是 `f(x) == f(x)` 的展開，恆為真**。

實測：**12 個 mutant（M1~M8 + N4 + N5b + P4 + P7）無一使它轉紅（0/12）**。

> **它是 round 1 FINDING-2 的同一個形狀，長在修 FINDING-2 的動作裡。**
> 意圖（解釋為何要 scoping）是對的，但那是**註解該做的事，不是測項**。
> 目前形式在讀者心裡留下「這裡驗過了」。

**處置：選 ②（改成有牙的形式），不是刪除。** 理由：它要表達的性質**是真的、可測、且沒有別的測項在守**——cause 段由「機制名 + 計數」推導，**不含節點身分**，所以兩塊**節點集合完全不相交**的板子只要機制相同，就會產生**逐 byte 相同的 cause**，而 summary 不同。這正是「比整條訊息無法看見 cause」的根因。改寫後對真實儀器斷言：

```
board A: N1={J1.1,R1.1} 被剪斷        board B: A1={U1.1,U2.1} 被剪斷
  → cause 相同（assertEqual）
  → summary 不同（assertNotEqual）
  → 整體訊息不同（assertNotEqual）——而這個「不同」只來自 summary
```

並加 precondition 斷言兩者的 `disconnected` 各為 `['J1.1','R1.1']` / `['U1.1','U2.1']`，否則「cause 相同」是廢話而非資訊。

**反向 mutation 證明它有牙**：`P7` = `diagnosis()` 印節點清單而非計數
（`{len(self.disconnected)}` → `{sorted(self.disconnected)}`）。
P7 在改寫**前**通過整套 19 項（SURVIVED），改寫**後** → **KILLED @311**
（`"...['J1.1', 'R1.1']..." != "...['U1.1', 'U2.1']..."`）。
它同時被 M5 抓到（@308），故紅面 0/12 → **2/12**。

### round 3：`_cause()` 的分隔符契約會靜默失效（FINDING-4b）

`P4` = 只把 `FidelityError` 的 `":\n"` 換成 `" -- "`，其餘不動（一次合理的重構）：

| | PRISTINE | P4 |
| --- | --- | --- |
| slice 長度 | 141 | **282** |
| 切片含 summary？ | False | **True**（吞掉整個 summary body） |
| precondition「含 `(`」 | True | **True ← 仍通過，擋不住** |
| cause 段不等 | True | True ← **靠 summary 差異滿足**，正是 round 1 的機制 |

即 `split` 找不到分隔符時**靜默把整條訊息當成切片**，layer-2 無聲退回 round 1 狀態。
P4 單獨 SURVIVED；只有 P4+N4 疊加時才被 layer-3 抓到——**當時守住的是 layer-3，不是 docstring 宣稱的 layer-2。**

**處置：選 ①**（precondition 加 `assertNotIn("baseline nets=", cause)`，名指一個只有 `summary()` 會產生的字串）。
不選 ②（讓 `FidelityError` 暴露 `self.cause`），因為那會使 `fidelity.py` 產生實質變更，**超出本輪授權**。
① 是「缺席態與失敗態不得共用輸出」的直接應用：**過長的切片與正確的切片不得回報同一件事**。
P4 由 SURVIVED 轉 **KILLED @264**（`'baseline nets=' unexpectedly found in ...`）。

### round 3 mutation 總表

| mutant | round 2 結果 | round 3 結果 | 紅在 |
| --- | --- | --- | --- |
| M1~M8 | 8/8 KILLED | **8/8 KILLED**（未回歸） | 同前 |
| N4 | KILLED | **KILLED** | @268 |
| N5b | KILLED | **KILLED** | @172, @180 |
| P4（分隔符） | SURVIVED | **KILLED** | @264 |
| P7（印節點非計數） | SURVIVED | **KILLED** | @311 |
| M9~M12 | SURVIVED | **SURVIVED（仍為範圍外，未補殺）** | — |

測項數維持 **19**（round 3 只重寫既有兩處，未新增測項）。

### round 3 誠實邊界

- **量了**：P4 / P7 / M5 / N4 / N5b 的前後 rc 與紅行號、12 個 mutant 對該測項的紅面統計（0/12 → 2/12）、M1~M8 未回歸、19 項全綠、`fidelity.py` 三格零變更各配控制組。
- **沒**量：**M9~M12 仍未補殺，繼續是明確的範圍外**，非已處理。
- **沒**量：`test_fidelity_gate.py` 對本 BR 修復點仍**零判別力**（本輪 14 個 mutant 無一使它轉紅）。
- **沒**量：P7 之外，其他「診斷內容格式改變」的變異未窮舉；「至少 12 個可變異點」仍是下界，未證明恰為 12。
