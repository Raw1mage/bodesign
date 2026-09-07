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

## Vacuous 的三次出現：通過條件在真實輸入上不成立

本包最該留給下一個人的東西。三格外觀完全不同，**形狀是同一個**：
一個檢查存在、寫得對、review 看不出問題，而它**在真實輸入上永遠安靜**。

| # | 何處 | 通過條件為何不成立 | 它看起來像什麼 |
|---|---|---|---|
| 1 | `declare.py::check_completeness` 零元件分支 | `components[] == []` ⇒ 沒有腳可檢 | `pass`（全綠） |
| 2 | round 13 每片段標籤（fix 前） | 單片段時 `segments[0]` 就是全部 ⇒ 新舊碼 byte-identical | 測試綠（**直到某個 hop 真的被擋**才會紅） |
| 3 | `_assert_no_cross_net_junction()` @ `:2134` | 呼叫點在 power net 進 `fusion_registry`（`:2251`）**之前** | 沒有輸出（連 predicate 都沒進去） |

第 3 格的量測（round 18-19，`$XDG_RUNTIME_DIR/r19-lategate/`）：

- **原始 defect-1 那塊 13 件板上 `predicate_calls=0`**——這顆 assert 在本線的核心
  fixture 上**從來沒執行過** predicate 本體。不是「跑了但沒抓到」。
- enforcer 執行時 registry ＝ `{SIG_A, SIG_B, SIG_C}`；emit 結束時 ＝
  `{GND(13 segs), SIG_A, SIG_B, SIG_C, VCC(5 segs)}`。**power net 從不在它的視窗內。**
- 判別對（同一套注入機制，只換受害 net）：注入 SIG_A 線段中點 ⇒ **raise**；
  注入真實 GND 線段中點 ⇒ **不 raise**；同一份 GND 幾何但偏離線段 ⇒ 不 raise。

**為什麼 review 看不出來**：三格的程式碼本身都是對的。缺陷在
**「這一行」與「它要回答的問題」這一對**上——第 3 格的謂詞完全有判別力，
錯的只是呼叫位置。所以永遠不要問「這個檢查寫得對嗎」，要問
**「它在該紅的時候真的會紅嗎」**，而且要對**真實輸入**問，不是對想像中的輸入問。

**可機械套用的防線**：任何斷言／gate 交付前，附一格「它確實在真實 fixture 上
執行過」的讀數（進入計數／看見了什麼），以及一格「破壞前提時它會紅」的變異控制組。
兩格都缺時，「從未觸發」與「觸發了但沒排放」共用同一個沉默。

### 第四次：差一點被我們親手造出來（round 21，被攔下）

前三格是發現的，這一格是**差點寫進去的**。round 20 量到逃逸樁觸發過寬後，
我推薦把觸發條件收窄成「pin 落他 net 線上 **且該點有 junction** 才出樁」。

dispatcher 否決了，理由逐字成立：**junction 落點由 multinode 迴圈決定，那是出樁
決策點的下游**。決策當下該點還沒有 junction ⇒ 條件恆為假 ⇒ 樁永不產生。
我複查 code，找不到任何更早的 junction 落點，**所以我接受否決、不請求重議**。

**為什麼值得寫進來**：那個提議在當下看起來是「把謂詞收緊到電氣必要性」——
比原版更精確、更節制、更符合直覺。而它的實際效果是讓整個修法變成死碼，
且不會有任何測試會紅。**第四次與前三次的差別只在有沒有人問「這個條件在真實
輸入上何時成立」**。收窄一個謂詞時，要問的不是「這樣是不是更精確」，
而是「新條件在產生順序上拿得到它需要的資訊嗎」。

## 驗證與防護措施自身的失效（round 21-23）

**這一節與上一節是同一族的另一半。** §Vacuous 講的是「檢查永遠不紅」；
這一節講的是「檢查紅得很漂亮，但它讀的東西是假的」——以及**防護措施自己壞掉**
而它的壞掉態與正常態共用同一個輸出。

**分兩類**：前半（四版報廢）是**探針**自失效；後半（round 23 兩格）不是探針，
是**留給未來的防護措施**——docstring 是給未來讀者的防護，封存 patch 是給未來
復活的防護。**兩者的共同形狀相同：成功態與失敗態共用同一個輸出。**

為了回答「defect 1 現在到底有沒有在發生」，我寫了一支拋棄式探針。
**它在四個獨立版本上給出四種自信、可讀、錯誤的答案：**

| 版本 | 回報什麼 | 真正的病 | 它看起來像什麼 |
|---|---|---|---|
| v1 | `FUSED=4 SEPARATE=0` | regex netlist parser 在 12 件板回 `nets=2`、另一塊回 `nets=0`；注入的 junction 用了手寫多行格式，emitter 從不那樣寫 | 五格裡四格一致的紮實結論 |
| v2 | `flipped=0 did_not_flip=0` | parser 修好了，但**控制組欄位是空的**——沒有 SEPARATE 案例可翻轉 | 「控制組沒紅」（實為從沒執行） |
| v3 | `NEG CONTROL NO_CTLPINS` ×5 | 控制組樣本 `ctlpins` 全空 | 「控制組沒紅」（同上，不同成因） |
| v4 | `kept_count=0` | 探針自己 `NameError: pathlib`（模組用 `from pathlib import Path`）；20 行 `PROBE_FAILED` 混在測試點點裡，rc 本來就非零 | 「沒有命中」 |

**v1 最危險**：`FUSED=4` 與最終答案**相反**。若當時回報，dispatcher 會據以判定
「state A 存在而幾何偵測看不見」，推翻已 commit 的 round 8/9 交叉放行——
**一個完全錯誤、而且很有說服力的重大發現。**

### 共同形狀

**錯不在判準，在判準的輸入被上游悄悄污染**，而判準本身跑得很正常。
`parsed_nets=0`、`ctlpins=[]`、`own=None`、`kept_count=0` —— 這四個都是
**「輸入是空的」的外觀**，而每一個當時都被讀成了資料。

### 最貴的一格：全體皆 None

round 21 我報「B=55，其中 `own_net` 全部是 `None`」時就該起疑。
真正的原因是 `_all_pin_points` 的 id 是 `'REF.PIN'` **字串**，而 `net.nodes`
裝的是 `('REF','PIN')` **tuple**，`_nid in own_members` **恆為 False**，
於是每一支 pin 都被算成「不屬於任何 net」。修正後 B 從 55 降到 34。

> **全體皆 None 是「判定壞了」的典型外觀，我當時讀成了「這些 pin 真的沒有 net」。**

這句不要改寫成通則——通則沒有判別力，這句有。

**可機械套用的防線**：判準跑之前，先斷言**它的輸入非空且型別正確**。
一個回傳 0／空集合的判準，要能分辨「量到 0」與「根本沒東西可量」。

### 規則寫在筆記裡不會自我執行（tracebacks 復發）

round 12 我踩過一次探針自失效（`atexit` NameError 讓 `run_rc=0` 卻什麼都沒寫），
當時**我自己寫下**「往後每次 instrumented run 都要數 `tracebacks=N`」。
**round 22 第一次跑時我忘了數**，於是 `kept_count=0` 差點被讀成「沒有 B 命中」。

**教訓不是「要更仔細」**——那不可執行。是：
**要嘛把規則放進 runner（讓它自動執行），要嘛它就是會被忘掉。**
一條只存在於文件裡、依賴人記得的驗證規則，其失效是時間問題而不是機率問題。

### 防護措施自身的兩格失效（round 23，A/B 分離時抓到）

前面四版都是**探針**。這兩格不是探針，是**留給未來的防護措施**——
而它們各自壞在一個「看起來成功」的輸出上。

**(1) docstring 懸空引用。** A（enforcer 移位）與 B（逃逸樁）分離時，
我寫進 `_point_on_segment` 的 T1/T2 註解引用了 `exempt_interior_pt`——
**那個識別符只存在於 B**。A 單獨 commit 後，那句話會指向一個樹上不存在的符號。

- **為什麼 grep 抓不到**：分離驗證用的是「B 的識別符在 A-only 檔裡計數為 0」。
  而懸空引用**正是** B 的識別符出現在 A 裡，所以它讓那格計數變成非零——
  我當時把非零讀成「還沒切乾淨」，差一步就要把整句刪掉而不是修正引用。
- **形狀**：`grep` 回報的是**符號在不在**，不是**符號指向的東西在不在**。
  一份引用不存在符號的註解，其 grep 讀數與一份正確註解**完全相同**。
- **防線**：切分之後要**讀**留下來那份的內容，不能只數識別符。

**(2) `git apply` rc=0 而目標檔沒有被建立。** B 的封存 patch 第一版由
`git diff --no-index a/ b/` 產生，兩側 header 路徑不對稱
（`a/home/pkcs12/...` vs `b/run/user/1000/...`）。`git apply -p1` 回 **rc=0**，
bytes 落進 `verify_b/run/user/1000/…` 這條垃圾路徑，**目標檔根本沒被建立**。

- **形狀**：「patch 套用成功」與「patch 重建出正確的檔」**共用 rc=0**。
- **代價的時間點最壞**：封存的用途是「未來要復活時拿出來」。這一版若進樹，
  失敗會在**最需要它的那一刻**才被發現，而那時原始工作區早已不存在。
- **防線（本輪實際採用）**：封存驗證不是「apply 回 rc=0」，是
  **apply 到 pristine HEAD 副本後與錨定的全量檔逐字相同**，
  外加一格控制組（HEAD vs 全量檔必須有差異，證明比對不是恆真）。

**兩格的共同教訓**：`errors.md` 前面幾節管的是「量測工具會騙人」。
這兩格說的是**防護措施也會**，而且更難察覺——探針的錯誤當輪就會影響結論，
防護措施的錯誤要等到未來有人依賴它時才爆，那時沒有人在看。

### 探針有假陽性時，差值仍可用、絕對值不可用（round 26）

`LED_WIFI` 的 fragment label 覆蓋檢查回報 `fragments_with_no_label=50`。
那個數字**是錯的**：`#PWR` power-port symbol 會為銅箔命名，但不發出 `(label` block，
所以我的解析器把每一段這樣的銅箔都算成「無標籤 fragment」。

**但那格證據仍然成立，因為我沒有用絕對值**：

```
HEAD    fragments_with_no_label = 50
A-1     fragments_with_no_label = 50      ← 差值 0，無回歸
LED_WIFI 具名 fragment          0 → 1     ← 這才是被主張的東西
```

**判準**：一支探針若有**與 treatment 無關的系統性假陽性**，該假陽性在 base 與 treatment
上等量出現，於是**差值把它消掉**。所以：

- **可用**：`Δ = treatment − base`（假陽性同時出現在兩邊，相減歸零）
- **不可用**：`treatment` 的絕對值（它含有一個與被測命題無關的常數項）

**前提是那個假陽性真的與 treatment 無關**——若改動本身會改變假陽性的數量，
差值也會被污染。本格的理由：`#PWR` symbol 的數量由 placement 決定，
而本次改動不碰 placement（⑦ 已證元件座標逐字不變）。

**權威判準另有其人**：這格只用來說「沒有回歸」，
「net 成員對不對」由 `kicad-cli` netlist export 按 size 仲裁，不由這支探針決定。
**一支已知有假陽性的探針，不得升格為權威判準，只能當差分感測器。**

### 第八次，但不同族：失敗的是**工具用法**，不是探針邏輯（round 27）

前七次都是「我寫的探針邏輯壞了」。這一次不同——**探針邏輯沒有錯，是我呼叫工具的方式錯了，
而工具的錯誤訊息長得像資料。**

量測「`packages/eda-bridge/` 裡有沒有階層 sheet 原語」時：

```
grep -rc -- "$TOK" packages/eda-bridge/bodesign_eda_bridge/ --include=*.py
  → grep: --include=*.py: No such file or directory
```

`--include` 被這台機器的 grep 當成**檔名參數**而非旗標（前面有 `--` 終止符，
是我自己放的），於是它去找一個叫 `--include=*.py` 的檔案並失敗。
而我的迴圈把空結果印成 `(none)`：

```
TOKEN[hierarchical_label]:
  (none)              ← 這行的意思是「工具沒跑成功」
TOKEN[sheetpath]:
  (none)              ← 這行的意思也是「工具沒跑成功」
```

**而「這個 token 在樹裡真的不存在」印出來逐字也是 `(none)`。**
我差一步就要把 `hierarchical_label: (none)` 當成「本 repo 沒有階層原語」的證據——
**結論碰巧是對的，但支撐它的那格讀數是空的。**

- **為什麼前七次的防線擋不住**：`tracebacks=N` 只數 Python traceback，
  grep 的錯誤訊息不是 traceback。`rc` 也沒用——迴圈裡每個 token 各跑一次，
  整串的 rc 是最後一個的。
- **為什麼比前七次更難察覺**：前七次錯的是我寫的邏輯，重讀自己的程式碼看得出來；
  這次我的邏輯正確，錯的是**一個我以為自己會用的工具**。重讀程式碼只會看到
  「grep 這個 token，沒有就印 none」——完全合理。
- **正解（本輪實際採用）**：改用 grep tool 重跑。它的零結果會回報**搜了幾個檔**，
  所以「搜了 40 個檔、0 命中」與「include glob 把窗口清空了」分得開；
  bash 的 `grep -c` 沒有這格揭露。
- **通則**：**凡是「工具失敗」與「量測結果為零」會落到同一個顯示字串的地方，
  該處必須額外印出工具自己的成敗**（rc 逐次捕捉、或 stderr 非空檢查），
  否則那個零沒有判別力。而最省事的作法是——**純搜尋／計數一律走 grep tool，
  它內建這格揭露；bash 只留給只有 bash 做得到的事。**

---

## 五格「讀數看起來像資料，其實是判準或母體壞掉」（round 29-30）

前面八格講的是「探針失效」。這五格講的是**探針跑得很好、輸出很漂亮、而它量的東西
不是我以為的那個東西**。它們的共同代價：每一格單獨看都會被當成發現寫進報告。

### ① 名字不是身分，節點集合才是（`pile3=167`）

把「真板有而我們 spec 沒有的 net」用**名字**比對，得到 `pile3=167`。

實際上真板有 19 條 net 沒有被人命名，KiCad 自動命名成 `Net-(U1-ISET2)`；
我們的 spec 對同一條線命名為 `ISET2`。於是**同一條 net 被同時算進兩個方向**——
「真板有我們沒有」算一次、「我們有真板沒有」再算一次。167 這個數字裡沒有一條是真的缺口。

改用 `frozenset{(ref, pin)}` 當身分後，**27 條 spec net 與真板 27/27 精確對應，
`pile3` 歸零**。

- **判準**：兩份資料要比對「同不同」時，先問「我用來當身分的那個欄位，
  兩邊是不是由同一個東西產生的」。名字是**人或工具給的**，會各給各的；
  節點集合是**電路本身**，兩邊只能一致。
- **為什麼難察覺**：167 這個數字本身很有說服力，而且它「解釋」了差距。
  一個能解釋現象的錯誤答案，比一個沒有答案更難被推翻。

### ② 啟發式歸屬會結構性偏向最大的類別（`?GND=120`）

per-net 線段歸屬的第一版，遇到無法解析的 wire 就退回啟發式：
**取該線段觸及的元件所屬 net 裡最常見的那一條**。

「最常見」在一塊有 49 支腳接地的板子上永遠是 `GND`。於是那支探針把 120 條
（426 的 28%）無法歸屬的線全部倒進 `GND`——**而輸出讀起來就是一格正常的統計數字**，
沒有任何標記說這 120 是猜的。

- **判準**：**任何 fallback 分支都要問「它的偏差往哪個方向」**。
  一個往最大類別偏的 fallback，會讓最大的那一類看起來更大，
  而那正是你最可能想下結論的地方。
- **正解**：改用 `(ref, pin)` 精確解析，`?` 歸零。
  **無法歸屬時要留在「無法歸屬」這一格，不要分配給任何人**——
  `unattributed=N` 是資料，`GND=N` 是捏造。

### ③ `all_label=False` 是無效組態：「關掉旗標」與「旗標沒有作用」共用同一個輸出

要量「政策全部關掉會畫幾條線」，第一版傳 `spec["all_label"]=False`。
讀數與 HEAD baseline **逐字相同**。

當時的兩個解釋分不開：(i) 政策關掉後剛好沒有變化、(ii) 這個旗標根本不是那三條政策的開關。
答案是 (ii)——`all_label` 只控制 `composer.py:2178` 的 `if all_label:` 分支，
`False` 就落回同一段政策碼，它本來就是預設值。

- **判準**：**一個「關掉某功能」的組態，必須先證明它開著的時候會改變讀數。**
  `all_label=True` 實測 `wire 120→64`、`global_label 43→75`——**有了這格，
  `False` 的無變化才有意義**（它證明旗標有效而 `False` 是 no-op），
  沒有這格就只是一個不知道有沒有接上的開關。
- **同族**：這是「控制組必須能失敗」在**組態**上的版本。

### ④ 116 vs 120：讀磁碟舊產物 vs 讀當前 code 的產出（快照歧義）

round 24-26 的每一份報告都寫 `116 wire`，round 29 重跑得到 `120`。
兩邊都沒有量錯——**116 是 `0195950`（那格豁免修法）之前留在磁碟上的 `.kicad_sch`**，
120 是當前 code 跑出來的。

**兩者都是「一個 `.kicad_sch` 檔的 wire 數」，形狀完全相同，沒有任何標記說它是哪一版產生的。**

- **判準（AGENTS.md §6.1 快照歧義陷阱的又一例）**：
  **報告一個產物的統計值時，要一併報告「產生它的 code 是哪一個 commit」。**
  在一棵有人正在改 emitter 的樹上，昨天的輸出檔與今天的輸出檔長得一模一樣。
- **實害**：dispatcher 連續兩輪拿 116 當基準做裁決；差值 4 條線不大，
  但**如果那格修法改的更多，整個裁決的基準就是錯的而沒有人會發現**。

### ⑤ 同一顆 handler、同一個問題、兩個帶控制組的答案（170 vs 124）

這格是本節最重要的，因為**兩輪的控制組都是綠的**。

round 26 報「三條政策全拿掉 = 170 wire」，round 29 報「= 124」。對帳結果：
**它們拿掉的不是同一組東西，因為那個政策在系統裡有兩份實作。**

```
composer.py:2227     compose 階段算出 label_nets，當 kwarg 傳給 emitter
kicad_emit.py:1274   emitter 收到 label_nets 之後，又自己呼叫
                     capacity_plan.decide_route_policy 重算一次 cross-IC，
                     結果 OR 進 label_nets（:1282）
```

- round 26 的探針同時攔了兩處（wrapper 濾 `label_nets` **＋** 覆寫 `decide_route_policy`）
  → 政策真的全關 → **180**（今日 HEAD 重跑值；round 26 當時是 170）
- round 29 的探針只 patch 了 composer 那三條規則 → emitter 的重算原封不動、
  把 8 條 cross-IC net 又加回 label → **124**

**兩個數字都是對的，它們回答的是兩個不同的問題**：
「compose 端的政策關掉會怎樣」vs「這個系統的 cross-IC 政策全部關掉會怎樣」。

- **控制組為什麼沒抓到**：兩輪的控制組都是 **pass-through 必須複現 baseline**。
  那格只證明「我的 wrapper 沒有污染讀數」，**證明不了「我的 wrapper 涵蓋了全部的作用點」**。
  一個只攔一半的 wrapper，pass-through 時同樣完美複現 baseline。
- **判準**：**要「關掉某條規則」之前，先數這條規則在樹裡有幾個實作點。**
  ```
  grep -n "decide_route_policy" packages/    → 定義 1 + 呼叫 1（kicad_emit.py:1274）
  ```
  這格是**幾秒鐘的事**，而少做它的代價是一整輪的矛盾讀數 + 一張送到使用者面前的錯表。
- **機制層歸因**：`kicad_emit.py:1270-1274` 的註解逐字寫著
  「this decision's SINGLE SOURCE OF TRUTH is now the L2.5 capacity layer」——
  **它宣告自己是唯一真相來源，而 compose 端仍保留一份等價推導（`composer.py:2208-2231`）。
  兩份都在跑，OR 在一起。** 「已經去重了」這句註解本身是這格的誘因。
- **同族**：與第 ①-③ 格一樣，錯的不是判準，是判準的**作用面**與我以為的不同。

## 防護措施自身失效的第三、四例（round 35-36）

前兩例在 round 23（docstring 懸空引用、`git apply` rc=0）。那兩例壞的是
**留給未來的**防護。底下兩例壞的是**當輪正在用的**東西，而且它們各自壞在
一個「程式碼看起來完全正常」的地方。

### ⑥ `except` 把診斷資訊吞成一個合理值（round 35）

量 cross-IC 政策的邊際貢獻時，我呼叫 `_net_power_kind_names(names, None)`，
它對 `None` 丟 `AttributeError`（`'NoneType' object has no attribute 'get'`）。
我的 `except` 印了一行「composer helper failed」然後讓 `powerlike` 留在空集合。

```
powerlike = set()            ← except 之後的實際值
power-rail labelled : []     ← 於是 power-rail 一條都沒標到
final label_nets    : 12     ← 真值是 13
```

- **它回了什麼令人安心的值**：`12`。不是 0、不是負數、不是例外——**是一個
  和 13 只差一條的、完全落在預期範圍內的數字**。而 `label_nets` 本來就會隨
  政策組合浮動，所以 12 沒有任何一格看起來不對。
- **RCA（機制層）**：`except` 的設計目的就是**讓程式繼續跑**，而「繼續跑」
  正是它靜默的方式。前面所有失效模式裡，污染源都在被測系統或探針邏輯裡；
  這一例的污染源是**錯誤處理本身**——它是我為了「探針不要中途爆掉」而寫的，
  結果它把「helper 沒跑成」和「helper 跑了、回空」壓成同一個輸出。
- **偵測**：改傳 `{}`（一個 helper 能接受的空 dict）再跑一次，得 `powerlike`
  = `{'+3V3','GND','VBUS'}`，`label_nets` = 13。**兩次讀數不同 ⇒ 前一次的
  except 分支有實質作用**，而它在 log 裡只佔一行、混在正常輸出中間。
- **防線**：探針裡的 `except` **必須讓被吞掉的變數帶上「我沒被算出來」的標記**，
  不可以留在型別合法的預設值（空 set／空 dict／0）上。最低限度：`except` 之後
  把該格設成 `None` 並在最終輸出印它，讓「沒算出來」與「算出來是空的」分開。
- **與 `code-thinker` §12 的關係**：這正是 `not-run` 與 `empty` 塌成同一格。
  差別在於這次塌陷發生在**探針自己的產出狀態**上，不是被測模組上。

### ⑦ 宣告要 instrument 分支，實際只 instrument 了結果（round 36）

診斷 `power` 紙的 `CROSS_NET_JUNCTION_SHORT` 時，`probe3.py` 開頭逐字寫著
「INSTRUMENT THE BRANCH, not the result」，並宣告了三個計數器：

```python
SITE = {"interior_retry_true": 0, "guard_calls": 0, "guard_interior_ok": 0}
_real_guard = kicad_emit._guard_route if hasattr(...) else None
```

**然後從頭到尾沒有把 `_guard_route` 換掉，也沒有印 `SITE`。** 三個計數器是
死變數；`_real_guard` 取了值之後再也沒被使用。

- **它回了什麼令人安心的值**：探針正常跑完、`tracebacks=0`、其他三格證據
  （幾何、接觸點分類、整圖對照）全部有效且結論正確。**唯一沒有的是我宣告
  要量的那一格**，而它的缺席不會讓任何其他讀數看起來不對。
- **若我當時印了 `SITE`，會拿到三個 0**——而「那條分支沒走」與「我根本沒把
  recorder 接上去」**共用這個 0**。這是 §「缺席態與失敗態不得共用同一個輸出」
  的教科書形狀，發生在一支開頭就引用了該條規則的探針裡。
- **RCA（機制層）**：instrument 結果只需要包住一個**已經會被呼叫**的函式
  （`cross_net_junction_shorts` 我確實包了，而且有效）；instrument 分支需要
  **改變控制流上的一個點**。前者寫完就會有輸出，後者寫完若忘了接線，**輸出
  形狀與「接了但分支沒走」完全相同**。所以前者的疏漏會自己現形，後者不會。
- **偵測（可機械套用）**：任何 `SITE` / counter / flag 型的分支計數器，
  **在正控制上必須先看到非零才可信**。做法是拿一條**已知會走那條分支**的輸入
  跑一次（本例：round 26 量到 `exempted_at_site1=7` 的整圖路徑），
  看到非零，才有資格把 0 讀成「沒走」。
- **防線**：counter 宣告與 patch 動作**寫在同一個 code block 裡**，不要分開；
  並在每次輸出無條件印出 counter，**不管是不是 0**——一個從不出現在輸出裡的
  counter，與一個不存在的 counter，對讀者是同一件事。
- **代價**：這格缺席讓 A1 復活條件 2 的判定停在「判不出來」，而 dispatcher
  必須再派一輪才能拿到它。**一輪的成本，換一行沒寫的 `SITE[...] += 1`。**

### ⑦-b 接不上的時候怎麼辦：從唯一消費者讀出雙條件等價（round 37）

⑦ 說的是「宣告要 instrument 分支卻沒接上」。**本則是同一個事件的另一面：
為什麼接不上，以及接不上時正確的做法是什麼。** 兩則要一起讀。

**接不上的原因（機制層）**：`_guard_route` 是 `emit_kicad_schematic` 的
**內部閉包**（定義於 `kicad_emit.py:1647`），不是模組層級的屬性。
`monkeypatch` 只能換掉**模組屬性**；閉包在函式每次被呼叫時重新綁定，
外部沒有任何名字指向它。所以 `kicad_emit._guard_route = recorder` 這行
**不會報錯、不會有任何效果**——`hasattr(kicad_emit, "_guard_route")` 回 `False`，
而 `setattr` 只是替模組新增一個從未被讀取的屬性。

> **這正是 ⑦ 那三個死變數的成因**：`_real_guard = kicad_emit._guard_route if hasattr(...) else None`
> 的 `hasattr` 回 `False`，於是 `_real_guard = None`，而 `None` 是一個
> 型別合法、不會拋錯的值（⑥ 的形狀）。**「取不到」與「取到了但沒用」共用 `None`。**

**正確做法——不要從行為推，去讀原始碼找等價命題**：

| 步驟 | 本例的內容 |
|---|---|
| 1. 找旗標的**唯一消費者** | `interior_retry` 只在 `:1690-1692` 被讀，讀完只做一件事：決定傳給 `_segment_fuses` 的 `exempt_interior*` 參數 |
| 2. 找旗標的**唯一產生點** | `_guard_route(..., interior_retry=True)` 全樹只有 `:1920` 一處（`:1990` 有逐字註解說明它刻意不傳） |
| 3. 推出雙條件 | `_segment_fuses` 收到豁免參數 ⟺ 該次 `_guard_route` 呼叫帶了 `interior_retry=True` |
| 4. patch 可及的那一端 | `_segment_fuses` **是模組層級屬性**，可 monkeypatch。量它 ＝ 量到閉包 |

**這一步為什麼不是繞過而是等價**：繞過是「換一個相關的東西量，希望它跟著動」，
得到的是**相關性**；本例是先在原始碼上證明兩個命題互為充要（唯一消費者 + 唯一產生點
＝ 沒有第三條路徑能讓其中一邊成立而另一邊不成立），得到的是**等價**。
**差別在於前者要祈禱沒有旁路，後者已經把旁路數完了。**

- **它回了什麼令人安心的值**：`setattr` 到一個不存在的閉包名**不會拋任何錯**，
  探針照常跑完、`tracebacks=0`、其他讀數全部有效。**沒有任何東西會不一致。**
- **偵測（可機械套用）**：monkeypatch 之前先 `assert hasattr(mod, name)`。
  這一行把「patch 成功」與「patch 到一個不存在的名字」分開——
  沒有它，兩者都是靜默成功。
- **驗收**：等價推導完成後，正控制必須非零（本例 `exempt_calls=13`）、
  負控制為 0、**falsification 決定性**（豁免中性化後短路消失、
  `changed_verdict` 3→0）。**三格齊了才算量到分支。**
- **與 ⑦ 的分工**：⑦ 告訴你「counter 在正控制上必須先非零才可信」；
  本則告訴你**當 counter 永遠接不上時，該去原始碼裡找哪三樣東西**
  （唯一消費者、唯一產生點、可及的那一端）。
