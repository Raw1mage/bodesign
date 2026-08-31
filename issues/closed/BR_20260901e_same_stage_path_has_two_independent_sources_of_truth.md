# BR_20260901e — 同一條 stage 路徑有兩個獨立的真相來源（跨模組寫死字面）

- **Status**: **FIXED** — 2026-09-01 收斂完成（§7 修復紀錄）。**六**處獨立宣告收斂為單一
  宣告；修法是「讀側 import 寫側常數」。BR 原本記四對，第五、第六處是實作階段量出來的。
  SSOT 落點：**P1** → `c01_id_package.C01_OUTPUTS["constraints"]`；**P2/P3/P5** →
  `orchestration.py` 的 `C00_ANSWER_STATE_REL` / `C00_ANSWER_STATE_REL_LEGACY`；
  **P4/P6** → `c03_mechanical_constraints.C03_OUTPUT`。
**Severity**: medium — 不是當下的錯誤行為，是**兩個獨立字面各自漂移的空間**
**Owner**: `readiness-contract` family（`issues/OWNERS.md`）
**Filed by**: `ses_fa6ece187ffe2jyvANSTFBQStk`（BRNS handler，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`）
**Filed**: 2026-09-01
**Closed**: 2026-09-01 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`
  — 依據：commit `d5dee04`（九檔：五個生產模組 + 兩支測試 + 本 BR + `BR_20260901g`）
  ⊕ 獨立 VANS 六格全部復現：
  **[A]** 六處 `is=True`，控制組獨立建構的等值 `Path` 回 `is=False ==True`（決定性——
  證明 `assertEqual` 在此無判別力、`assertIs` 才有牙）；
  **[B]** 八模組 + `__init__` 全 rc=0，控制組 `NEVER_EXISTS` rc=1、scratch 造真環 rc=1；
  **[C]** 9 變異全 RED、accepting control 13/13 GREEN、存活 0；
  **[D]** 同環境雙臂 RED 集合 `cmp` rc=0，控制組刪首行 rc=1（限定見 §7.5）；
  **[E]** 六個破口無承重缺陷，E5 復驗「C01/C02 兩筆非重複」；
  **[F]** 三條 Related 邊皆可引用。
  殘留：無未修缺陷。§7.7 Remaining 全為**未掃範圍 / 未判定**，不是本 BR 的未修項。
**Related**:
- `issues/BR_20260804h_c02_outputs_constants_are_dual_role_so_the_one_place_stage_prefix_claim_is_false.md`
  — **同一組常數的不同失效面**，可引用依據：兩者都以 `C01_OUTPUTS["constraints"]`
  （`c01_id_package.py:55`）為交點。804h 講的是**一個常數超載三個角色**；本張講的是
  **同一條路徑有兩個獨立來源**。
  **修法方向相反且必須分開**：804h 的裁決是**保留**單一常數不拆（選項 A 否決，見其 §10.1）；
  本張的方向是**消除**重複來源。把本張併入 804h 會讓一張已判 `FIXED-AS-DOCUMENTED`
  的 BR 帶著未修項。
- `issues/BR_20260804_stage_deliverable_names_are_hardcoded_per_module_so_the_C0N_prefix_rule_cannot_be_adopted.md`
  — 同族的上位形狀（stage 交付物名稱寫死在各模組）。本張是它的一個**已量測實例**：
  不只名稱寫死，而是**同一個名字被寫死了兩次**。

---

## 1. 一句話

`c04_layout_constraints.py:34` 的 `_C01_CONSTRAINTS_REL` 與 `c01_id_package.py:55` 的
`C01_OUTPUTS["constraints"]` **指向同一個檔案，卻是兩個各自獨立的字面常數**。
沒有任何機制保證它們一起改。**同族另有 3 對**（見 §3）。

## 2. 量測（2026-09-01，全部可重跑）

### 2.1 逐字比對（不是「看起來一樣」）

```
PP=$(ls -d packages/*/ | tr '\n' ':')
PYTHONPATH="$PP" python3 -c '...'   # 完整腳本見 §2.3
```

| 對 | A | B | IDENTICAL | same_object |
|---|---|---|---|---|
| **P1** | `c04_layout_constraints.py:34` `_C01_CONSTRAINTS_REL`<br>`'C01-ID/Interface_Constraints.json'` | `c01_id_package.py:55` `C01_OUTPUTS['constraints']`<br>`'C01-ID/Interface_Constraints.json'` | **True** | **False** |
| **P2** | `mode_contracts.py:30` `_C00_ANSWER_STATE_REL`<br>`'C00-PRD/03_output/answer_state.json'` | `c00_orchestration.py:29` `_C00_ANSWER_STATE_REL`<br>同值 | **True** | **False** |
| **P3** | `mode_contracts.py:31` `_C00_ANSWER_STATE_REL_LEGACY`<br>`'C00-PRD/answer_state.json'` | `c00_orchestration.py:30` 同名同值 | **True** | **False** |
| **P4** | `upstream_constraints.py:58` `UPSTREAM_FILES['mechanical'][0]`<br>`'C03-EE/Mechanical_Constraint_Export.json'` | `c03_mechanical_constraints.py:16` `C03_OUTPUT`<br>同值 | **True** | **False** |

**`same_object=False` 是本 BR 的核心證據**：值相同但**不是同一個物件**
⇒ 兩處各自建構，沒有共用引用，**沒有任何東西保證它們一起改**。

**控制組（證明比對器有判別力）**：
```
Path('a').as_posix() == Path('b').as_posix()   -> False
Path('C01-ID/x') == Path('C01-ID/y')           -> False
```
若比對器恆回 True，上表的 4 個 True 就沒有意義。它不恆真。

### 2.2 「現在相同」不等於「有人保證相同」

四對今日**全部逐字相同**，所以**尚未發生 drift**。這是本 BR 目前是 medium 而非 high 的唯一理由。
但 `same_object=False` 意味著：**改其中一邊、另一邊不會有任何訊號**——
沒有 import、沒有斷言、沒有測試把它們綁在一起。

⚠ **「今天相同」這一格會過期，而它過期時不會通知任何人。** 這正是 `BR_20260804h` §3
記錄的同一個形狀在資料層的版本。

### 2.3 同族掃描（母體與控制組）

**掃描窗口**：`packages/` 下全部 `.py`，排除 `.venv` / `__pycache__`。

```
grep -rn --include=*.py --exclude-dir=.venv --exclude-dir=__pycache__ \
     -E 'Path\("C0[0-9]-[A-Za-z]+"\)' packages/
```
→ **72 行命中**，分佈於 13 個模組。

**控制組**：同一支 pattern 對 `Path("C99-NEVER")` → rc=1（零命中）
⇒ 探針會回空，所以上面的 72 非空是真訊號。

在這 72 行中，**跨模組指向同一路徑**的對經逐字比對確認為 **4 對**（P1–P4，見 §2.1）。

**經量測確認「不是」重複來源的（避免誤報）**：

| 候選 | 判定 | 依據 |
|---|---|---|
| `upstream_constraints.py:56` `'C01-ID/Face_Layout.json'` | **非重複** | 不在 `C01_OUTPUTS` 值集合內（`in` 判定 False）⇒ 它不是 C01 emitter 的產物，是 C04 對上游的獨立期望 |
| `upstream_constraints.py:57` `'C02-ME/Envelope_Constraint.json'` | **非重複** | 同上，不在 `C02_OUTPUTS` 內 |
| `c04_layout_constraints.py:30` `C04_FOLDER`、`:35` `_C03_FOLDER` | **非重複** | 是 folder 常數（等價 `C0x_STAGE_DIRNAME` 的角色），不是檔案路徑 |
| `c01_id_package.py` 的 `C01_OUTPUT_CANDIDATES`（`:77`-`:98`） | **非重複** | 同模組內的 read 側候選表，且已由
`tests/test_readiness_folder_contract.py::TV4::test_candidate_paths_match_the_dod_manifest` 綁住 |

**集合成員判定的控制組**：
```
'C01-ID/Interface_Constraints.json' in C01_OUTPUTS 值集  -> True   （必須 True）
'C01-ID/NEVER_EXISTS.json'          in C01_OUTPUTS 值集  -> False  （必須 False）
```
⇒ `in` 判定分得出「有」與「沒有」，上表的 False 不是探針失效。

## 3. 為什麼這比「兩處寫同一個字串」更貴

`C01_OUTPUTS["constraints"]` 是 **emitter 的寫入位置**（角色1，`c01_id_package.py:402`）。
`c04_layout_constraints.py:34` 是 **C04 讀取上游時的期望位置**。

⇒ 這兩個字面是一條**跨 stage 的隱式契約**：C01 寫到哪、C04 就必須讀哪。
改動其中一邊而漏改另一邊，症狀是 **C04 報「上游約束缺失」而 C01 報「已產出」**——
**兩個 verb 各自都是對的，而使用者看到的是矛盾**。

這正是 `BR_20260719` 記錄過的形狀（`dod_ok: true` 而 `readiness_pct: 0`），
只是換到 C01→C04 這條邊上。

P2/P3 更貴一格：**同名同值出現在兩個模組**（`_C00_ANSWER_STATE_REL`），
名字相同會讓讀者以為是同一個東西被 import，實際是各寫一次。

## 4. Fix surface（精確到 file:line，**本輪不修**）

| # | 位置 | 現況 | 方向 |
|---|---|---|---|
| F1 | `packages/workflow-core/bodesign_workflow_core/c04_layout_constraints.py:34` | `_C01_CONSTRAINTS_REL = Path("C01-ID") / "Interface_Constraints.json"` | 改為 `from .c01_id_package import C01_OUTPUTS` 取 `["constraints"]`，或加 drift guard 斷言兩者相等 |
| F2 | `packages/workflow-core/bodesign_workflow_core/mode_contracts.py:30-31` | `_C00_ANSWER_STATE_REL` / `_LEGACY` | 與 `c00_orchestration.py:29-30` 收斂到單一宣告處 |
| F3 | `packages/workflow-core/bodesign_workflow_core/c00_orchestration.py:29-30` | 同上（哪一邊當 SSOT 需裁決） | 同上 |
| F4 | `packages/workflow-core/bodesign_workflow_core/upstream_constraints.py:58` | `UPSTREAM_FILES["mechanical"][0]` | 引用 `c03_mechanical_constraints.C03_OUTPUT` |

**⚠ import 方向要先確認不成環**：`c04_layout_constraints` → `c01_id_package` 這條邊
在動手前必須驗證不會造成循環 import。**這是 F1 的前置量測，不是實作細節。**

**最小版本（不動 import 結構）**：只加 drift guard 測試，斷言四對逐字相等。
它不消除重複，但讓漏改**當場變紅**而不是在下一跳。這與 `BR_20260804h` §10.3(b) 的
`tests/test_stage_prefix_invariant.py` 是同一個手法，可直接擴充該檔。

## 5. 建議驗證（正向 + 反向控制組）

- **正向**：一支 guard 斷言 P1–P4 四對的 `as_posix()` 逐字相等。今日應綠。
- **反向**：測試中臨時把其中一邊換掉（**就地替換命名空間物件，不 mutate 磁碟**——
  理由見 `BR_20260804h` §10.4：磁碟 mutate 會撞上 AGENTS.md §6.3 的 stale-pyc 假陰性），
  guard 必須紅。**沒做過反向的 guard 不算數。**

## 6. 誠實邊界（沒量什麼）

> **本節是立案當時（2026-09-01 上午）的狀態。** §7 記錄哪幾格已在修復階段補上，
> §7.7 列出**至今仍未量**的。兩節請一起讀——單讀本節會把已消解的邊界當成仍然開著。

- **只掃了 `packages/`**。`services/` 與 `skills/` 下是否有第五對未量。
- **只比對了 `Path("C0N-...")` 形式的字面**。以字串拼接（`f"{folder}/..."`）或
  從 JSON 讀取的路徑不在本次窗口內。
- **未量 import 環**：F1 的 `c04 → c01` import 是否成環未驗（§4 已標為前置）。
- **未量測試側**：`tests/` 下是否也各自寫死這些路徑（若有，修法時同樣要一起收斂）。

---

## 7. 修復紀錄（2026-09-01，過去式）

Handler `ses_fa658134bffeM1Ve1jIomrfYD9`，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`，
獨立 VANS 覆核判 PASS（六格 A–F 全部復現）。

### 7.1 立案時記四對，實際是六處

| # | 位置 | 修法 |
|---|---|---|
| P1 | `c04_layout_constraints.py:34` | `_C01_CONSTRAINTS_REL = C01_OUTPUTS["constraints"]`（新增 `from .c01_id_package import C01_OUTPUTS`） |
| P2 | `mode_contracts.py:30` + `c00_orchestration.py:29` | 兩處本地宣告刪除，改 `from .orchestration import C00_ANSWER_STATE_REL as _C00_ANSWER_STATE_REL` |
| P3 | 同上 `_LEGACY` | 同上 |
| P4 | `upstream_constraints.py:58` | `"mechanical": (C03_OUTPUT, "")` |
| **P5** | `orchestration.py:48` `_DEFAULT_ANSWER_STATE` | **立案時未發現**。改為 `C00_ANSWER_STATE_REL.as_posix()`，並把該模組升為這條路徑的唯一 owner |
| **P6** | `c04_layout_constraints.py:187` | **立案時未發現**。gap 訊息改 f-string 引用 `C03_OUTPUT` |

P2/P3/P5 收斂到 `orchestration.py` 而非任一消費端，理由是**方向**：`c00_orchestration.py:25`
當時已經 `from .mode_contracts import enter_c01_mode`，邊已存在。往回接（mode_contracts 取
c00_orchestration）必成環——AST 反向可達性判為 True。`orchestration.py` 是兩個消費端**都已經
import** 的共同祖先，且它本身只 import `agent_registry`，是安全的低層模組。

import 改動全部實跑驗證（清 `__pycache__` 後 `python3 -c 'import ...'`）：八個模組 + 套件
`__init__` 全 rc=0。控制組：`NEVER_EXISTS` rc=1；在 scratch 複本刻意造真環
（`c03` import `c04`）→ rc=1 `partially initialized module ... circular import`，同一份未變異
複本 rc=0。

### 7.2 P5 為什麼被本 BR 自己的掃描漏掉（機制層）

§2.3 的掃描窗口是：

```
grep -rnE 'Path\("C0[0-9]-[A-Za-z]+"\)' packages/
```

而 P5 是**裸字串字面**：

```python
_DEFAULT_ANSWER_STATE = "C00-PRD/03_output/answer_state.json"   # 沒有 Path(
```

**掃描器對它零判別力**——不是它掃了沒中，是它從結構上看不見這一類。這比「漏了一個」更值得
記：**下一次用同形狀 pattern 做同族普查會再漏一次**，而且掃描結果會長得一樣乾淨。

P5 又是六處裡最貴的一處：`orchestration.py:303` 把它塞進 work packet 的
`"answer_state_path"` 欄位——那是**交給下游 agent 的對外契約字串**。前四處漂移只讓本地讀檔
失敗（會炸、看得見）；P5 漂移是**把錯的路徑發給下游**，上游 packet 顯示一切正常。

P6 同族但反向：`c04:176` 用常數、`:187` 寫死同一條路徑。改了常數之後，**程式去找新路徑、
訊息叫使用者看舊路徑**——兩個都不會報錯的錯。

### 7.3 guard 用 `assertIs` 而非 `assertEqual`（§5 的建議在此被推翻並升級）

§5 原本建議「斷言四對的 `as_posix()` 逐字相等」。**那個判準沒有判別力**：六處的值今天逐字
相同，所以等值斷言在**修法前後都會綠**——它釘的是「今天恰好相等」這個事實，不是「只有一個
宣告」這個契約。

VANS 沒有照抄這個推理，做了能證偽的實驗：獨立建構一個 byte-equal 的 `Path`，量得
**`is=False` 而 `==True`**。這一格是決定性的——它證明等值斷言接受「重複字面」這個正是要
禁止的狀態，而 `assertIs` 拒絕它。

所以 `tests/test_cross_stage_path_ssot.py` 的六個正向 guard 一律用 `assertIs`，每個反向
control 先 `assertEqual`（證明控制組真的等值、不是拿不等的東西來湊）再 `assertIsNot`。

### 7.4 變異證明（§5 的反向要求，已履行）

替換全部在**測試命名空間**內（`mock.patch.object` / `dict(...)` 複本），磁碟 `.py` 零 mutate
（理由見 AGENTS.md §6.3：同秒等長編輯會讓 stale `.pyc` 存活、mutant 靜默不被套用，於是得到
**反向結論**）。

- handler 側：8 個變異點（P2/P3 各有兩個消費端，各自獨立變異）全部 RED，存活 0。
- VANS 側：9 個變異點全部 RED。第 9 格是 VANS 自加的，值得記下差別——
  handler 的 8 格證明「guard 對每一對敏感」；**VANS 的 M9 重建 pre-fix 狀態**（訊息改回硬編
  字面 + 常數改名），證明的是「guard 抓得到我們原本要修的那個東西」。兩者不同，都需要。
- **accepting control**：未變異時同樣的 cells 必須全綠（13/13）。沒有這格，一個恆回 failure
  的 runner 也能讓上面每一行看起來合格。

### 7.5 零回歸的量法與它的限定（**這一格請照抄，不要簡化**）

零回歸結論成立於**同環境雙臂**：scratch base `19 failures / 57 errors` vs scratch after
`19 / 57`，RED 集合逐筆 `cmp` rc=0（+13 = 新測試 cells）。

**不是**跨環境對照 handler 在真實工作樹量到的 `11 / 51`。VANS 第一次量到不符時查出成因：
差的 8 筆全是 `SentinelProvenanceTests`——它們要追 sentinel 到 git commit，而 scratch 複本
**排除了 `.git`**。

⚠ **所以正確的說法是「同環境雙臂 RED 集合 cmp rc=0」，不是「對上了基線」。**
在 scratch 複本上跑本 repo 測試的人會撞到同一格：缺 `.git` 讓 8 筆 sentinel 測試變紅，
而那與被測改動無關。

控制組：`cmp` 對刪首行的副本 rc=1（證明 `cmp` 不是恆 0）；抽取器對 `ZZQQ_NEVER` 回 0
（證明抽取器會回空）。

### 7.6 主動劃出「不做」的三處（都經量測，不是省略）

| 不做的 | 依據 |
|---|---|
| `tests/test_c01_id_package.py:72,79` 獨立寫死 `C01-ID/Interface_Constraints.json` | **測試獨立寫死是特性不是缺陷**。測試若 import 生產常數，就變成用被測物驗證自己 |
| `upstream_constraints.py` 的 `face_layout` / `envelope` 兩筆 | 無可衍生來源。VANS E5 復驗：`C01_OUTPUTS` 五個值、`C02_OUTPUTS` 十二個值裡都沒有 `Face_Layout.json` / `Envelope_Constraint.json`；控制組（問 `mechanical` → 命中 `C03_OUTPUT`）證明該搜尋有牙 |
| `skills/bodesign/stages/c00-prd/assets/render_prd.py:18,78,110` | 跨 package 邊界且**物理上無法引用**——`:78` 在 `_prepend_packages()` 改 `sys.path` **之前**執行。另立 `BR_20260901g`（同族，Related 帶三條可引用依據） |

### 7.7 Remaining（**未判定，不是已確認無事**）

- **f-string / 字串拼接 / 從 JSON 讀出的路徑形式未掃**。§6 的這一格未縮小。
- **非 `.py` 檔（`.json` / `.md` / template）的同路徑字面未掃。**
- **`orchestration.py:303` `answer_state_path` 的下游消費端未追。** 「P5 最貴」是基於它是對外
  契約欄位這個結構事實的**推論**，不是量測。修法讓它從 SSOT 衍生、值不變，所以這個推論
  **不承重**——它只影響優先序，不影響修法正確性。
- **`packages/` 內尚有六個檔含 `answer_state.json` basename**（`package_readiness.py`、
  `provenance.py`、`c00_prd_docx.py`、`prd_bom_crosscheck.py`、`c01_id_package.py`、
  `c00_prd_template.py`）。**未逐檔判定是否為第七、第八對。** 它們多為 f-string 片段或
  `03_output` 目錄名的組合，不落在本 BR「完整路徑重複宣告」的窗口內，但**沒有做逐檔證明**。
- **VANS 未做全 repo dual-SSOT 普查**（其自標邊界）。本 BR 收斂的是已量測的六處，
  不宣稱 repo 內不存在第七處。
