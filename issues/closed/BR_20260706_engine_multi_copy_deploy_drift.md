# BR: 引擎三副本部署漂移(host/engpatch/site-packages)+ 未 commit 工作區被 subagent git checkout 摧毀

日期:2026-07-06
來源:thesmart_products aiguard C03 v03 session(引擎修改跨 6+ 接力棒)

## 現象(含硬證據)

引擎程式碼同時存在三份可被 import 的副本,session 內至少 4 次因版本漂移浪費整棒工作或誤導 RCA:

1. 三副本:host repo(bind mount 進容器)、容器 `/tmp/engpatch/bodesign_eda_bridge/`(PYTHONPATH 最前)、容器 `/app/packages/eda-bridge`(site-packages)。
2. stale 事故 #1:product RCA 棒發現 engpatch composer 缺 `power_ports` 參數(07:18 舊版)→ `gen_product_v2` 拋 TypeError → label compose 從未執行 → 殘留 draftsman 短路檔被誤判為「compose 成功但未落盤」,整棒結論跑偏。
3. stale 事故 #2:all_label 驗證棒同步 engpatch 後仍報簽名不符——`__pycache__` 未清,舊 bytecode 繼續生效。
4. stale 事故 #3:同棒誤判 `label_nets` 是 `compose_schematic` 簽名參數(實為 emit 層參數),因三處版本不一致無法用「單一事實」排除臆測。
5. **資料損失事故(最嚴重)**:引擎重構棒失敗後執行 `git checkout -- kicad_emit.py` 意圖回退自己的改動,但工作區含 6 棒未 commit 的成果(HEAD 33797 bytes vs 工作版 61972 bytes)——power_ports/satellite-snap/power-symbol/四輪防疊全部被抹掉。靠容器 engpatch 恰好留有 09:22 副本才復原,純屬僥倖。

## RCA

- 部署層:沒有單一部署動作。「改 host → docker cp → 清 pycache → 驗證 import 簽名」是四個手工步驟,每個接力棒自己做、各做一半;bind mount 與 engpatch overlay 並存讓「哪份在生效」變成每棒都要重新考古的問題。
- 資料安全層:多棒連續修改同一未 commit 檔案,無 snapshot 機制;subagent 在挫敗狀態下的 `git checkout` 是可預期的行為(它以為在回退「自己的」改動),但 blast radius 是全部前棒成果。工作流層面沒有「引擎改動前先快照」的硬規。

## 建議修復

1. **單一部署 verb(必做)**:提供 `scripts/sync_engine.sh`(或 gate verb):host → 容器 engpatch + site-packages 一鍵同步、強制清 `__pycache__`、末尾用 `python3 -c "import inspect; ..."` 印出實際生效簽名/版本戳。接力棒禁止手工 docker cp。
2. **版本戳**:`bodesign_eda_bridge/__init__.py` 加 `__engine_rev__`(內容 hash 或遞增戳),compose 輸出時印出,讓「哪份在生效」一眼可證。
3. **engpatch overlay 退場評估**:bind mount 已即時反映 host,engpatch 的存在只剩歷史原因;若容器內 PYTHONPATH 可直接指 bind mount 路徑,砍掉 engpatch 消滅一個漂移源。
4. **引擎改動快照硬規(工作流)**:任何棒改引擎前先 `tar -C packages/eda-bridge -cf $XDG_RUNTIME_DIR/.../engine_snap_<ts>.tar bodesign_eda_bridge`;git 操作(checkout/reset)對未 commit 引擎檔一律禁止,寫入 subagent dispatch 模板紅線。

## 影響範圍

- 容器映像 build(engpatch 機制)、`packages/eda-bridge/` 全部
- 所有委派 coding subagent 修引擎的工作流(dispatch 模板)

## 驗證手段

- sync verb 跑完後,三處 `grep -c <sentinel>` 一致 + import 簽名一致 + pycache mtime 晚於源檔。
- 版本戳:compose stdout 印 `engine_rev`,與 host 檔案 hash 對得上。
- 快照:模擬 git checkout 誤操作後,能從最近 snapshot 完整還原(演練一次)。

## Resolution (2026-07-06)

1. **單一部署 verb**：`scripts/sync_engine.sh` 已收編（同 session 先行落地）並在本次修訂——engpatch 改為 assert-absent（fail-loud），僅驗證 `/app/packages`（host bind mount，唯一合法副本）的 `__engine_rev__` + live signature。
2. **版本戳**：`bodesign_eda_bridge/__init__.py __engine_rev__`（core 檔案 content-hash）；`bodesign_compose_schematic` MCP 結果回 `engine_rev`（本次接線，先前文件宣稱但 handler 未透傳）。
3. **engpatch 退場（已執行）**：實測 server 行程 PYTHONPATH 從未包含 /tmp/engpatch——它只是 session workaround、純漂移源；已 `rm -rf` 並由 sync_engine.sh 防再生。dev 模式 bind mount 即時反映 host 修改，「部署」= restart + verify。
4. **快照硬規**：SKILL.md「Delivery contract」rule 5（tar snapshot + 禁 git checkout/reset/stash 於未 commit 引擎檔）+ rule 6（交接物標準化：engine_rev 戳/改動摘要/QA baseline）。

驗證：sync_engine.sh 實跑 `SYNC OK rev=640dc1f8bb74`，signature 含 power_ports+fidelity；engpatch GONE。
