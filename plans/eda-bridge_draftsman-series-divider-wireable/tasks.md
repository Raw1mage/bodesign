# Tasks: eda-bridge_draftsman-series-divider-wireable

## 1. 第一刀 — `divider` + `bridge` 兩個原語打通到 compose（最小可用版）

**選這一刀的理由**：`divider` 是本包 slug 的字面來源（series-divider），
也是 `BR_20260905` §3.2 逐字點名的驗收範例（「串聯分壓」）；
`bridge` 是真實板子上數量最多的形狀（btdongle 45 元件裡 28 顆被動件多半是這個）。
兩者合起來能跑通一個完整的可辨識子電路，而**不需要碰任何既有繪圖程式碼**。

- [ ] 1.1 新模組 `packages/eda-bridge/bodesign_eda_bridge/declare.py`，純函式，零 I/O，
      不 import `composer` / `kicad_emit`（避免循環依賴，也讓它可被單獨 unittest）
- [ ] 1.2 實作 `Decl_divider` 展開：top/tap/bottom 三條 net + `load` 併入 tap
- [ ] 1.3 實作 `Decl_bridge` 展開：兩條既有 net 各加一個 node
- [ ] 1.4 實作 provenance map（DD-6）與 `E_PROVENANCE_ORPHAN` 內部斷言
- [ ] 1.5 實作完整性 gate 三態（`pass`/`fail`/`unknown`），含 `E_PIN_UNASSIGNED`
      與 `E_PIN_MULTI_NET`，**全部缺項一次列出**
- [ ] 1.6 實作 status codomain 五值的排放點（`errors.md` §Outcome Codomain 那張表逐格對應）
- [ ] 1.7 單元測試：`tests/test_declare_circuit.py`，涵蓋 TV-1..TV-8（見 `test-vectors.json`）
- [ ] 1.8 端到端：把 btdongle 的 R13/R14/C13 電池分壓 + 一組去耦，
      用 `declare_circuit` 產出 spec → 餵 `compose_schematic` → 確認
      `junction > 0` 且該分壓被畫成連通實線

**Phase 1 的完成判準（可機檢）**：
```
declare_circuit(btdongle 分壓宣告).status == "ok"
產出的 spec 餵 compose_schematic 後，VBAT_SENSE 這條 net 是 drawn 不是 label
該子電路的 junction 數 > 0
控制組：把 tap 改成等於 top => status == "rejected" 且 code == E_DIVIDER_TAP_DEGENERATE
```

## 2. 其餘四個原語 + MCP verb 註冊

- [ ] 2.1 `Decl_connect` 展開
- [ ] 2.2 `Decl_series` 展開，含中間節點衍生命名（DD-3）與 `pins` 極性映射
- [ ] 2.3 `Decl_no_connect` 展開至 `nc[]`
- [ ] 2.4 `Decl_rail` 展開（**只做電氣部分**，`render` 欄先收下但不接線，
      回 `W_RENDER_HINT_IGNORED` + `render_source:"default"`）
- [ ] 2.5 `services/mcp/server.py` 註冊 `bodesign_declare_circuit`（handler `_h_*` + schema 兩處）
- [ ] 2.6 `E_NET_NAME_COLLISION` / `E_SERIES_TOO_SHORT` / `E_RAIL_SCOPE_UNKNOWN` 三個錯誤碼
- [ ] 2.7 補齊 TV-9..TV-14

## 3. `render` hint 接線（DD-4，61 顆 power glyph 問題）

**前置條件（硬）**：round 1 發現的 `try_reserve` 71/71 全失敗必須先修。
理由見 `design.md` DD-4 —— `BR_20260905` §8.5.2 記載 power clustering 修法
讓 `moved` 從 10 爆到 67，而 round 1 定位到那道 anti-fusion 防護
（`_guard_route` 只對「已註冊 wire segment」防護）**其集合恆為空集**。
**在那格修好之前不要動這個 Phase。**

- [ ] 3.1 確認前置：`reserve_wire_ok > 0`（現況 0/71）
- [ ] 3.2 `composer.py` 的 power net 分支讀 `render_plan`
- [ ] 3.3 `local_star` / `daisy_chain` 兩種展開的幾何實作
- [ ] 3.4 真板驗收：btdongle GND `daisy_chain` 後，`#PWR` glyph 數下降、
      junction 上升，且 **fidelity `moved` 維持 10**（不得因此惡化）

## 4. Consumer 遷移與收尾

- [ ] 4.1 thesmart_products btdongle 改用 `declare_circuit`（分階段，不強制一次全遷）
- [ ] 4.2 `specs/architecture.md` 同步：C03 上游新增「宣告層」
- [ ] 4.3 event log 收尾一筆
- [ ] 4.4 KB 蒸餾判定：本包的跨 repo 教訓是
      「入口缺完整性檢查時，下游每個關卡各自發明容錯，而每種容錯的失效各自成為一張 BR」
      —— 這條換 repo 換題目都成立，應蒸
