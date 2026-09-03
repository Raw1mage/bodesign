# event 2026-09-03 — capability-sync 手寫標本在修法裁決前被 resync 消耗

**狀態**：已發生，不可逆。本檔是全系統唯一倖存的 pre-resync 記錄。
**全文過去式敘述** —— 這裡描述的是已完成的事實，日後 marker 再被誰 resync 都不會使本檔變假。

## 1. 這件事是什麼

`~/.local/share/opencode/skills/bodesign/` 是 capability-sync 從 repo SSOT
（`skills/bodesign/`）投影出來的 leaf。2026-09-03 上午，bodesign 值星官授權 handler
以手動 copy 把兩個檔送進該 leaf，**沒有更新 `.capability-installed.json`**。於是 marker 的
`projectionHash` 停在七月的投影值，而磁碟上是九月的內容 —— capability-sync 把這個狀態
分類為 `xdg-drift`。

opencode repo 的值星官（`ses_fb6d912c2`）當時正在調查 family
`capability-sync-winner-undecidable`（`~/.local/share/opencode/skills/<name>/` 有多個互不
知情的 writer，capability-sync 會比 hash、發現 drift 就停手，於是唯一守規矩的 writer 必然
墊底）。他指出 bodesign 這顆是**現地活標本**：全系統唯一一個「成因已知、成因是手寫、
marker 停在六週前」的實例，且同 repo 的 `bodesign-kb` 構成天然對照組（同機制、同一天、
但沒被手寫過 ⇒ marker 正常）。他建議在修法方向裁決前保留它。

bodesign 值星官採納並發出 HOLD。**HOLD 抵達 handler session 時，resync 已於三分鐘前執行完畢。**

## 2. 時序

| 時刻 | 事件 |
|---|---|
| 2026-07-21 10:10:28 | marker `installedAt` —— 最後一次正常投影 |
| 2026-07-23 08:29:08 | marker mtime —— 最後一次被寫入（TTL 探測） |
| 2026-09-03 10:27:55.756057951 | published `SKILL.md` 的 mtime |
| 2026-09-03 10:57:13.854952933 | published `references/deliverable-content-criteria.md` 的 mtime |
| 2026-09-03 ~15:50 | opencode 值星官觀察到 bodesign 在 drift 清單裡 |
| 2026-09-03 17:22 | handler 完成 Step 0 快照（published / repo / bodesign-kb 三份 sha256 全表） |
| 2026-09-03 17:22–17:24 | handler 跑 read-only `skill status`、讀 opencode 原始碼確認 `--accept-source` 語意 |
| **2026-09-03 17:25:02** | **`opencode skill resync bodesign --accept-source` 執行，標本消耗** |
| 2026-09-03 17:25–17:26 | handler 完成驗證三格 + grep 四處 |
| 2026-09-03 17:26 | handler 依派工單清除 `$XDG_RUNTIME_DIR` scratch |
| 之後 | HOLD 抵達 handler session |

兩次手寫相隔 29 分鐘，是兩次獨立動作而非一次批次 —— 依據是兩檔 mtime 不同秒。
**（不要據此推論用的是哪種 copy 指令，見 §7。）**

handler 依派工單執行，時序無誤。dispatcher 事後自陳：他在發 HOLD 之前，
對 opencode 值星官宣告了「Step 2 尚未執行」，那是讀了一個必然過期的中途快照當終局狀態，
且沒有先驗證 HOLD 是否真的攔到就報告出去。

## 3. 消耗的那一刻（逐字）

```
$ opencode skill resync bodesign --accept-source
[self-heal] baseline check: pulled=3 merged=0 needs-user-action=0 missing-source=1
[self-heal] no template source for: .gitignore
= bodesign/bodesign-kb: already current
✓ bodesign/bodesign: reconciled (xdg-drift → 644b4eebbbd6)
RESYNC_RC=0
```

`xdg-drift` 這個 state 就是標本本體，`reconciled` 就是它被消耗的動詞。

## 4. pre-resync marker 全文（**本檔存在的主要理由**）

以下 520 bytes 是消耗前 `~/.local/share/opencode/skills/bodesign/.capability-installed.json`
的逐字內容。它在磁碟上已不存在，此處是唯一副本。

```json
{
  "id": "bodesign",
  "kind": "skill",
  "version": "0.0.0+a961fd43915f",
  "schemaVersion": 1,
  "sourceHash": "a961fd43915f833c021f533c298f6350a56b5ebdfb4245d1211ba24d2cfccab3",
  "projectionHash": "aa5c109be0d1b440fb0152913143d59557ede5ca7811e1fa418754841f7ae3bf",
  "sourceRepoPath": "/home/pkcs12/projects/bodesign",
  "projectionPath": "/home/pkcs12/.local/share/opencode/skills/bodesign",
  "installedAt": "2026-07-21T10:10:28.408Z",
  "syncToolVersion": "1",
  "probeCachedUntil": "2026-07-23T01:29:08.744Z"
}
```

- 該檔的 sha256：`3d1aff8d00a895fcb24965c1b5c3f331d5a8f65dfd4574e2aec482bcf69ba38b`
- 該檔的 mtime：`2026-07-23 08:29:08.732670471 +0800`
- 大小：520 bytes

## 5. post-resync marker（對照）

| 欄位 | pre-resync | post-resync |
|---|---|---|
| mtime | `2026-07-23 08:29:08.732670471` | `2026-09-03 17:25:02.178881859` |
| `version` | `0.0.0+a961fd43915f` | `0.0.0+644b4eebbbd6` |
| `sourceHash` | `a961fd43915f833c…ccab3` | `644b4eebbbd6e9da…85a41` |
| `projectionHash` | `aa5c109be0d1b440…ae3bf` | `dd857568cf96e7b0…fde7a` |
| `installedAt` | `2026-07-21T10:10:28.408Z` | `2026-09-03T09:25:02.182Z` |
| `probeCachedUntil` | `2026-07-23T01:29:08.744Z` | `2026-09-03T10:25:02.183Z` |
| `sourceRepoPath` | `/home/pkcs12/projects/bodesign` | 未變 |

四個 hash 欄全部改值，不只 mtime —— 這一格是分兩次量的，因為
「只 touch 檔案而沒重算 hash 的 resync」與「正確的 resync」共用「mtime 變了」這個輸出。

**172 個 content 檔的 bytes 一個都沒被動。** 全樹 sha256 before/after 逐檔比對，
唯一差異是 `.capability-installed.json` 那一行；控制組（竄改 after 表第 5 行後 diff 立即報 `5c5`）
證明該探針在該紅時會紅。4 條 symlink 指向不變。

## 6. 對照組 `bodesign-kb`

`opencode skill resync bodesign` 的 `<target>` 同時匹配 app id，而 `bodesign` 正是 app id，
所以同 app 的 `bodesign-kb` 也被納入該次呼叫。實際發生的變化：

| 欄位 | before | after |
|---|---|---|
| `SKILL.md` mtime（唯一 content 檔） | `2026-07-04 23:31` | 未變 |
| `projectionHash` | `9e3f718205e77eced40ff64da77d7e26ac6d71adf8e78e205dd036a21a61c8b6` | **逐字未變** |
| `sourceHash` / `version` / `installedAt` | — | 全未變（`installedAt` 仍 `2026-07-04T15:32:05.747Z`） |
| `probeCachedUntil` | `2026-09-03T09:38:08.602Z` | `2026-09-03T10:25:01.582Z` |
| marker mtime | `2026-09-03 16:38:08` | `2026-09-03 17:25:01` |

CLI 對它的判定是 `= bodesign/bodesign-kb: already current`，走 `outcome === "current"` 分支，
未 reconcile、未覆寫。

- **損失的性質**：「這顆 marker 從未被今天的任何動作觸碰」。
- **倖存的性質**：「hash 從未變過、從未 drift、`installedAt` 仍是七月」。

若研究需要前者，該格已不可用；若只需要後者，對照組完整。

## 7. 這次量錯了什麼 —— mtime 奈秒相同被當成 `cp -p` 指紋

handler 在回報中寫過：「repo 側與 published 側同兩檔的 mtime 奈秒級逐字相同，
這正是 `cp -p` / `cp -a` 保留 mtime 的指紋」，並據以推論手寫用的是哪種 copy 指令。

dispatcher 跑了一個 handler 沒跑的控制組：一個**從未被手寫過的檔**。

```
SKILL.md                      (手寫過)  published 10:27:55.756057951 == repo 10:27:55.756057951
deliverable-content-criteria  (手寫過)  published 10:57:13.854952933 == repo 10:57:13.854952933
stages/c00-prd/GUIDE.md       (沒手寫)  published 09:10:49.433773803 == repo 09:10:49.433773803   ← 也相同
負控 bogus path → rc=1（stat 探針有牙）
```

**沒被手寫過的檔也奈秒相同** —— 因為 `resync` 用的是 `rsync -a --checksum`
（`packages/opencode/src/capability-sync/sync.ts:104`），`-a` 同樣保留 mtime。
**所以「奈秒相同」是這棵樹的基線，不是手寫的簽名。** 該推論在 post-resync 的樹上不可判定。

**根因是母體選擇，不是量錯數字**：handler 只比了「已知被手寫的那兩檔」，
而判別一個特徵是不是簽名，必須有一個**不帶該特徵的對照**。
與本 repo 反覆處理的形狀同族（`^\**Status\**:` 把合規檔讀成缺席、
帶 pathspec 的 `git status` 被當成全域結論），這次的載體是 mtime。

**仍有一條路可能讓該推論成立，但需不同論證**：pre-resync 時 rsync 尚未跑過
（marker 停在 07-23），所以 rsync 無法解釋那時的 mtime 相同。若能證明
「pre-resync 時 published 全樹只有這兩檔的 mtime 與 repo 相同、其餘不同」，
那 `cp -p` 的推論就站得住。handler 的 Step 0 快照只存了 hash 全表、
**沒存 mtime 全表**，所以該格在本檔寫成時不可判定，未作為證據送給 opencode。

## 8. 另一格發現：`skill resync <target>` 的作用域在執行前不可知

依 handler 閱讀 `packages/opencode/src/mcp/skill-resync.ts:69`，target 篩選是
`id !== target.value && skillName !== target.value` —— **app id 與 skill name 兩者皆匹配**。
`bodesign` 同時是 app id（bundle 了 `bodesign` 與 `bodesign-kb` 兩顆）與 skill name，
因此一次呼叫必定碰兩顆。CLI help 逐字寫的是「MCP app id **or** skill name」，
且 `resync` **沒有 `--dry-run`**（旗標表只有 `--all` / `--accept-source` / log 選項）。

於是「我以為我只碰一顆」與「我碰了兩顆」在執行前無法分辨。
本次派工單的 Boundaries 寫了「不要動 `bodesign-kb`」，**而 CLI 沒有任何方式能遵守它**。

> 本節引用的是 handler 的原始碼閱讀，dispatcher 未複驗。

## 9. 重建配方（**尚未執行**）

標本的本體是「marker 的 hash 欄位對不上磁碟內容」這個**狀態**，不是一次性物理事件。
構成它的三件材料在本檔寫成時都還在：

1. pre-resync marker 全文（§4，520 bytes 逐字）
2. 172 個 content 檔的 bytes —— resync 從未動過它們
3. 因果鏈（§2 時序）

配方：把 §4 的 JSON 原封寫回 `.capability-installed.json`，再用
`touch -d '2026-07-23 08:29:08.732670471'` 還原奈秒。`opencode skill status bodesign`
會再次回報 `drifted (projection hand-edited)`，理由與原本同構。

**未執行，且不由 bodesign 單方發動。** dispatcher 的裁示是 (b)：

1. 重建是又一次手寫進 published，而同一輪正在 `AGENTS.md` 寫下「禁止手動 `cp`」——
   規則生效前一刻自己破例，那條規則之後不會有人當真。
2. 重建品是否構成可用證據，決定權在需要它的人（opencode 值星官），不在 bodesign。
3. 重建隨時可做且成本不變；**不做的代價為零，做錯的代價不可逆**。

## 10. 連帶產出：揭露缺口已補

同一輪實測了「正確做法寫在哪裡」，三處皆無（各配正負控制組、絕對路徑）：

| 探針 | 結果 | 正控制 |
|---|---|---|
| `grep -n 'resync' AGENTS.md` | 空 rc=1 | `grep -c 'mcpctl'` = 5；299 行 |
| `grep -n 'resync' skills/bodesign/SKILL.md` | 空 rc=1 | `grep -c 'bodesign'` = 38；467 行 |
| `grep -rn 'resync' ~/.local/share/opencode/skills/bodesign/` | 空 rc=1 | 173 檔被掃，`bodesign` 命中多檔 |

負控（bogus token）三處皆 rc=1。第二種寬度（`skill resync\|capability-sync\|\.local/share/opencode`）
對 SKILL.md 仍空；對 published 樹有 9 個命中，但全部是「skill 執行環境沒有 `packages/`」
的同一句樣板 + marker 自己的 `projectionPath` 欄，沒有一處講部署方式。

正確做法當時只寫在：
- `specs/quality/readiness-enforces-guide-definition-of-done/handoff.md:31`
- `specs/quality/readiness-enforces-guide-definition-of-done/tasks.md:55`
- `issues/closed/issue_20260623_readiness_only_checks_state_not_guide_dod.md:103`

三處全在 `specs/` 或 `issues/closed/` —— 一個正要部署 skill 的 agent 沒有理由
在那個當下打開它們。而 `AGENTS.md` §3 的標題逐字是「Runtime / 啟動（**唯一入口**）」，
它宣稱了完整性卻只講容器 —— 這不只是「沒寫」，是寫了一個會誤導的完整性宣稱。

本輪已在 `AGENTS.md` §3 補上 skill 投影段（+17 行）。

## 11. 還沒量的

- **marker 正確 ≠ 記憶體裡的 skill 是新的**。`resyncOne` 傳了 `reload: Skill.reset`，
  但那是 CLI 進程內的 reset；跑著的 daemon/session 有沒有重讀，本輪未驗。
- **其餘 8 顆 capability-sync 管轄的 skill** 有無 drift，本輪未查（不在射程）。
- **pre-resync 的 mtime 全表**。Step 0 只存了 hash，這是 §7 那格無法收尾的直接原因。
  下一次拍基準快照時，**hash 與 mtime 兩者都要存** —— 它們回答不同的問題。

