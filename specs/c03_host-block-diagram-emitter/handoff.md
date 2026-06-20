# Handoff: c03_host-block-diagram-emitter

## Execution Contract

執行者為 **coding subagent**（user 明確指示「不要自己做」）。orchestrator 負責規劃、派工、審查、event log；
不親手寫 emitter / test / skill 檔。

## Required Reads

1. `packages/workflow-core/bodesign_workflow_core/c03_partition_diagram.py`（鏡射範本，全檔 586 行）
2. `tests/test_c03_partition_diagram.py`（test 鏡射範本）
3. `services/mcp/server.py` line 365 + 935（handler + tool 註冊範本）
4. 本 package 的 `spec.md` / `design.md` / `data-schema.json` / `test-vectors.json` / `tasks.md`

## Stop Gates In Force

- **不得**修改 `emit_c03_partition_diagram` 既有行為（只新增 sibling，partition test 必須仍全綠）。
- **不得**引入 RNG / 任何 silent fallback（缺欄位 fail-fast、未知 type → named placeholder）。
- honest-boundary footer 常開、不可參數化關閉。
- 若放射狀 layout 演算法遇到 spec 未涵蓋的 edge case（如四側皆 0、bus 路徑必交叉），
  先在 design.md Risks 對應條目記錄抉擇，不擅自擴張 scope。

## Execution-Ready Checklist

- [ ] Phase 1 emitter 全部 `_draw_*` + validate + layout + entry point 完成
- [ ] Phase 2 server handler + tool 註冊
- [ ] Phase 3 test 覆蓋 test-vectors 全 8 case + partition test 回歸綠
- [ ] Phase 4 SKILL.md router + 2 GUIDE 文字
- [ ] Phase 5 server 列出新 tool + TV1 實跑 + event log + .state.json

## Validation Plan

```bash
cd /home/pkcs12/projects/bodesign
python3 -m pytest tests/test_c03_host_block_diagram.py tests/test_c03_partition_diagram.py -v
# determinism: emit TV1 twice to different folders, diff the two SVGs (must be byte-identical)
# server: mcpctl.sh + GET /tools | grep bodesign_c03_emit_host_block_diagram
```
