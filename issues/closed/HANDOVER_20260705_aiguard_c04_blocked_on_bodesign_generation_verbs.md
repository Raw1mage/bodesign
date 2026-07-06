# HANDOVER → bodesign agent — 讀我，然後排 plan

- **類型**：agent-to-agent handover / backlog 觸發
- **發起端**：aiguard 消費端 session（thesmart_products/03.aiguard）
- **日期**：2026-07-05
- **給誰**：下一個在 bodesign repo 開工的 agent
- **一句話**：aiguard 的文件層（C00/C01/C02/C03/C05/C06/C07）已 **100% 對齊權威需求（deck v3）、零臆造、gate 全綠**，唯一卡點是 **C04-Layout**——它 blocked 在 bodesign **尚未落地的兩個生成 verb**。這四份 BR 已躺在 `issues/` 但沒被消費。請讀完本檔，把它們排進 plan。

---

## 0. 為什麼發這份 HANDOVER（而不是只留 BR）

上一輪確認：bodesign 端今天很活躍，但方向全在**另一條線**（verify-checker 技能化、copper-clearance checker、IPC 標準地圖、測試債 921 green），**完全沒碰** C04 placement 生成 / castellated / c01-c02 emitter 這三塊。BR 是被動文件，agent 沒主動掃 `issues/` 就不會排進 plan。這份 HANDOVER 是主動觸發：**請把下面的閱讀順序當成 backlog 起手。**

---

## 1. 先讀這四份 BR（依此順序）

| # | 檔案 | 角色 |
|---|---|---|
| 1 | `BR_20260704_EPIC_capability_inversion_refs_derived_design.md` | **總綱**——7 條驗收準則 = 「bodesign 改好了」的定義 |
| 2 | `BR_20260704_no_component_placement_castellated_tool_c04_gap.md` | **缺口**——精確到缺哪兩個 verb（`place_components` + `emit_castellated`）|
| 3 | `BR_20260704_aiguard_c04_consumer_input_contract_and_acceptance_case.md` | **輸入合約 + 驗收案例**——aiguard 能餵的精確 JSON 形狀 + 端到端測法 |
| 4 | `BR_20260704_c01_c02_emitter_modular_platform_template_not_refs_derived.md` | **前提修正**——emitter 預設吐「5 埠 modular-platform 骨架」，placement 引擎要能正確運作，得先修這個 |

---

## 2. 缺口收斂到「兩個生成 verb」（硬證據）

`gate.py --list` 目前 **52 landing + 40 compute verb**，C04 只有：
- `c04_readiness`（審查）
- `c04_emit_layout_package`（打包既有約束）
- 40 個 compute verb **全在 placement 之後**（route / pour / length-match / DRC）

**明確缺的兩個：**

1. **`place_components`（約束驅動 placement 生成）**
   - C03→C04 之間工作量最大的中間步。
   - `build_c04.sh → net2pcb.py` pipeline **明文假設板上已有 placement**，但既無 GUI、也無 headless verb 去**產生**它。
   - 這是 EPIC 準則 2（constraint-driven placement engine），目前仍 `proposed`（plan `quality_deterministic-preplacement`）。

2. **`emit_castellated`（郵票半孔陣列）**
   - 三件式核心板的板緣半孔接腳，目前只能徒手 pcbnew（踩 SwigPyObject segfault，見 `BR_20260704_pcbnew_scripting_segfault_hazards.md`）。
   - 這是**製程特徵、不涉元件保真庫**，最適合先工具化——建議當第一個落地目標。

---

## 3. aiguard 端已備妥的「乾淨驗收案例」（不用你準備輸入）

aiguard 上游**全凍結、零臆造**，是 EPIC 驗收定義要的「第一個真實 refs-derived 輸入」。你落地 verb 後可直接拿它回歸：

- **輸入來源**（deck v3 權威、皆可 trace）：
  - `03.aiguard/C03-EE/C03_Pin_Allocation.csv`、`C03_BOM.csv`、`Netlist_Status.md`
  - `03.aiguard/C04-Layout/01_refs/C04_物理約束SSOT.md`（板框、板緣-面映射、stamp hole 定義）
  - `03.aiguard/C02-ME/…/Mechanical_Constraints.json`（板尺寸 = C02 envelope 推導）
- **placement 約束要點**：center = U1（STM32N657）、高速記憶體（PSRAM HEXASPI / Octal Flash OCTOSPI）**不跨半孔**、低速訊號/電源才走 castellated、板尺寸來自 C02 envelope、pad count **參數化**（deck 未定案）。

---

## 4. 端到端驗收（判定「改好了」）

```
place_components → emit_castellated → route → layout_drc_gate
                                                 ├ copper violations = 0
                                                 ├ unconnected pads  = 0
                                                 └ unmapped pads     = 0
= C04 freeze → 解鎖 C07 整個 fab inventory
```

三件式核心板（core stamp 20 + product board 10 + dev board 10）能通過此鏈 = EPIC 準則 2/3 達標。

---

## 5. c01/c02 emitter 前提（準則 1 的 emitter 級證據）

aiguard 的 C01/C02 交付物**整層都是 pre-deck**——不是單行殘留，而是 emitter 內建的 "modular platform" variant 模板（5 埠 universal socket A~E + MIPI 5→2 mux + host/module 大小樂高）當**預設起手**。檔案自證 `_skeleton_note: "Corrected from generic C01 template"`。

- **根因**：emitter 不吃 `01_refs/` SSOT，且 readiness 只檢**存在性**、不檢 **refs 回溯**，臆造模板能過 gate。
- **建議**：emitter 改吃 `01_refs/` SSOT；readiness 加 provenance 回溯檢查並掛鉤 `dod_ok`。
- 若 placement 引擎吃的是 emitter 吐出的 C01/C02 約束，**先修 emitter，否則 placement 會建在臆造骨架上**。

---

## 6. 建議的 plan 排序

1. **`emit_castellated`** 先落地（製程特徵、無保真庫依賴、可獨立測）。
2. **c01/c02 emitter refs-first 修正 + readiness provenance gate**（placement 的乾淨輸入前提）。
3. **`place_components`**（最大塊，吃 1+2 的輸出）。
4. 用 aiguard 三件式核心板跑 §4 端到端鏈 → 回填 EPIC 準則 2/3 驗收。

---

## 7. 回饋方式

落地後請在對應 BR 補 `## Resolution` 段（commit hash + verb 名 + gate.py verb 數變化），或把 BR 移到 `issues/closed/`。aiguard 端會定期複查 `gate.py --list` verb 數與 placement 原始碼是否出現——**你動工的訊號就是這兩者變化**。

球在你這邊。aiguard 端不需再做任何事即可當回歸驗收案例。

## Resolution（2026-07-06 consumed & closed）

四份 BR 已全數消費並歸檔（各檔補 `## Resolution`）。§6 建議排序實際落地情況：

1. `emit_castellated` → **`c04_castellation`** verb ✅
2. c01/c02 emitter refs-first + provenance readiness → spec `capability/refs-first-emitters`（living）✅
3. `place_components` → **`c04_face_placement`** + `placement_to_coords` + `net2pcb_board(placement=...)` + G3 `preplace.py` ✅
4. 端到端鏈：本 repo 以 `tests/test_worker_side_placement_roundtrip.py`（DRC gate 實跑）+ TV 系列覆蓋；**aiguard 實檔回歸請 aiguard 端執行**（§7 約定的訊號：`gate.py --list` 由 52 → 56 landing verbs，placement/castellation 原始碼已在 `upstream_constraints.py` / `board_surgery.py` / `preplace.py`）。
