# BR: draftsman drawn-wire 無障礙迴避 → 全頁被迫 label-only,交付圖淪為單晶片 pinout

- **Date**: 2026-07-08
- **Severity**: high(阻塞 aiguard C03 審圖 gate——user 明確判 v10 不合格)
- **Reporter**: aiguard C03 交付 session
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/composer.py`(`_bus_route` / `_orthogonal_route`)

## 症狀(user 原話)

> 「v10圖根本沒有畫出正常的跨晶片電路連結原理,都是單晶片pinout」

CCM 七頁(v10)每頁 = 元件 symbol + 每 pin 掛 global label,**零跨件 drawn wire**。
01_power 頁 census:30 symbols / 78 wires(全為 pin 短 stub)/ 4 global_labels 型式主導連通。
電氣連通性(netlist 層)正確——FIDELITY PASS 0/0——但**圖面不呈現電路原理**,不符
業界原理圖慣例(局部子電路應畫實線:buck 的 L/C 迴路、crystal 迴路、decoupling、
2-node 點對點;label 僅用於跨頁/長距/bus)。

## 根因鏈

1. composer `style="draftsman"` 的 drawn-wire 連線由 `_bus_route`/`_orthogonal_route`
   實作,**走線無元件本體 keep-out(障礙迴避)**——同 net 的 daisy-chain 正交走線直接
   貫穿 symbol 本體。
2. 實測病灶(前輪 session):02/03 頁 ADQ5/6/7 走線穿過 U2 本體。
3. 止血法(gen_ccm_pages.py:695-703,現行狀態):全頁強制
   `_compose_common.update(connection_style="label")`,把 drawn-wire 全面退回
   label-only——止血把「走線穿件」修成「無走線」,矯枉過正。
4. 交付圖因此淪為 pinout 表,user 審圖 gate FAIL。

## 期望行為(修復驗收標準)

1. `_orthogonal_route` 支援元件本體 bbox 為 keep-out 障礙(含 pin-name 文字帶),
   走線繞行不貫穿。
2. 混合範式:2-node 短距 net(同頁、距離 < 閾值)畫實線;多節點(>=3)/跨頁/
   電源 rail 走 label(T3 既有裁決保留)。局部子電路(buck L/C、crystal、decap)
   必須實線成迴路。
3. 驗收:重產 aiguard CCM 01_power / 02_mcu_core,(a) 零走線貫穿元件本體
   (幾何檢查可機檢:wire segment ∩ symbol bbox = ∅ 除了自己 pin 的落點);
   (b) buck/crystal 子電路以實線閉合;(c) FIDELITY gate 仍 PASS。

## 現場資產

- 現行止血點:容器 `bodesign-pkcs12-bodesign-ee-1` `/work/aiguard/C03-EE/full_board/gen_ccm_pages.py:695-703`
- composer 範式判定:`composer.py:1570-1615`(style/connection_style 推導)
- v10 交付(label-only 現狀樣本):`thesmart_products/03.aiguard/C03-EE/CCM_*_v10.{svg,png}`
- 真值:同 repo `/work/.../full_board/gen_ccm.py`(31-row BOM 對齊版,U3=MX25UM51245G/U5=TPS62088/U8=TCR2LE33 已入)

## 邊界

- aiguard 交付 session 不做引擎 R&D(既定紀律);本 BR 等 bodesign 實作後,
  交付 session 重跑 gen_ccm_pages 產 v11 送審。
- 電氣真值(gen_ccm.py net 定義)不在本 BR 範圍——已對齊定案 BOM 且 FIDELITY PASS。

## 落地紀錄(2026-07-10)

### 根因(消費端實證確認)
`_orthogonal_route`/`_bus_route`(`kicad_emit.py`)只吃兩個 pin 端點、無障礙集合輸入,
所以短距 L 走線必然可能貫穿第三個 symbol 本體;唯一既有幾何守衛 `_guard_route`/
`_segment_fuses` 只檢查跨 net 共線熔合,從不查 symbol bbox。消費端因此被迫
`connection_style="label"` 全頁止血 → 七頁淪為 pinout。

### 改了什麼

**引擎 `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`**
- 新增 `WIRE_KEEPOUT_MM=1.27`(1 grid keep-out 環)。
- 新增 `_seg_hits_box()` / `_waypoints_clear()`:軸對齊線段 ∩ 障礙 bbox 內部判定
  (邊緣接觸=合法 pin 落點,不算貫穿)。
- `_orthogonal_route(p1,p2,obstacles=None)`:候選路徑(直線 / H-first / V-first /
  障礙聯集左右上下 detour channel)依序取第一條 interior 清空障礙者;端點恆保留
  (FIDELITY 安全)。無障礙時 byte-identical(直線/H-first)。
- `_bus_route(endpoints,obstacles=None)`:daisy-chain 每 hop 走障礙感知路由。
- `emit_kicad_schematic` 內建 per-ref 絕對 sheet body AABB(源自 symbol
  `(rectangle)`,同 guard C 真值),keep-out 膨脹後餵入路由;路由排除該 wire 自身
  host body(pin approach leg 允許貼自己本體)。
- 新增機檢:post-emit 收集每段 drawn wire × 非 host body 交集 → `wire_body_intrusions`
  (queryable,`SchematicEmitResult` / `ComposeResult` 皆帶),外加獨立 accessor
  `check_wire_body_clearance(result)`。
- 共線熔合防護沿用既有 `_guard_route`(未動,detour 後仍過該關)。

**`composer.py`**:`ComposeResult.wire_body_intrusions` 欄位 + 回傳串接。

**消費端 `/work/aiguard/C03-EE/full_board/gen_ccm_pages.py`**:移除
`:703 _compose_common.update(connection_style="label")` 全頁止血 → 改用 draftsman
混合預設(2-node→實線 wire / multi-node+電源 rail→label);dense castellated stamp
頁改在 spec 層設 `all_label=True`(共線 connector 欄無法安全走線)。

### 驗證數字(實跑)
- **機檢(合成回歸案:3 symbol 一列,2-node net 跨中間本體)**:`wire_body_intrusions=[]`、
  `wired_nets=1`(走線繞行、實線畫出、零本體貫穿)。
- **消費端回歸(7 頁重產,ee 容器)**:全頁 compose 成功,drawn wire 恢復——
  01_power wires=78 / 02_mcu=57 / 03a=82 / 03b=63 / 04_wireless=69(+labels),
  stamp 05a/05b wires=0(all_label,設計如此)。**不再是全 label pinout**。
- **FIDELITY gate**:`FIDELITY: PASS diff 0/0`(ssot_nets=111,signal_balls_lost=0,
  orphan_nodes=0)——電氣保真未退化。
- **單元測試**(`tests/test_composer_draftsman.py`,ee 容器 unittest):
  `test_br20260708_wire_avoids_symbol_body`、`test_br20260708_orthogonal_route_detours`
  皆 PASS。

### 邊界/未竟
- stamp 頁本就走 all_label(collinear connector 欄無法畫線),非本 BR 迴避範圍。
- product 板 +3V3_PB 189-pin 共線熔合案:本次未跑該板回歸(消費端另案),但同一
  anti-fusion + all_label 機制已在 stamp 頁生效。
