# BR_20260804g — guard C 的 pin-tip fallback box 對 1198 個共線腳位符號退化，判準恆為 False

- **Status**: **PARTIAL**（2026-09-01 重驗更新；原措辭見下方引言）— `b1fde6b` 已修主路徑。**殘留數字已隨重驗更正，逐項對照見 §10。**
  > **原 Status 措辭（2026-08-04，保留不刪）**：`PARTIAL (b1fde6b 已修主路徑) — 兩項具名殘留未解，見下`／`殘留一：6 個具名符號仍退化`／`殘留二：zero-pin 第三族 33 個（…在 :1709 更早出局…）`
- 修法：guard C 的 `rect is None` 分支接上 `graphics_rects`（body-first，見 §9）
- **殘留一：6 個具名符號仍退化 — 2026-09-01 重驗仍成立，名單逐字相符**（graphics 本身是 1-D 或不存在）
- **殘留二：zero-pin 第三族 —— 今為 37 個，非原記載的 33**（有二維繪圖本體，但在 `:1758`／原記 `:1709`，行號已漂移 — 更早出局，本修法碰不到）。同時 **§9.2 第一行 OPEN 已收斂為 219**（探針 B 的值），§9.2 第二行（gdiff 1030 vs 1027）**仍 OPEN**
- **⚠ 跨 BR 因果，歸檔時不得漏**：§9.5 原記「rect-bearing 嚴格退化 **3** 個」，今為 **1** 個 —— `Device:Earphone` 與 `Relay:COTO_3660_Split` 是**被 `BR_20260804b` 的修法 `d64bbd0`（ULP 容差）救回的**，不是本張的 `b1fde6b`。兩者 y-span 落在 `2*inset` 的 1 ULP 內；`git merge-base` 實測 `b1fde6b`(08-04 22:23) **先於** `d64bbd0`(08-05 09:04)，故 §9.5 寫下時 ULP 修法尚未存在。**那 2 個從來不是本張轄區。** 量測見 §10.1
- **✅ 本張派生數字已在 901f 修法後重取（2026-09-01，見 §11）**：**§7.6 第三族（`g 非退化`）仍為 37，一個不差**（逐符號具名比對，37 個全數未動）；`g 退化` 仍為 2（`Mechanical:Fiducial` / `Mechanical:MountingHole`）。但 **zero-pin 總數從 219 降到 39**，因為 `g_none` 那桶從 **180 降到 0**——那 180 個從來不是 zero-pin，是區塊被截斷後 pin map 變空而被誤判（機制見 `BR_20260804b §11.2`）。**新恆等式 `0 + 2 + 37 = 39`**。故 §10.2 那張表的 `zero-pin 總數 219` 與 `g_none 180` 是修法前的讀數，**而第三族 37 這個數字本身未受影響**。
- **✅ `load errors 150` 已歸零（2026-09-01，901f 修法後重取）**：§3／§9.5 記為「`KeyError` 名稱查找失敗，非本 BR 相關」——**該判定不成立**：那 150 個符號的 marker 全部在檔案內，成因是 `_balanced_block` 無引號狀態機而括號失步（`BR_20260901f` §4.2/§4.3）。修法已落（901f §10），**重取後 load_fail = 0**，P_ROOT 22583 個現 100% 解析成功。故 §3 的「load errors 150」、§9.5 的 `load_fail 150 / first = KeyError: Symbol 'TLP184xSE' not found` 都是**已修具缺陷的讀數**，不得再當基線。**⚠ 本張以 150 為母體的派生數字（§9.2 的 219、§7.6 的 37）本輪未在修法後重跑**——那 150 個現在可用，必然會流進這些桶，數字只會上升不會下降。**引用前必須先重取。**
**Filed**: 2026-08-04 by `ses_03408d1faffeKuPkQZ9Zj6gWO2` (OWNS bodesign/schematic-engine)
**Family**: schematic-engine
**Severity**: medium — 靜默失去判別力，但**非全新盲區**：這些符號在 `BR_20260804b` 的 516/513 名單之外，走的是另一條程式路徑
**Related**:
- `BR_20260804b_guard_c_inset_inverts_the_box_for_narrow_bodies_so_intrusion_check_is_blind.md`
  （同一元件、同一個 guard、**不同路徑**：804b 是 rect-bearing 符號的 inset 反轉，本張是
  no-rectangle 符號的 fallback。804b §2.4 把本張列為具名開放問題，本張是它的探測結果）
- `BR_20260804f_power_port_intrusions_is_a_declared_but_never_assigned_result_field.md`
  （同一 guard 的**儀器**缺陷；本張是同一 guard 的**判準**缺陷。修好 f 才看得見本張的效果）
- 失敗類別同族：`BR_20260804_bus_route_docstring_promises_a_channel_router_the_code_does_not_implement.md`
  （皆為「機制在場但實際不執行，與『沒有發現問題』共用同一個輸出」）

---

## 1. 一句話

`kicad_emit.py:1725-1727`，符號不畫 `(rectangle)` 時 guard C 退回用 **pin-tip extent** 當 body box。
2-pin 與單排接頭的腳位**共線**，該 extent 某一軸 span = 0，內縮後區間退化
（`bx0 >= bx1`），於是 `bx0 < ex < bx1` **恆為 False**——那個元件從此不被 intrusion 判準審視，
而輸出與「檢查過、沒有 intrusion」逐字相同。

**全庫 1198 個符號**（no-rectangle 4216 個中的 28%）處於此狀態。

---

## 2. 機制

```
:1719  rect = body_rects.get(component.lib_id)          # _body_rect() -- rect only
:1720  if rect is not None:  ...                        # 正常路徑（804b 管這裡）
:1725  else:                                            # ← 本 BR
:1726      xs = [component.x + p[0] for p in pmap.values()]
:1727      ys = [component.y - p[1] for p in pmap.values()]
:1735      _guard_c_body_box(min(xs), max(xs), min(ys), max(ys))
```

pin `at` 是腳位的**外端點**，不是本體邊界。共線腳位的外端點集合是一條**線**不是框：

```
Device:LED   pins (-3.81, 0.0) (3.81, 0.0)     ->  y-span = 0
Device:C     pins (0.0, 3.81)  (0.0, -3.81)    ->  x-span = 0
MMBT2222A    pins (-5.08,0) (2.54,5.08) (2.54,-5.08)  ->  兩軸皆非零（非共線，OK）
```

`_guard_c_body_box` 的條件式降級（804b 的修法）在這裡救不了：它只在
`span - 2*inset > 0` 時才用 `inset`，否則降級——但 **span = 0 時任何非零內縮都退化**，
降級後的內縮量仍 > 0。這與 inset 大小無關，是輸入本身沒有二維範圍。

---

## 3. 量測方法（可從本 BR 重現）

> `BR_20260804b` 記了數字沒記方法，導致 452 vs 513 的分歧耗掉一整輪。本節是那條教訓的執行。

- **符號來源**：`/usr/share/kicad/symbols/*.kicad_sym`（223 檔）
- **切 symbol 區塊**：`re.finditer(r'\n\t\(symbol "([^"]+)"', txt)`，排除 `":" in name` 與
  `_\d+_\d+$`（unit 子符號）
- **載入**：`kicad_emit.load_symbol(f"{lib}:{name}")` —— **走引擎自己的路徑**，
  故 `(extends ...)` 已由 `_flatten_extends` 展開。未展開的掃描量的是「檔案寫了什麼」，
  展開後量的才是「guard C 看到什麼」（804b 的收斂結論）
- **判準**：`_body_rect(definition) is None` ⇒ 進入本 BR 的範圍
- **box**：`_guard_c_body_box(min(xs), max(xs), min(ys), max(ys), inset=_PWR_STUB_STEP_MM/4)`
- **退化定義**：`(bx1-bx0) <= 0 or (by1-by0) <= 0` —— 與 guard 自己的嚴格不等式同一口徑
- **判別力探針**：`centre_inside`（元件中心 `(0,0)` 是否落在 box 內）與
  `far_inside`（`(1000,1000)`）
- **load failure 不吞**：150 筆全部帶型別與訊息輸出（皆為 `KeyError` 名稱查找失敗，
  非本 BR 相關）

---

## 4. 結果

```
scanned                   22582
  with rectangle          18216      <- 804b 的範圍，不在本 BR
  NO-RECT                  4216      <- 走 fallback 的符號總數（含 215 個無 pin 者）
      tip box 退化         1198  (28%)   判準恆為 False
      tip box 有判別力     2803          centre_inside=True, far_inside=False
  load errors               150      （已列出型別與訊息）
```

**⚠ 兩個口徑，都要看，不要只留一個**（1198 + 2803 = 4001 ≠ 4216）：

```
4216   走 fallback 的符號總數（`_body_rect` 回 None）
4001   其中真正有 tip extent 可談的（4216 − 215）
 215   既無 rectangle 也無任何 pin 的符號（圖框 / logo / 註記類）
       它們在 `:1709` 的 `if not pmap: continue` 就出局，從不進入判準——
       既不退化也不非退化，所以不在 1198 / 2803 任何一邊
       （**位置更正**：本 BR 先前寫 `:1728 if not xs`。那一行是**死碼**——
       `pmap` 非空時兩條路徑都保證 `xs` 非空：rect 分支給 2 個元素，fallback
       分支給 `len(pmap)` 個。故 `if not xs` 恆為 False，出局點比先前敘述更早。）
```

「多少符號走 fallback」與「多少符號有 tip extent」是**兩個問題，各有讀者**。
`deg` 與 `nondeg` 在兩種口徑下逐字相同（1198 / 2803），差的 215 全在分母。

> **每一個數字都要帶母體，否則它不是事實。** 下表全部數字（退化 1198、救回 1192、
> 三分桶）的母體是「**NO-RECT 且至少有一根 pin**」（4001）。
> 若把 215 個 zero-pin 也算進去，對應值是 **退化 1413 / 救回 1225 / 仍退化 188**。
> 兩組都對，只是回答不同問題——下一個人用另一個母體重算對不上時，
> 會先懷疑數字錯而不是口徑不同。（本 BR 與 dispatcher 各花一輪在這件事上。）

#### 退化的三分桶——`other = 0` 是本 BR 與 `804b` 不相交的證據

```
退化 1198 依成因分桶
    1-pin       112     tip extent 是一個「點」，兩軸皆 0
    共線       1086     2+ pins 全在一線上，某一軸 = 0
    其他          0     <- 決定性
CHECK  112 + 1086 + 0 = 1198 = deg        三桶互斥且窮盡
```

**`other = 0` 的意義**：沒有任何一個退化案例是「本體有二維範圍、只是被 inset 吃掉」。
若該格非零，那部分本來落在 `804b` clamp 的射程內，兩張 BR 的域就會重疊。

> 實測為 0 ⇒ **`804b`（本體太窄，clamp 可救）與本 BR（輸入缺一個維度，clamp 救不了）
> 的域嚴格互斥。** 這先前是機制推論，現由全庫窮盡計數坐實。

分桶樣本（證明分桶不是把所有東西塞進同一個桶）：

```
1-pin      Connector:Conn_01x01_Socket  npin=1  tipW=0.0  tipH=0.0
           Connector:TestPoint          npin=1  tipW=0.0  tipH=0.0
共線       Connector:Conn_01x02_Socket  npin=2  tipW=0.0  tipH=2.54
           Connector:Conn_01x06_Socket  npin=6  tipW=0.0  tipH=12.7
```


**控制組（雙向，證明探針不是對什麼都說 yes/no）**：

```
far-point (1000,1000) inside box     0 / 4216      <- 恆 False，謂詞沒有失控
非退化樣本 centre_inside             True          <- 4xxx_IEEE:4502, 74LVC1G00 ...
退化樣本                             Connector:Conn_01x01..06_Socket（單排接頭，pin 共線）
```

**e2e-led-driver-npn 真實頁的分布**（22 comps）：

```
NO-RECT  12   其中 8 個退化（Device:C / LED / D_TVS / SW_SPST，全 2-pin 共線）
                 4 個有判別力（MMBT2222A ×4，3-pin 非共線）
BLIND     9   804b 的範圍，已由 05dce34 修復
SEEN      1   USB_C_Receptacle
```

---

## 5. 修法候選與它的代價（**已量，未實作**）

同一檔案 `:528` 已有 `_graphics_bbox`，union **每一個**繪圖原語（polyline / arc / circle），
docstring 自陳是 `_body_rect` 的 superset。而 `:1169` 與 `:1567` 兩個消費者**已經**走
`graphics_rects.get(...) or body_rects.get(...)` 的降級鏈——**只有 guard C（`:1719`）單用
`body_rects`**。這個不對稱本身是本 BR 最強的一格證據：更好的 box 來源在同一次 compose 裡
已經算好了（`:968`），guard C 沒有用它。

```
_graphics_bbox 對退化者的效果
    修好                        1192 / 1198
    仍退化                          6        TestPoint / TestPoint_Small / NetTie_2 /
                                             MountingHole_Pad — 真的沒有 body，正確行為
```

**但換來源不是免費的，且代價正是上一輪被明令禁止的形狀**：

```
CONTROL — rect-bearing 符號換來源是否 no-op
    same                        17186
    differ                       1030      <- 會擴大 box
    例：4xxx_IEEE:4006  rect (-6.35,-13.97, 6.35, 1.27)
                        graphics (-6.35,-13.97, 6.35, 7.62)   y 上緣 +6.35mm
```

那 1030 個符號的 box 會**變大**，於是可能在已驗證的頁上產生**新的 raise**——
與 `BR_20260804b` 裡被否決的 `min(inset, span/4)`（1617 個非盲符號被擾動）是同一個病：
**修法不該順手提高靈敏度**。

所以修法若採 `_graphics_bbox`，必須**只在 fallback 分支使用**（`rect is None` 時），
不動 rect-bearing 路徑——那樣 CONTROL 的 1030 全部不受影響，打擊半徑收斂為
「1192 個原本無判別力的符號獲得判別力」。此形狀**未實作、未量測其在真實頁的 intrusion 差值**。

---

## 6. 為什麼不是「合理降級」

`_body_rect` 的 docstring（`:633`）稱 fallback 為 "the pin-tip extent"，語氣是有意的降級。
若它只是**偏大/偏小**的近似，那確實是合理降級。但實測顯示它在 28% 的情況下不是近似而是
**退化**——判準在該路徑上完全不執行，且與「執行了、沒發現」共用同一個輸出。

一個宣稱存在但實際不執行的檢查，比缺少檢查更貴：它讓下一個讀者停止尋找防護。

---

## 7. 誠實邊界（本 BR 沒有量什麼）

1. **沒有量真實頁的 intrusion 差值**。裁示為「只探測不修」，故未套修法重跑 compose。
   e2e-led-driver 那 8 個退化符號修好後會不會產生新 intrusion——**未知**。
2. **沒有量 1198 個退化符號分布在哪些真實頁**。全庫比例 28% 不等於真實頁比例；
   e2e-led-driver 是 8/12（67%），但單一頁不能外推。
3. **`_graphics_bbox` 只證明了「不含腳位」，未證明它是「正確的本體範圍」。**
   已證（4xxx_IEEE:4006 的 +6.35mm 來自 polyline 而非腳位；兩條 regex 在 pin 子區塊
   全庫命中 0）——但那只排除了污染，不等於它等於電氣本體。
   **本 BR 不把它列為修法前置**（裁示）：guard C 要的不是本體真值，是一個
   比現況更好的保守下界；現況是「恆為 False 的判準」，任何非退化且不含腳位的 box
   都嚴格優於它。但拿它去**別的用途**（例如當作真實本體畫圖）時必須重新驗證。
4. **`_ARC_PT_RE` 不含半徑——這是低估方向，必須可見。**
   它只取 `(start|mid|end|center ..)` 四個點，**圓弧凸出 `center` 之外的部分未計入**。
   對以 `(arc)` 畫本體外緣的符號，bbox 會**偏小** ⇒ keep-out 偏小 ⇒ **漏報而非誤報**。
   在「電氣正確性優先」的裁示下方向可接受，**但不得默默接受**：下一個人若拿
   `_graphics_bbox` 當作「本體範圍」用在需要上界的場合，會得到錯的答案。未量規模。
5. **180 個 `_graphics_bbox` 也回 None 的符號，未查是什麼。**
   實測「退化者中 g_none = 0」，所以這 180 個全在非退化或 zero-pin 區——
   不影響本 BR 的數字，但它們連一個繪圖原語都沒有，屬於第三種狀態。
6. **zero-pin 那 215 個裡，有33 個有二維繪圖本體而現行路徑取不到——未被任何 BR 涵蓋。**
   ```
   zero-pin        215
       g_none      180
       g 退化         2
       g 非退化      33   <- 有可用幾何，卻在 :1709 就 continue 了
   CHECK 180 + 2 + 33 = 215                    ✓
   CONTROL with-pin NO-RECT = 4001（未混入）  ✓
   樣本：Graphic:Logo_Open_Hardware_Large (22.25×19.96) / SYM_Arrow45_* /
         Auxiliary_Items:MountingScrew (2.54×3.81)
   ```
   **本 BR 先前寫「那 215 個連 fallback 的輸入都沒有」是不完整的**：它們沒有 pin-tip
   extent，但其中 33 個有繪圖本體。它們今天走不到 fallback 是**現行程式碼的
   路徑選擇**，不是它們沒有可用幾何。本輪修法碰不到它們（`pmap` 為空在 `:1709`
   就 `continue`），故列為**第三族**，不在本 BR 範圍，但不得讓它消失。
7. **未量真實頁的 intrusion 差值**（裁示為只探測不修，屬實作階段）。
8. **未量那 6 個仍退化者在真實頁的出現頻率**。`TestPoint` / `MountingHole` 在真實 PCB 上
   並不罕見，若常出現，「6 個」的實際影響會大於全庫比例。

---

## 8. 對 `BR_20260804b` §2.4 的處置

§2.4 把 pin-tip fallback 列為具名開放問題，並問「它是合理降級還是同型的反轉」。

**答案是二分的，不是二選一**：4216 個中 2803 個有判別力（合理降級），1198 個退化（缺陷）。
故 §2.4 **不得**整格收斂為「已查、非缺陷」，也不是整格缺陷——請改為指向本 BR。

---

## 9. 修法落地（`b1fde6b`）與兩個未收斂的口徑

### 9.1 形狀：body-first，不是 graphics-first

```python
rect = body_rects.get(component.lib_id)
if rect is None:
    rect = graphics_rects.get(component.lib_id)   # 只補這一個分支
```

`:1169` / `:1567` 消費同樣兩個 dict 卻是 **graphics 優先**，照抄會是錯的：那兩處是
**避讓**（box 越大越安全，取聯集上界正確），guard C 是**內含判定**（box 越大 = 誤報）。
同一個資料來源，兩個相反的最佳化方向。實測 graphics-first 會改動 1030 個
`graphics != rect` 的 rect-bearing 符號中的 **1026** 個 verdict。

`if rect is None` 用顯式判斷而非 `or`，是為了不讓「缺席」與「存在但 falsy」共用一條路徑。

### 9.2 兩個 OPEN：不同口徑的量測，差值未查明，**刻意不對齊**

| 量 | 探針 A | 探針 B | 狀態 |
|---|---|---|---|
| zero-pin 符號數 | 215 | 219 | **OPEN** |
| `graphics != rect`（gdiff） | 1030（含 zero-pin） | 1027（排除） | **OPEN** |

兩組都是**獨立量測**，錨定頂層符號的方式不同（B 用 `^\t\(symbol "`）。
**不把任一邊調去對上另一邊**——調整口徑去命中已知答案，會讓兩個獨立量測退化成一個，
而那正是本 fleet 反覆付學費的形狀。差值未查明，記為 OPEN。

### 9.3 方法論：量修法**直接改變**的量，不要量它下游三層的後果

真實頁 `e2e-led-driver-npn` 的 intrusion 差值是 **0**，而這**不是**紅旗。

intrusion 計數對下面兩件事回同一個答案，因此在此**沒有判別力**：

```
(a) 降級鏈生效、box 確實變了，只是沒有 port 落進新生效的 box
(b) 降級鏈根本沒接上，box 沒變
```

判別方式是**攔 `_guard_c_body_box`**，直接看 emitter 實際建出來的 box：

```
                BEFORE(HEAD)   AFTER
degenerate box       8           0
non-degenerate      14          22
(0.0, 3.81)×2  ->  (0.254, 0.762)×2
(3.81, 0.0)×5  ->  (1.27, 1.27)×5
(6.35, 0.0)    ->  (2.032, 1.778)
```

是 (a)。**一般形式**：判別力會被下游每一層稀釋，而稀釋到 0 的那一刻不會有任何提示——
它只會回一個看起來正常的數字，而那個數字同時相容於「修好了」與「根本沒接上」。
所以驗收判準要打在修法直接改變的量上，不是它的後果上。

### 9.4 mutation proof 的一格陷阱

M-A（拿掉降級鏈）若用 regex 刪掉那一行賦值，會留下一個空的 `if` 區塊 →
`IndentationError`。那是**無效 mutant 不是紅**，而 collection error 與 assertion
failure 在輸出的 `FAILED` 那行**長得一模一樣**。正解是拿 HEAD 本身當 mutant。

### 9.5 全庫實測（`b1fde6b` 的 bytes，驅動真的 emitter）

**量法**：`sys.path` 指向 `b1fde6b` 抽出的套件樹，呼叫 `emit_kicad_schematic` 本身，
spy 掛在 production helper `_guard_c_body_box` 上。**不是模擬 fallback 的演算法**——
量的是 committed bytes 實際建出來的 box。

```
boxes captured        22214    == 進得了 guard C 的符號數（mismatch batches = 0）
load_fail               150    first = KeyError: Symbol 'TLP184xSE' not found
NO-RECT                4001
rect-bearing          18213
CONTROL  NO-RECT + rect-bearing == captured                      ✓

NO-RECT 嚴格退化          6    <- 與事先寫下的驗收判準逐字相符
    Connector:TestPoint          span 0×0
    Connector:TestPoint_Small    span 0×0
    Mechanical:MountingHole_Pad  span 0×0
    MountingHole_Pad_MP          span 0×0
    Connector:TestPoint_2Pole    span 3.556×0      <- 有寬無高
    Device:NetTie_2              span 2.54×0       <- 有寬無高
⇒ 修復 4001 − 6 − (原本就非退化的 2803) = 1192，與修法前的模擬值相符

rect-bearing 嚴格退化      3    74xGxx:74LVC1GU04DRL (rect span 0×15.24)
                               Device:Earphone     (3.175×3.81)
                               Relay:COTO_3660_Split (6.35×3.81)
    這三個是 `BR_20260804b` 的既有殘留（rect 自身退化 / 浮點邊界），
    **不經過本修法的分支**（它們 `rect is not None`）。本修法對 rect-bearing
    的影響是 0，由控制流結構蘊含（`if rect is None` 才進 graphics）。
```

### 9.6 新發現：浮點邊界上有 14 個「技術上非退化、實務上等同退化」的符號

篩選時用 4 位小數的 box 得到 20 個候選，嚴格判定只有 6 個。差額 14 個**不是**捨入誤差
造成的假象，而是一個真實的邊界族：

```
Connector:Conn_01x05_Socket … Conn_01x59_Socket   （10 個，5/11/17/…/59 pin）
Device:D_Zener_Dual_CommonCathode_KAA
Device:NetTie_4_Cross
Device:Thermistor_US
Device:Varistor_US
```

以 `Conn_01x11_Socket` 為例，它進 `_guard_c_body_box` 的 x-span 是
**3.8100000000000005**，比 `2*inset = 3.81` 大 **5e-16**。於是條件式判定「夠寬」，
走 `inset` 分支而非 clamp 分支，得到寬度 **5.68e-14 mm** 的 box：

```
span = 3.81                  -> clamp 分支 -> w = 1.905     可用
span = 3.8100000000000005    -> inset 分支 -> w = 4.44e-16  形同無物
span = 3.809999999999999     -> clamp 分支 -> w = 1.905     可用
CONTROL span = 10.0 -> 6.19 · span = 1.0 -> 0.5            遠離邊界時無歧義
```

**這與 `BR_20260804b` 具名的 `Mechanical:Housing_Pad`（x-span 3.8100000000000005）
是同一族**，只是當時只發現一個。**不在本 BR 修法範圍**（本修法只決定 rect 從哪裡來，
不動 clamp），列為給 `804b` 的第三個 OPEN：條件式的邊界比較用 `>` 對浮點寬度有
5e-16 級的敏感度，而兩側結果差 15 個數量級。

### 9.7 量測本身壞了三次，形狀各不相同（**這節比數字重要**）

三次都通過了「跑完、沒有 exception、有輸出」，而輸出都像正常結果：

| # | 缺陷 | 錯誤輸出 | 為什麼看不出來 |
|---|---|---|---|
| 1 | 定義了 `Recorder` 類別要攔 `_body_boxes.append`，**從未裝上去** | JSON = `{}`（2 bytes） | 「零筆記錄」與「零個退化」共用同一個輸出 |
| 2 | `_guard_c_body_box` 回傳 `(x0, x1, y0, y1)`，我當成 `(x0, y0, x1, y1)` | 2058 個假退化 | 兩種排列都是四元組，型別、長度、數量級全部合理 |
| 3 | 用 4 位小數的 box 判退化 | 20 個（含 14 個 4e-16 寬的） | 捨入把極小正數變 0，與真正的 0 不可分辨 |

第 2 個是最危險的：它產生的不是空結果或例外，而是**一個看起來很有說服力的錯誤結論**
（「修法沒生效，2058 個仍退化」）。抓到它靠的是常識檢查——`Device:C` 與 `Device:LED`
出現在「仍退化」名單裡，而那兩個我上一輪剛量到修好了。

第 3 個的正確處置不是「改用嚴格判定重跑」，而是認識到**捨入只會把極小正數變成 0，
不會把 ≤0 變成正數**⇒ 捨入後的退化集合是嚴格退化集合的**超集**，拿它當初篩不會漏，
但必須再過一層嚴格判定。這個推理讓我不必重跑 33 分鐘。

### 9.8 效能外推與正確性推論適用同一條規則，但只有後者會被要求附控制組

我用「60 元件 / 2 個 library、0.15 秒」的試跑，外推出全庫「約 4 分鐘」。實測 33 分鐘。

錯誤的形狀與本 BR 反覆記錄的完全相同：**樣本沒有經過與 treatment 相同的管線**——
試跑只讀 2 個 `.kicad_sym`，而 emitter 每次呼叫都重讀，真跑要讀 223 個。

但它與前面所有實例有一個關鍵差別：**判準沒壞、結論沒錯，錯的是成本估計**。
而成本估計同樣會做決策——那個「4 分鐘」差點讓我不去問「有沒有哪個 variant 可以砍掉」。
（實際上 BEFORE variant 完全不必跑：`rect-bearing 改變 = 0` 由控制流結構蘊含，
且有一條專屬 mutation M-B 守著，不需要用 18213 個符號的窮舉去再證一次。）

**沒有人會要求一個效能估計附上控制組**，而正確性推論被要求了幾十次。這條不對稱
本身就是缺口：兩者都是從樣本外推到母體，兩者都會做決策。

---

## 10. 兩項殘留的重驗（2026-09-01，`ses_fa70cfaf8`，dispatcher `ses_04db7a1c5` 派工）

> 重驗的理由：`BR_20260804f`（`power_port_intrusions` 欄位從未被賦值）已於 `8d63c49` 修完並三方驗收。
> 本張 **Related** 自己寫著「修好 f 才看得見本張的效果」——這是這批殘留第一次可測。
> **本輪未修改任何生產程式碼**（裁示為「量測 + 判定」）。母體定義與完整交集表見 `BR_20260804b` §10。

### 10.1 殘留一（6 個具名符號仍退化）—— **今天仍成立，逐字相符**

在 P_GUARD（root symbol 且 pin map 非空，22214 個）上跑 HEAD 生產來源鏈，嚴格退化者 **7** 個：

```
來源 graphics（6 個，就是 §9.5 具名那 6 個）
    Connector:TestPoint              w=0      h=0
    Connector:TestPoint_Small        w=0      h=-0
    Connector:TestPoint_2Pole        w=1.778  h=-0
    Device:NetTie_2                  w=1.27   h=-0
    Mechanical:MountingHole_Pad      w=0      h=0
    Mechanical:MountingHole_Pad_MP   w=0      h=0
來源 rect（1 個，不屬本張轄區）
    74xGxx:74LVC1GU04DRL             w=0      h=11.43   <- rect 自身 span=0，804b §1.2 已具名
```

✅ **§9.5 的「6 個具名」今天完全成立**，名單逐字一致，不多不少。

#### ⚠ 但 §9.5 另一格已過期：「rect-bearing 嚴格退化 3 個」今天是 **1** 個

§9.5 列了 3 個（`74LVC1GU04DRL` / `Device:Earphone` / `Relay:COTO_3660_Split`）。今天量：

```
74xGxx:74LVC1GU04DRL    rect_span 0 × 15.24     box w=0      h=11.43   blind=True   <- 仍退化
Device:Earphone         rect_span 3.175 × 3.81  box w=1.5875 h=1.905   blind=False  <- 已救回
Relay:COTO_3660_Split   rect_span 6.35 × 3.81   box w=2.54   h=1.905   blind=False  <- 已救回
CONTROL AMS1117-3.3     rect_span 10.16 × 6.985 box w=6.35   h=3.175   blind=False
CONTROL TestPoint       graphics 0 × 0          box w=0      h=0       blind=True
```

**救回它們的是 `d64bbd0`（804b 的 ULP 容差），不是本張的 `b1fde6b`**。判別依據——兩者的 y-span 恰好落在門檻的一個 ULP 內：

```
threshold 2*inset = 3.81            ulp(3.81) = 4.440892098500626e-16
Device:Earphone        y_span = 3.8099999999999996   > T? False   within_1ulp_of_T? True
Relay:COTO_3660_Split  y_span = 3.81                 > T? False   within_1ulp_of_T? True
CONTROL 74LVC1GU04DRL  y_span = 15.24                > T? True    within_1ulp_of_T? False
CONTROL AMS1117-3.3    y_span = 6.985                > T? True    within_1ulp_of_T? False
```

且 `git merge-base --is-ancestor` 實測：`b1fde6b`（2026-08-04 22:23）**先於** `d64bbd0`（2026-08-05 09:04），
rc=0；反方向 rc=1（控制組：自己是自己的祖先 rc=0）。
⇒ §9.5 寫下那 3 個時，`d64bbd0` 還沒落地。**那 3 個從來不是本張轄區，現已被 804b 的修法清掉兩個。**

### 10.2 殘留二（zero-pin 第三族 33 個）—— **機制仍成立，但數字是 37 不是 33**

`:1758`（本張 §4 舊稱 `:1709`，行號已漂移）的 `if not pmap: continue` **今天仍在**，
本張修法碰不到那一族——機制成立。但三分桂的數字與 §7.6 不同：

| 桂 | §7.6 原記 | 本輪重量 | 差 |
|---|---|---|---|
| zero-pin 總數 | 215 | **219** | +4 |
| `g_none` | 180 | **180** | 0 |
| `g 退化` | 2 | **2** | 0 |
| `g 非退化`（第三族） | 33 | **37** | **+4** |

`CHECK 180 + 2 + 37 = 219` ✓

**這 +4 不是誰錯，是 §9.2 自己記下的那個 OPEN 現在有答案了。**
§9.2 記著「zero-pin 符號數：探針 A = 215 / 探針 B = 219，**OPEN**」並刑意不對齊。
本輪的 string-aware walker 得 **219**，**與探針 B 一致**，且有一條獨立交叉驗證：
`root 22583 + unit 23746 = 46329 = naive re.findall(r'\(symbol\s+"')`，逐字相等
⇒ root ⊎ unit 窮盡了檔案裡每一個 `(symbol "`。
⇒ **§9.2 第一行 OPEN 可收斂到 219**（探針 A 的 215 少了 4 個）。第二行（gdiff 1030 vs 1027）**本輪未量，維持 OPEN**。

#### 這 2 個 `g 退化` 首次具名（§7.6 只有計數）

```
Mechanical:Fiducial        graphics 0.0 × 0.0    would-be box w=0 h=-0
Mechanical:MountingHole    graphics 0.0 × 0.0    would-be box w=0 h=-0
```

**這兩個名字是 `BR_20260804b` §9 R9 那個交集核對的缺字塊**：804b 記的 9 個 blind 中有 8 個 graphics 來源，
其中 6 個是 §9.5 名單、另 2 個正是這對。完整交集表見 804b §10.2；**結論：沒有未建檔的第三批 blind 符號。**

### 10.3 本輪沒量什麼（誕實邊界）

1. **§9.2 第二行 OPEN（gdiff 1030 vs 1027）未量**。
2. **§7.8（6 個仍退化者在真實頁的出現頻率）仍未量**——只知 repo 內現存 14 頁均未使用它們（見 804b §10.3），
   而「現存頁面沒用到」不等於「使用頻率低」——TestPoint / MountingHole 在真實 PCB 上並不罕見。
3. **未重跑 §5 那條 `_graphics_bbox` 對 rect-bearing 符號的 1030 個差異**。
4. **未驗證第三族那 37 個接上 fallback 後會不會產生新 intrusion**（需動 code，本包裁示不修）。

---

## 11. zero-pin 分桶重取（2026-09-01，`BR_20260901f` 修法後）

> §10.2 的三分桶是在 `_balanced_block` 缺陷存在時量的，而那個缺陷會把有腳位的符號誤判成 zero-pin。
> 本節重取。**口徑逐字沿用 §10.2**（P_ROOT 中 pin map 為空者，再依 `_graphics_bbox` 三分）。

### 11.1 三分桶前後對照

| 桶 | §7.6 原記 | §10.2 重量（901f 修法**前**） | 本輪（901f 修法**後**） | 判別意義 |
|---|---|---|---|---|
| zero-pin 總數 | 215 | 219 | **39** | −180，成因見 §11.2 |
| `g_none` | 180 | 180 | **0** | 整桶消失 |
| `g 退化` | 2 | 2 | **2** | 未動 |
| `g 非退化`（**第三族**） | 33 | 37 | **37** | **未動，一個不差** |
| **CHECK** | — | 180+2+37 = 219 ✓ | **0+2+37 = 39 ✓** | 恆等式仍成立 |

**第三族 37 這個數字未受 901f 修法影響**，逐符號具名比對確認 37 個全數停在同一桶
（`zeropin_g_ok -> zeropin_g_ok`）。`g 退化` 那 2 個同樣未動（`Mechanical:Fiducial` / `Mechanical:MountingHole`）。

> **dispatcher 點名要求：若某個桶的新舊數字相同，要特別說明。**
> 這裡正是那種情形，而它**有具體理由**：那 150 個假 not-found 被修好後**全數有 pin**，
> 所以它們進的是 P_GUARD，根本不會流進 zero-pin 的任何一桶。
> **「沒改變」在這裡不是「沒量到」**——逐符號 join 顯示 `load_fail -> guard` 150 列、
> `-> zeropin_*` **0 列**。

### 11.2 為何 `g_none` 那 180 整桶消失

它們**從來不是 zero-pin**。實測（before/after 同一支探針，namespace 切換掃描器，不動磁碟）：
180/180 在修法前取到的區塊長度不同，且 180/180 的 pin map 從空變非空：

```
Connector_Generic:Conn_02x01_Row_Letter_Last  2267 -> 981   2 pins -> 0
Connector_Generic:Conn_02x04_Row_Letter_Last  4664 -> 981   8 pins -> 0
CONTROL Device:R（未移動者）              1646 vs 1646   2 pins vs 2   逐字相同 ✓
```

`bad_len` 恆為 981：這批都是 `(extends ...)` 衍生符號，區塊被截斷在衍生頭部，
於是 `_flatten_extends` 拿不到 pin、`:1758 if not pmap: continue` 把它們當成 zero-pin 排掉。
**它們沒有 graphics，是因為區塊本身不完整**——`g_none` 不是一個真實的分類，是一個缺陷的殘影。
完整交叉表見 `BR_20260804b §11.1`。

### 11.3 本節沒量什麼

1. **§7.8 仍未量**（6 個具名退化符號在真實頁的出現頻率）——依裁決維持未量，這是**未涵蓋區**。
2. **未重跑 §9.2 第二行（gdiff 1030 vs 1027）**，仍 OPEN。
3. **未驗證那 37 個接上 fallback 後會不會產生新 intrusion**（需動 code）。
4. **殘留一（6 個具名退化）本輪未重驗**，它們不在 zero-pin 族，不受本次分桶變動影響。
