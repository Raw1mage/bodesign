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
- **規劃**需求：把自然語言規格轉成結構化計畫（並反問釐清）。
- **生成** KiCad 符號與經 `kicad-cli` 驗證的原理圖（以參考設計為依據）。
- **佈局**（`pcbnew` 擺件＋DRC）並**匯出製造輸出**（gerber／鑽孔／pos／STEP）。
- **驗證**四層：ERC/DRC · 對照組交叉檢核 · SPICE · EMC/熱分析。
- **追蹤就緒度**，並為每個工程檔產出可讀伴隨檔（docx/pdf）與分享文件。

架構總覽：[IDEF0 功能分解](specs/product/pcb_ai_viewer/idef0.svg) ·
[GRAFCET 執行流程](specs/product/pcb_ai_viewer/grafcet.svg) · 完整規格見
[`specs/product/pcb_ai_viewer/`](specs/product/pcb_ai_viewer/README.md)。

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

## Skill 套件

bodesign 負責生成；分析／文件／模擬／採購／製造則編排成熟的 **EDA skill 套件**
（`kicad`、`kidoc`、`spice`、`emc`、`datasheets`、`bom`、distributors、fab）。可從執行中的服務在
`/skills/` 下載（整包＋個別 skill），安裝到你的 skill 目錄。

## 目錄結構

- `services/mcp/` — MCP server（`server.py`）、token 檔案儲存、requirements、skill 套件資產。
- `packages/` — 通用能力函式庫（匯入、組成、佈局、製造、BOM、驗證……）。
- `specs/product/pcb_ai_viewer/` — 設計規格（proposal／design／tasks／IDEF0／GRAFCET）。

## 可靠度邊界

交叉檢核＋SPICE/EMC 是**矽前風險層**——在打樣前抓出問題。它們**不取代**實驗室／工廠的
認證 EMC／EVT／DVT；且 bodesign 在未經確定性驗證＋明確批准前，不會輸出任何送廠檔案。
