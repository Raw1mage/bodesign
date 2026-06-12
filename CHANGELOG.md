# Changelog

All notable changes to bodesign are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); the source of truth for design
rationale is the plan-builder specs under `specs/`.

## [Unreleased]

### 新增 — datasheet 接地的 SPICE model 卡（vault L4 → cascade tier-1）
- `packages/component-kb/spice_card.py` — 一條完全確定性的管線，把 SPICE 模擬接地到 datasheet
  證據，使 model 準確度是被**展示**而非假設。LLM 只參與上游抽取；ingest／generate／materialize
  全程確定性。
- **Vault L4 命名空間** `spice_model.{diode,ldo,passive}` — 封閉的 v1 `SPICE_MODEL_FIELDS`
  registry。`repository.py resolve_field_path` 改為 **longest-prefix root 匹配**，讓多段 root
  （`spice_model.diode`）能與單段 root 並存解析（P1 測試揭露並修復的一個真實合約 bug）。
- **逐筆 evidence ingest 契約**（`ingest_spice_extraction`）：每筆參數都驗證 registry leaf／
  `sha256`+page 證據／數值；不合格的列**逐筆拒絕**
  （`SPX_FIELD_UNKNOWN`／`SPX_EVIDENCE_MISSING`／`SPX_VALUE_INVALID`）；`not_found` 會回報但
  絕不寫入；所有寫入皆 `trust=unverified`。
- **確定性卡生成**（`generate_model_card`）：從 L4 產出 byte-identical 的 `.model`／`.subckt`
  卡，typ-selection（typ→唯一值→`SPX_PARAMS_AMBIGUOUS`，絕不自行平均），provenance 註解卡頭、
  無時間戳；`SPX_PARAMS_MISSING`／`SPX_CATEGORY_UNSUPPORTED` fail-fast。
- **物化 + smoke**（`materialize_model_cards`）：ngspice DC-op smoke（pass／fail／
  `skipped-no-simulator`；**fail 的卡排除於 manifest 之外**），再把卡檔 +
  `manifest.json`（`source=vault-grounded`）寫入 `<project>/spice/models/` —— 即 `spice` skill 的
  model-resolution **cascade tier-1 快取**，因此 vault-grounded model 自然優先命中且 **零 skill 改動**
  （寫入前已對 skill 鎖定 manifest 格式 round-trip —— R-A 風險解除）。
- **Simulate provenance**：`eda-bridge/simulate.py` 透過確定性 manifest 查表為每筆結果標注
  `model_source`（`vault-grounded` | `generic-default`）—— 讓結果背後的 generic-default model 保持
  可見。新增的 `spice` ValidationEvidence adapter 把 simulate 的 warn／fail subcircuit 與失敗的
  model-card smoke 映成 evidence findings。
- **MCP 工具** `bodesign_spice_model_card`（core group）；`SPX_*` 錯誤碼型錄，皆帶結構化 payload
  與修復指引。
- 測試：`tests/test_spice_card_{ingest,generate,materialize,mcp}.py` —— 新增 46 tests
  （含真 ngspice DC-op pass + cascade round-trip）；全 suite 530/530 綠。
  Graduated spec：[`specs/knowledge/datasheet-spice-models/`](specs/knowledge/datasheet-spice-models/README.md)。

### 新增 — 參考優先的驗證紀律（G1–G7）
- 一條確定性的驗證骨幹，使可靠度是對照參考設計被**展示**，而非由 LLM 宣稱。落於
  `packages/workflow-core` + `packages/design-ir/compare`。
- **G1 需求契約** — `ExtractedRequirement` 可契約化
  （`metric`／`threshold`／`measurement_method`／`oracle_tool` 封閉 enum／`verification_status`）；
  `oracle_tool="none"` 強制 `unverifiable` + open-question 升級；`requirement_passfail_table()` 在
  沒有 oracle 執行紀錄前絕不推斷 pass。
- **G2 實作前設計審查** — `record_design_review`／`review_gate_status` 驗證一份持久化的
  `DesignReviewRecord`（subject、帶嚴重度的情境走查、APPROVE／APPROVE_WITH_CONCERNS／REJECT
  裁決）；缺紀錄（`REVIEW_MISSING`）或 `REJECT`（`REVIEW_REJECTED`）即擋住確定性驗證。
- **G3 crosscheck + root cause** — `crosscheck_diff()` 把 net crosscheck 一般化為多維度
  `CrossCheckDiff`（net／pad／component／pin／component_value／layout_rule 項目，帶嚴重度 +
  `first_divergence`；缺證據的維度回報 `dimensions_unavailable`，絕不偽裝成 matched）。
  `record_root_cause()` 持久化四段式 root-cause 報告（方法論／發現／錨定證據／修復）。
  `BlockerReturn.simple_fix_candidates[]` 在每個廉價假設都以證據排除前，擋住結構性提案。
- **A3/A5 證據回流** — `ValidationEvidence` 信封作為骨幹第三類產物 `evidence_returns/` 回流到 C00
  （`bodesign.c00.evidence_return.v1`，計數式 `<LAYER>-EV-NNNN` ID；格式錯誤的 payload fail-fast 且
  不落任何資料）；`ingest_evidence` 記錄逐需求裁決，且絕不自動執行修復。
- **A1 workflow plan 衍生** — stage 狀態**由 orchestration 骨幹衍生**
  （`derive_workflow_plan(folder)`：`_orchestration/` work packet + blockers + evidence returns 為單一
  真實來源）；缺 `_orchestration/` 即顯式回報 `SPINE_NOT_INITIALIZED` —— 絕不 silent fallback 回
  參數快照狀態。
- **G7 參考比對器** — `packages/design-ir/compare/` 是確定性參考比對器：兩階段元件配對
  （必要件優先；參考設計的選用件免罰）、pin-neighborhood 簽章、**純 Python Hungarian 指派**
  （scipy 不在部署依賴）、對稱被動件 pin 正規化、FlexiblePin 群組，以及加權分數
  `S = 0.4·S_comp(Dice) + 0.2·S_attr + 0.4·S_conn`（權重集中於 `ScoringConfig`）。
  `ComponentInstance` 新增選用欄位 `value`／`optional`／`flexible_pin_groups`。
  輸入不合法即 fail-fast（`CMP_IR_INVALID`／`CMP_CONFIG_INVALID`，無部分比對）；相同輸入 →
  byte-identical 輸出，LLM 全程不參與。
- MCP 介面新增 `bodesign_reference_board_workflow`、`bodesign_wrap_validation_evidence`、
  `bodesign_return_evidence`、`bodesign_list_evidence_returns`、`bodesign_ingest_evidence`。
- 測試：`tests/test_requirement_contract.py` + `tests/test_verification_discipline_p{2,3,4,5}.py`。
  Graduated spec：[`specs/workflow/verification-discipline/`](specs/workflow/verification-discipline/README.md)。
  含 `docs/research/` 下的 arXiv workflow 分析（分析 `.md`；論文原始碼已 gitignore）。

### Added — persistent server-side Component Vault (SQLite + FTS5, 8 layers)
- `packages/component-kb` gains `storage.py` + `repository.py`: a durable vault under
  `BODESIGN_VAULT_DIR` (docker named volume `bodesign-vault`) with WAL SQLite,
  `user_version` migrations v1–v5, content-addressed blob store, and fail-fast
  startup (missing dir / corrupt DB → VAULT-E001/E002, never silently rebuilt).
- Eight knowledge layers: identity (canonical MPN + aliases, explicit absent),
  documents (sha256 dedup + version chains + mandatory provenance), chunks
  (doc-core adapter + FTS5 BM25 search with page anchors; extractor upgrades mark
  stale, never delete), spec EAV (field_path registry, min/typ/max + condition
  coexistence, `verified`-needs-evidence enforced by trigger), EDA assets
  (symbol/footprint verification ladder unverified→pin-checked→drc-passed with
  provenance per rung), app knowledge (4 payload types, evidence-gated trust),
  append-only audit log (trigger-enforced), usage/sourcing (cross-project
  occurrence aggregation, point-in-time sourcing snapshots, substitutions).
- API surface: 4 MCP tools (`bodesign_vault_ingest/query/spec_check/queue`) and
  5 HTTP routes share the thin `services/mcp/vault_api.py` layer; `spec_check`
  consults the server vault first and marks verdict origin
  (`server-vault` | `client-cache`) while keeping four-state semantics.
- Client-cache import (`import_client_cache`): always unverified with
  `client-cache-import` provenance; conflicts keep both sides (VAULT-E903).
- Consumers: `kicad_emit.vault_symbol` / `footprint_map.vault_footprint` query
  the vault via duck-typed repository and return explicit absent — no guessing.
- Tests: `tests/test_vault_{storage,chunks,specs,api,usage,eda}.py` — 105 new
  vault tests; full suite 132/132 green. Spec: `plans/feature_component_vault/`.

### Fixed — workers topology silently reverted to monolith on rebuild
- `mcpctl.sh` only knew `docker-compose.yml` (monolith), so any `rebuild`/`restart`
  dropped the opt-in `docker-compose.workers.yml` split (heavy CAD/EDA dep isolation,
  core + me/ee workers) and orphaned the worker containers — a silent regression.
- Added a **sticky `BODESIGN_WORKERS` mode** (mirrors `BODESIGN_DEV`): once started with
  `BODESIGN_WORKERS=1`, a `.run/.workers` marker keeps every later `restart`/`rebuild` in
  workers mode; `BODESIGN_WORKERS=0` reverts to the monolith. `status` now reports the mode
  + per-worker health; all `up` calls use `--remove-orphans` so switching modes stays clean.

### Added — C00→C04 judgment layer, recursive reconciliation, feasibility triage
- Per-stage **design-judgment references** — the "how to think" layer the agent reads,
  distinct from the execution engines/MCP. C01: reduction-lens + Ashby material selection
  + design-for-disassembly. C02: DFM/DFA/tolerance/material + IP-sealing advisory, and a
  geometry-authoring (inspect-don't-visualise) loop. C03: EE-design advisory (regulator
  selection, decoupling, the SI requirement numbers, thermal, RF, power-sequencing) and a
  **pinout→circuit synthesis method** (classify every pin's obligation, ground in the
  reference design). C04: stackup/placement, HDI (IPC-2226), SI realisation.
- **Cross-stage reconciliation** ([`references/cross-stage-reconciliation.md`](skills/bodesign/references/cross-stage-reconciliation.md)) —
  area / thermal / height budgets and C06 verdict-fails route *back* to the owning stage,
  reusing the existing `BlockerReturn` primitive (`return_blocker`/`list_blockers`/
  `ingest_blocker`). `assess_package_readiness` now surfaces unresolved blockers and blocks
  the milestone all-clear — machine-enforced, not memory-dependent.
- **Feasibility triage** (`classify_product_feasibility`, `bodesign_workflow_core.feasibility`)
  — classifies a product into a C04 delivery tier (1 fab-ready · 2 routed-draft · 3
  concept+constraints → pro-EDA) by the hardest complexity driver, declared up front at C01
  so "give C00, get C01–C04" is honest per-product; re-run firm at C03.
- **SI constraint handoff** (`emit_si_constraint_export`, `bodesign_workflow_core.si_handoff`)
  — Tier-3 (HDI/DDR/RF) products emit a neutral SI constraint package (JSON source-of-truth
  + CSV net-classes + per-tool import mapping for Allegro / Xpedition / Altium); the routing
  wall becomes a clean pro-EDA handoff. Constraints bodesign did not derive are listed under
  `tbd[]`, never guessed.
- Tests: `test_feasibility`, `test_reconciliation_gate`, `test_si_handoff` (full suite green).

### Added — C04 EDA toolchain (MCP)
- `bodesign_impedance_solve` — pure-core closed-form microstrip/differential class
  widths + delay constants from an explicit stackup (guidance; fab-solver confirmed).
- `bodesign_widen_bus_tracks`, `bodesign_length_match_bus` — clearance-safe bus
  finishing on the EE worker (widen to target width; clearance-aware serpentine
  skew tuning), each writing a new `.kicad_pcb`.
- `bodesign_render_gerber_preview` — real single-layer Gerber raster (gerber-core /
  pygerber); composite/stack modes return explicit `render-unavailable`.
- Graduated spec: [`specs/feature/eda-mcp-toolchain/`](specs/feature/eda-mcp-toolchain/README.md)
  documents the full C04 routing/finishing toolchain; KB-indexed.

### Changed — tool generality (no SILENT overfit)
- `bodesign_route_net2pcb` — connector pin expansion is no longer gated on refdes
  `J1`. Accepts an explicit `connectors` pinmap and otherwise applies the built-in
  USB-C table to any USB-C footprint on any refdes; result reports `applied_pinmaps`
  and `unmapped_connectors` instead of silently skipping.
- `bodesign_si_check` — driver/load/edge/thresholds (`rdrv`/`cload`/`edge_ns`/
  `overshoot_pass_pct`/`overshoot_warn_pct`) are now caller-overridable with
  documented STM32-class-CMOS defaults; result echoes the `effective` values.
- `bodesign_emit_layout` — placement grid + outline margin exposed
  (`board_mm`/`columns`/`place_start_mm`/`place_pitch_mm`/`margin_mm`).
- `bodesign_emit_fab` — PDF layer set exposed via `pdf_layers` (default = 2/4-layer).
- `bodesign_pour_planes` — stitch net + grid/via geometry exposed
  (`stitch_net`/`stitch_pitch_mm`/`stitch_drill_mm`/`stitch_pad_mm`).
- `bodesign_via_in_pad` — JLCPCB-advanced POFV via defaults documented.

### Added — generality contract enforcement
- `docs/generality-check.md` — the no-silent-overfit bar + 5-axis checklist + audit.
- `tests/test_tool_generality.py` — schema-level regression guard asserting each
  tool's board/process assumptions stay caller-overridable or reported.
- Durable socket-level MCP smoke test (`test_socket_level_list_and_call_smoke`):
  real `initialize → list_tools → call_tool` roundtrip over stdio; skips without
  the MCP SDK.

### Fixed
- Repaired a broken HEAD where `impedance.py` and the gerber-preview implementation
  had been left untracked while their wiring was committed (fresh-checkout import
  failure).

### Known limitations
- Real-board EE execution (widen/length-match/route/pour via `pcbnew`) requires the
  EE worker; board-level mutation regression is env-gated. Decision logic is covered
  by pure-helper + schema tests on a bare host.

## Earlier
- `component-kb`: lazy MPN-keyed datasheet vault + RCA spec-audit gate
  (`bodesign_datasheet_register` / `bodesign_spec_check` / `bodesign_rca_spec_audit`)
  — anti-hallucination spec grounding, project-scoped.
- `bodesign_render_board_model` — render a published 3D board model (glTF/.glb,
  incl. Draco) to board-view PNGs.
- Worker split (core / ee / me) via `docker-compose.workers.yml`.
