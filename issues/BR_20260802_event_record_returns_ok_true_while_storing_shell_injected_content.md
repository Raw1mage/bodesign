# BR_20260802 — `event_record` 回 `ok:true` 並給了 slug，而存進去的內文已被 shell 命令替換掉包

- **Status**: OPEN — STILL-VALID（2026-08-05 重驗）。**修復面確認不在 bodesign**：
  `skills/plan-builder/scripts/producer.ts` 在本 repo **不存在**，實際位於
  `/home/pkcs12/projects/specbase/skills/plan-builder/scripts/producer.ts`
  （CONTROL：同一支探針對 bodesign 的 `AGENTS.md` 回 present，證明它讀得到本 repo）。
  ⇒ 本張的 `Custody: 修復面在 specbase（跨 repo）` 註記正確，應走 BRNS 交給 specbase。
- **Owner**: unassigned（filed by 值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH`）
- **Family**: `G13-harness-disclosure`
- **Severity**: real — **append-only ledger 收下了一筆內容不是我寫的紀錄，且回報成功**
- **Component**: `specbase` 的 `skills/plan-builder/scripts/producer.ts`（`event_record` verb）× 呼叫端的 shell 引號處理
- **Custody**: 修復面在 `specbase` repo（跨 repo）；本張先在 bodesign 立案存證
- **Filed at**: 2026-08-02
- **時區**: Asia/Taipei (UTC+08:00)

## Symptom（實測，同一天兩筆對照）

用 bash heredoc 呼叫 `event_record`，`--arg body=...` 內含反引號包住的指令名（markdown 慣例）：

```
--arg body="...用 `git show --stat` 去 grep 長檔名得到 0..."
```

bash 把反引號當**命令替換**執行。`git show --stat` 真的被跑了，
**它的完整輸出（commit sha、Author、Date、commit message 全文）被注入事件內文**，
取代了我原本要寫的那句話。

`event_record` 回：

```json
{ "ok": true, "data": { "slug": "…_bnp13e", "dbPath": "…/events.sqlite" } }
```

**寫入成功與寫入掉包共用同一個輸出。**

### 結構化證據（非字串比對）

字串比對在這裡會誤判——**一篇「描述這個缺陷」的文章本身就含有那些 token**。
必須用**結構**判定：真正的 git-log 注入具有 `commit <40-hex>\nAuthor: …\nDate: ` 的三行形態。

```
                         injected_blocks   len
bnp13e（受損）                  1          3370
bnpda9（同內容重寫）            0          2396
bnrup5（更正紀錄）              0           882
控制組：僅提及那些 token 的散文  0            —
```

**控制組雙向有效**：偵測器對真受損的那筆會響（=1），對只是「提到」那些字的散文不響（=0）。
我第一版偵測器用的是 `"Author: Raw1mage" in body`，它對我自己的**更正紀錄**回報 True——
因為那篇文章在引述損毀內容。**偵測器自己踩了同一種缺陷。**

## RCA

兩層，都在「該說話的時候沒說話」：

1. **呼叫端**：以 shell 字串傳遞含反引號 / `$(...)` / `${...}` 的 markdown，shell 會先解讀再交棒。
   這是我的操作，但——
2. **接收端沒有任何完整性訊號**：`event_record` 拿到一段**內含 40-hex sha + Author 行 + Date 行**的
   body，這在語意上幾乎不可能是人寫的事件內文，而它照收不誤並回 `ok:true`。

判準（G13）：**那一格的資訊，系統當下有沒有？**

**有。** bash 的 `command not found` 出現在 stderr（`--stat`、`...`、`--name-only` 三行），
producer 也拿得到那段結構異常的 body。兩邊都握有證據，兩邊都沒說。

而 stderr 那三行看起來像雜訊不像錯誤——**真正的訊號（我的句子被換掉了）沒有任何地方顯示**。

## 為什麼這一張特別值得修

這個 ledger 存在的目的，是讓決策與 RCA 在 compaction 之後仍然可讀。
一筆**內容不是我寫的**紀錄留在裡面，比沒有紀錄更糟：

- 它有正確的 title、正確的 scope、正確的日期
- 內文中段突然變成一段 git log，讀者會以為那是刻意引用的證據
- **append-only 的設計讓它無法被覆寫**，只能追加更正指標

> 用來記錄「判準會靜默失效」的工具，自己靜默失效了。

## Fix proposal

**傾向 1**，理由與本 repo 其他 G13 張相同：它不依賴任何人記得。

1. **接收端結構檢查（唯一在決策點生效的）**：`event_record` 在寫入前掃 body，
   命中 `commit [0-9a-f]{40}\nAuthor: .+\nDate: ` 或 `fatal: ` / `command not found` 等
   **明顯是工具輸出而非人類敘述**的形態時，**fail fast 並回報疑似 shell 注入**，不要靜默收下。
   誤報成本 = 呼叫端加一個 flag 覆寫；漏報成本 = 永久性的假紀錄。
2. **呼叫端紀律**：含反引號 / `$` / `(` 的 markdown 一律用 argv 陣列傳參
   （python `subprocess` list 形式、或 `--json` 檔案輸入），**全程不經過 shell**。
   本次更正紀錄即以此方式寫入（`bnrup5`，結構檢查 0 命中）。
3. **不建議**用「呼叫端記得跳脫」當唯一防線——本 session 已示範紀律在場仍會踩。

## Validation plan

- **控制組先行**：確認結構偵測器**對真受損紀錄會響**（`bnp13e` = 1），
  且**對僅提及 token 的散文不響**（合成字串 = 0）。沒有這一格，偵測器可能只是常回 True。
- 修復後：以受損 body 餵 `event_record`，斷言它**拒絕**並帶出可讀原因。
- **Mutation proof**：把結構檢查改成 `return false`，上述拒絕案例必須轉為通過（證明檢查在承重）。

## Explicitly NOT bugs

- **append-only 設計本身沒問題**。無法覆寫是刻意的；正解是追加更正指標，不是開放改寫。
- **重複記錄（`bnp13e` / `bnpda9` 同一件事兩筆）不是本張的缺陷**，是我重送造成的，一併留存。

## Cross-ref

- 更正紀錄：`bodesign-coordination/event_2026-08-02_bash-git-log-event-record-ok-true_bnrup5`
- 同族：`AGENTS.md §6.1` 的 pathspec 陷阱 / 快照歧義 / `git log -S` 回空
- `issues/BR_20260802_denylist_has_no_rule_for_the_one_git_command…`（opencode，同為「工具握有資訊卻不說」）
