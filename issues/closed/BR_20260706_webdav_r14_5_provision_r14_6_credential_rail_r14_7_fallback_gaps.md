# BR_20260706 — bodesign WebDAV working-cache: R14.5 provision config missing + R14.6 credential rail needs verification + R14.7 fallback unproven

**Status**: CLOSED (2026-07-06)
**Severity**: Medium (R14 mount + lifecycle conformant; provisioning/credential-rail/fallback gaps block full R14 conformance)
**Scope**: bodesign webdav working-cache (R14 conformance)
**Source**: fleet plan `opencode/plans/mcp_webdav-fleet-conformance` — coverage-gap sweep (deep-recon ses_0cccd3679ffe, governance session 2026-07-06)
**Fleet SSOT**: `opencode/specs/mcp-integration-standard/standard.md` §R14 + §12 readiness matrix
**bodesign in-flight**: `plans/mcp_r13-landing-webdav-cache/` + `docs/events/event_20260702_r13-landing-webdav-kickoff.md` — bodesign is already landing its own webdav cache; **this BR must align with that plan, not duplicate it**

## 現象(含硬證據)

bodesign 是 **fleet coverage 的重量級遺漏** —— 原始 deep-recon 完全沒掃它(只掃 docxmcp/patentmcp/drawmiat/pmsmcp/specbase)。實查:bodesign 有**完整的 R14 webdav working-cache 實作**,但三款有缺口:

- **交付物**：AI PCB 設計副駕,交付可送廠文件包(KiCad 原理圖/佈局/Gerber/BOM/STL/STEP + render)—— 大量重檔案交付,是 R14 的正牌適用對象。
- **實作齊全**：`services/mcp/_webdav.py`（class-2 DAV）+ `token_store.py` + `_auth_provider.py`；cache lifecycle `cache_provision/export/close`（`services/mcp/server.py:622,640,654`）。
- 逐款狀態：
  - R14.1 ✅ class-2 `/dav/{token}/` mount（`server.py:824` desc + `_webdav.py`）
  - R14.2 ✅ per-deliverable working cache + dirty-gated close（`server.py:593 _cache_close`,`WORKSPACE_CLOSE_DIRTY`）
  - R14.3 ✅ `cache_export(cache_token,target)` land whole tree（`server.py:554,640`）
  - R14.4 ✅ cross-owner `CACHE_FORBIDDEN`（`server.py:828` desc）
  - **R14.5 ❌**：`docker-compose*.yml` grep `AUTH_PROVIDER` 全空 —— per-host provision 設定缺
  - **R14.6 ⚠️ 需確認**：`server.py:633 credentials.issue(owner)` 在 MCP handler `_h_cache_provision` 內,provision 時直接回 `webdav_password`（`:636`）+ rotate（`:824` desc "rotated on every provision"）。HTTP path `cache_provision`（`server.py:1545`）也簽發（`:1566`）。**待查點**:是否有獨立的 `issue_webdav_credential` opt-in flag(對照 docxmcp `bin/mcp_server.py:2641`),還是 credential **綁死 provision**？若綁死,則每次 provision 都回 password,**default payload 就不是 byte-identical** —— 可能違反 R14.6 的 opt-in 精神(天条 11)。
  - **R14.7 ⚠️ 未證實**：有 token file model（`stage_dir` 小檔路徑,`mcp.json` desc）,但未讀到「未 provision → stage-inline fallback」分支。

## RCA

bodesign 獨立移植了 docxmcp 的 `_webdav.py` + AuthProvider（其 `event_20260702_r13-landing-webdav-kickoff.md` 自述），mount/wire/lifecycle 都到位,credential 甚至做到 provision-即簽發+rotate（比 patentmcp 進一步）。但:(1) R14.5 per-host provision 設定沒進 compose;(2) credential 簽發語義與 docxmcp R14.6 的 **opt-in flag** 模型可能分歧(provision-bound vs opt-in),需對照確認 default payload 是否 byte-identical;(3) R14.7 fallback 未證。屬「自行移植 reference 時，落在 opt-in 語義與 provisioning 部署層的偏差」,非設計錯誤。

## 建議修復

1. **R14.5**：在 bodesign 部署設定（compose）加 per-host `AUTH_PROVIDER=builtin`（或等價）provision 設定。
2. **R14.6 確認 + 對齊**：確認 credential 簽發是**綁死 provision** 還是有獨立 opt-in flag。若綁死,評估是否需 port docxmcp 的 `issue_webdav_credential` opt-in 模型以保 default payload byte-identical（天条 11）。若已是 capability-gated 且 caller 可選,如實記錄為 conformant。
3. **R14.7**：確認/實作「未 provision → stage-inline + UDS GET」fallback（loud 不 silent）。
4. **對齊 in-flight plan**：本 BR 的修補應併入 bodesign 既有 `plans/mcp_r13-landing-webdav-cache/`,不另起爐灶。
5. **test-verify（DD-5）**：bodesign 已有 `tests/test_webdav_poc.py` + `tests/test_cache_store.py` —— 補 credential opt-in + provision-state 的 test-run 證據。

## 影響範圍

- bodesign webdav 在**無 compose provision 設定**的 host 上 R14.5 不合規（部署層）。
- R14.6 若 credential 綁死 provision,default payload 非 byte-identical —— 影響「不想要 credential 的 caller」（天条 11 精神）。
- 打擊半徑：`server.py:622-636,1545-1584`、`docker-compose*.yml`、`services/mcp/{_webdav.py,_auth_provider.py}`；與 bodesign 既有 webdav plan 的協調。

## 驗證手段

- `grep AUTH_PROVIDER docker-compose*.yml` 有命中（R14.5 provision 設定就位）。
- 確認 credential opt-in 語義：不要 credential 時 `cache_provision` payload byte-identical；要時明確回 rotated credential。
- `bodesign tests/test_webdav_poc.py test_cache_store.py` 綠 + 新 credential opt-in test。
- fleet §12 矩陣新增 bodesign 列,從 ⚠️ 升至 test-verified ✅ 後才 close。

## 結案記錄 2026-07-06

**Status → CLOSED**（bodesign session，61 tests passed + live MCP smoke）

- **R14.6 查證結果**：credential 確實**綁死 provision 且每次 rotate**（比 BR 猜測更實害：re-provision 會作廢 live mount 的密碼）。修復：MCP-rail `bodesign_cache_provision` 加 `issue_webdav_credential` opt-in flag（`services/mcp/server.py _h_cache_provision`），default payload 不帶 credential（天條 11）。HTTP `/caches` 維持 provision-bound（該路徑本就要求 Basic auth，caller 明確持有並預期 credential）——as-designed，非缺口。
- **R14.5**：`docker-compose.yml` 加 `BODESIGN_AUTH_PROVIDER: "builtin"`；`_auth_provider.py` 新增 `host_provision_state()`（rail + HTTP 兩payload 都帶 `host_provision`；未知 provider 值 fail-fast `AUTH_PROVIDER_UNKNOWN`，不靜默 coerce）。
- **R14.7**：caller 由 `host_provision` 顯式欄位決定 webdav-mount vs stage-inline（`bodesign_stage_dir` R2 token model 即 fallback 路徑）——顯式訊號、非 implication。
- **驗證**：`tests.test_webdav_poc` + `tests.test_cache_store` 61 pass（+2 新測試：opt-in rotate 語義、default 不 rotate、provider fail-fast）；live smoke（dev restart 後）：default provision 無 credential + host_provision.state=provisioned/explicit=true → opt-in 回 credential → close 正常。
- **Spec 對齊**：`specs/mcp/r13-landing-webdav-cache` amend（DD-8）；idef0/grafcet 依 drawmiat-canonical shape 重寫（原為舊 simplified 形制，觸發 state-integrity 檢查）；`specs/architecture.md` 同步。fleet 矩陣（opencode standard.md §12）bodesign 列已升 ✅。
