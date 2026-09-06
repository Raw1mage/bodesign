# Tasks: eda-bridge_draftsman-series-divider-wireable

## 1. 第一刀 — `divider` + `bridge` 兩個原語打通到 compose（最小可用版）

**選這一刀的理由**：`divider` 是本包 slug 的字面來源（series-divider），
也是 `BR_20260905` §3.2 逐字點名的驗收範例（「串聯分壓」）；
`bridge` 是真實板子上數量最多的形狀（btdongle 45 元件裡 28 顆被動件多半是這個）。
兩者合起來能跑通一個完整的可辨識子電路，而**不需要碰任何既有繪圖程式碼**。

- [x] 1.1 新模組 `packages/eda-bridge/bodesign_eda_bridge/declare.py`，純函式，零 I/O，
      不 import `composer` / `kicad_emit`（避免循環依賴，也讓它可被單獨 unittest）
      —— `kicad_emit.load_symbol` 為**函式內 lazy import**，模組層仍為零耦合
- [x] 1.2 實作 `Decl_divider` 展開：top/tap/bottom 三條 net + `load` 併入 tap
- [x] 1.3 實作 `Decl_bridge` 展開：兩條既有 net 各加一個 node
- [x] 1.4 實作 provenance map（DD-6）與 `E_PROVENANCE_ORPHAN` 內部斷言
- [x] 1.5 實作完整性 gate 三態（`pass`/`fail`/`unknown`），含 `E_PIN_UNASSIGNED`
      與 `E_PIN_MULTI_NET`，**全部缺項一次列出**
      —— 實作為**五態**：另加 `vacuous`（零元件，跑了但無腳可檢）與 `not_run`
      （gate 從未被呼叫）。三態會讓「零元件全綠」與「檢查過全綠」共用同一個值，
      那正是 BR_20260730b 的形狀
- [x] 1.6 實作 status codomain 五值的排放點（`errors.md` §Outcome Codomain 那張表逐格對應）
- [x] 1.7 單元測試：`tests/test_declare_circuit.py`，涵蓋 TV-1..TV-8（見 `test-vectors.json`）
- [x] 1.8 端到端：把 btdongle 的 R13/R14/C13 電池分壓 + 一組去耦，
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

- [x] 2.1 `Decl_connect` 展開
- [x] 2.2 `Decl_series` 展開，含中間節點衍生命名（DD-3）與 `pins` 極性映射
      —— 中間節點 `<decl_id>_nN`，N 條 part 產出 N-1 個衍生節點；
      `_pin_lists` 拿得到時取 symbol 兩腳，拿不到才退 `["1","2"]`
- [x] 2.3 `Decl_no_connect` 展開至 `nc[]`
- [x] 2.4 `Decl_rail` 展開（**只做電氣部分**，`render` 欄先收下但不接線，
      回 `W_RENDER_HINT_IGNORED` + `render_source:"default"`）
      —— warning **實際排放**且回顯 `[decl_id, rail_name, render_mode]`；
      對照組（未給 hint）warnings 為空。刻意的無操作若無痕跡，
      「讀了但忽略」與「根本沒讀」共用同一份輸出，Phase 3 將無從驗證接線是否生效
- [x] 2.5 `services/mcp/server.py` 註冊 `bodesign_declare_circuit`（handler `_h_*` + schema 兩處）
      —— handler 走 `bodesign_eda_bridge.declare` **直接子模組 import**，不經 `__init__`
      （後者拉 kiutils；宣告層必須在無 KiCad 的主機上可用）；
      刻意**不列入** `_EE_GROUP_TOOLS`，同理
- [x] 2.6 `E_NET_NAME_COLLISION` / `E_SERIES_TOO_SHORT` / `E_RAIL_SCOPE_UNKNOWN` 三個錯誤碼
      —— 三者的錯誤物件都回顯它拒絕的識別符（chain 內容 / 撞名 net / 未知 ref），
      且 scope 一次列出全部未知 ref 而非只報第一個
- [x] 2.7 補齊 TV-9..TV-14

**Phase 2 的完成判準（已量，見 handoff.md §Phase 2 Evidence）**：
```
六個原語各自至少一個 vector 走到 ok        connect/bridge/series/divider/rail/no_connect 全數 status=ok gate=pass
三個新錯誤碼各自被觸發且回顯識別符          E_SERIES_TOO_SHORT / E_NET_NAME_COLLISION / E_RAIL_SCOPE_UNKNOWN
五個 status 值各自被 Phase 2 輸入觸發過      ok / rejected / not_run / empty / indeterminate 五值互異
verb 可達（非僅字串存在）                   NEGCTRL 回顯我送的假名，TREATMENT 經同一 dispatch 回 ok
回歸 NEW_failures_caused_by_me              [] （treatment 46 / baseline 46，集合逐字相同）
```

## 3. `render` hint 接線（DD-4，61 顆 power glyph 問題）

**前置條件（硬）**：round 1 發現的 `try_reserve` 71/71 全失敗必須先修。
理由見 `design.md` DD-4 —— `BR_20260905` §8.5.2 記載 power clustering 修法
讓 `moved` 從 10 爆到 67，而 round 1 定位到那道 anti-fusion 防護
（`_guard_route` 只對「已註冊 wire segment」防護）**其集合恆為空集**。
**在那格修好之前不要動這個 Phase。**

- [x] 3.1 確認前置：`reserve_wire_ok > 0`（round 7 treatment 量到 40，原 0/71）
      —— **但這一格不足以授權 3.2–3.4**，見下方 3.0。
- [ ] 3.0 **（round 11 新增的硬前置）** 先解 daisy_chain 的跨 net 熔接根因。
      round 11 在 scratch tree 重測（產品碼未改）：power rail 改走 drawn path 後
      `moved 0 → 20`（fused 15 / disconnected 5），歸因逐項量到
      **SIG_A 的 R1.1 R2.1 被熔進 GND**，熔接點 (161.29,96.52) / (161.29,120.65) /
      (184.15,120.65) 逐一指認為 **GND 的 pin site C2.2 / R4.2 / R3.2**。
      ⇒ 這正是 `BR_20260905` §8.5.2 的 open-circuit 缺陷，**在 wire 帳本修好之後
      仍然成立**。`_foreign_pin_points` 已在 HEAD（`kicad_emit.py:1902/1940`）
      卻沒擋住它——原因待查（本輪只量測不修）。
      **3.2/3.3 在這格綠之前不要動。**
- [ ] 3.2 `composer.py` 的 power net 分支讀 `render_plan`
- [ ] 3.3 `local_star` / `daisy_chain` 兩種展開的幾何實作
      —— ⚠ 這會是 `_PERPENDICULAR_OK_KINDS` / `path_clear` perp 豁免的
      **第一個非既有呼叫端**。若 hop 不經 `_guard_route`，T 接觸會漏成跨 net
      短路且無任何告警（見 `occupancy.py` `path_clear` docstring 第 3 句）。
- [ ] 3.4 真板驗收：btdongle GND `daisy_chain` 後，`#PWR` glyph 數下降、
      junction 上升，且 **fidelity `moved` 維持 10**（不得因此惡化）
      —— **狀態：`not-run`，不是 `pass`。** 本 repo **無 btdongle fixture**
      （round 11 量測：`find . -iname '*btdongle*'` → 0 命中；控制組
      `find tests -name 'test_fidelity*'` → 5 檔，證明搜尋窗口是真的）。
      `btdongle` 只以**字串**存在於 `PROVENANCE.md` / `readability_gate.py` /
      `test_consumer_fork_drift.py` 與本包四份 md。
      **判準不降級**（dispatcher round 11 裁決）：真板 fixture 的取得歸
      dispatcher（`thesmart_products` 為 GUEST repo，本包不得碰）。
- [ ] 3.4a 合成 fixture 檢查（**輔助，非驗收**）：以本 repo 內合成的 power-heavy
      spec 量 `#PWR` glyph / junction / `moved`。
      **它不是 3.4、不能替代 3.4、通過它不構成 Phase 3 的驗收。**
      理由：本 repo 三個月 40 張 BR 的形狀就是「每一格都綠、板子畫不出來」；
      把真板判準改寫成合成判準，是那個模式的下一次發作。

## 4. Consumer 遷移與收尾

- [ ] 4.1 thesmart_products btdongle 改用 `declare_circuit`（分階段，不強制一次全遷）
- [ ] 4.2 `specs/architecture.md` 同步：C03 上游新增「宣告層」
- [ ] 4.3 event log 收尾一筆
- [ ] 4.4 KB 蒸餾判定：本包的跨 repo 教訓是
      「入口缺完整性檢查時，下游每個關卡各自發明容錯，而每種容錯的失效各自成為一張 BR」
      —— 這條換 repo 換題目都成立，應蒸
