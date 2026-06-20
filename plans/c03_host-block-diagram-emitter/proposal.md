# Proposal: c03_host-block-diagram-emitter

## Why

- bodesign 的 concept-diagram router (`skills/bodesign/SKILL.md` §"Concept-diagram router") 明令
  「**do not hand-author the SVG**」，且 c03-ee GUIDE (`stages/c03-ee/GUIDE.md:74`) 規定 EE 架構
  必須用 functional block diagram。但 router 目前只有三個 emitter：`c03_emit_partition_diagram`
  (board 切割)、`c01_emit_id_visual_package` (ID skeleton)、`drawmiat` (C4/IDEF0/Grafcet 軟體圖)。
- **缺口**：沒有任何 deterministic emitter 對應「**MCU/host-centric 放射狀功能方塊圖**」
  (center SoC + 周邊 block 放射，正交 bus 連線) —— 這正是 OpenMV N6 / aiguard host 架構圖的
  主形態。實務上（本次 thesmart_products aiguard 任務）只能**手刻 SVG**，直接違反 router 原則。
- 同時暴露兩個較小的文件缺口：(a) c01/c03 GUIDE 未明列「board-partition 屬 C03 而非 C01/C00」
  的責任邊界；(b) derived product 的「vs reference baseline 差異對照 + sourcing gates」是
  honesty model 的核心動作，但目前無模板/欄位承載，每次靠手寫。

## Original Requirement Wording (Baseline)

- "這節的工作要求與產出要求，有沒有值得蒸餾到 bodesign skill/tool 的地方" → 經盤點確認三個 gap，
  user 選擇 "#1+#2+#3 全做"，並指示 "在 bodesign repo 開 plan" + "不要自己做"（實作委派 subagent）。

## Requirement Revision History

- 2026-06-20: initial draft created via plan-init.ts
- 2026-06-20: scope 由盤點 thesmart_products aiguard C01→C03 功能方塊圖任務蒸餾而來，確認三項 gap。

## Effective Requirement Description

1. **新增 deterministic emitter** `bodesign_c03_emit_host_block_diagram`：將 host-centric MODEL
   (center_part + peripherals[{name, mpn?, side, bus?, type?}]) 投影成分層、可編輯 SVG，鏡像
   `emit_c03_partition_diagram` 的所有契約（named layers、fail-fast、placeholder 不靜默、
   honest-boundary footer 常開、deterministic byte-stable、cairosvg-gated PNG、docxmcp-gated PPTX）。
2. **reference-diff 能力**：emitter MODEL 支援 optional `reference_baseline`（name + diffs[]），
   在圖上以獨立 annotation layer 標示「derived-from / 與 baseline 的差異 / sourcing gates」；
   並在 partition/host-block 的文件模板新增固定 §"vs reference baseline" section。
3. **GUIDE 文字補強**：c01-id GUIDE 明列 board-partition / host block diagram 屬 C03 責任；
   c03-ee GUIDE 與 SKILL.md concept-diagram router 增列新 emitter 列，移除「需手刻」的隱性缺口。

## Scope

### IN
- `packages/workflow-core/bodesign_workflow_core/c03_host_block_diagram.py`（新檔，pure-python emitter）
- `bodesign_workflow_core/__init__.py` export 新 entry point
- `services/mcp/server.py` 新 handler + tool 註冊 (`bodesign_c03_emit_host_block_diagram`)
- `tests/test_c03_host_block_diagram.py`（新檔，鏡像 partition test pattern）
- `skills/bodesign/SKILL.md` concept-diagram router 增列 + `stages/c01-id/GUIDE.md`
  + `stages/c03-ee/GUIDE.md` 文字補強
- reference-diff：emitter MODEL 欄位 + 文件模板 section

### OUT
- 不改 `emit_c03_partition_diagram` 既有行為（只新增 sibling emitter，不重構）
- 不碰 docxmcp / pptx 插圖契約（本次 thesmart_products pptx RCA 屬 docxmcp territory，不蒸餾進 bodesign）
- 不回頭重畫 thesmart_products 既有手刻 SVG（那是已交付產出；本 plan 只讓未來不必手刻）
- 不動 c04/c05/c06 stage 或其他 emitter

## Non-Goals

- 不追求「自動從 netlist 推導 host 架構」——MODEL 仍由呼叫端提供（與 partition emitter 一致）
- 不產生 fab pinout / DRC-SI claim（honest-boundary footer 明示）

## Constraints

- **Determinism**：same MODEL → byte-stable SVG，no RNG（與 partition emitter 同一硬約束）
- **No silent fallback**（AGENTS.md 天條 #11）：缺 required 欄位 → status=missing + missing_fields；
  未知 peripheral type → named placeholder + 列入 placeholders[]，不靜默丟棄
- **Honest boundary 常開、不可參數化關閉**（鏡像 partition emitter DD-5）
- **Toolchain-gated raster**：PNG 經 cairosvg，缺則 png_rendered=false 且不列入 files（無 phantom）
- 實作由 coding subagent 執行；本 plan 階段只產 spec，不寫 code

## What Changes

- 新增一個 concept-diagram emitter，補齊 router 的 host-block 形態
- 兩份 GUIDE + SKILL router 表新增對應列與責任邊界文字
- 文件模板新增 reference-diff section

## Capabilities

### New Capabilities
- `c03_emit_host_block_diagram`: MCU/host-centric 放射狀功能方塊圖 deterministic SVG emitter
- `reference_baseline` diff annotation: derived-product 與 reference 差異 + sourcing gates 的結構化承載

### Modified Capabilities
- concept-diagram router: 由 3 個 emitter 形態擴為 4（補 host-block）
- c01/c03 GUIDE: 明確化 board-partition / host-block 的 stage 責任歸屬

## Impact

- 受影響 code：`packages/workflow-core/...`、`services/mcp/server.py`、`tests/...`
- 受影響 docs：`skills/bodesign/SKILL.md`、`stages/c01-id/GUIDE.md`、`stages/c03-ee/GUIDE.md`
- 受影響使用者：未來任何 C03 host 架構圖任務不再需要手刻 SVG（含 thesmart_products 後續 stage）
