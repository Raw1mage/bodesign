# Errors: c02_voice-to-design

## Error Catalogue

口述抽取 / 反問補全 / 編排各層的錯誤碼、訊息、復原策略、責任層。

| Code | Layer | When | User-visible message | Recovery |
|---|---|---|---|---|
| `C02_VTD_EMPTY_SPEC` | 抽取 (plan_c02_intent) | spec_text 為空或全空白 | 「請描述你要的產品結構（板尺寸、裝什麼、開哪些孔、什麼環境）」 | 提示使用者重新口述，不產空草稿 |
| `C02_VTD_DIM_UNPARSEABLE` | 抽取 regex | 提到尺寸但抽不出明確數字（如「中等大小」） | 轉成 board_outline 澄清問題 | 不臆測尺寸（DD-2），轉反問 |
| `C02_VTD_BLOCKING_MISSING` | 反問 | board_outline 或 component_heights 缺失 | next_question（仿 c01_next_question） | 回下一題，不生 source |
| `C02_VTD_DIMENSION_GUESS_BLOCKED` | 編排 | 嘗試在 wall/clearance 未提供時生 source | 「壁厚/間隙必須明確指定，系統不猜尺寸」 | 轉 gen_params 反問（wall/clearance/lid） |
| `C02_VTD_NOT_APPROVED` | 編排 approval gate | 約束齊備但 approve!=true | 回 ready-for-approval + 完整約束集 | 等使用者確認後再帶 approve=true 重呼 |
| `C02_VTD_RENDER_NO_GL` | 渲染 | worker 缺 EGL/GL | status=no-gl（沿用 ModelRenderResult） | 不造假圖；回報環境缺 GL（已於 DD-3 實作） |
| `C02_VTD_STL_EXPORT_UNAVAILABLE` | 編排→export_stl | worker 無 OpenSCAD CLI | status=stl_export_unavailable | fail-fast，不造假 STL（既有行為） |

## 不可違反原則

- 任何尺寸抽不到 → 轉反問，**永不臆測**（DD-2）。
- approval gate 未通過 → **永不自動生 CAD**（DD-4）。
- 渲染/匯出依賴缺失 → fail-fast 結構化回報，**永不造假輸出**。
