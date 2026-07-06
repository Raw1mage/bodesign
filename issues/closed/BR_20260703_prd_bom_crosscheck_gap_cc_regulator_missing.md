# BR: C00 PRD 定義的恆流晶片未落板 —— C03 降級超出 PRD 允許範圍且無 PRD↔BOM 履約 gate 攔截

- Date: 2026-07-03
- Session: opencode `ses_0db8f20d1ffe9Jyjzd1sFEb1Go`（E2E LED driver 實證，使用者驗收 C04 交付物時發現）
- Severity: **High**（交付物不符 PRD；降級決策未被任何確定性 gate 攔截，違「展示可靠度」哲學的縫隙）

## 現象（含硬證據）

1. C00 PRD `s04_system_architecture.main_components` 明載：
   > "NPN/resistor linear current sink **or AL5809-ish 2-pin CC regulator**"
   （`experiments/e2e-led-driver/C00-PRD/Project_Requirements.generated.md:125`）
2. C04 板上實際 footprint 盤點（`e2e-led-driver.routed.kicad_pcb`）：
   C1/C2（decap）、D1（TVS）、D2-D5（LED×4）、F1（polyfuse）、J1（USB-C）、R1-R6、SW1、H1/H2 ——
   **零個電晶體、零個 regulator IC**（netlist grep SOT/NPN/Q/regulator = 0 hits）。
3. 實際電流控制淪為 4×140R 純電阻鎮流（`C03-EE/e2e-led-driver.net:167-206`），
   且 140R 基於假設 Vf≈3.0V、無 datasheet 錨定（G4 已記）。
4. PRD 效能目標 P1「LED string current 60mA ±10% @5.0V」（generated.md:93）——
   純電阻鎮流下 LED Vf 散差（±0.3V 級）直接吃掉 >±20% 電流變化，**P1 結構性達不到**，
   但 C04 交付物無任何 deviation 標記，DRC/ERC gate 全綠照樣產出 Gerber。

## RCA

三層失效鏈：

1. **降級超範圍**：C03 vault 查 `AL5809-060` → absent → fail-fast 降級。降級本身符合 G4 天條，
   但降級落點選了「純電阻鎮流」——PRD 允許的替代下限是「NPN/resistor linear current **sink**」
   （仍是主動恆流），純電阻不在 PRD 允許集合內。降級決策由 LLM 在 session 內裁定，無規格比對。
2. **無 PRD↔BOM 履約 gate**：現有 `reference_crosscheck` 只對照參考設計；`export_bom` 只輸出。
   **不存在**「C00 main_components ↔ C03 netlist 元件」的確定性交叉檢核——PRD 定義的關鍵元件
   缺席/被替代時，沒有任何工具產生 BLOCKING deviation 清單要求使用者批准。
3. **C04 gate 只看電氣規則**：DRC/ERC 檢查的是「板子自身一致性」，不檢查「板子履約 PRD」。
   四層驗證（ERC/DRC/crosscheck/SPICE）在 C00→C03 縫上是空的。

## 建議修復

1. **本案補救（使用者裁決拓撲）**：AL5809 datasheet ingest 後按 PRD 首選重設計 C03，或退而用
   NPN linear sink（需 PRD P1 容差放寬批准），重跑 C04；純電阻方案若保留必須 `revise` PRD 並留
   deviation 記錄。
2. **工具層（結構修）**：新增 `bodesign_prd_bom_crosscheck`（core 側 pure function）：
   輸入 C00 answer_state `main_components` + C03 netlist，輸出逐項 `present / substituted / missing`；
   `missing`/`substituted` 未經使用者批准 → BLOCKING，C04 入口 gate 拒走。
3. **降級協議**：vault absent 降級時，替代方案必須通過 PRD 允許集合比對；集合外替代一律
   BLOCKING 等使用者決策，不得由 LLM 自行落點。

## 影響範圍

- 所有 compose 路徑案件的 C00→C03 handoff（履約縫全開）。
- E2E LED driver 案 C04/fab 交付物：**不合格**，需重做。
- `quality/deterministic-preplacement` 開案的基線板同此問題（重跑時一併換基線）。

## 驗證手段

- 迴歸：AL5809 缺席 + 純電阻 netlist → crosscheck 回 `substituted (out-of-envelope)` BLOCKING。
- 正案：補齊恆流器件後 crosscheck 全 `present`，C04 gate 放行。
- E2E 重跑：新板 P1 可由 SPICE/datasheet 錨定證據支撐。

## Resolution（2026-07-06 closed）

- **工具層**：`packages/workflow-core/bodesign_workflow_core/prd_bom_crosscheck.py` 已落地——確定性履約檢核（C00 `main_components_structured.json` manifest ↔ C03 netlist），逐項 `present / substituted / missing` verdict；out-of-envelope 替代未經使用者批准 → BLOCKING。輸出 `prd_bom_crosscheck.report.json`，manifest 過期有 loud `MANIFEST_STALE` warning。
- **降級協議**：`skills/bodesign/stages/c03-ee/GUIDE.md` 已補 vault-absent substitution protocol 段——降級落點必過 PRD 允許集合比對；集合外一律 BLOCKING 等使用者裁決，approvals 寫入 user-owned 檔。
- **Spec**：`specs/quality/prd-bom-crosscheck/`（living，tasks 全 [x]）。
- **殘留（非工具層）**：E2E LED driver 案的板重做屬產品側補救，由使用者裁決拓撲後另案執行。
