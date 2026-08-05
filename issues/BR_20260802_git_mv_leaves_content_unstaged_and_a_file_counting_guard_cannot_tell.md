# BR_20260802 — `git mv` 後的內容編輯不進暫存區，而「數檔案」的 staging 閘看不出差別：rename-only 與 rename+content 都回 1

- **Status**: OPEN — STILL-VALID（2026-08-05 重驗，最小複現逐字成立）。
  **但 §Fix proposal #1 的判準寫法本身有陷阱，見 §重驗補充（2026-08-05）。**
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

## 重驗補充（2026-08-05，`ses_030847a3affev5QmJelNWqSK41`，round=2 口徑矩陣）

缺陷本身**完全成立**。但「哪一個判準扛得住」需要**帶口徑**陳述——
round=1 我寫成無口徑的絕對句（「numstat 帶 pathspec 無判別力」），那是不完整的。

### 四態定義（`git show HEAD:a/f.md` 與 D 的 sha256 逐字相同，已驗 CONTROL）

| 態 | 情境 | index | worktree |
|---|---|---|---|
| **B** | `git mv` 後編輯工作區，**從未 `git add`**（缺陷態） | OLD | NEW |
| **D** | 純 rename，內容逐字未變（**合法**態） | OLD | OLD |
| **E** | 同 B 的編輯但**已 staged**，行數相同（修好態） | NEW | NEW |
| **C** | 同 E 但行數不同 | NEW | NEW |

### 3×4 矩陣（判準全部不接管道：`cmd > out 2>&1` 再讀）

| 判準 | B | D | E | C |
|---|---|---|---|---|
| p1 `numstat --cached -- <new>` | `3 0 b/f.md` | `3 0 b/f.md` | `3 0 b/f.md` | `4 0 b/f.md` |
| p2 `numstat --cached`（無 pathspec） | `0 0 {a => b}/f.md` | `0 0 {a => b}/f.md` | `1 1 {a => b}/f.md` | `0 3 a/f.md` + `4 0 b/f.md` |
| p3 `git show :<new>` readback | `Status: OLD` | `Status: OLD` | `Status: NEW` | `Status: NEW` |
| p4 `git diff --name-only`（未暫存殘留） | `[b/f.md]` | `[]` | `[]` | `[]` |

### ★ 決定性的一對是 B vs D，而**只有 p4 分得出來**

> **⚠ 結論的口徑（務必連同結論一起讀，不得擴大解釋）**
>
> 精確宣稱是：**在偵測「`git mv` 後同行數編輯且未 staged」這個特定缺陷態上，
> 區分 B 與 D 唯有 p4 具判別力。**
>
> **不是**「任何情況下只有 p4 能用」。若編輯**改變行數**（C 態），p1 就分得出來
> （B `3 0` vs C `4 0`）。p1 的失效**僅在改動不影響行數時成立**——
> 而 BR 歸檔（改 Status 一行、加 Closed 戳）恰好落在那個口徑內，
> 所以對本 repo 的歸檔流程而言 p4 是必要的。
>
> 無口徑的絕對句在兩個方向都是錯的：「p1 永遠無判別力」錯，
> 「readback 是三態通用判準」也錯。判準的適用範圍必須與判準本身一起陳述。

```
B(缺陷) vs D(合法純 rename)：  p1 相同  p2 相同  p3 相同  p4 DIFFERS
B(缺陷) vs E(同編輯已 staged)： p1 相同  p2 DIFFERS  p3 DIFFERS  p4 DIFFERS
```

**這推翻兩件事，其中一件是我 round=1 自己的建議：**

1. **`git show :<path>` readback 不是萬用解。** 它在 B vs E 有判別力，
   但在 **B vs D 完全沒有**——兩者都回 `Status: OLD`，因為純 rename 的 index 內容
   本來就該是舊的。readback 回答的是「index 內容是什麼」，**不是「有沒有東西該進去而沒進去」**。
2. **p1（帶 pathspec）的失效有口徑**：它在 B/D/E 三態共用 `3 0`，
   但 C（行數不同）回 `4 0`。所以「零判別力」**僅在改動不影響行數時成立**——
   而 BR 歸檔（改 Status 一行、加 Closed 戳）**正好落在那個口徑內**。
   無口徑的絕對句是錯的；無口徑的「有判別力」也是錯的。

### 正解：p4，且它耐得住 pathspec

缺陷的本質是「**工作區有改動沒進 index**」，所以判準要直接問那件事，
而不是繞道問 index 的內容或差異量：

```bash
# 精確 pathspec（本 repo 共用工作樹的強制要求），實測仍有判別力
test -z "$(git diff --name-only -- "$NEW")" || abort "content edited but NOT staged: $NEW"
```

```
B  git diff --name-only -- b/f.md = [b/f.md]   <- 開火
D  git diff --name-only -- b/f.md = []         <- 合法純 rename，正確放行
E  git diff --name-only -- b/f.md = []         <- 已 staged，正確放行
```

⇒ **§Fix proposal 的 ★ 應從 #1（numstat）改為本節的 p4**；
`git show :<path>` readback（#3）作為**內容正確性**的補充檢查仍有價值，
但它**不能**單獨用來偵測本 BR 的缺陷。

### 附帶發現：`git mv` 的錯誤訊息指錯對象（同族，建議併入本張）

由獨立驗證員踩到、本輪複現：目的地目錄不存在時，

```
$ git mv a/f.md b/f.md            # b/ 不存在
fatal: renaming 'a/f.md' failed: No such file or directory     rc=128

  source a/f.md 在 disk?  YES-EXISTS
  source 被 git 追蹤?      a/f.md（是）
  目的地 b/ ?              ABSENT   <- 真正的原因
CONTROL：mkdir -p b 後同一道指令 rc=0、stderr 空（探針有判別力）
```

**訊息把 `No such file` 掛在 source 上，而缺的是 destination。**
讀者會去查 source（存在、且 tracked），於是「路徑打錯」與「目的地目錄沒建」
共用同一句話。rc=128 是誠實的，但**若被管道尾端或 `|| true` 吃掉**
（本家族的既有形狀），就退化成缺席態偽裝成成功態。
歸入本張而非另立：同一個 `git mv` 表面、同一類「操作沒生效而輸出不明說」。

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
