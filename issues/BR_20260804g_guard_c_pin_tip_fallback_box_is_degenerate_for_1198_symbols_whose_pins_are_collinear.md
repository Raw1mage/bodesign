# BR_20260804g — guard C 的 pin-tip fallback box 對 1198 個共線腳位符號退化，判準恆為 False

**Status**: OPEN — 探測完成，修法未定（打擊半徑已量，見 §5）
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
       它們在 `:1728` 的 `if not xs: continue` 就出局，從不進入判準——
       既不退化也不非退化，所以不在 1198 / 2803 任何一邊
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
       g 非退化      33   <- 有可用幾何，卻在 :1728 就 continue 了
   CHECK 180 + 2 + 33 = 215                    ✓
   CONTROL with-pin NO-RECT = 4001（未混入）  ✓
   樣本：Graphic:Logo_Open_Hardware_Large (22.25×19.96) / SYM_Arrow45_* /
         Auxiliary_Items:MountingScrew (2.54×3.81)
   ```
   **本 BR 先前寫「那 215 個連 fallback 的輸入都沒有」是不完整的**：它們沒有 pin-tip
   extent，但其中 33 個有繪圖本體。它們今天走不到 fallback 是**現行程式碼的
   路徑選擇**，不是它們沒有可用幾何。本輪修法碰不到它們（`xs` 為空在更前面就
   `continue`），故列為**第三族**，不在本 BR 範圍，但不得讓它消失。
7. **未量真實頁的 intrusion 差值**（裁示為只探測不修，屬實作階段）。
8. **未量那 6 個仍退化者在真實頁的出現頻率**。`TestPoint` / `MountingHole` 在真實 PCB 上
   並不罕見，若常出現，「6 個」的實際影響會大於全庫比例。

---

## 8. 對 `BR_20260804b` §2.4 的處置

§2.4 把 pin-tip fallback 列為具名開放問題，並問「它是合理降級還是同型的反轉」。

**答案是二分的，不是二選一**：4216 個中 2803 個有判別力（合理降級），1198 個退化（缺陷）。
故 §2.4 **不得**整格收斂為「已查、非缺陷」，也不是整格缺陷——請改為指向本 BR。
