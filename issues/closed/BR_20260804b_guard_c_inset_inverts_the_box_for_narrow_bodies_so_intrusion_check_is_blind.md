# BR_20260804b — guard C 的 inset 讓窄本體的 box 區間反轉，POWER_PORT_INSIDE_SYMBOL_BODY 對 513 個符號永遠回 False

- **Status**: **FIXED**（2026-09-01；§9 三項殘留全數收斂，量測見 §10。前兩版措辭保留於下方引言）— **§1 主缺陷已修**（`05dce34` + `d64bbd0`，重驗見 §1.1）；**§6 建議修法已被實測否決（SUPERSEDED，見 §6.1，照著施工會誤傷 1617 個從未盲的本體）**；§8 浮點邊界已修（打擊半徑實測 1 個，非原記載 14/15，見 §8.2 更正）。
  - **⚠ 引用本張任何 blind 數字前必讀（口徑，不是 delta）**：`9` 與 `7` 量的是**兩個母體**，不是修法前後。**口徑 A**（每個能算出 box 的 root symbol，不過 `:1758` 閘）= **9**；**P_GUARD**（pin map 非空、HEAD 生產路徑真正審視者）= **7**。差的 2 個是 `Mechanical:Fiducial` 與 `Mechanical:MountingHole`（zero-pin，生產上永遠不會被建 box）。`7 + 2 = 9` 已由同一輪掃描坐實（§10.2）。**把兩者相減會得到一個不存在的回歸。**
  - **殘留三項的收斂結果**：C8 各頁曝險**已量**（母體 = repo 內 14 個 `.kicad_sch`、184 個已擺放元件，BLIND = **0**，附六態 codomain 控制組，§10.3）；R9 交集**已核對完畢**（9 個 blind 全數有轄區，**「兩者都不在」= 空集合**，§10.2）；N3 母體數分歧**已裁定為口徑問題**（22583 可由兩個獨立方法重現並通過交叉驗證；22431 與 21437 判為**無法重建**而非錯誤，§10.1）。
  - **⚠ 未涵蓋區，不得被 FIXED 吞掉**：`BR_20260804g §7.8`（那 6 個仍退化符號在真實頁的出現頻率）**仍未量**。本張只證明「repo 內現存 14 頁沒用到它們」，而**「現存頁面沒用到」≠「使用頻率低」**——`TestPoint` / `MountingHole` 在真實 PCB 上並不罕見。
  - **✅ guard C 分桶已在 901f 修法後重取（2026-09-01，逐符號具名對照，見 §11）**：`P_GUARD 22214 → **22544**`、`P_ZEROPIN 219 → **39**`、`load_fail 150 → **0**`，恆等式 `22544 + 39 + 0 = 22583` 仍成立。**兩桶各增分開報**：那 150 個假 not-found 全數進 P_GUARD（非分流），另有 **180 個本來被誤判為 zero-pin 的符號也進了 P_GUARD**（+150 +180 = +330）——那 180 是 901f §4.2 「長度錯誤 182」中的一部分，區塊被截斷後 pin map 變空而落錯桶，机制已具名坐實（§11.2）。**未有任何符號反向移動。**
  - **⚠ §10.1 的 `CHECK P_GUARD 22214 + P_ZEROPIN 219 + load_fail 150 = 22583` 是修法前的讀數**，三項均已過時（但恆等式本身成立，不刪）。引用請改用 §11 的新值。
  > **前版 Status 措辭（2026-08-05，保留不刪）**：`**PARTIAL**（2026-08-05 更正）— §1 主缺陷已修…**殘留（故為 PARTIAL 而非 closed）**：§6 的「各頁曝險」仍 **UNMEASURED**（只量 1 頁）；HEAD 殘留 9 個 blind 中 8 個為 graphics 來源、轄區在 BR_20260804g 但**未核對是否已在其名單內**；母體數三方分歧未裁定。逐項見 §9。`
  > **原 Status 措辭（2026-08-04，保留不刪）**：`open — 機制 ACCEPTED；量值 disputed；**§8 浮點邊界已修（打擊半徑實測 1 個，非原記載 14/15，見 §8.2 更正）；§1/§6 主缺陷仍 OPEN**`
- **Closed**: 2026-09-05 by ses_04db7a1c5ffelvbxyLP1p6xlRH（landed 驗收：commit 05dce34+d64bbd0 存在且改 kicad_emit.py，控制組 deadbee→fatal 反證）
- **Severity**: MEDIUM-HIGH（純視覺缺陷的**檢查器**失效；受影響符號含 `Device:R`——最常用的符號）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:1645-1661`（guard C / `_port_intrusions`）
- **Family**: schematic-engine
- **Owner**: ses_03408d1faffeKuPkQZ9Zj6gWO2
- **Scheduled**: 未排（P0 fixture 前置量測時撞到，未插隊施工）

---

## 1. 一句話

guard C 把本體 box **內縮** `inset = _PWR_STUB_STEP_MM/4 = 1.905 mm` 後才做 `bx0 < ex < bx1`。
本體寬度 ≤ 2×inset = 3.81 mm 時，內縮後 `bx0 > bx1`，**區間反轉**，該不等式恆為 False。

「port 沒有落在 body 內」與「這個 body 太窄所以我看不見」**共用同一個輸出**（都是不 append）。

### 1.1 ⚠ ALREADY-FIXED（2026-08-05 重驗，`ses_030202fa9` 隔離量測 + `ses_03000bf24` 覆算）

> **上方 §1 是原記載，保留不刪。** 它記述的是**修法落地前**的行為；記載的演變本身就是這張 BR 在講的那件事的證據。
> **要區分兩件事**：**觸發前提消失了，機制沒有。**

**修掉它的兩顆 commit**（本 session 以 `git log -1` 逐顆驗過 sha 與標題存在，控制組：假 sha `deadbee` → `fatal: unknown revision`，rc=128）：

| sha | 標題 |
|---|---|
| `05dce34` | `fix(guard-c): conditional inset degrade + assign the intrusion field it promised` |
| `d64bbd0` | `fix(eda-bridge): guard C -- treat a span within one ULP of 2*inset as not wide enough` |

`_guard_c_body_box`（`kicad_emit.py:558`）現在是 **CONDITIONAL**，不再是固定內縮（`:664-665`，本 session 直接讀原始碼確認）：

```python
ix = inset if _wide_enough(x1 - x0) else (x1 - x0) / 4.0
iy = inset if _wide_enough(y1 - y0) else (y1 - y0) / 4.0
```

#### 原記載 / 重驗（2026-08-05）並列

| 格 | 原記載 | 重驗（HEAD） | 判定 |
|---|---|---|---|
| §2.2 `Device:R` 的 GUARD C box | `x[100.889, 99.111]`（**區間反轉**） | **`x[99.492, 100.508]`，w=1.016，`inverted=False`** | 已修 |
| §2.5 真實頁 `e2e-led-driver-npn` 的 BLIND | **9** | **0** | 已修 |
| 機制：guard 只有 append / 不 append 兩態、無第三態（`:1801-1814`） | 成立 | **仍然成立** | **未修，也不打算修** |

**重驗的決定性證據**——真實頁 `experiments/e2e-led-driver/C03-EE/e2e-led-driver-npn.spec.json`（本 session `test -f` 確認存在；控制組假檔名回 MISSING），spy 掛**生產 helper**（非重寫的等價實作）：

```
          boxes_built   DEGENERATE(blind)   intrusions
HEAD           22               0                1
PRE-FIX        22              17                1
```

`DEGENERATE` 兩個 variant 不同（17 → 0）⇒ **這個探針有判別力，不是「兩邊都 0 所以看不出差別」。**

#### 覆算（`ses_03000bf24`，直接呼叫生產 `_guard_c_body_box`，非採信上游回報）

```
Device:R body x[98.984, 101.016]  -> guard C x[99.492, 100.508] w=1.016 inverted=False
CONTROL AMS1117ish 10.16 x 6.985  -> x[1.905, 8.255] y[1.905, 5.080] inverted=False   （寬本體，走 inset 分支，未被修法擾動）
CONTROL 74LVC1GU04DRL 型 span=0.0 -> w=0.000000                                        （rect 本身退化，任何 inset 規則都救不了）
```

**⇒ §1 的觸發前提（固定 inset 造成區間反轉）已不存在；§1 的機制描述（兩態共用輸出）仍為真。不要把整張 BR 讀成「完全不成立」。**

### 1.2 §1 標題的「513 個符號」——三個口徑都是真的，但沒有一個是 513

| 口徑 | pre-fix blind | HEAD blind | 定義 |
|---|---|---|---|
| **A 生產全鏈** | 1882 | **9** | root-level lib_id（paren-depth 追蹤，排除 `_0_1` / `_1_0` 子單元）= 22583 個；走生產 fallback 全鏈 `_body_rect` → `_graphics_bbox` → pin-tip；blind ⟺ box 寬 ≤ 0 |
| **B 只算 rect 來源** | **516** | **1** | 同 A 但只計 `_body_rect` 有回值者（18547 個）。**這格逐字對上 §2.3 修正後的 516** |
| **C BR 原記載** | 513 | — | **方法未記錄，兩方皆無法重現** |

三分計數（**缺席態不與失敗態共用輸出**）：`src_rect=18547 / src_graphics=4036 / src_pintip=0 / load 失敗=0 / flatten 失敗=0`。

HEAD 殘留的 **9 個 blind** 拆解：

- **rect 來源 1 個**：`74xGxx:74LVC1GU04DRL`，x-span **0.0** —— rect 本身退化，**任何 inset 規則都救不了**（覆算已重現，見上方 CONTROL）。
- **graphics 來源 8 個**：轄區屬 `BR_20260804g`。**未核對是否已在 804g 名單內**（見 §9）。

**⇒ `513` 在 A / B / C 任一口徑下皆不重現。** 這與 §2.6 記的是同一個教訓：**一個沒有標註口徑的數字，會被下一個人當成另一個口徑的答案。**

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

### 6.1 ⛔ SUPERSEDED（2026-08-05）——上方建議修法**不得照著施工**

> **上方 §6 是原記載，保留不刪**——它是「一個看起來合理的修法被實測否決」的記錄，刪掉就看不到否決發生過。

**否決的是 `min()` 形式本身，不只是參數選得不好。** `kicad_emit.py:583-589` 的 docstring 記載實測結果（本 session 直接讀原始碼確認，`grep -n '1617'` 命中 `:585`；控制組：假 token 回 0）：

```
Same sweep, `min(inset, span/4)`: 512 fixed but **1617 never-blind bodies
perturbed** (e.g. `Regulator_Linear:AMS1117-3.3`, y-span 6.985mm).
```

⇒ `min()` 形式會擾動**每一個落在 `span < inset/k` 帶內的 body**，包括那些 unclamped box 本來完全正常的。本 session 覆算 AMS1117 y-span 6.985：`min(1.905, 6.985/4) = 1.746` ≠ `inset 1.905` ⇒ **確實會被擾動**。

**實際落地的是條件式降級，不是 `min()`**：

```python
def _wide_enough(span): return span > threshold and not math.isclose(span, threshold, rel_tol=0.0, abs_tol=math.ulp(threshold))
ix = inset if _wide_enough(x1 - x0) else (x1 - x0) / 4.0
```

條件式形式在 `span - 2*inset > 0` 時依構造是 no-op，所以誤傷數是 **0 而非只是很小**。另見 §8.2b（ULP 容差）。

### 6.2 §6 的「**必然**新增 intrusion 回報」——預測未兌現，但只量了 1 頁

真實頁 `e2e-led-driver-npn`：

```
HEAD     intrusions = 1
PRE-FIX  intrusions = 1
delta    = 0
```

**這不是「§6 的預測是錯的」，是「在這一頁未兌現」。** 其餘 aiguard CCM 各頁**未量** ⇒ §6 結尾要求的那次「各頁曝險」量測仍是 **UNMEASURED，不是 FALSE**。兩者不得共用同一個輸出——這正是本 BR 全文在講的形狀。

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

> **⚠ 已超越（標記補於 2026-09-02；現行狀態見 line 3 `FIXED`，收斂量測見 §10–§12）**：
> 下一行與 line 3 下方 L12 的引用塊是**同一段 2026-08-04 措辭**，此處是它未經標記的第二份副本。
> 依本檔 L10/L12 既有慣例補上標記，**原文一字未刪**。缺此標記時，它與一條現行狀態宣告
> 在渲染上完全相同（`BR_20260804l §11.8` 把本處列為該批 7 張中唯一的矛盾）。
>
> **Status**: open（機制 ACCEPTED；量值 disputed，非阻塞；另見 §8 浮點邊界）

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

~~本張 BR 仍 OPEN 的是 **§1/§6 的主缺陷（量值 disputed）**，與 §8 是不同的標的。~~

> **⚠ 2026-08-05 更正（原句保留划掉，不刪）**：§1 主缺陷已於 `05dce34` + `d64bbd0` 修正（見 §1.1），
> §6 建議修法已 SUPERSEDED（見 §6.1）。本張現為 **PARTIAL**，殘留逐項列於 §9。

---

## 9. ⚠ 未量 / 未裁定（2026-08-05，本張仍為 PARTIAL 而非 closed 的理由）

> 這一節存在的理由：上方 §1.1 / §6.1 把已修的部分寫得很清楚，**而一張只寫「已修」不寫「還沒量什麼」的 BR，
> 讀起來與一張真的收斂完的 BR 長得一模一樣。** 未量的格不得被已量的格吸收掉。

| # | 未量 / 未裁定項 | 現狀 | 不得誤讀為 |
|---|---|---|---|
| C8 | **aiguard CCM 各頁曝險**（§6 結尾要求的那次量測） | **只量了 1 頁**（`e2e-led-driver-npn`，delta=0） | 不得讀成「全部頁都不會新增 intrusion」。**UNMEASURED ≠ FALSE** |
| R9 | **HEAD 殘留 8 個 graphics 來源 blind** | 已知存在，已知轄區屬 `BR_20260804g` | **未核對它們是否已在 804g 的名單內**。「已轉出」與「沒人接」目前共用同一個輸出 |
| N3 | **母體數三方分歧** | `22583`（生產全鏈 root-level）/ `22431`（dispatcher 重跑，見覆核節）/ `21437`（§2.3 掃描） | **未裁定哪個是對的**。三個都可能量的是不同東西（參 §8.2a 那次口徑分歧的形狀） |

**本張可以 closed 的條件**：C8 補量、R9 核對完（或明確轉入 804g）、N3 裁定或明確判為不影響結論。

---

## 10. §9 三項殘留的收斂量測（2026-09-01，`ses_fa70cfaf8`，dispatcher `ses_04db7a1c5` 派工）

> 這一節回答 §9 的 C8 / R9 / N3。**每個數字都帶母體**——母體不同的兩個數字並列會被讀成 delta。
> 量測腳本落 scratch（`$XDG_RUNTIME_DIR/guardc_remainder/`，收尾自清）；方法見 §10.0，可據以重寫。
> **本輪未修改任何生產程式碼**（裁示為「量測 + 判定」，修法回報給 dispatcher 裁決）。

### 10.0 母體定義（三個，互斥且窮盡，全節沿用）

| 代號 | 定義 | 值 |
|---|---|---|
| **P_ROOT** | `/usr/share/kicad/symbols/*.kicad_sym`（223 檔）內 **root-level** `(symbol "NAME")`，以**字串感知**的括號深度判定（深度 2 = `kicad_symbol_lib` 的直接子節點）；不含 unit 子區塊 | **22583** |
| **P_GUARD** | P_ROOT 中 pin map 非空者，即通過 `kicad_emit.py:1758 if not pmap: continue` 而**真正進入 guard C** 者 | **22214** |
| **P_ZEROPIN** | P_ROOT 中 pin map 為空者，`:1758` 即 continue，**從不建 box** | **219** |

`CHECK  P_GUARD 22214 + P_ZEROPIN 219 + load_fail 150 = 22583 = P_ROOT` ✓

**⚠ 量測儀器自己先壞了一次，形狀與本 BR 同族。** 第一版 walker 用生產的 `_balanced_block`
跳過已記錄的區塊，而**該 helper 不是字串感知的**：屬性值裡的一個 `(` 就讓深度計數器對
「檔案剩餘部分」全部失準。症狀是 `MCU_ST_STM32H7` 回報 **1** 個 root symbol（tab-regex 看到 225）。
**它沒有報錯，它回了一個比較小的、看起來合理的數字。**
修正後的判別依據：對五個先前分歧的檔案，string-aware walker 與 `\n\t(symbol "` regex 逐檔相符
（533 / 225 / 1170 / 334 / 419），外加一組合成控制組——屬性值內含 `x(y)z` 的括號不得移動深度，
實測 roots=['A','B'] units=['A_0_1'] 與預期逐字相同。

### 10.1 ✅ N3 裁定：三個母體數只有一個今天可重現，而它有兩條獨立證據

| 數字 | 出處 | 今天重算 | 判定 |
|---|---|---|---|
| **22583** | §1.2 口徑 A「生產全鏈 root-level lib_id」 | **22583**（string-aware 深度）**且** **22583**（`\n\t(symbol "` regex，獨立方法） | **重現，採為 P_ROOT** |
| 22431 | Dispatcher 覆核節重跑（`_body_rect` 掃描） | — | **不可重建**：該節只記「掃 223 檔、用 `_body_rect`」，未記切塊方式 |
| 21437 | §2.3 兩個 variant 的 `scan` 欄 | — | **不可重建**：腳本落 `$XDG_RUNTIME_DIR/guardc-scan/fast.py`（scratch），已不存在 |

**裁定：這不是「哪個對」的問題，是「只有一個附了可重跑的方法」。**
22583 今天由**兩個互不相干的切塊法**得到同值，並通過一條交叉驗證：

```
root 22583  +  unit 23746  =  46329
naive re.findall(r'\(symbol\s+"')  =  46329        ✓ 逐字相等
```

⇒ 「root ⊎ unit」窮盡了檔案裡所有 `(symbol "` 的出現位置，**沒有第三類**。

另兩個數字**不判為錯，判為無法重現**。這是 §2.3 開頭那條教訓（「數字記了、方法沒記」）
在**同一張 BR 上第二次兌現**：當時付一輪學費寫下六欄方法表，而覆核節與 §2.3 自己的
`scan` 欄並沒有跟著把方法落地。

### 10.2 ✅ R9 核對：9 個 blind 的歸屬已全數確定，**且 9 = 7 + 2 的口徑差已坐實**

§9 R9 問的是「這 8 個 graphics 來源的 blind 是否已在 804g 名單內」。核對結果：

| # | lib_id | 來源 | box w × h | 落在 804g 哪個名單 |
|---|---|---|---|---|
| 1 | `74xGxx:74LVC1GU04DRL` | rect | 0 × 11.43 | **都不在**——屬本張（§1.2 已具名：rect 自身退化） |
| 2 | `Connector:TestPoint` | graphics | 0 × 0 | **804g §9.5 具名 6 個** ✓ |
| 3 | `Connector:TestPoint_Small` | graphics | 0 × −0 | **804g §9.5 具名 6 個** ✓ |
| 4 | `Connector:TestPoint_2Pole` | graphics | 1.778 × −0 | **804g §9.5 具名 6 個** ✓ |
| 5 | `Device:NetTie_2` | graphics | 1.27 × −0 | **804g §9.5 具名 6 個** ✓ |
| 6 | `Mechanical:MountingHole_Pad` | graphics | 0 × 0 | **804g §9.5 具名 6 個** ✓ |
| 7 | `Mechanical:MountingHole_Pad_MP` | graphics | 0 × 0 | **804g §9.5 具名 6 個** ✓ |
| 8 | `Mechanical:Fiducial` | graphics | 0 × −0 | **804g zero-pin 第三族**（§7.6 `g 退化 2`，原本只有計數沒有名字） |
| 9 | `Mechanical:MountingHole` | graphics | 0 × −0 | **804g zero-pin 第三族**（同上） |

**回答 §9 R9 那句「兩者都不在」的審慎：沒有未建檔的第三批。**
8 個 graphics 來源中 6 個逐字命中 804g §9.5 具名名單，另 2 個命中 804g §7.6 的 zero-pin 退化桂（先前只有計數 2，本輪首次具名）；第 1 個是 rect 來源、屬本張。**全數有轄區。**

#### 為什麼 §9 記 9 而今天生產路徑只看得到 7（口徑，不是差值）

**先寫假説再跑，且假説可被推翻**：若差別僅來自 `:1758` 那道閘，則應有
`A_blind == P_GUARD_blind + zero_pin_degenerate`，即 `9 == 7 + 2`，且多出的兩個名字必須
**恰好是**那對 zero-pin 退化者。兩個計數由**同一輪掃描**同時輸出，故不可能來自不同版本的 code：

```
口徑 A  （每一個能算出 box 的 root symbol，不過 :1758 閘）
    A_blind = 9    sources = {rect: 1, graphics: 8}      <- 逐字對上 §9 的 9 與 8
口徑 G  （P_GUARD，HEAD 真實路徑）
    G_blind = 7    sources = {rect: 1, graphics: 6}

A 有而 G 沒有的名字 = 2，且兩個都是 ZEROPIN：
    Mechanical:Fiducial        graphics  w=0 h=-0
    Mechanical:MountingHole    graphics  w=0 h=-0

HYPOTHESIS  7 + 2 = 9  -> MATCH（未被推翻）
HYPOTHESIS  graphics in A = 8 -> MATCH
```

⇒ **「9」與「7」不是 delta，是兩個母體。** §9 那個 9 含兩個 `:1758` 會提前 short-circuit
、生產上永遠不會被建 box 的符號。兩個數字都對，回答的是不同問題：
「有多少符號的 box 是退化的」 vs「有多少符號在 guard C 裡是盲的」。

### 10.3 ✅ C8 補量：各頁曝險（定義寫在數字旁邊）

> §9 C8 要求的是 §6 結尾那次「各頁曝險」量測，先前只量了 1 頁。

**「一頁」的定義（不定義就不交數字）**：

```
一頁        := repo 內一個已輸出的 KiCad root schematic 檔（*.kicad_sch）
其元件母體 := 該檔內每個已擺放的 `(symbol (lib_id "X")` INSTANCE 區塊
              ——**不是** `lib_symbols` 快取（那裡還含未被擺放的 power/flag 定義）
一頁的曝險 := 該頁已擺放元件中，在 HEAD guard C 來源鏈下 box 退化（w≤0 或 h≤0）者的個數
```

**為何不用 `.spec.json` 當母體**：全 repo 只有 **1** 個 `.spec.json`（就是 §6.2 已量過的
`e2e-led-driver-npn`），以它為母體的「全部頁」等於同一頁，答不了 C8。`.kicad_sch` 是真正較大的已輸出頁面母體。

**母體 = 14 頁**（repo 內全部 `*.kicad_sch`，排除 `.git` / `.venv`）

```
page                                                        inst  BLIND  seen  0pin   pwr
---------------------------------------------------------------------------------------
aiguard_c03_compose/probeA|D/sch_product/verifyN2_empty        0      0     0     0     0   (4 頁空)
aiguard_c03_compose/probeB                                     1      0     1     0     0
aiguard_c03_compose/probeC                                     1      0     1     0     0
aiguard_c03_compose/probeE                                     2      0     2     0     0
aiguard_c03_compose/probeG  /  probeG2                       2,2      0     2     0     0  (各)
aiguard_c03_compose/sch_direct/aiguard_product               134      0    46     0    88
aiguard_c03_verify/n1_bare  /  p_twodirs2                    2,2      0     2     0     0  (各)
e2e-led-driver/C03-EE/e2e-led-driver-npn                      22      0    22     0     0
e2e-led-driver/C03-EE/e2e-led-driver                          16      0    16     0     0
---------------------------------------------------------------------------------------
TOTAL （14 頁）                                              184      0    96     0    88
```

**結果：全 14 頁、184 個已擺放元件，BLIND = 0。**

**這個 0 有判別力嗎？** 採用六態 codomain（blind / seen / zero-pin / engine-pwr / no-such-lib / load-fail），
使「缺席」與「失敗」不共用輸出，並以七組探針證明分類器真的會說出不同答案：

```
Connector:TestPoint            -> blind        ✓ （它真的能說 blind）
Regulator_Linear:AMS1117-3.3   -> seen         ✓
Device:R                       -> seen         ✓
Graphic:SYM_Arrow_Large        -> zero-pin     ✓
power_gnd_GND                  -> engine-pwr   ✓
NoSuchLib:NoSuchPart           -> no-such-lib  ✓
Device:ZZ_NoSuch_9999          -> load-fail    ✓
```

**⚠ 這一格的第一版儀器壞了，而它回的也是 `BLIND=0`。** 實錄並保留：
v1 只將 lib_id 解析到 `/usr/share/kicad/symbols`，於是最大那頁 134 個 instance 中 **93 個回 `load-fail`**
（實際上它們住在 repo 內 42 個 project-local `.kicad_sym`，以及 engine 內嵌的 `power_*` glyph）。
**一頁元件全部解析失敗時，它也回報 BLIND=0——與一頁真的干淨逐字相同。**
v2 把搜尋路徑擴到 stdlib + repo 內全部 42 個本地 library，並把 engine glyph 從「失敗」分出來
成為獨立態 `engine-pwr`；fail 欄這才降到 0，上表的 0 才有意義。

**⇒ C8 已補量。§6 那句「必然新增 intrusion 回報」在此 14 頁母體上未兑現，
而這次是有判別力的 0，不再是 UNMEASURED。**

**誕實邊界**：母體是「repo 裡已經輸出到磁碟上的 `.kicad_sch`」。它**不等於**「任何人未來可能產生的頁」——
若未來某頁用上上表那 9 個 blind 符號（TestPoint / MountingHole 類），曝險就不是 0。
804g §7.8 已經指出這件事並列為未量項，**本輪也沒量**。

---

## 11. guard C 分桶重取（2026-09-01，`BR_20260901f` 修法後）

> §10 的分桶是在 `_balanced_block` 缺陷存在時量的。901f 修法落地後，那 150 個假 not-found
> 變成可用符號，本節重取。**母體定義逐字沿用 §10.0，未改口徑**——只有被量的 code 變了。

### 11.1 三桶前後對照（母體 P_ROOT = 22583，不變）

| 桶 | 口徑（§10.0） | 修法前 | 修法後 | 差 |
|---|---|---|---|---|
| **P_GUARD** | pin map 非空，過 `kicad_emit.py:1758` 閘，真正進 guard C | 22214 | **22544** | **+330** |
| **P_ZEROPIN** | pin map 為空，`:1758` 即 continue，從不建 box | 219 | **39** | **−180** |
| **load_fail** | `load_symbol` 解析不出來 | 150 | **0** | **−150** |
| **CHECK** | 三桶相加 | 22583 ✓ | **22583 ✓** | 恆等式仍成立 |

**兩桶各增分開報**——不能只報 +330，否則 804g 的 37 無法重算：

```
問：每個符號從哪個桶移到哪個桶？（逐符號具名 join，22583 列全數對上）

  22214  guard                -> guard                 未動
    150  load_fail            -> guard                 假 not-found 被修好，全數有 pin
    180  zeropin_g_none       -> guard                 見 §11.2，機制已坐實
     37  zeropin_g_ok         -> zeropin_g_ok          未動（804g 第三族）
      2  zeropin_g_degenerate -> zeropin_g_degenerate  未動（Fiducial / MountingHole）

  沒有任何符號反向移動（guard -> zeropin 或 -> load_fail 為 0 列）。
```

控制組：`CTRL_A` 母體枚舉器真的跑了（enumerated=22583，且 `Device:R` 確實在枚舉結果中）
——這一格是 901f §10.5 #1 那次教訓的直接產物；`CTRL_B` 分類器能落進**兩個**桶
（`Device:R` 有 pin ✓／`Mechanical:Fiducial` zero-pin ✓）；`CTRL_C` load_fail 桶可達
（真的不存在的名字仍回 None ✓）。**三個桶都被證明是可到達的**，0 才有意義。

### 11.2 那 180 個不是「多出來的」，是先前被誤判成 zero-pin

**這是本輪最需要解釋的一格。** 150 個假 not-found 只能解釋 +150，剩下的 +180 必須有自己的機制，
不得以「應該是因為修好了吧」帶過。實測（before/after 同一支探針，namespace 切換掃描器，不動磁碟）：

```
問：這 180 個在修法前取到的區塊與修法後一樣嗎？
     block_differs = 180 / 180        全數不同
問：它們的 pin map 怎麼變的？
     pins_before_empty_after_nonempty = 180 / 180

樣本（name, good_len, bad_len, good_pins, bad_pins）：
  Connector_Generic:Conn_02x01_Row_Letter_Last  2267 -> 981   2 pins -> 0
  Connector_Generic:Conn_02x02_Row_Letter_Last  3068 -> 981   4 pins -> 0
  Connector_Generic:Conn_02x03_Row_Letter_Last  3863 -> 981   6 pins -> 0
  Connector_Generic:Conn_02x04_Row_Letter_Last  4664 -> 981   8 pins -> 0

CONTROL Device:R（未移動者）  len 1646 vs 1646   pins 2 vs 2   逐字相同 ✓
```

**機制鍵在 `bad_len` 恆為 981**：這些 `Conn_*_Row_Letter_Last` 都是 `(extends ...)` 衍生符號，
區塊被截斷在同一個位置（衍生頭部），於是 `_flatten_extends` 拿不到 pin、`_pin_endpoints` 回空字典，
`:1758 if not pmap: continue` 就把它們當成 zero-pin 排掉。

> **這 180 個從來不是 zero-pin。** 它們是有 2–36 支腳的 connector，在 guard C 眼中消失了一整段時間。
> 而「真的沒有 pin」與「區塊被截斷到拿不到 pin」**共用同一個空 pin map** ——
> 與 901f 主缺陷同形，只是發生在下一層。

這也解釋了 `zeropin_g_none` 為何從 180 降到 **0**：那個桶裡裝的全部是這批被截斷的衍生符號，
它們沒有 graphics 是因為區塊本身就不完整。**不是一個真實的分類，是一個缺陷的殘影。**

### 11.3 本節沒量什麼

1. **未重跑 §10.2 的 9 個 blind 交集表與 §10.3 的 14 頁曝險。** 那 330 個新進 P_GUARD 的符號
   **可能包含新的 blind 者**（box 退化）——本輪只重建了分桶，**沒有重跑 blind 判定**。
   這是一個**具體、可排程**的缺口，不是一個模糊的保留。
2. **未驗證那 180 個重新進入 guard C 後是否觸發新的 intrusion 回報**（同上，需重跑 blind 判定）。
3. **§10.1 的 22431 / 21437 仍不可重建**，本輪未重試。

> **§11.3 第 1、2 項已於 2026-09-01 補量，見 §12。第 3 項仍未重試。**

---

## 12. blind 判定在新 P_GUARD 上重跑（2026-09-01，`ses_fa70cfaf8`，dispatcher `ses_04db7a1c5` 派工）

> 這一節回答 §11.3 的第 1 項與第 2 項。**口徑逐字沿用 §10.2**（同一支分類器、同一組 box 退化
> 判準、同一條來源鏈 rect → graphics → pin-tip）——**判準一換，新舊就不可比較，而「不可比較」
> 會被讀成「有變化」。** 本輪**零生產碼變更**。

### 12.1 三個數字，各自帶母體

| 量 | 母體 | 值 |
|---|---|---|
| **blind 總數** | **P_GUARD_now = 22544** | **7** |
| 其中屬 **OLD**（修法前就在 guard 的 22214） | OLD = 22214 | **7** |
| 其中屬 **NEW**（新進的 330） | NEW = 330 | **0** ← 本包的答案 |

**判準未漂移**：`blind(OLD) == 7` 這個數不只是「等於 7」，而是**與修法前那一輪逐名相同**——
同一支分類器在同一個 process 內對注入舊掃描器的 pass 也回 7，且兩組名單集合相等：

```
drift check:  blind_before(P_GUARD_before 22214) == blind_now ∩ OLD   ->  True
```

> **方法註記（dispatcher `ses_04db7a1c5` 覆核裁決 ①，2026-09-01）——集合相等優於數值相等。**
> 這裡回報的不是「兩邊都等於 7」，而是**兩個名單集合相等**。差別是可判別性：
> **數值相等可以由「兩個不同的 7」滿足**（修法讓 A 不再 blind、同時讓 B 變成 blind，
> 計數不動而判準已經漂移），集合相等不行。凡是拿一個計數去證明「沒有變化」的地方，
> 先問一句：**這個數字若由不同的成員湊出來，我看得出來嗎？** 看不出來就改比集合。

**成員拆分（同一次掃描同時輸出，不可能來自不同版本的 code）**：

```
OLD  (兩個 pass 都在 guard)     22214
NEW  (新進 guard)                 330   = 150 (原 load_fail) + 180 (原 zeropin)
LOST (離開 guard)                   0   ← 沒有任何符號反向移動
```

### 12.2 blind 7 個逐一具名（母體 = P_GUARD_now 22544）

| # | lib_id | 來源 | w | h | pins | 轄區 |
|---|---|---|---|---|---|---|
| 1 | `74xGxx:74LVC1GU04DRL` | rect | 0.0 | 11.43 | 5 | **804b**（§1.2 具名，rect 自身退化） |
| 2 | `Connector:TestPoint` | graphics | 0.0 | 0.0 | 1 | **804g §9.5 具名 6 個** |
| 3 | `Connector:TestPoint_2Pole` | graphics | 1.778 | −0.0 | 2 | **804g §9.5 具名 6 個** |
| 4 | `Connector:TestPoint_Small` | graphics | 0.0 | −0.0 | 1 | **804g §9.5 具名 6 個** |
| 5 | `Device:NetTie_2` | graphics | 1.27 | −0.0 | 2 | **804g §9.5 具名 6 個** |
| 6 | `Mechanical:MountingHole_Pad` | graphics | 0.0 | 0.0 | 1 | **804g §9.5 具名 6 個** |
| 7 | `Mechanical:MountingHole_Pad_MP` | graphics | 0.0 | 0.0 | 1 | **804g §9.5 具名 6 個** |

來源分布 `{graphics: 6, rect: 1}` —— 與 §10.2 的 P_GUARD 列（`rect 1 / graphics 6`）逐字相同。

**⇒ §10.2 的結論在 330 個新成員加入後仍然成立**：blind 全數有轄區，
**「兩者都不在」仍是空集合，沒有未建檔的第四批。**

### 12.3 那個 `0` 有判別力嗎（NEW 330 中 blind = 0）

**同一支分類器、同一輪掃描**對已知 blind 者必須回非零，否則這個 0 只是探針壞掉：

```
74xGxx:74LVC1GU04DRL      -> ['guard', True,  'rect',     w=0.0,   h=11.43 ]  ← 說得出 blind
Connector:TestPoint       -> ['guard', True,  'graphics', w=0.0,   h=0.0   ]  ← 說得出 blind
Device:R                  -> ['guard', False, 'rect',     w=1.016, h=1.27  ]  ← 說得出 non-blind
Regulator_Linear:AMS1117-3.3 -> ['guard', False, 'rect',  w=6.35,  h=3.175 ]  ← 同上
Mechanical:Fiducial       -> ['zeropin', None, …]                             ← 真 zero-pin 未被誤收進 guard
```

另外三組控制組**保護的是不同層**（§10.5 那句「控制組只覆蓋它所在的那一層」）：

- **CONTROL_ENUM（母體枚舉器，非分類器）**：`P_ROOT` 兩個 pass 皆 22583 且集合相等
  （`set(now) == set(before)` assert 未觸發）。母體為空時分類器會全綠——這格擋的是那個。
  枚舉器起點錨定用 `src.index("(", m.start())` + `assert src[st] == "("`，**不寫死偏移量**
  （§10.5 #2 的形狀，本 fleet 已獨立踩過兩次）。
- **CONTROL_EQ（探針 == 生產路徑）**：本輪把 `load_symbol` 的 body 內聯（它每次呼叫都重讀整個
  213 MB 語料，O(n²)）。內聯鏈與 `load_symbol` 對六個具名樣本**逐字相等**，含錯誤態：
  ```
  Device:R                                     True  1653 == 1653
  Isolator:TLP184xSE                           True  4944 == 4944
  Mechanical:Fiducial                          True  1122 == 1122
  Connector:TestPoint                          True  1463 == 1463
  ZZ_NoSuchLib:Nope                            True  ERR  == ERR
  Connector_Generic:Conn_02x04_Row_Letter_Last True  4682 == 4682
  ```
- **CHECK 恆等式**：`22544 + 39 + 0 = 22583`（now）與 `22214 + 219 + 150 = 22583`（before）
  兩側皆成立。

### 12.4 §11.3 第 2 項：那 180 個重進 guard 後有沒有觸發新 intrusion

分兩層回答，因為「符號層」與「頁面層」是兩個母體：

```
符號層（母體 = 180）：blind = 0        沒有任何一個的 box 退化
符號層（母體 = 150）：blind = 0        同上
頁面層（母體 = 14 頁 / 184 個已擺放元件）：這 330 個的已擺放 instance 數 = 0
  CONTROL_MEMBER: 'Connector_Generic:Conn_02x04_Row_Letter_Last' ∈ the180  ->  True
```

**⇒ 新 intrusion 數 = 0，而這個 0 有兩個獨立理由**：那 330 個的 box 都不退化（判準層），
且它們在現存 14 頁上**一個都沒被擺放**（曝險層）。`CONTROL_MEMBER` 證明那個 0 不是因為
集合是空的——集合裡確實有可查得到的成員。

### 12.5 §10.3 各頁曝險重取（母體與定義逐字沿用 §10.3）

```
page                                                        inst  blind seen  0pin  pwr  nolib fail
---------------------------------------------------------------------------------------------------
probeA / probeD / sch_product / verifyN2_empty（4 頁空）        0      0    0     0    0     0    0
probeB / probeC                                              1,1      0    1     0    0     0    0  (各)
probeE / probeG / probeG2 / n1_bare / p_twodirs2              2×5     0    2     0    0     0    0  (各)
sch_direct/aiguard_product                                   134      0   47     0   87     0    0
e2e-led-driver/C03-EE/e2e-led-driver-npn                      22      0   22     0    0     0    0
e2e-led-driver/C03-EE/e2e-led-driver                          16      0   16     0    0     0    0
---------------------------------------------------------------------------------------------------
TOTAL（14 頁）                                               184      0   97     0   87     0    0
```

**BLIND = 0，與 §10.3 相同。** 六態 codomain 控制組六格全中（blind / seen / zero-pin /
engine-pwr / no-such-lib / load-fail 各有具名探針回對應態），另加 `CONTROL_INST`：
instance regex 對最大那頁回 134，而 `lib_symbols` 樣式的條目是 9 —— 兩者不同，
證明母體選的是**已擺放 instance** 而非快取定義。

**⚠ 與 §10.3 有一格差異，是我的分類器口徑改變，不是資料變動**：`seen 46 → 47`、
`pwr 88 → 87`，總數 134 不變。移動的是**同一個 instance**：`power:PWR_FLAG`（1 個）。
§10.3 的分類器把它歸為 engine glyph；本輪先判斷 `lib_id` 是否帶 library 前綴，
`power:PWR_FLAG` 帶前綴故走 stdlib 解析路徑，解析成功（1 pin、graphics
`(-1.016, 0.0, 1.016, 2.54)`、box `w=1.016 h=1.27`）⇒ `seen`。
**兩種歸類下它都不是 blind，所以 BLIND=0 不受影響。** 控制組：無冒號的
`power_gnd_GND` 與裸 `PWR_FLAG`（3 個 instance）仍走 engine-pwr 路徑。

**兩個口徑各自的定義，寫在數字旁邊**（dispatcher 覆核裁決 ②：讓下一個人知道
差 1 的成因是**分類規則**而不是資料變動）：

| 口徑 | 判「是不是 engine glyph」的規則 | `power:PWR_FLAG` 落哪 | 該頁 seen / pwr |
|---|---|---|---|
| **§10.3（2026-09-01 上午）** | 比對 **engine glyph 名單**（`power_*` 前綴與 `PWR_FLAG` 字面，含帶 library 前綴的變體） | `engine-pwr` | 46 / 88 |
| **§12.5（本輪）** | 先看 `lib_id` **有無 library 前綴**；有前綴就交給 library 解析鏈，解析成功即依 box 判 blind/seen | `seen` | 47 / 87 |

```
同一份檔案、同一個 instance、總數 134 不變 —— 移動的只有 power:PWR_FLAG 這 1 個。
兩種歸類下 blind 皆為 False，故 BLIND=0 在兩個口徑下都成立。
```

**不把它解析成一個數字，是刻意的。** 兩個都是可辯護的枚舉方式，
而「兩個可辯護的枚舉對同一份檔案答不同數字」正是本張 BR 的形狀（§10.1 同理）。
把差異記下來比抹平誠實：**下一個看到 46 與 47 的人不會誤讀成回歸。**

### 12.6 本節沒量什麼

1. **§7.8 仍未量**（那 6 個具名 blind 符號在**真實** PCB 頁上的出現頻率）——依 dispatcher
   裁決維持未量。本節只證明「repo 內現存 14 頁沒用到它們」，**不等於**「使用頻率低」。
2. **未量那 330 個在未來頁面上的曝險**。它們今天一個都沒被擺放；若某天被擺上，
   本節的頁面層 0 就不再適用（判準層的 0 仍適用——它們的 box 不退化）。
3. **§10.1 的 22431 / 21437 仍不可重建**，本輪未重試（§11.3 第 3 項照舊）。
4. **未跑 `emit_kicad_schematic` 端到端**。本節量的是 guard C 的判準與來源鏈，
   不是完整 emit 流程；`_port_intrusions` 的實際觸發還需要 power endpoint 幾何，
   而現存 14 頁上那 330 個符號一個都沒出現，故無可觸發的案例。
