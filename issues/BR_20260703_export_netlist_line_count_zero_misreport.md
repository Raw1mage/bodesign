# BR: export_netlist 回 line_count:0 但 netlist 檔正確 —— 誤導性回報（cosmetic）

- Date: 2026-07-03
- Session: opencode `ses_0db8f20d1ffe9Jyjzd1sFEb1Go`（quality/prd-bom-crosscheck L3 C04 全鏈）
- Severity: Low（cosmetic 回報缺口；產物正確，但回報值誤導呼叫端判定失敗）

## 現象（含硬證據）

`bodesign_export_netlist` 對 NPN sink schematic 回 `line_count: 0`，但實際 `.net` 檔為 526 行 / 22 元件的合法 KiCad netlist（`export_bom` 同檔讀得 22 comp 正常）。呼叫端若以 `line_count > 0` 判成功，會誤判為失敗（L3 首輪即因此把 C04 誤標 blocked）。

## RCA

handler 回 `BomResult(status="ok", netlist_path=...)` 但從不填 `line_count` 欄（dataclass 預設 0）。檔案寫入正確，純粹是回報欄未帶值——不是 emitter bug。屬 no-silent-fallback 的反例變體：工具「靜默回 0」讓呼叫端誤判，而非顯式回真實行數。

## 建議修復

- `export_netlist` handler 寫檔後實算 `.net` 行數（或元件數）填入回傳；或改回傳 `component_count` 語意明確欄位。
- 呼叫端契約：以 `status == "ok"` + 檔案存在為成功判準，不倚賴 line_count。

## 影響範圍

- 所有以 export_netlist 回傳值判定成功的工作流（C03→C04 handoff）。

## 驗證手段

- NPN sink schematic export → 回傳 line_count == 實際行數（>0）。
- 空 schematic → line_count == 0 且 status 反映真實。
