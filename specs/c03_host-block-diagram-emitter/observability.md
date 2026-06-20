# Observability: c03_host-block-diagram-emitter

> emitter 是同步 pure-python 工具，無長駐 runtime。觀測點以 result 欄位 + warnings + 結構化回報為主。
> 鏡射 c03_partition-diagram-emitter sibling 觀測模型，平移到 host-block 語境。

## Events

emitter 是同步 pure-python 工具，無背景 worker、無 Bus event；「事件」以 result 回報 + warnings 形式呈現（呼叫端可記入 specbase event log）。

- `host_block.emit.ok` — 成功產圖（result.status=ok），帶 peripherals_count。
- `host_block.emit.missing` — MODEL fail-fast（result.status=missing），帶 missing_fields。
- `host_block.glyph.placeholder` — peripheral 型別未覆蓋（E-HB-004），帶 peripheral 名。
- `host_block.png.unavailable` — cairosvg 缺（E-HB-005）。
- `host_block.pptx.unavailable` — docxmcp 不可達（E-HB-006）。

## Metrics

| 指標 | 計算 | 用途 |
|---|---|---|
| placeholder_ratio | len(placeholders) / peripherals_count | 樣式庫覆蓋率；偏高代表需擴充 peripheral 型別 |
| peripherals_count | result 欄位 | 圖複雜度、放射狀版面壓力 |
| png_rendered 率 | 統計多次呼叫 | raster toolchain 可用性 |
| missing 率 | status=missing / 總呼叫 | 上游 MODEL 品質訊號 |

屬產品演進訊號，非 runtime alert；可在 event log 隨任務記錄，無 metrics endpoint。

## Result-level signals（每次呼叫回報）

| 訊號 | 來源欄位 | 用途 |
|---|---|---|
| 成功/失敗 | `status` (ok/missing) | 區分產出 vs fail-fast |
| 缺項清單 | `missing_fields[]` | 定位 MODEL 哪個 center/peripheral 欄位缺或 side 非法 |
| placeholder 使用 | `placeholders[]` | 哪些 peripheral 型別未被樣式庫覆蓋（驅動樣式庫擴充） |
| PNG 狀態 | `png_rendered` (bool) | cairosvg toolchain 是否可用 |
| PPTX 狀態 | `pptx_status` (not-requested/ok/unavailable) | docxmcp orchestration 結果 |
| 規模 | `peripherals_count` | 圖複雜度、放射狀版面壓力 |
| honest-boundary | `boundary.notes[]` | 確認三條誠實標註實際帶上 |
| reference echo | `reference_baseline` echo | derived product diff/gate 數確認 |
| 真實產出檔 | `files[]` | 磁碟真實存在檔（無 phantom） |

## Warnings（非阻塞，累積回報）

- `PERIPHERAL_GLYPH_UNCOVERED`（E-HB-004）：peripheral 型別未覆蓋 → 樣式庫缺口訊號。
- `PNG_TOOLCHAIN_ABSENT`（E-HB-005）：raster 不可用。
- `PPTX_DOCXMCP_UNREACHABLE`（E-HB-006）：跨 server orchestration 失敗。

## 測試可觀測性

- 確定性回歸（TV6）：兩次 run SVG 必須 byte-identical——是 emitter 健康的硬訊號。
- fail-fast 回歸（TV2/TV3/TV4）：缺欄位或非法 side 必回 missing，是 no-silent-fallback 天條的守門測試。
- no-fabrication 回歸（TV7）：無 reference_baseline 不渲染 derived-from 區塊。

## 無需的觀測

- 無持久狀態、無背景 worker、無 race window → 不需 Bus event / metrics endpoint / 長駐健康檢查。
- PPTX 經 `bodesign_mcp_call` 是同步委派；失敗即時回報於 result，無需非同步追蹤。
