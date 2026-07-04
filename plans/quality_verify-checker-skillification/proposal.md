# Proposal: quality_verify-checker-skillification

## Why

- **知識已備、技能未成。** `quality_verify-knowledge-hardening` 已把 8 大領域 PCB verify 判斷力蒸進 ragbase，累積 **57 個 `control.*` 物件（44 verified / 10 partial / 3 todo）**，每值附逐字 datasheet/標準來源錨點。但這些知識目前**幾乎完全與可執行 checker code 脫節**——57 個裡只有 **1 個**（`control.dfm.jlcpcb-ipc-thresholds` 等 → `eda-bridge/kicad_emit.py::classify_erc_report()`）被人工轉成確定性 checker 落地。
- **脫節的知識庫 = 無法在 pipeline 上發揮的判斷力。** bodesign 的核心哲學是「展示可靠度」——確定性驗證 + 對照良品交叉檢核，LLM 只做上游抽取/裁決。57 個 control 物件正是「怎麼判斷 PCB 設計對錯」的裁判規則，但若不變成 pipeline 上實際執行的 gate，它們只是靜態文件，C00–C04 設計流程跑過去時**不會**被這些規則檢核。
- **已有成熟的注入骨架可複用。** repo 已有 5 層信任驗證架構（ERC/DRC · crosscheck · SPICE · EMC/thermal · constraint-solving）、`ValidationEvidence` 證據封套、`ORACLE_TOOLS` 註冊表、`gate.py` landing plane（52 個確定性 verb）。技能化**不需造新輪子**，而是把 control 知識系統化接進這些既有機制。

## Original Requirement Wording (Baseline)

- 「假設目前收集的知識夠豐富了，剩下的就是技能化。請開 plan 設計，並把你建議的方法寫出來」

## Requirement Revision History

- 2026-07-04: initial draft created via plan-init.ts

## Effective Requirement Description

1. 設計一套**系統化方法**，把 ragbase 的 57 個 `control.*` verify 判斷知識物件，轉成插進 bodesign 既有驗證骨架的**可執行 checker**。
2. 方法必須守住 bodesign 天條：**確定性驗證**（checker 本身零 LLM）、**no-silent-fallback**（缺輸入 fail fast + 缺項清單）、**datasheet-grounded**（電氣門檻回溯 control 物件的來源錨點）、**no-fabrication**（partial/UNVERIFIED 知識不得偽裝成可硬性 gate 的確定規則）。
3. 明確劃定「**確定性 checker** vs **LLM 裁決**」的邊界：哪些 control 可純程式檢核（有明確數值門檻 + 可從 design IR 讀到的量），哪些只能當 LLM design-review 的結構化提示（定性準則、需語意判斷）。
4. 產出可執行的 phased 實作計畫（tasks.md），本 plan 階段**只做設計不實作**（designed gate 前收斂）。

## Scope

### IN

- **control → checker 分類法（taxonomy）**：把 57 個 control 依「可確定性執行程度」分三層（machine-checkable / semi / advisory-only），並對映到 5 個信任層與 C00–C04 階段。
- **Checker 注入架構設計**：定義 checker 的統一介面（輸入=design IR/artifact、輸出=`ValidationEvidence` 封套）、註冊機制（接 `ORACLE_TOOLS` / `gate.py` landing verb）、與 control 物件的**證據回溯連結**（checker verdict 引用 `control.*` id + 其 source anchor）。
- **知識↔code 耦合機制**：設計 checker 如何在執行期引用 ragbase control 的門檻值/來源，讓「知識更新 → checker 門檻同步」不再靠人工複製（避免 batch1 ERC classifier 那種一次性人工搬運）。
- **確定性 vs LLM 邊界契約**：明確規則——只有 `confidence=verified` 且有可從 IR 取得的量化門檻的 control 才可成為硬性 gate；partial/定性者降級為 advisory design-review 輸入。
- **IDEF0 + GRAFCET 建模**：技能化 pipeline 的功能分解與執行狀態機。
- **Phased 實作 tasks**（設計產出，非本階段執行）。

### OUT

- **實際實作全部 57 個 checker**（本 plan 只設計方法 + 首批試點分類；實作是後續 implementing 階段）。
- **新增 verify 知識蒸餾**（知識已判定足夠；補 UNVERIFIED 缺口是另一條線）。
- **修改既有 5 層驗證骨架的核心語義**（只擴充、不改寫既有 `classify_erc_report` / `validation_evidence.py` 行為）。
- **送廠 gate 決策流程**（send-to-fab 仍需使用者明確批准，不在技能化範圍內動它）。

## Non-Goals

- 不把 partial/todo 知識強行 gate 化（no-fabrication：定性/未驗證知識不得偽裝成確定性硬 gate）。
- 不引入新 fallback（缺 IR 欄位 → fail fast + 缺項清單，不用預設值續跑）。
- 不讓 LLM 參與 checker 的確定性計算（LLM 只在上游抽取 IR、下游裁決 advisory，比對/門檻判斷全確定性）。

## Constraints

- **確定性天條**：每個 machine-checkable checker 必須零 LLM、同輸入 byte-identical 輸出、fail fast。
- **注入既有骨架**：checker 輸出必須是既有 `ValidationEvidence` 封套（`validation_evidence.py` `_ADAPTERS` 家族），流回 C00 `evidence_returns/`；不另立平行證據系統。
- **core/worker 邊界**：純 python 確定性檢核（IR 數值門檻、幾何比對）落 core；需 pcbnew/KiCad-mutating 的落 worker，經 `_forward_to_worker`。
- **datasheet-grounded**：任何電氣門檻 checker 的門檻值必須可回溯到 control 物件的逐字來源錨點；無來源的規格值 = BLOCKING，不得臆測。
- **landing plane 契約**：確定性 repo-local verb 落 `skills/bodesign/scripts/gate.py`（52 verb registry），heavy 者才進 MCP 43 compute tools。

## What Changes

- 新增一套 **control-object → executable-checker 的映射方法與注入架構**（本 plan 設計；後續實作）。
- ragbase control 物件從「靜態知識」升級為「pipeline 上實際執行的裁判規則來源」。
- C00–C04 設計流程跑過時，verified 量化 control 會被自動確定性檢核並產出 evidence 封套。

## Capabilities

### New Capabilities

- **Verify-checker registry**：control id ↔ checker 的註冊表，帶「可執行程度」分層與階段/信任層對映。
- **Control-grounded checker interface**：統一 checker 介面，verdict 引用 control id + source anchor，門檻值執行期讀自 ragbase（知識-code 不再脫節）。
- **確定性/advisory 二分閘**：verified+量化 → 硬 gate；partial/定性 → LLM design-review 結構化提示。

### Modified Capabilities

- **既有 5 層驗證骨架**：從「少數人工 checker」擴充為「control 知識系統化驅動的 checker 群」，封套/證據回流機制不變。

## Impact

- **Code**：`packages/eda-bridge/`（checker 落點，比照 `classify_erc_report`）、`packages/workflow-core/`（`ORACLE_TOOLS` / `validation_evidence.py` 註冊）、`skills/bodesign/scripts/gate.py`（landing verb）、`services/mcp/server.py`（若需 MCP 曝露：handler + schema 兩處）。
- **Knowledge**：`.specbase/ragbase.sqlite`（control 物件被執行期引用；可能加 checker-binding metadata）。
- **Docs**：`specs/architecture.md`（Verification Baseline 章節擴充技能化架構）。
- **無 breaking change**：既有 checker 行為與封套語義保持向後相容。
