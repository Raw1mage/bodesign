# BR_20260704 — 【消費端後續】aiguard C04 已備妥「refs-derived 驗收案例」：這是 EPIC 能力翻轉的第一個真實輸入合約，缺的兩個生成 verb 是唯一卡點

- **類型**：consumer-follow-up（承接 `BR_20260704_EPIC_capability_inversion_refs_derived_design.md` 與 `BR_20260704_no_component_placement_castellated_tool_c04_gap.md`，**不重述缺口**，改提供可直接動手的輸入合約 + 驗收案例）
- **來源 session**：aiguard C00–C07 deck v3 對齊（scope=aiguard，2026-07-04，接續同日 EPIC session）
- **軸**：A（工具缺）— 但本 BR 的貢獻是把「缺什麼」轉成「餵什麼、驗什麼」
- **嚴重度**：High（aiguard 文件層已全綠，唯一未完成的 C04 完全阻塞在 bodesign 兩個未落地 verb）
- **給 bodesign agent 的一句話**：你不用再自己找驗收案例了——aiguard 現在就是一個「上游全部凍結、全部可追溯、只差你生成 placement」的乾淨輸入。下面給你精確的輸入 JSON 形狀與端到端測法。

---

## 1. 為什麼現在發（與 EPIC 的差異）

EPIC BR（同日稍早）是在 **pre-deck** 狀態寫的：那時 aiguard 的 SSOT 建自 N6_X01（第一代整合板），架構是雙板 CCM/ECB、含 Ethernet、含 5 埠模組 + MIPI 5→2 mux——**上游本身還不乾淨**，所以 EPIC 的驗收案例裡混著待丟棄的 place1~place5 與 deck-obsolete 元件。

本 session 之後，aiguard 上游**已經乾淨了**：

| 層 | 狀態（2026-07-04 收尾） | 可追溯到 |
|---|---|---|
| C00-PRD | ✅ deck v3 即權威來源 | 正式需求書 deck v3（`DECK_V3_擷取.md`，owner adjudication） |
| C03-EE | ✅ 三件式、去 Ethernet、WiFi 降候選、去 5 埠子系統 | deck v3 + N6 ballout（derived-candidate 標記） |
| C05-FW | ✅ Pin_Map_Bridge.json 去臆造、單一固定相機 | C03 pinmap（zero invented pins，gate dod_ok:true） |
| C06-Verify | ✅ 九類驗收綁 deck、modular-platform 標 n/a | deck S11 + Verification_Summary.json |
| C07-MFG | ✅ 三件式（core stamp 20 + product 10 + dev 10） | deck v3 建構計畫 + IP 條款 |
| **C04-Layout** | ❌ **唯一未完成** | — 缺 bodesign 生成 verb |

**意義給 bodesign**：EPIC 驗收定義第 1 條（refs-first gate 有真實 SSOT 可消費）現在有一個**乾淨、無臆造殘留、每個數字可追溯到 deck** 的案例。你落地 placement 引擎時，不必自己造測資——直接吃 aiguard 的 5 層 SSOT。

---

## 2. bodesign 到底少了什麼（精確到 verb，非泛論）

硬證據 `gate.py --list`（2026-07-04，本 session 實跑）：**52 landing verb + 40 compute tool**，C04 相關只有：

- `c04_readiness`（審查就緒度，read-only）
- `c04_emit_layout_package`（打包 C01+C03 約束成 constraint package）
- compute plane：`route_net2pcb` / `autoroute` / `pour_planes` / `length_match_bus` / `si_check` / `layout_drc_gate` / `emit_fab`…（**全在 placement 之後**）

**中間缺的、且是工作量最大的一步 = placement 生成**。C04 pipeline（`build_c04.sh` → `net2pcb.py`）明文假設「板上已有 placement」，但 bodesign **既無 GUI、也無 headless placement verb 去產生它**。→ agent 只能徒手 pcbnew（踩 segfault，見姊妹 BR）或發明座標（被 honesty gate 正確擋下）。

**兩個必須新增的 verb**（承接 `no_component_placement_castellated_tool_c04_gap` BR §建議修復，此處補上 aiguard 消費端的精確輸入形狀）：

### verb A — `place_components`（約束驅動，非硬座標）
```
輸入: {
  board_or_netlist: <C03 netlist>,
  placement_intent: {                    # 語意約束，座標由 solver 解，不由 agent 給
    center: "U1",                         # STM32N657（核心板中心）
    high_speed_keep_on_core: ["PSRAM(HEXASPI)","OctalFlash(OCTOSPI)"],  # deck S6: 不跨半孔
    edge_band: [<掛 castellated 半孔的低速訊號/電源 net>],
    board: { w, h }                       # 來自 C02 envelope（凍結約束，非 C04 自由度）
  }
}
輸出: .kicad_pcb（solver 產生座標 + 回報），courtyard 無重疊，誠實不臆造 stackup
```
**aiguard 能餵的來源**：`C04-Layout/01_refs/C04_物理約束SSOT.md`（板框/面向）+ `C03_元件與腳位SSOT.md`（元件清單 + 高速記憶體留核心板規則已明文）。

### verb B — `emit_castellated`（郵票半孔陣列）
```
輸入: { edges:[L,R,B,T], pins_per_edge, pitch, net_map }
輸出: 真 PTH 半孔 pad（drill 落板緣、鍍通半孔），承接指定 net
```
**aiguard 消費端合約（deck v3 已凍結的物理事實）**：
- 高速記憶體（PSRAM/Flash）**不跨半孔** → `net_map` 只含低速訊號/電源/低速 bus。
- pad count **未定案**（deck 開放項）→ verb 需支援參數化 `pins_per_edge`，不寫死。
- 這是**製程特徵、不涉元件保真庫**（不需 real MPN/3D STEP），所以是純工具化、最適合先落地的一塊。

---

## 3. 端到端驗收（bodesign 判定「改好了」的可執行測法）

以 aiguard 為第一個真實案例，全程**不得有任何憑空座標/腳位/元件**（每個數字可追溯到 SSOT → SSOT 追溯到 deck v3）：

```
C03 netlist + C04_物理約束SSOT
  → place_components        # solver 產座標；核心板中心=U1、高速記憶體留核心板
  → emit_castellated        # 板緣半孔承低速 net；pad count 參數化
  → route_net2pcb → autoroute → pour_planes → length_match_bus
  → layout_drc_gate         # copper=0 / unconnected=0 / unmapped=0 / SI ok
```

**每一 verb 的具體 assert**（承 `no_component_placement_castellated_tool_c04_gap` BR §驗證手段）：
- `place_components`：`layout_drc_gate` 檢 courtyard 無重疊、unconnected pad 數合理。
- `emit_castellated`：pcbnew 實讀 `pad.GetAttribute()==PTH`、位置落 Edge.Cuts 上、net 正確掛上。
- **端到端過關 = C04 freeze**：aiguard C07 的整個 fab-output inventory（現全 `pending against C04-freeze`）才能從 pending 轉 available。

**反向判定（未達標）**：若仍需徒手 pcbnew scripting、或 solver 要 agent 提供硬座標、或高速記憶體被擺到跨半孔 → 翻轉未達標。

---

## 4. 影響範圍

- **bodesign**：這兩個 verb 是 C00→C04 全鏈唯一斷點；補上後既有 40 個 routing/finishing/fab compute tool 才終於有正確輸入（它們在 placement 之後，一直缺上游）。
- **aiguard**：C00/C03/C05/C06/C07 文件層**已全部完成且對齊 deck v3**，不再等任何東西——**只等這兩個 verb**。是最省事的回歸驗收案例（上游已凍結、已去臆造）。
- **通用性**：郵票模組 / SoM / 板對板這類 placement-defines-product 設計，目前在 bodesign 內**完全做不出**；此二 verb 一落地即解鎖整類產品。

---

## 5. 與既有 BR 的關係（避免重複、明示接續）

| 既有 BR | 本 BR 的補充 |
|---|---|
| `EPIC_capability_inversion_refs_derived_design` | 提供 EPIC 驗收定義第 1、2、3 條的**乾淨真實案例 + 精確輸入 JSON 形狀**（EPIC 當時案例還混著 pre-deck 臆造，現已清乾淨） |
| `no_component_placement_castellated_tool_c04_gap` | 承其 §建議修復的 verb 設計，補上 **aiguard deck-v3 消費端的實際輸入來源檔 + net_map 約束**（高速記憶體不跨半孔、pad count 參數化） |
| `pcbnew_scripting_segfault_hazards` | 佐證：因缺此二 verb，唯一替代路徑（徒手 pcbnew）已證實是地雷 |

**不需要 aiguard 端再做任何事**——上游 SSOT 已備妥。球在 bodesign。
