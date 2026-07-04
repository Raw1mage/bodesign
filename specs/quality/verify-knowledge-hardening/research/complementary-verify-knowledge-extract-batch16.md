# Batch16 萃取檔 — C00 需求品質 + C01/DFA 可組裝 + DFM 製造性

> 著作權邊界：僅萃取公開工程準則 + 定性方法論 + 來源錨點，不整段複製原文。
> no-fabrication：每值附逐字來源引文；查無來源標 UNVERIFIED 不臆造、不硬填 draft/rib 數值。
> subagent ses_0d4815ec1 純研究產出，本輪 read_subsession 逐字核對後落檔。
> 主來源：Wikipedia《Design for Assembly》引 Boothroyd DFA Handbook 1980 / Boothroyd-Dewhurst DFMA（教科書級）；
> Bayer/Covestro Part & Snap-Fit Design Guide（26頁，原廠原文級）；
> Wikipedia《Software Requirements Specification》引 ISO/IEC/IEEE 29148（標準轉述級）。

---

## control.requirements.prd-quality-characteristics（confidence=verified，ISO/IEC/IEEE 29148 標準轉述級）

| 規則 | 準則 | 逐字來源引文 | 出處 |
|---|---|---|---|
| 個別需求特徵 | 每條需求須 necessary（必要）、appropriate（適當）、unambiguous（無歧義） | 「Individual requirements shall hence be necessary, appropriate, and unambiguous」 | Wikipedia SRS 引 ISO/IEC/IEEE 29148 |
| 需求集合特徵 | 整組須 complete（完整）、consistent（一致）、feasible（可行）、comprehensible（可理解） | 「A set of requirements shall moreover be complete, consistent, feasible, and comprehensible」 | 同上 |
| 需求是 what 非 how | 需求只講需要什麼，獨立於設計，不講如何做 | 「Requirements should strictly be about what is needed, independently of the system design, and not how the software should do it」 | 同上 |
| requirements smell 反樣式 | 避免 subjective language / ambiguous adverbs/adjectives / superlatives / negative statements / comparative phrases / non-verifiable terms / totality terms | 「Examples of requirements smells are subjective language, ambiguous adverbs and adjectives, superlatives and negative statements... non-verifiable terms or terms implying totality should also be avoided」 | 同上 |

**checker**：C00 PRD 完整性 gate（LLM 審 PRD 條目是否可驗證/無歧義/可追溯；requirements smell 反樣式偵測），對位 bodesign C00 PRD 產出。
**織網**：`references` `control.datasheet-grounded-claims`（需求可驗證性↔主張需接地）、`control.deterministic-validation-before-fab`（需求可測試性↔送廠前驗證）。

---

## control.dfa.part-count-reduction（confidence=verified，Boothroyd DFMA 教科書級）

| 規則 | 準則 | 逐字來源引文 | 出處 |
|---|---|---|---|
| DFA 核心目標 | 減少分離零件數是降組裝成本最重要因素 | 「the most important factor in reducing assembly costs was the minimization of the number of separate parts in a product」 | Wikipedia DFA 引 Boothroyd |
| 零件消除三準則 | 逐一問三題判零件能否消除/合併：①相對已組裝件是否需**相對運動**②是否必須**不同材料**（電氣/絕緣/隔離）③是否為**組裝/拆解**所必需 | 「he introduced three simple criteria which could be used to determine theoretically whether any of the parts in the product could be eliminated or combined」 | Boothroyd DFA Handbook 1980 |
| grasp/orient/insert 因子 | 提供易抓取/移動/定向/插入的 feature 降組裝時間 | 「parts are provided with features which make it easier to grasp, move, orient and insert them, this will also reduce assembly time」 | 同上 |

**checker**：C01/BOM 零件數合理性審查（定性三問法：相對運動/不同材料/組裝必需→判零件可否消除合併）+ grasp-orient-insert 因子 + 對稱化利自動送料。
**織網**：`references` `control.mech.snap-fit-geometry`（batch13，snap-fit 為減扣件手段）、`control.mfg.assembly-courtyard`（batch11，組裝製造域）。

---

## control.dfm.injection-molding-geometry（confidence=partial，Bayer 原廠原文級但缺 draft/rib 逐值）

**已 verified（Bayer 原廠原文）**：

| 規則 | 量化值 | 逐字來源引文 | 出處 |
|---|---|---|---|
| 均勻壁厚 | 壁厚不均→縮水/voids | 「[non-uniform] sections will usually result in sinks and/or voids」 | Bayer Part Design |
| 漸縮設計增撓度 | 厚度 h 或寬 b 漸縮 → deflection 增 >60% | 「either its thickness (h) or width (b) tapers... increases permissible deflection by more than 60%」 | 同上 |
| 重複拆裝 strain 折減 | 頻繁分離/再接合用額定值 60% | 「design is for frequent separation and rejoining, use about 60% of these values」 | 同上 |
| 插入/自鎖角 | insertion angle 30°（易入）、self-lock lead/return angle 45° | 「Angle of inclination (a) = 30°」「The lead and return angle is 45°」 | 同上 |
| 材料摩擦係數表 | PS 0.40–0.50、SAN 0.45–0.55、PC 0.45–0.55、PMMA 0.50–0.60、ABS 0.50–0.65、PE 0.55–0.60、PVC 0.55–0.60（×1.2 修正） | 「PS 0.40-0.50 (x1.2) / PC 0.45-0.55 / ABS 0.50-0.65 / PVC 0.55-0.60」 | Bayer Table 3 |

**UNVERIFIED 待補（不硬填）**：draft angle 模具拔模角最小值（0.5–2°/側 未命中逐字）、均勻壁厚 mm 範圍與壁厚比（<3:1）、rib 厚=壁厚 50–60%、boss 外徑=2×釘徑、圓角半徑（內圓角≥0.5×壁厚）— injection molding design guide PDF 連結全 404/JS 導頁失敗，標 confidence=partial，後批換有效來源補齊。
**織網**：`references` `control.mech.snap-fit-geometry`（batch13，同塑膠件力學）、`control.env.conformal-coating-thickness`（batch11，塑膠/塗層製造性）。

---

## UNVERIFIED / 未取得（誠實掛帳，不臆造）

- draft angle 最小值、壁厚 mm/壁厚比、rib 厚 50–60%、boss 幾何、圓角準則 — injection molding design guide PDF 全失效，嚴禁憑記憶填。
- ID-CMF 可製造銜接（分模線對外觀、texture/咬花對拔模角加成、MoldTech 咬花等級對應拔模角增量、表面處理公差）— 完全未命中 CMF-manufacturability 專屬來源，全數 UNVERIFIED，**不蒸**。
- INCOSE Guide for Writing Requirements 逐 rule（R1–R42）— INCOSE 官方 PDF 失效；取得的是 29148 經 Wikipedia 轉述特徵集，標「29148 特徵集 verified、INCOSE 逐 rule UNVERIFIED」。

## Batch16 新增 control 物件（2 verified + 1 partial）

1. `control.requirements.prd-quality-characteristics`（verified）
2. `control.dfa.part-count-reduction`（verified）
3. `control.dfm.injection-molding-geometry`（partial，數值待補）

累計 control：50 → 53。
