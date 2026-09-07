# Spec: eda-bridge_multi-sheet-subsystem-schematics

## Purpose

保證 bodesign 能把一份電路 spec 產出成 **1 個 root `.kicad_sch` + N 個葉 `.kicad_sch`** 的
hierarchical schematic：元件依功能子系統嚴格 partition 到葉紙，跨紙連接以同名 `global_label`
建立，且該連通性經 `kicad-cli` netlist 實測確認，不以「原語存在」推定。
單張輸出（N=1）的既有行為必須 byte-stable。

## Requirements

### Requirement: Multi-file schematic emission

系統 SHALL 在給定 sheet 分派時產出 1 個 root 檔與 N 個葉檔，且 `files` 清單只列磁碟上
真實存在的檔（repo 天條 §2.2 No fabrication）。

#### Scenario: N 個子系統產出 N+1 個檔

- **WHEN** spec 宣告 3 個子系統分派
- **THEN** 輸出目錄含 1 個 root 與 3 個葉 `.kicad_sch`，且 `files` 恰列這 4 個檔

#### Scenario: N=1 時 byte-stable

- **WHEN** spec 未宣告任何分派（或只有一個子系統）
- **THEN** 輸出與 HEAD 現行單檔路徑逐字相同（`WIRE_GEOM_SHA` 不變）

### Requirement: Root sheet block

root 檔 SHALL 為每個葉檔寫出一個 KiCad 9 合法的 `(sheet …)` block，欄位取自真板 root 逐欄抄錄。

#### Scenario: root 可被 kicad-cli 開啟

- **WHEN** root + N 葉產出後執行 `kicad-cli sch export netlist`
- **THEN** 匯出成功，且 netlist 涵蓋全部 N 張葉紙的元件

### Requirement: Strict component partition

元件→sheet SHALL 是嚴格 partition：每顆元件恰好出現在一張葉紙上。
重複或遺漏 SHALL fail-fast 並列出違例 ref，不得靜默丟進「其他」那一張
（repo 天條 §2.1 No silent fallback）。

#### Scenario: 未分派元件 fail-fast

- **WHEN** spec 中有元件不屬於任何已宣告子系統
- **THEN** 拋出具名錯誤並列出該 ref 清單；不產出任何檔

### Requirement: Cross-sheet connectivity by global_label

跨紙 net SHALL 在其跨到的每一張葉紙上放置**同名** `global_label`，
且 SHALL NOT 引入 `hierarchical_label`。

#### Scenario: 同名跨檔連通（treatment）

- **WHEN** root + 2 葉，兩葉各有 1 個同名 `global_label`
- **THEN** `kicad-cli` 匯出的 netlist 中兩端落在**同一條** net

#### Scenario: 不同名不連通（control）

- **WHEN** 同一份輸出改成兩個**不同名** `global_label`
- **THEN** 兩端落在**兩條不同** net

### Requirement: Sheet-aware policy scope

三條繪圖政策（cross-IC / power-rail / high-fanout）的判定範圍 SHALL 可設定為
「單張 sheet 內」而非「整張圖」。**政策本身不放寬**——K8 已測得放寬政策在多 sheet
形狀下交叉數仍達單張紙的 80%，`M6-8d` 存活。

#### Scenario: 判定範圍降到 sheet 層級

- **WHEN** 一條 net 的節點全部落在同一張葉紙上
- **THEN** 該 net 的政策判定只考慮該葉紙上的節點，不考慮其他紙上的同名 IC 對

## Acceptance Checks

- [ ] AC-1 三子系統輸入產出恰 4 個檔，`files` 與磁碟逐一相符
- [ ] AC-2 N=1 輸入的 `WIRE_GEOM_SHA` 與 HEAD 逐字相同
- [ ] AC-3 未分派元件觸發 fail-fast 並列出 ref（負向控制：全部分派時不觸發）
- [ ] AC-4 跨檔 global_label 實驗：treatment 同 net、control 兩 net，**兩格都做**
- [ ] AC-5 五組子系統各自成為一張可獨立閱讀的葉紙
- [ ] AC-6 既有 153 個測試模組無 NEW RED（逐 test-id 比對，不看總數）
