# Observability: dsl_atopile-integration

## Events

| 信號 | 位置 | 內容 |
|---|---|---|
| `ato_build` 請求/回應 | core `run_tool` 既有 log | tool name、group routing 決策（served locally vs forwarded） |
| forwarding 邊界 | `_forward_to_worker`（server.py:931）既有 log | ee worker URL、HTTP 狀態、timeout（180s） |
| build 執行 | ee worker `ato_bridge` 新增 | subprocess 起訖、exit code、耗時、atopile 版本 |
| build 原始 log | `build_log_path`（workspace 落盤） | atopile stdout/stderr 全文；MCP 回應僅帶路徑 |
| 證據信封 | `validation_evidence.v1` 既有結構 | oracle=constraint_solve、solver_verdict、picks、版本 |
| readiness 聚合 | `c06_test_plan` 聚合輸出 | 第五層狀態（present/pass/fail/absent） |

## Debug checkpoints（component boundaries）

跨層問題（例如「build 成功但 C04 吃不進 pcb」）依序檢查：

1. **request boundary**：core 收到的 `project_path` 是否在 workspace 內、`PATH_ARG_KEYS` token 解析是否生效。
2. **forwarding boundary**：ee worker 收到的 arguments 與 core 發出的是否一致（既有 `/invoke` POST body）。
3. **subprocess boundary**：`ato build` 實際 argv、cwd、exit code、`build_log_path` 內容。
4. **artifact boundary**：`.kicad_pcb` 是否存在、KiCad 版本相容（kicad-cli 可開）、路徑是否回傳給 core。
5. **evidence boundary**：信封是否過 `__post_init__` oracle 檢查（ENV_TOOL_UNKNOWN = DD-4 三處註冊不齊）。

## Metrics

- ee 容器啟動自檢：`ato --version` == pinned 版本（比照 kicad-cli 檢查模式），不符即容器啟動失敗（fail-loud）。
- TV-3 的「零 registry 外連」驗證手段：worker 容器 net namespace 觀測或 mock registry endpoint。
