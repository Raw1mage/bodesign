# Tasks: mcp_r16-domain-kb

## 1. Server 實作

- [x] 1.1 先 `sqlite3 .specbase/ragbase.sqlite ".schema"` 對齊 ragbase 實際表結構（objects/FTS 表名欄位），據此寫 `_h_kb_query`（FTS/LIKE/hybrid 三模式 + matchMode 揭露 + limit 預設 10）與 `_h_kb_get`（單物件全文 + provenance）
- [x] 1.2 TOOLS schema 註冊兩工具（description 開頭聲明 read-only、無副作用；kb_query 帶 q/type/limit 參數 schema）
- [x] 1.3 KB 連線層：`BODESIGN_KB_DB` env + URI `mode=ro` + `PRAGMA query_only=ON`；缺檔/不可開 → `KB_UNAVAILABLE` typed error + remedy 行

## 2. 掛載與 manifest

- [x] 2.1 三份 compose（主/dev/workers）core 服務加 `./.specbase:/var/lib/bodesign/kb` bind mount + `BODESIGN_KB_DB=/var/lib/bodesign/kb/ragbase.sqlite` env
- [x] 2.2 mcp.json instructions 加 KB signpost 句 + version 0.2.0→0.3.0
- [x] 2.3 判斷密集工具 description 加 `consider: bodesign_kb_query`（emit_layout / analyze_emc / analyze_thermal / si_check / simulate / layout_drc_gate / autoroute_preflight / placement_preflight，≥5 個）

## 3. 測試與驗證

- [x] 3.1 `tests/test_kb_tools.py`：FTS 命中既有物件 / 短 token like-scan matchMode / 缺檔 KB_UNAVAILABLE / query_only 生效（嘗試寫入應失敗）
- [x] 3.2 既有測試套件無回歸（PYTHONPATH 全 packages）— 失敗集與 pre-change baseline byte-identical（4 FAIL + 1 ERROR 皆為既存：test_mcp_server 工具數舊期望 47 / gate.py registry 漂移），非本 plan 回歸
- [x] 3.3 live MCP smoke：`BODESIGN_DEV=1 ./mcpctl.sh restart` 後由 MCP rail 呼叫 kb_query（"EMC decoupling" 命中）+ 兩門一致性（gate.ts 同 query 同 id 集合）
- [x] 3.4 event_record 收尾 + CHANGELOG + specs/architecture.md 同步（新 KB serving 邊界）— orchestrator 完成：architecture.md services/mcp 段補 R16 節、CHANGELOG 2026-07-11 段、test_mcp_server 工具數 47→55 修正、TV-6 兩門一致性驗證通過
