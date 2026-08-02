# bodesign — Repo Working Rules (AGENTS.md)

> 本檔是 **bodesign repo 專屬** 開發規則，補充（不取代）全域 `~/.config/opencode/AGENTS.md`
> 與 `SYSTEM.md`。衝突時：SYSTEM.md > 全域 AGENTS.md > 本檔 > driver > skills。
> 動手前先讀 `specs/architecture.md`（C00–C07 模組邊界、資料流、runtime flows 的單一真相來源）。

## 1. 這個 repo 是什麼

bodesign = 獨立的 **MCP server**，把 C00–C07 硬體設計（PCB）生命週期暴露成 `bodesign_*` 工具。
- 宿主無關、可獨立對外營運：UDS（本機 `.run/bodesign.sock`）。TCP `:8077` 只綁在容器內、
  **不對 host publish**（BR_20260730d：publish 會把未認證的 `POST /invoke` 暴露在所有介面上）；
  對外 HTTP 應由 gateway 擺在 socket 前面。
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

## 6.1 共用工作樹紀律（2026-08-02 事故後新增）

**這棵樹長期有多顆 session 並行工作，且大量工作處於未 commit 狀態。** 以下指令會靜默摧毀
他人未 commit 的修改，**在本 repo 一律先問、先查**：

| 指令 | 為什麼危險 |
| --- | --- |
| `git reset --hard` | **與 `git checkout` 相反**：checkout 遇到會被覆蓋的本地修改會 REFUSE 並列出擋路檔案；`reset --hard` 靜默執行、exit 0、什麼都不印。**成功態與災難態共用同一個輸出。** |
| `git clean -fd` | 刪除全部 untracked（本樹有 458 個） |
| `git checkout -- .` | 丟棄全樹工作區修改 |
| `git stash`（無 pathspec） | 會捲走他人的修改 |

**強制前置**：執行上述任何一個之前，先跑
```
git status --porcelain | grep '^ M\|^M \|^MM'
```
非空就停手——那些是別人的工作。

**等價的安全替代**：
- 撤銷 commit → `--soft` / `--mixed`（**不碰工作區**，絕大多數情況要的是這個）
- 丟棄特定修改 → `git stash push -- <精確 pathspec>`，不要全樹 `--hard`
- 搬移檔案 → `git mv`（它會在檔案未進版控時報錯，是有用的訊號）

**⭐ 開工前先錨定自己的工作（唯一不依賴任何人記得的防護）**：

```bash
# ⚠ 不要用 `git stash create` —— 它只涵蓋 tracked 檔案，untracked 新檔會靜默漏掉
export GIT_INDEX_FILE=$(mktemp -d -p "${XDG_RUNTIME_DIR:-$HOME/.cache}" snap.XXXXXX)/index
git read-tree HEAD
git add -- <每一個要保的檔案，含 untracked>
C=$(git commit-tree $(git write-tree) -p HEAD -m "snapshot: <what>")
git update-ref refs/wip/<session-id> "$C"
unset GIT_INDEX_FILE
```

**驗收必須逐檔 `git show <ref>:<path>` 比對，不是「ref 建好了」。**
`ses_0c87bab06` 的第一版快照就漏掉一個 untracked 測試檔——而 **ref 存在、`git show <ref>` 有輸出，
讀起來完全像「我的工作受保護了」**。

> **「我以為我快照了」比「我沒快照」更危險，因為它讓人停止擔心。**

這是本節所有陷阱的同一個形狀，**發生在防護措施自己身上**：涵蓋範圍與你以為的不同，而輸出不會說。

**`reset --hard` 拿不走一個有 ref 指著的 commit。** 未 `git add` 的內容從未進 object store，
所以事後任何回收手段（`reflog` / `fsck --lost-found` / `stash list`）都是空的——**錨定必須在事前**。

這條由 `ses_0c87bab06` 在復原 `kicad_emit.py` 時提出並實地驗證
（`refs/recovered/kicad_emit_full` 保住了 3030 行的完整檔案，否則 `git gc` 會永久刪除它）。

**為什麼是「唯一」**：2026-08-02 實測了三條 pre-reset 護欄，全部失敗——

| 路徑 | 結果 |
| --- | --- |
| `git config alias.reset` | **不可行**。控制組決定性：同一份 alias 值掛 `zzprobe`（非內建）正常展開，掛 `reset`（內建）被完全忽略。git 只在找不到內建指令時才查 alias |
| `reference-transaction` hook | **比不裝更危險**。它在 ref 更新時觸發，而 ref 更新是 `reset --hard` 的**最後**一步——工作區早已被覆寫。treatment 與 control 的檔案內容**完全相同**，而 git 印 `aborted` 且 exit 128。裝上去會讓人把 `aborted` 讀成「工作還在」 |
| PATH wrapper | 攔得到（四組控制組）但無可行落點：`~/.local/bin` 不在 PATH、`export PATH=` 不跨 tool call 存活、`~/.bashrc` 不被 harness shell source、`/usr/local/bin` 是 root-owned 而本機有 13 個真實使用者 |

前兩者是**防護不存在**，第三個是**打擊面錯配**（為攔 agent 而改全機共用的 git）。
只有「事前錨定」把防護放在自己手上，不需要攔截任何東西。
詳見該 BR §5 與 opencode `issues/BR_20260802_denylist_has_no_rule_for_the_one_git_command_that_silently_destroys_peer_work.md`。

**⚠ 快照歧義陷阱（pathspec 陷阱的姊妹條）**：讀一個檔案時，`git show HEAD:<path>`、
`git cat-file -p <blob>`、直接讀工作區——**三者輸出形狀完全一樣，沒有任何標記說你讀的是哪一份**。
實錄：值星官 AST 比對 `composer.py` 得到「需要 19 個符號」，據以判定 peer 的「18 個」有誤；
實際上值星官讀的是 peer **未 commit 的工作區**，peer 的基線是 **HEAD**。兩人都對，讀的不是同一份。
**跨 session 比對數字前，先聲明「我讀的是哪一個快照」。**

**⚠ `git log -S` 回空 ≠ 從未存在**：在一棵大量工作未 commit 的樹上，
它的空結果只證明「沒有被 commit 過」。「從未寫過」與「寫過、只活在工作區、然後被 `reset --hard` 清掉」
對它而言是同一個空結果。任何用它推論「這東西不存在」的結論，
都該先問一句「有沒有可能它只是沒被 commit」。
實錄：`issues/BR_20260802_reset_hard_destroyed_kicad_emit_and_the_BR_blamed_the_import_that_was_correct.md`
——一張 BR 因此把根因寫成「import 了不存在的符號」，派出去的會是「實作三個不存在的函式」，
而正確工作是「還原一份存在且已驗證的檔案」。

**⚠ pathspec 陷阱**：`git status --porcelain <path>` 與不帶 path 的版本**輸出形狀完全一樣**，
沒有任何標記說結果被過濾過。**任何帶範圍限定的 `git status` / `grep` / `ls` 結果，
若要拿去支撐全域結論，必須先重跑一次不帶限定的版本。**

實錄：`issues/BR_20260802_reset_hard_silently_destroyed_uncommitted_work_on_shared_tree.md`
——46 個檔案的未 commit 修改永久遺失，兩顆 peer 的 context 都無可回收內容。
肇事者在事故前 30 分鐘才剛立案一張警告「`git clean -fd` 會無聲刪光 peer 工作」的 BR。
**正在寫某條規則不構成該規則的豁免。**

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
