# Observability: knowledge_datasheet-spice-models

本 plan 全部表面是同步函式呼叫 + MCP 工具，無常駐服務；observability 聚焦於**結構化回傳值、provenance 落點、與可追溯 artifact**，而非 metrics/alerts。

## Events

本 plan 無常駐事件流；「事件」= 結構化回傳值與 ValidationEvidence envelope（`tool="spice"`，回流 spine `_orchestration/evidence_returns/`，沿用 P3 既有機制）。以下為觀測主面。

## 結構化回傳（觀測主面）

| 表面 | 回傳 | 可觀測訊號 |
|---|---|---|
| `ingest_spice_extraction` | `IngestReport{written[], rejected[], not_found[]}` | 每 row 的去向完整可見：寫入幾筆（含 spec_value_id）、拒絕幾筆（含 SPX 碼 + detail）、幾筆不可得 |
| `generate_model_card` | `ModelCard{card_text, provenance[], smoke}` 或 SPX 例外 | provenance 每參數一筆（field_path / sha / page / trust / value_kind）；失敗時 payload 列缺項或歧義 rows |
| `materialize_model_cards` | per-card 結果列表（written / SPX_SMOKE_FAILED / skipped） | manifest entry 含 smoke 狀態與 provenance_summary |
| `simulate_schematic` | `SimResult.results[].model_source` | 每子電路 model 來源確定性標注（grounded vs generic） |
| MCP `bodesign_spice_model_card` | ModelCard JSON / 結構化錯誤 | run_tool 包裝層保留 code + payload 透傳 |

## Metrics

無常駐 metrics 基礎設施；以下計數由結構化回傳承載，可由呼叫端／測試聚合（人工巡檢條件）：

| 計數 | 來源 | 巡檢意義 |
|---|---|---|
| written / rejected / not_found 數 | `IngestReport` | rejected 比例異常高 → 抽取品質或 evidence 管線問題 |
| SPX_PARAMS_MISSING 缺項 field_path 分布 | 生成例外 payload | 高頻缺項 → 抽取目標 schema 或 datasheet 覆蓋缺口 |
| smoke pass / fail / skipped 比例 | materialize 回傳 + manifest | fail 比例高 → 模板 bug 或參數異常；skipped 多 → 環境缺 ngspice |
| model_source 分布（grounded vs generic） | `SimResult.results[]` | grounded 覆蓋率 = 本 plan 的價值量測 |

## 持久 artifact（事後可稽核）

| Artifact | 位置 | 內容 |
|---|---|---|
| L4 audit rows | component-kb sqlite `audit` 表（既有 `_audit()` 機制） | 每筆 spice_model.* 寫入的 insert 紀錄 + evidence_ref |
| model 卡檔 | `<project>/spice/models/<MPN>.sub` | 卡頭 provenance 註解（`* source: <sha8>:p<page> trust=<level>` 每參數一行）——卡本身就是可稽核文件 |
| manifest | `<project>/spice/models/manifest.json` | source=vault-grounded、smoke 狀態、provenance_summary |
| smoke testbench + log | `<project>/spice/models/.smoke/<MPN>/`（暫定） | 失敗時保留 testbench 與 ngspice stderr 供 debug |
| ValidationEvidence | spine `_orchestration/evidence_returns/` | `tool="spice"` envelope（沿用 P3 機制），raw_result 保留 |

## 日誌慣例

- 模組內不引入新 logging framework；沿用 component-kb / eda-bridge 現有風格（回傳值承載資訊，例外承載失敗）。
- smoke 執行的 ngspice stdout/stderr 截斷保留於 SPX_SMOKE_FAILED payload（≤500 chars）與 `.smoke/` 目錄（完整）。

## Debug checkpoints（實作期 instrumentation plan）

1. **ingest 邊界**：進（rows JSON）/ 出（IngestReport）——fixture 測試直接斷言
2. **L4 查詢邊界**：`generate_model_card` 的參數查詢結果（含 value_kind 分布）——SPX_PARAMS_AMBIGUOUS payload 即此 checkpoint 的外顯
3. **模板渲染邊界**：card_text byte-identical 斷言（兩次生成 diff）
4. **cascade 命中邊界**：spice skill 是否讀到 manifest——以 fixture 專案跑 `simulate_subcircuits.py` 觀察其 model resolution 輸出（R-A 風險的驗證點）
5. **標注邊界**：SimResult.model_source 與 manifest 內容一致性斷言
