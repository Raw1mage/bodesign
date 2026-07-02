# BR: render_prd.py 印出「readiness 100% | blocking 0」，但 canonical c00_readiness 回 84% / blocked / 13 fake-complete — 兩個 readiness 表面不一致

- Date: 2026-07-03
- Session: opencode `ses_0dc8a6aaaffeaeAvPml5SkW25Q`（thesmart_products aiguard C00-PRD）
- Severity: medium（誤導性完成訊號；honesty-model 風險）

## 現象（含硬證據）

1. `stages/c00-prd/assets/render_prd.py` 對 aiguard C00 answer_state 執行後印出：
   `readiness 100% | complete 81/81 | blocking 0 | approved False`。
2. 同一份 answer_state 跑 canonical verb `gate.py c00_readiness`（→ `assess_c00_prd_readiness`）回：
   `readiness_pct: 84, status: "blocked", field_counts: {complete: 68, blocking: 13}, dod_ok: false`，
   並列出 13 個 `fake_complete_fields`（success_metric, subsystems, main_components, interfaces, industrial_design_intent, display_or_ui, environment, power_budget, battery_or_charging, sensors, key_parts_or_references, risks, range_or_link_target）— 全部因 prose 內含 inline `TBC`（DD-4 fake-complete 偵測）。
3. 後果實例：前一 session 以 render_prd.py 輸出為據，在交付文件與 generated md 標註「C00 readiness: 100% (ready)」— 與 canonical gate 判定相反。

## RCA

`render_prd.py`（stage asset，快速渲染腳本）自帶簡化 readiness 計算：只看 state ∈ answered/accepted-risk，**不跑 DD-4 fake-complete（placeholder token）偵測、不算 document_gates/dod_ok**。canonical `assess_c00_prd_readiness` 才是 gate 契約（GUIDE 明言 `readiness_pct: 100 ≠ done，讀 dod_ok`）。兩條路徑對同一輸入給出矛盾的頂層數字，且 asset 腳本的輸出格式（`readiness 100%`）看起來就像正式判定，agent 極易引用錯的那個。

## 建議修復

1. render_prd.py 改為 import `assess_c00_prd_readiness` 取數（單一計算來源），或至少在輸出行印 `dod_ok` + fake-complete 計數與「non-canonical, run gate.py c00_readiness for the gate」警語。
2. 生成的 `Project_Requirements.generated.md` 頭部 readiness 行同樣取自 canonical assess。

## 影響範圍

- 任何用 render_prd.py 快速重生 PRD 的流程：頂部 readiness 標註可能虛高；下游（docx 轉寫、handoff 報告）繼承錯誤的「ready」聲明，違反 honesty model。

## 驗證手段

- 修復後：render_prd.py 與 `gate.py c00_readiness` 對同一 answer_state 輸出相同 readiness_pct/status；含 TBC 欄位時兩者都應報 blocked。
- 本次證據：兩指令對照輸出（見上）；placeholder 命中明細由 `_PLACEHOLDER_EN` 掃描確認全為 inline `TBC`。

## 結案（2026-07-03）

- 修復：`skills/bodesign/stages/c00-prd/assets/render_prd.py` 全面改寫 —— 移除本地簡化 readiness 計算（OPEN/PARTIAL/DONE_STATES + count_fields + DOC_GROUPS/HANDOFF_GATES 鏡射表全數刪除），改為 `_resolve_src()`（同 gate.py 的 $BODESIGN_SRC / 向上走訪解析）+ import canonical `assess_c00_prd_readiness` 取數。無 fallback：packages 找不到即 fail fast 並指向 `gate.py c00_readiness`。
- 輸出強化：文件頭與 stdout 皆帶 `readiness N% (status)` + `DoD ok` + `fake_complete` 計數；handoff report 新增 Fake-Complete Fields / Warnings 區塊；document/downstream gates 直接取自 canonical result。
- 驗證：TBC fixture（69 欄、13 個 inline TBC）下 `gate.py c00_readiness` 與 render_prd.py 均回 `81% (blocked), dod_ok=false, fake=13, blocking=13` —— 完全一致。既有測試 `test_c00_prd_template` / `test_guide_dod` / `test_readiness_invisible_path` 全 OK。
