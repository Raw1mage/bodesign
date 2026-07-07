# Symbol 覆蓋率報告 — aiguard C03 BOM（task 1.1）

日期：2026-07-07　來源：`01.openmv/C03-EE` C03_BOM.csv（36 rows → 28 distinct MPN）

## 總覽

- **覆蓋率：1/28（3.6%）** — 誠實見底，無硬配
- gap 成因：unresolved_mpn（BOM 料號未定案 TBC/佔位）× 21、no_official_symbol × 5、low_confidence × 1
- 註：CSV 內 1 列註解/非料號列已過濾，不計分母

## Gate 裁決（2026-07-07，task 1.2 stop gate）

使用者裁定：**批次 disposition + 放行 Phase 1 引擎**。disposition 已回填 `symbol_gaps.json`：

| disposition | 筆數 | 處置 |
|---|---|---|
| `vendor_cad` | 1 | U1 STM32N657——task 1.2a 已解（LCSC C42457345 原廠 CAD，ballout 222/222） |
| `defer` | 21 | TBC/佔位料——BOM 成熟度問題非 symbol 問題，交 C03 定料工作並行 |
| `pending-defer` | 5 | 真缺 official symbol（J_CAM/J3/U_S/LENS/U_EE）——Phase 2 前以 vendor_cad/manual/substitute 解 |

**不擋引擎開發的理由**：task 1.5 只需「MCU + 連接器 + 被動群」三張代表圖，不需全 BOM 解完；STM32N657 已有真 symbol，連接器/被動可用官方庫通用件。

## Resolved（需人工確認 substitute）

| MPN | lib_id | refs | 備註 |
|---|---|---|---|
| BQ25890 | `Battery_Management:BQ25895RTW` | U9 | BQ25895≠BQ25890，家族近似命中，**需人工確認**是否可代用 |

## Gaps（disposition 全部 pending，交使用者裁決）

| MPN | 成因 | refs | 說明 |
|---|---|---|---|
| STM32N657L0Q3 | low_confidence | U1 | 最接近的官方 symbol 為 MCU_ST_STM32C0:STM32C011D6Yx（共同前綴僅 5 字），低於門檻不自動採用，交人工確認 substitute |
| FFC 22P 0.5mm same-side | no_official_symbol | J_CAM | 官方 symbol 庫查無此料號家族 |
| 2.54mm | no_official_symbol | J3 | 官方 symbol 庫查無此料號家族 |
| IMX335 | no_official_symbol | U_S | 官方 symbol 庫查無此料號家族 |
| M12 2.8mm F2.0 | no_official_symbol | LENS | 官方 symbol 庫查無此料號家族 |
| I2C EEPROM | no_official_symbol | U_EE | 官方 symbol 庫查無此料號家族 |
| APS512 class (TBC) | unresolved_mpn | U2 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| MX25UM family (TBC) | unresolved_mpn | U3 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| external SMPS (TBC) | unresolved_mpn | U5 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| MIC5365 (TBC) | unresolved_mpn | U7 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| TCR2LE33 (TBC) | unresolved_mpn | U8 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| castellated half-hole (low-speed sig/pwr only) | unresolved_mpn | J_X1,J_X2 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| USB-C 2.0 waterproof (TBC) | unresolved_mpn | J1 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| LM66200 (TBC) | unresolved_mpn | U10 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| LM66100 (TBC) | unresolved_mpn | U11 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| 18650 holder | unresolved_mpn | BT1 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| EMIF02-4CMX8 (TBC) | unresolved_mpn | U12 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| microSD push-push (TBC) | unresolved_mpn | J_SD | BOM MPN 為未定案/佔位料號，無可解析對象 |
| UNDECIDED (deck S8 open item) | unresolved_mpn | U4 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| PCB/chip/IPEX (TBC) | unresolved_mpn | ANT1 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| OLED+CTP (TBC) | unresolved_mpn | DS1 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| PDM mic (TBC) | unresolved_mpn | MIC1 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| LSM6DSM class (TBC) | unresolved_mpn | U_IMU | BOM MPN 為未定案/佔位料號，無可解析對象 |
| RGB LED (TBC) | unresolved_mpn | D1 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| tact + gasket (TBC) | unresolved_mpn | SW1 | BOM MPN 為未定案/佔位料號，無可解析對象 |
| various | unresolved_mpn | C*/R* | BOM MPN 為未定案/佔位料號，無可解析對象 |
| 2.54mm headers/test points | unresolved_mpn | J_BRK | BOM MPN 為未定案/佔位料號，無可解析對象 |

## 裁決選項（每筆 gap 擇一）

- **vendor_cad**：取原廠/第三方 CAD symbol（ST 官方 CAD、SnapEDA/UL 等），入庫走 provenance 記錄
- **manual**：依 datasheet 手工繪 symbol（四邊 pin 慣例），一次性成本高但可控
- **substitute**：換成官方庫有 symbol 的等效料（動 BOM，需 C03 層面核可）
- **defer**：BOM 未定案者（TBC/UNDECIDED）先定料再解 symbol——**22 筆 unresolved_mpn 屬此類，是 BOM 成熟度問題而非 symbol 問題**
