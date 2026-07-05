# BR_20260705 — landing-verb ergonomics：gate.py 從 XDG skill mirror 跑需手動 `BODESIGN_SRC`；且 `refs_ingest` 列於 server.py LANDED_VERBS 卻非 gate.py 實際 verb（宣稱 1:1 mirror 卻漂移）

- **Scope**: bodesign — `skills/bodesign/scripts/gate.py` landing-verb 探索/註冊 + server.py `LANDED_VERBS` 一致性
- **Severity**: MEDIUM（拖慢 landing-verb 首次使用；drift 讓 agent 依 server 提示呼叫不存在的 verb）
- **Discovered during**: `aiguard/refs-ssot-build` Phase 3/4（想用 refs-derived gate 驅動 regression）

## 現象（硬證據）

**D1 — BODESIGN_SRC 非自我說明**：
- 從 skill mirror 路徑 `/home/pkcs12/.local/share/opencode/skills/bodesign/scripts/gate.py` 直接跑 `c04_readiness` / `refs_ingest` →
  `{"code":"LANDING_PACKAGES_NOT_FOUND","message":"could not find bodesign packages/ ... Set BODESIGN_SRC=/path/to/bodesign repo","hint":"export BODESIGN_SRC=<bodesign repo root>"}`。
- 需 `export BODESIGN_SRC=/home/pkcs12/projects/bodesign` 後才能跑 landing verb。skill 文件/`--help` 未在首行醒目標示此前置需求（mirror 副本無法從 `../packages` 相對定位 repo）。

**D2 — refs_ingest verb drift**：
- `services/mcp/server.py:866` 的 `LANDED_VERBS` frozenset **包含 `"refs_ingest"`**（註解宣稱「This set mirrors gate.py's VERBS registry 1:1 (drift-guarded by tests)」）。
- 但 `gate.py refs_ingest` → `{"code":"VERB_UNKNOWN","message":"unknown verb: 'refs_ingest'; run gate.py --list"}`，且 `gate.py --list`（52 verbs）**不含** `refs_ingest`。
- 實際 refs 能力是 `bodesign_workflow_core.refs_gate` 的 Python API（`ingest_refs` / `require_refs`），**沒有** `refs_ingest` 這個 landing verb。plan handoff.md 亦引用「Run `refs_ingest`」誤導。

## RCA

- **D1**：gate.py 以相對 `../..` 尋找 `packages/workflow-core`；XDG mirror（`bun run install-skills` 投影）不含 repo 的 `packages/`，故 fail 並要求 `BODESIGN_SRC`。這是設計上的 fallback，但**未前置說明**，agent 首用必踩一次錯。
- **D2**：`server.py` 的 `LANDED_VERBS` 與 `gate.py` 的 VERBS registry **實際已漂移**——`refs_ingest` 在前者、不在後者。所謂「drift-guarded by tests」的測試未覆蓋此項，或 `refs_ingest` 是遺留命名（能力後來改以 Python API 暴露卻沒從 LANDED_VERBS 移除）。server 的 `TOOL_LANDED` 提示因此會叫 agent 去跑一個不存在的 landing verb。

## 建議修復

- **D1**：gate.py 啟動時，若非從 repo 內執行且 `BODESIGN_SRC` 未設，**主動探測**常見 repo 路徑（如 `~/projects/bodesign`）或讀 skill 的 `.capability-installed.json` 內記錄的 repo root；`--help` / SKILL.md 首段醒目標註 `BODESIGN_SRC`。
- **D2**：修 drift ——要嘛在 gate.py VERBS 補上 `refs_ingest`（若確實該是 landing verb，wrap `ingest_refs`），要嘛從 `server.py` `LANDED_VERBS` 移除 `refs_ingest` 並修正 plan handoff.md 的引用；補一條測試真正驗證 `LANDED_VERBS == gate.py VERBS` 1:1。

## 影響範圍

- 任何用 gate.py landing verb 的 C00–C06 流程（首用 BODESIGN_SRC 摩擦）。
- 依 server `TOOL_LANDED` 提示或 handoff 文件呼叫 `refs_ingest` 的 agent 會撞 `VERB_UNKNOWN`，誤判 refs-derived gate 壞掉（實際只是命名/註冊漂移）。

## 驗證手段

- D1：從 XDG mirror 跑 `gate.py c04_readiness`（不手動 export）→ 修復後應自動定位 repo 或給出可據以自救的精確 hint。
- D2：`gate.py --list` 是否含 `refs_ingest`，與 `server.py LANDED_VERBS` 逐項比對的測試通過；`gate.py refs_ingest`（若保留）回真實結果而非 VERB_UNKNOWN。
