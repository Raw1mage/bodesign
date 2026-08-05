# BR_20260723b — power_ports=False 未真正抑制 power-port 幾何 + stub-orientation defect

- **Status**: open
- **Filed by**: aiguard C03 consumer session (ses_073a93d09ffeRTpR9TwIdofhb3)
- **Repo**: bodesign (platform)
- **Severity**: medium — 純視覺 layout defect(不影響 net 連通),但擋住預設 emit
- **Fix venue**: bodesign-rooted session (platform owner，上輪已預告可接)

## Symptom (verbatim)

symbol_dirs 三個 bug 修完後(kiutils + a7fe826 + 080b454 + consumer 側 stage_dir base64 修正),
aiguard MCU core spec 的 52 元件(1 STM32 + 51 stdlib Device)**全部 resolve**,compose
前進到 emit 的 power-port 幾何階段才失敗:

```
ValueError: POWER_PORT_INSIDE_SYMBOL_BODY: power-port endpoints fell inside a
component symbol body (stub orientation defect — BR left-pin stub blind):
73 個 +1V8/GND/+3V3 power-port 端點落在 U1 symbol body 內
```

**關鍵**:consumer 傳的是 `power_ports=False`,引擎**仍執行** power-port 端點放置幾何並在
落入 U1 body 時 raise。

## RCA（consumer 側觀察 + platform 上輪自承）

1. **`power_ports=False` 未真正 bypass**(新發現,比「只在 True 出現」更嚴重):
   `kicad_emit.py:1377/1390/1417/1433/1461` 有 `kind = _power_net_kind(net.name) if power_ports else None`
   ——看似 False 時 kind=None,但 power-port 端點的**幾何放置 + intrusion 檢查**(1645 `if _port_intrusions`)
   似乎不受 `power_ports` 條件保護,仍在 False 下執行並 raise。請 platform owner 確認:
   `power_ports=False` 時是否應**完全跳過** power-port 端點放置與 `_port_intrusions` 檢查?

2. **stub-orientation defect（根本 defect）**:
   `kicad_emit.py:1647` 註解 "stub orientation defect — BR left-pin stub blind"。
   power-port 端點的 stub 方向使端點落在相鄰 U1 body 內。這是 BR_20260710 已知的純視覺 defect。

## 影響範圍

- 這是 **BR_20260710** 明確定義的**純視覺 layout defect**(power-port glyph 畫在 symbol body 上),
  `kicad_emit.py:1654-1662` 註解自承 **不影響 net 連通性**。
- 因此 `power_port_gate="warn"` 可讓乾淨電氣 spec 仍 emit(consumer 本輪即採此降級路徑產圖)。
- 但預設 `power_port_gate="error"` + `power_ports=False` **仍撞** raise,是不一致的行為契約。

## Fix proposal（platform owner 定奪，二選一或都做）

1. **`power_ports=False` 應完全抑制 power-port 幾何**:False 時跳過端點放置 + `_port_intrusions`
   檢查,讓 dense/connector 頁不受 power-port defect 影響(subagent 觀察此路徑未被保護)。
2. **修 stub-orientation defect**（根治）:讓 power-port 端點的 stub 方向使端點落在 U1 body **外**,
   則 `power_ports=True` 也能乾淨 emit 含 power-port 符號的完整電路。

## Validation plan

修後用 aiguard MCU core spec(存 `/run/user/1000/mcu-core-compose/`)重跑:
- `power_ports=False` → 不再撞 POWER_PORT_INSIDE_SYMBOL_BODY,乾淨 emit
- (root fix 後)`power_ports=True` → power-port 端點落 U1 body 外,73 個 intrusion 歸零
- placed:194、nets:18、可 render .kicad_sch

## Explicitly NOT bugs

- symbol_dirs 三個 bug — 已全修(b96263f / a7fe826 / 080b454),與本 bug 無關。
- consumer stage_dir @FILE 語法 — consumer 側已用 base64 修正,非引擎 bug。
- 本 defect **不影響 net 連通**(BR_20260710 自承),故 `power_port_gate="warn"` 是有效臨時繞道。
