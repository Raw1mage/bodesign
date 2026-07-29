---
slug: control/no-silent-degradation
title: No Silent Degradation — 部分失敗不得讀成完全成功
layer: ragbase
type: control
confidence: verified
locator: issues/KB_20260729_silent_degradation_antipattern_invariant_and_lint.md / checkers/no_silent_degradation.py
---
# No Silent Degradation

**一個操作若只完成了它被要求的一部分，回傳的狀態必須讓呼叫端無法把它讀成「完全成功」。**

判準句（review 時問這一句就夠）：

> **如果呼叫端只讀 `ok` 或只讀一個計數就會得出錯誤結論，這個 API 就違反本 invariant。**

`no-silent-fallback` 管的是「缺輸入時不要猜」；本 control 管的是「處理過程掉東西時不要裝沒事」。
兩者是同一種誠實的兩面，但**測試覆蓋率高完全擋不住後者**——2026-07-29 一輪 C04 交付連續撞出
5 個實例，全部通過了當時的全部測試，因為測試都在測 happy path 的正確性，沒有一個斷言
「當 8 顆元件掉了，回傳值必須讓呼叫端知道」。

## 具體要求

任何「輸入元素集合 → 處理 → 輸出」的操作，若集合中任一元素被跳過、丟棄、無法解析、
或以降級方式處理，則：

1. 該事實必須出現在**回傳值**（不只 log、不只 warning 字串），且
2. 必須有一個**呼叫端會檢查的欄位**因此改變（`ok:false` / `status != "ok"` /
   `dropped[]` / `unresolved[]` / `basis` 非預設值），且
3. `expected` 與 `actual` 的計數必須同時可見（讓「84 vs 92」這種落差無法被單看一個數字掩蓋）。

## 五種變體

| 變體 | 定義 | 實例（BR_20260729） |
|---|---|---|
| **V1 元素靜默丟棄** | 迴圈內 skip 掉無法處理的元素，計數器不涵蓋此類 | §B `net2pcb` footprint、§D `plane_layers` key |
| **V2 量測降級無標記** | 首選量測法不可用時 fallback 到語意不同的次選法，回傳不標 basis | §C `courtyard → 含絲印 bbox` |
| **V3 狀態欄位不反映降級** | 降級資訊有收集也有傳出（誠實），但 `status`/`ok` 恆為成功 | S2 `layout.py unresolved_footprints` |
| **V4 量測基準分散** | 同一物理量在多處各自實作，修正只落其中一處 | §E `_extract_part_geoms` vs `placement_preflight` |
| **V4-b 參考系不一致** | 只有一份實作，但跨模組對同一座標的**參考系**假設不同 | §F origin vs courtyard-centre |

**V4/V4-b 與 V1–V3 的關鍵差異（勿混淆，修法不同）**：V1–V3 是**假綠**（靜默成功，違反天條）；
V4/V4-b 是**假紅**（gate 大聲失敗且訊息精確，*沒有*違反 no-silent-fallback，壞的是餵給它的量測）。
V1–V3 靠「加欄位讓降級可見」解；V4 靠**收斂實作到單一 helper**解；V4-b 靠**在型別/docstring 上
明確化參考系**解。把 V4 當 V2 修（加個 `basis` 欄位）不會解決任何事。

## 正確樣態（positive pattern，KB 只有反例不夠）

- **`plane_layers_applied: [{spec, layer, net, type}]`**（`routing.py net2pcb_board`）——
  呼叫端傳入的每一個元素，回傳裡都有一筆說明它的**實際去向**。這是要求 2 的教科書實作。
- **`basis: "courtyard" | "bbox_no_text" | "mixed"` + `courtyard_missing: [refs]`**
  （`routing.py placement_preflight`）——量測降級時，判決的基準本身是回傳的一部分。
- **`implausible_measurement`**（同上）——物理量超出定義域（占用率 > 1.0 = 元件面積大於板面積）
  時回 `passed:false` 並在 reason 明說此判決 **UNUSABLE**，而不是給一個自信的 `false`
  害呼叫端去「修」一塊從未被正確量測的板。這是 V2 的通用防線：即使降級邏輯沒被 lint 抓到，
  荒謬的結果會自己爆掉。
- **`PartGeom` 的 REFERENCE FRAME docstring**（`preplace.py`）——明寫 placement entry 是
  ORIGIN（因為那是 `pcbnew.SetPosition()` 寫的）、`pads` 從 origin 量、`anchor_dx_mm` 是
  courtyard-centre 減 origin 且為 part-local 未旋轉座標。V4-b 的正解是讓參考系**無法被誤會**，
  不是讓每個 caller 自己猜對。
- **`unconnected` + `complete: (unconnected == 0) if unconnected is not None else None`**
  （`routing.py autoroute`，BR_20260708）——routing 只完成 22/111 個網路時，回傳**沒有**把它
  報成成功；`complete` 的三態（True/False/None）還把「無法判定」與「判定為失敗」分開，
  不用 `False` 冒充「我不知道」。
- **`vias_per_ref: {ref: n}` + `refs_requested`**（`routing.py via_in_pad`，§G）——呼叫端點名的
  每一個 ref 都能被稽核：一個成功解析卻貢獻 0 個 via 的 ref（全部球都在 keep_rings 內、或沒接網路）
  在這裡是可見的，而不是被平均進一個看似合理的 `vias_added` 總數。
- **`advisories: [surface_escape_infeasible: …]`**（`routing.py bga_escape_capacity`，round=12）——
  **「資訊有給」與「資訊有用」是兩件事。** `traces_per_gap_computed: 0` 從第一版就在回傳裡，
  形式上完全合規；但它要求讀者自己重做 `n*w+(n+1)*c <= gap` 的算術才知道「表面逃逸在這個線寬下
  物理上不可能」。一個呼叫端因此用錯 `keep_rings`，花了 50 分鐘 routing 才回頭讀懂那個 0。
  修法是把**算術的結論**也講出來（需要 0.416mm、gap 只有 0.22mm、所以容量用的是樂觀 floor），
  而不是只給原始數字。**invariant 說呼叫端必須能稽核，而能稽核的前提是看得懂。**
  兩個配套約束：(a) advisory **永不翻轉 `blocking`**——樂觀 floor 正是讓這個 gate 不誤擋 fab
  天天在做的 fine-pitch 板的設計；(b) 措辭**不得指定動作**（用「only viable if the inner layers
  have the capacity」條件句，不寫 `keep_rings=1`），因為這個 gate 不評估內層容量，讀起來像
  指令就會把一個未評估的假設變成建議。有測試分別鎖這兩點。
- **`_load_board()` 這個 helper 本身**（`routing.py`，§H）——`pcbnew.LoadBoard()` 對不存在的路徑
  **回 `None` 而不 raise**，下游任何 pcbnew 呼叫拿到 null `BOARD*` 就 **SIGSEGV（exit 139）**，
  呼叫端只看到連線斷、連 Python 例外都沒有。正解是把「唯一開板方式」收斂成一個會 fail-loud 的
  helper（`BOARD_NOT_FOUND` 帶 resolved 絕對路徑 + worker cwd，因為觸發條件通常是呼叫端傳了
  相對於**自己** cwd 的路徑），並用一條 **AST 守衛測試**斷言模組內沒有任何 call site 繞過它。
  這是 V4（量測基準分散）的解法用在**資源取得**上：SSOT + 機械化防復發，而不是靠每個新 call site
  的作者記得檢查 `None`。

## §G：裸崩不是 silent degradation，但同樣讓呼叫端拿不到可行動資訊

§G（`via_in_pad` 對 castellated/LGA 模組的數字 pad 名拋 `max() iterable argument is empty`）
**不是**本 control 的變體：它沒有騙人，它大聲失敗了。但它與 V1–V3 共有同一個**後果**——
呼叫端拿不到可行動資訊（訊息未指出哪個 ref、哪個欄位、該怎麼修）。定性為 **L2 的反面案例**：

> `except` 吞掉失敗是一種病；**完全不 guard、讓底層 API 的裸錯冒到呼叫端**是它的鏡像。
> 兩者都讓呼叫端無法行動。修法對稱：前者要「把吞掉的講出來」，後者要「把底層錯誤翻譯成
> 領域錯誤」（哪個輸入、為什麼不適用、該怎麼辦）。

§G 修復時另外挖出兩個**真** V1（都已一併修）：(a) `refs` 中不在板上的 ref 原本靜默 no-op；
(b) **混合命名**（部分 `A1`、部分 `1`）原本不崩，但每個非網格 pad 都繞過 `keep_rings` 保護
被塞 via——`cols` 非空所以沒人發現，呼叫端只看到一個合理的 `vias_added`。**裸崩其實是在
遮蔽一個更糟的靜默缺陷**：只有「全部 pad 都非網格」才崩，混合命名反而安靜地毀掉板邊 pad。

## 可執行的閘

`packages/workflow-core/bodesign_workflow_core/checkers/no_silent_degradation.py`。
tier **由實測訊噪比決定**（對 §B–§F 修復前後的 `routing.py` 各掃一次，看是否「修前命中、修後歸零」）：

| 規則 | 修前 | 修後 | tier | 內容 |
|---|---|---|---|---|
| L2 | 2 | 0 | **T-A** | `except` 只有 pass/log 而函式有回傳值 |
| L6 | 1 | 0 | **T-A** | 呼叫端傳入的 key 查找失敗即靜默跳過（§D 直接規則） |
| L8 | 1 | 0 | **T-A** | 同一量測 API 在 >1 個函式各自實作（§E 直接規則） |
| L1 | 19 | 19 | **T-C** | 迴圈內 `continue` 未記錄被跳過的元素 |
| L10 | — | — | **設計規則** | 掃描/檢查類工具必須回報實際覆蓋範圍（見下） |

**L1 誠實降為 advisory**（預設不輸出）：它修復前後都報 19 筆，命中的是 regex 不匹配、
keep-ring 篩選這類**正常 filter 語意**——那些 `continue` 不是在丟棄呼叫端交付的元素，
而是在表達「這一項本來就不該處理」。AST 分不出「篩掉」與「丟掉」，硬當 T-A 會讓 19 筆雜訊
淹掉 3 筆真訊號，最後沒人跑這條 lint。

**誠實未實作**（不假裝覆蓋）：L3（expected vs actual 計數，需回傳 schema 對照）、
L4（primary/fallback 標記，需語意判斷）、L5（荒謬值 tripwire——**runtime domain 檢查，
靜態不可判**，它是設計規則不是 lint，見上方 `implausible_measurement`）、L7（key 正規化，advisory）。

## L10：掃描/檢查類工具必須回報實際覆蓋範圍

> 一個只回 findings 的 checker，**本身就是它所執行的反模式**：回報「0 findings」時，
> 呼叫端無法區分**真的乾淨**與**根本沒掃到那裡**。掃描範圍必須是回傳值的一部分。

這不是假設性風險，而是**本 checker 自己犯過的錯**：它的 `__main__` default roots 曾只有
`[packages/eda-bridge, packages/workflow-core]`，漏掃 `services/`——文件記載基線 11 筆，
預設指令印出 5 筆，**CI 若照預設跑會在從未被檢查的 code 上拿到假綠**。

實作（checker 自己先合規）：`check_paths(..., with_coverage=True)` 回 `Coverage`，
`__main__` 無條件印在 finding 數旁邊：

- `roots` / `files_scanned` / `files_skipped`——這個數字是由哪些檔支撐的
- `missing_roots`——**不存在的 root 是覆蓋缺口，不是空結果**（打錯的路徑否則會以「0 findings」冒充乾淨）
- `unparsable`——parse 不了的檔**不計入 `files_scanned`**：把規則從未真正跑過的檔算進已掃描數，
  正是這個 coverage 要阻止的不誠實
- 有缺口時 `exit 2`，CI 不會把「沒掃到」當成通過

一個順帶的發現：實作時我先寫了 `except SyntaxError` 來採集 `unparsable`，測試才曝出
`check_file` **從不拋** SyntaxError——它回一筆 `L0` finding 繼續（那才是對的：讀不了的檔
是 findings 不是 skip）。我那個 `except` 是**永不觸發的死碼**，已改成從 L0 finding 推導。
這條規則對**未來所有 checker** 適用，不只這一個。

**為何不進 `checkers/registry.py`**：那張表的每一列是「control → **design-IR** checker」
（`ir_fields` 是 IR 路徑、`stage` 是 C00–C04 管線階段、evidence 走 `ORACLE_TOOLS` envelope）。
本 control 檢的是 **Python 原始碼**，沒有 IR 輸入、不屬於任何管線階段、不產生板級 evidence。
硬註冊會逼我們在 `ir_fields` 填假路徑——那正是本 control 自己禁止的捏造。它改由 CI /
開發期直接呼叫（`python3 -m ...no_silent_degradation packages services/mcp`）。

## 全 repo 基線（2026-07-29，T-A）

11 筆真陽性：`L2`×8（`c01_id_package._emit_doc_pdf`、`c02_me_package._parse_connector_answer`、
`guide_dod.assess_guide_dod`、`mcp_delegate.resolve_mcp_server`、`server._h_kb_get`、
`server._produced_meta`、`token_store._reap_ephemeral`、`token_store.resolve`）、
`L6`×3（`spice_card._select_value`、`kicad_emit.emit_kicad_schematic`、`l4_check.check`）。
未修，登記為已知基線。

**這個數字必須由無參數的預設指令重現**（`python3 .../no_silent_degradation.py`）。§G 時發現
`__main__` 的 default roots 只有 `[packages/eda-bridge, packages/workflow-core]`，漏掃 `services/`
少報 6 筆——文件寫 11、預設跑出 5，CI 若照預設跑會拿到假綠。已改為 `[packages, services]`。
**一條 lint 的預設掃描範圍自己就是一個「回傳值是否反映實際做了什麼」問題**：它回報「0 findings」
時，呼叫端無法區分「真的干淨」與「沒掃到那裡」。

## Source evidence

- `distilled_from` → `issues/KB_20260729_silent_degradation_antipattern_invariant_and_lint.md`
  （aiguard C04 consumer 提案，四實例全帶實測數據）
- `distilled_from` → BR_20260729 五實例：commit `1269a20`（§B）、`cdbcb02`（§C/§D/S2）、
  `f958e68`（§E）、`a25d898`（§F）

## Related

- ← `refines` [[control/no-silent-fallback|No Silent Fallback]]（缺輸入不猜 ⊥ 掉東西不裝沒事）
- → `constrains` [[workflow/c04-layout|C04 Layout — placement → routing → fab outputs]]
- ← `references` [[concept/impl-evidence-gaps|Evidence-Linked Knowledge, Explicit Gaps]]
