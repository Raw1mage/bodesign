# BR_20260802 — local-first issue ledger 只在歸檔時進版控，立案時不會：8 張 open BR 從未被 git 追蹤

| Field | Value |
| --- | --- |
| Title | The issues/ ledger commits BRs when ARCHIVED but never when FILED — the open-issue list lived in one working tree only |
| Component | 流程／harness 揭露（`issues/` 工作流），非程式缺陷 |
| Owner | `ses_04db7a1c5ffelvbxyLP1p6xlRH`（coordinator，`(default)` family） |
| Reporter | ses_04db7a1c5 — 在歸檔 BR_20260729 時由 `git mv` 失敗撞出 |
| Date | 2026-08-02 |
| Severity | high — 不影響 runtime，但**整份 open-issue 帳本沒有歷史、沒有備援、對任何 clone 不可見**；peer 一次 `git clean -fd` 就會無聲刪掉全部未結案 BR |
| Priority | P1 — 已修（8 張補進版控，commit 見下），但**復發防護尚未存在** |
| Affected paths | `issues/*.md`（頂層）；對照 `issues/closed/*.md` |

```
State:
Fix: 8 files now tracked (commit 見 Timeline)
Effect: partial — 既有檔案已入版控，但沒有任何機制阻止下一張新 BR 重蹈
Custody: bodesign
Blocker: none
Disposition: filed under G13-harness-disclosure. 這是「揭露缺陷」不是「我不夠仔細」——
  判準見 §3。
Venue: bodesign
Status: OPEN — 殘留：復發防護未實作
```

## 1. 怎麼撞出來的

歸檔 `BR_20260729_ee_worker` 時：

```
$ git mv issues/BR_20260729_ee_worker_missing_freerouting_toolchain.md issues/closed/
fatal: not under version control, source=issues/BR_20260729_ee_worker_missing_freerouting_toolchain.md
```

**我當下的第一反應是「我路徑打錯了」。** 那個反應本身就是建檔的觸發條件——不是「這算不算缺陷」（那要對系統下結論，而下結論正是失效的那環），而是「我剛才是不是在想我打錯了」。

路徑沒打錯。那個檔案在磁碟上、`ls` 看得到、`grep` 讀得到、`cat` 印得出來，**它只是從來沒有被 `git add` 過**。

## 2. 量測（不是印象）

```
$ git ls-files issues/ | grep -c "^issues/[BK].*\.md"                    → 6   （頂層 tracked）
$ git ls-files --others --exclude-standard issues/ | grep -c "…"         → 7   （頂層 untracked）
$ git ls-files issues/closed/ | grep -c "\.md"                           → 60  （closed tracked）
$ git ls-files --others --exclude-standard issues/closed/ | grep -c ".md" → 0   （closed untracked）
```

**`closed/` 60 張全 tracked、0 張 untracked；頂層 7 張全 untracked。** 這個分布不是隨機的，它指認了一個明確的行為模式：

> **BR 在「歸檔」時進版控，在「立案」時不進。**

git 考古佐證：抽查兩張 closed BR，其 `--diff-filter=A` 的首次出現都在一個**修復 commit** 裡（`7405dd0`、`8fd59b0`），也就是「修完了，順手把 BR 一起 commit」——而不是立案當下。

**排除 .gitignore**：`git check-ignore -v issues/BR_20260729_ee_worker…` → exit 1（未被忽略）。**控制組**：同一指令對 `.venv` → `.gitignore:6:.venv/` 命中。所以 `check-ignore` 是活的，exit 1 是真的「沒被忽略」，不是指令壞掉。

## 3. RCA — 為什麼這歸責於揭露不足，而不是「誰忘了 git add」

那一格的資訊，系統當下有沒有？**有。** git 完全知道 `issues/BR_xxx.md` 是 untracked——`git status` 印得出來。但：

- **`git status` 在這個 repo 是雜訊**：peer 有 87 個未 commit 改動，`??` 區塊長期有幾十行，一張新 BR 混進去毫無訊號。
- **untracked 的 BR 與 tracked 的 BR 在所有日常操作下完全一樣**：`ls`、`cat`、`grep`、編輯器、甚至 `issues/OWNERS.md` 的清單，全部看不出差別。
- **缺席態與失敗態共用同一個輸出**：「這張 BR 沒進版控」與「這張 BR 好好地在那裡」渲染成同一個畫面。唯一會報錯的時機是 `git mv`——而那發生在**歸檔時**，也就是這張 BR 的生命週期末端。整個中間期完全無訊號。

所以這不是「agent 不夠仔細」。**「不夠仔細」可以解釋任何一次失誤，正因如此它什麼都沒解釋**——把它寫成個人特質，缺口就永遠留在原地等下一個人重踩。改寫成「立案動作沒有任何一步會揭露檔案未入版控」，它就變成可修的東西。

### 3.1 這件事的實際風險（不是理論）

- **沒有歷史**：任何一張 open BR 被誤刪、被覆寫、被截斷，都無法 `git checkout` 救回。
- **對 clone 不可見**：另一台機器 / 另一個 worktree clone 這個 repo，**看到的 `issues/` 是空的**（只有 `closed/`）。「local-first issue ledger」實際上是 "one-working-tree-only ledger"。
- **一次 `git clean -fd` 全滅**：而這個 repo 現在有 peer 在同一棵樹上工作。**這是最接近實際發生的那個情境。**
- **本次差點成真**：我在歸檔流程中用了 `git mv`。若我當時用的是 `mv`（很自然的替代），檔案會靜靜搬進 `closed/`、`git add` 成功、commit 成功——**而那張 BR 的全部歷史就此不存在**，且沒有任何一步會報錯。

## 4. 已做的處置

8 張未追蹤的 open BR 已補進版控（`BR_20260707`×3、`BR_20260719`×2、`BR_20260723`×3）。處置後量測：頂層 untracked = **0**，tracked = **13**。

## 5. Remainder — 復發防護（本 BR 留 OPEN 的唯一理由）

**上面只修了存量，沒修流程。** 下一張新 BR 若照舊只 `write` 不 `add`，會完全重演，而且一樣不會有任何訊號。

候選處置（未裁決）：

1. **pre-commit hook**：commit 時若 `issues/*.md` 有 untracked，loud warn（不阻擋——阻擋會逼人用 `--no-verify`，反而更糟）。
2. **把「filing a BR」的動作定義成 write + add + commit 三步**，寫進 `AGENTS.md` §6 的 issues 段落。**但這是紀律不是機制**，效力等同現況（現況失效正是因為它只是紀律）。
3. **一個 `issues/` 自檢 verb**：與 `check_c03` 同類，回報 untracked BR 清單。有 landing plane 才有意義，否則沒人會跑。

**判準（用於裁決）**：候選 1 是唯一在「決策點」生效的——它在 commit 當下自己報出來，不依賴任何人記得去查。候選 2 依賴「記得」，而記得正是最不可靠的那環。候選 3 依賴「有人跑它」，同樣的問題。

**傾向候選 1**，但需要確認本 repo 是否已有 pre-commit hook 以及它與 peer 工作流的相容性（peer 有 87 個未 commit 改動，一個吵鬧的 hook 會變成它的噪音）。

## 6. Explicitly NOT bugs

- **`issues/closed/` 沒有問題**，60 張全部 tracked。不要「順手統一」去動它。
- **`.gitignore` 沒有問題**，已用 `check-ignore` + 控制組排除。不要去改它。
- **peer 的 87 個未 commit 改動不是本 BR 的成因**，只是讓 `git status` 的訊號被淹沒的放大器。不要碰那些改動。
