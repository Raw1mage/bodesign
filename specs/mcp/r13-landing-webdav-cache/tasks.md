# Tasks: mcp_r13-landing-webdav-cache

> 執行順序：先 landing plane（磨擦 #1/#2 根除，獨立可驗證），再 WebDAV cache
> （磨擦 #3，依賴 store 擴充），最後 surface 收斂 + 文件。
> 兩層驗證配方（DD-9）：
> - host venv：`PP=$(ls -d packages/*/ | tr '\n' ':') && PYTHONPATH="$PP" python3 -m unittest discover -s tests -v`
> - 部署映像：`docker run --rm --entrypoint python3 -v $PWD/tests:/app/tests:ro -v $PWD/skills:/app/skills:ro -w /app bodesign:latest -m unittest discover -s tests -v`（app 目錄 = `/app`；test_mcp_server.py 直接 load `/app/skills/…/gate.py` 故 skills/ 必掛；若 schema 契約測試需 specs/，加 `-v $PWD/specs:/app/specs:ro`）

## 1. Landing plane — gate.py 骨架

- [x] 1.1 `skills/bodesign/scripts/gate.py`：argparse（`<verb> --repo <abs> [--json {…} | --arg k=v]`）、python 版本 fail-fast（`LANDING_PYTHON_TOO_OLD`）、`BODESIGN_SRC` 解析 + packages/* PYTHONPATH 組裝（缺 → `LANDING_PACKAGES_NOT_FOUND`）、JSON envelope 輸出（stdout 單物件，錯誤 typed code + exit≠0）
- [x] 1.2 verb registry 宣告表（DD-2）：`VERBS = {name: (module, callable, required_args)}`；未知 verb → `VERB_UNKNOWN`；heavy verb 名列黑名單表 → `VERB_NOT_LANDING`（hard-guard，R13.6）
- [x] 1.3 `--list` 輸出全 verb 清單 + 一行說明（agent 可發現性）

## 2. Landing plane — Bucket-2 verbs 落地（~40）

- [x] 2.1 C00 家族：c00_scaffold_prd / c00_readiness / c00_emit_prd / c00_update_answers / c00_emit_prd_docx（render-only 路徑；assemble 明確拒收 → 指路容器 tool）
- [x] 2.2 C01 全家族（10 verbs）：emit_package / readiness / next_question / update_answers / emit_concept_prompts / add_reference_image / confirm_reference_cue / emit_id_visual_package / emit_cmf_package / emit_uiux_package
- [x] 2.3 C02 analysis-only：c02_readiness / c02_emit_enclosure_package / c02_generate_openscad（寫 .scad 文字）/ c02_plan_intent
- [x] 2.4 C03 emitters：c03_export_mechanical_constraints / c03_emit_partition_diagram / c03_emit_host_block_diagram
- [x] 2.5 C04/C05/C06 scaffold+readiness：c04_emit_layout_package / c04_readiness / c05_scaffold_fw_spec / c05_readiness / c06_assemble_test_plan / c06_readiness
- [x] 2.6 Orchestration spine（14 verbs）：agent_registry / dispatch_work_packet / list_work_packets / return_blocker / list_blockers / ingest_blocker / wrap_validation_evidence / return_evidence / list_evidence_returns / ingest_evidence / enter_c01_mode / c00_orchestration_status / c00_orchestration_tick / reference_board_workflow
- [x] 2.7 Read/gate：ingest_project / package_readiness / datasheet_lookup / vault 除外的 spec_check 路徑（`datasheet_lookup`/`rca_spec_audit` 讀 `<project>/datasheets/extracted/`，無 vault 依賴的部分）
- [x] 2.8 純函數：plan_design_intent / evidence_manifest / pin_allocation / reference_crosscheck / impedance_solve
- [x] 2.9 逐 verb import 圖驗證（R2 風險）：host 無 cairosvg 等 optional 套件時 gated-omit 行為保持（不 crash）

## 3. Landing plane — 測試

- [x] 3.1 `tests/test_landing_gate.py`：gate.py 骨架（版本檢查 / packages 解析 / unknown verb / not-landing verb / envelope 格式）
- [x] 3.2 代表性 verb 端到端（host venv 直跑 gate.py 子程序）：c00_scaffold_prd → readiness → update_answers → emit_prd 全循環寫進 tmp repo；orchestration dispatch→return→ingest 循環
- [x] 3.3 全 verb smoke：`--list` 的每個 verb 至少 import-resolve 成功（防 registry 表打錯 module 路徑）

## 4. token_store 擴充（WebDAV 前置，DD-7）

- [x] 4.1 kind 欄位（`ephemeral` | `deliverable-cache`）+ owner_identity + subject_id + last_export_at 持久化（沿用現行目錄 + sidecar JSON 模式）
- [x] 4.2 mkdir / move / copy helpers（traversal defence 沿用 `_safe` 解析）
- [x] 4.3 reaper class-aware：deliverable-cache 免 idle reap；safety-net 長 TTL（warn-first）；ephemeral 現行為不變
- [x] 4.4 單元測試：reaper 狀態機 fast-forward（照 docxmcp `test_webdav_cache_reaper.py` 模式）

## 5. WebDAV 層移植（DD-4/DD-6）

- [x] 5.1 `services/mcp/_webdav.py`：自 docxmcp `bin/_webdav.py` 移植（multistatus / PROPFIND depth 0-1 / OPTIONS DAV:1,2 / Timeout parse / LockTable）；unit tests 同步移植
- [x] 5.2 `services/mcp/_auth_provider.py`：Basic per-owner credential store（hash 存放、constant-time 比對、issue/rotate/revoke）；cred path → `BODESIGN_WEBDAV_CRED_PATH` 預設 sessions volume dotfile sibling（`.webdav-creds.json`）
- [x] 5.3 cache lifecycle routes：`POST /caches`（provision，idempotent per subject，回 token + mount URL + credential）/ `POST /caches/{token}/export`（host target，typed `EXPORT_TARGET_UNREACHABLE`）/ `POST /caches/{token}/close`（dirty-gate 409 `WORKSPACE_CLOSE_DIRTY` unless clean/force）/ `GET /caches`（list mine）
- [x] 5.4 DAV method routes：`/dav/{token}[/{rel}]` OPTIONS/PROPFIND/GET/HEAD/PUT/DELETE/MKCOL/MOVE/COPY/LOCK/UNLOCK；每 method（除 OPTIONS）resolve_identity→owns() 先行；audit log per method；cross-token Destination → 403
- [x] 5.5 MCP tool 對應：`bodesign_cache_provision` / `bodesign_cache_export` / `bodesign_cache_close`（agent 走 tool、人走 mount）
- [x] 5.6 PoC 測試：in-process TestClient（provision → OPTIONS → PUT×2 → PROPFIND → GET → MOVE → close dirty→409 → export → close 200）+ 多 user 隔離（錯 credential 401 / 他人 token 403）
- [x] 5.7 rclone E2E（真 server + 真 rclone webdav backend）：copyto/lsf/cat/mkdir/moveto/deletefile + 錯密碼被拒（照 docxmcp `experiments/webdav_rclone_e2e.py` 模式）

## 6. Container surface 收斂（DD-3/DD-8）

- [x] 6.1 server.py registry 移除 Bucket-2 entries；被呼叫的已移除 tool → typed `TOOL_LANDED` + gate.py 等效指令（R3）
- [x] 6.2 INSTRUCTIONS 重寫：R13.5 三類宣告（compute tools / landing verbs via gate.py / cache lifecycle 流程）；砍掉「46 MB times out」段改為 landing+cache 指路
- [x] 6.3 mcp.json：version 0.2.0、instructions 同步、skillPaths 確認
- [x] 6.4 `GET /tools` 反映收斂後 registry；`/skills` 不變

## 7. 兩層驗證 + 回歸（DD-9）

- [x] 7.1 host venv 全套件綠（含新 landing/webdav/store 測試）
- [x] 7.2 部署映像 pytest 綠（配方見本檔頂部；首跑失敗先分辨環境假影 vs 回歸）
- [x] 7.3 `mcpctl.sh restart` 後 UDS + TCP 雙 transport smoke：`GET /health` / `GET /tools`（收斂後數量）/ 一發 heavy tool（token 路徑不回歸）
- [x] 7.4 gate.py 從 XDG 投影位置跑一次（`BODESIGN_SRC` 顯式指定情境）驗 R13.6 自足性

## 8. 文件 + 收尾

- [x] 8.1 `skills/bodesign/SKILL.md`：新增 landing/compute 路由契約段（何 verb 走 gate.py、何 verb 走 MCP tool、cache 三層心智：truth store / working cache / vault）
- [x] 8.2 `specs/architecture.md` 全貌同步（landing plane / WebDAV cache / store kind / auth provider 模組列 + 資料流）
- [x] 8.3 README.md / README.en.md transport+file-model 段更新
- [x] 8.4 event_record 收尾（Key Decisions / Verification / Friction 區塊）+ ragbase distill 判斷
- [x] 8.5 CHANGELOG.md 0.2.0 條目
