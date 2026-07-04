# Spec: quality_verify-checker-skillification

## Purpose

本 spec 定義「把 ragbase verify-knowledge control 物件技能化成可執行 checker」的方法契約：每個 control 依可執行性分三層（T-A machine-checkable / T-B artifact-gap / T-C advisory），T-A 產出零 LLM、fail-fast、control-grounded 的 `ValidationEvidence`，T-B 掛帳為 parser/IR backlog 不硬編假欄位，T-C 注入 G2 design-review。守住 bodesign 四天條（確定性、no-silent-fallback、datasheet-grounded、no-fabrication）。

## Requirements

### Requirement: Executability tiering is objective and no-fabrication-safe

系統 SHALL 依三條客觀判準（confidence=verified、有量化門檻、門檻量可從 IR 或現成 parser 讀到）將每個 control 分入 T-A/T-B/T-C，且任何 confidence=partial/todo 的 control SHALL 一律歸 T-C，不得成為確定性硬 gate。

#### Scenario: partial control cannot become a hard gate

- **WHEN** 一個 control 有明確數值門檻但 confidence=partial
- **THEN** 它被歸為 T-C advisory，不產出硬 gate checker，直到知識升 verified 才可重分類

### Requirement: T-A checkers are deterministic and control-grounded

系統 SHALL 讓每個 T-A checker 為純 python、零 LLM、同輸入 byte-identical 輸出、缺 IR 欄位時 fail-fast 附缺項清單；其輸出 SHALL 是既有 `ValidationEvidence` 封套並攜帶 `control_id` + `source_anchor` + `threshold_provenance`。

#### Scenario: checker verdict traces back to datasheet source

- **WHEN** 一個 T-A checker 對設計判 fail
- **THEN** 產出的 ValidationEvidence 帶 control_id 與該 control 的逐字來源錨點，verdict 可回溯到 datasheet/標準

### Requirement: Thresholds are read from knowledge, not hard-coded

系統 SHALL 讓 T-A checker 執行期從 ragbase control 的 machine-readable threshold block 讀門檻值，而非在 code 硬編，使知識門檻更新時 checker 自動跟隨。

#### Scenario: knowledge update propagates without code change

- **WHEN** 一個 control 的 threshold block 門檻值被更新
- **THEN** 對應 checker 下次執行即採用新門檻，無需改 checker code

## Acceptance Checks

- [ ] 57 個 control 全數分入 T-A/T-B/T-C，partial/todo 全在 T-C（`control-classification.md` 可稽核）
- [ ] 三個試點各驗證一條路徑（擴充既有 checker / 全新 IR-native / T-B 掛帳）
- [ ] T-A checker 輸出通過 `ValidationEvidence.__post_init__`（tool 在 ORACLE_TOOLS）且帶 control_id + source_anchor
- [ ] threshold block 解析層讓門檻更新不需改 checker code
- [ ] IDEF0 + GRAFCET 經 drawmiat validate 通過
