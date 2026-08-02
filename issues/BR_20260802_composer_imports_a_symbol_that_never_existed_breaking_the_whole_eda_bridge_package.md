# BR_20260802 — `composer.py` import 一個從未存在的符號：`bodesign_eda_bridge` 整個套件無法 import，5 個測試模組在收集期就死

- **Status**: OPEN
- **Owner**: `(default)`
- **Family**: `schematic-engine`（該 family 目前無 owner，見 `issues/OWNERS.md`）
- **Filed at**: 2026-08-02（coordinator `ses_04db7a1c5ffelvbxyLP1p6xlRH`；由 BR_20260731 handler 在驗證中發現並回報，coordinator 獨立覆核）
- **Severity**: real — 一個公開套件的 `import` 直接 `ImportError`；**5 個測試模組因此從未執行過**，且它們回報的是「1 個 error」而不是「N 個測試失敗」
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/composer.py:36` × `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`
- **Fix venue**: NEW session (BRNS) rooted in `/home/pkcs12/projects/bodesign`
- **時區**: Asia/Taipei (UTC+08:00)

## Symptom（實測）

```
$ PP=$(ls -d packages/*/ | tr '\n' ':'); PYTHONPATH="$PP" python3 -c "import bodesign_eda_bridge"
  File ".../bodesign_eda_bridge/composer.py", line 36, in <module>
    from .kicad_emit import (
ImportError: cannot import name '_vendor_sym_scale' from 'bodesign_eda_bridge.kicad_emit'
```

**這不是本次修改造成的**。用 `git archive HEAD` 匯出乾淨樹到 XDG scratch 重跑，同樣 ImportError；
控制組：同一棵乾淨樹 `import bodesign_workflow_core` → OK。**確為 HEAD 既有破損。**

## RCA

`_vendor_sym_scale` **從未存在於 `kicad_emit.py`**——不是被刪除，是從未落地：

```
$ git log --oneline -S"_vendor_sym_scale" -- packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py
（無輸出 — 該檔案的歷史中從未出現過這個字串）

$ git log --oneline -S"_vendor_sym_scale" -- packages/eda-bridge/bodesign_eda_bridge/composer.py
a7fe826 fix(eda-bridge): compose_schematic merges KiCad stdlib into symbol_dirs ... (2026-07-23)
```

控制組：`grep -c "^def \|^    def " kicad_emit.py` → 70（該檔有大量 def，grep 有鑑別力，
不是「找不到任何東西」的假陰性）。

`composer.py:36` 從 `a7fe826`（7/23）起 import 它，`:462` 與 `:2007` 使用它，
docstring（`:453`）描述它應該是 emit 端與 placement 端共用的縮放 helper。

`tests/test_dd31_pitch_align_main_chip.py:18-24` 的 docstring 自陳：

> **TDD-first: RED until a shared `_vendor_sym_scale` helper exists and both sites call it.**

**所以這是一個刻意的 TDD RED——但 RED 的代價外溢了。** 測試預期紅是合理的；
`composer.py` 在 helper 尚未實作時就 import 它，導致**整個套件無法 import**，
把一個「單一測試該紅」擴大成「五個模組無法執行」。

## 打擊半徑（實測，非估計）

```
test_pin_allocation             -> FAILED (errors=1)   ← import 期就死
test_dd31_pitch_align_main_chip -> FAILED (errors=1)
test_composer_draftsman         -> FAILED (errors=1)
test_kicad_emit                 -> FAILED (errors=1)
test_block_drafter              -> FAILED (errors=1)

CONTROL（不 import eda_bridge）：
test_vacuous_pass_gates         -> OK
```

## 這是哪一種缺陷（為什麼歸在 vacuous-pass 家族）

**一個不能執行的測試，與一個通過的測試，在「有沒有紅」這個維度上長得不一樣——
但在「這個模組有沒有在保護我」這個維度上一模一樣：都是零。**

而 `errors=1` 這個輸出，對「1 個測試失敗」與「N 個測試從未被執行」共用同一個形狀。
`test_pin_allocation.py` 裡有 3 個測試，它現在回報 1 個 error——
**沒有任何一處告訴你那 3 個測試今天一次都沒跑過。**

這正是 BR_20260731 修的同一個形狀（缺席態與失敗態共用輸出），只是發生在測試基礎設施層。
BR_20260731 的 handler 因此改用 `spec_from_file_location` 直接載入 `pin_allocation.py`，
繞開破損的套件 `__init__`，確保新測試真的會跑——那是正確的權宜，但不能取代修這張 BR。

## Fix proposal

**必須先裁決 `_vendor_sym_scale` 的歸屬**，這不是接線問題：

1. **實作它**（若 DD-31 的設計意圖仍成立）——在 `kicad_emit.py` 實作該 helper，
   讓 emit 端 `_place_component` 與 placement 端 `composer._estimate_bbox` 共用同一個縮放
   來源（single-source-no-drift）。這會讓 `test_dd31` 從 RED 轉 GREEN，且解除全套件 import 破損。
   **這是唯一同時解決兩件事的選項。**

2. **移除 import**（若 DD-31 已被放棄）——`composer.py:36` 拿掉，`:462`/`:2007` 改回各自計算。
   但這會**重新引入 DD-31 要消滅的 drift**（placement bbox 與 emitted geometry 不同源），
   等於用回歸換 import 修復。**不建議**，除非有人確認 DD-31 已作廢。

3. **（不可接受）** 讓 `composer.py` try/except 吞掉 ImportError 並 fallback——
   違反 no-silent-fallback 天條，且會讓 drift 靜默發生。**明確排除，記錄於此以免下一個人重新考慮。**

## Validation plan

- **控制組（必要）**：修復前斷言 `import bodesign_eda_bridge` 會 `ImportError`（證明缺陷存在）。
- 修復後：`import bodesign_eda_bridge` 成功。
- **五個模組逐一實跑**，斷言它們回報的是**真實的測試數**而非 `errors=1`：
  `test_pin_allocation` 應回報 3 個測試的實際結果。
- 若走選項 1：`test_dd31_pitch_align_main_chip` 由 RED 轉 GREEN，且**證明它在 helper 行為錯誤時會紅**
  （改壞 helper 一次，確認測試抓得到）。
- 迴歸：`test_kicad_emit` / `test_composer_draftsman` / `test_block_drafter` 的既有斷言全通過
  （這些是 byte-stable 迴歸基線所在，見 `issues/OWNERS.md` 的 schematic-engine 條目）。

## Cross-ref

- `issues/OWNERS.md` — `schematic-engine` family 無 owner；該 family 的前候選 session
  （`ses_0c8efa1b4`）已探測並拒絕（「我當初就不是作者」），且明確建議
  **新 handler 從 spec + fidelity 閘讀起**。
- `packages/eda-bridge/bodesign_eda_bridge/fidelity.py` 是這個 family 的驗收儀器，
  任何動 wire emission 的修復都必須保持保真閘綠。
- BR_20260731（`b429b06` 已修）——本 BR 由該任務的驗證過程發現。
