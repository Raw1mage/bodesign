# BR: C06 analyzer engines (kicad/spice/emc) 未掛載進 bodesign 容器 — simulate/EMC/thermal 永遠 skipped-no-skills

- **Date**: 2026-06-23
- **Reporter**: TheSmartAI (orchestrator)
- **Target**: bodesign 維護者（容器/部署層 + eda-bridge + 文件）
- **Type**: capability/deployment gap（非 code bug — 是部署/掛載缺漏，導致一整類 C06 工具無法產出 verdict）
- **Severity**: **high** —— C06 的三個核心驗證工具（simulate/analyze_emc/analyze_thermal）在現行容器部署下**永遠**回 `skipped-no-skills`，使 C06 的 SPICE/EMC/thermal 永遠停在 `not-run`，無法從設計流程內推進。
- **Origin task**: 完備 `thesmart_products/01.openmv` (aiguard) C06 — 嘗試把 not-run 升為真實工具 verdict 時撞到此邊界。

---

## 1. 一句話

bodesign 的類比/EMC/熱分析工具靠 `resolve_skill(name, ENV_VAR, ...)` 在執行期找 kicad/spice/emc analyzer engine，但**現行 Docker 容器既沒設 `BODESIGN_KICAD_SKILL`/`BODESIGN_SPICE_SKILL`/`BODESIGN_EMC_SKILL`，也沒把 analyzer skill 目錄掛載進去**。於是 `simulate` / `analyze_emc` / `analyze_thermal` 三個工具一律回 `skipped-no-skills`、產不出任何 verdict——C06 的 SPICE/EMC/thermal 在容器內**結構性無法執行**。

---

## 2. 觀察到的 gap（以本次任務為證據）

需求：把 aiguard C06 的 simulate/EMC/thermal 從 `not-run` 升為真實工具 verdict（依 honesty model，verdict 必須由實跑產生，不可偽造）。

實跑（對真實 `aiguard_power.kicad_sch` + `aiguard_power_routed.kicad_pcb`，已用 file-model 上傳進容器）：

| 工具 | 回傳 | warning |
|---|---|---|
| `bodesign_simulate` | `skipped-no-skills` | `kicad/spice skill not found (set BODESIGN_KICAD_SKILL / BODESIGN_SPICE_SKILL).` |
| `bodesign_analyze_emc` | `skipped-no-skills` | `kicad/emc skill not found.` |
| `bodesign_analyze_thermal` | `skipped-no-skills` | `kicad skill not found.` |

容器邊界證據：
- `docker exec bodesign-pkcs12-bodesign-1 sh -c 'echo $BODESIGN_KICAD_SKILL; echo $BODESIGN_SPICE_SKILL; echo $BODESIGN_EMC_SKILL'`
  → 三者皆**空**。
- `ls /root/.claude/skills/bodesign/engines/kicad` (容器內) → `No such file or directory`。
- `docker-compose.yml` / `docker-compose.workers.yml` 的 `volumes:` 區段**沒有**掛載 analyzer skill 目錄，也沒有對應的 `BODESIGN_*_SKILL` env。

---

## 3. Root cause（code anchor）

- **`packages/eda-bridge/bodesign_eda_bridge/pcb_verify.py:55-58`** — `analyze_emc` 以 `resolve_skill("kicad", "BODESIGN_KICAD_SKILL", ...)` + `resolve_skill("emc", "BODESIGN_EMC_SKILL", ...)` 找引擎；任一缺 → `return PcbVerifyResult("emc", "skipped-no-skills", ...)`。
- **`packages/eda-bridge/bodesign_eda_bridge/pcb_verify.py:84-86`** — `analyze_thermal` 同樣靠 `resolve_skill("kicad", ...)`；缺 → `skipped-no-skills`。
- **`packages/eda-bridge/bodesign_eda_bridge/simulate.py:48-52`** — `simulate` 需要 `resolve_skill("kicad", ...)` + `resolve_skill("spice", ...)`；缺 → `skipped-no-skills`。
- **部署層**：`Dockerfile` / `docker-compose*.yml` 沒有 (a) 安裝/掛載 `engines/kicad`（含 spice/emc analyzer）到容器、(b) 設定指向它的 `BODESIGN_*_SKILL` env。MCP server instructions 雖寫「verification tools call the skill's engines back (via BODESIGN_KICAD_SKILL, default ~/.claude/skills/bodesign/engines/kicad)」，但該預設路徑在容器內不存在。

> 註：這與 2026-06-23 已修的 readiness path-visibility BR
> (`issue_20260623_readiness_silent_missing_on_invisible_path.md`) **是不同缺陷**。那個是 host
> 路徑不可見；這個是 analyzer engine 沒進容器。兩者唯一共通點是「容器掛載邊界」這個主題。

---

## 4. 為何這是 bodesign 該補的

1. **C06 是 bodesign 宣稱的交付層**：`bodesign_simulate` / `analyze_emc` / `analyze_thermal` 是已暴露的工具，MCP 自述也明說 verification tools 會回呼 engine。工具存在卻在預設部署下永遠跑不動，是部署契約沒收尾。
2. **honesty model 需要「能真跑」的路徑**：honesty 規則禁止偽造 verdict，所以唯一能讓 C06 前進的方式就是讓工具真的能執行。目前 analyzer 不在容器內 → C06 永遠卡 not-run，與「reliability is shown, not asserted」的精神矛盾（無法 show）。
3. **fail 訊號雖正確但無修復路徑**：工具誠實回 `skipped-no-skills`（這點是對的，沒有偽造），但使用者/agent 拿到後**無法在 bodesign 範圍內自救**——env 與掛載都在部署層，非 tool 參數可控。

---

## 5. 建議修復方向（治本，細節留待 plan）

1. **容器內提供 analyzer engine**：在 `Dockerfile` / compose 把 `engines/kicad`（含 spice/emc analyzer + ngspice 依賴）安裝或 bind-mount 進 bodesign（或負責 EE 分析的 worker）容器，並設 `BODESIGN_KICAD_SKILL`/`BODESIGN_SPICE_SKILL`/`BODESIGN_EMC_SKILL` env 指向它。
2. **釐清執行歸屬**：確認 simulate/EMC/thermal 應在 main 容器或 ee/me worker 跑（`bodesign-ee`/`bodesign-me` 已存在），把 engine 掛到正確 service。
3. **部署自檢**：啟動時（或一個 `bodesign_*_selfcheck`）回報 analyzer engine 是否就緒，讓「能不能跑 C06」一眼可見，而非要 agent 用 `docker exec` 偵查 env。
4. **文件對齊**：MCP 自述目前說 `BODESIGN_KICAD_SKILL` 預設 `~/.claude/skills/bodesign/engines/kicad`——在容器內此路徑不存在，需更正為實際容器路徑或標明「需部署時掛載」。

---

## 6. 影響範圍 / 暫行狀態

- 受影響：所有需要 C06 SPICE/EMC/thermal verdict 的專案（本次為 aiguard）。
- 暫行：aiguard C06 的 simulate/EMC/thermal 維持 `not-run`，已誠實記於
  `thesmart_products/01.openmv/Gap_Readiness_Report.md` §3.1（含 unblock step）。crosscheck verdict
  (**pass**, 269/269) 不受影響——它走 `reference_crosscheck`，非 analyzer engine。
- 未開遠端 GitHub issue（依 local-first 慣例）。

> **Plan package opened (2026-06-23)**: `plans/deployment_c06-analyzer-engines-in-container/`
> (state: **planned**, plan-only). RCA grounded against the real topology — root cause restated
> as **engine *scripts* never packaged into the image + no `BODESIGN_*_SKILL` env** (the
> container-mount framing above is a red herring; engines exist as cleaned tarballs at
> `services/mcp/assets/skills/{bodesign,spice,emc}.tar.gz` but are never extracted). simulate/
> analyze_emc/analyze_thermal ∈ `_EE_GROUP_TOOLS` → fix lands in `Dockerfile` + `Dockerfile.ee`
> (not `Dockerfile.core`, which forwards EE). DD-1..DD-6 + tasks + tests in the package.
> Implementation + GB image rebuild await separately-authorized execution (see the package handoff).
