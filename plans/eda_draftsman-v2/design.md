# Design: eda_draftsman-v2

## Context

舊 draftsman 幾何引擎（kicad_emit 2141 + composer 1529 + kicad_symbol 441 LOC）以手算座標 + 手搓 f-string S-expression 生成 schematic，經多輪症狀補丁仍四度被人工審圖打回（兩側 pin、20% 面積窄帶、label 互疊、線穿字）。使用者裁定報廢重構。偵察（ses_0c5f8c279）確認：砍除區與保留區（fidelity/render_qa/ink_metrics/BOM/footprint 保真管線）切割乾淨，單向依賴，`__init__.py` 只需替換三個 export。

## Architecture（掛在 IDEF0 骨架上）

依 idef0.json A0 分解，v2 由五個 activity 構成，模組對應：

- **A1 Resolve official symbol** — 新模組 `symbol_resolver.py`：BOM MPN → KiCad 官方庫 lib_id + pin_map；查無者產 `SymbolGap` 缺口清單（DD-1）
- **A2 Draw single pinout block** — 新模組 `block_drafter.py`（Phase 1 核心）：kiutils 物件層擺放周邊接線件，輸出獨立 `PinoutBlock`（DD-2）
- **A3 Validate pinout block** — 保留資產接線：render_qa + fidelity 雙閘 + kicad-cli render，包成 `block_qa.py` 迴路（DD-4）
- **A4 Compose sheet from blocks** — 新模組 `sheet_composer.py`（Phase 2 核心）：不可變積木 sheet-fill 排頁 + 頁間 hierarchical label（DD-3）
- **A5 Validate sheet & deliver** — 整頁雙閘 + ink_metrics 利用率門檻（DD-6）→ 人工審閱 gate → C03 交付

資料流骨架：BOM+netlist →(A1)→ ResolvedSymbol/SymbolGap →(A2)→ PinoutBlock →(A3 驗收)→ validated blocks →(A4)→ SheetPlan+整頁 sch →(A5)→ 交付頁。Phase 1 = A1–A3，Phase 2 = A4–A5，分期硬閘在 A3→A4 之間（使用者人工抽查）。

## Goals / Non-Goals

**Goals**

- Phase 1：單一 pinout 圖——官方 symbol + 周邊接線件擺放，零疊字，獨立驗收
- Phase 2：已驗收單圖排頁——sheet-fill 面積規劃，利用率機檢
- 消除手搓 sexp / 手算 symbol 幾何（kiutils 讀寫、官方庫供幾何）
- 雙機檢閘（fidelity + render_qa）前置為 TDD 紅線

**Non-Goals**

- wiring 美學最佳化（正確 + 不疊字即可）
- 舊產出 byte-level 相容
- PCB placement/routing、webdav workflow BR（獨立處理）

## Decisions

- DD-1: **Phase 1 symbol 幾何來源＝直接吃 KiCad 官方 symbol 庫。** 真 MPN 對應官方/原廠 symbol（四邊 pin 排位由專業繪圖師定好），v2 完全不生成 symbol 本體幾何，只負責周邊接線件（電源符號/label/no-connect/去耦群）的擺放與避讓。缺官方 symbol 的 MPN 誠實標缺口（no-fallback 天條），不程式生成替代。已否決：kiutils 規則生成補缺（自產幾何品質風險回鍋）、skidl（schematic 產生器實驗性質）。使用者 2026-07-07 question gate 選定。
- DD-2: **sexp 讀寫一律經 kiutils**，禁止 f-string 拼接 S-expression。kiutils 提供 .kicad_sym / .kicad_sch 的完整 dataclass 模型，座標寫入前可程式化檢查，錯誤在物件層被攔截而非渲染後人眼發現。
- DD-3: **分期硬閘（使用者裁定）**：Phase 1 單圖通過「機檢雙閘 + 人工抽查」前不得動 Phase 2；Phase 2 排頁把已驗收單圖當**不可變積木**（只平移/鏡射整塊，不得改內部幾何）。根治舊架構「單符號幾何與整頁排版混在同一條鏈、任一層錯誤都要整頁重產才可見」的迭代成本病。
- DD-4: **驗收閘前置（TDD 紅線）**：fidelity 連通分量保真閘 + render_qa SVG text-bbox 疊字閘在寫任何幾何碼**之前**先接進 v2 測試迴路，並補獨立單元測試（現況兩閘無單測）。每輪迭代 = emit → render → 機檢雙閘 → 全綠才呈人工。根治舊 session「QA 量錯層、渲染後才發現」的 RCA。
- DD-5: **對外 API 相容面最小化**：只替換 `__init__.py` 的 `emit_kicad_schematic` / `compose_schematic` / `emit_kicad_symbol` 三個 export；其餘 re-export（BOM/footprint/fidelity/render_qa/…）原封不動，MCP server 介面層不變。
- DD-6: **面積利用率為機檢規格而非事後觀感**：Phase 2 排頁引擎以 ink_metrics 量測 bbox 利用率，低於門檻（design 時定，暫訂 ≥55% 佔用可用繪圖區）即 fail，不進人工審閱。
- **DD-7**: DD-7: STM32N657 symbol 來源＝原廠 CAD 匯入（ST 官方 CAD Resources / SamacSys / SnapEDA 之 KiCad 格式），入庫記 provenance（lib_source=vendor_cad），並以 thesmart_products refs 的 authoritative ballout 交叉驗證 pin 定義。使用者 2026-07-07 gate 1.2 裁決；同輪裁決 22 筆 TBC 料立即開 BOM 定案工作（C03 層面、thesmart_products repo，與 v2 引擎開發並行）。
- **DD-8**: DD-8: render_qa 疊字閘的職責邊界＝draftsman 所畫的 peripheral 物件（net label / wire / power port），不含 vendor symbol 本體內部 pin-name↔pin-name 疊字。RCA：dense-BGA（STM32N657 VFBGA223）render_qa FAIL(138) 中 125 個為 vendor 符號自帶 223 pin-name 在密集網格互撞，符號幾何依 DD-1 逐字載入、draftsman 無權更動——閘不應量一個模組無權負責的東西。實作：qa_svg_text(path, peripheral_texts=None) opt-in scope——peripheral_texts=None 維持現行全計行為（整頁 CCM 5 頁 baseline 不回歸），block_qa 單圖 QA 傳 set(pin_map.values()) 使一對疊字只在至少一方是 draftsman label 才計違規。已否決：對高 pin 數 symbol 放寬門檻（門檻模糊化、實質容忍 symbol 內部撞字）、dense-BGA 只 gate fidelity（放棄 label 疊字檢查）。使用者 2026-07-07 question gate 選定 A。單圖驗收門檻＝fidelity PASS AND scoped-render_qa PASS。
- **DD-9**: DD-9: dense-BGA 電源網用 power-port 符號、不用文字 net label；signal net 維持文字 label 但 seed vendor pin-name/number box 進 stagger avoidance set。RCA（boundary-verified，前 subagent ses_0c5806060）：VFBGA223 上把每個電源 ball 畫成同名文字 label（24×VDD/17×GND）會擠爆 top/bottom 密集邊帶，6 次 stagger 無法分離 N 個同名 label——非幾何 bug 而是 label 母體過密；且文字 label 錨在 ey±LABEL_GAP 會落在 vendor 自帶 pin-name glyph 上（stagger 的 placed 只含 draftsman label、無 vendor pin-text 模型）。解法（KiCad 慣例、DD-1 早列電源符號為 draftsman 責任、屬完成預定實作非擴範圍）：(1) power/ground net→power:GND / power:+3V3 等 power-port 符號，同名自動連通、緊湊，溶解密度；(2) signal net 維持 LocalLabel，但把 vendor 223 pin-name/number 的 rendered box（read-only 模型、DD-1 不動 symbol 幾何）seed 進 placed 使 label 避讓。已解前置（on disk, 21 tests green）：_label_box(rotated) 軸修（單元隔離驗證 sparse 4+4 label=0 overlap）、render_qa peripheral_texts opt-in scope（DD-8）。單圖驗收門檻不變：fidelity PASS AND scoped-render_qa PASS。使用者 2026-07-07 question gate 選定 A。

## Risks / Trade-offs

- 官方庫覆蓋率不足（專用 MPN 無 symbol）— mitigation：誠實缺口清單前置產出（Phase 1 第一棒先盤 aiguard C03 全 BOM 的 symbol 覆蓋率），缺口交使用者裁決（找原廠 CAD 檔 / 換料 / 手工補繪）
- kiutils 對 KiCad 9 sexp 方言的相容性 — mitigation：選型棒先以官方庫任一 symbol 做 read→write→kicad-cli render roundtrip 驗證
- 官方 symbol 的 pin 幾何與 refs 資料 pin 對應錯位 — mitigation：fidelity 閘本來就比對連通分量，pin name/number 對映錯誤會被攔
- Phase 2 頁間連線（跨積木 net label）複雜度 — mitigation：沿用 hierarchical label 慣例，label 擺放納入 render_qa 閘

## Critical Files

- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py` — 病灶主體，Phase 1 完成後砍除
- `packages/eda-bridge/bodesign_eda_bridge/composer.py` — placement 病灶，Phase 2 完成後砍除
- `packages/eda-bridge/bodesign_eda_bridge/kicad_symbol.py` — 兩側 pin 根因，DD-1 後不再需要 symbol 生成
- `packages/eda-bridge/bodesign_eda_bridge/fidelity.py` — 保留資產，連通分量保真閘（v2 回歸基準）
- `packages/eda-bridge/bodesign_eda_bridge/render_qa.py` — 保留資產，SVG text-bbox 疊字閘（v2 驗收閘）
- `packages/eda-bridge/bodesign_eda_bridge/ink_metrics.py` — 保留資產，DD-6 利用率量測
- `packages/eda-bridge/bodesign_eda_bridge/__init__.py` — 唯一對外總線（DD-5 相容面）
