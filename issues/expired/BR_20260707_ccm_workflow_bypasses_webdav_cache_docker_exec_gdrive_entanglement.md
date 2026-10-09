# BR_20260707 — CCM 原理圖工作流繞過 webdav working-cache：docker-exec 直驅容器內部路徑 + GDrive 工程檔糾纏

- **Status**: OPEN
**Severity**: Medium（工作流違規，非引擎缺陷；R14 rail 本身已合規）
**Scope**: C03 CCM 頁面生成工作流（orchestration 層，axis-B tool-selection miss）
**Related**: `issues/closed/BR_20260706_webdav_r14_5_provision_r14_6_credential_rail_r14_7_fallback_gaps.md`（R14 rail 已 CLOSED 合規——本 BR 是「rail 存在卻沒被用」的正交缺陷）

## 現象（含硬證據）

C03 原理圖（CCM 5 頁）的整條工程迭代工作流完全繞過 bodesign MCP 的 working-cache rail：

1. **工作區在容器內部路徑**：`gen_ccm_pages.py` + 全部工程檔（`.kicad_sch`/`_symvariants`/render）活在 `bodesign-pkcs12-bodesign-ee-1` 容器的 `/work/aiguard/C03-EE/`。`docker inspect` mounts 證實該路徑**不是任何 volume/bind mount**（僅有 bodesign-sessions volume、/app/packages ro、/app/services ro、/work/experiments bind）——純容器 ephemeral 檔案系統，容器重建即滅失。
2. **傳輸走 docker exec/cp**：每輪重產 `docker exec ... python3 gen_ccm_pages.py`，產物 `docker cp` 到 /tmp 再 cp 到 GDrive rclone FUSE。跨 host↔容器邊界的 bytes 全走 docker CLI，不走 MCP cache lifecycle。
3. **GDrive 被當工程同步target**：除了合法的最終 PDF 交付（使用者指定 `03.aiguard/C03-EE/` 根目錄），工程中間檔也被同步到 GDrive `02_build/full_board/sch_ccm_pages/`——網路 FUSE 掛載被當工作區用（違反 scratch-to-tmp / R14 分工）。
4. 該 session 期間 bodesign 的 webdav working-cache **已完整可用**（R14.1-R14.7 全綠、61 tests、`cache_provision`/`cache_export`/`cache_close` + class-2 DAV mount），從未被呼叫過一次。

## RCA

- **起點**：session 早期為了快速 debug 引擎（pycache 陷阱、md5 核對 host↔容器），搭了 docker-exec 直驅便道；當時工程檔已在容器 /work 下，路徑依賴就此固化。
- **固化機制**：後續 20+ 輪修復棒的 dispatch prompt 逐輪複製同一套「docker exec 重產 → docker cp → cp GDrive」操作規格，orchestrator 從未回頭檢查「這條 transfer 路徑是否該走 MCP rail」。
- **分類**：axis-B（tool-selection miss）——webdav cache 工具存在且合規，是 orchestration 沒選它。與 axis-A（R14 rail 缺陷，已由前 BR 修復關閉）正交。
- **使用者已多次糾正**：fleet 層面「MCP 工作用 webdav working cache、與 agent 所在空間無關」已有多個 BR 反覆談論（location 軸 vs transfer 軸的範疇錯誤），本次是同類復發。

## 建議修復

1. **工作流遷移（本案）**：CCM 工程檔遷入 working cache——`bodesign_cache_provision(subject_id="c03-ccm", issue_webdav_credential=true)` → host rclone mount 該 DAV token 當工作資料夾 → `gen_ccm_pages.py` 與工程產物全在 cache 內迭代 → 最終 PDF `cache_export(target=GDrive 交付樹)` 或由 host 從 mount cp。GDrive 只留最終交付物落點，`02_build/` 工程同步停止。
2. **容器內部路徑撤場**：`/work/aiguard/C03-EE/` 的工程檔搬進 cache 後，容器內部副本廢棄（本就 ephemeral）。
3. **dispatch 模板修正**：後續修復棒的 prompt 規格改寫為 cache-rail 操作（provision/mount/export），不再傳播 docker exec/cp 便道。
4. **（工具層評估）**：CCM 頁面生成若常態化，評估把 gen_ccm_pages 收編為 bodesign MCP 工具（server-side compose），caller 全程只碰 cache token，杜絕 docker exec 直驅的誘因。

## 影響範圍

- 工程檔滅失風險：容器重建 = `/work/aiguard/C03-EE` 全滅（目前唯一備份是 GDrive 02_build 的手動同步副本）。
- GDrive FUSE 承受工程檔寫入流量（先前已因此觸發 write-then-read EIO 禁令）。
- 打擊半徑：orchestration 層 dispatch 模板；引擎程式碼零改動。

## 驗證手段

- 遷移後：`docker exec` 不再出現在 CCM 重產工作流；`bodesign_cache_provision`/`cache_export` 呼叫紀錄存在；GDrive 僅剩 `C03_原理圖_*.pdf` 最終交付物更新。
- 容器重建測試：重建 ee 容器後工作流可從 cache 無損恢復。

## 使用者裁決補充（2026-07-07）

> 「bodesign本身不管gdrive。那只是剛好project home在gdrive。bodesign要用webdav工作」

釘死兩層語義，修復方向以此為準：

1. **location ≠ transfer**：`C03-EE/` 交付點只是 project home 恰好在 GDrive FUSE 掛載上；對 bodesign 而言它就是 host 最終交付路徑。GDrive 不是 bodesign 的介面，不出現在任何工作流設計裡。
2. **bodesign 的唯一工作面是 webdav working cache**：工程工作（netlist、sch_ccm_pages、gen 腳本、重產中間檔）應經 `bodesign_cache_provision`(subject_id=C03-EE) → webdav mount，讓 server 在自己的 cache namespace 裡讀寫；host 只在最後把 final PDF 從 cache export/copy 到交付點。現行 `docker exec` 直鑽容器 `/work/aiguard/` 是旁路，引擎修復收斂後即遷移。
