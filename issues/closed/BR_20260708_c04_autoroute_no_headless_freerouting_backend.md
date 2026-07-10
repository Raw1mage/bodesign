# BR: C04 autoroute 無 headless freerouting backend，route.sh 在乾淨環境不可執行

- **Date**: 2026-07-08
- **Severity**: high（C04 pipeline 的 route 步驟整段不可用）
- **Reporter**: thesmart_products aiguard C04 gerber run（session 實測）
- **Scope**: bodesign C04 layout engine / route.sh

## Symptom

`03.aiguard/C04-Layout/02_build/generated/tools/route.sh`（build_c04.sh 的 route 步驟）依賴 `freerouting`，但：

1. **freerouting 不在 bodesign 交付的工具鏈裡**——host 沒有安裝、bodesign container 也沒有 bundle。任何乾淨環境跑 `build_c04.sh <board>` 都會在 route 步驟死掉。
2. **freerouting v1.9.0 CLI 模式仍要求 headful AWT**：`MainApplication.main` 呼叫 `Toolkit.getScreenSize()`，headless JRE（如 Ubuntu `openjdk-21-jre-headless`，無 `libawt_xawt.so`）直接 `java.awt.HeadlessException` 崩潰。需要 (a) full JRE（含 libawt_xawt）＋ (b) `xvfb-run` 虛擬 display 才能跑。
3. 系統重啟後 orphan 的 Xvfb display / wrapper script 需要 lifecycle 管理，ad-hoc nohup 不可靠。

## Evidence（session 實測）

- 系統 JRE headless：`ls /usr/lib/jvm/*/lib/libawt_xawt.so` → 不存在；執行即 `HeadlessException at MainApplication.java:269`。
- 帶 `libawt_xawt.so` 的 Temurin 21 full JRE + `xvfb-run -a` → 正常完成 auto-routing 並寫出 `.ses`。
- aiguard_product（30 comps, 91 nets, 2-layer）route+optimize 約 35–40 分鐘；aiguard_ccm（19 comps, 275 nets, 6-layer, BGA）單輪 20–30 分鐘。

## Ask（bodesign 執行）

1. 把 freerouting（建議升到 v2.x，CLI 模式較完善）+ full JRE + xvfb 作為 bodesign C04 engine 的 bundled dependency（Dockerfile.ee 或 route worker image）。
2. route.sh 增加 preflight：`command -v` / headless 偵測，缺件時 fail fast 並指出缺什麼，而不是丟 Java stack。
3. route 步驟由 bodesign worker 執行（container 內），target repo 只留 netlist/DSN 輸入與 SES/routed 輸出，不在 target repo 現場裝工具。

## Honest boundary

本次 session 在 target repo 用 ad-hoc JRE+xvfb 跑通過（product 板已 routed），但這不是可重現的工程路徑；已被 owner 叫停。此 BR 是正式化的請求。

## Resolution (2026-07-10, verified — no code change needed)

**Verdict: RESOLVED in the engineering layer prior to this pass; closed after live verification.** All three Asks are already landed in `Dockerfile.ee` + `packages/eda-bridge/bodesign_eda_bridge/routing.py`. This pass VERIFIED against the live `bodesign-pkcs12-bodesign-ee-1` worker; no source was modified (parallel BRs own route_dsn / net2pcb.py / finish_c04.sh — not touched).

### Ask ①+③ — freerouting + full JRE + xvfb bundled into the EE worker
- `Dockerfile.ee:26-27`: `apt-get install ... default-jre xvfb wget` + `wget -O /opt/freerouting.jar .../freerouting-1.9.0.jar`.
- Live probe (ee container):
  - `/opt/freerouting.jar` present (5.0 MB, v1.9.0 build-2023-10-30).
  - `java` = OpenJDK 21.0.11 on PATH; `xvfb-run` on PATH.
  - `ENV FREEROUTING_JAR=/opt/freerouting.jar JAVA_BIN=java` — route is env-driven, runs inside the worker; target repo only carries DSN in / SES out.

### Ask ② — full JRE with libawt_xawt.so (the headless-crash root cause)
- Live: `/usr/lib/jvm/java-21-openjdk-amd64/lib/libawt_xawt.so` **exists** → the JRE is HEADFUL, so `Toolkit.getScreenSize()` will not throw `HeadlessException`.
- Smoke test: `xvfb-run -a java -jar /opt/freerouting.jar -de /nonexistent.dsn` → Freerouting boots to `Opening '...'` and fails only on the missing input file (a `FileNotFoundException`, NOT a HeadlessException) — the AWT/display path is proven functional.

### Ask ② — route preflight fail-fast (no raw Java stack)
- `routing.py:998-1072`: `classify_autoroute_readiness(probe)` (pure) + `autoroute_preflight()` (probes jar/java/awt_headful/xvfb) enumerate exactly what is missing — `freerouting.jar` / `java` / `full-JRE-libawt_xawt.so` / `xvfb-run-or-DISPLAY` — each with a remediation string.
- Wired to a real MCP entrypoint: `services/mcp/server.py:548` `_h_autoroute_preflight` → tool `bodesign_autoroute_preflight` (server.py:814). A caller can preflight before routing instead of eating a Java stack.
- `autoroute()` itself (routing.py:1075+) still degrades to a no-op passthrough (`{"routed": False, "reason": "freerouting/java not present"}`) when the worker lacks the toolchain — backward-compatible.

### Bonus (cross-BR, verified present, owned by BR_20260708 route_dsn)
- `autoroute(netclasses=...)` → `build_dsn_with_netclasses` injects per-class BGA-escape width/clearance rules into the DSN — the single-global-rule limitation is already addressed.

### Residual hardening recommendation (non-blocking, NOT applied)
- `Dockerfile.ee` installs `default-jre`, a floating meta-package. On this image it resolves to headful openjdk-21 (libawt_xawt.so present ✅), but a future base-image shift could regress it to `-headless` — reintroducing the exact crash this BR describes. **Recommend pinning `openjdk-21-jre` (headful) explicitly** and adding a build-time `test -f /usr/lib/jvm/*/lib/libawt_xawt.so` assert (mirrors the existing `kicad-cli version` fail-loud check). Not applied here to avoid an unverified change to the environment-install surface while parallel BRs are in flight; filed as a follow-up note.

**Disposition:** closed — moved to `issues/closed/`.
