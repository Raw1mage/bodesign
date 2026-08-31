# BR_20260802 — 保真閘無法回報斷路，且對任何偏離都硬編同一個病因

- **Status**: PARTIAL — 硬編病因（Fix proposal 第 2 點）已於 `cedc262` 修復；斷路診斷能力已具備。
  **scoped remainder：現有測試對修復點的 mutation 全數 survived**——修復存在但**未被測試釘住**，
  任何人把它改回來不會有任何東西變紅。見 §「落地與殘留」。**留頂層，不歸檔。**
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

對應 Fix proposal 第 2 點：`FidelityError` 不再硬編「collinear-wire fusion / label collision」，
改由 report 推導實際量到的機制。斷路（`only_candidate` / 節點消失）的診斷能力已在代碼具備。
伴隨測試：`tests/test_fidelity_instrument_reports_measured_mechanism.py`。

### 為什麼是 PARTIAL 而不是 FIXED

針對修復點做 mutation 測試，**全數 survived**：把 `cedc262` 引入的訊息推導邏輯變異掉，
現有測試套件**沒有任何一個轉紅**。這代表：

```
修復存在      ✅  (cedc262 在 HEAD，可 `git show` 驗證)
修復行為正確  ✅  (訊息由 report 推導)
修復被釘住    ✗  ← 沒有測試在看這一格
```

本 BR 自己的 Validation plan 就寫了「Mutation proof（必要，非加分）」——那一格目前是紅的。
**一張「修好了但沒有任何東西防它回退」的 BR 不得標 FIXED**：歸檔會把這個缺口一併帶走，
而下一個把訊息改回硬編的人會看到全綠。

### 後續（remainder）

- 補一組釘住 `cedc262` 行為的測試：餵三種偏離（節點消失 / 跨 class 熔接 / 座標偏移），
  斷言印出的病因名稱各不相同且正確，且 revert 修復後該測試必須轉紅（mutation proof）。
- Fix proposal 第 1 點（`sch_union_classes` 保留單節點 net）是否已完整落地：本輪**未獨立量測**，
  不得因 `cedc262` 存在而推定。
