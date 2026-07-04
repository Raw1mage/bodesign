# 互補源 verify 知識萃取 batch5（補 batch4 UNVERIFIED：IPC-2152 trace/current · IPC-7351 fillet · KiCad source 嚴重度）

> 目的：補齊 batch4 掛帳的 4 個 UNVERIFIED 缺口。
> - **IPC-2152 trace-width vs current**（二手轉述，含 master 公式 + 修正因子）
> - **IPC-7351 fillet Jt/Jh/Js**（archive.org 全文 PDF 經 pdftotext 解碼＝原文條款級）
> - **KiCad source 逐項預設嚴重度 + Pin Conflicts 12×12 矩陣**（GitHub 官方 GPL 鏡像 master，逐字附檔案:行號）
>
> 天條守則：每個數值附來源錨點；查無來源標 UNVERIFIED，不憑記憶填。IPC-7351 走原文 PDF（條款級）；IPC-2152 走二手（原文付費，明標二手）；KiCad GPL 可引用 source 片段。

---

## 家族 D：IPC-2152 trace width vs current（補 batch4 A4 UNVERIFIED）

### D1. trace-width vs current 逐值（20°C rise）

| Current | 1oz 外層(mil) | 1oz 內層(mil) | 2oz 外層(mil) |
|---|---|---|---|
| 1A | 10 | 12 | 5 |
| 2A | 30 | 35 | 15 |
| 3A | 50 | 60 | 25 |
| 5A | 100 | 120 | 50 |
| 10A | 250 | 300 | 125 |
| 15A | 450 | 550 | 225 |

**master 公式**：`A(mil²) = k₁ × I^k₂`；20°C rise 外層 k₁≈0.0647, k₂≈1.378。
**銅厚→寬換算**：`width(mil) = A(mil²) / thickness`；0.5oz=0.7mil / 1oz=1.4 / 2oz=2.8 / 3oz=4.2mil。
**via 電流容量（20°C，Area=π×D×T）**：8mil=0.7A / 10mil=0.9A / 12mil=1.1A / 20mil=1.8A。

**修正因子（IPC-2152 革新，可寫成 current-aware checker）**：
- 內外層：IPC-2152 內層≈外層（**非** IPC-2221 舊式「內層減半」假設；舊圖是把外層值直接對半）。
- 板厚修正：1.0mm=1.08 / 1.6mm=1.00(baseline) / 2.4mm=0.96 / 3.2mm=0.92。
- 銅平面鄰近：相鄰層大平面 0.65–0.80（散熱助益）。
- 平行走線：<1inch 間距需合併電流計算（互熱），IPC-2152 數據假設 >1inch。

來源錨點：`ipc://2152/quick-ref`（二手轉述 pcbsync.com/ipc-2152，IPC-2152 原文付費）。

### D2. IPC-2221 舊式 k 係數 — 仍 UNVERIFIED
`I = k × ΔT^0.44 × A^0.725` 的 k=0.048(external)/0.024(internal)：常見流傳值但無原文/可信二手佐證，續標 UNVERIFIED，不臆造。

---

## 家族 E：IPC-7351 fillet goal Jt/Jh/Js（補 batch4 A2 fillet UNVERIFIED，原文條款級）

archive.org IPC-7351 全文 PDF（85頁）經 curl+pdftotext 解碼。單位 mm，Level C=最小/B=中位/A=最大。

| 元件族（表號） | Toe Jt (C/B/A) | Heel Jh (C/B/A) | Side Js (C/B/A) | Courtyard excess (C/B/A) |
|---|---|---|---|---|
| Chip 矩形 ≥1608(0603) (Table 3-5) | 0.15/0.35/0.55 | −0.05/−0.05/−0.05 | −0.05/0.00/0.05 | 0.1/0.25/0.5 |
| Bottom-only terminations (Table 3-8) | 0.15/0.35/0.55 | 0.25/0.35/0.45 | 0.01/0.03/0.08 | 0.1/0.25/0.5 |
| Leadless Chip Carrier (Table 3-9) | 0.20/0.30/0.40 | 0.00/0.00/0.00 | −0.04/−0.04/−0.04 | 0.1/0.25/0.5 |
| Gullwing SOIC/QFP (heel goal, Smin≤Amax) | 0.2/0.4/0.6 | 0.05/0.15/0.25 | 0.01/0.05/0.1 | 0.4/0.25/0.5 |
| 大型 gullwing (Toe 0.6 級) | 0.6/0.8/1.0 | 0.6/0.8/1.0 | 0.1/0.2/0.3 | 0.2/0.8/1.5 |
| Flat Lug Leads (Table 3-12) | 0.15/0.35/0.55 | 0.25/0.35/0.45 | −0.04/0.01/0.05 | (未逐字) |
| Inward Flat Ribbon/鉭電容 (Table 3-11) | 0.2/-/0.8 | 0.07/0.15/0.25 | −0.10/−0.05/0.01 | 0.1/0.25/0.5 |

**定義（原文逐字）**：Jt=solder fillet/land protrusion at toe（超出 lead 外側）；Jh=at heel（超出 internal lead）；Js=at side（lead 兩側）。

**land pattern 計算公式（原文）**：
- Zmax(land 外緣) = Lmin − 2Jt + √(C_L² + F² + P²) 形式。
- Xmax(land 寬) = Wmin + 2Js + √(...) + F + P。
- 三組公差：component tolerance(C) + fabrication(F) + placement(P)，statistical RSS 合成。

**特例（原文）**：gullwing heel goal 三級（C=0.05/B=0.15/A=0.25mm）不適用 lead 端子公差 T1 > 0.5mm 的元件；LCC 為維持 0.20mm 到 thermal tab 淨空需 heel trim −0.2mm（無 thermal tab 時 heel 可增至 0.50mm）。

來源錨點：`ipc://7351/tables-3-5..3-14`（archive.org IPC-7351 eng_text.pdf, 原文條款）。

UNVERIFIED：BGA 球狀專節 fillet 表未命中逐字；部分 OCR 雜訊欄位（如 0.2/-/0.8 中欄）標「未逐字」不臆補。

---

## 家族 F：KiCad source 逐項預設嚴重度 + Pin Conflicts 矩陣（補 batch4 C4 UNVERIFIED，GPL source 逐字）

來源基準：`KiCad/kicad-source-mirror @ master`（GitHub 官方 GPL v3 鏡像）。**機制：三 map 預設全 `RPT_SEVERITY_ERROR`，僅明列項降級為 WARNING/IGNORE**。

### F1. DRC 預設嚴重度（`pcbnew/board_design_settings.cpp:166-211`）

未明列者 = **ERROR**（`for(...) m_DRCSeverities[errorCode] = RPT_SEVERITY_ERROR`）。明列降級（關鍵）：

- **WARNING**：DRILLED_HOLES_COLOCATED, DRILLED_HOLES_TOO_CLOSE, DANGLING_TRACK, DANGLING_VIA, COPPER_SLIVER, ISOLATED_COPPER, PADSTACK, MISSING_FOOTPRINT, DUPLICATE_FOOTPRINT, EXTRA_FOOTPRINT, NET_CONFLICT, SCHEMATIC_PARITY, SILK_CLEARANCE, SILK_MASK_CLEARANCE, SILK_EDGE_CLEARANCE, TEXT_HEIGHT, TEXT_THICKNESS, LIB_FOOTPRINT_ISSUES/MISMATCH, CONNECTION_WIDTH, MIRRORED/NONMIRRORED_TEXT, MISSING_TUNING_PROFILE 等。
- **IGNORE**：MISSING_COURTYARD, FOOTPRINT_FILTERS, FOOTPRINT_TYPE_MISMATCH, TUNING_PROFILE_IMPLICIT_RULES, TRACK_NOT_CENTERED_ON_VIA。
- **ERROR（繼承預設）**：clearance, hole_clearance, hole_to_hole, track_width, annular_width, via_diameter, hole_size, PTH/NPTH_IN_COURTYARD（明列 ERROR）, edge_clearance, shorting_items, unconnected_items。

判斷重點：**MISSING_COURTYARD 預設 IGNORE**（bodesign 若要求 courtyard 完整性須主動升級）；短路/未連接/間距/環寬等安全關鍵 = ERROR。

### F2. ERC 預設嚴重度（`eeschema/erc/erc_settings.cpp:94-128`）

未明列者 = **ERROR**。明列降級（關鍵）：

- **WARNING**：ENDPOINT_OFF_GRID, PIN_TO_PIN_WARNING, SIMILAR_LABELS/POWER, GROUND_PIN_NOT_GROUND, LABEL_SINGLE_PIN, DRIVER_CONFLICT（多重 net 名）, BUS_ENTRY_CONFLICT, LIB_SYMBOL_ISSUES/MISMATCH, NOCONNECT_CONNECTED（NC 旗標卻有連接）, NOCONNECT_NOT_CONNECTED（懸空 NC）, MISSING_INPUT_PIN, MISSING_BIDI_PIN, LABEL_MULTIPLE_WIRES, UNCONNECTED_WIRE_ENDPOINT 等。
- **IGNORE**：SINGLE_GLOBAL_LABEL, FOOTPRINT_FILTERS, SIMULATION_MODEL, FOUR_WAY_JUNCTION。
- **ERROR（繼承預設）**：PIN_TO_PIN_ERROR, PIN_NOT_DRIVEN（input 未被 output 驅動）, POWERPIN_NOT_DRIVEN（power_in 未被 power_out 驅動）, DUPLICATE_PIN_ERROR, BUS_ALIAS/BUS_TO_BUS/BUS_TO_NET_CONFLICT, DUPLICATE_SHEET_NAME, UNANNOTATED, DUPLICATE_REFERENCE, BUS_ENTRY_NEEDED, WIRE_DANGLING。

**對位 bodesign classify_erc_report（batch1 checker）**：KiCad 對 NOCONNECT_CONNECTED / NOCONNECT_NOT_CONNECTED 預設只給 WARNING、對 POWERPIN_NOT_DRIVEN 給 ERROR——正好印證 bodesign no-connect 三分類（刻意 NC 抑制、真衝突升 error）的 severity 分級方向。

### F3. Pin Conflicts 12×12 矩陣（`eeschema/erc/erc_settings.cpp:43-57`，`m_defaultPinMap`）

行=驅動 pin，列=被連 pin。OK / WAR(warning) / ERR(error)。pin type 順序：I=Input, O=Output, Bi=Bidirectional, 3S=Tri-state, Pas=Passive, NIC=Free, UnS=Unspecified, PwrI=Power-in, PwrO=Power-out, OC=Open-collector, OE=Open-emitter, NC=No-connect。

| 驅動＼被連 | I | O | Bi | 3S | Pas | NIC | UnS | PwrI | PwrO | OC | OE | NC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| I | OK | OK | OK | OK | OK | OK | WAR | OK | OK | OK | OK | ERR |
| O | OK | ERR | OK | WAR | OK | OK | WAR | OK | ERR | ERR | ERR | ERR |
| Bi | OK | OK | OK | OK | OK | OK | WAR | OK | WAR | OK | WAR | ERR |
| 3S | OK | WAR | OK | OK | OK | OK | WAR | WAR | ERR | WAR | WAR | ERR |
| Pas | OK | OK | OK | OK | OK | OK | WAR | OK | OK | OK | OK | ERR |
| NIC | OK | OK | OK | OK | OK | OK | OK | OK | OK | OK | OK | ERR |
| UnS | WAR | WAR | WAR | WAR | WAR | OK | WAR | WAR | WAR | WAR | WAR | ERR |
| PwrI | OK | OK | OK | WAR | OK | OK | WAR | OK | OK | OK | OK | ERR |
| PwrO | OK | ERR | WAR | ERR | OK | OK | WAR | OK | ERR | ERR | ERR | ERR |
| OC | OK | ERR | OK | WAR | OK | OK | WAR | OK | ERR | OK | OK | ERR |
| OE | OK | ERR | WAR | WAR | OK | OK | WAR | OK | ERR | OK | OK | ERR |
| NC | ERR | ERR | ERR | ERR | ERR | ERR | ERR | ERR | ERR | ERR | ERR | ERR |

**判斷規則（可直接寫成 pin-net-ssot checker 的裁決表）**：
- **NC 列/行全 ERR**：任何 pin 連到 no-connect = 一律 error（對位 bodesign no-connect 分類的「刻意 NC 不應有連接」）。
- **Output↔Output / Output↔PowerOut / PowerOut↔PowerOut = ERR**：雙驅動衝突（真短路的電氣根因）。
- **Output/PowerOut → OC/OE = ERR**：open-collector/emitter 不可被推挽驅動。
- **Unspecified 幾乎全 WAR**：未指定 pin type 一律警告（強制 pin type 標註的動機）。
- **Passive/Input/NIC 對多數 = OK**。

來源錨點：`kicad://source/master/erc_settings,board_design_settings`（GPL v3）。

UNVERIFIED：master vs 9.0.9 tag 未逐項 diff（極少差異可能）；DRC check 名稱↔settings key 完整 610 行對照未逐一抽（severity map 已足）。

---

## 蒸餾計畫（補 batch4 UNVERIFIED）

batch5 產出 **3 個新知識物件**（互補源，repo scope）：

1. `control.dfm.ipc-trace-width-current` — IPC-2152 trace-width/current 逐值 + master 公式 + 修正因子（補 batch4 A4，current-aware trace-width checker 數值層）
2. `control.dfm.ipc-fillet-land-pattern` — IPC-7351 各 family Jt/Jh/Js 三級 + Zmax/Xmax 公式（補 batch4 A2 fillet，原文條款級，density-aware footprint 驗證）
3. `control.verify.kicad-default-severities` — KiCad DRC/ERC 預設嚴重度 map + Pin Conflicts 12×12 矩陣（補 batch4 C4，可移植裁決表 + 印證 no-connect 三分類）

link 織網：
- `ipc-trace-width-current` → `references` 既有 `control.dfm.jlcpcb-ipc-thresholds`（DFM 數值增補）
- `ipc-fillet-land-pattern` → `references` 既有 `control.placement.post-place-quality-checks`（courtyard/footprint 增補）
- `kicad-default-severities` → `references` 既有 `control.verify.kicad-dru-rule-language`（同 KiCad 規則體系，語法+嚴重度互補）
- `kicad-default-severities` → `references` 既有 `concept.no-connect-classification`（severity 分級印證三分類）
- 3 個新物件 `distilled_from` batch5 asset

剩餘 UNVERIFIED（不臆造）：IPC-2221 舊式 k=0.048/0.024、IPC-2152 其他 ΔT(10/30°C) k 係數、BGA fillet 專節、KiCad master↔9.0.9 tag diff。
