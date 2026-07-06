# BR_20260704 — bodesign 無 component-placement / castellated 工具，C04 pipeline 假設「placement 已完成」卻無工具產生它

- **軸**：A（工具缺）
- **層**：bodesign 工具層（eda-bridge compute plane + gate.py landing plane）
- **嚴重度**：High（阻塞整個 C04 從 schematic → routable board 的關鍵一步）

## 現象（含硬證據）

本 session 需求：把 aiguard CCM 核心板重設計成 castellated 郵票模組（移除假排針 J_B2B、縮板、元件三面環繞、板緣半孔接腳）。這是**純 placement 工作**（擺件 + 改板框 + 建板緣接腳），尚未進 routing。

嘗試在 bodesign 工具鏈找對應 verb，硬證據（`gate.py --list` + compute-plane not_landing 表，2026-07-04）：

- **52 個 landing verb**：C00–C06 scaffold/readiness/emit、pin_allocation、impedance_solve、reference_crosscheck… **沒有任何 place / move / castellated / stamp / board-resize verb**。
- **40 個 compute tool**（not_landing）：`route_net2pcb` / `autoroute` / `pour_planes` / `widen_bus_tracks` / `length_match_bus` / `via_in_pad` / `si_check` / `layout_drc_gate` / `emit_fab` / `emit_layout`… 全是 **routing / finishing / fab** 階段，**placement 之後**才用得上。
- `emit_layout`（C04）依 skill 描述是「constraint-first；placement 座標/stackup 從不臆造」——即它**刻意不產 placement**。
- AGENTS.md C04 pipeline 明文：`build_c04.sh <board> <netlist.net>` 的第一步 `net2pcb.py` 是「rebuild .kicad_pcb from netlist, assign nets」——**假設 placement 是 bodesign 上游（人手）已完成的輸入**，pipeline 本身不含 placement 產生器。

結果：我被迫**徒手寫 raw pcbnew 腳本**搬件、改板框、建 castellated pad。這既違反「禁止徒手替代專門工具」的紅線精神（但此處是真的沒有專門工具），又踩進 pcbnew 的 segfault 地雷（見姊妹 BR_20260704_pcbnew_scripting_segfault_hazards）。

## RCA

bodesign 的 C04 心智模型是「**placement 是人在 KiCad GUI 手動做的、屬於 bodesign 邊界之外的輸入**」，因此工具鏈從 `net2pcb`（已有 placement 的板）起跳。但實務上：

1. 從 C03 schematic/netlist 到「可 route 的板」中間，**placement 是必經且工作量最大的一步**；
2. Agent 環境沒有 GUI，無法手動擺件；
3. 對 castellated / 郵票模組這類**板型即產品定義**的設計，placement + 板緣接腳結構就是核心交付物，不是可外包的前置。

→ 缺口：沒有 headless、constraint-first 的 placement 產生器 / 編輯器 verb。

## 建議修復

新增一組 placement-plane verb（compute plane，因需 pcbnew/kicad 重工具鏈）：

1. **`place_components`**（constraint-first）：吃 `{board, netlist, placement_intent}`，intent 用**語意約束**而非硬座標（e.g. `{center: U1, ring: [U2,U3], edge_band: [U5..U8], board: {w,h}}`），內部解算不重疊擺放 + courtyard 檢查，輸出 .kicad_pcb。誠實邊界：座標由 solver 產生並回報，不臆造 stackup。
2. **`resize_board`**：改 Edge.Cuts 板框到指定尺寸，重新錨定原點。
3. **`emit_castellated`**：板緣半孔陣列產生器，吃 `{edges:[L,R,B,T], pins_per_edge, pitch, net_map}`，輸出真 PTH 半孔 pad（castellated：drill 落在板緣、鍍通半孔），承接指定 net。這是郵票模組的核心特徵，且是**製程特徵、不涉元件保真庫**，適合工具化。
4. 全部走**安全 pcbnew wrapper**（見姊妹 BR），避免 agent 各自重踩 segfault。

Placement solver 可先做簡單版（grid / ring / edge-band 三種 pattern），不必一步到位自動佈局。

## 影響範圍

- 所有需要從 C03 → C04 且無 GUI 的 headless 流程（本專案 aiguard 雙板、未來任何 agent-driven 板）。
- 郵票模組 / SoM / 板對板這類 placement-defines-product 的設計，目前**完全無法在 bodesign 內完成**。
- 不影響已有 routing/finishing/fab verb（它們在 placement 之後，補上 placement 反而讓它們終於有正確輸入）。

## 驗證手段

- `place_components` 對 aiguard CCM netlist 產出板 → `layout_drc_gate` 檢 courtyard 無重疊、unconnected pad 數合理。
- `emit_castellated` 產出的半孔 pad → pcbnew 實讀 pad.GetAttribute()==PTH、位置落在 Edge.Cuts 上、net 正確掛上。
- `resize_board` 後 `GetBoardEdgesBoundingBox()` == 指定尺寸。
- 端到端：CCM 從 authentic 板 → place → castellated → route_net2pcb → autoroute 全鏈跑通，無需徒手 pcbnew。

## Resolution（2026-07-06 closed）

- **placement**：`c04_face_placement` landing verb（`upstream_constraints.py solve_face_placement()`，約束驅動、確定性、面向凍結）+ `placement_to_coords` adapter + `net2pcb_board(placement=...)`；另 `preplace.py` G3 確定性 pre-placement（patent-anchored placement_rules，quality/deterministic-preplacement graduated）。DRC roundtrip 實板驗證：`tests/test_worker_side_placement_roundtrip.py`（pcbnew + kicad-cli 9.0.9 實跑）。
- **castellated**：`c04_castellation` landing verb（`board_surgery.py build_castellation()`，pitch/pad_count/drill 全參數化、provenance-gated、S-expression 注入 segfault-free）。
- **resize_board**：未做獨立 verb——板框為上游凍結約束（C02 envelope）而非 C04 自由度（EPIC 切面 4），`net2pcb` 依 placement/約束產 Edge.Cuts；與本 BR 原提案的範式差異屬刻意設計（refs-derived paradigm）。
- **安全 wrapper**：見姊妹 BR resolution（`assert_safe_surgery_path()` + `UNSAFE_PATHS`）。
