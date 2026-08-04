# BR_20260804b — guard C 的 inset 讓窄本體的 box 區間反轉，POWER_PORT_INSIDE_SYMBOL_BODY 對 513 個符號永遠回 False

- **Severity**: MEDIUM-HIGH（純視覺缺陷的**檢查器**失效；受影響符號含 `Device:R`——最常用的符號）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:1645-1661`（guard C / `_port_intrusions`）
- **Family**: schematic-engine
- **Owner**: ses_03408d1faffeKuPkQZ9Zj6gWO2
- **Status**: open
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

### 2.4 ❗ OPEN：`no rectangle` 那 4039 個符號走 pin-tip fallback，曝險完全未知

**這不是本 BR 的盲區，是另一條程式路徑，且它比盲區大 8 倍。**

```
guard C 看得見但盲掉的        =  516      <- 本 BR 的標的
_body_rect 回 None 而走 fallback = 4039      <- 完全未量（`:1640-1642`）
```

別把它當成冷門集合——實測兩個主流符號就在裡面：

```
Device:C                      _body_rect -> None   （以 polyline 畫極板，不畫 rectangle）
Amplifier_Operational:LM358   _body_rect -> None
```

**guard C 對這些符號不是「盲」，是根本不審視**——它們在 `:1640` 就轉彎走了
從 pin 端點重建本體的 fallback，那條路徑的寬高取自 pin 長而非真實畫形，
**它自己會不會产生同型的區間反轉或尺寸失真，兩邊都沒人量過。**

此格的歸屬：**另一個工作包**（dispatcher 已裁示排在 guard C 曝險量測之後）。
寫在這裡是為了防止下一個讀者把 **516 誤讀成全部曝險面**。

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

**Status**: open（機制 ACCEPTED；量值 disputed，非阻塞）
