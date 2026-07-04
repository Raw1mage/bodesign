# pjcau PCB verify 知識萃取 batch2（審計哲學 · 對抗式交叉檢核 · 失效分類）

> 來源：`pjcau/esp32-emu-turbo` `.claude/skills/`（hardware-audit / design-intent / verify / dfm-test），2026-07-03 爬取。
> 法律邊界同 batch1：知識萃取重寫（非複製 code），限公開工程方法論；標來源錨點。
> 定位：累積知識庫（repo scope，不綁 plan 生命週期），最後統合規劃實作 plan 的輸入。

## 1. 兩層審計哲學（對齊 bodesign 天條，最高價值）

pjcau `hardware-audit` 的核心方法論——一次完整硬體審計**必須兩層都跑，且順序不可顛倒**：

- **Layer 1 — 自動化幾何/電氣 gate（先跑，HARD BLOCK）**：客觀的幾何、電氣、跨源檢查。LLM 無法靠讀原理圖發現「0.02mm trace 穿過 pad 的重疊」——這類 bug 活在 cache 幾何裡，不在文字裡。必須跑真腳本對 parsed `.kicad_pcb`。**任一 gate 失敗就停，先修再進 Layer 2**——一塊有幾何短路/斷電源鏈/漂移原理圖的板，不值得用文字審。
- **Layer 2 — 逐域文字推理（後跑）**：用 datasheet/原理圖/firmware 對每個功能域做文字 review。這是 LLM 擅長的：抓邏輯矛盾、選錯零件、pinout 不符、boot 時序、文件與 code 的歧義。

**歷史教訓（可萃取的血淚）**：早期 R1-R4 輪審計只跑 Layer 2，從沒抓到 v3.3 的 trace-through-pad 回歸——因為 bug 在 cache 幾何不在文字。Layer 1 是事後補上才堵住缺口。

**對位 bodesign**：這正是 bodesign 核心哲學的獨立印證——「**確定性驗證先於 LLM 裁決**」「LLM 只做上游抽取/裁決，驗證比對零 LLM」。bodesign 已有 G7 crosscheck / DRC gate（≈Layer 1），但缺「Layer 1 全綠才准進 Layer 2」的**強制順序 gate**與「幾何 bug 活在 cache 不在文字」的自覺。這是 C06 審計流程該內建的紀律。

## 2. 對抗式 5 源交叉檢核（design-intent adversary）

pjcau `design-intent` 當「魔鬼代言人」：把每個 GPIO/device/net/連接映射出來，跨**所有設計來源**獵殺不一致、孤兒 net、遺失訊號路徑、邏輯錯誤。

**5 個交叉檢核來源**（單一真相來源彼此對帳）：
1. firmware GPIO 定義（`board_config.h`）
2. 原理圖生成器 GPIO 映射（`config.py`）
3. datasheet pin→net specs（`datasheet_specs.py`）
4. PCB cache（從 `.kicad_pcb` parse 的實際 net/pad）
5. BOM/CPL 製造檔

**18 類對抗檢查（方法論，可套用任何板）**：
| 類 | 檢查 | 抓什麼 |
|---|---|---|
| GPIO 一致性 | firmware vs 原理圖 vs datasheet 三源 pin 映射 | 同一 pin 三處定義不符 |
| 重複 GPIO | 同 GPIO# 指派給多訊號 | 資源衝突 |
| 訊號端點 | GPIO 訊號是否抵達目標零件 | 斷在半路 |
| **孤兒 net** | net 只連 0-1 個 pad | 遺失連接 |
| **電源鏈走查** | VBUS→PMIC→+5V→LDO→+3V3→所有 VDD pin 全鏈 | 供電斷鏈 |
| GND 完整性 | 零件缺地連接 | 浮地 |
| 按鈕電路 | 按鈕 GPIO 缺開關或 MCU 連接 | 電路不完整 |
| pin 能力 | GPIO 用於不支援功能（保留給 PSRAM 等） | 誤用保留腳 |
| strapping pin | boot pin（GPIO0/3/45/46）衝突風險 | 開不了機 |
| 跨零件 net | 期望的零件↔零件 net 是否真連 | 預期連接落空 |
| 各功能鏈完整 | display/audio/SD/USB 全路徑（含 ESD→series R→MCU） | 鏈路缺件 |
| net 命名 | typo、大小寫衝突、可疑 auto-name | 命名漂移 |

**對位 bodesign**：`concept.pin-net-ssot-verification`（batch1）是單源逐腳驗證；這個是**多源對帳**——bodesign 的 forward-design 從 datasheet/reference design 組 IR，正需要「IR vs 原理圖 vs netlist vs BOM」的對抗式對帳來抓組裝漂移。孤兒 net 檢查、電源鏈走查是純圖論確定性檢查，零 LLM 可實作。

## 3. Fab-short gate 家族（幾何短路檢查，Layer 1 核心）

pjcau Layer 1 的具體 gate（KiCad DRC **看不到**的物理短路類，因 `.kicad_dru` 調到 0.09mm 絕對最小值）：

| gate | 方法 | 抓什麼（KiCad DRC 漏的） |
|---|---|---|
| trace-through-pad | netted trace 物理穿過 unnetted pad（F.Cu+B.Cu） | v3.3 回歸類幾何短路 |
| trace-crossings | 同銅層不同 net 的兩 trace capsule 重疊 | trace-vs-pad gate 看不到的 trace-vs-trace 橋接 |
| **copper-clearance** | Shapely polygon：每銅層合併同 net feature，量每對不同 net 的最小 polygon 距離 | <0.10mm=DANGER，0.10-0.15mm=WARN。抓 KiCad DRC 漏的 0.11-0.145mm gap |
| per-net copper connectivity | 走每 net 銅圖，斷言每 net 是單一連通分量 | pad-net label 對但銅碎裂（浮島、去耦浮空、上拉斷連） |

**JLCDFM 視角洞見（重要製造知識）**：JLCDFM 量的是 **mask-aperture 到 mask-aperture** 距離，每側減 ~0.05mm mask expansion——所以 0.110mm 的 copper-edge gap 在 JLCDFM 視角變 ~0.010mm 被標 Danger。checker 若只看 copper-edge 會漏這類。這是「銅間距 vs 阻焊開窗間距」的關鍵區別。

**對位 bodesign**：bodesign gerber-core 已 parse RS-274X 幾何、有 pygerber。這組 shapely polygon 最小距離 + per-net 連通圖走查是**確定性幾何短路檢查**的成熟方法論，對位 bodesign 「幾何短路活在 cache 不在文字」缺口——是 C05/C06 幾何驗證 checker 的直接藍圖。

## 4. 驗證失效分類法（failure taxonomy，debug 加速）

pjcau `verify/failure-categories.md`：驗證失敗的 8 分類 + 根因定位表——把「驗證報 fail」快速歸因，不盲修：

| 類 | 徵象 | 根因定位/處置 |
|---|---|---|
| **DFM violation** | pad 間距、trace 間距、mask bridge | 修生成器（擺件/佈線參數） |
| **DFA violation** | 缺 fiducial、方向錯、ref-des 錯 | 修生成器 |
| **DRC error** | 間距、未連 net、短路 | 修佈線/擺件 |
| **Script bug** | Python exception、parse error | 修腳本本身 |
| **Regression** | 曾過現在 fail | git diff 找變更，必要時 revert |
| **False positive** | 同 net 重疊、刻意設計 | 加已知例外或調閾值（對位 batch1 no-connect 刻意NC） |
| **Environment** | toolchain/容器不可用 | 修環境（對位 bodesign T6 ee 缺 AWT / T2 跨容器） |
| **Stale cache** | 結果與現況不符 | 刪 cache 重生（對位 bodesign cache disposable 天條） |

**對位 bodesign**：這是 checker 失敗後的**分診方法論**——bodesign 天條「fail-fast + 缺項清單」需要這層歸因才不會盲修。False-positive 類直接對位 batch1 的「分辨意圖 vs 缺陷」；Environment/Stale-cache 類對位 bodesign 已實測的 T2/T6/T7/T8 跨容器 friction。可蒸成 debug 分診的 failure-mode 知識。

## 5. DFA（可組裝性）維度（bodesign 幾乎空白）

pjcau `dfm-test` 的 DFA（Design for Assembly）9 檢查——bodesign C04/送廠前的空白：
- BOM：檔存在、零件數、料號齊
- CPL：檔存在、位置、旋轉
- **極性**：極性敏感零件（二極體/電解電容/IC pin1）方向正確

**baseline 管理洞見**：密集區的固有 violation 用 baseline 追蹤（如 drill-trace=71、trace-pad=140）——佈線改動**減少**就降 baseline，**增加**就先查回歸再決定是否抬。這是「已知固有 vs 新回歸」的區分紀律，比純閾值更務實。對位 bodesign fixture-driven 回歸測試哲學。
