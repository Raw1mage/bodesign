# bodesign — Repo Working Rules (AGENTS.md)

> 本檔是 **bodesign repo 專屬** 開發規則，補充（不取代）全域 `~/.config/opencode/AGENTS.md`
> 與 `SYSTEM.md`。衝突時：SYSTEM.md > 全域 AGENTS.md > 本檔 > driver > skills。
> 動手前先讀 `specs/architecture.md`（C00–C07 模組邊界、資料流、runtime flows 的單一真相來源）。

## 1. 這個 repo 是什麼

bodesign = 獨立的 **MCP server**，把 C00–C07 硬體設計（PCB）生命週期暴露成 `bodesign_*` 工具。
- 宿主無關、可獨立對外營運：UDS（本機 `.run/bodesign.sock`）+ TCP（`:8077` HTTP `/mcp/`）。
- 與配套的 `bodesign` skill（C00-C07 workflow 腦 + kicad/kidoc 引擎）成對；verification 工具會回呼 skill 引擎。
- 核心哲學：**展示**可靠度（對照已知良品交叉檢核 + KiCad/SPICE/EMC 確定性驗證），而非宣稱。
  LLM 只做上游抽取／裁決，驗證與比對全程不參與。

## 2. 天條（hard rules，違反即缺陷）

1. **No silent fallback**（全域天條，在此 repo 尤其嚴）。缺欄位／缺幾何／缺 datasheet 證據 →
   **fail fast + 顯式報錯 + 缺項清單**，不以預設值／第一個可用值／泛用模型靜默續跑。
   既有設計到處是這個 pattern（C02 `never guesses`、orchestration `SPINE_NOT_INITIALIZED`、
   spice `model_source` 可見、EDA-bridge `no SILENT overfit`）。新程式碼必須延續。
2. **No fabrication / 不偽造交付物**。
   - 不偽造原生檔：`.ai` / `.skp` / STEP / STL 只在真實 toolchain 存在時產出；否則誠實標 unavailable
     或給中間產物（如 `figma_import_spec.json`）。`c02_export_skp` 就是「honestly unavailable」範本。
   - **`files` 清單只列磁碟上真實存在的檔**，不放 phantom 佔位（PDF pending 時不列 `.pdf`，
     用 `pdf_status=pending` + README note 表達）。
   - 視覺／文件交付物必帶可見 draft 標記（`not final ID` / `not CMF approval` / `not UI sign-off` …），
     永不把人工核可（`human_approved` / approved）由程式翻 true。
3. **No send-to-fab without deterministic validation + explicit user approval**。送廠輸出前必須過
   確定性驗證（DRC gate / crosscheck / SI / SPICE）並取得使用者明確批准。
4. **Datasheet-grounded electrical claims**。陳述任何零件電氣規格前，先 `bodesign_datasheet_lookup` /
   `bodesign_vault_spec_check`；RCA 發布前用 `bodesign_rca_spec_audit` 把關。無 datasheet 來源的規格值
   = BLOCKING，不臆測。
5. **不主動新增 fallback mechanism**，除非使用者明確批准（見全域 AGENTS.md §11）。

## 3. Runtime / 啟動（唯一入口）

bodesign MCP server 只透過 **`./mcpctl.sh`** 管理（docker-compose 後端，per-user project `bodesign-${USER}`）：
- `./mcpctl.sh start | restart | rebuild | stop | status | log`
- **Dev loop（改 code 不重建 image）**：`BODESIGN_DEV=1 ./mcpctl.sh start`（首次 build + 綁定原始碼掛載），
  之後 `BODESIGN_DEV=1 ./mcpctl.sh restart` 數秒生效。**只有改依賴（requirements/Dockerfile）才 `rebuild`**。
- **Workers 模式**（lean core + me/ee workers，重 CAD/EDA 依賴隔離在 `Dockerfile.core/.ee/.me`）：
  `BODESIGN_WORKERS=1`。**STICKY**：一旦以 workers 模式啟動，`.run/.workers` marker 讓後續 restart/rebuild
  維持 workers 模式（避免 rebuild 悄悄退回 monolith 並 orphan workers）。`BODESIGN_WORKERS=0` 強制退回。
- 禁止手工 `docker run` / 直接起 server 繞過 `mcpctl.sh`。

## 4. Core vs Worker 邊界

- **core（pure-python / lightweight）**：規劃、readiness、constraint 組裝、pure-python 估算（impedance、
  Gerber preview）、orchestration spine。失敗時對不支援輸入／不可用 renderer **顯式報錯**。
- **worker（重 toolchain）**：`pcbnew`/KiCad-mutating、OpenSCAD/build123d CAD、pyrender/EGL render、
  freerouting autoroute → 路由到 me / ee worker（`_forward_to_worker`，需 `httpx`）。
- 新工具歸類前先想清楚落在哪一側；core 不可硬依賴 worker-only 套件（如 `httpx` 僅 worker-forwarding 用，
  monolith/純 unittest 環境缺它是預期的，不要當成回歸）。

## 5. 套件結構與測試

- `packages/`：`workflow-core`（C00-C07 邏輯）、`reverse-core`（Rockbox 證據抽取 + `emit_document`）、
  `design-ir`、`gerber-core`、`eda-bridge`（KiCad adapter 邊界）、`doc-core`、`source-core`、
  `storage-core`、`component-kb`、`kicad-plugin`、`shared`。
- `services/mcp/server.py`：MCP 工具註冊（handler `_h_*` + schema list）。新增工具 = handler + schema 兩處。
- **跑測試的 PYTHONPATH**：要含**所有** package 子目錄，不是只有一個。慣用：
  ```
  PP=$(ls -d packages/*/ | tr '\n' ':') && PYTHONPATH="$PP" python3 -m unittest tests.<module> -v
  ```
  （`python` 不存在，一律 `python3`。）`bodesign_workflow_core/__init__` 會 import `bodesign_reverse_core`，
  PYTHONPATH 不全會 `ModuleNotFoundError`。
- 文件工具（PDF/docx）走 **approved pipeline**：`bodesign_emit_doc`（markdown→docx+pdf，
  reverse-core `emit_document` / LibreOffice）或 `bodesign_mcp_call` 驅動 docxmcp。**不手工拼 PDF/OOXML bytes**。

## 6. 開發流程（對齊全域 AGENTS.md）

- **非瑣碎任務先走 plan-builder**：草稿包在 `/plans/<category>_<topic>/`（扁平命名），
  `proposed→designed→planned→implementing→verified`。狀態用 specbase `plan_advance`，
  **務必帶 `repo:/home/pkcs12/projects/bodesign`**（否則會跑去 opencode repo 找不到 slug）。
  graduate 到 `/specs/` 只在使用者明確指示時。
- **Event log**：開工 + 收尾各一筆 `specbase event_record`，`scope` 帶 project 或 plan slug；
  重大決策 / RCA / 部署隨手 append。
- **架構同步**：動到模組邊界／資料流／狀態機／觀測點 → 收尾前比對並同步 `specs/architecture.md`
  （全貌同步，非流水帳）；即使無變更也在 event 註記 `Architecture Sync: Verified (No doc changes)`。
- **Tasks 即時勾選**：`tasks.md` 每完成一項立刻 `[ ]→[x]`，不批次補。
- **Issues local-first**：bug report / feature request 預設記在本地 `issues/`
  （`issue_<YYYYMMDD>_<slug>.md`，關閉移 `issues/closed/`）。除非使用者明確要求，不開 GitHub issue。
- **plan-builder spec 在隔離分支建置才需要 beta-workflow**；純 repo 內 code 修改可直接做。

## 7. Diagram / 建模

- IDEF0 / GRAFCET / C4 用 `drawmiat` MCP，**先 `validate_diagram` 再 `generate_diagram`**。
- plan 進 `designed` 需 `idef0.json` + `grafcet.json`（經 drawmiat 驗證）。

## 8. 常見陷阱

- docxmcp `assemble` 需 **絕對** 容器路徑 `doc_dir`（`/var/cache/docxmcp/sessions/<token>/…`）；相對路徑會
  resolve 到 `/app` 而失敗。
- C01 有兩條路徑別搞混：`C01-ID/Display UIUX/`（無底線，companion source-of-truth markdown）vs
  `C01-ID/Display UI_UX/`（底線，BR 的 optional ID-native bucket）。並存不衝突。
- C02 的 2D 向量是從 3D STL **projection 衍生**（`c02_project_svg`，single-source-no-drift），不是另一條
  LLM 直畫的 2D 路徑。C01 的 ID skeleton SVG 是**不同交付類別**（description→ID hand-off scaffold）。
