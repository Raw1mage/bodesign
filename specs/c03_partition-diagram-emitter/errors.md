# Errors: c03_partition-diagram-emitter

> 每個錯誤：code / 觸發條件 / 使用者可見訊息 / 回復策略 / 責任層。對齊 repo no-silent-fallback 天條。

## Error Catalogue

## E-PART-001 MODEL_MISSING_FIELD（BLOCKING）
- **觸發**：board 缺 `role`，或 interconnect 缺 `class` / `dir`。
- **訊息**：`partition model invalid: missing required field(s): <list>`（列出 board 名 / interconnect 索引 + 欄位）。
- **回復**：回 `status="missing"` + `missing_fields[]`，不產圖。呼叫者補欄位後重試。
- **責任層**：`_validate_model`（A1）。不以預設值續跑（天條）。

## E-PART-002 MODEL_EMPTY_BOARDS（BLOCKING）
- **觸發**：`boards` 為空或缺。
- **訊息**：`partition model invalid: at least one board required`。
- **回復**：`status="missing"` + `missing_fields=["boards"]`，不產圖。
- **責任層**：`_validate_model`（A1）。

## E-PART-003 MODULE_GLYPH_UNCOVERED（WARN，非阻塞）
- **觸發**：模組 `type` 未被樣式庫收錄。
- **訊息**：`module '<name>' type '<type>' not in glyph library; rendered as generic placeholder`。
- **回復**：以 named placeholder 方塊呈現 + 列入 `placeholders[]`；不靜默省略、不阻斷產出。
- **責任層**：`_resolve_glyphs`（A2）。對齊 c01 placeholder 紀律。

## E-PART-004 PNG_TOOLCHAIN_ABSENT（INFO，非阻塞）
- **觸發**：cairosvg（或等價 raster）不可用。
- **訊息**：`PNG raster unavailable (cairosvg absent); SVG delivered, PNG skipped`。
- **回復**：`png_rendered=false`，PNG **不列** `files`（no phantom）；SVG 正常交付。
- **責任層**：A6。toolchain-gated，非錯誤態。

## E-PART-005 PPTX_DOCXMCP_UNREACHABLE（WARN，非阻塞）
- **觸發**：`emit_pptx=True` 但 `bodesign_mcp_call(server="docxmcp")` 不可達 / 失敗。
- **訊息**：`editable PPTX unavailable: docxmcp unreachable (<reason>); SVG/PNG delivered`。
- **回復**：`pptx_status="unavailable"` + reason；不偽造 `.pptx`（no fabrication 天條）。SVG/PNG 仍交付。
- **責任層**：A7。

## E-PART-006 OUTPUT_DIR_UNWRITABLE（BLOCKING）
- **觸發**：`folder` 不可寫 / 不存在且無法建立。
- **訊息**：`cannot write outputs to '<folder>': <oserror>`。
- **回復**：拋出明確 IO 錯誤，不靜默吞。
- **責任層**：A6 寫檔階段。
