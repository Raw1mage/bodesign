# 方案 C 第二切片設計：series-termination「有據建議」生成器

> plan: knowledge_c03-ee-design-kb 延伸（軌 C，合成層方案 C）
> 來源：consumer round=7 認同的 pattern 優先序（pull-up→**series-term**→crystal→去耦）
> 守哲學鐵律：引擎**建議**（suggested），不**決定**（committed）；值算不硬編、錨 evidence、人 review 後 commit
> 對齊：第一切片 `design_suggest.py::suggest_i2c_pullups` 的同範式（compute + anchor + draft + spec_fragment）

## 為什麼 series-term 比 pull-up 更能展示「有據」

pull-up 值是查典型表（2.2k/4.7k/10k），series-term 值**依物理量算**：source series R = Z0，而 Z0 依 stackup 幾何算。這更硬核地證明「引擎在做電路設計、不是查表」。aiguard 有 Flash/PSRAM/WiFi 三條高速匯流排（XSPI/QSPI）= 真缺口。

## 關鍵設計約束（SI KB 揭示，決定 intent 形狀）

`control.si.interface-requirements`（軌 A 已 ingest，locator ee-design-advisory.md §SI L89-107）明列：
1. **只有跨 λ/10 的 net 才需 termination**：trace 長度 > λ/10 @ knee freq（knee ≈ 0.35/t_r）。所以生成器**第一步是判斷該不該加**——短線不需 series R，硬加是錯的（誠實：回「no termination needed, sub-λ/10」不硬塞）。
2. **series R = Z0 at source（point-to-point）**：這是 C03 能算的部分。
3. **Z0 需要 stackup 幾何**：`Z0 ≈ (87/√(er+1.41))·ln(5.98H/(0.8W+T))`（microstrip），但 **H（stackup 高度）/W（走線寬度）是 C04 layout 階段的物理量**。KB 明文「C03 hand C04 the target Z0 + stackup height assumption, NOT a trace width」。

**結論——series-term 生成器的誠實形狀**：C03 階段能算 series R = target Z0，但 Z0 本身依賴 C04 才有的 W/H。所以：
- 若 intent 帶 **target_z0**（設計者已定阻抗目標，常見 50Ω single-ended / 100Ω diff）→ 直接建議 series R = Z0 @ source。
- 若 intent 帶 **stackup 假設（er, H, W）** → 用 microstrip 公式算 Z0 → series R = Z0，但標「Z0 derived from ASSUMED stackup; C04 must confirm with real W/H」。
- 若兩者都無 → **fail-loud 或標 pending-C04**，不猜 Z0（守天條 No silent fallback）。
- 長度判斷：若 intent 帶 trace 長度 + t_r → 算 λ/10 判斷該不該加；無長度 → 標「length unknown, assume needs termination if flagged high-speed by caller」不靜默略過。

## 落點

- 同模組 `packages/eda-bridge/bodesign_eda_bridge/design_suggest.py`（與 I2C 生成器並列，共用 evidence/範式）。
- 新純函式 `suggest_series_termination(intent: dict) -> dict`——deterministic、不 mutate、不寫檔。

## intent schema

```
{
  "net": "XSPI_CLK",                # 目標 net
  "driver_ref": "U1",               # source 端（series R 放這端）
  "net_class": "XSPI",              # 匯流排類別（誠實標記用）
  # 阻抗來源（二擇一，都無 → fail-loud/pending-C04）:
  "target_z0_ohm": 50,              # 設計者已定的目標阻抗（優先）
  # 或 stackup 假設讓生成器算 Z0:
  "stackup": {"er": 4.2, "h_mm": 0.1, "w_mm": 0.15, "t_mm": 0.035},
  # 長度判斷（可選，決定該不該加）:
  "trace_len_mm": 40,               # 已知走線長度（C04 才精確；C03 可估）
  "edge_rate_ns": 1.0,              # 訊號邊緣 t_r（決定 knee freq）
}
```

## output schema（對齊 I2C 生成器 + spec_fragment）

```
{
  "status": "suggested",            # 永不 committed
  "net": "XSPI_CLK",
  "termination_needed": true/false, # λ/10 判斷結果（false → 短線不需，誠實不硬塞）
  "suggestion": {
    "component": {"type":"resistor", "value":"50R", "placement":"series at source (U1)", "net_from":"...", "net_to":"..."},
    "computed": {
      "z0_ohm": 50,
      "z0_source": "caller-specified" | "derived-from-assumed-stackup" | ...,
      "series_r_ohm": 50,           # = Z0
      "knee_freq_hz": ...,          # 0.35/t_r（若有 edge_rate）
      "lambda_over_10_mm": ...,     # 該不該加的門檻
      "trace_len_mm": ...,
      "basis": "series R = Z0 at source (point-to-point), SI KB rule"
    },
    "c04_handoff": "Z0 target + stackup assumption handed to C04; C04 solves real trace width via impedance_solve. Series R value confirmed only after C04 W/H.",
    "evidence": {"kb_object":"control.si.interface-requirements","formula":"...","provenance":"..."}
  },
  "spec_fragment": {...},           # 可貼的 draft（同 I2C 範式）
  "review_required": true,
  "note": "Draft — NOT applied. Series R = Z0 depends on C04-confirmed impedance. Human review + commit."
}
```

## 守哲學鐵律（同第一切片，加 C04 handoff 誠實）

- status 永 suggested、review_required=true、不 mutate、不寫檔。
- Z0 **算或用 caller 給的**，不猜——無阻抗來源 → fail-loud/pending-C04。
- **誠實標記 C04 依賴**：series R = Z0，但 Z0 的實現需 C04 的 W/H；生成器明文標 `c04_handoff` 說「這是 target，C04 用 impedance_solve 確認實際走線」。這守 KB 明文「C03 交 target Z0 不交 width」。
- λ/10 短線 → `termination_needed: false` 誠實回「不需」，不硬塞 series R。
- evidence 錨 `control.si.interface-requirements` + microstrip Z0 公式 + knee freq 公式。

## 驗證

新測試加進 `tests/test_design_suggest.py`（class 內或新 class）：
1. XSPI_CLK intent（target_z0=50, trace_len=40mm, edge_rate=1ns）→ 建議 50R series @ source、termination_needed 判斷、evidence 錨 SI KB、status=suggested、spec_fragment 可貼。
2. Z0 from stackup：只給 stackup（er/h/w/t）→ 算出 Z0（microstrip 公式）→ series R = Z0、z0_source="derived-from-assumed-stackup"、標 c04_handoff。
3. 短線：trace_len 遠小於 λ/10 → termination_needed=false、不硬塞 series R。
4. 無阻抗來源（無 target_z0 無 stackup）→ fail-loud（ValueError）或明確 pending-C04，不猜 Z0。
5. 守哲學 assert：status 永 suggested、不 mutate、不寫檔（同第一切片）。

跑：`PP=$(ls -d packages/*/ | tr '\n' ':')`，`.venv/bin/python3 -m unittest tests.test_design_suggest -v`。

## demo（給 consumer）

用 aiguard 高速匯流排真缺口（XSPI/QSPI CLK net）跑一次，貼建議輸出（series R = Z0 + evidence + c04_handoff + spec_fragment），證明引擎能「從 intent（這是高速 net）算出 source series termination 建議」——比 pull-up 更硬核的「有據設計」。intent 的 target_z0 / stackup 欄位需 consumer 提供（阻抗目標是設計者定的），等做到需對齊時 [COWORK-ASK] consumer。
