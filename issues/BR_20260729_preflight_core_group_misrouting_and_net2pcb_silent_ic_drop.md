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

