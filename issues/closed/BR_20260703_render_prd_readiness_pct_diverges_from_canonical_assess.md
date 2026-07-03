
## RESOLUTION（2026-07-03，VERIFIED-CLOSED）

- 修復 commit：`c2bab09 fix(skill): render_prd.py readiness now sourced from canonical assess_c00_prd_readiness (BR_20260703)`。
- render_prd.py 不再自算 readiness：全部數字（pct/status/counts/dod_ok/fake-complete）import canonical `assess_c00_prd_readiness`（與 gate.py c00_readiness 同一 code path）；找不到 workflow-core 時 fail-fast 報錯並指向 gate.py，無簡化 fallback。
- 端到端驗證（aiguard answer_state）：render_prd 輸出 `readiness 84% (blocked) | complete 68/81 | blocking 13 | dod_ok False | fake_complete 13` + 13 欄 fake-complete warning — 與 canonical gate 判定一致，原矛盾（100% vs 84%）消除。
- 部署：XDG 投影已 rsync 同步（本次再度發現投影 stale，同前一 BR 教訓）。
- 附註：canonical layout 要求 `<project>/C00-PRD/answer_state.json` 且需 `BODESIGN_SRC` 指向 repo — 屬顯式 fail-fast 契約，非缺陷。
