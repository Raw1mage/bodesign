# BR_20260723d — compose 對 active IC symbol-not-found 靜默產出空框（違反 No-silent-fallback 天條）

- **status**: CLOSED（2026-07-23 內聯修復落地，commit `d1ab7fd`）— `composer.py` 新增 `symbol_load_failures[]` 收集 + fail-loud raise（active IC symbol 載入失敗 → 顯式 error「compose refuses to emit ... pinless active-IC empty boxes」），passive ≤2-pin 小方塊降級保留（NOT-bug）；BR_d gate 三案 + draftsman 66/66 aiguard consumer 三方驗收
- **severity**: high（天條缺陷 · 靜默產出不可用圖）
- **repo**: bodesign（當前 repo，electrical design capability 主線 scope 內）
- **discovered-by**: aiguard C03 consumer session（`ses_073a93d09ffe...`）於 wire 渲染驗證中坐實；platform-owner session（`ses_0c87bab06ffe...`）RCA 定案
- **related**: BR_20260723_kb_query_...（軌 A）· PC-001 passive-completeness gate（同 philosophy：active IC 缺件校驗）· plan `plans/knowledge_c03-ee-design-kb/`

## Symptom（verbatim，consumer 坐實）

使用者截圖批評 aiguard MCU core 一頁「U1（STM32N657）框內全空、只有邊緣冒出零星 pin label」。
consumer 於 wire 渲染驗證中坐實真因：

> 🔴 U1（STM32N657）symbol 從頭到尾就沒載入過——它一直是個無 pin 空框。
> - spec 的 U1 symbol 欄位 = `stm32n657_full:STM32N657_FULL`（lib 名 `stm32n657_full`）
> - 但 scratch 裡 symbol 檔實際叫 `stm32_pruned.kicad_sym`，且 `symbols/` 子目錄不存在
> - lib 名對不上檔名 → U1 symbol 從未載入 → U1 無 pin → 掛 U1 pin 的所有 net 無從 route wire，只剩晶振等 2-pin net 的 5 條殘 wire
> - 而且連前一棒 A3.5「placed:51」也帶同一個 U1 not-found warning——意味先前每一張 compose 圖（含被使用者罵「格式災難」的 label 圖）U1 都是空框。

**consumer 一路產了好幾張圖都沒發現 U1 全程是空框**——因為引擎只發一個混在一堆 warning 裡的訊息就繼續產出完整圖。

## RCA（platform-owner 坐實，`packages/eda-bridge/bodesign_eda_bridge/composer.py`）

symbol 載入失敗在三處被靜默吞掉，沒有一處對 active IC fail-loud：

1. **`_estimate_bbox` L358-362**：
   ```python
   try:
       _definition, pins = load_symbol(lib_id, symbol_dir, page_scale=_sym_scale)
   except (FileNotFoundError, KeyError):
       _cache[_key] = None
       return None          # ← symbol 檔不存在／lib-id 對不上 → 靜默 None
   ```
2. **`_pin_ct` 建置 L1738-1741**：
   ```python
   try:
       _def, _pins = load_symbol(_c["symbol"], symbol_dirs)
       _pin_ct[_c["ref"]] = len(_pins)
   except Exception:
       _pin_ct[_c["ref"]] = 0   # ← 載入失敗 → 靜默當 0-pin
   ```
   連帶效果：`_is_ic(ref)` 判 `_pin_ct > 2`，0-pin ⇒ **active IC 被誤判為非-IC**，cross-IC label 邏輯、passive 分類全部錯位。
3. **placement L1799-1800**：
   ```python
   if bboxes[c["ref"]] is None:
       warnings.append(f"{c['ref']}: symbol '{c['symbol']}' bbox unavailable; excluded from force-directed placement")
   ```
   → 混入一般 warning 列表、繼續產圖。lint 註解（L137-138）自承「a symbol that fails to load is skipped」。

**根因**：symbol 載入失敗一律降級為 warning + skip + substitute（空框 / 0-pin / 小方塊），繼續產出「看起來完整」的圖。這正是 bodesign 天條 2「No silent fallback：缺幾何 → fail fast + 顯式報錯 + 缺項清單」禁止的行為。一個 **active IC**（多 pin、承載主要連線）的 symbol 缺失，比一顆去耦缺失更根本——PC-001 已為「缺去耦」建了硬 gate，卻無任何 gate 攔「active IC 根本沒 symbol」。

## Explicitly NOT bugs（勿誤修）

- **wire honour 邏輯無誤**：consumer 讀 `composer.py:1661-1663/2090` 交叉坐實 `connection_style="wire"` 確實生效。5 條殘 wire 不是 wire 模式失效，是 U1 無 pin 導致無線可 route。**不要動 wire 渲染路徑。**
- **passive/2-pin symbol 缺失降級為小方塊是可接受的**（passive 無 pin 幾何影響有限）——本 BR 的硬化範圍**只針對 active IC**（pin-count 意圖 > 2 / type=ic 的元件），不是所有 symbol 一律 fail。避免把「passive symbol 可選缺失」也升成 error 造成過度嚴格。
- **consumer 的 stage-file lib-name↔檔名對不上是 consumer 側 stage bug**，consumer 自修——本 BR 修的是**引擎對此的靜默反應**，不是 consumer 的 stage 資料。

## Fix proposal（守天條 + 對齊 PC-001 philosophy）

新增一個 compose 層 fail-visible gate：**active IC（宣告 type=ic 或 spec 意圖多-pin）的 symbol 載入失敗 → 顯式 error（非混入 warning），列缺項清單，預設拒絕產出「完整」圖**。

- 判準：元件在 spec 帶 `type: "ic"`（或 symbol lib-id 標示為 active IC）而 `load_symbol` 拋 `FileNotFoundError/KeyError` → 收集成 `symbol_load_failures[]`（ref, symbol lib-id, reason）。
- 語義對齊既有 no-fallback pattern（C02 `never guesses`、orchestration `SPINE_NOT_INITIALIZED`）：回傳結果帶顯著 `symbol_load_failures` + 一個 blocking 訊號（如 compose result `state=blocked_missing_active_ic_symbol` 或非-warning 的 error finding），讓 consumer/gate 立即看見，而非埋在 warning 堆。
- 不改 passive 小方塊降級（NOT-bug 保留）。
- 可選：對「lib 名對不上目錄任何檔」給更 actionable 的訊息（列出 symbol_dirs 下實際可見的 .kicad_sym 檔名，加速 consumer 診斷 lib-name↔檔名 mismatch）。

## Validation plan

1. 回歸測試：一個 spec 含 active IC（type=ic）指向不存在的 lib-id → compose 回傳帶 `symbol_load_failures`（含該 ref + lib-id）且 **不**靜默回「完整」圖；passive 指向缺失 symbol → 維持小方塊降級（不誤升 error）。
2. 對 consumer 的 MCU core spec（U1 lib-name mismatch 場景）跑，確認引擎現在**顯著**報 U1 symbol 載入失敗，而非只在 warning 堆裡。
3. 既有 compose 測試不退化（passive-heavy spec、正常 spec 全綠）。

## Fix venue

**當前 session 內聯修**（同 repo 同關注點的直接缺陷，在 electrical design capability 主線 scope 內；照 BRNS 邊界規則不需開新 session）。**但納入本輪修與否，等使用者裁決**——本輪主線是「電路設計能力層」（軌 A/B/C），此 BR 是順手坐實的引擎天條缺陷，可 (a) 本輪內聯修、(b) 排入 plan 下一 task、(c) 獨立 BR 待排。
