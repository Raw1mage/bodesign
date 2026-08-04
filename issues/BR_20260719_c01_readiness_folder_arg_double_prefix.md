# BR: c01_readiness `folder` arg double-prefixes rel paths → false-negative all-missing

- **Status**: PARTIAL — 內部 folder 契約已統一（`44deecb`），**但標題主張的 c01 雙前綴假陰性仍可重現**（見文末「2026-08-04 覆核」）。**留頂層，不歸檔。**
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

---

## 2026-08-04 覆核（by `ses_04db7a1c5ffelvbxyLP1p6xlRH`）

**本檔原本沒有 Status 行**（三張例外之一，另見 `BR_20260804l`）。

這張 BR 有**兩個可分辨的層面**，而它們狀態不同——這正是它不能標 FIXED 也不能標 OPEN 的原因：

### 已修：內部路徑契約層

`44deecb`（已驗存在，**控制組：假 sha `deadbee` 回 `fatal: unknown revision`**）
統一了 readiness 家族「`folder` = 產品根，stage 前綴內部推導」的契約；
`readiness_common.py:66-109` 的 `stage_dir_arg_detail()` 專門偵測並具名回報
「folder 就是 stage dir」的誤用（**不做靜默 normalize**，符合本 repo 的 no-silent-fallback 天條）。
`tests/test_readiness_folder_contract.py` 14 passed。

### 仍 OPEN：**c01 這條路徑沒有接上那個偵測器**

```
grep -c stage_dir_arg_detail  c01_id_package.py  ->  0     <- 沒接
控制組 同一支 grep on  c02_me_package.py  ->  2     <- 證明 grep 有牙
```

機制鏈（静態證據，未實跑——見下方未量）：
`gate.py:871-874` 對相對 `folder` 一律 `os.path.join(repo, val)`
⇒ `folder=C01-ID` 變 `<repo>/C01-ID`；
接著 `_c01_resolve_output`（`c01_id_package.py:106`）的候選 rel 每個又以 `C01-ID/` 開頭
⇒ 實際 stat `<repo>/C01-ID/C01-ID/...`。

**`readiness_common.py:75-77` 的原始碼註解自承「still reproducible at HEAD」**——
判 FIXED 會與程式碼自己寫的話矛盾。

### 未量（不得讀成已驗）

**未實跑 `gate.py c01_readiness --arg folder=C01-ID`**。OPEN 判定來自四條靜態證據鏈
（join 邏輯 + 候選 rel 前綴 + 碼註解自承 + grep 證實未接偵測器），
要鐵證需要一個真實的 `C01-ID/` fixture repo。

### scoped remainder

c01 路徑接上 `stage_dir_arg_detail()`（或等效的雙前綴偵測）。
**不要順手改成靜默 strip 前綴**——那是 fallback，c02 那邊刻意選了具名回報而非自動修正。
