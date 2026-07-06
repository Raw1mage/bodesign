# BR_20260704 — 【總綱】bodesign 需核心能力翻轉：從「憑空生成」轉為「refs-derived 設計」，否則 C00~C04 無法正確且專業

- **類型**：epic / capability-inversion（總綱 BR，統攝本 session 全部分項 BR）
- **來源 session**：aiguard C00–C07 設計專案（scope=aiguard）
- **狀態**：**BLOCKING** — aiguard 專案暫停，等 bodesign 完成核心能力翻轉後回來
- **嚴重度**：critical — 非單點 bug，是 bodesign C00~C04 生成範式的根本缺陷

---

## 一句話結論

bodesign 目前的 C00~C04 是「**從薄空氣生成 artifact**」的範式——它假設物理決策、placement、腳位、元件清單都已由上游人工凍結，但**它自己既不提供產生這些決策的工具，也不強制設計必須回溯 owner 的權威 refs**。結果是 agent 被迫憑空發明，產出「看似完整、實則造假」的交付物。要支撐 C00~C04 的正確性與專業性，bodesign 必須翻轉為「**refs-derived 設計**」範式：先逆向拆解 owner 權威來源 → 建各層 SSOT → 下游只能消費、不能發明。

---

## 為什麼這是「能力翻轉」而非「補幾個工具」

本 session 燒掉數十輪，暴露的不是零星缺口，而是**同一個範式錯誤的多個切面**。逐一對應到已發的分項 BR：

### 切面 1：無 refs-first gate → 設計從 design root 旁路（範式核心）
- **證據**：aiguard 真實模組（N6_X01 說明文件 PDF + 正式需求書 PPTX）= 11 元件 / Stamp Hole X1(18)+X2(18)=36 pad dual-edge；agent 憑空發明版 = 8 元件（漏 WiFi/BT LBEE5KL1YN、Ethernet PHY RTL8211FI-CG、IMU LSM6DSMTR）/ 三面 28-pin。**座標、腳位數、元件清單全錯**。
- **分項 BR**：`BR_20260704_no_refs_decomposition_gate_design_root_bypass.md`
- **翻轉要求**：bodesign 必須有一個 **C00-refs 逆向拆解 gate**——進入任何下游生成前，強制把 owner 權威來源拆解、把各層擁有的資料 file 進該層 `01_refs/` SSOT；SSOT 不存在則下游 verb 拒絕執行（fail-fast，非 warn）。

### 切面 2：無 placement / castellated / stamp-module 工具 → C04 根本做不出真板
- **證據**：跨 52 landing verbs + 40 compute tools，**無任何** placement / component-move / castellated half-hole / stamp-module 生成 verb。C04 pipeline 假設 placement 已完成卻無工具產生它。
- **分項 BR**：`BR_20260704_no_component_placement_castellated_tool_c04_gap.md`
- **翻轉要求**：C04 需補「約束驅動的 placement 引擎」——消費 C01 ID face-layout（哪個邊、哪個面）+ C02 ME envelope/開孔約束，產生 placement；連接器面向/邊緣是**上游凍結的物理約束，非 C04 自由度**（「USB 插不進去」根因）。castellated / stamp module 需原生 verb，不靠 pcbnew 徒手腳本。

### 切面 3：pcbnew scripting 是地雷 → 徒手繞道必踩 segfault
- **證據**：`fp.Reference().SetTextSize()` 直接段錯誤；SwigPyObject 二次 cast；重複 `GetFootprints()` 快取退化。因無切面 2 的原生工具，被迫徒手 scripting，燒掉約 15 輪。
- **分項 BR**：`BR_20260704_pcbnew_scripting_segfault_hazards.md`
- **翻轉要求**：bodesign 需提供安全的 board-surgery wrapper（castellated PTH 半孔走 S-expression text-layer 注入），禁止把徒手 pcbnew scripting 當作 C04 的隱含路徑。

### 切面 4：lifecycle 方向性未被工具強制 → 下游發明上游未凍結的決策
- **證據**：C01/C02 的六面配置（USB-C=BOTTOM 密封朝下、microSD=LEFT、天線=RIGHT、OLED=FRONT、18650=BACK、Socket+按鈕=TOP）與 envelope，agent 從未消費就直接在 C04 發明。envelope 至今未收斂（C01 158×73×25 vs C02 grounded 145×75×26）。
- **翻轉要求**：lifecycle 有向性需工具化——下游 stage 的 verb 必須讀取上游凍結的約束 JSON（face-layout、envelope、mechanical-constraint）作為輸入，缺上游約束則拒絕生成。

### 切面 5：C00 DoD / 交付驗證的既有裂縫（放大範式錯誤）
- **分項 BR（20260703）**：`dod_status_json_location_silently_ignored_stage_scoped`、`c00_dod_rf_requirements_asymmetric_02build_path`、`compose_nc_emit_flaky_first_write`、`export_netlist_line_count_zero_misreport`、`workers_mode_infra_gaps_block_c04_realization`、`prd_bom_crosscheck_gap_cc_regulator_missing`。
- **共同性**：DoD 檢查與交付驗證只看表面存在性/state，不看是否**回溯真實 refs**，讓「憑空生成的假完整」得以通過 gate。

### 切面 6：工具介面摩擦（本 session 實測踩到，拖慢每一步）
- **證據**：`gate.py` landing verb 的 stdout 污染 JSON envelope；ragbase producer id 契約反直覺（source id 點分隔 vs 我傳連字號 → FK violation；extract id 從 path derive、共用 glob path → dup guard；references target 須 canonical id 非 `bodesign.` 投影版）；`ragbase_query` 結果結構 `data.tiers[].hits[]` 反直覺致我一度誤報 n=0。
- **分項 BR**：`BR_20260704_gate_py_landing_verb_stdout_pollutes_json_envelope.md`；ragbase id/結構摩擦已納入 `BR_20260704_kb_skill_exposure_window_not_knowledge_source.md` 硬證據。

### 切面 7：知識介面應暴露 skill 而非知識源本體（讓翻轉後的能力可被外部 agent 正確串接）
- **分項 BR**：`BR_20260704_kb_skill_exposure_window_not_knowledge_source.md`
- **與翻轉的關係**：翻轉後 bodesign 的新能力（refs-derived 設計紀律）必須透過 `<mcp>-kb` skill 暴露給客戶端工作 agent，而非要求它們直接懂 schema——否則正確能力也會因介面誤用而失效。

---

## 核心翻轉的驗收定義（bodesign 改好的判準）

翻轉完成 = 以下全部成立，才可讓 aiguard 回來繼續：

1. **refs-first gate 存在且強制**：無各層 `01_refs/` SSOT 時，下游生成 verb fail-fast 拒絕；SSOT 必須可追溯到 owner 權威來源（PDF/PPTX），非 agent 自撰。
2. **約束驅動 placement 引擎存在**：C04 能消費 C01 face-layout + C02 envelope 產生 placement；連接器綁定其面/邊，無法被 C04 任意移動。
3. **castellated / stamp-module 原生 verb 存在**：不需徒手 pcbnew scripting。
4. **lifecycle 方向性工具化**：下游 verb 以上游凍結約束 JSON 為必要輸入。
5. **DoD 檢查涵蓋 refs 回溯**：不再讓「憑空生成的假完整」通過 gate。
6. **工具介面摩擦修掉**：gate.py stdout 乾淨、ragbase id 契約直覺化或有明確 --help 契約、query 結果結構有穩定 accessor。
7.（延伸）**知識介面走 KB skill**：翻轉後能力透過 `bodesign-kb` skill 暴露。

---

## 影響範圍

- **bodesign**：C00~C04 生成範式重構（非單點修補）；新增 refs-decomposition gate、placement 引擎、castellated/stamp verb、lifecycle 約束鏈、安全 board-surgery wrapper；修 DoD gate 與工具介面摩擦。
- **aiguard 專案**：**暫停**。已完成且仍有效的資產：5 個各層 SSOT（C01 物理配置 / C02 envelope 開孔映射 / C03 元件與腳位 / C04 物理約束 / C05 韌體腳位），這些正是翻轉後 refs-first gate 應消費的輸入——翻轉時可拿它們當第一個真實驗收案例。
- **應丟棄**：place1~place5 五版憑空 placement（座標全非 refs-derived）。

## 驗證手段（翻轉後回歸）

以 aiguard 為第一個真實案例：從已建的 5 個 SSOT 出發，跑通「refs-first gate → 約束驅動 placement → castellated stamp module → C04 DRC/SI freeze」全鏈，且**全程無任何憑空發明的座標/腳位/元件**（每個數字可追溯到 SSOT，SSOT 可追溯到 N6_X01 PDF / 正式需求書 PPTX）。若仍需徒手 pcbnew scripting 或仍能繞過 refs gate，則翻轉未達標。

## 待處理的 aiguard 端 source gap（翻轉後一併解）

1. Ethernet 是否保留（N6_X01 有 RTL8211FI PHY + RJ45，但 aiguard face map 無網路埠面）。
2. Envelope 收斂：C01 158×73×25 vs C02 grounded 145×75×26。
3. V1 正式需求書 PPTX 仍未讀（docxmcp decompose cache 被回收，已另有 docxmcp BR）。

---

## 附：本 session 分項 BR 索引（本總綱統攝）

| 分項 BR | 對應切面 |
|---|---|
| no_refs_decomposition_gate_design_root_bypass | 1（範式核心） |
| no_component_placement_castellated_tool_c04_gap | 2 |
| pcbnew_scripting_segfault_hazards | 3 |
| gate_py_landing_verb_stdout_pollutes_json_envelope | 6 |
| kb_skill_exposure_window_not_knowledge_source | 6, 7 |
| (20260703) dod_status_json_location_silently_ignored_stage_scoped | 5 |
| (20260703) c00_dod_rf_requirements_asymmetric_02build_path | 5 |
| (20260703) compose_nc_emit_flaky_first_write | 5 |
| (20260703) export_netlist_line_count_zero_misreport | 5 |
| (20260703) workers_mode_infra_gaps_block_c04_realization | 2, 5 |
| (20260703) prd_bom_crosscheck_gap_cc_regulator_missing | 5 |
| (docxmcp repo) pptx_decompose_session_cache_reclaimed | source gap 3 |

---

## Resolution（2026-07-06 closed）

能力翻轉已完成，spec `specs/capability/refs-derived-design/`（living，950 tests green）。對照 7 條驗收準則：

1. **refs-first gate** ✅ `refs_gate.py`（`require_refs()` chokepoint、`REFS_SSOT_MISSING` typed fail-fast）+ `refs_ingest` landing verb。
2. **約束驅動 placement 引擎** ✅ `upstream_constraints.py` `solve_face_placement()`（DD-4 connector face 凍結、`CONNECTOR_FACE_CONFLICT`）+ `placement_to_coords` adapter → `net2pcb_board(placement=...)`，worker-side DRC roundtrip 實跑通過（`tests/test_worker_side_placement_roundtrip.py`）；另有 G3 確定性 preplacement（`preplace.py`，quality/deterministic-preplacement graduated，commit 100ada0）。
3. **castellated 原生 verb** ✅ `board_surgery.py` `build_castellation()`（S-expression 注入，segfault-free）+ `c04_castellation` landing verb。
4. **lifecycle 方向性工具化** ✅ `require_upstream_constraints()`（缺上游 JSON → `UPSTREAM_CONSTRAINT_MISSING`，全缺項一次列）。
5. **DoD refs 回溯** ✅ `dod_traceback.py` `dod_refs_traceback()`（untraceable + unfulfilled 任一非空 → blocking）+ 20260703 五筆 DoD/交付驗證 BR 已折入 P2 修畢（見 tasks.md §3）。
6. **介面摩擦** 部分✅：gate.py stdout 為 stale-mirror false-positive 已關（DD-7）；ragbase id 契約/query accessor 屬 specbase repo，已於該 repo 發 BR 追蹤（cross-repo）。
7. **KB skill** ✅ `skills/bodesign-kb/SKILL.md`（refs-derived client 契約）。

**殘留（consumer-side，非本 repo）**：aiguard 5 SSOT 實檔端到端回歸由 aiguard 端解鎖後執行（本 repo 驗收已以 TV-1~TV-6 + roundtrip 測試覆蓋）。
