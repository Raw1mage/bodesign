# Tasks: quality_verify-knowledge-hardening

## 1. 知識萃取（pjcau 8 域 verify → ragbase, plan scope）

- [x] 1.1 盤點既有 ragbase concept/control schema（`ragbase_query` 對齊不新造）
- [x] 1.2 萃取 workflow 物件：8 域驗證流程骨架（power/signal/thermal/EMI/DFM/mechanical/電氣review/datasheet一致性）
- [x] 1.3 萃取 concept 物件：各域判斷準則（decap-adequacy / power-path / no-connect-intent / pin-net-ssot / thermal-via / crosstalk）
- [x] 1.4 萃取 control 物件：JLCPCB/IPC 可執行檢查規則（trace/via/hole/pad/mask/silk/edge 閾值 + 來源錨點 + as_of）
- [x] 1.5 ragbase_distill + link 成鏈（source→asset→extract→distill），標來源錨點

## 2. 首個確定性 checker（DD-3：no-connect 宣告完整性）

- [x] 2.1 設計 checker 契約：輸入 `.kicad_sch`/netlist + NC 宣告，輸出 real-short vs pad-net-bug vs 刻意NC 分類（fail-fast，零 LLM）
- [x] 2.2 實作 checker 模組（core / eda-bridge，pure-python），引 control 物件為閾值源
- [x] 2.3 MCP 工具註冊（server.py handler `_h_*` + schema 兩處）
- [x] 2.4 單元測試（fixture-driven，含 E2E LED driver NC 案；byte-identical 輸出驗證）

## 3. 收尾

- [x] 3.1 tasks 即時勾選 + event_record 收尾（scope=plan:quality/verify-knowledge-hardening）
- [x] 3.2 architecture.md 同步（驗證 baseline / Immediate Capability Gaps）
- [x] 3.3 Friction→BR 掃描；ragbase rescope repo（若知識可跨 repo 復用則 promote）
