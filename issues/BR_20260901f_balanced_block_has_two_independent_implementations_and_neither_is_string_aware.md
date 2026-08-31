# BR_20260901f — `_balanced_block` 有兩份獨立實作，皆無引號狀態機；332 個符號被靜默解析錯誤，其中 150 個回報成「symbol not found」

- **Status**: **open** — 機制已坐實（活體重現，兩份實作皆紅）；曝險已量（生產路徑 332/22583）；**未修**（裁示為只建檔，修法另排）
- **Severity**: **HIGH** — 不是潛在缺陷。`load_symbol` 對 **150** 個實際存在的符號拋 `KeyError: Symbol 'X' not found`，另 **182** 個回傳長度錯誤的區塊而不報錯
- **Component**:
  - `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:444-453`（`_balanced_block`）
  - `packages/eda-bridge/bodesign_eda_bridge/fidelity.py:263-274`（**第二份獨立實作**）
- **Family**: schematic-engine
- **Filed**: 2026-09-01 by `ses_fa70cfaf8ffeEPDvmHXCCsBkRv`（dispatcher `ses_04db7a1c5` 派工並親驗）
- **Owner**: 未指派

---

## 1. 一句話

兩份 `_balanced_block` 都逐字元數括號，**沒有引號狀態機**。KiCad 符號庫的屬性值裡合法地含有未配對括號（`"PA13(JTMS"`、`"…(750mA"`），於是深度計數器從那一格起對**檔案剩餘部分**全部失準。

**它不會拋例外。** 一份多吞後續區塊（靜默污染），另一份回空字串（靜默截斷），第三種結果是深度永不歸零而跑到檔尾 `return s[start:]` —— 呼叫端把它讀成「找不到這個符號」。

**「這個符號不存在」與「這個符號存在但我解析失步了」共用同一個輸出。**

## 2. 兩份實作，兩種失效形狀（**不得合併敘述**）

修一份不會修到另一份。下一個人只讀到一份就會以為修完了。

| | `kicad_emit.py:444` | `fidelity.py:263` |
|---|---|---|
| 失步後行為 | 深度歸零於**後續**區塊 ⇒ **多吞** | 深度永不歸零 ⇒ 迴圈走完 ⇒ `return ""` |
| 活體實測 | want=33 **got=64** | want=33 **got=0** |
| 下游症狀 | 區塊含入下一個 symbol 的內容 | 呼叫端拿到空字串當合法輸入 |

### 2.1 生產路徑（決定 severity，非假設）

**`kicad_emit.py`**：`_balanced_block` 的唯一呼叫者是 `:466 _symbol_children`（取 `(symbol …)` 的直接子 s-expression），其呼叫者是 `:489/:490 _flatten_extends` —— 展開 `(extends "Base")` 衍生符號時，用它取出 derived 的 property override 與 base 的 attrs/units。**這是 `load_symbol` 的必經之路**（`:383` 對每個 block 呼叫），不是選用路徑。

**同檔另有 `_extract_symbol_block:427-442`**，是同一個演算法的第三次抄寫（同樣無引號狀態機），且它是 `load_symbol:403` 取 block 的入口。**本 BR 量到的 150 個假 not-found 就是它造成的。**

**`fidelity.py`**：`:302` 取 `(lib_symbols …)` 整塊、`:305` 逐一取符號定義判斷 `(power)`、`:321` 反向搜出放置 instance 的 `(symbol …)` 區塊以讀 Reference。這是保真閘判定「哪些 ref 是 power symbol、會被 netlist 匯出器略去」的依據 —— 失步 ⇒ power symbol 認定錯誤 ⇒ 元件數對帳錯誤。

## 3. 活體重現（可貼上就跑，含控制組）

```python
#!/usr/bin/env python3
# cd /home/pkcs12/projects/bodesign
# find . -name __pycache__ -prune -exec rm -rf {} +
# PP=$(ls -d packages/*/ | tr '\n' ':'); PYTHONPATH="$PP" python3 this.py
import sys
sys.path.insert(0, "packages/eda-bridge")
from bodesign_eda_bridge.kicad_emit import _balanced_block as ke_bb
from bodesign_eda_bridge.fidelity  import _balanced_block as fid_bb

TREAT = '(symbol "A" (property "V" "x(y"))'   # 引號內未配對 '('
CTRL  = '(symbol "A" (property "V" "xy"))'    # 同形，無括號
TAIL  = '(symbol "B" (property "W" "z"))'     # 後續 sibling，不得被吞

def probe(fn, block):
    got = fn(block + TAIL, 0)
    return len(block), len(got), got == block

for name, fn in (("kicad_emit", ke_bb), ("fidelity", fid_bb)):
    for variant, blk in (("TREATMENT", TREAT), ("CONTROL  ", CTRL)):
        w, g, ok = probe(fn, blk)
        print(f"{variant} {name:12s} want={w:3d} got={g:3d} correct={ok}")
```

實測輸出：

```
TREATMENT kicad_emit   want= 33 got= 64 correct=False
CONTROL   kicad_emit   want= 32 got= 32 correct=True
TREATMENT fidelity     want= 33 got=  0 correct=False
CONTROL   fidelity     want= 32 got= 32 correct=True
```

**⚠ fixture 為什麼一定要接 `TAIL`** —— 見 §6，這一格是 dispatcher 的探針第一次量錯的地方。

## 4. 曝險量測（帶母體標籤；每個數字回答「這是哪個母體」）

### 4.1 第一層：檔案裡有多少未配對括號的引號值

**判準說明**：只計 **未配對**（`(` 與 `)` 數量不等）者。值裡的**平衡**括號（`"V(ref)"`）不會讓深度計數器失步，計進去會高估曝險。

| 母體 | 檔數 | 引號串總數 | 含括號 | **未配對（曝險）** |
|---|---|---|---|---|
| **P_STDLIB** `/usr/share/kicad/symbols/*.kicad_sym` | 223 | 2334205 | 9925 | **630** |
| **P_LOCAL** repo 內 `*.kicad_sym` | 42 | 2801 | 27 | **0** |
| **P_SCH** repo 內 `*.kicad_sch`（`fidelity.py:302` 實際讀的語料） | 14 | 4572 | 13 | **0** |

樣本：`"PA13(JTMS"`（STM32H7 腳位名）、`"PB3(JTDO"`、`"…Outputs (750mA"`、`"…docget.jsp?did=14118&prodNam…"`。

控制組（掃描器必須數得出給它看的括號）：`"x(y"`→1 ✓／`"x(y)z"`→0 ✓／`"xy"`→0 ✓。

### 4.2 第二層（決定性）：生產路徑上實際被解析錯的符號數

第一層是**檔案層**計數，不等於「有多少符號真的被解析錯」。用 string-aware walker 取得每個 root symbol 的**真實邊界**，再與生產 `_extract_symbol_block` 的輸出逐一比長度：

```
母體 = P_ROOT（22583 個 string-aware root symbol）

    長度正確                         22251
    長度錯誤（靜默污染）               182   <- 不報錯，回傳被污染的區塊
    回 None 而 marker 確實在檔案裡      150   <- 假的 "symbol not found"
    回 None 且 marker 真的不存在          0
    CHECK  22251 + 182 + 150 + 0 = 22583   ✓
```

**`回 None 且真的不存在 = 0` 是決定性的**：它排除了「這 150 個本來就不該存在」這個解釋。每一個都在檔案裡，`src.find('(symbol "NAME"')` 都命中。

控制組（雙向，證明分類器不是對什麼都說同一句）：

```
Device:ZZ_NoSuch_9999  extract=None  marker_in_file=False   -> 落入 absent 桶 ✓
Device:R               extract_len=1646  true_len=1646       -> 落入 correct 桶 ✓
```

具名（前 10 個假 not-found）：`Isolator:TLP184xSE`、`MCU_ST_STM32H5:STM32H503CBTx/CBUx/EBYx/KBUx/RBTx`、`MCU_ST_STM32H5:STM32H523CCTx/CCUx/CETx/CEUx`……

### 4.3 這 150 個先前被誤讀成「名稱查找失敗」

`BR_20260804g §3` 與 `§9.5` 都記載 `load errors 150 / first = KeyError: Symbol 'TLP184xSE' not found`，並判定為「**皆為 `KeyError` 名稱查找失敗，非本 BR 相關**」。

**那個判定是錯的，而它錯得完全合理**——錯誤訊息字面就是 "not found"。實測：

```
TLP184xSE  literal_find=1592583  loose_regex=HIT@1592583  _extract_symbol_block=None
TLP185xSE  literal_find=1593754  loose_regex=HIT@1593754  _extract_symbol_block=len=39763  <- CONTROL
TLP2361    literal_find=     -1  loose_regex=MISS         _extract_symbol_block=None       <- CONTROL
```

`TLP184xSE` 的 marker 在 offset 1592583，**而 `_extract_symbol_block` 回 None**。控制組 `TLP185xSE`（同檔、相鄰）正常解析，`TLP2361`（真的不存在）同樣回 None —— **兩個成因共用同一個回傳值**，這正是本 BR 的形狀。

> **修好本 BR 之後，那 150 筆會從 error 變成可用符號。** 任何引用「load_fail=150」的既有量測（804g §4/§9.5、804b §10）其母體都會變動。

### 4.4 為何 severity 是 HIGH 而不是 LOW

派工單預設了一個可能性：「若曝險為 0，那是重要結果，把 severity 從 HIGH 降到 LOW」。
**實測不是 0。** 且兩層量測指向不同結論，不得互相抵消：

- **repo 自己的檔案（P_LOCAL / P_SCH）曝險 = 0** ⇒ `fidelity.py` 那一侽在**現有語料上**是潛伏的。
- **stdlib（P_STDLIB）曝險 = 630，且生產路徑實際錯誤 332 個** ⇒ `kicad_emit.py` 那兩份是 **LIVE**。

而 stdlib **就是引擎的預設符號來源**（`:32 DEFAULT_SYMBOL_DIR`）——不是選用語料。
**332 / 22583 = 1.47%，且分布不是隨機的**：集中在 STM32H5 / STM32H7 這類腳位名帶括號的 MCU，
而 MCU 正是任何一塊板子的主符號。**盲區不在冷門角落。**

## 5. 明確不是缺陷 / 不要動

- **不要把修法寫成「改用 regex 抽換 `_balanced_block`」**。三個呼叫點的語意不同（取子節點 / 取命名區塊 / 反向搜尋包围區塊），需各自驗證。
- **不要只修 `kicad_emit` 那一份**。`fidelity.py:263` 是獨立抵達的同一個缺陷，它今天潛伏只因為 repo 內的 `.kicad_sch` 沒有觸發語料——**匯入一個帶 STM32H7 的頁就會觸發**。
- **不要把 `load_fail=150` 當成干淨的基線**。修完後它會變，引用它的地方都要重新帶口徑。

## 6. 方法論：探針與被測對象共用失效模式時，判別力歸零

> 這一節是 dispatcher（`ses_04db7a1c5`）自述，寫進來因為下一個要驗這件事的人會直接受益。

第一版探針兩格都回 `correct=True`，**看起來就像「沒問題」**。成因：測資本身括號不平衡，
helper 失步後掉到字串末端執行 `return s[start:]`，**而那恰好等於整個輸入**。

```
「解析正確」          -> return 正確的 block
「失步後回傳全部」      -> return 整個輸入，而輸入 == block
                          兩者共用同一個 True
```

控制組也是 `True`，所以**那一格的判別力是零**——兩個 variant 同值不是「沒差別」，是「測不出差別」。

**修法是在 fixture 尾巴接一個 sibling block**（上方 `TAIL`）：失步的 helper 會吐回包含 `TAIL`
的東西，長度與 `block` 不同，兩態這才分得開。

> **一般形式**：當探針的失敗路徑恰好會產生「正確答案」時，它就不是探針了。
> 寫完任何判準要問一句：**它在該紅的時候真的會紅嗎？** 答不出來就先做一組正向控制組。

同族前例（同一個 fleet，不同題目）：`BR_20260804e §` 記載量測 `pkill -f` 時，
**控制組與 treatment 死於同一個原因**（控制組的字面 pattern 也在命令列裡）。

## 7. 驗收判準（給未來的修法）

1. §3 重現碼：兩個 TREATMENT 必須轉為 `correct=True`，兩個 CONTROL 維持 `True`
2. §4.2 三分計數：`長度錯誤` 與 `假 not-found` 均需降至 **0**，`長度正確` 升至 **22583**
3. `fidelity.py` 那份要有**自己的**測試，不得以 `kicad_emit` 的測試代替
4. mutation proof：把引號狀態機拿掉 → 測試轉紅 → 還原 → byte-identical
5. 回歸控制組：`Device:R` 的 `extract_len` 需維持 1646（修法不得擾動本來就對的 22251 個）

## 8. 誕實邊界（本 BR 沒量什麼）

1. **未量那 182 個「長度錯誤」的下游後果**。它們回傳被污染的區塊，但污染是否改變 `_body_rect` / `_pin_endpoints` 的結果——**未驗**。
2. **未量 `fidelity.py` 那三個呼叫點的實際錯誤率**。只證了 helper 本身會錯、且現有 `.kicad_sch` 語料曝險為 0。
3. **未量 `_extract_symbol_block`（第三份拄寫）以外是否還有第四份**。只掃了 `eda-bridge` 兩個檔。
4. **未量這 332 個被錯誤解析的符號在真實頁上的使用頻率**。repo 內 14 頁未使用它們（見 `BR_20260804b §10.3`），但**「現存頁面沒用到」不等於「使用頻率低」**——STM32H7 是主流 MCU。
5. **未嘗試修法**（裁示為只建檔）。

## Related

- `BR_20260804b_guard_c_inset_inverts_the_box_for_narrow_bodies_so_intrusion_check_is_blind.md`
  —— **依據：同一條執行路徑**。804b §10 的全庫量測經由 `load_symbol` → `_extract_symbol_block`
  → `_flatten_extends` → `_symbol_children` → `_balanced_block`，即本 BR 的缺陷點。
  804b §10 記載的 `load_fail = 150` **就是本 BR §4.2 那 150 個假 not-found**。
- `BR_20260804g_guard_c_pin_tip_fallback_box_is_degenerate_for_1198_symbols_whose_pins_are_collinear.md`
  —— **依據：同一條執行路徑 + 具體錯誤判定**。804g §3 與 §9.5 將這 150 筆判為「`KeyError`
  名稱查找失敗，非本 BR 相關」，本 BR §4.3 證實那個判定不成立（marker 均在檔案內）。
- 失敗類別同族：`BR_20260804e_pkill_f_self_matches_and_silently_kills_the_calling_shell.md`
  —— **依據：同一種失效類別（探針與被測對象共用失效模式）**，見本 BR §6。
- 失敗類別同族：`BR_20260804_bus_route_docstring_promises_a_channel_router_the_code_does_not_implement.md`
  —— **依據：同一種失效類別（機制在場但實際不執行，與「沒發現問題」共用同一個輸出）**。
