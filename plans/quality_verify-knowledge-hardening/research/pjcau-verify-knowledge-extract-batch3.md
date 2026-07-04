# pjcau PCB verify 知識萃取 batch3（送廠對位 · 跨域一致性 · bring-up 測試）

> 來源：`pjcau/esp32-emu-turbo` `.claude/skills/`（jlcpcb-check / jlcpcb-alignment / pcb-to-firmware / firmware-sync / hardware-test-gen / pad-analysis / jlcpcb-validate），2026-07-03 爬取。
> 法律邊界同前批：只萃通用工程方法論 + 公開製造慣例/廠家參數數值；**剝除 project-specific 硬編**（GPIO 號、具體零件型號、+3.62mm 等 ESP32 專屬位置修正值只當「correction 存在性」的例子，不當通用值）。標來源錨點。
> 定位：累積知識庫（repo scope，不綁 plan），統合規劃實作 plan 的輸入。

## 1. CPL / Pick-and-Place 對位驗證（送廠 gate，bodesign 完全空白，HIGH）

pjcau `jlcpcb-check`（單元件診斷）+ `jlcpcb-alignment`（批次 gate）教「貼片機會不會把元件擺對」——bodesign 目前只做 pin→net，完全沒碰 fab 廠 CPL 旋轉慣例。

**JLCPCB 底面元件旋轉慣例（通用製造慣例，可萃）**：
- 底面（bottom-side）元件，JLCPCB 貼片機套用：(1) **Y-mirror**（負 X，從底面看）→ (2) **CW 旋轉** by CPL 旋轉角。
- 一般公式：`rot = (rot - 180) % 360`（mirror 修正）→ `rot = (rot + correction) % 360`（per-footprint 修正）。
- **per-footprint 旋轉修正是普遍現象**：EasyEDA/LCSC 3D model 的 pin1 方向與 KiCad footprint 慣例常差一個固定角，需一張 per-package 修正表（SOP/SOIC、SOT-23、ESOP、SOT-223 等各有固定修正）。具體角度值依零件庫版本，checker 應建可查表而非寫死。

**三重檢核 gate（方法論，套任何板）**：
1. **CPL 旋轉一致性**：對每個 pin，比對 `rotate(cpl_rot)→mirror_X→translate` vs `rotate(kicad_rot)→mirror_X→translate`，每 pin 誤差 < **0.1mm** 才 PASS。關鍵技巧：**用 board_pos 而非 cpl_pos 做平移**，以隔離「旋轉檢查」與「位置修正檢查」（兩者分開才能定位是哪個錯）。
2. **CPL 位置修正存在性**：驗 `cpl_pos == board_pos + correction`，抓錯的/缺的修正。
3. **pin-net 一致性**：驗每個已佈線 pin 的 net 符合期望——**抓旋轉/mirror bug 導致的 pin swap**（旋轉錯會讓 pin 對到隔壁 net）。

**風險類型（可萃的判斷經驗）**：exposed pad（ESOP）、tab pad（SOT-223）、asymmetric shield pad（連接器/SD 座）是對位高風險——不對稱封裝旋轉錯不易目視發現，靠 pin-net 一致性檢核才抓得到。

**對位 bodesign**：C04/送廠前的 CPL gate 是 DFA（batch2）之外的獨立維度——DFA 檢查極性，這個檢查**旋轉+鏡射+位置**三重對位。bodesign forward-design 產 CPL 時必須過這關才能宣稱可送廠 PCBA。

## 2. firmware ↔ PCB 跨域 SSOT 一致性仲裁（跨邊界，HIGH）

pjcau `pcb-to-firmware`（主，四源仲裁）+ `firmware-sync`（子集，GPIO 兩源比對）——bodesign 的 pin→net SSOT（batch1）只在 PCB 內部，這是**跨 PCB/firmware 邊界**的一致性判斷。

**多源真值表 + master 仲裁（方法論，剝除 project GPIO 號）**：
- 指定一個 **MASTER source of truth**（pjcau 用 GPIO_NETS 設定檔），其餘源（firmware header、datasheet pin specs、routing）都對它對帳。
- 建**跨源比對表**：每個 signal 一列，各源一欄，標 OK / MISMATCH。
- MISMATCH 時：(1) master 為準；(2) 分析**級聯影響**（改一個 GPIO 會波及 firmware 行為、PCB 佈線、docs、按鈕遮罩 BTN_MASK / 組合鍵定義等衍生常數）。

**跨源一致性測項（通用類型）**：
- signal ↔ 各源 pin 映射三源一致（firmware vs 設定 vs datasheet）。
- 重複指派偵測（同一實體 pin 綁多 signal）。
- 新增 signal 在某源缺漏偵測（master 有、下游缺）。

**對位 bodesign**：這是「設計意圖跨越載體邊界不漂移」的判斷。bodesign 若要支援「PRD → 原理圖 → PCB → 韌體腳位表」全鏈，需要這種多源仲裁；即使暫不做韌體，「IR（master）vs 原理圖 vs netlist vs BOM」的仲裁模式完全同構——是 batch2 「5 源對抗交叉檢核」的**仲裁機制補完**（對抗檢核找出不一致，仲裁決定誰對 + 級聯修正範圍）。

## 3. 組裝後 bring-up 硬體測試生成（全新維度，HIGH）

pjcau `hardware-test-gen`：從腳位定義生成可執行 Unity 測試韌體，做 PCBA **組裝後驗證**——bodesign 完全沒有的維度（bodesign 驗證止於送廠前的 gerber/DRC，不碰「板子焊出來會不會動」）。

**通用 bring-up 測項模式庫（剝除 project 腳位，留測試模式）**：
| 測試模式 | 方法 | 抓什麼 |
|---|---|---|
| **idle-HIGH 按鈕測** | 內部上拉，讀 idle 應為 HIGH | 按鈕焊接/短路/上拉缺失 |
| **walking-1 短路偵測** | 對匯流排（如 LCD D0-D7）逐位拉高、其餘應為低 | 相鄰腳橋接短路 |
| **bus toggle 測** | 控制腳（CS/RST/DC/WR）toggle 讀回 | 控制線斷連 |
| **bus probe** | SPI CMD0 / I2C 位址 probe | 週邊初始化/連接 |
| **靜音/pattern 測** | I2S PDM TX 靜音、記憶體 XOR pattern 寫讀 | 訊號完整性/記憶體位元錯 |
| **電源軌 ADC sanity** | 內部 ADC 量電源軌電壓在容差內 | 供電偏移 |
| **視覺測（CI skip）** | LED blink 人眼確認 | 標記為 IGNORE 不進自動判斷 |

**方法論核心**：把 **netlist/腳位表 → 自動生成可執行測項**。walking-1 是無外接儀器就能測相鄰腳短路的經典手法；電源軌 ADC sanity 用晶片自身資源自檢。

**對位 bodesign**：這是「展示可靠度」哲學延伸到**實體板**——bodesign 現在展示的是設計期確定性（DRC/SPICE/crosscheck），這補上「組裝後可執行驗證」。是 DVT/bring-up 階段的知識，屬 bodesign roadmap 遠期但獨特的維度。

## 4. （MED 增補既有物件）幾何假陽性過濾 + trace-through-unnetted-pad

併入 batch2 `control.geometry.fab-short-gates`：

- **同 net 假陽性過濾準則**（`pad-analysis` 核心）：pad 間距檢查會報**所有**近距對，但多數是刻意的——trace 連到它的目標 pad = 同 net（OK）；via 貼著它連接的 pad = 同 net（OK）。**只有不同 net 且 gap < 閾值才是真違規**。行動前必須先按 net 過濾。這是所有幾何 gate 的共通判斷準則（對位 batch2 「per-net 連通」的反面：同 net 該連、不同 net 該離）。
- **雙帶閾值**：不同 net gap < 0.10mm = DANGER（JLCPCB 拒收）；0.10-0.15mm = WARNING（可能觸發 DFM alert）。
- **trace-through-unnetted-pad 特定短路模式**（`release-prep` gate）：有 net 的 trace 物理穿過**無 net** 的 pad = 真短路，但 **DFM 與 DRC 都抓不到**（DFM 看製造規則、DRC 看已知 net 關係，都不檢查「trace 壓過無 net pad」）——是雙盲短路類，根因通常是 pad-net 初始化缺項。必須專屬 gate。

## 5. （MED 增補既有物件）JLCPCB DFM 閾值補數值 + 硬限/最佳實踐分層

併入 batch1 `control.dfm.jlcpcb-ipc-thresholds`：

- **補充數值**（`jlcpcb-validate`，公開廠家參數）：drill increment 0.05mm（孔徑須為此倍數）；via aspect ratio ≤ 10:1（孔深:孔徑）；copper sliver < 0.1mm（細銅絲有剝離風險）；silk 字高 ≥ 1.0mm；7 層 gerber 完整性（缺層 = 送廠失敗）；annular ring 絕對最小 0.075mm。
- **分層判斷準則**：**failure = 硬製造限**（廠會拒收）vs **warning = 最佳實踐**（可製但次佳）。checker 輸出必須分這兩級，不可混為一談——對位 bodesign 天條「fail-fast」但需區分「阻塞級」與「建議級」。
- **驗證編排順序**（`jlcpcb-validate` + `verify` 主流程）：DFM → DFA → datasheet 物理 → DRC → connectivity → schematic sync → short circuit，各層獨立且有序；JLCPCB 專屬檢查是 core `/verify` 之上的**額外一層**，不取代。
