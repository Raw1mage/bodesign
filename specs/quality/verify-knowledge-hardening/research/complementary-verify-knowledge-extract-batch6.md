# 互補源 verify 知識萃取 batch6（SI/EMC/熱深度：補 KB 最弱維度）

> 目的：補知識庫偏 DFM/幾何/電源、缺高速訊號完整性(SI)與 EMC/熱的空白（bodesign C06 驗證真正空白）。
> - **家族 G：高速 SI**（差分對 impedance/geometry、length-match/skew、spacing/crosstalk、via-stub/return-path、loss-budget）— TI spraar7j 官方 PDF pdftotext 解碼＝原文級 + atlaspcb 逐值交叉
> - **家族 H：EMC/EMI**（stitching λ/20、via fence、20-H rule、guard trace、ground split）— atlaspcb 工程級二手
> - **家族 I：熱管理**（thermal via 陣列、θJA 熱阻網路、IPC-4761/6012 填充）— atlaspcb 引 IPC 條款
>
> 天條守則：每個數值附來源錨點；查無來源標 UNVERIFIED，不臆造。TI app note 走原文 PDF（條款級）；atlaspcb 二手工程級明標。TI 著作權：只萃規則+數值+出處，不整段複製。

---

## 家族 G：高速 SI（TI 原文級 + atlaspcb 逐值）

### G1. 差分對目標阻抗 by interface（Zdiff Ω / 容差 / intra-pair skew limit）

| 介面 | Zdiff | 容差 | skew limit | single-ended |
|---|---|---|---|---|
| USB 2.0 | 90 | ±10% | ±150 mil | — |
| USB 3.x | 90 | ±10% | ±5 mil | 45 |
| PCIe Gen3/4 | 85 | ±15% | ±5 mil | 42.5(AC) |
| PCIe Gen5 | 85 | ±10-15% | ±5 mil | 42.5 |
| HDMI 2.0+ | 100 | ±15% | ±2.5 mil | — |
| Ethernet 1G | 100 | ±10% | ±50 mil | — |
| 10/25/100G Eth | 100 | ±10% | — | — |
| LVDS | 100 | ±10% | ±100 mil | — |
| DDR4/DDR5 | 80-100(diff) | ±10% | — | 40-50 |
| General RF | — | — | — | 50 |

關係式：`Z_diff = 2 × Z_odd`；快速估算 `Z_diff ≈ 2×Z₀×(1 − 0.48×e^(−0.96×s/h))`（正式須 2D field solver）。microstrip `Z₀≈(87/√(Dk+1.41))×ln(5.98h/(0.8w+t))`；stripline `Z₀≈(60/√Dk)×ln(4b/(0.67π(0.8w+t)))`。

來源錨點：`si://interface-impedance`（atlaspcb，與多源分類一致，非 USB-IF/PCI-SIG 原文）。

### G2. 差分對幾何起始值（4-layer FR4, Dk≈4.3, 4-5mil to plane）

| Zdiff | Trace W | Gap S | Dielectric H |
|---|---|---|---|
| 90Ω(USB) | 4.5-5.5 mil | 4-6 mil | 4-5 mil |
| 100Ω(HDMI/Eth) | 4.0-5.0 mil | 5-8 mil | 4-5 mil |
| 85Ω(PCIe) | 5.0-6.0 mil | 4-5 mil | 4-5 mil |
| 85Ω stripline(Megtron4 Dk3.7) | 4.0 mil | 5.0 mil | 4.5 mil each |

### G3. length matching / skew（TI 原文 + atlaspcb 逐值）

| 規則 | 量化值 |
|---|---|
| intra-pair skew by data rate | 5Gbps=10ps/1.5mm; 10Gbps=5ps/0.75mm; 25Gbps=3ps/0.45mm; 56G PAM4=1.5ps/0.23mm; 112G PAM4=1.0ps/0.15mm |
| inter-pair(lane) match | PCIe Gen4/5=±12.7mm(500mil); USB3.2 TX-RX=±2.0mm; DDR5 byte lane=±1.0mm; LVDS=±2.5mm |
| 90° bend skew | 6mil gap 每轉 ≈9.4mil(0.24mm) skew |
| serpentine 幾何 | amplitude≥2×W; segment gap≥4×W; 用 arc 非直角 |

TI 原文（spraar7j §2.3）：intra-pair 補償 serpentine 須置於失配源後（越靠 mismatched end 越好），非累積到末端；**TX pair 不需與 RX pair 等長**（inter-group 不需匹配）。

### G4. spacing / crosstalk（TI 原文級高信度）

| 規則 | 量化值 | 來源 |
|---|---|---|
| **TI 5W rule** | 差分對 pair-to-pair 間距 ≥**5× trace width**（6mil→30mil） | TI spraar7j §3.1 原文 |
| TI keep-out to other signal | ≥30 mil；靠 clock/週期訊號 ≥50 mil | TI §3.1 原文 |
| TI pair-to-pair(封裝逃逸後) | 不得 <30 mil | TI §3.4 原文 |
| TI reference-plane edge | 差分訊號距參考層邊緣 ≥90 mil | TI §3.2 原文 |
| TI void 距離 | 距參考層 void ≥1.5W | TI §3.2 原文 |
| TI 封裝逃逸 | break-out 須在封裝 0.25 inch 內完成 | TI §3.3 原文 |
| inter-pair spacing vs crosstalk | 3H≈2-5% NEXT; 4H≈1-2%; 5H<1% NEXT | atlaspcb |
| NEXT/FEXT vs spacing | 1H:8-12%/5-8%per inch; 3H:1-2%/<1%; 5H:<0.5%/negligible | atlaspcb |
| guard trace 有效性 | 僅 ground via ≤λ/20 間距時 +10-20dB；**無 via 反增耦合** | atlaspcb |

### G5. via stub / back-drill / return path（TI 原文 + atlaspcb）

| 規則 | 量化值 | 來源 |
|---|---|---|
| **TI stitching via 間距** | signal transition via 旁 ≤**200 mil** center-to-center（越近越好，對稱） | TI spraar7j §2.4 原文 |
| TI stitching cap(跨 split) | ≤1µF，置 split 交越處 | TI 原文 |
| via stub 共振 | f_res = c/(4×L_stub×√Dk) | atlaspcb 公式 |
| via stub 長度上限 | <0.25mm for 10+ Gbps | atlaspcb |
| back-drill 殘餘 stub | ±0.1mm 精度，殘餘 0.1-0.2mm | atlaspcb |
| via 特性阻抗 | PTH via ≈25-35Ω（低於 50Ω trace） | atlaspcb |
| anti-pad 調阻抗 | 0.3mm drill+0.7mm anti-pad+0.1mm dielectric ≈45-50Ω | atlaspcb |
| return via 置放 | ≤0.5mm from signal via；≥2 GND via per signal via | atlaspcb |
| return current 高頻路徑 | >1MHz 走 trace 正下方最近參考層（最小電感） | atlaspcb |
| plane slot 危害 | 1GHz 下 2mm slot 致 20+dB EMC 劣化 | atlaspcb |

### G6. loss budget / dielectric

| 規則 | 量化值 |
|---|---|
| PCIe Gen5 channel loss budget | ~28-36 dB @ 16GHz(Tx pad→Rx pad) |
| via pair insertion loss | 0.3-1.0 dB per via pair @ 10+GHz |
| solder mask 阻抗影響 | 外層 trace 上 mask(Dk≈3.5) 改變阻抗 2-5Ω |
| 銅箔粗糙度損耗 | 標準粗糙比平滑箔增 20-50% |
| FR4 Dk | ≈4.2-4.5(typ 4.3) |
| impedance 製造容差 | etch±0.5-1.0mil; prepreg±10%/core±5%; Dk FR4±3-5%/controlled±1-2%; plated Cu±15% |
| critical length（控阻門檻） | trace > 1/6 rise-time distance 需控阻；1ns/FR4→2.5cm |

來源錨點：`si://ti-spraar7j`（TI 原文）+ `si://atlaspcb`（二手逐值）。

---

## 家族 H：EMC/EMI（atlaspcb 工程級二手）

### H1. Stitching / Shielding Via

| 規則 | 量化值 |
|---|---|
| stitching via λ/20 間距(FR4 Dk≈4) | 1GHz=7.5mm / 3GHz=2.5mm / 5GHz=1.5mm / 10GHz=0.75mm / 20GHz=0.375mm |
| 高頻折衷 | 10GHz+ 可用 λ/10=1.5mm |
| signal via 旁 stitching | <50mil(1.27mm)；10Gbps<30mil(0.76mm) |
| via fence 距板邊 | 50-100mil(1.3-2.5mm) |
| 板邊 stitching 間距 | 每 2-3mm |
| via 電感 | L≈(5.08×h)×[ln(4h/d)+1] nH；12mil/62mil=0.95nH(@1GHz≈6Ω) |
| cavity resonance | f=(c/2√Dk)×√((m/a)²+(n/b)²) |
| 邊緣輻射抑制 | λ/20 fence 降 10-20dB |
| stitching drill/antipad | drill 8-12mil(0.2-0.3mm)；antipad 5-8mil |

### H2. Ground Plane / Guard / Shield

| 規則 | 量化值 |
|---|---|
| 20-H rule | ground 延伸 20×介電厚度(0.1mm 介電→2mm) |
| plane 覆蓋率 | ≥80% |
| ground 平面隔離度 | 連續銅 40-60dB |
| ground split 代價 | 0.5mm 槽跨高速線 → 諧波 +20dB |
| guard trace via 間距 | 每 3-5mm；延伸信號兩端 2mm |
| guard trace 間距 | 1-2×(trace 到參考層距離) |
| via fence 隔離度 | 單排 20-30dB；雙排(交錯,行距0.5-1mm)40-50dB；coax cage 50-60dB |
| split 跨接電容 | 每信號跨越點放 100nF+10nF |
| decap 到 IC power pin | <1mm |
| shield can 隔離 | 單室 60-70dB(1GHz)/50-60(5GHz)；雙壁 70-80dB |
| shield pad stitching | 沿 footprint 每 1.5-2mm |
| EMC 層數建議 | 4層:L2 ground / 6層:L2,L5 / 8層:L2,L4,L7 |

來源錨點：`emc://atlaspcb-stitching,shielding`（二手工程級）。

---

## 家族 I：熱管理（atlaspcb 引 IPC-2152/4761/6012 條款）

| 規則 | 量化值 |
|---|---|
| FR-4 導熱率 | 0.3-0.4 W/m·K(vs 銅 390) |
| thermal via 標準 | 0.3mm(12mil) drill 起手 |
| via pitch | 最小0.8mm / 最佳1.0-1.2mm / 超1.5mm 劣化 |
| via 距 pad 邊 | ≥0.3mm |
| 單 via 熱阻(未填) | R=L/(k_Cu×A_annulus)；0.3mm/25µm/1.6mm=190°C/W |
| 單 via 熱阻(銅填) | 58°C/W(降3.3×) |
| via 陣列並聯 | R_array = R_via / N |
| θJA 熱阻網路 | R_θJA = R_θJC + R_contact + R_via_array + R_spreading + R_convection |
| 陣列熱阻範例 | 5×5@1.0mm(25via)=6.7°C/W(1.6mm板)/4.2(1.0mm板); 3×3@1.5mm=18.5 |
| 有效導熱率 | k_eff=k_Cu×(A_via/A_pad)+k_FR4×(1−A_via/A_pad); 0.3mm@1mm=27.9 W/m·K |
| solder paste 覆蓋(QFN 熱pad) | 50-75% 防 void |
| 底面銅面積 | ≥4× 元件熱pad 面積 |
| 熱 relief 代價 | spoke 連接 +5-15°C/W → 內層用 full-flood |
| 對流係數 | 自然 5-25 / 強制風 25-100 W/m²·K |
| 板厚影響 | 1.0mm 較 1.6mm 降 37.5% via 熱阻 |
| IPC-4761 via 填充型 | Type V 非導0.2-0.8 / Type VI 導1-10 / Type VII 銅390 W/m·K |
| IPC-6012 Class3 via 鍍銅 | 桶壁最小 25µm(§3.6.2.4)；填充 void ≤25% |
| 功率→方案決策 | <1W epoxy填/1-5W 導電epoxy/5-30W 銅填2ozCu/>30W 銅coin或MCPCB |
| copper coin | 10×10mm coin <1°C/W |

來源錨點：`thermal://atlaspcb-ipc4761-6012`（二手引 IPC 條款）。

---

## 蒸餾計畫（補 KB SI/EMC/熱空白）

batch6 產出 **5 個新知識物件**（互補源，repo scope）：

1. `control.si.diff-pair-impedance-geometry` — 差分對介面阻抗表 + W/S/H 幾何 + skew limit（G1+G2）
2. `control.si.length-match-skew` — intra-pair skew budget by data rate + inter-pair match + serpentine（G3）
3. `control.si.spacing-via-return-path` — TI 5W rule/30mil/90mil/200mil stitching（原文級）+ via stub/return via/loss budget（G4+G5+G6）
4. `control.emc.stitching-shielding-plane` — stitching λ/20 + via fence + 20-H rule + guard trace + ground split（H1+H2）
5. `control.thermal.via-array-jarray-network` — thermal via 陣列 + θJA 網路 + IPC-4761/6012 填充 + 功率決策（I）

link 織網：
- `si.spacing-via-return-path` → `references` `control.emc.stitching-shielding-plane`（stitching via 兩用途：SI return + EMC）
- `si.spacing-via-return-path` → `references` 既有 `control.verify.kicad-dru-rule-language`（clearance/diff_pair_gap constraint 落地）
- `emc.stitching-shielding-plane` → `references` 既有 `control.placement.power-stage-hot-loop`（decap/plane 與電源佈局互補）
- `thermal.via-array` → `references` 既有 `control.placement.power-stage-hot-loop`（thermal via 與 exposed pad 互補）+ `control.dfm.ipc-annular-tolerance-stack`（via 幾何）
- 5 個新物件 `distilled_from` batch6 asset

UNVERIFIED（不臆造）：USB-IF/PCI-SIG 官方原文容差、glass-weave skew 量化係數、DDR 完整 timing matrix、TI Appendix A 逐裝置 max-length、CM choke/ESD/TVS/plane-cap 具體量化、Würth/TI EMC 原廠條款級。
