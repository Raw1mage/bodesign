# BR + RCA: readiness 工具對「容器看不到的路徑」靜默回報 missing/0%，而非 fail-loud

- **Date**: 2026-06-23
- **Reporter**: TheSmartAI (orchestrator)
- **Target**: bodesign 維護者（workflow-core readiness 家族 + skill + enablement + MCP 自述）
- **Type**: bug（靜默失敗，違反 honesty / fail-fast 原則）+ capability/doc gap
- **Severity**: **high** —— 工具回傳「看似乾淨」的假結果，會直接誤導 agent 與使用者下錯結論（以為交付物不存在），且 honesty model 的整個價值建立在「不謊報狀態」之上。
- **Origin task**: 用 bodesign MCP 完備 `thesmart_products/01.openmv` (aiguard) C00–C07 交付物。第一步跑 readiness 全回 0%/missing，但檔案明明都在。

---

## 1. 一句話

bodesign MCP 跑在 Docker 容器內，容器**沒有掛載**使用者的專案路徑（本案是 GoogleDrive FUSE 掛載點）。`ingest_project_folder` 偵測到 `base.exists() == False` 時，**只 append 一條 warning 就回傳空 index**，而 `assess_package_readiness` 隨即把所有 deliverable 判成 `missing`、`readiness_pct: 0`，且 `PackageReadiness.to_dict()` **根本沒有 warnings 欄位**——那條「Folder not found」永遠到不了輸出。Agent 只看到一份語法完整、`ok: true` 的 0% 報告，**零跡象**顯示真正原因是「容器看不到這條路徑」。

---

## 2. RCA（syslog-style，附 code 證據）

### 2.1 Baseline（症狀 / 重現 / 影響）

- **症狀**：對 `01.openmv`（及各 `CXX/` 子目錄）跑 6 個 readiness 工具，全部回 `readiness_pct: 0` / 每個 deliverable `status: missing`。
- **反證（檔案確實存在）**：host 端直讀，例如 `C01-ID/Ai file/Design_Direction.md` = 2568 bytes、`C00-PRD/answer_state.json` = 29 KB，皆為已依 honesty model 撰寫的真實交付物。
- **重現**：任何 `bodesign_*_readiness(folder=<容器未掛載的 host 路徑>)`。
- **影響**：agent 幾乎要據此判定「portfolio 全空、需全量重生成」，差點用生成器 skeleton 覆蓋既有細寫內容。這是 honesty model 反面案例：工具自己謊報了狀態。

### 2.2 Instrumentation（埋點 / 觀察邊界）

埋點在「host ↔ 容器」邊界：
- `docker inspect bodesign-pkcs12-bodesign-1 --format '{{range .Mounts}}...'`
  → mounts 只有 `/home/pkcs12/projects/bodesign/.run → /run/bodesign`、sessions volume、vault volume。**專案路徑不在其中。**
- `docker exec bodesign-pkcs12-bodesign-1 ls "/home/.../01.openmv/C01-ID/Ai file/"`
  → `No such file or directory`。**容器內確實看不到這條路徑。**

### 2.3 Execution（證據 / 假設取捨）

排除「檔案真的缺」假設（host 端 2568-byte 檔證實存在），確認「容器 mount namespace 看不到」假設。再追工具內部資料流。

### 2.4 Root Cause（causal chain，逐層 code anchor）

1. **`packages/reverse-core/bodesign_reverse_core/project_ingest.py:96-101`** — 冒煙槍：
   ```python
   def ingest_project_folder(root, max_files=20000) -> ProjectFolderIndex:
       base = Path(root)
       index = ProjectFolderIndex(root=str(base))
       if not base.exists():
           index.warnings.append(f"Folder not found: {base}")
           return index          # ← 回傳空 index，不 raise、不標記特殊狀態
   ```
   路徑不可見 → `base.exists()` False → 空 index（`files == []`）。

2. **`packages/workflow-core/bodesign_workflow_core/package_readiness.py:108-127`** — `assess_package_readiness` 以 `ingest_project_folder(folder)` 起手；`files` 為空 → 每個 `POC_CHECKLIST` 項 `matched == []` → `status = "missing"`；`readiness_pct = 0`。**完全不知道「空」是因為路徑看不到，而非交付物真缺。**

3. **`package_readiness.py:82-93`** — `PackageReadiness.to_dict()` 的輸出鍵只有 `folder / milestone / readiness_pct / next_step / summary / external_sections / open_blockers / deliverables`，**沒有 `warnings`**。`ingest` 那條「Folder not found」warning 在這裡被吞掉，永不外露。

4. **per-stage 同病**：`packages/workflow-core/bodesign_workflow_core/c01_id_package.py` 的 `assess_c01_package_readiness` 逐檔 `if not path.exists(): ... "missing"`——路徑整個看不到時，每個 artifact 都被判 missing，無任何錯誤。

5. **家族內錯誤處理不一致（強化本 RCA）**：`packages/workflow-core/bodesign_workflow_core/c00_prd_template.py:351-352` 的 `assess_c00_prd_readiness` 卻**會 raise**：
   ```python
   if not path.exists():
       raise C00TemplateError(f"C00 artifact not found: {path}")
   ```
   → 本案 c00 readiness 回 `ok: false` 並明確說 artifact not found（這反而正確！），而 c01/c04/c05/c06/package 全部靜默回 0%。**同一個 readiness 家族，fail-loud 與 fail-silent 並存**，沒有統一契約。

**結論**：root cause 是 `ingest_project_folder` 對「路徑不存在」採 **silent-empty-return**，加上 readiness 輸出層 **丟棄 warnings**，兩者疊加使「路徑不可見」與「交付物真缺」在輸出上無法區分。容器未掛載專案路徑只是**觸發條件**，不是 root cause——即使在 host 同機跑，打錯路徑也會得到同樣的假 0%。

### 2.5 Validation（修復後如何驗證）

見下方修復 plan 的 Acceptance / 驗證計畫。核心：對「不存在/不可見路徑」呼叫任一 readiness 工具，必須得到**顯式可區分的錯誤或狀態**（例如 `status: "path-not-found"` 或 `ok: false` + 明確訊息），絕不可回 `readiness_pct: 0` 假裝評過分。

---

## 3. 次要 friction（同根或鄰近，一併記錄）

- **F3 — MCP 自述誤導**：server instructions 寫「Tools also accept plain host paths for the local same-host UDS case」，未限定「該路徑必須落在容器的 mount namespace 內」。實際上容器只掛載 `.run`/sessions/vault，任何容器外 host 路徑都不可見。應改為：host-path 模式僅適用於已掛載進容器的路徑；否則一律走 file-model（tar 上傳 → token + `doc_dir`）。
- **F4 — 容器邊界知識未沉澱**：agent 必須動用 `docker inspect` / `docker exec`（非正規偵查手段）才查出「MCP 在容器內、看不到 FUSE 路徑」。這條邊界應寫進 bodesign skill 與 `enablement.json`，讓 agent 一開始就知道「host 路徑要先確認在 mount 內，否則用 file-model」。
- **F5 — 大樹上傳無指引**：正規 file-model 路徑對 46 MB 樹（C04 含 `.glb`/`viewer.html`/PNG/generated KiCad 共 39 MB）兩次 tar 上傳逾時。文件應給「readiness 評分只需 text/json 交付物，建議排除重二進位」「大樹分階上傳 / 給大小上限」的指引。

---

## 4. 修復方向（治本，細節見 plan）

1. **`ingest_project_folder` fail-loud**：路徑不存在/不可讀時，回傳帶顯式狀態的結果（或在結構上標 `root_exists: false`），不可與「掃過但空」混淆。
2. **readiness 輸出層保留 warnings**：`PackageReadiness.to_dict()`（及 per-stage readiness 結果）加入 `warnings` / `root_visible` 欄位，把 ingest 的「Folder not found」一路帶到 MCP 輸出。
3. **統一 readiness 家族錯誤契約**：c00 的 fail-loud 行為設為全家族基準——路徑/必要 artifact 不可見一律顯式報錯或標記，不靜默回 0%。
4. **文件/邊界沉澱**：修正 MCP 自述的 host-path 描述；在 bodesign skill + `enablement.json` 寫明容器 mount 邊界與 file-model 首選路徑；補大樹上傳指引。

> 對應 plan-builder package：`plans/quality_readiness-fail-loud-on-invisible-path/`（本 repo）。

---

## Resolution

- **Status**: resolved。Closed 2026-06-23.
- **Final RCA**（確認,與 §2.4 一致）：root cause 是 `ingest_project_folder` 對「路徑不存在」
  採 **silent-empty-return**,疊加 readiness 輸出層 **丟棄 warnings**,使「路徑不可見」與
  「交付物真缺」在輸出上無法區分。容器未掛載只是觸發條件,非 root cause。
- **Fix implemented**：spec `specs/quality_readiness-fail-loud-on-invisible-path/` 已
  **graduate 至 living**(= 併入 main)。
  - 新增共用 `root_guard`(`packages/workflow-core/bodesign_workflow_core/readiness_common.py`),
    每個 readiness entrypoint(package + c00–c06)先過 guard。
  - `ingest_project_folder` 帶 `root_exists`;每個 readiness `to_dict()` additively 帶
    `root_visible` + `warnings`(可見資料夾為嚴格 superset,向後相容)。
  - 不可見 root → `root_visible:false` + warnings + 邊界 `next_step`(有 status 欄位處為
    `path-not-visible`);c00 對「可見資料夾但缺 `answer_state.json`」仍 raise `C00TemplateError`
    (artifact-missing 與 root-invisible 兩個獨立 loud 信號)。
  - 文件沉澱:MCP 自述 host-path 描述修正、skill `references/container-boundary.md`。
- **Verification**：`tests/test_readiness_invisible_path.py` 於容器 `bodesign-pkcs12-bodesign-1`
  以 `python -m unittest` 重跑 —— **9 tests, OK**(ingest root_exists、package + c00–c06
  root_visible、honesty invariant、向後相容 superset 全綠)。容器主鏡像未裝 `pytest`,但本套件是
  unittest、bodesign 套件在 PYTHONPATH 上,故直接以 unittest 執行。sibling spec 狀態為 `living`、
  spec.md 8 項 Acceptance 全 `[x]`。
- **Follow-ups / residual risk**(承 spec handoff,非阻斷)：(1) 跨 repo 的
  `prompts/enablement.json` 邊界註記待使用者在 opencode repo 路由;(2) image rebuild 讓更新後的
  MCP 自述字串上線(程式修復已可於 `BODESIGN_DEV=1 ./mcpctl.sh restart` 生效)。
- **相關**:同日 C06 analyzer-engines BR(`issue_20260623_c06_analyzer_engines_not_mounted_in_container.md`)
  是**不同缺陷**(引擎未打包進 image),仍 open(plan 在 `plans/deployment_c06-analyzer-engines-in-container/`,
  state=planned)。
