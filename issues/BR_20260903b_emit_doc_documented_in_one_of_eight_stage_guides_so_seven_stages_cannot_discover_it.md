# BR_20260903b — `bodesign_emit_doc` 只在 8 份 stage GUIDE 的 1 份出現，於是 7 個 stage 的 caller 在原理上讀不到 doctrine 指定的文件產出路徑

- **Status**: FIXED-UNDEPLOYED — 8 份 GUIDE 已在 repo SSOT 補上（見 §7）。**發佈副本 `~/.local/share/opencode/skills/bodesign/` 尚未同步**，部署授權在值星官。

| Field | Value |
| --- | --- |
| Title | The doctrine-mandated `.docx`/`.pdf` render path is documented in exactly one of eight stage GUIDEs, so a caller entering at any other stage cannot discover it |
| Component | `~/.local/share/opencode/skills/bodesign/stages/*/GUIDE.md`（8 份）、`doctrine.md:201-203` |
| Owner | 未指派（handler `ses_f9b3c1c20ffeHznP5iE1YLe38n` 立案，權責歸 bodesign 值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH`） |
| Reporter | `thesmart_products` 值星官 `ses_038683542`（客人，只報不動手），跑 `04.btdongle` C00–C04 交付物時發現；由 bodesign handler 獨立重驗 |
| Date | 2026-09-03 |
| Severity | low — **不會害人走錯路**（未提到 `emit_doc` 的 GUIDE 都指向 docxmcp，那也是合法路徑），危害在讓 caller 事後才發現有更直接的入口，付出可避免的探索成本 |
| Family | `G14-doc-coverage-gap`（文件覆蓋缺口，非揭露缺陷 —— 見 §4 為何不歸 G13） |
| Affected paths | `stages/c00-prd/GUIDE.md`、`c01-id`、`c02-me`、`c04-layout`、`c05-fw`、`c06-verify`、`c07-mfg`（7 份缺）；`stages/c03-ee/GUIDE.md:414`（唯一命中） |

## 1. 症狀

`doctrine.md:201-203` 逐字規定：

> **Never hand-merge or hand-edit an Office/OOXML deliverable.** `.docx` / `.pptx` /
> `.xlsx` go through `bodesign_emit_doc` (markdown → docx+pdf) or `bodesign_mcp_call`
> driving docxmcp — not a caller-side `zip`/`ElementTree`/`python-docx` script.

而 `emit_doc` 這個名字在 8 份 stage GUIDE 中只出現 **1 次**，在 C03。
C00 是 PRD（`.docx` 交付物最集中的 stage，`.docx` 出現 8 次）卻一次都沒提。

## 2. 重驗（獨立於客人回報，2026-09-03）

⚠ 本班當日剛付過「pattern 寫太窄被讀成缺席」的代價，故本次用 **5 種寬度**＋**正負控制組**。

### GUIDE.md 實際清單（**8 份，不是五份**）

```
find <skill>/stages -name GUIDE.md | sort
stages/c00-prd/GUIDE.md
stages/c01-id/GUIDE.md
stages/c02-me/GUIDE.md
stages/c03-ee/GUIDE.md
stages/c04-layout/GUIDE.md
stages/c05-fw/GUIDE.md
stages/c06-verify/GUIDE.md
stages/c07-mfg/GUIDE.md          ← 8 個
```

客人只點名 C00/C01/C02/C04 缺，實際上 **C05/C06/C07 也缺**（客人只跑到 C04，未及於此）。

### 5 種 pattern 寬度（全部對 `stages/` 遞迴，絕對路徑）

| # | pattern | 命中 | rc |
| --- | --- | --- | --- |
| P1 | `emit_doc`（客人用的） | `c03-ee/GUIDE.md:414` | 0 |
| P2 | `emit.doc`（regex `.` 通配） | 同上，1 筆 | 0 |
| P3 | `emit_document` | **0 筆** | 1 |
| P4 | `bodesign_emit_doc` | 同上，1 筆 | 0 |
| P5 | `emit[_ -]?doc`（`-iE` 忽略大小寫） | 同上，1 筆 | 0 |

**四種寬度收斂到同一筆命中**，且最寬的 P5 沒有多撈到任何東西——
這排除了「pattern 太窄」這個競爭解釋。P3 的 0 筆是真缺席（`emit_document` 是
`reverse-core` 的內部函式名，本來就不該出現在 GUIDE）。

唯一命中逐字：

```
stages/c03-ee/GUIDE.md:414:5. **Render path.** Prefer `bodesign_emit_doc` (md → docx+pdf) when the worker has LibreOffice;
```

### 控制組

| 類型 | 探針 | 結果 | 它排除了什麼 |
| --- | --- | --- | --- |
| **正控制 A** | `grep -rc 'GUIDE' <skill>/stages/*/GUIDE.md` | 8 個檔全部非零（6/6/5/2/3/6/4/2） | 證明探針當下**讀得到全部 8 個檔**，不是路徑打錯或權限問題 |
| **正控制 B** | `grep -rlc 'bodesign_' <skill>/stages` | 10 個檔命中，含 c03-ee/c04-layout/c07-mfg 三份 GUIDE | 證明 `bodesign_` 前綴的 tool 名字在 GUIDE 中**確實會出現**，所以「`emit_doc` 只出現一次」不是因為 GUIDE 從不提 tool 名 |
| **負控制** | `grep -rn 'zzq_bogus_token_xyz' <skill>/stages` | 0 筆，rc=1 | 證明探針不是什麼都 match |

### 逐檔文件路徑覆蓋率（決定性的那張表）

```
                     docxmcp  render_companion  .docx   emit_doc
c00-prd/GUIDE.md        3           0             8        0     ← PRD stage，.docx 最密集，零提及
c01-id/GUIDE.md         2           0             0        0
c02-me/GUIDE.md         2           0             0        0
c03-ee/GUIDE.md         4           0             6        1     ← 唯一
c04-layout/GUIDE.md     1           0             0        0
c05-fw/GUIDE.md         1           0             0        0
c06-verify/GUIDE.md     1           0             0        0
c07-mfg/GUIDE.md        1           0             0        0
```

這張表同時證明兩件事：
1. **缺口是真的** —— `emit_doc` 欄只有一個 1。
2. **危害有上限** —— `docxmcp` 欄 8 份全部非零，所以每個 stage 的 caller 都有一條合法路徑可走。
   這正是客人說的「不會害人走錯路」，本次重驗**確認此判斷成立**，故 Severity 記 low 而非 medium。

## 3. 結論

**客人回報成立**，但兩處與原述不同，據實記載：

- 缺的是 **7 份**不是 4 份（C05/C06/C07 客人未及測）。
- 「C03 GUIDE:414 唯一命中」逐字正確。

## 4. 為何歸 `G14-doc-coverage-gap` 而非 `G13-harness-disclosure`

G13 的判準是「**系統當下握有那格資訊卻不揭露**」——BR_20260903a 的 `_resolve_src()`
就是握著而不說。本張不同：**沒有任何執行中的程式握有「這個 stage 也可以用 emit_doc」這格資訊**，
它純粹是 8 份手寫文件之間的覆蓋不一致。把它掛 G13 會稀釋該 family 的判別力
（該 family 的價值在於指向「有資訊但不排放」這一類可機械修復的缺陷）。

## 5. 修法方向（**本輪不修**，供 dispatcher 裁決）

在 8 份 GUIDE 首次出現「產出 `.docx` 交付物」之處補一行指向 `bodesign_emit_doc`，
或在 GUIDE 共用前言統一敘明。**注意**：C00 的 `.docx` 走的是
`c00_emit_prd_docx`（docxmcp assemble 路徑，見 `SKILL.md:260`），與 `emit_doc`
是兩條不同的路徑——補文件時不可把兩者混為一談，否則會製造新的誤導。

## 6. 沒量到什麼

- 未量測 `references/` 與 `assets/` 底下是否提及（只掃 `stages/` 遞迴，該範圍已含這些子目錄，但未逐檔分類）。
- 未量測 bodesign repo 內 `docs/` 的覆蓋率。
- 未驗證「補上之後 caller 真的會讀到」——那是修法後的驗收，不在本輪。
- 未修改任何 GUIDE.md（派工單明令 step 3 不修）。

## 7. 修法記錄（2026-09-03，handler `ses_f9b321defffekP04rBeQBFoKdl`，未 commit）

單一派工包連同 BR_20260903a-B 一併做（同一批 `stages/*/GUIDE.md`，拆兩個工作包會撞檔）。

### 適用性審查（先讀 `doctrine.md:201-203` 與 `references/stage-structure.md`）

`bodesign_emit_doc` 的 schema 是 `{md_path, out_dir, formats}`（`services/mcp/server.py:1181-1183`）——
「markdown → docx+pdf」的**無範本**渲染路徑，靠 worker 端 LibreOffice。
而 `stage-structure.md:116-131` 規定的 house-style 交付物（`C0N_*.docx`、繁體中文、壹/一/（一）numPr 編號、內嵌圖表）走的是 **docxmcp assemble**。

結論：**8 個 stage 都有適用面，但不是取代 docxmcp**——每個 stage 都有「純 markdown 寫完、只需變成可分享 docx/pdf」的交付物（c00 Handoff Report、c01 CMF/UX 寫作、c02 Vendor_Handoff、c04 stackup/fab notes、c05 Firmware_Architecture、c06 test plan / Bring_Up_Checklist、c07 Manufacturing_Transfer）。
因此補的是「**這是另一條路、何時該走它**」，不是「把 docxmcp 換成 emit_doc」。

尤其遵守 §5 的警告：**C00 的 `.docx` 走 `c00_emit_prd_docx` → docxmcp assemble，與 `emit_doc` 是兩條不同路徑**。
c00 GUIDE 的插入段逐字寫明這個區別（「the PRD deliverable itself」不走 emit_doc），避免製造新的誤導。

### 逐檔插入點

| GUIDE | 插入位置 | 形式 |
| --- | --- | --- |
| c00-prd | §"6. Emit optional .docx" 的 docxmcp 項下 | 新一項，明寫兩條路徑的分工 |
| c01-id | 工具清單 docxmcp 項下 | 新一項 |
| c02-me | 工具清單 docxmcp 項下 | 新一項 |
| c03-ee | 已存在（`:414` Render path） | **未動** — 原本就是唯一命中且描述正確 |
| c04-layout | 工具清單 docxmcp 項下 | 新一項 |
| c05-fw | 工具清單 docxmcp 項下 | 新一項 |
| c06-verify | 工具清單 docxmcp 項下 | 新一項 |
| c07-mfg | 工具表格 | 新一列（該 GUIDE 的工具段是表格不是清單） |

### 驗證（兩種 pattern 寬度 + 正負控制組）

問題：**8 份 GUIDE 是否都提及 `emit_doc`？**

| 探針 | 命中 |
| --- | --- |
| `grep -lc 'emit_doc'`（客人原本用的寬度） | **8/8**（修改前 1/8） |
| `grep -lciE 'emit[_ -]?doc'`（§2 最寬的 P5） | **8/8** — 未多撈到任何東西，收斂 |
| `grep -lc 'bodesign_emit_doc'`（P4） | **8/8** |
| 正控制：必然存在的字串 | 8/8 — 探針讀得到全部 8 個檔 |
| 負控制：`zzq_bogus_token_xyz` | 0/8 — 探針不是什麼都 match |

逐檔 `emit_doc` 計數皆為 1（c03 本來就是 1，其餘 7 份從 0 → 1）。

### 這一輪沒量什麼

- **未部署**。發佈副本 `stages/*/GUIDE.md` 未動，客人從 XDG 副本進場仍讀不到。
- 未驗證「補上之後 caller 真的會讀到」（§6 已記為修法後驗收，仍不在本輪）。
- 未改 `references/` / `assets/` / `docs/` 的覆蓋率（§6 列為未量，本輪也未量）。
- 未實際跑一次 `bodesign_emit_doc` 驗證 LibreOffice 可用性——本輪是文件修正，不涵蓋 runtime 可用性。

**Related**:
- `issues/BR_20260903a_gate_py_list_enumerates_61_verbs_while_none_of_them_can_run_without_bodesign_src.md`
  — **時序與來源因果**：同一位客人（`ses_038683542`）在同一次 `04.btdongle` C00–C04 執行中撞出的兩條可教性缺陷，
  由同一張派工單（`ses_04db7a1c5ffelvbxyLP1p6xlRH`，task=file-guest-reported-teachability-defects）一併重驗立案。
  兩者的**共同上游**是「stage GUIDE 是 caller 的實際進場點，而關鍵前提／路徑不在那裡」。
- 未找到既有的 doc-coverage family BR。已查：`ls issues/` 與 `issues/closed/` 全部檔名、
  `grep 'emit_doc'` 於本 repo `issues/` 樹。若 dispatcher 知道有更早的同類前例，請告知後補。
  **`G14-doc-coverage-gap` 是本張新起的 family 名，不是既有登記名**——這一點必須明說，
  以免下一個 agent 拿它去 grep 而得到 0 命中後誤判為指標爛掉。
