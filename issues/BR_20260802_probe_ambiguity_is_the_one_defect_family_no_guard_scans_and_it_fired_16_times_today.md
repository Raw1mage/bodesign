# BR_20260802 — 探針歧義：唯一沒有任何防護掃描的缺陷家族，今日開火 16 次

**Status**: OPEN — 生產線因此停線（使用者指令 2026-08-02）
**Severity**: P0 — 它汙染的是「我們如何知道任何事情」
**Family**: G13-harness-disclosure
**Owner**: ses_04db7a1c5ffelvbxyLP1p6xlRH（值星官）
**Filed**: 2026-08-02

---

## 1. 使用者指令

> 「關於重覆踩雷的事，不容許再發生，全面停止生產線，優先處理那個雷。」

兩顆 handler 已停在安全靜止態（tracked 零變更，6 筆 commit 落地，mutation residue = 0）。

---

## 2. 「那個雷」的精確形狀

**判準自己壞掉，而它的壞掉態與健康態產生同一個輸出。**

不是「粗心」。每一次失效都是一個**當下看起來完全合理**的指令，回傳一個**當下看起來完全合理**
的結果，而那個結果是錯的。

---

## 3. 今日清冊（16 次，三個 agent）

### 值星官（本 session，11 次）

| # | 指令 | 回傳 | 為何無鑑別力 | 如何發現 |
|---|---|---|---|---|
| 1 | `git status --porcelain issues/` | 4 個 ` M` | pathspec 縮小的視野與完整視野**輸出完全同形** | 事後被追問（全樹實為 46） |
| 2 | `sudo -n true 2>&1 \| head` | `exit=0` | `$?` 取到 `head` | `false \| head` 控制組 |
| 3 | `bunx tsc \| tail -3` | `TSC_EXIT=0` | 同上 | 一行沒被吞掉的 `command not found` |
| 4 | PATH wrapper 探針用 `git -C` | `exit=0` | `$1` 是 `-C` 不是 `reset` | 結論反直覺才回頭看 |
| 5 | `grep -rlc` | 空 | `-l` 與 `-c` 互斥，一個靜默勝出 | 控制組也回空 |
| 6 | storage 訊息路徑探針 | 0 | 路徑整個錯，**控制組也回 0** | 控制組自曝 |
| 7 | `git show --stat \| grep <basename>` | 0 | `--stat` 用 `...` 截斷長檔名 | diffstat 明明有那兩個檔 |
| 8 | event 污染偵測（子字串） | `True` | 分不出「被注入」與「在描述注入」 | 對自己的更正紀錄誤報 |
| 9 | sqlite 探針 | 表不存在 | 猜錯 schema 三次 | 錯誤訊息 |
| 10 | `_CLEARANCE_EPS_MM` 存在性 | 0 vs 控制組 0 | **兩個都零，我卻寫「probe discriminates」** | 回頭看自己的 echo |
| 11 | M5 mutation `s.index('[')` | `substitutions=1` | decl 用 `(...)`，注入落到別處；**「成功替換」與「替換到錯地方」同輸出** | TV4 該紅而沒紅 |

### peer `ses_0c87bab06`（4 次自報）

| # | 指令 | 為何無鑑別力 | 若沒發現 |
|---|---|---|---|
| 12 | `cmp` + `grep` 驗 mutation 還原 | 判準檢查**磁碟**，失效發生在 **bytecode 快取**；兩者正交，**結構上永遠攔不到** | 四個 mutation proof 全部無效 |
| 13 | `unittest discover` → `grep '^(FAIL\|ERROR):'` | 「零失敗」與「一個測試都沒跑」同輸出 | 回報「A 0 筆 / B 0 筆」 |
| 14 | `wc -l` 數清單 | 數的是換行**位元組**；末行無換行則少算 | 48/38/9/8 報成 47/37/8/7 |
| 15 | `getattr(rep,'disconnected',[])` | 「欄位不存在」與「欄位是空的」同輸出 | 第一次量的數字**全錯** |
| 16 | aiguard compose 缺 symbol 目錄 | 0 次比較與「沒有比較發生」同輸出 | **整個結論會反過來** |

### handler `ses_03dea7914`（4 次自報，與上表部分重疊）

- c00 pre-flight 探針第一版：C01 從未進入 `ready_undispatched`，那行**根本沒執行**
- c00 pre-flight 探針第二版：讀 `r["next_action"]`，`to_dict()` 把它攤平 → `.get()` 回 `None`
  → **三格輸出完全相同，含控制組**
- Q3 機檢第一版：少了「handler 是否已補償」過濾 → 2 個偽陽性
- 回歸差集兩次：`57→56`（總數**下降**，實際 NEW=2）、`57→57`（總數**不變**，實際 NEW=4）

---

## 4. 根因：對策全程在場，且不在決策點

**這是本 BR 最重要的一格。**

| 對策 | 狀態 | 今日攔截數 |
|---|---|---|
| `code-thinker §8.1` | **always-on pinned，逐字在每一輪 context** | 0 |
| 同家族既有 BR | **15 張**（`issues/` + `closed/`） | 0 |
| `AGENTS.md` §6.1 硬護欄 | 已寫入 | 0 |
| `no_silent_degradation` lint | 已實作，L1-L9 | 0 |
| `pre-commit` hook | 已安裝 | **1**（未進版控的 BR） |

**唯一有攔截紀錄的是唯一在決策點執行的那個。** 而那個 hook 的註解自己就寫著正解：

> This is the one step that runs at the **decision point** (commit time) instead of
> relying on anyone remembering.

**知識在場 ≠ 決策點攔截。** 這 16 次每一次，正確判準都在我的 context 裡逐字可讀。

### 為何 lint 攔不到

`no_silent_degradation` 掃的是 `rglob("*.py")` —— **已 commit 的程式碼**。

今天 16 次失效**沒有一次住在那裡**。它們住在**拋棄式 shell 探針**裡：寫出來、跑一次、
拿走結論、丟掉。那是這個 fleet 唯一**完全沒有掃描面覆蓋**的表面，而它恰好是
**所有事實主張的來源**。

我們對「要交付的程式碼」有 lint、有測試、有 mutation proof、有 VANS；
對「我們用來判斷交付是否正確的那些指令」**零防護**。

---

## 5. 為何「更努力記得」不是解法

peer 提出的判準（本 BR 採納）：

> 次數本身不是有意義的量。真正該量的是**多少次被自己的控制組抓到、多少次被對方抓到、
> 多少次沒被抓到**，而第三格我們兩個都不知道有多大。

今日已知的 16 次分佈：

```
自己的控制組抓到    7
對方 / 追問抓到     5
純屬僥倖（一行沒被吞掉的字、結論反直覺）  4
從未被抓到          未知，且無法從內部估計
```

**第四格才是真正的風險量，而它按定義不可觀測。**

一個只在「當天剛好有人多看一眼」時才生效的防護，不是防護。

---

## 6. 提案機制：執行後歧義偵測（post-execution ambiguity detector）

**不是 linter（掃不到拋棄式探針），不是文件（已證明無效），是 bash tool 的執行後鉤子。**

觸發條件是**觀察到的輸出恰好是那個歧義值** —— 即「缺席」與「問錯問題」共同產生的那個值。
不猜意圖，不擋執行，只在該值出現時說一句話。

### 原型已建並量測（`$XDG_RUNTIME_DIR/probeguard/`）

9 條規則對今日**真實**案例：

```
TREATMENT（必須開火）           CONTROL（必須不開火）
  FIRE  grep -c 回 0             ok  grep -c 回非零
  FIRE  grep -rlc                ok  一般 grep 有命中
  FIRE  sudo | head 取 $?        ok  管道但沒取 $?
  FIRE  bunx | tail 取 $?        ok  已 set -o pipefail
  FIRE  wc -l                    ok  git log -S 有命中
  FIRE  git log -S 回空          ok  不帶 pathspec 的 status
  FIRE  status 帶 pathspec       ok  測試真的跑了
  FIRE  show --stat | grep       ok  wc -c
  FIRE  perl -i
  FIRE  Ran 0 tests

recall 10/10    false-positives 0/8
```

### 訊息形狀（示例）

```
grep -c 回 0。錯的路徑、打錯的 pattern、真正的缺席，三者產生同一個 0。
加一個控制組：grep -c <你確知存在的 token>。
```

**只警告不阻擋** —— 理由與 pre-commit hook 相同：阻擋會逼人繞過，而繞過會關掉所有未來的鉤子。

### 落點

**`packages/opencode/src/tool/bash.ts`** —— 與 `denylistVerdict` 同一個表面
（已有 AST 解析、wrapper 剝除、純函式可測）。差別：

- `denylistVerdict` 在**執行前**看 argv → 擋危險動作
- 本機制在**執行後**看 argv + stdout + exit → 對歧義輸出說一句話

**這是跨 repo，走 BRNS。**

---

## 7. 驗收條件（不得以「已實作」代替）

1. **今日 16 個案例逐一 replay**，每個必須開火，附原始指令與輸出
2. **控制組必須存在且必須不開火** —— 缺控制組的 recall 數字無意義
3. **mutation proof**：拿掉規則表，今日案例必須全部重新漏過
4. **偽陽性率**在真實 session log 上量測，不是在合成案例上

---

## 8. 復工條件

生產線復工需滿足：

1. 本 BR 的機制**已落地並經 mutation proof**（不是「已設計」）
2. 兩顆 handler 的失效探針清冊**已收回並併入本 BR §3**
3. 使用者明確批准復工

---

## 9. 方法論（給下一個人）

**這張 BR 自己就是它所描述缺陷的產物**：它的 §4 表格「今日攔截數 = 0」那一欄，
如果我沒有去量 `pre-commit` hook 的註解，我會寫成「對策不足，需要加強」——
而正確結論是**對策充分且完全在場，位置錯了**。

判準：**「那一格的資訊，系統當下有沒有？」**
- 有 → 揭露缺陷，file BR，不要寫成自我檢討
- 沒有 → 才是真的需要更多工作

這 16 次**全部**是第一種。`grep -c` 的實作內部知道它掃了幾個檔案；
`wc -l` 知道最後一位元組不是換行；`git worktree remove` 知道有未 merge 的 commit。
**那一格資訊一直都在，只是沒有被說出來。**
