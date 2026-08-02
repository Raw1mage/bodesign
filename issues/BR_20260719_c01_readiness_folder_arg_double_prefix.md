# BR: c01_readiness `folder` arg double-prefixes rel paths → false-negative all-missing

- Date: 2026-07-19
- Axis: A（工具可用性——參數語義缺陷）
- Origin: thesmart_products plan aiguard_c01-c04-autonomous-delivery, task 1R.6 磨擦盤點

## Symptom

`gate.py c01_readiness --repo <abs>/03.aiguard --arg folder=C01-ID` 回報
`readiness_pct: 0, dod_ok: false`，所有 artifact `missing`，evidence 列的候選路徑為
`C01-ID/Ai file/Design_Direction.md` 等——但這些 rel path 是相對 `folder` 解析的，
實際檢查的是 `03.aiguard/C01-ID/C01-ID/...`（雙重前綴），全部落空。

同一 repo 改用預設 folder（`--repo .../03.aiguard`，不帶 folder arg）則正確回報
5/5 present、`dod_ok: true`。

## Expected

`folder` arg 與 rel_path 應只擇一承擔 stage-dir 前綴：либо rel_path 相對 folder 時
不再含 `C01-ID/` 前綴，либо folder 僅作 repo-root override。同一份交付在兩種呼叫下
verdict 必須一致；假陰性 all-missing 會誤導 agent 重造已存在的交付物。

## Repro

```
BODESIGN_SRC=~/projects/bodesign python3 <skill>/scripts/gate.py c01_readiness \
  --repo /home/pkcs12/GoogleDrive/Projects/thesmart_products/03.aiguard --arg folder=C01-ID
# → all missing (false negative)
# omit folder → all present, dod_ok true
```

## Suggested fix

Normalize：若 `folder` basename 已等於 stage dir 名（C01-ID），strip rel_path 的
stage 前綴再 join；或在 readiness 家族統一「folder = stage dir 絕對/相對路徑，
rel_path 不含 stage 名」的契約並套用到全部 c0x_readiness verbs（c00/c02/c04/c05/c06
可能同病）。
