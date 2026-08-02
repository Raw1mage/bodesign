# BR_20260802 — `git mv` 後的內容編輯不進暫存區，而「數檔案」的 staging 閘看不出差別：rename-only 與 rename+content 都回 1

- **Status**: OPEN
- **Owner**: `(default)`
- **Family**: `G13-harness-disclosure` / git-staging-visibility
- **Filed at**: 2026-08-02（coordinator `ses_04db7a1c5ffelvbxyLP1p6xlRH`；歸檔 BR_20260707 時**實際踩到**，commit `788e523` 是一個空 commit）
- **Severity**: real — 一個看起來成功的 commit 可以完全不含它宣稱的內容，且所有輸出都正常
- **Component**: 工作流層（`git mv` 語意 × 本 repo 通用的 staging 閘寫法）
- **時區**: Asia/Taipei (UTC+08:00)

## Symptom（實際事故，非假想）

歸檔 BR_20260707 的流程：

```
1. edit  <BR>            改 Status: FIXED-UNDEPLOYED → FIXED，加 Closed 戳記，加依賴解除紀錄（40 行）
2. git mv <BR> issues/closed/
3. git add <BR>          （被 git mv 隱含完成，我沒重跑）
4. staging 閘：staged 檔案數 == 1  ✓ 通過
5. git commit
```

commit `788e523` 落地，訊息完整，`git log` 正常。**但它的內容是：**

```
$ git show --stat 788e523
 ...BR_20260707_....md | 0
 1 file changed, 0 insertions(+), 0 deletions(-)

$ git show 788e523:issues/closed/BR_20260707_....md | grep -c 'FIXED-UNDEPLOYED'
1        ← 舊狀態，我改掉的那個
$ git show 788e523:issues/closed/BR_20260707_....md | grep -c '^- Closed:'
0        ← 我加的戳記不存在
```

**歸檔動作發生了，歸檔的理由沒有進版控。** 一個從 `git log` 完全看不出異常的空 commit。

## RCA（mechanism）

`git mv` 從 **index** 暫存 rename——它移動的是 HEAD 版本的 blob，不是工作區當下的內容。
之後（或之前）對工作區檔案的編輯留在**未暫存**區。

而我用的 staging 閘是：

```bash
test "$(git diff --cached --name-only | wc -l)" -eq 1 || abort
```

**它數的是「有幾個路徑被暫存」，不是「暫存了多少改動」。** rename-only 與
rename-plus-content 在這個判準下**完全相同**，都回 1。

### 最小複現（已實測）

```bash
git init -q . && mkdir -p a b
printf 'Status: OLD\n' > a/f.md && git add . && git commit -qm base
git mv a/f.md b/f.md
printf 'Status: NEW\n' > b/f.md        # 編輯發生在 mv 之後

git diff --cached --name-only | wc -l   → 1     # 弱判準：通過
git diff --cached --numstat | cut -f1    → 0     # 真相：零插入
git show :b/f.md                         → Status: OLD
```

## 這是哪一種缺陷

**判準的形式讓「做了」與「沒做」共用同一個輸出**，而且系統當下**知道**答案——
`git diff --cached --numstat` 就有 insertions=0 這一格，`git show --stat` 也印得出 `| 0`。
資訊在場，只是我選的那個判準沒有去問它。

依歸責原則（G13）：**那一格的資訊，系統當下有沒有？有 ⇒ 揭露缺陷，不是「我不夠仔細」。**

值得記錄的是**這條 BR 是在同一個 session 內、在我反覆對 handler 強調
「缺席態與失敗態不得共用同一個輸出」之後踩到的**——我為自己的 commit 建了一個守衛，
而那個守衛犯的正是我整場在抓的錯。這是 code-thinker §8「正在寫某條規則不構成該規則的豁免」
的第二個活例（第一個是同日的 `git reset --hard` 事故）。

## Fix proposal

**這不是 git 的 bug，`git mv` 的行為是文件化的。缺陷在「我們怎麼寫 staging 閘」。**

1. **★ staging 閘一律改數「改動量」而非「路徑數」**：

   ```bash
   INS=$(git diff --cached --numstat -- "$F" | cut -f1)
   test "$INS" -gt 0 || abort "rename-only: content not staged"
   ```

   純 rename（無內容變更）是合法情境，此時判準應顯式寫成「預期 insertions=0」，
   而不是讓兩種情況共用一個沉默的通過。

2. **`git mv` + 內容編輯的順序紀律**：`git mv` 之後**一律重跑 `git add <new-path>`**。
   本 repo 的 BR 歸檔流程（改 Status + 蓋 Closed 戳 + `git mv`）**每次都會撞到這個組合**，
   應寫進 AGENTS.md 的歸檔步驟。

3. **commit 後回讀**：對「內容必須落地」的 commit，用
   `git show <sha>:<path> | grep -c <新字串>` 雙向驗證（新字串出現、舊字串消失）。
   這是唯一不依賴暫存區語意的檢查。

## Validation plan

- 上述最小複現腳本作為迴歸：斷言弱判準（`--name-only | wc -l`）回 1 而強判準
  （`--numstat` insertions）回 0——**證明兩者確實可分辨**，否則修法無意義。
- 修 AGENTS.md 後，用一次真實的 BR 歸檔走完整流程，斷言 commit 內容含新 Status。

## 已修正的實例

`788e523`（空的 rename commit）後續由下一個 commit 補上內容，並在該 commit message 裡
記錄了根因。**未 amend**——歷史保留這個空 commit 作為證據，比整齊的歷史有用。

## Cross-ref

- `issues/BR_20260802_reset_hard_silently_destroyed_uncommitted_work_on_shared_tree.md`
  ——同日、同 session、同一類「git 操作的破壞性/惰性不自我揭露」。
- `issues/BR_20260802_issues_ledger_committed_on_archive_not_on_filing.md`
  ——同樣關於 `issues/` 帳本的版控完整性；本 BR 是它的孿生（那張是「立案時沒進版控」，
  這張是「歸檔時內容沒進版控」）。
