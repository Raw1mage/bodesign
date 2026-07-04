# Tasks: quality_prd-bom-crosscheck

## 1. L1 — 確定性履約 gate

- [x] 1.1 `packages/workflow-core/bodesign_workflow_core/prd_bom_crosscheck.py`：manifest/netlist 讀取（fail-fast）、輕量 .net S-expr 元件解析、逐 role pattern+qty 比對、Verdict/CrosscheckReport dataclass、報告落盤
- [x] 1.2 `tests/test_prd_bom_crosscheck.py`：test-vectors.json 四案（missing BLOCKING / in-envelope substituted / unapproved out-of-envelope / manifest 缺席 fail-fast）+ 確定性重跑案（10 tests 綠，含 MANIFEST_INVALID 一輪全報 / NETLIST_PARSE_ERROR / qty_min / stale 案）
- [x] 1.3 `services/mcp/server.py` 註冊 `bodesign_prd_bom_crosscheck`（handler + schema，core 側）；`test_converged_registry_tool_count` 同步 43→45（含未 commit 的 ato_build）
- [x] 1.4 E2E LED driver 迴歸：手工抽取現案 manifest（含 current-regulator role + NPN 允許替代），對現有純電阻 netlist 跑出 `missing` BLOCKING FAIL（報告落盤 C03-EE/prd_bom_crosscheck.report.json：16 元件、6 present、current-regulator missing）

## 2. L2 — 降級協議接線

- [x] 2.1 `skills/bodesign/stages/c03-ee/GUIDE.md`：vault-absent substitution protocol 段（降級落點必過允許集合比對；集合外一律 BLOCKING 等使用者；approvals 寫入 user-owned）
- [x] 2.2 C03 readiness 接線：crosscheck 報告存在且 gate=FAIL 時 readiness 列 BLOCKING 項；報告缺席時明示「gate 未跑」（不得默認 PASS）
- [x] 2.3 `specs/architecture.md` C03 段補 gate 資料流

## 3. L3 — E2E 本案重做（stop gate：拓撲裁決）

- [x] 3.1 使用者裁決拓撲（AL5809 datasheet ingest 首選 / NPN sink 備選）— 2026-07-03 裁決：NPN linear sink（in-envelope，MMBT+Rsense，Vbe 需 datasheet 錨定）
- [x] 3.2 C03 重設計為 NPN linear sink（Q1-Q4 MMBT2222A 集極接 LED 陰、射極→Rsense→GND、共用偏壓 R7/R8）；compose_schematic 成功（route_stats wired 10 / labelled 5，sheet A3）；**crosscheck gate=PASS**（current-regulator `substituted in_envelope` matched [Q1-Q4]，其餘 6 roles present，blocking=[]）— 以 L1 pure function host 端實跑證實，報告落 `C03-EE/prd_bom_crosscheck-npn.report.json`；spec+netlist 落 `C03-EE/e2e-led-driver-npn.spec.json` / `.net`
- [x] 3.3 C04 重跑完成 — 解阻後（workers experiments mount + rebuild tools:45）跑通全鏈：net2pcb placed=22/pads=90/unmapped=0（J1 USB-C pinmap applied）→ autoroute routed=True 185 seg/12 via → DRC copper=0/unconnected=0/silk=0 clean=True → emit_fab 25 gerber + drill + pos + STEP + PDF，host 可見 C04-LAYOUT/fab-npn/。根因修復：NPN spec 補 22 元件 footprint（原空 Footprint 欄致 placed:0，屬設計資料缺口非工具 bug）

## 4. 收尾

- [x] 4.1 全套測試綠（778 tests，僅 4 既有 error：3 c02 discover 匯入 + 1 worker_unreachable，與本輪零 delta）；L1/L2 落地
- [x] 4.2 收尾 event 已記；architecture.md C03 gate 資料流已同步（L2 2.3）
- [x] 4.3 infra 三缺口已立案 BR_20260703_workers_mode_infra_gaps_block_c04_realization.md（Medium，投影 issue 物件）
