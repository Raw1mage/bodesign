# Handoff: capability_refs-derived-design

## Execution Contract

執行 agent 必須交付 refs-derived 範式翻轉的實作，done 定義 = aiguard 5 個既有 SSOT 跑通全鏈（refs gate → 約束驅動 placement → castellated → DoD freeze）且**全程無任何憑空發明的座標/腳位/元件**（每數字可追溯 SSOT，SSOT 可追溯 owner 權威來源 PDF/PPTX）。分階段交付：P0 refs-gate MVP 先過 aiguard 驗收案例，再進 P1-P3。

## Required Reads

- `proposal.md`、`design.md`（DD-1~DD-8）、`idef0.json`、`grafcet.json`（本包）
- `specs/architecture.md`（C00~C07 模組邊界、core vs worker）
- `issues/BR_20260704_EPIC_capability_inversion_refs_derived_design.md`（總綱）+ 6 切面分項 BR
- repo `AGENTS.md` §2 天條（No silent fallback / No fabrication）、§4 core vs worker 邊界、§5 測試 PYTHONPATH
- 既有 `plans/quality_deterministic-preplacement/`（切面 2 子件，約束介面對接）

## Stop Gates In Force

- **約束 JSON schema 凍結前需使用者確認**（DD-8 對接既有 preplacement plan，schema 影響下游）。
- **P0 refs-gate 語意（fail-fast vs warn 邊界）需確認**：哪些 verb 強制擋、哪些僅警示。
- **graduate 為 user-only gate**：verified 達標僅提示，不自行 promote。
- **送廠輸出需確定性驗證 + 使用者明確批准**（repo 天條 3）。

## Validation Evidence (verified gate)

- **Full suite: 952 pass / 0 fail** (30 pre-existing env skips) — `python3 -m unittest discover -s tests`.
- **mcp_server drift invariants: 47 pass / 0 fail** — landing-verb mirror / count / removed-from-registry.
- **Worker-side DRC roundtrip: DRC clean gate=PASS** — `test_worker_side_placement_roundtrip.py` (solver → placement_to_coords adapter → net2pcb_board real .kicad_pcb → kicad-cli drc_gate) runs on pcbnew 9.0.9; frozen BOTTOM face lands on the real board bottom edge (ERC/DRC gate mechanism verified, 2 pass / 0 fail).
- **Acceptance vectors: TV-1..TV-6 pass / 0 fail** — refs-gate (缺 SSOT 擋 / 齊備過), constraint placement (USB-C=BOTTOM movable_by_c04=false), DoD traceback (憑空版 blocking / refs-derived 過).
- **6 open 20260703 BRs triaged: 5 closed + 1 consumer-side** — all code fixes carry regression tests.
- Architecture Sync: Verified (`specs/architecture.md` refs-derived paradigm 段全貌同步).

## Execution-Ready Checklist

- [x] proposal / design / tasks / idef0 / grafcet 齊備且 drawmiat 驗證通過
- [ ] 使用者確認 P0 切入（refs-gate MVP + aiguard 驗收案例先行）
- [ ] 約束 JSON schema 初稿與既有 preplacement plan 對齊
- [ ] BODESIGN_DEV / BODESIGN_WORKERS 模式確認（P1 需 ee worker）
