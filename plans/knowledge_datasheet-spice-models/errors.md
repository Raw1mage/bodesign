# Errors: knowledge_datasheet-spice-models

SPX_* 錯誤碼命名空間（DD-6）。全部 fail-fast、結構化 payload、附修復指引；無 silent fallback。

## Error Catalogue

| Code | 觸發層 | 訊息（user-visible） | Payload | Recovery |
|---|---|---|---|---|
| `SPX_FIELD_UNKNOWN` | ingest（per-row） | `field_path '<path>' not in registry` | `{field_path, nearby_candidates[]}` | 修正 field_path 拼寫，或確認該參數屬 v1 範圍外（registry 是封閉清單，不靜默建立） |
| `SPX_EVIDENCE_MISSING` | ingest（per-row） | `row '<field_path>' lacks evidence (document_sha256 + page required)` | `{field_path, missing: ["document_sha256"\|"page"]}` | 補齊 evidence 後重新提交該 row；該 row 被拒不影響批次其他 row |
| `SPX_VALUE_INVALID` | ingest（per-row） | `row '<field_path>' status=found but value_num absent/non-numeric` | `{field_path, got}` | 修正抽取結果的數值欄位；若 datasheet 確實無值，改標 `status: not_found` |
| `SPX_PARAMS_MISSING` | model 卡生成 | `cannot generate <category> card for <mpn>: required parameters missing` | `{mpn, category, missing_field_paths[], repair_guidance: "extract these parameters from the datasheet and ingest with evidence"}` | 對缺項 field_path 補抽取（回 R2 管線）；不得用預設值補洞 |
| `SPX_PARAMS_AMBIGUOUS` | model 卡生成 | `field '<field_path>' has multiple rows without a typ value` | `{mpn, field_path, candidate_rows[]（含 value_kind/condition/value）}` | 補抽取 typ 值，或以 condition 區分後刪除多餘 row；系統不自行平均或取中點 |
| `SPX_CATEGORY_UNSUPPORTED` | model 卡生成 / MCP | `category '<cat>' not supported in v1` | `{got, supported: ["diode","ldo","passive"]}` | 改用支援類別；其他類別屬 extend 範圍 |
| `SPX_SMOKE_FAILED` | materialize | `model card for <mpn> failed ngspice smoke test` | `{mpn, card_name, stderr_excerpt（≤500 chars）, testbench_path}` | 檢視 stderr 判斷是參數異常（回抽取）或模板 bug（回報 issue）；fail 卡不進 manifest，cascade 不可見 |

## 責任層對照

| 層 | 模組 | 拋出的碼 |
|---|---|---|
| ingest | `component-kb/spice_card.py::ingest_spice_extraction` | SPX_FIELD_UNKNOWN / SPX_EVIDENCE_MISSING / SPX_VALUE_INVALID（per-row，不中斷批次） |
| 生成 | `component-kb/spice_card.py::generate_model_card` | SPX_PARAMS_MISSING / SPX_PARAMS_AMBIGUOUS / SPX_CATEGORY_UNSUPPORTED（拋例外，中斷該次生成） |
| 物化 | `component-kb/spice_card.py::materialize_model_cards` | SPX_SMOKE_FAILED（per-card 回報；其他卡繼續） |
| MCP | `services/mcp/server.py::bodesign_spice_model_card` | 全部透傳（run_tool 包裝層保留 code + payload） |

## 非錯誤的顯式狀態（不是 SPX 碼）

- `smoke: "skipped-no-simulator"`：ngspice 不在 PATH。卡可生成、可進 manifest，但 smoke 欄位誠實記錄未驗證——不偽裝 pass。
- `not_found`（ingest report）：抽取顯式回報參數不可得。不落 DB、不算錯誤；下游生成若因此缺必要參數，屆時以 SPX_PARAMS_MISSING 浮現。
