# Design: knowledge_c03-ee-design-kb

## Context

使用者盤查「C03 是否缺乏功能和知識」，經深度診斷（`research/c03-capability-diagnosis.md`）+ recall-before-crawl 收斂出真實缺口，並接入兩張同日 BR：

- **BR_A**（`BR_20260723_kb_query_fts_and_false_negative_and_c03_content_gaps.md`）：C03 設計知識**在庫但撈不到**——`_h_kb_query`（`services/mcp/server.py` L908-953）多詞英文走 FTS5 implicit-AND，命中率隨詞數單調崩潰（`crystal oscillator load capacitor`→0，但物件在庫、單詞 `crystal` 命中）；另有 regulator 拓撲選型 / SI 需求數值 / pull-up sizing 三主題確實未 ingest。
- **BR_B**（`BR_20260723_c03_composer_accepts_pinout_only_no_passive_completeness_gate.md`，high）：consumer(aiguard C03) 實測——composer 忠實畫出 pinout-only spec，ERC/fidelity/check_c03 全 PASS，卻是 STM32N657 零去耦、memory 零 pull-up、radio 零 matching 的不可用板。method（`pinout-to-circuit-method.md` 9-class obligation 表）是 load-bearing prose，**無 machine backstop**。

使用者定調 = 選項 4「補 A + 用 A 織密 B 的校驗面」。兩張 BR 是**同一個病的兩面**且**互為依賴**：BR_B 的 passive-completeness gate 需要判準 threshold，而那些 threshold 正是 BR_A 修好後可 `kb_query` 的 KB 規則。故合併規劃成一條依賴序。

Q1 架構層已查證：串 KB = 改 ragbase（read-only 讀 `.specbase/ragbase.sqlite`，寫入端 specbase producer）；opencms 早 drop、不涉入。

## Goals / Non-Goals

**Goals**

- **G1（BR_A Fix1，可發現性根因）**：`_h_kb_query` 多詞英文改 OR-ranked 召回（bm25 排序），AND 降為 opt-in `mode=all`；matchMode 自描述。多詞情境句撈得到在庫物件。
- **G2（BR_A Fix2，內容缺口）**：ingest regulator 拓撲選型 / SI 需求數值 / I²C-SPI pull-up sizing 三主題為 graded `control.*`（provenance 分級，heuristic 標 rot、datasheet/bus-spec 標 primary），走 specbase producer 鏈。
- **G3（BR_B，passive-completeness gate）**：新增一道校驗閘，把 9-class per-pin obligation 表機器投影到已組出的圖——active IC 零必要被動件 = HARD FAIL 或顯式 waiver；gate 判準引用 G2/既有 KB threshold；支援 honest-subset waiver。
- **G4（缺口 B，evidence-backed 有據建議合成層 — 使用者拍板方案 C 立案）**：新增 `design_suggest.py` 生成器族，把「circuit design intent → concrete passive topology + 選型」的推導做成**有據建議**——引擎依軌 A KB graded 規則算值、標 evidence source、輸出 `status=suggested` draft + 可貼進 spec 的 `spec_fragment`，人 review 後才 commit。首發三 pattern：I2C pull-up / crystal load cap / series termination，同一 `compute→anchor→draft→spec_fragment` 範式，可續擴（去耦 / TVS / feedback 分壓）。**這是「有據的建議」不是「被宣稱的設計」——守哲學紅線內的合成（見 DD-9）。**

**Non-Goals**

- **不做「被宣稱的設計」合成**——引擎永不替人拍板選型、永不自動 mutate spec、永不把建議標成 approved/final；G4 的合成是 `status=suggested` draft + evidence，決策權留在人手上（DD-9）。不代 LLM 決定「這顆晶片要不要這個介面」這種架構決策；只在既定 intent（「這條 I2C 是 4-device 開漏匯流排」）下算出 concrete 被動件建議。
- 不改 `compose_schematic` 建 spec 的行為（BR_B 明文：忠實建 spec 是對的；partial/interface-subset 合法）。
- 不改 `pinout-to-circuit-method.md`（method doc 正確完整，要的是 machine backstop 不是改寫）。
- 不碰 C04/DFM KB；不重 ingest batch14/15/18（已 verified 在庫）。

## Decisions

- **DD-1：兩張 BR 合併為一 plan、以依賴序執行。** A1(檢索修) → A2(內容 ingest) → A3(passive gate)。理由：A3 gate 判準要引 A2 ingest 的 threshold；A2 ingest 後的知識要靠 A1 修好的檢索才撈得到。拒絕方案：三者並行（A3 會撈不到判準）、或分三 plan（耦合過緊、重複 lifecycle 開銷）。
- **DD-2：passive-completeness gate 是「obligation 表的機器投影」，非新知識、非合成。** SSOT = `pinout-to-circuit-method.md` 9-class 表；gate 把它投影到已組出的圖判完備性。這是守哲學的關鍵界定——校驗一張已存在的圖，不是替 LLM 生設計。
- **DD-3：gate seam 由 bodesign 架構裁決（三候選），本 plan 記選型準則不預先綁死 API。** 候選：(a) `compose_schematic(passive_completeness=True)`→`passive_gaps[]`（最早、最 fail-loud）；(b) `analyze_schematic` 新規則 `PC-001(high)`（騎既有 finding envelope）；(c) `check_c03` R5（滾進 C04 入口 gate）。實作期擇一或組合，以最小改動 + 對齊既有失敗語義為準。**gate policy（什麼算 mandatory obligation、waiver 語義）升使用者，非 agent 拍板。**
- **DD-4：honest-subset waiver 必須支援。** interface-subset / reverse-eng baseline 可用 `Netlist_Status.md` 宣告 documented gap + provenance waiver 通過——no-silent-fallback：waiver 要顯式、帶 provenance，不強塑被動件到刻意 partial 的交付物。
- **DD-5：檢索改 OR 化不得退化既有單詞召回與精確查詢。** 保留 `mode=all` 精確 AND；回歸測試鎖既有單詞命中集不變。
- **DD-6**: DD-6 (A3.1 user-gate 裁決): passive-completeness gate 第一版 HARD FAIL 只覆蓋三類 pinout-to-circuit-method 明標的 silent killer——(1) active IC power pin 零去耦電容、(2) clock/XTAL pin 無 load cap、(3) boot/strapping pin 未拉定態。其餘 6 class (analog VREF filter、GPIO idle pull、I2C pull-up、SPI series term、NC/DNC、ground/exposed pad) 第一版列 WARN 不阻擋。理由: 這三類是 method 明標 silent killer (floating-PSRAM 級災難、latch-up、undefined boot)，誤報率低、共識強；其餘 class mandatory 認定情境依賴 (GPIO idle pull 依 bus、analog VREF 不一定需 filter、NC 依 datasheet)，漸進強化避免誤報合法 partial。gate 判準 threshold 引用軌 A 已 ingest 的 KB 規則 (decoupling cascade、crystal load cap 公式 2·CL−Cstray)，非硬編。honest-subset waiver (DD-4) 對三硬類仍支援: interface-subset/reverse-eng baseline 可用 Netlist_Status.md 顯式 waiver + provenance 通過。

- **DD-7（缺口 B 立案定調：方案 C—有據建議）**。proposal 預留的缺口 B（設計合成能力）經 BR_20260723c 升使用者拍板，使用者決定：**方案 C（evidence-backed 有據建議）** — bodesign 正式長「有據建議」電路設計能力層（非方案 A 只校驗、非方案 B 完整合成）。拒絕方案 A（只校驗）理由：使用者痛點是「從 intent 走到真電路」，校驗層只告知缺什麼、不生件；拒絕方案 B（完整合成）理由：引擎替人拍板選型撞 honesty 天條。方案 C 是唐線內的合成（見 DD-9）。
- **DD-8（三 pattern 同範式，非三孤例）**。首發三 pattern — I2C pull-up（Rp=f(VCC,Cb,speed)，錂 NXP UM10204）/ crystal load cap（C_load=2·(CL−Cstray)，錂 crystal-oscillator-layout verified，算+核對）/ series termination（R=Z0 microstrip，錂 interface-requirements，依物理量算+C04 handoff）— 均走同一 `intent → 算值（值算非硬編）→ 錂 evidence+provenance → status=suggested draft → spec_fragment → 人 commit` 範式。這是**一個可擴展能力層**（去耦/TVS/feedback 分壓 pattern 都能套同範式），不是三個寫死的獨立函式。
- **DD-9（守哲學的合成邊界）**。方案 C 守 bodesign「展示不宣稱」哲學的四條紅線：(1) **建議非決定**（`status` 永 suggested、`review_required:true`）；(2) **值算非猜**（落在 KB 規則公式算出的窗內，非硬編）；(3) **evidence 可港**（每個建議值錂 KB 物件 + provenance source_anchor；若 KB 只 concept-verified 而具體公式未逐字命中，必顯式標 form_note）；(4) **人決策**（引擎不 mutate spec、不寫檔、不翻 approved；人 review spec_fragment 後才 merge）。crystal verify 模式額外展現「算+核對」（算應然值、核對 spec 現值→ CONSISTENT/mismatch），對齊 bodesign「展示可靠度—對照交叉檢核」哲學。

## Risks / Trade-offs

- **OR 化引入雜訊**（多詞 OR 召回過寬、低相關物件混入）— mitigation：bm25 排序 + `limit`；回歸測試斷言目標物件排前、既有單詞集不退化。
- **passive gate 誤報**（把合法 partial/interface-subset 判 FAIL）— mitigation：DD-4 waiver 機制 + BR_B validation 第 3 案（honest-subset waiver 應 PASS）。
- **gate policy 過嚴/過鬆**（mandatory obligation 認定爭議）— mitigation：DD-3 policy 升使用者；gate 先覆蓋最硬的「power pin 零去耦」，其餘 class 漸進。
- **A1 動 core（server.py）需 restart_self 生效**——非 hot-reload；mitigation：先寫 `test_kb_tools.py` 回歸再改，restart 後對 BR_A Symptom 表逐一驗。

## Critical Files

- `services/mcp/server.py`（`_h_kb_query` L908-953）— A1 檢索改 OR-ranked 的落點；core，需 `mcpctl.sh restart`。
- `tests/test_kb_tools.py` — A1 回歸測試（多詞召回 + 單詞不退化）。
- specbase `producer.ts`（host-side）— A2 ingest 三主題的執行路徑（不重啟）。
- `skills/bodesign/stages/c03-ee/references/ee-design-advisory.md` + `engines/kicad/references/schematic-analysis.md` — A2 ingest 的來源 prose（regulator 拓撲 / SI 數值 / pull-up 公式）。
- `packages/eda-bridge/bodesign_eda_bridge/composer.py`（`compose_schematic`）/ `engines/kicad/scripts/analyze_schematic.py` / `packages/workflow-core/bodesign_workflow_core/check_c03.py` — A3 gate seam 三候選落點。
- `skills/bodesign/stages/c03-ee/references/pinout-to-circuit-method.md` — A3 gate 的 obligation SSOT（9-class 表，只讀不改）。
- `tests/test_composer.py` / `tests/test_check_c03.py` — A3 回歸。
