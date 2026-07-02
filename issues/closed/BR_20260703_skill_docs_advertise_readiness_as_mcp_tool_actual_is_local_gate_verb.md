# BR: SKILL.md / GUIDE.md 仍教 agent 以 MCP tool 名呼叫 `bodesign_c00_readiness`，但 R13 split 後 readiness 已是 local gate verb — 造成 invalid-toolcall 迴圈

- Date: 2026-07-03
- Session: opencode `ses_0dc8a6aaaffeaeAvPml5SkW25Q`（thesmart_products aiguard C00-PRD 交付更新）
- Severity: medium-high（文件與工具面 drift；每個照文件走的 agent 都會撞 invalid sink 多輪）
- Axis: 軸A（工具文件缺陷）為主；伴生軸B（gate.py 正解存在但 agent 未選中）

## 現象（含硬證據）

1. Agent 依 skill 文件自驗 C00 readiness，呼叫 `bodesign_c00_readiness(folder=...)` → opencode invalid sink：
   `Tool "bodesign_c00_readiness" does not exist in this session`。同 session 內含 remcp catalog refresh 後重試，共 **~10 次 invalid**（02:11–02:17）。
2. `refresh_capability_layer(remcp:true)` 顯示 `mcpapp-bodesign=connected(N tools)` — server 連線正常，只是**沒有這個名字**。
3. MCP server 實際註冊面（`services/mcp/server.py` 全量 `"name": "bodesign_*"` 掃描）：
   - 有 `bodesign_c00_emit_prd_docx`（line 728）
   - **沒有任何 `bodesign_c00_readiness` / `bodesign_c0X_readiness` / `bodesign_package_readiness`** MCP tool。
4. 文件仍宣稱它們是可呼叫工具：
   - `skills/bodesign/SKILL.md:110`：「C00 / C01 / C02 / C05 / C06 → `bodesign_c00_readiness` … `bodesign_c06_readiness` (`folder`)」
   - `skills/bodesign/stages/c00-prd/GUIDE.md:53`：「**Self-verify:** run `bodesign_c00_readiness` (`folder`)」
   - 同段亦引用 `bodesign_c04_readiness`、`bodesign_package_readiness`。
5. 真正的執行路徑已存在且可用：`skills/bodesign/scripts/gate.py` landing verbs —
   `c00_readiness` → `assess_c00_prd_readiness(folder)`（gate.py:173），另有 `c00_scaffold_prd` / `c00_emit_prd` / `c00_update_answers` / `c01..c06_readiness` / `package_readiness`（gate.py:171-268）。
6. Agent 本次 fallback 成功路徑：直接跑 `stages/c00-prd/assets/render_prd.py`，輸出 `readiness 100% | complete 81/81 | blocking 0` — 證明 compute 本身健在，缺的只是文件指路。

## RCA

R13 compute/landing split（opencode commit `f80694827` docs(mcp-standard)）把 ~50 個 deterministic Bucket-2 verbs（含全部 readiness）從 MCP server 下放到 skill-attached local script `gate.py`，MCP 面只留 heavy/compute tools。**SKILL.md 與各 stage GUIDE.md 的 self-verify 段落未同步改寫**，仍以 `bodesign_<verb>` MCP-tool 語法宣傳這些 verbs。Agent 忠實照文件 → invalid；invalid 訊息又不含「這是 gate.py verb」的導引，agent 只能瞎試 tool_loader / remcp / 改 prefix，全部無效。

## 建議修復

1. **SKILL.md §self-verify + 全部 stage GUIDE.md**：把 readiness 呼叫語法改為 gate.py 形式，例如
   `python3 <skill>/scripts/gate.py c00_readiness --folder <abs>`；明文「readiness/scaffold/emit/update-answers 是 landing verbs，不是 MCP tools」。
2. **命名對照表**：SKILL.md 附一張「文件舊名 → gate.py verb」對照（`bodesign_c00_readiness` → `c00_readiness` 等），供舊記憶 agent 自我糾正。
3. （opencode 側，可選）invalid sink 對 `bodesign_*` 未知名可附 hint：「bodesign readiness/landing verbs run via skills/bodesign/scripts/gate.py」。
4. 檢查 enablement.json / template 是否也殘留舊 MCP-tool 名（本次掃描 enablement 無 c00 字串，低風險）。

## 影響範圍

- 所有依 SKILL.md/GUIDE.md self-verify 契約收尾的 bodesign stage 工作（C00/C01/C02/C04/C05/C06 readiness、package_readiness roll-up）：每次收尾必撞 invalid，或被迫繞道手跑 assets script，self-verify 契約實質失效。

## 驗證手段

- 修復後：grep skill tree 應無「`bodesign_c0X_readiness`」以 MCP-tool 語法出現；`python3 gate.py c00_readiness --folder <thesmart 03.aiguard C00-PRD>` 應回 readiness JSON。
- 本次證據指令：`grep -oE '"name": "bodesign_[a-z0-9_]+"' services/mcp/server.py | sort -u`（無 readiness）；`grep -n readiness skills/bodesign/scripts/gate.py`（有 c00..c06/package readiness verbs）；opencode session recall 02:11–02:17 invalid 記錄。
