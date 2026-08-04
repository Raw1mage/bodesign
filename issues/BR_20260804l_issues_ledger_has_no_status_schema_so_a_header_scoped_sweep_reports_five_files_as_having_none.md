# BR_20260804l — `issues/` 帳本沒有 Status schema：兩支合理的 sweep 對同一批檔案回不同答案，而「沒有 Status」與「Status 在我的視窗外」共用同一個輸出

- **Status**: PARTIAL — schema 已定、checker 已落地並帶內建控制組（`d63566d`，實作選項 1+3）；殘留只剩 26 張 WARN 的格式收斂（見 §10）

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

實測（`d63566d` 落地後，41 張頂層）：
```
self-test: no-status fixture -> ERROR （控制組有牙）
self-test: canonical fixture -> OK
scanned 41 file(s), window=full-file
ERROR = 0        <- 沒有一張是真的零 Status（§7 已補齊那 3 張）
WARN  = 26       <- 格式收斂 backlog，見下
```

### 殘留：26 張 WARN（格式收斂，PARTIAL 的唯一開口）

這 26 張都**有** Status（checker 綠、不擋 commit），只是不在 line-3 canonical 形式
（裸 `Status:`、或深埋 line 6/7/23/24/26）。它們是漸進收斂工作，不急、可隨手做：
每次碰到其中一張 BR 時把 Status 行改成 canonical 形式即可，WARN 數單調下降。
**不批次搬**——批次改 26 個檔的 Status 位置與本 BR 的 scope 無關，且會在共用樹上
產生一大批與各 BR 內容無關的 diff。checker 的 WARN 清單就是這個 backlog 的 live 追蹤。

本 BR 標 **PARTIAL 留頂層**：schema+checker 已生效（主交付完成），
WARN=26 的收斂是明確的 scoped remainder。WARN 歸零時可移 `closed/`。
