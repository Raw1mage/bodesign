# Proposal: eda-bridge_component-multi-fetch

## Why

- 使用者觀察到 opencode 的 `batch` 工具拒收 `bodesign_component_fetch`（"not batch-eligible ... mutating or undeclared — call it directly"）。這是**正確安全閘**，非 bug：`component_fetch` 寫檔到磁碟（symbol/footprint/STEP 落進 `output_lib`），是 mutating 工具；opencode `batch` 只把 `readOnlyHint=true` 的 MCP 工具放進順序 lane。
- 但使用者直覺指向另一件事：`component_fetch` **應用層天生適合批次**——一張 BOM 幾十個料號，一次拉 N 個 `lcsc_id` 是常態。目前每料號一次獨立 MCP 呼叫，冗長。
- 兩個「batch」是不同概念：opencode `batch` **工具** = 省 round-trip（傳輸層，不適用 mutating 工具）；本提案 = **工具自身接受陣列**（應用層，server 內部順序迭代）。

## Original Requirement Wording (Baseline)

- "batch.ts呼叫到這個功能會報錯。但我覺得這個tool好像原生就適合batch處理。"

## Requirement Revision History

- 2026-07-07: initial draft created via plan-init.ts
- 2026-07-07: 決策定案 — continue-on-error 逐筆回報 + lcsc_id XOR lcsc_ids 共存

## Effective Requirement Description

1. **R1** schema 新增 `lcsc_ids: string[]`，與既有 `lcsc_id: string` **XOR 共存**（必須提供其一），向後相容——現有單筆呼叫端不改。
2. **R2** 多筆走**順序迭代**（非併行）：共用 easyeda2kicad CLI 與 `output_lib`，併行會檔案競爭。
3. **R3** **continue-on-error**：某筆失敗（vendor 無此件 / CLI 錯 / 逾時）不中斷其餘，逐筆回報 `results[]`，彙總 `fetched`/`failed`。
4. **R4** **no-fallback 維持**：某筆 vendor 無 STEP → `has_3d=false`；某筆 CLI 缺 → 該筆 `ok=false`，如實回報，絕不補假模型。

## Scope

### IN
- `packages/eda-bridge/bodesign_eda_bridge/component_fetch.py`：新增 `fetch_components(lcsc_ids, output_lib, overwrite)` 迭代包裝（複用 `fetch_component`）。
- `services/mcp/server.py`：`_h_component_fetch` 支援 `lcsc_id` XOR `lcsc_ids`；schema 加 `lcsc_ids`。
- `tests/`：多筆語義測試（成功、部分失敗 continue-on-error、XOR 驗證）。

### OUT
- 不動 opencode `batch` 工具語義（傳輸層，與此無關）。
- 不引入併行（順序迭代是正解）。
- 不改 `search_components`。

## Non-Goals

- 不讓 mutating 工具變成 opencode batch-eligible（不宣告假 readOnlyHint）。

## Constraints

- 天條 no-fallback / no-fabrication：逐筆缺項如實回報。
- 順序迭代（檔案競爭風險）。

## What Changes

- `component_fetch.py` 加多筆迭代函式；`server.py` handler + schema 支援陣列輸入。

## Capabilities

### New Capabilities
- 多筆 fetch：一次呼叫拉 N 個 lcsc_id，逐筆 continue-on-error 回報。

### Modified Capabilities
- `bodesign_component_fetch`：schema 由「僅 lcsc_id」擴為「lcsc_id XOR lcsc_ids」，回傳在多筆模式下帶 `results[]` + `fetched`/`failed` 彙總。

## Impact

- `packages/eda-bridge/bodesign_eda_bridge/component_fetch.py`
- `services/mcp/server.py`（handler + schema）
- `tests/`
- `specs/architecture.md`：component fetch 能力描述（若需）
