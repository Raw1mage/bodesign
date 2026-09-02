# BR_20260804l — `issues/` 帳本沒有 Status schema：兩支合理的 sweep 對同一批檔案回不同答案，而「沒有 Status」與「Status 在我的視窗外」共用同一個輸出

- **Status**: PARTIAL — schema 已定、checker 已落地並帶內建控制組（`d63566d`，實作選項 1+3）；格式收斂**已完成並已 commit（`fcd6fcc`，WARN 24 → 0）**；2026-09-02 重量測確認 49/49 全部 canonical、ERROR=0、WARN=0（§11）。**建議升 FIXED，歸檔待 dispatcher 裁決（見 §11.5）**

| Field | Value |
| --- | --- |
| Title | The issues/ ledger has no Status schema, so a header-scoped sweep silently reports 8 files as having none when only 3 do |
| Component | 流程／harness 揭露（`issues/*.md` 帳本格式），非程式缺陷 |
| Owner | `ses_04db7a1c5ffelvbxyLP1p6xlRH`（coordinator，`(default)` family） |
| Reporter | `ses_04db7a1c5ffelvbxyLP1p6xlRH` — 在結算兩張 header/body 矛盾的 BR 時撞出 |
| Date | 2026-08-04 |
| Severity | medium — 不影響 runtime。危害是**排程判斷**：讀者用哪支 sweep 決定了它看到幾張未結案 BR |
| Family | `G13-harness-disclosure` |
| Affected paths | `issues/*.md`（頂層 40 張） |

**Related**：
- `BR_20260802_issues_ledger_committed_on_archive_not_on_filing.md`（**同一份帳本、不同缺陷面**：那張管「BR 有沒有進版控」，本張管「BR 的狀態能不能被機器讀出來」。兩張都不覆蓋對方——一張全部進了版控的帳本，仍然可能每張的 Status 寫法都不同）
- `BR_20260804k_*.md`（同族失敗形狀：狀態存在但不被表面化）
- `AGENTS.md §6.1` pathspec 陷阱（**同一個形狀的上位敘述**：帶範圍限定的 `git status` / `grep` / `ls` 與不帶的輸出形狀完全一樣，沒有任何標記說結果被過濾過。本 BR 是它在 `issues/` 帳本上的具體實例）

---

## §1 一句話

`issues/` 的 Status 行**沒有 schema**——40 張頂層 BR 用了 7 種寫法，且 5 張的 Status 在第 23–26 行而非 header。於是**一支只掃 header 的 sweep 會回報 8 張「沒有 Status」，而全檔掃描回報 3 張**，兩者都不會說自己掃了哪個範圍。

## §2 量測（可重跑，全部帶控制組）

```bash
cd /home/pkcs12/projects/bodesign/issues

# A：格式直方圖（每檔第一條 Status-ish 行的行號與寫法）
for f in BR_*.md; do
  L=$(grep -n -m1 -E '^[-*# ]*\**Status\**[:：]' "$f" | head -1)
  if [ -z "$L" ]; then echo "NONE|$f"
  else N=${L%%:*}; T=$(echo "$L" | sed -E 's/^[0-9]+://' | sed -E 's/(Status\**[:：]).*/\1/'); echo "LINE$N|$T|$f"; fi
done | awk -F'|' '{print $1"\t"$2}' | sort | uniq -c | sort -rn
```

實測（2026-08-04，頂層 40 張）：

| 次數 | 行號 | 寫法 |
| --- | --- | --- |
| 11 | LINE3 | `- **Status**:` |
| 8 | LINE3 | `**Status**:` |
| 4 | LINE7 | `- **Status**:` |
| 3 | LINE6 | `- **Status**:` |
| 3 | **LINE23** | `Status:` |
| 2 | LINE3 | `Status:` |
| 1 | LINE5 / LINE4 / LINE4 / LINE3 / **LINE26** / **LINE24** | `- **Status**:` / `- Status:` / `- **Status**:` / `- Status:` / `Status:` / `Status:` |
| 3 | — | **NONE** |

**7 種格式變體，行號分佈 3–26。**

### §2.1 決定性的一格：兩支 sweep 對同一語料回不同答案

```
header-only（只看 1..10 行）   NONE = 8
full-file                      NONE = 3
CONTROL  含 ATX heading 的檔 = 40/40   <- 證明兩支都真的讀到了全部 40 個檔
```

差的 5 張，Status 埋在 line 23/24/26。**控制組排除了「其中一支根本沒讀到檔」這個解釋**——兩支都讀了，只是視窗不同。

header-only sweep 誤報為「沒有 Status」的 8 張：

```
BR_20260707_bom_proposal_workflow_no_ssot_preread_conflicted_owner_dd.md     真的沒有
BR_20260719_c01_readiness_folder_arg_double_prefix.md                        真的沒有
BR_20260719_c02_readiness_provenance_root_and_dod_surface.md                 真的沒有
BR_20260730_skills_endpoint_serves_targz_and_advertises_filenames_not_r9_zip.md   誤報
BR_20260731_vacuous_pass_empty_input_reads_as_verified_in_gates.md               誤報
BR_20260802_freerouting_jar_default_path_contradicts_install_path.md             誤報
BR_20260802_issues_ledger_committed_on_archive_not_on_filing.md                  誤報
BR_20260802_reset_hard_silently_destroyed_uncommitted_work_on_shared_tree.md     誤報
```

**後 5 張是有 Status 的**，其中包含 `reset_hard`（severity high）與 `issues_ledger`（severity high）——**一支合理的 header sweep 會把兩張 high severity BR 歸進「狀態不明」桶**。

## §3 為什麼是 G13 而不是「我 grep 打錯了」

判準是 **「那一格資訊，系統當下有沒有？」**

**有。** Status 就在檔案裡，第 23 行。是 sweep 的視窗把它切掉的，而 sweep **不揭露自己的視窗**——`grep` 對 `sed -n '1,10p'` 之後的輸入回空，與對整個檔案回空，形狀完全相同。

這與今日已收錄的同族實例是同一形狀：

| 實例 | 缺席態 | 失敗態 | 共用的輸出 |
| --- | --- | --- | --- |
| `git worktree remove` | 沒有未 merge commit | 有未 merge commit | exit 0 + 全空 |
| `jq '.f'` | 欄位不存在 | 值為 null | `null` |
| `bun test <bad-path>` | 全部通過 | 路徑不存在被靜默丟棄 | exit 0 |
| **本 BR** | **這張真的沒有 Status** | **Status 在視窗外** | **sweep 回 NONE** |

## §4 危害：它作用在排程上，不在 runtime 上

三種讀法各自得到不同的未結案清單：

```
讀 header      -> 8 張狀態不明（其中 5 張其實有，2 張 high severity）
讀全檔第一條   -> 3 張狀態不明
讀全檔最後一條 -> 又不同（今天已實測到兩張頭尾矛盾，見 337ef16）
```

**而三種讀法都「看起來成功」**——沒有一種會說「我可能漏了」。今天已經實際發生兩次：

1. 我自己第一支 grep 用 `^Status:` 對 `BR_20260719` 回空，**我當下的反應是「我打錯了」**（§8.5 觸發條件）。實際上那三張是真的沒有，但我當時無法從輸出分辨。
2. 兩顆獨立盤點 subagent 的 NO-STATUS 清單逐字相同（3 張），而我自己的 header sweep 回 8 張——**若我只跑了自己那支，我會排程 5 張不需要排程的 BR**。

## §5 修法（未裁示）

**選項 1 — 定 schema，加 checker（建議）**
- `issues/README.md` 或 `AGENTS.md` 明訂：Status **必須**是第 3 行、格式 `- **Status**: <OPEN|PARTIAL|FIXED|CLOSED> — <一句話>`
- 一支 `scripts/check_issue_headers.sh`：任何不符者 fail loud 並印出行號與實際內容
- **checker 本身要有控制組**：對一個刻意寫錯的 fixture 必須紅，否則它只是另一支回空的 grep

**選項 2 — 只補三張缺的，不定 schema**
成本低，但**不解決根因**：下一張新 BR 仍可自創第 8 種寫法，而 5 張埋在 line 23 的仍然會被 header sweep 漏掉。

**選項 3 — 讓 sweep 揭露自己的視窗**
任何掃描腳本回報時必須同時印 `scanned N files, window=<range>`。這是 §3 的直接對症，但它治的是讀者側，寫入側的 7 種格式仍在。

我傾向 **1 + 3**：1 治寫入側，3 治讀取側，而**兩側各自都會單獨失效**。

## §6 量了什麼 / 沒量什麼

**量了**：40 張的格式直方圖、兩支 sweep 的差值（8 vs 3）、控制組（40/40 檔案可讀）、5 張誤報檔名逐一列出、既存 BR 未覆蓋本格（控制組：`grep -l 'Status'` 回 37 證明搜尋有牙）。

**沒量**：
- `issues/closed/` 裡的格式分佈——本 BR 只掃頂層。closed 的 Status 已無排程意義，但若要寫 checker，它會不會對 closed 全部報錯**未查**。
- 這 7 種格式是否對應不同的作者 session——**未查**，且我不打算查：修法與作者是誰無關。

## §7 三張 NONE 的實況（已補，2026-08-04）

派唯讀調查員 `ses_032bd6158` 判定，我親手覆核兩個載重主張後補入：

| 檔 | 已補 Status | 依據 |
| --- | --- | --- |
| `BR_20260707_bom_proposal_...` | **FIXED** | GUIDE.md `:222` §3c 必讀清單、`:250` 自查段、gate.py `:232` `check_c03` + `:239` `prd_bom_crosscheck` |
| `BR_20260719_c01_readiness_...` | **PARTIAL** | `44deecb` 修了內部契約；但 `grep -c stage_dir_arg_detail c01_id_package.py` = **0**（控制組：c02 回 2），且 `readiness_common.py:75-77` 碼註解自承 still reproducible at HEAD |
| `BR_20260719_c02_readiness_...` | **FIXED** | `c02_me_package.py:772`/`:847` 兩個 provenance 呼叫點都走 `_c02_stage_dir`；`:156` 接上 `guide_compliance_for` |

控制組：假 section `ZZZNOSUCHSECTION` 回 0、假 verb `"check_c99"` 回 0、假 sha `deadbee` 回 `fatal: unknown revision`。

補完後重跑兩支 sweep：`header-only 8 -> 6`、`full-file 3 -> 1`。

## §8 我在寫這張 BR 的當下遷了它自己譴責的那件事

上方 `full-file NONE = 1` 剩下的那一個，**就是本檔**。

我把 Status 寫在 `| Field | Value |` 表格裡（`| Status | OPEN |`），
而本檔 §5 選項 1 提議的 schema 是「第 3 行、格式 `- **Status**: <值>`」。
**一張主張「帳本需要統一格式」的 BR，自己用了第 8 種格式。** 已改。

這不是自嗣而已——它是 **§5 選項 2（只補不定 schema）不夠的直接證據**：
寫入者在沒有機械閘的情況下會自創格式，**即使他正在寫的就是那條規則**。
本 repo 今日已第三次碰到這個形狀（`AGENTS.md §6.1` 的 `reset --hard` 實錄是第一次）：
**正在寫某條規則不構成該規則的豁免。**

⇒ 強化 §5 的裁定建議：**選項 1（schema + checker）是必要的，選項 2 已被本段實測否證**。

## §9 殘餘（header-only NONE 還有 5 張）

這 5 張有 Status，但在 line 23/24/26：

```
BR_20260730_skills_endpoint_serves_targz_...
BR_20260731_vacuous_pass_empty_input_...
BR_20260802_freerouting_jar_default_path_...
BR_20260802_issues_ledger_committed_on_archive_...      <- severity high
BR_20260802_reset_hard_silently_destroyed_...           <- severity high
```

**我刻意不在本輪搬它們**：搬位置就是實施 §5 選項 1 的一半，
而那個選項還未裁示、checker 還沒寫。**先搬完再寫 checker，會讓 checker 失去它唯一的真實負例**
——一支從未在真實資料上紅過的 checker，與一支壞掉的 checker 共用同一個輸出。

## §10 裁決與實作（2026-08-05，`d63566d`）

值星官裁定 **選項 1 + 3**（§5 傾向已由 §8 實測否證選項 2）。已落地：

| 交付物 | 檔 | 治哪一側 |
| --- | --- | --- |
| schema 定義 | `issues/README.md` | 寫入側——canonical `- **Status**:` line-3 + 四態 |
| checker | `scripts/check_issue_headers.sh` | 讀取側——全檔掃描 + 揭露視窗 `scanned N, window=full-file` |
| pre-commit 接線 | `scripts/hooks/pre-commit` | 決策點（commit time）warn-only |

**§9「唯一真實負例」的顧慮已由永久 fixture 解決**，不再依賴那 5 張暫不搬：
`issues/.schema-fixtures/` 兩個檔（一保證 ERROR、一保證 clean），checker 每次跑先自測，
任一翻轉就拒絕對真實資料下判。這把「唯一真實負例」從一次性的暫存狀態，
升級成**永久的、每次跑都存在的控制組**——§9 那 5 張現在可以安全收斂而不影響 checker 的牙。

### checker 判準（兩級）

- **ERROR（rc=1）**：全檔零條 Status-ish 行 → 真排程危害。實測負例＝ERROR fixture。
- **WARN（rc=0）**：有 Status 但非 line-3 canonical 形式 → 收斂用，不擋。

實測（**歷史快照：`d63566d` 落地當下**，41 張頂層。**這三個數字皆已過期，當前值見緊接著的更正框**）：
```
self-test: no-status fixture -> ERROR （控制組有牙）
self-test: canonical fixture -> OK
scanned 41 file(s), window=full-file
ERROR = 0        <- 沒有一張是真的零 Status（§7 已補齊那 3 張）
WARN  = 26       <- 格式收斂 backlog，見下
```

> **量值更正（2026-08-05 12:2x CST，by `ses_02fe2ffe8ffe0y33B8FszeyVvM`）**：
> 上方區塊是 **`d63566d` 落地當下的快照**，三個數字全部不是現況，
> 而它們**未帶任何時間錨**——這正是 `BR_20260805c` 描述的缺陷，
> 發生在記錄該缺陷家族的帳本自己身上。以 **2026-08-05 checker 實測為準**：
>
> | 欄位 | `d63566d` 快照 | 2026-08-05 實測 |
> | --- | --- | --- |
> | `scanned` | 41 file(s) | **47 file(s)** |
> | `ERROR` | 0 | 0（未變） |
> | `WARN` | 26 | **0**（收斂前為 24，非 26） |
>
> 歷史區塊保留不刪（它是 `d63566d` 當下的真實輸出），
> 但任何引用請以本更正框為準。`41 → 47` 的差額成因未查。

### 殘留：格式收斂 — **已於 2026-08-05 完成（WARN 24 → 0）**

> **量值更正（2026-08-05 12:21 CST，by `ses_02fe2ffe8ffe0y33B8FszeyVvM`，BRNS handler）**：
> 本節原寫「26 張 WARN」且**未帶時間錨**，讀起來像現況而實為快照
> （即 `BR_20260805c` 描述的缺陷）。於基底 commit `cf0f62f` 實測為 **24 張**，非 26。
> 差額來源未查（可能是 `d63566d` 之後有兩張被別人順手收斂或歸檔）——
> 本次只重新量測，不回推歷史。

**收斂前**（量測於 2026-08-05 12:10 CST，基底 commit `cf0f62f`）：
`WARN = 24`、`ERROR = 0`、`rc = 0`，checker 自報 `scanned 47 file(s), window=full-file`，
self-test 雙綠。這 24 張都**有** Status（checker 綠、不擋 commit），只是不在 line-3
canonical 形式（裸 `Status:`、缺列表前綴的 `**Status**:`、或深埋 line 4/5/6/7/23/24/26）。

**收斂後**（量測於 2026-08-05 12:21 CST，同一基底 `cf0f62f` + 工作樹未 commit 修改）：
`WARN = 0`、`ERROR = 0`、`rc = 0`，self-test 雙綠。
**壞掉控制組**：把其中一張的 line 3 改回裸 `Status:` 後重跑，checker 回到
`WARN: 1` 並點名那一張；還原後輸出與壞掉前逐字相同——證明 `WARN = 0`
不是因為 checker 瞎了。

收斂手法分兩類，**語意狀態一字未改**（OPEN / PARTIAL / FIXED 逐字保留）：

- **20 張**：原 Status 行補上 `- ` 列表前綴、或整行上移至 line 3（純搬遷，不新增不刪除）。
- **4 張**（`BR_20260730_skills_endpoint`、`BR_20260802_freerouting_jar`、
  `BR_20260802_issues_ledger_committed`、`BR_20260802_reset_hard_silently`）：
  Status 位於結構化 State 區塊內（`Fix:` / `Effect:` / `Custody:` / `Blocker:` /
  `Disposition:` / `Venue:` / `Status:` 一整組）。**搬走它會拆壞那筆記錄**，
  故改為在 line 3 **新增**一行 canonical Status 鏡射區塊內的值，區塊原封不動。
  其中三張為逐字鏡射；`BR_20260730` 因原 Status 是四行換行段落，line 3 寫成
  同語意縮寫（態詞 `PARTIAL — deliberately NOT closed` 逐字相同，
  尾句改指向 State 區塊與 §13）——**這是唯一一張 line 3 非逐字複寫者**。

**尚未裁決**：本 BR 是否由 PARTIAL 升 FIXED、是否移 `closed/`——依權責歸 dispatcher，
handler 不自行改語意狀態。handler 的理由見回報。

---

## §11 補充量測（2026-09-02，by `ses_f9e79b665ffew786CUnKAKi2jA`，BRNS handler）

**本節不更正 §1–§10 的任何結論。** 起因是 dispatcher 用一支**本 BR 從未使用過的**
pattern 盤點帳本，得到「42 張沒有 Status」，懷疑本 BR 的歸因（「ledger 沒有 schema」）
是錯的。重量測結果：**本 BR 的歷史結論在其自身脈絡下完全成立且可逐字複現**，
而那 42 是**第三支 pattern 的視窗效應**——正是本 BR §3 描述的同一個缺陷，
第三次發生在本 BR 自己身上（§8 是第一次，§10 的過期快照是第二次）。

### §11.1 三支 pattern 不是同一支（這是全節的關鍵）

| 代號 | pattern | 出處 |
| --- | --- | --- |
| **P-BR** | `^[-*# ]*\**Status\**[:：]` | 本 BR §2 自己用的（容忍 list 前綴、ATX、全形冒號） |
| **P-CANON** | `^- \*\*Status\*\*:` 且在 line 3 | `issues/README.md:13` 定的 canonical schema |
| **P-STRICT** | `^\**Status\**:` | **dispatcher 2026-09-02 臨時寫的**，本 BR 與 checker 皆未使用 |

P-STRICT **依定義排除 canonical 形式**——`- ` 前綴不在它的字元集裡。實證：

```
$ printf -- '- **Status**: OPEN — x\n' > canon.txt ; grep -c -E '^\**Status\**:' canon.txt
0        rc=1     <- canonical 形式對 P-STRICT 是「不存在」
$ printf -- '**Status**: OPEN — x\n'   > bare.txt   ; grep -c -E '^\**Status\**:' bare.txt
1        rc=0     <- 只有裸形式才命中
```

所以「P-STRICT 回 7」讀作「**42 張沒有 Status**」是錯的；正確讀法是
「**42 張是 canonical，7 張檔內另有一條裸 Status 行**」。**P-STRICT 量到的是
schema 遵循度的補集，不是缺席。** 它把「合規」渲染成「缺席」——
與 §3 表格裡那四列同構，只是這次視窗不是行號範圍而是**格式集合**。

### §11.2 對本 BR 當時檔案集（40 張，`5e13dbe^`）的複現

以 `git archive 5e13dbe^ issues/` 取出 2026-08-04 backfill 前的原始 40 張，逐字重跑：

```
files_extracted=40
P-BR  header-only(1..10) NONE = 8      <- §2.1 記載 8   ✅ 逐字複現
P-BR  full-file          NONE = 3      <- §2.1 記載 3   ✅ 逐字複現
P-STRICT full-file       NONE = 23     <- 第三支 pattern，本 BR 從未主張過這個數
CONTROL  含 ATX heading 的檔 = 40/40    <- 40 個檔都真的被讀到
CONTROL  假 pattern '^ZZZNOSUCHTOKEN' = 0/40  <- 探針不是什麼都 match
```

**§2.1 的 8 與 3 在其原始語料上逐字成立。** 兩個控制組分別排除了
「其中一支沒讀到檔」與「探針無牙」兩個替代解釋。

### §11.3 對現況檔案集（49 張，HEAD）的量測

```
total=49
P-STRICT  命中 = 7
P-BR/loose 命中 = 49        <- 零張真的沒有 Status
P-CANON（'- **Status**:' 且在 line 3）= 49/49   <- 100% 遵循 schema
genuinely_none（loose 掃全檔）= 0
```

**控制組（這一格 dispatcher 的版本無效，見 §11.6）**：

```
repo-root README.md  → 0  rc=1   ✅ 有效負控制
issues/README.md     → 1  rc=0   ❌ 無效——它是 schema 定義文件，第 13 行就是範例
```

正控制：對本檔跑 loose → 1、rc=0。負控制對 `../README.md` / `../CHANGELOG.md` /
`../AGENTS.md` 皆 0/rc=1。**探針兩側都有牙。**

### §11.4 那 7 張裸 Status 行是什麼

逐檔查證：**7 張的 line 3 全部是 canonical**，P-STRICT 命中的是檔案**深處**
另一條裸 Status——即 §10「收斂手法」第二類（4 張結構化 State 區塊鏡射）
與其他 3 張的 RCA 段落內舊狀態記錄。行號：210 / 25 / 26 / 25 / 28 / 421 / 437。

**這些是刻意保留的**：`fcd6fcc` 的收斂原則是「line 3 新增 canonical，
區塊原封不動」（§10 明載）。所以 P-STRICT 的 7 不是殘留缺陷，是**設計決定的痕跡**。

### §11.5 checker 現況與 Status 建議

`scripts/check_issue_headers.sh` 於 2026-09-02 實測：

```
self-test: no-status fixture     -> ERROR （控制組有牙）
self-test: canonical fixture     -> OK
self-test: duplicate-id fixtures -> ERROR naming BR_29991231z (rc=1)
self-test: collision-free dir    -> clean (rc=0)
scanned 49 file(s) in issues, window=full-file
status ERROR = 0 · status WARN = 0 · status_check_rc=0
```

§10 記載的「改動停在工作樹未 commit」**已不成立**：`fcd6fcc`
（`docs(issues): converge 24 BR Status lines to canonical + correct BR_20260804l stale counts`）
已把那 24 張連同本 BR 的更正一起提交，涵蓋 25 個 `issues/BR_*.md`。

**handler 的 Status 建議（不自行歸檔）**：**PARTIAL → FIXED**。三面都已收斂——
寫入側 schema（`issues/README.md`）、讀取側 checker（含永久 fixture 控制組）、
存量格式（49/49 canonical，已 commit）。**是否移 `issues/closed/` 授權在 dispatcher。**

### §11.6 本節的元教訓：這是同一缺陷的第三次自我復發

§8 記過一次「一張主張需要統一格式的 BR 自己用了第 8 種格式」；
§10 的更正框記過第二次「記錄快照缺陷的帳本自己留了無時間錨的快照」。
**這是第三次**，而且踩坑的是 dispatcher 自己：

| 誰 | 動作 | 得到的輸出 | 它其實意謂 |
| --- | --- | --- | --- |
| dispatcher | `grep -E '^\**Status\**:'` | 42 張「無」 | 42 張**合規**（canonical 被 pattern 排除） |
| dispatcher | 控制組打 `README.md` | 宣稱回 0 | 從 `issues/` cwd 打到的是 `issues/README.md`，實回 **1**——**該控制組當下無效** |

第二列尤其值得記：**控制組自己失效了，而它的輸出形狀與有效時完全相同。**
本 BR §9 早已寫過「一支從未在真實資料上紅過的 checker，與一支壞掉的 checker
共用同一個輸出」——這次是它在**負控制組**上的實例。`README.md` 這個檔名在
repo root 與 `issues/` 各有一份，而 `grep` 不會告訴你它讀的是哪一個。

**判準沉澱**：負控制組的選擇必須**先驗證它確實不含目標**，不能靠檔名直覺。
「這個檔應該沒有 Status」與「這個檔剛好是 Status schema 的定義文件」
在 `grep` 的輸出上分不出來——**除非你先看它 match 到哪一行**。

### §11.7 §11 量了什麼 / 沒量什麼

**量了**：三支 pattern 的定義差異（含 fixture 反證）、40 張歷史集的 P-BR 雙視窗複現
（8/3，兩組控制）、49 張現況集的三支 pattern 命中數（正負控制各一）、
7 張裸 Status 的逐檔行號與 line-3 內容、checker 全量自測、`fcd6fcc` 的 numstat 涵蓋。

**沒量**：
- `issues/closed/` 的 Status 格式分佈——**與 §6「沒量」欄同一格，仍未量**。
  checker 的 status 掃描仍只涵蓋頂層（dup-scan 才跨 `closed/`）。
- `41 → 47 → 49` 的檔數增長逐張成因——只確認了 epoch 邊界計數
  （`5e13dbe^`=40、`5e13dbe`=41、`d63566d`=41、`fcd6fcc`=47、HEAD=49），
  未逐張追誰新增。§10 更正框留的「`41 → 47` 差額成因未查」**依然未查**。
- 那 7 張深處裸 Status 與其 line 3 canonical 值**是否語意一致**——只比對了
  存在性與行號，未逐字比對狀態詞是否矛盾。**這是一個真實的殘留風險**：
  §10 自承 `BR_20260730` 的 line 3 是「同語意縮寫」而非逐字複寫。
- pre-commit hook 是否真的在 commit time 觸發——只跑了 checker 本體，未實測 hook 接線。
