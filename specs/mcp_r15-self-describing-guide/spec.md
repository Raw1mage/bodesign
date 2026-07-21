# Spec: mcp_r15-self-describing-guide

## Purpose

bodesign 作為 fleet MCP 標準 `mcp-integration-standard` 的 conformant service，保證其
完整 usage doctrine（C00–C07 organ coordination、cross-tool tradeoffs、pre-call
disciplines、counter-intuitive gotchas）以 **delivered context** 形式活在 portable MCP
surface 上——透過 `bodesign_init` tool 與 `prompts/get bodesign_init` 兩面同源投影，
並由 instructions signpost 在 action boundary 指路——而非仰賴 host-side prose 被模型
主動載入（R15 self-describing organism）。

## Requirements

### Requirement: Dual-protocol single-source usage guide (R15.1 / R15.5)

系統 SHALL 透過 `bodesign_init` MCP tool（`tools/call`）與 `prompts/get bodesign_init`
兩個 public MCP primitives，回傳 bodesign 完整 usage doctrine；二者 SHALL 從同一份
記憶體常數 `BODESIGN_GUIDE_DOCTRINE` 投影，回傳 byte-identical 文本（禁止手維護兩份）。
doctrine SHALL 於 server 啟動時自 `skills/bodesign/doctrine.md` 載入；檔案缺失或空
SHALL fail-fast 拒絕啟動（天條 11：無 doctrine 的 guide = no contract）。

#### Scenario: Tool-first agent fetches doctrine

- **WHEN** 客戶端呼叫 `tools/call bodesign_init`
- **THEN** server 回傳 `{ok:true, doctrine:<full text>, source}`，doctrine 涵蓋 R15.2 四類

#### Scenario: Bare prompts client fetches same doctrine

- **WHEN** 客戶端呼叫 `prompts/get bodesign_init`
- **THEN** 回傳的 PromptMessage 文本與 tool 回傳的 doctrine byte-identical

#### Scenario: Doctrine source missing at startup

- **WHEN** container 內 `skills/bodesign/doctrine.md` 缺失或空
- **THEN** server 於啟動時 raise `DOCTRINE_SOURCE_MISSING` / `DOCTRINE_SOURCE_EMPTY` 並拒絕 boot

### Requirement: Service-authored signpost (R15.3)

系統 SHALL 於 `mcp.json.instructions` 與 server `INSTRUCTIONS` 常數各載一句 signpost，
宣告 guide surface 存在並指向 `bodesign_init`。此 SHALL 為 service-authored manifest
宣告，SHALL NOT 為 host-side conversational nudge 或 `<system-reminder>` 注入（天條 2）。

#### Scenario: Client bootstrap sees signpost

- **WHEN** 客戶端呼叫 `initialize`
- **THEN** 回傳的 `instructions` 含 `USAGE GUIDE: ... call bodesign_init ...` signpost 句

## Acceptance Checks

- [x] `tools/call bodesign_init` 回傳完整 doctrine（`{ok, doctrine, source}`）
- [x] `prompts/get bodesign_init` 回傳 byte-identical doctrine（live 驗證 11872 chars 相同）
- [x] doctrine.md 涵蓋 R15.2 四類（cross-tool tradeoffs / pre-call disciplines / organ coordination / gotchas）
- [x] `initialize.instructions` 與 `mcp.json.instructions` 皆含 R15.3 signpost
- [x] 缺 doctrine.md → container 啟動 fail-fast（live 驗證）
- [x] guide tool annotations `readOnlyHint:true, openWorldHint:false`
- [x] drift 檢查：改 doctrine.md → 重啟 → tool 即反映（single-source 證實）
