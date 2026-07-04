# Batch18 萃取檔 — C03/C04 補齊（stackup 阻抗 + crystal/oscillator layout）

> 著作權邊界：僅萃取公開工程數值 + 定性方法論 + 來源錨點，不整段複製原文。
> no-fabrication：每值附逐字來源引文；查無來源標 UNVERIFIED 不臆造。
> subagent ses_0d4758ed8 純研究產出，本輪 read_subsession 逐字核對後落檔。
> 主來源：Multi-CB「Layout examples for impedance」defined-buildup 逐值表（製造商規格表級）；
> NXP AN1706「Oscillator Design Considerations」12頁（原廠原文級）；
> Microchip AN826「Crystal Oscillator Basics」14頁（原廠原文級）。均 pdftotext/HTML 解碼。

---

## control.si.stackup-impedance-control（confidence=verified，Multi-CB 製造商規格表級）

逐字來源 Multi-CB `impedance-examples.html`，值為「width|space|width」，Er 標於各 buildup。

| Stackup | 目標阻抗 | 信號/參考層 | trace 寬 (µm) | space (µm) | 逐字引文 |
|---|---|---|---|---|---|
| 4L-01 1.6mm | 50Ω SE | TOP/IN2 | 245 | - | 「Single ended 50 Ω TOP IN2 245µm」 |
| 4L-01 1.6mm | 90Ω diff | TOP/IN2 | 180 | 120 | 「90 Ω ... 180µm 120µm 180µm」 |
| 4L-01 1.6mm | 100Ω diff | TOP/IN2 | 120 | 115 | 「100 Ω ... 120µm 115µm 120µm」 |
| 4L-02 1.0mm | 50Ω SE | TOP/IN2 | 395 | - | 「Single ended 50 Ω TOP IN2 395µm」 |
| 4L-02 1.0mm | 90Ω diff | TOP/IN2 | 230 | 120 | 「90 Ω ... 230µm 120µm 230µm」 |
| 4L-02 1.0mm | 100Ω diff | TOP/IN2 | 180 | 130 | 「100 Ω ... 180µm 130µm 180µm」 |
| 8L-01 1.7mm | 50Ω SE stripline | IN3/(IN2/IN4) | 175 | - | 「Single ended 50 Ω IN3 IN2/IN4 175µm」 |

**dielectric（逐字）**：4L-01「Ԑr for 1x Prepreg 1080: 3.95」；4L-02/6L-01/8L-01「Ԑr for 1x Prepreg 2116: 4.20」；「Df: ca. 0.02」；「final thickness (+/- 10%)」；「impedance control (+/- 10% bzw. +/- 5%)」。
**calculator 公式限制（逐字）**：Surface/Coated Microstrip、Edge-Coupled「0.1 < w/h < 3.0」「0.1 < s/h < 3.0」；FR4 standard Er=4.3（coated Ereff=3.5）。
**diff Z0 設計法（逐字）**：先算 SE 50Ω microstrip，再調 distance s 直到 ZDiff 達 90Ω。

**checker**：controlled-impedance net 的 trace 寬/間距對 stackup 檢核（50Ω SE / 90Ω USB / 100Ω diff 對 defined buildup 逐值）。
**織網**：`references` `control.si.diff-pair-impedance-geometry`（既有 diff pair 幾何互補）、`control.dfm.ipc-trace-width-current`（trace 寬↔載流/阻抗雙約束）。

---

## control.si.crystal-oscillator-layout（confidence=verified，NXP AN1706 + Microchip AN826 原廠原文級）

| 規則 | 量化值/準則 | 逐字來源引文 | 出處 |
|---|---|---|---|
| trace 盡量短（首要） | 保持 oscillator trace 盡量短、loop area 最小 | 「keep the oscillator trace length as short as possible and with minimal loop area」 | NXP AN1706 §3.1 |
| 元件靠近 OSC pin | Cx/Cy/Rf/crystal 盡量靠近 MCU oscillator pin | 「Cx, Cy, Rf and the crystal should be placed as close as possible to the microcontroller's oscillator pins」 | NXP AN1706 |
| load cap 走線不可過長 | Cx/Cy 走線過長增不必要電感 | 「Making the traces for Cx and Cy exceedingly long can add unwanted inductance」 | NXP AN1706 |
| loop area 最小/GND plane | 大 ground plane 通常保證最小 loop area | 「Having a large ground plane can usually guarantee the smallest loop area」 | NXP AN1706 |
| power/return 短路徑 | 電源與 return 路徑盡量短、loop area 盡量小 | 「Make certain that the power supply and return paths are as short as possible」 | NXP AN1706 |
| stray C 定量風險 | 1.0cm×0.1cm trace 於 solid GND plane、Dk 高時 stray C 15–50pF | 「a trace 1.0 cm long by 0.1 cm wide sitting directly above a solid ground plane... 15–50 pF」 | NXP AN1706 |
| CL 匹配 | Cx/Cy+stray 的容抗須等於晶體感抗（諧振） | 「The combined capacitive impedance of Cx, Cy and other stray capacitance equals the inductive reactance of the crystal」 | NXP AN1706 |
| CL 組成 | CL=晶體所見負載電容，含 holder/enclosure stray | 「stray capacitances due to the crystal holder and enclosure」 | Microchip AN826 |

**checker**：時鐘 layout 檢核（crystal 元件靠近度 + loop area + trace 長度 + 大 GND plane）。
**織網**：`references` `control.si.spacing-via-return-path`（既有 loop area/return path 互補）、`control.emc.stitching-shielding-plane`（既有 GND plane 完整性）。

---

## UNVERIFIED / 未取得（誠實掛帳，不臆造）

- crystal guard ring 環寬、GND island 具體幾何、crystal 下方 no-trace 明文、clock trace keepout mm — NXP/Microchip 提供 trace短/loop area定性，guard-ring 具體逐字未命中（ST AN2867 http=000 失效）。
- CL=(C1×C2)/(C1+C2)+Cstray 逐字明式 — 概念 verified、明式未命中。
- IPC-2141 microstrip 通用解析式（calculator 為 JS）、copper weight 0.5/2oz 對阻抗獨立逐值 — Multi-CB 表為 buildup-specific 逐值非通用式，UNVERIFIED。

## Batch18 新增 control 物件（2 個 verified）

1. `control.si.stackup-impedance-control`
2. `control.si.crystal-oscillator-layout`

累計 control：53 → 55。
