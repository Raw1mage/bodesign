# Proposal: mcp_fleet-telemetry-feedback

## Why

bodesign 是負責硬體與電路設計（C00–C07 PCB 設計生命週期）的專用 MCP 服務器。使用者與 AI Agent 在呼叫各項硬體設計工具（如符號生成、線路合成、自動繞線、網表與三維渲染）時，若遭遇幾何錯誤、規格矛盾、工具異常或設計阻礙，亟需標準化機制讓呼叫端 Agent 能在第一時間將錯誤歷程與摩擦點（Friction）結構化上報給 bodesign 倉庫開發團隊。

藉由套用 OpenCode 全域艦隊遙測回饋架構（Fleet Telemetry & Retrospective Feedback，規範於 `specs/mcp-fleet-telemetry.md` 與 `mcp-builder/SKILL.md`），bodesign 能以「零網路侵入、零金鑰洩漏、被動推播」的純淨架構實現即時回報，並對接母系統 Ingress 將覆盤通知精確派發至 bodesign 在席值星官（`★main`），實現自動化立案與除錯閉環。

## Original Requirement Wording (Baseline)

- "這個mcp feedback mechanism特別適合讓使用者在消息mcp工作的時候隨時發BR給repo developer。請接著把bodesign架構也套上這個架構"

## Requirement Revision History

- 2026-10-10: initial proposal created, aligning bodesign with OpenCode Mother Fleet Telemetry SSOT (`specs/mcp-fleet-telemetry.md`).

## Effective Requirement Description

1. **客戶端通用工具 `submit_retrospective` / `bodesign_submit_retrospective`**：
   - 在 `services/mcp/feedback_drafts.py` 實作標準回饋接口，參數包含 `intent`（≤4096 字元）、`trajectory`（≤16384 字元）、`friction`（≤8192 字元）、`suggestion`（≤4096 字元）。
   - 應用程式將不可變草稿（帶 UUIDv7 `draftId` 與 `eventId`）寫入本地 SQLite 草稿庫，並向 `$FLEET_SIDECAR_SOCKET` 發送非阻塞 UDP/IPC 喚醒信號。
   - 應用程式保持 100% 純淨：**零網路通訊、零簽章計算、零回呼網址、零金鑰存儲**。
2. **部署維運神經層（Harness Sidecar Outbox）**：
   - 實作 `deploy/fleet-outbox-adapter.py`：監聽喚醒 Socket，讀取待發送草稿，以高強度對稱金鑰計算標準 HMAC-SHA256 簽章，並以指數退避（總共 5 次嘗試）推播至母系統 Gateway `/api/v1/fleet/events`。
   - 實作 `scripts/fleet-outbox-reconcile.py`：提供運維人員檢視、審查與重入隊死信（Dead-letter queue）之 CLI 工具。
   - 支援 Docker / 容器化環境變數注入（`FLEET_CALLBACK_URL`、`FLEET_NODE_ID`、`FLEET_DEPLOYMENT_ID`、`FLEET_NODE_SECRET`）。
3. **母系統艦隊註冊與值星官聯動**：
   - 於母系統 `~/.config/opencode/fleet-nodes.json` 註冊 `bodesign` 節點，綁定 `ownerUser: pkcs12` 與 `owningRepo: /home/pkcs12/projects/bodesign`。
   - 事件到達母系統後，自動持久化至 `/home/pkcs12/projects/bodesign/.specbase/fleet-events.sqlite`，並自動喚醒 bodesign 值星官 `★main` 進行 `fleet_read_event` 受控調閱與 Bug Report（BR）立案。

## Scope

### IN
- `services/mcp/feedback_drafts.py`：本機 SQLite 草稿寫入與 IPC 非阻塞 wake ping。
- `services/mcp/server.py`：註冊 `submit_retrospective` 及 `bodesign_submit_retrospective` 工具。
- `deploy/fleet-outbox-adapter.py`：Outbox 推進器（HMAC 簽章、指數退避、死信隔離、`--self-test` 驗證）。
- `scripts/fleet-outbox-reconcile.py`：死信審查與重入隊 CLI。
- `tests/test_feedback_drafts.py`：單元測試（長度驗證、SQLite 寫入、事件識別碼格式）。
- `~/.config/opencode/fleet-nodes.json`：新增 bodesign 節點定義與金鑰。
- 同步 `specs/architecture.md`：記錄 bodesign 遙測回饋通道與邊界。

### OUT
- 不修改 bodesign 既有的 EDA 核心演算法（KiCad、ngspice、autoroute、pyrender 等）。
- 不在應用程式內部引入任何外部 HTTP 網路請求模組。
- 不修改母系統 Gateway 與 Daemon 核心邏輯（其已具備全域通用 `owningRepo` 路由能力）。

## Non-Goals
- 不自動執行代碼修復或自動 Commit（值星官收到事件後依人機協同紀律手動/派工處置）。
- 不使用輪詢（Polling）機制監控草稿庫，嚴格採用被動 Socket Ping + 啟動補漏機制。

## Constraints
- 嚴格遵守全域安全合約：禁止使用 `/tmp` 或 `/var/tmp`，IPC 必須位於 `$XDG_RUNTIME_DIR` 或容器內部受保護掛載點。
- 註冊表權限必須為 `0600`，金鑰禁止寫入 Git 倉庫或映像檔。
- 通訊協定嚴格與 `specs/mcp-fleet-telemetry.md` 規範（v1 HMAC、±300s 時鐘差、UUIDv7 時間戳對齊）100% 保持一致。

## Capabilities

### New Capabilities
- `submit_retrospective` / `bodesign_submit_retrospective`：供 Agent/使用者隨時提交結構化問題回饋與歷程。
- `fleet-outbox-adapter`：被動喚醒 Outbox 守護進程，確保網絡離線時的可靠重試與死信保全。
- `bodesign` 值星官自動感知艦隊事件：透過母系統 Ingress 自動喚醒在席值星官進行缺陷審查。

## Impact
- `services/mcp/`：新增回饋接口，擴展 MCP 工具清單。
- `deploy/` & `scripts/`：新增 Outbox 運維腳本。
- `tests/`：新增自動化測試。
