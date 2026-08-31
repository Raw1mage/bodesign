# BR_20260831a — 這個 repo 沒有 test bootstrap：測試綠燈依賴一條口耳相傳的 `PYTHONPATH`，而漏掉它的紅燈與「真的回歸了」共用同一個輸出

- **Status**: OPEN — 已實測定位並附雙控制組；修法未落地（本張只建檔，不做實作）
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
