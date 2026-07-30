# Spec: mcp_r16-domain-kb

## Purpose

保證 bodesign 的任何 MCP 用戶（本機 UDS 或遠端 TCP client agent）能在設計工作中以確定性檢索查到 repo 的 ragbase 領域知識庫，且該路徑唯讀、fail-fast、與 host-side specbase 讀取同一個 store——實現 mcp-integration-standard R16 的 reference impl。

## Requirements

### Requirement: In-band KB query（R16.2）

系統 SHALL 提供 `bodesign_kb_query(q, type?, limit?)` MCP 工具：對 `.specbase/ragbase.sqlite` 的知識物件做確定性 FTS 檢索（trigram tokenizer；全 token ≥3 碼點走 FTS、全 <3 走 LIKE scan、混合走 hybrid），回傳 `{hits:[{id,type,title,score,confidence,source_weight}], matchMode, total}`；並提供 `bodesign_kb_get(id)` 回單一物件全文（body_md + provenance）。兩工具皆標註 read-only 語義。

#### Scenario: 遠端 agent 查 EMC 準則

- **WHEN** MCP client（透過 `mcp.json` 宣告的 UDS，或 gateway 前置的 HTTP）呼叫 `bodesign_kb_query(q="EMC decoupling")`
- **THEN** 回傳含 `control.pcb.emc-decoupling-placement` 等既有蒸餾物件的 hits，payload 帶 `matchMode:"fts"`，每筆 hit 帶 confidence 與 source_weight

#### Scenario: 短 CJK 查詢降級自述

- **WHEN** 呼叫 `bodesign_kb_query(q="佈線")`（全 token <3 碼點）
- **THEN** 走 LIKE scan 並在 payload 明示 `matchMode:"like-scan"`，0-hit 時 caller 可分辨「降級查詢無命中」而非「無知識」

### Requirement: Read-only serving + fail-fast（R16.4 / 天條 1）

serving 端 SHALL 以 `mode=ro` + `PRAGMA query_only=ON` 開啟 KB；MCP surface SHALL NOT 暴露任何 KB 寫入工具。KB 檔不存在或不可開 SHALL 回 typed error `KB_UNAVAILABLE`（含 remedy 行指向 host-side 蒸餾路徑），不得回靜默空結果。

#### Scenario: KB 檔缺失

- **WHEN** 容器內 `BODESIGN_KB_DB` 指向的檔案不存在
- **THEN** `bodesign_kb_query` 回 `KB_UNAVAILABLE: ...` + `remedy:` 行，isError=true

### Requirement: One KB, two doors（R16.7）

容器內工具與 host-side `gate.ts ragbase_query` SHALL 讀同一個 `.specbase/ragbase.sqlite`（bind mount，非複本）；同一查詢字串在兩個門的命中物件集合 SHALL 一致（排序分數容許實作差異）。

#### Scenario: 兩門一致

- **WHEN** host 端 `gate.ts ragbase_query --arg q="clearance voltage"` 與容器內 `bodesign_kb_query(q="clearance voltage")` 先後執行
- **THEN** 兩者命中相同 object id 集合

### Requirement: Recall-first signpost（R16.5）

`mcp.json` instructions SHALL 含一句 KB 宣告（查詢工具名 + 何時用）；判斷密集工具（emit_layout / analyze_emc / si_check / simulate / layout_drc_gate 等）的 description SHALL 帶 `consider: bodesign_kb_query` affordance。

#### Scenario: 冷啟動 agent 發現 KB

- **WHEN** 全新 MCP client 讀取 bodesign manifest instructions
- **THEN** 看到 KB 宣告句，知道設計判斷前可先 `bodesign_kb_query`

## Acceptance Checks

- [ ] `bodesign_kb_query("EMC decoupling")` 由 MCP rail 回傳 ≥1 筆既有蒸餾物件，payload 含 matchMode
- [ ] `bodesign_kb_get` 回傳 body_md + confidence + source 資訊
- [ ] 短 token 查詢 payload `matchMode:"like-scan"`
- [ ] KB 檔缺失 → `KB_UNAVAILABLE` typed error + remedy 行（測試以暫時改 env 驗證）
- [ ] 兩門一致性：同 query 在 gate.ts 與 MCP 工具命中相同 id 集合
- [ ] MCP surface 無任何 KB 寫入工具；serving connection query_only
- [ ] instructions 含 signpost；≥5 個判斷密集工具 description 帶 consider 行
- [ ] 既有測試套件不回歸；新測試全綠
