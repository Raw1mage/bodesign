# BR_20260901h — eager-import 稽核是非傳遞式的，一條相對 import 新邊即可夾帶重依賴而守衛不紅

- **Status**: **COVERAGE GAP — 現行 offender 數為 0，無已知損壞行為**
  這不是「現在有東西壞了」，也不是「所以不重要」。準確的描述是：守衛回綠時，
  **「真的沒有 offender」與「有 transitive offender 但守衛看不到」共用同一個輸出**，
  而 `BR_20260901e` 剛新增的三條相對 import 邊是第一次把這個形狀送到守衛面前。
  — **「offender 數為 0」已於 2026-09-02 收編進版控時重驗**（`ses_ff4d5aa5cffe`，adopt-901h）：
  照抄 `tests/test_check_c03_gate_reachability_and_netlist.py:133-152` 的兩條 regex 對
  `packages/workflow-core/bodesign_workflow_core/` 重跑，得
  `EAGER_MODULE_COUNT=32 / DIRECT_OFFENDER_COUNT=0 / TRANSITIVE_OFFENDER_COUNT=0`，
  與 §3.2 逐字一致。**兩組控制組同批執行**：正向 —— 同一支掃描器問
  `package_readiness` 回 `['bodesign_reverse_core']`（非空，證明它抓得到 module-level
  重依賴，故 `0` 不是「掃描器沒跑」）；反向 —— 問 `zzqq_never_20260901` 回 `(None, [])`
  （證明它不是永遠命中）。
**Severity**: low-medium — 揭露缺陷（disclosure gap），非行為缺陷。它的成本在**未來**：
  下一條新增的相對 import 邊若指向一個 module-level 重依賴的模組，`check_c03`
  的 consumer reachability 會在守衛全綠的情況下再次破裂——那正是 `BR_20260730 §3`
  已經付過一次代價的事。
**Owner**: `(default)`（`ses_04db7a1c5ffelvbxyLP1p6xlRH`，coordinator）
  — **依據**：本張的修復面是 `packages/workflow-core/bodesign_workflow_core/__init__.py`
  的 `_LAZY_EXTERNAL_DEP_EXPORTS` 與 `tests/test_check_c03_gate_reachability_and_netlist.py`。
  實測 `issues/OWNERS.md` 內 `grep -n "platform_gate_unreachable\|consumer_fork"` → **rc=1**
  （控制組：同檔查 impossible token 亦 rc=1 ⇒ 探針有牙），即**孕育這支守衛的
  `BR_20260730_platform_gate_unreachable` 從未被登記進任何 family**。
  依 `OWNERS.md` §"Why `(default)` exists"：「No family matched」永不構成開新 session 的理由，
  一律路由 `(default)`。
  **Cross-ref（不是 owner，是動刀前該知會的）**：`c03-stage-discipline`——守衛存在的**目的**
  是保住 `check_c03` 的可達性，而該 family 的 fix surface 含 `check_c03.py`；
  但本張的修復面（`__init__.py` + 該測試檔）不在其宣告清單內，故不冒認。
**Filed by**: `ses_fa658134bffeM1Ve1jIomrfYD9`（BRNS handler，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`）
**Filed**: 2026-09-01

**Related**:

- `issues/closed/BR_20260730_platform_gate_unreachable_drives_consumer_fork_and_bom_netlist_gate_hole.md`
  — **同一個守衛，不同的涵蓋邊界**（**不是**同一個缺陷，也不是它的復發）。可引用依據：
  **兩個可引用錨，分屬不同檔、不可互換**（2026-09-02 逐檔查證，收編時更正）：
  ① `issues/closed/BR_20260730_…md:124` `## §3 缺陷 3（機制性根因）：平台 gate 在 consumer
  端無法執行` —— 該節建立的是**根因**（`__init__.py:80` eager import `checkers` 鏈，
  逐字 `ModuleNotFoundError` traceback）。**該節並未提到 `_LAZY_EXTERNAL_DEP_EXPORTS`
  或 PEP 562**：在 §3 的 36 行視窗內 grep 該兩詞 rc=1，而視窗經 `wc -l` 證明為 36 行非空
  （第一次探針把視窗切成 0 行，treatment 與 control 同時 rc=1 而無判別力，已重做）。
  手寫清單那件事落在**同檔 :519-521（§10.9 未做／邊界）**：「`_LAZY_EXTERNAL_DEP_EXPORTS`
  是手寫清單 = V4-c 形狀，故 `test_no_third_eager_offender_appears` 從原始碼**重新推導**
  audit，出現第三個 eager 違規者即紅」。
  ② 英文版「The map is a hand-written list … **re-derives the audit from source** and fails
  if a third eager offender appears」**只存在於 `specs/architecture.md:67`**，不在該 BR 內
  （`grep -rn "re-derives the audit from" --include=*.md .` 全 repo 僅命中 architecture.md:67
  與本檔；控制組：同形狀查 `re-derives the ZZQQ from` rc=1）。
  本張指出的正是那句話裡 **"eager offender" 的量詞範圍**：稽核只走 `__init__` 的 eager
  子模組**自身那一層**，不跟著相對 import 往下走。原 BR 修的兩個 offender
  （`.checkers`、`package_readiness`）都是 direct，所以當時的非傳遞式稽核對它們**完全足夠**；
  本張不主張它當時寫錯。

- `issues/closed/BR_20260901e_same_stage_path_has_two_independent_sources_of_truth.md`
  — **時序因果**（不是同一失效類別）。可引用依據：901e 的 commit `d5dee04` 在
  `workflow-core` 內部新增三條**相對** import 邊（2026-09-02 逐條在 HEAD 查證存在，補上 `file:line`；
  控制組：同一支 grep 在同檔查 `from .zzqq_never_20260901 import` rc=1，
  而同檔 `grep -c import` = 9 證明探針有牙）——
  `c04_layout_constraints → c01_id_package`（`c04_layout_constraints.py:25`
  `from .c01_id_package import C01_OUTPUTS`）、
  `upstream_constraints → c03_mechanical_constraints`（`upstream_constraints.py:39`
  `from .c03_mechanical_constraints import C03_OUTPUT`）、
  `mode_contracts → orchestration`（`mode_contracts.py:28` `from .orchestration import (`）——
  該 commit 標題 `fix(workflow-core): collapse six cross-stage path declarations to one each`，
  `--numstat` 動 5 檔全在 `packages/workflow-core/bodesign_workflow_core/`——
  這是第一次有變更需要回答「新的相對邊會不會讓輕量模組繼承重依賴」，
  而該問題在 901e 的 architecture-sync 覆核（`ses_fa658134bffe…`，本 session）中量測時，
  才發現守衛答不出來。901e 本身**未**造成任何 offender（見 §3 量測），
  故本張不是 901e 的殘留缺陷，是它照亮的既有邊界。

- `issues/BR_20260901g_skill_side_render_prd_hardcodes_legacy_answer_state_and_cannot_import_the_constant.md`
  — **無因果關係，僅同批次**。列出只為讓讀者知道本輪產出兩張新 BR，形狀不同：
  901g 是 dual-SSOT（901e 同類），本張是稽核涵蓋缺口。

- 查過但**無**其他可引用的邊：`grep -rln "_LAZY_EXTERNAL_DEP_EXPORTS\|eager\|reachability"
  issues/ --include=*.md` 命中 6 檔，逐一判讀後只有上述 `BR_20260730` 與此議題同源；
  其餘（`BR_20260730_skills_endpoint`、`BR_20260730b`、`BR_20260730d`、
  `BR_20260707_c03_stage_entry_gate`、`BR_20260802_reset_hard…`）命中的是
  「import」「reachability」的其他語義，非本議題。控制組：同一支 `grep` 查
  `ZZQQ_NEVER_20260901` → rc=1，證明它會回空而非永遠命中。

---

## 1. 症狀 — 一句話

`tests/test_check_c03_gate_reachability_and_netlist.py::test_no_third_eager_offender_appears`
在「eager 模組自己不 import 重依賴，但它相對 import 的另一個模組會」的情況下**回綠**。

它綠的時候，讀者得到的訊息是「consumer reachability 仍然守住」；
實際上它只驗證了那個保證的**一層**。

---

## 2. 機制 — 稽核的實作決定了它的量詞範圍

`tests/test_check_c03_gate_reachability_and_netlist.py:133-152`（逐字，HEAD）：

```python
init_src = (_MOD_DIR / "__init__.py").read_text(encoding="utf-8")
eager = set(re.findall(r"^from \.(\w+) import", init_src, re.M))
...
offenders: dict[str, list[str]] = {}
for mod in sorted(eager):
    f = _MOD_DIR / f"{mod}.py"
    if not f.is_file():
        continue
    src = f.read_text(encoding="utf-8")
    deps = sorted(set(
        re.findall(r"^from (bodesign_(?!workflow_core)\w+)", src, re.M)
        + re.findall(r"^import (bodesign_(?!workflow_core)\w+)", src, re.M)))
    if deps:
        offenders[mod] = deps
self.assertEqual(offenders, {}, ...)
```

迴圈只迭代 `eager` 這個集合，每個成員只讀**自己那一個檔**。
`from .x import Y` 這種相對 import 在 `deps` 的兩條 regex 裡都不匹配
（`bodesign_(?!workflow_core)\w+` 要求絕對名），所以**相對邊既不被記錄、也不被追蹤**。

**Python 的 import 語義是傳遞的，這支稽核不是。** 落差就是本張。

配對的 `test_audit_would_catch_an_offender`（:154-160）只驗證那兩條 regex
對一個已知 offender 字串仍匹配——它守的是「regex 沒爛掉」，
**不是**「稽核的走訪範圍夠大」。兩者是不同的判別問題。

---

## 3. 證據

### 3.1 三場景重現（scratch 造假 package，跑稽核的**實際邏輯**，regex 照抄 :133-152）

| 場景 | 結構 | 稽核輸出 | 判定 |
|---|---|---|---|
| **S1** direct offender | `__init__` eager → `a.py`，`a.py` module-level `from bodesign_design_ir import …` | `{'a': ['bodesign_design_ir']}` | **偵測到** ✔ |
| **S2** transitive offender | `__init__` eager → `a.py` → `from .b import Y`，`b.py` module-level `from bodesign_design_ir import …` | `{}` | **漏掉** ✘ |
| **S3** 乾淨對照 | `a.py` 只 `import json`，`b.py` 無 import | `{}` | 正確為空 ✔ |

**S2 是本張的核心**：offender 真實存在、`import bodesign_workflow_core`
會真的觸發它、`ModuleNotFoundError` 會真的發生——而稽核回 `{}`，與 S3 逐字相同。

S1/S3 的存在是必要的：**沒有 S1，`{}` 可能只代表稽核根本沒跑；
沒有 S3，`{}` 可能只代表它永遠回空。** 三者合起來才使 S2 有意義。

### 3.2 現行 repo 的實況（HEAD，兩種稽核並排）

```
EAGER_MODULE_COUNT      = 32
DIRECT_OFFENDER_COUNT   = 0     ← 現行守衛所見；它斷言 == 0，套件 64/64 綠
TRANSITIVE_OFFENDER_COUNT = 0   ← 若改成傳遞式，所見亦為 0
```

**現行沒有任何真實 offender 被這個缺口藏起來。** 這句話必須明寫，
否則本張會被誤讀成「有東西壞了」。

探針非平凡性（否則 `0` 什麼都不證明）：

```
reach(c04_layout_constraints) = 8 個模組
reach(mode_contracts)         = 9
reach(upstream_constraints)   = 2
reach(zzqq_never_20260901)    = 0        ← 控制組
```

### 3.3 稽核的 regex 集合本身沒有漂移

`__init__.py` 的 eager 集合，兩種取法一致：

```
regex  set  = 32
AST    set  = 32
in_ast_not_in_regex = []
in_regex_not_in_ast = []
CONTROL sets_are_nonempty = True
```

（`ast_list` 未去重時為 34，落差是**兩筆重複 import**，不是取法差異。）
所以本張**不**主張那兩條 regex 有 parsing 缺陷——缺陷純粹在走訪深度。

### 3.4 901e 的三條新邊為何實際上沒有夾帶（本張不是行為缺陷的理由）

module-level-only 外部依賴閉包，`d5dee04~1` vs `d5dee04` 雙臂：

```
                          base   after
c04_layout_constraints    []     []
upstream_constraints      []     []
mode_contracts            []     []
c01_id_package            []     []
```

新上游 `c01_id_package` 的重依賴全部是函式內 deferred：

```
c01_id_package.py:1668         cairosvg               FUNCTION-LEVEL
c01_id_package.py:1957         bodesign_reverse_core  FUNCTION-LEVEL
package_readiness.py:18        bodesign_reverse_core  MODULE-LEVEL   ← 已在 lazy map，不在 eager 集合
CONTROL 同掃描器問 impossible token → 0 hits
```

**若 `c01_id_package.py:1668` 當初寫在 module level，這條新邊就會夾帶 cairosvg
給 `c04_layout_constraints`，而守衛不會紅。** 這一句是本張存在的全部理由。

---

## 4. 修法選項（**不做裁決**，各自列出防住什麼、代價是什麼）

### 選項 A — 把現行稽核改成傳遞式閉包

跟著 `from .x import …` 往下走，把整條鏈上每個模組的 module-level 外部依賴
都算進該 eager 模組名下。

- **防住**：S2 形狀。任何深度的相對邊夾帶都會紅。
- **噪音代價（已量）**：**0**。現行 32 個 eager 模組套上傳遞式稽核後，
  offender 數仍為 0（§3.2）——即**套上去不會站紅**，不存在「太吵而被關掉」風險。
  這格是 dispatcher 點名要求先量的，量出來的答案讓此選項的代價遠低於預期。
- **真實代價在別處**：稽核從「讀 N 個檔」變成「走一張圖」，需處理循環依賴
  （`seen` 集合）與 `from . import x` 這種無 module 名的形式；稽核本身變複雜，
  而**變複雜的稽核自己就需要控制組**（現行的 `test_audit_would_catch_an_offender`
  只守 regex，不足以守一個圖走訪）。
- **不防住**：動態 import（`importlib.import_module(字串)`）、
  函式內 import 被改成 module-level 以外的任何形式。

### 選項 B — 另寫一支專測 transitive 的守衛，現行那支不動

- **防住**：同 A。
- **優點**：兩支守衛失敗時的訊息不同——direct offender「X 自己 import 了 Y」
  與 transitive offender「X 經 a→b 觸及 Y」修法不同（前者搜 lazy map，
  後者要判斷該切哪一條邊），分開報不會把兩種診斷塌在一起。
- **代價**：兩支守衛對同一份 `__init__.py` 各自 re-derive，
  即本 repo 已有前例的 **V4-c 手寫複本**形狀（`BR_20260729`）——
  兩支的 eager 集合取法可能獨立漂移。

### 選項 C — 不修，只把涵蓋邊界寫進守衛的 docstring 與 `architecture.md:67`

- **防住**：什麼都不防。它只修正**讀者的推論**：
  綠燈不再被讀成「整條 import 鏈都安全」。
- **代價**：最低（改兩段散文）。
- **風險**：這是把判別力問題降級成文件問題。下一個 cold-context agent
  看到的仍然是一支全綠的守衛，而 docstring 不會在 CI 裡叫。

**本張不做選擇。** 三者都是實作，建檔者只建檔。

---

## 5. 驗收建議（若日後採 A 或 B）

不論採哪個，驗收必須包含 **§3.1 的 S2 場景作為反向控制組**：
新守衛必須對 S2 紅、對 S3 綠。**只驗 S1 不夠**——現行守衛對 S1 本來就會紅，
一支只能通過 S1 的新守衛可能一行都沒改到。

另建議把 `TRANSITIVE_OFFENDER_COUNT`（現為 0）当成基線記入，
理由與 `no_silent_degradation.py` 把 repo baseline 11 記入 KB 相同：
**零發現時，呼叫端必須分得出 `clean` 與 `never scanned`。**

---

## 6. Remaining — 本輪**未判定**，不是已確認無事

1. **動態 import 形式未掃**。本張所有量測皆為 **AST 静態**分析。
   `importlib.import_module(字串拼出來的名字)`、`__import__(變數)`、
   `exec` 這類形式探針看不到。**現行 repo 有沒有這種形式，未查。**

2. **32 個 eager 模組未做 base/after 全比對**。§3.4 只量了 901e 直接涉及的
   四個模組（三個下游 + 新上游）。其餘 28 個在兩臂間是否一致，未量。

3. **`_LAZY_EXTERNAL_DEP_EXPORTS` 那 8 個 symbol 是否有多餘項，未查。**
   這一項值得單獨講清楚：**守衛測試綠只證明「沒有應該 lazy 卻是 eager 的模組」，
   不證明「那張手寫表上每一項都仍然必要」。** 兩個方向是不同的問題，
   而現行只有一個方向有守衛。一個已經不再需要 lazy 的 symbol 留在表上，
   會讓它的 export 比必要的晚一拍解析，而沒有任何東西會叫。

4. **`specs/` 下其他目錄未掃**。本輪只對 `specs/architecture.md` 一個檔做過比對；
   其他 spec 目錄是否也在描述這層 import 拓泫，未查。

5. **`(default)` 是依 OWNERS.md 規則推出來的，不是查到明文指派。**
   若 coordinator 判定該開一個 `import-reachability` family 或歸給
   `c03-stage-discipline`，以 coordinator 為準。

---

## 7. 計量環境

- HEAD `d5dee04`（+ 已 commit 的 `2e652a0` 歸檔），工作樹在 `packages/` 無未提交修改
- 雙臂以 `git show <sha>:<path>` 落到 `$XDG_RUNTIME_DIR`，**未動工作樹、未 checkout**
- 所有 unittest 執行前清 `__pycache__`（AGENTS.md §6.3：`-B` 擋不掉既有 stale pyc）
- scratch 跑完已清，配 `test -d` 控制組
