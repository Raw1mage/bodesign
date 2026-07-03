# BR: net2pcb_board 不設 Reference → DSN export 靜默失敗 → autoroute 假成功

日期：2026-07-03
來源：validation/prd-to-gerber-e2e E2E 實證（C04 段，subagent 實跑）
嚴重度：High（假成功面，違「no silent fallback」天條）

## 現象（硬證據）

- `bodesign_route_net2pcb` 產出的 .kicad_pcb 全板元件 Reference 為 `REF**`。
- `pcbnew.ExportSpecctraDSN` 對含 `REF**` 板**靜默回 False**（不拋例外）。
- `bodesign_autoroute` 未檢查 export 回值與 SES 存在性 → 回 `routed:true, segments:0`——假成功。
- 復現：兩顆 REF** 元件的最小板即可復現（二分定位確認）。
- 修補後實跑：freerouting v1.9.0 1.92s 完成＋優化 7.81s，99 segments / 4 vias，unconnected=0。

## RCA

1. `packages/.../routing.py` `net2pcb_board` 建 footprint 時未呼叫 `fp.SetReference(ref)`。
2. `ExportSpecctraDSN` 的 False 回值被忽略。
3. `subprocess.run(capture_output=True)` 跑 freerouting 後不驗 returncode / SES 檔存在性，崩潰被吞。

三層都缺 fail-fast，形成連鎖假成功。

## 建議修復

- [x] `routing.py:116` 加 `fp.SetReference(ref)`（**已熱修**：host 源碼已改、ee 容器已熱修；**未 commit**）。
- [ ] `ExportSpecctraDSN` 回 False → 顯式報錯（列出板上 REF**/異常元件）。
- [ ] autoroute 驗 freerouting returncode + SES 檔存在性，缺失 → fail-fast。

## 影響範圍

C04 佈線鏈全部呼叫者；任何經 net2pcb_board 建板的流程。

## 驗證手段

- 迴歸：REF** 板 → 預期顯式報錯（非 routed:true）。
- 正常板：E2E LED driver 案 99 seg / 4 via / unconnected=0 可重現。
