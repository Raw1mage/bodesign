# BR: E2E 實證揭露的工作流缺口五項（no-connect / 容器路徑 / wire 連接 / 環境 / 跨容器）

日期：2026-07-03
來源：validation/prd-to-gerber-e2e E2E 實證（C03+C04 全程）
嚴重度：Medium（各自獨立可修，彙整立案）

## T1 compose_schematic 不支援 no-connect 宣告（結構性）

- 現象：power-only USB-C 的 D+/D-/SBU 刻意 NC，spec 無法表達 → ERC 永遠殘留 6 個 `pin_not_connected`，「ERC clean」對含 NC 腳的板結構性達不到。
- 證據：composer.py / kicad_emit.py 全庫 grep 無 no_connect emit 路徑（僅 kicad_symbol.py 讀取端有 pin kind）。
- 修法：spec 加 `"nc": ["J1.A6", ...]`，emit `(no_connect ...)` S-expr。

## T2 工具產出落在 ee 容器內、host 不可見（工作流斷點）

- 現象：`out_dir` 傳 host 絕對路徑，實際寫進 ee 容器同名路徑（experiments/ 不在 compose mount）；每階段需手動 docker cp。
- 修法候選：experiments/ 進 compose mount（dev 模式）或工具回傳標注 `location: container|host`。

## T3 draftsman wire 連接對 >2 節點 net 不可靠

- 現象：預設 wire 連接第一輪 ERC 9 errors（GND 25 節點連成一團、net 分裂、斷連）；`connection_style=label` 才正確。
- 修法：多節點 net auto-switch 到 label，或 label 設為預設。

## T6 ee 映像缺非 headless AWT（重建即回歸）

- 現象：freerouting 需 `libawt_xawt.so`，`openjdk-21-jre-headless` 不夠；容器內已 apt 補 `openjdk-21-jre`，**rebuild 會消失**。
- 修法：`Dockerfile.ee` 改裝 `openjdk-21-jre`。

## T7 out_path 指向不存在目錄 → 回 ok 但檔案進黑洞

- 現象：寫進被健康檢查重啟抹掉的容器層；ee worker 曾連環重啟（restarts=4）。
- 修法：工具寫檔前驗目錄存在性（mkdir -p 或顯式報錯）。

## T8 render_gerber_preview 跨容器斷點

- 現象：preview 跑 core、gerbers 在 ee，需手動複製到 `/var/cache/bodesign/sessions/` 共享區。
- 修法：emit_fab 完成時自動同步 gerber 到共享區，或 preview 支援 ee 側路徑。

## 附：T4 sheet-fit 小電路過度膨脹（Low）

16 零件被 CLUSTER_GUTTER_MM=30 撐到 A2；gutter 應隨零件數縮放。

## 驗證手段

E2E LED driver 案（`experiments/e2e-led-driver/`）可全程重跑作為迴歸基準：ERC 歸零（T1 修後）、無 docker cp（T2 修後）、單輪 compose 通過（T3 修後）。

## RESOLUTION（2026-07-03，VERIFIED-CLOSED）

- **T1**：`emit_kicad_schematic()` 支援 `nc` 清單（spec `"nc": ["J1.A6", ...]` 透傳），emit `(no_connect ...)` S-expr；不可解析項 fail-fast ValueError 列全部壞項。kicad-cli 實跑驗證 ERC=0。
- **T2**：`docker-compose.dev.yml` 全 service 補 `./experiments:/work/experiments` mount。
- **T3**：draftsman 預設下 ≥3 節點 net 逐 net 走 label（`reason="multi-node"`），2 節點仍 wire；caller 顯式 `connection_style` 照舊尊重。emit 端新增 `label_nets` override，統計與實際 emission 不漂移。
- **T4**：`_cluster_gutter_mm(n)` 確定性階梯（≤20→12、≤50→20、>50→30），16 零件不再膨脹到 A2；`CLUSTER_GUTTER_MM=30` 保留為上限。
- **T6**：`Dockerfile.ee` `default-jre`（full AWT），commit 85d36e0。
- **T7**：`_ensure_parent_dir()` 統一 6 個寫檔出口（routing.py）。
- **T8**：`emit_fab_outputs()` 完成後自動複製到 `$BODESIGN_SESSIONS_ROOT/fab/<basename>/`，回傳 `shared_copy`/`shared_copy_reason` 顯式欄位（env 未設＝None+reason，非 fallback）。
- 驗證：目標模組 26/26 綠；全套 768 tests 僅既有 5 失敗（c02 discover 匯入、host 缺 httpx、tool count 44≠43 屬未 commit atopile 註冊）。
