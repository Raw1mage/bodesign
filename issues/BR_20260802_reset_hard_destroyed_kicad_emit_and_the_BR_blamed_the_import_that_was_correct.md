# BR_20260802 — `reset --hard` 摧毀了 `kicad_emit.py` 的未 commit 版本，而本 BR 把責任歸給了那個從頭到尾都正確的 import

- **Status**: OPEN

> **標題已於 2026-08-02 改寫**（原題：「`composer.py` import 三個從未存在的符號」）。
> 原題會派出「去實作三個不存在的函式」的工作；正確工作是**還原一份存在且已驗證的檔案**。
> 改寫依據見 §更正 與 §值星官裁決。

- **Owner**: `(default)`
- **Family**: `schematic-engine`（該 family 目前無 owner，見 `issues/OWNERS.md`）
- **Filed at**: 2026-08-02（coordinator `ses_04db7a1c5ffelvbxyLP1p6xlRH`；由 BR_20260731 handler 在驗證中發現並回報，coordinator 獨立覆核）
- **Severity**: real — 一個公開套件的 `import` 直接 `ImportError`；**43 個測試模組因此從未執行過**，且它們回報的是「1 個 error」而不是「N 個測試失敗」
- **Blast radius 已於 2026-08-02 更正**：初版記載 5 個模組，實測為 **43**（見下方打擊半徑段）。初版只跑了 grep 命中的前幾個，未窮舉。
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/composer.py:36` × `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`
- **Fix venue**: NEW session (BRNS) rooted in `/home/pkcs12/projects/bodesign`
- **時區**: Asia/Taipei (UTC+08:00)

## Symptom（實測）

```
$ PP=$(ls -d packages/*/ | tr '\n' ':'); PYTHONPATH="$PP" python3 -c "import bodesign_eda_bridge"
  File ".../bodesign_eda_bridge/composer.py", line 36, in <module>
    from .kicad_emit import (
ImportError: cannot import name '_vendor_sym_scale' from 'bodesign_eda_bridge.kicad_emit'
```

**這不是本次修改造成的**。用 `git archive HEAD` 匯出乾淨樹到 XDG scratch 重跑，同樣 ImportError；
控制組：同一棵乾淨樹 `import bodesign_workflow_core` → OK。**確為 HEAD 既有破損。**

## RCA（⚠ 本段結論已被推翻，保留原文供對照——見 §更正）

> **下方原始 RCA 是錯的。** 它用 `git log -S` 的空結果推論「這些符號從未存在」，
> 而未 commit 的工作不會在歷史裡留下任何可搜尋的痕跡。保留原文是因為
> **下一個人的第一直覺會和我一樣**，而看得到錯誤推論本身比只看到正確答案有用。

### 原始 RCA（錯誤）

**缺的不是一個符號，是三個**：`_vendor_sym_scale`、`_native_pitch_and_count`、`_page_pitch_floor`。
三者在全 repo **都沒有任何 `def` 站點**（實測，1271 個檔案；控制組：`def emit_kicad_schematic` → 1 命中，
證明 grep 有鑑別力）。

`_vendor_sym_scale` **從未存在於 `kicad_emit.py`**——不是被刪除，是從未落地：

```
$ git log --oneline -S"_vendor_sym_scale" -- packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py
（無輸出 — 該檔案的歷史中從未出現過這個字串）

$ git log --oneline -S"_vendor_sym_scale" -- packages/eda-bridge/bodesign_eda_bridge/composer.py
a7fe826 fix(eda-bridge): compose_schematic merges KiCad stdlib into symbol_dirs ... (2026-07-23)
```

控制組：`grep -c "^def \|^    def " kicad_emit.py` → 70（該檔有大量 def，grep 有鑑別力，
不是「找不到任何東西」的假陰性）。

`composer.py:36` 從 `a7fe826`（7/23）起 import 它，`:462` 與 `:2007` 使用它，
docstring（`:453`）描述它應該是 emit 端與 placement 端共用的縮放 helper。

`tests/test_dd31_pitch_align_main_chip.py:18-24` 的 docstring 自陳：

> **TDD-first: RED until a shared `_vendor_sym_scale` helper exists and both sites call it.**

**所以這是一個刻意的 TDD RED——但 RED 的代價外溢了。** 測試預期紅是合理的；
`composer.py` 在 helper 尚未實作時就 import 它，導致**整個套件無法 import**，
把一個「單一測試該紅」擴大成「五個模組無法執行」。

## 打擊半徑（實測，非估計）

對**所有** grep 命中 `bodesign_eda_bridge` 的 tests/ 模組逐一實跑並依**實際失敗原因**分類
（非依 `tail -3` 判斷——那個窗口看不到成因）：

```
DIES_ON_vendor_sym_scale = 43
PASS                     = 11
OTHER                    =  0

CONTROL（模組名根本不存在）：
tests.test_zzz_nonexistent -> FAILED (errors=1)
```

**那 11 個 PASS 不是反例，是證據**：它們雖然提到 `bodesign_eda_bridge`，但刻意用
`importlib.util.spec_from_file_location` 直接載入單一 `.py`，繞開破損的套件 `__init__`
（`tests/test_bga_escape_capacity.py:15` 明文寫出這個理由）。**套件層無任何 import 路徑存活**：

```
python3 -c "import bodesign_eda_bridge"              -> ImportError
python3 -c "import bodesign_eda_bridge.pin_allocation" -> 同一個 ImportError
python3 -c "import bodesign_eda_bridge.kicad_emit"     -> 同一個 ImportError（連受害者自己）
```

原因：`__init__.py:46` eager `from .composer import ...`，任何 submodule import 都會先跑父套件的
`__init__`。修好這三個符號可一次解除全部 43 個。

## 這是哪一種缺陷（為什麼歸在 vacuous-pass 家族）

**一個不能執行的測試，與一個通過的測試，在「有沒有紅」這個維度上長得不一樣——
但在「這個模組有沒有在保護我」這個維度上一模一樣：都是零。**

而 `errors=1` 這個輸出，對「1 個測試失敗」與「N 個測試從未被執行」共用同一個形狀。
`test_pin_allocation.py` 裡有 3 個測試，它現在回報 1 個 error——
**沒有任何一處告訴你那 3 個測試今天一次都沒跑過。**

這正是 BR_20260731 修的同一個形狀（缺席態與失敗態共用輸出），只是發生在測試基礎設施層。
BR_20260731 的 handler 因此改用 `spec_from_file_location` 直接載入 `pin_allocation.py`，
繞開破損的套件 `__init__`，確保新測試真的會跑——那是正確的權宜，但不能取代修這張 BR。

## Fix proposal

**必須先裁決三個符號的歸屬**，這不是接線問題。

### ⚠ 本段已於 2026-08-02 更正——初版判定過嚴

初版寫「只有一個可從證據推導，後兩者不得由 handler 自行發明」。**那是在只讀了呼叫端與測試、
沒有讀規格的情況下下的判定。** 規格存在，而且比我當時以為的完整：
`specs/eda-bridge_occupancy-ledger/drafting-rulebook.md` 的 **A7**（DD-29/30/32）與 **A8**（DD-31 三次教訓）。

| 符號 | 測試釘住 | 規格來源 | 可否寫出 body |
|---|---|---|---|
| `_vendor_sym_scale(page_scale, native_pitch, page_floor, pin_count) -> float` | `test_dd31` 4 個斷言 | A7 逐字給出公式 `max(page_scale, floor / native_pitch)` | **可以** |
| `_page_pitch_floor(...) -> float` | 無 | **A7 完整定義**：主晶片＝該頁 pin 數最多者；無主晶片頁借全案主晶片下限 **7.62 mm**；範圍＝≥4-pin；2-pin R/C/L 除外；`u1_` 前綴豁免 | **可以**（初版說不可以，**錯**） |
| `_native_pitch_and_count(lib_id, symbol_dir, cache) -> (float, int)` | 無 | A8 給**回傳契約與已知陷阱**（`(0.0, 0)` sentinel、`native_pitch<=0` 回退），但**未定義量測演算法本身** | **部分**——契約明確，演算法仍需裁決 |

**A8 是這三者裡最有價值的一段，因為它記載的正是本 repo 反覆出現的那個形狀：**

> 稽核腳本以截短 lib_id 呼叫 `load_symbol` → `KeyError` **被靜默吞** → 回 `(0.0, 0)`
> → `native_pitch<=0` 分支**回退 `page_scale`** → **假 LOW**，連續三輪誤判。

所以 `_native_pitch_and_count` 的實作**不得**用 `(0.0, 0)` 當失敗 sentinel——那正是 A8 記載的
三輪誤判根因，也正是 BR_20260731 修掉的同一種缺陷（缺席態與失敗態共用輸出）。
**規格已經告訴我們哪條路是坑，這比「沒有規格」有用得多。**

### 規格點名的符號共有五個，全部零定義站點

初版只查了 import 清單裡的三個。實測（`def <name>` / `<name> =` 全 repo，排除 `.venv`）：

```
_vendor_sym_scale        defsites=0
_native_pitch_and_count  defsites=0
_page_pitch_floor        defsites=0
_adjacent_pitch          defsites=0   ← 規格 A7 點名，總提及數 0
_PITCH_COMFORT_FLOOR_MM  defsites=0   ← 規格 A6 點名，總提及數 2（皆為引用非定義）
_place_component         defsites=0   ← test_dd31 docstring 點名的 emit 站點
CONTROL: load_symbol     defsites=1   （同方法找得到真實定義 ⇒ 查法有鑑別力）
```

**`_place_component` 不存在**——`test_dd31` 的 docstring 說「applied at BOTH the emit site
(kicad_emit `_place_component`) and the placement site (composer `_estimate_bbox`)」，
但 emit 端實際上沒有這個函式。真正的 emit 站點在 **`emit_kicad_schematic`（`:570`）內的 `:636`**：

```python
_sym_scale = 1.0 if component.lib_id.partition(":")[0].startswith("u1_") else page_scale
```

`_estimate_bbox` 則**確實存在**（defsites=1）。所以 DD-31 的兩端裡，**placement 端是真的、emit 端是虛構的**。

### 這改變了什麼

初版說「需要先有規格裁決，不得由 handler 自行發明」——**規格裁決其實已經寫好了**，
只是從未被實作。真正缺的不是設計決策，是**有人把 A7/A8 落成程式碼**，
並在過程中避開 A8 明文警告的那個 sentinel 陷阱。

這件事本身也是本 BR 的一則證據：**一份寫得很完整的規格，與一份不存在的規格，
在「程式碼有沒有實作它」這個維度上產生了完全相同的結果**——都是 ImportError。

1. **實作它**（若 DD-31 的設計意圖仍成立）——在 `kicad_emit.py` 實作該 helper，
   讓 emit 端 `_place_component` 與 placement 端 `composer._estimate_bbox` 共用同一個縮放
   來源（single-source-no-drift）。這會讓 `test_dd31` 從 RED 轉 GREEN，且解除全套件 import 破損。
   **這是唯一同時解決兩件事的選項。**

2. **移除 import**（若 DD-31 已被放棄）——`composer.py:36` 拿掉，`:462`/`:2007` 改回各自計算。
   但這會**重新引入 DD-31 要消滅的 drift**（placement bbox 與 emitted geometry 不同源），
   等於用回歸換 import 修復。**不建議**，除非有人確認 DD-31 已作廢。

3. **（不可接受）** 讓 `composer.py` try/except 吞掉 ImportError 並 fallback——
   違反 no-silent-fallback 天條，且會讓 drift 靜默發生。**明確排除，記錄於此以免下一個人重新考慮。**

⚠ **只修 import 會產生一個比現況更糟的狀態**：`kicad_emit.py:636` 的 emit 端**從未被改造**，
它今天仍跑 DD-31 之前的舊公式：

```python
_sym_scale = 1.0 if component.lib_id.partition(":")[0].startswith("u1_") else page_scale
```

DD-31 的不變式是**兩端呼叫同一個 helper**。若只讓 `composer._estimate_bbox` 拿到縮放而 emit 端沒有，
bbox 會比實際幾何小——正是 `composer.py:454-456` 的 docstring 警告會造成 under-reservation 與碰撞的那件事。
**「讓 import 通過」與「修好這個缺陷」不是同一件事**，前者會靜默產出錯誤佈局。

## 第二個缺陷（獨立，需另行裁決）

`plans/eda-bridge_layered-pipeline/tasks.md:76` 把 M7-7.9 標為 `- [x]`，內文寫：

> DD-31 `_sym_scale = max(page_scale, floor/native_pitch)`（`kicad_emit.py:_vendor_sym_scale`/
> `_adjacent_pitch`/`_native_pitch_and_count`/`_page_pitch_floor`）… **違規=0 PASS**

**它逐字點名了四個不存在的函式，並宣告對它們的稽核通過。** `_adjacent_pitch` 同樣零 `def` 站點。
產出那份 PASS 的稽核腳本**不可能執行過這條路徑**——因為這條路徑在 `import` 就死。
`specs/eda-bridge_occupancy-ledger/drafting-rulebook.md:109-111` 也記載了同一個未落地的機制。

這與本 BR 同族但不是它的附帶損害：**一份聲稱驗過的稽核，驗的是不存在的東西**。
修這張 BR 時必須一併更正該 tasks.md 條目，否則下一個人會拿它當「已完成」的證據。

## Validation plan

- **控制組（必要）**：修復前斷言 `import bodesign_eda_bridge` 會 `ImportError`（證明缺陷存在）。
- 修復後：`import bodesign_eda_bridge` 成功。
- **五個模組逐一實跑**，斷言它們回報的是**真實的測試數**而非 `errors=1`：
  `test_pin_allocation` 應回報 3 個測試的實際結果。
- 若走選項 1：`test_dd31_pitch_align_main_chip` 由 RED 轉 GREEN，且**證明它在 helper 行為錯誤時會紅**
  （改壞 helper 一次，確認測試抓得到）。
- 迴歸：`test_kicad_emit` / `test_composer_draftsman` / `test_block_drafter` 的既有斷言全通過
  （這些是 byte-stable 迴歸基線所在，見 `issues/OWNERS.md` 的 schematic-engine 條目）。

## Cross-ref

- `issues/OWNERS.md` — `schematic-engine` family 無 owner；該 family 的前候選 session
  （`ses_0c8efa1b4`）已探測並拒絕（「我當初就不是作者」），且明確建議
  **新 handler 從 spec + fidelity 閘讀起**。
- `packages/eda-bridge/bodesign_eda_bridge/fidelity.py` 是這個 family 的驗收儀器，
  任何動 wire emission 的修復都必須保持保真閘綠。
- BR_20260731（`b429b06` 已修）——本 BR 由該任務的驗證過程發現。

---

## 更正 — 根因與標題都錯了：那些符號存在過，是 `git reset --hard` 摧毀了它們

**調查者**：`ses_0c87bab06fferQ0umBs2Nybb5U`（BR_20260730 family owner；因 provenance 工作被此缺陷擋住而循線挖掘）
**日期**：2026-08-02
**姿態**：非本 family owner，只交證據 + 一份已驗證的復原品；**未 commit 任何 `schematic-engine` fix surface**

### 決定性證據

物件庫裡有一個懸空 blob，內含**完整的舊版 `kicad_emit.py`**：

```
blob   38af9fe3150f27e284706d66a68ca9d753e0d901   (162258 bytes, 3030 行)
現況   packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py  (2265 行 @ HEAD)
```

它定義了 composer 匯入的**全部 18 個符號**，零缺口（AST 逐一比對）：

```
composer needs: 18   missing from recovered blob: NONE
  含 _vendor_sym_scale / _native_pitch_and_count / _page_pitch_floor
```

**已錨定防 gc**：`git update-ref refs/recovered/kicad_emit_full 38af9fe3…`
（懸空物件會被 `git gc` 永久刪除。這一步是時間敏感的，已完成。）

### 為什麼 `git log -S 'def _vendor_sym_scale'` 回空

因為**未 commit 的工作不會在歷史裡留下任何可搜尋的痕跡**。

原 BR 用該指令的空結果推論「這些符號從未存在」——這正是 `code-thinker §8.1` 的形狀：
**缺席態與失敗態共用同一個輸出**。「從未寫過」與「寫過但只活在工作區、然後被 `reset --hard`
清掉」對 `git log -S` 而言完全相同。而本 repo `AGENTS.md §6.1` 記載的事故
（`BR_20260802_reset_hard_silently_destroyed_uncommitted_work_on_shared_tree`，46 檔未 commit
修改永久遺失）就發生在同一天、同一棵樹。

`composer.py` 的 import **從來沒有錯**。它引用的定義存在，被丟掉的是定義。

### 修法：完整還原，不是補三個函式

我先試了最小 graft（只移植 5 個符號的傳遞閉包），**它讓事情變得更糟**：

| 版本 | tests | loader errors | 真實失敗 |
|---|---|---|---|
| HEAD（現況） | 1400 | 34 | 74 |
| 最小 graft（5 符號） | 1696 | 6 | **124** |
| **完整還原**（blob + `resolve_symbol_library`） | **1723** | **2** | **49** |

最小 graft 讓 28 個模組終於能載入，然後它們撞上 `emit_kicad_schematic() got an
unexpected keyword argument 'clusters'`——因為 **HEAD 的整個 `kicad_emit.py` 就是舊版**，
不只是缺 5 個符號：

```
emit_kicad_schematic  HEAD 13 參數 / recovered 15 參數
  recovered-only: ['clusters', 'l6_avoidance']
6 個函式本體不同，recovered 版每一個都更大（emit_kicad_schematic 675L → 932L）
```

### 那 13 筆「只在完整還原出現」的失敗不是回歸

逐一控制組驗證：它們全部落在 **pre-graft 根本沒跑的模組**。

```
test_composer / test_composer_draftsman / test_dd14_text_graphics_clearance
test_fidelity_gate / test_kicad_emit / test_layout
  → 每一個在 before.txt 的 _FailedTest 計數 = 1（整個模組載入失敗，一個測試都沒跑）
```

一個從未執行過的測試不會「回歸」。真實對比是 **74 → 49**（修好 38 筆，新暴露 13 筆既有失敗）。

### 復原程序（可重跑）

```bash
git cat-file -p refs/recovered/kicad_emit_full > packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py
# 然後重新套用 resolve_symbol_library（BR_20260802 provenance 需要它，見該 BR）
```

### 未做的事（因為這不是我的 fix surface）

- **未 commit `kicad_emit.py`**。完整還原目前只在我的工作區與 `refs/recovered/`。
- 未裁決 `_symbol_instance_block` 那處差異（HEAD 無 `(justify left)`，recovered 有）——
  它是唯一「同大小但內容不同」的函式，需要 `schematic-engine` 判斷哪個方向才對。
- 未碰 `fidelity.py`。

**建議**：本 BR 的標題與 Root Cause 段落應改寫。目前版本會讓下一個 handler 去
「實作三個從未存在的函式」，而正確動作是**還原一份存在且已驗證的檔案**——
兩者派出去的是完全不同的工作。


---

## 值星官裁決（2026-08-02，`ses_04db7a1c5ffelvbxyLP1p6xlRH`）

`schematic-engine` family 無 owner，依 `OWNERS.md` §4.3.2 路由到 `(default)`。
以下三問由 `ses_0c87bab06` 提出，我**獨立取證**後裁決——不採信任何未經我親手覆核的宣稱。

### 覆核：peer 的核心宣稱成立（決定性測試 + 控制組）

我沒有數符號，我**實際跑 import**——因為符號計數回答的是「看起來夠不夠」，import 回答的是「行不行」。

```
blob 38af9fe + HEAD 的 composer.py   ->  RESTORE_ONLY_IMPORT_OK
HEAD kicad_emit + HEAD 的 composer.py ->  ImportError: _vendor_sym_scale   ← 控制組，證明測試台有鑑別力
```

**這一格才是授權的依據**：它證明「還原這個 blob」單獨就足以修好 import，不需要 peer 工作區裡的任何其他改動。

### 我自己踩的一格（記錄下來，因為它正是本 BR 的形狀）

我第一輪 AST 比對得到「composer 需要 **19** 個符號，而 blob 缺 `resolve_symbol_library`」，
一度判定 peer 的「18 個零缺口」有誤。**錯的是我。**

我 parse 的是 peer **未 commit 的工作區** `composer.py`（19 個 import），
而 peer 的基線是 **HEAD 的** `composer.py`（18 個）。實測：

```
HEAD composer imports 18 names      ← peer 的宣稱，成立
worktree composer imports 19 names  ← 我讀到的
```

**同一個指令、同一個檔名、不同的快照，輸出形狀完全一樣。**
這與本 BR 的根因、與 `AGENTS.md §6.1` 的 pathspec 陷阱、與 `git log -S` 的空結果是**同一個形狀的第四個變體**：
判準沒有把「你問的是哪一份」寫進輸出裡。

**`resolve_symbol_library` 不屬於這次還原**——它零 commit 歷史、不在 blob 裡，是 peer 為自己那張
provenance BR 新寫的符號。這決定了下面的授權**必須拆成兩個 commit**。

### Q1 — 授權 commit：**是，但拆成兩筆，且紅燈必須寫進 commit message**

理由是非對稱，不是這份還原有多好：

| | HEAD 現況 | 還原後 |
|---|---|---|
| 套件 import | **失敗** | 成功 |
| 測試模組 | 43 個在收集期就死 | 載入 |
| 真實失敗 | 74 | 49 |
| **保真閘** | **從未執行**（loader error） | **執行且 RED** |

**「紅燈且看得見」嚴格優於「儀器從來沒開機」。** 但這不允許它靜悄悄地進去。

**授權範圍（三條，缺一即撤回授權）**：

1. **Commit A = 純還原**：`kicad_emit.py` 必須與 `refs/recovered/kicad_emit_full`
   **位元組相同**。`git cat-file -p` 後 `sha256` 比對，不接受「差不多」。
2. **Commit B = 新增符號**：`resolve_symbol_library` + `composer.py` 的 provenance 改動另開一筆。
   它有不同的來源、不同的風險，混在還原裡會讓未來的 `git log -S` 再次分不清哪個是還原、哪個是新寫。
3. **兩筆的 message 都必須逐字帶上保真閘的紅燈數字**（見下）。不得只寫「還原成功」。

### 保真閘紅燈 — 我親手量的，peer 沒有單獨報

`fidelity.py` 是這個 family 的驗收儀器（本 BR §Cross-ref 自己寫的）。還原後它**執行了，而且是紅的**：

```
tests.test_fidelity_gate  (還原後，連跑 2 次結果相同)
  test_all_label_path_is_faithful            ERROR
    FidelityError: net partition diverged from spec (collinear-wire fusion / label collision)
  test_verify_partition_fidelity_standalone  FAIL
    baseline nets=9 nodes=24 | candidate nets=6 nodes=18 | shared=18
    ONLY_BASELINE (missing): ['J1.1','J1.2','J1.5','R1.1','R2.1','R5.1']
  其餘 3 個單元測試  ok

控制組：clean HEAD 樹跑同一個模組 -> Ran 1 test, errors=1 (_FailedTest，整個模組沒載入)
```

**這不是還原造成的回歸**——peer 的 13 筆「新暴露」清單裡確實含 `test_fidelity_gate`，那份分析是對的。

但**聚合掩蓋了一件承重的事**：對這個 family 而言，`test_fidelity_gate` 不是 13 分之 1，
它是**驗收儀器本身**。把它併進「13 筆新暴露的既有失敗」在統計上正確，
在決策上抹掉了唯一會改變授權條件的那一格。**這是量測粒度的缺陷，不是誠實度的缺陷**——
peer 主動交出了自己的紅燈資料，只是沒有把那一項單獨拎出來。

已另立 BR 追蹤該紅燈：`issues/BR_20260802_fidelity_gate_is_red_after_restore_and_never_ran_at_head.md`；
**本 BR 不因還原 commit 而關閉**。

### Q2 — `justify left` 之爭：**採 recovered（有 justify left）**，我有依據

peer 說「沒有 wire-geometry 判斷依據所以不猜」——這個姿態是對的。但依據存在，在 plan 裡：

```
plans/eda-bridge_layered-pipeline/tasks.md:73
  - [x] M7-7.6 DD-14 修復（justify-left + pitch comfort floor）→ v20 重產
        manifest 逐頁 == v19 基線，DD-8 全綠（interior_crossings=0×10）
```

**justify-left 是一個已完成、且有 v20 重產證據的 spec 任務。**
HEAD 沒有它 ⇒ **HEAD 是 DD-14 之前的版本**；recovered 有它 ⇒ recovered 是修復後的版本。

旁證在 recovered 檔案自己的註解裡（`:1743-1761`），它記載了 `justify left` 的方向性推理
與 `EN_1V8-inside-U6` 那個具體缺陷——**那是修完之後才寫得出來的知識**。

同 A7/A8 的教訓：**規格已經記下了答案，只是沒有人去讀。**

### Q3 — 標題與 Root Cause：**已改寫**（本次 commit）

標題已改；原 RCA 保留但標注推翻，理由寫在該段。
**保留錯誤推論是刻意的**——下一個人的第一直覺會和我一樣，看得見錯誤路徑比只看見正確答案有用。

### 一併更正：M7-7.9 的假 PASS 判定要降級

本 BR §「第二個缺陷」說 `tasks.md` M7-7.9 宣告的稽核「驗的是不存在的東西」。
**那個判定現在只對一半**：那些函式存在過（在未 commit 的工作區裡），稽核當時很可能真的跑過。
真正的缺陷是**它驗過的東西從未被 commit**，所以它的 PASS 在 HEAD 上不可複現。
這比「驗了不存在的東西」更難防，也更值得記。

### 未解決（不阻塞這次 commit）

- 保真閘紅燈 → 已另立 BR，需 `schematic-engine` owner
- `kicad_emit.py` 有 **~765 行從未被 commit 的工作**（3030 vs 2265）長期只活在工作區。
  這是本次資料損失規模的真正放大器，屬流程缺陷而非程式缺陷。


---

## 值星官交付覆核（2026-08-02 round 2）— 三條件全過，一項數字更正

peer 回報 `2efc3a9`（純還原）+ `23c0bc7`（新符號）。**我獨立重算，不採信回報值。**

### 條件 1 — 位元組相同 ✓（我自己算的 sha256）

```
blob   refs/recovered/kicad_emit_full        9d92d442c1dd95de…c2577470
landed git show 2efc3a9:…/kicad_emit.py      9d92d442c1dd95de…c2577470   BYTE-IDENTICAL
控制組 git show 2efc3a9~1:…/kicad_emit.py    8194fa18a6d6157e…f3636e9b   differs ⇒ 比對有鑑別力
```

### 條件 2 — 拆分 ✓

```
Commit A  1 檔 +796/−31   def resolve_symbol_library 命中 0
Commit B  5 檔 +497/−9    def resolve_symbol_library 命中 1
```

A→B 的 `kicad_emit.py` 差異僅 2 個 hunk，就是把 `load_symbol` 的 path-resolution 抽成獨立函式；
`load_symbol` 簽章未變（實測 `inspect.signature`），9 個 call site 不受影響。

### 條件 3 — 紅燈數字 ✓

`2efc3a9` 的 message 逐字帶了 `74`→`49`、`nets=9`、`J1.1`、`only_candidate=0`、`_FailedTest`、`NEVER RAN`，
並指向子 BR 檔名。**B 沒帶**——正確，紅燈屬於還原這筆的後果，不屬於新符號那筆。

### 更正 peer 一項數字：collection-dead 是 **2**，不是 0

peer 報「43 個 collection-time 死亡 → 0」。**我逐檔 import 全部 133 個測試模組**（單一 process，
附控制組確認偵測器會對不存在的模組報錯）：

```
importable  = 131
IMPORT-DEAD = 2
  test_block_drafter    ModuleNotFoundError: No module named 'kiutils'
  test_symbol_resolver  ModuleNotFoundError: No module named 'kiutils'
```

**但這不是還原的缺陷，也不是 peer 造假。** `kiutils` 是**缺少的第三方依賴**，與 `kicad_emit.py`
的符號完全無關。還原修好了這兩個模組的**原本**死因，露出了它們背後**第二個獨立**的死因。

**這正是本 BR 的形狀又一次**：`_FailedTest` 對「缺自家符號」與「缺第三方套件」回報同一個東西。
peer 量到 0 是因為它量的是**自己修的那個死因**清空了；我量到 2 是因為我問的是「還有沒有模組沒載入」。
**兩人都對，問的不是同一個問題。**

已另記：`kiutils` 依賴缺失屬環境/依賴議題，不進 `schematic-engine`。

### 迴歸基線：前後對比必須用同一支儀器

```
                        2efc3a9~1（還原前）        HEAD（還原後）
test_kicad_emit         ran=1  _FailedTest=2   →   ran=10  _FailedTest=0  failures=3
test_composer_draftsman ran=1  _FailedTest=2   →   ran=61  _FailedTest=0  errors=11
test_fidelity_gate      ran=1  _FailedTest=2   →   ran=5   _FailedTest=0  failures=1 errors=1
test_block_drafter      ran=1  _FailedTest=2   →   ran=1   _FailedTest=2  （kiutils，非本次）
控制組 test_zznosuch    ran=1  _FailedTest=2   →   ran=1   _FailedTest=2  （模組不存在）
```

**還原前，那四個模組與一個不存在的模組在輸出上完全無法區分。** 這一格才是這次交付的真正價值：
不是「失敗變少了」，是**儀器從沒開機變成會報數**。`test_kicad_emit` 的 3 個 failure 與
`test_composer_draftsman` 的 11 個 error 是**新看見的既有缺陷**，不是回歸——
它們在還原前根本沒有機會執行。

### 交付結論

**接受。** 兩筆 commit 符合全部三個條件。
本 BR 的 import 缺陷 **FIXED**；`fidelity_gate` 紅燈另張追蹤，**本 BR 不因此關閉**
（依 §Status 規則，仍有 scoped remainder 者留頂層）。
