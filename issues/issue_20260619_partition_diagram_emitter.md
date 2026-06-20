# BR / FR: bodesign 缺「介面分割 / 模組 breakout 概念圖」emitter(C03/C04)

- **Date**: 2026-06-19
- **Reporter**: TheSmartAI (orchestrator)
- **Target**: bodesign 維護者(tool surface + bodesign skill)
- **Type**: feature request / capability gap(非 bug)
- **Severity**: medium —— 任務可完成,但只能繞過 bodesign 手做,且重做性差
- **Origin task**: aiguard C00 PRD 需要 CCM(核心板)/ECB(擴充載板)模組安排的 breakout 圖示。

---

## 1. 一句話

bodesign 把「核心板/載板分割 + board-to-board pin classes」當成 **第一級 C03 交付物**(`C03_核心板模組ICD.md`、`bodesign_c03_export_mechanical_constraints`),卻**沒有任何工具能把這份結構化資料畫成概念分割圖**。使用者要這張圖時,只能離開 bodesign、手寫腳本、再手刻 docxmcp ops —— 即便 bodesign 自己已具備所有必要零件。

---

## 2. 觀察到的 gap(以本次任務為證據)

需求:把 `C03_核心板模組ICD.md` §2/§3/§4 的內容(CCM 7 模組 / ECB 6 模組 / 10 條 pin-class 互連 + 方向)畫成一張可交付的「breakout 方塊圖」。

盤點 bodesign 現有工具後,**沒有一個對應概念分割/介面圖**:
- `c01_emit_id_visual_package` → ID 機構外觀分層 SVG(非電氣分割)
- `emit_layout` / `route_net2pcb` → 實體 PCB placement(需 netlist、是真佈局非示意)
- `render_companion` / `render_board_model` → 渲染既有 EDA/3D 檔(不從 ICD 生圖)
- `c03_export_mechanical_constraints` → 匯出跨層**資料**,但不畫圖

結論:概念方塊圖被 bodesign 設計成「外包給 drawmiat C4 或手做」。但這次使用者明確排除 C4 語意(C4 是軟體容器圖,不適合表達電氣板級分割 + pin-class fan-out),於是只剩「手做」一條路。

---

## 3. 為何這是 bodesign 該補的(不是 drawmiat / docxmcp)

1. **資料源頭在 bodesign**:CCM/ECB 分割與 pin classes 是 `C03_核心板模組ICD.md` 的核心,bodesign 已有 `c03_export_mechanical_constraints` 把這類跨層資料結構化。畫圖只是把已有資料投影成圖形。
2. **bodesign 已有「diagram emitter」先例**:`c01_emit_id_visual_package` 就是「吃結構化設計意圖 → 吐分層可編輯 SVG」。本請求是它在 C03/C04 電氣域的對應物。
3. **bodesign 已能驅動 docxmcp**:`bodesign_mcp_call(server="docxmcp", tool="pptx_edit", ...)` + `bodesign_stage_dir` 已存在。要產出「可編輯 PPTX」版本,bodesign 內部就能 orchestrate,使用者完全不必碰 docxmcp 的 add_shape ops 細節(那層細節摩擦另見 docxmcp BR：issue_20260619_docxmcp_pptx_addshape_friction.md)。

換句話說:**零件齊全,只缺一個 emitter 入口把它們串起來。**

---

## 4. 提議

### R1(主)：新增 `bodesign_c03_emit_partition_diagram`(或 c04 命名)

- **輸入**:core/carrier 分割 + interconnect pin classes。優先直接讀 `C03_核心板模組ICD.md` 的結構化區塊;或吃 `c03_export_mechanical_constraints` 的輸出;或吃顯式 JSON(`{boards:[{name,role,tier,modules:[...]}], interconnect:[{class,signals,dir}]}`)。
- **輸出**:
  - 分層 SVG + PNG(比照 `c01_emit_id_visual_package` 的分層可編輯模式)
  - **可選** editable PPTX —— bodesign 內部用 `mcp_call → docxmcp` 產生原生可編輯 shape,使用者不接觸 ops。
- **honest-boundary 內建**:圖上自動標註「design partition, not fab pinout / no RefDes.Pin→net / no DRC-SI claim」——這正是 bodesign 的誠實模型,emitter 應預設帶上,而非靠使用者手寫 footer。

### R2：資料/繪圖分離,emitter 吃 MODEL

本次手做的生成器已驗證這個形狀可行:純資料 dict(boards + pin classes)→ 繪圖函式 → ops/SVG。建議 emitter 內部就採此結構,MODEL 即工具參數,方便日後加 board 數(>2 板)或換主題。

### R3：bodesign skill 補一段「概念圖路由」

skill 目前沒講「使用者要分割/介面/breakout 概念圖時走哪」。建議補:
- 電氣板級分割 / pin-class fan-out → `c03_emit_partition_diagram`(本請求)
- 機構外觀 / 模組艙排列 → `c01_emit_id_visual_package`
- 實體元件落點 → `emit_layout`
- 軟體容器/系統架構 → drawmiat C4
明確區分這四類,避免每次都要使用者與 agent 重新判斷「這張圖該用什麼工具」。

---

## 5. 影響 / 價值

- C00–C07 lifecycle 裡,「板級分割確認」是早凍結項(ICD 要早凍結)。一張**從 ICD 自動生成、且隨 ICD 更新可重生**的分割圖,直接服務這個 milestone。
- 目前手做版本的致命缺點是**重做性差**:ICD 一改,圖要全手工重畫。emitter 化後,圖變成 ICD 的可重生投影,符合 bodesign「spec 是產品、圖是衍生」的精神。

---

## 6. 現況(本次手做交付,作為 emitter 的參考實作)

- 交付物:`03.aiguard/C00-PRD/C00_CCM_ECB模組Breakout.pptx`(90 原生可編輯 shape,lint ready:true)
- 參考實作:`03.aiguard/C00-PRD/02_build/tools/gen_breakout.py`(SVG/PNG)、`gen_breakout_pptx.py`(資料→docxmcp ops)—— 資料/繪圖已分離,可作為 `c03_emit_partition_diagram` 的演算法藍本。
- 相關 docxmcp 摩擦 BR:`issues/issue_20260619_docxmcp_pptx_addshape_friction.md`(若 bodesign emitter 內部走 mcp_call,可一併規避該層摩擦,讓使用者完全無感)。
