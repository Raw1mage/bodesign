# Errors: dsl_atopile-integration

錯誤分類即 `deficiency.kind` enum（data-schema.json）。所有錯誤走 fail-fast + 結構化缺項清單；**無任何自動降級路徑**。

## Error Catalogue

| kind | 觸發 | 回應內容 | 呼叫方（LLM）預期動作 |
|---|---|---|---|
| `compile_error` | `.ato` 語法錯誤、單位型別不符、未定義引用 | detail + source_anchor（file:line） | 修 `.ato` 原始碼後重呼叫 |
| `unsat_constraint` | assert 恆假或約束系統無解 | 違反的約束表達式 + source_anchor | 檢討設計參數或約束本身；不得放寬約束後靜默重試 |
| `pick_failure` | 選料來源無符合參數區間的零件 | 所需 spec_interval + 搜尋過的來源 | 調整參數區間、要求使用者補 vault、或經使用者同意改 component_source |
| `component_wrapper_missing` | vault 模式下該元件類無 `.ato` wrapper | 缺的元件類名 | 報告使用者；wrapper 擴充屬 implementing 增量工作 |
| `toolchain_missing` | ee 容器內 atopile 不可用（版本不符/未安裝） | 實測 `ato --version` 輸出 | 報告使用者；屬部署缺陷，非設計輸入問題 |
| `worker_unavailable` | ee worker 不可達（monolith 或 worker down） | 沿用既有 `_route_tool` 語義（retryable `worker_starting` 或 hard fail） | 等待 / 報告使用者；不得改走 compose_schematic 替代 |

## 錯誤處理原則

1. **一次回報全部缺項**：單次 build 的多個錯誤合併為一個 `deficiency[]`，不逐項擠牙膏。
2. **原始 log 不進回應主體**（DD-6）：`build_log_path` 落 workspace 供 debug。
3. **`ok=false` 且 `deficiencies=[]` 視為 bridge 自身缺陷**：解析器必須至少產出一筆（`kind=compile_error, detail=unparsed build failure` + log path）。
4. **不重試、不降級**：timeout 或 crash 一律 fail 給呼叫方；重試決策屬呼叫方（LLM/使用者），不屬工具層。
