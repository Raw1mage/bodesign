# BR_20260802 — 保真閘還原後是紅的：`test_fidelity_gate` 在 HEAD 從未執行過，所以沒有人知道它壞了

- **Status**: OPEN
- **Owner**: unassigned（`schematic-engine` family 無 owner；filed by 值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH`）
- **Family**: `schematic-engine`
- **Severity**: real — `fidelity.py` 是這個 family 的**驗收儀器**，它現在 RED 且 deterministic
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/fidelity.py` × `composer.py:2600` × `tests/test_fidelity_gate.py`
- **Filed at**: 2026-08-02
- **時區**: Asia/Taipei (UTC+08:00)
- **Parent**: `issues/BR_20260802_reset_hard_destroyed_kicad_emit_and_the_BR_blamed_the_import_that_was_correct.md`

## 這張為什麼會存在

還原 `kicad_emit.py`（見 parent BR）之後，`bodesign_eda_bridge` 終於能 import，
於是 43 個測試模組第一次真的載入。**其中包含這個 family 的驗收儀器，而它是紅的。**

在 HEAD，這個模組**從來沒有跑過**——它回報的是 `Ran 1 test, errors=1`（`_FailedTest`，
整個模組在收集期就死）。

> **「儀器紅燈」與「儀器從未開機」在測試摘要上都是一行 FAILED。**
> 這是本 repo 反覆出現的形狀（`code-thinker §8.1`）：缺席態與失敗態共用同一個輸出。

## 實測（還原後的樹，連跑兩次結果相同）

```
tests.test_fidelity_gate
  test_all_label_path_is_faithful             ERROR
  test_verify_partition_fidelity_standalone   FAIL
  test_expected_partition_from_dict_nets      ok
  test_faithful_candidate_passes              ok
  test_fused_candidate_is_flagged             ok
```

### ERROR（integration path）

```
tests/test_fidelity_gate.py:88  compose_schematic(...)
  -> composer.py:2600  raise FidelityError(report)
bodesign_eda_bridge.fidelity.FidelityError:
  schematic fidelity gate FAILED — net partition diverged from spec
  (collinear-wire fusion / label collision)
```

### FAIL（standalone path）

```
baseline nets=9 nodes=24 | candidate nets=6 nodes=18 | shared=18
ONLY_BASELINE (missing from candidate): ['J1.1','J1.2','J1.5','R1.1','R2.1','R5.1']
FIDELITY FAIL moved=0 only_baseline=6 only_candidate=0
```

**9 個 net 被熔成 6 個**，6 個節點消失，且 `only_candidate=0` / `moved=0`——
沒有節點跑錯 net，是**整段連接被吃掉**。錯誤訊息自己指名的機制是 collinear-wire fusion：
共線的線段被併成一條，於是本該分離的 net 短接在一起。

**這是電氣正確性缺陷，不是外觀缺陷。** J1（連接器）與 R1/R2/R5 的接點在候選裡不存在。

## 三個必須先回答的問題（不要直接跳去修）

1. **這個紅燈是還原造成的，還是還原**揭露**的？**
   還原的 `kicad_emit.py` 比 HEAD 多 765 行、`emit_kicad_schematic` 多兩個參數
   （`clusters`、`l6_avoidance`），6 個函式本體不同。紅燈可能來自那些差異，
   也可能是這份未 commit 的 WIP 本來就沒做完。**先分辨，再動刀。**
2. **baseline 是對的嗎？** `baseline nets=9` 來自 `expected_partition_from_dict_nets`。
   若 baseline 本身過期，修 candidate 是修錯邊。
3. **`refs/recovered/kicad_emit_full` 是未 commit 的 WIP，從來沒有被證明是好的。**
   它唯一被證明的是「能讓 import 成功」（值星官親手驗，見 parent BR）。
   **能 import ≠ 正確。** 不得因為它修好了 43 個模組就推定它整體正確。

## Validation plan（必要，不接受「改到綠」）

- **控制組先行**：確認這個測試在**該紅的時候會紅**——手動把一個 net 熔掉，
  斷言 `only_baseline` 增加。沒有這一格，「改到綠」可能只是把儀器關掉。
- **Mutation proof**：修好之後，把修復點改壞一次，斷言測試轉紅。
- **不得放寬閾值當修復**。`fidelity.py` 是驗收儀器，調鬆它等於銷毀證據。
- 迴歸：`test_kicad_emit` / `test_composer_draftsman` / `test_block_drafter`
  （byte-stable 迴歸基線所在）。

## Cross-ref

- parent BR — 還原的授權與位元組條件
- `issues/OWNERS.md` — `schematic-engine` family 無 owner
- `plans/eda-bridge_layered-pipeline/` — DD-8（`interior_crossings=0`）、DD-14（justify-left）
  的驗收紀錄；DD-16 記載 net-flag 疊印為獨立缺陷軸


---

## 值星官獨立覆核（2026-08-02，commit `2efc3a9` / `23c0bc7` 落地後）

三個授權條件我親手重算，不採信 peer 的自報數字：

```
條件1 位元組  blob   9d92d442c1dd95dece15a9fe44a1616e2f7e02559b01d68d374a4074c2577470
              landed 9d92d442c1dd95dece15a9fe44a1616e2f7e02559b01d68d374a4074c2577470   IDENTICAL
   控制組     pre-commit 版本 8194fa18a6…  ← 不同 ⇒ sha256 比對有鑑別力，非 vacuous
條件2 分離    resolve_symbol_library: A=0  B=1        （控制組 bogus 在 A=0）
條件3 紅燈    A 的 message: nets=9 / J1.1 / only_candidate=0 / _FailedTest / NEVER RAN 全命中
```

### 回歸基線：pre vs post，同一個儀器

原 BR 的「還原前這些模組沒跑」是引述 peer 的。我用 `git archive 2efc3a9~1` 匯出乾淨樹自己量：

| 模組 | pre-restore | post-restore |
| --- | --- | --- |
| `test_kicad_emit` | ran=1 `_FailedTest`=2 | **ran=10** failures=3 |
| `test_composer_draftsman` | ran=1 `_FailedTest`=2 | **ran=61** errors=11 |
| `test_fidelity_gate` | ran=1 `_FailedTest`=2 | **ran=5** failures=1 errors=1 |
| `test_block_drafter` | ran=1 `_FailedTest`=2 | ran=1 `_FailedTest`=2 ← **沒變** |
| **控制組**：不存在的模組 | ran=1 `_FailedTest`=2 | ran=1 `_FailedTest`=2 |

**控制組與四個真實模組在 pre-restore 完全同形。** 這不是儀器失效，這正是本 BR 的論點：
還原前，「這個模組壞了」與「這個模組根本不存在」**在測試輸出上無法區分**。

### ⚠ 更正 peer 的一項數字：43 → **2**，不是 43 → 0

`commit 2efc3a9` 的 message 寫「43 個 collection-time 死亡模組歸零」。**實測不是 0。**

```
逐一 import 全部 133 個 tests/test_*.py（單一 process）
  importable  = 131
  IMPORT-DEAD = 2
    test_block_drafter    ModuleNotFoundError: No module named 'kiutils'
    test_symbol_resolver  ModuleNotFoundError: No module named 'kiutils'
  控制組：import 一個確定不存在的模組 → raise（偵測器有鑑別力）
```

**但這不折損還原的價值**：剩下 2 筆的成因與被摧毀的符號**完全無關**——是 `kiutils`
這個第三方套件沒安裝。還原修好了它該修的那 41 個，第二個獨立的阻塞因此才浮現。

**這正是本 BR 的形狀第三次出現**：`kiutils` 缺失一直都在，只是先前被
`_vendor_sym_scale` 的 ImportError 蓋住——**一個缺陷把另一個缺陷藏起來，而兩者回報同一個訊號**。

`kiutils` 缺失屬環境/依賴問題，不屬本 BR，另計。

### 結論

- 還原**成立**，三條件全過，import 在 HEAD 可用（我親測 `IMPORT_OK`）
- 保真閘紅燈**確認**、deterministic、與 peer 回報逐字相同
- 本 BR **維持 OPEN**，需 `schematic-engine` owner

---

## RCA（`ses_0c87bab06fferQ0umBs2Nybb5U`，2026-08-02 · 單張授權、非 family）

授權範圍：RCA 至根因坐實為止。**修法未落地**，未 commit 任何原始碼變更。
取證全在 `$XDG_RUNTIME_DIR/fidrca`，repo 內 `packages/` `tests/` `services/` 零變更
（控制組：不帶 pathspec 的 `git status --porcelain` 有 34 筆，帶 pathspec 後只剩 7 筆
既存 untracked 測試檔，皆非本輪產生）。

### 根因（機制）

**浮點等值比較落在刀鋒上。** 鏈路四段：

```
_bbox_clear(label_box, graphics_box)                     kicad_emit.py:1933
  gap_y = 1.2699999999999818   clearance = 1.27          → gap >= clearance  FALSE
    ↓ 判定「未達淨空」
_avoid_label_overlap  把 anchor 沿外向量推出一步          kicad_emit.py:2383
  _L6_AVOID_STEP_MM = _LABEL_CH_MM + _LABEL_VMARGIN_MM = 1.27 + 0.3 = 1.57
    ↓ label anchor 離開 pin endpoint 1.57 mm
DD-22/23 契約禁止任何 stub / jog / wire 把它接回去          kicad_emit.py:2340-2356
    ↓ 沒有導體連接
KiCad 匯出時該腳成為 unconnected-(Rn-Pad1)                 電氣斷路
```

**`1.27` 這個數字同時是三個東西**：格點、`_CLEARANCE_MM`（最小淨空）、`_LABEL_CH_MM`
（文字高）。於是「元件放在格點上、標籤盒高一格」自然產生**恰好等於淨空**的間隙——
本 fixture 8 個垂直標籤**全部**落在 `gap == clearance` 這個刀鋒上，
其中 3 個因浮點累積算成 `1.2699999999999818`（差 −1.8e-14）而判偽：

| net | `gap_y` 實際浮點值 | `gap_y − 1.27` | `>= clearance` | 結果 |
| --- | --- | --- | --- | --- |
| N4 / N6 / N7 / N8 | `1.2700000000000102` | +1.02e-14 | True | 不動 |
| N3 | `1.2700000000000031` | +3.11e-15 | True | 不動 |
| **N1 / N2** | `1.269999999999996` | −4.00e-15 | **False** | **推 1.57mm** |
| **N5** | `1.2699999999999818` | −1.82e-14 | **False** | **推 1.57mm** |

被推的三個標籤 `R1.1` / `R2.1` / `R5.1` 因此離開腳位，落入
`unconnected-(R1-Pad1)` / `(R2-Pad1)` / `(R5-Pad1)`。

**這不是「哪些元件比較擠」的問題**——8 個間隙名目上完全相同（都是一格），
差別只在浮點誤差的正負號。同一份 spec 換個座標順序，中招的會是另外三個。

### 決定性實驗（雙控制組）

```
A  stock                          → RED   only_baseline=[J1.1 J1.2 J1.5 R1.1 R2.1 R5.1]
B  _avoid_label_overlap 停用      → GREEN ok=True
C  還原 stock                     → RED   （同 A，證明 B 的綠來自 patch 而非執行順序）

D  _bbox_clear 改 epsilon 容差     → GREEN ok=True
D' 負向控制：epsilon 不得使真缺陷失明
     true gap = 1.27                  stock=True   eps=True
     true gap = 1.2699999999999818    stock=False  eps=True    ← 只有這格改判
     true gap = 1.20 / 0.5 / 0.0      stock=False  eps=False   ← 仍正確判紅
```

### 起點假設的驗證結果：**推翻**

> 起點假設：`only_candidate=0` / `moved=0` ⇒ 整段連接消失，嫌疑在
> **wire fusion / label collision 把兩條 net 熔成一條**。

**實測是相反的機制。** 匯出的 netlist 逐 net 全文：

```
N1  ['J1.1']                       ← 只剩連接器側
N2  ['J1.2']
N5  ['J1.5']
N3  ['J1.3','R3.1']                ← 正常的對照
unconnected-(R1-Pad1)  ['R1.1']    ← 電阻側被踢成孤立節點
unconnected-(R2-Pad1)  ['R2.1']
unconnected-(R5-Pad1)  ['R5.1']
```

**沒有任何兩條 net 被熔在一起。** 節點**全部都被產生了**（`parse_net_file` 宇宙
24 個節點，與 baseline 相同），是**接線斷掉**，被拆成兩個各自孤立的單節點 net。
你要求的那個分岔——「節點沒被產生」vs「節點被併進別的 net」——**兩個都不是**，
是第三種：**節點被產生、但接不上**。

錯誤訊息 `(collinear-wire fusion / label collision)` 是 `FidelityError.__init__` 的
**硬編字串**（fidelity.py:64），對任何一種偏離都印同一句。它把讀者導向錯的機制。
—— 這是本 repo 那個形狀的又一例：**訊息文字宣告的病因，與實際判定出的病症無關**。

### 儀器側的第二個缺陷（獨立於上面那個）

`sch_union_classes`（fidelity.py:104）用 union-find 重建 net，**只 union 有第二個節點的
class**；單節點 net 從不進入 `parent` dict，因此**整個從候選宇宙消失**：

```
parse_net_file      universe = 24 nodes   R1.1 在裡面（class size 1）
sch_union_classes   universe = 18 nodes   R1.1 不在
DROPPED: ['J1.1','J1.2','J1.5','R1.1','R2.1','R5.1']
```

後果：斷路節點**不是**以「跑到別的 class」被偵測，而是以「從宇宙裡消失」被偵測，
再由 `compare_partitions` 的 `only_baseline` 撿回來。這條路徑**目前有效**，但它讓
`only_candidate` 恆為 0——而 `only_candidate=0` 正是誘導出「熔接」假設的那個訊號。
**儀器的呈現方式，直接導致了對病因的錯誤推論。**

### 量了什麼

- 紅燈在 host（`kicad-cli 9.0.9`）確定性重現，與 BR 記載逐字相同
- 逐 net 全文 dump（不是 nets 數量差）
- 每一個垂直標籤的 `label_bbox` vs `graphics_box`，在**決策點**捕捉未捨入浮點
- `_avoid_label_overlap` 全程 spy：3 次位移，每次 `#placed_hits=0` / `#graphics_hits=1`
  → 觸發者是 **DD-14 graphics clearance**，不是 label-vs-label
- 位移後的 anchor 是否被任何 wire endpoint 觸及：**9 條 wire，0 條觸及**
- `l6_avoidance` 參數是否活的：**死的**。`emit_kicad_schematic(l6_avoidance=)` 的值
  從未被讀（唯一使用點 kicad_emit.py:1515 硬編 `l6_avoidance=True`）。
  分離 process + 修正 UUID 正規化後，`False`/`True` 各兩次跑出**同一個 sha256**。
  ⚠ 我第一次量得到「param IS live」是**偽陽性**：我在同一個 process 連跑四次，
  `#PWR000n` 是 process-global 計數器，且我的 UUID 正規式漏了 `(path "/uuid")` 形式。
- 這條路徑在 pre-restore 樹（`2efc3a9~1`）**完全不存在**：`_bbox_clear` / `_CLEARANCE_MM`
  / `_avoid_label_overlap` / `graphics_boxes` 出現次數皆為 0（控制組：
  `def emit_kicad_schematic` 為 1，證明我讀到的是同一個檔）
  → **回答 BR 的問題 1：紅燈是還原「引入」的，不是還原「揭露」的。**
- `_bbox_clear` 全 repo 只有一個呼叫點（kicad_emit.py:2413）——blast radius 極小

### 沒量什麼（邊界）

- **baseline 是否正確**（BR 問題 2）：未獨立驗證。我只證明 candidate 側斷路，
  沒有反向確認 `expected_partition_from_nets` 的 9 條 net 本身無誤。
- **DD-20 對向垂直位移路徑**：本 fixture 的垂直標籤 edge **全部**是 `(0,-1)`，
  沒有對向配對，`_dd19_dense_column_offsets` 回傳 0 筆。這條路徑**不受
  `l6_avoidance` 閘控（產品 all-label 頁會走到）**且同樣位移 anchor——
  **它是否有相同的斷路風險，本輪完全未量測**，不是量了沒事。
- **真實產品頁**（aiguard C03 等）是否已受害：未量。本 fixture 是合成的。
- **修法對既有 byte-stable 迴歸基線的影響**：未量（修法未落地）。
- `test_dd14_text_graphics_clearance.py`（untracked，非本輪產生）本身有 1 個
  `TypeError: _symbol_geometry() got an unexpected keyword argument 'sides'`
  的既存錯誤，與本 BR 無關，另計。
- `kiutils` 缺失（值星官已記載）未處理。

### 修法的形狀（不是修法本身）

三個層次，**由淺到深，需要的原作脈絡遞增**：

1. **止血層（不需原作脈絡）**：`_bbox_clear` 的比較加 epsilon 容差。
   已驗證能讓保真閘全綠，且負向控制證明它不會讓真缺陷失明（gap 1.2 / 0.5 / 0.0
   仍正確判紅）。**但這只是把刀鋒往安全側挪一格，沒有拿掉刀鋒。**

2. **結構層（需要「1.27 為何同時是三個常數」的脈絡）**：格點、`_CLEARANCE_MM`、
   `_LABEL_CH_MM` 共用 `1.27` 是刀鋒的成因。若淨空定義為「> 一格」或標籤盒
   高度不等於一格，這類等值比較就不會出現。**這是設計取捨，我沒有原作脈絡。**

3. **契約層（需要 DD-22/23 原作決策脈絡）——我認為這才是真缺陷**：
   > 「為了避開圖形而移動 label anchor」與「anchor 必須落在 pin endpoint 上才有電氣連接」
   > **是兩個直接衝突的契約**，而 DD-22/23 禁止用 stub wire 調和它們。
   目前的解法是讓**美觀契約無條件贏**，代價是**靜默斷路**——沒有任何斷言擋住
   「anchor 被移離 pin endpoint」這件事。epsilon 只是讓這次不觸發，
   **下一次幾何稍有不同就會再觸發，而且一樣不會有人知道。**

   最小的契約層修法形狀：`_avoid_label_overlap` 位移後，**斷言 anchor 仍在
   pin endpoint 上，否則 fail-loud**（美觀讓位給電氣，或顯式報錯要求人介入）。
   這改變的是「衝突時誰讓步」的產品決策，**必須由有 DD-22/23 脈絡的人裁決，不是我**。

### 派工建議

- 層次 1 可由任何人執行（含 mutation proof 已備）
- 層次 3 需要 `plans/eda-bridge_layered-pipeline/` DD-22/23 的原作者或有該脈絡者
- **不建議只做層次 1 就關掉這張 BR**——那會把一個契約衝突降級成一次浮點調整
