# BR_20260831a — 這個 repo 沒有 test bootstrap：測試綠燈依賴一條口耳相傳的 `PYTHONPATH`，而漏掉它的紅燈與「真的回歸了」共用同一個輸出

- **Status**: FIXED — 2026-09-01 落地選項 3+4+5（`tests/__init__.py` 機制層 + `scripts/run_tests.sh` 顯式入口 + `AGENTS.md §5` 文件）；三格對照 + 反向控制組 + 零回歸集合比對均已量測，見 §修復紀錄。**已於 2026-09-01 經 dispatcher 授權後 commit（sha 由 dispatcher 於歸檔時補）。**
- **Owner**: unassigned（filed by BRNS handler `ses_02fb3c62cffewvdN14bK1KHXbc`，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`）
- **Family**: `G13-harness-disclosure`
- **Severity**: high — 它讓「模組根本沒載入」偽裝成「測試失敗」，而下一個 cold-context 的人會據此推論「先前的修復失效」
- **Component**: repo root（缺 `conftest.py` / `pyproject.toml` / `pytest.ini` / `tests/__init__.py` bootstrap）× `tests/*` × `packages/*/`
- **Filed at**: 2026-08-31
- **時區**: Asia/Taipei (UTC+08:00)

**Related**（citable basis）：

- `issues/BR_20260802_fidelity_gate_is_red_after_restore_and_never_ran_at_head.md` §9.2
  —— **時序因果**：本張正是從那張 BR 的可重現性缺口衍生。§9.2 宣稱
  「`tests.test_fidelity_gate` 在 HEAD 為綠」卻未寫出呼叫方式；VANS 在複驗時照直覺跑
  得到紅燈，逐字踩到本張所述的坑。該 BR 的 §9.2.1 已於同一輪補上呼叫指令，
  但**指令被寫進一張 BR ≠ 這個 repo 有 bootstrap**——那只是把口耳相傳搬到另一份文件裡。
- 同一張 BR 的 :21（行號；該檔 heading 皆無數字編號）：
  > 「儀器紅燈」與「儀器從未開機」在測試摘要上都是一行 FAILED。
  —— **同一種失效類別：缺席態與失敗態共用同一個輸出**。那張講的成因是
  `kicad_emit.py` 缺檔，本張講的成因是 `sys.path` 缺 `packages/*/`；
  **成因不同，輸出字串完全同形**（`Ran 1 test in 0.000s` / `FAILED (errors=1)` / rc=1）。
- `AGENTS.md §5`（「跑測試的 PYTHONPATH」）—— **同一條執行路徑**：那裡已寫下正確配方
  （`PP=$(ls -d packages/*/ | tr '\n' ':')`），也已警告「PYTHONPATH 不全會
  `ModuleNotFoundError`」。**本張不是「沒人寫過」，是「寫在只有讀過 AGENTS.md 的人才知道的地方，
  而工具鏈本身不揭露」**——這正是它屬於 G13 而非文件缺漏的理由。
- `issues/BR_20260802_probe_ambiguity_is_the_one_defect_family_no_guard_scans_and_it_fired_16_times_today.md`
  —— **同一種失效類別（probe ambiguity）**，本張是該族在 test harness 這一格的實例。

---

## 一句話問題陳述

**這個 repo 的測試能不能跑，取決於呼叫者是否事先知道一條沒有任何機制會告訴他的 `PYTHONPATH`；
而不知道的人拿到的錯誤訊息，與「這個測試真的壞了」在字面上完全相同。**

---

## 最小重現（含控制組，2026-08-31 實測於 `/home/pkcs12/projects/bodesign`，HEAD 工作樹）

前置（排除 stale `.pyc` 干擾，見 `AGENTS.md §6.3`）：

```bash
find . -name __pycache__ -prune -exec rm -rf {} +
```

### A — 不帶 PYTHONPATH（最直覺的跑法）

```
$ python3 -m unittest tests.test_fidelity_gate
E
======================================================================
ERROR: test_fidelity_gate (unittest.loader._FailedTest.test_fidelity_gate)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_fidelity_gate
Traceback (most recent call last):
  File "/usr/lib/python3.12/unittest/loader.py", line 137, in loadTestsFromName
    module = __import__(module_name)
             ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/pkcs12/projects/bodesign/tests/test_fidelity_gate.py", line 16, in <module>
    from bodesign_eda_bridge import (
ModuleNotFoundError: No module named 'bodesign_eda_bridge'


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)

rc=1
```

### B — 帶 PYTHONPATH（正向控制組：證明代碼本身沒問題）

```
$ PP=$(ls -d packages/*/ | tr '\n' ':')
$ echo "$PP"
packages/component-kb/:packages/design-ir/:packages/doc-core/:packages/eda-bridge/:packages/gerber-core/:packages/kicad-plugin/:packages/reverse-core/:packages/shared/:packages/source-core/:packages/storage-core/:packages/workflow-core/:

$ PYTHONPATH="$PP" python3 -m unittest tests.test_fidelity_gate
.....
----------------------------------------------------------------------
Ran 5 tests in 0.664s

OK

rc=0
```

**A 與 B 之間唯一的差異是環境變數。** 同一棵樹、同一個 HEAD、同一份 `tests/test_fidelity_gate.py`。

### C — 負控制組：證明 runner 對「真的不存在」也會非零，所以 A 的 rc=1 沒有判別力

```
$ PYTHONPATH="$PP" python3 -m unittest tests.test_NON_EXISTENT_MODULE_CONTROL
E
======================================================================
ERROR: test_NON_EXISTENT_MODULE_CONTROL (unittest.loader._FailedTest.test_NON_EXISTENT_MODULE_CONTROL)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_NON_EXISTENT_MODULE_CONTROL
Traceback (most recent call last):
  File "/usr/lib/python3.12/unittest/loader.py", line 137, in loadTestsFromName
    module = __import__(module_name)
             ^^^^^^^^^^^^^^^^^^^^^^^
ModuleNotFoundError: No module named 'tests.test_NON_EXISTENT_MODULE_CONTROL'


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)

rc=1
```

### 三格並排（這才是本張的核心）

| variant | 摘要行 | rc | 真實情況 |
| --- | --- | --- | --- |
| A 無 PYTHONPATH | `Ran 1 test in 0.000s` / `FAILED (errors=1)` | 1 | 測試**完全沒跑**，env 缺口 |
| C 模組不存在 | `Ran 1 test in 0.000s` / `FAILED (errors=1)` | 1 | 目標**根本不存在** |
| B 帶 PYTHONPATH | `Ran 5 tests in 0.664s` / `OK` | 0 | 5 個 case 真的跑完 |

**A 與 C 的摘要行與 rc 逐字相同。** 而若 `test_fidelity_gate` 內真有一個 case 壞掉，
輸出會是 `Ran 5 tests` / `FAILED (failures=1)` / rc=1 —— **也是 rc=1**。
於是 rc 這一格同時承載三種互斥情境：env 缺口 / 目標不存在 / 真的回歸。

唯一能分開它們的是 traceback 內容與 `Ran N tests` 的 N，而**沒有任何東西提示讀者要去看那裡**。

---

## 機制：為什麼這是 G13-harness-disclosure，不是「使用者沒讀文件」

系統當下**握有**這格資訊，只是不說：

1. **`unittest` 知道差別。** `_FailedTest` 是 loader 專用的合成 case，內部與「真的跑了一個 case 然後 error」
   是不同路徑。它有能力在摘要標註「0 個模組載入成功 / 1 個收集期失敗」，但它選擇塞進同一個
   `Ran N tests` 計數，讓 collection error 長得像 test error。
2. **`ModuleNotFoundError` 知道差別。** 缺的是第三方套件、是 repo 自己的 package、還是測試模組本身，
   Python 完全分得出來（前者名字在 `packages/*/` 底下就有），但錯誤訊息一律同一句。
3. **repo 知道正確答案。** `packages/*/` 的佈局是既成事實，`AGENTS.md §5` 甚至寫下了確切的一行配方。
   缺的不是知識，是**把知識放進工具鏈會自動讀到的位置**。任何一個 `conftest.py` /
   `[tool.pytest.ini_options] pythonpath` 都會讓 A 這一格消失。

> **缺的不是資訊，是揭露。** 這與 `AGENTS.md §6.1`（`reset --hard` 的 exit 0）、
> `§6.2`（`pkill -f` 的空輸出）、`§6.3`（stale pyc 的正常執行結果）同族：
> **成功態與危險態共用同一個輸出**。

### 為什麼「已經寫在 AGENTS.md 了」不構成已修

- AGENTS.md 是**給讀過它的 agent 看的**。cold-context 的人、外部貢獻者、CI 上的一行
  `python3 -m unittest discover` 都不經過它。
- 它是**口耳相傳的機械化版本**，不是機制。判準：**「若沒有人記得這條，什麼會失敗、有多大聲？」**
  答案是「安靜地給出一個看起來像回歸的紅燈」——正是 `code-thinker §7` 禁止的那一格。

---

## 修法選項（**列出，不裁示**；決策權在 dispatcher）

| # | 手段 | 覆蓋範圍 | 代價 / 疑慮 |
| --- | --- | --- | --- |
| 1 | repo root 放 `conftest.py`，在其中把 `packages/*/` 插進 `sys.path` | pytest **與** `python3 -m unittest`（後者不讀 conftest，**只有 pytest 生效**——需先驗證） | 最小侵入；但對 `unittest` 路徑無效，需實測確認 |
| 2 | `pyproject.toml` 加 `[tool.pytest.ini_options] pythonpath = ["packages/..."]` | 僅 pytest | repo 目前無 `pyproject.toml`，新增會影響 build/packaging 認知；需確認不與 Docker build 衝突 |
| 3 | `tests/__init__.py` 內做 `sys.path` bootstrap | pytest **與** unittest 都吃得到（`tests` 被 import 時即執行） | 最通用；但把 env 設定藏進 package init，對「顯式優於隱式」是取捨 |
| 4 | `Makefile` / `scripts/run_tests.sh` target | 只有走該入口的人 | 顯式、可 self-test；但**不擋直覺跑法**，A 這一格仍存在 |
| 5 | 純文件化：`AGENTS.md` 已有，再加 `tests/README.md` | 只有讀的人 | **現狀即此**，本張正是它失效的證據 |
| 6 | 組合：3（機制）+ 4（顯式入口）+ 5（文件） | 全部 | 需一次裁定三處 |

**未裁示的關鍵未知**：選項 1 對 `python3 -m unittest` 是否生效（conftest 是 pytest 專屬機制），
以及本 repo 的容器化測試路徑（`mcpctl.sh` / `Dockerfile.*`）是否已用別的方式解決同一格
——這兩點本輪**未量**，見下。

---

## 量了什麼

- A / B / C 三個 variant 的**完整原文輸出與 rc**，於同一輪、同一棵樹、清過 `__pycache__` 之後連續執行。
- `PP` 展開後的實際值（11 個 package 目錄）。
- 負控制組 C 證明：`unittest` runner 對不存在的模組**確實會非零**，所以 A 的 rc=1
  **不能**用來區分「env 缺口」與「真的失敗」——這一格是本張成立的必要條件，不是裝飾。
- repo root 確認無 `conftest.py` / `pyproject.toml` / `pytest.ini`（透過 §Boundaries 允許的唯讀掃描）。

## 沒量什麼（誠實邊界）

- **只量了 `tests.test_fidelity_gate` 一個模組。** 未做全 suite 掃描，因此「有多少個測試模組
  受同一條 `PYTHONPATH` 約束」是未知數（合理推測是全部 import `bodesign_*` 的那些，但**未實測**）。
- **未驗證任何一個修法選項會不會有效。** 選項 1 對 unittest 是否生效、選項 2 是否與現有
  Docker build 衝突——一格都沒跑。本張是建檔，不是修復。
- **未量容器內路徑。** `mcpctl.sh` 起的容器裡 `PYTHONPATH` 可能已由 `Dockerfile` 設好，
  於是「容器內綠、host 上紅」可能是既存狀態；本輪未進容器驗證。
- **未量 CI。** 不確定本 repo 是否有 CI 跑測試、若有它用什麼呼叫方式。
- **未量 pytest。** 三個 variant 全部走 `python3 -m unittest`；`pytest` 是否有不同行為未測。
- **時間錨**：以上全部為 2026-08-31 的快照。工作樹當時有大量 peer 未提交修改
  （見 `AGENTS.md §6.1`），故 B 的「綠」是**該時刻該工作樹**的綠，不等同於某個 commit 的綠。

---

## 修復紀錄（2026-09-01，BRNS handler `ses_fa68c949effejyOcL1nYr1OwHx`，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`）

**裁決**：選項 **3 + 4 + 5**（機制 + 顯式入口 + 文件）。選項 1（root `conftest.py`）排除，
因為 conftest 是 pytest 專屬而本 repo 全部測試走 `python3 -m unittest`；選項 2 需新增
`pyproject.toml`，會動到 Docker build 認知。

### 落地的三個檔

| 檔 | 角色 | 要點 |
| --- | --- | --- |
| `tests/__init__.py`（新） | **機制層** | `Path(__file__).resolve().parent.parent` 推 repo root（不寫死絕對路徑），把 `packages/*/` 每個目錄放進 `sys.path` **與** `os.environ["PYTHONPATH"]`。`packages/` 不存在或為空時 `RuntimeError` 明講。匯出 `BOOTSTRAPPED_PATHS`（可被斷言），並以 `BODESIGN_TEST_BOOTSTRAP=0` 提供停用開關供反向控制組使用 |
| `scripts/run_tests.sh`（新） | **顯式入口** | 先清 `__pycache__`；顯式列舉模組（不用 `discover`）；`--self-test` / `--list` / `--help`；`tests.` 前綴可省 |
| `AGENTS.md §5` | **文件** | 舊 PYTHONPATH 配方改為指向新入口，並新增一條「判別欄位是 `Ran N tests` 的 N，不是 rc」 |

### 為什麼 `sys.path` 一個人不夠 —— 本輪實測發現的第二格

第一版只設 `sys.path`。全套件跑完，**恰好一個測試 green→red**：

```
FAIL: test_no_pcbnew_import (tests.test_copper_geometry.NoPcbnewTests.test_no_pcbnew_import)
AssertionError: 1 != 0 : copper_geometry pulled pcbnew: ...
ModuleNotFoundError: No module named 'bodesign_gerber_core'
```

`tests/test_copper_geometry.py:143` 用 `subprocess.run([sys.executable, "-c", ...])` 在
**全新 interpreter** 裡斷言 `copper_geometry` 不會 transitively import `pcbnew`（因為父進程的
`sys.modules` 被 sibling 測試污染）。**子進程繼承的是「環境」，不是父進程的 `sys.path`。**
舊配方靠 `PYTHONPATH` env var 的繼承讓它們**碰巧**能跑。

這正是本 BR 講的同一種病，只是換一格：那個失敗訊息把「子進程 env 缺口」報成
「被測不變量被違反」（`copper_geometry pulled pcbnew`），**成因與症狀共用同一個輸出**。
修法是 bootstrap 同時修 `sys.path`（本進程）與 `PYTHONPATH`（子進程）。

### 量測

**三格對照 + 負控制組**（每格先清 `__pycache__`，跑 `tests.test_fidelity_gate`）：

| variant | N (`Ran N tests`) | rc | 判讀 |
| --- | --- | --- | --- |
| (a) 帶 `PYTHONPATH`，bootstrap 在 | **5** | 0 | 現狀作法仍可用 |
| (b) **`env -u PYTHONPATH`**，bootstrap **啟用** | **5** | 0 | ← **本包的答案**：無任何 env 設定即可跑 |
| (c) `env -u PYTHONPATH` + `BODESIGN_TEST_BOOTSTRAP=0` | **1** | 1 | ← **反向控制組**：`ModuleNotFoundError` 復現 |
| neg. 不存在的模組，bootstrap 啟用 | **1** | 1 | runner 對真不存在仍非零 |

**(c) 證明 bootstrap 真的在承重**：若不是它在提供 path，(c) 也會是 N=5。
(c) 用**環境變數開關**停用，不是 mutate-on-disk —— 後者在同秒等長編輯下會讓 stale `.pyc`
存活、mutant 根本沒被套用而測試仍綠（`AGENTS.md §6.3`），得到的是**反向結論**而非少一格證據。

**零回歸（集合比對，非計數比對）**：

```
baseline: PYTHONPATH="$PP" python3 -m unittest <142 模組>
          → Ran 1871 tests, failures=11 errors=40 skipped=51 → 51 筆 RED
after:    env -u PYTHONPATH ./scripts/run_tests.sh
          → Ran 1871 tests, failures=11 errors=40 skipped=51 → 51 筆 RED

comm -13 baseline.red after.red  → 0 筆（green→red 為零）
comm -23 baseline.red after.red  → 0 筆（red→green 為零）
cmp -s   baseline.red after.red  → rc=0（逐字節同一集合，不只是「兩個 51」）
CONTROL: cmp baseline.red <刪掉首行的副本> → rc=1（cmp 有判別力）
```

**`scripts/run_tests.sh --self-test`：9 格控制組全綠**，每格都配對了會紅的那一半——
bootstrap 生效 ↔ 停用即 `ModuleNotFoundError`；腳本對失敗模組非零 ↔ 對通過模組為零；
`BOOTSTRAPPED_PATHS` 非空 ↔ 停用時為空；`list_modules()` 有輸出 ↔ 空 `tests/` 時走 FATAL 分支。

### 沒量什麼

- **未量容器內**（`mcpctl.sh` 起的 container）。`tests/__init__.py` 是 repo 相對計算，理應等效，但未進容器驗證。
- **未量 pytest**。全部量測走 `python3 -m unittest`。機制上 `tests/__init__.py` 對 pytest 同樣生效（import `tests.<mod>` 時執行），但未實跑。
- **未量 CI**。仍不確定本 repo 是否有 CI 跑測試。
- **未動任何生產碼**。`packages/**/*.py` 零變更，`tests/test_*.py` 零變更（只新增 `__init__.py`）。
- **時間錨**：2026-09-01，工作樹仍有大量 peer 未提交修改；51 筆 RED 是**該時刻該工作樹**的基線。

### 第二輪（驗收退回後修正的兩件事）

**一、self-test 第 8 格初版是裝飾。** 它宣稱是第 7 格（`list_modules()` 有輸出）的 reverse
control，實際斷言的是一段**內嵌重寫的 bash**，不是 `list_modules()` 本尊。內嵌副本可以永遠
正確而真函式壞掉，這格照樣綠——由獨立 VANS 指出。改為把真腳本 `cp` 進 scratch 空 repo
skeleton（`REPO_ROOT` 由 `BASH_SOURCE` 推導，副本自然錨在 scratch）跑 `--list`。

敏感度以三格突變證明（均在**副本**上突變，不碰 repo 內檔）：

| 副本 | `--list` rc | 意義 |
| --- | --- | --- |
| pristine（真函式） | **1** + `FATAL` | 被測條件成立時會紅 |
| mutant（`list_modules(){ return 0; }`） | **0** | 翻綠 ⇒ 這格對該函式敏感 |
| 無關函式突變（`normalise_module`） | **1** | 仍紅 ⇒ 不是實作“腳本被動過”的 tamper-detector |

第三格是決定性的：前兩格單獨成立時，“對 `list_modules()` 敏感”與“對任何改動敏感”的數字
**完全一樣**。另補 `populated` 一格（scratch 內放一個 `test_dummy_control.py` → rc=0 且列出它），
證明副本在 scratch 中**有能力成功列舉**，所以 pristine 的紅來自“`tests/` 真的空”而非機制故障。
並新增 8b 格：`rm -rf` 後同時斷言 scratch 不存在 **且** `$XDG_RUNTIME_DIR` 仍在——單看“scratch 沒了”
分不出“刪對了”與“把父目錄一起端了”。

**二、realpath 被考慮並駁回。** `_bootstrap()` 對 `PYTHONPATH` 的去重是**字串**比對，等價但拼寫不同
的路徑（相對 vs 絕對、尾斜線差異）不會合併。實害已量為零：textually_unique=22 /
realpath_unique=11，且 gen0→gen3 巢狀子進程每一代恆為 22（**不累積**），import 解析不受影響。

駁回的理由不只是“成本大於收益”，而是**同構**：realpath 會讓 `PYTHONPATH` 的內容取決於
檔案系統當下的 symlink 狀態，同一份 repo 在 host 與容器裡會產出不同字串。那把一個純字串操作
變成有**外部依賴**的操作——而外部依賴正是本 BR 整張在消滅的東西。**用一個新的外部依賴去修
一個關於外部依賴的 BR，方向是反的。** 此為機制層論證，非量測（symlink 語義差異未實測）。
註解已改寫為過去式量測事實（`code-thinker` §11）。

### 本輪沒量什麼（追加）

- **cell 8 的 mutant 驗證只做了一個突變點**（`list_modules` 整體替換）。未做逐分支突變——例如
  “`mods` 非空但 `printf` 壞掉”這種壞法這格抓不到。它證明的是“對該函式的存亡敏感”，
  不是“對它的每一種壞法敏感”。
- **未量 symlink 語義差異**（realpath 那格是論證，非量測）。
- **未量容器內 / pytest / CI**，同上一輪。
