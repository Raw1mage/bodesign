# Spec: capability_refs-derived-design

## Purpose

bodesign C00~C04 生成 verb 必須從「憑空生成 artifact」翻轉為「refs-derived 設計」：任何下游生成前，各層資料必須先逆向拆解 owner 權威來源並落 `01_refs/` SSOT；缺 SSOT 或無法追溯來源錨點時，下游 verb **fail-fast 拒絕執行**，不以預設值/第一可用值/泛用模型靜默續跑。此 spec 保證每個交付的座標/腳位/元件都可追溯 SSOT，SSOT 可追溯 owner 權威來源（PDF/PPTX）。

## Requirements

### Requirement: refs-first gate 強制化

系統 SHALL 在任何 C00~C04 生成 verb 執行前檢查對應各層 `01_refs/` SSOT 存在且可追溯 owner 來源錨點；不滿足時 SHALL 回傳 typed error（含缺項清單），SHALL NOT 以任何 fallback 續跑。

#### Scenario: 缺 SSOT 時 fail-fast

- **WHEN** 下游生成 verb 被呼叫但對應層 `01_refs/` SSOT 不存在或無來源錨點
- **THEN** verb 回傳 typed error + 缺項清單，不產出任何 artifact

#### Scenario: SSOT 齊備時放行

- **WHEN** 各層 `01_refs/` SSOT 存在且每筆資料帶可追溯 owner 錨點
- **THEN** 生成 verb 正常執行，產物每項可回溯至 SSOT

### Requirement: 約束驅動生成不發明上游決策

系統 SHALL 讓下游 stage 的生成 verb 以上游凍結約束 JSON（C01 face-layout、C02 envelope、mechanical-constraint）為必要輸入；連接器面向/邊緣 SHALL 綁定上游約束，SHALL NOT 由 C04 自由發明。

#### Scenario: 缺上游約束時拒絕

- **WHEN** placement/castellated verb 被呼叫但上游凍結約束 JSON 缺失
- **THEN** verb fail-fast 拒絕，不產出憑空 placement

#### Scenario: 連接器綁定上游面向

- **WHEN** placement 引擎消費 C01 face-layout（USB-C=BOTTOM 等）
- **THEN** 連接器擺放於指定面/邊，C04 無法移動（USB 可正確插入）

### Requirement: DoD 檢查涵蓋 refs 回溯

系統 SHALL 在交付驗證時檢查每個座標/腳位/元件可追溯 SSOT→來源錨點，而非僅檢查表面存在性/state；有憑空發明項時 SHALL 阻擋交付。

#### Scenario: 憑空發明版被 DoD 擋

- **WHEN** 交付物含 SSOT 無法追溯的元件/腳位（如漏 WiFi/BT/PHY/IMU）
- **THEN** DoD gate 回傳 BLOCKING + 不可追溯項清單

## Acceptance Checks

- [ ] refs-gate：缺 SSOT → typed error + 缺項清單；齊備 → 放行（單元測試）
- [ ] 約束驅動：缺上游約束 → 拒絕；有 C01 face-layout → 連接器面向正確
- [ ] castellated/stamp 原生 verb 不需徒手 pcbnew scripting（無 segfault）
- [ ] DoD refs 回溯：aiguard 憑空版被擋、refs-derived 版通過
- [ ] 全鏈回歸：aiguard 5 SSOT → 全鏈無憑空發明，每數字可追溯 owner 來源
