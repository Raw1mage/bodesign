# arXiv 線徵集：PCB 擺件 / 佈線 / PDN 演算法（12 篇）

來源：arXiv API 檢索（abstract 級評估），2026-07-03。
評估軸：確定性可實作（bodesign 天條：驗證比對不用 LLM）× 小板（<100 零件）適用性。

## A. 擺件

| arXiv id | 方法 | 確定性 | 小板適用 |
|---|---|---|---|
| **2602.23540** Component Centric Placement (DRL) | 主 IC 錨定中心，被動元件依所屬 pin 先驗離散化搜索空間；DQN/AC/SA 三法比較，9 塊真實 PCB 驗證 | **High**（去 RL 化：離散化+先驗+固定 seed SA） | **High** |
| 1312.4587 FFTPL (ePlace) | 靜電場類比解析式擺件，FFT 解 Poisson | High（DREAMPlace 開源） | Medium（VLSI 級） |
| 2510.21547 AccFFT+ePlace-MS | FFT 加速 5.78x | High | Medium |
| 2303.03964 t-FDP | t 分佈短程力 force-directed，FFT 加速 | High（可升級現有 composer force-directed 力模型） | High |
| 2002.06998 RapidLayout | 演化演算法 FPGA hard-block 擺件 | Medium | Low-Medium |
| 2605.10547 PhysEDA | 曼哈頓距離指數衰減電氣先驗注入 attention/reward | Low（code 未釋出）；先驗本身可萃取 | 知識可用 |

## B. 佈線

| arXiv id | 方法 | 確定性 | 小板適用 |
|---|---|---|---|
| 1906.08809 DRL Global Routing | DQN vs sequential A* baseline＋benchmark 生成器 | RL=Low；A* baseline=High | High（已有 freerouting） |
| **2407.19195** Obstacle-Aware Length-Matching | 兩階段（區域指派→蛇形補償），MSDTW 差分對，任意方向 | **High**（純幾何，無 ML） | High——`length_match_bus` 升級直接對位 |
| 1705.04984 ILP Meander Alleviation | 蛇形過密→crosstalk speedup；ILP 重分佈間距 | High | Medium |
| 2412.21035 ML Net Ordering | 佈線順序 ML 評分 | ML=Low；啟發式基線可確定性實作 | 知識可用（freerouting pass 順序） |

## C. PDN / 去耦

| arXiv id | 方法 | 確定性 | 小板適用 |
|---|---|---|---|
| **2305.01540** Capacitor Optimization (DesignCon) | 頻域目標阻抗＋worst-case 時域評分選 decap 組合 | **High**（純數值） | High |
| 2106.10693 Fast PDN Impedance (DNN) | BEM＋DNN 代理 | DNN=Low；BEM/腔體模型=Medium-High | Medium（lumped 模型即夠） |

背景情報：2605.30345 SchGen——LLM 生成原理圖的語義化 code 表示，印證 compose/ato 雙路徑哲學。

## 前 3 名自研 MVP

1. **Component-centric 確定性 pre-placement**（2602.23540 去 RL 化）：netlist+footprint 尺寸 → 主 IC 錨定 → 被動元件 pin 歸屬（decap→電源 pin、crystal 負載 C→crystal pin、上拉→訊號 pin）→ 環帶格點貪婪指派 → 固定 seed SA 精修（HPWL+歸屬距離懲罰+不重疊）。輸出 `{ref:(x,y,rot)}` 直餵 `route_net2pcb` placement 參數。
2. **目標阻抗法 decap 選擇器**（2305.01540＋2106.10693 lumped 簡化）：ESL/ESR+安裝電感 lumped 模型（vault L4 datasheet 值），貪婪/窮舉選組合滿足目標阻抗；輸出每 rail 電容值/數量/擺放距離上限。
3. **蛇形段品質後處理**（2407.19195＋1705.04984）：`length_match_bus` 蛇形生成強制 ≥3W 間距＋均勻分佈，消除自耦合 speedup 隱性缺陷。改造成本最低。

## 限制（friction）

- arXiv 對 PCB 專屬擺件/佈線覆蓋薄（主流在 DAC/ICCAD/TCAD 付費牆）。
- 近 5 年主流 RL/Transformer 與確定性天條衝突；可萃取的是先驗與 reward 設計。
- 僅 abstract 級；落地前需對 2602.23540 §method 與 2407.19195 §region-assignment 做 PDF 精讀。
- DevFormer (2205.13225) 有 repo，pretrained 權重可用性待 GitHub 線確認。
