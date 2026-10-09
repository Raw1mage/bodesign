# BR_20260901g — skill 側 render_prd 獨立寫死 legacy answer_state 路徑，且物理上無法引用生產常數

- **Status**: OPEN — 已量測定位，**未修**（901e 實作時**主動劃出範圍外**，不是漏掉）
**Severity**: medium — 與 901e 同一失效類別（cross-stage-path dual-SSOT），但**修法必須不同**
**Owner**: `readiness-contract` family（`issues/OWNERS.md`）
**Filed by**: `ses_fa658134bffeM1Ve1jIomrfYD9`（BRNS handler，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`）
**Filed**: 2026-09-01

**Related**:
- `issues/BR_20260901e_same_stage_path_has_two_independent_sources_of_truth.md`
  — **同一失效類別：`cross-stage-path dual-SSOT`**（同一條 stage 檔案路徑有兩個以上各自
  獨立宣告的字面來源，`same_object=False`，無任何機制保證一起改）。可引用依據有三：
  1. **同一條路徑字面**：本張的 `C00-PRD/answer_state.json` 就是 901e 的 **P3**
     （`_C00_ANSWER_STATE_REL_LEGACY`）。901e 已把 package 側的三個宣告收斂到
     `orchestration.py:C00_ANSWER_STATE_REL_LEGACY`（單一宣告，`assertIs` 釘住）；
     本張是**同一條路徑在 package 邊界之外的第四個宣告**。
  2. **同一個機制斷點**：901e 的修法是「讀側 import 寫側常數」。本張**用不上**——
     見 §3，`render_prd.py` 在 import 時點還沒有 `bodesign_workflow_core` 可用。
  3. **時序因果**：本張是 901e 實作過程中量測出來的，且**當時就判定不能用同一個修法**，
     於是切出來。901e 的 `Remaining` 會指回本張。

  **為什麼這一格不能用 901e 的修法**：901e 的四對全部落在同一個 python package 內，
  `from .x import Y` 是一行的事（實測四對 import 全部 rc=0，無成環）。本張跨 package
  邊界且 import 是**延遲且有條件的**（§3），所以「引用上游常數」在這裡不是「代價較大」，
  是**在該行執行時點不可能**。硬套會把一個當前正確的檔案改成 import-time crash。

- `issues/BR_20260804_stage_deliverable_names_are_hardcoded_per_module_so_the_C0N_prefix_rule_cannot_be_adopted.md`
  — 同族的上位形狀（stage 交付物名稱寫死在各模組）。本張與 901e 都是它的已量測實例。

---

## 1. 一句話

`skills/bodesign/stages/c00-prd/assets/render_prd.py` 有 **3 處**獨立寫死
`C00-PRD/answer_state.json`（**legacy 位置**），而 package 側的同一條路徑已於 901e
收斂為單一宣告 `orchestration.py:C00_ANSWER_STATE_REL_LEGACY`。skill 側是**第四個宣告**，
且它**寫死的是 legacy 位置，不是 canonical 位置**——所以它與 package 側不只是「可能漂移」，
而是**已經指向不同的檔案**。

## 2. 量測（2026-09-01，可重跑）

```
grep -rn --include=*.py --exclude-dir=.venv --exclude-dir=__pycache__ \
     -F "C00-PRD/answer_state.json" skills/
```

| # | 位置 | 角色 | 字面 |
|---|---|---|---|
| S1 | `render_prd.py:18` | module docstring 的 Usage 說明 | `<project>/C00-PRD/answer_state.json` |
| S2 | `render_prd.py:78` | **`sys.exit()` 的錯誤訊息**（告訴使用者正確 layout 是什麼） | 同上 |
| S3 | `render_prd.py:110` | **產出的 Markdown 內文**（寫進交付物，給讀者看） | `` `C00-PRD/answer_state.json` `` |

**控制組（證明探針有判別力）**：同一支 grep 對 `C99-NEVER/nope.json` → rc=1（零命中）。
所以上面的非空是真訊號。

**與 package 側的位置差異**（901e 收斂後的 HEAD 狀態）：

| 側 | 常數 | 值 |
|---|---|---|
| package canonical | `orchestration.C00_ANSWER_STATE_REL` | `C00-PRD/03_output/answer_state.json` |
| package legacy | `orchestration.C00_ANSWER_STATE_REL_LEGACY` | `C00-PRD/answer_state.json` |
| **skill 側 S1–S3** | **無常數，3 個字面** | `C00-PRD/answer_state.json`（＝legacy） |

⚠ **S3 最貴**：它不是內部路徑，是**寫進使用者拿到的 Markdown 交付物裡的一句話**。
`c00_prd_template.py:600` 的對應句子寫的是 **canonical** 位置
（`C00-PRD/03_output/answer_state.json`）。**同一份文件由兩條 render 路徑產出時，
會告訴使用者兩個不同的來源檔位置，而兩邊都不會報錯。**

## 3. 為什麼不能用 901e 的修法（機制層，非偏好）

`render_prd.py` **不在 module 層 import `bodesign_workflow_core`**：

```
grep -n "^import \|^from " skills/bodesign/stages/c00-prd/assets/render_prd.py
→ 25:import argparse  26:import json  27:import os  28:import sys
```

它是**先解析路徑、再把 `packages/` 塞進 `sys.path`、然後才 import**：

```python
def _canonical_readiness(answer_state_path):
    c00_dir = os.path.dirname(answer_state_path)
    if os.path.basename(c00_dir) != "C00-PRD":
        sys.exit(f"render_prd: canonical readiness requires the "
                 f"<project>/C00-PRD/answer_state.json layout; got {answer_state_path}")   # ← S2
    _prepend_packages(_resolve_src())          # ← sys.path 在這裡才被改
    from bodesign_workflow_core import assess_c00_prd_readiness    # ← 才 import
```

**S2 在 `_prepend_packages` 之前執行。** 那一行如果改成引用
`orchestration.C00_ANSWER_STATE_REL_LEGACY`，就必須在 module 層 import
`bodesign_workflow_core`——而 module 層 import 正是這個檔刻意避開的（它的 docstring 說明
路徑解析失敗要 fail fast 且**不得退回簡化的本地計算**，所以 import 被推遲到路徑確定之後）。

S1 是 docstring、S3 是輸出字串，兩者技術上可在 import 之後求值，但把三處拆成
「兩處引用常數、一處寫死」會製造比現況更難讀的狀態。

## 4. Fix surface（**本輪不修**）

| # | 位置 | 方向候選 |
|---|---|---|
| S1 | `render_prd.py:18` | 三處收斂為該檔頂部的**一個** module 常數（skill 側自有 SSOT），並加註解指向 package 側的 owner |
| S2 | `render_prd.py:78` | 同上（不可 import 生產常數，理由見 §3） |
| S3 | `render_prd.py:110` | 同上；**額外**需裁決它該印 canonical 還是 legacy——見 §5 |

**候選方向 A（skill 側自有單一常數）**：三處收斂成一個，drift 面從 3 降到 1。
**防不住**跨 package 邊界的漂移（package 側改了、skill 側不會知道）。

**候選方向 B（延遲引用）**：把 S1/S3 改成在 import 之後才求值並引用生產常數，S2 維持字面。
**代價**：三處變成兩種機制，且 S2 仍是獨立來源——**drift 面只從 3 降到 2，卻多一種機制**。

**候選方向 C（跨邊界不變量測試）**：測試 import `orchestration` 並斷言 skill 側常數等於
`C00_ANSWER_STATE_REL_LEGACY.as_posix()`。**唯一能防住跨邊界漂移的手段**，因為測試環境
兩邊都 import 得到——`render_prd.py` 的執行時點限制在測試裡不存在。
**A + C 是可疊加的**；本張建議兩者一起，但**留給 owner 裁決**。

## 5. 未決問題（不是實作細節，是契約問題）

**S3 到底該印哪一個位置？** `c00_prd_template.py:600` 印 canonical、`render_prd.py:110` 印
legacy。這兩條 render 路徑是**同一份交付物的兩個產生器**還是**兩個不同交付物**，本張未量。
在回答之前，任何「統一成同一個字串」的修法都可能是把一個正確的差異抹掉。

⚠ **這一格必須先回答再動手。** 若兩條路徑服務不同的 layout（audience-split 契約，
`stage-structure.md` 2026-07-17），那 S3 印 legacy 是**正確的**，本張就只剩 S1/S2 的
「同一檔內三個字面」問題，severity 應降。

## 6. 誠實邊界（沒量什麼）

- **沒量 `render_prd.py` 的實際呼叫端**：誰在什麼 layout 下呼叫它、傳進來的是 canonical
  還是 legacy 路徑，未追。§5 的未決問題就是這一格的直接後果。
- **沒量 skills/ 下其他 stage 是否有同樣形狀**。本次窗口只針對這一條路徑字面
  （`C00-PRD/answer_state.json`），不是對 skills/ 全樹做 stage-path 掃描。
- **沒量非 `.py` 檔**（`.md` / `GUIDE.md` / template）中的同路徑字面。
- **沒跑任何測試驗證 render_prd 現況行為**——本張只做靜態量測，未執行該腳本。
