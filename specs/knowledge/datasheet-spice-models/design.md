# Design: knowledge_datasheet-spice-models

## Context

- bodesign 第 3 層驗證 = `simulate_schematic`（`packages/eda-bridge/bodesign_eda_bridge/simulate.py`）：薄編排 kicad analyzer → spice skill `simulate_subcircuits.py`（ngspice）。
- spice skill 已有 **model resolution cascade**（`spice_model_cache.py`）：① project `spice/models/` + manifest → ② lookup table → ③ API parametric → ④ datasheet extraction JSON → ⑤ PDF regex → ⑥ ideal/generic fallback。**第 ① 位就是本 plan 的注入點**——skill 不需改動（OUT scope），只要把 vault-grounded model 卡物化到 `<project>/spice/models/` + manifest，cascade 自然優先命中。
- vault L4 = `spec_values` EAV（`packages/component-kb/bodesign_component_kb/repository.py`）：`field_path` registry + `resolve_field_path()` fail-fast（unknown path 拋錯帶 nearby candidates）；`trg_spec_verified_needs_evidence` trigger 強制 verified 需 evidence。
- `vault.py` 另有 datasheets-skill 端的 `lookup()`/`spec_check()`（manifest-based 抽取 JSON 查詢），與 repository 的 sqlite EAV 是兩個查詢面；本 plan 的 model 卡參數源 = **repository EAV**（trust/evidence 機制在那裡）。

## Goals / Non-Goals

### Goals

- L4 `spice_model.*` 命名空間（diode / ldo / passive 第一批）
- 抽取入庫契約（per-row evidence 驗證、not_found 顯式）
- 確定性 model 卡生成器（fail-fast 缺項清單、provenance 註解、byte-identical）
- 物化到 project `spice/models/` + manifest → cascade ① 命中
- SimResult 增加 `model_source` 標注；smoke 驗證 + ValidationEvidence 回流

### Non-Goals

- 不改 spice skill（host 側）；不做 curve fitting / 廠商 model 下載 / RF model（proposal OUT）

## Decisions

- **DD-1 落點 = `packages/component-kb/bodesign_component_kb/spice_card.py`（新模組）**。model 卡是 L4 的 derived artifact；eda-bridge 只負責物化呼叫與來源標注（薄消費）。已由使用者 scope 決策確認。
- **DD-2 注入點 = spice skill cascade 第 ① 位（project `spice/models/` + manifest），不動 skill 程式碼**。物化函式 `materialize_model_cards(project_dir, mpns, repo)` 寫卡檔 + 更新 manifest.json；manifest entry 帶 `source="vault-grounded"` 與 provenance 欄位。skill 既有 cascade 讀到就用——零 skill 改動，相容性風險最低。
- **DD-3 `spice_model.*` field roots（v1 封閉清單）**：
  - `spice_model.diode.{is_a, n, rs_ohm, cj0_f, bv_v, ibv_a}`（必要：is_a, n）
  - `spice_model.ldo.{vout_v, dropout_v, iout_max_a, iq_a, psrr_db}`（必要：vout_v, dropout_v, iout_max_a）
  - `spice_model.passive.{esr_ohm, esl_h, c_f, l_h, r_ohm}`（必要視類別：C 需 c_f，L 需 l_h，R 需 r_ohm；寄生選配但有就進卡）
  - 沿用 EAV：同 field 可多 row（min/typ/max + condition）；model 卡取 **typ**，無 typ 取唯一值，多值無 typ → `SPX_PARAMS_AMBIGUOUS` fail-fast（不自行平均）。
- **DD-4 抽取入庫 API = `ingest_spice_extraction(repo, mpn, rows) -> IngestReport`**，per-row 驗證：field_path 在 registry、evidence 含 document sha256 + page、value 數值合法。缺 evidence → 該 row 拒絕（`SPX_EVIDENCE_MISSING`），其餘照寫；`not_found` rows 只記入 report.not_found[]，不落 DB。全部寫 `trust='unverified'`。
- **DD-5 model 卡模板 = 純 f-string 確定性模板，每類別一個 generator 函式**（`_card_diode` / `_card_ldo` / `_card_passive`）。輸出 dataclass `ModelCard{mpn, category, card_text, provenance[], missing[], smoke}`。provenance 註解寫進卡檔頭（`* source: <sha8>:p<page> trust=<level>` 每參數一行）；不含時間戳（byte-identical 約束）。LDO 行為級模板借鏡 spice skill `generate_ldo_model` 的介面形狀但獨立實作（skill 是 host 側，不 import）。
- **DD-6 錯誤碼命名空間 `SPX_*`**：`SPX_EVIDENCE_MISSING`、`SPX_PARAMS_MISSING`（payload 帶缺項 field_path 清單 + 修復指引「補抽取這些參數」）、`SPX_PARAMS_AMBIGUOUS`、`SPX_SMOKE_FAILED`、`SPX_CATEGORY_UNSUPPORTED`。全走既有 fail-fast 錯誤慣例（結構化 payload，不 silent fallback）。
- **DD-7 smoke = ngspice batch DC op**：把卡 + 最小 testbench（類別對應：diode 串 1V/1k、LDO 接額定 vin/負載、passive 接 AC 源）丟 `ngspice -b`，exit 0 且無 `Error` 行 = pass。fail 的卡**不寫入 manifest**（cascade 不可見）；無 ngspice → `skipped-no-simulator` 顯式記在 manifest entry。
- **DD-8 SimResult 擴充 `model_source`**：`simulate.py` 讀 spice skill 報告時，比對子電路元件 MPN 是否命中 project manifest 的 vault-grounded entries → 每個 result dict 加 `model_source: "vault-grounded" | "generic-default"`。判定確定性（manifest 查表），不猜。
- **DD-9 MCP 工具 = `bodesign_spice_model_card`**（`services/mcp/server.py`，走既有 run_tool 包裝層）：args = `{folder, mpn, category, materialize?: bool}`；回傳 ModelCard JSON（含 card_text、provenance、smoke 狀態）；`materialize=true` 時寫入 project `spice/models/`。錯誤碼透傳。

## Risks / Trade-offs

- **R-A spice skill manifest 格式漂移**：cascade ① 讀 manifest.json 的鍵名若 skill 升級改變，物化卡會失配。緩解：fixture 鎖定現行格式（`spice_model_cache.py` 已讀過確認），測試覆蓋 manifest round-trip。
- **R-B LDO 行為級模板精度**：第一階近似（dropout + 限流），不模擬瞬態響應。卡上明示限制聲明（proposal Non-Goal），不宣稱超過能展示的。
- **R-C typ 選值規則過嚴**：部分 datasheet 只給 min/max。`SPX_PARAMS_AMBIGUOUS` 會擋住——這是刻意的 fail-fast；修復指引提示使用者以 condition 標注或補 typ 值。不自動取中點。

## Critical Files

- `packages/component-kb/bodesign_component_kb/repository.py` — FIELD_PATH_ROOTS / FIELD_ALIASES 擴充（spice_model.*）
- `packages/component-kb/bodesign_component_kb/spice_card.py` — 新模組：ingest_spice_extraction、generate_model_card、materialize_model_cards、smoke
- `packages/eda-bridge/bodesign_eda_bridge/simulate.py` — SimResult.model_source 標注
- `services/mcp/server.py` — `bodesign_spice_model_card` 工具
- `tests/` — fixture 測試（contract / 生成 / fail-fast / 標注 / smoke 三態）
