# Spec: quality_deterministic-preplacement

## Purpose

保證 bodesign C04 的 pre-placement 是電氣感知且確定性的：同一 netlist + 幾何 + seed 輸入必得同一擺件輸出；decap/被動元件依 pin 歸屬先驗貼近其服務對象；擺後以帶來源錨點的規則（R1/R8）產出可解釋違反清單，取代零感知的天真網格。

## Requirements

### Requirement: Deterministic reproducibility

系統 SHALL 在同一輸入（parts 幾何、nets、seed、規則參數）下產出 byte-identical 的 placement 結果與違反清單。

#### Scenario: Same input twice

- **WHEN** 以相同引數呼叫 preplace 兩次
- **THEN** 兩次回傳的 `{ref:(x,y,rot)}` 與 violations 完全相等

### Requirement: Electrically-aware placement

系統 SHALL 將 decap 依 pin 歸屬先驗擺放於其服務 IC 電源 pin 的 R1 距離內（幾何可行時），主 IC 錨定於板中心。

#### Scenario: LED driver baseline

- **WHEN** 對 16 零件 10 net LED driver 案以 `strategy=deterministic` 擺件
- **THEN** 100nF decap 距其 IC 電源 pin ≤3.0mm（R1），且 HPWL 低於 grid 基線

### Requirement: Explainable rule check

系統 SHALL 於擺後執行 R1/R8 檢查，每筆違反含 rule id、來源錨點、量測值、閾值。

#### Scenario: Violation reporting

- **WHEN** 某 decap 因板框限制無法滿足 R1
- **THEN** violations 列出 `{rule:"R1", source:"US7929315B2", measured_mm, limit_mm, refs}`，不靜默吞沒

### Requirement: No silent fallback

系統 SHALL 在 `strategy=deterministic` 缺必要幾何時 fail fast 並回報缺項清單，不退回 grid。

#### Scenario: Missing footprint geometry

- **WHEN** 某 ref 的 footprint 無法載入
- **THEN** 拋出含缺項 ref 清單的錯誤，不產生部分擺件板

## Acceptance Checks

- [ ] unit test：同輸入兩次執行結果相等（確定性）
- [ ] unit test：decap 歸屬分群正確（decap→電源 pin、crystal C→crystal pin）
- [ ] unit test：R1/R8 checker 對已知違反案例輸出帶錨點違反清單
- [ ] 基線對比：LED driver 案 deterministic vs grid，decap 距離與 HPWL 量化改善
- [ ] `strategy=grid` 行為與既有完全一致（回歸不破）
