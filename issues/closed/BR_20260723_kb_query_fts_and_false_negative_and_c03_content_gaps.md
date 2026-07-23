# BR_20260723 — C03 domain-KB 可發現性缺陷（FTS AND 假陰性）+ 少數真內容缺口

- **Severity**: Major（可發現性缺陷）+ Minor（內容缺口）
- **Component**: `services/mcp/server.py` `_h_kb_query`（ragbase FTS 檢索）／ ragbase KB store（C03 EE 段內容覆蓋）
- **Status**: CLOSED（2026-07-23 修復落地）— Fix1 `_h_kb_query` mode=all/any OR-recall 已 commit `320bed0`，`test_kb_tools` 17/17 綠；Fix2 三真缺主題已 ingest 為 graded control（`design_suggest_*.md` graduated 進 `specs/knowledge_c03-ee-design-kb/`）
- **Filed**: 2026-07-23
- **Scope / venue**: bodesign repo（本 repo 內修，非跨 repo；plan slug `knowledge_c03-ee-design-kb`）
- **Related**: `plans/knowledge_c03-ee-design-kb/research/c03-capability-diagnosis.md`（設計能力邊界診斷）、`issues/BR_20260704_kb_skill_exposure_window_not_knowledge_source.md`（closed，KB 曝光窗前案）

---

## Symptom（verbatim 觀測）

盤查「C03 電路設計層是否缺乏知識」時，對 `bodesign_kb_query` 下 C03 EE 設計術語，**多詞自然語言 query 幾乎全數 0 命中**：

| query（多詞，自然語言） | hits | 實況 |
|---|---|---|
| `regulator LDO buck decoupling capacitor SPICE model derating IPC impedance EMC` | **0** | 假陰性 |
| `signal integrity return path crystal oscillator layout` | **0** | 假陰性 |
| `fuse derating MOV surge NTC inrush decoupling PDN stackup impedance crystal` | **0** | 假陰性 |
| `crystal oscillator load capacitor` | **0** | **假陰性**（物件確實存在，見下） |
| `decoupling cascade regulator topology LDO buck boost selection thermal theta-JA` | **0** | 假陰性 |
| `LDO buck boost topology selection` | **0** | 真缺口（見下） |

但**單詞 query 全部命中**、且物件早已 `confidence: verified`、帶 machine-checkable `threshold_block`：

| query（單詞） | hits | 頂端命中 |
|---|---|---|
| `decoupling` | 19 | `control.power.decoupling-pdn-strategy` (verified, threshold 12.5mm) |
| `fuse derating` | 5 | `control.protection.fuse-ptc-derating` (verified, threshold 0.75) |
| `crystal` | 10 | `control.si.crystal-oscillator-layout` (verified) |
| `regulator` | 11 | `step.sch.dcdc-review-checklist` 等 |

`kb_get` by-id 直接命中證實物件在庫：`control.power.decoupling-pdn-strategy` / `control.protection.fuse-ptc-derating` / `control.si.crystal-oscillator-layout` / `control.protection.mov-surge-selection` 皆 verified、provenance 錨到 batch14/15/18、`updated_at` 1783xxx（已 ingest）。

**最關鍵的單一反例**：`crystal oscillator load capacitor` 回 **0**，但 `control.si.crystal-oscillator-layout`（body 明含 "load cap"）就在庫裡且單詞 `crystal` 撈得到。**知識在庫、cold-context agent 用自然多詞句撈不到 = 對該 agent 而言等於不存在。**

---

## RCA（根因，evidence-anchored）

### 根因 1（Major）：FTS `MATCH` 是 AND-of-all-tokens，多詞 query 命中率隨詞數單調崩潰

`services/mcp/server.py` `_h_kb_query`（L908-953）對 ≥3 codepoint 的英文 token 走 FTS5 `ragbase_fts MATCH ?`（L931，`base_from` JOIN `ragbase_fts`，`bm25()` 排序）。SQLite FTS5 的 `MATCH` 對「以空白分隔的多個 bare token」預設語義是 **implicit AND**——**每一個 token 都必須在同一文件出現**，該文件才進入候選。

- trigram tokenizer（doctrine「ragbase FTS5 uses the trigram tokenizer」，server L837）把每個詞切成 3-gram；一個文件要命中一個長 query，得同時含**所有**詞的 3-gram。
- 後果：query 詞數越多 → AND 條件越嚴 → 任一詞在目標文件缺席即整筆 miss。`crystal oscillator load capacitor` 四詞，只要 `control.si.crystal-oscillator-layout` 的 body/title 缺其中任一詞面（例如它寫 "load cap" 而非 "load capacitor"、或 "oscillator" 在 title 但 "capacitor" 只以 "cap" 出現），整筆就被 AND 濾掉。
- **這不是內容缺席，是檢索召回策略問題。** query 描述設計「情境」（自然會用多詞），但索引要求全詞交集——兩者天生對不上。

證據：server L920-933 的 where 組裝只把整串 `q` 當單一 `MATCH ?` 綁定，未做 OR 展開／未降級為 per-token OR／未提供 relevance-only（非過濾）模式。matchMode 只分 `fts`(全 ≥3) / `like-scan`(全 <3 CJK) / `hybrid`——**沒有「多詞英文 → OR/ranked」這一檔**，所以多詞英文一律落進最嚴的 AND。

### 根因 2（Minor）：少數 C03 EE 設計主題確實未 ingest（真內容缺口）

即使改善檢索，以下主題**單詞也撈不到專屬規則**，屬 `ee-design-advisory.md` prose 尚未蒸餾進 KB：

- **regulator 拓撲選型**（LDO vs buck vs boost 的適用條件 + watch 表）：`LDO buck boost topology selection` → 0；`regulator` 命中的都是 review-checklist / failure-mode / sourcing，**沒有「topology selection」決策規則**。來源在 `ee-design-advisory.md` §Power tree & regulator selection（L30-40）尚未 ingest。
- **SI 需求數值**（Z0 / 3W / λ/10 / termination 的 C03→C04 交付數字）：`signal integrity termination` → 僅 1 命中且是 C04 `layout-scoring-rubric`，非 C03 SI 需求規則。
- **I²C / SPI pull-up / series-termination sizing**：`I2C pull-up` → 2 命中皆泛用（datasheet-validation / erc-gate），**沒有 pull-up 計算規則**（`Rp_min=(VCC-VOL)/IOL`、`Rp_max=t_rise/(0.8473·Cb)`），雖 `schematic-analysis.md` §I2C Bus 有完整公式但未進 KB。

### 明確「不是 bug」的區分（守 by-design，不亂修）

- **`kb_query` 對 CJK 短詞走 LIKE-scan（score=0, recency-ordered）**：by-design（trigram 對 <3 codepoint 無效），不是本 BR 範圍。
- **batch14/15/18 已 ingest 且 verified**：**不是缺口**——先前診斷「未 ingest」是**用長 query 誤判造成的假陰性**，本 BR 據實更正。這些 control 不需重 ingest。
- **fail-fast on missing KB（`KB_UNAVAILABLE`）**：by-design 天條，正確，不動。
- **缺口 B「設計合成能力」（pin-obligation → 輔助被動件合成零工具化）**：**不在本 BR**——那是撞 bodesign「LLM only extraction/adjudication」哲學的產品決策，另案（見 capability-diagnosis 報告）。本 BR 只治「知識在庫但撈不到」+「少數主題未上架」的檢索/內容層問題。

---

## Impact

- **誰受影響**：所有 cold-context 走 C03（及任何 stage）的 agent。doctrine 明令「Call `bodesign_kb_query` before judgment-heavy design steps (layout, EMC, SI, derating)」——但 agent 自然會用多詞情境句查詢，落進 AND 假陰性，撈到 0 就可能誤判「KB 沒有這知識」而跳過 recall、或回退硬幹（違反 KB-first 紀律）。
- **KB 作為被動資產的核心價值（靠調用拉到眼前）在多詞查詢下失效**：知識越多、query 越具體，miss 機率越高——與「KB 越厚越有用」的預期完全相反。
- **波及面不限 C03**：FTS AND 是 `_h_kb_query` 全域行為，C04/DFM/EMC 的多詞查詢同樣受害，只是 C04 內容厚、單詞召回夠用而較少暴露。

---

## Fix Plan

### Fix 1（Major，根因 1）：`_h_kb_query` 多詞英文 → OR-ranked 召回，AND 改為可選精確模式

**目標**：多詞 query 預設「命中任一詞、bm25 排序」（召回優先），而非「命中全部詞」（精確優先）。守 no-silent-fallback：模式可見、回傳自描述。

候選做法（實作時擇一、以最小改動 + 最不破壞既有精確查詢為準）：

1. **per-token OR 展開**：把 `q` 切詞後組成 FTS5 `"t1" OR "t2" OR …`，`bm25()` 排序自然把「命中多詞」排前、「命中單詞」仍可見。matchMode 增列 `fts-or`。這是 FTS5 原生語法，改動集中在 L920-933 的 where 組裝。
2. **保留 AND 為 opt-in**：新增 `mode=all`（或 query 前綴/參數）走現行 implicit-AND，給「我就是要全詞交集」的精確場景。預設走 OR。
3. **payload 自描述**：matchMode 如實回 `fts-or`/`fts-and`，讓 0 命中與召回模式一眼可辨（延續現行「matchMode 讓 0 hits self-describing」設計）。

**驗證**（回歸測試落 `tests/test_kb_tools.py`）：
- `crystal oscillator load capacitor` → 必須命中 `control.si.crystal-oscillator-layout`（目前 0 → 應 ≥1）。
- `regulator LDO buck decoupling` → 必須命中 decoupling/regulator 相關 control（目前 0 → 應 ≥1）。
- 既有單詞 query（`decoupling`/`fuse derating`/`crystal`）命中集不得退化。
- 精確 `mode=all` 對多詞仍走 AND（保留能力）。
- matchMode 欄位如實反映實際模式。

### Fix 2（Minor，根因 2）：ingest 三個真缺主題（走 plan-builder producer 鏈，不手改 sqlite）

從既有 prose 蒸餾、帶 provenance 分級（`[primary]`/`[rot]` 對齊 `pcb-layout-rules-compendium.md` 慣例），ingest 為 `control.*`/`concept.*`：

- `control.power.regulator-topology-selection` ← `ee-design-advisory.md` §Power tree（LDO/buck/boost 適用條件 + watch；標 heuristic/rot，非 datasheet-backed）。
- `control.si.interface-requirements` ← `ee-design-advisory.md` §SI + `schematic-analysis.md`（Z0/3W/λ10/termination 為 C03→C04 交付數值）。
- `control.sch.pullup-termination-sizing` ← `schematic-analysis.md` §I2C Bus / §SPI（`Rp_min`/`Rp_max` 公式，datasheet/bus-spec grade）。
- 誠實掛帳：無來源主題標 UNVERIFIED，不臆造、不蒸空殼（延續 batch14/15 慣例）。

**驗證**：ingest 後 `LDO buck boost topology selection` / `signal integrity termination` / `I2C pull-up` 各命中對應新 control；provenance lineage 錨到來源 prose；confidence/source_weight 如實。

### Fix 3（收尾，可選）：GUIDE 補一行檢索指引

`stages/c03-ee/GUIDE.md` step 4/5 補註：`bodesign_kb_query` 多詞為 OR-ranked（Fix 1 後），設計規則可直接用情境詞撈；step 5「輔助件完備性」檢查可引 KB 的 threshold_block（decoupling 12.5mm / fuse 0.75 / crystal load cap 公式）做機檢依據——此即 `knowledge_c03-ee-design-kb` plan 選項 4「用 A 織密 B 校驗面」的落點。

---

## Validation Plan（整體）

1. `tests/test_kb_tools.py` 新增多詞召回回歸（Fix 1 五案 + Fix 2 三案），全綠。
2. `BODESIGN_DEV=1 ./mcpctl.sh restart` 後，對 Symptom 表的多詞 query 逐一重跑，命中數由 0 轉正。
3. 單詞查詢命中集不退化（防止 OR 化引入雜訊或破壞既有排序）。
4. `event_record` 記修復收尾；若動 `_h_kb_query` 行為，同步 `specs/architecture.md` KB 檢索語義段（或註記 Verified No doc changes）。

## Fix venue

本 repo 內修（`knowledge_c03-ee-design-kb` plan 承接）。Fix 1 動 `services/mcp/server.py`（core，需 `mcpctl.sh restart` 生效）；Fix 2 走 host-side specbase `producer.ts` ingest（不重啟）；Fix 3 動 skill GUIDE。三者可分批，Fix 1 為主線（治可發現性根因）。
