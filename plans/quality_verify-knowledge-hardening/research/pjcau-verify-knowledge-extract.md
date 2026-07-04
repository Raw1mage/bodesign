# pjcau PCB verify 知識萃取（8 域驗證判斷）

> 來源：`pjcau/esp32-emu-turbo` `.claude/skills/`（mcpmarket `pcb-design-auditor` 真身），2026-07-03 爬取。
> 法律邊界：本檔為**知識萃取重寫**，非複製。萃取對象限縮為公開製造能力數值（IPC / JLCPCB published capabilities）
> 與方法論分類；用自己的話重寫、標來源錨點。pjcau repo 無 LICENSE（保留所有權利），其 project-specific
> `verify_*.py` code、硬編路徑、寫死零件均**不**搬入。
> 天條對齊：以下數值為「參考閾值 + 來源」，checker 消費時須標 `source`/`as_of` 且可覆寫（廠商 profile），非寫死預設。

## 1. 8 域驗證分類法（方法論骨架）

資深硬體工程師 review 一塊板時，逐域判斷「對錯」。pjcau 的 `pcb-review` 把它系統化為可打分的 8 域：

| # | 域 | 判斷什麼（設計對錯） | bodesign 對位 |
|---|---|---|---|
| D1 | Power Integrity | power trace 寬度足夠載流、decap 就近、bulk cap 每 rail、GND via 夠 | G3 擺後 / C06 |
| D2 | Signal Integrity | 阻抗控制、差分對匹配、crosstalk 間距、走線角度 | C05/C06 |
| D3 | Thermal | 功率 IC 的 thermal via、銅平衡、散熱路徑 | C04/C06 |
| D4 | EMI/EMC | 回流路徑完整、平面分割不跨越、stitching、天線 keepout | C06 analyze_emc |
| D5 | DFM（可製造性） | trace/via/hole/pad/mask/silk/edge 符合廠商能力 | C04 DRC gate |
| D6 | Mechanical | 板邊間距、連接器/孔位、機構配合 | C02/C04 |
| D7 | 電氣功能 review | 會不會開機、上電時序、strapping pin、power sequencing | C06（bodesign 缺） |
| D8 | datasheet 一致性 | 每個 pad 的 net 是否對得上 datasheet pin 定義 | G4 / vault L4 |

**判斷紀律**（可萃取的方法論，非 code）：
- 每域給 verdict：`OK / CONCERN / RISK`（或扣分制）；不是二元 pass/fail，而是分級。
- 驗證要**逐項可追溯到來源**（datasheet page / 標準號 / 製造能力）——這正是 bodesign datasheet-grounded 天條。
- DFM/DRC（製造規則）與電氣功能（會不會動）是**兩個獨立層**，不可互相替代。pjcau 特別立 `electrical-review` 補「DFM 過了但板子開不了機」的缺口。

## 2. no-connect 分類法（對位 bodesign T1 缺口）

pjcau `drc-audit` 的核心洞見：DRC 報的 short/unconnected **不都是真問題**，要分類：

| 現象 | 描述特徵 | 分類 | 處置 |
|---|---|---|---|
| `nets XXX and YYY`（兩個實 net 相碰） | 兩不同 net 短路 | **REAL SHORT** | CRITICAL，板會故障 |
| `nets XXX and )`（第二 net 空） | pad 無 net、trace 碰到 | **pad-net assignment bug** | 生成器 bug，修 pad 初始化 |
| pad 刻意不接（datasheet 標 NC / power-only 介面） | 意圖性斷開 | **intentional no-connect** | 需 spec 顯式宣告，非 error |

**對位 bodesign T1**：power-only USB-C 的 D+/D-/SBU 刻意 NC，但 bodesign `compose_schematic` 無法宣告 → ERC 永殘留 6 errors。正解 = spec 加 `no_connect` 宣告，checker 據此把「刻意 NC」從 error 降為 INFO，只對「應接卻斷」與「real short」報 fail。這是 checker 判斷力的核心：**分辨意圖 vs 缺陷**。

## 3. pin→net single-source-of-truth 驗證模式（對位 G4 / vault L4）

pjcau `datasheet-verify` 的模式：`datasheet_specs.py` 是 pin→net 的唯一真相來源，每個零件宣告：
- reference designator + 零件號
- datasheet 檔名 + 頁碼參照（證據錨點）
- 逐 pin 期望 net（exact / any-of / unconnected）
- pin 功能描述、要求的 pad type、最小 drill

驗證腳本逐 pad 比對「實際 net」vs「datasheet 期望 net」，輸出 PASS/FAIL/WARN/INFO。

**對位 bodesign**：這正是 vault L4（`spice_model` / datasheet-grounded specs）該長的樣子——bodesign 已有 vault L4 EAV + evidence-gated trust，但**缺 pin→net 逐腳驗證 checker**。G4 冷啟動（`AL5809-060` 查無）的下一步，就是這種「datasheet pin 定義 → 期望 net → 對比實際佈線」的確定性 checker。輸出四碼：
- `PASS`：pad net 正確
- `FAIL`：pad net 錯 / 該接卻斷
- `WARN`：net 對但 pad type / drill 錯
- `INFO`：刻意不接（spec 有記載）

## 4. JLCPCB / IPC 製造規則數值（公開製造能力，checker 閾值源）

以下為公開製造能力參考值（source: JLCPCB published capabilities / IPC-7525 stencil / IPC-2222 drill）。checker 消費須標 `source` + `as_of`，可被廠商 profile 覆寫。

### 4.1 Trace 寬/間距（1oz Cu）
| 參數 | 最小 | 建議 |
|---|---|---|
| trace 寬（2 層 1oz） | 0.127mm (5mil) | ≥0.15mm |
| trace 間距（diff net） | 0.127mm (5mil) | ≥0.15mm |
| trace 寬（4 層 1oz/0.5oz） | 0.1mm (4mil) | — |

### 4.2 載流寬度（1oz Cu, 10°C rise, external）
| 電流 | 外層最小寬 | 內層最小寬 |
|---|---|---|
| 0.5A | 0.127mm | 0.254mm |
| 1.0A | 0.254mm | 0.508mm |
| 2.0A | 0.762mm | 1.27mm |
| 3.0A | 1.27mm | 2.16mm |

### 4.3 Via
| 參數 | 2 層最小 | 4+ 層最小 | 建議 |
|---|---|---|---|
| via drill (PTH) | 0.3mm | 0.2mm | ≥0.3mm |
| via 外徑 | 0.6mm | 0.45mm | ≥0.6mm |
| annular ring | 0.15mm | 0.15mm | ≥0.2mm |
| via-to-via（孔邊） | 0.254mm | 0.127mm | ≥0.3mm |
| 最大縱橫比（drill:厚度） | 10:1 | 10:1 | — |
| via 塞孔限制 | 距 pad <0.35mm 不可塞 | — | — |

### 4.4 Hole / Pad（source: IPC-2222 drill-to-pad）
| 參數 | 值 |
|---|---|
| PTH drill 最小 | 0.15mm（建議 ≥0.3mm） |
| NPTH drill 最小 | 0.5mm（建議 ≥0.8mm） |
| 孔徑規則 | > pin 最大尺寸 + 0.1mm；0.05mm 倍數 |
| NPTH-to-copper 間距 | ≥2.0mm |
| pad 間距（diff net） | ≥0.127mm |
| pad-to-edge | ≥0.25mm（建議 0.3mm） |

### 4.5 Soldermask / Silk
| 參數 | 值 |
|---|---|
| mask bridge（pad 間） | ≥0.1mm（<0.075mm JLCPCB 自動移除） |
| mask expansion（每側） | 0.05mm |
| silk 線寬 | ≥0.15mm |
| silk 字高 | ≥0.8mm（建議 1.0mm） |
| silk-to-pad 間距 | ≥0.15mm |
| silk on pad | 禁止（廠自動裁切） |

### 4.6 Stencil aperture（source: IPC-7525）
- 面積比（area ratio）+ 縱橫比（aspect ratio）門檻依 stencil 厚度（3-5mil）；細間距零件需 area ratio 檢查決定錫膏釋放。

### 4.7 Board
| 參數 | 值 |
|---|---|
| copper-to-edge | ≥0.2mm（建議 0.3mm） |
| 板厚 | 0.6–2.0mm（1.6mm 標準） |
| 縱橫比（板長:厚） | ≤4:1（防翹曲） |

## 5. 擺後品質檢查規則（對位 G3 擺後檢查，非生成）

pjcau `pcb-optimize` 的擺後檢查（bodesign G3 只有天真網格 → 需要這些檢查發現問題）：

| 模組 | 檢查 | 閾值（參考） | 對應 bodesign 專利規則 |
|---|---|---|---|
| decap 距離 | 100nF 到每個 IC VDD pin | ≤3mm | R1/R8（die shadow） |
| thermal via | 功率 IC 附近 GND via | ≥2-3 個，5mm 內 | R3/R7 |
| copper balance | F.Cu vs B.Cu 分布 | 差異 >50% 警告翹曲 | — |
| via 數 | 每 net via 數 | >4 過多 | R7（多 via 降感抗，但過多有反效果） |
| parallel trace | data 訊號 crosstalk | 間距 <3× trace 寬 | 3W 規則 |
| bulk cap | 每 power rail | ≥10µF | R5（PDN 目標阻抗） |

**與 bodesign 既有 decap R1-R18 concept 互補**：R1-R18（來自 e2e 徵集）是**生成規則**（decap 該放哪）；pjcau 這組是**擺後檢查閾值**（放完了對不對）。兩者對位：R1↔decap 距離、R3/R7↔thermal via、R8↔die shadow 有效範圍。

## 6. 電氣功能 review（bodesign C06 最大缺口，方法論可萃取）

pjcau `electrical-review` 的 30 題檢查骨架，補「DFM 過了但板子開不了機」——分四階段：
- **Pre-Power**：power rail 隔離無短路、電源開關位置、CC pull-down（USB-C 5.1k to GND）、反接保護。
- **Power-Up 時序**：boost 啟動、LDO dropout 餘裕（Vin-Vout > dropout）、EN pin RC 延遲（3τ < 取樣窗）。
- **Boot strapping**：MCU boot pin 上下電平（GPIO0 HIGH 正常開機 / download mode）、VDD_SPI 電平。
- **Runtime**：電流餘裕（總峰值 < LDO 額定）、各匯流排完整。

**萃取為方法論**：這是一組「上電能不能動」的確定性檢查清單，可對 bodesign 任何板套用（不限 ESP32）——每題對應一個可從 `.kicad_sch` + datasheet 推出的判斷。bodesign C06 目前只有 DRC/crosscheck/SPICE，缺這層「功能性 sanity」。列為 8 域 checker 增量的高價值方向。
