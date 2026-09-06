# Errors: eda-bridge_draftsman-series-divider-wireable

## Outcome Codomain

**這一節在實作之前寫，不是實作之後補。** 理由是 `proposal.md` §Why 量到的那件事：
上一個空缺長出了 13 張 BR，成因不是某個函式寫錯，而是**沒有人在入口處問
「這份輸入完整嗎」**，於是每個下游關卡各自發明容錯，而每一種容錯的失效各自成為一張 BR。
`declare_circuit` 是新的入口，若它自己不先宣告完整的結束狀態集合，它會複製同一個病。

`declare_circuit` 的回傳物件恆帶 `status` 欄，值域封閉，五類齊備。
底層的完整性 gate 是**獨立模組**，自己也有完整值域——它回三態而非 bool，
所以它必須自己列一組，不能被上層的 `status` 代表。

| Module | Value | Class | Means | Emitted at |
|---|---|---|---|---|
| declare_circuit | `"ok"` | ok | 展開成功、完整性 gate 全綠、spec 可餵 compose | `declare.py::declare_circuit` 結果組裝（GRAFCET step 9） |
| declare_circuit | `"rejected"` | failed | 跑了、判定不通過。**帶 `errors[]` 非空** | `declare.py::declare_circuit` 拒絕出口（GRAFCET step 10 / step 7） |
| declare_circuit | `"not_run"` | not-run | **根本沒展開**：`declarations` 缺欄、schema 不合、引用了未宣告的 ref | `declare.py::_validate_input`，在展開器被呼叫**之前**（GRAFCET step 2） |
| declare_circuit | `"empty"` | empty | 跑完了，但 `declarations` 是空陣列 ⇒ 產出 0 net 0 node | `declare.py::_expand` 入口的顯式分支，**不與 `ok` 共用**（GRAFCET step 4） |
| declare_circuit | `"indeterminate"` | indeterminate | 展開成功、**`spec` 照常產出**，但**有 gate 無法判定**（見下） | `declare.py::declare_circuit` 降級出口（GRAFCET step 12） |
| completeness_gate | `"pass"` | ok | 每支已宣告的腳恰好出現一次 | `declare.py::check_completeness` 回傳（IDEF0 A4） |
| completeness_gate | `"fail"` | failed | 有缺項或重複，`missing[]` / `duplicated[]` 非空 | `declare.py::check_completeness` 回傳（IDEF0 A4） |
| completeness_gate | `"not_run"` | not-run | 展開在此之前就失敗，gate **從未被呼叫**——與「檢查過且全綠」必須分得開 | `declare.py::declare_circuit` 早退路徑，gate 呼叫點之前 |
| completeness_gate | `"vacuous"` | empty | `components[] == []` ⇒ gate 有跑但無腳可檢；**不得回 `pass`**（零元件全綠是假綠燈） | `declare.py::check_completeness` 零元件分支 |
| completeness_gate | `"unknown"` | indeterminate | symbol 載不到 ⇒ pin 清單未知 ⇒ 無法判定該元件 | `declare.py::check_completeness` symbol 解析失敗分支 |

### 為什麼 `E_SERIES_TOO_SHORT` 與 `E_RAIL_SCOPE_UNKNOWN` 是 `not_run` 而非 `rejected`

**這兩列曾經寫成 `rejected`，是錯的，2026-09-07 修正。寫下理由是為了防止下一個人「修正」回去。**

兩者都在 `_validate_input` 被擋下來，**而展開器從未被呼叫**。
而 `not_run` 在本表的定義逐字就是這件事：「根本沒展開」。

差別不是語意潔癖，是**呼叫端會做出不同的事**：

- 讀到 `rejected` 的呼叫端會以為宣告已經被展開過、`provenance` 與 `render_plan` 有意義，
  並可能拿那些部分結果繼續做事——但它們都是空的。
- 讀到 `not_run` 的呼叫端知道要回頭修輸入、重跑。

這正是 codomain 契約要防的第一件事：**「跑了且判定不過」與「根本沒跑」不得共用同一個輸出。**
若日後有人想把它們改回 `rejected`，先問：這兩個錯誤發生時，`_expand` 有沒有跑過？
沒有，那就不是 `rejected`。

### 為什麼 `empty` 必須與 `ok` 分開

`declarations: []` 會產出一份語法合法的空 spec，而 `BR_20260730b` 記錄過
**「空 spec 四閘齊綠」**——四個 gate 全部通過一份什麼都沒有的輸入。
`ok` 與 `empty` 共用同一個 status 就是那張 BR 的複製。

### `indeterminate` 仍然給 spec —— 「驗不了」不等於「產不出」

**這一格 2026-09-07 修正。原本 `indeterminate` 回 `spec=null`，是錯的。**

`spec` 是**宣告的函數，不是 symbol library 的函數**。`{components, nets, nc}` 的每一個欄位
都來自 caller 宣告的內容——沒有任何一格需要知道 `Device:R` 有幾支腳。
pin list 只用在**一件事**：完整性 gate（DD-5「每支腳恰好出現一次」）。

原本的寫法把兩件事綁在同一個 return 上：

```
檢不了完整性  ⇒  連 spec 都不給
```

**因果方向是反的**，而代價是實測到的：lean core 容器沒有 KiCad symbol library
（`/usr/share/kicad/symbols` 不存在，EE worker 則有 224 個），於是它**什麼都宣告不了**——
即使宣告拓樸根本不需要 KiCad。

這與本檔 `vacuous` 那一格是**同一個病的不同外觀**：

| | 兩個被混在一起的事實 | 共用的輸出 |
|---|---|---|
| `vacuous` | 「零元件所以沒得檢」 vs 「檢過了全對」 | `pass` |
| 本格 | 「完整性未驗」 vs 「產不出 spec」 | `spec=null` |

**修法**：`indeterminate` 照常給 `spec`，語意維持不變——
缺的是**判決**（verdict），不是**產物**。`completeness.verdict` 仍為 `unknown`、
`unknown[]` 仍逐筆列出讀不到的 symbol，所以沒有任何一格宣稱這份 spec 被背書過。

**為什麼不另立第六個 status**：`indeterminate` 的定義本來就是「跑了，判不出來」，
它從未承諾「所以我不給你產物」。真正壞掉的是實作，不是值域。
多開一格會讓契約表變成「四個正常態 + 兩個各自解釋 spec 有沒有」，
而那正是 codomain 契約要消滅的東西。

### `indeterminate` 的具體來源（不是佔位）

- 某個 `ref` 的 symbol 載入失敗 ⇒ 拿不到 pin 清單 ⇒ **無法判定該元件的腳是否都被指派**。
  這時不得回 `ok`（假裝完整），也不得回 `rejected`（可能只是 symbol path 沒給），
  必須回 `indeterminate` 並在 `unknown[]` 列出是哪些 ref、為什麼。
- `bridge` 引用的 net 名在本次宣告中不存在，但可能由 caller 稍後併入更大的 spec。

### 「進行中」不存在，故不需要心跳

`declare_circuit` 是同步純函式，沒有任何意思是「進行中」的狀態值。
（code-thinker §12 要求「閂要配心跳」，此處以「不存在該類值」滿足，不是略過。）

### 每個 gate 自己也回三態

完整性 gate 不回 bool。回 `pass` / `fail` / `unknown`，理由同上：
`fail` 與 `unknown` 需要不同的修法（改宣告 vs 給 symbol path），
共用一個 `False` 會讓呼叫端無法分辨。

---

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `E_PIN_UNASSIGNED` | 已宣告元件的某支腳，既不在任何 net 也不在 `nc[]` | `status="rejected"`，`errors[]` 列 `["U1.14","U1.16"]` 全部缺項，**不只第一個** | 補 `connect`/`bridge`/`rail` 宣告，或加入 `no_connect` |
| `E_PIN_MULTI_NET` | 同一支腳出現在 >1 條 net | `status="rejected"`，列出該腳與它所屬的全部 net 名 | 修正宣告；這是**電氣矛盾**不是風格問題 |
| `E_REF_UNKNOWN` | 宣告引用了不在 `components[]` 的 ref | `status="not_run"`（展開前就擋） | 補元件宣告或修正 ref 拼字 |
| `E_PIN_UNKNOWN` | 宣告引用了該元件 symbol 沒有的 pin 編號 | `status="rejected"` | 對照 symbol pin map 修正 |
| `E_NET_NAME_COLLISION` | 自動衍生的中間節點名撞上使用者宣告的 net 名 | `status="rejected"`，列出撞名 | 改宣告的 net 名（衍生名規則固定，不讓步） |
| `E_DIVIDER_TAP_DEGENERATE` | 分壓的抽頭接回自己的上端或下端 | `status="rejected"` | 這是**必抓**的一格，見下方失效模式表 |
| `E_SERIES_TOO_SHORT` | `series.chain` 少於 3 項（頭尾是 net，中間至少一個元件） | `status="not_run"`，並回顯它拒絕的 chain 內容 | 兩個 net 沒有元件是 `connect`，不是 `series` |
| `E_RAIL_SCOPE_UNKNOWN` | `rail.scope` 列了不存在的 ref | `status="not_run"`，**一次列出全部**未知 ref 而非只第一個 | 修正 scope，或補上缺的元件宣告 |
| `E_PROVENANCE_ORPHAN` | 輸出的某個 node 沒有對應的宣告來源 | `status="rejected"`，**這是引擎自己的 bug**，不是使用者錯 | 內部斷言失敗；不得放行（天條 §2.2 No fabrication） |
| `E_SYMBOL_UNRESOLVED` | 元件的 symbol 載不到，pin 清單未知 | `status="indeterminate"`，`unknown[]` 列 ref + 理由 | 給 `symbol_dirs`，或接受降級判定 |
| `W_RENDER_HINT_IGNORED` | 給了 `render` 但目前 Phase 尚未接線 | **warning 非 error**，`render_source:"default"` | 資訊；Phase 3 前預期會出現 |

---

## 「語法合法但電路錯誤」——誰抓得到，誰抓不到

**這一節是本包的誠實邊界。** dispatcher 明確要求：「沒抓到」也是一個必須被寫出來的狀態。

| agent 寫錯的形狀 | 誰抓到 | 什麼時候 |
|---|---|---|
| 電容跨在兩個**不存在**的 net | `E_REF_UNKNOWN` / `E_NET_UNKNOWN` | 展開前，`not_run` |
| 分壓抽頭接到自己 | `E_DIVIDER_TAP_DEGENERATE` | 展開期，`rejected` |
| 某支腳忘了接 | `E_PIN_UNASSIGNED` | 完整性 gate，`rejected` |
| 同一支腳接到兩條 net | `E_PIN_MULTI_NET` | 完整性 gate，`rejected` |
| 上拉電阻接到 GND 而非 VCC | **本層抓不到** | 下游 ERC 可能報 power 衝突；**不保證** |
| 5V rail 接到 3V3 pin | **本層抓不到** | 需 datasheet gate / SPICE；本包不做 |
| 去耦電容接在錯的 IC 旁 | **抓不到，且無人抓** | 電氣上完全合法，只有人看得出來 |
| 分壓比例算錯（10k/10k 卻要 3.3V） | **抓不到** | `design_suggest` / SPICE 可算，但需另外呼叫 |
| 整個子電路漏掉一顆必要元件 | **抓不到** | `prd_bom_crosscheck` 部分覆蓋；宣告層無從知道「應該有什麼」 |

**最後三列是本包明確不解決的**，寫在這裡是為了讓它們**不能被讀成已解決**。
`atopile` 的 interface 型別檢查也擋不住第 6 列（名目型別只擋 I2C↔Power，
不擋 5V↔3V3）——這是整個領域的現況，不是本包的退讓。

**因此**：`status="ok"` 的正確讀法是
**「這份宣告內部一致且完整」**，不是「這個電路是對的」。
result 物件的欄位命名必須反映這件事（用 `completeness` 不用 `valid`），
否則下一個讀它的 agent 會把「完整」讀成「正確」——而那正是第 41 張 BR。

## 驗證 ledger 行為必須走 `compose_schematic`，不可走 `emit_kicad_schematic` 直呼

**這兩條路徑對同一個缺陷會給出相反的讀數，而兩者都叫「跑了一次 emit」。**

`emit_kicad_schematic(..., ledger=None)`（每一個非 composer 呼叫端）會**自建**一個空帳本，
裡面**沒有任何 `body` rect**——body 是 composer 在擺件階段落的。於是任何
「wire rect 與元件 body 相撞」類的缺陷，在直呼路徑上**天生不可能重現**。

round 7 實測（同一份 HEAD、同一支探針，只換入口）：

| 入口 | `reserve_wire_ok` | `ledgergate_FALSE` | 讀起來像 |
|---|---|---|---|
| `emit_kicad_schematic` 直呼 | 4（FAIL 2） | 9 | **一切正常** |
| `compose_schematic` | **0**（FAIL 20，conflicts `{body: 20, pin_extent: 4}`） | **0** | 帳本 wire 層全空、碰撞偵測是死的 |

下面那行才是真相；上面那行令人安心且完全錯誤。

**結論**：任何只走 emit 直呼的測試，對「帳本 / 佔用 / 碰撞」這一整類缺陷是**結構性盲**的
——它不是覆蓋率不足，是那條路徑上根本不存在被測的那個條件。
要驗 ledger 行為，入口必須是 `compose_schematic`（或自行注入帶 body 的外部 ledger）。
