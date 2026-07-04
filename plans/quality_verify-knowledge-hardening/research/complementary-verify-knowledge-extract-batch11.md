# 互補源 verify 知識萃取 batch11（DFT/panelization + conformal coating/機構介面）

> 目的：換新域——補知識庫全缺的 **製造/組裝可檢測性與拼板**（family R）與 **環境防護/板邊機構 keepout**（family S）維度。
> - family R：IPC-7351B courtyard + JLCPCB V-cut/mouse-bite/fiducial 官方（支線 A ses_0d4a438ef，已 read_subsession 核對）
> - family S：IPC-HDBK-830 全文 + IPC-2221A 全文 + 廠商 coating guide（支線 B ses_0d4a3f2d3，已 read_subsession 核對）
>
> 天條守則：每數值附逐字來源引文+文件編號+章節；查無來源標 UNVERIFIED，不臆造。皆廠商官方/IPC 標準原文級 pdftotext 解碼真值，無記憶臆造。

---

## 家族 R：DFT / panelization / assembly courtyard（廠商官方 + IPC 標準原文級）

### R1. panelization — V-cut（JLCPCB 官方原文級）

| 規則 | 量化值 |
|---|---|
| V-cut 角度 | 25°（雙面對稱） |
| V-cut 殘厚（web） | ≈1/3 板厚（比例式，非固定 mm） |
| **V-cut 到銅/trace/pad clearance** | ≥0.4mm 自中心線（建議 ≥1.0mm、高元件 ≥2.0mm） |
| 連接邊最小寬 | 3mm（板厚 ≤0.8mm 時 5mm） |
| panel 尺寸 | min 70×70mm；max 475×475mm |
| 板厚限制 | 0.4mm 不支援 V-cut |
| 尺寸公差 | ±0.4mm |
| process edge（tab）寬 | 3–5mm |

### R2. panelization — mouse-bite / tab（JLCPCB 官方原文級）

| 規則 | 量化值 |
|---|---|
| mouse-bite hole 直徑 | 0.60mm |
| holes per set | 5–8（不建議 <5） |
| hole 邊緣間距 | 建議 0.4mm，min 0.3mm |
| panel gap（板間距） | 1.6–2mm，min 1.2mm（V-cut 為零間距） |

### R3. fiducial（JLCPCB 官方原文級）

| 規則 | 量化值 |
|---|---|
| fiducial copper 直徑 | 1.0mm（典型） |
| solder mask 開口 | 2.0mm |
| keep-out（無銅）半徑 | ≥ pad 半徑；keep-out zone 半徑 3.0mm |
| 每板最少+位置 | ≥2 global fiducial/板，對角放置 |
| fiducial 到板邊 | ≥5mm |
| **fiducial 中心到板邊（SMT rail）** | ≥3.85mm |

### R4. assembly courtyard（IPC-7351B 標準原文級）

| 規則 | 量化值 |
|---|---|
| courtyard 定義 | 提供最小電氣+機械 clearance 的最小矩形區 |
| **courtyard excess（依 density level）** | Most(L)=0.5mm / Nominal(N)=0.25mm / Least(M/S)=0.1mm |
| 大間距族 courtyard excess | 部分族 0.2/0.8/1.5mm |

來源錨點：`mfg://jlcpcb-panel`（廠商官方）+ `mfg://ipc-7351b`（標準原文）。

UNVERIFIED（family R，不臆造）：testpoint/DFT probe pitch/min 直徑/密度、stencil area-ratio ≥0.66（IPC-7525 抓取失敗）、tooling hole 直徑位置、mouse-bite 到元件 keepout 距離。

---

## 家族 S：conformal coating / board-edge 機構 keepout（IPC 標準原文級）

### S1. conformal coating 厚度（IPC-HDBK-830 §8.4.1 原文級）

| 規則 | 量化值 |
|---|---|
| coating 厚度範圍（全型別） | 12.5µm [0.49mil] ~ 200µm [7.9mil] |
| 典型端產品厚度 | 0.01mm ~ 0.2mm [0.394~8.27mil]（原文 OCR 誤植 6.01，依 0.394mil 校正為 0.01mm） |
| 厚度非線性 | 0.2mm 非 0.1mm 兩倍保護；過厚 CTE mismatch/cracking |
| 溶劑型固化收縮 | 50% 溶劑 @濕膜 0.2mm → 乾膜 ≈0.1mm |
| 最薄處保證 | 非 parylene 型須提高平均厚度以保證最薄處（solder joint/lead）達標 |
| parylene 均勻性 | 僅 parylene（真空沉積）可全 PCA 均勻 |
| 型別代號 | AR=Acrylic / SR=Silicone / UR=Polyurethane / ER=Epoxy / XY=Parylene |
| 合格參照 | 生產組件參照 J-STD-001/IPC-2221；coupon 參照 IPC-CC-830 |

### S2. coating keep-out / masking（IPC-HDBK-830 §7 原文級）

| 規則 | 量化值/準則 |
|---|---|
| keep-out 元件清單 | connector/test point/可變元件/接地點/socket 接點不上漆 |
| 敏感 keep-out 區 mask pattern 最小寬 | 3.175mm [125 mil] |
| edge connector | 須 mask |
| connector/via 背面 | 會滲漏 coating，須注意 |

### S3. board edge / 元件 keepout / 擺放 grid（IPC-2221A §8.1 原文級）

| 規則 | 量化值 |
|---|---|
| **元件到板邊最小距離** | 1.5mm [0.0591in]（含 board guide/mounting hardware） |
| land 最小尺寸 | ≥0.6mm [0.024in] |
| standoff/foot clearance | ≈0.75mm [0.0295in] |
| 元件擺放主 grid | 0.5mm [0.020in]（優先） |
| 元件擺放細 grid | 0.05mm [0.00197in] |
| 英制 grid 備選 | 2.54→1.27→0.64mm |
| 元件可維修性 | land 不得被他件遮蔽，須可不拆他件而移除 |
| test fixture edge clearance | conductor 距板邊須留 fixture clearance |

### S4. coating 型別厚度（廠商/二手交叉，佐證 IPC）

| coating 型別 | 典型乾膜厚度 | 出處 |
|---|---|---|
| acrylic/urethane/silicone 通用 | 25–75µm 乾膜 | HumiSeal/Chase |
| silicone（廠商實務） | 50–210µm | Nemco |
| acrylic（廠商實務） | 30–130µm | Nemco |
| IPC-A-610 通用範圍 | 25–127µm | andwinpcb |

來源錨點：`env://ipc-hdbk-830`（標準原文）+ `mech://ipc-2221a`（標準原文）+ `env://coating-vendor`（廠商交叉）。

UNVERIFIED（family S，不臆造）：mounting hole 對 M2/M2.5/M3 孔徑逐值（螺絲廠 datasheet 給定）、mounting hole 到板邊/washer keepout、connector 到板邊/mating keepout/mezzanine stack height、potting keepout/排氣/熱膨脹、高電流 connector 每腳載流+pad、TIM/gap filler/heatsink mounting 厚度、各 coating 型別 IPC-CC-830 分別標準厚度（範圍 verified，各型別分別值需查 CC-830 原文）。

---

## 蒸餾計畫

batch11 產出 **4 個新 control 物件**（repo scope，confidence=verified，source_weight=7）：

1. `control.mfg.panelization-geometry` ← family R1-R3：V-cut 25°/clearance ≥0.4mm(建議1.0/高元件2.0)/連接邊≥3mm/panel 70~475mm + mouse-bite 0.6mm/5-8holes/gap 1.6-2mm + fiducial 1.0mm/mask 2.0mm/keepout 3.0mm/中心到邊 3.85mm — JLCPCB 官方
2. `control.mfg.assembly-courtyard` ← family R4：IPC-7351B courtyard excess 0.1/0.25/0.5mm 依 density level — IPC 標準原文
3. `control.env.conformal-coating-thickness` ← family S1-S2：coating 12.5–200µm/典型 0.01–0.2mm/溶劑收縮半厚/parylene 唯一均勻 + keep-out(connector/test point 不上漆、敏感區 mask 3.175mm) — IPC-HDBK-830 原文
4. `control.mech.board-edge-keepout` ← family S3：元件到板邊 ≥1.5mm + land ≥0.6mm + standoff 0.75mm + 擺放 grid 0.5/0.05mm — IPC-2221A 原文

link 織網：
- `mfg.panelization-geometry` → `references` `control.verify.kicad-dru-rule-language`（clearance/keepout 落 DRU）
- `mfg.panelization-geometry` → `references` `control.mech.board-edge-keepout`（同 assembly keepout 域）
- `mfg.assembly-courtyard` → `references` `control.dfm.ipc-annular-tolerance-stack`（IPC 系列同源）
- `mfg.assembly-courtyard` → `references` `control.mfg.panelization-geometry`（同製造/組裝域）
- `env.conformal-coating-thickness` → `references` `control.mech.board-edge-keepout`（coating keep-out 與板邊 keepout 同 assembly-geometry 域）
- `env.conformal-coating-thickness` → `references` `control.dfm.ipc-trace-width-current`（coating 為 DFM 環境延伸）
- `mech.board-edge-keepout` → `references` `control.verify.kicad-dru-rule-language`（1.5mm edge keepout 落 DRU）
- `mech.board-edge-keepout` → `references` `control.dfm.ipc-annular-tolerance-stack`（land 0.6mm 與 annular 互補）
- 4 物件 `distilled_from` batch11 asset
