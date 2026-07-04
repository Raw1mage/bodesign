# 互補源 verify 知識萃取 batch8（安規 spacing + RF/微波：補電氣安全與高頻缺維度）

> 目的：補知識庫完全缺的 **電氣安全間距 creepage/clearance**（family L）與 **RF/微波 layout**（family M）維度。
> - family L：TI SLUP421 官方 PDF（原廠級，引 IEC 60664-1/62368-1 表）+ smps.us（引 UL796/UL60950/IPC-2221B/9592B 原文）
> - family M：待支線 B（RF）回報後補
>
> 天條守則：每數值附來源錨點；查無來源標 UNVERIFIED，不臆造。**安規逐值查表僅取到錨點列（verified），完整表 UNVERIFIED——不以二手近似值填表**；公式型（UL796/IPC-9592B）最可靠。

---

## 家族 L：電氣安全間距 creepage/clearance（TI SLUP421 原廠級 + smps.us 引標準）

### L1. 定義

| 項目 | 定義 | 決定因素 |
|---|---|---|
| Creepage (CPG) | 沿固體絕緣材料表面兩導體間最短距離 | working voltage(RMS)、pollution degree、material group |
| Clearance (CLR) | 空氣中兩導體間最短距離 | transient overvoltage、altitude、pollution degree |
| 關係 | CPG 恆 ≥ CLR | — |

### L2. material group / CTI 分級（引 IEC 60112）

| Material Group | CTI range (VRMS) |
|---|---|
| I | CTI ≥ 600 |
| II | 400 ≤ CTI < 600 |
| IIIa | 175 ≤ CTI < 400（**多數 FR4 PCB 屬此**） |
| IIIb | 100 ≤ CTI < 175 |

CTI 定義：材料耐 50 滴污染水(0.1% NH₄Cl)不 tracking 的最大 VRMS。一般 FR4 查 creepage 用 IIIa 欄。

### L3. pollution degree

| PD | 定義 |
|---|---|
| 1 | 無導電污染（密封/clean room） |
| 2 | 暫時因凝露變導電（**多數商用 PCB 環境**） |
| 3 | 持續導電污染 |
| 4 | 導電粉塵/雨/濕連續導電 |
| coated | conformal coating 可降到 PD1（IEC 62109-1，用 Table G.13 降 CPG） |

### L4. overvoltage category → transient (kVPK) @ 主電源

| OVC | transient |
|---|---|
| IV | 4 kVPK |
| III (fixed installation) | 2.5 kVPK |
| II | 1.5 kVPK |
| I | 0.8 kVPK |

### L5. clearance/creepage 逐值錨點列（IEC 60664-1 Table F.2/F.4，僅錨點 verified）

| 類型 | 條件 | 值 |
|---|---|---|
| clearance | 2.5 kVPK, PD2, basic | 1.5 mm（IEC62368-1 server 值 1.8） |
| clearance | 6.0 kVPK, PD2, basic | 5.5 mm（server 7.9） |
| creepage | 800 VRMS, PD1/PD2/PD3 | 2.4 / 4.0 / 5.6 mm（reinforced = ×2 = 8.0） |

**⚠ 完整逐列（50V/100V/250V/300V…→mm）UNVERIFIED**（IEC 原文付費、PDF 版面破壞），不以二手近似臆造。

### L6. altitude derating（IEC 60664-1 Table A.2）

| 海拔 | 修正係數 |
|---|---|
| 2000m（基準） | ×1.0 |
| 5000m | ×1.48 |
| 10000m | ×3.02 |

範例：clearance at 5000m = 3.8mm × 1.48 = 5.7mm。中國 GB4943.1-2022 >2000m 亦 ×1.48。

### L7. insulation grade 加倍準則

| grade | 準則 |
|---|---|
| functional | 僅需通過 HiPot 電氣強度測試，無固定間距 |
| basic | 查表基準值 |
| double/reinforced | = basic ×2（primary↔secondary 危險電壓隔離） |

### L8. 公式型 spacing（smps.us 引標準原文，**可直接落 checker 無需查表**）

| 規則 | 量化值 | 出處 |
|---|---|---|
| UL796 withstand voltage | 40 V/mil ≈ 1.6 kV/mm（間距↔耐壓換算） | UL796 |
| IPC-9592B 早期線性 functional | SPACING(mm) = 0.6 + Vpeak×0.005 | IPC-9592B |
| IPC-9592B 修訂 step (uninsulated) | V<15V:0.13mm; 15≤V<30:0.25mm; 30≤V<100:0.1+V×0.01 | IPC-9592B |
| IPC-2221B Table 6.1 | 各電壓→間距(ext/int/coated)，1998起未修訂，step function | IPC-2221B |
| IPC step 不連續 | 300V→1.25mm 但 301V→2.5mm | IPC |
| 換算 | 1mm ≈ 40 mils | — |
| UL 頻率適用上限 | 絕緣要求僅適用至 30 kHz | UL60950 |
| worked example | 500V→withstand 1740Vrms→2461Vpk→/40V·mil=62mils(1.6mm) | UL Table5B |

### L9. 實務 layout

| 規則 | 說明 |
|---|---|
| slot/cutout | PCB 開槽切斷表面爬電路徑，增有效 creepage（達 isolation barrier） |
| coating | conformal coating → PD1 降需求 |

來源錨點：`safety://ti-slup421`（原廠級，引 IEC 60664-1）+ `safety://smps-us`（二手引 UL796/UL60950/IPC-2221B/9592B 原文）。

UNVERIFIED（family L，不臆造）：IEC 62368-1/60664-1 完整 clearance/creepage 逐列表（僅錨點列）、IPC-2221B Table 6.1 逐值電壓→mm、UL60950-1 Table 2N 逐值、reinforced/basic 各 PD 完整對照。

---

## 家族 M：RF/微波 layout（TI SWRA367A/469 原廠級 + Johanson 天線 datasheet 逐值）

來源：TI SWRA367A(AN098 Layout Review for Low Power RF) + SWRA469(Antenna Diversity) + Johanson 2450AT18A100E 天線 datasheet，全 pdftotext 解碼原文。

### M1. 傳輸線阻抗 / 板材

| 規則 | 量化值 | 出處 |
|---|---|---|
| RF 標準阻抗 | 50Ω single-ended | TI SWRA367A §3.1 |
| microstrip Z0 公式 | Z0=(60/√εeff)·ln(8h/w + w/4h)（t/h<0.005, w/h<1） | §3.1 |
| εeff 公式 | εeff=(εr+1)/2 + ((εr−1)/2)·[1/√(1+12h/w) + 0.041(1−w/h)²] | §3.1 |
| 板厚建議(microstrip) | 0.8-1.0mm（過厚使 50Ω 線寬過大不實用） | §3.3 |
| 4-layer 增厚 | ~60mils | §3.3 |
| 阻抗匹配 | 共軛匹配求最大功率傳輸；複製 reference design | §3.1 |

### M2. 接地 / via

| 規則 | 量化值 | 出處 |
|---|---|---|
| RF via 間距 | ≤λ/10（注：與 EMC/SI 的 λ/20 不同情境，皆有原文非矛盾） | TI SWRA367A §3.5/checklist#11 |
| ground plane 連續性 | RF 段下方須連續不斷；分割阻礙 return path | §3.5 |
| 4-layer stack | L1 signal / L2 ground(緊鄰 top) / L3 power / L4 ground+signal | §3.3 |
| top ground fill 縫合 | top pour 用多 via 縫到 ground plane 與 bottom | checklist#11 |
| decoupling 就近 | pin↔capacitor↔via | checklist#5 |

### M3. 天線 keepout / 淨空

| 規則 | 量化值 | 出處 |
|---|---|---|
| 天線下方無 ground | 天線下不得有 ground plane（除非廠商指定如 whip） | TI SWRA367A checklist#8 |
| battery 不置天線下 | coin cell 會當 ground plane | checklist#13 |
| antenna diversity 間距 | 兩天線 feedpoint 相距 λ/4 | TI SWRA469 §3 |
| chip antenna keepout(逐值) | 2450AT18A100E @2.45GHz：GND 淨空 6.5mm、GND 高 13.5mm、板 39.5mm、50Ω feed 19mm | Johanson datasheet |
| chip antenna 匹配 | pi/shunt 3.9nH/2.7nH（ref board 值） | Johanson datasheet |

### M4. coupling / 隔離 / 元件擺位

| 規則 | 量化值 | 出處 |
|---|---|---|
| ground shield 隔離 | top ground fill + via 縫合形 shield 護 RF 段 | §3.5 |
| inductor 方向 | 磁場耦合鄰件，依 ref design 擺位/朝向 | §3.6 |
| 元件尺寸 | RF 段不建議 0603 discrete（尺寸/寄生） | checklist#2 |
| crystal 就近 | 晶振盡量近 oscillator pin | checklist#10 |
| differential 對稱 | 差分段 trace 須對稱如 ref design | checklist#12 |
| RF 段複製準則 | white box 內全複製 reference design；外可自由改 | §4 |

來源錨點：`rf://ti-swra367a`（原廠）+ `rf://ti-swra469` + `rf://johanson-2450at`（天線 datasheet 逐值）。

UNVERIFIED（family M，不臆造）：CPWG 專屬幾何（ground gap/via pitch 逐值）、λ 絕對值逐頻率表（公式已驗證需代入）、Rogers RO4350B Dk/Df 逐值、L/pi/T matching network 通用算法、TX/RX 隔離 dB 與 RF trace 間距逐值。

---

## 蒸餾計畫

batch8 共 **4 個新 control 物件**（family L 2 + family M 2，repo scope）：
1. `control.safety.creepage-clearance-spacing` — 安規查表判準 — confidence **partial**（判準邏輯完整但逐值查表 partial，僅錨點 verified）
2. `control.safety.functional-spacing-formula` — 公式型 spacing（UL796 40V/mil、IPC-9592B `0.6+Vpeak×0.005`）— confidence **verified**
3. `control.rf.transmission-line-ground` — RF 50Ω microstrip Z0/εeff 公式 + 板厚 0.8-1.0mm + via ≤λ/10 + ground 連續性 + 4-layer stack — confidence **verified**（TI 原廠級）
4. `control.rf.antenna-keepout` — 天線下 no-ground + λ/4 diversity + chip antenna 逐值 keepout + RF white-box 複製 + 元件擺位 — confidence **verified**（TI 原廠）

link 織網（batch8）：
- `safety.creepage-clearance-spacing` → `references` `control.verify.kicad-dru-rule-language`（clearance 落 DRU）
- `safety.creepage-clearance-spacing` → `references` `control.safety.functional-spacing-formula`（查表 vs 公式互補）
- `rf.transmission-line-ground` → `references` `control.si.diff-pair-impedance-geometry`（single-ended 50Ω 共用阻抗基礎）
- `rf.transmission-line-ground` → `references` `control.emc.stitching-shielding-plane`（RF via λ/10 vs EMC λ/20 不同情境）
- `rf.antenna-keepout` → `references` `control.verify.kicad-dru-rule-language`（keepout zone 落地）
- 4 物件 `distilled_from` batch8 asset
