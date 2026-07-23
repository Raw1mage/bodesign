# Design: eda-bridge_component-multi-fetch

## Context

`bodesign_component_fetch` 目前 handler（`services/mcp/server.py:529`）呼叫 `fetch_component(lcsc_id, output_lib, overwrite)`（`packages/eda-bridge/bodesign_eda_bridge/component_fetch.py:71`），一次一個 lcsc_id → 寫檔到磁碟。使用者踩到 opencode `batch` 工具拒收此 mutating 工具（正確安全閘），但料號批次抽取（BOM 場景）是真實需求。需在**工具自身**加原生多筆能力，與傳輸層 batch 無關。

## Goals / Non-Goals

**Goals**

- `component_fetch` 接受 `lcsc_ids[]`，順序迭代、continue-on-error、逐筆回報。
- 向後相容：既有 `lcsc_id` 單筆呼叫端不改。

**Non-Goals**

- 不改 opencode `batch` 傳輸層語義。
- 不引入併行（共用 CLI/output_lib 檔案競爭）。

## Decisions

- **DD-1: 新增 `fetch_components()` 包裝而非改寫 `fetch_component()`。** 單筆函式是既有穩定契約，多筆是純迭代複用；分離降低打擊半徑，單筆呼叫路徑零風險。
- **DD-2: continue-on-error 逐筆回報。** 某筆失敗不中斷其餘，回傳 `{ok, output_lib, fetched, failed, results:[{lcsc_id, ok, ...paths|reason}]}`。符合天條 no-fallback 顯式列缺項精神——一次看完全部缺口，而非第一筆掛就停。
- **DD-3: handler 層 lcsc_id XOR lcsc_ids。** `_h_component_fetch` 判斷：提供 `lcsc_ids` → 走 `fetch_components`；提供 `lcsc_id` → 走 `fetch_component`；兩者皆無或皆有 → fail-fast 顯式報錯（`must provide exactly one of lcsc_id / lcsc_ids`）。
- **DD-4: no-fallback 維持。** 每筆沿用 `fetch_component` 的既有 no-fallback（has_3d=false / ok=false），迭代層不吞不補。

## Risks / Trade-offs

- **順序迭代 N 筆逾時累積** — mitigation: 沿用單筆 90s timeout；N 大時由呼叫端分批，不在此層加總 timeout（顯式行為勝過隱式上限）。
- **同 output_lib 多筆寫入順序依賴** — mitigation: 順序迭代本身即序列化，overwrite 語義沿用單筆。

## Critical Files

- `packages/eda-bridge/bodesign_eda_bridge/component_fetch.py` — 新增 `fetch_components()` 迭代包裝。
- `services/mcp/server.py` — `_h_component_fetch` XOR 分派 + schema 加 `lcsc_ids`。
- `tests/test_component_fetch_multi.py` — 多筆語義測試（mock CLI）。
