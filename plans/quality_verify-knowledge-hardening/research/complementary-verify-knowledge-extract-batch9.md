# 互補源 verify 知識萃取 batch9（撓性板 flex + 高電流/電源 layout：補結構與大電流缺維度）

> 目的：補知識庫完全缺的 **撓性板 flex/rigid-flex**（family N）與 **高電流/電源 layout**（family O）維度。
> - family N：IPC-2223 + 廠商 flex design guide（待支線 A 回報後補）
> - family O：TI SLVA959 官方 PDF（原廠級，Best Practices for Board Layout of Motor Drivers，引 IPC-2152）
>
> 天條守則：每數值附來源錨點；查無來源標 UNVERIFIED，不臆造。TI/IPC 原廠走原文 PDF（條款級）；廠商 guide 明標。

---

## 家族 N：撓性板 flex/rigid-flex（IPC-2223 標準原文級）

來源：IPC-2223 Sectional Design Standard for Flexible Printed Boards（1998, archive.org 全文 pdftotext 解碼）＝標準原文級；JLCPCB/pcbsync 二手交叉。已 read_subsession 核對（ses_0d4bcfe51），無記憶臆造。

### N1. copper elongation → 最小彎曲（§5.2.3.4.1, rolled-annealed 銅）

| 使用類型 | copper deformation E |
|---|---|
| One time crease（一次折彎） | 16%（ultimate elongation at break, RA 銅） |
| Flex-to-install（Use A 裝配彎） | 10%（IPC-MF-150 min elongation） |
| Dynamic flex（Use B 動態彎） | 0.3% |

### N2. R/T 比值逐值計算範例（§5.2.3.4）

| 構造 | 使用類型 | E | R(min bend radius) | R/T |
|---|---|---|---|---|
| Single-sided (T=185µm) | One time crease | 16% | 16.9µm | 0.09 |
| Single-sided | Flex-to-install | 10% | 0.08mm | 0.45 |
| Single-sided | Dynamic flex | 0.3% | 5.74mm | 31 |
| Double-sided+coverlay (T=320µm) | One time crease | 16% | 0.371mm | 1.16 |
| Double-sided+coverlay | Flex-to-install | 10% | 0.690mm | 2.15 |
| Double-sided+coverlay | Dynamic flex | 0.3% | 28.17mm | 88 |

計算式: Single-sided R=(c/2)[(100-E)/E]-D (Eq1); Double-sided R=(d/2+c)×[(100-Ea)/Ea]-D (Eq2). c=copper厚µm, D=dielectric厚µm, E=deformation%.

### N3. bend 區導體準則（§5.2.3.3 原文級硬規則）

| 規則 | 量化/準則 |
|---|---|
| trace 垂直 bend | 導體垂直於 bend line |
| trace 均勻分佈 | 均勻跨 bend 區、最大化跨越、寬度一致 |
| 無額外鍍層 | bend 區導體不加 plated metal |
| double-sided 不重疊 | 雙面導體不得正上下對齊（避 I-beam 效應） |
| bend 區減層 | bend 區層數最小化 |
| bend 區避 via/PTH | via 與 PTH 應避免置於 bend 區 |
| neutral axis | 導體置中性軸；兩側等 modulus/厚度達平衡構造 |
| 不彎於不連續處 | 不得於 covercoat 不連續/plating 終止/potting/應力集中處彎折 |

### N4. 多層/銅箔/介電（原文級）

| 規則 | 量化值 |
|---|---|
| adhesive 厚度基準 | 0.025mm per 34µm 銅厚 |
| 3層以上不建議 | 3-4層使導體離 neutral axis 過遠致銅拉伸 |
| Board Type | Type1=單面/Type2=雙面/Type3=多層 flex/Type4=剛撓結合/Type5 |
| Use 分類 | Use A=flex-to-install / Use B=dynamic flex / Use C=high temp >105°C |
| RA vs ED 銅 | 動態撓曲用 rolled-annealed(RA)（elongation 優於 ED） |

### N5. 二手交叉（JLCPCB/pcbsync，佐證 IPC-2223）

| 規則 | 量化值 |
|---|---|
| static bend min | ≥6× total thickness（業界簡化口訣） |
| dynamic bend min | ≥100× total thickness |
| flex 區技法 | 薄 RA 銅、adhesiveless PI、staggered traces、cross-hatched pattern |

來源錨點：`flex://ipc-2223`（標準原文）+ `flex://jlcpcb`（二手交叉）。

UNVERIFIED（family N，不臆造）：coverlay 覆蓋厚度/重疊逐值、stiffener 厚度逐值、rigid-flex 過渡區 via/PTH keepout mm、hatched plane 開口率。特別標注：static 6×/dynamic 100× 為業界簡化口訣，IPC-2223 原文實為 elongation-based R/T 計算法（動態範例 R/T=31~88 與 100× 量級一致）。

---

## 家族 O：高電流/電源 layout（TI SLVA959 原廠級，聚焦 via-ampacity/grounding/sensing，不重複前批 IPC-2152 trace-width）

### O1. via / copper pour ampacity（TI 原廠級 Table 3-1）

| 規則 | 量化值 | 出處 |
|---|---|---|
| **單 via 載流 Table 3-1** | 6mil=0.2A / 8mil=0.55A / 10mil=0.81A / 12mil=0.84A / 16mil=1.1A（10°C rise, 1-oz, per IPC-2152） | SLVA959 §3.1 Table 3-1 |
| 高電流用 multi-via | power 連接用 multi-via/via stitching 確保低阻抗跨層；via 靠近電流進出元件腳 | §3 |
| via 直徑準則 | copper plane 當 trace 時，via 直徑至少等於 trace 長度 | §3.1 |
| copper 厚度 | 儘量用 1.5- 或 2-oz copper | §2.6 |

### O2. thermal via（TI 原廠級）

| 規則 | 量化值 | 出處 |
|---|---|---|
| thermal via 尺寸 | 20 mil diameter / 8 mil hole（thermal pad 正下方） | §2.5 |
| 單 thermal via 熱阻 | θCu = 5.7304 °C/W（1.561mm FR-4, 20/8mil, Eq.4） | §2.5 Eq.4 |
| 焊錫 wicking 控制 | 7.874 mil × 19.874 mil 避免過度 solder wicking | §2.6 |
| direct-connect vs thermal relief | power via 須 direct bond（thermal relief spoke 降熱流，不可用於 power via） | §2.4 |
| thermal via 分組 | 分組成陣列求最小跨層熱阻 | §2.4/2.6 |

### O3. grounding 拓樸（TI 原廠級）

| 規則 | 量化值 | 出處 |
|---|---|---|
| single-point distribution | 所有 reference 從 source 出發；建議用於 power distribution traces | §1.1 |
| star-ground distribution | reference 集中一點（source 未必居中），平衡共同阻抗；建議用於 signal traces | §1.1 |
| power/logic ground 合併 | 於 star-point/single-point 合併高電流 ground 與 logic ground | §1.3.1 |
| ground gridding（2-layer） | 無完整 plane 時用 ground fill+trace+via 網格化，近似真 ground plane | §1.1.1 |
| ground plane 建議 | 4-layer 或大 2-layer 用連續 ground plane；via 彼此拉開避免斷 plane | §1.2 |
| current loop 面積 | 最小化 return current loop 面積（loop 當天線輻射，正比電流/頻率/幾何面積） | §1.4 |

### O4. current sensing / shunt（TI 原廠級）

| 規則 | 量化值 | 出處 |
|---|---|---|
| shunt 值範圍 | mΩ 級（20A×1mΩ=400mW，CSA 得 20mV） | §7 |
| shunt 擺位 | 與 power stage 元件 in-line 最小化 trace 阻抗；就近 CSA | §7 |
| high-side shunt 位置 | 近 supply 與 high-side MOSFET source 間 star point | §7 |
| low-side shunt 位置 | 置 low-side MOSFET source 與 star point ground 間 | §7 |
| **sense 走線 = 差分對** | sense 訊號須用 differential pair，緊耦合平行從 shunt 到 CSA input | §7 |
| gain resistor 順序 | 用外部 gain resistor 時，divider 第一顆最靠近 shunt | §7 |
| high-side vs low-side 取捨 | high-side 需較高 common-mode voltage；low-side 易受 ground noise 且無法偵測 short-to-ground | §7.1/7.2 |

### O5. high-current loop / Kelvin（TI 原廠級）

| 規則 | 量化值 | 出處 |
|---|---|---|
| VDRAIN Kelvin connection | high-current 路徑用 Kelvin 量測（避 IR drop 汙染 sense） | §6 Fig 6-13 |
| high-current loop 最小化 | high-current loop path 面積最小化 | §6 Fig 6-11/6-12 |
| bulk cap multi-via | bulk capacitor 用 multi-via 置放（低阻抗） | §5 Fig 5-1 |
| parallel gate/power trace | gate/power trace 平行多條走線分流 | §4 Fig 4-2/4-5 |
| via→pad 過渡 | via 過渡到 pad 須平滑（避免電流集中） | §4 Fig 4-4 |

來源錨點：`power://ti-slva959`（原廠級，引 IPC-2152）。

UNVERIFIED（family O，不臆造）：protection（fuse/PTC/TVS/MOV power-entry/reverse-polarity P-FET/inrush NTC）擺位載流、電池/充電 IC layout（bq 系列）、high-current connector 每腳載流、copper pour 面積→電流逐值（指向 IPC-2152 trace-width，前批已有）、多相 shunt 逐值。

---

## 蒸餾計畫

family O 產出 **2 個新 control 物件**（repo scope）：
1. `control.power.high-current-via-ground` — via 載流 Table 3-1（N_via ≥ I_net/via_capacity）+ power via direct-connect + thermal via 20/8mil 陣列 + 1.5-2oz + star/single-point/gridding ground + current loop 最小化 — confidence **verified**（TI 原廠級）
2. `control.power.current-sense-layout` — shunt in-line power stage + sense=differential pair + high/low-side 位置 + Kelvin VDRAIN + gain resistor 順序 — confidence **verified**（TI 原廠級）

family N 產出 **1 個新 control 物件**（repo scope）：
3. `control.flex.bend-area-geometry` — elongation-based R/T 計算式（Eq1 單面/Eq2 雙面，E=16%/10%/0.3% 依 use type）+ bend 區硬規則（trace 垂直 bend、禁 via/PTH、雙面不上下對齊、減層、neutral axis、不彎於不連續處）+ 二手保守 static≥6×T/dynamic≥100×T — confidence **verified**（IPC-2223 標準原文級）

link 織網（family O）：
- `power.high-current-via-ground` → `references` `control.thermal.via-array-jarray-network`（thermal via 陣列同源；此補「載流」維度、彼為「散熱」維度）
- `power.high-current-via-ground` → `references` `control.placement.power-stage-hot-loop`（hot loop 面積最小化互補）
- `power.high-current-via-ground` → `references` `control.dfm.ipc-2152-trace-width`（若存在；via 跨層載流 vs trace 平面載流互補，同引 IPC-2152）
- `power.current-sense-layout` → `references` `control.si.diff-pair-impedance-geometry`（sense=差分對，共用差分準則）
- `power.current-sense-layout` → `references` `control.placement.power-stage-hot-loop`（shunt in-line power stage）
- 2 物件 `distilled_from` batch9 power asset

link 織網（family N）：
- `flex.bend-area-geometry` → `references` `control.dfm.*`（撓性板 DFM = 剛性板 DFM 的撓性延伸；若存在）
- `flex.bend-area-geometry` → `references` `control.verify.kicad-dru-rule-language`（bend-zone via keepout 落 DRU keepout rule；若存在）
- 1 物件 `distilled_from` batch9 flex asset
