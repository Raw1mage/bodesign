# Changelog

All notable changes to bodesign are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); the source of truth for design
rationale is the plan-builder specs under `specs/`.

## [Unreleased]

### 新增 — C00 PRD 以 docx 產出（重現 Rockbox Word 文件架構）
- 把 C00 PRD 的產出從純 Markdown 升級為**可組成帶樣式 .docx** 的封裝，文件架構**重現真實
  Rockbox C07-PRD Word 檔**：封面區 + 改版紀錄表 + 12 個編號 Heading-1 章節 + 各章節內部的
  表格骨架（Objectives 表、Electrical 規格表、R&R RACI 矩陣、Team Roster 聯絡卡…），並依
  `include_rf` 條件產出獨立的 RF Requirements 文件。
- **伺服端預存範本**：Word 架構以 `.dotx` 二進位 + JSON 架構描述並存於
  `packages/workflow-core/.../templates/`（`c00_prd.dotx`、`c00_rf.dotx`、
  `c00_prd.docx_architecture.json`），供重複使用。
- **Renderer**（`workflow-core/c00_prd_docx.py` `render_c00_prd_docx_package`）：從
  `answer_state` 為每份文件渲染出 docxmcp 可組裝的封裝——`body.md` + `outline.md` +
  `manifest.json` + `template/template.dotx`。誠實紀律不變：missing／drafted 等欄位狀態保持
  可見，且 renderer **絕不**標記 human approval。
- **MCP 工具** `bodesign_c00_emit_prd_docx`（handler `_h_c00_emit_prd_docx`）：**預設為
  client-side orchestration**（MVP）——bodesign 只回傳封裝 + assemble 提示，由呼叫端用自己的
  docxmcp 連線驅動 `document.assemble`（因此 bodesign 不依賴 docxmcp 的 runtime／帳號／權限）。
  `assemble=true` 才選用內部 MCP bridge（經 `mcp_delegate.call_external_mcp_tool` 接 docxmcp）；
  當 docxmcp server 未配置時誠實降級為 `worker_unavailable`，**絕不**偽造 .docx。
- docxmcp 雷點記錄：`assemble` 的 `doc_dir` 必須是**絕對容器路徑**
  （`/var/cache/docxmcp/sessions/<token>/…`）；相對路徑會解析到 `/app` 而失敗。
- 測試：`tests/test_c00_prd_docx.py` —— 6 unit（架構描述載入／封面+章節標題／欄位狀態可見+表格
  渲染／不標 approval／產出可組裝封裝／render 需先 scaffold）；端到端實跑驗證通過（scaffold →
  填 81 欄 answers → render → docxmcp assemble → 兩份合法 Word 2007+ .docx）。

### 變更 — bodesign skill：階段交付物改置於 stage 根目錄
- 取消 `03_output/` 交付物子目錄，改為**交付物平鋪在各 cXX 階段根目錄**，打開階段資料夾即可
  一眼看出該階段交付了什麼；只有輔助材料（`01_refs/` 輸入、`02_build/` 中間產物）仍留在編號
  子目錄。同步更新 `SKILL.md`、`stage-structure` 與 `si-constraint` 參考文件，以及 C04–C07
  各階段 GUIDE。

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

### 新增 — 持久化的伺服端 Component Vault（SQLite + FTS5，八層）
- `packages/component-kb` 新增 `storage.py` + `repository.py`：一個位於 `BODESIGN_VAULT_DIR`
  （docker named volume `bodesign-vault`）的耐久 vault，採 WAL SQLite、`user_version` migration
  v1–v5、content-addressed blob store，以及 fail-fast 啟動（缺目錄／DB 損毀 → VAULT-E001/E002，
  絕不 silently rebuild）。
- 八層知識：identity（canonical MPN + aliases，顯式 absent）、documents（sha256 去重 + 版本鏈 +
  強制 provenance）、chunks（doc-core adapter + 帶 page anchor 的 FTS5 BM25 搜尋；抽取器升級時標記
  stale，絕不刪除）、spec EAV（field_path registry、min/typ/max + condition 共存、`verified` 需證據
  由 trigger 強制）、EDA assets（symbol/footprint 驗證階梯 unverified→pin-checked→drc-passed，每階
  帶 provenance）、app knowledge（4 種 payload 型別、evidence-gated trust）、append-only audit log
  （trigger 強制）、usage/sourcing（跨專案出現次數彙總、point-in-time sourcing 快照、替代料）。
- API 介面：4 個 MCP 工具（`bodesign_vault_ingest/query/spec_check/queue`）與 5 條 HTTP route 共用
  輕薄的 `services/mcp/vault_api.py` 層；`spec_check` 優先查詢伺服端 vault 並標注裁決來源
  （`server-vault` | `client-cache`），同時保留四態語義。
- Client-cache 匯入（`import_client_cache`）：一律 unverified、帶 `client-cache-import` provenance；
  衝突時兩邊都保留（VAULT-E903）。
- 消費端：`kicad_emit.vault_symbol` / `footprint_map.vault_footprint` 透過 duck-typed repository
  查詢 vault，並回傳顯式 absent —— 不臆測。
- 測試：`tests/test_vault_{storage,chunks,specs,api,usage,eda}.py` —— 新增 105 個 vault 測試；
  全 suite 132/132 綠。Spec：`plans/feature_component_vault/`。

### 修正 — workers 拓樸在 rebuild 時 silently 退回 monolith
- `mcpctl.sh` 只認得 `docker-compose.yml`（monolith），因此任何 `rebuild`／`restart` 都會丟掉
  opt-in 的 `docker-compose.workers.yml` 拆分（重量級 CAD/EDA 依賴隔離，core + me/ee workers），
  並使 worker 容器變成 orphan —— 一個 silent regression。
- 新增**黏性 `BODESIGN_WORKERS` 模式**（對齊 `BODESIGN_DEV`）：一旦以 `BODESIGN_WORKERS=1` 啟動，
  `.run/.workers` 標記就讓之後每次 `restart`／`rebuild` 維持 workers 模式；`BODESIGN_WORKERS=0`
  退回 monolith。`status` 現在會回報模式 + 逐 worker 健康度；所有 `up` 呼叫都帶 `--remove-orphans`，
  讓切換模式保持乾淨。

### 新增 — C00→C04 判斷層、遞迴對帳、可行性 triage
- 逐階段的**設計判斷 reference** —— agent 閱讀的「如何思考」層，與執行引擎／MCP 區分。C01：
  reduction-lens + Ashby 選材 + design-for-disassembly。C02：DFM/DFA/公差/材料 + IP-sealing 建議，
  以及一個幾何作圖（inspect-don't-visualise）迴圈。C03：EE 設計建議（穩壓器選型、去耦、SI 需求
  數值、散熱、RF、power-sequencing）以及一套**腳位→電路合成法**（將每個 pin 的義務分類，並接地於
  參考設計）。C04：stackup/placement、HDI（IPC-2226）、SI 實現。
- **跨站對帳**（[`references/cross-stage-reconciliation.md`](skills/bodesign/references/cross-stage-reconciliation.md)）——
  面積／散熱／高度 budget 與 C06 verdict-fail 會*回饋*到負責的階段，重用既有 `BlockerReturn` primitive
  （`return_blocker`／`list_blockers`／`ingest_blocker`）。`assess_package_readiness` 現在會浮出未解決
  的 blocker 並擋住 milestone all-clear —— 機器強制，而非依賴記憶。
- **可行性 triage**（`classify_product_feasibility`、`bodesign_workflow_core.feasibility`）——
  依最難的複雜度驅動因子，把產品分類成 C04 交付分級（1 fab-ready · 2 routed-draft · 3
  concept+constraints → pro-EDA），並在 C01 一開始就宣告，讓「給 C00，得 C01–C04」對每個產品誠實；
  在 C03 重跑確定。
- **SI 約束交接**（`emit_si_constraint_export`、`bodesign_workflow_core.si_handoff`）——
  Tier-3（HDI/DDR/RF）產品產出中性的 SI 約束包（JSON 單一真實來源 + CSV net-classes + 逐工具的
  Allegro / Xpedition / Altium 匯入對應）；繞線硬牆變成乾淨的 pro-EDA 交接。bodesign 未能推導的約束
  列於 `tbd[]`，絕不臆測。
- 測試：`test_feasibility`、`test_reconciliation_gate`、`test_si_handoff`（全 suite 綠）。

### 新增 — C04 EDA 工具鏈（MCP）
- `bodesign_impedance_solve` —— 從明確 stackup 以 pure-core 閉式解算 microstrip/differential
  class 線寬 + 延遲常數（屬指引；以 fab-solver 確認）。
- `bodesign_widen_bus_tracks`、`bodesign_length_match_bus` —— 在 EE worker 上做 clearance-safe 的
  bus finishing（加寬至目標線寬；clearance-aware 蛇形 skew 調校），各自寫出新的 `.kicad_pcb`。
- `bodesign_render_gerber_preview` —— 真實的單層 Gerber 點陣（gerber-core / pygerber）；
  composite/stack 模式回傳顯式 `render-unavailable`。
- Graduated spec：[`specs/feature/eda-mcp-toolchain/`](specs/feature/eda-mcp-toolchain/README.md)
  記錄完整的 C04 routing/finishing 工具鏈；已 KB-indexed。

### 變更 — 工具一般性（不 SILENT overfit）
- `bodesign_route_net2pcb` —— connector pin 展開不再以 refdes `J1` 為條件。接受明確的
  `connectors` pinmap，否則把內建 USB-C 表套用到任何 refdes 上的任何 USB-C footprint；結果回報
  `applied_pinmaps` 與 `unmapped_connectors`，而非 silently 跳過。
- `bodesign_si_check` —— driver/load/edge/閾值（`rdrv`/`cload`/`edge_ns`/`overshoot_pass_pct`/
  `overshoot_warn_pct`）現在可由呼叫端覆寫，並附文件化的 STM32-class-CMOS 預設值；結果回放
  `effective` 值。
- `bodesign_emit_layout` —— 暴露 placement grid + 外框 margin
  （`board_mm`/`columns`/`place_start_mm`/`place_pitch_mm`/`margin_mm`）。
- `bodesign_emit_fab` —— 透過 `pdf_layers` 暴露 PDF 圖層集（預設 = 2/4 層）。
- `bodesign_pour_planes` —— 暴露 stitch net + grid/via 幾何
  （`stitch_net`/`stitch_pitch_mm`/`stitch_drill_mm`/`stitch_pad_mm`）。
- `bodesign_via_in_pad` —— 文件化 JLCPCB-advanced POFV via 預設值。

### 新增 — 一般性契約強制
- `docs/generality-check.md` —— no-silent-overfit 基準 + 5 軸檢查表 + 稽核。
- `tests/test_tool_generality.py` —— schema 層的回歸防線，斷言每個工具的 board/process 假設都維持
  可由呼叫端覆寫或回報。
- 耐久的 socket 層 MCP smoke 測試（`test_socket_level_list_and_call_smoke`）：透過 stdio 跑真實的
  `initialize → list_tools → call_tool` 往返；無 MCP SDK 時跳過。

### 修正
- 修復一個壞掉的 HEAD：`impedance.py` 與 gerber-preview 實作被留成 untracked，但其接線卻已被提交
  （fresh-checkout import 失敗）。

### 已知限制
- 真板 EE 執行（透過 `pcbnew` 的 widen/length-match/route/pour）需要 EE worker；板級變更的回歸測試
  以 env 把關。決策邏輯由裸機上的 pure-helper + schema 測試涵蓋。

## 更早
- `component-kb`：lazy 的 MPN-keyed datasheet vault + RCA spec-audit 閘
  （`bodesign_datasheet_register` / `bodesign_spec_check` / `bodesign_rca_spec_audit`）——
  anti-hallucination 的 spec 接地，project-scoped。
- `bodesign_render_board_model` —— 把已發布的 3D board model（glTF/.glb，含 Draco）渲染成
  board-view PNG。
- 透過 `docker-compose.workers.yml` 的 worker 拆分（core / ee / me）。
