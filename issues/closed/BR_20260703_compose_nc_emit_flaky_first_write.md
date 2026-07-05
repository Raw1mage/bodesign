# BR: compose no_connect emit 首寫持久目錄對合法 NC 腳偶發 raise（flaky）

- Date: 2026-07-03
- Session: opencode `ses_0db8f20d1ffe9Jyjzd1sFEb1Go`（quality/prd-bom-crosscheck L3 C04 全鏈）
- Severity: Low（flaky；乾淨重跑即通，非阻塞）

## 現象（含硬證據）

L3 首次寫入持久目錄時，`compose_schematic` 對 J1 USB-C 的 NC 腳（A6/B6/A7/B7/A8/B8——符號確實有此腳）raise no_connect 相關錯誤；同一 spec 乾淨重跑即通過（`warnings=[]`）。錯誤與腳位存在性無關（腳確實存在），指向首寫時序/狀態殘留。

## RCA（待確認）

T1 no_connect emit（本輪新加）在首次寫入既有非空目錄時，可能對前一輪殘留的 schematic 狀態或 pin 解析快取產生偶發不一致。乾淨目錄或重跑即消失 → 時序/狀態殘留類 flaky，非邏輯錯誤。需在 composer.py 的 nc pin 解析路徑埋 checkpoint 確認首寫 vs 重跑的 pin 解析輸入差異。

## 建議修復

- 追查 compose_schematic 首寫既有目錄時 nc pin 解析的輸入狀態（是否讀到殘留 .kicad_sch）。
- 若確認狀態殘留，寫入前清理或以乾淨臨時目錄組裝後原子搬移。

## 影響範圍

- 含 NC 腳宣告的 compose_schematic 重複寫入同目錄場景。

## 驗證手段

- 同 spec 對既有非空目錄連續 compose 兩次 → 兩次皆 `warnings=[]` 無 raise。
