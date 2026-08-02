# BR_20260802 — 保真閘還原後是紅的：`test_fidelity_gate` 在 HEAD 從未執行過，所以沒有人知道它壞了

- **Status**: OPEN
- **Owner**: unassigned（`schematic-engine` family 無 owner；filed by 值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH`）
- **Family**: `schematic-engine`
- **Severity**: real — `fidelity.py` 是這個 family 的**驗收儀器**，它現在 RED 且 deterministic
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/fidelity.py` × `composer.py:2600` × `tests/test_fidelity_gate.py`
- **Filed at**: 2026-08-02
- **時區**: Asia/Taipei (UTC+08:00)
- **Parent**: `issues/BR_20260802_reset_hard_destroyed_kicad_emit_and_the_BR_blamed_the_import_that_was_correct.md`

## 這張為什麼會存在

還原 `kicad_emit.py`（見 parent BR）之後，`bodesign_eda_bridge` 終於能 import，
於是 43 個測試模組第一次真的載入。**其中包含這個 family 的驗收儀器，而它是紅的。**

在 HEAD，這個模組**從來沒有跑過**——它回報的是 `Ran 1 test, errors=1`（`_FailedTest`，
整個模組在收集期就死）。

> **「儀器紅燈」與「儀器從未開機」在測試摘要上都是一行 FAILED。**
> 這是本 repo 反覆出現的形狀（`code-thinker §8.1`）：缺席態與失敗態共用同一個輸出。

## 實測（還原後的樹，連跑兩次結果相同）

```
tests.test_fidelity_gate
  test_all_label_path_is_faithful             ERROR
  test_verify_partition_fidelity_standalone   FAIL
  test_expected_partition_from_dict_nets      ok
  test_faithful_candidate_passes              ok
  test_fused_candidate_is_flagged             ok
```

### ERROR（integration path）

```
tests/test_fidelity_gate.py:88  compose_schematic(...)
  -> composer.py:2600  raise FidelityError(report)
bodesign_eda_bridge.fidelity.FidelityError:
  schematic fidelity gate FAILED — net partition diverged from spec
  (collinear-wire fusion / label collision)
```

### FAIL（standalone path）

```
baseline nets=9 nodes=24 | candidate nets=6 nodes=18 | shared=18
ONLY_BASELINE (missing from candidate): ['J1.1','J1.2','J1.5','R1.1','R2.1','R5.1']
FIDELITY FAIL moved=0 only_baseline=6 only_candidate=0
```

**9 個 net 被熔成 6 個**，6 個節點消失，且 `only_candidate=0` / `moved=0`——
沒有節點跑錯 net，是**整段連接被吃掉**。錯誤訊息自己指名的機制是 collinear-wire fusion：
共線的線段被併成一條，於是本該分離的 net 短接在一起。

**這是電氣正確性缺陷，不是外觀缺陷。** J1（連接器）與 R1/R2/R5 的接點在候選裡不存在。

## 三個必須先回答的問題（不要直接跳去修）

1. **這個紅燈是還原造成的，還是還原**揭露**的？**
   還原的 `kicad_emit.py` 比 HEAD 多 765 行、`emit_kicad_schematic` 多兩個參數
   （`clusters`、`l6_avoidance`），6 個函式本體不同。紅燈可能來自那些差異，
   也可能是這份未 commit 的 WIP 本來就沒做完。**先分辨，再動刀。**
2. **baseline 是對的嗎？** `baseline nets=9` 來自 `expected_partition_from_dict_nets`。
   若 baseline 本身過期，修 candidate 是修錯邊。
3. **`refs/recovered/kicad_emit_full` 是未 commit 的 WIP，從來沒有被證明是好的。**
   它唯一被證明的是「能讓 import 成功」（值星官親手驗，見 parent BR）。
   **能 import ≠ 正確。** 不得因為它修好了 43 個模組就推定它整體正確。

## Validation plan（必要，不接受「改到綠」）

- **控制組先行**：確認這個測試在**該紅的時候會紅**——手動把一個 net 熔掉，
  斷言 `only_baseline` 增加。沒有這一格，「改到綠」可能只是把儀器關掉。
- **Mutation proof**：修好之後，把修復點改壞一次，斷言測試轉紅。
- **不得放寬閾值當修復**。`fidelity.py` 是驗收儀器，調鬆它等於銷毀證據。
- 迴歸：`test_kicad_emit` / `test_composer_draftsman` / `test_block_drafter`
  （byte-stable 迴歸基線所在）。

## Cross-ref

- parent BR — 還原的授權與位元組條件
- `issues/OWNERS.md` — `schematic-engine` family 無 owner
- `plans/eda-bridge_layered-pipeline/` — DD-8（`interior_crossings=0`）、DD-14（justify-left）
  的驗收紀錄；DD-16 記載 net-flag 疊印為獨立缺陷軸
