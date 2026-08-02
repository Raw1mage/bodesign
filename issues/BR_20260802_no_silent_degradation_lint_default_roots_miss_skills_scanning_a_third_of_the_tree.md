# BR_20260802 — no-silent-degradation lint 的預設 root 漏掃 `skills/`：預設回 12 筆，實際全樹 70 筆

- **Status**: OPEN（訊噪比已量測完成 2026-08-02，修法已裁決；待實作）
- **Owner**: `(default)`
- **Family**: `silent-success`
- **Filed at**: 2026-08-02（coordinator `ses_04db7a1c5ffelvbxyLP1p6xlRH`；由 BR_20260731 handler 在第二輪回報「基線 11 vs 實測 12」的疑點延伸量測而發現）
- **Severity**: real — 一個用來偵測「靜默降級」的 lint，本身靜默地只看了三分之一的程式碼
- **Component**: `packages/workflow-core/bodesign_workflow_core/checkers/no_silent_degradation.py:508` × `ragbase/control/no-silent-degradation/README.md`
- **Fix venue**: 同 repo（`silent-success` family），可內聯修
- **時區**: Asia/Taipei (UTC+08:00)

## Symptom（實測數據）

```
$ check_paths(['packages','services'])        # ← CLI 預設（:508）
  total=12   L2=9  L6=3    files_scanned=137

$ check_paths(['packages','services','skills'])
  total=70   L2=60 L6=10   files_scanned=228
```

**58 筆 finding 對預設執行完全不存在**，其中包含 `skills/bodesign/engines/kicad/scripts/`
下 91 個 python 檔的全部命中——那正是 BR_20260731 第四個 vacuous-pass 站點
（`_check_rf_reference_values`）所在的目錄。

而 `:503-506` 的程式碼註解寫著：

```python
# Default roots must match the documented baseline in
# ragbase/control/no-silent-degradation/README.md (11 findings). Scanning only
# two sub-packages under-reported by 6 (all of services/), so a CI run on the
# default would have gone green while services/mcp/server.py still carried L2s.
targets = sys.argv[1:] or ["packages", "services"]
```

這段註解**記錄了同一個病的上一次發作**（當時漏的是 `services/`，已修），
但修法是把 `services` 加進預設清單——**沒有處理「清單是手寫的、下一個目錄照樣會漏」這個根因**。
`skills/` 就是下一個。

## 這是哪一種缺陷

**`L10` 這條規則自己的活反例。** 該模組 `:447` 定義：

```python
"""What the scan ACTUALLY covered (BR_20260729 L10)."""
```

L10 的立意是「掃描/檢查類工具必須回報實際覆蓋範圍」，README:670 逐字寫著它的由來：

> 掃描/檢查類工具必須回報實際覆蓋範圍（這就是 L10 的由來——README 記 11 筆但預設只跑 5 筆 = CI 假綠）

`Coverage` 機制**確實有被實作**且無條件列印（`:517-519`），所以資訊不是完全缺席——
但它報的是 `files_scanned=137`，一個**沒有分母的分子**。137 個檔案聽起來很多；
沒有任何一處告訴你全樹有 228 個，也沒有任何一處告訴你 `skills/` 從未進入 root 清單。

**「掃了 137 個檔案，0 個 L9 命中」與「L9 覆蓋的程式碼有三分之二沒被看過」共用同一份輸出。**

## RCA（mechanism）

`:508` 的 `targets = sys.argv[1:] or ["packages", "services"]` 是**手寫白名單**。
repo 有三個含 python 的頂層目錄（`packages/` / `services/` / `skills/`），清單列了兩個。

沒有任何機制在「新增一個含 python 的頂層目錄」時提醒清單需要更新——
與 `batch` description 那條手寫白名單同構（`size === 15` 擋得住增刪、擋不住抽換）。

## Fix proposal

**★ 推薦**：讓預設 root **從檔案系統推導**而非手寫——列舉 repo 根下所有含 `*.py`
的頂層目錄（排除 `.venv` / `__pycache__` / `.git`），這樣新目錄自動納入。

**同時**：`Coverage` 的輸出必須帶分母。目前是 `files_scanned=137`，應為
`files_scanned=137 / repo_python_files=228 (uncovered_roots=['skills'])`。
**一個沒有分母的覆蓋率數字無法揭露自己的不完整**——這正是 L10 要解決的問題，
而它目前的實作只做了一半。

**不建議**：只把 `skills` 加進清單。那是第三次用同一個修法修同一個病
（第一次漏 `services/`、這次漏 `skills/`），根因是「清單是手寫的」，不是「清單少了某一項」。

## Validation plan

- **控制組（必要）**：修復前斷言預設執行的 finding 數 < 全樹掃描數（證明缺口存在）。
- 修復後：預設執行的 finding 數 == 顯式傳入全部三個 root 的數量。
- **新目錄迴歸**：在 scratch 建一個含已知 L2 缺陷的新頂層目錄，斷言預設執行**會**抓到它
  （證明推導機制真的動態，不是把三個目錄寫死）。
- **分母**：斷言 Coverage 輸出同時含 scanned 與 total，且在有未覆蓋 root 時明確列出。
- **README 基線同步**：文件記載的數字必須與修復後的預設執行一致，並註明掃描範圍。

## 訊噪比量測——第一輪（13/58 抽樣），已被下方窮舉量測取代

原本此段標為「未確認、修這張 BR 前必須先量測」。已量測，**結果改變了推薦修法**。

**規則分布**（實測；控制組見下）：

| root | findings | files_scanned | 密度 | 規則 |
|---|---|---|---|---|
| `skills` | **58** | 91 | **0.64/檔** | L2×51、L6×7 |
| `packages` | 6 | 128 | 0.047/檔 | L6×3、L2×3 |
| `services` | 6 | 9 | 0.67/檔 | L2×6 |
| `docs` | 0 | **0** | — | — |

⚠ **`docs/` 是空對照，證明不了任何事**（它沒有 `.py` 檔，掃描器根本沒啟動）。
真正有效的鑑別力證據是**密度差異**：`skills/` 是 `packages/` 的約 13 倍。

**人工稽核 13 筆（22% 樣本）**：**6 真陽性 / 7 誤報 ≈ 46% 訊號**。
6 個真陽性中只有 **3 個是中高嚴重度**，全部在 `analyze_schematic.py`、且全是同一個形狀
（datasheet metadata 讀不到 → 判決與「本來就沒有 datasheet」完全相同）。
**實際可行動的訊號約 23%。**

⚠ **樣本偏誤（誠實標註）**：稽核者刻意挑了看起來最高風險的 L2，
所以 51 筆 L2 的真實真陽性率**可能更低**，不會更高。46% 不是點估計。

### 最嚴重的一筆

`skills/bodesign/engines/kicad/scripts/analyze_schematic.py:6468`（`_read_ic_abs_max`）：

```python
except (json.JSONDecodeError, OSError):
    pass
if not extract_path.exists():
    return None
```

`datasheets/extracted/manifest.json` 損毀或讀不到 → 該 IC 被**靜默排除在絕對最大額定電壓
derating 檢查之外**（呼叫端 `:6535`）→ `derating_issues` 保持空 → 報告呈現「無 derating 問題」。
**一個 PASS 形狀的答案，由「沒有檢查」產生。而它守的是過壓安全。**

### 一個 lint 抓不到的漏網（recall gap）

`skills/bodesign/engines/kicad/scripts/analyze_pcb.py:1998`：

```python
except (ValueError, TypeError):
    thickness += 0.2      # 靜默塞入一個沒有來源的 0.2mm 介電厚度
```

這比 51 筆 L2 中的多數**更嚴重**（它不只是丟失資訊，是編造一個數值參與 `best_neighbor` 計算，
會選錯參考層），而 **L2 看不到它**——因為 handler body 既不是 `pass` 也不是 log call。
**規則的形狀決定了它能看見什麼；擴大掃描範圍不會讓它看見這個。**

## 窮舉量測（2026-08-02，55 個 unique 站點全數人工判讀）

第一輪是 22% 抽樣；本輪把 **55 個 unique 站點全部讀完**（非抽樣），另追 6 個模糊站點的完整 caller 鏈。

```
TP=26   FP=29   unclassified=0      （unique 站點）
TP=27   FP=31                        （raw-58 基準）
精確度 26/55 ≈ 47%
```

### 一個重要的 dedup 發現：**58 筆 findings ≠ 58 個站點**

```
raw=58   unique(path,line,rule)=55   dup=3
```

三筆重複是**嵌套 `def` 導致同一行原始碼被報兩次**（`what_if.py:1205/1211` 同時落在
`_run_emc_preview` 與 `_run_emc` 底下；`analyze_schematic.py:6468` 同時落在 `analyze_voltage_derating`
與 `_read_ic_abs_max` 底下）。**任何拿「58」當分母算訊噪比的人都會算錯。**

### 抽樣估計的準確度（及它標錯的那一格）

| | 第一輪抽樣 | 窮舉 |
|---|---|---|
| 訊號率 | 6/13 ≈ **46%** | 26/55 ≈ **47%** |

估計得準。**但第一輪標註的「樣本偏誤方向」說反了**——當時寫「真陽性率可能更低，不會更高」，
實測是微幅**更高**。記下來因為這正是本 BR 在講的事：**一個方向性的保守宣稱，若沒有被量測，
就只是一個講得很謹慎的猜測。**

### 四筆 fab-safety 類真陽性（coordinator 親手讀原始碼覆核，4/4 成立）

`analyze_pcb.py:713` [L2]：`pad_info["drill"] = float(drill_val)` 失敗則 `pass`——
**一個 drill 格式損毀的 THT pad，其 dict 與 SMD pad 逐位相同**。下游 fab 匯出讀成表點。

`analyze_pcb.py:1994` [L6]：`t = stackup[k].get("thickness")` 後 `if t is not None:` **無 else**，
缺層貢獻 0.0 → 那層反而贏得 `if thickness < best_thickness` 而被選為參考平面。
⚠ 此處與下方「漏網」段的 `:1998` **是同一個 `for` 迴圈裡相鄰的兩個缺陷**：
`:1994` 是「欄位不存在 → 靈」（L6 看得到），`:1998` 是「欄位壞掉 → 編造 0.2」（L2/L6 都看不到）。

`analyze_pcb.py:4498` [L6]：`required_dia = nc.get('via_diameter')` 無 else，且 `rules_checked`
**只在違規路徑遞增**→ 未檢查的 net class 被報成「N rules checked, no violations」。

`kicad_utils.py:1477` / `:1505` [L2 ×2]：`except OSError: pass` 後 `return False`——
**`is_referenced_as_child` 對「檔案讀不開」回答「未被引用」**，一個讀不到的子圖頁因此被提升為 root schematic。

### 五種誤報結構形狀（這些才是修法的依據）

| # | 形狀 | 站點數 | 代表 |
|---|---|---|---|
| FP-1 | `finally` / cleanup 區塊內的 handler（`os.unlink`/`os.close`） | 4 | `kidoc_docx.py:267` |
| FP-2 | 探測函式回 `Optional[T]`，**`None` 就是契約** | 4 | `kicad_cli.py:110` `_check_flatpak() -> str \| None` |
| FP-3 | parse ladder：每個 `except` 落到**下一個策略**，終於明確預設 | 6 | `schematic.py:263` → `return PAPER_SIZES['A4']` |
| FP-4 | 用 `print` 而非 drop-named container 報告降級 | 5 | `generate.py:75` |
| FP-5 | [L6] `.get()` 取 **schema 上本就 optional** 的欄位 | 4 | `pcb_graphics.py:294` |

**FP-4 是最尖锐的一個，值得單獨指出**：`schemdraw_templates/generate.py:75` 印的是

```python
print(f"\n{len(made)}/{len(matches)} matched block(s) rendered into {out_dir}")
```

**分子與分母俱全**——這正是本 checker 整個存在目的要求的那種紀律，**却被 checker 自己標記為缺陷**。
`_records_drop()` 只認容器**名稱**含 `drop/skip/fail` 的 append，看不見 `print`。
（coordinator 抽驗 FP-3 / FP-4 / FP-5 各一筆，**3/3 成立**。）

### 誤報集中的根因

> `packages/` 是 IR 轉換的函式庫碼，吐掉的異常真的會污染回傳的量測值；
> `skills/` 是 engine / CLI 碼，它的 `except: pass` 大量屬於**能力探測、格式 ladder、溫檔拆除**
> 這三種形狀——吐掉本身就是正確設計。

**同一條規則在兩種程式碼上的正確率不同，這本身就是不能直接把 `skills/` 加進預設的理由。**

### L8/L9 的零是真零（非死規則）

```
POS_L9 -> ['L9']    NEG_L9 (同程式碼 + 零長度 guard) -> []
POS_L8 -> ['L8']    NEG_L8 (換接收者)                -> []
```

這兩條規則在 `skills/` 下 0 命中，**且已證明它們在該命中時真的會命中**——所以 0 是證據，不是沉默。

### 控制組

| 控制組 | 證明了什麼 |
|---|---|
| `check_paths(["skills_TYPO"])` → `n=0, files_scanned=0, missing_roots=[...]` | 58 是 91 個**真的被解析過**的檔的結果，非路徑靈解析 |
| `include_advisory=True` → 1060（L1=1002） | 58 是 tier 過濾效果，不是掃描上限 |
| dedup 58 raw vs 55 unique | 「58 findings」不等於「58 站點」 |

## 修法裁決（依量測結果，2026-08-02）

**掃描 `skills/`：要。直接加進預設 root：不要（順序反了）。**

靜默略過 91 個檔案在這個模組上是不可辯護的——它自己的 `Coverage` docstring（`:447`）
就是為了「0 findings 不得被讀成從未掃描」而寫的，**現行預設正是該模組自己的反模式**。

但把 58 筆（46% 誤報、僅 23% 可行動）直接倒進一個會擋人的閘，會重演該 docstring 自己
診斷過的 L1 失敗：**「19 筆雜訊淹掉 3 筆真訊號，最後沒人跑這條 lint」**。

**正確順序：先精煉規則，再擴大範圍（同一個 commit）。**
三條窄豁免可消掉稽核樣本中 7 個誤報的 6 個：

1. `finally` / cleanup 區塊內的 handler（best-effort 拆除，無可觀測輸出）
2. handler 之後緊接 `return None`／sentinel 且函式回傳型別為 `Optional`
   （**`None` 本身就是明確的缺席標記**，規則的前提在此不成立）
3. L6 守的是 **schema 上本來就 optional 的欄位**，而非呼叫端提供的 key

精煉後若 `skills/` 的誤報率仍 >30%，該目錄的 L2 先降為 advisory 一個週期。
**基線數字必須在同一個 commit 重新錨定**（README 記載 11、實測 12）。

## Cross-ref

- `issues/KB_20260729_silent_degradation_antipattern_invariant_and_lint.md` — 該 lint 的 KB 條目
  （標記 PARTIAL）。
- BR_20260731（`b429b06` + round-2 commit）——本 BR 由其驗證過程發現；
  第四個站點 `_check_rf_reference_values` 正位於漏掃的 `skills/` 目錄下，
  **它是被人工發現的，不是被 lint 抓到的**。
