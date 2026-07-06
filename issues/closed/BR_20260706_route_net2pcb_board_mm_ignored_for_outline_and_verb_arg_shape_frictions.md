# BR: route_net2pcb 的 board_mm 不畫板框(pad-extent 自動框勝出)+ 多 verb 參數形狀摩擦 batch

日期:2026-07-06
來源:aiguard C00→C04 refs-derived 重跑(consumer session)

## 現象(含硬證據)

### 1. board_mm 只餵 preplace,板框仍由 pad-extent 自動生成
- `route_net2pcb(strategy="deterministic", board_mm=[130,65])` 產出的 `.kicad_pcb`,Edge.Cuts 板框是 **pad extents + 3mm margin**(routing.py L228-240),不是 130×65。
- 實測:板 bbox = `22.235,1.925 → 107.765,65.615`(85.5×63.7),BT1(18650 holder,pad span ~79mm)被錨在板緣 → `copper_edge_clearance` HARD FAIL ×2(pad 離 Edge.Cuts 0.0mm)。
- deterministic preplace 用 board_mm 算 SA 邊界,但出板時丟棄 → 語義分裂:同一參數半生效。
- Workaround(不該存在):手動 pcbnew 重繪 Edge.Cuts 至 130×65 後 DRC 過(0/0/0)。
- **建議修復**:`board_mm` 給定時,Edge.Cuts 直接畫該尺寸(0,0)-(W,H);pad-extent 自動框僅在 board_mm 缺席時使用。preplace 的 R_edge 檢查與出板板框必須同源。

### 2. pour_planes 之後 zone thermal relief 產生 starved_thermal
- `pour_planes(["B.Cu:GND"])` 預設 thermal relief;PTH pad(PinHeader GND)4 spokes 連到 isolated island → `starved_thermal` error,gate 不 clean。
- Workaround:手動 `SetPadConnection(ZONE_CONNECTION_FULL)` + refill 後 clean。
- 建議:pour_planes 增加 `pad_connection="thermal|solid"` 參數(或對 plane-net pad 預設 solid),避免每次手術。

### 3. 參數形狀試錯 batch(每項都是一次 fail-fast 往返)
| verb | 期望形狀 | 我方第一直覺(失敗) |
|---|---|---|
| `compose_schematic` components | `symbol: "Lib:Part"` | `lib` + `part` 分欄 → **silent skip**(`component #N missing ref/symbol; skipped` 但 ok=true、ERC 0 violations 假綠) |
| `pour_planes` planes | `"LAYER:NET"`(如 `B.Cu:GND`) | `{"net","layer"}` dict / `"NET:LAYER"` → schema error / `AttributeError: pcbnew has no attribute 'GND'`(錯誤訊息誤導) |
| `c04_castellation` spec | `pad_height_mm` | `pad_length_mm` |
| `c04_dod_traceback` items | `{ref, provenance}` | `{item, ssot_ref, note}` → 全部 `<unnamed>` untraceable |
| `reference_crosscheck` nets | `{name: [nodes]}` dict | `[{name, nodes}]` list → `TypeError: unhashable type` |
- **compose 的 silent-skip 最危險**:13 元件全 skip 仍回 `ok:true` + `validated, 0 violations`(空 schematic 當然零違規)→ 假綠。建議:components 非空但 placed=0 時 fail-fast。
- 其餘建議:gate.py `--help` 對這些 verb 印 arg contract(比照 specbase producer.ts);pour_planes 的 spec 解析錯誤訊息應說「expected LAYER:NET」而不是拿 NET 名去 getattr(pcbnew)。

## 影響範圍
C04 全鏈 rerun 的每個 verb 至少一次參數往返;consumer 無法只憑 SKILL.md/GUIDE 一次呼叫成功。

## 驗證手段
aiguard rerun 產物:`03.aiguard/C04-Layout/02_build/rerun_refs_derived/aiguard_power_frontend_rerun_finished.kicad_pcb`(手動板框重繪+solid zone 後 DRC 0/0/0);drc_f2/f3/f4.json 為各階段證據。

## Resolution (2026-07-06)

全數修復（同日，coding subagent + orchestrator 驗證）：

1. **board_mm 板框**：`routing.py net2pcb_board` — `board_mm` 給定時 Edge.Cuts 直接畫 (0,0)-(W,H)（任何 strategy），pad-extent 自動框僅在缺席時使用；回傳 `outline_source: "board_mm"|"pad_extent"`。preplace R_edge 與出板板框同源。
2. **pour_planes**：新增 `pad_connection="thermal"|"solid"`（solid → `ZONE_CONNECTION_FULL`，消 starved_thermal）；`_parse_plane_spec` 防呆——冒號數/空欄/非 pcbnew layer 一律 `POUR_PLANES_BAD_SPEC: expected "LAYER:NET"...`，在 getattr 前擋掉誤導性 AttributeError。
3. **compose silent-skip**：`composer.py` — 全 skip → raise `COMPOSE_ALL_COMPONENTS_SKIPPED`（列每筆原因）；部分 skip warning 帶正確形狀提示 `symbol: "Lib:Part"`。
4. **server.py**：`pad_connection` 透傳 + schema 說明；`route_net2pcb` description 補 board_mm 語義。
5. 其餘參數形狀摩擦（c04_castellation/c04_dod_traceback/reference_crosscheck）：由 schema description 補強承接；gate.py `--list` 已列 required_args。

驗證：52 tests OK（含新增 ComposeSkipContractTests + PourPlanesSpecTests）。
