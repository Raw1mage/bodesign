# BR_20260802 — no-silent-degradation lint 的預設 root 漏掃 `skills/`：預設回 12 筆，實際全樹 70 筆

- **Status**: OPEN
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

## 未確認（誠實標註）

- 未逐一分類那 58 筆新增 finding 中有多少是真陽性、多少是誤報。
  `skills/` 下多為 KiCad 引擎腳本，L2（except 只有 pass/log 而函式有回傳值）在該類程式碼
  的訊噪比**未經量測**。**這會影響修法**：若誤報率高，正解可能是「納入掃描但分層報告」
  而非「直接讓 CI 對 70 筆變紅」。**修這張 BR 前必須先做這個量測。**
- 未確認是否有 CI 實際在跑這個 CLI 入口（`if __name__ == "__main__"`），
  若無，則「CI 假綠」的後果目前是潛在而非已發生。

## Cross-ref

- `issues/KB_20260729_silent_degradation_antipattern_invariant_and_lint.md` — 該 lint 的 KB 條目
  （標記 PARTIAL）。
- BR_20260731（`b429b06` + round-2 commit）——本 BR 由其驗證過程發現；
  第四個站點 `_check_rf_reference_values` 正位於漏掃的 `skills/` 目錄下，
  **它是被人工發現的，不是被 lint 抓到的**。
