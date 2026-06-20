# Tasks: c03_host-block-diagram-emitter

> 執行由 coding subagent 進行（user 指示「不要自己做」）。本清單為可委派的 phase 切片。

## 1. Emitter 核心（pure-python）

- [x] 1.1 新建 `packages/workflow-core/bodesign_workflow_core/c03_host_block_diagram.py`，
      鏡射 `c03_partition_diagram.py` 結構：`HostBlockModel` + `EmitHostBlockResult` dataclass
- [x] 1.2 `_validate_model`：fail-fast（center_part.name / peripherals 非空 / 每 peripheral name+side；
      side enum 檢查，非法值回 `peripherals[i].side(invalid:<v>)`）
- [x] 1.3 `_layout`：deterministic 放射狀佈局（center 置中；peripherals 依 side 分組、組內宣告順序）
- [x] 1.4 `_draw_center` / `_draw_peripherals` / `_draw_buses` / `_draw_legend` / `_draw_honest_boundary`
      五層 named groups；未知 type → dashed placeholder + placeholders[]
- [x] 1.5 `reference_baseline` annotation：有則渲染 derived-from + diffs + sourcing_gates；無則不渲染
- [x] 1.6 `emit_c03_host_block_diagram` entry point + cairosvg-gated PNG + docxmcp-gated PPTX（無 phantom）
- [x] 1.7 `__init__.py` export 新 entry point

## 2. MCP server 註冊

- [x] 2.1 `services/mcp/server.py` 新增 `_h_c03_emit_host_block_diagram` handler（範本 line 365）
- [x] 2.2 註冊 tool `bodesign_c03_emit_host_block_diagram` + 完整 description（範本 line 935）

## 3. 測試

- [x] 3.1 新建 `tests/test_c03_host_block_diagram.py`，覆蓋 test-vectors.json 全部 8 個 case
      （valid-full / missing-center / empty-peripherals / invalid-side / placeholder /
      determinism / no-baseline / lopsided）
- [x] 3.2 跑 `python3 -m pytest tests/test_c03_host_block_diagram.py tests/test_c03_partition_diagram.py`
      全綠（確認未破壞 partition emitter）

## 4. Skill 文件同步

- [x] 4.1 `skills/bodesign/SKILL.md` concept-diagram router 表增列 host-block emitter（約 line 130-140）
- [x] 4.2 `skills/bodesign/stages/c01-id/GUIDE.md` 明列 host-block / board-partition 屬 C03 責任
- [x] 4.3 `skills/bodesign/stages/c03-ee/GUIDE.md` block-diagram 段落指向新 emitter（約 line 74，移除手刻隱含）

## 5. 驗證與收尾

- [x] 5.1 server 啟動後確認 `bodesign_c03_emit_host_block_diagram` 可列出（mcpctl 或 GET /tools）
- [x] 5.2 用 TV1 (aiguard MODEL) 實跑一次，肉眼確認 SVG 合理（可選：對照本次手刻版）
- [x] 5.3 event log + 更新 .state.json
