# BR_20260802 — stale `.pyc` 讓 mutation proof 靜默失效：同一秒內、同長度的改動，Python 不會重新編譯

- **Status**: OPEN — STILL-VALID on 2026-08-05, **and prescription #1 (`python3 -B`) is MEASURED WRONG — see §Correction**
- **Owner**: unassigned
- **Family**: `G13-harness-disclosure`
- **Severity**: real — 這個機制會讓**驗證程序本身**回報「已驗證」而其實什麼都沒驗到
- **Component**: 任何用「改壞 → 跑測試 → 改回」做 mutation proof 的流程（本 repo 全部 Python 套件）
- **Filed at**: 2026-08-02
- **時區**: Asia/Taipei (UTC+08:00)
- **Filed by**: `ses_0c87bab06fferQ0umBs2Nybb5U`（在跑 BR_20260802 fidelity gate 的 mutation proof 時踩到）

## 現象

做 mutation proof：把 `_CLEARANCE_EPS_MM = 1e-9` 改成 `1e-3`，跑測試（正確轉紅），
再 `cp` 回好的版本。然後：

```
cmp -s kicad_emit.py kicad_emit.py.good   →  位元組相同（exit 0）
grep -n "_CLEARANCE_EPS_MM = " …          →  1957:_CLEARANCE_EPS_MM = 1e-9
python3 -c "from …kicad_emit import _CLEARANCE_EPS_MM as e; print(e)"
                                          →  0.001        ← ？？？
```

**檔案在磁碟上是對的，直譯器讀到的是舊的。** 而測試繼續紅，讀起來像「我的修法有問題」。

## 根因

CPython 的 `.pyc` 失效判準是 **`(source_mtime_秒, source_size)`**——不是內容雜湊
（雜湊模式要 `PYTHONPYCACHEPREFIX` / `--invalidation-mode checked-hash` 才會啟用，預設不是）。

實測：

```
pyc 記錄     source_mtime=1785669649  source_size=164524
實際檔案     source_mtime=1785669649  source_size=164524
match? mtime=True size=True  →  pyc 被視為 VALID
```

兩個條件同時成立，因為：

1. **`1e-9` 與 `1e-3` 字元數相同** → `size` 不變
2. **mutate 與 restore 落在同一秒** → `mtime` 的秒數不變

於是 Python 直接用了 mutation 版本的 bytecode。

## 為什麼這比「測試沒跑」更糟

**它有一個看起來正確的成功態。** 我當時手上有三個訊號：

- `cmp` 說位元組相同 ✓
- `grep` 說常數是 `1e-9` ✓
- 測試說紅 ✗

前兩個都是真的，第三個也是真的，**但它們描述的不是同一份程式碼**。
沒有任何一個訊號會說「你正在執行的不是你正在讀的那個檔案」。

更精確地說：**我原本用來確認 restore 成功的判準（`cmp` + `grep`），
在這個失效模式下必定回報成功**——它們檢查的是磁碟，而失效發生在 bytecode 快取。
判準與缺陷正交，所以它永遠攔不到。

## G13 判準：那一格的資訊，系統當下有沒有？

**有。** pyc 檔頭的前 16 bytes 就寫著它假設的 `source_mtime` 與 `source_size`，
`importlib` 每次 import 都讀它。系統完全知道自己在用快取，**它只是不說**。

而且失敗方向是最安穩的那個：你以為驗證跑過了。

## 影響範圍

任何符合以下形狀的驗證都受影響：

- mutation proof（改壞→測→改回）
- A/B 比較（換檔案→測→換回）
- 任何在**一秒內**完成的「改一個常數再跑」迴圈

**字元數相同的改動特別危險**，因為那是最常見的 mutation 形式：
`1e-9`→`1e-3`、`>=`→`> `、`True`→`Fals`（誤植）、數字調參。

## ⚠ Correction（2026-08-05，`ses_030847a3affev5QmJelNWqSK41` 重驗時量到）

**下方修法 #1 的括號說明「不寫也不讀 bytecode」是錯的，而這個錯會造成假安心。**

`-B` 只設定 `sys.dont_write_bytecode` ——它**阻止寫入**，**不阻止讀取既有的 `.pyc`**。
所以在本 BR 描述的情境（`.pyc` 已經存在且被判定為 valid）下，`-B` **完全沒有保護力**。

```
情境：mod/__init__.py 已被 import 過（pyc 已存在），
      接著同長度 mutate + 還原 mtime  ->  pyc 仍被視為 valid

  disk truth                     EPS = 1e-3
  T1 python3（預設）              1e-09      <- stale
  T2 python3 -B                   1e-09      <- stale，**與預設完全相同**
  T3 PYTHONDONTWRITEBYTECODE=1    1e-09      <- stale
  T4 rm -rf __pycache__ 後         0.001      <- 唯一正確

ACCEPTING CONTROL（證明探針有判別力）：
  無既有 pyc 時，-B 讀 disk 正確     4.2
```

**T4 是唯一有效的處置。** T2 與 T1 共用同一個輸出——
這正是本 BR 在講的那個形狀，**發生在本 BR 自己開的處方上**。

**`-B` 唯一真正的作用是「不留下 `.pyc` 給下一次」**（預防），
對「這一次已經存在的 stale `.pyc`」（治療）無效。兩者不可互換。

⇒ **正解**：mutation proof 前後一律
`find . -name __pycache__ -exec rm -rf {} +`（下方 #2），
或以 #3 從直譯器問回來。`-B` 可加，但**不得單獨作為保護**。

此更正同步影響 `BR_20260804j` §4.5（措辭相同）。

## 修法形狀

三個層次，可疊加：

1. ~~**驗證腳本一律用 `python3 -B`**（不寫也不讀 bytecode）。~~
   **上行已被上方 §Correction 推翻——`-B` 不讀既有 pyc 是錯的，它照讀。**
   `-B` 僅作為「不留 pyc 給下一次」的預防，**不可單獨作為本 BR 情境的保護**。
2. **mutation 前後 `find . -name __pycache__ -exec rm -rf {} +`**。
   比 `-B` 慢，但涵蓋子行程。
3. **驗證「我讀到的就是我執行的」**：mutation 後不要只 `cmp` 磁碟檔，
   要 `python3 -c "import M; print(M.THE_CONSTANT)"` **從直譯器問回來**。
   這是唯一能同時涵蓋磁碟與快取的判準。

**建議把第 3 條寫進派工單的 Verification 欄**——它是「控制組」概念在
import 快取上的實例：不要用磁碟狀態證明執行狀態。

## 本輪的實際處置

四個 mutation proof（M1 union-find seeding / M2 硬編病因 / M3 epsilon 移除 /
M4 epsilon 放寬）**全部以 `-B` 重跑**，結果與原先一致：各自轉紅、restore 後回綠。
所以結論沒有被污染——但**那是重跑之後才知道的**，不是當下就知道。

## Cross-ref

- `code-thinker` §8.1 — 缺席態與失敗態不得共用同一個輸出
- 全域 AGENTS.md「歸責紀律」§ — 那一格的資訊系統當下有沒有
