# BR_20260901a — `_cause()` 依賴 `":\n"` 這個沒有任何東西保證的隱式分隔符契約

- **Status**: OPEN (MITIGATED — 大聲失敗，未消除)
**Severity**: LOW-MEDIUM (instrument coupling — 目前會紅，但紅的原因與根因隔了一層)
**Family**: instrument-discipline / implicit-contract-between-test-and-production-string-format
**Filed**: 2026-09-01 by ses_fa73bab76ffeM0Dhhz9pK0Xln2 (BRNS leaf handler，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`)
**Owning repo**: `~/projects/bodesign` (本地)
**Fix surface**: `packages/eda-bridge/bodesign_eda_bridge/fidelity.py:151-153`（`FidelityError.__init__`）
＋ `tests/test_fidelity_instrument_reports_measured_mechanism.py:226-235`（`_cause()`）

**Related**: `aa016db75e84599a6d0fd86393925fa84e8c4384`
*test(fidelity): give the instrument's own controls teeth (BR_20260802 r2+r3)*
——**時序因果**：本缺陷是該 commit 收案時**明確保留**的 scoped remainder（FINDING-4b 選項 ①）。
該 commit 加入的 `assertNotIn("baseline nets=", cause)`（`tests/…:264`）正是本 BR 所說的「緩解」，
而它同時**沒有**消除根因——測試仍在對一個字串格式做切片。
同族失敗形狀：中央 KB `tooling-failmodes.failure-mode.a-tautological-assertion-comparing-a-helper-to-its-own-definition`
（同族＝**測試對隱式契約的依賴**：那則是 helper 與自身定義比對而永遠為真，本則是 helper 與
生產碼的字串格式耦合而無人保證；兩者都讓「測試在量什麼」與「測試看起來在量什麼」分岔）。

---

## 1. 一句話

`tests/test_fidelity_instrument_reports_measured_mechanism.py` 的 `_cause()` 用
`str(err).split(":\n", 1)[0]` 從錯誤訊息切出 cause 段。這依賴 `FidelityError` 用 `":\n"`
分隔 cause 與 summary——**一個沒有任何 assertion、型別、或介面保證的隱式契約**。
生產碼那一行的分隔符一改，測試切到的就不再是它以為的東西。

## 2. 現況（重要：不要讀成「未修」）

**已緩解到「大聲失敗」，但根因未消除。**

- **緩解機制**：`tests/…:264` 的 `assertNotIn("baseline nets=", cause, ...)`。`"baseline nets="`
  是**只有 `summary()` 會吐**的字串，所以切片一旦吃進 summary，這條就紅。
- **未消除的是什麼**：測試依然**靠切字串**取得 cause。它偵測到的是「切片變長了」這個**症狀**，
  不是「契約斷了」這個**原因**。分隔符改動後，紅燈訊息說的是「the cause slice swallowed
  summary()」——正確且有用，但它是一道補在下游的網，不是把契約變成顯式的。
- 因此本 BR 的殘留價值在於：**下一個改 `FidelityError` 訊息格式的人，仍然沒有任何東西告訴他
  有一個測試綁著這個格式**，他只會在跑測試時撞到一個看似無關的 assertion。

## 3. 重現（本輪實跑，2026-09-01，shadow tree，未動 repo 檔案）

環境紀律：`find . -name __pycache__ -prune -exec rm -rf {} +`（AGENTS.md §6.3 stale-pyc 天條）、
mutation 只發生在 `$XDG_RUNTIME_DIR/brns_file_three_brs/shadow/` 的副本、`PYTHONPATH` 指向該副本。

**Step 0 — baseline（未 mutate，repo 原檔）**

```
PP=$(ls -d packages/*/ | tr '\n' ':')
PYTHONPATH="$PP" python3 -m unittest tests.test_fidelity_instrument_reports_measured_mechanism -v
→ Ran 19 tests … OK
```

**Step 1 — 建 shadow tree 並套用 mutant P4**（分隔符 `":\n"` → `" -- "`）

生產碼 `fidelity.py:152` 由
`f"from spec ({cause}):\n"` 改為 `f"from spec ({cause}) -- "`。
mutation 腳本斷言 `occurrences_of_target == 1` 才寫入（否則 abort），並以 `diff` 證明 bytes 真的變了：

```
152c152
<                          f"from spec ({cause}):\n"
---
>                          f"from spec ({cause}) -- "
diff_rc=1   (1 = differs，如預期)
```

**Step 2 — 證明被 import 的是 shadow 而非 repo**（否則整個 mutation proof 無效）

```
loaded_from: /run/user/1000/brns_file_three_brs/shadow/packages/eda-bridge/bodesign_eda_bridge/fidelity.py
```

**Step 3 — 跑 mutated 測試**

```
P4_MUTANT_unittest_rc=1        (non-zero ⇒ KILLED)
Ran 19 tests … FAILED (failures=1)

FAIL: test_error_message_differs_between_the_two_mechanisms
  File ".../tests/test_fidelity_instrument_reports_measured_mechanism.py", line 264
    self.assertNotIn("baseline nets=", cause, …)
AssertionError: 'baseline nets=' unexpectedly found in
  'schematic fidelity gate FAILED — net partition diverged from spec (open circuit:
   2 node(s) lost every peer they share a net with in the spec) -- baseline nets=2
   nodes=5 | candidate nets=3 nodes=5 | shared=5\nFIDELITY FAIL moved=2 …'
  : the cause slice swallowed summary(): the separator contract in _cause() no longer
    holds, so this test is measuring the summary, not the cause
```

**Step 4 — 量化切片被撐大的幅度**（同一顆 mutant，直接量字串）

| 量測 | 值 |
| --- | --- |
| `len(slice)` under P4 | **292** |
| `"baseline nets=" in slice` | **True**（切片吃進了 summary） |
| `len(whole_message)` | 447 |
| `slice == whole_message` | False（`" -- "` 之後仍有一個 `":\n"`，故切片不是整條訊息） |

> **與 dispatcher 給的線索的差異，據實記錄**：派工單引述 VANS round 2/3 的數字為「141 → 282」。
> 本輪實測為 **292**（whole message 447）。差異來源是 fixture 不同（我用的是 `SPEC_NETS`
> 兩網 5 pin 的 open-circuit 案例）。**方向與結論一致**（切片吞掉 summary、mutant 被 killed），
> 但**數字不可互相引用**。這裡記的是我自己量到的那一個。

**Step 5 — 控制組（判別力驗證）**

- **正向控制**：未 mutate 時 19 tests OK（rc=0）⇒ 這支測試不是恆紅。
- **反向控制**：mutate 後 rc=1 且**恰好 1 個 failure**，失敗的正是那條 `assertNotIn`
  ⇒ 紅燈來自我注入的那個改動，不是環境噪音。
- **stale-pyc 控制**：shadow 與 repo 皆先清 `__pycache__`，`remaining_pycache_count=0`
  ⇒ 排除 AGENTS.md §6.3 所述「mutant 沒被真的載入卻誤讀成測試沒判別力」。

## 4. 為什麼這仍是缺陷（機制層）

`FidelityError` **握有** cause 這格資訊——它在 `__init__` 裡算出 `cause` 這個區域變數
（`fidelity.py:150`），然後**把它丟進字串就不再保留**。測試想要那格資訊，只剩下
「把字串切回來」這一條路。

於是形成一個**沒有任何一端知道自己參與其中的契約**：

- 生產碼那一行不知道有人在解析它（沒有註解、沒有常數、沒有測試錨）；
- 測試知道自己在解析，但它能表達這件事的唯一方式是一條下游 assertion。

這是 **G13-harness-disclosure 的近親**：資訊在系統手上，卻只以「已被格式化成人類散文」的
形式對外，於是程式化的消費者只能反解析。

## 5. 徹底解（**未授權，不在本輪範圍**）

讓 `FidelityError` 暴露屬性：

```python
def __init__(self, report: FidelityReport):
    self.report = report
    dx = report.diagnosis()
    self.cause = "; ".join(dx) if dx else "mechanism unclassified"   # ← 新增
    super().__init__(f"... ({self.cause}):\n" + report.summary())
```

測試改讀 `err.cause`，`_cause()` staticmethod 整個刪除。之後訊息格式怎麼改都與測試無關。

**這會動 `packages/eda-bridge/bodesign_eda_bridge/fidelity.py`，本輪 dispatcher 未授權，故只建檔。**

## 6. 驗收判準（給未來修這張的人）

修完後，下面兩件**必須同時**成立，缺一即未修：

1. `grep -n 'split(":' tests/test_fidelity_instrument_reports_measured_mechanism.py` 回空
   （**且**先用一個確定存在的 pattern 證明這支 grep 會非空——回空不得單獨作為通過依據）；
2. 重跑 mutant P4（分隔符改 `" -- "`）後，測試**全綠**——因為測試已不再依賴分隔符。
   注意：**這與現況的紅燈方向相反**，這正是「緩解」與「消除」的分野。
   若修完 P4 仍紅，代表還有別的地方在解析訊息字串。

## 7. 本輪沒有量什麼

- 沒有量其他 11 顆 mutant（VANS round 3 的完整 mutation 矩陣），只重跑了 P4。
- 沒有驗證 `_cause()` 在 `test_whole_message_comparison_is_not_what_pins_the_cause`
  （`tests/…:278`）那條路徑上的行為，只驗了 `:237` 那條。
- 沒有動 repo 內任何檔案；所有 mutation 只存在於 `$XDG_RUNTIME_DIR` 副本，收尾已刪。
