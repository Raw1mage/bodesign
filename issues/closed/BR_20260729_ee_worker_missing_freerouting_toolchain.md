# BR_20260729 — ee worker 缺 freerouting toolchain,C04 routing 完全不可跑

**Status**: CLOSED — self-superseded；toolchain 從未缺失（`Dockerfile.ee:23`/`:91`）
**Closed**: 2026-08-02 by ses_04db7a1c5（coordinator，(default) owner）
**Filed by**: ses_073a93d09ffeRTpR9TwIdofhb3 (aiguard consumer / C00~C04 交付 coordinator)
**Fix venue**: bodesign repo(platform owner session,同 repo infra)
**Severity**: blocking — C04 產品交付(routed board / gerbers / assembly)完全無法產出
**Class**: 部署漂移(image 過期),同 BR kiutils 家族

---

## Symptom(verbatim)

`bodesign_autoroute_preflight` 回報:

```json
{
  "ready": false,
  "missing": ["freerouting.jar", "java", "xvfb-run-or-DISPLAY"],
  "reason": "freerouting autoroute NOT runnable — missing: freerouting.jar, java, xvfb-run-or-DISPLAY",
  "probe": {
    "jar_present": false,
    "java_present": false,
    "xvfb_present": false,
    "awt_headful": false,
    "display": false,
    "jar_path": "/opt/freerouting/freerouting.jar",
    "java_bin": "java"
  }
}
```

三項全缺:jar / JRE / 虛擬顯示。

## RCA(consumer 側可及範圍)

preflight 自帶的 remedy 第一條就是根因線索:

> install freerouting.jar (FREEROUTING_JAR env or /opt/freerouting.jar);
> **rebuild the ee worker image (Dockerfile.ee bundles v1.9.0)**

即 **`Dockerfile.ee` 宣稱 bundle freerouting v1.9.0,但運行中的 ee worker image 裡沒有**。這與 2026-07-23 的 kiutils BR 是**同一類缺陷**:source 正確、運行 image 過期。

**為何上輪的修復沒有涵蓋這個**:2026-07-23 收尾時 platform 對 d1ab7fd 採用 `BODESIGN_DEV=1 mcpctl restart`(dev bind mount 熱重載 Python)。那個判斷對當時的 scope 是正確的(`/app/packages` 是 host bind,Python 改動不需 rebuild),但 **freerouting.jar / java / xvfb 是 image 層產物,不在 bind mount 內** —— restart 永遠補不進來,只有 image rebuild 會。所以這不是上輪的疏失,而是「restart 修得了 Python、修不了 image 層依賴」的邊界暴露。

**未由 consumer 側驗證的部分**(需 platform 確認):
- `Dockerfile.ee` 是否真的有 freerouting 的 COPY/RUN 指令,還是宣稱與實作有落差(比照 BR kiutils 的 RCA-2:三個 worker Dockerfile 從沒 COPY doctrine.md)
- java / xvfb 是否也在同一份 Dockerfile 宣告
- 是否有其他 image 層依賴同樣漂移(建議一併機檢,避免逐個踩)

## Impact(對 aiguard C00~C04 交付)

當前 aiguard 狀態(`gate.py package_readiness`):

| stage | dod_ok | 備註 |
|---|---|---|
| c00 | ✅ | |
| c01 | ✅ | |
| c02 | ✅ | |
| c03 | ✅ | 剛完成 DoD 正規化(commit e313e4e) |
| c04 | ✅ | 但 row3-6 是 `honest-status: pending` |

**gate 綠 ≠ 產品可交付**。C04 的 `routed_board` / `gerbers_drill` / `assembly_package` / `copper_renders` 四項在 DoD manifest 裡帶 `honest_states: [pending, not-run]`,所以 gate 誠實放行——但那正是「還沒交付」的意思。要把它們從 pending 變成真交付,**必須跑 routing**,而 routing 現在不可跑。

換言之:這個 BR 是 aiguard C04 從「gate 綠」走到「產品可交付」的**唯一硬 blocker**。

## Fix proposal

1. **確認 `Dockerfile.ee` 實況**:比對它是否真的 bundle freerouting v1.9.0 + JRE + xvfb;若宣稱與實作有落差(如 kiutils RCA-2 的 doctrine.md 案),補上。
2. **Rebuild ee worker image**(非 restart —— 這是 image 層依賴,bind mount 熱重載無效)。
3. **Live 驗證證據**(比照 kiutils / symbol_dirs 的慣例):
   - `bodesign_autoroute_preflight` → `ready: true`、`missing: []`
   - 容器內 `java -version` OK、`ls /opt/freerouting/freerouting.jar` 存在
   - 對真 board 跑一次 `bodesign_autoroute` 確認不再 raise HeadlessException
4. **順帶建議**:preflight 已經是好設計(fail-loud 且自帶 remedy,沒有靜默降級)。若能在 `mcpctl status` 加一行 image 層依賴的健康檢查,這類漂移就會在部署當下暴露,而不是等 consumer 踩到。

## Explicitly NOT bugs(consumer 側已排除)

- **`autoroute_preflight` 本身無誤**:它精確列出三個缺項 + 可執行 remedy + probe 細節,是教科書級的 fail-loud gate。這個 BR 正是因為它做對了才能快速定位。
- **上輪的 `mcpctl restart` 決策無誤**:對 d1ab7fd(純 Python)是正確且更安全的選擇(避開 image build 吃工作區殘留)。本 BR 只是暴露它的作用邊界。
- **aiguard 側 netlist / DoD 無誤**:`C03-EE/aiguard_ccm.net`(166KB / 2823 行,零 TBC)已就緒,C00~C04 全 `dod_ok=true`。blocker 純在 platform 工具鏈。

## Validation plan

platform 修好後,consumer 側會執行並回報:

1. `bodesign_autoroute_preflight` → 期望 `ready: true`
2. `bodesign_route_net2pcb`(用 `aiguard_ccm.net`)→ placed board
3. `bodesign_placement_preflight` → 確認 floorplan 不是必死
4. `gate.py c04_placement_review` → 產 review package 交使用者核可(**AI 不得自行寫 `PLACEMENT_APPROVED.json`**)
5. 核可後 `bodesign_autoroute` → routed board
6. `bodesign_layout_drc_gate` → copper/unconnected violations
7. `bodesign_emit_fab` → gerbers + drill

## Consumer 側同時進行(不等此 BR)

routing 被擋不代表停工。以下不需 freerouting:
- `route_net2pcb`(placement,只需 pcbnew)
- `placement_preflight`(floorplan 可行性)
- `c04_placement_review`(review package + 使用者核可 gate)

這三步會先跑完,讓 routing 一解除就能立刻接上。

---

**Fix venue**: bodesign repo,platform owner session 內聯修(同 repo infra,確定性 image rebuild)
**Relay**: a2a topic `aiguard-c00c04-delivery` + inject ses_0c87bab06fferQ0umBs2Nybb5U
