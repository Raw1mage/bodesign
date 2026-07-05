# Handoff: capability_refs-first-emitters

## Execution Contract

- 交付：provenance 基建 + C01/C02 emit gate + readiness provenance gate + BR §5 三條驗收測試全綠 + 全 suite 回歸綠。
- Done 定義：tasks.md 全勾、`tests/test_refs_first_emitters.py` 通過、既有 c01/c02 測試補 fixture 後綠、無新增 silent fallback。

## Required Reads

- `plans/capability_refs-first-emitters/design.md`（DD-1~DD-7 為約束性決策）
- `packages/workflow-core/bodesign_workflow_core/refs_gate.py`（既有 chokepoint，勿重造）
- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py:256/429/777/891`
- `packages/workflow-core/bodesign_workflow_core/c02_me_package.py:216/607/697`
- `packages/workflow-core/bodesign_workflow_core/guide_dod.py`（dod_ok 合流點）
- `issues/BR_20260704_c01_c02_emitter_modular_platform_template_not_refs_derived.md` §3/§5

## Stop Gates In Force

- 不得新增任何 fallback（缺 refs 必 fail fast；不得加「跳過 gate」參數）除非使用者批准。
- graduate 為 user-only gate。

## Execution-Ready Checklist

- [x] refs_gate.require_refs 已存在且有 c04 使用範例（refs_ingest verb）
- [x] 模板汙染向量已定位（emit 無 gate、無 provenance、corpus 推導無標記）
- [x] 測試路徑已知：`PP=$(ls -d packages/*/ | tr '\n' ':') && PYTHONPATH="$PP" python3 -m unittest ...`
