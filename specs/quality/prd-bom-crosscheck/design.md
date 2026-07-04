# Design: quality_prd-bom-crosscheck

## Context

E2E 實證（`specs/validation/prd-to-gerber-e2e/`）使用者驗收發現 C04 交付物不履約：C00 PRD `main_components` 定義的恆流器件（NPN sink 或 AL5809-ish CC regulator）在 C04 板上完全缺席，電流控制淪為集合外的純電阻鎮流，且無任何 gate 攔截（`issues/BR_20260703_prd_bom_crosscheck_gap_cc_regulator_missing.md`，High）。四層驗證（ERC/DRC/crosscheck/SPICE）在 C00→C03 履約縫上是空的。本設計依 IDEF0 骨架（A1 結構化 → A2 netlist 解析 → A3 確定性比對 → A4 readiness 執法）補上這道 gate。

## Goals / Non-Goals

**Goals**

- C00 `main_components` ↔ C03 netlist 的逐項履約判定成為確定性、可重現的 gate。
- vault-absent 降級的落點決策從 LLM session 內裁定改為「允許集合比對 + 集合外一律等使用者」。
- E2E LED driver 案按裁決拓撲重做，成為合格基線板。

**Non-Goals**

- 不做 NLP 全自動解析 PRD 句子（結構化產物落盤供人工審計，錯誤可見可修）。
- 不改 `reference_crosscheck`（參考設計對照是另一層）。
- 不追溯歷史案件。

## Decisions

- DD-1: **結構化中間檔（manifest）承載履約契約。** LLM 只做一次上游抽取，把 `main_components` 句子轉成 `main_components_structured.json`（角色/數量/允許替代/比對 pattern），落盤在 C00 資料夾供人工審計；比對本身純確定性。拒絕方案：直接讓比對函數吃自然語句（把 LLM 埋進 gate，違「LLM 不參與驗證」哲學）。
- DD-2: **按角色（role）+ pattern + 數量比對，不按 MPN。** C00 階段 MPN 尚未解析（PRD 明言 exact MPNs resolved at C03 vault stage），gate 比對的是「這個電路角色有沒有器件落板」：pattern 對 netlist 的 value/footprint/lib-symbol 做大小寫不敏感正則匹配。拒絕方案：MPN 精確比對（C00 時點資訊不存在，必然全 missing）。
- DD-3: **Gate 落點 = C03 readiness、C04 入口。** 判定接進 C03 readiness 評估；BLOCKING 未清時 C04 工具鏈拒走。拒絕方案：放 C04 DRC 後（太晚，浪費佈線）；放 C00（netlist 還不存在）。
- DD-4: **替代批准是資料、不是對話。** manifest `approvals[]` 記錄使用者批准的替代（role、替代描述、批准語錄、日期）；比對函數看到集合外替代時查 approvals，有記錄 → `substituted (approved)` 非 BLOCKING，無記錄 → BLOCKING。批准寫入只能由使用者指示觸發（user-owned，同 plan_graduate 語意）。
- DD-5: **落地為 workflow-core pure function（core 側）。** 輸入兩個檔案路徑、輸出 dataclass 報告；不依賴 pcbnew/httpx，monolith 與 unittest 環境可跑。MCP 註冊走 server.py 慣例（handler `_h_*` + schema）。

## Risks / Trade-offs

- Pattern 匹配偽陽性（任何含 "regulator" 字樣的 value 都算 present）— mitigation：pattern 由抽取時生成且經人工審計；報告逐項列 matched_refs，誤配可見。
- manifest 與 PRD 修訂漂移 — mitigation：manifest 記 answer_state sha256；不符時報告 `manifest_stale: true` warn 要求重抽取。
- 角色數量語意模糊（"4x 0603 white LED"）— mitigation：schema 明確 `qty_min`，抽取時定值，比對按 `matched >= qty_min`。

## Critical Files

- `packages/workflow-core/bodesign_workflow_core/prd_bom_crosscheck.py` — 新增：pure function + report dataclass（本案核心）。
- `packages/workflow-core/bodesign_workflow_core/c00_prd_template.py:226` — `assess_c00_prd_readiness` 慣例參考；readiness 接線模式。
- `packages/eda-bridge/bodesign_eda_bridge/bom_export.py:43` — 既有 netlist 讀取慣例參考（L1 自帶輕量 S-expr parse，不依賴 eda-bridge）。
- `services/mcp/server.py` — `bodesign_prd_bom_crosscheck` handler + schema 註冊（tool count 測試同步）。
- `skills/bodesign/stages/c03-ee/GUIDE.md` — L2 降級協議 + gate 接線敘述。
- `experiments/e2e-led-driver/` — L3 重做產物與迴歸證據。
