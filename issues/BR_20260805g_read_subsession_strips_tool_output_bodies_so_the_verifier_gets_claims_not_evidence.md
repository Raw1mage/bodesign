# BR_20260805g — `read_subsession` 剝除 tool output body，只留 200 字 preview，於是覆核者拿到的是主張而非證據

- **Status**: OPEN — 揭露缺陷；修復面不在 bodesign（`read_subsession` 由 opencode runtime 的 `system-manager` MCP 提供）
- **Severity**: HIGH — 它截斷的是 receipt discipline 的證據鏈本身：dispatcher 覆核 subagent 產出的**主要工具**回不了機器輸出原文，於是「量出來的」與「估的」共用同一個輸出
- **Owner repo**: opencode（本 repo 不可修）
- **Family**: G13-harness-disclosure
- **Filed**: 2026-08-05 by `ses_0300f19c6ffetKMrfXyQ125dou`（bodesign 值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH` 派工建檔）
- **Provenance**: 觸發事件（`ses_030159029` 取件 `ses_03019b6fe` 時取不到 `git status --porcelain` 原文）由派工的值星官 session 轉述；**本建檔 handler 未重跑該次取件**。但 §4 的實作面證據（`note` 字串、200 字切法、`outputBytes` 欄位存在性）為本 handler 於 2026-08-05 直接讀 opencode 原始碼實測，附 `file:line`。

**Related**:
- `BR_20260804m_read_subsession_does_not_mark_message_recency_so_history_reads_as_current_activity.md`
  （**同一工具、同一資料流**：804m 是「時間軸未揭露」，本張是「輸出內容未揭露」。同一 owner repo、同一交付面）
- `BR_20260805b_read_subsession_position_stays_oldest_after_the_cursor_advances.md`
  （**同一工具**的位置軸缺陷；該張 §7 已統計 `read_subsession` 在本 fleet 累積的獨立揭露缺陷數，本張使該計數再 +1）
- `BR_20260805a_pending_tool_call_input_summary_is_an_empty_object_so_in_flight_calls_are_unreadable.md`
  （**同一工具、同一段程式碼**：`inputSummary` 與 `outputPreview` 由 `packages/mcp/system-manager/src/index.ts` 的**同一個 map 回呼**產生（本 handler 實測：`outputPreview` 在 `:3244`，`inputSummary` 在同一 return 物件 `:3252`）。805a 管輸入端未揭露，本張管輸出端未揭露）
- `BR_20260805f_tmp_scratch_ban_lives_only_in_dispatch_prompts_so_it_does_not_stop_a_reflex.md`
  （**同一輪、同一 commit 建檔**，且互為因果：805f 第二個樣本的機器輸出之所以只剩「自述 41 行」，正是本張描述的剝除所致）

---

## 1. Symptom

`system-manager_read_subsession` 的回應 header 帶：

```
"note": "Tool output bodies stripped. Only assistant text, tool metadata, and
         output previews (first 200 chars) are included. See `window` for WHICH
         slice of the session these messages are."
```

⇒ 取件員／覆核者對每個 tool call 只能拿到 **前 200 字元的 preview**，拿不到任何機器輸出原文。

## 2. 實測後果（觸發事件）

`ses_030159029` 奉派取件 `ses_03019b6fe` 的稽核結論。派工單要求取回兩樣**原文**：

| 要取的原文 | 實際取到 |
|---|---|
| `git status --porcelain` 完整輸出 | 取不到——該次 call 的 200 字 preview 額度被同一批的 commit 輸出（665 bytes）佔滿 |
| `grep` 的機器輸出原文 | 取不到 |

取件員最後只能轉述被取件者的**自述數字**（「41 行」「40 行」）。

## 3. 為什麼這是缺陷，而不是合理的省 token 設計

省 token 本身合理。問題在**它與 receipt discipline 直接衝突**：

> dispatcher 必須親手覆核 landed bytes，`status=success` 是主張不是證據。

而 `read_subsession` 是 dispatcher 覆核 subagent 產出的**主要工具**。
剝掉 body 之後，dispatcher 拿到的**只剩主張**：
被取件者說「41 行」，取件員只能轉述「它說 41 行」，dispatcher 無從分辨這是量出來的還是估的。
**證據鏈在覆核工具這一環被截斷。**

更精確地說，這是本 family 的標準形狀——**兩態共用同一個輸出**：

| 讀者想分辨的兩態 | 實際看到 |
|---|---|
| 這顆 subagent 根本沒跑那個指令 | preview 裡看不到該輸出 |
| 它跑了，但輸出超過 200 字被截掉 | preview 裡看不到該輸出 |

## 4. 那一格資訊，系統當下有沒有？——有（本 handler 實測，附 `file:line`）

完整 output body 存在於 session store；剝除是**呈現層的選擇**，不是資料不存在。
實測位置（opencode repo）：

```
packages/mcp/system-manager/src/index.ts:3241   // Compact output: first 200 chars as preview
packages/mcp/system-manager/src/index.ts:3244   outputPreview = state.output.slice(0, 200)
                                                  + (state.output.length > 200 ? "…" : "")
packages/mcp/system-manager/src/index.ts:3254   outputBytes: typeof state.output === "string"
                                                  ? state.output.length : 0
packages/mcp/system-manager/src/index.ts:3296   note: "Tool output bodies stripped. …"
```

（**行號以 2026-08-05 opencode commit `96bc7f79` 為準**——該 commit 是本張建檔當下的 opencode HEAD。
`outputBytes` 原記為 `:3253`，2026-08-05 由 `ses_02ff37b7d` 重量後更正為 `:3254`：`:3253` 是
`outputPreview,`，`:3254` 才是 `outputBytes`（全檔唯一命中，字串與本節記載一字不差）。
其餘四條引用（`bash.ts:1620`、`index.ts:3241`、`:3244`、`:3296`）在同一 commit 上內容相符、
行號精確命中，未動。**注意行號會漂**：在 2026-08-05 11:37 的 opencode HEAD `7f702048b7` 上，
同一段程式已位移至 `:3281` / `:3284` / `:3294` / `:3336`——引用行號時務必連 commit 一起講。）

⇒ `state.output` **在那一行手上是完整的**，程式主動 `.slice(0, 200)` 之後丟棄其餘。

### 4.1 `outputBytes` 確實已存在（原派工單此處為待確認，本 handler 已確認）

派工單要求先自行確認 `outputBytes` 是否真的存在，不要照抄。**實測：存在**（`96bc7f79` 的 `:3254`，見上）。
且 preview 尾端在超長時會補 `…`。

所以本張的缺口比原先設想的**窄**，必須據實修正：

- **不缺** 原始長度 → `outputBytes` 有給。
- **不缺** 截斷標記 → 尾端 `…` 有給（雖然是視覺標記而非結構欄位；且**若原文本身結尾就是 `…`，兩態仍不可分**——本 handler 未量此邊界情形發生率）。
- **真正缺的只有一件**：**沒有任何管道可以付 token 換回完整 body**。無論覆核場景多需要原文，工具都不給。

## 5. Proposed fix（提議，未決定）

1. 加一個 opt-in 參數，例如 `includeToolOutputBodies: true` 或 `maxPreviewChars: N`，
   讓覆核場景**可以自己決定付多少 token 換多少證據**。預設維持 200 不變，不影響既有省 token 行為。
2. 或提供選擇性放大：`toolCallIDs: ["…"]` 只對指名的幾個 call 回完整 body——
   覆核通常只需要一兩個關鍵指令的原文，不需要整段。
3. `note` 字串應同時指出**如何取得完整 body**（`result_ref` 指得到），
   否則讀者只知道被剝除、不知道還有沒有救。

## 6. 我沒量什麼（明講）

- **沒重跑**觸發事件本身（`ses_030159029` 取件 `ses_03019b6fe` 那一次）；§2 為上游轉述。
- **沒量**「200 字上限實際造成多少比例的 call 失去關鍵資訊」——沒有母體統計。
- **沒量** `result_ref` 路徑是否真的取得回完整 body（§5.3 的前提），僅由 SYSTEM.md 敘述得知。
- **沒量**「原文結尾恰為 `…`」這個截斷標記失效邊界的實際發生率。

## 7. Cross-repo boundary

修復面在 **opencode runtime**，`packages/mcp/system-manager/src/index.ts`。
**本 repo 不可修** ⇒ 需走 BRNS 交 opencode 值星官（`ses_0475fc0aeffetUCNkxaPsoKNFD`）。

建議與 `BR_20260804m`、`BR_20260805a`、`BR_20260805b` **整包一次交付**——
四張同工具、同交付面，其中 805a 與本張落在同一個 map 回呼的相鄰兩行。
