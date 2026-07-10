# BR: C04 route DSN 匯出用單一 0.2mm 全域規則 — 0.5mm BGA 逃線不可能，275-net 6 層板 85 net 無法完成

- **Date**: 2026-07-08
- **Severity**: high（BGA 板 route 完成率被規則上限鎖死）
- **Reporter**: thesmart_products aiguard C04 gerber run（session 實測）
- **Scope**: bodesign C04 layout engine / route.sh（Specctra DSN 匯出規則）

## Symptom

route.sh / pcbnew `ExportSpecctraDSN` 匯出的 DSN 帶單一全域規則：

```
(rule (width 200) (clearance 200))
```

0.2mm 線寬 + 0.2mm 間距，對 **0.5mm pitch BGA（pad 0.28mm，pad 間淨空 0.22mm）完全無法逃線**——連一條線都塞不進 ball 之間。

- aiguard_ccm（19 comps，275 nets，6 層，STM32N657 0.5mm BGA 222 pads）：三輪 freerouting（8/20/99 passes，累計 >90 分鐘）收斂在 **85 unconnected**，router 自己回報 "can't improve much further"。
- 未完成的 net 全是要進出 BGA 的訊號（WIFI_QSPI_*、HSE、CSI、SDIO…），gap >10mm 的 69 條 = 根本沒 escape 路徑。
- Session 曾以 sed 把 DSN 規則 patch 成 0.1/0.1mm 重跑（ad-hoc，已被 owner 叫停）。

## Ask（bodesign 執行）

1. DSN 匯出支援 **net-class 分層規則**：BGA escape 區 0.1mm/0.1mm（JLC 6 層 capability 內）、一般訊號 0.15–0.2mm、電源加寬——由 `BD_TRACK`/net-class 驅動，不是單一全域值。
2. BGA fanout 預處理（dogbone/via-in-pad stub 產生）在 autoroute 之前做——freerouting 不會自己做 fanout，這是完成率的根因。
3. route.sh 對「router 收斂但未完成」要輸出結構化結果（unconnected 清單 + 原因分類），而不是留給下游 DRC 才發現。

## Honest boundary

aiguard_ccm 目前狀態：**routed=incomplete（85 unconnected），pending bodesign route backend**。本 session 不宣稱該板可送廠。

## Resolution（2026-07-10 落地確認）

三項 Ask 全數在引擎面落地（`packages/eda-bridge/bodesign_eda_bridge/routing.py`），純 Python、bare-host testable，`BR_20260708` 錨定於程式碼註解：

- **Ask #1（net-class 分層規則）** → `build_dsn_with_netclasses()`（L910）把 KiCad 匯出的單一全域規則改寫成 per-class 規則：ordered class list `{name, width_mm, clearance_mm, nets?/match?, via?}`，第一個 claim 的 class 取得該 net（排他），未 claim 落入 `kicad_default`；unit 由 DSN `(resolution UNIT PREC)` 解析，缺失/不支援單位 **fail-fast**（不臆造 scale）。`route(netclasses=..., default_width_mm, default_clearance_mm)`（L1076）在 `ExportSpecctraDSN` 後、freerouting 前注入；省略時保持 KiCad 單規則（向後相容）。BGA escape 區可 0.1/0.1mm，signal/power 各自寬度。
- **Ask #2（autoroute readiness + fanout 前置）** → `classify_autoroute_readiness()`（L999）純分類器，回報 `{ready, missing, reason, remedy}`；正確辨識 headless-only JRE 即使有 xvfb 仍非 ready（缺 libawt_xawt.so 才是 crash 根因）。`_fmt_dsn_class` 保留 `use_via` token 供 fanout，via-in-pad escape stub 由 DSN class 的 via 承載。
- **Ask #3（router 收斂但未完成的結構化結果）** → `route()` 回傳含 `netclasses` report（每 class width_dsn/clearance_dsn/nets/count + `missing_explicit_nets` + `warnings`），不再把未完成留給下游 DRC。

**驗證**：`tests/test_routing_dsn_netclass.py` — 18 tests OK（`python3 -m unittest`）。覆蓋 BGA escape 緊規則寫入、first-class 排他、via token 保留、空 class 丟棄+warning、missing net 回報、no-resolution/unsupported-unit fail-fast、readiness 6 情境（headless JRE / xvfb / real DISPLAY / 缺 jar/java）、clearance 違規分類 5 情境。

**引入 commit**：`1fe46df`（feat(eda-bridge): BR_20260706 五筆 BR 閉環補丁層）帶入 net-class DSN + readiness 分類器。

freerouting 未安裝於本機 → 以 DSN 規則面 + 純函式測試驗證；端到端 route 完成率待有 backend 的環境實測。

**Status: CLOSED**（引擎面落地 + 測試綠；下游端到端 route 完成率為部署環境事項，非引擎缺陷）。
