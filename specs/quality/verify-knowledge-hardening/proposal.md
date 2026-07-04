# Proposal: quality_verify-knowledge-hardening

## Why

- bodesign PRD→Gerber 管線已實證走通（`specs/validation/prd-to-gerber-e2e/`），但**驗證判斷力薄弱**：C04-C06 只有 DRC gate + crosscheck 骨架，缺乏「像資深硬體工程師逐項判斷設計對錯」的系統化知識。三個實測缺口 G3（擺件品質無電氣感知）、G4（datasheet-grounded 冷啟動）、T1（no-connect 無法宣告）都指向同一根因：**bodesign 不會判斷「這個設計哪裡有問題」**。
- 爬取 mcpmarket `pcb-design-auditor` → 真身 GitHub `pjcau/esp32-emu-turbo`，發現一整套 40+ PCB verify skill + 80+ 確定性 `verify_*.py`，涵蓋 8 域驗證（power/signal/thermal/EMI/DFM/mechanical）、JLCPCB 完整製造規則、pin→net single-source-of-truth、擺後品質檢查。**它的價值是「教 bodesign 判斷對錯」的驗證知識**，正好命中 bodesign 核心哲學（展示可靠度＝確定性驗證，非宣稱）。

## Original Requirement Wording (Baseline)

- 「bodesign還是相當不成熟。需要補知識技能。不然根本沒辦法從使用者的PRD產出gerber」
- 「https://mcpmarket.com/zh/tools/skills/pcb-design-auditor-1 可以去爬一些技能回來補充嗎」
- 「對。它是verify用的，但可以讓你學會判斷對錯。」

## Requirement Revision History

- 2026-07-03: initial draft created via plan-init.ts
- 2026-07-03: 澄清方向——使用者拍板 pjcau skill 是 verify 導向，價值是教 bodesign 判斷對錯；採「知識萃取進 ragbase + 寫確定性 checker」路徑（非照搬 code）。

## Effective Requirement Description

1. 萃取 pjcau `esp32-emu-turbo` skill 集合的**驗證判斷知識**（非 code）進 bodesign ragbase，帶可追溯來源錨點（skill 名 / 標準號 IPC/JLCPCB）：
   - 8 域驗證分類法（power / signal / thermal / EMI-EMC / DFM / mechanical + 電氣 review + datasheet 一致性）
   - JLCPCB 製造規則數值表（trace/via/hole/pad/mask/silk/edge 參數）＝公開製造能力
   - pin→net single-source-of-truth 驗證模式（G4 datasheet-grounded 對位）
   - 擺後品質檢查規則（decap 距離 / thermal via / copper balance / crosstalk，G3 對位）
   - DRC 分類法：real-short vs pad-net-bug、no-connect 意圖宣告（T1 對位）
2. 把萃取知識寫成**確定性 checker**（零 LLM、fail-fast、帶來源錨點），至少實作首個 checker 打通端到端，證明知識→工具的路徑。
3. 產出可被 bodesign skill（C06 verify 階段）與 workflow-core 驗證管線引用的知識物件。

## Scope

### IN
- 萃取 pjcau 8 域驗證知識 → ragbase 知識物件（concept / control / workflow，plan scope）。
- JLCPCB DFM 規則表、IPC-7525/IPC-2222 標準值萃取（自己的話重寫 + 標來源）。
- 首個確定性 checker 實作（對位 T1 no-connect 宣告 或 G3 擺後品質檢查）+ 單元測試。
- proposal / design（含 idef0 + grafcet）/ tasks 規格。

### OUT
- 照搬 pjcau 的 project-specific `verify_*.py` code（硬編路徑、寫死零件、無 LICENSE）。
- 複製 pjcau 受著作權保護的原文段落。
- G3 擺件**生成**演算法（走既有 `plans/quality_deterministic-preplacement/` 專利/arXiv 線）。
- 8 域全部 checker 一次做完（本案立方法 + 首個示範，其餘增量另案）。
- send-to-fab、實體打樣。

## Non-Goals

- 不做 IC 級 EDA 驗證；目標場景 <100 零件小板。
- 不引入需訓練的 ML 驗證（違天條）。
- 不把 pjcau 的 ESP32 專屬規格值當通用預設（那是它的板、不是通用製造能力）。

## Constraints

- bodesign 天條：驗證/比對零 LLM、no silent fallback、datasheet-grounded 規格值、no fabrication。
- 法律邊界：製造參數數值（JLCPCB/IPC）＝公開製造能力，不受著作權保護，可萃取；但**須用自己的話重寫、標來源錨點**，不複製 pjcau 原文與 code。pjcau repo 無 LICENSE 檔＝保留所有權利。
- checker 落點對齊既有架構：core（pure-python 判斷）vs ee/me worker（重 toolchain）邊界。
- 知識沉澱走 ragbase `plan:quality/verify-knowledge-hardening` scope，收尾 rescope repo。

## What Changes

- ragbase 新增 8 域驗證知識物件（DFM 規則 / 分類法 / SSOT 模式 / 擺後檢查規則）。
- workflow-core 或 eda-bridge 新增首個確定性 checker 模組 + MCP 工具註冊 + 測試。
- `specs/architecture.md` 驗證 baseline / Immediate Capability Gaps 段落更新。
- bodesign skill C06 verify 階段 GUIDE 可引用新知識（本案標註，實際接線視首個 checker 落點）。

## Capabilities

### New Capabilities
- 驗證判斷知識庫：8 域 PCB 設計對錯判斷規則，帶標準來源錨點，供 checker 與 skill 引用。
- 首個確定性 verify checker：把知識落成 fail-fast 檢查，證明知識→工具路徑。

### Modified Capabilities
- C06 驗證管線：從「DRC gate + crosscheck 骨架」擴為「知識驅動的多域對錯判斷」的起點。

## Impact
- 後續 verify checker 增量（8 域逐一補齊）的立案依據與知識來源。
- `plans/quality_deterministic-preplacement/`（G3 生成）互補：本案供擺後檢查規則，該案供擺件生成。
- `specs/knowledge/datasheet-spice-models/`（G4 vault L4）互補：本案 pin→net SSOT 驗證模式對位。
