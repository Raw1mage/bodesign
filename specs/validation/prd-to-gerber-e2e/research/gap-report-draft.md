# E2E 實證缺口報告（完整版 — PRD→Gerber 全程走通）

案件：USB 5V LED driver 小板（16 零件 10 net），compose 路徑 PRD→Gerber 全程實跑。
Plan：`plans/validation_prd-to-gerber-e2e/`（research profile）。

## 1. 已證實的缺口

### G4 vault 冷啟動（已證實）
- `AL5809-060`（PRD 首選 2-pin CC regulator）vault 查詢 → `status: absent`，依天條 fail-fast 降級為 resistor-set 方案。
- 衍生風險：140R 鎮流值假設白光 LED Vf≈3.0V 為泛用典型值、非 datasheet 錨定；C06 驗證前必須 ingest 實際 LED datasheet，否則 60mA±10% 目標無證據。
- 結論：vault 無批次 ingest、外抓被 approval gate 擋 → 冷啟動需使用者供檔，流程上應在 C00 結束時就列出「須供 datasheet 清單」。

### 工具缺口 T1：compose_schematic 不支援 no-connect（C03 發現，結構性）
- power-only USB-C 的 D+/D-/SBU 刻意 NC，但 spec 無法宣告 → ERC 永遠殘留 6 errors，「ERC clean」目標對含 NC 腳的板結構性達不到。
- 修法：spec 加 `"nc": ["J1.A6", ...]`，emit `(no_connect ...)` S-expr。composer.py/kicad_emit.py 目前無 emit 路徑。

### 工具缺口 T2：產出落在 ee container 內、host 不可見（工作流斷點）
- `out_dir` 傳 host 絕對路徑，實際寫進 ee container 同名路徑（experiments/ 不在 compose mount）。
- 每階段都要手動 `docker cp` 取回；跨階段工具鏈讀輸入時要用 container 側路徑。
- 修法候選：experiments/ 加進 compose mount，或工具回傳時標注 `location: container|host`。

### 工具缺口 T3：draftsman wire 連接對 >2 節點 net 不可靠
- 第一輪 compose 用預設 wire 連接 → ERC 9 errors（GND 25 節點連成一團、net 分裂、斷連）。
- `connection_style=label` 後才正確。label 應成為多節點 net 的安全預設（或 auto-switch）。

### 工具缺口 T4：sheet-fit 對小電路過度膨脹
- 16 零件被 CLUSTER_GUTTER_MM=30 固定值撐到 A2（content bbox 218×360mm），可讀性反降。
- 修法：gutter 隨零件數/cluster 數縮放。

### G3 擺件品質基線（已量測，C04 實跑）
- grid placement（8mm 網格排排站）：C1(100nF) 距 LED 負載群 >30mm、decap 迴路面積大（違 R1/R8）；USB-C 與 M3 孔 courtyard 相撞；零電氣感知。
- freerouting v1.9.0：1.92s 完成＋優化 7.81s（改善 ~51.79%），99 segments + 4 vias，`unconnected=0` → **佈通率 100%**。誠實評註：小板全佈通靠板小，品質輸給規則。
- DRC：`** Found 1 DRC violations **` — `[courtyards_overlap] J1 × H2`（grid 把 M3 孔排進 USB-C courtyard）；copper=1 / unconnected=0 / silk=0。
- 結論：**pre-placement 工具立案證據已足**（本輪徵集的 workflow.preplacement-deterministic 直接對位）。

### 工具缺口 T5：autoroute 假成功面（C04 發現，含已修 bug）
- **[已熱修] `net2pcb_board` 不設 Reference → 全板 REF\*\* → `ExportSpecctraDSN` 靜默回 False → `routed:true, segments:0` 假成功**。修於 `routing.py:116` 加 `fp.SetReference(ref)`（host 源碼已改、未 commit；ee 容器已熱修）。
- `subprocess.run(capture_output=True)` 不驗 returncode/SES 存在性，freerouting 崩潰被吞。
- 修法：DSN export False / SES 缺失 → fail-fast 顯式報錯（天條對齊）。

### 環境缺口 T6：ee 映像缺非 headless AWT
- freerouting 需 `libawt_xawt.so`，`openjdk-21-jre-headless` 不夠；容器內已 apt 補 `openjdk-21-jre`，**重建會消失，需進 Dockerfile.ee**。

### 工具缺口 T7：`out_path` 指向不存在目錄 → 回 ok 但檔案進黑洞
- 寫進被健康檢查重啟抹掉的容器層；ee worker 曾因此連環重啟（restarts=4）。目錄需先 mkdir -p；工具應驗證目錄存在性。

### 工具缺口 T8：render_gerber_preview 跨容器斷點
- preview 跑在 core、gerbers 在 ee，需手動複製到 `/var/cache/bodesign/sessions/` 共享區才渲得出。

## 2. 知識徵集成果 → 工具設計路線

三路徵集已沉澱 ragbase（plan scope：1 workflow + 3 concept + 3 source/asset/extract 鏈）：

1. **確定性 pre-placement 工具（G3 正解，優先級最高）**
   - 骨架：arXiv 2602.23540 去 RL 化（主 IC 錨定＋pin 歸屬先驗＋環帶格點貪婪＋固定 seed SA）。
   - 生成規則：專利 R2/R3/R7（decap 背面對置/專屬 ground via/多 via）；擺後檢查 R1/R8。
   - 替代/加速路徑：KiCad-Autoplace（MIT）1 天 spike 實測 vs grid 基線。
2. **PDN/decap checker（OSS 空白，自研）**
   - 規則源：R1-R8＋arXiv 2305.01540 目標阻抗法；照 analyze_emc 模式落 ee worker。
3. **length_match_bus 升級（改造成本最低）**
   - 蛇形段 ≥3W 間距＋均勻分佈（2407.19195＋1705.04984）。

## 3. Friction 記錄（工具層，收尾時掃描成 BR）

- producer.ts `ragbase_ingest_source` 參數名不一致：schema 要 `name` 但慣用 `title`；`ragbase_distill` 要 `id`+`title`（`name` 不通用）＋confidence enum 是 `verified|partial|inferred|todo`（非 `confirmed`）——三次 invalid_args 試錯才通。
- gate.ts `ragbase_query` 對中文 token（「徵集」）query 回 0 hits，但列直查有資料——FTS 中文斷詞疑似無效，待驗證後發 BR。
- subagent 工具池無 websearch/codesearch（GitHub 線改用 GitHub API webfetch 繞過，屬軸 B 提示層可補）。
