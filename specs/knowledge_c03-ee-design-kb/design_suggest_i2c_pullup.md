# 方案 C 第一切片設計：I2C pull-up「有據建議」生成器

> plan: knowledge_c03-ee-design-kb 延伸（軌 C，合成層方案 C）
> 來源：BR_20260723c 方案 C（consumer 洞見）+ 使用者優先序裁決「電路設計能力層提為主攻」
> 守哲學鐵律：引擎**建議**非**決定**；標 evidence；**不自動改 spec**；人 review 後才 commit。

## 為什麼是 I2C pull-up（不是去耦）

A3.5 坐實：consumer aiguard MCU core spec 的 **U1 去耦已齊**（+1V8/GND/VDDA cascade 完整），但
**SHARED_I2C 缺 pull-up**：
- `SHARED_I2C_SCL`: 1 node = `U1.P2`（只有 MCU 一端，零 pull-up）
- `SHARED_I2C_SDA`: 1 node = `U1.R1`（同上）

這正是 KB 規則 `control.sch.pullup-termination-sizing` 明列的 common error「missing pull-ups
entirely (bus floats)」。所以 I2C pull-up 是這個 spec 的**真缺口**，是 demo「從 intent 生電路」的
黃金標的——去耦建議器對此 spec 無東西可建議（U1 已完備）。

## 能力邊界（守哲學，釘死）

這是「**有據建議**」（suggested-with-evidence），**不是合成決定**：

| 做 | 不做（跨紅線） |
|---|---|
| 依 KB graded 規則算 Rp 範圍、選 typical 值 | 替人拍板「就用這個值」直接寫進 spec |
| 輸出 draft 建議（標 `suggested`/`draft`） | 輸出被宣稱已驗證的設計 |
| 每個建議帶 evidence source（KB 規則錨點） | 無據臆造值 |
| 產出 `suggested_passives.json` 供人 review | 自動 mutate 輸入 spec |
| 人接受後由 consumer/人補進 spec | 引擎 commit |

## 輸入 / 輸出契約

**輸入**（intent，非 concrete topology）：
```json
{
  "bus": "SHARED_I2C",
  "scl_net": "SHARED_I2C_SCL",
  "sda_net": "SHARED_I2C_SDA",
  "pull_rail": "+1V8",          // 由現有 spec 的 VDD 推得或 intent 指定
  "speed_hz": 400000,           // intent：bus 速度
  "bus_capacitance_pf": 150,    // intent 或估算（device 數 × ~10pF + trace）
  "device_count": 4             // intent：N-device 開漏
}
```

**輸出**（draft 建議，人 review）：
```json
{
  "status": "suggested",        // 永不 "committed"
  "bus": "SHARED_I2C",
  "suggestions": [
    {
      "component": {"type": "resistor", "value": "2.2k",
                    "net_from": "SHARED_I2C_SCL", "net_to": "+1V8"},
      "rationale": "Rp for SCL pull-up",
      "computed": {"rp_min_ohm": 486, "rp_max_ohm": 3934, "chosen": "2.2k",
                   "basis": "typical for 400kHz fast mode; within [Rp_min, Rp_max]"},
      "evidence": {
        "kb_object": "control.sch.pullup-termination-sizing",
        "formula": "Rp_min=(VCC-VOL)/IOL, Rp_max=tr/(0.8473*Cb)",
        "provenance": "I2C-bus spec NXP UM10204 (bus-spec grade)",
        "confidence": "partial"
      }
    },
    { "...SDA 同上..." }
  ],
  "review_required": true,
  "note": "Draft suggestion — NOT applied to spec. Human review + commit required."
}
```

## 計算邏輯（依 KB 規則，非硬編）

1. `Rp_min = (VCC - VOL) / IOL`，VOL=0.4V, IOL=3mA（standard），VCC=pull_rail 電壓
2. `Rp_max = tr / (0.8473 * Cb)`，tr 依 speed（standard 1000ns / fast 300ns），Cb=bus_capacitance
3. `chosen` = KB typical 值中落在 [Rp_min, Rp_max] 且符合 speed 的那個（400kHz→2.2k / 100kHz→4.7k）
4. 若 typical 值超出 [Rp_min, Rp_max] → 標 warning「no typical value fits; compute exact」，不硬塞

## 落點（seam）

- 新模組 `packages/eda-bridge/bodesign_eda_bridge/design_suggest.py`（or workflow-core）——
  **獨立於 composer**，不碰 compose_schematic 建 spec 的行為（BR_B 明文：忠實建 spec 是對的）。
- 純函式 `suggest_i2c_pullups(intent: dict) -> dict`——deterministic、無副作用、不寫檔。
- 呼叫方（consumer/人）拿到建議後**自己決定**是否補進 spec。

## 驗證

- 單元測試：SHARED_I2C intent（400kHz, 4-device）→ 建議 2.2k pull-up ×2、evidence 錨到 KB、
  status=suggested、review_required=true。
- 邊界：Cb 過大 → Rp_max < Rp_min → warning 不硬塞。
- 守哲學 assert：輸出永不含 `committed`；不 mutate 輸入；不寫任何檔。
- 用 consumer 真實 SHARED_I2C 缺口 demo：intent → 建議 → （人 review）→ 補進 spec → 缺口填實。

## 這對使用者痛點的意義

這是使用者要的「電路設計能力」的**最小可驗證切片**：引擎第一次能**從高層 intent 生出
concrete passive topology + 選值**（而非只校驗、或只渲染 consumer 手寫的 net）。守哲學——建議帶
evidence、人 commit——所以它是「有據的建議」不是「被宣稱的設計」，落在 honesty 紅線內。
