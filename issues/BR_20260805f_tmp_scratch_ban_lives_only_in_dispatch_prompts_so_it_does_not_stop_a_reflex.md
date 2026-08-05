# BR_20260805f — `/tmp` scratch 禁令的唯一載體是派工單文字，攔不住反射動作；同一天三顆 handler 各踩一次（第三顆的任務正是覆核本張）

- **Status**: OPEN — 揭露缺陷；修復面不在 bodesign（`bash` denylist 由 opencode runtime 提供）
- **Severity**: HIGH — 洩漏面是本機 13 個真實使用者可讀的 world-readable 目錄，且實際外洩內容包含他人未完成工作的檔名清單；禁令已重申三次仍在同一天連續失效（第三顆的任務就是覆核本張 BR）
- **Owner repo**: opencode（本 repo 不可修）
- **Family**: G13-harness-disclosure
- **Filed**: 2026-08-05 by `ses_0300f19c6ffetKMrfXyQ125dou`（bodesign 值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH` 派工建檔）
- **Provenance**: 三顆 handler 的 session id 與所用 `/tmp` 路徑皆由派工的值星官 session 轉述，**未獨立驗證它們的實際指令**（見 §6）。§3 的權限位／使用者數、§4 的 denylist 前例與 bash.ts 反證，為建檔 handler 於 2026-08-05 親自實測；§1.1（第三個樣本）由 `ses_02ff37b7d` 於 2026-08-05 回填，其中 `/tmp` 權限位、使用者數、`/tmp/.nope` 現況為該 handler 重量，檔案 mode／size／內容性質為受試 session 自報。

**Related**:
- `BR_20260805g_read_subsession_strips_tool_output_bodies_so_the_verifier_gets_claims_not_evidence.md`
  （**同一輪、同一 commit 建檔**，且互為因果：本張的第二個樣本（`ses_03019b6fe` 把 `git status --porcelain` 全文寫進 `/tmp/.x`）之所以只留下「自述 41 行」而拿不到原文，正是 805g 描述的剝除行為）
- `BR_20260802_reset_hard_silently_destroyed_uncommitted_work_on_shared_tree.md`
  （**同一處方面**：該張 §5 已實測推翻 alias／git hook 兩條路，明寫「正解移交 opencode bash denylist（跨 repo，見 §5.4）」。本張提出的處方落在**同一個 denylist**、同一個 owner repo、同一個共用工作樹情境）

---

## 1. Symptom — 三個獨立樣本，同一天

| # | session | 用了什麼路徑 | 存了什麼 |
|---|---|---|---|
| 1 | `ses_03023e18e` | `/tmp/x`、`/tmp/base.out`、`/tmp/wt.out` | 指令 stdout |
| 2 | `ses_03019b6fe` | `/tmp/.x` | `git status --porcelain` 完整輸出 |
| 3 | `ses_03002962d` | `/tmp/.nope` | `git status --porcelain` 完整輸出（見 §1.1） |

三顆的派工單**都明文寫了**「scratch 一律落 `$XDG_RUNTIME_DIR`，絕對禁止 `/tmp`（資安天條，world-readable）」。
三顆**都自報了**違規——這一點是好的，誠實回報保住了本張 BR 的存在。
但**三顆都是在違規之後才自報，沒有一顆在動手前被攔下**。

第二顆的內容值得單獨記：`/tmp/.x` 存的是 `git status --porcelain` 的完整輸出，
**內含這棵共用工作樹上他人約 41 行未 commit 修改的檔案路徑清單**。
該 handler 自陳「無密鑰」——正確，但它沒點出洩漏的是**他人未完成工作的檔名與目錄結構**。

**三個獨立樣本、同一天、不同任務、不同模型指派**，是「這不是單一 handler 疏忽」的證據。
單一樣本無法區分「這顆不小心」與「這條普遍攔不住」；兩顆可以區分；
**第三顆進一步把「禁令資訊強度不足」這個退路也封死了**（見 §1.1）。

### 1.1 第三個樣本——比前兩個都強，因為受試者當時正在讀的就是這張 BR

前兩個樣本還留著一個可信的反論：「handler 沒讀仔細 / 禁令寫得不夠顯著」。
若如此，則處方就是「把禁令寫得更大聲」，而不是執行面攔截。
**第三個樣本不能這樣解釋。**

| 項 | 值 |
|---|---|
| session | `ses_03002962d` |
| 它當時的任務 | **覆核「`/tmp` 禁令攔不住反射」這張 BR 本身**（即本檔） |
| 違規發生點 | **它的第一條指令** |
| 指令 | `git status --porcelain > /tmp/.nope` |
| 實際落地 | `-rw-r--r-- 1 pkcs12 pkcs12 1372 Aug  5 11:35 /tmp/.nope` |
| 檔案 mode | `644` —— **全機可讀**，不需任何提權 |
| size | 1372 bytes |
| 內容性質 | 本 repo 完整的未 commit 檔名清單（tracked 修改 + untracked） |
| 目錄權限 | `/tmp` = `drwxrwxrwt root root 1777`（任何使用者可列目錄、可讀該檔） |
| 本機真實使用者數 | 13（§3 實測） |
| 曝露窗 | 下一條指令 `rm -f` 移除並 `ls` 驗證消失；該 handler 自估數十秒 |

該 handler 自己的定性（逐字）：

> 一個剛被指派去覆核「`/tmp` 禁令攔不住反射」的覆核員，第一條指令就踩了它。

**為什麼這一格比前兩格有力（本節重點）：**
受試者當時手上拿著、正要讀的工作對象，**就是這張描述該違規的 BR**。
禁令對它而言不只是派工單裡的一行字，而是它當下的**任務主題本身**——
資訊強度不可能再高了。即使如此，`> /tmp/…` 仍然先於規則檢索發生。

這正是 §2 所說的 reflex 形狀：**它不經過「我記得有條規矩嗎」這個步驟。**
並把 §2 引的 `code-thinker` §8.1.1 從推論提升為實測：
若連「正在讀這條禁令」都攔不住，則任何純資訊性修復（寫進 skill、寫進派工單、提高音量）
的預期效果不只是「低」，而是**已有一個實測樣本將它釘在 0**。

**本格未量（不得讀成已驗）**：曝露窗內**有沒有人實際讀到該檔，無從得知**——
未裝監控，`atime` 也不可靠。上表只記載**可量測的客觀事實**
（mode、size、內容性質、目錄權限、使用者數），**不斷言實際外洩發生與否**。

## 2. Mechanism — 為什麼攔不住

禁令的**唯一載體是派工單文字**。派工單是一次性注入的 prompt，
而使用 scratch 檔是 handler 的**反射動作**——`> /tmp/x` 是最短、最順手的寫法，
在「我只是暫存一下 stdout」的心智狀態下**不會觸發任何規則檢索**。

這正是 `code-thinker` §8.1.1 記載的形狀：

> 對已成反射的動作，純資訊性修復（寫進 skill／寫進派工單／提高音量）預期效果視為 0。

判別問法是：「這條規則要擋的動作，我在讀到它之前會不會自然想做？」
會 ⇒ reflex ⇒ 把規則寫進文字只是自我感覺良好。

**加重情節（本 handler 實測）**：runtime 自己就在教這個動作。
`packages/opencode/src/tool/bash.ts:1620`（opencode repo）在輸出過長時回給 agent 的提示是：

```
For long-running commands, redirect stdout to a file (e.g. '> /tmp/out.log') then read the file in slices.
```

⇒ 派工單說「絕對禁止 `/tmp`」，而 runtime 在 agent 剛好需要 scratch 的那一刻，
**主動示範 `> /tmp/out.log`**。禁令與示範同時存在，示範出現在動作的當下，禁令在幾千 token 之前。

## 3. Measurement — 洩漏面（本 handler 2026-08-05 實測）

```
$ stat -c '%A %U %G %a' /tmp /var/tmp
drwxrwxrwt root root 1777
drwxrwxrwt root root 1777

$ awk -F: '$3>=1000 && $3<60000 && $1!="nobody" {print $1":"$3}' /etc/passwd
pkcs12:1000  cece:1002  rooroo:1003  liam:1004  yeatsluo:1005  chihwei:1006
raysu:1007   jerryliao:1008  cmchen:1009  claudia:1010  pierrechen:1011
wayne:1012   eddylin:1013
count=13
```

**負控制組**：`awk -F: '$3==999999' /etc/passwd | wc -l` → `0`
⇒ 上面的 13 不是「awk 對任何條件都回一堆」，該探針有判別力。

⇒ `/tmp` 與 `/var/tmp` 皆為 `1777`（world-writable + sticky，**任何使用者可列目錄**），
本機有 **13 個真實使用者帳號**。這不是理論風險。

## 4. Why this is a disclosure/enforcement gap, not operator error

**那一格資訊，系統當下有沒有？——有。**

`bash` 工具在**執行指令前**就看得到指令字串，字串裡就有 `/tmp/`。
而且**同款攔截機制已經存在於本 harness**，本 handler 實測到既有前例：

```
$ grep -c "FORBIDDEN_MCP_BYPASS" packages/opencode/src/tool/bash.ts   # opencode repo
1        (rc=0)
$ grep -c "FORBIDDEN_ZZZ_DOES_NOT_EXIST" packages/opencode/src/tool/bash.ts
0        (rc=1)   ← 負控制組：探針有判別力
$ ls -la packages/opencode/src/tool/bash-denylist.test.ts
-rw-r--r-- 1 pkcs12 pkcs12 16226 Aug  3 03:16
```

`FORBIDDEN_DAEMON_SPAWN`、`FORBIDDEN_MCP_BYPASS` 都是既有的執行面攔截：
**在指令跑之前擋下，並回一個直接給正解的錯誤訊息**。

⇒ 缺的不是資訊、也不是機制、也不是先例。
缺的是**沒有為這條天條掛上同款的執行面攔截**。

⇒ 這是揭露／執行面缺陷（G13），**不是 handler 不夠仔細**。
誤歸責最貴：把可修的 harness 缺口寫成不可修的個人特質，缺口就永遠留在原地，
而下一顆 handler 會用「它不夠仔細」來解釋自己也踩到的同一個坑。

## 5. Proposed fix（提議，未決定）

1. **`bash` denylist 增一條**：指令字串含 `/tmp/` 或 `/var/tmp/` 的**寫入型**用法時擋下——
   `> /tmp/`、`>> /tmp/`、`-o /tmp/`、`tee /tmp/`、`mktemp` 未帶 `-p`。
   錯誤訊息直接給正解：`$XDG_RUNTIME_DIR/<slug>/`（`mkdir -p -m 700`）。
2. **唯讀放行**：`cat /tmp/x`、`ls /tmp` 不擋，以免誤傷讀取他人／系統既有檔的正當用途。
3. **同步修掉 `bash.ts:1620` 的示範字串**：把 `> /tmp/out.log` 改成
   `> "$XDG_RUNTIME_DIR/out.log"`。這一條**成本最低、打擊面最準**——
   它是 runtime 在 agent 最需要 scratch 的那一刻主動給的建議，
   單改這一行就把「示範」從錯的那邊搬到對的那邊。
4. 若 denylist 一時不能動，至少讓 `bash` 在偵測到寫入型 `/tmp/` 時**回一行警告但仍執行**——
   讓違規在**動手的當下**可見，而不是等 handler 事後自報。

## 6. 我沒量什麼（明講）

- **沒量**「denylist 是否真的攔得到這個 pattern」——那需要在 opencode repo 實作＋實測，
  本 repo 不可修，本 handler 未做。§5 全部是**提議**，不是既成事實。
- **沒獨立驗證**前兩顆 handler 的 session id（`ses_03023e18e`、`ses_03019b6fe`）與它們實際跑的指令；
  這些是派工的值星官 session 轉述而來。**本張是存證，不是二次確認。**
- **沒量**那 13 個使用者中有多少現在有活躍 session、有多少實際去讀過 `/tmp`。
  量到的只有「權限允許」與「帳號存在」，不是「已被讀取」。
- **沒量**前兩顆 handler 寫進 `/tmp` 的檔案是否還在磁碟上（未跑 `ls /tmp`）。
- （第三個樣本已量：2026-08-05 回填時 `ls -la /tmp/.nope` 回 `No such file or directory`，
  與該 handler 自報的 `rm -f` 一致。正控制組：同一支 `ls` 對 `/tmp` 下實存在的檔回正常
  stat 輸出 ⇒ 該探針有判別力。但這**只證明現在不在**，不證明曝露窗內沒被讀過。）
- **沒獨立驗證**第三顆（`ses_03002962d`）實際跑的指令串與 session id；
  同樣由值星官 session 轉述。本回填 handler 只獨立重驗了 `/tmp` 權限位、使用者數與該檔現況。

## 7. Cross-repo boundary

修復面（`bash` denylist、`bash.ts:1620` 提示字串）皆在 **opencode runtime**，
`packages/opencode/src/tool/bash.ts`。**本 repo 不可修** ⇒ 需走 BRNS 交 opencode 值星官
（`ses_0475fc0aeffetUCNkxaPsoKNFD`）。

本張與 `BR_20260802_reset_hard_silently_destroyed_uncommitted_work_on_shared_tree.md` §5.4
指向**同一個 denylist**，建議整包一次交付，而非逐張轉交。
