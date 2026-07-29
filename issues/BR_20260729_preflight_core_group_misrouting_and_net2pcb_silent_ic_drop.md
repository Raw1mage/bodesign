# BR_20260729 — (A) autoroute_preflight 誤分 core group 永遠 ready:false；(B) route_net2pcb 靜默丟棄 8 顆主動 IC

- Status: OPEN
- Filed by: aiguard consumer session `ses_073a93d09ffeRTpR9TwIdofhb3`
- Supersedes: `br=freerouting-toolchain` 的 "restart 空窗暫態" RCA（該 RCA 不成立，見 §A）
- Fix venue: NEW session rooted in `/home/pkcs12/projects/bodesign`

---

## §A 缺陷 A：`bodesign_autoroute_preflight` 被分到 `core` group，在 workers 模式下永遠 `ready:false`

### Symptom（verbatim，連續兩次重跑一致）

```json
{"ready": false,
 "missing": ["freerouting.jar", "java", "xvfb-run-or-DISPLAY"],
 "probe": {"jar_present": false, "java_present": false, "xvfb_present": false,
           "jar_path": "/opt/freerouting.jar", "java_bin": "java"}}
```

### 為何 platform 的 "restart 空窗暫態" RCA 不成立

platform 用 `docker exec` 進 **ee worker 容器**驗證，看到 java/jar/xvfb 全在 → 結論「toolchain 從未缺失」。
但 consumer 是透過 **MCP facade** 呼叫，probe 實際在 **facade 容器**執行。兩者是不同容器。

### RCA（evidence-anchored）

1. **依賴確實只在 ee worker**（`docker exec` 三容器實測）：

   | 容器 | java | xvfb-run | /opt/freerouting.jar | FREEROUTING_JAR |
   |---|---|---|---|---|
   | `bodesign-pkcs12-bodesign-1`（facade, `--tools core`） | MISSING | MISSING | MISSING | UNSET |
   | `bodesign-pkcs12-bodesign-ee-1`（`--tools ee`） | /usr/bin/java | /usr/bin/xvfb-run | 5044336 bytes | /opt/freerouting.jar |
   | `bodesign-pkcs12-bodesign-me-1` | MISSING | MISSING | MISSING | UNSET |

2. **group 表漏列 preflight** — `services/mcp/server.py:1275-1305` 的 `_EE_GROUP_TOOLS` 收錄了
   `bodesign_autoroute`，**但沒有收錄 `bodesign_autoroute_preflight`**。
   `_group_of()`（L1314-1320）對未列名者一律 `return "core"`。

3. **facade 以 `--tools core` 啟動**（`docker inspect` Cmd 實測：
   `--transport http --uds ... --tools core`），
   `_serves_locally("core")` → True → `_route_tool` 回 `("local", None)`（L1341-1350），
   於是 `_h_autoroute_preflight`（L594-596）**直接本地 import** `bodesign_eda_bridge.autoroute_preflight()`，
   在**沒有 java/jar/xvfb 的 facade 容器內**做 probe → 三項必然全 false。

### 結論

- **不是暫態**：與 restart 時序無關，是 group 分派表的靜態缺漏，**每次呼叫都必 false**。
- **契約自相矛盾**：`bodesign_autoroute` 正確 forward 到 ee worker，其**前置 gate** 卻在 facade 本地跑。
  gate 與被 gate 的動作在不同容器評估環境 → gate 結論對 autoroute 毫無效力。
- platform 順修的 `routing.py` jar default 路徑（`/opt/freerouting/` → `/opt/freerouting.jar`）
  是**另一個獨立的 latent bug，修得對**，但**不解本缺陷**（facade 內 jar 根本不存在，路徑對不對都 false）。

### Fix proposal

`services/mcp/server.py` `_EE_GROUP_TOOLS` 補上 `"bodesign_autoroute_preflight"`。
（同時複查其餘 C04 gate 類 tool 是否有同樣漏列：`bodesign_placement_preflight` 亦需確認——
它讀 `.kicad_pcb` 算 courtyard，若依賴 pcbnew 也該在 ee。）

### Validation plan

1. 修後從 **MCP facade**（非 docker exec）呼叫 `bodesign_autoroute_preflight` → 應 `ready:true, missing:[]`。
2. 確認回傳帶 worker 來源（或 probe 中 jar_path 實際存在）。
3. 連續 3 次穩定。

---

## §B 缺陷 B：`route_net2pcb` 靜默丟棄 8 顆主動 IC，卻回報 `unmapped: 0`

### Symptom

```
route_net2pcb(netlist=aiguard_ccm.net, layers=4) →
  ok:true, placed:84, nets:282, pads_assigned:237, unmapped:0
```

netlist 實含 **92** 個 `(comp (ref`，board 內僅 **84** 個 `(footprint`。
差額 8 個經 `comm` 比對為：**`U1 U2 U3 U5 U6 U7 UB1 UW1`**——**全部是主動 IC**
（MCU / PSRAM / NOR Flash / PMIC / LDO / BLE 模組 / WiFi）。被動件 84 顆全數保留。

### RCA

被丟棄的 8 顆，其 footprint 全部指向**專案自帶 library**：

```
U1  aiguard:STM32N657_VFBGA223
U2  aiguard:PSRAM_TPBGA24
U3  aiguard_U3:BGA-24_L8.0-W6.0-P1.00-D0.4_MX25UM51245GXDI00
U5  aiguard_U5:DSBGA-6_L0.8-W1.2-P0.40-R3-C2-TL
U6  aiguard:TPS62824_VSON6
U7  aiguard:MIC5365_SOT323
UB1 aiguard:MDBT53_SMD65
UW1 aiguard:NRF7002_QFN48
```

保留的 84 顆則全用 KiCad stdlib（如 `Capacitor_SMD:C_0402_1005Metric`）。
→ **footprint library 未解析 → 元件被靜默略過**，且 `unmapped` 計數器未計入
（`unmapped:0` 只反映 pad-name 對應，不涵蓋「整顆元件消失」）。

### 為何這是嚴重缺陷（同族 BR_20260723d）

- **靜默降級**，違反 No-silent-fallback 天條：`ok:true` + `unmapped:0` 讀起來完全成功。
- **後果比空框更嚴重**：下游 `placement_preflight` 會對一塊「沒有任何 IC 的板」算出漂亮的
  utilization/courtyard verdict；`autoroute` 會 route 一塊沒有 MCU 的板；
  DRC 會全綠。**整條 C04 鏈會在缺 8 顆主動件的板上一路綠燈到 fab**。
- 這正是 repo 天條所指的 floating-PSRAM 型災難（gate 假 PASS）。

### Fix proposal

1. **fail-loud**：footprint lib 無法解析時 raise（比照 BR_20260723d 的 `SymbolLoadError`），
   或至少回傳 `dropped_components: [...]` + `ok:false`。
2. 新增 `fp_dirs` / `footprint_dirs` 參數（比照 composer 的 `symbol_dirs` merge 修法 `a7fe826`），
   讓 caller 提供專案 footprint library 路徑，且**與 stdlib 併集非互斥**。
3. `placed` vs netlist 元件數不一致時，結果必須顯著標示。

### Validation plan

1. 對同一 netlist 不給 fp_dirs → 應 `ok:false` 或帶 `dropped_components` 8 項，**不得** `ok:true/unmapped:0`。
2. 給正確 fp_dirs → `placed:92`。
3. 確認 `placement_preflight` 不會對殘缺 board 回 `passed:true`。

---

## Explicitly NOT bugs（已確認正確，勿動）

- `autoroute_preflight` 的 fail-loud **輸出設計**無誤（列缺項 + remedy + probe），問題純在**執行位置**。
- platform 對 `routing.py` jar default 路徑的順修**正確**，應保留。
- `experiments/` bind mount（`/home/pkcs12/projects/bodesign/experiments` → `/work/experiments`, rw）
  是可用的 host↔容器大檔通道，**運作正常**（166881 bytes netlist 實測雙向可見）。
  先前 subagent 回報的「傳輸 blocker」是它沒發現這條路徑，非平台缺陷。
- aiguard netlist 本身無誤（92 元件，md5 `59192a6d424172d572314b728cb6d5b4`）。

## Environment

- facade: `bodesign-pkcs12-bodesign-1` `--tools core`
- ee worker: `bodesign-pkcs12-bodesign-ee-1` `--tools ee`, `BODESIGN_EE_WORKER_URL=http://bodesign-ee:8077`
- 證據取得日：2026-07-29

---

## §C 缺陷 C（round=3 新增）：`placement_preflight` 靜默 fallback 到「含絲印文字」的 bbox，overlap/utilization 判決全部失真

### Symptom

對已修好的完整 92 元件 board（`aiguard_ccm_full.kicad_pcb`）跑 `placement_preflight`：

```
passed:false  overlap_pairs:135  utilization:1.2679
parts_area_mm2:11151.088  board_area_mm2:8795.12
worst: ['JSA','JSB'] 915.3208 mm²
```

其中包含**物理上不可能**的判決：相距 8mm 的兩顆 0402 電容（真實 courtyard 約 1.9 mm²，邊長 ~1.4mm）
被判「重疊 27.7808 mm²」。utilization 1.27（元件面積 > 板面積 127%）本身即為荒謬值。

### RCA（實測，非推論）

`routing.py:328-332`：

```python
try:
    bb = fp.GetCourtyardBoundingBox()
    if bb.GetWidth() <= 0 or bb.GetHeight() <= 0:
        bb = fp.GetBoundingBox()
except Exception:
    bb = fp.GetBoundingBox()      # ← 靜默 fallback
```

在 ee worker 的 pcbnew 版本中 **`FOOTPRINT.GetCourtyardBoundingBox` 根本不存在**：

```
>>> hasattr(fp,'GetCourtyardBoundingBox') → False
>>> [m for m in dir(fp) if 'ourtyard' in m]
    ['AllowMissingCourtyard','BuildCourtyardCaches','GetCachedCourtyard','GetCourtyard','SetAllowMissingCourtyard']
```

→ 每顆 footprint 都 `AttributeError` → 被 `except Exception` 吞掉 → **全部**改用
`GetBoundingBox()`，而該 bbox **包含 F.SilkS / F.Fab 的參考編號與數值文字**。
文字框遠大於元件本體，於是任意兩顆鄰近元件的「文字框」互相相交 → 假重疊。

### 量化對照（同一塊 board，容器內 pcbnew 實測）

| 量測基準 | overlap pairs | 元件總面積 | 最糟對 |
|---|---|---|---|
| `GetBoundingBox()`（含文字，= 現行行為） | **135** | **11151.1 mm²** | JSA/JSB 915.32 mm² |
| `GetBoundingBox(False, False)`（排除文字） | **6** | 1051.2 mm² | JSB/U7 8.96 mm² |
| `GetCourtyard(F_CrtYd/B_CrtYd).BBox()`（真 courtyard） | — | **1008.8 mm²** | — |

逐件對照（mm²）：

| ref | bbox+文字 | bbox−文字 | 真 courtyard |
|---|---|---|---|
| C1 | 59.91 | 1.81 | 1.93 |
| C2 | 59.91 | 1.81 | 1.93 |
| U1 | 137.72 | 102.21 | 100.60 |
| U2 | 486.06 | 55.70 | 49.27 |
| U3 | 578.02 | 55.70 | 49.27 |
| JSA | 1312.41 | 147.36 | 149.36 |
| JSB | 1312.41 | 147.36 | 149.36 |
| UB1 | 555.42 | 158.19 | 135.12 |
| UW1 | 457.18 | 47.02 | 37.09 |

**面積灌水約 11 倍**（11151 vs 1009）。

### 為何嚴重

1. **違反 No-silent-fallback 天條**：API 不存在是部署事實，卻被 `except Exception` 吞成「靜靜換一種量法」，
   呼叫端完全看不出 verdict 的基準已經換掉。
2. **docstring 明示的契約被違反**：函式自稱 "from REAL footprint courtyards (**no guessing**)"，
   實際上 100% 的量測都不是 courtyard。
3. **gate 失效（雙向）**：
   - 假陽性（現況）：好的 floorplan 被判 135 重疊 → 逼使用者去「修」不存在的問題，
     或更糟——去放寬門檻（正是本 repo 天條禁止的 floating-PSRAM 型災難路徑）。
   - 假陰性風險：utilization 被灌水 11 倍，`sheet_under_filled`（min_utilization=0.40）
     這條檢查**永遠不可能觸發**，等於該 gate 已死。
4. 這是 §A/§B 修好後**才浮現**的下一層缺陷——與它們同族（都是靜默降級）。

### Fix proposal

1. **改用實際存在的 API**：`fp.GetCourtyard(pcbnew.F_CrtYd)` / `B_CrtYd` 取 `SHAPE_POLY_SET`，
   `.OutlineCount()>0` 時用 `.BBox()`。
2. **fallback 必須 loud**：真的沒有 courtyard 圖層時，退用 `GetBoundingBox(False, False)`
   （**排除文字**），並在回傳中列出 `courtyard_missing: [refs]` + 標明 `basis: "bbox_no_text"`，
   不得靜默。
3. **禁止裸 `except Exception`**：API 不存在（`AttributeError`）與單一 footprint 無 courtyard
   是兩種不同狀況，前者是部署問題應 fail-loud，不可與後者混為一談。
4. 回傳新增 `basis` 欄位（`courtyard` / `bbox_no_text`），讓呼叫端知道 verdict 的量測基準。

### Validation plan

1. 對 `aiguard_ccm_full.kicad_pcb`（92 元件，grid 擺放）跑修後 preflight：
   overlap_pairs 應為 **6**（非 135），parts_area 應約 **1009 mm²**（非 11151），
   utilization 應約 **0.115**（非 1.27）。
2. 回傳應含 `basis` 欄位；若走 fallback 應同時列 `courtyard_missing`。
3. `C1`/`C2` 這類相距 8mm 的 0402 **不得**出現在 overlaps 中。

### 附帶影響：C04 真實 floorplan 結論（本 BR 修好前無法定案）

以真實 courtyard 計，這塊 grid 擺放的板實際只有 **6 對重疊**（最糟 JSB/U7 8.96 mm²），
utilization ≈ 0.115（遠低於 0.40 門檻 → 真正的問題其實是 **sheet_under_filled**，
即元件擠在一小條區域、板子過大，而非「擠爆」）。
真實結論與現行 gate 回報的「utilization 127% 擠爆」**完全相反**。


---

## §D 缺陷 D（round=4 新增）：`route_net2pcb` 的 `plane_layers` 值格式不符即靜默丟棄 → 4 層板沒有任何 power plane

### Symptom（我自己的 C04 board 就已中招，且完全無感）

呼叫：
```json
route_net2pcb(layers=4, plane_layers=["In1.Cu:GND","In2.Cu:PWR"], track_mm=0.25, ...)
→ ok:true, placed:92, nets:282, unmapped:0, dropped_components:[]
```
回傳一切正常。但容器內 pcbnew 實測該 board：
```
copper layer count = 4          （layers=4 生效 ✔）
In1.Cu  type=0  is_POWER=False  ← 應為 LT_POWER
In2.Cu  type=0  is_POWER=False  ← 應為 LT_POWER
F.Cu / B.Cu type=0
LT_POWER=1  LT_SIGNAL=0
default netclass track width = 0.25 mm   （track_mm 生效 ✔）
```
**`plane_layers` 完全沒有作用**，而 `layers` / `track_mm` 在同一次呼叫中都生效 —— 所以不是整個呼叫失敗，是**單一參數被靜默吃掉**。

### RCA（`routing.py:135-143`）

```python
lymap = {"In1": pcbnew.In1_Cu, "In2": pcbnew.In2_Cu, ...}   # key 是 "In1"
for nm in (plane_layers or ["In1", "In2"]):
    ly = lymap.get(nm)          # 我傳 "In1.Cu:GND" → None
    if ly is not None:          # ← None 直接跳過，無任何訊號
        try: board.SetLayerType(ly, pcbnew.LT_POWER)
        except Exception: pass  # ← 連真的設定失敗也吞掉
```

實測：
```
lymap.get('In1.Cu:GND') = None
lymap.get('In2.Cu:PWR') = None
```

**雙層靜默**：
1. `if ly is not None` — 無法辨識的 key 靜默跳過，不 raise、不進 warnings、不進回傳值
2. `except Exception: pass` — 即使 key 認得、`SetLayerType` 真的失敗，也一樣吞掉

### 為何這個格式會被傳進來（不是純粹使用者失誤）

- tool schema 只寫 `"plane_layers": {"type":"array","items":{"type":"string"}}`，**未說明合法值域**
- KiCad 的實際圖層名就是 `In1.Cu`（帶 `.Cu`），`Stackup.md` 也寫 `L2=GND / L3=PWR`
- `In1.Cu:GND` 這種「圖層:網路」寫法是同類工具（含本 repo 其他 net-class 參數）的常見慣例
→ 呼叫端幾乎必然會傳到不被接受的格式，而工具**不會告訴你**。

### 為何嚴重（C04 交付實質影響）

1. **4 層板的核心價值就是 GND/PWR plane**。沒有 plane 的 4 層板等於「兩層訊號 + 兩層閒置銅」，回流路徑、阻抗控制（`Stackup.md` 的 Z0 目標）、EMC 全部失去前提。
2. 下游**無一能發現**：`pour_planes` 會照做但沒有 LT_POWER 語義、`autoroute` 照 route、`layout_drc_gate` 不檢查圖層型別、`si_check` 的 Z0 假設已失效卻仍給數字。**一路綠燈到 fab**。
3. 與 §B/§C 同構：失敗被轉成「看起來正常的回傳值」，且**回傳值裡沒有任何欄位反映這件事**。

### Fix proposal

1. **值域正規化**：接受 `In1` / `In1.Cu` / `In1.Cu:GND` 三種寫法（取 `.`/`:` 前的圖層 token），並把 `:GND` / `:PWR` 的網路意圖保留下來（可用於後續 `pour_planes` 的預設網路）。
2. **無法辨識即 fail-loud**：不在 `lymap` 中的 key → `raise ValueError("PLANE_LAYER_UNKNOWN: ...")`，或至少放進回傳的 `warnings[]` + `plane_layers_applied[]`。
3. **回傳值必須可稽核**：新增 `plane_layers_applied: [{layer, net, type}]`，讓呼叫端能確認 plane 真的建立了 —— 這是本 BR 四個缺陷的共同解方（**回傳值要能反映「實際做到什麼」，而非「請求了什麼」**）。
4. **移除 `except Exception: pass`**：`SetLayerType` 失敗是實質失敗，不可吞。
5. schema description 補上合法值域與範例。

### Validation plan

1. `plane_layers=["In1.Cu:GND","In2.Cu:PWR"]` → 修後 In1/In2 的 `GetLayerType()` 應為 `LT_POWER(1)`，回傳 `plane_layers_applied` 兩項。
2. `plane_layers=["Bogus9"]` → 應 fail-loud（raise 或 warnings + applied 為空），**不得**靜默 `ok:true`。
3. 既有 `plane_layers=["In1","In2"]` 寫法必須保持相容。


---

# §E–§L（round=5–24 續補）

前四節（§A–§D）逐個詳述。§E 之後同一反模式反覆出現，改以**索引 + 各節關鍵證據**記錄；
完整推理與判別句住在 KB control `ragbase/control/no-silent-degradation/`，此處保留缺陷本身的
一手證據與 commit 對應，避免 BR 與 KB 互抄（V4-c：同一事實抄兩份必然 drift）。

## 缺陷索引（全 12 節）

| 節 | 缺陷 | KB 變體 | commit |
|---|---|---|---|
| §A | `_EE_GROUP_TOOLS` 漏列 preflight 工具 → 在無 toolchain 的 facade 本地跑 → 永遠 `ready:false` | 分派表漏列 | `1269a20` |
| §B | `route_net2pcb` 遇 footprint lib 未解析即 `continue`，靜默丟 8 顆主動 IC，`unmapped:0` 掩蓋 | V1 | `1269a20` |
| §C | `GetCourtyardBoundingBox()` 不存在 → 裸 `except` 靜默 fallback 到含絲印 bbox → 面積灌水 11× | V2 | `cdbcb02` |
| §D | `plane_layers` 值格式不符即靜默跳過 → 4 層板 power plane 從未建立 | V1 | `cdbcb02` |
| S2 | `layout.py` 收集 `unresolved_footprints` 但 `status` 恆為 `"ok"` | V3 | `cdbcb02` |
| §E | `_extract_part_geoms` 仍用含絲印 bbox（§C 只修了兩個 call site 之一）→ `PREPLACE_BOARD_TOO_SMALL` 假紅 | V4 | `f958e68` |
| §F | extent 統一但 anchor 未統一：`_overlap_area` 當 `p` 是盒心、`SetPosition` 寫 origin | V4-b | `a25d898` |
| §G | `via_in_pad` 對非網格 pad 名裸崩；混合命名則靜默穿透繞過 `keep_rings` | V1 反向 | `58c37cd` |
| §H | `pcbnew.LoadBoard(不存在路徑)` 回 `None` → 下游 SIGSEGV worker 猝死；DSN export 只信旗標不驗產物 | 資源取得 | `545fddb` |
| §I | `clean_micro_stubs` 漏於 `_EE_GROUP_TOOLS`（§A 第二次復發） | V4-c | `c87b1ba` |
| §J | `autoroute` 不 echo 有效搜尋預算 → 呼叫端把「我給的努力不夠」誤讀成「這塊板佈不通」 | V5 | `740ac75` |
| §K | router 被授權的 via（0.6mm）大於 BGA ball pitch（0.5mm）→ 內層形同不可達，而 `capacity` 算式默認換得了層 | V6 | `b13ae58` |
| §L | `mcpctl.sh restart` 摧毀他人長跑運算後仍印 `restarted` | ops 層 V1 | `d7a0b86` |

配套 commit：`21a4afc`（KB control + checker + 15 測試）、`33197b2`（L10 checker 自報覆蓋範圍）、
`1927982`（`bga_escape_capacity` 工具）、`bddfdc8`（KB 驗證工具元層級）、`60b987e`（doctrine §6）。

## §E 關鍵證據：修一半比不修更危險

§C 修好 `placement_preflight` 的量測基準後，`_extract_part_geoms`（preplace 路徑）仍用舊 bbox。
後果不是「還沒修好」而是**新的假紅**：`PREPLACE_BOARD_TOO_SMALL` 擋掉合法板，因為它用灌水 11× 的
面積去比板框。真板數據：`parts_area_mm2` courtyard 基準 = 1008.794，含絲印 = 11151.1。

修法是 `footprint_extent(fp)` 單一 helper（回傳 `(w,h,dx,dy,basis,degraded)`），兩個 call site 共用。
**L8 lint 由此而生**：同一量測 API 在 >1 個函式各自實作即報。

## §F 關鍵證據：extent 對了，參考系仍錯

`_overlap_area` 把 `p` 當盒心用，但 `pcbnew.SetPosition()` 寫的是 **origin**。5 顆 courtyard 不置中的
元件（JSA/JSB 偏移 22.2mm）於是被 SA 依錯誤世界模型最佳化。修後 HPWL 2453.48 → 2065.235（−15.8%）
——**這個下降本身就是修前在錯誤前提上最佳化的反證**。

參考系契約寫進 `PartGeom` docstring：placement entry 是 ORIGIN、pads 從 origin 量、
`anchor_dx_mm` 是 courtyard-centre 減 origin 且為 part-local 未旋轉座標。

## §G 關鍵證據：裸崩在遮蔽一個更糟的靜默缺陷

`via_in_pad` 對 castellated/LGA 的數字 pad 名拋 `max() iterable argument is empty`。修復時挖出：
**混合命名（部分 `A1`、部分 `1`）不崩，但每個非網格 pad 都繞過 `keep_rings` 保護被塞 via**——
`cols` 非空所以沒人發現，呼叫端只看到合理的 `vias_added`。只有「全部 pad 都非網格」才崩。

## §H 關鍵證據：SIGSEGV 與 timeout 在外部無法區分

`pcbnew.LoadBoard(不存在路徑)` 回 `None`（不 raise），下一個 pcbnew 呼叫直接 SIGSEGV，worker
EXIT=139。consumer 側看到的現象是「連線斷」，與 MCP timeout **一模一樣**——它據此做的
「detached vs MCP」對照實驗從一開始就分不出真相。

修法：`_load_board(path)` SSOT helper，fail-loud `BOARD_NOT_FOUND` 帶 resolved 絕對路徑 + worker cwd +
「原本會 segfault」三件事，11 個 call site 全部替換。同函式的 DSN export 補產物驗證
（原本 `.ses` 有驗、`.dsn` 沒驗的不對稱）。

## §I 關鍵證據：第二次復發代表補名字不是解法

`_EE_GROUP_TOOLS` 是**手維護靜態清單**，而「這個工具需要 pcbnew」的權威來源是函式體的
`_need_pcbnew()` 呼叫。同一事實記在兩處且可以不一致 = V4-c。

守衛 `tests/test_worker_group_routing.py` 從權威 AST 推導（fn → handler import → TOOLS entry → group
成員），測試檔內**不寫死任何工具名**。三個設計決定：不用命名猜測（真實映射是
`net2pcb_board` → `bodesign_route_net2pcb`，靠猜會誤報）、加反向鑑別力（拿掉真成員必須被報）、
ME group 涵蓋不到就把缺口寫成會爆的測試而非注解。

## §J 關鍵證據：判決必須帶著產生它的預算

consumer 四輪全程傳 `-mp 10`（預設 40），卻把結果定性成「freerouting 搜尋能力不足」的外生限制。
單調關係實測：`-mp 1` → 27/111（1m56s）、`-mp 10` → 74/111（35m40s）、`-mp 40` → 81/111（2h45m）。

從 jar 取得規格證據（freerouting 自己的 `command_line_help`）：`-mp` 是 **upper limit**。因此
**欄位不叫 `passes`** 而叫 `passes_limit`——叫 `passes` 會被讀成「跑了 40 pass」，是拿一個誤導數字
換另一個。實跑 `-mp 1` 確認 per-pass log 被 TestLevel 閘住，**實際 pass 數拿不到就誠實不報**。

附帶發現：**docstring 對 MCP 呼叫端不存在**，schema `description` 才是唯一暴露面。已進 doctrine §5。

## §K 關鍵證據：「存在什麼」與「被授權什麼」是兩件事

```
netclass Default:       via=0.6mm  drill=0.3mm   ← router 被授權新建的
via OBJECTS on board:   0.3mm/0.15mm × 168       ← via_in_pad 實際打的
U1 ball pitch = 0.5mm   →  0.6mm via 相鄰邊緣間距 −0.1mm，球陣內開不了孔
```

`via_in_pad`（`routing.py` `SetWidth(pad_mm)`/`SetDrill(drill_mm)`）從不查板檔規則。呼叫端看到板上
168 個小 via 就以為小 via 可用——**兩個相鄰事實被讀成一個**。

`bga_escape_capacity` 的 `capacity = perimeter × per_gap × len(signal_layers)` 乘 `len(signal_layers)`
默認 router 換得了層。所以 `capacity=288`（167 需求的 1.7× 餘裕）建立在假前提上，而實測 B.Cu 只承載
10% segments、282 個 via 全是貫穿孔。

**下游背黑鍋的部分**：那 168 個 via 低於板檔自己的 `min_via_diameter=0.5`，每個生 3 筆 DRC finding，
504 筆在三步後的 `drc_gate` 才浮現，讀起來像「這塊板的設計規則有問題」。consumer 真的照這個讀法
自我歸因，還手改了 `.kicad_pro`（掃 35 個檔坐實：`ccm8_pin`=0.5 → `ccm8_pin_vip`=0.3 是事後編輯）。
**呼叫端替工具圓場時，缺陷永遠不會被 file，而且圓場動作本身製造假證據。**

修法**不自動修正**（改使用者規則或偷改 via 尺寸都是 fallback）：列 `rule_conflicts`、預告 DRC 筆數、
明說源自此處，把 fab 製程決定權留給呼叫端。

## §L 關鍵證據：指令回報意圖而非後果

`mcpctl.sh restart` 重建容器後印 `bodesign MCP restarted`——該句在「容器本來就閒著」與「剛殺掉
165 分鐘 freerouting」兩種情況下完全相同。consumer 的 routing 被腰斬兩次（13:11、13:33，`exit=0`）。

**為何修法不能是約定**：consumer 原本請求「restart 前 inject 我一聲」，但那把守衛託付給雙方記憶，
而記憶恰好在兩邊最忙時蒸發（code-thinker §7 同一條）。gate 必須在指令自己身上。

最容易寫錯的一行正是本 control：`docker exec ps` 失敗回空清單 → 讀成「沒 process」→ 放行。
**「我看不到」不是「那裡沒東西」**——探測失敗報 `UNKNOWN` 並同樣擋下。代價不對稱：誤擋成本是
多等一下，誤放成本是別人 165 分鐘的運算。

實測（用 consumer 當時正在跑的 job，382s）：`restart`/`rebuild`/`stop` 三個指令全部 exit 3，
java 進程存活。

## Explicitly NOT bugs（§E–§L 期間確認，勿再 file）

- **freerouting toolchain 從未缺失**。round=1 的「restart 空窗暫態」RCA 已被推翻——問題是 §A 的
  group 分派，preflight 實際在 facade 跑而非 ee 容器。
- **`autoroute` 運算 8 分鐘 > MCP request timeout 是常態**，非缺陷；它已有 BR_20260708 的 `complete`
  三態回報（`None` 表無法判定），是 positive pattern。
- **routing 佈不通的主因是設計層數/授權而非工具缺陷**。U1 STM32N657 19×19 BGA 222 balls / 0.5mm
  pitch，167 訊號需求 > 144 理論上界（72 通道 × 2 訊號層）。
- **netclass 差異化線寬無效不是缺陷**：規則確實逐條注入 DSN（已逐 class 核對），是該手段對此問題
  無效（真正的鎖是 §K 的 via 授權）。
- **板子加大到 200×120 決定性負面**：面積 1.66×、utilization 掉到 4.2%、佈通 74→70、耗時 35m→1h4m。

## 驗證工具自身被騙的四次（本線元層級）

| # | 側 | 工具 | 壞掉時的表現 |
|---|---|---|---|
| 1 | platform | 驗證腳本把 `docker cp` 的 stderr 導進 `/dev/null` | 測試檔沒複製進去卻報成「4 errors」——看起來像測試失敗，實際是測試沒跑 |
| 2 | consumer | 核 §I 用的 grep parse 寫壞 | 吐出「13 個工具全部不在 EE group」，含 `bodesign__load_board` 這種不存在的名字 |
| 3 | platform | 回溯 `len(TOOLS)` 的 AST counter 只處理 `Assign`，而 `TOOLS` 是 `AnnAssign` | 回 `0` 而不報錯 |
| 4 | platform | `undeclared_vias`（**預防性攔截**） | freerouting 對不存在的 padstack 靜默忽略；若 via 字串打錯，會讀到「結果沒變」而結論「via 不是瓶頸」，把真缺陷永久誤判成非缺陷 |

只有第 4 次是在造成誤判**之前**攔住的。推論：**驗證工具的輸出也是回傳值，同樣受本 invariant 約束**
——掃描類工具必須自報覆蓋範圍（L10 由此而生：README 記 11 筆但預設只跑 5 筆 = CI 假綠），
守衛測試必須有反向鑑別力（拿掉一個真成員，主檢查必須紅）。

## 順帶修掉的既有債

`tests/test_mcp_server.py::test_converged_registry_tool_count` 斷言 55，但自 `8fd59b0` 起實際就是 56
（**出生即紅**），`1927982` 加 `bga_escape_capacity` 後變 57。沒人發現，因為沒人跑完整 host suite。
改成 57 個工具**名單**斷言——計數對改名零鑑別力，而改名正是最會弄壞呼叫端的變更。

## Status

**全部 12 節已修復並經 consumer 側 facade 獨立驗證後 commit。** platform 側無未結驗證債。
