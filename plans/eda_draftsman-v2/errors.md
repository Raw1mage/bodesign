# Errors: eda_draftsman-v2

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `SYMBOL_GAP` | MPN 查無官方/原廠 symbol（A1） | resolver 報告 + SymbolGap JSON | 記缺口清單，該元件停繪，交使用者裁決；禁 fallback 生成 |
| `PIN_MAP_MISMATCH` | 官方 symbol pin 與 refs netlist 對不上（A1/A3） | fail fast + pin diff 清單 | 人工核對 refs 資料 vs symbol 版本，不得靜默跳過 |
| `TEXT_BBOX_OVERLAP` | render_qa 疊字閘：文字 bbox 相交（A3/A5） | QA verdict overlaps[]（含座標） | 回 A2/A4 修擺放；同簽名 2 輪未收斂 → 停手 RCA |
| `CONNECTIVITY_DIVERGE` | fidelity 閘：連通分量與 refs netlist 不一致（A3/A5） | HARD FAIL + 分量 diff | 禁交付；查 wire/label 生成邏輯 |
| `ROUNDTRIP_FAIL` | kiutils 寫出的 sch 無法被 kicad-cli 開啟/渲染（A2） | kicad-cli 非零 exit + stderr | HARD FAIL；查 kiutils 版本/方言；禁手搓 sexp 繞過 |
| `UTILIZATION_LOW` | ink_metrics 利用率 < 0.55（A5） | 排頁 QA verdict + 數值 | 調 SheetPlan（分頁/擺放），不進人工審閱 |
| `IMMUTABLE_BLOCK_TOUCHED` | Phase 2 改動 validated 積木內部幾何（A4） | 程式 assert HARD FAIL | 違反 DD-3；修 composer，不得改積木遷就排頁 |
