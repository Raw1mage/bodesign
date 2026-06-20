# Handoff: c03_partition-diagram-emitter

## Execution Contract

實作 `c03_emit_partition_diagram` emitter——把板級分割 MODEL 投影成分層 breakout 圖。對齊既有 `emit_c01_id_visual_package` 範式（同類 emitter）。MVP 只吃顯式 JSON MODEL，ICD 自動解析留階段 2。

## Required Reads

- `plans/c03_partition-diagram-emitter/design.md`（DD-1..DD-10、Critical Files、Code Anchors）
- `plans/c03_partition-diagram-emitter/data-schema.json`（PartitionModel / EmitPartitionResult 契約）
- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py`（emitter 範式：分層 SVG、preview/png gating、placeholder 不靜默）
- `services/mcp/server.py:251`（`_h_c01_emit_id_visual_package` handler 範式）、`server.py:840`（c01 schema 條目範式）
- 參考藍本：手做 `gen_breakout.py` / `gen_breakout_pptx.py`（資料/繪圖分離演算法）

## Stop Gates In Force

- **MODEL 缺欄位**：缺 board.role / interconnect.class / interconnect.dir → 回 missing + 缺項清單，**不產圖、不以預設值續跑**（天條）。
- **PNG/PPTX toolchain 缺失**：誠實標 unavailable，不偽造、不列 phantom files。
- **architecture.md 邊界變更**：新增 emitter 模組，收尾前同步。
- 任何需要破壞既有工具行為的改動 → 先停下確認（本 plan 純新增，預期不觸發）。

## Execution-Ready Checklist

- [x] design / data-schema / sequence / idef0 / grafcet 完成且驗證
- [x] emitter 範式（c01）已定位
- [x] core/worker 邊界明確（workflow-core，PNG/PPTX toolchain-gated）
- [x] 參考藍本可循（gen_breakout）
- [ ] 實作依 tasks.md phase 1→7 順序

## Boundaries / Notes

- **歸屬 workflow-core**（DD-1），非 eda-bridge——純 deterministic SVG，不觸 KiCad toolchain。
- **資料/繪圖分離**（DD-2）：PartitionModel dict → `_draw_*` 純函式 → emit 入口。
- **honest-boundary 不可關閉**（DD-5）：三條固定 annotations 程式自動帶。
- **確定性**（DD-9）：相同 MODEL → byte-stable SVG，無 RNG。
- PYTHONPATH 跑測試需含所有 package 子目錄（repo 慣例）；`python3` 非 `python`。
