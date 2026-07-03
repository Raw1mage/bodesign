# 專利線徵集：PCB 擺件 / decap / EMC 可執行規則（18 條）

來源：patentmcp gpatents 檢索 + TIPO GPSS batch claims（8/8 成功），2026-07-03。
用途：bodesign G3 缺口（確定性 pre-placement 指導工具）的規則基底。
註：公開工程知識萃取，非 FTO 分析；US5648913A / US5781446A / US6346743B1 / US6706974B2 均 NOT_ACTIVE。

## High actionability（可直接寫成確定性檢查/生成規則）

| # | Rule | Source |
|---|---|---|
| R1 | 去耦電容→IC 電源腳路徑阻抗必須低於主電源平面→該腳的路徑阻抗（proxy：距離+過孔數） | US7929315B2 claim 1 (Canon) |
| R2 | 背面對置式去耦：bypass cap 置於 IC 電源腳正下方板背面，經專用 via 直連（星形饋電，via 不直接進電源層） | US7679930B2 claim 1 (Canon) |
| R3 | 每顆去耦電容需有緊鄰其焊盤的專屬 ground via | US7679930B2 claim 1 |
| R4 | decap 擺放順序：footprint 由大到小，依序放最近可用位置（大電容先佔位） | US9582628B1 claim 1 (Altera) |
| R5 | PDN 目標阻抗驅動 decap 選型：Z_PDN(f) > Z_target 則增補對應諧振頻率電容（公式化，無需場求解器） | US9582628B1 claim 1 |
| R6 | force-directed 擺件二段法：連線引力+元件斥力算連續佈局→legalize 到格點；I/O 元件以內部結果為條件再排 | US10460062B2 claim 1 (Fraunhofer) |
| R7 | 多 via 並聯降電容安裝電感（via 對數是可數檢查項） | US6346743B1 claim 1 (Intel) |
| R8 | decap 有效範圍 = die shadow：中頻去耦須落在 IC 投影內才計入有效 | US20090140400A1 (DuPont) |

## Medium（需參數校準）

| # | Rule | Source |
|---|---|---|
| R9 | bus 元件插入 alignment net 拉直線、按偏好方向給走線權重 | US9251306B2 claim 1 (GlobalFoundries) |
| R10 | 頻率驅動優先序：高頻 net 元件優先擺、優先佈 | US5648913A claim 1 (Xilinx) |
| R11 | 禁止走線跨平面分割；不可避免時跨越點加 stitching cap / 阻尼材料 | US6706974B2 (Intel) |
| R12 | 抑制 PDN 反諧振：混值配置/加阻尼，不能只堆同值電容 | US20070279880A1 (Samtec) |
| R13 | 元件↔電容連線長度最小化為嵌入式/表貼電容第一目標函數 | US8698278B2 (NGK) |
| R14 | 設計期 EMI 迭代閉環：模型推導 EMI→與容許值比對→不過改 decap/電源網再迭代 | US20150234972A1 (NEC), US7831949B2 (Panasonic) |

## Low（方向性）

| # | Rule | Source |
|---|---|---|
| R15 | clock 輸出電路加屏蔽罩＋罩內電源 trap filter | US8660434B2 claim 1 (Oclaro) |
| R16 | 穩壓器貼近負載，縮短大電流迴路 | US7919840B2 (IBM) |
| R17 | PMIC 電感緊鄰對應 power port | US20240387345A1 (Qualcomm) |
| R18 | 多約束域各自產生 violation-free 解再交集 | US5781446A |

## 落地建議

- R2/R3/R7 → decap 擺放生成器的生成規則；R1/R8 → 擺後檢查；R4/R5 → 選型+排序演算法。
- R6 與現有 draftsman force-directed placement 同構，可延伸到 PCB 擺件。

## 檢索限制（friction）

1. gpatents 語義檢索雜訊高：crystal 佈局規則 0 有效命中，需 app note 類文獻補。
2. PCB 專屬擺件演算法專利稀少，多為 IC/FPGA 域移植（標 medium）。
3. switching converter hot-loop 量化規則未在 claim 層出現，建議 TI/ADI app note 補強。
