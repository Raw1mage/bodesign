# Observability: c03_partition-diagram-emitter

> emitter 是同步 pure-python 工具，無長駐 runtime。觀測點以 result 欄位 + warnings + 結構化回報為主。

## Events

emitter 是同步 pure-python 工具，無背景 worker、無 Bus event；「事件」以 result 回報 + warnings 形式呈現（呼叫端可記入 specbase event log）。

- `partition.emit.ok` — 成功產圖（result.status=ok），帶 boards/modules/interconnect 計數。
- `partition.emit.missing` — MODEL fail-fast（result.status=missing），帶 missing_fields。
- `partition.glyph.placeholder` — 模組型別未覆蓋（E-PART-003），帶模組名。
- `partition.png.unavailable` — cairosvg 缺（E-PART-004）。
- `partition.pptx.unavailable` — docxmcp 不可達（E-PART-005）。

## Metrics

| 指標 | 計算 | 用途 |
|---|---|---|
| placeholder_ratio | len(placeholders) / modules_count | 樣式庫覆蓋率；偏高代表需擴充模組型別 |
| boards_count / modules_count / interconnect_count | result 欄位 | 圖複雜度、版面壓力 |
| png_rendered 率 | 統計多次呼叫 | raster toolchain 可用性 |
| missing 率 | status=missing / 總呼叫 | 上游 MODEL 品質訊號 |

屬產品演進訊號，非 runtime alert；可在 event log 隨任務記錄，無 metrics endpoint。

## Result-level signals（每次呼叫回報）

| 訊號 | 來源欄位 | 用途 |
|---|---|---|
| 成功/失敗 | `status` (ok/missing) | 區分產出 vs fail-fast |
| 缺項清單 | `missing_fields[]` | 定位 MODEL 哪個 board/interconnect 欄位缺 |
| placeholder 使用 | `placeholders[]` | 哪些模組型別未被樣式庫覆蓋（驅動樣式庫擴充） |
| PNG 狀態 | `png_rendered` (bool) | cairosvg toolchain 是否可用 |
| PPTX 狀態 | `pptx_status` (not-requested/ok/unavailable) | docxmcp orchestration 結果 |
| 規模 | `boards_count` / `modules_count` / `interconnect_count` | 圖複雜度、版面壓力 |
| honest-boundary | `boundary.notes[]` | 確認三條誠實標註實際帶上 |
| 真實產出檔 | `files[]` | 磁碟真實存在檔（無 phantom） |

## Warnings（非阻塞，累積回報）

- `MODULE_GLYPH_UNCOVERED`（E-PART-003）：模組型別未覆蓋 → 樣式庫缺口訊號。
- `PNG_TOOLCHAIN_ABSENT`（E-PART-004）：raster 不可用。
- `PPTX_DOCXMCP_UNREACHABLE`（E-PART-005）：跨 server orchestration 失敗。

## 健康指標（樣式庫覆蓋率，後續可彙整）

- placeholder 比率 = `len(placeholders) / modules_count`：長期偏高代表樣式庫需擴充模組型別。
- 此指標屬產品演進訊號，非 runtime alert；可在 event log 隨任務記錄。

## 測試可觀測性

- 確定性回歸（TV5）：兩次 run SVG 必須 byte-identical——是 emitter 健康的硬訊號。
- fail-fast 回歸（TV2/TV2b）：缺欄位必回 missing，是 no-silent-fallback 天條的守門測試。

## 無需的觀測

- 無持久狀態、無背景 worker、無 race window → 不需 Bus event / metrics endpoint / 長駐健康檢查。
- PPTX 經 `bodesign_mcp_call` 是同步委派；失敗即時回報於 result，無需非同步追蹤。
