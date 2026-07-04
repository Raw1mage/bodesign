# BR: c00 DoD manifest — rf_requirements 漏 `02_build/` 對稱路徑,誤導 agent 搬檔

## 現象(硬證據)

`03.aiguard/C00-PRD` 交付物完全合規(`.docx` 在 stage root、`.md` 中間產物在 `02_build/`),但 `c00_readiness` 持續回報:

```
readiness_pct: 100 | dod_ok: False | missing_blocking: ['rf_requirements']
```

檔案實況:
- `C00-PRD/C00_射頻需求規格書.docx`  ← stage root(交付物)✅
- `C00-PRD/02_build/RF_Requirements.md`  ← 中間產物層 ✅(符合 bodesign stage-structure)

manifest `templates/c00.dod.json` 兩個 row 對「.md 中間產物在 `02_build/`」處理不對稱:

| row | any_of 含 `02_build/` | 結果 |
|---|---|---|
| `prd` | ✅ `C00-PRD/02_build/Project_Requirements.md` | 命中 → present |
| `rf_requirements` | ❌ 只列 3 個 stage-root 候選 | miss → 假性 blocking |

## RCA

`guide_dod.py assess_guide_dod` 依 manifest `any_of` 逐路徑 `_match_any`。`prd` row 的 any_of 已含 `02_build/` 對稱路徑、`rf_requirements` row 漏列。bodesign stage-structure 明訂 `.md` 是可 GC 中間產物、放 `02_build/`;stage root 只放 `.docx`。因此 RF 交付物放對了位置,是 manifest 的候選清單不對稱 → 假性 blocking。

**二次傷害(agent 行為層)**:假性 blocking 誘導 agent 反覆「把 `.md` 搬到 stage root 迎合 gate」,違反 stage-structure 且被使用者制止。gate 的假訊號直接製造了錯誤的修復動作。

## 建議修復(已施作)

`templates/c00.dod.json` 的 `rf_requirements.any_of` 補上對稱路徑:

```json
"any_of": ["C00-PRD/RF_Requirements.md", "C00-PRD/RF_Requirements.generated.md",
           "C00-PRD/C00_射頻需求規格書.md", "C00-PRD/02_build/RF_Requirements.md"]
```

驗證:`c00_readiness --arg folder=03.aiguard` → `dod_ok: True`、`rf_requirements` status=present(ev=`C00-PRD/02_build/RF_Requirements.md`)。

## 影響範圍

- 任何遵守 stage-structure(RF `.md` 放 `02_build/`)的 C00 package 都會撞到假性 blocking。
- 應**系統性稽核**其他 stage 的 `.dod.json`:凡有 `02_build/` 對稱路徑的中間產物 row,須比照 `prd`/`rf` 補齊,避免同類不對稱。C01–C07 manifest 待查。

## 驗證手段

- `python3 skills/bodesign/scripts/gate.py c00_readiness --repo <proj> --arg folder=03.aiguard` → dod_ok True。
- JSON 合法性:`json.load` 通過。
- 回歸測試 `tests/test_guide_dod.py` 因環境缺 `bodesign_reverse_core` 姊妹套件無法在本機直接跑(既有環境問題,非本改動引入);建議補一條測 `02_build/` 對稱命中的 case。
