# Observability: eda-bridge_draftsman-series-divider-wireable

## Events

每一則事件都對應 `errors.md` §Outcome Codomain 的一個排放點。
**沒有排放點的狀態是註解，不是狀態**——這一節是那張表的落地面。

| Event | 何時發出 | 攜帶欄位 |
|---|---|---|
| `declare.enter` | 入口參數驗證**之前**，無條件 | `n_components`, `n_declarations` |
| `declare.not_run` | schema 不合 / 引用未宣告 ref，展開器**未被呼叫** | `reason`, `offending_refs[]` |
| `declare.empty` | `declarations == []` 的**顯式分支** | — |
| `declare.expanded` | 展開器跑完，gate 之前 | `n_nets`, `n_nodes`, `n_derived_names` |
| `declare.gate.pass` / `.fail` / `.unknown` | 完整性 gate，**三態各自一個事件** | `unassigned[]`, `multi_net[]`, `unknown[]` |
| `declare.provenance_orphan` | 無主 node 偵測到（引擎自身 bug） | `orphan_nodes[]` |
| `declare.render_default_applied` | `rail` 未給 `render`，套用預設 | `net`, `applied="global_label"` |
| `declare.exit` | 回傳前，無條件，**無論成敗** | `status`, `elapsed_ms` |

**`enter` 與 `exit` 都無條件發出**（code-thinker §12：「每個步驟無條件發言，
只在成功時回報的步驟與從未執行的步驟不可分辨」）。
一則 `enter` 沒有配對的 `exit` ⇒ 展開器中途拋例外，那本身是可觀測的事實。

**instrument 分支，不是結果**：`declare.gate.*` 三個事件是三個不同的發射點，
不是同一個發射點帶不同欄位。理由是同一個 `status="rejected"` 可以由
`E_PIN_UNASSIGNED` 或 `E_PIN_MULTI_NET` 或展開期例外產生，
只有進入標記能指認是哪一條路徑走了。

## Metrics

| Metric | 量什麼 | 為什麼要這格 |
|---|---|---|
| `declare_status_total{status}` | 五個 status 各自的計數 | 若 `empty` 恆為 0 而 `ok` 異常高，代表 `empty` 分支從未被走到——那是 `BR_20260730b`「空 spec 四閘齊綠」的復發訊號 |
| `declare_unassigned_pins` | 每次呼叫的未指派腳數 | 直接量「輸入完整度」。本包存在的理由就是這個數字今天無人統計 |
| `declare_derived_names` | 自動衍生的中間節點數 | DD-3 的採用率；若恆為 0 代表 `series` 沒被使用 |
| `declare_render_source{source}` | `declared` vs `default` 的比例 | Phase 3 的前置指標：若 `declared` 恆為 0，`render` hint 接了也沒人用 |
| `declare_gate_unknown` | gate 回 `unknown` 的次數 | symbol 解析失敗率。這個數字高時，完整性判定本身不可信——**它是其他指標的信心係數** |

## 下游可觀測性的接點

`declare_circuit` 的 `provenance` 與 `render_plan` 兩個欄位**必須被
`compose_schematic` 的 result 透傳**（Phase 2），否則產出的 `.kicad_sch`
與產生它的宣告之間斷鏈，而那正是
`BR_20260802_compose_reports_no_provenance_of_the_bytes_it_consumed` 的形狀。

**已知缺口（誠實列）**：本包不改 `compose_schematic` 的 result 結構（Phase 1-2 範圍外），
所以在 Phase 2 完成之前，**宣告與最終圖面之間的鏈路只存在於呼叫端的記憶中**。
這是接受的暫時狀態，不是已解決。
