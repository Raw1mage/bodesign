# BR_20261001 — Bound mcp dependency upper limit to <2 (DD-2 pin-bound hotfix)

- **Family**: `dependencies/mcp` / unbounded-pin
- **Status**: open
- **Filed by**: opencode mcp-upgrade plan coordinator (`ses_f0c4003c2ffefhPv60Z1a8jQzf`)
- **Repo**: `/home/pkcs12/projects/bodesign`
- **Severity**: 高（阻斷風險）。目前容器執行 1.28.1，但無上限的 `mcp>=1.27` 在下次 rebuild 時將拉取 mcp 2.2.0，導致 lowlevel decorator 崩潰與服務啟動失敗。
- **Source Plan**: `/home/pkcs12/projects/opencode/plans/mcp_protocol-sdk-upgrade` (DD-2, Task 1.1)

## 1. 缺陷背景與現況

在 `services/mcp/requirements.txt:2`：
```
mcp>=1.27
```
此處未設定 major 版本上限。

## 2. 爆炸半徑與風險

PyPI 於 2026-07-28 發布 Python `mcp` 2.0.0，目前最新版為 2.2.0。SDK 2.x 移除了 `@server.list_tools()` 及 `@server.call_tool()` 等 decorator，改用建構子引數 `on_list_tools` / `on_call_tool`。
若 bodesign 容器或環境觸發重建（rebuild），pip 將自動解析到 `mcp 2.2.0`，導致服務啟動即崩潰（如 specbase BR_20260730 前例）。

目前 live 容器運行版本為 `1.28.1`。

## 3. 修復指示與驗收標準

由 bodesign duty officer 執行：
1. 將 `services/mcp/requirements.txt:2` 改為：
   ```
   mcp>=1.28,<2
   ```
2. 驗證依賴安裝與測試無回歸。
3. 提交變更並結案歸檔此 BR。
