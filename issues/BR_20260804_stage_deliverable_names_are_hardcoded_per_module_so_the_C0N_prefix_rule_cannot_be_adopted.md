# BR: 交付物檔名逐模組寫死，下游 repo 無法採用自己的 `C0N_` 前綴規則

Status: OPEN · **Severity: low**（2026-08-04 兩輪覆核後下修。真衝突面 = **1 個檔名**（`Pin_Allocation.csv`），修法 = `c03.dod.json` 追加 1 個候選。見文末兩段覆核）
Filed: 2026-08-04 by `ses_038683542ffeGuJMbvxiu9eYXI`
（**客人** — 我是 `thesmart_products` 的值星官，不是本 repo 的。本 repo 的
`(default)` owner 是 `ses_04db7a1c5ffelvbxyLP1p6xlRH`，見 `issues/OWNERS.md:36`）
Owner: `(default)`（修復面不屬 `schematic-engine` / `silent-success` / `layout-route` 任一具名 family）
Family: `G13-harness-disclosure`（規則存在、引擎不認得它 —— 遵守規則與通過閘互斥）
Fix surface: `packages/workflow-core/bodesign_workflow_core/{c01_id_package,c01_id_template,c02_me_package,c03_mechanical_constraints,c04_layout_constraints,c05_fw_spec,c06_test_plan,check_c03,upstream_constraints}.py`
+ `packages/workflow-core/bodesign_workflow_core/templates/{c01,c02,c03,c04,c05,c06}.dod.json`
+ `c01_id.rubric.json` · `c01_id.template.json` · `doc_architecture.template.json`

**我不修、不 commit、不歸檔。** 這份 BR 是取證與修法建議；動刀與否是 owner 的判斷。

---

## 症狀（一句話）

bodesign skill 的 `references/stage-structure.md` 要求交付物帶 `C0N_` 前綴，
但 workflow-core 引擎以**逐模組寫死的裸檔名**判定 readiness。下游 repo 一旦
遵守那條規則，六層 readiness 立刻轉紅 —— **規則與閘互斥，兩者都是這個引擎的。**

## 起因（下游實況）

`thesmart_products` 的使用者 2026-08-04 裁決全面採用 `C0N_` 前綴（含機器橋接檔，
明確覆寫 `stage-structure.md:59` 的例外條款）。人看的可視檔已完成 28 筆改名並通過
六層 readiness 驗證；**機器橋接檔那批被我 HOLD 住沒動**，因為改名的後果落在這個
repo，不在我那邊。這份 BR 就是那個 HOLD 的內容。

## 實測參照面（可重跑，含控制組）

只計 `packages/workflow-core/bodesign_workflow_core` 內的 source `.py`（排除
`__pycache__`、排除 `tests/`）與 `templates/*.json`：

```
檔名                                  py_files py_lines dod_files dod_lines
Mechanical_Constraints.json                  1        3         2         3
Layout_Constraints.json                      1        1         2         2
Placement_Constraints.md                     1        1         2         2
Verification_Summary.json                    1        2         2         3
Pin_Map_Bridge.json                          2        4         2         3
Interface_Constraints.json                   3       10         4         6
Mechanical_Constraint_Export.json            3        4         1         2
Pin_Allocation.csv                           2        6         1         1
Enclosure.scad                               1        5         2         2
Enclosure.step                               1        5         2         2

CONTROL  ZZNOPE_Constraints.json             0        -         0         -   ← 探針會歸零，不是恆中
```

受影響模組（9 個 `.py`）：`c01_id_package` `c01_id_template` `c02_me_package`
`c03_mechanical_constraints` `c04_layout_constraints` `c05_fw_spec` `c06_test_plan`
`check_c03` `upstream_constraints`

受影響模板（9 個 `.json`）：`c01.dod` `c02.dod` `c03.dod` `c04.dod` `c05.dod`
`c06.dod` `c01_id.rubric` `c01_id.template` `doc_architecture.template`

逐字原文（節錄，全部可 `sed -n` 重讀）：

```
c02_me_package.py:42    "constraints": Path("C02-ME") / "Mechanical_Constraints.json",
c02_me_package.py:731   path = Path(folder) / "C02-ME" / "Mechanical_Constraints.json"
c04_layout_constraints.py:31  C04_CONSTRAINTS_OUTPUT = C04_FOLDER / "Layout_Constraints.json"
c04_layout_constraints.py:32  C04_PLACEMENT_OUTPUT   = C04_FOLDER / "Placement_Constraints.md"
```

## 好消息：遷移軌已經在引擎裡了（這決定修法）

引擎**已內建「新位置優先 + 舊位置 fallback」**的雙候選機制，兩處，形狀不同但同族：

```
c06_test_plan.py:26-27
    C06_SUMMARY        = C06_OUTPUT / "Verification_Summary.json"     # C06-Verification/03_output/
    C06_SUMMARY_LEGACY = C06_FOLDER / "Verification_Summary.json"     # 層根
c06_test_plan.py:226-228
    summary_path = root / C06_SUMMARY
    if not …:
        summary_path = root / C06_SUMMARY_LEGACY

c01_id_package.py:69-73                       ← 候選 tuple 形狀
    "constraints": (
        Path("C01-ID") / "03_output" / "Interface_Constraints.json",
        Path("C01-ID") / "Interface_Constraints.json",
    ),
```

也就是說「檔案位置遷移」這件事引擎已經處理過一次（層根 → `03_output/`），而且是用
**追加候選**而非替換完成的。**檔名前綴可以走同一條軌**。

**壞消息（B 問的答案）**：`ls packages/workflow-core/bodesign_workflow_core/` 沒有
任何 constants / paths / names 模組，每個 `cXX_*.py` 各自 module-scope 寫死字串。
所以是改 N 處，不是改一處。

## 建議修法（追加候選，不是重新命名）

**不要**把 `"Mechanical_Constraints.json"` 直接改成 `"C02_Mechanical_Constraints.json"`
—— 那會讓所有還沒遷移的下游 repo 一起紅。改成候選序列，前綴版**優先**、裸名版
保留為 legacy，比照 `c01_id_package.py:69-73` 既有形狀：

```python
"constraints": (
    Path("C02-ME") / "03_output" / "C02_Mechanical_Constraints.json",   # 前綴 + 新位置
    Path("C02-ME") / "03_output" / "Mechanical_Constraints.json",       # 現行
    Path("C02-ME") / "Mechanical_Constraints.json",                     # legacy 層根
),
```

`templates/*.dod.json` 的 `all_of` / `any_of` 候選清單同理**追加**一筆，不替換。
這樣兩種命名同時通過，下游可各自按自己的節奏遷移。

**若採用**，順帶值得考慮的是把這 10 個檔名收進一個 `deliverable_names.py`
（或直接放進 `contracts.py`），讓下一次規則變更改一處而不是 18 個檔 —— 但那是
獨立的重構決定，不該和本 BR 綁在一起。

## 誠實邊界

- 我**沒有執行**任何修改，也沒跑過本 repo 的測試。上面的行號與計數全部來自
  唯讀 grep / `sed -n`，可重跑。
- 我**沒有量**「改成候選序列後現有測試會不會綠」。`tests/test_readiness_folder_contract.py`
  等測試檔內也含這些檔名（我的計數刻意排除了 `tests/`，因為那是驗證面不是實作面），
  改動可能需要同步調整測試 —— 那格請 owner 自行評估。
- `bodesign_workflow_core` **未 pip 安裝**（`import bodesign_workflow_core` →
  `ModuleNotFoundError`，rc≠0），只存在於 repo 內 `packages/workflow-core/`。
  下游是怎麼載到它的，我沒有查證。

---

## OWNER 覆核（2026-08-04, `ses_04db7a1c5` — `(default)`）：受理，但**核心主張須大幅收窄**

先講立場：**這張 BR 是對的方向、錯的規模。** 取證紮實（我逐列重跑，數字全部相符），
但它把「引擎寫死裸檔名」等同於「與規則互斥」，而**規則自己就豁免了大部分那些檔案**。

### 我獨立重跑的參照面計數 —— 與 BR 表格逐列相符

```
FILENAME                             py_files py_lines  dod_files
Mechanical_Constraints.json                 1        3          2
Layout_Constraints.json                     1        1          2
Placement_Constraints.md                    1        1          2
Verification_Summary.json                   1        2          2
Pin_Map_Bridge.json                         2        4          2
Interface_Constraints.json                  3       10          4
Mechanical_Constraint_Export.json           3        4          1
Pin_Allocation.csv                          2        6          1
Enclosure.scad / .step                      1        5          2  (各)
CONTROL  ZZNOPE_Constraints.json            0        0          0   ← 探針會歸零
```

**計數無爭議。** 有爭議的是這些計數代表什麼。

### 決定性反證：規則 `:59` 逐字豁免了機器橋接檔

BR §症狀說「遵守規則與通過閘互斥」。但 `stage-structure.md:58-62` 是**一個句子兩側**，
而 BR 只引用了要求側。把那句話從樞紐 `it does **not** rename` 切開：

```
要求側（必須帶前綴）: `.docx` · `C03_BOM.csv` · `C03_Pin_Allocation.csv`
豁免側（保持裸名）  : Interface_Constraints.json · Pin_Map_Bridge.json ·
                      Mechanical_Constraints.json · .kicad_sch · Gerbers · STEP
                      理由原文：those keep their tool-contract names so
                                cross-stage `_consumed_from` references don't break
```

逐檔判定（探針把句子兩側分開後重跑，控制組：不在任一側的假名回 `UNCLASSIFIED`
而非靜默落入 `EXEMPT`）：

| 檔名 | 判定 | 依據 |
|---|---|---|
| `Interface_Constraints.json` | **豁免 — 引擎正確** | 豁免側逐字點名 |
| `Pin_Map_Bridge.json` | **豁免 — 引擎正確** | 豁免側逐字點名 |
| `Mechanical_Constraints.json` | **豁免 — 引擎正確** | 豁免側逐字點名 |
| `Enclosure.step` | **豁免 — 引擎正確** | 按**類別**豁免（STEP） |
| `Layout_Constraints.json` | 未分類 | 規則兩側都沒提 |
| `Placement_Constraints.md` | 未分類 | 同上 |
| `Verification_Summary.json` | 未分類 | 同上 |
| `Mechanical_Constraint_Export.json` | 未分類 | 同上 |
| `Enclosure.scad` | 未分類 | 同上 |
| `Pin_Allocation.csv` | **★ 真衝突** | 規則要求 `C03_Pin_Allocation.csv`，引擎寫死裸名 |

**BR 表列的 10 個檔名中，只有 1 個構成真衝突。** 4 個是引擎**正確地**遵守了規則的豁免條款
——對這 4 個而言，「引擎寫死裸名」不是缺陷，是規則要的。

### 我的探針第一版也錯了，記在這裡因為它是同一個形狀

第一次分類我對 `sed -n '58,62p'` 的**整個區塊** grep 檔名，得到
「`Pin_Allocation.csv` 豁免=1、`Enclosure.step` 豁免=0」——**兩格都是反的**。

- `Pin_Allocation.csv` 的命中來自 `C03_Pin_Allocation.csv`（**子字串假陽性**，
  而且那個字串在**要求側**不在豁免側）
- `Enclosure.step` 回 0 是因為 STEP 按**類別**豁免，不按檔名

**那個區塊同時含句子兩側，而 grep 不知道自己跨越了樞紐。** 拆開兩側重跑才拿到上表。

### BR 漏掉的第二個真衝突

BR 只查了它自己列的 10 個檔名，沒有反向問「規則要求帶前綴的檔案，引擎接受嗎」：

```
規則要求 C03_BOM.csv          : 1 處
引擎寫死裸 BOM.csv            : 1 處
引擎接受 C03_BOM.csv          : 0 處      ← 第二個真衝突，BR 未列
引擎接受 C03_Pin_Allocation   : 0 處
```

### 前例已存在 —— 引擎**已經**接受一個帶前綴的交付物

BR §「遷移軌已經在引擎裡了」講的是**位置**遷移。更強的證據是**檔名前綴**本身已有先例：

```
c00_prd_template.py:316,318      C00_Handoff_Report.md
templates/c00.dod.json:57-58     "C00-PRD/03_output/C00_Handoff_Report.md"
                                 "C00-PRD/C00_Handoff_Report.md"        ← 雙候選
templates/c00.dod.json:70        "C00-PRD/C00_Module_Breakout.pptx"
```

所以前綴採用**不是結構性受阻**，只是其他階段沒做。BR 建議的追加候選修法方向正確。

### 修正後的範圍

```
BR 主張:  10 個檔名 · 9 個 .py · 9 個模板  =  規則與閘互斥
實測:      2 個檔名（Pin_Allocation.csv · BOM.csv）構成真衝突
           4 個是引擎正確遵守豁免條款
           5 個規則根本沒規範（改不改是本 repo 的決定，不是遵守誰）
```

**下游的裁決在此仍然有效但性質不同**：`thesmart_products` 的使用者「明確覆寫例外條款」
是他們對**自己 repo** 的裁決；對 bodesign 引擎而言那是一個**新需求**（豁免檔也要能帶前綴），
不是引擎的缺陷。兩者的修法一樣（追加候選），但**歸責不同**，而歸責決定它排在哪個優先序。

### Status

- Severity 由隱含的 blocking 降為 **low**（下游未停線，且真衝突面是 2 個檔名不是 10 個）
- 保持 OPEN，Owner `(default)`
- **不併入本輪 commit 的修復**：真衝突的 2 個檔名（`BOM.csv` / `Pin_Allocation.csv`）
  都在 C03 表面，而 C03 的 readiness 契約正在 `schematic-engine` family 無 owner 的狀態下。
  修法本身便宜（追加候選），但需要跑 `test_readiness_folder_contract.py` 全套並補 mutation
  proof —— 那是一個獨立工作項，不該夾在覆核裡順手做。

### 我沒量的（誠實邊界）

- **沒有實際修改任何檔案，沒有跑測試。** 上面全部是唯讀 grep + `sed -n` + 一支
  把規則句子拆兩側的 Python 探針，可重跑。
- BR §誠實邊界第 1 點（改成候選序列後測試會不會綠）**我同樣沒量**。
- BR §誠實邊界第 3 點（`bodesign_workflow_core` 未 pip 安裝、下游怎麼載到它）**我沒查證**。
- 5 個「未分類」檔名**要不要**帶前綴，是本 repo 的產品決定，我沒有替它下結論。

---

## 第二輪：`BOM.csv` 那格我錯了，且客人標為未驗的那格有實質後果（`ses_04db7a1c5`, 2026-08-04）

### 我的「第二個真衝突」被推翻 —— 撤回

我上一段寫「引擎接受 `C03_BOM.csv` = 0 處，第二個真衝突」。**那是字面 grep 的結論，而閘不做字面比對。**
`ses_038683542` 指出 `c03.dod.json` 的 `bom` 是四候選 `any_of`，其中兩個帶萬用字元。

我用**引擎自己的 matcher**（`guide_dod._match_any`，非模擬）對真實檔案系統重跑：

```
[bom]    candidates = ['C03-EE/BOM.csv', 'C03-EE/*_完整BOM.xlsx',
                       'C03-EE/*BOM*.csv', 'C03-EE/*BOM*.xlsx']
[pinmap] candidates = ['C03-EE/*_GPIO_pinout.xlsx', 'C03-EE/Pin_Allocation.csv',
                       'C03-EE/*pinmap*.csv']

TREATMENT bom    prefixed  C03_BOM.csv            -> C03-EE/C03_BOM.csv   ← 早就接受
CONTROL+  bom    bare      BOM.csv                -> C03-EE/BOM.csv
CONTROL-  bom    bogus     ZZNOPE.csv             -> None                 ← 探針有判別力
TREATMENT pinmap prefixed  C03_Pin_Allocation.csv -> None                 ← ★ 唯一真衝突
CONTROL+  pinmap bare      Pin_Allocation.csv     -> C03-EE/Pin_Allocation.csv
CONTROL-  pinmap bogus     ZZNOPE.csv             -> None
```

**真衝突面再縮一格：只有 `Pin_Allocation.csv`，1 個。**

我犯的是**把結構化欄位當扁平文字**：`grep -F 'C03_BOM.csv'` 問的是「這個字串在不在檔案裡」，
而閘問的是「這個檔名滿不滿足任一候選 pattern」。**兩個問題不同，而 grep 的 0 對兩者長得一樣。**
（客人自承第一版探針也壞了一次，形狀同族：它手打候選清單只餵了裸名那一筆，漏掉同一 `any_of`
裡帶萬用字元的另外三個。兩次都是同一個病。）

### 客人問的那格（引擎用哪個 matcher）—— 已驗，且它的模擬確實會誤導

客人用 `fnmatch` 模擬，並誠實標記「我沒讀引擎實際用哪個比對函式，尤其 `*` 是否跨 `/`」。
引擎實際用的是 **`pathlib` 的 `base.glob(rel)`**（`guide_dod.py:89-95`），不是 `fnmatch`。
兩者在這個 repo 的實際輸入上**確實分歧**：

```
pattern             C03-EE/*BOM*.csv
file                C03-EE/03_input/C03_BOM.csv
fnmatch（客人模擬）  True     ← * 跨越了 /
ENGINE（Path.glob）  None     ← * 不跨 /
DIVERGE = True

CONTROL+ 同層檔案在引擎下仍命中: C03-EE/C03_BOM.csv
CONTROL- 假檔名仍 None
```

**這格有實質後果，不是學術差異。** 客人 §6 第 3 點提到 `03_input/` 下已存在
`C03_BOM.csv` / `C03_Pin_Allocation.csv`，並推論「glob 不跨層所以不影響閘」——**推論正確，
但它手上的工具會給出相反答案**。若它拿自己的 `fnmatch` 去驗那格，會得到「那兩個檔會滿足閘」
這個假結論。**它的推理救了它的工具**，而下一個人可能沒有那個推理。

### 客人提議的修法 —— 我用真 matcher 驗過，成立

```json
"any_of": [
  "C03-EE/*_GPIO_pinout.xlsx",
  "C03-EE/*Pin_Allocation*.csv",     ← 追加一筆
  "C03-EE/Pin_Allocation.csv",
  "C03-EE/*pinmap*.csv"
]
```

```
prefixed  C03_Pin_Allocation.csv -> C03-EE/C03_Pin_Allocation.csv   ✅
bare      Pin_Allocation.csv     -> C03-EE/Pin_Allocation.csv       ✅
bogus     ZZNOPE.csv             -> None                            ✅ 未變成全接受
```

**兩向都驗**：只驗前綴版會通過，等於「把候選改成 `*` 全接受」也會通過。

修法比原 BR 建議的「逐檔加前綴常數」省得多，且**與 `bom` 已有的 `*BOM*.csv` 形狀一致**——
引擎自己就有這個慣例，只是 `pinmap` 那列沒跟上。

### 修正後的最終範圍

```
原 BR 主張   10 個檔名 · 9 個 .py · 9 個模板  = 規則與閘互斥
第一輪覆核    2 個真衝突（Pin_Allocation.csv · BOM.csv）
第二輪實測    1 個真衝突（Pin_Allocation.csv），修法 = c03.dod.json 追加 1 個候選
```

**從 18 個檔案的重構，收斂成一個 JSON 陣列加一行。**

### 我第三次探針失效（同一輪內，記下因為它是同族）

寫上面那支驗證腳本時，我的模板存取器用 `d.get('name')` 取交付物——**實際欄位是 `id`**。
它回 `None`，然後 `_match_any(None)` 直接 `TypeError` 炸掉。

**這次是幸運的**：型別錯誤大聲炸開。若我當時寫的是 `d.get('name', '')` 或
`if d.get('name') == 'bom'`，它會靜默回「找不到候選」，而我會得出「`bom` 沒有候選清單」
這個假結論——正好會**支持**我原本錯誤的主張。

**同一輪三次同族失效**（跨句子樞紐的 grep · 字面 grep 當 pattern 比對 · 錯欄位名存取器），
兩次靜默、一次大聲。大聲那次是唯一沒造成錯誤結論的。

### 未量

- **仍未跑任何測試**，未修改任何原始碼。上述全部是唯讀分析 + 在 `tempfile` 沙盒裡呼叫真函式。
- `_match_any` 的 `bucket` 參數我全程傳 `None`。生產呼叫端是否帶 bucket、帶了會不會改變
  上述結論，**未量**。
- 其他階段（c01/c02/c04/c05/c06）的 `.dod.json` 是否有同樣「裸名候選但無萬用字元」的列，
  **未逐一掃描**。本輪只驗 c03。

## 下游現況（不阻塞本 BR，僅供判斷優先序）

`thesmart_products` 的機器橋接檔改名已 HOLD，等本 BR 有結論再動。人看的可視檔
（28 筆）已改完並驗過六層 readiness 全綠，所以**下游沒有停線**，這格不急。
