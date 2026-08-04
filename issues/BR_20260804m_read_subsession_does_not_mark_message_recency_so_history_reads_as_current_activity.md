# BR_20260804m — `read_subsession` 不標示訊息新舊，於是歷史讀起來就是現況

- **Status**: OPEN — 已量測，未修
- **Severity**: high — 它產生的不是空結果，而是一個很有說服力的錯誤結論，且該結論驅動了破壞性動作（誤遣散）
- **Owner**: (default)
- **Family**: G13-harness-disclosure
- **Filed**: 2026-08-04 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`（bodesign 值星官）
- **Scheduled**: 未排程

**Related**: `BR_20260804j_the_verification_layer_has_no_verification_layer_five_instances_in_one_round.md`
（同一失敗類別：「缺席態與失敗態共用同一個輸出」的對偶——那張管**我建造的判準**，本張管**我使用的工具**）；
`BR_20260804l_issues_ledger_has_no_status_schema.md`（同一 fleet 同日，兩支合理的 sweep 對同一批檔案回不同答案，
差別同樣在「讀取視窗未被揭露」）。

---

## 1. 現象

`system-manager_read_subsession(sessionID, sinceMessageID=..., limit=N)` 回傳一批訊息，
**輸出中沒有任何欄位說明這批訊息相對於「現在」有多舊**。

於是「這顆 handler 正在做 X」與「這顆 handler 兩小時前做過 X」共用同一個輸出形狀。

## 2. 量測（可重跑）

觸發情境：daemon sweep 送來 `[BRNS-REPLY-OVERDUE ... awaiting_since=1785860687460]`，
我呼叫 `read_subsession` 查該 handler 在做什麼。

```
TREATMENT  read_subsession 回傳的訊息 timestamp
  oldest returned  1785852680097  ->  比 awaiting_since 早 8007 秒（2.22 小時）
  newest returned  1785852981640  ->  比 awaiting_since 早 7706 秒（2.14 小時）

CONTROL    get_session 的 updated（證明該 session 當下真的活著）
  updated 1785861797621 - sweep2 1785861760631 = +37 秒
  liveness.alive = true / workflow.state = running
```

**回傳的每一則都比 sweep 觸發時刻早兩小時以上，而輸出讀起來完全像當前活動。**

## 3. 造成的實際損害

我據此判定該 handler「停在舊 NO-RECT fixture 擴張 = scope drift」，
發出 `[BRNS-DISMISS]` 遣散了一顆**正在正常待命、且從未偏離範圍**的 handler。

handler 隨後回報 `status=not-started-status-confirmed`：實作 0、測試 0、tracked-modified 0。
**它沒有漂移，只是還沒開始。** 我看到的「fixture 擴張」是它上一個工作包（`804g`，已於 `ae8589a` 結清）的歷史。

代價：一次錯誤的遣散 + 一次撤銷 + 完整派工單重送，約三個往返。

## 4. 那一格資訊，系統當下有沒有？

**有。** 三處都握著，只是都不出現在輸出裡：

| 系統知道的 | 揭露了嗎 |
|---|---|
| 每則訊息的 `time.created` / `time.completed`（原始 JSON 內就有） | 有，但**未與「現在」或 `awaiting_since` 對比** |
| 該 session 的 `time.updated`（`get_session` 回得出來） | `read_subsession` 不回 |
| `liveness.alive` / `workflow.state`（`get_session` 回得出來） | `read_subsession` 不回 |

⇒ 這是**揭露缺陷**，不是「我不夠仔細」。判準：那一格資訊系統當下有沒有——有。

## 5. 為什麼 `sinceMessageID` 不構成防護

`sinceMessageID` 是**位置**游標，不是**時間**游標。傳一個舊的 message id 會忠實地回傳它之後的訊息，
無論那批訊息是三秒前還是三小時前產生的。呼叫端要自行把 `time.created` 與 `awaiting_since` 相減——
而**沒有任何東西提示你該做這件事**，尤其在 sweep 訊號正把你的注意力導向「這顆是不是死了」的時候。

更糟的是它與 sweep 的組合：`[BRNS-REPLY-OVERDUE]` 已經在暗示異常，
此時任何看起來「不在做該做的事」的歷史片段，都會被讀成佐證。

## 6. 建議修法（未實作）

擇一或並行：

1. **輸出加時間錨**：`read_subsession` 回應頂層加 `now`、`session_updated_at`，
   並在每則訊息旁標 `age_seconds`。讓「兩小時前」無法被讀成「現在」。
2. **回傳 liveness**：把 `get_session` 已有的 `liveness.alive` / `workflow.state` 一併回，
   讓「查這顆在做什麼」與「查這顆還活著嗎」不必分兩次呼叫、不必由呼叫端拼接。
3. **落在 `hasMore=true` 且游標指向舊訊息時給出明確提示**：
   「你正在讀歷史；最新訊息在 X 之後」。

## 7. 對照：本 fleet 已知的同族形狀

- `git worktree remove` 對有未 merge commit 的樹 exit 0 全空
- `for p in packages/*/` 漏掉更深層的 `package.json`
- `sed -i` / `perl -i` pattern 沒中仍 exit 0 零修改
- `bun test <不存在路徑>` 靜默丟棄 + exit 0
- `jq '.f'` 對「欄位不存在」與「值為 null」回同一個 `null`

**共通形狀**：工具握有能分辨兩態的資訊，但輸出把兩態壓成同一個字串。

## 8. 我在建這張檔的當下的自我揭露

寫本節時我第一次的重複性檢查用了 `grep -l ... | wc -l`，同時給了 `-l` 與 `-c`——
兩者互斥，其中一個會靜默勝出，於是那個結果**回答的不是我問的問題**。
是 harness 的 `probe_ambiguity` 提示攔下來的，不是我自己發現的。

**正在寫某條規則不構成該規則的豁免**——本 repo 今日第四次。
而這次被攔下來，靠的是**工具自報**，不是我的紀律：這恰好就是 §6 建議修法的論據。
