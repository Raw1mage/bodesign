# BR: `analyze_emc` 合成層丟棄結果 — engine 產出真實 findings，工具卻回 `failed: produced no output`

- **Date**: 2026-06-23
- **Reporter**: TheSmartAI (orchestrator)
- **Target**: bodesign 維護者（eda-bridge / pcb_verify EMC 合成層）
- **Type**: bug（合成層丟結果 — 工具回 failed 但底層 analyzer 已成功產出資料）
- **Severity**: **medium-high** —— `analyze_emc` 在 analyzer engine 已就緒（前一 BR 已修）的情況下，仍**穩定**回 `failed: produced no output`，使 C06 EMC verdict 無法落地，即使分析其實已跑完。
- **Origin task**: aiguard C06 — analyzer engine 掛載修好後，補跑三個 verdict，simulate/thermal 正常，唯 EMC 卡在合成層。

---

## 1. 一句話

C06 analyzer engine 掛載修復後（見 `issue_20260623_c06_analyzer_engines_not_mounted_in_container.md`，已驗證解決），`bodesign_analyze_emc` 的**底層 analyzer 確實成功執行並產出真實中介結果**（schematic analyzer 41 findings、pcb analyzer 36 findings），但 `analyze_emc` 工具的**最終合成層**沒把這些中介結果組成 verdict，反而回 `status: failed` + warning `analyze_emc produced no output` —— 真實分析資料在合成階段被丟棄。

---

## 2. 觀察到的 gap（以本次任務為證據）

對真實 `aiguard_power.kicad_sch` + `aiguard_power_routed.kicad_pcb` 跑 `bodesign_analyze_emc`，**兩次**（含指定 `standard: CISPR32`）皆回：

```json
{ "kind": "emc", "status": "failed", "finding_count": 0, "findings": [],
  "report_path": null, "warnings": ["analyze_emc produced no output."] }
```

但工具同時 produced 了中介檔，內含真實資料：

- `emc_power/schematic.json` — `analyzer_type: schematic`, schema 1.3.0,
  **total_findings: 41**（error 2 / warning 4 / info 35）。實際 findings 例：
  - `SS-001` (error): Sourcing audit 0/21 BOM lines 有 MPN（與 C03 BOM 未填 MPN 一致）。
  - `RS-001` (warning): VBAT/VBUS/VSYS 等 power net 無 power_out/PWR_FLAG（典型 power-source 標註）。
- `emc_power/pcb.json` — `analyzer_type: pcb`, **total_findings: 36**（error 6 / warning 1 / info 29），
  含完整板級統計（43 footprints、401 track segments、`routing_complete: false, unrouted_net_count: 4`）。

對照組（同次任務、同 engine）：`simulate` 回 `status: ok`（15/15 pass）、`analyze_thermal` 回 `status: ok` —— 證明 engine 與掛載沒問題，**只有 EMC 工具的合成路徑壞了**。

---

## 3. Root cause 方向（待維護者以 code 證實）

- **`packages/eda-bridge/bodesign_eda_bridge/pcb_verify.py`** 的 `analyze_emc` 路徑：engine resolvable（`resolve_skill` 已過，否則會是 `skipped-no-skills` 而非 `failed`），schematic/pcb 兩個 sub-analyzer 也都寫出了 `*.json`，但把兩者**合成為 PcbVerifyResult findings** 的那一步回了空 → `produced no output`。
- 可能成因（候選，需 code 確認）：
  1. 合成層讀 sub-analyzer 輸出時 schema 對不上（中介是 schema 1.3.0；合成器可能期待不同鍵）。
  2. EMC 合成器期待某個 emc-specific 中間產物（非 schematic/pcb generic findings），而該產物沒生成。
  3. 例外被吞成空結果（`failed` + 空 findings，而非把實際 error 往上拋）。
- **對比 anchor**：`simulate.py` 的合成路徑能把 ngspice 輸出組成 15 筆 pass results；EMC 路徑在相同前置條件下卻產不出，差異就在 EMC 合成器本身。

---

## 4. 為何是 bug 而非誠實邊界

- engine 已就緒（非 `skipped-no-skills`）、sub-analyzer 已產出真實 findings —— 條件齊備卻回 `failed`，且 `failed` 訊息（`produced no output`）**掩蓋**了「其實有 41+36 筆結果」這個事實。
- 這不是「沒資料可分析」的誠實 not-run，是「分析了但結果在最後一哩被丟掉」。對使用者而言，等於白跑且無從得知中介資料其實存在（除非手動撈 `produced` 裡的中介檔，本次即如此）。

---

## 5. 建議修復方向

1. **合成層接住中介 findings**：讓 `analyze_emc` 把 schematic.json + pcb.json 的 findings 正常合併進 `PcbVerifyResult`（至少把已存在的 41+36 findings 暴露出來，按 severity 分桶）。
2. **失敗要 fail-loud 帶因**：若合成真的失敗，warning 應說明「為何」（schema mismatch / missing emc artifact / caught exception），而非籠統 `produced no output` —— 比照已修的 readiness fail-loud 精神。
3. **回歸測試**：用一個已知會產 findings 的 schematic+pcb 對，斷言 `analyze_emc` 回非空 findings 且 `status != failed`。

---

## 6. 影響範圍 / 暫行狀態

- 受影響：所有需要 C06 EMC pre-compliance verdict 的專案。
- 暫行：aiguard C06 的 EMC 維持 `not-run`，已在 `01.openmv/C06-Verification/Verification_Summary.json`
  與 `Test_Plan.md` 誠實註記「analyzer 有產出 41+36 findings，但工具合成回 failed」，原始中介檔保留於
  `C06-Verification/evidence/emc_power_{schematic,pcb}.json` 供修復後比對。simulate（pass）/thermal
  （空跑）/crosscheck（pass）不受影響。
- 未開遠端 GitHub issue（local-first）。治本實作待維護者授權。

> 關聯：這是 C06 analyzer 三部曲的第三個缺陷 —— (1) 路徑可見性 readiness 靜默
> (`issue_20260623_readiness_silent_missing_on_invisible_path.md`, 已修)、(2) analyzer engine 未掛載
> (`issue_20260623_c06_analyzer_engines_not_mounted_in_container.md`, 已修)、(3) 本 issue：engine 已掛
> 但 EMC 合成層丟結果。前兩個修復讓本缺陷得以浮現（engine 不在時根本到不了合成層）。

---

## Resolution

- **Status**: resolved / fixed。Closed 2026-06-23。歸入 C06 spec DD-7
  (`plans/deployment_c06-analyzer-engines-in-container/`)。
- **Final RCA**（在 ee 容器內重現、撈出 pcb_verify 吞掉的 stderr 證實）：不是合成層 schema
  對不上,也不是缺 emc 中介產物 —— 是**跨引擎 import 失敗**。emc 引擎
  `analyze_emc.py → emc_rules → emc_formulas` 有一行 `from kicad_utils import ...`,
  而 `kicad_utils` 住在 **kicad 引擎**。在我 C06 修復採的 bundled 分目錄佈局
  (`/opt/bodesign-engines/{emc, bodesign/engines/kicad}`)下,emc 子行程的 `sys.path` 只有
  自己的 scripts 目錄 → `ModuleNotFoundError: No module named 'kicad_utils'` → 腳本
  crash、不寫 `emc.json` → 工具回 `failed: produced no output`。simulate/thermal 沒事是因為
  它們跑的是 kicad 自己目錄的腳本,`kicad_utils` 同目錄就在 path 上。§3 的候選 #3「例外被吞成
  空結果」最接近 —— pcb_verify 用 `capture_output` 卻沒把 stderr 往上帶。
- **為何 C06 驗證沒抓到**：C06「verified」當時只跑了 simulate + emc/thermal 的**引擎 gate**
  (`resolve_skill` 過),沒跑完整 emc verdict —— gate 過了,但**合成下一步**才炸。誠實補記於
  DD-7。
- **Fix implemented**（`pcb_verify.py`）：
  1. 新增 `_engine_env()`,把 kicad 引擎的 `scripts/` 前置進 emc 子行程的 `PYTHONPATH`,
     讓跨引擎 import 解析得到。
  2. 產不出 output 時,把子行程 stderr 末行帶進 warning(fail-loud-with-cause),不再只回
     籠統的 "produced no output"。
  3. 測試缺口一併修:整合測試 `test_emc_and_thermal_on_generated_board` 的 skip-guard 原本只認
     legacy `~/.claude/skills`,所以在 bundled 佈局下永遠 skip(這就是本 bug 漏網主因);改用
     `resolve_skill` 認 bundled 佈局。另加 host 可跑的 `EngineEnvTests`。
- **Verification**：
  - 引擎層直證:`PYTHONPATH=<kicad>/scripts python3 analyze_emc.py --schematic … --output emc.json`
    → `EMC analysis complete → emc.json`,exit 0(修前同指令 `ModuleNotFoundError`)。
  - 端對端:rebuild ee image 後,`test_pcb_verify` 在容器內 **4/4 OK**,含
    `test_emc_and_thermal_on_generated_board`(compose→layout→`analyze_emc` 回 `status: ok`、
    findings 非空、含 error severity)。
- **Follow-ups / residual risk**：若未來有更多引擎彼此互相 import,`_engine_env` 可擴充帶多個
  engine scripts 目錄(目前只需 kicad)。aiguard 真實 PCB 的 EMC verdict 待該 tree 可見時補跑
  (非阻斷;本次以 generated board 端對端驗證)。
