# BR_20260805a — `pending` tool call 的 `inputSummary` 回空物件，於是在飛的 call 無法被讀懂

- **Status**: OPEN — 揭露缺陷；修復面不在 bodesign（`read_subsession` 由 opencode runtime 的 `system-manager` MCP 提供）
- **Severity**: MEDIUM — 不產生錯誤結論，但把「在飛時查它在做什麼」這個唯一動機直接歸零；讀者只能等它結束，而等它結束時這個查詢已無意義
- **Owner repo**: opencode（本 repo 不可修）
- **Family**: G13-harness-disclosure
- **Filed**: 2026-08-05 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`（bodesign 值星官）
- **Provenance**: 現象由派工的值星官 session 於 2026-08-05 實測；**本建檔 handler 未能獨立重驗**——`system-manager_read_subsession` 不在本 handler 的工具集內（見 §3「沒量什麼」）。本張為存證＋轉交，不得當作二次確認。

**Related**:
- `BR_20260805b_read_subsession_position_stays_oldest_after_the_cursor_advances.md`
  （同一工具 `read_subsession` 的同一輪量測、同一根因家族：**系統當下握有該格資訊但輸出不揭露**。兩張同時建檔、同一 commit）
- `BR_20260804m_read_subsession_does_not_mark_message_recency_so_history_reads_as_current_activity.md`
  （**同一工具、同一資料流**：804m 管「這批訊息有多舊」未揭露，本張管「這個 call 的參數」未揭露。同一 owner repo、同一交付面）
- `BR_20260802_probe_ambiguity_is_the_one_defect_family_no_guard_scans_and_it_fired_16_times_today.md`
  （**同一失敗類別**，該張 §2 定義的類別名為「缺席態與失敗態共用同一個輸出」；本張是該類別在 harness 讀取面的實例）

---

## 1. Symptom

以 `system-manager_read_subsession` 讀一個子 session 時，狀態為 `pending`（尚未完成）的 tool call，
其 `inputSummary` 欄位回 **`{}`（空物件）**。

已完成（`completed`）的 call 則 `inputSummary` 有內容。

於是同一份輸出裡，兩態共用同一個字串：

| 讀者想分辨的兩態 | 實際輸出 |
|---|---|
| 這個 call 本來就沒有參數 | `inputSummary: {}` |
| 這個 call 有參數，但因為還在飛所以不給看 | `inputSummary: {}` |

## 2. Reproduction

```
# 1) 找一顆正在跑的子 session
system-manager_list_subagents({ includeFinished: false })

# 2) 在它「工具還在飛」的當下讀它
system-manager_read_subsession({ sessionID: "<running child>" })

# 3) 在回應中找 state=pending 的 tool part
#    -> 觀察其 inputSummary
```

## 3. Control（證明這個探針有判別力）

**正組**：同一次呼叫的回應中，`state=completed` 的 tool part 其 `inputSummary` **有內容**。
⇒ 欄位本身會被填、序列化路徑正常；空值不是「這個工具從不填這欄」。

**負組**：若把觀察窗改到該 call 完成之後再讀同一個 part，`inputSummary` 變為非空。
⇒ 差異來自 **狀態**，不是來自 call 種類或參數本身為空。

**沒量什麼（明講）**：上述兩組對照由派工 session 敘述，本建檔 handler **未能親自跑一次**——
`read_subsession` 不在本 handler 可呼叫的工具集內（實測：`tool_loader` 對本 handler 只暴露
`system-manager_get_session` / `switch_session` / `list_subagents` 等，不含 `read_subsession`）。
接手者請先自行跑一次 §2 再據以修改。

## 4. Why this is a disclosure gap, not operator error

**那一格資訊，系統當下有沒有？——有。**

參數在 call 被**發出的當下**就已經存在：它就是被送出去的那個東西，是 runtime 用來執行該 call 的輸入。
`pending` 的意思是「結果還沒回來」，不是「輸入還沒決定」。所以系統手上百分之百握有那一格。

而讀 pending call 的**唯一動機**就是「它現在在做什麼」。把這一格壓成 `{}`，等於在讀者最需要它的那一刻
把它拿掉，並回一個看起來很像「沒有參數」的安心答案。

## 5. Proposed fix（提議，未決定）

擇一或並行：

1. **pending 也填 `inputSummary`**——輸入在發出時就已知，沒有等待的理由。
2. 若基於某種序列化時機確實無法填，則**不要回 `{}`**：回 `null` 並附 `inputSummaryReason: "pending"`，
   讓「無參數」與「有參數但未揭露」不再共用同一個字串。
3. 在 pending part 上加 `toolName` + 起始時間，至少讓讀者知道在飛的是哪一支。

## 6. Related work

本張與 `BR_20260805b` 同輪量測、同工具、同 commit 建檔（`a183170` 之後）。
兩張都應隨 `BR_20260804m` 一併走 BRNS 交給 opencode repo 的值星官——**本 repo 的 `packages/` 不含此修復面**。
