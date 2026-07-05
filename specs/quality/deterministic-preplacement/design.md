# Design: quality_deterministic-preplacement

## Context

E2E 實證（`specs/validation/prd-to-gerber-e2e/`）量測到 G3 缺口：`net2pcb_board` 的 placement 段在呼叫端未給 `placement` 時退化為 8mm 天真網格（`routing.py:130-133`），零電氣感知——C1(100nF) decap 距 LED 負載群 >30mm（違 R1/R8）、M3 安裝孔撞 USB-C courtyard。知識徵集已收斂確定性路線：arXiv 2602.23540（component-centric placement 去 RL 化）+ 專利規則 R1-R18（`specs/validation/prd-to-gerber-e2e/research/`）。HANDOVER_20260705 指出此案同時對應 aiguard EPIC 準則 2（constraint-driven placement engine）。

## IDEF0 skeleton mapping

架構掛在 idef0.json 的五個活動骨架上：A1（幾何/netlist 抽取，pcbnew adapter，`routing.py`）→ A2（錨定+pin 歸屬分群，DD-7）→ A3（環帶格點貪婪初擺，R4）→ A4（固定 seed SA 微調，DD-4/DD-8）→ A5（R1/R8 擺後檢查，DD-5/DD-6）。A2~A5 全在純核心 `preplace.py`（DD-1）；A1 是唯一 pcbnew 邊界。grafcet.json 的 step 0-5 對應同一鏈的 runtime 行為（step 5 = 擺件寫回 board 續走 net2pcb pipeline）。

## Goals / Non-Goals

**Goals**

- 純 Python 確定性 pre-placement：主 IC 錨定 → pin 歸屬先驗分群 → 環帶格點貪婪初擺 → 固定 seed SA 微調。
- 生成規則注入（R4 擺件相關子集，帶專利錨點）；擺後檢查 R1/R8 輸出可解釋違反清單。
- `route_net2pcb` 增加 `strategy: grid|deterministic`（grid 保留為對照基線，非 fallback）。
- LED driver 案（16 零件 10 net）基線對比：decap 距離、courtyard 重疊、HPWL。

**Non-Goals**

- RL/ML 擺件、autorouter 更換、PDN checker 自研、length_match 升級（皆另案）。
- 商用 EDA 級品質；目標是「電氣感知 ≥ 明顯優於 grid、違反可解釋」。
- 互動式手動擺件 UI。

## Decisions

- DD-1: **Pure-core / adapter 分離** — 演算法核心（`preplace.py`）純 Python、零 pcbnew 依賴，輸入為 `{ref: PartGeom}` + nets + 規則參數，輸出 `{ref: (x, y, rot)}` + 違反清單；pcbnew 只負責 footprint 幾何抽取與落板（沿用 `resolve_connector_pads` 的 pure+wrapper 模式）。使 host 端 unittest 可完整驗證確定性，不需 EE worker。
- DD-2: **自研 minimal core；KiCad-Autoplace 判 REJECT-vendor（spike 結論，2026-07-05）** — spike 實查四個候選 repo：唯一實質命中 DTU-EKB/KiCad-Autoplace（MIT、pure-Python engine 與 pcbnew 分離、`electrical.py decoupling_pairs()` 有 decap→power-pin 先驗、文件宣稱 hashseed-independent 確定性、`anneal.py` SA）。判 REJECT-vendor 理由：(1) repo 極年輕（0 stars、單一組織、v0.5.0 發布兩天前），無第三方使用實績，vendor 進送廠關鍵路徑等於為 129 commits 的未背書行為全額擔保，違反「展示可靠度而非宣稱」哲學；(2) 本案需求子集小（<100 零件、R1/R8 專利錨點檢查器該 repo 沒有），自研核心可 100% 測試覆蓋；(3) 其架構（pure engine + kicad_io bridge、multiseed 確定性）與 DD-1/DD-4/DD-7 同構，證明路線可行，引為參考實作（reference: github.com/DTU-EKB/KiCad-Autoplace @ v0.5.0）。未來若需多 seed 候選盤或 route-driven refinement，重開 ADAPT 評估。
- DD-3: **`strategy` 顯式參數** — `net2pcb_board(strategy="grid"|"deterministic")`，預設 `grid`（保持既有行為，變更需呼叫端顯式選擇；grid 是對照基線而非 fallback）。`deterministic` 路徑缺 footprint 幾何時 fail fast 並列缺項，不靜默退回 grid。
- DD-4: **確定性契約** — 唯一隨機源為 `random.Random(seed)`，`seed` 顯式參數（預設 42、回傳結果 echo 生效值）；同輸入同輸出是驗收條件（unit test 跑兩次結果相等）。
- DD-5: **規則值必帶來源錨點** — 規則表落盤 `placement_rules.py`，每條規則含 `source`（專利號/文獻 id）與 `value` + `unit`；無錨點規則不硬編碼。採用子集：R1（decap→電源 pin ≤3.0mm，US7929315B2 claim 1 proxy + pcb-optimize 閾值）、R4（decap 大到小排序先佔位，US9582628B1 claim 1）、R8（mid-freq decap 落 IC 投影/courtyard 擴張帶內，US20090140400A1）、R16（穩壓器貼近負載，US7919840B2，引力權重）。R2/R3/R7（背面對置/專屬 ground via/多 via）涉 via 生成屬佈線段，不在本模組生成範圍。
- DD-6: **R8 die-shadow proxy** — 無 die 幾何資料，以 IC courtyard bbox 外擴 `die_shadow_margin_mm`（預設 1.0，可覆寫）作為有效帶；100nF 級以下歸為 mid-freq 受檢。
- DD-7: **錨定與分群先驗** — 主 IC＝pad 數最多者（tie-break：refdes 字典序，確定性）；pin 歸屬：decap（C 且值 ≤1µF）→ 所屬電源 net 上最近 IC 電源 pin；crystal 負載 C → crystal pin；上拉/串阻 → 訊號 pin；連接器/安裝孔 → 板緣帶（外環）。歸屬不明者入自由層，僅受 HPWL 引力。
- DD-8: **SA 能量函數** — `E = HPWL + w_aff·Σ(affinity 距離超額) + w_ovl·Σ(AABB 重疊面積) + w_edge·Σ(板外/板緣違反)`；權重顯式可覆寫、結果 echo 生效值。移動集合：單件平移（格點）、90° 旋轉、同類互換。

## Risks / Trade-offs

- SA 參數對不同板型需調參 — mitigation: 範圍限定小板（<100 零件），權重 echo + 基線對比量化；多板型泛化明確 OUT。
- footprint courtyard 幾何在純核心不可得 — mitigation: adapter 從 pcbnew 抽 bbox+pad 座標傳入純核心；缺幾何 fail fast 列缺項（DD-3）。
- 貪婪+SA 可能仍劣於人工 — mitigation: 驗收標準是「明顯優於 grid 基線」且違反清單可解釋，非絕對品質。

## Critical Files

- `packages/eda-bridge/bodesign_eda_bridge/preplace.py` — 新增：純核心（PartGeom/錨定/分群/貪婪/SA/檢查器）。
- `packages/eda-bridge/bodesign_eda_bridge/placement_rules.py` — 新增：帶錨點規則表。
- `packages/eda-bridge/bodesign_eda_bridge/routing.py` — `net2pcb_board` 加 `strategy` 參數 + 幾何抽取 adapter。
- `packages/eda-bridge/bodesign_eda_bridge/__init__.py` — export。
- `services/mcp/server.py` — `bodesign_route_net2pcb` schema 補 `strategy`/`seed` 參數。
- `tests/test_preplace.py` — 新增：確定性、分群、規則檢查、基線對比 unit tests。

## Code Anchors

- `packages/eda-bridge/bodesign_eda_bridge/routing.py:130` — grid fallback 段（改造點）
- `packages/eda-bridge/bodesign_eda_bridge/routing.py:79` — `net2pcb_board` 簽名
- `packages/eda-bridge/bodesign_eda_bridge/composer.py:281` — 既有確定性 FR placement（schematic 域，模式參照）
