# BR_20260805b — `read_subsession` 的 `position` 在游標推進後仍回 `oldest`，且假 `sinceMessageID` 也回 `oldest`

- **Status**: OPEN — 揭露缺陷；修復面不在 bodesign（`read_subsession` 由 opencode runtime 的 `system-manager` MCP 提供）
- **Severity**: MEDIUM — 呼叫端的停止條件失效；它不會讓人得到錯誤結論，但會讓人**無限翻頁或提早停手**，且第二節（假 id）的形狀更危險：打錯的 id 與「真的要從頭讀」不可區分
- **Owner repo**: opencode（本 repo 不可修）
- **Family**: G13-harness-disclosure
- **Filed**: 2026-08-05 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`（bodesign 值星官）
- **Provenance**: 現象由派工的值星官 session 於 2026-08-05 分段讀取時實測；**本建檔 handler 未能獨立重驗**（`read_subsession` 不在本 handler 工具集內，見 §4）。本張為存證＋轉交。

**Related**:
- `BR_20260805a_pending_tool_call_input_summary_is_an_empty_object_so_in_flight_calls_are_unreadable.md`
  （**同一工具、同一輪量測、同一 commit 建檔**；同一根因家族：系統握有該格資訊但輸出不揭露）
- `BR_20260804m_read_subsession_does_not_mark_message_recency_so_history_reads_as_current_activity.md`
  （**同一工具、同一資料流的姊妹缺陷**：804m 是「時間軸未揭露」，本張是「位置軸未揭露」。兩者合起來的後果是：呼叫端既不知道讀到哪、也不知道讀的是多久以前）
- `BR_20260802_probe_ambiguity_is_the_one_defect_family_no_guard_scans_and_it_fired_16_times_today.md`
  （**同一失敗類別**——該張界定的「缺席態與失敗態共用同一個輸出」；§2 的假 id 行為是該類別的教科書實例）

---

## 1. Symptom（第一節：`position` 不推進）

`system-manager_read_subsession(sessionID, sinceMessageID=..., limit=N)` 分段前進時，
回應中的 `position` 欄位在游標**已經推進到中段／尾端之後，仍然回報 `oldest`**。

於是：

| 讀者想分辨的兩態 | 實際輸出 |
|---|---|
| 我真的還在最舊端，該繼續翻 | `position: "oldest"` |
| 我已經翻到底了，欄位只是沒更新 | `position: "oldest"` |

呼叫端唯一能用的停止條件變成 `omittedNewerInFrame == 0`——而那是**推導**出來的，不是這個欄位承諾的語意。

## 2. Symptom（第二節：不存在的 `sinceMessageID` 靜默回 `oldest`）

傳入一個**不存在**的 `sinceMessageID` 時，工具**不報錯**，而是回 `position: "oldest"` 並從頭給訊息。

| 讀者想分辨的兩態 | 實際輸出 |
|---|---|
| 我傳的 id 是假的／打錯了 | `oldest` + 從頭的訊息 |
| 我確實要求從最舊端開始讀 | `oldest` + 從頭的訊息 |

這一節比第一節嚴重：第一節只是欄位沒用，第二節會讓一個**打錯的游標**看起來像一次成功的全量讀取，
而讀者拿到的是**與他要求的位置無關**的一批資料。

## 3. Reproduction

```
# 第一節
r1 = read_subsession({ sessionID: S })                       # 觀察 r1.position
r2 = read_subsession({ sessionID: S, sinceMessageID: <r1 最後一則的 id> })
r3 = read_subsession({ sessionID: S, sinceMessageID: <r2 最後一則的 id> })
# -> r2.position / r3.position 仍為 "oldest"
# -> 但 r2/r3 的 omittedNewerInFrame 有在遞減 ⇒ 系統算得出位置

# 第二節
read_subsession({ sessionID: S, sinceMessageID: "msg_this_id_does_not_exist_zzz" })
# -> 不報錯；position="oldest"；從頭回訊息
```

## 4. Control（證明這個探針有判別力）

**正組**：`omittedNewerInFrame` 在同一串分段呼叫中**確實遞減**。
⇒ 系統**算得出**目前 frame 相對於全體的位置——這正是「那一格資訊系統當下有沒有」的直接證據。

**負組**：`position` 在同一串呼叫中**恆為同一字串**。
⇒ 兩個欄位取自同一次計算，一個變一個不變 ⇒ 差異不是「系統不知道」，是「知道但沒寫進去」。

第二節的對照：把 `sinceMessageID` 換成一個**真實存在的舊 id**，回應同樣是 `oldest` ＋從頭的訊息。
⇒ 假 id 與真舊 id 的輸出**逐字相同**，故該欄位對「id 是否有效」零判別力。

**沒量什麼（明講）**：以上由派工 session 於 2026-08-05 實測；本建檔 handler **未親自重跑**——
`read_subsession` 不在本 handler 的工具集內（實測：`tool_loader` 只暴露
`system-manager_get_session` / `list_subagents` / `switch_session` 等，不含 `read_subsession`）。
接手者請先自行跑一次 §3。

## 5. Why this is a disclosure gap, not operator error

**那一格資訊，系統當下有沒有？——有，而且證據就在同一個回應裡。**

- 第一節：能算出 `omittedNewerInFrame` 就代表已經知道「這個 frame 在整體的哪裡」。`position` 是同一份
  知識的另一個投影，卻停在初值。
- 第二節：`sinceMessageID` 是否命中一則真實訊息，是查表的**當下**就知道的事實（查不到才會 fallback）。
  系統選擇把「查不到」靜默降級成「從頭讀」，於是把一個可判別的錯誤壓成一個令人安心的成功。

兩節都不是「呼叫端不夠仔細」：呼叫端沒有任何管道能從輸出裡把兩態分開。

## 6. Proposed fix（提議，未決定）

1. **`position` 反映真實位置**：`oldest` / `middle` / `newest`，由已經算出的 frame 位置直接導出。
   或者更誠實：**移除這個欄位**，只留 `omittedOlderInFrame` / `omittedNewerInFrame`——
   一個永遠回同值的欄位比沒有欄位更糟。
2. **假 `sinceMessageID` 必須報錯**：回一個明確的 `INVALID_CURSOR`（附「你給的 id 不在這個 session」），
   而不是靜默 fallback。若基於相容性必須 fallback，至少加 `cursorResolved: false`。
3. 回應頂層加 `totalMessages` 與 `frameRange: [i, j]`，讓停止條件不必用推導。

## 7. Related work

本張與 `BR_20260805a` 同輪、同工具、同 commit 建檔。與 `BR_20260804m` 合併後，
`read_subsession` 在本 fleet 已累積 **3 個獨立的揭露缺陷**（時間軸、位置軸、在飛參數），
建議整包走 BRNS 交 opencode repo 值星官，而非逐張轉交。
