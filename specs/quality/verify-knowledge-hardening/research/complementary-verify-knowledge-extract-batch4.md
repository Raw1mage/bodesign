# 互補源 verify 知識萃取 batch4（IPC 幾何 · TI 電源佈局 · KiCad DRC/ERC 規則體系）

> 來源：跳出 pjcau，三個互補源家族補其缺乏的深度。
> - **IPC 標準幾何**（IPC-2221B / 7351B / 7352 / 6012 / A-600）— clearance/land pattern/annular 逐值
> - **TI app note 電源佈局**（SLYT614 五步法、SNVA803 EMI power stage）— hot-loop/decap/SW-node/熱管理真實量化
> - **KiCad EDA verify 規則體系**（9.0.9 官方文件）— DRC/ERC 分類 + `.kicad_dru` custom rule 語法（可移植規則介面）
>
> 天條守則：每個數值附來源錨點；查無來源標 UNVERIFIED，不憑記憶填。IPC 原文有著作權——只萃數值+定性一句+出處，不整段複製。TI app note 正文經 curl+pdftotext 解碼（poppler 24.02）取真實值；KiCad 為 GPL/CC-BY，語法可自由引用。

---

## 家族 A：IPC 標準幾何規則（可落成確定性 checker 的數值層）

### A1. IPC-2221B Table 6-1 導體間距 vs 電壓（clearance）

單位 mm，海拔 <3050m。兩獨立二手來源（smpspowersupply / pcbsync，皆引 Table 6-1）逐列交叉一致 → 高信度。

| 導體類別 | 電壓帶 | 最小間距(mm) |
|---|---|---|
| 內層 B1 | 0–15V | 0.05 |
| 內層 B1 | 31–100V | 0.1 |
| 內層 B1 | 101–300V | 0.2 |
| 內層 B1 | 301–500V | 0.25 |
| 外層未塗覆 B2 | 0–30V | 0.1 |
| 外層未塗覆 B2 | 31–100V | 0.6 |
| 外層未塗覆 B2 | 101–150V | 0.6 |
| 外層未塗覆 B2 | 151–300V | 1.25 |
| 外層未塗覆 B2 | 301–500V | 2.5 |
| 外層塗覆 B4 | 0–30V | 0.05 |
| 外層塗覆 B4 | 31–100V | 0.13 |
| 外層塗覆 B4 | 101–300V | 0.4 |
| 外層塗覆 B4 | 301–500V | 0.8 |
| Component lead A6 | 0–30V | 0.13 |
| Component lead A6 | 31–100V | 0.6 |

**>500V 公式**（可寫成 checker 連續函式）：
- 外層未塗覆：`2.5 + (V−500)×0.005` mm
- 內層：`0.25 + (V−500)×0.0025` mm（等效 0.0025 mm/V）
- 塗覆/component（B4/A5/A6）：`0.005` mm/V

**判斷規則（可寫成 checker 語意）**：
- solder mask = 欄 B4；conformal coating = 欄 A5，**兩者不可互換**（材料類別不同）。
- creepage 用 slot 加大：slot 寬須 **>1mm** 才被 IPC/IEC 認可為有效 creepage 延伸。
- 高海拔 >3050m 另有修正欄；中國 GB 4943.1 需 **×1.48**（海平面值）。

來源錨點：`ipc://2221B/table-6-1`（二手轉述 smpspowersupply.com/ipc2221pcbclearance.html + pcbsync.com/pcb-creepage-clearance）。

### A2. IPC-7351B / 7352 land pattern 密度等級 & courtyard excess

| 規則 | 值 |
|---|---|
| 密度等級 A / B / C | A=Most material(最大land凸出) / B=Nominal(中位) / C=Least(最小凸出) |
| Courtyard excess 三級（IPC-7352 solder-joint goal） | Least=0.10 / Nominal=0.25 / Most=0.50 mm |
| SMD pad→courtyard 距離 | A=0.50 / B=0.25 / C=0.20 mm |
| THT pad→courtyard 距離 | A=0.75 / B=0.50 / C=0.25 mm |
| IPC-7351B 標稱 courtyard excess | 0.25mm（Nominal Density Level） |

> 實務調整值（非 IPC 標稱）：業界常用 0.10/0.20/0.40（Least/Nominal/Most）——蒸餾時標「實務值 vs IPC 標稱值」，checker 預設用 IPC 標稱。

來源錨點：`ipc://7351B,7352/courtyard`（pcblibraries.com forum，PCB Libraries Tom Hausherr 引 IPC-7352 表）。

### A3. IPC-6012 / A-600 annular ring & aspect ratio

| 規則 | 值 |
|---|---|
| Class 2 外層最小 annular | 50µm (2mil) at all points |
| Class 2 內層 | 允許 90° breakout |
| Class 3 外層最小 annular | 50µm (0.001969″) at all points |
| Class 3 內層最小 annular | 25µm (0.000975″)，**no breakout** |
| Aspect ratio Class 3 上限 | 8:1 (board thickness : hole diameter) |

**量測定義（判斷基礎，易錯）**：
- 外層 annular：由 **finished plated hole 內徑**量到 land 最短邊。
- 內層 annular：由 **drill diameter**（非 finished hole）量到 land 最短邊。→ 內外層基準不同，checker 不可混用。
- microvia：雷射鑽孔，**不進機械鑽孔的 hole-to-hole / hole-size 判斷**（與 KiCad 一致，見家族 C）。

**Tolerance stack（可寫成 tolerance-aware pad checker）**：
- 標準 CNC drill wander：±50µm(±2mil)；高精度 ±25µm；雷射 ±15–25µm。
- 鑽孔尺寸公差：≥0.30mm 機鑽 ±25µm；<0.15mm 雷射 ±15µm。
- 層間 registration：外層 ±50µm；內層 ±50–75µm；HDI 雷射 ±25µm。
- **worst-case pad 公式**：`Pad = MaxDrill + 2×(minAnnular + drillPosTol + registrationTol)`。
- Teardrop：有效 annular +20–50%。

來源錨點：`ipc://6012E/table-3-9`（summitinterconnect Gerry Partida 直引 Table 3-9 + atlaspcb fab 實務 + LinkedIn snippet aspect ratio）。

### A4. trace width vs current — UNVERIFIED
IPC-2152 / IPC-2221 trace-width vs current 逐值表（銅厚 vs 溫升 10/20°C 對應寬度）**未取得逐值**。多 calculator 頁存在但未回傳原始係數表。標 UNVERIFIED，下批單獨補 IPC-2152 charts。

---

## 家族 B：TI app note 電源佈局（正文經 pdftotext 解碼，真實量化值）

### B1. SLYT614 「Five steps to a great PCB layout for a step-down converter」（Chris Glaser, AAJ 1Q 2015）

正文經 `curl + pdftotext -layout` 解碼（非二進位臆造）。五步佈局法 + 可檢核規則：

| 步序 | 規則 | 量化/定性（逐字驗證） |
|---|---|---|
| Step 1 | input cap 最先擺、緊鄰 IC | 「it should be the first component placed in the layout after the IC」；「Place the input capacitor as close to the IC as allowed by manufacturing rules」 |
| Step 1 | input cap↔IC 路徑淨空 | 「Route the capacitor to the IC immediately after it is placed, so that nothing else can be routed in its path」 |
| Step 1 | 寄生電感致 IC 失效 | 「Extra parasitic inductance … creates excessive voltage spikes … V=L×dI/dt. This can lead to IC failure」 |
| Step 2 | SW node 銅箔面積最小化（EMI 耦合板） | 「place the inductor as close as possible to the IC with the area of the SW-node copper kept to a minimum」；「All copper connected to the SW node is one plate of a parasitic capacitor … a noise coupling path」 |
| Step 2 | snubber 置 SW–PGND 最短路徑 | 「shortest possible routing between the SW and PGND (GND) pins, minimizing its parasitic inductance」 |
| Step 3 | power 元件間迴路面積最小化、**不用 via** | 「Keeping these loop areas small enables the best operation」；「no vias should be used to route these components, because vias add significant inductance」 |
| Step 3 | VOS/FB 回授走線短且直 | 「Make the VOS pin trace short and direct to the output capacitor」；「keep the FB node as small as possible to minimize noise pickup」 |
| Step 4 | small-signal 元件緊鄰 IC、短走線 | 「Place each of these components close to the IC with a short and direct routing to keep their noise sensitivity low」 |
| Step 5 | single-point ground 匯於 exposed thermal pad | 「join these two grounds at a single point, typically the exposed thermal pad under the IC」 |
| Step 5 | power/quiet ground 分離後單點連 | 「keeping one ground for power components, which are noisy, and a separate ground for the small-signal components, which are quiet」 |
| Step 5 | **via 數量法則** | 「a good rule of thumb for the number of vias necessary is to use one via per amp of current flowing. However, more is better if room allows」 |
| Step 5 | thermal via 置 IC 下方 | 「vias are best placed directly under the IC so that the exposed thermal pad conducts its heat down into the PCB layers. This is required to achieve the IC's best thermal performance」 |
| 特例 | quiet ground 不接系統 GND plane（避免耦合雜訊） | 「Placing vias into the system ground plane on the quiet grounded components is not generally recommended because this can couple noise」 |

來源錨點：`ti://SLYT614`（www.ti.com/lit/an/slyt614/slyt614.pdf, AAJ 1Q 2015）。

### B2. SNVA803 「Improve High-Current DC/DC Regulator EMI Performance … Optimized Power Stage Layout」（Timothy Hegarty, 2019）

正文經 pdftotext 解碼。真實量化值（EMI power stage）：

| 規則 | 量化值（逐字驗證） |
|---|---|
| 橫向 switching loop（劣）迴路面積 | ~20 mm²；「a relatively high area of almost 20 mm2」，寄生電感 >1nH |
| 垂直 switching loop（優，L1/L2 self-cancel）迴路面積 | 2 mm²；「a small physical loop area of 2 mm2」 |
| 優化後寄生迴路電感 | <500 pH；「a parasitic loop inductance less than 500 pH, ringing is not evident」 |
| input decap 配置 | 「Four 10-nF input capacitors with small 0402 or 0603 case size … placed in parallel very close to the drain of Q1」；低 ESL + 高 SRF |
| input cap 負端接 L2 GND via | 「connected to the L2 GND plane with multiple 12-mil (0.3-mm) diameter vias, minimizing inductance」 |
| SW node 銅箔 | 「switch-node copper polygon … includes just the pad of the inductor and the minimum area required to connect to the MOSFETs」 |
| L1–L2 緊耦合間距 | 0.15mm（stack-up 圖標）；via 0.3mm |
| high-side FET 旋轉 90° | 改善散熱 + 便於 0603 decap 近距離擺放；「high-side FET (Q1) is rotated 90° … improves heatsinking」 |
| SW/BST 走線單層 | 「vias with high dv/dt do not appear on the bottom side … avoids e-field coupling to the reference ground plane during the EMI test」 |
| 量測效益 | 垂直 loop 峰值 overshoot 較橫向低 ~4V（VIN=48V/VOUT=12V/IOUT=8A） |

來源錨點：`ti://SNVA803`（www.ti.com/lit/an/snva803/snva803.pdf, 2019-09）。

> 著作權邊界：TI app note 為技術資源，此處只萃「規則定性一句 + 關鍵數值 + 出處」，不整段複製；蒸餾物件用自己的話重述，數值標 TI 來源錨點。

---

## 家族 C：KiCad EDA verify 規則體系（9.0.9，GPL/CC-BY，可自由引用）

### C1. DRC 違規類別（PCB / pcbnew）— 分類法（多數逐字嚴重度被官方 JS 表格截斷，標 UNVERIFIED）

clearance（copper-copper）、hole clearance（孔↔copper 異net）、hole-to-hole、physical clearance（不分net）、courtyard overlap（error）、footprint no courtyard、silk clearance、board edge clearance、via diameter（**error**）、annular width、hole size（oval 取小徑）、via count（custom rule 驅動，**error**）、malformed board outline、footprint↔library pad mismatch。

**判斷規則（逐字，機制層 SSOT）**：
- 嚴重度三態：「Each rule may be set to create an error marker, a warning marker, or no marker (ignored)」；設 Ignore = 完全停用該檢查。
- microvia 特例：「For the purposes of DRC, microvias are not considered drilled holes as they are laser drilled rather than mechanically drilled」（與家族 A3 一致）。
- board-level 最小值（annular width / micro via hole / through hole）可於 board setup 設為絕對下限。

### C2. ERC 違規類別（Schematic / eeschema）

pin-to-pin conflict（Pin Conflicts Map 驅動）、unconnected pin（warning，可 no-connect flag 抑制）、no-connect flag 誤用、power pin not driven（power_in 未被 power_out 驅動）、conflicting labels（一 net 只能一名，否則 violation）、bus alias 跨 sheet 衝突、bus entry needed、rule-area 交越、自訂 `ERC_ERROR <name>` directive label。

**pin type 分類（pin→net 判斷基礎，對位家族既有 pin-net-ssot）**：power_in / power_out / input / output / bidirectional / open-collector / open-emitter，各有 default Pin Conflicts 設定。netlist 型別範例：`(pin (num "3") (name "V+") (type "power_in"))`。

**天條相容 caveat（逐字）**：「ERC is imperfect and cannot detect all errors」→ ERC 通過 ≠ 設計正確，不可當充分條件（印證 bodesign 兩層審計哲學）。

### C3. `.kicad_dru` custom rule 語法（**可移植規則介面 — 最高價值**）

bodesign 把 ragbase 知識物件「編譯成確定性檢查」的理想目標格式。

規則骨架：
```
(rule "<名稱>"
      (condition "<selector 表達式>")
      (constraint <型別> (min …) (opt …) (max …)))
```

**Constraint 型別（22 項，逐字 token 掃描命中）**：clearance / physical_clearance / hole_clearance / physical_hole_clearance / edge_clearance / courtyard_clearance / silk_clearance / hole_size / track_width / annular_width / via_diameter / disallow（track/via/micro_via/zone/pad/hole/footprint）/ length / skew / diff_pair_gap / thermal_relief_gap / thermal_spoke_width / min_resolved_spokes / zone_connection / connection_width / creepage / assertion（自訂布林斷言）。

**Selector 函式（9 項，逐字驗證）**：`A.NetClass` / `A.hasNetclass('<name>')` / `A.Layer` / `A.Type` / `A.insideCourtyard` / `A.intersectsArea` / `A.inDiffPair` / `A.memberOf` / `A.isPlated`。

**關鍵語意（逐字）**：
- board-setup minimum = 絕對下限「cannot be overridden with a more specific design rule」。
- netclass 值 = optimal 非 min/max「They are not minimum or maximum values」，改 netclass 值不觸發 DRC。
- 多 netclass「effective aggregate net class … highest priority net class which has that property set」。
- arc 近似預設 0.005mm（唯一命中的具體預設數值）。

> **關鍵合成**：KiCad 提供 constraint **型別 + selector 語言介面**（規則怎麼寫），但**不提供數值**（文件明言依 board manufacturer）。→ 家族 A（IPC 數值）+ 家族 C（KiCad 規則語言）結合 = bodesign 可把知識物件**編譯成可移植 `.kicad_dru` 規則生成器**。這是 batch4 三源互補的核心價值。

來源錨點：`kicad://9.0.9/pcbnew,eeschema/drc-erc-custom-rules`（docs.kicad.org/9.0/en）。

### C4. UNVERIFIED（KiCad）
- 多數 DRC/ERC check 的逐字預設嚴重度（官方表格 JS 渲染 + webfetch 50K 截斷）；僅 via diameter/via count 確認 error。需讀 KiCad source `DRC_ITEM`/`ERC_ITEM` 定義補齊。
- Pin Conflicts Map 完整 24×24 矩陣。
- selector `A.insideArea`/`A.existsOnLayer`/`A.enclosedByArea`/`A.getField`（8/9 存在但 9.0.9 頁面未命中逐字）。

---

## 蒸餾計畫（對位 bodesign 缺口）

batch4 產出 **5 個新知識物件**（互補源，repo scope）：

1. `control.dfm.ipc-clearance-voltage` — IPC-2221B Table 6-1 全欄 + >500V 公式（clearance checker 數值層，跨兩來源一致）
2. `control.dfm.ipc-annular-tolerance-stack` — IPC-6012 Class2/3 50µm + worst-case pad 公式 + tolerance stack（tolerance-aware annular checker）
3. `control.placement.power-stage-hot-loop` — TI SLYT614/SNVA803 hot-loop 最小化量化規則（2mm² vs 20mm²、<500pH、one-via-per-amp、SW-node 最小化）→ 對位 G3 電源佈局深度（e2e 專利線缺）
4. `control.verify.kicad-dru-rule-language` — KiCad constraint 型別 + selector 語法（可移植規則介面）
5. merge → `control.placement.post-place-quality-checks`（+IPC-7352 courtyard 三級距離，增補既有擺後檢查的 courtyard 維度）

link 織網：
- `ipc-clearance-voltage` + `kicad-dru-rule-language` → `references`（數值×規則語言 = 可編譯 checker）
- `power-stage-hot-loop` → `references` 既有 `control.placement.post-place-quality-checks`（decap R1-R18 互補）
- `ipc-annular-tolerance-stack` → `references` 既有 `control.dfm.jlcpcb-ipc-thresholds`（annular 增補）
- 4 個新物件 `distilled_from` batch4 asset

UNVERIFIED 明確標註（不臆造）：trace-width/current 逐值、fillet 逐值、KiCad 逐項嚴重度、Pin Conflicts 矩陣 — 下批補。
