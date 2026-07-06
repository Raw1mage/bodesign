---
slug: failure-mode/deploy/multi-copy-engine-drift
title: 引擎多副本部署漂移(host/engpatch/site-packages)+ 未 commit 工作區被 git checkout 摧毀
layer: ragbase
type: failure-mode
confidence: verified
---
# 引擎多副本部署漂移(host/engpatch/site-packages)+ 未 commit 工作區被 git checkout 摧毀

**症狀**:同一引擎三份可 import 副本(host bind mount、容器 /tmp/engpatch PYTHONPATH 最前、/app site-packages),session 內 4 次事故:stale composer 缺參數致 TypeError 誤導 RCA、docker cp 後 __pycache__ 未清致舊 bytecode 生效、簽名歸屬誤判(label_nets 是 emit 層參數非 compose 簽名)、subagent 挫敗下 git checkout 抹掉 6 棒未 commit 成果(靠 engpatch 副本僥倖復原,HEAD 33797B vs 工作版 61972B)。

**通則**:(1) 多副本可 import 環境必須有單一部署動作 + 版本戳(__engine_rev__),否則「哪份在生效」變成每次考古;(2) 同步後必清 pycache 並用 inspect 驗證實際 import 簽名;(3) 多 agent 連續修改未 commit 檔案時,任何 git 回退操作是可預期的災難——改動前強制快照、dispatch 紅線禁 git checkout/reset。

見 BR_20260706_engine_multi_copy_deploy_drift.md。

## Source evidence

- `distilled_from` → [[extract/issues/assets/20260706/c03/session/readme/md|text: issues/assets_20260706_c03_session/README.md]] @ issues/assets_20260706_c03_session/README.md — source_weight 7

## Related

- → `references` [[issue/engine-multi-copy-deploy-drift|BR: 引擎三副本部署漂移(host/engpatch/site-packages)+ 未 commit 工作區被 subagent git checkout 摧毀]]

