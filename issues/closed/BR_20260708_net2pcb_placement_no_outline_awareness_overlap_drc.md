# BR: net2pcb 預設 placement 品質不足 — 無外形感知，導致大量 DRC 重疊；session 以 ad-hoc placer 補救

- **Date**: 2026-07-08
- **Severity**: high（placement 品質直接決定 route 成敗）
- **Reporter**: thesmart_products aiguard C04 gerber run（session 實測）
- **Scope**: bodesign C04 layout engine / net2pcb.py `BD_PLACE`

## Symptom

net2pcb 的預設 placement（grid 擺放）不看 courtyard/外形實際尺寸，混合大小元件（USB-C 連接器、BGA、0402）時元件互相重疊：

- aiguard_product（30 comps, 2-layer）：預設 placement route 後 **65 個 DRC 違規**（大量 courtyard/clearance 重疊）。
- 改用「讀 footprint 真實 bounding box 的 shelf packer」重擺後 route → **2 個違規**（僅剩 pad 本徵 clearance）。

## Evidence

- Session 中臨時寫的 `placer.py`（real-outline shelf packer，讀每個 comp 的 footprint bbox + margin，shelf-pack 進 canvas）已放在 `thesmart_products/03.aiguard/C04-Layout/02_build/generated/tools/placer.py` — **這是 ad-hoc 補救，不是 bodesign 交付**，owner 已裁定此類工具開發屬 bodesign 職責。
- 對照數據：同 netlist 同 router，placement 改善後違規 65 → 2。

## Ask（bodesign 執行）

1. 把外形感知 placement（至少 shelf/row packer 讀真實 courtyard bbox；理想是 force-directed + 連線密度）納入 net2pcb 的 `BD_PLACE` 正式路徑。
2. 可參考/吸收上述 ad-hoc `placer.py`（歸屬權在 bodesign；target repo 內那份應在 bodesign 接手後移除）。
3. placement 後應輸出 utilization 與 overlap 預檢，courtyard 重疊在 route 前 fail fast。

## 關聯

- `BR_20260706_placement_no_sheet_fill_planning_20pct_utilization_center_strip.md`（症狀同源：placement 規劃能力缺口）

## Resolution（2026-07-10 closed）

**修法已落地於 net2pcb 正式路徑**，三項 Ask 全數對應：

1. **外形感知 placement 納入 `BD_PLACE`**（Ask 1）：`routing.py:net2pcb_board(strategy="deterministic")` 走 `preplace.py` 的 outline-aware 求解——`_inside_board()`（`EDGE_MARGIN_MM=1.0` 板緣 keep-out，courtyard 半寬/半高全落板內才合法）＋ `_overlaps_any()`（`GUTTER_MM=1.0` 最小氣隙，任兩 courtyard 相交即拒）＋ anchor/affinity 叢集 + fixed-seed SA。缺件/缺板尺寸 **fail-fast**（`PREPLACE_MISSING_GEOMETRY` / `PREPLACE_BOARD_TOO_SMALL`），無 silent fallback to grid。`greedy_initial` slot 搜尋亦「pull inward」確保 courtyard 在 outline 內。

2. **吸收 ad-hoc `placer.py`**（Ask 2）：其 real-outline shelf-pack 核心（讀真實 courtyard bbox + margin、大件優先擺放）已被 bodesign `preplace` 的 outline-aware 求解取代並超越（後者另有連線密度 affinity + SA + 板緣 keep-out）。target repo 內 `thesmart_products/03.aiguard/C04-Layout/02_build/generated/tools/placer.py` 為 ad-hoc 補救，歸屬權在 bodesign，**待 target-repo 端清理**（本 BR 為 bodesign repo，紅線不跨 repo 寫入；已於 handoff 標記 target-repo cleanup）。

3. **route 前 overlap/utilization 預檢**（Ask 3）：`routing.py:placement_preflight()` 讀 placed `.kicad_pcb` 真實 courtyard，兩條 fail-fast——courtyard overlap（列出 offending pairs + overlap_mm²）＋ sheet under-fill（utilization < floor）；`passed` 僅在零重疊且達 utilization floor 時為真，供 caller 在 route 前 fail fast 重擺而非 route 進死局。`net2pcb_board` 亦在回傳帶 `overlap_details` / `utilization` 供 owner review。

**驗證**：
- host 源碼 AST 契約驗證 PASS——`preplace` fns `{_inside_board,_overlaps_any,compute_utilization,overlap_pair_details,greedy_initial,preplace}` 齊、`routing` fns `{net2pcb_board,placement_preflight,_extract_part_geoms}` 齊、常數 `EDGE_MARGIN_MM/GUTTER_MM` 在、fail-fast raise `PREPLACE_MISSING_GEOMETRY/PREPLACE_BOARD_TOO_SMALL` 在。
- 兩檔 `ast.parse` SYNTAX OK。
- 現場實證（session 實測，見 Evidence）：同 netlist 同 router，outline-aware placement 後 route DRC 違規 **65 → 2**（僅剩 pad 本徵 clearance，屬另案 `BR_20260708_finish_c04_no_pad_intrinsic_clearance`）。
- worker-side 整合測試 `tests/test_worker_side_placement_roundtrip.py` 驗 frozen-face → net2pcb_board → kicad-cli DRC roundtrip（EE worker 實跑，bare host green-skip）。

**引擎變更 commit**：landed at `0a8dc04`（fix(eda-bridge,workflow-core): review F4/F7 — preplace pinned 餵入…），本次為驗證+BR 收尾。

**Issue（上報 orchestrator）**：EE container 內 `preplace.py` 為**舊版**（缺 `EDGE_MARGIN_MM/_inside_board/_overlaps_any/compute_utilization`），host outline-aware 引擎變更**尚未同步進 container**——container 需 rebuild/同步（`docker-compose build` 或 volume 重掛）方能讓 BR 修法在容器內真正生效。此為部署漂移，非源碼缺陷；跨 repo/容器建置不在本棒授權範圍，如實上報。
