# BR: c02_readiness provenance 解析根與 constraints 載入根不一致 + dod_ok 工具面缺口

- **Status**: FIXED — 兩個症狀（folder 語義矛盾、缺 dod_ok）都已收斂（見文末「2026-08-04 覆核」）
- Date: 2026-07-19
- Source: thesmart_products aiguard C02-ME 執行（plan aiguard_c01-c04-autonomous-delivery task 2.8）
- Axis: 軸A（工具能用性）
- Severity: medium（造成假 gap，需 caller 猜測繞路）

## §1.5 History Review
- 同族 BR：`BR_20260719_c01_readiness_folder_arg_double_prefix.md`（同構：readiness verb 的 folder 語意混亂——「stage root」vs「product root」兩種解讀在不同 code path 各自為政）。本 BR 是同一架構契約（folder 參數語意）在 c02 的第二次外顯 → 復發證據，根因在共用的 folder-resolution 契約，不在單一 verb。
- KB：未見 owning spec 直接規範 landing-verb folder 語意；provenance.py 是 plan capability_refs-first-emitters DD-2 產物。

## 症狀（可重現）
repo=`thesmart_products`，stage 交付位於 `03.aiguard/C02-ME/`，refs SSOT 位於 `03.aiguard/C02-ME/01_refs/`。

1. `gate.py c02_readiness --arg folder=03.aiguard`：
   - `_load_constraints` 讀 `<folder>/C02-ME/Mechanical_Constraints.json` → **要求 folder=product root**。
   - `collect_provenance_gaps(folder=...)` → `_refs_source_resolves` 解析 `<folder>/01_refs/<source>` → **要求 folder=stage root**。
   - 兩者矛盾：constraints 讀得到時，provenance 永遠 `refs_source_unresolvable`（假 gap，實檔存在於 `C02-ME/01_refs/C02_尺寸凍結表.md`）。
   - 反向帶 `folder=03.aiguard/C02-ME` 則 constraints 全 missing（讀 `C02-ME/C02-ME/...` 雙前綴）——與 c01 BR 同構。
2. `c02_readiness` 輸出**沒有** `dod_ok`/`guide_compliance` 欄位；c02 的 GUIDE-DoD 機檢只存在於 `package_readiness` 的 `c02` block。GUIDE c02-me §Self-verify 指示「run c02_readiness … 讀 dod_ok」→ 照做拿不到 dod_ok，caller 需自行發現要改跑 package_readiness。

## Root cause（一句話）
landing verb 的 `folder` 參數缺乏單一契約：`assess_c02_constraint_readiness` 內部兩條 code path（constraints loader vs provenance resolver）對同一 folder 值採用不同的目錄基準（product root vs stage root），且 c02 readiness 工具面未接 `guide_compliance_for`（c01/c04/c05/c06 都有接，c02 獨缺）。

## 恢復的契約
「一個 readiness verb 的 folder 參數在其所有內部 code path 中指同一目錄」+「每個 cXX_readiness 自帶該 stage 的 dod_ok/guide_compliance（GUIDE 指示與工具面一致）」。

## Fix 建議
1. `assess_c02_constraint_readiness`：provenance 解析基準改為 constraints 檔所在 stage dir（`<folder>/C02-ME/`），或統一 folder 語意為 stage root 並修 `_load_constraints`。
2. c02 readiness result 附掛 `guide_compliance_for(folder, "c02", conditions={"toolchain": ...})`，對齊其餘 stage。
3. 順帶：`gate.py` 在 XDG skills 安裝下需手動 `BODESIGN_SRC`（LANDING_PACKAGES_NOT_FOUND）——error hint 已足夠，但可考慮 fallback 探測 `~/projects/bodesign`。

## Workaround（本次採用）
caller 在 `Mechanical_Constraints.json` 補 scanner 期望的頂層 key（board_outline/component_heights/battery_envelope/provenance），dod 判定改讀 `package_readiness` 的 c02 block（dod_ok:true 已驗）。

---

## 2026-08-04 覆核（by `ses_04db7a1c5ffelvbxyLP1p6xlRH`）

**本檔原本沒有 Status 行**（三張例外之一，另見 `BR_20260804l`）。

兩個症狀分別驗證（我親手跑）：

### 症狀 A：folder 語義矛盾 — 已修

```
c02_me_package.py:57   def _c02_stage_dir(folder)          <- 它把 folder 當產品根推導 <folder>/C02-ME
c02_me_package.py:772  collect_provenance_gaps(..., stage_dir=_c02_stage_dir(folder))
c02_me_package.py:847  同上（第二個 provenance 呼叫點）
```

與 `_load_constraints` 讀 `<folder>/C02-ME/Mechanical_Constraints.json` **同基準**
⇒ 原本「constraints 讀得到時 provenance 永遠假 gap」的矛盾不再成立。

### 症狀 B：缺 `dod_ok` / `guide_compliance` — 已修

```
c02_me_package.py:18   from .guide_dod import guide_compliance_for
c02_me_package.py:156  gc = guide_compliance_for(self.folder, "c02", root_visible=...)
c02_me_package.py:159  d["dod_ok"] = bool(gc.get("dod_ok"))
CONTROL  grep 'def guide_compliance_for' 全 packages -> 命中 1（guide_dod.py:69）
```

GUIDE 指示「跑 c02_readiness 讀 dod_ok」現在拿得到了，與 c01/c04/c05/c06 對齊。
`tests/test_readiness_folder_contract.py` 14 passed。

### 一個不屬本張的殘留（已另行建檔，不阻礍本張歸檔）

`_c02_stage_dir` 目前只有 provenance 兩個 consumer；export / generate verb 仍各自
`root / C02_OUTPUTS[key]`。這個 dual-prefix 殘留已拆成獨立 work item **`BR_20260804h`**
（見 `c02_me_package.py:63-73` 的契約註解）。

**本張主張的兩個具體症狀已收斂，故判 FIXED；那個殘留不是本張的 scoped remainder，
而是另一張已建檔的獨立缺陷**——兩者差別在於：前者歸檔會讓殘留消失，後者不會。
