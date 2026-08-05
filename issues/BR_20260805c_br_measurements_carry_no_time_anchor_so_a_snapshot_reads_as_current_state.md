# BR_20260805c — BR 內引用的量測值不帶時間錨，於是快照讀起來像現況

- **Status**: OPEN
- **Severity**: HIGH — 本張是**唯一在今日已產生實際代價**的一張：一份派工單照著一段六小時前就已在 `main` 修好的 BR 內容寫成，整輪白跑
- **Owner repo**: bodesign（本 repo 可修——這是本 repo 的文件慣例缺陷）
- **Family**: G13-harness-disclosure
- **Filed**: 2026-08-05 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`（bodesign 值星官）

**Related**:
- `BR_20260804m_read_subsession_does_not_mark_message_recency_so_history_reads_as_current_activity.md`
  （**同一失敗形狀的對偶，且是同一條資料流的兩端**：804m 管**工具輸出**未標新舊，本張管**人寫的文件**未標新舊。
  804m §1 的句子逐字適用於本張：「這顆 handler 正在做 X」與「兩小時前做過 X」共用同一個輸出形狀）
- `BR_20260804l_issues_ledger_has_no_status_schema_so_a_header_scoped_sweep_reports_five_files_as_having_none.md`
  （**同一標的物 `issues/` 的同一類治理缺陷、同一處方形狀**：804l 為 Status 欄立 schema ＋ checker，
  本張提議為量測值立 schema；且處方落點同為 `issues/README.md` ＋ `scripts/check_issue_headers.sh`）
- `BR_20260802_probe_ambiguity_is_the_one_defect_family_no_guard_scans_and_it_fired_16_times_today.md`
  （**同一失敗類別**：該張界定的「兩態共用同一個輸出」；本張的兩態是「現在還成立」與「曾經成立過」）

---

## 1. Symptom

本 repo 的 BR 檔大量引用具體量測數字（檔案數、符號數、誤差值、測試數、commit 數），
但幾乎都**不註明那個數字是何時、對哪個 commit 量的**。

於是同一個寫法承載兩個互斥的意思：

| 讀者想分辨的兩態 | 實際寫法 |
|---|---|
| 這個數字**現在**還成立 | `223 lib / 15 symbols` |
| 這個數字**曾經**成立過（快照） | `223 lib / 15 symbols` |

## 2. 造成的實際損害（今日實測）

**一張 BR 的 section A 在六小時前就已於 `main` 修好**，派工單照著該 section 寫成並發出，
handler 進場後發現無事可做——**整輪白跑**。該 section 的文字本身完全正確，錯的只是它讀起來像現況。

同族實測（2026-08-05，@ `a183170`）：

| BR 內寫的 | 當日實測 |
|---|---|
| `223 lib / 15 symbols` | 21437 / 1 |
| `41 張 BR` | 43（`issues/*.md` 總數；其中 `BR_*.md` = 40） |
| `untracked 33` | 40 |

三筆全部漂移，且**沒有一筆的寫法能讓讀者察覺它已經漂移**。

## 3. Reproduction（可重跑）

```bash
cd /home/pkcs12/projects/bodesign
# 分母：頂層 BR 檔數
ls issues/BR_*.md | wc -l
# 分子：帶時間錨的 BR 檔數
grep -lE 'measured [0-9]{4}-[0-9]{2}-[0-9]{2}' issues/BR_*.md | wc -l
# 帶 commit 錨的
grep -lEi 'measured.*@ *[0-9a-f]{7}' issues/BR_*.md | wc -l
```

**實測結果（measured 2026-08-05 @ `a183170`）**：

```
分母（BR_*.md 總數）        40
帶日期錨                     1     （2.5%）
帶 commit 錨                 0     （0%）
```

唯一帶日期錨的是
`issues/BR_20260802_refs_ingest_landing_verb_is_a_third_folder_convention_and_its_miss_looks_like_absence.md`。

## 4. Control（證明這個探針有判別力）

同一支 `grep -l ... | wc -l`，換成兩個結果已知的 token：

```bash
# 正組：一個必然全中的 token
grep -l 'Status' issues/BR_*.md | wc -l                      # -> 40（= 分母，全中）
# 負組：一個必然落空的假 token
grep -l 'zzzz_impossible_token_qqq' issues/BR_*.md | wc -l    # -> 0
```

正組 40、負組 0 ⇒ 這支探針**在該全中時全中、在該落空時落空**，
所以 §3 的「1」不是探針壞掉的產物。

（本節存在的理由見 `BR_20260804j`：一個從未在真負例上變紅的檢查，與壞掉的檢查不可區分。）

## 5. Why this is a disclosure gap, not operator error

**那一格資訊，寫的人當下有沒有？——有。**

寫 BR 的那一刻，作者手上百分之百握著「今天是幾號」與「HEAD 是哪個 sha」——
`date` 與 `git rev-parse --short HEAD` 都是零成本、零額外量測的。
把它省略，等於在資訊完全免費的時候選擇不揭露，並讓下一個 cold-context 的讀者承擔全部風險。

而承擔方式是最壞的那種：**讀者不會懷疑**。一個沒有時間戳的數字讀起來就是現況，
它不像空結果那樣會引起警覺，它是一個具體、精確、有說服力的錯誤前提。

這也不是「讀者應該自己去驗」：BR 存在的意義就是讓讀者不必重驗全部背景。
若每個數字都要重驗，BR 的資訊價值歸零。

## 6. Proposed fix（提議，未決定）

1. **量測值後綴時間錨**：BR 內每一處具體量測值後面加
   `（measured <YYYY-MM-DD> @ <short-sha>）`。
   本張自己全程遵守此格式，作為可讀的示範。
2. **寫進 schema 說明**：在 `issues/README.md` 現有的「Status line schema」之後，
   新增一節「Measurement anchor」，把上述格式定為慣例。
3. **是否加進 checker，留待裁示**：`scripts/check_issue_headers.sh` 可增一個 **WARN 級**
   檢查——「BR 內出現裸數字量測但全檔無 `measured ... @` 錨」。
   但這個偵測本身有誤判風險（數字不一定是量測值），
   故**提議為 WARN、絕不 block**，且是否採用由使用者裁示，本張不自行實作。

## 7. 自我揭露

本張 §3 的數字全部帶錨（`measured 2026-08-05 @ a183170`），§4 提供了正負對照組。
但**本張未回頭補正既有 40 張 BR 的錨**——那是分開的、需要逐張重驗的工作，
不在本派工單範圍。**未補正的部分不得被讀成已補正。**
