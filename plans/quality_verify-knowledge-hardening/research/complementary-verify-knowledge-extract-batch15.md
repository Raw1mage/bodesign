# Batch15 萃取檔 — C03 補齊（MOV/surge 選型 + NTC inrush 選型）

> 著作權邊界：僅萃取公開工程數值 + 定性方法論 + 來源錨點，不整段複製原文。
> no-fabrication：每值附逐字來源引文；查無來源標 UNVERIFIED 不臆造、不蒸空殼。
> subagent ses_0d481bb4e 純研究產出，本輪 read_subsession 逐字核對後落檔。
> 主來源：Littelfuse Varistors — Basic Properties, Terminology and Theory（13頁，原廠原文級）；
> Vishay/Ametherm ICL SPICE App Note Doc#24291 Rev 08-Sep-2025（9頁，原廠原文級）。均 pdftotext 解碼。

---

## control.protection.mov-surge-selection（confidence=verified，Littelfuse Varistor AN 原廠原文級）

| 規則 | 量化值/準則 | 逐字來源引文 | 出處 |
|---|---|---|---|
| 額定 RMS 電壓上限 | VM(AC)=可持續施加的最大連續正弦 RMS 電壓（系統電壓不得超過） | 「Rated RMS Voltage... Maximum continuous sinusoidal RMS voltage which may be applied. VM(AC)」 | Littelfuse Varistor AN |
| 額定 DC 電壓上限 | VM(DC)=可持續施加的最大連續 DC 電壓 | 「Rated DC Voltage... Maximum continuous DC voltage which may be applied. VM(DC)」 | 同上 |
| clamping ratio（箝位 FoM） | VC/VM(AC) 或 VC/VM(DC)，比值越小箝位越好 | 「A figure of merit measure of the varistor clamping effectiveness as defined by the symbols VC/VM(AC), VC/VM(DC)」 | 同上 |
| clamping 定義 | VC=指定峰值脈衝電流下量測的跨壓（8/20µs 波形） | 「Peak voltage across the varistor measured under conditions of a specified peak VC pulse current」 | 同上 |
| voltage overshoot | 快於 8µs 前緣脈衝使跨壓超出 clamping voltage，以 %VC 表示 | 「The excess voltage above the clamping voltage... expressed as a % of the clamping voltage (VC)」 | 同上 |
| 額定物理來源 | 能量額定由體積、電壓額定由厚度、電流能力由面積（垂直電流方向） | 「energy rating is determined by volume, voltage rating by thickness... current capability by area measured normal to the direction of current flow」 | 同上 |
| DC standby 漏電流 | ID=額定電壓 VM(DC) 下量測的 varistor 電流 | 「DC Standby Current... Varistor current measured at rated voltage, VM(DC)」 | 同上 |
| clamp vs 壽命脈衝 trade-off（二手） | 70J clamp 315V >10⁶ 脈衝；11J clamp ~385V >10⁵ 脈衝 | 「A 70J rated varistor will clamp at 315V... over 10⁶ such pulses. An 11J unit will clamp to approximately 385V... 10⁵」 | RS/Littelfuse Design Examples（DDG 摘要，二手） |

**checker**：MOV VM(AC)/VM(DC) 為系統電壓上限、clamping ratio VC/VM 越小越好、VC 以 8/20µs 定義、MOV 置 AC power-entry 跨線保護域。
**織網**：`references` `control.protection.fuse-ptc-derating`（batch14 同 power-entry 保護鏈）、`control.protection.tvs-esd-layout`（batch10 surge 箝位協調）、`control.protection.reverse-polarity-layout`（batch12 power-entry 保護群）。

---

## control.protection.ntc-inrush-selection（confidence=verified，Vishay/Ametherm Doc#24291 原廠原文級）

| 規則 | 量化值/準則 | 逐字來源引文 | 出處 |
|---|---|---|---|
| 選型準則1 min resistance | 最小電阻決定最大允許 inrush 電流 | 「The minimum resistance, which determines the maximum allowed inrush current」 | Vishay Doc#24291 |
| 選型準則2 max steady current | 使元件維持可持續溫度的最大穩態電流 | 「The maximum steady current (keeping the component at a sustainable temperature)」 | 同上 |
| 選型準則3 joule energy | 須承受電容充電期間焦耳能量 | 「The joule energy that the component must be able to sustain during capacitor loading」 | 同上 |
| surge 初值公式 | 開機 t=0 時 surge current = V/R25 | 「the surge current reaches the value V/R25 at t = 0」 | 同上 |
| R25 定義 | R25 = 25°C 時的電阻值 | 「R25 is the electrical resistance at 25 °C」 | 同上 |
| reset/recovery time | 兩次開關間需給定 reset time；電阻回穩需 >10s 達 steady state | 「Reset time: the time allowed between two consecutive on/off switches」「a steady state is reached after more than 10 s」 | 同上 |
| 殘餘電阻（實測範例） | 100% Imax(36A) 殘餘 0.0065–0.011Ω（spec 0.01）；50% Imax(18A) 0.016–0.028Ω（spec 0.03） | 「residual resistance at 100 % Imax. (36 A) is from 0.0065 Ω up to 0.011 Ω... 50 %... 0.016 up to 0.028 Ω」 | 同上 |
| 選型範例參數 | R25=20Ω/I=8A/J=250；R25=1Ω/I=36A/J=160；R25=5Ω/I=25A/J=600 | 「params:R25=20 I=8 J=250」「params:R25=1 I=36 J=160」「params:R25=5 I=25 J=600」 | 同上 |
| 串聯拓樸（二手摘要） | ICL 與負載串聯於開機端，冷態高電阻限流 | 「Connected in series with the load at switch-on, the thermistor's relatively high cold resistance limits the current」 | Ametherm catalog（DDG 摘要，二手） |

**checker**：NTC 選型三準則（min-R/steady-I/joule）、I_surge=V/R25、reset>10s、串聯負載開機端。
**織網**：`references` `control.protection.fuse-ptc-derating`（batch14 inrush 選 time-delay fuse 互補）、`control.power.decoupling-pdn-strategy`（batch14 bulk cap 充電為 inrush 來源）、`control.placement.power-stage-hot-loop`（power-entry 迴路）。

---

## UNVERIFIED / 未取得（誠實掛帳，不臆造、不蒸空殼）

- MOV 擺位到板邊/後級距離、MCOV 對系統電壓餘裕具體 %（如 20% guard band）、GDT/TVS 分級協調間距、MOV 劣化壽命曲線 — Littelfuse AN 提供 terminology 未給擺位 mm，UNVERIFIED（需 AN9769/SPD AN 或 IEC 61643）。表1 70J/11J clamp 值為 DDG 摘要標二手。
- NTC 擺位/熱隔離距離、soft-start layout、bulk cap 充電路徑幾何、hot-swap controller layout — Vishay AN 聚焦選型非 layout，UNVERIFIED。
- crystal guard ring 尺寸、GND island 幾何、load cap 對稱擺位距離、時鐘 trace keepout mm、crystal 下方 no-trace — Microchip AN826 僅理論（CL/Pierce），SiTime/Epson/ST/Silabs layout AN 連結全 404/403，UNVERIFIED（需換有效連結）。
- layer stackup 阻抗控制逐值（50Ω microstrip trace 寬對 dielectric、90Ω USB/100Ω diff、prepreg/core、copper weight、Dk）— Eurocircuits/Würth/JLCPCB impedance PDF 全 403/404，UNVERIFIED（batch7 SI diff-pair 部分重疊；需 fab impedance 表換源）。

## Batch15 新增 control 物件（2 個 verified）

1. `control.protection.mov-surge-selection`
2. `control.protection.ntc-inrush-selection`

累計 control：48 → 50。
