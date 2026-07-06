# BR(方法論): 產品交付 session 內做引擎 R&D 的反模式——收斂預算、能力分流、QA 前置三缺失

日期:2026-07-06
來源:thesmart_products aiguard C03 v03 schematic 交付 session 全程復盤
層級:workflow / skill(bodesign SKILL.md + GUIDE 交付契約),非單一程式缺陷

## 現象(含硬證據)

使用者的需求是「C03 正式 schematic 交付物 + placement 圖供審」。實際執行變成:**~3.5 小時、15+ 個 coding 接力棒 + 3 個 review 棒的引擎研發馬拉松**,交付物至今未出(CCM 電氣 PASS 但文字殘 29 violations;product 板分頁中斷)。逐層列舉:

1. 疊字問題連續 4 輪「修復→聲稱 QA 過→視覺 FAIL」,沒有停損 gate;第 4 輪引擎重構棒明知「越過收斂臨界」仍硬推,regression 到比初始更糟(29→173),最後誤 git checkout 險毀全部成果。
2. 短路問題三次(GND 141 / BAT_SENSE 177 / +3V3_PB 189),每次都是「修好一處、重產又冒一處」——因為根因(collinear fusion)在引擎層,session 卻在呼叫層逐案打地鼠。
3. 兩棒並行共享引擎所有權(重構棒 + product RCA 棒),重構棒回退 engpatch 直接把 RCA 棒的環境抽掉,RCA 棒整棒結論跑偏。
4. 每棒重新考古上下文(三副本哪份生效、哪個 QA 可信、前棒改了什麼),接力交接成本佔比極高。

## RCA

1. **能力缺口分流缺失(最根本)**:任務開工時未做 capability triage。bodesign draftsman/emit 當時不具備「產業級多頁 schematic 排版」能力——這是引擎級能力缺口,正確處置是開 bodesign repo 的 plan 走完整 R&D 生命週期(spec→design→tasks→驗證),產品 session 用現有能力交付並誠實標註限制。實際卻在產品 session 內用接力棒現場磨引擎,把「交付 deadline 壓力」和「引擎品質工程」綁在同一條線上,兩頭都輸。
2. **收斂預算缺失**:同類缺陷第 2 輪修復失敗就該觸發「停手、升層重新定性」;實際跑了 4 輪,每輪都相信「再修一點就收斂」。缺一條硬規:**同類問題 2 輪不收斂 → 停止迭代,root-cause 升層(呼叫層→emit 層→placement 層→方法論層)再議**。
3. **QA 前置缺失**:「渲染層 QA(SVG text bbox + fresh-eyes)才是交付判準」是第 3 輪才建立的;若開工就定義交付層 QA 閘(先寫 QA、跑 baseline、再修),前兩輪的假收斂根本不會發生。這正是 pptx skill「第一次 render 幾乎一定有問題、必用 subagent fresh-eyes」契約的 schematic 對應物——bodesign skill 缺這一章。
4. **資源所有權缺失**:引擎(共享可變狀態)同時交給兩棒,經典 race。缺「引擎單一持有權:同一時間至多一棒可寫引擎」的 dispatch 紀律。

## 建議修復(寫入 bodesign SKILL.md / GUIDE)

1. **Capability triage gate(開工必做)**:C0x 交付任務開工時列「交付需要的引擎能力 vs 現有能力」清單;缺口若預估 >2 輪引擎修改才能補,**強制分流**——在 bodesign repo 開 plan 做引擎 R&D,產品 session 以現有能力出「誠實限制版」交付物給 user 先審方向(本 session 的正確路徑:CCM 5 頁電氣 PASS + 已知疊字清單,先交 user 看架構對不對,排版問題入 plan 慢修)。
2. **2 輪收斂停損硬規**:同一類缺陷連續 2 輪修復未收斂 → 禁止第 3 輪同層迭代;必須升層定性(工具→方法論)並回報 user 裁決。寫入 skill 的交付契約。
3. **交付層 QA 先行**:任何「生成→渲染」類交付,第一步先定義並實作渲染層機器 QA(如 SVG text bbox 掃描)+ 跑 baseline,才允許開始修復迭代。「模型層 QA 過」永遠不得作為呈現層完成宣告依據。
4. **引擎單一持有權**:並行棒的檔案範圍必須不相交;引擎目錄同一時間至多一棒可寫,orchestrator dispatch 時顯式聲明持有權。
5. **接力棒交接物標準化**:引擎改動棒必交「engine_rev 戳 + 改動摘要 + QA baseline 數字」,下一棒開工先驗戳,消滅考古成本。

## 影響範圍

- `skills/bodesign/SKILL.md` + `stages/c03-ee/GUIDE.md`、`stages/c04-layout/GUIDE.md`(交付契約章節)
- orchestrator 的 subagent dispatch 模板(所有權聲明、快照紅線、交接物)
- 本次未完成的 aiguard C03 交付(復工時按新方法論走)

## 驗證手段

- 下一個 C0x 交付任務按新契約走:開工有 triage 記錄、QA 閘先於修復存在、無同層第 3 輪迭代、引擎改動有單一持有權與 engine_rev 交接——以 event log 可稽核。
- bodesign skill 文件 diff 審閱通過。

## Resolution (2026-07-06)

五條硬規全數寫入 `skills/bodesign/SKILL.md`「Delivery contract — hard rules for generate→render deliverables」：

1. Capability-triage gate（>2 輪引擎改動 → 強制分流開 plan，交付 session 出誠實限制版）
2. 2 輪收斂停損（同類缺陷 2 輪不收斂禁第 3 輪同層迭代，升層 + 回報 user）
3. 交付層 QA 先行（render-layer 機器閘 + baseline 先於任何修復迭代；模型層 QA 過 ≠ 呈現層完成）
4. 引擎單一持有權（同時至多一棒可寫引擎，dispatch 顯式聲明）
5. 引擎快照 + 禁 git rollback（tar snapshot；git checkout/reset/stash 於未 commit 引擎檔為紅線）
6. 接力棒交接物標準化（engine_rev 戳 + 改動摘要 + QA baseline；下一棒先驗戳）

c03-ee GUIDE done-criteria 補三閘：fidelity gate PASS、render-layer text QA violation=0、fresh-eyes 視覺 QA 一輪。
引擎能力缺口本體已分流：spec `specs/eda_schematic-draftsman-quality` extend（DD-8..DD-11）走完整生命週期。
驗證手段（下一個 C0x 交付按新契約走、event log 可稽核）留待實戰檢核。
