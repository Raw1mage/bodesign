# Errors: eda_schematic-draftsman-quality

> 每個錯誤：code / 觸發條件 / 使用者可見訊息 / 回復策略 / 責任層。對齊 repo no-silent-fallback 天條。

## Error Catalogue

## E-DRAFT-001 SYMBOL_LOAD_FAILED（WARN，非阻塞）
- **觸發**：spec component 的 symbol（lib_id）載入失敗。
- **訊息**：`<ref>: symbol '<lib_id>' load failed: <reason>`（沿用既有 warnings）。
- **回復**：該件不參與 force-directed（fail-visible，DD-4），列入 warnings；不以預設尺寸/預設 symbol 靜默替代。
- **責任層**：`_estimate_bbox` / `load_symbol`（phase 2.1）。

## E-DRAFT-002 NET_UNRESOLVED_PIN（WARN，非阻塞）
- **觸發**：net 節點 `REF.PIN` 無法解析（ref 不存在 / pin 不存在）。
- **訊息**：`unresolved pin: <ref>.<pin>`（沿用既有 unresolved_pins）。
- **回復**：該 net 退回 global-label（route_stats.label_fallback_reasons reason=unresolved），不靜默丟棄。
- **責任層**：`emit_kicad_schematic`（既有）+ composer 統計（phase 3.2）。

## E-DRAFT-003 CLUSTERING_DEGENERATE（WARN，非阻塞）
- **觸發**：net-degree clustering 在 star 拓撲退化成單一大群（R4）。
- **訊息**：`net-degree clustering produced a single dominant cluster (hub degree=<n>); consider declaring groups`。
- **回復**：對高 degree hub 做 degree-capping 切分；仍無法分群則維持單群 + warning，不阻斷產出。
- **責任層**：`_cluster`（phase 2.2）。

## E-DRAFT-004 PLACEMENT_OVERLAP_UNRESOLVED（WARN，非阻塞）
- **觸發**：force-directed 收斂後仍有 symbol bbox 重疊。
- **訊息**：`<n> component pairs still overlap after refinement; applied deterministic gutter re-spacing`。
- **回復**：確定性 gutter 重排兜底（非隨機，R1）；仍重疊則 warning，不隨機抖動。
- **責任層**：`_refine`（phase 2.4）。

## E-DRAFT-005 SHEET_OVERFLOW（WARN，非阻塞）
- **觸發**：內容 bbox 超過最大標準頁（A0）。
- **訊息**：`content exceeds largest standard sheet; consider splitting into multiple sheets`。
- **回復**：選最大頁 + warning，**不靜默裁切**（DD-5）；建議拆 sheet。
- **責任層**：`_fit_sheet`（phase 3.3）。

## E-DRAFT-006 INK_TOOLCHAIN_ABSENT（INFO，非阻塞）
- **觸發**：缺 pdftoppm / poppler / PIL。
- **訊息**：`ink measurement unavailable (missing: <list>); schematic delivered, metric skipped`。
- **回復**：`ink_metrics.available=false` + missing_tools，不偽造度量（DD-6 天條）。schematic 正常交付。
- **責任層**：`ink_metrics.py`（phase 4.2）。

## Non-fallback invariants

- 預設 `style="netlist"` **不得**因新功能被靜默改成 draftsman（DD-3，使用者決策）。
- force-directed **不得**引入 RNG 來「繞過」收斂問題（確定性鐵律）。
- ink toolchain 缺失**不得**回傳估算/捏造數字假裝有度量。
- symbol 載入失敗**不得**塞預設尺寸讓 placement「看起來成功」。
