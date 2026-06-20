# Errors: c01_design-vector (BR-extended)

每個 error 碼對應使用者可見訊息、recovery、負責層。三 bucket emitter 與 readiness 共用此目錄。天條：no silent fallback——缺欄一律顯式報錯，不續跑。

## Error Catalogue

| Code | When | User-visible message | Recovery | Layer |
|---|---|---|---|---|
| `C01V-E001` | Ai file bucket 缺 `form_archetype` / `primary_face` / `exposed_components` / `cmf_direction` 任一 | `missing: cannot emit ID visual package — required answer_state fields absent: <list>` | 先用 `c01_update_answers` 補欄位，再重呼叫 | emit_c01_id_visual_package |
| `C01V-E002` | SVG schema 驗證失敗（圖層缺、元件 group 缺、SVG 非法） | `validation-failed: layered SVG schema violations: <list>` | 不輸出半成品；回頭調 S2 圖元庫/佈局，修正後重試 | SVG validator |
| `C01V-E003` | 要求 `.ai` 但無 Illustrator-compatible export path | `external-needed: .ai export path unavailable; emitted SVG + figma_import_spec.json instead` | 用 SVG/Figma spec 接手；如需 .ai 須配置真實 exporter | emit_c01_id_visual_package |
| `C01C-E001` | CMF bucket 缺 `cmf_direction` | `missing: cannot emit CMF package — cmf_direction absent` | 補 `cmf_direction` 後重呼叫 | emit_c01_cmf_package |
| `C01C-E002` | CMF token 推導出空 material_family / color_routes | `validation-failed: CMF tokens incomplete: <list>` | 補充 constraints / cmf_direction 細節後重試 | CMF token deriver |
| `C01U-E001` | UIUX bucket 缺 `display_uiux` 且無任何 status 互動描述 | `missing: cannot emit UIUX package — no display/status interaction described` | 補 `display_uiux`（含無 display 的 LED/status 描述）後重呼叫 | emit_c01_uiux_package |
| `C01U-E002` | UIUX 狀態詞彙推導出空集合 | `validation-failed: UIUX state set empty: <reason>` | 補 exposed_components / status 描述後重試 | UIUX state deriver |
| `C01D-E001` | PDF pipeline（docxmcp/bodesign_emit_doc）不可用 | `blocker: PDF pipeline unavailable; markdown source emitted, PDF pending` | 確認 docxmcp 可呼叫後重跑 PDF 步驟；不手工拼 PDF | PDF pipeline |
| `C01R-E001` | readiness 讀到損壞的 bucket（檔案存在但內容非法） | `partial: <bucket> present but invalid: <detail>` | 重新產出該 bucket | assess_c01_package_readiness |

## Non-fallback invariants

- 任何 emitter 在缺關鍵欄位時，**只**回 `missing`/`external-needed`，**不**以預設形態/材質/狀態續跑（違反即視為缺陷）。
- `draft_markings` 為空 = 缺陷（每個視覺/文件必帶 draft 標記）。
- ID-native 產出**永不**把 `human_approved` 由 False 改 True。
