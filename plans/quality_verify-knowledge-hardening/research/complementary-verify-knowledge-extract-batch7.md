# 互補源 verify 知識萃取 batch7（protection/filtering + 記憶體 routing：補全缺維度）

> 目的：補知識庫完全缺的 **ESD/TVS 保護 + EMI 濾波**（family J）與 **DDR 記憶體 routing**（family K）維度。
> - family J：TI slva680A 官方 PDF（pdftotext 原文級）+ atlaspcb ESD 專篇（引 IEC 61000-4-2）
> - family K：待支線 B（DDR）回報後補
>
> 天條守則：每數值附來源錨點；查無來源標 UNVERIFIED，不臆造。TI/JEDEC/Micron 原廠走原文 PDF（條款級）；atlaspcb 二手工程級明標。

---

## 家族 J：ESD/TVS 保護 + EMI 濾波（TI slva680A 原文級 + atlaspcb 逐值）

### J1. IEC 61000-4-2 ESD test level（atlaspcb 引標準）

| Level | Contact | Air |
|---|---|---|
| 1 | ±2 kV | ±2 kV |
| 2 | ±4 kV | ±4 kV |
| 3 | ±6 kV | ±8 kV |
| 4（多數商用目標） | ±8 kV | ±15 kV |
| 汽車 ISO 10605 | — | ±25 kV |

ESD 波形：±8kV → 30A peak <1ns；~3.75 A/kV peak current。1ns rise ≈ PCB trace 75mm（自由空間 300mm 之半）。

### J2. TVS/ESD 擺位（TI slva680A 原文級 + atlaspcb 逐值）

| 規則 | 量化值 | 來源 |
|---|---|---|
| TVS 到 connector 距離 | ≤**10 mm** | atlaspcb 二手 |
| **TVS 就近 connector（原文）** | TVS 儘量近 connector；Protected IC 距 TVS 須遠大於 TVS 距 connector | TI slva680A Summary 原文 |
| **禁 stub（原文）** | TVS 到 Protected Line 間不得有 stub，ESD Source→TVS 直接 route | TI slva680A 原文 |
| in-line routing | connector→TVS pad→IC，不得過 TVS 再分支 | atlaspcb 二手 |
| ground return 路徑 | TVS ground pin 到最近 GND plane via ≤**5 mm** trace | atlaspcb 二手 |
| 專用 ground via 數 | ≥**2** GND via/TVS；4+ 通道陣列用 3-4 | atlaspcb 二手 |
| **寄生電感臨界性（原文）** | 8kV 下 dI/dt=(30A)/(0.8ns)=4×10¹⁰ A/s；即使 0.25nH 也多出 10V clamp | TI slva680A §2 原文 |
| **L3(TVS→ground) 最關鍵（原文）** | L3 為最主要寄生（影響 VESD 最大），須極小化 | TI slva680A 原文 |
| **EMI keep-out（原文）** | connector→TVS 之間視為 keep-out，未保護線不得相鄰 | TI slva680A §2.2 原文 |
| **corner 角度（原文）** | connector→TVS 走線轉角 ≤45°，理想大半徑圓弧 | TI slva680A §2.1 原文 |
| **via 準則（原文）** | connector→TVS 間放 via 有害；不得已時亦不可有未保護線相鄰 | TI slva680A §2.3 原文 |

### J3. TVS 電氣選型（atlaspcb 逐值）

| 規則 | 量化值 |
|---|---|
| 響應時間 | <1 ns |
| 電容(高速線 >1Gbps) | <1 pF（理想 <0.5pF） |
| 電容(USB2.0 480Mbps) | ≤5 pF |
| 漏電流 | <1 µA @ working V |
| clamp 餘裕 | V_clamp < IC abs max，留 ≥0.5V margin |
| peak pulse current(±8kV contact) | ~16 A |
| 介面 Max TVS Cap | USB2=5pF / USB3=0.5pF / HDMI2.1=0.3pF / Ethernet=3pF / GPIO=5pF / CAN=15pF |

### J4. guard ring / ESD ground（atlaspcb 逐值）

| 規則 | 量化值 |
|---|---|
| guard ring trace 寬 | ≥0.5 mm(20 mil) |
| guard ring via 間距 | ≤5 mm（ESD 至 300MHz，λ/20） |
| guard ring via 尺寸 | 0.3 mm drill PTH |
| guard ring gap | 缺口 <1mm，內層橋接 |
| ferrite bead(補強) | connector 與 TVS 間可加，但不可拖慢 TVS 響應 |

來源錨點：`esd://ti-slva680a`（TI 原文）+ `esd://atlaspcb`（二手逐值,引 IEC 61000-4-2）。

UNVERIFIED（family J，不臆造）：Littelfuse 原文兩份（需 browser session，未取條款級 mm/nH）、CMC 具體量化（距 connector mm/對稱容差）、ferrite bead 選型（DC-R vs 額定電流/impedance@頻率/LC 諧振避免）、pi filter/feed-through cap 拓樸值、power-entry（MOV/inrush/fuse 額定）、cable shield 360° 接地具體準則。

---

## 家族 K：DDR3 記憶體 routing（TI sprabi1 DDR3 原廠級逐值；DDR4/5 UNVERIFIED）

來源：TI sprabi1（DDR3 Design Requirements for KeyStone，34頁官方 PDF pdftotext 解碼）＝原廠級。DDR4（Xilinx UG583 擋直連 / TI 命中誤為 DDR2/OSPI）、DDR5（無命中）逐值誠實標 UNVERIFIED，不臆造。

### K1. fly-by topology + termination（DDR3）

| 規則 | 量化值 | 出處 |
|---|---|---|
| fly-by 拓樸 | address/command/control/clock 走 fly-by 菊鏈，端接 VTT | TI sprabi1 §3.1.2 |
| VTT termination 電阻 | 39-42Ω（偏好 39Ω 1%） | §3.4 |
| VTT 定義 | VDDq/2 = 0.75V（DDR3 1.5V） | §3.4 |
| termination 擺位 | 置 fly-by 最末 SDRAM 端；each trace 到 termination ≤500 mil | §3.4 |
| ZQ 校準電阻 | 專用 240Ω（≤1% tolerance）每顆 SDRAM | §3.3 |

### K2. length matching 三級逐值（DDR3，Table 6-2~6-6）

| net class | 量化值 | 出處 |
|---|---|---|
| Address/Command | 到 clock ±20 mil；stub<80 mil；stub skew ±10 mil | §6.3.1.4/Table 6-2 |
| Control(CS/CKE/ODT) | 到 clock ±20 mil；stub<80 mil；stub skew ±10 mil | §6.3.1.5/Table 6-3 |
| Data(DQ within byte-lane) | byte-lane 內 DQ ±10 mil | §6.3.1.6/Table 6-4 |
| DQS diff pair intra-pair | DQS/DQS# skew ±1 mil | §6.3.1.6/Table 6-4 |
| Clock CK/CK# intra-pair | CK/CK# skew ±1 mil；stub<40 mil | §6.3.1.7/Table 6-6 |
| DQ 換層 | 單 byte-lane 全走同層（避 via barrel skew） | §6.3.1.6 |
| via 數一致 | 各 length-matched 段須有相同 via 數 | §6.3.1.4 |

### K3. impedance（DDR3）

| 訊號 | 目標阻抗 | 出處 |
|---|---|---|
| Address/Command/Control (SE) | 50Ω ±5% | §6.3.1.4/5 |
| DQ point-to-point (SE) | 50Ω ±5% | §6.3.1.6 |
| DQS diff pair | 100Ω ±5% | §6.3.1.6 |
| CK/CK# diff pair | 100Ω ±5% | §6.3.1.7 |
| PCB 系統阻抗 | 50Ω（多數 DSP 板） | §6.2 |

### K4. spacing / VREF（DDR3）

| 規則 | 量化值 | 出處 |
|---|---|---|
| center-to-center spacing | ≥5W（含 serpentine）；4W 僅限 ≤1066 MT/s | §6.2 |
| 長線走 stripline | 降 EMI/skew | §6.2 |
| reference plane | 相鄰 solid ground 或 solid DVDD15 power plane | §6.3.1.4 |
| VREF trace 寬 | ≥30 mil(0.762mm)、盡量短 | §6.3.x |
| VREF 間距 | 距其他 net ≥15 mil(0.381mm) | §6.3.x |
| VTT rail tracking | track VDDq/2，1% 分壓 | §3.4 |
| ZQCS 校準精度 | 最小 0.5% impedance error / 64 clock | §3.3 |

來源錨點：`ddr://ti-sprabi1`（DDR3 原廠級）。

UNVERIFIED（family K，不臆造）：DDR4 全套（POD termination 取代 VTT SSTL、per-bit deskew、DBI、byte-lane match 放寬）、DDR5 全套（on-DIMM PMIC、DFE、2×32-bit sub-channel、更嚴 skew 窗）、byte-lane 間 match 窗（fly-by + write/read leveling 吸收 lane skew，確切窗需 JEDEC/控制器原廠佐證）、DDR4/5 VTT/POD 電阻值。

---

## 蒸餾計畫

family J 產出 **2 個新 control 物件**（repo scope）：
1. `control.esd.tvs-placement-routing` — TVS 擺位/routing（TI 原文級 keep-out/no-stub/45°/L3-min + atlaspcb 10mm/5mm/2-via/guard-ring）— confidence verified（TI 原文級）
2. `control.esd.tvs-electrical-selection` — TVS 電氣選型（介面→Max TVS Cap + V_clamp margin + IEC level 目標）— confidence partial

family K：待 B 回報後定物件數。

link 織網（family J）：
- `esd.tvs-placement-routing` → `references` `control.verify.kicad-dru-rule-language`（keep-out/clearance 落地）
- `esd.tvs-placement-routing` → `references` `control.emc.stitching-shielding-plane`（ground via/guard ring 與 EMC 互補）
- `esd.tvs-electrical-selection` → `references` `control.si.diff-pair-impedance-geometry`（介面分類共用）
- 2 物件 `distilled_from` batch7 asset
