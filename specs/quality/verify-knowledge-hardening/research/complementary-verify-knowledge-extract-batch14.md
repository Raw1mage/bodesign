# Batch14 萃取檔 — C03 電路完整性（fuse derating + decoupling PDN）

> 著作權邊界：僅萃取公開工程數值 + 定性方法論 + 來源錨點，不整段複製原文。
> no-fabrication：每值附逐字來源引文；查無來源標 UNVERIFIED 不臆造。
> subagent ses_0d488c520 純研究產出，本輪 read_subsession 逐字核對後落檔。
> 主來源：Littelfuse Fuseology Selection Guide（fuse derating/I²t，原廠原文級）；
> TI SPRABV2「PCB Design Guidelines for Reduced EMI / BGA decoupling」6頁（原廠原文級）。均 pdftotext 解碼。

---

## control.protection.fuse-ptc-derating（confidence=verified，Littelfuse Fuseology 原廠原文級）

| 規則 | 量化值 | 逐字來源引文 | 出處 |
|---|---|---|---|
| fuse 電流 derating | 25%（10A fuse 不建議用超過 7.5A@25°C） | 「The current rating of a fuse is typically derated 25%」「a fuse with a current rating of 10A is not usually recommended for operation at more than 7.5A in a 25°C ambient」 | Littelfuse Fuseology |
| 額定基準溫度 | 25°C（ambient 升高反應更快，需 rerating） | 「Fuse characteristics ... at 25°C & will be affected by changes in ambient. At higher ambient temperatures, a fuse will respond faster」 | 同上 |
| ambient rerating | 載流餘裕 = Temp rerating factor × 0.75 | 「Temp rerating factor x 0.75」 | 同上 |
| I²t 脈衝耐受 | melting/arcing/total clearing I²t；Total clearing = melting + arcing，單位 A²s | 「I2t are expressed in ampere-squared-seconds [A2s]」「Total clearing I2t = (melting I2t) + (arcing I2t)」 | 同上 |
| inrush 脈衝選型 | inrush 脈衝常見，選 time-delay fuse 使脈衝 I²t < 熔斷 I²t | 「Transient pulses of inrush current are commonplace ... require fuses to have a time delay」 | 同上 |
| 脈衝疲勞 | fuse 可承受給定 I²t 脈衝次數有限 | 「number of pulses of a given I2t value that can be withstood」 | 同上 |

**checker**：fuse 電流 derating 25%（10A→≤7.5A@25°C）、ambient rerating、脈衝 I²t < melting I²t、inrush 選 time-delay、fuse 置 power-entry 第一顆。
**織網**：`references` `control.protection.reverse-polarity-layout`（batch12 同 power-entry 保護鏈）、`control.protection.tvs-esd-layout`（batch10 surge 協調）、`control.dfm.ipc-trace-width-current`（fuse 前 trace 載流餘裕）。

---

## control.power.decoupling-pdn-strategy（confidence=verified，TI SPRABV2 原廠原文級）

| 規則 | 量化值 | 逐字來源引文 | 出處 |
|---|---|---|---|
| pin cap 值 | 每 2 power pin 一顆 0.1µF（最小封裝降 lead inductance） | 「placing one 0.1 µF cap (in the smallest possible package size...) as close to the chip as possible for every two power pins」 | TI SPRABV2 |
| pin cap 擺位 | 盡量近晶片；電源/地經 cap 再入 BGA | 「as close to the chip as possible ... Power and ground routes to the BGA should go [through the cap]」 | 同上 |
| bulk cap 準則 | 每 10 power pin ≥1 顆 ~15µF，可稍遠但仍盡量近 | 「at least one bulk (approximately 15 µF or larger) cap ... for every 10 or so power pins」 | 同上 |
| pin-per-cap 演進 | pitch <1.0mm 時舊法 1 cap/power pin 幾不可能，改 2 pin/cap | 「recommended 1 capacitor per power pin ... With any pitch less than 1.0 mm this is nearly impossible」 | 同上 |
| 多值 cap 迷思 | 不同值 cap 不一定互補相加，勿盲堆 | 「studies have shown that these varying capacitor values do not usually add in a complementary [manner]」 | 同上 |
| decoupling 到 IC 最大距離 | ≤1.25cm（0402 較佳；直接接 BGA power pin via） | 「within 1.25 cm maximum distance to be effective ... connected directly to the via attached to the BGA power pin ... 0402」 | TI TMS320 HW（manualzz 引 TI §5.6，二手轉載） |
| cap under BGA | cap 置 BGA footprint 下方（背面）共用 power/ground via | 「caps to fit directly underneath the part ... share every via with two power or ground balls」 | TI SPRABV2 |
| ferrite Pi filter | ferrite 置兩對地 cap 之間形成 Pi filter；chip-side cap 必須存在 | 「Ferrite beads should be used in between two capacitors to ground. This forms a Pi filter」「The chip side capacitor should always be there」 | 同上 |
| ferrite 限制 | ferrite 阻高頻但不允許高 ramp-rate 大電流瞬變通過 | 「Ferrite beads ... will not allow power to flow through them with the high ramp [rate]」 | 同上 |

**頻段分工（逐字）**：bulk 70Hz–40kHz、secondary bulk（near chip）15kHz–1MHz；善用 inter-plane capacitance。
**checker**：每 2 power pin 0.1µF、每 10 pin ~15µF bulk、decoupling ≤1.25cm、cap 置 BGA 下方共用 via、ferrite Pi filter、chip-side cap 必存。
**織網**：`references` `control.placement.power-stage-hot-loop`（電源迴路最小化互補）、`control.power.high-current-via-ground`（power/ground via 共用）、`control.emc.stitching-shielding-plane`（PDN 與 plane 完整性）、`control.si.spacing-via-return-path`（decoupling via 回流路徑）。

---

## UNVERIFIED / 未取得（誠實掛帳，不臆造、不蒸空殼）

- PTC (resettable fuse) hold/trip current 準則、PTC 熱隔離距離 — Littelfuse Fuseology 聚焦傳統 fuse，PTC 專節未命中（需 Bourns MF-R / PolySwitch PTC AN）。
- MOV 擺位、AC power-entry surge clamping、MOV 與後級距離、GDT/TVS 協調 — 未抓到 MOV/surge 專屬 AN（需 Littelfuse/Bourns MOV AN + IEC 61643）。
- inrush NTC thermistor 擺位、soft-start、bulk cap 充電路徑、inrush 限流電阻、hot-swap controller layout — NTC/soft-start 專屬逐值未命中（需 Ametherm/EPCOS NTC inrush AN）。
- BGA fillet、SMD vs non-SMD pad、via-in-pad filled/capped、QFN thermal pad via 陣列、dogbone vs via-in-pad 逐值 — IPC-7093 僅付費預覽頁，全文未解（惟 TI SPRABV2 有 cap-under-BGA 共用 via 定性佐證）。
- layer stackup 阻抗控制逐值（dielectric 厚度、prepreg/core、50Ω/90Ω/100Ω trace 寬/間距、copper weight）— fab stackup 阻抗全表未抓（需 JLCPCB/Multi-CB impedance 表；batch7 SI diff-pair 部分重疊）。
- crystal/oscillator layout（guard ring、GND island、load cap 擺位、時鐘 trace keepout）— Abracon crystal AN 連結失效（404），未取得逐值（換有效連結重試）。

## Batch14 新增 control 物件（2 個 verified）

1. `control.protection.fuse-ptc-derating`
2. `control.power.decoupling-pdn-strategy`

累計 control：46 → 48。
