# bodesign

_語言：**繁體中文** · [English](./README.en.md)_

**bodesign** 是一個 AI 電路設計（PCB）副駕，以**獨立的 MCP server** 形式交付。
它由對談與原始輸入檔驅動，走完整個 KiCad 設計生命週期——原理圖 → 佈局 → 製造——
產出可送廠的文件包，並以**展示**可靠度（對照已知良品的交叉檢核＋KiCad/SPICE/EMC）
而非「宣稱」可靠度。

它**與宿主無關、可獨立對外營運**：任何支援 MCP 的客戶端（IDE、agent，或你自己的 HTTP 呼叫端）
都能透過 Unix socket（本機）或 TCP port（對外）驅動它。**不需要任何宿主外殼或閘道。**

## 它做什麼

- **匯入**整個專案資料夾（datasheet、原理圖、BOM、Gerber），唯讀。
- **規劃**需求：把自然語言規格轉成結構化計畫（並反問釐清），並把 C00 PRD 產出為**帶樣式的
  .docx**——重現真實 Rockbox C07-PRD Word 架構（封面＋改版紀錄表＋12 章＋章節內表格），範本以
  `.dotx` + JSON 架構描述預存在 server 端供重複使用。
- **生成** KiCad 符號與經 `kicad-cli` 驗證的原理圖（以參考設計為依據）。
- **佈局**（`pcbnew` 擺件＋DRC）並**匯出製造輸出**（gerber／鑽孔／pos／STEP）。
- **驗證**四層：ERC/DRC · 對照組交叉檢核 · SPICE · EMC/熱分析；其中對照組交叉檢核由
  **確定性參考比對器**（G7：純 Python Hungarian 配對＋Dice/屬性/連接性加權）執行，SPICE 以
  **datasheet 接地的 model 卡**（每筆參數帶 page-anchor 證據）取代泛用預設模型。
- **追蹤就緒度**，並為每個工程檔產出可讀伴隨檔（docx/pdf）與分享文件。所有「可靠度」皆以
  **可重現的確定性證據展示**（LLM 只負責上游抽取／裁決，驗證與比對全程不參與）。

## 架構圖

完整規格見 [`specs/product/pcb_ai_viewer/`](specs/product/pcb_ai_viewer/README.md)。

**IDEF0 功能分解（A0）**

![IDEF0 功能分解](specs/product/pcb_ai_viewer/idef0.svg)

**GRAFCET 執行流程（生成迴圈）**

![GRAFCET 執行流程](specs/product/pcb_ai_viewer/grafcet.svg)

## 執行

**Docker（可攜，建議）** — 內含 KiCad 9（`kicad-cli` + `pcbnew`）＋ LibreOffice ＋整套工具鏈：

```bash
./mcpctl.sh start     # 建置映像＋啟動容器（UDS 於 ./.run/bodesign.sock + TCP :8077）
./mcpctl.sh status    # 健康檢查＋socket
./mcpctl.sh log       # 追蹤日誌
./mcpctl.sh stop
```

**主機（不用 Docker）** — 需要 PATH 上有 `kicad-cli`、`pcbnew`、`soffice`、`ngspice`：

```bash
pip install -r services/mcp/requirements.txt
python services/mcp/server.py --transport http --uds .run/bodesign.sock --port 8077
# 或 --transport stdio 供 IDE/agent 直接使用
```

## 連線（MCP）

MCP **Streamable HTTP**，由同一個行程同時提供 UDS（本機）與 TCP（對外）：

- 本機：`unix:///…/.run/bodesign.sock:/mcp/`
- 對外：`http://<host>:8077/mcp/`

註冊資訊見 [`mcp.json`](mcp.json)。開啟 `/`（或 `http://<host>:8077/`）即是即時的自我說明指南——
安裝、檔案模型、電路設計工作流，以及 `/tools`、`/tools/{name}` 的完整 tool-call schema。

## 檔案模型（docxmcp 風格）

bodesign **不內含任何工作資料**。把專案樹以 tarball 上傳 → 取得 **token**；將 token 傳給任一工具
（路徑參數會在 token 的 `doc_dir` 內解析）；以 token 下載產出檔。伺服端的工作資料會依 TTL 自動垃圾回收。
工具也接受一般的主機路徑（本機使用）。

```bash
tar -C myproject -cf - . | curl --unix-socket .run/bodesign.sock \
     -X POST -H 'Content-Type: application/x-tar' --data-binary @- http://bd/files
curl --unix-socket .run/bodesign.sock http://bd/files/{token}/blob/{rel}
```

## Skill 配對

bodesign（MCP）是**生成的那一半**；配套的 **`bodesign` skill** 是工作流大腦（C00–C07 生命週期、
誠實契約、各階段 SOP），**並且**承載分析／文件引擎——`kicad`（原理圖／PCB／Gerber 分析）與
`kidoc`（工程文件）現在以 `engines/kicad`、`engines/kidoc` 的形式住在那裡，所以請安裝 `bodesign`
skill，而非獨立的 `kicad`／`kidoc`。分工是雙向的：skill 驅動本 MCP 的 `bodesign_*` 工具來**生成**，
而 MCP 的驗證工具（`bodesign_simulate`／`analyze_emc`／`analyze_thermal`）回頭呼叫 skill 的引擎來
**分析**（透過 `BODESIGN_KICAD_SKILL` 解析，預設 `~/.claude/skills/bodesign/engines/kicad`）。

其餘成熟的模擬／採購／製造 EDA skill（`spice`、`emc`、`datasheets`、`bom`、distributors、fab），
連同獨立的 `kicad`／`kidoc`（legacy，已併入 `bodesign` skill），都可從執行中的服務在 `/skills/`
下載（整包＋個別 skill），安裝到你的 skill 目錄。

skill 在執行層之上再加一層**設計判斷**（各階段的 reference：C01 reduction-lens＋Ashby 選材、
C02 DFM/DFA/IP 密封＋幾何作圖迴圈、C03 EE advisory＋「腳位→電路」合成法、C04 stackup/HDI/SI）。
跨站不收斂（面積／散熱／高度 budget、C06 verdict fail）會以既有 `BlockerReturn` **回饋**到負責的
階段並擋住下游完成（遞迴自我修正）。一開始就用**可行性 triage** 從 C00 估算分級(Tier 1 可直接
投板／2 需人類 SI 簽核／3 HDI 級交專業 EDA)，讓「給 C00，得 C01–C04」對每個產品**誠實**；
Tier-3 由 `emit_si_constraint_export` 產出中性 SI 約束包（JSON＋CSV＋逐工具對應），把繞線硬牆變成
乾淨交接而非斷點。

## 目錄結構

```text
bodesign/
├── services/mcp/                 MCP server —— 產品的唯一對外介面
│   ├── server.py                 工具分派、token 路徑解析、UDS+TCP 雙綁定、自我說明網頁
│   ├── token_store.py            docxmcp 式 token 檔案儲存 ＋ TTL/GC
│   ├── requirements.txt
│   └── assets/skills/            EDA skill 套件（13 個 tarball ＋整包 bundle ＋ MANIFEST.md）
├── packages/                     通用能力函式庫（無產品專屬碼）
│   ├── shared/                   共用契約 ＋ data_root()（程式↔工作資料隔離邊界）
│   ├── design-ir/                DesignIntent 等中介表示（IR）；compare/ 子模組＝確定性
│   │                             參考比對器（G7：純 Python Hungarian＋Dice/屬性/連接性加權＋FlexiblePin）
│   ├── component-kb/             可重用零件知識（datasheet 萃取）；spice_card.py＝datasheet 接地
│   │                             SPICE model 卡（vault L4 → cascade tier-1，確定性、byte-identical）
│   ├── doc-core/                 pin-table／文件產生工具
│   ├── source-core/              來源／證據契約
│   ├── reverse-core/             專案匯入、伴隨檔渲染、文件輸出、board 重建
│   ├── gerber-core/              Gerber／鑽孔解析 ＋ 預覽
│   ├── eda-bridge/               KiCad 橋接：符號／原理圖／佈局／製造／BOM／SPICE／EMC；
│   │                             simulate 標注 model_source（vault-grounded｜generic-default）
│   ├── workflow-core/            需求規劃、證據蒐集、就緒度羅盤、對照組交叉檢核、
│   │                             可行性 triage（C04 交付分級）、跨站對帳閘、SI 約束交接；
│   │                             驗證紀律 G1–G7（需求契約／設計審查閘／crosscheck＋root-cause／
│   │                             ValidationEvidence 回流／workflow plan 衍生）
│   ├── storage-core/             客戶自有專案登錄
│   └── kicad-plugin/             in-KiCad Action Plugin 契約（roadmap）
├── specs/                        規格／知識庫（plan-builder）
│   ├── architecture.md           跨領域架構索引
│   ├── product/pcb_ai_viewer/    已上線（living）產品設計規格 ＋ IDEF0/GRAFCET SVG ＋ 中文 README
│   ├── feature/eda-mcp-toolchain/  已上線（living）C04 EDA 工具鏈規格（routing/finishing MCP 工具）
│   ├── workflow/verification-discipline/  已上線（living）參考優先驗證紀律規格（G1–G7）
│   └── knowledge/datasheet-spice-models/  已上線（living）datasheet 接地 SPICE model 卡規格
├── tests/                        測試（乾淨 clone 全綠；資料相依測試自動跳過）
├── Dockerfile · docker-compose.yml · mcpctl.sh   容器封裝 ＋ 操作
├── mcp.json                      MCP 註冊資訊
└── README.md · README.en.md      本文件（繁中／英）
```

> bodesign **不內含任何工作資料**；客戶專案樹只在執行期經 token 儲存進入，或由外部 `data_root()`（`BODESIGN_DATA_DIR`）讀取。

## 可靠度邊界

交叉檢核＋SPICE/EMC 是**矽前風險層**——在打樣前抓出問題。它們**不取代**實驗室／工廠的
認證 EMC／EVT／DVT；且 bodesign 在未經確定性驗證＋明確批准前，不會輸出任何送廠檔案。
