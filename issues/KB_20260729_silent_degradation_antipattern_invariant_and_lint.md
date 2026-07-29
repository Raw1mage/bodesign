# KB 提案 — `control.quality.no-silent-degradation`:部分失敗不得靜默降級為完全成功

- Type: **KB ingest 提案**(非 bug report)
- Proposed by: `ses_073a93d09ffeRTpR9TwIdofhb3`(aiguard C04 consumer)
- Evidence basis: 2026-07-29 一輪 C04 交付中連續撞出的 **4 個同族缺陷**(§B/§C/§D + S2),全部有實測數據
- Target: bodesign ragbase `control.*` object + `packages/workflow-core/.../checkers/` lint + `skills/bodesign/doctrine.md` 一行
- Status: OPEN — 待 platform adjudicate 並 ingest

---

## 0. 為什麼要沉澱(不是又一張 bug 清單)

bodesign 已有天條「No-silent-fallback」,寫在 `specs/architecture.md` 多處、寫在 doctrine、也被多份 BR 引用。
**但它在 2026-07-29 這一輪被違反了四次,而且四次都通過了現有全部測試。**

這證明一件事:**天條目前是 prose,不是可執行的閘。** 每次靠人臨場想起才生效——這正是天條自己禁止的那種
「靠自律、不靠機制」的狀態。本提案要把它從 prose 變成 (a) 一條可檢索的 KB invariant + (b) 一份
code-review/實作期可跑的 lint checklist。

補充一個更硬的理由:**§D 的受害者是本輪的實際交付物。** 我的 4 層板兩個 power plane 從未建立,
而 API 回報一切正常。若不是我為了查 §C 去 dump `.kicad_pcb` 的 layer type,這塊板會帶著
「以為有 GND/PWR plane、實際兩層都是 signal」進 routing、進 fab。**這不是理論風險。**

---

## 1. Invariant 陳述(建議 KB 正文)

> **一個操作若只完成了它被要求的一部分,回傳的狀態必須讓呼叫端無法把它讀成「完全成功」。**
>
> 具體:任何「輸入元素集合 → 處理 → 輸出」的操作,若集合中任一元素被跳過、丟棄、無法解析、
> 或以降級方式處理,則:
> 1. 該事實必須出現在**回傳值**(不只 log、不只 warning 字串),且
> 2. 必須有一個**呼叫端會檢查的欄位**因此改變(`ok:false` / `status != "ok"` / 專用的
>    `dropped[]` / `unresolved[]` / `measurement_basis` 欄位非預設值),且
> 3. `expected` 與 `actual` 的計數必須同時可見(讓「84 vs 92」這種落差無法被單看一個數字掩蓋)。
>
> **反向表述(判準句)**:如果呼叫端只讀 `ok` 或只讀一個計數就會得出錯誤結論,這個 API 就違反本 invariant。

### 四種變體(分類法,供 lint 分項)

| 變體 | 定義 | 本輪實例 |
|---|---|---|
| **V1 元素靜默丟棄** | 迴圈內 `continue`/`skip` 掉無法處理的元素,計數器不涵蓋此類 | §B `net2pcb`、§D `plane_layers` |
| **V2 量測降級無標記** | 首選量測法不可用時 fallback 到語意不同的次選法,回傳值不標記 basis | §C `courtyard → bbox` |
| **V3 狀態欄位不反映內部降級** | 內部確實收集了降級資訊並傳出(誠實),但 `status`/`ok` 欄位恆為成功 | S2 `layout.py unresolved_footprints` |
| **V4 量測基準分散** | 同一物理量在多處各自實作,修正只落在其中一處 → 系統內部對同一事實有互相矛盾的兩個答案,而兩者都被當權威使用 | §E `_extract_part_geoms` vs `placement_preflight` |

#### V4 是後加的,而且它揭露了 V1–V3 的一個盲點

V1–V3 全部關於**單一 API 的回傳誠實性**。V4 不同——`PREPLACE_BOARD_TOO_SMALL` 這個 gate
**本身運作完全正確**,它大聲失敗、訊息精確、沒有違反 No-silent-fallback。壞的是**餵給它的量測**。

| | V1/V2/V3 | **V4** |
|---|---|---|
| 失敗模式 | 靜默成功 → **假綠** | fail-loud 但基準錯 → **假紅** |
| 天條關係 | 違反 No-silent-fallback | **不違反**——它確實大聲失敗了 |
| 後果 | 缺陷溜過去 | 合法的板被誤擋,人被迫去「解決」不存在的問題 |

**這條必須寫進 KB**,因為修好 V1–V3 不會讓 V4 消失:§C 把 `placement_preflight` 的量測
修成真 courtyard 之後,`_extract_part_geoms` 裡的同一份灌水量測**原封不動**——同一塊板,
系統內部同時持有 1008.8mm² 與 11151.1mm² 兩個「元件總面積」,兩者都被當權威使用。

**誠實補充**:V4 的存在本身就是本 KB 提案的價值證明——如果當初 §C 修復時 KB 裡已經有
「同一物理量須收斂到單一 helper」這條,§E 根本不會發生。

#### V4-b 參考系不一致(§F)—— 與 V4 分開收,因為修法不同

> **V4-b 參考系不一致**:同一物理量只有一個實作(V4 已解),但它的**語意/參考系**在各呼叫端
> 被各自假設 → 數值本身正確,放在錯的地方。

**實例 §F**:`footprint_extent` 統一了 courtyard 的 **w/h**(V4 已解),但 `preplace` 把座標當「盒子中心」
(`x±w/2`),`pcbnew` 的 `SetPosition()` 設的却是 **footprint origin**。實測 92 顆中 **5 顆 courtyard 不置中**:
```
JSA/JSB  dy=+22.225mm  ← 郵票孔連接器,原點在 pin 1 不在幾何中心
ANT1     dx=+4.550 dy=-2.625
UB1      dy=-1.650
```

**決定性實驗**(`experiments/aiguard_c04/probe_model.py`):同一份 courtyard w/h,只換盒子中心——

| 模型 | 中心取法 | 重疊對數 |
|---|---|---|
| A: origin-centred | `fp.GetPosition()`(preplace 假設) | **6** ← 與 preplace 自報逐項相同 |
| B: real courtyard | `GetCourtyard().BBox().GetCenter()` | **8** ← 與 preflight 判決逐項相同 |

兩份清單只有 4 對共同;差異項**全部**涉及 ANT1/UB1(偷移最大那幾顆)。

**為何不能併進 V4**:V4 的解是「收斂實作到單一 helper」;V4-b 已經只有一個實作了,
解是「**明確化參考系**」——helper 回傳值必須自帶 anchor 定義,不能讓呼叫端各自假設。
若併進 V4,未來讀 KB 的人會以為「抽個 helper」就解了。

**嚴重性高於數字不一致**:preplace 的 SA optimizer 正在對一個**錯誤的世界模型**做最佳化。
`placement_violations: []`(R1 decap 距離、R8 die-shadow)也是用同一個 origin-centred 模型算的
→ **那個「零違規」不可信**。它報零違規,而真實 courtyard 有 8 對重疊、最糟 6.59mm²。

**已排除的假設**(誠實記錄,免後人重查):
- **旋轉**:`preplace.py:160 _dims()` 對 90° 正確交換 w/h,是 rotation-aware 的。6 9/92 顆有非零旋轉但不是成因。
- **gutter**:`GUTTER_MM` 只進 `need` 面積估算與 greedy 間距,不進 `_overlap_area`。

---

## 2. 四個實例的完整證據(KB 的 evidence anchor)

### V1-a — `routing.py net2pcb_board`(§B,已修 commit `1269a20`)
```
不給 fp_dirs:  ok:true   placed:84   unmapped:0     ← 讀起來全成功
真相:          92 元件中 8 顆主動 IC(U1 U2 U3 U5 U6 U7 UB1 UW1)被整顆丟棄
機制:          grid strategy 遇 footprint lib 無法解析 → `continue`
                `unmapped` 只計 pad-name mismatch,完全不涵蓋「元件消失」
```
修後:`ok:false` + `dropped_components[{ref,fpid,reason}]` + `expected_components` vs `placed`。

### V1-b — `plane_layers` key 靜默丟棄(§D,待修;**本輪交付物已中招**)
```
呼叫:  plane_layers=["In1.Cu:GND","In2.Cu:PWR"]   track_mm=0.25
回傳:  一切正常
實測:  .kicad_pcb 中 In1/In2 皆 type=0 (LT_SIGNAL) — 兩個 power plane 從未建立
機制:  lymap 只認 "In1"/"In2" → lymap.get() 回 None → `if ly is not None` 跳過
        外層還包 `except Exception: pass`(雙層吞)
對照組: 同一次呼叫的 track_mm=0.25 有生效 → 證明不是整包參數沒吃到,是單一 key 靜默丟
```
**這是最惡性的一例**:輸入是**合法且更精確**的格式(`In1.Cu:GND` 明確指定層+網路),
卻因為 key 正規化缺失被當成不存在。使用者寫得越精確,越容易踩到。

### V2 — `placement_preflight` courtyard 量測(§C,待修)
```
機制: GetCourtyardBoundingBox() 在此 pcbnew 版本 AttributeError
      → 外層 except Exception 靜默 fallback 到 GetBoundingBox()(含絲印文字框)
```
| 指標 | preflight 回報 | 真實 courtyard | 倍率 |
|---|---|---|---|
| 重疊對數 | 135 | **6** | 22× |
| 元件總面積 | 11151 mm² | **1009 mm²** | 11× |
| utilization | **1.27** | ~0.115 | — |

**決定性反證**:兩顆**相距 8mm** 的 0402(courtyard ≈0.5mm²)被判「重疊 27.78mm²」——
物理不可能,是絲印文字框相交。

**注意這一例的特殊惡性**:它 fail 的方向是**偏保守**(誤報板子太擠),所以不會被
「結果太好看所以可疑」的直覺抓到。而 `utilization=1.27`(元件面積 > 板面積,物理上不可能)
這個**荒謬值本身就是 tripwire**,系統卻照樣回傳它。→ 衍生一條 lint 規則(見 §3 L5)。

### V3 — `layout.py unresolved_footprints`(S2,待評估)
有收集、經 `asdict` 傳出(**這部分是誠實的**),但 `status` 恆為 `"ok"`,即使整批 footprint 都沒解析到。
比 V1/V2 輕(資訊有到呼叫端),但仍違反 invariant 第 2 條(沒有任何呼叫端會檢查的欄位改變)。

### 誠實排除(驗過**不是**缺陷,寫進 KB 以免後人重查)
- `composer._pin_ct` 的 `except` **不吞** `SymbolLoadError`:`raise` 在 L1791、`_pin_ct` 在 L1829 之後,
  對 symbol-load 失敗路徑不可達。BR_20260723d 的修法是完整的。

---

## 3. Lint checklist(建議落成可跑的 checker)

適用於 `packages/eda-bridge/` + `packages/workflow-core/` 全部對外 API。

| # | 規則 | 機器可檢性 | 判法 |
|---|---|---|---|
| **L1** | 迴圈體內出現 `continue` / `break` / `pass` 且該分支未寫入任何「被跳過」的累積容器 | **T-A**(AST 可判) | AST:for/while body 內的 `continue` 節點,回溯同 scope 有無 `.append(`/`+=` 到名稱含 `drop|skip|unresolved|fail|missing` 的變數 |
| **L2** | `except` 區塊只有 `pass` / 只有 `log`,且函式有回傳值 | **T-A** | AST:`ExceptHandler.body` 全為 `Pass`/`Expr(Call(log*))` |
| **L3** | 函式接受集合型參數(list/dict)但回傳值不含該集合的 `expected` vs `actual` 計數 | **T-B** | 需簽章+回傳 schema 對照,先做人工 checklist |
| **L4** | 有 primary/fallback 兩條量測路徑,但回傳值不含 `*_basis` / `*_method` 標記 | **T-B** | 靠 review;可先列出所有 `hasattr(x,'Get...')`/`getattr(...,None)` 分支點 |
| **L5** | **荒謬值 tripwire**:回傳的物理量超出定義域(占用率>1.0、面積>板面積、距離為負、計數>母集合) | **T-A** | 每個量在 schema 上標 domain,超界 → `ok:false` + `reason=implausible_measurement`。**這一條是 V2 的通用解**:即使 fallback 邏輯沒被抓到,荒謬的結果也會自己爆掉 |
| **L6** | dict key 查找(`.get(k)`)結果為 `None` 時直接 `continue`/跳過,而 key 來源是**呼叫端傳入** | **T-A** | AST:`Subscript`/`.get()` + `if x is not None` 守衛 + 無 else 分支記錄。**這是 §D 的直接規則** |
| **L7** | 呼叫端傳入的 key 有多種合理書寫法(`In1` / `In1.Cu` / `In1.Cu:NET`),但只接受一種 | **T-C**(advisory) | review 提問:「這個 key 的所有合理寫法都被正規化了嗎?無法解析時是 fail-loud 嗎?」 |
| **L8** | **同一物理量的取得分散在 >1 個函式**,各自實作 | **T-A** | AST:同一個底層 API(`GetBoundingBox` / `GetCourtyard` / 任何幾何或計量取得法)出現在多個函式定義內 → 要求收斂到單一 helper。**這是 §E/V4 的直接規則** |
| **L9** | 跨模組傳遞的**座標/幾何值未在型別或欄位名上顯式標明參考系** | **T-C**(advisory) | review 提問:「這個 `(x, y)` 是 origin 還是 bbox center?哪一層座標系?」——`placement[ref] = (x, y, rot)` 沒說,`PartGeom.w_mm` 有說。**這是 §F/V4-b 的規則**;L8 拓不到 V4-b(沒有重複實作) |

**L5 + L6 是最高 ROI**:兩者都是 T-A(純 AST / 純 schema),且分別覆蓋本輪最惡性的 V2 和 V1-b。

---

## 4. 為什麼現有機制沒接住(RCA of the RCA)

值得寫進 KB,因為這決定 lint 該放哪裡:

1. **測試都在測 happy path 的正確性,沒測 unhappy path 的可觀測性。**
   `net2pcb` 有測試、`placement_preflight` 有測試——但沒有一個測試斷言「當 8 顆元件掉了,
   回傳值必須讓呼叫端知道」。**測試覆蓋率高 ≠ 誠實性有保障。**
   → 建議:每個對外 API 至少一個 `test_*_partial_failure_is_loud` 案例。

2. **天條寫在 architecture.md / doctrine,但 checker registry 裡沒有對應的 `control.*` 物件。**
   `checkers/registry.py` 目前 19 bindings 全是**電路領域**規則(decoupling / spacing / derating),
   沒有一條是**軟體契約**規則。天條因此永遠不會被任何 CI 檢查到。
   → 本提案要求新增 `control.quality.no-silent-degradation`,tier=T-A,stage=all,
     並讓它成為 registry 中第一條 meta/軟體層 control。

3. **四個缺陷分散在 3 個檔案 2 個 package,單看每一個都像「一個小疏忽」。**
   只有把它們並排,反模式才浮現。→ KB 的價值正在於此:讓第 5 個實例被寫出來時,
   `kb_query("silent degradation partial failure")` 能直接命中。

---

## 5. 建議的 ingest 動作(給 platform)

1. `ragbase` 新增 `control.quality.no-silent-degradation`,`body_md` = 本檔 §1 + §3,
   `metadata_json.threshold_block` 不適用(非數值閾值),`source_anchor` = 本檔 + 四個實例的
   commit/檔案:行號。`confidence` 建議 `verified`(四個實例全有實測數據)。
2. `checkers/` 新增 `check_no_silent_degradation.py`,先落 **L1 / L2 / L5 / L6** 四條 T-A,
   L3/L4 登記為 T-B stub(誠實標注需要什麼才能升 T-A),L7 進 advisory。
3. `registry.py` 註冊上述 binding(會是第一條軟體契約層 control)。
4. `skills/bodesign/doctrine.md` 加一行 pre-call discipline:
   > 任何回傳集合處理結果的 tool,先看 `expected` vs `actual` 計數與 `dropped*`/`unresolved*` 欄位,
   > 再看 `ok`。**只讀 `ok` 會漏掉部分失敗。**
5. `specs/architecture.md` 在 No-silent-fallback 段落補一個反向索引,指到本 control。

---

## 6. 我(提案方)的邊界聲明

- 本檔只提供 **evidence + 分類法 + 建議規則**。是否 ingest、tier 怎麼定、checker 怎麼實作,
  是 platform 的 adjudication,我不代決。
- §3 的 T-A/T-B/T-C 分級是我依 `checkers/` 既有 DD-1 慣例**推測**的,可能與實際實作成本不符——
  請 platform 以實作可行性為準覆寫。
- 我**沒有**讀完 `checkers/registry.py` 全部實作,§4.2「registry 裡沒有軟體層 control」是依
  `architecture.md` L65 對 19 bindings 的描述推得(全部是電路領域規則),**未逐條核對**。
  若實際已有軟體層 control,請以實況為準。
