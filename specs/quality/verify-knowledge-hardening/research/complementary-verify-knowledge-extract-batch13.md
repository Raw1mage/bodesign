# Batch13 萃取檔 — C02 機構整合層（snap-fit 幾何 + 材料 strain）

> 著作權邊界：僅萃取公開工程數值 + 定性方法論 + 來源錨點，不整段複製原文。
> no-fabrication：每值附逐字來源引文；查無來源標 UNVERIFIED 不臆造。
> subagent ses_0d4891313 純研究產出，本輪 read_subsession 逐字核對後落檔。
> 主來源：Covestro（原 Bayer）Snap-Fit Joints for Plastics — A Design Guide（26頁，原廠原文級）；
> productdesignonline Snap-Fit Design Manual（BASF/Ultramid 材料實測，24頁，原廠原文級）。均 pdftotext 解碼。

---

## control.mech.snap-fit-geometry（confidence=verified，Covestro/Bayer + BASF 原廠原文級）

### cantilever snap-fit 幾何設計（Covestro/Bayer）

| 規則 | 量化值/準則 | 逐字來源引文 | 出處 |
|---|---|---|---|
| fillet R/h 比 | R/h=0.6（最佳；>0.6 交叉處過厚、<0.6 應力集中上升） | 「stress concentration is obtained using the ratio R/h as 0.6」 | Covestro Fig.9 |
| fillet 最小半徑 | ≥0.015 in（≈0.38mm，任何情況不得更小） | 「should not be less than 0.015 in. in any」 | 同上 |
| 漸縮厚度臂 tapered beam | 厚度線性縮至根部一半 → permissible deflection 增 >60% | 「increases the permissible deflection by more than 60%」 | Covestro/productdesignonline |
| 常截面設計懲罰 | 等位移/力下多用 17% 材料、應力高 46% | 「This design uses 17% more material and exhibits 46% higher [strain]」 | Bayer/Covestro |
| permissible deflection | deflection y 等於 undercut 量 | 「The deflection y occurring during the joining operation is equal to the undercut」 | Covestro |
| 玻纖強化材 permissible strain | ≈½ elongation（snap 允許應變砍半） | 「permissible strain for these materials in the case of snap joints is about half the elongation」 | Covestro |
| 90° return angle | return angle 90° 於張力鬆弛=永久固定；大 return angle + 增 land length 降失效 | 「a 90° return angle so that it relaxes in tension... increase the land length」 | productdesignonline Fig.VI-3 |
| sharp corner 失效主因 | snap-fit 最常見失效=根部 sharp corner 應力集中超材料極限 | 「The single most common cause of failure in snap-fits is [sharp corner at root]」 | productdesignonline |

### snap-fit 材料 allowable strain 逐值（productdesignonline / BASF 實測）

| 材料 | Allowable Strain εo（unfilled 單次） | 30% 玻纖 | 逐字引文 |
|---|---|---|---|
| PC | 4%(1)–9.2%(2) | 2.0% | 「PC ... 4%(1) - 9.2%(2) ... 30% GLASS ... 2.0%」 |
| Nylon 6 | 8%(5) | 2.1%(1) | 「Nylon 6 ... 8%(5) ... 2.1%(1)」 |
| PC/PET | 7%(1) | 2.0% | 「PC/PET ... 7%(1) ... 2.0%」 |
| ABS | 8.8%(2) | 1.5%(1) | 「ABS ... 8.8%(2) ... 1.5%(1)」 |
| PET | 5.8%(2) | — | 「PET ... 5.8%(2)」 |

**通用準則（逐字）**：重複拆裝用 tensile yield strain 的 70%（「70% of tensile yield strain value」）；mating force 計算用 4%（「4% should be used in Mating Force」）。
**deflection/mating force 公式（Bayer 逐字符號）**：y=deflection(=undercut)、E=permissible strain outer fiber、l=arm length、h=root thickness、P=deflection force；W=P×(μ+tanα)/(1−μ tanα)，範例 μ=0.3、α=30°→「P=72.45 N... W=76.9 N」。

**checker（對位 bodesign）**：snap-fit 幾何/材料 strain check（enclosure 對接 PCB 固定），落 fillet R/h=0.6 + min radius 0.38mm + 材料 strain 上限查表。
**織網**：`references` `control.mech.mounting-hole-clearance`（batch12 同機構固定域）、`control.flex.bend-area-geometry`（batch9 塑膠/撓性彎折力學互補）。

---

## UNVERIFIED 佔位（誠實掛帳，不蒸空殼、待後批補實）

- **control.mech.board-to-enclosure-fit**：PCB 邊到外殼間隙、board retention slot、公差堆疊 worst-case/RSS——本批未取得逐字，**不蒸**，待後批抓 Bayer Part&Mold Design / ME 外殼規範補實。
- **control.mech.connector-mechanical-keepout**：connector 到板邊 mating 淨空、拔插 keepout、panel-mount 對位、SMT 焊點應力釋放——屬 connector datasheet（Molex/JST/TE mechanical drawing）給定，**不蒸**，待抓具體 datasheet 補實。
- plastic boss 高度/直徑、standoff 逐值、display/FPC 機構固定、light-pipe 對位公差 — 全數 UNVERIFIED 未命中，不臆造 ±mm。

## Batch13 新增 control 物件（1 個 verified）

1. `control.mech.snap-fit-geometry`

累計 control：45 → 46。
