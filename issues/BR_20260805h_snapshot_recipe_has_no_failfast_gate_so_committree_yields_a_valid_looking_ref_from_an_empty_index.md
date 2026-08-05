# BR_20260805h — AGENTS.md §6.1 的快照配方沒有 fail-fast 閘：`commit-tree` 對空 index 照常產出一個看起來完全有效的 ref

- **Status**: OPEN — 已量測定位並實地踩到，修法（在配方加 `||` 閘）未落地

| Field | Value |
| --- | --- |
| Title | The §6.1 snapshot recipe has no fail-fast gate; commit-tree happily yields a valid-looking ref from an empty index, so "I thought I snapshotted" produces the same output as a real snapshot |
| Component | `AGENTS.md §6.1`（⭐ 開工前先錨定自己的工作 — 快照配方本身），非 bodesign 程式缺陷 |
| Owner | `(default)` — dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH` |
| Reporter | `ses_02fe2ffe8ffe0y33B8FszeyVvM`（BRNS handler，804l WARN 收斂）— **我就是踩到的人**，自我通報 |
| Date | 2026-08-05 |
| Severity | **high** — 它讓唯一一道「不依賴任何人記得」的護欄靜默失效，而失效態與成功態共用同一個輸出（一個 40 字元 sha） |
| Family | `G13-harness-disclosure` |
| Affected paths | `AGENTS.md:110-120`（配方本體）；任何照抄該配方的 session |

**Related**（citable basis）：

- `AGENTS.md §6.1` 的快照配方 —— **same component，且本 BR 是它自己的失效**。
  §6.1 已經警告過**同一族**的一個陷阱（「⚠ 不要用 `git stash create` —— 它只涵蓋
  tracked 檔案，untracked 新檔會靜默漏掉」），也已經記載過一次實錄
  （`ses_0c87bab06` 的第一版快照漏掉一個 untracked 測試檔）。**本 BR 是第三個
  同族實例**：涵蓋範圍與你以為的不同，而輸出不會說——這次連 tracked 檔都是 0。
- `BR_20260802_git_mv_leaves_content_unstaged_and_a_file_counting_guard_cannot_tell.md`
  —— **same component（git 的 index/staging 狀態不可見）+ same failure class**：
  那張是「`git mv` 後內容未進 index，而數檔案的護欄看不出來」，本張是
  「index 根本沒被填充，而 `commit-tree` 看不出來」。同一個盲區的兩個切面。
- `BR_20260802_reset_hard_silently_destroyed_uncommitted_work_on_shared_tree.md`
  —— **temporal causality**：§6.1 的錨定配方**就是為了防那次事故而寫的**
  （46 個檔案的未 commit 修改永久遺失）。本 BR 說的是那道防護自己有一個
  無聲失效模式，所以它是那張的直接殘留風險。
- `BR_20260804j_the_verification_layer_has_no_verification_layer_five_instances_in_one_round.md`
  —— **same failure class**：護欄／驗證層自身靜默失效，且失效的輸出與通過逐字相同。
- `BR_20260802_stale_pyc_silently_invalidated_a_mutation_proof.md`
  —— **same failure class**：一個本該證明某事的機制沒有真的執行，而結果讀起來像它執行了。

---

## §1 一句話

`git commit-tree` **不檢查 index 是否被成功填充**。空 index 與填好的 index
對它是同一件事，兩者都產出一個合法的 commit 物件。於是
**「快照成功」與「快照是空的」共用同一個輸出：一個 40 字元的 sha。**

## §2 實錄（2026-08-05 12:25 CST，br=804l_warn_convergence）

我照 `AGENTS.md §6.1` 的配方建快照。scratch 目錄有一個先前留下的 `snapidx.lock`，於是：

```
fatal: Unable to create '.../snapidx.lock': File exists.     × 26 次
  ↑ git read-tree HEAD  失敗
  ↑ git add -- <path>   失敗 × 25
ref=c6ff0e3                                                   ← 但 ref 建出來了
```

`git commit-tree` 與 `git update-ref` **都成功**。若我停在這裡，
我會認為 25 個檔案的改動已受保護。

依 §6.1 規定逐檔驗收（**不是「ref 建好了」**）：

```
snapshot_matches=0  mismatches=25
```

**那個 ref 指向的是 HEAD 原樣，我的改動一個都不在裡面。**

控制組（證明驗收手法有判別力）：
- 對 snapshot 內不存在的路徑 `git show` → rc=128（非零）
- 重建後同一支驗收 → `matches=25 mismatches=0`
- 對假路徑的 `diff -q` → rc=1（驗證器會紅）

修正後：新 index、每步 `|| exit 1` 硬閘、驗 `entries=1368`，
重建 `refs/wip/ses_02fe2ffe8` = `3307d55`，逐檔 25/25。空 ref `c6ff0e3` 已刪除。

## §3 為什麼是 G13 而不是「我沒清 lock」

判準：**那一格資訊，系統當下有沒有？**

**有，而且印了 26 次。** git 大聲說了每一步都失敗。缺的不是資訊，是**閘**：

1. **`commit-tree` 不檢查 index 是否被填充** —— 空 index 與填好的 index 對它是同一件事，
   兩者都回一個合法 sha。它有能力知道（index 就在 `GIT_INDEX_FILE`），但不問。
2. **`AGENTS.md §6.1` 的配方本體沒有任何 `||` 閘** —— `git read-tree HEAD` 後面
   直接跟 `git add`，`git add` 後面直接跟 `commit-tree`。**照抄就會踩**。
3. **最終輸出兩態同形** —— 成功是一個 40 字元 sha，災難也是一個 40 字元 sha。

這與 §6.1 已收錄的第一個實例（`ses_0c87bab06` 的快照漏掉一個 untracked 檔）
是**同一個形狀在不同刻度上**：那次涵蓋範圍少一個檔，這次涵蓋範圍是零。
兩次都是「**我以為我快照了**」——而 §6.1 自己寫過那句話：

> 「我以為我快照了」比「我沒快照」更危險，因為它讓人停止擔心。

**本 BR 是那句話發生在防護措施自己身上的第二次。**

## §4 修法（未實作，屬 coordinator 轄區）

在 `AGENTS.md §6.1` 的配方本體加 fail-fast 閘與落地驗收，例如：

```bash
IDX=$(mktemp -d -m 700 -p "${XDG_RUNTIME_DIR:-$HOME/.cache}" snap.XXXXXX)/index
export GIT_INDEX_FILE="$IDX"
git read-tree HEAD || { echo "FAIL read-tree"; exit 1; }
for p in <要保的每個檔>; do git add -- "$p" || { echo "FAIL add $p"; exit 1; }; done
T=$(git write-tree) || { echo "FAIL write-tree"; exit 1; }
[ "$(git ls-tree -r --name-only "$T" | wc -l)" -gt 0 ] || { echo "EMPTY TREE"; exit 1; }
C=$(git commit-tree "$T" -p HEAD -m "snapshot: <what>")
git update-ref "refs/wip/<session-id>" "$C"
unset GIT_INDEX_FILE
```

關鍵是 **`mktemp` 保證新路徑**（避開 stale lock）＋**每步 `||` 閘**＋
**`entries > 0` 斷言**。§6.1 現有的「逐檔 `git show` 驗收」規定要保留——
它正是這次唯一抓到問題的東西。

## §5 量了什麼 / 沒量什麼

**量了**：26 次 `fatal` 的原文、失敗後仍產出的 ref、逐檔驗收 0/25、
修正後 25/25、三組控制組（不存在路徑 rc=128、驗證器對假路徑 rc=1、重建後全綠）。

**沒量**：
- `commit-tree` 在**其他** index 異常態（部分填充、損壞）下的行為 —— **未測**。
  本 BR 只證明了「完全空」這一態。
- stale lock 的來源 —— 未追查是哪個先前程序留下的。
- 這個配方在別的 repo 被照抄了幾次 —— **未查**，且與修法無關。


## §2 實錄（2026-08-05，804l WARN 收斂任務中）

照 §6.1 配方建快照，實際輸出：

```
fatal: Unable to create '.../snapidx.lock': File exists.      × 26 次
（git read-tree 失敗、25 次 git add 全部失敗）
ref=c6ff0e3                                                    ← ref 仍然建出來了
```

`git read-tree` 與**全部 25 次 `git add` 每一次都失敗**（stale lock），
而 `git commit-tree` **照樣成功**、`git update-ref` **照樣成功**。

逐檔驗證才抓到：

```
snapshot_matches=0 mismatches=25
```

**那個 ref 指向的是 HEAD 原樣，25 個改動一個都不在裡面。**

控制組（證明驗證器有牙）：
- 對不存在路徑 `git show <ref>:<bogus>` → rc=128
- 驗證器對假路徑比對 → rc=1（非零）
- 修好後重驗 → `snapshot_matches=25 mismatches=0`

## §3 為什麼是 G13 而不是「我操作失誤」

判準：**那一格資訊，系統當下有沒有？**

**有，而且印了 26 次。** git 明明大聲報了 `fatal`。缺的是三件事：

1. **`commit-tree` 不檢查 index 是否被填充** —— 空 index 對它是合法輸入。
2. **§6.1 配方本身沒有任何 `||` 閘** —— `git read-tree HEAD` 後面直接跟
   `git add`，照抄就會踩。配方是給人照抄的，而它把 fail-fast 留給讀者自己想。
3. **最終輸出無法分辨** —— 成功態與災難態都是一個 40 字元的 sha。

這正是 §6.1 自己那句話的實地重演：

> **「我以為我快照了」比「我沒快照」更危險，因為它讓人停止擔心。**

而這次它**發生在防護措施自己身上**——§6.1 已經為此警告過一次
（`git stash create` 漏 untracked），本 BR 是同一形狀的第三個實例。

## §4 修法（未落地）

在 §6.1 配方的每一步加 fail-fast，並把**逐檔驗證**從「建議」升為配方的一部分：

```bash
git read-tree HEAD || { echo "FAIL read-tree"; exit 1; }
for p in <paths>; do git add -- "$p" || { echo "FAIL add $p"; exit 1; }; done
T=$(git write-tree) || exit 1
[ "$(git ls-tree -r --name-only "$T" | wc -l)" -gt 0 ] || { echo "EMPTY TREE"; exit 1; }
```

**驗收必須逐檔 `git show <ref>:<path>` 比對，不是「ref 建好了」**
——§6.1 已經寫了這句話，但配方本身沒有強制它。

## §5 量了什麼 / 沒量什麼

**量了**：26 次 fatal 的原文、`mismatches=25`、修好後 `matches=25 mismatches=0`、
三組控制組（假路徑 rc=128 / rc=1、`entries=1368`）。

**沒量**：
- stale lock 的成因 —— 未追查（可能是先前 `GIT_INDEX_FILE` 指向同一路徑的殘留）。
- `commit-tree` 是否有任何旗標可要求非空 index —— **未查 man page**。
- 其他 session 是否也踩過同一格 —— 未查。
