# BR_20261004 — composer.py still duplicates `decide_route_policy`; `capacity_plan.py` is not actually the sole authority

- **Family**: `packages/eda-bridge/`／dual-implementation (same class as the historical "170 vs 124" discrepancy)
- **Status**: closed (2026-10-05 by ses_04db7a1c5ffelvbxyLP1p6xlRH)
- **Closed**: 2026-10-05 by ses_04db7a1c5ffelvbxyLP1p6xlRH (Resolution: composer.py:2272-2287 delegates to capacity_plan.decide_route_policy, eliminating duplicate pairwise counting)
- **Filed by**: `ses_f884168d5ffeCB4omppZFOFXzk`（[OWNS multi-sheet-schematics]，`plans/infra_dockerlab-migration-and-structural-review` Phase 2 lint-qa review）
- **Repo**: `/home/pkcs12/projects/bodesign`
- **Severity**: 中。今天兩份實作算出同一個答案，不影響現有行為；風險在**未來任一份被改動而另一份沒跟上**，會重現本線已經診斷過一次的「兩個都帶控制組的答案」。

## 1. 斷言原文在哪裡

`packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:1270-1274`：

```
# M7-3.3 (DD-9 方案 B): this decision's SINGLE SOURCE OF TRUTH is now the L2.5
# capacity_plan layer. kicad_emit.py's own call site below is a transitional
# delegation ...
```

這句宣告 `capacity_plan.decide_route_policy` 是「唯一權威」。`kicad_emit.py:1274` 確實
lazy-import 並呼叫它——**這一側是真的修好的**。

## 2. 今天實際發生什麣

`composer.py:2195-2231`（`compose_schematic` 內，`style == "draftsman" and not
explicit_conn` 分支下）**沒有呼叫** `capacity_plan.decide_route_policy`，而是獨立
重寫了一份結構相同的演算法：

```python
# composer.py:2208-2231
_pin_ct: dict[str, int] = {}
for _c in parsed:
    try:
        _def, _pins = load_symbol(_c["symbol"], symbol_dirs)
        _pin_ct[_c["ref"]] = len(_pins)
    except Exception:
        _pin_ct[_c["ref"]] = 0
def _is_ic(ref: str) -> bool:
    return _pin_ct.get(ref, 0) > 2
_pair_sig: dict[frozenset, list[str]] = {}
for net in nets:
    ic_refs = sorted({r for (r, _p) in net.nodes if _is_ic(r)})
    if len(ic_refs) < 2:
        continue
    for _i in range(len(ic_refs)):
        for _j in range(_i + 1, len(ic_refs)):
            _pair_sig.setdefault(frozenset((ic_refs[_i], ic_refs[_j])), []).append(net.name)
_crossic_label = {
    n for names in _pair_sig.values() if len(names) >= 2 for n in names
}
if _crossic_label:
    label_nets |= _crossic_label
```

對照 `capacity_plan.py:58-86` 的 `decide_route_policy`：

```python
def decide_route_policy(nets, pin_count):
    pair_signals: dict[frozenset, list[str]] = {}
    for net in nets:
        ics = sorted({r for (r, _p) in net.nodes if pin_count.get(r, 0) > _IC_PIN_THRESHOLD})
        if len(ics) < 2:
            continue
        for i in range(len(ics)):
            for j in range(i + 1, len(ics)):
                pair_signals.setdefault(frozenset((ics[i], ics[j])), []).append(net.name)
    label_nets = {name for names in pair_signals.values() if len(names) >= 2 for name in names}
    return {net.name: ("label" if net.name in label_nets else "wire") for net in nets}
```

**兩段邏輯逐步對應**：`_pin_ct`/`pin_count`（pin 數字典）、`_is_ic`/`pin_count.get(r,0) >
_IC_PIN_THRESHOLD`（IC 判定，threshold 相同 = 2）、`_pair_sig`/`pair_signals`（frozenset
配對累積）、`_crossic_label`/`label_nets`（≥2 訊號門檻）。composer.py 的版本是
`capacity_plan.py` 的手寫複製，**不是呼叫它**。

## 3. 這是哪一類缺陷

這正是本 repo 已經診斷過一次的 bug class（`make-bodesign-draw-a-real-schematic` round
30 的「170 vs 124」）：**同一條政策在樹裡有兩份獨立實作**，而
`kicad_emit.py:1270-1273` 的「SINGLE SOURCE OF TRUTH」註解本身就是誘因——它讓讀者
以為只有一處需要關注。差別是：round 30 那次是 `kicad_emit.py` vs `composer.py`；
今天是 `composer.py` vs `capacity_plan.py`——**修了一邊、另一邊原地沒動，缺陷換了位置
繼續存在**。

該線已蒸進中央 KB 的判準直接適用：

> 要「關掉某條規則」之前，先數這條規則在樹裡有幾個實作點。
> pass-through 控制組只證明 wrapper 沒污染讀數，證明不了 wrapper 涵蓋了全部作用點。

（`tooling-failmodes.failure-mode.disable-a-rule-without-counting-its-implementations`）

## 4. 今天兩份實作算出同一個答案，不是這張 BR 的免責理由

**兩個獨立實作今天逐行對應，不代表它們永遠會一致。** 任一側未來被修改（例如調整
IC pin 數門檻、改變 frozenset 配對邏輯、修正 bug），若另一側沒跟上，composer.py 的
draftsman 路徑與 kicad_emit.py 透過 capacity_plan 的路徑會對同一塊板子算出不同的
label 決策——這正是 round 30 的「170 vs 124」當時發生的事。

## 5. 建議（不在本 BR 執行，留給修復輪）

`composer.py:2208-2231` 應改為：

```python
from .capacity_plan import decide_route_policy as _decide_policy
_route_policy = _decide_policy(nets, _pin_ct)
_crossic_label = {n for n, p in _route_policy.items() if p == "label"}
if _crossic_label:
    label_nets |= _crossic_label
```

刪除手寫的 `_is_ic`/`_pair_sig` 重複邏輯，改成單純消費 `capacity_plan` 的輸出。

## 6. 未量測

- 是否有既有測試同時走過 composer.py 的 inline 分支與 capacity_plan 的呼叫路徑並
  比對過兩者輸出——本次 review 沒有讀測試檔，留給修復輪第一件事查。
- `_is_active_ic`（composer.py:2119）與 `_is_ic`（composer.py:2215）是否為可合併的
  同一謂詞——未逐行比對。

## 7. 參考

- `docs/research/report_20261004_c03_lint_qa_structural_review.md` §9（本 BR 的完整
  上下文與發現過程）
- `plans/eda-bridge_draftsman-series-divider-wireable/errors.md` ⑤（round 30 的原始
  診斷：170 vs 124）
