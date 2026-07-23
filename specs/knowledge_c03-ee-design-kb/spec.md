# Spec: knowledge_c03-ee-design-kb

> Profile: docs. 本 spec 描述兩張 BR 合併後的可驗收 invariant（BR_A 檢索/內容 + BR_B passive-completeness gate）。守 bodesign 哲學：gate 是校驗非合成。

## Purpose

保證 C03 EE 設計知識**可被 cold-context agent 用自然多詞句撈到**（修 FTS AND 假陰性 + 補少數未 ingest 主題），並保證 composer 產出的圖過 gate 前**必經 passive-completeness 校驗**——active IC 零必要被動件不得靜默 PASS。

## Requirements

### Requirement: kb_query 多詞可發現性（BR_A Fix1）

`bodesign_kb_query` 對多詞英文 query SHALL 以 OR-ranked（命中任一詞、bm25 排序）召回，而非 implicit-AND；精確 AND SHALL 保留為 opt-in `mode=all`；payload SHALL 自描述實際 matchMode。

#### Scenario: 多詞情境句撈到在庫物件

- **WHEN** agent 下多詞 query `crystal oscillator load capacitor`
- **THEN** 在庫物件 `control.si.crystal-oscillator-layout`（body 含 "load cap"）SHALL 命中（目前回 0 = 假陰性）
- **AND** 既有單詞 query（`decoupling`/`fuse derating`/`crystal`）命中集 SHALL NOT 退化

### Requirement: C03 設計主題 KB 覆蓋（BR_A Fix2）

regulator 拓撲選型、SI 需求數值、I²C-SPI pull-up/termination sizing 三主題 SHALL 以 graded `control.*` 存在且可 `kb_query` 命中，每筆帶來源錨點；無來源主題 SHALL 標 UNVERIFIED，不臆造。

#### Scenario: 真缺主題 ingest 後可查

- **WHEN** ingest 完成且 A1 檢索已修，下 `LDO buck boost topology selection` / `signal integrity termination` / `I2C pull-up`
- **THEN** 各 SHALL 命中對應新 control，provenance lineage 錨到來源 prose

### Requirement: passive-completeness gate（BR_B，校驗非合成）

帶 power pin 的 active IC 若攜零去耦——且依 pin class 攜零必要 pull/termination/load cap——SHALL 判 HARD FAIL 或顯式 provenance-carrying waiver，不得靜默 PASS。gate SHALL 是 `pinout-to-circuit-method.md` 9-class obligation 表對已組出的圖的機器投影，SHALL NOT 代 LLM 決定要哪些件。

#### Scenario: pinout-only 板被攔、honest-subset 帶 waiver 放行

- **WHEN** 對 pinout-only schematic（active IC + power pins + 零被動件）跑 gate
- **THEN** SHALL FAIL 並列 `passive_gaps[]`/`PC-001`（ref + pin + class + missing-obligation）
- **AND WHEN** 對 honest interface-subset（`Netlist_Status.md` 宣告 documented gap + waiver）跑 gate
- **THEN** SHALL PASS 且 waiver 被記錄（no-silent-fallback）

## Acceptance Checks

- [ ] `test_kb_tools.py` 多詞召回綠 + 單詞不退化 + `mode=all` 保留
- [ ] `LDO buck boost topology selection`/`signal integrity termination`/`I2C pull-up` 各命中新 control
- [ ] pinout-only fixture→FAIL、properly-decoupled→PASS、honest-subset+waiver→PASS(記錄)
- [ ] aiguard `02_mcu_core` 加去耦前後 FAIL→PASS；`test_composer.py`/`test_check_c03.py` 綠
