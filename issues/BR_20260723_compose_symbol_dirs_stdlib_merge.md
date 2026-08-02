# BR_20260723 — compose_schematic 覆蓋標準庫 → 給定 symbol_dirs 時 placed:0

- **Filed by**: aiguard C03 consumer session (ses_073a93d09ffeRTpR9TwIdofhb3)
- **Repo**: bodesign (platform)
- **Severity**: high — 任何需要「自訂 symbol 目錄 + 標準庫 passive」的 compose 全數 `placed:0`
- **Status**: open
- **Fix venue**: bodesign-rooted session (platform owner)

## Symptom (verbatim)

`bodesign_compose_schematic` 對 aiguard MCU core spec(52 元件 / 18 net)每次回傳 `placed: 0`，
無論 `symbol_dirs` 怎麼傳（試過相對字串、JSON 陣列字串、逗號分隔字串三種）。
首次帶 fidelity 閘：`FidelityError: candidate nets=0 nodes=0`（空 schematic，閘正確抓出）。
真 STM32 pruned symbol 已正確 stage 進 token（10446 bytes / STM32N657_FULL ×3 / 63 pins），
compose 仍 `placed: 0`。無 host 產物、無圖。

## RCA（evidence-anchored，已讀真實原始碼坐實）

根因不是「str 沒 parse 成 array」，而是 **facade 把「使用者指定 symbol_dir」與「KiCad 標準庫」當互斥而非合併**：

1. **`services/mcp/server.py:153`** — `_h_compose`:
   ```python
   symbol_dirs=a.get("symbol_dirs", "/usr/share/kicad/symbols"),
   ```
   標準庫 `/usr/share/kicad/symbols` **只在 client 完全沒給 `symbol_dirs` 時**當 default 生效。
   一旦 client 給了 token symbol 路徑（放自訂 STM32 pruned symbol），標準庫 default **被整個覆蓋掉**。

2. **`packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:380`** — `load_symbol`:
   ```python
   dirs = [symbol_dir] if isinstance(symbol_dir, (str, Path)) else list(symbol_dir)
   lib_path = next((Path(d)/f"{library}.kicad_sym" for d in dirs if (Path(d)/f"{library}.kicad_sym").exists()), None)
   ```
   拿到的單一 dir 只含 token 路徑；R/C/L 等 passive 的 symbol 在標準庫 `Device.kicad_sym`
   （已確認存在，`/usr/share/kicad/symbols/Device.kicad_sym` 2.2MB），但那個 dir **不在 `dirs` 裡**
   → `Device.kicad_sym` not found → 52 元件全 symbol 解析失敗 → `placed: 0`。

3. **`packages/eda-bridge/bodesign_eda_bridge/composer.py:1582`** — `compose_schematic`
   本身也不主動合併標準庫，完全依賴呼叫端傳完整 dir list。

**核心缺陷**：使用者必須**同時**要兩者（自訂 symbol 在 token、passive symbol 在標準庫），
但 facade 的 `.get(default)` 語義使得「給了自訂路徑」⇒「丟掉標準庫」，兩者無法兼得。
這是引擎設計缺陷，非 arg 傳法問題（consumer 已試 3 種傳法坐實無解）。

## Fix proposal（platform owner 定奪）

在 **facade 層（server.py:153）** 把使用者 `symbol_dirs` 與標準庫**合併**成 list，而非覆蓋：
```python
_user_dirs = a.get("symbol_dirs")
_dirs = ([_user_dirs] if isinstance(_user_dirs, str) else list(_user_dirs or [])) + ["/usr/share/kicad/symbols"]
symbol_dirs=_dirs,
```
（或在 `compose_schematic` / `load_symbol` 層永遠 append 標準庫作為 fallback dir，擇一即可。
避免兩層都做導致重複。標準庫路徑應取 `DEFAULT_SYMBOL_DIR` 常數，不硬編。）

## Explicitly NOT bugs

- kiutils / doctrine.md 缺失 — 那是**上一張 BR**（BR_kiutils-missing，commit b96263f），已修，與本 bug 無關。
- consumer 的 arg 傳法 — 已試 3 種，全數 `placed:0`，非傳法問題。
- SMPS L=TBD 決策 — consumer 側 spec 正確（僅 C_SMPS_IN/OUT、無 L_SMPS、U1 網路未動），與本 bug 無關。
- fidelity gate — 運作正確（空 schematic 時正確 raise FidelityError）。

## Validation plan

修後在 ee worker 內用 aiguard MCU core spec 重跑 compose：
- 期望 `placed: 52`（非 0）
- fidelity gate 通過（candidate nets/nodes 非 0）
- 產出可 render 的 .kicad_sch
consumer spec 已存 `/run/user/1000/mcu-core-compose/`（spec.json / stm32_pruned.kicad_sym）可直接重測。
