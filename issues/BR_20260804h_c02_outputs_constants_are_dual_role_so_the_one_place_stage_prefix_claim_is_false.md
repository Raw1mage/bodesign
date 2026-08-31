# BR_20260804h — `C0x_OUTPUTS` 常數身兼兩職，使「stage 前綴只在一處推導」這句宣稱不成立

- **Status**: FIXED-AS-DOCUMENTED — 错誤宣稱已改寫為事實（三個角色各帶 file:line），且其中可機械斷言的不變量已由 `tests/test_stage_prefix_invariant.py` 釘住（含四組實測過的反向控制組）。**雙前綴模型本身仍存在且是刻意保留**（選項 A 被否決，理由見 §10）——不是遺漏，是裁決。還原為單一前綴模型的工作追蹤於 §11。
**Severity**: medium — 不是當下的錯誤行為，是**一句錯誤的單一真相來源宣稱**
**Owner**: `readiness-contract` family（`issues/OWNERS.md`）
**Filed by**: `ses_0330e7869ffev0nZL0XqoXSp78`（BRNS handler，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`）
**Filed**: 2026-08-04
**Related**:
- `issues/BR_20260804_c02_export_stl_cannot_see_files_staged_into_its_own_token.md`
  （同一條契約線：這張是那張的**根因層**。那張的症狀由 `folder_is_stage_dir` 揭露修法擋住，
  但雙前綴模型本身仍在）
- `issues/BR_20260719_c01_readiness_folder_arg_double_prefix.md`
  （同族：c01 的 `folder` 雙前綴半邊仍 OPEN，§2 附今日重現）
- `issues/BR_20260804_stage_deliverable_names_are_hardcoded_per_module_so_the_C0N_prefix_rule_cannot_be_adopted.md`
  （同一批常數的另一個面向：名稱寫死在各模組）

---

## 1. 一句話

`c02_me_package.py:35-38` 的區塊註解**逐字宣稱**：

> the stage dir is derived from it here, **in ONE place**, so no caller has to
> pre-join it and **no two code paths can disagree** about what `folder` meant

**兩句都不成立。** 那個「ONE place」（`_c02_stage_dir()`）只有 2 個呼叫點，
而模組裡另有 5 個 verb 走完全不同的前綴模型。

## 2. 量測（2026-08-04，全部可重跑）

```
$ grep -n "_c02_stage_dir" packages/workflow-core/bodesign_workflow_core/c02_me_package.py
  57:def _c02_stage_dir(...)          ← 定義
 693:  stage_dir=_c02_stage_dir(folder)   ← provenance
 768:  stage_dir=_c02_stage_dir(folder)   ← provenance
（全部呼叫點就這兩個，皆在 provenance 路徑）

$ 而 C02_OUTPUTS 的 12 個值每一個都自帶 "C02-ME/" 前綴，且被這樣消費：
  export_c02_stl / export_c02_skp / export_c02_step /
  export_c02_projection_svg / generate_c02_openscad
    → root / C02_OUTPUTS[key]         ← 第二套前綴模型
```

c01 同構：`_c01_stage_dir()` 2 個呼叫點（`:617`、`:1133`），
`C01_OUTPUTS`（5 keys）與 `C01_OUTPUT_CANDIDATES`（read 側候選表）全部自帶 `C01-ID/`。

**BR_20260719 的 `folder` 雙前綴半邊今日仍逐字重現**（production import，同一份合規交付）：

| `folder` 傳入 | readiness_pct | missing |
|---|---|---|
| `<product root>` | **100** | `[]` |
| `<product root>/C01-ID` | **0** | 全部 5 個 |

（`C01_OUTPUT_CANDIDATES` 修的是 read 側 bucket 位置分歧（`03_output/` vs legacy），
**沒有碰 `folder` 雙前綴**。同一張 BR 的兩半只修了一半。）

## 3. 為什麼這比「沒有註解」更貴

這句宣稱**讓讀者停止尋找第二個真相來源**。

本 handler 實測：讀到 `:35-38` 的註解時，第一反應是「契約已收斂，我只要順著單點改」——
是 dispatcher 要求「自己去讀 `_c02_stage_dir()` 的實際涵蓋範圍」才發現宣稱與實作不符。

同族形狀已在本 repo 記錄多次（`code-thinker` §8.1.3(d)）：
**宣稱存在但實際只覆蓋一條路徑的護欄，比缺少護欄更貴。**

## 4. 為什麼**不能**與 BR_20260804 同輪修（這格是本 BR 的核心）

直覺修法是「把前綴從 `C0x_OUTPUTS` 拿掉，全部經 `_c0x_stage_dir()` join」。**不行**，因為
那 12 個常數**身兼兩職**：

1. **檔案系統 join 的右手邊** — `root / C02_OUTPUTS["openscad"]`
2. **回傳給呼叫端的 rel path** — `stl_path=str(C02_OUTPUTS["stl"])` → `"C02-ME/Enclosure.stl"`

第 2 個角色**真的被下游 join**：

```
services/mcp/server.py:317-320
    stl_rel = (result.get("stl") or {}).get("stl_path")
    stl_abs = str(Path(a["out_dir"]) / stl_rel)      ← 呼叫端自己再 join 一次
```

⇒ 一旦把前綴從常數移走，這兩個角色必須**分別**重建（一個要 `root/stage/name`，
另一個要 `stage/name`）。任何一處漏改都會產生「路徑對、但回傳的 rel 少一層」——
**在下一跳才炸**，而且炸的地方離改動點很遠。

**這正是我們在修的病換個位置發作**：一個名字承載兩種語意。

## 5. 建議修法（獨立工項，需完整掃描）

1. 把兩個角色拆成**兩組**常數：`C02_STAGE_REL`（stage 內相對，供 join）與
   `C02_PRODUCT_REL`（product root 相對，供回傳）；或保留單一常數但讓回傳點顯式
   `str(C02_STAGE_DIRNAME / name)`
2. 前綴 join 收斂到 `_c0x_stage_dir()`，讓那句註解變成事實
3. 加 drift guard：斷言「任何 verb 回傳的 rel path，與呼叫端 `out_dir` join 後
   等於實際寫入的絕對路徑」——這條護欄若不加，下次搬動仍會靜默錯位

## 6. 已知缺口（誠實邊界）

- **`C0x_OUTPUTS` 的下游消費點我只掃了 `c02_me_package.py` 與 `services/mcp/server.py`。**
  `skills/bodesign/scripts/gate.py` 及其他 skill 端消費者**未掃**。
  動手修此 BR 前必須先完整掃描，否則 §4 的「漏改一處」風險成真。
- ~~**c00 / c03–c07 是否同構未量。**~~ → **已於 2026-09-01 量完，見 §11。**
  （原文：依 `readiness_common.STAGE_FOLDER` 有 8 個 stage，本次只驗了 c01 / c02 兩個。）

## 7. 當前狀態

`_c02_stage_dir()` 的 docstring 已在 BR_20260804 的修法中補上 SCOPE 段落，
明寫「本 helper 只有兩個 provenance 呼叫點，模組內兩套前綴模型並存」並指向本 BR，
使那句不成立的宣稱不再誤導下一個讀者。**那是止血，不是修復。**

---

## 8. 解除封鎖重驗（2026-09-01，handler `ses_fa6ece187ffe2jyvANSTFBQStk`）

### 8.1 §4 延後理由逐字

§4 標題：**「為什麼**不能**與 BR_20260804 同輪修（這格是本 BR 的核心）」**。逐字理由：

> 直覺修法是「把前綴從 `C0x_OUTPUTS` 拿掉，全部經 `_c0x_stage_dir()` join」。**不行**，因為
> 那 12 個常數**身兼兩職**：1. 檔案系統 join 的右手邊 2. 回傳給呼叫端的 rel path
> ⇒ 一旦把前綴從常數移走，這兩個角色必須**分別**重建（一個要 `root/stage/name`，
> 另一個要 `stage/name`）。任何一處漏改都會產生「路徑對、但回傳的 rel 少一層」——
> **在下一跳才炸**，而且炸的地方離改動點很遠。

§6 另立一條**硬前置**：

> `C0x_OUTPUTS` 的下游消費點我只掃了 `c02_me_package.py` 與 `services/mcp/server.py`。
> `skills/bodesign/scripts/gate.py` 及其他 skill 端消費者**未掃**。
> **動手修此 BR 前必須先完整掃描**，否則 §4 的「漏改一處」風險成真。

### 8.2 三態判定：**已解除，可修**（但 §4 從來不是「該不該修」的閘，是「怎麼修」的約束）

依據三格：

| # | 問題 | 量測 | 結論 |
|---|---|---|---|
| 1 | 「同輪」這個條件今天還存在嗎？ | `BR_20260804_c02_export_stl_cannot_see_files_staged_into_its_own_token.md` 已在 `issues/closed/`（控制組：頂層 `issues/` 仍有 9 個 `BR_20260804*`，證明 `ls`+`grep` 探針有判別力，不是回空） | **不存在**。延後條件字面是「不能與 BR_20260804 **同輪**」；那一輪已結束並歸檔 ⇒ 條件自然解除 |
| 2 | §6 的硬前置（完整掃描）滿足了嗎？ | 見 §8.3 M4/M5：全 repo `.py`（排除 `.venv`/`__pycache__`）掃 `C02_OUTPUTS`/`C01_OUTPUTS`，消費者共 7 檔，**`skills/` 下零命中**（控制組 `C99_OUTPUTS_CONTROL` rc=1，證明探針會回非空） | **滿足**。§6 對 `skills/bodesign/scripts/gate.py` 的擔憂**被推翻**——它不是消費者 |
| 3 | §4 的技術風險消失了嗎？ | **沒有。** 那是這個改動**本身**的性質，與 BR_20260804 是否結案無關 | 它約束**修法形狀**（見 §10），不構成繼續延後的理由 |

**殘留未量（誠實邊界）**：§6 第二項「c00 / c03–c07 是否同構」**本輪仍未量**。它不阻擋 c01/c02 的修法，但意味著本 BR 若只修 c01/c02，同一個形狀可能還活在另外 6 個 stage。

### 8.3 缺陷本體重驗（2026-09-01，全部可重跑；行號以符號為準）

| # | 問題 | 指令 | 結果 | 控制組 |
|---|---|---|---|---|
| M1 | `_c02_stage_dir` 有幾個呼叫點？ | `grep -n "_c02_stage_dir" packages/workflow-core/bodesign_workflow_core/c02_me_package.py` | 3 行：`:57` 定義、`:772`、`:847` 呼叫 ⇒ **仍是 2 個呼叫點** | 同探針對 `_c02_stage_dir_NONEXISTENT_CONTROL` rc=1（會回空 ⇒ 上面的非空是真訊號） |
| M2 | c01 對稱嗎？ | `grep -n "_c01_stage_dir" .../c01_id_package.py` | `:94` 定義、`:617`、`:1133` ⇒ **2 個呼叫點，對稱成立** | 同上探針形狀 |
| M3 | `server.py` 呼叫端仍二次 join？ | `grep -n "stl_path\|..." services/mcp/server.py` | `:317` 取 `stl_path`、`:320` `Path(a["out_dir"]) / stl_rel` ⇒ **re-join 仍在**（BR 寫 `:317-320`，逐字命中） | `zzz_nonexistent_path_CONTROL` rc=1 |
| M4 | `C02_OUTPUTS` 全 repo 消費者？ | `grep -rn --include=*.py --exclude-dir=.venv --exclude-dir=__pycache__ "C02_OUTPUTS" .` | 2 檔：`c02_me_package.py`（**約 40 個 join/回傳點**）、`tests/test_c02_export_stl_failure_states.py`、`tests/test_c02_projection_svg.py` | `C99_OUTPUTS_CONTROL` rc=1 |
| M5 | `C01_OUTPUTS` 全 repo 消費者？ | 同上 pattern | 4 檔：`c01_id_package.py`、`c01_id_template.py:22,121`、`mode_contracts.py:27,74` | 同上 |
| M6 | 12 個常數仍自帶前綴？ | `read c02_me_package.py:41-54` | 12 keys 每個都是 `Path("C02-ME") / <name>` ⇒ **雙前綴模型仍成立** | — |
| M7 | §6 對 `skills/` 的擔憂成立嗎？ | M4/M5 的全 repo 掃描結果 | **`skills/` 下零命中** ⇒ §6 該項**被推翻** | M4/M5 的 rc=1 控制組同時保證「零命中」不是探針壞掉 |

**行號位移確認**：BR §2 寫 `:693`/`:768`，今日實為 `:772`/`:847`（位移 +79）。**呼叫點數量（2）與雙前綴模型皆未變**。

### 8.4 兩個角色在 c01 側的分佈（§4 只寫了 c02，這裡補齊）

| 消費點 | 角色 | 若移走前綴會怎樣 |
|---|---|---|
| `c01_id_package.py:399-403` | 角色1（`root / rel` 寫檔）| 需改成 `root / stage / name` |
| `c01_id_package.py:637` `len(C01_OUTPUTS)` | 兩者皆非（只數個數）| 不受影響 |
| `c01_id_template.py:121` `{p.as_posix() for p in C01_OUTPUTS.values()}` | **角色2 的變種**——與 template 的 `f"{folder}/{c}"`（folder=`C01-ID`）比對 | **會靜默破裂**：template 側算出 `C01-ID/CMF/...`，emitter 側若少前綴變 `CMF/...` ⇒ 兩集合差集非空 ⇒ `C01TemplateError` |
| `mode_contracts.py:74` `[str(rel) for rel in C01_OUTPUTS.values()]` | **角色2**（宣告為 packet expected outputs，對外契約字串）| 少一層前綴會讓對外宣告的路徑失真 |

`c01_id_template.py:121` 這一格是本 BR §4 風險的**最佳實例**：它既不是檔案 join、也不是回傳 rel，而是**與另一個獨立前綴來源（template `folder`）對帳**。§4 說的「兩個角色」實際上是**三個**。

### 8.5 基線測試（修法前的對照）

```
find . -name __pycache__ -prune -exec rm -rf {} +      # AGENTS.md §6.3
PP=$(ls -d packages/*/ | tr '\n' ':')
PYTHONPATH="$PP" python3 -m unittest tests.test_c02_export_stl_failure_states \
    tests.test_c02_me_package tests.test_c01_id_package tests.test_c01_id_template
→ Ran 60 tests … FAILED (failures=2, skipped=2)
```

**兩個既有失敗（與本 BR 無關，修法前就紅，是修法的基線不是回歸）**：
- `tests.test_c01_id_package.C01IdPackageTests.test_readiness_uses_field_gaps_when_answer_state_exists`
- `tests.test_c01_id_package.C01IdPackageTests.test_update_answers_persists_state_and_regenerates_package`

**負控制組**：`python3 -m unittest tests.test_NON_EXISTENT_MODULE_CONTROL` → `Ran 1 test … FAILED (errors=1)`。
⚠ 依 `BR_20260831a`，判別欄位是 **`Ran N tests` 的 N**：真跑那次 N=60，控制組 N=1。rc 兩者皆非零，**rc 無判別力**。

---

## 9. 修法選項（等 dispatcher 裁決，本輪未動任何 `.py`）

三個選項共用的**驗證骨架**（不論選哪個都要有）：

- **正向控制組**：一支新 drift guard 測試，斷言「每個 verb 回傳的 rel path，與呼叫端 `out_dir` join 後 == 實際寫入的絕對路徑」。改對時它綠。
- **反向控制組**：在測試裡**故意**把某一個常數的前綴拿掉（或把某個回傳點改成不帶 stage），該 guard **必須紅**。沒做過這一步的 guard 不算數——它可能是一支永遠綠的假護欄（`code-thinker` §8）。

### 選項 A — 拆成兩組常數（BR §5.1 的原案）

- **改什麼**：`C02_STAGE_REL`（stage 內相對，供 join）+ `C02_PRODUCT_REL`（product-root 相對，供回傳）；c01 同。
- **blast radius**：`c02_me_package.py` 約 40 處逐一判角色；`c01_id_package.py` 5 處；`c01_id_template.py:121`、`mode_contracts.py:74` 兩個角色2 消費者；`tests/test_c02_export_stl_failure_states.py`（8 處引用）、`tests/test_c02_projection_svg.py:54`。`server.py` 不需改（它吃回傳值）。
- **風險**：**最高**。40 個點每一個都要人判「這是 join 還是回傳」，而判錯的那個在下一跳才炸——正是 §4 描述的那件事。
- **驗**：上述骨架 + 一支「兩組常數 keys 必須相同、且 `PRODUCT_REL[k] == STAGE_DIRNAME / STAGE_REL[k]`」的結構斷言（反向：改掉其中一個 key 名，必須紅）。

### 選項 B — 保留單一常數，只讓「回傳點」顯式（BR §5.1 的替代案）

- **改什麼**：常數維持現狀（帶前綴，join 端不動）；把所有 `str(C0x_OUTPUTS[k])` 的**回傳**改成 `str(C0x_STAGE_DIRNAME / name)` 形式的顯式表達，並把 `:35-38` 的錯誤註解改寫成描述**兩個角色**的事實。
- **blast radius**：只碰回傳點（c02 約 20 處 `str(...)`），join 點零改動；測試檔不需改（它們吃的是 join 側與 `openscad_path` 字串，語義不變）。
- **風險**：**中低**。但它**沒有消滅雙前綴模型**，只是讓兩個角色在原始碼上可辨識。§1 那句「in ONE place」仍然是假的，只是不再誤導。
- **驗**：骨架 + 「`str()` 回傳點的字面值與 `C0x_OUTPUTS` 的 posix 形式逐字相等」的 AST/字串掃描（反向：改一個回傳點少一層，必須紅）。

### 選項 C — 只修註解，不動程式碼（把 §1 的宣稱改成事實）

- **改什麼**：`c02_me_package.py:35-38` 的區塊註解改寫為「stage 前綴由 `C02_OUTPUTS` 的每個值攜帶；`_c02_stage_dir()` 只服務 provenance 路徑；兩套模型並存，收斂追蹤於本 BR」。c01 對應處同步。
- **blast radius**：**零程式行為變更**，零測試改動。
- **風險**：最低，但它把 BR 從「契約缺陷」降級為「文件缺陷」。**`_c02_stage_dir()` 的 docstring（`:63-73`）已經做了這件事**（§7），所以選項 C 的邊際價值只剩「把止血從 docstring 提升到那句錯誤宣稱的**現場**」。
- **驗**：無程式驗證可做 ⇒ **這一格沒有判別力，必須誠實標明**，不得偽造一支「註解正確性」測試。

### 建議（handler 意見，非決定）

**B 或 C，不建議 A。** 理由：A 的 40 個判斷點每一個都是 §4 描述的失敗模式的獨立抽獎，而**收益是讓一句註解變真**——risk/reward 不成比例。若目標是「讓宣稱與實作一致」，改宣稱（C）比改 40 處實作（A）便宜三個數量級；若目標是「讓兩個角色在原始碼上可辨識」，B 已足夠且不觸碰 join 側。

**A 唯一值得做的時機**：當 §6 殘留項（c00/c03–c07 同構性）量出來確認是 8 個 stage 的系統性問題、且要一次性導入 `C0N` 前綴規則時——那時 A 是那個大工項的一部分，不是本 BR 的獨立修法。

---

## 10. 裁決與落地（2026-09-01，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH` 裁示）

### 10.1 採用 **C+**：註解改寫 + 機器斷言，**A 明確否決**

**A 被否決的理由 — 第三個角色的發現本身就是實據，這是本輪最有價值的產出：**

§4 的整個論證建立在「兩個角色」之上（filesystem join 的右手邊 / 回傳給呼叫端的 rel path）。
2026-09-01 的重驗發現實際是**三個**——第三個是 `c01_id_template.py:121` 的**對帳集合**：
`{p.as_posix() for p in C01_OUTPUTS.values()}` 與 template 自身獨立導出的 `f"{folder}/{carrier}"`
比對，差集非空即 `raise C01TemplateError`。它既不是檔案 join，也不是回傳 rel。

**關鍵在於誰漏掉了它**：BR_20260804h 的作者**正是專注在「這些常數身兼幾職」這個問題上**，
在 12 個常數的範圍內，仍然漏數了一個角色。

而選項 A 要求對**約 40 個消費點逐一人工判定角色**，其失敗模式是 §4 自己寫的
「路徑對、但回傳的 rel 少一層——**在下一跳才炸**，而且炸的地方離改動點很遠」。

一個專注的人在 12 個常數上漏了一格；40 個點的分類會漏幾格是可以推的。
**A 的風險論證至此不再只是 BR 自陳，而是有實測案例支撐。**

### 10.2 為什麼不是純 C

純 C 的自陳弱點（§9 選項 C 的「驗」欄）是：**無程式驗證可做 ⇒ 這一格沒有判別力**。

那是正確的自我評價，但它可以被修好——**註解描述的是可機械斷言的不變量，不是主觀文意**。
所以 C+ = C 的註解改寫 **＋** 把那些不變量變成測試。

### 10.3 已落地內容

**(a) 註解改寫（兩處，三個角色各帶 file:line）**

- `packages/workflow-core/bodesign_workflow_core/c02_me_package.py` — `C02_STAGE_DIRNAME` 上方區塊註解
- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py` — `C01_OUTPUTS` 上方區塊註解

原本那句「derived from it here, in ONE place, so ... no two code paths can disagree」已刪除，
改為明寫「TWO prefix models coexist」與三個角色：

| 角色 | 語義 | file:line 實例 |
|---|---|---|
| 1 | filesystem join 的右手邊 | `c02_me_package.py:386`（`path = root / C02_OUTPUTS["openscad"]`）／`c01_id_package.py:399`-`:403`、`:1391` |
| 2 | 回傳給呼叫端、被呼叫端**再 join 一次**的 rel path | 回傳於 `c02_me_package.py:453`，re-join 於 `services/mcp/server.py:320`（`Path(a["out_dir"]) / stl_rel`）／`mode_contracts.py:74` 的對外契約字串 |
| 3 | **對帳集合的成員**，與獨立導出的前綴比對 | `c01_id_template.py:121`（差集非空 → `C01TemplateError`）— **§4 自己漏掉的那個** |

兩處註解皆明記「Role 3 was missed by BR_20260804h's own analysis, which counted two.」

**(b) 新增 `tests/test_stage_prefix_invariant.py`** — 把註解宣稱中可機械斷言的部分變成測試：

| 類別 | 斷言 |
|---|---|
| `StagePrefixCarriedByEveryConstant` | 每個 `C0x_OUTPUTS` 值的 segment 0 == 該 stage dirname；且 dirname 與 `readiness_common.STAGE_FOLDER` 一致 |
| `StageDirHelperDerivesTheSameSegment` | `_c0x_stage_dir(root) == root / <dirname>`；`None` 仍 fail-closed；**兩套前綴模型產出同一段**（`root / rel == stage_dir(root) / rel[1:]`） |
| `TemplateReconciliationRoleStillHolds` | 角色3：`template_carriers ⊆ emitter_carriers`；`tpl.folder == C01_STAGE_DIRNAME` |
| `NegativeControlTests` | 四支預設控制，證明上述謂詞本身不是恆真 |

### 10.4 反向控制組實測（**活體**，不是只寫在測試裡的預設控制）

### 方法裁定：為什麼不能 mutate 磁碟上的 `.py`（下一個做 mutation proof 的人直接看這段）

派工單原本寫「在測試裡臨時把某個常數的前綴拿掉」，可讀成改磁碟。**拒絕，理由不是「另一種做法」而是避開一個已建檔的假陰性**：

> **AGENTS.md §6.3 的 stale-pyc 陷阱正是 mutate-on-disk 循環本身的失效模式。**
> CPython 判定 `.pyc` 是否有效用的是來源檔的 mtime（**秒級**）+ size。
> mutation proof 的典型手法——**同一秒內、等長度**地把 `"C02-ME"` 改成別的七字串——
> 兩個欄位都沒變，mutant 的 bytecode 沒被重建，**舊版被載入**。`-B` 擋不掉（它只阻止寫入、不阻止讀取既有 `.pyc`）。
> 於是：**mutant 根本沒被套用 → 測試仍綠 → 被讀成「這支 guard 沒有判別力」**。
> 得到的是**反向結論**，不是少一格證據，是一格假證據。

改用：載入模組後**就地替換測試命名空間中的真實常數／helper 物件**，再重跑同一段 assert。
同一段判斷程式碼、同一個資料物件，只有資料被換掉 ⇒ **判別力等價，且不觸碰磁碟，所以不可能撞上 pyc 快取**。

**可機械套用的判準**：凡在 repo 內做「mutate → 跑測試 → 還原」循環，
**先問「我能不能不碰磁碟就達到同樣的判別力」**；能 ⇒ 就不要碰。
非碰不可時，`find . -name __pycache__ -prune -exec rm -rf {} +` 是**必要步驟不是保險**，
而 `-B` 出現在腳本裡**不構成已經清過**。

| 突變 | 弄壞了什麼 | guard 反應 | 紅在哪一行 / 訊息 |
|---|---|---|---|
| BASELINE | 什麼都沒改 | `ran=3 failures=0` | — |
| MUT-1 | `C02_OUTPUTS["stl"]` 的 `C02-ME/` 前綴拿掉 | `failures=1` ✅（量測範圍：**只載入 `StagePrefixCarriedByEveryConstant` 這一個 TestCase**，`ran=3`） | `test_stage_prefix_invariant.py:55`，`AssertionError: 'C02-ME' != 'Enclosure.stl'`（subTest `key='stl'` 精確指名） |
| MUT-2 | `C01_STAGE_DIRNAME` 改一個字（`C01-ID`→`C01-1D`） | `failures=6` ✅ | 5 個 key 全紅 + `test_stage_dirnames_match_the_central_stage_folder_map` 紅（`AssertionError: 'C01-ID' != 'C01-1D'`）⇒ 中央 map 那條交叉斷言確實承重 |
| MUT-3 | `_c02_stage_dir` 回傳 `C02-MECH`（helper 與常數分歧） | `failures=13` ✅ | `test_c02_stage_dir` + `test_helper_output_is_the_prefix_the_constants_carry` 全部 12 個 key ⇒ **「兩套模型是否同意」這條真的在測** |
| MUT-4 | template 宣告一個 emitter 不產出的 carrier | `failures=1` ✅ | `AssertionError: {'C01-ID/Ghost/Not_Produced.md', ...} not less than or equal to {...}` ⇒ **角色3 被釘住** |
| RESTORE | 全部還原 | `failures=0` ✅ | 證明前面的紅來自突變，不是測試本身壞了 |

**四組突變全部使 guard 變紅，還原後回綠。** 這支 guard 不是永遠綠的假護欄。

**⚠ 量測範圍差異（照實記，不強行對齊）**：dispatcher 獨立複驗 MUT-1 時測到 `failures=2`，
本表記 `failures=1`。差異來源是**載入範圍不同**：本表只載入單一 TestCase（`ran=3`），
dispatcher 跑全模組（`ran=13`）而多觸發一條。
**方向與結論一致（突變使 guard 變紅），但兩個數字不可互相引用。**
（這正是 AGENTS.md §6.1 「快照歧義陷阱」的測試層版本：兩人都對，量的不是同一個窗口。）

### 10.5 迴歸

```
find . -name __pycache__ -prune -exec rm -rf {} +      # 前後皆清（AGENTS.md §6.3）
PP=$(ls -d packages/*/ | tr '\n' ':')
PYTHONPATH="$PP" python3 -m unittest tests.test_stage_prefix_invariant \
    tests.test_c02_export_stl_failure_states tests.test_c02_me_package \
    tests.test_c01_id_package tests.test_c01_id_template tests.test_c02_projection_svg
→ Ran 78 tests … FAILED (failures=2, skipped=3)
```

- 新 guard 單獨跑：`Ran 13 tests … OK`
- 78 = 基線 60（4 模組）+ 新 guard 13 + `test_c02_projection_svg` 5
- **兩個失敗與 §8.5 基線逐字相同**（`test_readiness_uses_field_gaps_when_answer_state_exists`、
  `test_update_answers_persists_state_and_regenerates_package`）⇒ **零回歸**
- 負控制組：`tests.test_NON_EXISTENT_MODULE_CONTROL` → `Ran 1 test … FAILED (errors=1)`。
  判別欄位是 `Ran N tests` 的 N（真跑 78 / 控制組 1），**rc 無判別力**（`BR_20260831a`）

---

## 11. c00 / c03–c07 同構性量測（2026-09-01，回填 §6 殘留項）

**母體宣告**：`readiness_common.py:30-39` 的 `STAGE_FOLDER` 共 **8 個 stage**（c00…c07）。
本節量其中 **6 個**（c00、c03、c04、c05、c06、c07），c01/c02 已在 §8.3 量過。
掃描窗口 = `packages/workflow-core/bodesign_workflow_core/` 共 38 個項目，其中 `c0N_*.py` 模組 **10 個**。

### 11.1 三個結構元件的全 repo 分佈（母體 = 全 repo `.py`，排除 `.venv`/`__pycache__`）

| 元件 | 命中 | 母體/控制組 |
|---|---|---|
| `^[A-Z0-9_]*OUTPUTS[A-Z0-9_]* *[:=]` 常數宣告 | **5 個**：`C02_OUTPUTS`(c02:41)、`C01_OUTPUTS`(c01:29)、`C01_PROMPT_OUTPUTS`(c01:139)、`_C01_EXPECTED_OUTPUTS`(mode_contracts:74)、`CANONICAL_OUTPUTS`(skills/…/analysis_cache.py:33，非 stage 路徑表) | 控制組 `^ZZZ_NEVER_OUTPUTS` rc=1 ⇒ 探針會回空 |
| `^def _c[0-9]+_stage_dir` | **2 個**：`c02:57`、`c01:94` | 同批次掃描，同 pattern 對 c01/c02 命中 ⇒ pattern 有效 |
| `*_STAGE_DIRNAME` 常數 | **2 個**：`C02_STAGE_DIRNAME`(c02:39)、`C01_STAGE_DIRNAME`(c01:91) | 同上 |

⇒ **c00 / c03–c07 六個 stage，三個元件全部零命中。**

### 11.2 那六個 stage 實際怎麼放前綴（逐檔實讀，非只數命中）

`grep -c 'C0[0-9]-'`，母體 = 上述 10 個 `c0N_*.py` 模組：

| 模組 | hits | 實際形狀 |
|---|---|---|
| `c00_orchestration.py` | 2 | `_C00_ANSWER_STATE_REL = Path("C00-PRD") / "03_output" / "answer_state.json"`（+legacy）— **單檔常數，非 dict** |
| `c00_prd_docx.py` | 5 | `root / "C00-PRD"` 與 inline `Path("C00-PRD") / ...` — **無常數表** |
| `c00_prd_template.py` | 11 | 全部 inline `Path("C00-PRD") / ...` / `root / "C00-PRD"` — **無常數表** |
| `c03_host_block_diagram.py` | 4 | `HOSTBLOCK_{SVG,PNG,PPTX}_REL = Path("C03-EE") / "block" / ...` — **三個單檔常數** |
| `c03_partition_diagram.py` | 4 | `PARTITION_{SVG,PNG,PPTX}_REL` 同形 — **三個單檔常數** |
| `c03_mechanical_constraints.py` | 1 | `C03_OUTPUT = Path("C03-EE") / "Mechanical_Constraint_Export.json"` — **單數，非 dict** |
| `c04_layout_constraints.py` | 9 | `C04_FOLDER = Path("C04-Layout")`、`_C03_FOLDER = Path("C03-EE")` + 6 處錯誤訊息字串 — **folder 常數而非 outputs 表** |
| `c04_placement_gate.py` | 0 | 無任何 stage 前綴字面 |
| `c05_fw_spec.py` | 1 | `C05_FOLDER = Path("C05-FW")` — **folder 常數** |
| `c06_test_plan.py` | 1 | `C06_FOLDER = Path("C06-Verification")` — **folder 常數** |
| CONTROL `c02_me_package.py` | **30** | 同一支 grep，已知必非零 ✅ |
| CONTROL `c01_id_package.py` | **35** | 同上 ✅ |

**c07**：`ls packages/workflow-core/bodesign_workflow_core/ | grep '^c07'` → rc=1（**無 c07 模組**）。
控制組：同指令 `grep '^c06'` → rc=0 命中 `c06_test_plan.py` ⇒ 零命中不是探針失效。

### 11.3 三態結論

| stage | 判定 | 依據 |
|---|---|---|
| **c00** | **不同構** | 無 `C00_OUTPUTS` dict、無 `_c00_stage_dir`、無 `C00_STAGE_DIRNAME`。前綴以 **inline 字面**散佈在 3 個模組共 18 處。**問題不同**：不是「一個常數身兼三職」，是「根本沒有常數表」——那是 `BR_20260804_stage_deliverable_names_are_hardcoded_per_module` 的領域 |
| **c03** | **不同構** | 同上三元件皆無。前綴以 **7 個單檔 `*_REL` 常數**（block/partition 各 3 + mechanical 1）攜帶。單檔常數不構成本 BR 的「一個 dict 服務三個角色」形狀 |
| **c04** | **不同構** | `C04_FOLDER = Path("C04-Layout")` 是 **folder 常數**（等價於 `C0x_STAGE_DIRNAME` 的角色），**沒有** outputs 對照表。`c04_placement_gate.py` 零前綴字面 |
| **c05** | **不同構** | 只有 `C05_FOLDER`，無 outputs 表 |
| **c06** | **不同構** | 只有 `C06_FOLDER`，無 outputs 表 |
| **c07** | **未能判定** | **`workflow-core` 下不存在 c07 模組**（控制組已排除探針失效）。`STAGE_FOLDER` 宣告了 `"c07": "C07-MFG"`，但沒有對應實作模組可掃 ⇒ **「這個 stage 沒有這個問題」與「這個 stage 的程式碼還沒寫」在本次量測中共用同一個零命中**。不得記為「沒有問題」 |

### 11.4 這對選項 A 的意涵

**本 BR 的形狀（一個 dict 常數同時服務三個角色）只存在於 c01 與 c02，母體 2/8。**

⇒ §9「A 唯一值得做的時機」所設想的前提（**8 個 stage 的系統性問題**）**不成立**。
六個 stage 各自用不同且較簡單的模型（inline 字面 / 單檔 `*_REL` / 只有 folder 常數），
把它們統一到 `C0N` 前綴規則是**另一張 BR 的工作**
（`BR_20260804_stage_deliverable_names_are_hardcoded_per_module_so_the_C0N_prefix_rule_cannot_be_adopted`），
且那項工作面對的是「常數缺席」而非「常數超載」——**與 A 的拆分手法不是同一件事**。

**結論：選項 A 在可預見的未來都不會有值得執行的時機。** 若將來仍要做，觸發條件應改寫為
「c01/c02 這兩個 dict 本身需要新增第四個角色時」，而不是「其他 stage 同構時」。

### 11.5 本節沒量什麼

- **只量了 `packages/workflow-core/`**。其他 package（`reverse-core`、`doc-core`、`gerber-core`…）
  是否有各自的 stage 前綴表**未掃**（§11.1 的 `*_OUTPUTS` 全 repo 掃描涵蓋了常數宣告，
  但 inline 字面形式的前綴未在其他 package 逐檔量）
- **`c04_layout_constraints.py:34` 的 `_C01_CONSTRAINTS_REL = Path("C01-ID") / "Interface_Constraints.json"`
  是一個跨 stage 的重複宣告**——它與 `C01_OUTPUTS["constraints"]` 指同一個檔卻是獨立字面。
  這是**另一個** drift 面（兩個模組各自寫死同一條路徑），本輪未展開，也未建 BR（依派工單⑤，回報 dispatcher 裁決）
