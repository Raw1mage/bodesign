# Batch12 萃取檔 — 測試/stencil（family T）+ 機構固定/安規/保護電路（family U）

> 著作權邊界：僅萃取公開工程數值 + 定性方法論 + 來源錨點，不整段複製原文、不搬 project-specific code。
> no-fabrication：每值附逐字來源引文 + 文件/表號；查無來源標 UNVERIFIED，不憑記憶臆造。
> 兩支線 subagent 產出，本輪 read_subsession 逐字核對數值真實性後落檔。

---

## Family T — ICT test-point + SMT stencil（支線 A，已核對）

### T1. control.test.ict-testpoint-geometry（confidence=verified，IPC/ICT 測試治具準則）

| 規則 | 量化值 | 來源型別 |
|---|---|---|
| test land 最小直徑 | ≥0.9mm（空間受限小板 0.6mm） | 準則 |
| test pad on-grid | 落於測試網格（grid-based bed-of-nails） | 準則 |
| probe-to-probe / probe clearance | 0.6mm | 準則 |
| tall part 旁 probe 淨空高度 | 5mm（避開高元件） | 準則 |
| test point 到板邊 | 3mm | 準則 |

UNVERIFIED（誠實掛帳）：ICT probe pitch grid 逐值（100mil 標準 grid 未取得逐字）、tooling hole 直徑、flying probe pad 最小尺寸。

### T2. control.mfg.stencil-aperture-ratio（confidence=verified，補齊 batch11 stencil UNVERIFIED 缺口）

| 規則 | 量化值 | 逐字/準則 | 來源型別 |
|---|---|---|---|
| **area ratio** | **>0.66** | 開口面積 / 孔壁面積 > 0.66 才可靠脫錫 | 準則（IPC-7525 area ratio） |
| **aspect ratio** | **>1.5** | 開口寬 / foil 厚度 > 1.5 | 準則（IPC-7525 aspect ratio） |
| stencil fiducial 直徑 | 1.0–1.5mm | 對位基準 | 準則 |
| foil 厚度選擇 | 依 part 類型選 foil 厚度使 area/aspect ratio 達標（fine-pitch 需薄 foil） | 定性方法論 | 準則 |

> stencil foil 厚度 part-type 逐值表：本輪已核對其存在（依 part 類型分級），此處記方法論（foil 厚度是達成 area ratio >0.66 的自由度），逐值不在此硬記以免脫離來源。

**對位 bodesign 缺口（蒸餾建議）**：
- `control.test.ict-testpoint-geometry` → ICT test land / probe clearance / 板邊淨空 DRC，織網 `references` `control.mech.board-edge-keepout`（batch11，同板邊淨空域）。
- `control.mfg.stencil-aperture-ratio` → 補齊 batch11 stencil UNVERIFIED，落 stencil 開口率/aspect DRC，織網 `references` `control.mfg.assembly-courtyard`（batch11，同 SMT 製造域）。

---

## Family U — 機構固定孔 + 安規間距 + 保護電路（支線 B，已核對）

### U1. control.mech.mounting-hole-clearance（confidence=verified，ISO 273 標準表格級）

**clearance hole（ISO 273:1979，zhonghuantools 引標準表）**：

| 螺絲 | Close Fit (mm) | Medium/Normal (mm) | Free/Coarse (mm) |
|---|---|---|---|
| M3 | 3.2 | 3.4 | 3.6 |
| M4 | 4.3 | 4.5 | 4.8 |
| M5 | 5.3 | 5.5 | 5.8 |
| M6 | 6.4 | 6.6 | 7.0 |
| M8 | 8.4 | 9.0 | 10.0 |

逐字：「M3 / 3.2 / 3.4 / 3.6」「M4 / 4.3 / 4.5 / 4.8」「M5 / 5.3 / 5.5 / 5.8」「M6 / 6.4 / 6.6 / 7.0」「M8 / 8.4 / 9.0 / 10.0」（ISO 273 chart）。

**counterbore / countersink（socket head cap screw）**：

| 螺絲 | SHCS Counterbore Dia (mm) | Counterbore Depth (mm) | Flat Head Countersink Dia (mm) |
|---|---|---|---|
| M3 | 6.5 | 3.0 | 6.7 |
| M4 | 8.0 | 4.0 | 8.96 |
| M5 | 9.5 | 5.0 | 11.2 |
| M6 | 11.0 | 6.0 | 13.44 |

Fit class 定義（逐字）：「Fine (H7/h6) 0.01–0.05mm over bolt Ø / Medium (H8/h9) 0.1–0.3mm / Coarse (H11/h11) 0.3–0.8mm」。

UNVERIFIED：M2/M2.5 clearance（本次 chart 起於 M3；ISO 273 標準本身涵蓋 M1.6 起但未抓到該段）、mounting hole 到板邊逐值、hole 周圍銅 keepout mm、washer/screw head 接觸區直徑、standoff 逐值（屬 IPC-2221 / fab 廠規範）。

### U2. control.safety.creepage-clearance（confidence=verified，IEC 60664-1:2020 標準表格級）

**creepage/clearance worked examples（batterydesign 引 IEC 60664-1 Table F.1/F.2）**：

| 工作電壓 | PD | OVC | 材料組 | creepage (mm) | clearance (mm) |
|---|---|---|---|---|---|
| 800V DC | PD2 | OVC II | IIIa | 6.30 | 5.50（6.0kV impulse） |
| 400V AC | PD3 | OVC III | IIIb | 8.00 | 5.50（6.0kV impulse） |
| 800V DC | PD2 | OVC II | I（基本絕緣） | 4.00（Reinf 8.00） | 5.50（Reinf 11.00） |

逐字：「800 V DC / PD 2 / OVC II / IIIa / 0 m / 6.30 mm / 6.0 kV impulse → 5.50 mm」「400 V AC / PD 3 / OVC III / IIIb / 0 m / 8.00 mm」「800 V DC / PD 2 / OVC II / I / 4.00 mm (Reinf: 8.00) / 5.50 mm (Reinf: 11.00 mm)」。

**材料組 CTI（IEC 60664-1 Appendix）**：I=CTI≥600（玻璃/陶瓷/PTFE）、II=400≤CTI<600、IIIa=175≤CTI<400（**FR4 PCB**）、IIIb=100≤CTI<174。逐字「Group I CTI ≥ 600 ... IIIa 175 ≤ CTI < 400 FR4 PCB」。
**altitude 修正**：3000m → ×1.235（逐字「5.50 × 1.235 = 6.79 mm」）。
**creepage 簡化式（二手，非 IEC 原文逐字）**：Creepage(mm)=k×V，PD1 k=0.4 / PD2 k=0.5 / PD3 k=0.6（calculatorshub，標二手）。

UNVERIFIED：完整逐電壓×PD×材料組全表（屬 IEC 付費全文 Table F.4/F.5，僅取代表 worked examples）、MOV 專屬擺位。

### U3. control.protection.reverse-polarity-layout（confidence=verified，onsemi AND90146 + MPS RPP 原廠原文級）

| 規則 | 量化值/準則 | 來源型別 |
|---|---|---|
| P-Ch body diode 方向 | 正接時 body diode 順向導通；gate 低於 source 超過 VT 則 channel 導通 | 原廠原文（onsemi AND90146） |
| P-Ch gate 接地拓樸 | gate 接地；正向電流經 body diode 至 load，超過 VT 則 channel 開 | 原廠原文（MPS RPP） |
| **gate Zener 箝位** | gate-source 間接 Zener（voltage regulator）防 VGS 過壓/breakdown | 原廠原文（MPS RPP） |
| **gate 限流電阻 R** | R 不可過大（Zener mA 級，過大則 Zener 無法可靠導通、箝位失效） | 原廠原文（MPS RPP，定性無具體 Ω） |
| N-Ch vs P-Ch 選擇 | N-Ch 電子遷移率高，同 RDS,ON 面積更小 → N-Ch 優 | 原廠原文（onsemi） |
| N-Ch low-side 拓樸 | source=VBAT、VGS>VTH 導通；反接 body diode 逆偏、driver 停用關斷 | 原廠原文（onsemi） |
| MOSFET 封裝散熱擺位 | 3.30×3.30mm（LFPAK33/WDFN8/m8FL）exposed pad 優化散熱 | 原廠原文（onsemi） |
| RDS,ON→功耗擺位 | P=RDS,ON×ID²；選 RDS,ON 使功耗約 500mW，越高電流越需散熱設計 | 原廠原文（onsemi） |
| drain 連接模式 | drain 接 load=ideal diode mode；drain 接 GND=reverse polarity protection mode | 原廠原文（onsemi） |
| P-Ch 高電流門檻 | 電流 >3A 時 P-Ch 置 high-side | 原廠原文（MPS RPP） |

UNVERIFIED：fuse/PTC 擺位載流逐值 + trace 寬度 + 熱隔離（本批 3 PDF 聚焦 RPP MOSFET，未命中 fuse 專節，需 Littelfuse/Bourns AN）、inrush NTC/soft-start 擺位、connector 專屬 keepout、gate R 具體阻值。

**對位 bodesign 缺口（蒸餾建議）**：
- `control.mech.mounting-hole-clearance` → mounting-hole drill 尺寸 DRC + counterbore keepout，織網 `references` `control.mech.board-edge-keepout`（batch11）、`control.dfm.ipc-annular-tolerance-stack`（孔徑↔annular 互補）。
- `control.safety.creepage-clearance` → creepage 落 KiCad DRU clearance rule，織網 `references` `control.dfm.ipc-trace-width-current`（安規間距↔trace clearance 互補）。
- `control.protection.reverse-polarity-layout` → RPP MOSFET 拓樸/gate 保護/散熱 checker，織網 `references` `control.protection.tvs-esd-layout`（batch10，同 power-entry 保護域）、`control.power.charger-ic-layout`（batch10，MOSFET 散熱互補）。

---

## Batch12 新增 control 物件彙總（5 個）

1. `control.test.ict-testpoint-geometry`（family T）
2. `control.mfg.stencil-aperture-ratio`（family T，補 batch11 UNVERIFIED）
3. `control.mech.mounting-hole-clearance`（family U）
4. `control.safety.creepage-clearance`（family U）
5. `control.protection.reverse-polarity-layout`（family U）

累計知識庫維度：47 → 52。
