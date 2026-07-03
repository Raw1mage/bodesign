# BR: workers 模式三缺口阻擋 C04 realization 全鏈（experiments 未掛載 / 映像過舊 / export_netlist line_count:0）

- Date: 2026-07-03
- Session: opencode `ses_0db8f20d1ffe9Jyjzd1sFEb1Go`（quality/prd-bom-crosscheck L3 E2E 重做）
- Severity: Medium（阻 C04 realization 驗證；設計層已 gate PASS，非設計缺陷）

## 現象（含硬證據）

L3 把 E2E LED driver 案 C03 重設計為 NPN linear current sink，crosscheck gate host 端實跑 PASS（current-regulator `substituted in_envelope` matched [Q1-Q4]）。但 C04 全鏈（ERC/DRC/Gerber）重跑被三個既有基礎設施缺口阻擋：

1. **workers 模式無 experiments bind mount**：`docker inspect` 確認執行中 workers compose 僅掛載 vault/sessions/run，無 `./experiments:/work/experiments`（該掛載僅 `docker-compose.dev.yml` 有，`docker-compose.workers.yml` 無）→ compose/emit 產物落容器 overlay 上層、host 不可見。
2. **執行影像過舊**：`/health` 回 44 tools，L1 本輪註冊的 `bodesign_prd_bom_crosscheck` → `unknown tool`（映像未含 L1 變更；dev bind-mount 掛 packages/services 但工具 schema 註冊在映像建置時固定）。
3. **export_netlist line_count:0**：同一 `.kicad_sch` 下 `export_bom` 讀得 11 comp、`export_netlist` 卻回 0 行——netlist emitter 缺口（與 L3 用的 host 端 spec→net 導出是兩條路徑）。

## RCA

- (1)(2) 同源：workers compose 未涵蓋 dev 開發迴圈所需的 experiments 掛載，且工具 schema 註冊在映像建置期固定，bind-mount 原始碼不會讓新工具進 `/health` 清單——需 `BODESIGN_DEV=1 mcpctl rebuild`。AGENTS.md §3 已載明 dev loop 需 rebuild 才生效工具層變更。
- (3) 獨立缺口：`export_netlist` 對某些 schematic 回 line_count:0 但 export_bom 正常，指向 netlist emitter 對特定拓撲（NPN sink 多支路）的解析缺口，需另查。

## 建議修復

1. **experiments 掛載**：`docker-compose.workers.yml` 為 core/ee/me 補 `./experiments:/work/experiments`（對齊 dev compose），讓 workers 模式也能驅動 experiments 產物 host 可見。
2. **映像重建**：`BODESIGN_DEV=1 ./mcpctl.sh rebuild`（含 L1 gate 工具註冊 + 三 Dockerfile 的 openjdk/atopile 補丁）後 C04 全鏈可跑。
3. **export_netlist 缺口**：獨立追查 emitter 對 NPN sink 拓撲回 0 行的成因（比對 export_bom 讀取路徑）。

## 影響範圍

- 所有 workers 模式下需 host 可見 experiments 產物的 E2E 流程。
- quality/prd-bom-crosscheck L3 task 3.3（C04 重跑）解阻依賴 (1)(2)。

## 驗證手段

- rebuild 後 `/health` 回 ≥45 tools（含 prd_bom_crosscheck）。
- workers 模式 compose_schematic → host `experiments/` 直接可見產物。
- NPN sink schematic export_netlist line_count > 0。
- C04 全鏈：ERC clean → route → DRC copper=0/unconnected=0 → Gerber。
