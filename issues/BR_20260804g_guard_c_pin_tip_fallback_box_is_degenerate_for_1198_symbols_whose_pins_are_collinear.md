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
  NO-RECT                  4216      <- 本 BR 的範圍
      tip box 退化         1198  (28%)   判準恆為 False
      tip box 有判別力     2803          centre_inside=True, far_inside=False
  load errors               150      （已列出型別與訊息）
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
3. **`_graphics_bbox` 本身的正確性未獨立驗證**。本 BR 只證明它對退化者給出非退化 box，
   沒有證明那個 box 是**正確的本體範圍**。`4xxx_IEEE:4006` 的 +6.35mm 差異是
   「graphics 更準」還是「graphics 把腳位圖形也算進去了」——未查。
4. **`still_deg_with_graphics = 6` 未逐個確認**。抽樣看起來全是 TestPoint / MountingHole
   這類真的沒有 body 的符號（正確行為），但只看了 6 個樣本中的 6 個名字，未窮舉。
5. **未量 1-pin 符號的比例**。histogram 顯示 NO-RECT 中有 112 個 1-pin 符號，
   它們的 tip extent 是**一個點**（兩軸皆 0），必然退化，但未分開統計。

---

## 8. 對 `BR_20260804b` §2.4 的處置

§2.4 把 pin-tip fallback 列為具名開放問題，並問「它是合理降級還是同型的反轉」。

**答案是二分的，不是二選一**：4216 個中 2803 個有判別力（合理降級），1198 個退化（缺陷）。
故 §2.4 **不得**整格收斂為「已查、非缺陷」，也不是整格缺陷——請改為指向本 BR。
