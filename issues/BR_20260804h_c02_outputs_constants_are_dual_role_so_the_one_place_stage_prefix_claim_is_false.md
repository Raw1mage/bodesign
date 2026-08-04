# BR_20260804h — `C0x_OUTPUTS` 常數身兼兩職，使「stage 前綴只在一處推導」這句宣稱不成立

**Status**: OPEN — 已量測定位，**刻意未修**（見 §4 為何不能與 BR_20260804 同輪）
**Severity**: medium — 不是當下的錯誤行為，是**一句錯誤的單一真相來源宣稱**
**Owner**: `readiness-contract` family（`issues/OWNERS.md`）
**Filed by**: `ses_0330e7869ffev0nZL0XqoXSp78`（BRNS handler，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`）
**Filed**: 2026-08-04
**Related**:
- `issues/BR_20260804_c02_export_stl_cannot_see_files_staged_into_its_own_token.md`
  （同一條契約線：這張是那張的**根因層**。那張的症狀由 `folder_is_stage_dir` 揭露修法擋住，
  但雙前綴模型本身仍在）
- `issues/BR_20260719_c01_readiness_folder_arg_double_prefix.md`
  （同族：c01 的 `folder` 雙前綴半邊仍 OPEN，§2 附今日重現）
- `issues/BR_20260804_stage_deliverable_names_are_hardcoded_per_module_so_the_C0N_prefix_rule_cannot_be_adopted.md`
  （同一批常數的另一個面向：名稱寫死在各模組）

---

## 1. 一句話

`c02_me_package.py:35-38` 的區塊註解**逐字宣稱**：

> the stage dir is derived from it here, **in ONE place**, so no caller has to
> pre-join it and **no two code paths can disagree** about what `folder` meant

**兩句都不成立。** 那個「ONE place」（`_c02_stage_dir()`）只有 2 個呼叫點，
而模組裡另有 5 個 verb 走完全不同的前綴模型。

## 2. 量測（2026-08-04，全部可重跑）

```
$ grep -n "_c02_stage_dir" packages/workflow-core/bodesign_workflow_core/c02_me_package.py
  57:def _c02_stage_dir(...)          ← 定義
 693:  stage_dir=_c02_stage_dir(folder)   ← provenance
 768:  stage_dir=_c02_stage_dir(folder)   ← provenance
（全部呼叫點就這兩個，皆在 provenance 路徑）

$ 而 C02_OUTPUTS 的 12 個值每一個都自帶 "C02-ME/" 前綴，且被這樣消費：
  export_c02_stl / export_c02_skp / export_c02_step /
  export_c02_projection_svg / generate_c02_openscad
    → root / C02_OUTPUTS[key]         ← 第二套前綴模型
```

c01 同構：`_c01_stage_dir()` 2 個呼叫點（`:617`、`:1133`），
`C01_OUTPUTS`（5 keys）與 `C01_OUTPUT_CANDIDATES`（read 側候選表）全部自帶 `C01-ID/`。

**BR_20260719 的 `folder` 雙前綴半邊今日仍逐字重現**（production import，同一份合規交付）：

| `folder` 傳入 | readiness_pct | missing |
|---|---|---|
| `<product root>` | **100** | `[]` |
| `<product root>/C01-ID` | **0** | 全部 5 個 |

（`C01_OUTPUT_CANDIDATES` 修的是 read 側 bucket 位置分歧（`03_output/` vs legacy），
**沒有碰 `folder` 雙前綴**。同一張 BR 的兩半只修了一半。）

## 3. 為什麼這比「沒有註解」更貴

這句宣稱**讓讀者停止尋找第二個真相來源**。

本 handler 實測：讀到 `:35-38` 的註解時，第一反應是「契約已收斂，我只要順著單點改」——
是 dispatcher 要求「自己去讀 `_c02_stage_dir()` 的實際涵蓋範圍」才發現宣稱與實作不符。

同族形狀已在本 repo 記錄多次（`code-thinker` §8.1.3(d)）：
**宣稱存在但實際只覆蓋一條路徑的護欄，比缺少護欄更貴。**

## 4. 為什麼**不能**與 BR_20260804 同輪修（這格是本 BR 的核心）

直覺修法是「把前綴從 `C0x_OUTPUTS` 拿掉，全部經 `_c0x_stage_dir()` join」。**不行**，因為
那 12 個常數**身兼兩職**：

1. **檔案系統 join 的右手邊** — `root / C02_OUTPUTS["openscad"]`
2. **回傳給呼叫端的 rel path** — `stl_path=str(C02_OUTPUTS["stl"])` → `"C02-ME/Enclosure.stl"`

第 2 個角色**真的被下游 join**：

```
services/mcp/server.py:317-320
    stl_rel = (result.get("stl") or {}).get("stl_path")
    stl_abs = str(Path(a["out_dir"]) / stl_rel)      ← 呼叫端自己再 join 一次
```

⇒ 一旦把前綴從常數移走，這兩個角色必須**分別**重建（一個要 `root/stage/name`，
另一個要 `stage/name`）。任何一處漏改都會產生「路徑對、但回傳的 rel 少一層」——
**在下一跳才炸**，而且炸的地方離改動點很遠。

**這正是我們在修的病換個位置發作**：一個名字承載兩種語意。

## 5. 建議修法（獨立工項，需完整掃描）

1. 把兩個角色拆成**兩組**常數：`C02_STAGE_REL`（stage 內相對，供 join）與
   `C02_PRODUCT_REL`（product root 相對，供回傳）；或保留單一常數但讓回傳點顯式
   `str(C02_STAGE_DIRNAME / name)`
2. 前綴 join 收斂到 `_c0x_stage_dir()`，讓那句註解變成事實
3. 加 drift guard：斷言「任何 verb 回傳的 rel path，與呼叫端 `out_dir` join 後
   等於實際寫入的絕對路徑」——這條護欄若不加，下次搬動仍會靜默錯位

## 6. 已知缺口（誠實邊界）

- **`C0x_OUTPUTS` 的下游消費點我只掃了 `c02_me_package.py` 與 `services/mcp/server.py`。**
  `skills/bodesign/scripts/gate.py` 及其他 skill 端消費者**未掃**。
  動手修此 BR 前必須先完整掃描，否則 §4 的「漏改一處」風險成真。
- **c00 / c03–c07 是否同構未量。** 依 `readiness_common.STAGE_FOLDER` 有 8 個 stage，
  本次只驗了 c01 / c02 兩個。

## 7. 當前狀態

`_c02_stage_dir()` 的 docstring 已在 BR_20260804 的修法中補上 SCOPE 段落，
明寫「本 helper 只有兩個 provenance 呼叫點，模組內兩套前綴模型並存」並指向本 BR，
使那句不成立的宣稱不再誤導下一個讀者。**那是止血，不是修復。**
