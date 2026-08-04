# BR_20260802 — `test_composer_draftsman` 的 11 個 error 是兩個獨立成因，其中 9 個是測試呼叫一個不存在的參數

- **Status**: OPEN
- **Severity**: P2 — 測試套件缺陷，非生產缺陷（生產端無任何呼叫端受影響）
- **Family**: `schematic-engine`（**unassigned** — 2 sessions probed，both declined）
- **Filed**: 2026-08-02 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`（bodesign 值星官）
- **Discovered**: 在驗證 `316150f`（L6 閘修復）時，需要分辨「我改壞了」與「本來就壞」而建的基線控制組

---

## §1 一句話

`tests/test_composer_draftsman` 回 `FAILED (errors=11)`。這 **11 個不是同一個缺陷**：

| 數量 | 例外 | 成因 |
|---|---|---|
| **9** | `TypeError: _symbol_geometry() got an unexpected keyword argument 'scale'` | 測試傳了函式簽章沒有的參數 |
| **2** | `ValueError: INK_DENSITY_LOW: page=pf_sparse / sp_filled paper=A3 ink_density=17` | 另一個獨立缺陷，本 BR 不追 |

**「11 個 error」這個數字本身會誤導**——它讀起來像一個成因的 11 個症狀。

---

## §2 這不是 `316150f` 造成的（基線控制組）

`316150f` 修改 `kicad_emit.py:1515`。為分辨因果，把 **HEAD 版**的 `kicad_emit.py` 複製進獨立 package tree 重跑同一套測試：

```
BASELINE (HEAD 版檔案)   rc=1  errors=11
WITH MY CHANGE           rc=1  errors=11
error 集合 diff          IDENTICAL
CONTROL: 自我 diff        SAME   ← 證明比對器有判別力
```

**兩側 error 集合逐字相同 ⇒ 既有缺陷。**

> 沒有這個基線，`FAILED (errors=11)` 會被讀成「我的改動弄壞了 11 個測試」——**「我改壞了」與「本來就壞」共用同一個 `FAILED`。**

---

## §3 量測

### §3.1 真實簽章（`kicad_symbol.py:140`）

```python
def _symbol_geometry(pins: list["KiCadSymbolPin"], min_half_h: float = 20.0,
                     pin_pitch: float = _PIN_PITCH,
                     pin_length: float = _PIN_LENGTH) -> _SymbolGeometry:
```

**沒有 `scale`，也沒有 `sides`。**

### §3.2 呼叫端分布

```
全部呼叫端                      7
生產端傳 scale=                 0     ← 生產完全不受影響
測試端傳 scale=                 2
```

| 檔案 | 行 | 傳入 | 版控狀態 |
|---|---|---|---|
| `tests/test_dd14_text_graphics_clearance.py` | 120 | `sides=sides, scale=1.0` | **UNTRACKED**（他人 WIP） |
| `tests/test_composer_draftsman.py` | 1348 | `scale=scale` | TRACKED |

`test_dd14` 那個檔**同時**傳了 `sides=` 與 `scale=`——兩個參數都不在簽章上。

---

## §4 未驗證 ⚠

**「這個 API 是被移除了」還是「測試寫的是一個規劃過但從未落地的 API」——沒有量測可以區分。**

嘗試過 `git log -S'scale' -- kicad_symbol.py`，回 1 個 commit；但**控制組 `git log -S'_symbol_geometry'` 也回 1**（bogus token 回 0）。treatment 與 control 同值 ⇒ **這個探針在此檔上沒有判別力**，該檔 commit 數本來就少。

且本 repo 的 `AGENTS.md §6.1` 已記錄：**在大量工作未 commit 的樹上，`git log -S` 回空只證明「沒有被 commit 過」，不證明「從未存在」。** 故不採信任一方向。

---

## §5 為什麼是 P2 而非 P1

生產端 `scale=` 呼叫數為 **0**——`kicad_emit.py` 走的是另一條路徑（`_scale_symbol_geometry(block, scale)`，對已產生的 block 做字串級縮放，不經 `_symbol_geometry`）。

所以這是**測試套件與實作漂移**，不是生產缺陷。但它的代價是真的：

> 一個恆紅的測試檔會讓下一個人無法用它分辨自己改壞了什麼。

本 BR 的 §2 就是被迫繞過它的實例——我必須自建基線控制組才能驗證一個一行改動。

---

## §6 修法選項（未裁示）

1. **測試對齊實作**：把 `scale=` / `sides=` 從兩個測試呼叫端拿掉（若這些參數本就不該存在）
2. **實作對齊測試**：在 `_symbol_geometry` 上加 `scale` / `sides`（若測試表達的是真實需求）
3. **標記 skip 並註明理由**：若那些測試對應的是未落地的規劃

**選 1 或 2 取決於 §4 那個未解的問題**——不知道 API 是被移除還是從未落地，就不知道哪一側是對的。**先解 §4。**

---

## §7 派工提示

- `test_dd14_text_graphics_clearance.py` 是 **UNTRACKED**，屬他人未 commit 工作。**動它之前必須先確認 owner**，不可逕自修改或 `git add`。
- 那 2 個 `INK_DENSITY_LOW` 是獨立成因，另計，不要一起修。
- 驗收判準：`errors=11` → 應降至 `2`（僅剩 INK_DENSITY_LOW）。**若降到 0，表示有人順手改了不該改的東西。**
