# 互補源 verify 知識萃取 batch10（flex 過渡區補缺 + power-entry protection/charger IC）

> 目的：補 batch9 `control.flex.bend-area-geometry` 的 UNVERIFIED 缺口（family P），與知識庫全缺的保護電路/充電 IC layout 維度（family Q）。
> - family P：IPC-2223 全文 §5.2.1/5.2.3/5.2.6-10 + Altium Rigid-Flex Guide（支線 A ses_0d4aeb788，已 read_subsession 核對）
> - family Q：Littelfuse/ON AND8232 + Rohm TVS AN + TI SLUAAU1 bq257XX charger（支線 B ses_0d4ae71eb，已 read_subsession 核對）
>
> 天條守則：每數值附逐字來源引文+文件編號+章節；查無來源標 UNVERIFIED，不臆造。皆原廠/標準原文級 pdftotext 解碼真值，無記憶臆造。

---

## 家族 P：flex 過渡區 / coverlay / stiffener 補缺（IPC-2223 標準原文級 + Altium 廠商交叉）

### P1. coverlay 覆蓋/厚度逐值（§5.2.3.1 / §5.2.3.4.2）

| 規則 | 量化值 | 出處 |
|---|---|---|
| coverlay adhesive 最小厚度基準 | 0.025mm per 34µm 銅厚 | §5.2.3.1 |
| coverlay 典型構造（單面例） | 0.025mm PI film + 0.025mm adhesive（總 0.136mm） | §5.2.3.1 |
| 高電流 coverlay adhesive 增厚 | 69µm 銅時 adhesive → 0.050mm | §5.2.3.1 |
| 機械強度 coverlay film 增厚 | film ≥0.050mm 或更厚（獨立於 adhesive） | §5.2.3.1 |
| dynamic flex coverlay（雙面例） | 25µm PI + 50µm adhesive（D=75µm） | §5.2.3.4.2 |
| coverlay 材料型別（廠商交叉） | film PI/LPI；PI/PET film ⅓–3 mil，1–2 mil 典型 | Altium guide |

### P2. stiffener 逐值（§5.2.10 + Altium 材質）

| 規則 | 量化值 | 出處 |
|---|---|---|
| stiffener access hole 直徑 | land 直徑 + ≥0.25mm | §5.2.10 |
| stiffener 邊緣處理 | 近 flex 側須 radiused/chamfered/adhesive-filleted | §5.2.10 |
| stiffener 規格標註 | 材質/尺寸/厚度/adhesive 型別須標 master drawing | §5.2.10 |
| stiffener 材質選項（廠商） | FR4 / rigid polyimide / 金屬（connector 用） | Altium guide |

### P3. rigid-flex 過渡區 keepout 逐值（§5.2.1 原文級硬規則）

| 規則 | 量化值 | 出處 |
|---|---|---|
| **rigid→flex 過渡邊 hole/PTH keepout** | **≥1.9mm** | §5.2.1.3 |
| flex 段 hole-to-edge | ≥1.3mm | §5.2.1.2 |
| **rigid→flex interface fillet（過渡幾何）** | 典型 1mm ~ 2.5mm 自 interface | §5.2.9 |
| cutout 圓角孔徑（過渡處） | ≥1.6mm（Figure 5-2 drilled hole） | Fig 5-2 |
| strain-relief slit/slot 終止孔 | ≥1.5mm 直徑孔 | §5.2.8 |
| variable thickness（過渡構造） | rigid laminated 段須同厚度以利 PTH 加工 | §5.2.1.5 |

### P4. hatched/crosshatched plane（§5.2.6/5.2.7 定性原文級）

| 規則 | 量化值 |
|---|---|
| ground/power plane 於 bend 區 | 分佈/破斷/平衡導體寬度過 bend 區；plane 可 latticed/crosshatched | §5.2.7 |
| shield layer crosshatch | shield layer 保持最小厚度，latticed/crosshatched 增撓性與附著 | §5.2.6 |

來源錨點：`flex://ipc-2223`（標準原文）+ `flex://altium-rigidflex`（廠商）。

UNVERIFIED（family P，不臆造）：hatch 開口百分比%/線寬 mil（§5.2.6/7 僅定性「as electrical characteristics allow」）、stiffener 絕對厚度逐值（§5.2.10 明定「由 master drawing 設計者指定」，非標準固定值）、stiffener 邊緣到 bend line 距離逐值、過渡區「不放元件」距離逐值。

---

## 家族 Q：power-entry protection + 充電 IC layout（原廠原文級）

### Q1. TVS/ESD layout（AND8232 + Rohm TVS AN）

| 規則 | 量化值/準則 | 出處 |
|---|---|---|
| TVS 近 connector | TVS 置 I/O connector 最近處，surge 耦合進鄰 trace 前先箝位 | AND8232 |
| TVS trace 比 IC 短 | TVS 到 connector trace 須比 IC 到 connector trace 短且小 | AND8232 Fig 3 |
| ground stub 短而寬 | 單一 ground 時 TVS 接地阻抗以短而寬 stub 最小化 | AND8232 |
| shunt 至 chassis/power ground | surge 分流至 reference/chassis ground（非直接 signal ground，避 ground bounce） | AND8232 Fig 5 |
| loop area 最小化 | 最小化 high-speed data 與 ground line loop 面積（loop=非預期天線） | AND8232 Fig 7 |
| 多層板降電感 | 短 trace + 多層板（獨立 ground/power plane）降寄生電感 | AND8232 |
| **寄生電感量化錨** | 50mm×0.5mm → 52nH；80mm×0.5mm → 91nH | Rohm TVS AN Fig 2 |
| 增寬 trace 降電感 | cathode↔被保護 wiring、anode↔ground plane 距離最小化 | Rohm TVS AN |
| TVS 封裝選小 | 電感正比封裝尺寸；SMD 優於 leaded | AND8232 |

### Q2. 電池/充電 IC layout（TI SLUAAU1 bq257XX）

| 規則 | 量化值/準則 | 出處 |
|---|---|---|
| **Kelvin sensing** | RAC/RSR current-sense 用 Kelvin；sense trace 接 pad 中心、走差分對 | §2.4 |
| non-Kelvin 誤差 | non-kelvin 使 SRP/SRN 電壓≠sense resistor 真實壓降 | §2.4 |
| **via 載流量化** | 10mil via + 1oz copper ≈ 1~2 A/via | §2.3 |
| high di/dt loop 最小化 | input/output switching loop 面積最小化，power 元件同層 | §2.3 |
| PGND/AGND 分離 | 先分離避小信號 ground 耦合 high di/dt 噪 | §2.6 |
| ground 近 power 層 | ground 置 power 元件層旁作屏蔽，最低熱阻/最小高頻 loop | §2.2 |
| 去耦電容擺位 | 10nF+1nF(0402) 置 RAC 後、儘量近 FET | §2.3 |
| BTST trace 寬度 | BTST1/2 節點≥8mil trace 降寄生電感；SW 節點用寬 copper polygon | §2.5 |
| SW 銅面積取捨 | SW pour 不宜過大（high dv/dt 經容耦合致 EMI） | §2.2 |
| 電池感測擺位 | QBAT、RSR 置電池端子近處（device 經 SRN pin 偵測） | §2.3 |

來源錨點：`protection://on-and8232`（原廠）+ `protection://rohm-tvs`（原廠）+ `power://ti-sluaau1`（原廠，bq257XX charger）。

UNVERIFIED（family Q，不臆造）：fuse/PTC 擺位載流逐值 mm、MOV/AC creepage 安規間距逐值（前批 batch8 SLUP421 有錨點+公式型）、reverse-polarity P-FET/N-FET layout（body diode 方向/gate 保護）、inrush NTC/soft-start 擺位。特別註明：TVS↔IC「trace 長度上限」原廠實為定性+電感錨（52nH@50mm），非硬 mm 上限；via 載流 1~2A@10mil 與 batch9 SLVA959 Table 3-1（10mil=0.81A）為不同情境估值須並列。

---

## 蒸餾計畫

batch10 產出 **3 個新 control 物件**（repo scope，confidence=verified）：

1. `control.flex.transition-keepout` ← family P：rigid→flex 過渡邊 hole/PTH keepout ≥1.9mm + flex hole-to-edge ≥1.3mm + interface fillet 1~2.5mm + strain-relief slit ≥1.5mm 孔 + coverlay adhesive 0.025mm/34µm(69µm→0.050mm) + stiffener access-hole land+0.25mm + bend 區 plane crosshatch — source_weight 7（IPC-2223 原文）
2. `control.protection.tvs-esd-layout` ← family Q1：TVS 近 connector + trace 比 IC 短 + ground stub 短寬 + shunt chassis-ground + loop 最小化 + 寄生電感錨 52nH@50mm×0.5mm — source_weight 7（AND8232/Rohm 原廠）
3. `control.power.charger-ic-layout` ← family Q2：Kelvin sensing 差分對 + via 1~2A@10mil-1oz + PGND/AGND 分離 + high di/dt loop 最小化 + BTST≥8mil + 去耦 10nF+1nF 近 FET — source_weight 7（TI SLUAAU1 原廠）

link 織網：
- `flex.transition-keepout` → `references` `control.flex.bend-area-geometry`（同 IPC-2223 撓性板域，補過渡區/coverlay/stiffener 維度）
- `flex.transition-keepout` → `references` `control.verify.kicad-dru-rule-language`（1.9mm/1.3mm keepout 落 DRU keepout rule）
- `flex.transition-keepout` → `references` `control.dfm.ipc-annular-tolerance-stack`（access-hole land+0.25mm 與 annular 互補）
- `protection.tvs-esd-layout` → `references` `concept.pcb-return-path-stitching`（stub 電感/return path 互補）
- `protection.tvs-esd-layout` → `references` `control.placement.power-stage-hot-loop`（loop 面積最小化互補）
- `charger-ic-layout` → `references` `control.power.current-sense-layout`（Kelvin 差分對 sense = bq 系列具體實作）
- `charger-ic-layout` → `references` `control.power.high-current-via-ground`（via 1~2A@10mil vs SLVA959 Table 3-1，不同情境交叉）
- `charger-ic-layout` → `references` `control.placement.power-stage-hot-loop`（high di/dt loop 最小化）
- 3 物件 `distilled_from` batch10 asset
