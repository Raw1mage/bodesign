# Tasks: mcp_r15-self-describing-guide

## 1. Doctrine one-source 投影機制（R15.5）

- [ ] 1.1 決定 doctrine source 形態：直接用 `skills/bodesign/SKILL.md`，或抽核心 doctrine 段成獨立檔（依 SKILL.md 實際長度/章節，記錄為 DD-2a）
- [ ] 1.2 server 啟動時載入 doctrine 檔到記憶體常數；缺檔/空檔 fail fast（DD-3，天條 11）
- [ ] 1.3 確認 `Dockerfile` COPY `skills/` 進 image，container 內 doctrine 檔存在

## 2. bodesign_init tool（R15.1 tool 面）

- [ ] 2.1 在 `services/mcp/server.py` 註冊 `bodesign_init` tool，annotations `{readOnlyHint:true, destructiveHint:false, idempotentHint:true, openWorldHint:false}`（DD-5）
- [ ] 2.2 guide tool 回傳載入的 doctrine（TextContent + 可選 structuredContent）；確認涵蓋 R15.2 四類（cross-tool tradeoffs / pre-call disciplines / organ coordination / gotchas）

## 3. prompts/get guide handler（R15.1 prompts 面，需新建）

- [ ] 3.1 在 `services/mcp/server.py` **新建** `prompts/list`+`prompts/get` handler（bodesign 現無），加入 `bodesign_init`（或 `usage`）entry。範本：docxmcp `bin/mcp_server.py`（DD-6）
- [ ] 3.2 prompts entry 回傳與 guide tool **byte-identical** 的同源 doctrine（DD-1 驗證）

## 4. Signpost（R15.3）

- [ ] 4.1 server instructions 常數補 R15.3 signpost 句（DD-4 措辭）
- [ ] 4.2 `mcp.json.instructions` 補同一 signpost 句

## 5. 驗證與收斂

- [ ] 5.1 rebuild bodesign container，live smoke：`bodesign_init` tool 可呼叫回 doctrine；`prompts/get bodesign_init` 回同源 doctrine；instructions 含 signpost
- [ ] 5.2 對照 `specs/mcp-integration-standard` §13 checklist R15.1/R15.2/R15.3/R15.5 逐項自檢通過
- [ ] 5.3 drift 檢查：guide/prompts/SKILL.md 三者同源（改 SKILL.md 後 guide 隨之變）
- [ ] 5.4 event_record 收尾（Key Decisions / Verification / Remaining）；回填 opencode standard §14 downstream 狀態
