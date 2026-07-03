# GitHub 線徵集：擺件 / 佈線 / PDN OSS 候選（13 項判定）

來源：GitHub Search API 實查（stars/push/license 為 2026-07-03 查核值）。

| # | Repo | Stars/活躍 | License | 領域 | 判定 |
|---|---|---|---|---|---|
| 1 | freerouting/freerouting | 1,774★ 極活躍 | GPL-3 | 佈線 | **已引入**（ee worker jar 1.9.0 subprocess 隔離） |
| 2 | DTU-EKB/KiCad-Autoplace | 0★ 2026-06 新 | **MIT** | connectivity-aware 擺件+freerouting refine | **引入候選（首選）** |
| 3 | remiblokker/CadMust-Neo | 20★ | MIT | KiCad SA 擺件 | 觀察（自研 SA placer 參考實作） |
| 4 | bbenchoff/OrthoRoute | 363★ | MIT | GPU Manhattan lattice 佈線 | 排除：僅巨型背板、需 CUDA 數十 GB VRAM |
| 5 | limbo018/DREAMPlace | 1,023★ | BSD-3 | IC analytical placement | 排除引入/保留知識：LEF/DEF 輸入、建置重、無 pcbnew 接口 |
| 6 | LukeVassallo/RL_PCB | 60★ 2024 停 | MIT | RL 擺件 | 排除：需訓練、非確定性，違天條；reward 設計入知識庫 |
| 7 | adamws/kicad-kbplacer | 522★ 極活躍 | GPL-3 | 鍵盤矩陣擺件 | 排除：領域特化；pcbnew 批次擺件管線是成熟參考碼 |
| 8 | mikwielgus/topola | 17★ | 未標示 | 拓撲 rubberband 佈線 | 觀察：Rust 早期、license 不明 |
| 9 | tscircuit/tscircuit-autorouter | 67★ 極活躍 | MIT | A* 佈線 (TS) | 觀察：freerouting 備援；circuit-json 接口成本中高 |
| 10 | vygr/C-PCB / Python-PCB | 82★/24★ 停更 | GPL-2 | 佈線 | 排除：無維護 |
| 11 | CGrassin/kicad-auto-silkscreen | 34★ | MIT | 絲印擺位 | 觀察（低優先，C04 finishing 加分項） |
| 12 | mentasystems/fragua | 2★ 新 | MIT | AI-native PCB 全流程 (Rust) | 觀察（競品追蹤） |
| 13 | PDN/decap checker 類 | — | — | — | **無可用 OSS → 需自研**（規則源=專利/論文線） |

## 前 3 名整合路徑

1. **KiCad-Autoplace（MIT）**：engine core pure-Python 無 pcbnew 依賴（multi-seed SA＋connectivity-aware＋鎖定件/邊緣 connector 約束），headless `cli.py place/preflight/metrics`＋無 pcbnew pytest。整合：ee worker subprocess 或 vendor core 進 eda-bridge。固定 seed 即確定性。風險：0★ 大學專案、目標 KiCad 10（ee 是 KiCad 9，kicad_io 橋接層需相容驗證）。建議 1 天 spike 用 E2E LED driver 板實測 vs 現有 grid。
2. **PDN/decap checker 自研**：OSS 空白。確定性 checker 照 `analyze_emc` 模式（.kicad_sch+.kicad_pcb → severity-bucketed findings），落 ee worker，規則帶專利/論文來源錨點。
3. **tscircuit-autorouter（MIT）**：唯一 license 乾淨且活躍的第二佈線引擎候選；等 freerouting 失敗率實測數據再評估。

## 限制（friction）

- websearch/codesearch 不在 subagent 工具池，改用 GitHub Search API webfetch（無 topic 標籤 repo 覆蓋可能不全）。
- topola license 未查 Codeberg 主站；DREAMPlace 判定基於 repo 文件未實際建置。
