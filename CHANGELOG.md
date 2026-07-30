# Changelog

All notable changes to bodesign are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); the source of truth for design
rationale is the plan-builder specs under `specs/`.

## [未發布] — 2026-07-30

### Fixed
- **R9 skill-shipping 遠端半合規（BR_20260730，外部 fleet 稽核 file、bodesign 自行 own fix）**：
  - `GET /skills` 先前廣告的是**檔名**（`bodesign.tar.gz`）而非 skill **名稱**，且只服務 `.tar.gz`。合規 client 依 R9.2 取 `name` 後附加 `.zip`，必然拼出 `bodesign.tar.gz.zip` → 404；14 個 companion 對遠端 client 全數不可取，而 `GET /skills` 仍回 200、manifest 看起來健康（靜態閘查不出，撥號才抓得到）。
  - **根因比症狀更深**：服務來源 `services/mcp/assets/skills/` 與 `mcp.json skillPaths` 宣告的 repo `skills/` 是兩棵樹，且**已經漂移**——被服務的 `bodesign.tar.gz` 是 2026-06-10 手工凍結快照，缺 `doctrine.md`（R15 single-source）與整個 `scripts/`（含 `gate.py`，~52 個 landing verb 唯一入口），另含 2 條 R9.7.1 明文禁止的 symlink。
  - 修法為結構性而非表面：新增 `services/mcp/skill_shipping.py`，archive 一律**從宣告來源即時打包**（R9.11.3 by-construction），不再有第二份會腐爛的 artifact。listing 改回 bare name；新增 `GET /skills/<name>.zip`；`.tar.gz` 保留但同樣投影自同一棵樹，格式不再能編碼內容差異。
  - `run_http` 綁 socket **前**執行 `assert_skill_source_parity()`，宣告與服務不一致就讓 process 死掉（R9.11.1）——半殘服務不得靜默啟動成功（天條 1）。
  - Producer 衛生：無絕對路徑／`..`／symlink，排除 dotfile 與 `__pycache__`，member mtime 固定使 archive byte-reproducible；未知名回 typed 404 而非 200 空 archive（R9.6.2）。私有 product-board vault symlink（`openmv`/`thesmart_products`）在打包與 image 兩層都排除。
  - 四個 Dockerfile 改 `COPY mcp.json` + `COPY skills`（取代原本只 COPY 單一 `doctrine.md`），dev overlay 同步掛載；新增 `.dockerignore`。kicad 引擎抽取改自 in-repo 樹（78 檔，較退役 tarball 的 50 檔新）。已退役 `assets/skills/bodesign.tar.gz`。
  - 13 個 vendored EDA companion **無 in-repo 來源**，無法滿足 R9.11 parity，故改列於獨立的 `bundles` 鍵，不冒充 R9 skill。
  - 驗證：`tests/test_skill_shipping.py` 23/23（含 traversal 負向與 accepting control、parity 負向控制）；live UDS 撥號 `.zip` 200/有效 zip/169 members、含先前遺失的 `doctrine.md`+`scripts/gate.py`，5 種 traversal/錯誤形狀全 404，`.tar.gz`+MANIFEST back-compat 未破。

## [未發布] — 2026-07-11

### Added
- **R16 domain-KB in-band serving（spec `plans/mcp_r16-domain-kb/`，fleet 標準 R16 reference impl）**：
  - 新增兩個 read-only core-group 工具（TOOLS 53→55，version 0.3.0）：`bodesign_kb_query(q, type?, limit?)`（確定性檢索 repo ragbase KB；token 規劃比照 specbase：全 ≥3 碼點→FTS AND、全 <3→LIKE scan、混合→hybrid；payload 自述 `matchMode`）與 `bodesign_kb_get(id)`（全文 body_md + confidence + source_weight + lineage provenance）。
  - **One KB, two doors（R16.7）**：容器內工具與 host-side specbase `gate.ts ragbase_query` 讀同一個 `.specbase/ragbase.sqlite`（bind mount `/var/lib/bodesign/kb`，rw 掛載 + 連線層 `mode=ro`+`PRAGMA query_only` 強制唯讀——純 ro mount 無法讀 WAL store，DD-3）；無任何 KB 寫入工具（R16.4）。
  - Fail-fast：KB 缺失/不可開 → typed `KB_UNAVAILABLE` + remedy 行；空 query → `KB_BAD_QUERY`；id 不存在 → `KB_OBJECT_NOT_FOUND`（天條 1，不回靜默空 hits）。
  - Recall-first signpost（R16.5）：`mcp.json.instructions` + server INSTRUCTIONS 加 KB 宣告；8 個判斷密集工具 description 帶 `consider: bodesign_kb_query`。
  - 驗證：`tests/test_kb_tools.py` 11/11 OK；live smoke UDS kb_query "EMC decoupling" 命中（matchMode=fts, total=5）；兩門一致性（同 query 同 id 集合）通過；既有失敗集與 pre-change baseline byte-identical 零新增（並修正 test_mcp_server 硬編碼舊工具數 47→55）。
  - KB 內容：同日從 6 個 GitHub PCB-design skill repos 蒸餾 52 筆 evidence-graded 知識物件（IPC-2221B 間距、IPC-2152 載流、EMC 去耦、DFM 閘、derating gate、failure modes 等）。

## [未發布] — 2026-07-06

### Added
- **BR_20260706 五筆 BR 闉環（spec `eda_schematic-draftsman-quality` extend DD-8..DD-11，living）**：
  - **保真閘接線**：`bodesign_compose_schematic` 新增 `fidelity` 參數（透傳 `fidelity.py verify_partition_fidelity`，spec 期望 net 劃分 vs kicad-cli 匯出連通分量節點集等價比對，diff!=0/0 即 `FidelityError`），結果回 `engine_rev` 戳。ERC 對共線熔合短路天然盲，此閘實戰抓出三次短路。
  - **防熔合 guard（治本）**：`kicad_emit.py` 全局 fusion_registry——drawn-wire segment 落盤前檢查跨 net 共線重疊/端點落線，衝突→ net-hash 確定性 jog 錯開（重試≤3）→仍衝突降級 label（`fusion_label_fallbacks` 可見）；無衝突輸入 byte-equivalent。
  - **密度預算 lint**：`compose_schematic(density_budget=...)` 前置檢查（nets/components/pins-per-symbol，aiguard 04_wireless PASS / 03_memory FAIL 兩點標定），超標 raise `DENSITY_BUDGET_EXCEEDED` 強制分頁；`None` 預設關閉零破壞。
  - **渲染層文字 QA**：`render_qa.qa_svg_text` 收編 + `gate.py` landing verb `qa_svg_text`（免容器）；aiguard CCM 5 頁回歸基線 13/6/18/3/2 只降不升。
  - **BR5 快贏**：`net2pcb_board(board_mm=...)` 直接畫 (0,0)-(W,H) 板框（回 `outline_source`）；`pour_planes` 加 `pad_connection="thermal"|"solid"`（消 starved_thermal）+ `POUR_PLANES_BAD_SPEC` 防呆；`compose_schematic` 全 skip → `COMPOSE_ALL_COMPONENTS_SKIPPED` fail-fast（消空圖假綠）。
  - **BR2 部署漂移收斂**：`/tmp/engpatch` overlay 正式退場（實測從未在 server PYTHONPATH，純漂移源）；`scripts/sync_engine.sh` 改 assert-absent + 單一 bind-mount 副本驗證。
  - **BR3 方法論**：`skills/bodesign/SKILL.md` Delivery contract 六硬規（capability triage / 2 輪停損 / 交付層 QA 先行 / 引擎單一持有權 / 快照+禁 git rollback / 交接物標準化）；c03-ee GUIDE done-criteria 補三閘。
  - 驗證：62 tests OK（含新增 density 7 + 防熔合 3 + skip-contract 2 + pour-spec 6；TV1-TV10 byte-stable 全綠）。五筆 BR 均補 Resolution 段並移 `issues/closed/`。
- **C04 placement approval gate(owner 指示)**:placement 圖列為 C04 第一階段交付物,owner 核可後才允許銅層 routing。
  - 新模組 `packages/workflow-core/bodesign_workflow_core/c04_placement_gate.py`:
    - `emit_c04_placement_review(board_pcb, out_dir, board_name)` — 從已擺件的 `.kicad_pcb` 產出 placement review 套件(top 3D PNG + 實體比例 SVG + `placement_manifest.json` + `PLACEMENT_REVIEW.md`);kicad-cli 缺失時 fail-fast(`kicad-cli-not-found`),無 fallback。
    - `assess_c04_placement_approval(folder)` — 檢查 `PLACEMENT_APPROVED.json`(必含非 placeholder 的 `approved_by`/`date`/`board`/`scope_note`);AI 不得自行寫核可檔,僅 owner 授權後代錄(契約載於 docstring 與 PLACEMENT_REVIEW.md 模板)。
  - `gate.py` 新 verbs:`c04_placement_review`、`c04_placement_gate`。
  - `assess_c04_layout_readiness`:偵測到 routed 證據(`.ses`/routed pcb/gerbers)但 `PLACEMENT_APPROVED.json` 缺失時,warnings 加 `placement_not_approved_before_routing`(warn,不 hard-fail,向後相容既有板)。

## [未發布] — 2026-07-05

### 修復 — skill 語料去誤導化（`quality/bodesign-skill-disambiguation` pilot + 推廣）

- **稽核**：全語料 505 筆 `should/must/always/never` 命中逐鯣，逾九成為刻意的
  honesty-model 契約語（保留）；真正誤導源 18 筆，高度集中於 2 份 rule-base。
- **P0 安全 bug（R20）**：`pcb-layout-rules-compendium.md` HV 間距列標籤
  「IPC-2221 B1, bare outer」自相矛盾（B1=Internal），數值實為跨欄拼湊——對裸外層板
  低壓間距偏小 4.6 倍（0.13 vs 0.6mm）→ DRC 過鬆。改為指向 `standards-compliance.md`
  主源表 + column-selection 教學（單一真源，不重述）。稽核 subagent 自身也被該標籤騙倒
  （誤報『差 2 倍』）——誤導標籤騙遝每個下游讀者的活標本。
- **provenance 三級制**：compendium 新增 `[primary:]`/`[fab:]`/`[rot]` 標註紀律；
  `[rot]`（經驗法則）禁入 DRC gate / 送廠文件。R1 電流線寬去 IPC-2152 誤歸屬；
  P8 熱過孔/S9 傳播延遲/G12 PDN 範例/D9 soldermask/P12 courtyard 逐筆補條件與失效邊界。
- **契約邊界語（7 檔）**：`datasheet-verification.md`（空結果=UNVERIFIED≠PASS，明列
  零 findings 不涵蓋項）；c04 GUIDE + `kicad-interactive-layout.md`（mirror→point-in-time
  copy 漂移警語）；kicad scripts README（12mm snapping 低信心、Vref 猜值清單外即錯）；
  `methodology_schematic.md`（1053 板未觀察≠安全證明）；`manual-schematic-parsing.md`
  （valid=parseable≠complete）；`report-manufacturing.md`（Skipped:never 讀法 key +
  fab 預設值=placeholder 禁直接送廠）；`mechanical-design-advisory.md`（FDM 值条件化）。
- **驗證**：skill-creator eval loop，3 測試案例 × 新舊版雙盲 subagent：新版 6/6、
  舊版 0/6（舊版實際答錯 HV 間距、誤歸屬 IPC-2152、把經驗值硬寫進 DRC gate）。
  KB 沉澱：`failure-mode.knowledge-base.misleading-provenance-label-cross-column-splice`
  + `control.knowledge-base.anti-misleading-writing-pattern`。

## [未發布] — 2026-07-04

### 新增 — 跨 spec extend：copper-clearance checker 落地（`control.dfm.ipc-clearance-voltage`）

- **上游畢業**：`design-ir/net-role-extension` 與 `gerber-core/copper-geometry-parser`
  兩份 verified plan graduate 至 `specs/`（living）。前者提供封閉 `NET_ROLES`
  island-role enum（`roles.py`），後者提供真實 edge-to-edge 銅箔幾何（`copper_geometry.py`，
  含 curve-skip provenance + 缺幾何 fail-fast）。
- **新 checker**：`packages/workflow-core/.../checkers/copper_clearance.py` 消費上述兩能力，
  逐對 distinct-net 銅島以 IPC-2221 工作電壓 clearance 閘檻把關；閘檻值 run-time 由
  ragbase threshold_block 讀取（DD-3），不硬編。
- **registry 解鎖**：`control.dfm.ipc-clearance-voltage` 由 `T-B stub`（`checker_fn=None`，
  gated 量非 IR-readable）翻為 `T-A landed`（`check_copper_clearance`，envelope `drc_gate`）。
  landed 計數 8→9。
- **no-fabrication 紀律**：拒絕 false-green——landed 由真實可運作 checker + 測試背書，
  而非空 `checker_fn`。每個缺/壞輸入（未綁閘檻、缺 source_anchor、缺 copper_geometry、
  缺 island_roles、role 超出封閉 enum、pair 幾何不可計算）一律 fail-fast，絕不靜默通過。
- **驗證**：新增 `tests/test_copper_clearance.py`（9 測試：pass/fail/determinism + 6 個
  no-fabrication 守衛）全綠；回歸 `test_verify_registry_threshold`(18)/`test_verify_checkers`(40)/
  `test_copper_geometry`(13)/`test_net_role`(14) 全綠。架構同步 Verified（無邊界/資料流變更）。

## [未發布] — 2026-07-03

### 修復 — C04 誠實機制接線：上游履約 gate + feasibility/SI-handoff 去孤兒化
（BR `issues/issue_20260703_tier3_honesty_mechanisms_unwired_c04_silent_passthrough.md`）

- **根因**：aiguard 驗收踩坑（C00 定義的 NPU/SRAM 一顆沒落板，卻無任何工具訊號標為未完成）
  的工具層根因——三個誠實機制存在但從未接線：`classify_product_feasibility`（tier 分診）與
  `emit_si_constraint_export`（Tier-3 SI 交手）是生產碼零呼叫的孤兒；C04 emit 對缺 C03 netlist
  靜默續跑；readiness 把「上游電氣全空」報成 `layout_constraints_drafted`（誤導性綠燈）。
- **P1 上游履約 gate（治本）**：`c04_layout_constraints.py` 新增 `_assess_upstream_fulfilment(root)`
  ——跨階段 disk-of-truth 檢查（C03-EE/、`*.net` netlist、Mechanical_Constraint_Export.json
  是否存在），產出顯式 `gaps[]`。缺 netlist（=C00 元件未落成電氣連接）時 readiness 回
  `status=blocked_upstream_c03_missing`、emit 的 `Layout_Constraints.json` 帶
  `state=blocked_on_upstream`，不再是誤導的 `drafted`。**與 tier 正交**（無 netlist 一律 blocking）。
- **P1 接線 feasibility**：`emit_c04_layout_package` / `assess_c04_layout_readiness` 新增
  `feasibility_signals` 參數，跑 tier 分診標 `feasibility_tier` + `c04_target`。**無 signals →
  tier=not-assessed，不臆測**（no-silent-fallback；臆測 Tier 1 會低估繞線難度）。
- **P2 接線 si_handoff**：Tier-3 且上游齊備 → `status=layout_constraints_drafted_tier3_handoff`，
  `next_step` 明示呼叫 `emit_si_constraint_export`（Tier-3 clean-handoff 路徑終於可達）。
- **驗證**：`tests/test_c04_layout_constraints.py` 補 4 測；C04+feasibility+si_handoff+readiness+
  package_readiness+guide_dod 共 41 tests 綠。架構同步 `specs/architecture.md` C04 段。

## [0.2.1] — 2026-07-03

### 新增 — 第 5 道信任層：PRD↔BOM 履約 crosscheck gate（C04 缺口治理）
- 驗收發現結構性缺口：**C00 PRD 定義的晶片模組未落到電路板上**。RCA 三層失效鏈——
  ① C03 vault 查 `AL5809-060` absent 後降級落點選錯（落到 4×140R 純電阻鎮流，超出 PRD
  允許集合且 140R 無 datasheet 錨定 → 60mA±10% 結構性達不到）；② 無 PRD↔BOM 履約 gate；
  ③ DRC/ERC 只驗板子自身一致性、不驗履約 PRD。
- **L1 履約 gate**：`prd_bom_crosscheck.py` pure function + MCP 工具
  `bodesign_prd_bom_crosscheck`（PRD `main_components` 逐 role 比對 BOM，缺件/集合外/無
  datasheet 錨定 → `gate=FAIL` BLOCKING）；10 tests 綠。E2E 迴歸證實舊純電阻板
  `gate=FAIL`（current-regulator missing），與 BR 預期一致。
- **L2 降級協議**：C03 GUIDE 補「Vault-Absent Substitution Protocol」——集合外替代一律
  BLOCKING 等使用者、approvals user-owned；readiness DoD 接線（報告缺席=gate 未跑）；
  architecture.md C03 資料流同步。
- **L3 重設計**：使用者裁決 **NPN linear current sink 拓撲**重做 C03，crosscheck
  `gate=PASS`（current-regulator substituted in_envelope matched [Q1–Q4]，6 roles present）。
- **C04 實體閉合**：ERC 0 err、net2pcb placed=22/pads=90/unmapped=0、autoroute routed=True
  185seg/12via、DRC clean=True、fab 25 gerber + drill + pos + STEP + PDF。板上 22 footprint
  含 Q1–Q4 恆流器件——設計層＋實體層雙履約閉合。

### 新增 — atopile DSL front-end（C03 電路描述前端）
- atopile 0.12.5 工具鏈進 `Dockerfile.ee`（+ `default-jre` for freerouting）；工具面
  43→45（atopile + prd-bom 兩組），無重複註冊。

### 修復 — eda-bridge E2E 工作流缺口
- T1–T8 缺口（no_connect emit、multi-node label default、gutter scaling、mkdir-before-write、
  fab shared-copy）；autoroute 在 DSN export False / freerouting 非零 returncode / 缺 SES 時
  fail-fast（不再無聲假成功，REF** 於 DSN export 前 annotate）。

### 基礎設施
- `docker-compose.workers.yml` 補 experiments mount（ee + me 兩 worker）+ 映像 rebuild
  （tools:45、三容器 healthy）。

### 已知邊界（誠實標記）
- Rsense/Rbias 標 TBD（MMBT2222A Vbe datasheet absent，datasheet-grounded 天條不臆測電氣值）。

## [0.2.0] — 2026-07-02

### 破壞性變更 — R13 compute/landing split：52 個工具落地為 gate.py verbs
- 依 fleet MCP integration standard 的 **R13 compute/landing split** 重構工具面：**52 個確定性、
  只碰專案目錄的 verbs**（C00/C01 全家族、C02 analysis-only、C03 emitters、C04–C06
  scaffold+readiness、orchestration spine 14 個、read/gate、純函數）**自 MCP tool registry 移除**，
  改由 agent 在主機端以 `skills/bodesign/scripts/gate.py` 直跑（`--list` 為權威清單；
  `<verb> --repo <abs> [--json {…}|--arg k=v]`；JSON envelope stdout；typed error + exit≠0；
  `BODESIGN_SRC` 顯式指定源碼樹；heavy verbs 黑名單 hard-guard → `VERB_NOT_LANDING`）。
- 呼叫已落地的 tool 名 → typed **`TOOL_LANDED`** 錯誤 + 等效 `landing_command`（絕不無聲消失）；
  dispatch 層記 `tool_landed_hit`。收斂後容器 registry = **43 個 compute-plane 工具**
  （heavy EDA 工具鏈 + vault 家族 + `stage_dir` + `mcp_call` + docxmcp-assemble 路徑
  `c00_emit_prd_docx` + 3 個 cache 工具）。
- INSTRUCTIONS 改為 R13.5 三類宣告（compute tools / landing verbs / cache lifecycle）；
  `SERVER_VERSION`/`mcp.json` → 0.2.0。

### 新增 — WebDAV working cache（消滅整包進出儀式）
- `services/mcp/_webdav.py`（自 docxmcp 移植：multistatus / PROPFIND depth 0–1 / OPTIONS
  `DAV: 1,2` / Timeout 解析 / LockTable）+ `services/mcp/_auth_provider.py`（per-owner Basic
  credential：hash 存放 `.webdav-creds.json`、constant-time 比對、issue/rotate/revoke）。
- Cache lifecycle routes：`POST /caches`（provision，per-subject idempotent，回 token + mount
  URL + credential）/ `POST /caches/{token}/export`（host 目標；typed
  `EXPORT_TARGET_UNREACHABLE`）/ `POST /caches/{token}/close`（dirty-gate 409
  `WORKSPACE_CLOSE_DIRTY`，除非 clean/force）/ `GET /caches`；DAV method routes
  `/dav/{token}[/{rel}]` 全 method 先 resolve identity→owns()、逐 method audit log、cross-token
  Destination → 403。已以真 rclone webdav backend E2E 驗證。
- MCP 工具 `bodesign_cache_provision` / `bodesign_cache_export` / `bodesign_cache_close`
  （agent 走 tool、人走 mount）。

### 變更 — token_store 分級
- 每筆 entry 帶 `kind`（`ephemeral` | `deliverable-cache`）+ `owner_identity` / `subject_id` /
  `last_export_at` sidecar 持久化；新增 `mkdir`/`move`/`copy` helpers（沿用 `_safe` traversal
  防禦）；reaper class-aware：deliverable-cache 免 idle 回收、走長 safety-net TTL（warn-first），
  ephemeral 行為不變。

### 驗證
- host venv 727 tests 綠（4 個既有環境假影）；部署映像 727 綠（6 個環境假影）；restart 後
  UDS+TCP 雙 transport smoke（health / tools=43 / heavy tool token 路徑）；gate.py 於 repo 外
  XDG 情境以 `BODESIGN_SRC` 自足執行。Plan：`plans/mcp_r13-landing-webdav-cache/`。

## [Unreleased]

### 新增 — 本地 DXF↔DWG 轉換工具（LibreDWG + ezdxf）
- 新增兩個 core-group MCP 工具 `bodesign_dxf_to_dwg` / `bodesign_dwg_to_dxf`，讓 bodesign 能**在本地**
  做 CAD 互轉，不依賴任何線上轉檔 API 或 Autodesk 專有工具。
- **轉換後端**：LibreDWG 0.13.3 從源碼**靜態編譯**（`dxf2dwg`/`dwg2dxf`/`dwgread`），烤入 `Dockerfile.core`
  與 `Dockerfile`；`build-essential`/`pkg-config` 在同一 layer `purge` 以保留 binaries 而不增肥。輸出
  為 AC1015（AutoCAD 2000）DWG，主流 CAD（AutoCAD/ZWCAD/BricsCAD）相容。
- **正規化**（`dxf_to_dwg(normalize=True)`，預設開）：先用 ezdxf 把輸入重寫成乾淨的 R2000 DXF
  （LWPOLYLINE/TEXT/layers/colors 保留），再交給 LibreDWG，取得最佳 DWG roundtrip fidelity；古老
  AC1006/POLYLINE 格式會在此被升級，避免 roundtrip 失真。
- **能力模組**：`packages/eda-bridge/bodesign_eda_bridge/dxf_dwg.py`，並用 `dwgread -O JSON` 解析
  `_subclass` 回報轉出後的實體計數（polyline/vertex/text）。`requirements.txt` 加 `ezdxf`。
- **No-fallback 紀律**：缺 LibreDWG binary 時回 `ok=false` 並提示 `rebuild image`，絕不靜默退化成
  部分／失真轉換。
- 端到端驗證：蘆洲成功段587地號 40:60 土地切割 DXF → DWG，`polyline2d:4 / vertex2d:50 / text:4`
  幾何零損失，座標 x 範圍與源圖一致。

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
