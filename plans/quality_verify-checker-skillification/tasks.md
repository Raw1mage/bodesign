# Tasks: quality_verify-checker-skillification

> 組織原則（design.md DD-7）：以「parser/IR 解鎖批次」而非「57 checker 流水帳」。
> 本 plan 到 designed 為止只做設計；implementing 階段才寫 code。M0 是本 plan 範圍。

## M0 — 設計收斂（本 plan，到 designed）

- [x] M0-1 探勘既有 verify 骨架（5 trust layers / ValidationEvidence / ORACLE_TOOLS / gate.py / classify_erc_report 範本）
- [x] M0-2 撈 57 control + 對照 design-ir 實際 schema 做三層分類（`control-classification.md`）
- [x] M0-3 proposal.md 方法設計（DD-1~DD-7）
- [x] M0-4 design.md + IDEF0 + GRAFCET（drawmiat-canonical）
- [x] M0-5 修正試點選擇（實測推翻初稿）+ DD-7 瓶頸洞察
- [x] M0-6 IDEF0/GRAFCET 經 drawmiat validate → advance designed
- [x] M0-7 使用者確認方法方向後 advance planned（含 handoff.md）

## M1 — 試點驗證（implementing，三條路徑各一）

- [x] M1-1 `kicad-default-severities`：延伸既有 `classify_erc_report`，示範「control→擴充既有 checker」
- [x] M1-2 `decoupling-pdn-strategy`：全新 IR-native checker（讀 placement x/y + Net.connected_pads），示範 DD-2 control-grounded evidence + DD-3 threshold block 完整路徑
- [x] M1-3 `board-edge-keepout`：T-B stub + backlog 掛帳，示範「不硬編假欄位、暴露 parser gap」的紀律
- [x] M1-4 建 verify-checker registry（DD-4）+ 三試點註冊進 ORACLE_TOOLS
- [x] M1-5 threshold block 解析層（DD-3）+ control checker_binding metadata schema

## M2 — parser 解鎖批次（implementing，槓桿優先）

- [x] M2-1 copper-spacing/clearance parser → `si.spacing-via-return-path` landed T-A；`ipc-clearance-voltage`/`safety.creepage-clearance`/`safety.functional-spacing-formula`/`mech.mounting-hole-clearance` 誕實 T-B 掛帳（IR 無 edge-to-edge/creepage 欄）
- [x] M2-2 board-outline parser（port skills analyze_pcb 幾何進 core，純 python 無 pcbnew）→ 退休 M1-3 stub、`board-edge-keepout` landed；`mounting-hole-clearance`/`flex.*` 可複用同 parser（後續掛帳）
- [x] M2-3 placement 拓樸分析 → `esd.tvs-placement-routing` landed T-A；7 個 placement control T-B 掛帳（需 net 語義分類/IR 無欄）
- [x] M2-4 vault datasheet 值比對 → `fuse-ptc-derating`/`mov-surge-selection`/`ntc-inrush-selection` 全 landed T-A（caller-supplied inputs；vault auto-lookup API 缺失為 upstream gap）

## M3 — advisory 注入（implementing）

- [x] M3-1 17 個定性 verified control → G2 ReviewScenario 結構化提示（DD-5，`checkers/advisory.py` `build_advisory_scenarios`；meta/天條 deny-list 排除、registered 去重、empty conclusion 不自我核可）
- [x] M3-2 partial/todo control 一律不 advisory 注入（confidence!=verified 過濾），待升 verified 才重分類；registry guard_tier 同步擋 partial→T-A

## M4 — 收尾

- [x] M4-1 registry 全量狀態面板：`build_pilot_registry().summary()` = total 19 / landed 8 / stub 11 / T-A 7 / T-B 12；advisory 17（`build_advisory_scenarios`）
- [x] M4-2 `specs/architecture.md` Verification Baseline 章節同步技能化架構
- [x] M4-3 event_record 收尾 + 驗證證據（58 tests green）

## T-B Backlog — 12 stub 盡職查核（2026-07-04，使用者選「維持 backlog」）

> 結論：在「純真 IR-native、不推上游、不 caller-supplied」嚴格前提下，剩 12 個 T-B stub 的
> 可新 land 集實際為空——皆按 DD-1 定義卡在 design IR 結構讀不到門檻量。逐 body 實證核對（非臆測）。
> 兩筆上游工是唯一真正解鎖路徑，各自應獨立立 plan：

- [!] **`Net.role` IR 擴充 plan**（中）→ 解鎖 6-7 個：`ddr.ddr3-flyby-routing` / `protection.tvs-esd-layout` /
  `protection.reverse-polarity-layout` / `placement.power-stage-hot-loop` / `power.charger-ic-layout` /
  `power.current-sense-layout` / `power.high-current-via-ground` / `rf.transmission-line-ground`。
  卡點：design IR `Net` 無 role 欄，分不出 power/ground/RF/high-current；net 名 heuristic 猜 role 踩
  no-fabrication 天條。正解＝加 `Net.role` 由 schematic net-class 明確供給（datasheet-grounded）。
- [!] **copper-geometry parser plan**（大）→ 解鎖 3-4 個：`ipc-clearance-voltage` / `safety.creepage-clearance` /
  `safety.functional-spacing-formula` / `rf.antenna-keepout`（天線下 no-ground 區）。
  卡點：需 edge-to-edge 銅距 / plane 幾何；gerber-core 僅 summary 級、`BoardObject.geometry` 為 opaque dict，
  無 copper polygon/track 解析。等同新蓋 gerber/copper 幾何 parser。
- [!] **需設計意圖（caller-supplied，使用者已否決此捷徑）**：`mech.mounting-hole-clearance`
  （body 明標 UNVERIFIED：hole→板邊/銅 keepout mm；drill Ø vs ISO273 可驗但「哪孔配哪號螺絲」屬設計意圖 IR 無欄）、
  `flex.bend-area-geometry` / `flex.transition-keepout` / `env.conformal-coating-thickness`（製程參數 IR 無欄）、
  `mfg.*` / `test.ict-testpoint-geometry` / `dfm.ipc-*`（需 courtyard/aperture/annular 幾何深解析）。
