# Tasks: mcp_r15-self-describing-guide

## 1. Doctrine one-source 投影機制（R15.5）

- [x] 1.1 決定 doctrine source 形態：DD-2a → author condensed `skills/bodesign/doctrine.md`（Dockerfile 刻意不 COPY 原始 skills/ 樹；比照 docxmcp doctrine.md pattern）
- [x] 1.2 server 啟動時載入 doctrine 檔到記憶體常數 `BODESIGN_GUIDE_DOCTRINE`；缺檔/空檔 fail fast（DD-3，天條 11；已 live 驗證 container 因缺檔正確拒絕啟動）
- [x] 1.3 `Dockerfile` COPY `skills/bodesign/doctrine.md` 進 image；dev overlay 補 targeted bind-mount（3 services），container 內 doctrine 檔存在

## 2. bodesign_init tool（R15.1 tool 面）

- [x] 2.1 `services/mcp/server.py` 註冊 `bodesign_init` tool（TOOLS 首位），annotations `{readOnlyHint:true, destructiveHint:false, idempotentHint:true, openWorldHint:false}`（DD-5）；list_tools 傳 ToolAnnotations；run_tool in-process 分派
- [x] 2.2 guide tool 回傳載入的 doctrine（`{ok, doctrine, source}`）；doctrine.md 涵蓋 R15.2 四類（§1 cross-tool tradeoffs / §2 pre-call disciplines / §3 organ coordination / §5 gotchas）

## 3. prompts/get guide handler（R15.1 prompts 面，需新建）

- [x] 3.1 `services/mcp/server.py` build_server() **新建** `list_prompts`+`get_prompt` handler（bodesign 原無），加入 `bodesign_init` entry（DD-6，範本 docxmcp）；capabilities.prompts live 確認
- [x] 3.2 prompts/get 回傳與 guide tool **byte-identical** 的同源 doctrine（live 驗證 11872 chars 完全相同，DD-1）

## 4. Signpost（R15.3）

- [x] 4.1 server INSTRUCTIONS 常數補 R15.3 signpost 句（DD-4 措辭）；live initialize.instructions 確認含 USAGE GUIDE
- [x] 4.2 `mcp.json.instructions` 補同一 signpost 句

## 5. 驗證與收斂

- [x] 5.1 dev restart + live smoke（UDS）：`bodesign_init` tool 回 doctrine；`prompts/get bodesign_init` 回同源；initialize.instructions 含 signpost；3 services healthy
- [x] 5.2 對照 `specs/mcp-integration-standard` §13 checklist：R15.1 (tool+prompts 雙面同源✓ readOnlyHint✓) / R15.2 (四類涵蓋✓) / R15.3 (instructions signpost✓ service-authored) / R15.5 (單一 source doctrine.md 投影✓) 逐項通過
- [x] 5.3 drift 檢查：改 doctrine.md → 重啟 → tool 即反映 marker → 還原（single-source 證實）
- [x] 5.4 event_record 開場+收尾已寫；Architecture Sync 完成（specs/architecture.md line 11）。opencode standard §14 downstream 狀態回填留待 graduate 時
