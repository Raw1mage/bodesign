# Tasks: quality_bodesign-skill-disambiguation

驗收尺（每個 task 適用）：每處重構須能指認「原本會誘導 agent 做出什麼錯誤推論」；硬知識 UNIT 的事實斷言須帶 SPEC-REF；指認不出誤導的不動。

## 1. Pilot：pcb-layout-rules-compendium.md → Engineer Mode 範本

- [x] 1.1 快照 baseline：`cp` 現行 compendium 到 workspace/skill-snapshot（供 eval 對照舊版）
- [x] 1.2 精讀 compendium 全檔 + 對照 standards-compliance.md（辨識每個裸值該引哪個主源）
- [x] 1.3 修正 P0 數值 bug：#1 HV 間距 0.005→0.0025 mm/V（對齊 standards-compliance.md:125 主源）
- [x] 1.4 重構 8 筆本檔誤導源（#1-5,8,17 + #18同型）為 Engineer Mode UNIT：quantity/rule core + SPEC-REF + FORBID + INVARIANT + DONE-WHEN + 失效邊界
- [x] 1.5 與主源衝突/重複值對齊單一真源（引「見 standards-compliance §X」而非重述）
- [x] 1.6 Override clause 檢查：只對可驗證契約用 rigid；rationale 保持 why-first 散文

## 2. 驗證 pilot（skill-creator eval loop）

- [x] 2.1 寫 2-3 個 eval 測試 prompt（模擬 agent 用 compendium 做 HV 間距/電流線寬/熱過孔判斷）
- [x] 2.2 spawn with-skill（新版）vs baseline（舊版 snapshot）subagent 同輪跑
- [x] 2.3 assertion 化 DONE-WHEN：關鍵 assertion = agent 是否算出正確 0.0025/V 而非 0.005/V
- [x] 2.4 grade + aggregate benchmark + generate_review.py 產 viewer 給使用者審
- [x] 2.5 依 feedback 修正，必要時再跑一輪

## 3. 推廣 pattern 到其餘高誤導密度 skill

- [x] 3.1 P1 契約缺口：datasheet-verification.md（#9 負電壓不查、#10 缺欄語意）補輸出契約邊界語
- [x] 3.2 P1 命名誤導：c04-layout/GUIDE.md + kicad-interactive-layout.md（#6,7 mirror）加漂移警語
- [x] 3.3 P2 啟發式當精確：scripts/README.md（#11 Vref 猜值、#12 12mm 吸附）補 confidence 標註
- [x] 3.4 P2 前提不齊：mechanical-design-advisory.md（#18 FDM 幾何值）逐列補條件
- [x] 3.5 剩餘散筆（#13,14,15,16）視 eval 佐證的收益決定是否納入

## 4. 收尾

- [x] 4.1 沉澱反誤導寫作 pattern 進 KB（failure-mode / control；含 honesty-contract vs 誤導的辨別法）
- [x] 4.2 event_record 收尾 + architecture sync 檢查
- [x] 4.3 更新 CHANGELOG/README（若動到交付面）
