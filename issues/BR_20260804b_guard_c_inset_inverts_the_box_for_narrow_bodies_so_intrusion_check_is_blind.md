# BR_20260804b — guard C 的 inset 讓窄本體的 box 區間反轉，POWER_PORT_INSIDE_SYMBOL_BODY 對 513 個符號永遠回 False

- **Severity**: MEDIUM-HIGH（純視覺缺陷的**檢查器**失效；受影響符號含 `Device:R`——最常用的符號）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:1645-1661`（guard C / `_port_intrusions`）
- **Family**: schematic-engine
- **Owner**: ses_03408d1faffeKuPkQZ9Zj6gWO2
- **Status**: open — 機制 ACCEPTED；量值 disputed；**§8 浮點邊界已修（打擊半徑實測 1 個，非原記載 14/15，見 §8.2 更正）；§1/§6 主缺陷仍 OPEN**
- **Scheduled**: 未排（P0 fixture 前置量測時撞到，未插隊施工）

---

## 1. 一句話

guard C 把本體 box **內縮** `inset = _PWR_STUB_STEP_MM/4 = 1.905 mm` 後才做 `bx0 < ex < bx1`。
本體寬度 ≤ 2×inset = 3.81 mm 時，內縮後 `bx0 > bx1`，**區間反轉**，該不等式恆為 False。

「port 沒有落在 body 內」與「這個 body 太窄所以我看不見」**共用同一個輸出**（都是不 append）。

## 2. 量測（可重跑，含控制組）

### 2.1 行為層——四格對照，控制組 RAISE

```
R1(Device:R) at (100,100)，其 pin '2' 絕對端點 = (100.0, 103.81)
把另一個元件 X1 擺在該端點上，令端點嚴格落在 X1 本體內部：

host                              TRUE body 含端點  guard C 看見  power_ports  結果
Regulator_Linear:AMS1117-3.3      True              True          True         RAISE   <- CONTROL
  (10.16 mm 寬)                                                   False        no-raise
Device:R                          True              False         True         no-raise
  (2.03 mm 寬, x 區間反轉)                                        False        no-raise
```

**控制組（第一列）RAISE，所以這個實驗有判別力。**
第一次跑時四格全 `no-raise`，原因是我把 X1 擺在 y=103.81 使端點恰落在 box 邊界（`103.810 < 103.81` = False）。
**四格同值不是「沒差別」，是「沒觸發」**——修正座標後控制組才亮。

窄本體那兩列：TRUE body **確實**包含該端點，guard C **看不見**。

### 2.2 幾何層——區間反轉的直接證據

```
Device:R at (100, 103.81)
  TRUE body box   x[ 98.984, 101.016]  y[101.270, 106.350]
  GUARD C box     x[100.889,  99.111]  y[103.175, 104.445]
                     ^^^^^^^^^^^^^^^^  bx0 > bx1
```

### 2.3 影響面——全庫掃描

> **2026-08-04 收斂完成。** 初版此節只記了數字沒記方法，導致 dispatcher 重跑得 452 而非 513，
> 且無從判斷誰對（見文末覆核節）。分歧點現已坐實為**單一維度**：`_flatten_extends`。
> 完整方法如下，任何人可重跑。

#### 方法（與數字同等重要，缺一則此節作廢）

| 維度 | 本次採用 | 為何是這個 |
|---|---|---|
| 掃描目錄 | `/usr/share/kicad/symbols/*.kicad_sym`（223 檔）| KiCad stdlib，引擎預設 `DEFAULT_SYMBOL_DIR` |
| symbol 切塊 | **深度解析，只取 lib 深度 1 的 `(symbol "X"`** | regex 掃 `(symbol "` 分不出 part 與其 unit 子區塊（`R_0_1`），會重複計數 |
| 擷取器 | `_body_rect`（`kicad_emit.py:542`）| guard C 於 `:879` 實際呼叫的就是它；**不是** `_graphics_bbox` |
| **是否展開 extends** | **是**——`_flatten_extends(blk, name, src)` | **這是分歧的唯一成因**，見下 |
| 盲區判準 | 該軸長度 `<= 2*inset = 3.81` | `:1647` 內縮後 `bx0 > bx1`，`:1659` 恆 False |

**為何必須展開 extends**：`load_symbol` 在 `:383` 對每個 block 呼叫 `_flatten_extends`，
**所以引擎看到的永遠是展開後的**。而 `(extends ...)` 的衍生符號自身不畫 rectangle——
未展開時它被歸進 `no rectangle`，展開後才顯出它繼承來的本體。
**未展開的掃描量的是「檔案裡寫了什麼」，展開後量的才是「guard C 看到什麼」。**

#### 結果（同腳本、只變動 flatten 一個維度）

```
inset = 1.905 mm   (blind when axis <= 3.81)

variant                 scan    hasR    sees    bX   bY   bB   BLIND    noR
A raw (no flatten)     21437    7882    7430   373   27   52     452  13555
B FLATTENED (engine)   21437   17398   16882   407   29   80     516   4039
```

**A 逐項對上 dispatcher 的獨立重跑**（他得 452 / 373 / 26 / 53 / 13744）——
所以他量的是未展開版，我初版量的是展開版，**兩邊都沒算錯，量的是不同東西**。

**B 是引擎的真實視角，`TOTAL BLIND = 516`。** 初版報 513，差 3；`scan` 21437 vs 22583 的差距
來自初版用 regex 掃 `(symbol "` 而含入了 unit 子區塊。**以 516 為準，513 作廢。**

熱路徑符號兩個變體一致（故此結論不受 flatten 影響）：

```
symbol                          has_rect      w        h    BLIND   這個樣本證明什麼
----------------------------------------------------------------------------------
Device:R                        yes       2.032    5.080   True    盲區（x 軸反轉）
Device:R_Small                  yes       1.524    3.556   True    盲區（兩軸全盲）
Regulator_Linear:AMS1117-3.3    yes      10.160    6.985   False   CONTROL —— 判準真的會說「不盲」
MCU_ST_STM32F4:STM32F407VETx    yes      40.640  134.620   False   CONTROL —— 同上，寬本體
flatten_errors = 0                                                 展開步驟本身未吞任何例外
```

> **❗ 控制組更正（2026-08-04，dispatcher 指正）。** 初版此處用 `Device:C` 當控制組並寫「不在盲區」——
> **那是壞的**。`Device:C` 的 `_body_rect` 回 `None`（它以 polyline 畫極板，不畫 rectangle），
> 於 `:1640-1642` 就走了 pin-tip fallback——**它從頭到尾沒有被 guard C 的謂詞審視過**。
>
> 所以「不盲」與「不在管轄內」共用了那個控制組的輸出。拿一個**從未執行該判準的樣本**
> 去證明該判準有判別力，判別力是零。現改用寬本體符號：它們 `has_rect=yes` 且回 `BLIND=False`
> **並帶實際尺寸**，那才證明這個謂詞真的會對某些輸入說不盲。

腳本落點：`$XDG_RUNTIME_DIR/guardc-scan/fast.py`（scratch，不入版控；
上表三欄 + 兩個 variant 的定義即其等價描述，可據以重寫）。

**2.8% 這個數字會誤導，因為分布不是隨機的。** 名單裡有：

```
Device:R                     body= 2.03 x  5.08   xw=-1.78
Device:R_Small               body= 1.52 x  3.56   xw=-2.29  yh=-0.25  (兩軸全盲)
Connector:Conn_01x01..10_Pin body= 0.86 x  N      xw=-2.95
74xGxx:74LVC1GU04DRL         body= 0.00 x 15.24   xw=-3.81
```

`Device:R` 是任何電路圖裡出現次數最多的符號。**盲區不在冷門角落，在最熱的路徑上。**

### 2.4 ✅ CLOSED（已探測）：`no rectangle` 的 pin-tip fallback —— 答案是**二分的**，見 `BR_20260804g`

**這不是本 BR 的盲區，是另一條程式路徑，且它比盲區大 8 倍。**

```
guard C 看得見但盲掉的        =  513      <- 本 BR 的標的（口徑見 §3）
_body_rect 回 None 而走 fallback = 4216      <- 本節的標的（`:1725-1727`）
```

別把它當成冷門集合——實測兩個主流符號就在裡面：

```
Device:C                      _body_rect -> None   （以 polyline 畫極板，不畫 rectangle）
Amplifier_Operational:LM358   _body_rect -> None
```

**guard C 對這些符號不是「盲」，是根本不審視**——它們在 `:1725` 就轉彎走了
從 pin 端點重建本體的 fallback。

#### 探測結果（2026-08-04，`ses_03408d1faffe`）：問題本身是錯的形狀

本節原本問「那條路徑是合理降級，還是同型的反轉？」——**它預設只有一個答案。實測有兩個**，
分界是**腳位共不共線**：

```
NO-RECT                4216
    tip box 退化       1198  (28%)   判準恆為 False  -> 缺陷
    tip box 有判別力   2803          centre_inside=True, far=False -> 合理降級
```

機制：pin `at` 是腳位**外端點**，共線腳位的外端點集合是一條**線**不是框，某軸 span = 0。

```
Device:LED   (-3.81,0) (3.81,0)                  y-span = 0   -> 退化
Device:C     (0,3.81) (0,-3.81)                  x-span = 0   -> 退化
MMBT2222A    (-5.08,0) (2.54,5.08) (2.54,-5.08)  兩軸皆非零  -> OK
```

**本 BR 的 clamp 在那裡救不了，而理由界定了本 BR 的適用範圍**：條件式降級只在
`span - 2*inset > 0` 時用 `inset`，否則降級——但 **span = 0 時任何非零內縮都退化**。
與 inset 大小無關。

> **本 BR 處理的是「本體太窄」（幾何退化，可調）；`804g` 處理的是「輸入沒有二維範圍」
> （資料模型退化，不可調）。同一個症狀（box 退化）兩個成因——混為一談會讓 clamp 看起來失效。**

完整量測、方法、修法候選與其打擊半徑：**`BR_20260804g_guard_c_pin_tip_fallback_box_is_degenerate_for_1198_symbols_whose_pins_are_collinear.md`**。

**本節原本的警告仍然成立且更強了**：不要把 513 讀成全部曝險面。真實頁
`e2e-led-driver-npn`（22 comps）的三態是 BLIND 9 / NO-RECT 12 / SEEN 1——
**guard C 修好 inset 之後仍有 12 個元件走另一條路徑**，其中 8 個的 box 是退化的。

### 2.5 ⚠ 判讀更正：修法恢復的是 43%，不是「intrusion 檢查」

**這一節更正的是本 BR 標題與 §1 讀起來的意思**，不是補充。§2.4 用全庫統計說「516 不是全部曝險面」；
下面是一個**真實頁**的實例，它比統計更能說明修法的實際涵蓋範圍。

`experiments/e2e-led-driver/C03-EE/e2e-led-driver-npn.spec.json`，22 個元件，
以引擎同路徑（`load_symbol`，含 `_flatten_extends`）逐一分類：

```
state      count  lib_ids                                        clamp 碰得到？
--------------------------------------------------------------------------------
BLIND          9  Device:R ×8, Device:Polyfuse ×1                 YES ← 本 BR 的標的
NO-RECT       12  Device:C ×2, Device:LED ×4, MMBT2222A ×4,       NO  ← §2.4 那條路徑
                  D_TVS ×1, SW_SPST ×1
SEEN           1  Connector:USB_C_Receptacle (20.32×35.56)        n/a ← 一直看得見
```

控制組（dispatcher 獨立重跑，非採信 handler 回報）：`Device:R` blind=True /
`AMS1117` blind=False / bogus lib_id raise `FileNotFoundError`。

**這頁 22 個元件裡，guard C 目前真正看得見的只有 1 個。**

於是修法的正確描述是：

> clamp 讓 **9/21 (43%)** 個不可見元件進入判準；其餘 **12/21 (57%)** 是 NO-RECT，
> 修完仍然**從未被判準執行過**。

**任何引用本 BR 的差值報告都必須帶分母。** 「修好後新增 0 個 intrusion」在不帶分母時
讀起來像「這個檢查現在是乾淨的」，實際意思是「這個檢查恢復了 43% 之後，那 43% 裡沒有東西」。

**這一節本身也是 §2.4 那句警告的實例**——它警告的誤讀（把 516 當全部曝險面）
在本 BR 自己的敘事裡就存在，直到有人拿一個真實頁去數才顯出來。

### 2.6 ⚠ `516` 這個數字有兩個口徑，引用時必須說明用哪個

§2.3 的 `TOTAL BLIND = 516` 用的判準是 `bx0 >= bx1`（**含**零寬）。改用 `>`（**不含**零寬）得 **502**。

```
OLD rule inverted, 判準 >=  : 516     <- §2.3 與本 BR 全文的口徑
OLD rule inverted, 判準 >   : 502
差                          :  14     <- 恰好零寬的邊界帶
```

那 14 個（如 `Connector_Audio:SpeakON_NL2`）的 unclamped box 寬度**恰好是 0**，
所以 `bx0 < ex < bx1` 對它們同樣不可滿足——**它們是盲的，`>=` 口徑才是對的**。

記在這裡的原因與 §2.3 六欄方法表相同：**452 vs 513 那次分歧的根因是「數字記了、方法沒記」**，
而口徑是方法的一部分。一個沒有註明口徑的 `516`，下一個人用 `>` 重跑會得到 502，
然後花一輪去找不存在的錯誤。

## 3. 這與 BR_20260723b 的關係（方向相反，不是同一件事）

723b 抱怨的是 **誤報**：`power_ports=False` 時仍 raise。
本 BR 是 **漏報**：本體窄時，即使真的侵入也不 raise。

723b 的原始場景是 73 個端點落在 **U1**（MCU，40.64 mm 寬）——guard C **看得見**那個，所以它 raise 了。
一致，不矛盾。

**723b claim #1 現已不重現**（見 §4），但它不是被這個缺陷掩蓋的——是另一條修法讓它成立了。

## 4. 順帶：BR_20260723b claim #1 已不重現

723b 問：「`power_ports=False` 時是否應完全跳過 power-port 端點放置與 `_port_intrusions` 檢查？」

**現況：是，而且已經是了。** 五個 `power_endpoints.append` 全部被 `if kind is not None` 保護
（1388/1401/1427/1444/1472），而 `power_ports=False` ⇒ `kind = None`（1386/1399/1426/1442/1470）。
`power_endpoints` 保持空 ⇒ 1649 的迴圈零輪 ⇒ 不可能 raise。

行為層印證：§2.1 表中 `power_ports=False` 兩列皆 `no-raise`，**且控制組 True 那列 RAISE**，
所以這不是「沒觸發」。

**但這是枚舉不是全稱證明**：我證的是「這五個 append 全被保護」，不是「不存在第六條路徑」。
`grep -n 'power_endpoints' ` 顯示除這五處外只有讀取點（1497/1503/1561/1649）。

723b 的 claim #2（stub-orientation defect，端點落在相鄰 body 內）**未驗**——它需要 723b 原始的
aiguard MCU spec，而該檔案在 `/run/user/1000/mcu-core-compose/`（scratch），**現已不存在**。

## 5. 明確不是缺陷 / 不要動

- **`inset` 的存在是對的**。註解（1632-1633）說明理由：power-port 端點合法地貼著 body 邊緣，
  不加容差會把正常貼邊誤判成侵入。**修法不是拿掉 inset。**
- **fail-loud 的預設（`power_port_gate="error"`）是對的**，不要改成 warn。
- **`ref == host_ref` 跳過自身宿主是對的**（1657），BGA 內部球腳合法落在自己 body 內。

## 6. 建議修法（需 dispatcher 裁示）

核心：**inset 不得把區間吃成空的**。內縮量應對每軸夾在該軸長度的一半以下：

```python
ix = min(inset, (max(xs) - min(xs)) / 2 - EPS)
iy = min(inset, (max(ys) - min(ys)) / 2 - EPS)
```

或改用「向內 clamp 後若區間為空則退回 0 容差」。**兩者都會讓目前 513 個符號從不可見變可見，
因此必然新增 intrusion 回報**——這是修好檢查器的預期後果，不是回歸。

**必須先量後改**：修法會讓既有 aiguard CCM 各頁冒出新的 intrusion，而預設 gate 是 `error`。
所以修法要跟一次「修好後有多少頁會從 pass 變 raise」的量測，否則會把一個檢查器修復變成一次交付中斷。

## 7. 驗收判準

1. §2.1 四格重跑：窄本體 + `power_ports=True` 必須從 `no-raise` 變 **RAISE**
2. 寬本體控制組維持 RAISE（不得因修法而失效）
3. `power_ports=False` 兩格維持 `no-raise`
4. mutation proof 三態：把 clamp 改壞 → 測試轉紅 → 還原 → 位元組相同
5. 全庫掃描的 `TOTAL BLIND` 降至 0，且 `guard sees it` 不減少

## Related

- `BR_20260723b_power_ports_false_not_bypassed.md`
  （**同一段 code（guard C），方向相反**：723b 是誤報、本 BR 是漏報。且本 BR §4 記錄 723b claim #1
  已不重現，claim #2 因輸入檔遺失而未驗）
- `BR_20260804_bus_route_docstring_promises_a_channel_router_the_code_does_not_implement.md`
  （**同族 failure class**：宣稱存在的護欄實際不生效。前者是 docstring 承諾 code 沒有的演算法，
  本 BR 是 code 有檢查但判準恆假——兩者都讓讀者停止尋找防護）
- `issues/closed/BR_20260710_*`（guard C 所針對的原始純視覺 defect，本 BR 指出其檢查器有盲區）

---

## Dispatcher 覆核（2026-08-04，`ses_04db7a1c5` 親手重跑）

### 機制層：確認，逐行對得上

`kicad_emit.py:1645` `inset = _PWR_STUB_STEP_MM / 4.0` = **1.905**（`:2008` `_PWR_STUB_STEP_MM = 7.62`）。
`:1647` 內縮後存進 `_body_boxes`，`:1659` 判 `bx0 < ex < bx1 and by0 < ey < by1`。
軸長 ≤ 3.81 mm ⇒ `bx0 > bx1` ⇒ 該不等式恆為 False。**成立。**

### 數字層：不重現，且分歧點是「方法沒被記錄」

我用**引擎自己的 `_body_rect`**（即 guard C 於 `:879` 實際呼叫者）掃 `/usr/share/kicad/symbols/*.kicad_sym`
（223 檔）重跑：

| 指標 | BR 所報 | Dispatcher 重跑（`_body_rect`） | Dispatcher 重跑（`_graphics_bbox`） |
|---|---|---|---|
| symbols scanned | 22583 | 22431 | 22431 |
| has rectangle | 18217 | **8687** | 10210 |
| guard sees it | 17704 | 8235 | 9310 |
| BLIND x only | 407 | 373 | 447 |
| BLIND y only | 26 | **26** | 163 |
| BLIND both | 80 | 53 | 290 |
| **TOTAL BLIND** | **513** | **452** | 900 |
| no rectangle | 4216 | 13744 | 12221 |

**兩個擷取器都不產生 513。** 排除過的假設：計數單位差異（parent 22431 + nested unit 23898 = 46329，
不是 22583，故非「含 unit 子區塊」）。

`y only = 26` **兩邊精確相符**，且 `Device:R` / `Device:R_Small` 在我的掃描中同樣落在盲區
（控制組：`Device:C`=False、`Regulator_Linear:AMS1117-3.3`=False，證明判準有判別力不是全命中）。
所以**方向與熱路徑一致，只有量值分歧**。

**這格本身是缺陷**：BR 記了數字沒記方法（掃了哪個目錄、用哪個擷取器、如何切 symbol 區塊），
因此**該數字無法從 BR 本身重現**。一個無法重現的數字在下一個讀者眼中與一個經過驗證的數字長得一樣。
往後任何全庫掃描的數字，**掃描腳本或其等價描述必須與數字同時落地**。

### 裁決

- **機制、方向、熱路徑（含 `Device:R`）：ACCEPTED**，這是真缺陷，優先序由它決定不受量值分歧影響。
- **`513` 標為 disputed**，待 owner 補記方法後重新收斂；本節兩個數字並列保留，不擇一。
- **`no rectangle` 那格（BR 稱 4216、我得 13744）同樣待重新收斂**——它決定 pin-tip fallback
  路徑（`:1640-1642`）的曝險規模，而該路徑**兩邊都未測**。

**Status**: open（機制 ACCEPTED；量值 disputed，非阻塞；另見 §8 浮點邊界）

---

## 8. 第三個 OPEN：inset 的邊界比較在浮點上失效，14 個符號拿到 4e-16 mm 寬的 box

> 這一節由 dispatcher（`ses_04db7a1c5`）於 2026-08-04 寫入。
> 來源是 `BR_20260804g` 全庫量測的副產物（`ae8589a` §9.6），而它指向本張。
> **寫進來的理由**：那邊寫了「列為給 804b 的第三個 OPEN」，但本檔一個字都沒提
> （控制組：`grep -c 'guard C\|inset'` 回 **29** 證明 grep 讀得到檔，
> 而 `Housing_Pad` / `3.8100000000000005` / `浮點` / `float` 全部回 **0**）。
> **一個寫在 A 檔裡、指定給 B 檔的殘留，B 的讀者永遠看不到**——
> 這與本 fleet 反覆付學費的形狀同族：資訊存在，只是不在會被讀到的地方。

### 8.1 現象

`_guard_c_body_box` 用「寬度是否大於 `2*inset`」決定走 inset 還是 clamp。
寬度恰好落在邊界上且帶浮點誤差時，它選錯邊：

```
span 3.81                  -> clamp -> w = 1.905       可用
span 3.8100000000000005    -> inset -> w = 4.44e-16    形同無物
span 3.809999999999999     -> clamp -> w = 1.905       可用
CONTROL span 10.0 -> 6.19 ・ span 1.0 -> 0.5           遠離邊界無歧義
```

比 `2*inset` 大 **5e-16**，就足以讓条件式判定「夠寬」而走進 inset 分支。

### 8.2 受影響的 14 個（全庫實測）

> ## ⚠ 本節已被實測否證。以下方框內是**原始記載**，保留不刪；更正在下方 §8.2a。

```
Conn_01x05_Socket · Conn_01x11_Socket · Conn_01x17_Socket · … · Conn_01x59_Socket   （10 個）
D_Zener_Dual_CommonCathode_KAA · NetTie_4_Cross · Thermistor_US · Varistor_US
```

**`Mechanical:Housing_Pad`（本張原本具名的那個）span 也是 `3.8100000000000005`**
⇒ 它不是孤例，是這個 15 元素族的第一個被發現者。

### 8.2a ⚠ 更正（2026-08-04，兩方獨立實測）：生產口徑下是 **1 個**，不是 14/15

> 更正者：dispatcher `ses_04db7a1c5`。上方 §8.2 的名單**保留不刪**——
> 它怎麼來的，本身就是這張 BR 在講的那件事的證據。

`§8.2` 的 14 個名單來自 `804g` 的一支初篩（4 位小數判退化），**未經生產路徑重驗**。
owner（`ses_03408d1fa`）與 dispatcher 各自獨立掃描，兩份互不知對方數字，結論一致：

```
TREATMENT  §8.2 具名 9 個的 _body_rect（生產路徑 root-level lib_id）
  Conn_01x05/11/17/59_Socket · Thermistor_US · Varistor_US
  D_Zener_Dual_CommonCathode_KAA · NetTie_4_Cross     -> rect = None（8 個，根本沒有 rect）
  Mechanical:Housing_Pad -> 3.8100000000000005        <- 唯一有 rect 且落在帶內的
CONTROL    Device:R rect span 2.032 -> band=False
CONTROL    Device:ZZ_NoSuch_9999   -> KeyError（loud，證明枚舉不會靜默吞）
```

**`8/9` 的 `_body_rect` 回 `None`** ⇒ 它們根本走不到 §8.1 那個邊界比較，
初篩把它們算進來是因為那支探針從別的來源取 span。

#### 為什麼兩個都合理的量法會回不同答案（口徑，必須連同數字一起引用）

dispatcher 另跑了一支**三分支**掃描（guard C 的唯一呼叫點 `kicad_emit.py:1788`
的 `xs/ys` 有三個來源：`rect` / `graphics_rects` fallback / pin-tip fallback，
而只掃 rect 那一支會讓「不在母體」與「不受影響」共用同一個輸出）：

```
symbols=46030  load_fail=299
sources: rect 29737 / graphics 7056 / pintip 8681 / nopins 556
band_hits = 7      <- 子單元口徑
  Mechanical:Housing_Pad          x  rect
  Mechanical:Housing_Pad_0_1      x  rect
  Analog_Switch:NX3L4051PW_1_0    x  pintip
  Connector:RJ45_JK00177_1_1      x  graphics
  Switch:SW_Rotary_2x6/3x4/4x3_0_1   x  graphics
CONTROL  synthetic T+tol -> True ／ far 10.0 -> False ／ far 40.64 -> False ／ 母體>10k -> True
```

**7 個裡 6 個是子單元名（`_0_1` / `_1_0`）。** 用生產真正解析的 root-level lib_id 重驗：

```
Analog_Switch:NX3L4051PW      sx=17.78                 band=False
Connector:RJ45_JK00177        sx=30.48                 band=False
Switch:SW_Rotary_2x6/3x4/4x3  sx=17.78                 band=False
Mechanical:Housing_Pad        sx=3.8100000000000005    band=True   <- 唯一
```

⇒ **生產口徑 1、子單元口徑 7、4 位小數初篩 20（含 14 個 4e-16 寬的捨入假象）。**
三個數字都是真的，量的不是同一件事。**引用任何一個時必須同時說明口徑**——
這正是 §8.2 原記載出錯的機制：一個沒有標註口徑的數字，被下一個人當成另一個口徑的答案。

### 8.2b ✅ 修法已落地

容差 = `math.ulp(2*inset)`。**不是選來的數**：`3.8100000000000005 - 3.81`
恰等於 `math.ulp(3.81)`，即離門檻最小的可表示一步 ⇒ 那個 span 是
「本體正好 `2*inset` 寬」的捨入產物，而**比 1 ULP 更小的容差不可表示**，
所以這是邊界修正，不是可調參數。

結構保留 CONDITIONAL（`min()` 形式維持否決——既有 docstring 記錄它誤傷 1617 個）。

dispatcher 八格覆核全 PASS，含**獨立重做**三條 mutation（各 `SUBSTITUTIONS=1`、
紅在三個不同斷言、還原後 byte-identical）：
M-A 移除容差 → 紅在「box 寬度 0.0」（缺陷本身）／
M-B 容差放寬 `abs_tol=7.0` → 紅在反方向誤傷（`span=10.0` 被推進 clamp）／
M-C fixture 改指 `Device:R` → 紅在 fixture 判別力。

### 8.3 為什麼不屬於 `BR_20260804g`

`804g` 的修法只決定 **rect 從哪來**（`body_rects` 還是 `graphics_rects`），
**不動 clamp 邏輯**。這 14 個符號的 rect 本身存在且非退化，
問題發生在拿到 rect **之後**的邊界比較——那正是本張的標的。

### 8.4 未量

> ⚠ 下列兩項在 2026-08-04 均已完成，保留原文並在各項標註結果。

- ~~**這 14 個在真實頁上的曝險未量**~~ → **已量，且成因已分辨**。
  `e2e-led-driver-npn` 修法前後 `captured 22 / degenerate 0 / intrusions 1`，delta = 0。
  **「修法沒生效」與「該族不在此頁」共用這個 0**，所以另加有判別力的探針：
  此頁 8 個 distinct symbol **無 `Housing_Pad`**；spy 量到 44 個 axis，
  落在一-ULP 帶內者 **0** 個（distinct spans 全部遠離門檻）。
  ⇒ 是後者。**此頁對本修法零曝險，不是紅旗。**
  兩個 variant 確實不同（liveness：`before_isclose=0` / `after_isclose=1`）。
- ~~**修法未裁示**~~ → **已裁示並落地**，見 §8.2b。反方向誤傷面**已量**：
  生產口徑下 `inset→clamp` 的移動恰 1 axis / 1 symbol（即 `Housing_Pad` x 本身），無其他。
  控制組非空性：庫內 exact `40.64` 命中 **768 axes**，全部未動。
  誠實邊界：`10.0` 在庫內 exact 命中 **0 axes**，故它只是合成控制組（直呼 helper），
  不像 `40.64` 有庫內樣本背書。

### 8.5 §8 這格的殘留

**無。** §8 已收斂——名單更正（§8.2a）、修法落地（§8.2b）、兩項未量補齊（§8.4）。
本張 BR 仍 OPEN 的是 **§1/§6 的主缺陷（量值 disputed）**，與 §8 是不同的標的。
