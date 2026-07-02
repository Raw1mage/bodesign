# Event: R13 landing split + WebDAV working-cache — kickoff（plan → implementing）

- **Date**: 2026-07-02
- **Scope**: `plans/mcp_r13-landing-webdav-cache/`
- **Status**: kickoff
- **Tags**: mcp-standard, r13, webdav, refactor

## 需求

使用者：「查看最新mcp integration standard，重構bodesign，用wendav和skill帶script
的技術來解決目前docker based mcp中磨擦最大的工作」。

## 範圍（IN/OUT）

- IN：(1) R13 compute/landing split — 全部 Bucket-2 ~40 個純 Python 專案目錄
  I/O verbs 落地為 `skills/bodesign/scripts/gate.py`（python3 + repo packages，
  不 vendor）；(2) WebDAV per-deliverable working cache — 照 docxmcp living spec
  （`specs/mcp/webdav-working-cache`）移植 `_webdav.py` 協議層 + AuthProvider
  （Basic-only）+ cache lifecycle + token_store kind/reaper 擴充；(3) 容器 surface
  收斂（~70 → ~30 tools，version 0.2.0，`TOOL_LANDED` 指路）；(4) 兩層驗證
  （host venv + 部署映像，配方明文化）+ rclone E2E。
- OUT：heavy 演算法不動、vault 資料模型不動、gateway 不動、workers 拓撲不動、
  R12 shared-tier 不做。

## 任務清單

tasks.md 8 群：1 gate.py 骨架 / 2 ~40 verbs 落地 / 3 landing 測試 /
4 token_store 擴充 / 5 WebDAV 移植 / 6 surface 收斂（stop gate：使用者批准）/
7 兩層驗證 / 8 文件收尾。

## Key Decisions（開場時已定）

- 偵查（explore subagent，line-verified）分桶：~40 landing / ~25 heavy+vault /
  4 borderline。
- DD-1 landing 執行器 = gate.py 單入口 + `BODESIGN_SRC` 解析 repo packages，
  typed error 無 fallback（使用者拍板，不 vendor）。
- DD-4 WebDAV 直接移植 docxmcp 已驗證件（協議層近原樣，store 介面對接為主要
  改寫點）。
- DD-6 Basic-auth-only 首發（承 docxmcp 部署拍板，不掛 JWT secret）。
- DD-9 兩層驗證配方明文化（吸收 docxmcp BR_20260702 教訓）。

## Verification plan

spec.md AC-1..AC-10；test-vectors.json TV-1..TV-12。
