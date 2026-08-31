# BR_20260901e — 同一條 stage 路徑有兩個獨立的真相來源（跨模組寫死字面）

- **Status**: OPEN — 已量測定位，**未修**（由 dispatcher 排入 backlog）
**Severity**: medium — 不是當下的錯誤行為，是**兩個獨立字面各自漂移的空間**
**Owner**: `readiness-contract` family（`issues/OWNERS.md`）
**Filed by**: `ses_fa6ece187ffe2jyvANSTFBQStk`（BRNS handler，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`）
**Filed**: 2026-09-01
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

- **只掃了 `packages/`**。`services/` 與 `skills/` 下是否有第五對未量。
- **只比對了 `Path("C0N-...")` 形式的字面**。以字串拼接（`f"{folder}/..."`）或
  從 JSON 讀取的路徑不在本次窗口內。
- **未量 import 環**：F1 的 `c04 → c01` import 是否成環未驗（§4 已標為前置）。
- **未量測試側**：`tests/` 下是否也各自寫死這些路徑（若有，修法時同樣要一起收斂）。
