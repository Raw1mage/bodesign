# BR_20260902 — `check_issue_headers.sh` 的 status 掃描只裁決 line 3，於是 `WARN = 0` 讀起來像「帳本一致」，實際只意味「每張的 line 3 合規」

- **Status**: OPEN — 已量測、已具名實例；修法未裁示（本張由 handler 立案，未 commit，待 dispatcher 裁決）

| Field | Value |
| --- | --- |
| Title | The status checker adjudicates line 3 only, so a second Status declaration deeper in the same file can contradict it and never be reported |
| Component | `scripts/check_issue_headers.sh:55-67`（`scan_one`）、`:84-93`（視窗揭露與 WARN 輸出） |
| Owner | 未指派（handler `ses_f9e79b665ffew786CUnKAKi2jA` 立案，權責歸 bodesign 值星官） |
| Reporter | `ses_f9e79b665ffew786CUnKAKi2jA` — 執行 `BR_20260804l §11.8` 派工（逐字比對 7 張的 line 3 與深處 Status）時撞出 |
| Date | 2026-09-02 |
| Severity | medium — 不影響 runtime。危害在**排程判斷**：讀者把 `WARN = 0` 讀成「帳本狀態一致」，而它只保證 line 3 的格式 |
| Family | `G13-harness-disclosure` |
| Affected paths | `scripts/check_issue_headers.sh`、`issues/README.md`（schema 文件同樣只描述 line 3） |

**Related**（每條帶可引用依據）：

- `BR_20260804l_issues_ledger_has_no_status_schema_so_a_header_scoped_sweep_reports_five_files_as_having_none.md`
  — **同一支 checker，不同缺陷面，且本張的證據就是那張 §11.8 產出的**。
  依據：`§11.8` 對 7 張裸 Status 的三分類 **一致 6 / 矛盾 1 / 不可判定 0**；`§11.9` 證明母體
  就是這 7 張（其餘 42 張 line 3 以外零條 Status）。**兩張不覆蓋對方**：804l 治的是
  「sweep pattern 與 schema 的一致性」（寫入側格式 + 讀取側視窗都指向 line 3 這一件事），
  本張治的是「**line 3 合規** 與 **全檔無矛盾** 共用同一個 `WARN = 0`」。
  804l 即使完全修好（49/49 canonical、ERROR=0、WARN=0，已達成），本缺陷仍原封不動——
  這正是它需要獨立一張的判準。
- `BR_20260804b_guard_c_inset_inverts_the_box_for_narrow_bodies_so_intrusion_check_is_blind.md`
  — **本張的具名實例**。依據：該檔 line 3 為 `- **Status**: **FIXED**`（2026-09-01），
  而 L437（修前）為 `**Status**: open`，兩者互斥且深處那條無任何超越標記；
  checker 對該檔的裁決是 `OK`（line 3 canonical），**從未對這個矛盾發出任何訊號**。
  該行已於 `98b17cc` 補上標記，但**那是修資料不是修儀器**——下一張新 BR 仍可製造同樣的矛盾。
- `AGENTS.md §6.1` pathspec 陷阱 — **同一形狀的上位敘述**：帶範圍限定的結果與不帶的輸出形狀
  完全相同，沒有任何標記說結果被過濾過。依據：本張的「範圍限定」是 `sed -n '3p'`
  （`check_issue_headers.sh:61`），而輸出（`OK`）不攜帶「我只看了第 3 行」這格資訊。

---

## §1 一句話

`scan_one`（`:55-67`）用**兩個不同的視窗**做兩件事：存在性用全檔（`STATUS_ANY_RE`），
**裁決用 `sed -n '3p'` 只取第 3 行**。於是一張 line 3 合規、而檔案深處另有一條**互相矛盾**
的 Status 宣告的 BR，checker 判 `OK`，而整體報告印出 `WARN = 0`——
**讀者拿到的訊號是「帳本乾淨」，儀器實際保證的只有「每張的 line 3 格式正確」。**

## §2 機制（逐行，可對照原始碼）

```bash
# scripts/check_issue_headers.sh:55-67
scan_one() {
  local f="$1"
  if ! grep -qE "$STATUS_ANY_RE" "$f"; then     # 視窗 A：全檔（存在性）
    echo "ERROR $f"; return
  fi
  local l3
  l3=$(sed -n '3p' "$f")                        # 視窗 B：只有第 3 行
  if echo "$l3" | grep -qE "$CANON_RE"; then    # 裁決只看視窗 B
    echo "OK $f"
  else
    echo "WARN $f"
  fi
}
```

`:85` 的視窗揭露印的是 `window=full-file`——**那是視窗 A 的描述，不是裁決用的視窗 B**。
`OK` / `WARN` 這兩個判決全部出自 `sed -n '3p'`，而報告字面說 full-file。
**揭露存在，但揭露的是另一格。**（這比不揭露更難察覺：讀者看到 `window=full-file`
會停止懷疑視窗問題。）

## §3 量測（2026-09-02，可重跑，帶控制組）

### §3.1 決定性的一格：一個實際存在的矛盾，checker 判 OK

母體：`BR_20260804b`（修前，即 `98b17cc^`）。

```
line 3 : - **Status**: **FIXED**（2026-09-01；§9 三項殘留全數收斂，量測見 §10。…）
L437   : **Status**: open（機制 ACCEPTED；量值 disputed，非阻塞；另見 §8 浮點邊界）

checker 對該檔的裁決            = OK
整體報告                        = scanned 49 file(s), window=full-file
                                  status ERROR = 0 · status WARN = 0 · status_check_rc=0
```

**`WARN = 0` 與「這批 49 張沒有任何狀態矛盾」在輸出上完全相同**，而實際存在 1 張矛盾。

### §3.2 母體與分佈（來自 `BR_20260804l §11.8`/`§11.9`，本張引用不重量）

```
line 3 以外還有 Status 宣告的         =  7 / 49
  其中 line 3 與深處一致              =  6
  其中 line 3 與深處矛盾              =  1   <- BR_20260804b
  其中不可判定                        =  0
其餘 42 張 line 3 以外零條 Status     =  42   （§11.9，附三組控制組）
```

**曝險面不是假想的 1 張**：只要 checker 的裁決視窗停在 line 3，
這 7 張裡任何一張未來被改動、或任何新 BR 沿用「深處保留舊狀態」的寫法，
都會落回同一個盲區。而該寫法**本身是本 repo 的既有慣例**
（`BR_20260804b:10,12` 就有兩個標記為已超越的引用塊）——**慣例合法，儀器看不見。**

### §3.3 控制組

```
探針有牙（正）  對 BR_20260804b 跑寬 pattern（含 '>' 前綴）
                → L3 與 L442 兩條，rc=0        ✅ 能抓到 line 3 以外、第 442 行的宣告
探針會失敗（負） 同一支 pattern 打 CHANGELOG.md
                → 空，rc=1                     ✅ 不是什麼都 match
計數控制        迴圈實際走訪檔數 = 49          ✅ 42 個空不是因為沒走到
checker 自測    no-status fixture → ERROR      ✅ checker 的既有控制組本身有牙
                canonical fixture → OK            （所以本缺陷不是「checker 壞了」，
                dup fixtures → ERROR naming        是它的裁決視窗與讀者預期不同）
```

最後一格重要：**checker 的自測全綠且確實有牙**，所以本張不是在說它壞掉。
它做的事情做對了，**問題是它做的事情比它的輸出讓人以為的少**。

## §4 為什麼是 G13 而不是「使用者該自己多看一眼」

判準是 **「那一格資訊，系統當下有沒有？」**

**有，而且同一支腳本已經在用它。** 同一支 checker 的 **dup-scan 跑的就是 full-file 且跨目錄**
（`:47` `LIVE_DUP_DIRS=(issues issues/closed)`，`:152` 印出
`dup-scan: 129 file(s) across [issues issues/closed], 114 with a BR id, …`）。
它甚至比 status scan 揭露得更完整——印出母體、有 id 的、沒 id 的、distinct id 數。

所以缺的不是能力也不是資訊，是**同一支工具內部兩個掃描的揭露水準不一致**：

| | 掃描視窗 | 揭露的內容 |
| --- | --- | --- |
| dup-scan | full-file、跨兩目錄 | 母體、分項計數、具名 |
| status-scan | 存在性 full-file、**裁決 line 3** | 只印 `window=full-file`（＝存在性那一格） |

**`WARN = 0` 的兩種成因共用同一個輸出**：

| 缺席態 | 失敗態 | 共用的輸出 |
| --- | --- | --- |
| 帳本真的沒有格式問題也沒有狀態矛盾 | line 3 全部合規，但深處有矛盾的第二條狀態 | `WARN = 0` |

## §5 修法（未裁示，三個選項）

**選項 1 — 第三級 `NOTE`：報告 line 3 以外的 Status 宣告（建議）**
- `scan_one` 增一格：全檔搜 `STATUS_ANY_RE`，行號 ≠ 3 且**該行未被引用標記包住**（`^>`）者列為 `NOTE`。
- 不擋、不 WARN——因為那 6 張一致的是**合法且有價值**的記錄（State 區塊、RCA 段落）。
- 只要**讓它可見**：`NOTE: N file(s) declare a Status outside line 3 — verify they agree`。
- **控制組要求**：對一個刻意製造矛盾的 fixture 必須出現在 NOTE 清單，否則它只是另一支回空的 grep。

**選項 2 — 自動比對態詞**
抽出 line 3 與深處各自的態詞（`OPEN|PARTIAL|FIXED|CLOSED|open`），不同就 WARN。
**風險高**：那 6 張一致者的深處措辭帶大量限定語（`open（RCA 部分過期…）`），
態詞抽取會產生誤報，而**誤報會訓練讀者忽略 WARN**——比不做更糟。

**選項 3 — 只改揭露文字，不改邏輯**
把 `window=full-file` 改成
`window=full-file(existence) + line-3(verdict)`。
成本近零，**直接對症 §2 的「揭露的是另一格」**，但不解決矛盾偵測。

傾向 **3 + 1**：3 先讓輸出停止說謊（一行改動），1 再補偵測能力。
**不建議 2。**

## §6 量了什麼 / 沒量什麼

**量了**：`scan_one` 的雙視窗機制（逐行對照原始碼）、一個實際存在的矛盾實例
（`BR_20260804b` 修前）、該實例下 checker 的裁決（`OK`）與整體輸出（`WARN=0`）、
7/49 的曝險母體與 6:1:0 分佈、四組控制組（含 checker 自測有牙）、
dup-scan 的揭露水準對照（證明資訊系統當下有）。

**沒量**：
- **`issues/closed/` 的同型矛盾**——status scan 本來就不掃 closed（`run_dir "issues"`，`:266`），
  且 dispatcher 已裁定 closed 不在 804l 範圍。本張沿用該邊界，**未查**。
- **選項 1 的誤報率**——沒有實作，所以不知道排除 `^>` 引用塊之後那 6 張一致者
  會不會仍全部進 NOTE 清單（若會，NOTE 就變成常態噪音，值得重新設計）。**未量。**
- **pre-commit hook 是否真的在 commit time 觸發**——只跑了 checker 本體，**未實測接線**。
  這格與 804l §11.7 的同名殘留是同一格，兩張都未量。
- **行中（非行首）的 Status 寫法**——例如表格儲存格 `| Status | OPEN |`。
  本張與 804l §11.9 的探針都只掛行首。**這不是假設而是已知風險**：
  804l §8 記載該檔自己曾經就是這種寫法。**未掃。**
