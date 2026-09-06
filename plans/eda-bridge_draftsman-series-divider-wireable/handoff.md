# Handoff: eda-bridge_draftsman-series-divider-wireable

## Execution Contract

執行者交付 `packages/eda-bridge/bodesign_eda_bridge/declare.py` 與其測試，
使 `tasks.md` Phase 1 的四條完成判準全綠：

```
declare_circuit(btdongle 分壓宣告).status == "ok"
產出的 spec 餵 compose_schematic 後，VBAT_SENSE 是 drawn 不是 label
該子電路 junction > 0
CONTROL：tap 改成等於 top => status == "rejected" 且 code == E_DIVIDER_TAP_DEGENERATE
```

**Done 的定義**：上面四格逐格貼出實際輸出（不是「測試通過」的轉述），
且 `errors.md` §Outcome Codomain 的五個狀態各自在測試中被觸發過至少一次。

**未完成即未完成**：若 Phase 1.8 的端到端因既有引擎缺陷（見 §Stop Gates）跑不出
`junction > 0`，**不得**調整判準來讓它綠，回報 blocked 並指名是哪一格擋住。

## Required Reads

執行前必讀，順序即依賴順序：

1. `plans/eda-bridge_draftsman-series-divider-wireable/{proposal,design,errors,spec}.md`
   —— 本包自己。`design.md` §Context 那段「與 KB 禁令的關係」**必讀**，
   否則會把本包誤實作成 netlist 合成器（那是被明文禁止的）。
2. `data-schema.json` + `test-vectors.json` —— I/O 契約與 14 個測試向量。
3. `issues/BR_20260905_draftsman_connection_strategy_degenerates_to_label_farm_on_non_label_friendly_topology.md`
   —— 特別是 **§8.5.2**（power clustering 修法為何失敗）與 **§8.5.5**（門檻的 scale 依賴：
   合成語料會給出假未達標，驗收一律用真 spec）。
4. `packages/eda-bridge/bodesign_eda_bridge/composer.py:1887`（`compose_schematic` 簽名）
   與 `:2181-2231`（現行 label/wire 判定）。**Phase 1-2 只讀不改。**
5. `AGENTS.md` §5（測試怎麼跑：`./scripts/run_tests.sh`，讀 `Ran N tests` 的 N 不是 rc）
   與 §6.1（共用工作樹紀律——這棵樹有多顆 session 並行且大量未 commit）。

## Stop Gates In Force

- **Phase 3 有硬前置，不得跳過**：`try_reserve` 目前 71 次嘗試 0 次成功
  （round 1 實測，`reserve_wire_conflict_kind_body 84 / pin_extent 58`），
  導致 ledger 的 wire 層恆空、wire-vs-wire 碰撞偵測是死的。
  在 `reserve_wire_ok > 0` 之前**不要動 `render` hint 接線**——
  `BR_20260905` §8.5.2 記載那條路會讓 fidelity `moved` 從 10 爆到 67。
- **不得為了讓判準變綠而關 fidelity gate**。`BR_20260905` §8.5.2 的教訓逐字：
  幾何判準（junction 數、短樁比例、子電路數）**全部大幅達標的同時把 net 接錯**，
  而擋住它的唯一一格就是 fidelity。**格式綠燈不授權任何電氣正確性宣稱。**
- **真板 fidelity 在本包範圍內不會轉綠**（`BR_20260905` §8.5.4）：
  HEAD 在 btdongle 上本來就 `moved=10`，signature 屬於另外兩張 BR
  （multi-unit 壓平 + VBUS/CC 熔合）。不要試圖在本包內讓它 PASS。
  本包的幾何數字在真板上一律是 fidelity OFF 下量的，**且必須明講這一點**。
- **commit 授權在 dispatcher**。改完、跑完測試、停在未提交狀態。

## Execution-Ready Checklist

- [ ] `.state.json` 的 `profile` 目前是 `[]`（空）。推 `designed` 之前需
      `plan_set_profile`，否則 gate 會要求全套 artifact 而本包的
      `idef0.json` / `grafcet.json` 仍是 scaffold。**這格由 dispatcher 裁決**，
      執行者不得自行改 `.state.json` 逃 gate（`BR_20260628`）。
- [ ] 確認 `./scripts/run_tests.sh test_declare_circuit` 可跑（新測試檔尚不存在時
      預期 `Ran 1 test / FAILED (errors=1)`——**那是模組沒載入的外觀，不是回歸**）
- [ ] 確認 btdongle 真 spec 可取：
      `/home/pkcs12/products/thesmart_products/04.btdongle/C03-EE/02_build/sch_gen/design.py`
      （**注意有 `sch_gen/` 一層**，少這層會 rc=1 而「查錯路徑」與「檔案不存在」共用同一個輸出）
- [ ] 開工前先做工作錨定（`AGENTS.md` §6.1 的 `refs/wip/<session-id>` 配方），
      並逐檔 `git show <ref>:<path>` 驗過——**「ref 建好了」不等於「內容在裡面」**

## Round 1 診斷的可用產出（下一輪要用）

- `generated/sch_bodesign/btdongle.kicad_sch`（消費端 repo，未 commit）——
  HEAD 引擎跑真 spec 的產物，wire=116 / junction=6 / short=71.6% / power glyph=61。
  **這是 Phase 1 的 before 基線。**
- `mk_sch_bodesign.py` 現在是可跑的（`style=draftsman validate=True fidelity=True` 通過）。
- 插樁副本在 `$XDG_RUNTIME_DIR/schdiag/pkg2/`（scratch，非 repo）——
  若要重量 router 呼叫/降級計數可直接重跑 `run_instr.py`。

## Open Questions for Dispatcher

1. **verb 命名**：`bodesign_declare_circuit` 是否可用？（`design.md` 全篇用這個名字）
2. **落點**：`declare.py` 放 `eda-bridge` 還是 `workflow-core`？
   它是純函式零依賴，兩邊都合理；我傾向 `eda-bridge`，因為它的輸出契約綁著 `composer.py`。
3. **profile**：本包要 `software` 全套（需補 IDEF0/GRAFCET）還是 `docs`？
   目前 `idef0.json` / `grafcet.json` 仍是 scaffold，這決定它們要不要畫。
