# BR_20260704 — bodesign 無安全 pcbnew wrapper，agent 徒手腳本反覆踩 SwigPyObject cast / SetTextSize segfault / 二次 GetFootprints 退化

- **軸**：A（工具缺，是 placement 工具缺口 BR 的姊妹檔）
- **層**：bodesign 工具層（eda-bridge，pcbnew 互動)
- **嚴重度**：High（每個徒手改板的 agent 都會重踩，燒大量回合）

## 現象（含硬證據）

因 bodesign 無 placement / board-edit verb（見 `BR_20260704_no_component_placement_castellated_tool_c04_gap.md`），本 session 被迫徒手寫 raw pcbnew 腳本改板。過程反覆撞上 KiCad 9.0.9 pcbnew swig binding 的三類地雷，硬證據（同一 CCM 板、同一 session，2026-07-04）：

1. **`.py` 檔 / `exec(open().read())` 執行 → SwigPyObject cast 退化**：
   - `python3 place_stamp.py` → `AttributeError: 'SwigPyObject' object has no attribute 'GetReference'`（footprint 物件退化）。
   - shell 迴圈重試 12 次全 flaky（每次全新程序仍 fail）。
   - `python3 -c "exec(open(...).read())"` → 12/12 確定性 fail。
2. **二次呼叫 `b.GetFootprints()` → 第二次起回傳退化物件**：第一次 find J_B2B 成功，第二次迴圈 place 元件時 cast 爆掉。修正：開頭 `list(b.GetFootprints())` materialize 一次，全程用同一份 list。
3. **`fp.Reference().SetTextSize()` → segfault (SIGSEGV, core dumped, exit 139)**：bisect 確認——移除所有 `Reference()` 操作的 min 版存檔成功（273KB），一加 `ref.SetTextSize()` 就 segfault。**放大 refdes 字級這個無害操作直接 crash 整個 python。**
4. **程式化建 `PAD`(PTH castellated) → 亦 segfault at save**：bisect 確認 castellated pad 建構段是另一個 segfault 源。

淨結果：一個「搬 7 顆件 + 縮板框 + 建板緣接腳」的簡單 placement，燒了 ~15 個回合在對抗 pcbnew swig，且最終 castellated 半孔與放大字級都做不出來（只能退回絲印示意）。

## RCA

KiCad pcbnew python binding（swig）在**非 KiCad-GUI host context** 下對物件生命週期管理脆弱：
- 物件從 board 容器取出後，跨「多次 accessor 呼叫」或「`.py` 檔 module-level 執行」會遺失 C++ 端 ownership → 退化成裸 SwigPyObject。
- 某些 setter（`SetTextSize` on Reference text、`PAD` 建構）觸發析構順序問題 → SIGSEGV。
- 這些是 pcbnew 的已知脆弱性，**不是 agent 邏輯錯**——但每個徒手 agent 都要重新踩一遍、重新 bisect，是巨大的重複成本。

## 建議修復

bodesign eda-bridge 提供一個 **safe-pcbnew wrapper 模組**（container 內，pcbnew 已裝），封裝已知安全模式，讓 placement / board-edit verb（見姊妹 BR）站在其上：

1. **single-load 契約**：一個 verb 呼叫 = 一次 `LoadBoard`，開頭 `list(GetFootprints())` / `list(GetTracks())` materialize，全程用 materialized list，**禁止二次容器查詢**。
2. **避開已知 segfault setter**：refdes 字級改用**存檔後文字層 S-expression 後處理**（.kicad_pcb 是文字格式）而非 `SetTextSize`；castellated PTH pad 同樣用文字層 S-expression 注入（`(pad "1" thru_hole ...)`）而非 `PAD()` 建構。
3. **execution mode 固定**：以 `python3 - <<HEREDOC`（stdin）或 container 內固定 entrypoint 執行，避開 `.py` 檔 module-level 的 cast 退化路徑；wrapper 自帶 `assert hasattr(b,'GetFootprints')` + `all(hasattr(f,'GetReference') for f in fps)` 前置健康檢查，退化就 fail-fast 重啟而非續跑。
4. **記錄為 known-hazard**：把這四個地雷寫進 eda-bridge 的 ENGINE.md / 註解，讓後續維護者不重踩。

## 影響範圍

- 所有需徒手改 .kicad_pcb 的 bodesign 操作（placement、board resize、castellated、任何 pcbnew 後處理）。
- 一旦 placement verb（姊妹 BR）建於此 wrapper 上，agent 完全不必再碰 raw pcbnew，本類磨擦歸零。

## 驗證手段

- wrapper 做「搬件 + 改板框 + 放大 refdes + 建 PTH castellated pad」全套 → 存檔成功、pcbnew 實讀驗證（字級變大、pad 為 PTH 落在板緣、net 正確），**零 segfault**。
- 對照組：同樣操作用 naive pcbnew（`.py` 檔 + `SetTextSize` + `PAD()`）→ 重現 cast/segfault，證明 wrapper 確實繞過。
- 回歸：single-load 契約下連續 100 次 load-edit-save 無 flaky cast。
