# Errors: eda-bridge_draftsman-series-divider-wireable

## Outcome Codomain

**這一節在實作之前寫，不是實作之後補。** 理由是 `proposal.md` §Why 量到的那件事：
上一個空缺長出了 13 張 BR，成因不是某個函式寫錯，而是**沒有人在入口處問
「這份輸入完整嗎」**，於是每個下游關卡各自發明容錯，而每一種容錯的失效各自成為一張 BR。
`declare_circuit` 是新的入口，若它自己不先宣告完整的結束狀態集合，它會複製同一個病。

`declare_circuit` 的回傳物件恆帶 `status` 欄，值域封閉，五類齊備：

| 類別 | `status` 值 | 意義 | **排放點** |
|---|---|---|---|
| ok | `"ok"` | 展開成功、完整性 gate 全綠、spec 可餵 compose | 展開器尾端，gate 判定後唯一出口 |
| failed | `"rejected"` | 跑了、判定不通過。**帶 `errors[]` 非空** | 完整性 gate（DD-5）與展開期 raise 的收斂點 |
| not-run | `"not_run"` | **根本沒展開**：`declarations` 缺欄、schema 不合、引用了未宣告的 ref | 入口參數驗證，在展開器被呼叫**之前** |
| empty | `"empty"` | 跑完了，但 `declarations` 是空陣列 ⇒ 產出 0 net 0 node | 展開器入口的顯式分支，**不與 `ok` 共用** |
| indeterminate | `"indeterminate"` | 展開成功但**有 gate 無法判定**（見下） | 每一個 gate 各自回三態，任一格 `unknown` 即整體降為此值 |

### 為什麼 `empty` 必須與 `ok` 分開

`declarations: []` 會產出一份語法合法的空 spec，而 `BR_20260730b` 記錄過
**「空 spec 四閘齊綠」**——四個 gate 全部通過一份什麼都沒有的輸入。
`ok` 與 `empty` 共用同一個 status 就是那張 BR 的複製。

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
| `E_SERIES_TOO_SHORT` | `series` 少於 2 個元件 | `status="rejected"` | 用 `connect` 而非 `series` |
| `E_RAIL_SCOPE_UNKNOWN` | `rail.scope` 列了不存在的 ref | `status="rejected"` | 修正 scope |
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
