# Batch19 萃取檔 — C02 機構補齊（tolerance stack-up + connector 機構 keepout）

> 著作權邊界：僅萃取公開工程準則 + 定性方法論 + 來源錨點，不整段複製原文。
> no-fabrication：每值附逐字來源引文；查無來源標 UNVERIFIED 不臆造。
> subagent ses_0d4753a5a 純研究產出，本輪 read_subsession 逐字核對後落檔。
> 主來源：Wikipedia《Tolerance analysis》（引 ASME Y14.5 血統，教科書級）；
> Würth Elektronik connector datasheet（recommended hole pattern，原廠原文級，惟具體 keepout mm 在圖面）。

---

## control.mech.tolerance-stackup（confidence=verified，Wikipedia 引 ASME Y14.5 教科書級）

| 規則 | 準則/定義 | 逐字引文 | 出處 |
|---|---|---|---|
| worst-case（arithmetic）法 | 各變數置公差極限求 max/min 距離；保證 100% 零件可組裝，代價為個別公差極嚴、成本高/報廢率高 | 「Arithmetic tolerance stackups use the worst-case maximum or minimum values... guarantees 100 percent of the parts will assemble... requires very tight individual component tolerances」 | Wikipedia Tolerance analysis |
| statistical（RSS）法 | 各變數建模為統計分佈後合成；用 root sum square (RSS) 或 Monte-Carlo；放寬個別公差達可接受良率（非 100%） | 「Statistical tolerance stackups evaluate the maximum and minimum values based on the absolute arithmetic calculation combined with some method... such as root sum square (RSS) or Monte-Carlo methods」 | 同上 |
| 兩法選用準則 | 關鍵機械介面/備品互換介面客戶常要求 worst-case；非合約要求時 statistical 可用較寬公差達可接受良率、降成本 | 「Worst-case tolerancing is often required by the customer for critical mechanical interfaces and spare part replacement interfaces... properly applied statistical tolerancing can ensure acceptable assembly yields with increased component tolerances and lower fabrication costs」 | 同上 |
| vector loop 建模 | 從 gap 一側起，各零件貢獻尺寸以向量首尾相接成鏈，逐一穿過每零件；1D/2D/3D 規則不同 | 「The vectors are joined tip-to-tail, forming a chain, passing through each part in the assembly in succession」 | 同上 |
| 適用標準 | 依 ASME Y14.5 / Y14.41 或 ISO 尺寸公差標準；無官方標準規範 stackup 格式本身 | 「such as American Society of Mechanical Engineers (ASME) Y14.5, ASME Y14.41, or the relevant ISO」 | 同上 |

**checker**：C02 機構對位審查——connector/light-pipe 對位公差分配該用 worst-case（關鍵介面）或 statistical；機構+PCB 累積公差如何影響 connector 對位。
**織網**：`references` `control.mech.mounting-hole-clearance`（孔位公差堆疊）、`control.mech.snap-fit-geometry`（機構配合）、`control.mfg.assembly-courtyard`（組裝製造域）。

---

## control.mech.connector-mechanical-keepout（confidence=partial，Würth datasheet 原廠原文級——定性）

| 規則 | 值/準則 | 逐字引文 | 出處 |
|---|---|---|---|
| 機械耐久 mating 週期 | 10 000 Mating cycles（影響固定強度需求） | 「Durability 10 000 Mating cycles」 | Würth connector DS |
| pegs/hold-down 加固 | Type B with Pegs——board-lock peg 提供機構定位+拔插應力釋放 | 「Type B with Pegs, High Current」 | 同上 |
| recommended hole pattern | datasheet 提供 recommended hole pattern [mm]（具體 keepout/pad 幾何在圖面標註） | 「Recommended Hole Pattern: [mm]」 | 同上 |

**checker**：板緣 connector 機構定位（board-lock peg）+ recommended hole pattern 遵循 + mating durability 對固定強度。
**織網**：`references` `control.mech.board-edge-keepout`、`control.mfg.assembly-courtyard`。

**partial 理由**：到板邊 mating 淨空 mm、拔插方向 keepout mm、面板開孔對位公差屬各 connector datasheet 圖面標註，pdftotext 文字流未擷取具體 mm；定性準則 verified，具體 mm 待逐一抓 datasheet 圖面/OCR。

---

## UNVERIFIED / 未取得（誠實掛帳，不臆造）

- PCB 邊到外殼內壁最小間隙 mm、board retention slot 寬度、外殼 boss 支撐接觸區、PCB 角落到固定柱 — 屬 enclosure ME 規範（Hammond/Bopla），本批來源被 bot 擋，未命中逐字 mm。→ **不蒸 `control.mech.board-to-enclosure-fit`（空殼）**，維持掛帳待後批。
- standoff 直徑/到板邊、component-to-enclosure clearance、上下元件高度預算 — Keystone/Bivar datasheet，未命中。
- connector 到板邊 mating 淨空 mm、拔插方向 keepout mm、面板開孔對位公差 — Würth 圖面標註，文字流未擷。
- RSS 平方和公式符號 Tasm=√(ΣTi²) 逐字 — Wikipedia 定性描述概念但未列逐字算式（概念 verified、明式 UNVERIFIED）。

## Batch19 新增 control 物件（1 verified + 1 partial）

1. `control.mech.tolerance-stackup`（verified）
2. `control.mech.connector-mechanical-keepout`（partial）

累計 control：55 → 57。
