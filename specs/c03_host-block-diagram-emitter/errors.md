# Errors: c03_host-block-diagram-emitter

> 每個錯誤：code / 觸發條件 / 使用者可見訊息 / 回復策略 / 責任層。對齊 repo no-silent-fallback 天條。
> 鏡射 c03_partition-diagram-emitter sibling 錯誤目錄，平移到 host-block 語境。

## Error Catalogue

## E-HB-001 MODEL_MISSING_FIELD（BLOCKING）
- **觸發**：`center_part.name` 缺，或某 peripheral 缺 `name` / `side`。
- **訊息**：`host model invalid: missing required field(s): <list>`（列出 `center_part.name` / `peripherals[i].name` / `peripherals[i].side`）。
- **回復**：回 `status="missing"` + `missing_fields[]`，不產圖。呼叫者補欄位後重試。
- **責任層**：`_validate_model`（A1）。不以預設值續跑（天條）。

## E-HB-002 MODEL_EMPTY_PERIPHERALS（BLOCKING）
- **觸發**：`peripherals` 為空或缺。
- **訊息**：`host model invalid: at least one peripheral required`。
- **回復**：`status="missing"` + `missing_fields=["peripherals"]`，不產圖。
- **責任層**：`_validate_model`（A1）。

## E-HB-003 PERIPHERAL_SIDE_INVALID（BLOCKING）
- **觸發**：某 peripheral 的 `side` 不在 {top,bottom,left,right}。
- **訊息**：`host model invalid: peripherals[i].side(invalid:<value>)`。
- **回復**：`status="missing"` + `missing_fields` 含 `peripherals[i].side(invalid:<value>)`，不產圖。
- **責任層**：`_validate_model`（A1）。enum 檢查，不靜默修正。

## E-HB-004 PERIPHERAL_GLYPH_UNCOVERED（WARN，非阻塞）
- **觸發**：peripheral `type` 未被樣式庫收錄。
- **訊息**：`peripheral '<name>' type '<type>' not in glyph library; rendered as dashed placeholder`。
- **回復**：以 dashed-border named placeholder 方塊呈現 + 列入 `placeholders[]` / `warnings[]`；不靜默省略、不阻斷產出。
- **責任層**：`_resolve_glyphs`（A2）。對齊 c01/partition placeholder 紀律。

## E-HB-005 PNG_TOOLCHAIN_ABSENT（INFO，非阻塞）
- **觸發**：cairosvg（或等價 raster）不可用。
- **訊息**：`PNG raster unavailable (cairosvg absent); SVG delivered, PNG skipped`。
- **回復**：`png_rendered=false`，PNG **不列** `files`（no phantom）；SVG 正常交付。
- **責任層**：A6。toolchain-gated，非錯誤態。

## E-HB-006 PPTX_DOCXMCP_UNREACHABLE（WARN，非阻塞）
- **觸發**：`emit_pptx=True` 但 `bodesign_mcp_call(server="docxmcp")` 不可達 / 失敗。
- **訊息**：`editable PPTX unavailable: docxmcp unreachable (<reason>); SVG/PNG delivered`。
- **回復**：`pptx_status="unavailable"` + reason；不偽造 `.pptx`（no fabrication 天條）。SVG/PNG 仍交付。
- **責任層**：A7。

## E-HB-007 OUTPUT_DIR_UNWRITABLE（BLOCKING）
- **觸發**：`folder` 不可寫 / 不存在且無法建立。
- **訊息**：`cannot write outputs to '<folder>': <oserror>`。
- **回復**：拋出明確 IO 錯誤，不靜默吞。
- **責任層**：A6 寫檔階段。
