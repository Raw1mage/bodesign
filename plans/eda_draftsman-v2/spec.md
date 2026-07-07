# Spec: eda_draftsman-v2

## Purpose

保證 bodesign 能從真 MPN BOM + refs 保真 netlist 產出**通過人工審圖品質**的 KiCad schematic：symbol 幾何一律取自 KiCad 官方/原廠庫（四邊 pin），周邊接線件零疊字，整頁面積利用率可機檢；缺資料一律誠實標缺口（no-fallback）。

## Requirements

### Requirement: Official-symbol resolution（官方 symbol 解析）

系統 SHALL 對 BOM 中每個 MPN 解析對應的 KiCad 官方/原廠 symbol；查無對應者 SHALL 記入缺口清單並中止該元件的圖面生成，不得程式生成替代幾何。

#### Scenario: MPN 有官方 symbol

- **WHEN** BOM 元件的 MPN 在官方 symbol 庫命中
- **THEN** 直接載入該 symbol（含四邊 pin 幾何），v2 不修改 symbol 本體

#### Scenario: MPN 無官方 symbol

- **WHEN** MPN 查無官方/原廠 symbol
- **THEN** 記入 `symbol_gaps` 缺口清單（含 MPN、封裝、pin 數），輸出報告交使用者裁決；不生成替代

### Requirement: Single pinout block（單一 pinout 圖，Phase 1）

系統 SHALL 以官方 symbol 為中心產出可獨立渲染/驗收的單一 pinout 圖：周邊接線件（電源符號、net label、no-connect、去耦群）之文字與圖形 bbox SHALL 互不相交、且不與 symbol 本體/wire 相交。

#### Scenario: 單圖機檢通過

- **WHEN** 單圖 emit 後經 kicad-cli render → render_qa text-bbox 閘 + fidelity 連通分量閘
- **THEN** 兩閘全綠才標記該單圖為「已驗收積木」

#### Scenario: 單圖機檢失敗

- **WHEN** 任一閘 FAIL
- **THEN** 回幾何修正；同一缺陷連續兩輪未收斂 SHALL 停手做 RCA（禁疊補丁）

### Requirement: Sheet composition（排頁，Phase 2）

系統 SHALL 只在 Phase 1 人工驗收通過後，將已驗收單圖作為**不可變積木**排入圖紙；排頁 SHALL 做面積規劃使 ink_metrics 利用率 ≥ 門檻（暫訂 55%），且不得修改積木內部幾何。

#### Scenario: 排頁利用率不足

- **WHEN** 整頁 render 後 ink_metrics 利用率 < 門檻
- **THEN** 排頁 FAIL，調整擺放/分頁，不進人工審閱

#### Scenario: 頁間連線

- **WHEN** 兩積木間存在共用 net
- **THEN** 以 hierarchical/global label 表達，label 擺放同樣受 text-bbox 閘約束

### Requirement: Emit via kiutils（禁手搓 sexp）

系統 SHALL 經 kiutils dataclass 物件層讀寫 .kicad_sym / .kicad_sch；SHALL NOT 以字串拼接生成 S-expression。

#### Scenario: roundtrip 驗證

- **WHEN** kiutils 寫出任一 .kicad_sch
- **THEN** kicad-cli 可無錯開啟並渲染（roundtrip 為 CI 回歸測試）

## Acceptance Checks

- [ ] aiguard C03 全 BOM symbol 覆蓋率報告產出，缺口清單經使用者裁決
- [ ] 任選 3 個代表元件（MCU/連接器/被動群）單圖通過雙機檢閘 + 使用者人工抽查（Phase 1 gate）
- [ ] CCM 5 頁以 v2 重產：雙閘全綠 + 利用率 ≥ 門檻 + 使用者審閱 gate 通過
- [ ] 三份幾何 BR（left_pin_stub / two_side_only / no_sheet_fill）閉環移至 issues/closed/
- [ ] 舊 kicad_emit.py / composer.py / kicad_symbol.py 移除，`__init__.py` 三 export 換新且其餘 re-export 不變（test_eda_bridge / test_companion_render 仍綠）
