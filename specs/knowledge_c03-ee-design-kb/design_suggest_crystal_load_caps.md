# 方案 C 第三切片設計：crystal load-cap「有據建議 + 核對」生成器

> plan: knowledge_c03-ee-design-kb 延伸（軌 C，合成層方案 C）
> 來源：consumer round=13/16 pattern 重排（crystal 插 series-term 前，此 spec 有 HSE+CX1/CX2 真載體）
> 守哲學鐵律：引擎**建議/核對**，不**決定**；值算不硬編、錨 evidence、誠實標 CL 來源與公式邊界
> 對齊：`design_suggest.py::suggest_i2c_pullups` 同範式（compute + anchor + draft + spec_fragment）

## 為什麼 crystal 提前（consumer 判準：有真載體）

此 MCU core spec 有 **X1（crystal）+ HSE_IN/HSE_OUT + CX1/CX2（18pF load cap）** 真載體。consumer 坐實 18pF 是「每顆 load cap 實值」，X1 才是晶振，spec 無 X1 的 CL datasheet 規格。所以此載體上生成器是 **驗證器角色**（核對現值），非「從無到有生成」——但兩模式共用同一算法核心。

## 算法核心 + 誠實公式邊界（關鍵）

標準晶振 load cap 匹配：`CL = (Cx·Cy)/(Cx+Cy) + C_stray`。對稱設計 Cx=Cy=C_load_each 時反解：

```
C_load_each = 2·(CL − C_stray)
```

- CL = 晶振 datasheet load capacitance（振盪穩定的目標）
- C_stray = PCB 雜散電容（典型 3-5pF；KB `control.si.crystal-oscillator-layout` 引 NXP：1.0cm×0.1cm trace on solid GND、Dk 高時 stray 15-50pF，但一般短 trace 4pF 合理）

**⚠️ 誠實公式邊界（守 no-fabrication，KB 明文約束）**：
KB 物件 `control.si.crystal-oscillator-layout`（verified, sw=6）**明文標 UNVERIFIED**：
> CL=(C1×C2)/(C1+C2)+Cstray 逐字明式（概念 verified、明式未命中）

即：load-cap 匹配的**概念**在 KB 是 verified（Cx/Cy + stray 的容抗匹配晶振感抗），但**逐字公式**未在此 KB 命中原文。所以生成器 evidence 必須誠實：
- `formula`: 標為 `C_load_each = 2*(CL - C_stray)` from standard symmetric crystal load-cap matching — **concept verified in KB (control.si.crystal-oscillator-layout, NXP AN1706 + Microchip AN826), explicit closed form is standard EE (not verbatim-anchored)**。
- **不宣稱逐字錨到 KB 明式**——這正是 bodesign 展示 vs 宣稱的哲學。

## 兩模式（同算法核心）

### suggest 模式（無 load cap 的晶振，從無到有）
intent 帶 CL（+ C_stray 假設）→ 算 C_load_each → 建議每顆 load cap 值 + spec_fragment（Cx/Cy 掛在 crystal 兩腳到 GND）。

### verify 模式（已有 load cap，consumer 的 X1 載體，核對）
intent 帶 CL + 現有 cap 值 → 算應然 C_load_each → 核對現值 → verdict CONSISTENT / MISMATCH + 差異量。**這正是 bodesign 核心哲學（對照交叉檢核）的縮影**——生成器不只會生，還會核對已存在設計對不對。

## 落點

- 同模組 `packages/eda-bridge/bodesign_eda_bridge/design_suggest.py`（append，不動既有 I2C/series 函式與 helper）。
- 新純函式 `suggest_crystal_load_caps(intent: dict) -> dict`——deterministic、不 mutate、不寫檔。

## intent schema

```
{
  "crystal": "X1",                       # 晶振 ref
  "osc_pins": ["HSE_IN", "HSE_OUT"],     # 兩個振盪 net（Cx/Cy 各掛一個）
  "load_cap_refs": ["CX1", "CX2"],       # load cap ref（verify 模式；suggest 模式可省或給 hint ref）
  "crystal_cl_pf": 13,                   # 晶振 CL（datasheet 或反推假設）
  "cl_source": "datasheet" | "back-derived-assumption",  # 誠實標記 CL 來源
  "stray_pf": 4,                         # PCB 雜散電容假設（可選，預設 4）
  # verify 模式額外:
  "existing_cap_pf": 18,                 # spec 現有每顆 cap 值（給了就進 verify 模式核對）
  "ground_net": "GND",                   # load cap 另一端（預設 GND）
}
```

## output schema（對齊前兩切片 + spec_fragment）

```
{
  "status": "suggested",                 # 永不 committed；verify 模式 verdict 另在 result
  "mode": "suggest" | "verify",
  "crystal": "X1",
  "computed": {
    "crystal_cl_pf": 13,
    "cl_source": "back-derived-assumption",   # 誠實標記
    "stray_pf": 4,
    "c_load_each_pf": 18,                      # = 2*(CL - stray)
    "formula": "C_load_each = 2*(CL - C_stray); symmetric crystal load-cap matching",
    "basis": "..."
  },
  # verify 模式:
  "verdict": "CONSISTENT" | "MISMATCH",       # 現值 vs 算出值
  "existing_cap_pf": 18,
  "delta_pf": 0,                              # 現值 - 算出值
  # suggest 模式 or verify 都有可貼片段:
  "suggestion": {
    "component": {"type":"capacitor", "value":"18pF", "count":2, "placement":"one per osc pin to GND"},
    "evidence": {"kb_object":"control.si.crystal-oscillator-layout","formula":"...","provenance":"NXP AN1706 + Microchip AN826","confidence":"verified","form_note":"explicit closed form is standard EE, concept KB-verified"}
  },
  "spec_fragment": {...},                # 兩顆 Cx/Cy draft（verify 模式：標「matches existing」）
  "review_required": true,
  "note": "Draft — CL source honestly marked. Human review + commit. ..."
}
```

## 守哲學鐵律（同前切片 + CL 誠實）

- status 永 suggested、review_required=true、不 mutate、不寫檔。
- C_load_each **算**（`2·(CL − stray)`），不硬編。
- **CL 來源誠實標記**：`cl_source` 明標 datasheet vs back-derived-assumption；反推假設時 note 明說「CL 是從現有 cap 反推、非 datasheet 實測，待 X1 datasheet 確認」。
- **公式邊界誠實**：evidence 標「concept KB-verified、explicit form standard EE、非逐字錨 KB 明式」。
- verify 模式核對：現值 == 算出值（容差如 ±1pF）→ CONSISTENT；否則 MISMATCH + delta，**不改 spec**（只報）。
- evidence 錨 `control.si.crystal-oscillator-layout`（verified, sw=6）。

## 驗證

測試加進 `tests/test_design_suggest.py`（新 class `SuggestCrystalLoadCapsTests`）：
1. **verify 模式（consumer X1 載體）**：intent{crystal:"X1", crystal_cl_pf:13, cl_source:"back-derived-assumption", stray_pf:4, existing_cap_pf:18} → c_load_each=18pF、verdict=CONSISTENT、delta=0、cl_source 明標反推、evidence 錨 crystal KB。
2. **suggest 模式（從無到有）**：intent 無 existing_cap_pf、帶 CL=20pF、stray=5 → c_load_each=2·(20−5)=30pF、mode=suggest、spec_fragment 兩顆 30pF。
3. **MISMATCH**：existing_cap_pf=22 但算出 18 → verdict=MISMATCH、delta=4、不改 spec。
4. **守哲學 assert**：status 永 suggested、不 mutate、不寫檔。
5. **CL 缺失 fail-loud**：無 crystal_cl_pf → ValueError（不猜 CL）。
6. **evidence form_note**：evidence 明標「concept KB-verified、explicit form standard EE」（不宣稱逐字錨）。

跑：`PP=$(ls -d packages/*/ | tr '\n' ':')`，先清 pycache，`.venv/bin/python3 -m unittest tests.test_design_suggest -v`。全部（I2C+series+crystal）綠。

## demo（給 consumer，verify 模式對 X1 真載體）

intent{crystal:"X1", osc_pins:["HSE_IN","HSE_OUT"], load_cap_refs:["CX1","CX2"], crystal_cl_pf:13, cl_source:"back-derived-assumption", stray_pf:4, existing_cap_pf:18}
→ computed c_load_each=18pF、verdict=CONSISTENT、cl_source 明標反推假設、evidence 錨 crystal KB（verified sw=6）+ form_note。
證明引擎能「對真 net 算 load cap + 核對現值一致性」——bodesign 對照交叉檢核哲學的縮影。
