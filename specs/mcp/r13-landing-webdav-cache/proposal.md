# Proposal: mcp_r13-landing-webdav-cache

## Why

bodesign 目前把 ~70 個 MCP 工具全部放在容器內，但偵查（2026-07-02）證實其中
**約 40 個是純 Python、對 caller 專案目錄的確定性 I/O**（scaffold / readiness /
answer-state / emit / orchestration spine / 純函數）——這些工具沒有任何容器限定
依賴，卻被迫走 `tar → token → blob` 往返：

1. **最高頻呼叫承受最重儀式**：C00/C01 Q&A loop（`update_answers` ×N 輪）與
   orchestration tick 每輪都要 re-tar / re-upload / snapshot-diff / per-file blob GET；
   token TTL 1h（`services/mcp/token_store.py:26-31`）逼長 session 反覆重傳。
2. **權威目錄倒置**：`specs/architecture.md` 明言 client folder 是 authoritative、
   cache disposable，但 token model 實務上反轉了這件事（token tree 變成工作真相，
   還會過期）。
3. **大產出流程逐檔取件**：`emit_fab` gerbers、C04 佈局 relay 鏈、renders 沒有
   對 client 的 mounted working cache；`mcp.json` instructions 自己都寫著
   「46 MB tree times out」（`services/mcp/server.py:53-56`）。

Fleet MCP integration standard（`opencode/specs/mcp-integration-standard/standard.md`）
已把解法標準化：

- **R13 compute/landing split**（specbase 驗證）：確定性 repo-local 工作以
  skill 內附 script 落地、agent 在 host 用自己的 uid 直跑；容器只留真正搬不動的
  重運算。
- **WebDAV working-cache**（docxmcp `specs/mcp/webdav-working-cache` 已畢業 living）：
  per-deliverable token workspace 掛成 mount point，消滅 host 目錄 ↔ token
  namespace 的雙向打包/逐檔儀式。

## Original Requirement Wording (Baseline)

- 「查看最新mcp integration standard，重構bodesign，用wendav和skill帶script的技術
  來解決目前docker based mcp中磨擦最大的工作」（2026-07-02）

## Requirement Revision History

- 2026-07-02: initial draft created via plan-init.ts
- 2026-07-02: 使用者三項拍板 — (1) R13 範圍 = 全部 Bucket 2（~40 工具）；
  (2) WebDAV working-cache 納入，照 docxmcp 精案移植；
  (3) landing 執行器 = python3 gate script + repo packages（不 vendor）。

## Effective Requirement Description

1. **R13 落地全部 Bucket 2（~40 工具）**：C0x scaffold/readiness/answers/emit +
   orchestration spine + 純函數全落地為 skill 內附 script；容器只留 heavy compute
   （pcbnew / kicad-cli / ngspice / OpenSCAD / build123d / pyrender / LibreDWG /
   LibreOffice / pygerber / freerouting）+ vault（server-owned state）。
2. **WebDAV working-cache 納入本次 scope**，照 docxmcp 精案移植
   （`bin/_webdav.py` 純協議層 + AuthProvider + cache lifecycle），服務對象是
   留在容器的 heavy 流程（C04 relay 鏈、emit_fab、renders）的檔案交換。
3. **Landing 執行器 = python3 gate script + repo packages**：
   `skills/bodesign/scripts/gate.py` 單入口（仿 specbase `gate.ts`），自動組
   PYTHONPATH 指向 bodesign repo 的 `packages/*`；host 只需 python3，零額外依賴，
   單一事實來源（不 vendor 複製套件）。

## Scope

### IN

1. **Landing plane**：`skills/bodesign/scripts/gate.py` verb runner + Bucket-2
   全部工具的 verb 落地（C00/C01/C02-analysis/C03-emit/C04-C06 scaffold+readiness/
   orchestration spine/純函數）。
2. **Container 收斂**：MCP tool registry 移除已落地工具（heavy + vault +
   borderline 留下）；`mcp.json` `instructions` 依 R13.5 宣告 compute vs landing
   verb 路由；version bump（breaking → 0.2.0）。
3. **WebDAV working-cache**：移植 docxmcp 驗證過的
   `_webdav.py`（class-2 protocol composer）+ cache lifecycle routes
   （provision/export/close）+ AuthProvider（Basic per-owner credential）+
   token_store 的 deliverable-cache 類別與 mkdir/move/copy helpers。
4. **兩層驗證**：host venv pytest 全綠 + 部署映像 pytest 全綠
   （in-image 執行配方明寫進 tasks，不重蹈 docxmcp BR_20260702 覆轍）+ rclone E2E。
5. **文件**：`specs/architecture.md` 全貌同步、`skills/bodesign/SKILL.md`
   路由段、event log。

### OUT

- 不動 heavy compute 工具的內部邏輯（layout/routing/simulate/render 演算法照舊）。
- 不動 vault 資料模型（SQLite+FTS5 named volume 照舊；`spice_model_card` 留容器）。
- 不做 gateway 端任何改動（docxmcp 前例：dumb splice proxy 自然穿透）。
- 不做 multi-host / R12 shared-tier 遷移（bodesign 是 per-user container）。
- 不 vendor packages 進 skill dir（單一事實來源決策）。
- workers 模式（me/ee split）拓撲不變。

## Non-Goals

- 不追求 token model 完全退場：留容器的 heavy 工具在無 WebDAV mount 的
  remote 場景仍用 token model（R2 契約不拆）。
- 不做 multi-user AuthProvider 以外的認證演進（R10 維持 `auth: none` 對外宣告）。

## Constraints

- 天條：no silent fallback、fail fast + 顯式報錯；landing script 對缺 repo /
  缺 packages 必須 typed error，不得退回容器路徑。
- `mcpctl.sh` 仍是唯一 runtime 入口；WebDAV routes 附掛在既有 server 上，
  不新增 daemon。
- 既有安全防護復用：traversal defence、size cap、audit log；WebDAV 每個 method
  同一條防護（docxmcp 前例）。
- Landing scripts 必須 R13.6 自足：從 skill dir 以 `--repo <abs>` 執行；
  script 自身 hard-guard scope（拒絕 heavy verbs）。

## What Changes

- `skills/bodesign/scripts/`：新增 gate.py + verb registry（landing plane 誕生）。
- `services/mcp/server.py`：tool registry 收斂至 heavy + vault + borderline；
  新增 WebDAV cache lifecycle + DAV method routes。
- 新增 `services/mcp/_webdav.py`（協議層）與 `services/mcp/_auth_provider.py`
  （Basic credential store），token_store 擴充 deliverable-cache 類別。
- `mcp.json`：instructions 重寫（R13.5 verb 路由宣告）、version 0.2.0。
- `skills/bodesign/SKILL.md`：新增 landing/compute 路由契約段。

## Capabilities

### New Capabilities

- **landing-gate**: agent 在 host 直跑 `python3 skills/bodesign/scripts/gate.py
  <verb> --repo <abs>`，涵蓋 ~40 個確定性 verbs，零 token 往返。
- **webdav-working-cache**: per-deliverable cache 可 provision / 掛載（rclone/
  davfs2）/ export 落地 / close，服務 heavy 流程的批量檔案交換。

### Modified Capabilities

- **MCP tool surface**: 容器工具數 ~70 → ~30（heavy + vault + borderline +
  cache lifecycle）；語意不變，位置遷移。
- **file exchange**: token model 保留（remote 場景），但 same-host 主路徑改為
  landing script 直寫 + WebDAV mount。

## Impact

- 受影響碼：`services/mcp/server.py`（registry + routes）、
  `services/mcp/token_store.py`、`skills/bodesign/`（scripts + SKILL.md）、
  `mcp.json`、`tests/`、`specs/architecture.md`。
- 消費端：opencode host 的 enablement/instructions 需跟著 mcp.json 更新；
  其他 IDE 用戶取得的工具數變少但獲得 skill script 路徑。
