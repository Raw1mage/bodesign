# BR: finish_c04 缺 pad 本徵 clearance 處理與 micro-stub 清理 — 已知假違規需人工 pcbnew 手術

- **Date**: 2026-07-08
- **Severity**: medium（gate 會 HARD FAIL 在可機械分類的假違規上）
- **Reporter**: thesmart_products aiguard C04 gerber run（session 實測）
- **Scope**: bodesign C04 layout engine / finish_c04.sh + check_c04.sh

## Symptom

route 後的 DRC 殘留違規中，有一類是 **footprint 本徵幾何**造成、不是走線錯誤，finish chain 不處理，導致 check_c04 硬閘 fail：

1. **Pad 本徵 clearance**：USB-C 連接器（land pattern pad 間淨空 0.10mm）與 LGA 封裝（U_IMU 14-pad，pad 間 0.10mm）在 0.15mm 板規則下，**pad 對 pad 自己違規**——這是封裝規格，不是可修的錯。正解是 pad-level `SetLocalClearance` override（本 session 以 pcbnew Python 手動做，0.09mm）。
2. **SES 匯入殘留 micro-stub**：freerouting SES 匯入後留下 <0.01mm 的殘段，造成假 unconnected / 假 clearance（MIC1 GND 0.0001mm track）。
3. **widen 步驟撞 via**：finish 的 widen(50Ω) 把訊號段加寬後與鄰近 via 產生新 clearance 違規（CHG_STAT vs USB_CC2 via），需要回退寬度或縮 via——finish chain 沒有 post-widen DRC 迴圈。

## Evidence

aiguard_product 板：finish 後 copper 違規 14 → 手動 pad override + stub 清理 + via 調整後 **0 copper / 0 unconnected**（僅剩 5 個 cosmetic silk warn）。全部修復都是機械可分類、可自動化的。

## Ask（bodesign 執行）

1. finish_c04 增加 **pad-intrinsic clearance 偵測**：DRC 違規若雙方是同 footprint 相鄰 pad 且距離=封裝本徵值 → 自動 pad-level override（記入 sidecar 供審查），不是留給 gate fail。
2. SES 匯入後自動清 <0.02mm micro-stub。
3. widen/pour 之後跑增量 DRC，新增違規的段自動回退（目前 length-match 有 DRC-guard，widen 沒有）。
4. check_c04 對「封裝本徵」類違規給獨立分類（warn + 證據），與真 copper 錯誤區分。

## 關聯

- `issue_20260703_tier3_honesty_mechanisms_unwired_c04_silent_passthrough.md`（gate 分類粒度）

## Resolution (2026-07-10)

BR 四項 Ask 全數落地於 `packages/eda-bridge/bodesign_eda_bridge/routing.py`（C04 finish chain 已 promote 為 pcbnew MCP primitives，非 shell script）：

1. **Pad-intrinsic clearance 自動 override（Ask #1）— 新增**：`apply_pad_intrinsic_overrides(in, out, *, override_mm=0.09, sidecar_path=None)`。跑 `drc_gate(classify_intrinsic=True)`，對每個 `package_intrinsic` 違規（同 footprint 相鄰 pad = land pattern 本徵幾何）在該 footprint 的 pad 施 pad-level `SetLocalClearance`（預設 0.09mm，低於 0.10mm land gap），全部記入 sidecar 供審查。true copper 違規不碰，仍照常 fail gate（非放寬閘門）。
2. **SES micro-stub 清理（Ask #2）— 既有**：`clean_micro_stubs`（<0.02mm 殘段）已落地，本輪覆核確認。
3. **Post-widen 增量 DRC 回退（Ask #3）— 新增**：`widen_bus_tracks` 加 `post_widen_drc=False` 參數；開啟時事前幾何 widen 後跑真 `drc_gate`，把引入新 copper 違規（事前 `_widening_is_clear` 幾何預測漏掉的 via 場景，即 CHG_STAT vs USB_CC2 症狀）的加寬逐段 width-only 回退，回傳 `reverted`/`copper_after`。
4. **check_c04 封裝本徵分類（Ask #4）— 既有**：`classify_clearance_violation` + `drc_gate(classify_intrinsic=True)` 已把 `package_intrinsic` 與真 copper 分開報（clean 仍要求 true copper=0，不靜默放行），本輪覆核確認。

MCP 曝面：`bodesign_apply_pad_intrinsic_overrides` 新增；`bodesign_widen_bus_tracks` schema 加 `post_widen_drc`。`__init__.py` 匯出 `apply_pad_intrinsic_overrides`。

**Validation**：host `py_compile` 三檔 PASS；container `bodesign-ee` import PASS（新符號可見）；pcbnew 實測——pad-intrinsic override 對 0.10mm 雙 pad footprint 正確施 0.09mm 且 board 讀回確認、sidecar 落檔；post_widen_drc 新路徑執行成功回傳 reverted/copper_after，no-track 場景不誤傷。

**未觸碰**：net2pcb.py / DSN 產生器 / draftsman / check_c04.sh 閾值（無放寬）。
