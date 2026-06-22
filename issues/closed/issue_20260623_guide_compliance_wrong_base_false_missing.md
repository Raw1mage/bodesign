# BR: `guide_compliance` DoD sub-check resolves stage deliverables against the WRONG base — reports present files as `missing` (false RED)

- **Date**: 2026-06-23
- **Reporter**: TheSmartAI (orchestrator)
- **Target**: bodesign maintainer (`guide_dod.py` + the `cXX_readiness` family that bundles it)
- **Type**: bug (path-resolution inconsistency → false "missing" / `dod_ok:false` on a compliant stage)
- **Severity**: **high** — this is the *enforcement mechanism added by the previous BR*
  (`issue_20260623_readiness_only_checks_state_not_guide_dod.md`). It is meant to be the machine
  gate that stops "green light ≠ compliant". As shipped it fires a **false RED**: a stage whose
  deliverables genuinely all exist at the stage root is reported `dod_ok:false` / every deliverable
  `missing`. A false gate is as corrosive to trust as the silent-green it replaced — and it
  directly contradicts the *same tool's* own main readiness block.
- **Origin task**: completing `thesmart_products/01.openmv` (aiguard) C05 — after authoring the
  genuinely-missing `Firmware_Build_Notes.md`, `c05_readiness` reported all 6 deliverables present
  in one block and all 6 missing in another.

---

## 1. One line

`cXX_readiness` returns a self-contradicting result: the **main block** sees every deliverable
(`present_sections`, `pin_bridge_present:true`), while the bundled **`guide_compliance` block**
reports every deliverable `missing` — because the two halves resolve deliverable paths against a
**different base directory** for the same input `folder`.

---

## 2. Evidence (the contradiction, from a single tool call)

`bodesign_c05_readiness(folder=".", token=…)` over a tree containing `C05-FW/Functional_Spec.md`,
`C05-FW/Pin_Map_Bridge.json`, …, `C05-FW/Firmware_Build_Notes.md` (all six present, verified by
`ls` and by the main block) returned:

```jsonc
{
  "present_sections": ["Functional_Spec","Module_Architecture","State_Machine","Task_Breakdown","Pin_Map_Bridge"],
  "pin_bridge_present": true, "functional_present": true,
  "status": "fw_spec_drafted", "root_visible": true,
  "guide_compliance": {
    "dod_ok": false,
    "deliverables": [
      {"id":"functional_spec","status":"missing","evidence":"none of ['Functional_Spec.md'] found"},
      … all six "missing" …
    ],
    "missing_blocking": ["functional_spec","module_architecture","state_machine","task_breakdown","pin_map_bridge","build_notes"]
  },
  "dod_ok": false
}
```

The **same tool, same input**, says both "present" and "missing" for the same six files.

---

## 3. Root cause (code anchors)

The two halves disagree on what `folder` means:

- **Main readiness** treats `folder` as the **project root** and prepends the stage folder:
  - `packages/workflow-core/bodesign_workflow_core/c05_fw_spec.py:27` — `C05_FOLDER = Path("C05-FW")`
  - `c05_fw_spec.py:244` — `"Functional_Spec": root / C05_FUNCTIONAL` where
    `C05_FUNCTIONAL = C05_FOLDER / "Functional_Spec.md"` → checks `root/C05-FW/Functional_Spec.md` ✅
- **`guide_compliance`** passes that **same `folder`** straight through, but the manifest paths are
  bare stage-relative filenames with **no `C05-FW/` prefix**:
  - `c05_fw_spec.py:63` — `guide_compliance_for(self.folder, "c05", …)` (`self.folder == str(root)`)
  - `guide_dod.py:77` — `base = Path(folder)` (no stage-folder prepend)
  - `guide_dod.py:_match_any` — `if (base / rel).exists()` with `rel = "Functional_Spec.md"`
    → checks `root/Functional_Spec.md` ❌ (missing the `C05-FW/` segment)
  - `templates/c05.dod.json` — every `any_of` is a bare filename (`["Functional_Spec.md"]`, …),
    no stage prefix, and the deliverables carry no `bucket` that would supply one.

So the main block prepends `C05-FW/`; the DoD block does not. With a project-root `folder` the DoD
block can never find a stage deliverable → unconditional false RED.

## 4. Scope

`guide_compliance_for(self.folder, "<stage>")` is bundled the same way in **c01 / c04 / c05 / c06**:
- `c01_id_package.py:174`, `c04_layout_constraints.py:71`, `c05_fw_spec.py:63`, `c06_test_plan.py:91`

Each pairs a `root / <STAGE_FOLDER> / file` main check with a bare-filename DoD manifest, so the
same false-RED is expected on any stage whose `folder` is the project root and whose `cXX.dod.json`
uses unprefixed paths. Confirmed reproduced on **c05**; the others share the identical construction.
(Note `c04.dod.json`'s first deliverable resolved to `null` in a quick probe — its manifest shape
may differ and deserves a look too.)

## 5. Fix direction (maintainer's call)

One of, applied consistently across the family:
1. **Prepend the stage folder at the call site** — `guide_compliance_for(root / C05_FOLDER, "c05")`
   (and likewise c01/c04/c06), so the DoD base matches the main block's base; **or**
2. **Stage-qualify the manifest paths** — make `cXX.dod.json` `any_of` entries
   `"C05-FW/Functional_Spec.md"` (and add the stage folder as a `bucket`); **or**
3. **Teach `assess_guide_dod` the stage folder** — pass `stage_folder` and resolve
   `base / stage_folder / rel`.

Add a regression test: a tree with all stage deliverables present at `<root>/<STAGE>/…` must yield
`guide_compliance.dod_ok == true` AND agree with the main readiness block. A result where the two
blocks disagree about the same files should itself be a test failure.

## 6. Honesty boundary

- This is a **false negative** (says missing when present) — the opposite polarity of the original
  silent-green bug, but the same class of failure: the gate's verdict diverges from ground truth.
- For the aiguard C05 task it did **not** cause a wrong delivery: the main block + a direct `ls`
  both confirmed all six deliverables exist at the stage root, so C05 DoD is genuinely met and the
  `dod_ok:false` was recorded as this tool bug, not acted on as a real gap.
- No claim here about EVT/DVT/cert — unaffected.

---

## Resolution

- **Status**: resolved / fixed。Closed 2026-06-23(與引入此機制的 BR 同日;歸入 plan
  `quality/readiness-enforces-guide-definition-of-done`)。
- **Final RCA**(確認 §3):兩半對 `folder` 的語意不一致。main readiness 把 `folder` 當**專案根**並
  前綴 stage 資料夾(`root/C05-FW/file`),但我新加的 manifest 用**裸檔名**(`Functional_Spec.md`),
  `guide_compliance_for(self.folder=root, ...)` 把根目錄直接交給 checker → 找 `root/Functional_Spec.md`
  → 永遠 missing → 無條件 false RED。c01/c04/c05/c06 共用相同構造,皆中。(c00 沒中,因其 manifest
  本來就帶 `C00-PRD/` 前綴。)
- **Fix implemented**(採 BR 修法 #2「stage-qualify manifest paths」,全家族一致):
  1. `templates/c01..c07.dod.json`:每個 `any_of`/`all_of` 路徑前綴對應 stage 資料夾
     (`C01-ID/`、`C04-Layout/`、`C05-FW/`、`C06-Verification/`…),`bucket`(如 `02_build`)折進路徑。
     現在**全部 8 個 manifest 一律 project-root-relative**(與 c00 一致)。
  2. `package_readiness.py`:roll-up 改為**所有 stage 都傳專案根**(移除 `_stage_subdir` 的 glob),
     以 `_STAGE_FOLDER` 對照表檢查「該 stage 是否已開工(資料夾存在)」才納入。
  3. per-stage 接線不變(`guide_compliance_for(self.folder=root, ...)`)——manifest 改 root-relative
     後即正確。
- **Verification**:
  - 新增回歸測試 `tests/test_guide_dod.py::PerStageBaseAgreementTests` —— 斷言「files 存在於
    `root/C05-FW/` 時 `guide_compliance.dod_ok==true` 且與 main block 一致(present_sections 含
    Functional_Spec/Pin_Map_Bridge)」,並斷言 package roll-up 用專案根、c05 全在時不入 `dod_missing`。
    正是 BR §5 要求的「兩 block 不一致即測試失敗」。
  - 全套 **84** 測試綠(test_guide_dod 含新回歸 + c00/c01/c04/c05/c06/package/invisible-path 無回歸)。
  - 重 build image 後容器內複驗(見 plan 事件)。
- **Note**:`dod_status.json`(誠實延遲覆寫)現讀自傳入的 base(專案根),以 deliverable id 為 key。
- 這是 readiness DoD 機制的自我修正:前一 BR 引入閘、本 BR 修正其 base 解析,使「綠燈=合規」真正成立
  且不誤判。
