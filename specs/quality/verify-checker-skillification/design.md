# Design: quality_verify-checker-skillification

## Context

`quality_verify-knowledge-hardening` 已把 8 大領域 PCB verify 判斷力蒸進 ragbase，累積 57 個 `control.*` 物件（44 verified / 10 partial / 3 todo），每值附逐字來源錨點。但 bodesign 的驗證骨架目前只有 **1 個** control 被人工轉成確定性 checker（`classify_erc_report`）。其餘 56 個是靜態知識——C00–C04 設計流程跑過時**不會**被這些規則檢核。

repo 已備成熟注入骨架，技能化不需造新輪子：

- **5 層信任驗證**：ERC/DRC · crosscheck · SPICE · EMC/thermal · constraint-solving。
- **`ValidationEvidence` 封套**（`workflow-core/validation_evidence.py` `_ADAPTERS`）：drc_gate/si_check/crosscheck/spice adapter，`raw_result` 原樣保留，流回 C00 `evidence_returns/`（`bodesign.c00.evidence_return.v1`）。
- **`ORACLE_TOOLS` 註冊表**（workflow-core）：oracle 工具清單，`ExtractedRequirement.oracle_tool` 閉集 enum，`oracle_tool="none"` 強制 `unverifiable` + 開放問題升級。
- **`gate.py` landing plane**：52 個確定性 repo-local verb，caller uid 直跑，零 token round-trip。
- **既有 checker 範本 `classify_erc_report`**（`eda-bridge/kicad_emit.py`）：純 python、零 LLM、fail-fast、把原始 ERC 輸出 bucket 成工程裁決，掛在 `KiCadValidationResult.erc_classification`——**這正是技能化的黃金範本**。

## Goals / Non-Goals

**Goals**

- 設計一套 control-object → executable-checker 的**系統化映射方法 + 注入架構**，讓 56 個未技能化 control 有一致的落地路徑。
- 劃死「確定性 gate vs LLM advisory」邊界，守住 no-fabrication（partial/定性知識不得偽裝硬 gate）。
- 設計知識↔code **執行期耦合**機制，讓門檻值不再靠人工複製（batch1 ERC classifier 是一次性人工搬運，不可規模化）。
- 全部接進既有 5 層骨架 + `ValidationEvidence` 封套，不另立平行證據系統。

**Non-Goals**

- 不在本 plan 實作全部 56 checker（設計 + 首批試點分類為止）。
- 不改寫既有 checker 語義（只擴充、向後相容）。
- 不引入 fallback；不讓 LLM 參與確定性計算。

## Decisions

### DD-1: control 物件三層可執行性分類（Executability Tier）

技能化的第一步不是寫 code，而是**把 57 個 control 依「能否確定性執行」分三層**。這是整個方法的地基——決定哪些能變硬 gate、哪些只能當 advisory。

| Tier | 定義 | 判準（同時成立） | 落點 | 數量估計 |
|---|---|---|---|---|
| **T-A machine-checkable** | 可純程式硬 gate | ①`confidence=verified` ②有明確數值/布林門檻 ③門檻涉及的量**可從 design IR / artifact 讀到** | 確定性 checker → `ValidationEvidence` 硬 gate | ~20-25 |
| **T-B semi / IR-gap** | 規則明確但 IR 讀不到 | ①verified ②有量化門檻 ③但 design IR **目前無此欄位**（如機構 fit、CMF、connector keepout mm） | checker stub + IR schema 擴充需求（掛帳） | ~15-20 |
| **T-C advisory-only** | 只能語意判斷 | 定性準則（無數值門檻）或 `confidence=partial/todo`（no-fabrication：不得硬 gate） | LLM design-review 結構化提示（G2 gate 輸入） | ~15-20 |

**判準 taxonomy（防止主觀分類）**：
- 「數值/布林門檻」= control body_md 含可比較的量（如 stackup 50Ω→245µm、fuse derating 25%、IPC trace width/current）或明確 pass/fail 條件。
- 「可從 IR 讀到」= 該量對映到既有 design-ir dataclass 欄位（`ComponentInstance`/net/trace/stackup/`GeometryPrimitive`）或既有 artifact（`.net`/`.kicad_pcb`/gerber/`Mechanical_Constraint_Export.json`）。**這一條靠 recon design-ir schema 逐一核對，不臆測。**
- partial/todo → **一律 T-C**（no-fabrication 天條硬性規定，不論門檻多明確）。

拒絕的替代方案：「全部一次寫成 checker」——會逼著為 T-B/T-C 硬編不存在的 IR 欄位或把定性知識假 gate 化，違反 no-fabrication。

### DD-2: 統一 Checker 介面 + control-grounded verdict

每個 T-A checker 遵循與 `classify_erc_report` 同構的契約：

```
checker(ir_or_artifact, *, control_id, thresholds) -> ValidationEvidence
  純 python，零 LLM，fail-fast（缺 IR 欄位 → 缺項清單，不預設值）
  同輸入 byte-identical 輸出
```

**關鍵創新——verdict 回溯 control**：checker 輸出的 `ValidationEvidence` 封套必帶：
- `control_id`：這條裁決依據的 control 物件 id（如 `control.si.stackup-impedance-control`）。
- `source_anchor`：control 的逐字來源（如「Multi-CB impedance-examples.html 4L-01」）——讓每個 verdict 都可回溯到 datasheet/標準，滿足 datasheet-grounded 天條。
- `threshold_provenance`：門檻值來自哪個 control body（執行期讀取，非人工複製）。

**taxonomy**：
- `ir_or_artifact`：輸入=design IR dict 或磁碟 artifact 路徑（`.net`/gerber/`.kicad_pcb`）。不允許解讀成 LLM prompt。
- `thresholds`：執行期從 ragbase control body 解析出的門檻結構（見 DD-3），非硬編常數。
- `ValidationEvidence`：既有封套型別，checker **不得**自創新輸出格式。

### DD-3: 知識↔code 執行期耦合（避免人工搬運）

batch1 的 ERC classifier 把門檻值人工複製進 code——知識更新時 code 不會同步，這是**反模式**。技能化要根治：

- **control body_md → 結構化門檻的解析層**：在 control 物件蒸餾時，除了人類可讀 body_md，額外存一個 **machine-readable threshold block**（JSON，存 `metadata_json` 或 body 內 fenced block），如 `{"metric":"impedance_se_50ohm","buildup":"4L-01","trace_width_um":245,"tol_pct":10}`。
- checker 執行期**讀 ragbase control 的 threshold block**，而非硬編。知識更新（門檻改值）→ checker 自動跟隨，零 code 改動。
- **binding metadata**：control 物件加 `checker_binding` 欄位（checker 函式 id + tier + 對映 IR 欄位路徑），形成 registry（DD-4）。

拒絕的替代方案：「checker 硬編門檻」——不可規模化、知識-code 永久脫節，正是要解決的病。

### DD-4: Verify-checker Registry（control id ↔ checker 對映表）

單一註冊表（可落 `workflow-core` 或 ragbase view）記錄每個 control 的技能化狀態：

```
control_id | tier(A/B/C) | trust_layer(1-5) | stage(C00-C04) | checker_fn | ir_fields[] | status(landed/stub/advisory)
```

- 接既有 `ORACLE_TOOLS`：T-A checker 註冊為 oracle，讓 `ExtractedRequirement.oracle_tool` 可指向它，`requirement_passfail_table()` 才能在有 oracle 執行紀錄時判 pass。
- registry 是「技能化進度」的可觀測面板——一眼看出 57 個裡幾個 landed、幾個 stub、幾個 advisory。

### DD-5: core/worker 落點 + landing plane 契約

- **T-A 純數值/IR 比對**（impedance、fuse derating、trace-width/current、part-count、tolerance-stackup 判定）→ core 純 python → `gate.py` landing verb（52 verb registry）。
- **T-A 需 pcbnew/KiCad 幾何**（DRC-類、實體 keepout 幾何比對）→ worker，經 `_forward_to_worker`，heavy 者進 MCP 43 compute tools。
- **T-C advisory** → 不落 checker，改注入 G2 design-review gate 的結構化提示（`DesignReviewRecord` scenario）。

### DD-6: 首批試點（designed→planned 的驗證錨）— 依實測分類修正

**實測發現（`control-classification.md`）推翻了初稿試點選擇**：對照 design-ir 實際 schema（極薄——僅 placement x/y、footprint、value、net connected_pads、GeometryPrimitive x/y），初稿選的 `stackup-impedance-control` 其實是 **T-B**（buildup 資料 IR/parser 都沒有）、`ipc-trace-width-current` 是 **partial→T-C**、`part-count-reduction` 是**定性→T-C**。三個都不是乾淨 T-A。修正後試點：

1. `control.verify.kicad-default-severities`（**T-A**，延伸既有 `classify_erc_report`）— 驗證「control→擴充既有 checker」路徑，最低風險。
2. `control.power.decoupling-pdn-strategy`（**T-A，唯一純 IR-native**）— decoupling cap→供電 pin 距離，純讀 `placement` x/y + `Net.connected_pads`，驗證「control→全新 IR checker + DD-3 threshold block + DD-2 control-grounded evidence」完整路徑。
3. `control.mech.board-edge-keepout`（**T-B 示範**）— 故意選一個 verified 但需 board-outline parser 的 control，驗證「T-B stub + backlog 掛帳、不硬編假欄位」機制，暴露 parser gap 的處理紀律。

試點覆蓋三條路徑（擴充既有 T-A / 全新 IR T-A / T-B 掛帳），方法可行後才規模化。

### DD-7: 技能化真正瓶頸是 parser/IR 覆蓋，非 checker 撰寫

實測分類結果：**T-A 僅 3、T-B 達 29、T-C 25**。29 個 T-B 的知識判斷力清楚，但卡在 design-ir 太薄 + gerber-core 僅 summary 級 + 無 copper-spacing/board-outline/stackup parser，導致「知道要檢什麼、卻讀不到要檢的量」。

因此 implementing 階段的槓桿點是**「補一個 parser 解鎖多個 control」**，而非逐一硬寫 checker。例如一個 copper-spacing/clearance parser 可一次解鎖 `ipc-clearance-voltage` / `safety.creepage-clearance` / `safety.functional-spacing-formula` / `si.spacing-via-return-path` 等多個 T-B。規劃 tasks 應以「parser 解鎖批次」組織，不是「57 個 checker 流水帳」。

## Risks / Trade-offs

- **T-B/T-C 佔多數，硬 gate 覆蓋有限** — mitigation：誠實分層，advisory 也是價值（結構化 design-review 提示 > 無提示）；T-B 掛帳為 IR schema 擴充 backlog，不硬編假欄位。
- **threshold block 解析層是新機制，可能與現有蒸餾流程衝突** — mitigation：threshold block 為 control 的**附加** metadata，不改既有 body_md/distill 契約；先在試點 3 個驗證。
- **registry 與 ragbase 雙寫漂移** — mitigation：registry 以 ragbase control 的 `checker_binding` 為單一真相，view 投影，不雙寫。
- **worker-side checker 依賴 pcbnew** — mitigation：core 不硬依賴 worker-only 套件（延續 AGENTS.md §4 邊界）；monolith 缺 pcbnew 是預期，非回歸。

## Critical Files

- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py` — `classify_erc_report` 黃金範本 + worker-side checker 落點。
- `packages/workflow-core/.../validation_evidence.py` — `ValidationEvidence` 封套 `_ADAPTERS`，checker 輸出必經。
- `packages/workflow-core/` — `ORACLE_TOOLS` 註冊、registry 落點、G2 `DesignReviewRecord`（advisory 注入）。
- `packages/design-ir/` — IR schema（`ComponentInstance`/net/trace/stackup/`GeometryPrimitive`）：T-A/T-B 分界的判準來源；T-B 擴充需求落點。
- `skills/bodesign/scripts/gate.py` — landing plane，T-A core checker 的 verb 落點。
- `services/mcp/server.py` — 若 checker 需 MCP 曝露：`_h_*` handler + schema list 兩處。
- `.specbase/ragbase.sqlite` — control 物件；加 `checker_binding` + threshold block metadata。
- `specs/architecture.md` — Verification Baseline 章節：技能化架構全貌同步。
