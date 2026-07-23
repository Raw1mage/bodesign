# Tasks: knowledge_c03-ee-design-kb

> 兩張 BR 合併規劃，依賴序 A1→A2→A3。BR_A=`BR_20260723_kb_query_fts_and_false_negative_and_c03_content_gaps.md`；BR_B=`BR_20260723_c03_composer_accepts_pinout_only_no_passive_completeness_gate.md`。守哲學：A3 是校驗非合成。

## 1. A1 — kb_query 多詞可發現性修復（BR_A Fix1，檢索根因）

- [x] 1.1 先寫回歸：`tests/test_kb_tools.py` 加多詞召回案（`crystal oscillator load capacitor` 應命中 `control.si.crystal-oscillator-layout`；`regulator LDO buck decoupling` 應命中 decoupling/regulator control）+ 單詞不退化案（`decoupling`/`fuse derating`/`crystal` 命中集鎖定）
- [x] 1.2 改 `services/mcp/server.py` `_h_kb_query`：多詞英文 token → FTS5 per-token OR（`"t1" OR "t2"…`）、bm25 排序；AND 降為 opt-in `mode=all`；matchMode 如實回 `fts-or`/`fts-and`。**修真回歸：`_h_kb_query` 原本沒把 `mode` 傳給 `_kb_match_plan`，`mode=all` 被靜默放寬成 OR（DD-5 破裂）→ 已補傳**
- [x] 1.3 `BODESIGN_DEV=1 ./mcpctl.sh restart` 生效；`bodesign_kb_query("crystal oscillator load capacitor")` → matchMode `fts-or`、total 38、命中 `control.si.crystal-oscillator-layout` 排第一（BR_A 症狀 0→轉正）
- [x] 1.4 驗證：`test_kb_tools.py` 17 tests OK；單詞召回集不退化；`mode=all` 精確 AND 保留（`test_a1_mode_all_preserves_exact_and` 綠）；matchMode 自描述正確

## 2. A2 — ingest C03 真缺主題（BR_A Fix2，內容缺口）

- [x] 2.1 蒸餾 `control.power.regulator-topology-selection` ← `ee-design-advisory.md` §Power tree（LDO/buck/boost 適用+watch，confidence=partial source_weight=3）
- [x] 2.2 蒸餾 `control.si.interface-requirements` ← `ee-design-advisory.md` §SI（Z0/3W/λ10/termination 為 C03→C04 交付數值，partial/3）
- [x] 2.3 蒸餾 `control.sch.pullup-termination-sizing` ← `schematic-analysis.md` §I2C（`Rp_min=(VCC-VOL)/IOL`／`Rp_max=tr/(0.8473·Cb)` 公式，bus-spec grade source_weight=4）
- [x] 2.4 走 specbase `producer.ts`（ingest_source/register_asset/record_extract/distill/link）`--repo bodesign` ingest；3 條 `distilled_from` provenance lineage 錨到來源 prose extract
- [x] 2.5 驗證：`regulator topology LDO buck boost`→命中 regulator control；`signal integrity termination impedance`→命中 SI control；`I2C bus`→命中 pull-up control；confidence/source_weight 如實

## 3. A3 — passive-completeness gate（BR_B，校驗非合成）

- [x] 3.1 **gate policy 使用者裁決**：mandatory scope = decoupling-only HARD FAIL；unmet obligation + sidecar waiver（USER-adjudicated，DD-2）
- [x] 3.2 架構裁決 seam：`analyze_schematic` 的 `validate_passive_completeness(ctx)` detector（`validation_detectors.py`），merge 進 validation_findings（勝過 composer 無 ref/rail 知識、check_c03 只看 BOM 看不到 topology）
- [x] 3.3 實作 gate（commit `68bdde1`）：9-class obligation 表機器投影；active IC 零去耦 = HARD FAIL；複用 analyzer pin→net map / comp classifier / is_power_net / detect_decoupling rail walk
- [x] 3.4 honest-subset waiver：sidecar waiver 宣告 documented gap 通過（DD-4，no-silent-fallback）
- [x] 3.5 驗證：`tests/test_passive_completeness.py` 9 tests OK；真板 aiguard before/after FAIL→PASS 已驗（見 BRNS round-1 commit 68bdde1）

## 3b. B — evidence-backed 有據建議合成層（缺口 B，使用者拍板方案 C，DD-7/8/9）

> 新增 `packages/eda-bridge/bodesign_eda_bridge/design_suggest.py` 生成器族，三 pattern 同 `compute→anchor→draft→spec_fragment` 範式。驗證載體 = aiguard MCU core spec（consumer 24+ 回合 cowork 三方驗收）。守 DD-9 四條紅線（建議非決定/值算非猜/evidence 可港/人決策）。

- [x] B.1 I2C pull-up 生成器：`suggest_i2c_pullups(intent)` — Rp_min=(VCC-VOL)/IOL、Rp_max=tr/(0.8473·Cb)、選 typical（400kHz→2.2k），錂 NXP UM10204；output `status=suggested`+`spec_fragment`（R_SCL_PU/R_SDA_PU 兩顆 2.2k + net 連接）。consumer 逐項驗算通過（466.7Ω/2360Ω/2.2k 在窗內）
- [x] B.2 series-termination 生成器：`suggest_series_termination(intent)` — 長線>λ/10 才需 termination、microstrip Z0=(87/√(er+1.41))·ln(...)、series R=Z0 @ source；三輸入態（target_z0 直給 / stackup 假設算 / 都無→fail-loud pending-C04）；錂 `control.si.interface-requirements`，明標 C04 MUST confirm real trace width
- [x] B.3 crystal load-cap 生成器：`suggest_crystal_load_caps(intent)` — 雙模式 suggest（從無到有）/verify（核對已存在），C_load_each=2·(CL−Cstray)；錂 `control.si.crystal-oscillator-layout`（verified）+ form_note 明標「explicit closed form standard EE、非逐字錂 KB」（守 no-fabrication）
- [x] B.4 `spec_fragment` 契約增強（consumer round=7 要求）：suggestion 帶可直接貼進 spec 的 component/net fragment（ref hint + symbol + value + 兩端 net），讓「人 review→補進 spec」從手抄變 review-then-paste
- [x] B.5 驗證：`tests/test_design_suggest.py` 35/35 綁（I2C 13 + series + crystal）；consumer 三方驗收全通過（I2C 逐項算 + crystal verify CONSISTENT delta=0 + series 三態分支）；I2C 活體閉環 PoC（SHARED_I2C 訊號側 net node 1→2、+5 wire、真 symbol 進圖，見 BR_20260723c §4b）
- [x] B.6 守哲學邊界（BR_20260723d 附帶天條修復）：compose 對 active IC symbol-not-found 從靈默產空框→顯式 `SymbolLoadError`（No-silent-fallback）；tests/test_composer_draftsman.py 66/66；consumer U1 lib-name mismatch 實測 raise 通過

## 4. 收尾

- [x] 4.1 兩 BR 收尾 `event_record`（開場+多次收尾）；BR_B 已 ship（68bdde1）；BR_A A1+A2 本輪完成
- [x] 4.2 架構同步：A3 gate 已同步 `specs/architecture.md`（68bdde1 +5行 C03 段）；A1 `_h_kb_query` OR-ranked 檢索語義 + A2 三新 control → 本輪收尾同步 KB 段
- [x] 4.3 BRNS relay：BR_B（PC-001）已回報 sender（round-1，commit 68bdde1）
