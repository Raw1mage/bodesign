# C03 深度診斷報告：設計能力邊界 vs 知識缺口

> 產出於使用者兩問：(Q1) 串接 KB 是改 ragbase 還是 opencms？(Q2) C03 真的展現出「多晶片共板 + 輔助被動件/RC/LC/分壓/功能電路推導」的設計能力嗎？
> 方法：實證讀 C03 stage guide、pinout-to-circuit method、KiCad analyzer 分析方法、compose/ato 契約、`bodesign_kb_query` 實測命中；不憑印象。

## 摘要（一句話）

**功能不缺、知識層有真實缺口，但更深的缺口不是「知識」而是「設計合成能力」——而後者是 bodesign 哲學刻意排除 LLM 的地方。** 使用者的觀察成立：C03 目前能*校驗*一張已存在的電路圖，但沒有一個確定性、非幻覺的機制能*從一組晶片合成*出帶正確輔助被動件的完整功能電路；那一步目前**完全落在 LLM 的 reasoning 上**，而系統其餘部分都刻意不信任 LLM。

---

## Q1：串接 KB 改哪裡？→ 改 ragbase，opencms 完全不涉入（已查證）

證據（`services/mcp/server.py`）：
- `bodesign_kb_query` / `kb_get` 是 **read-only 服務**，直讀 `<repo>/.specbase/ragbase.sqlite`（FTS5 trigram，L820-837、L908-969）。
- 寫入端在 **host-side 的 specbase producer**（`producer.ts ragbase_distill`，L821、_KB_REMEDY L834-837）。bodesign MCP 只讀不寫。
- **opencms 早已被移除**：git log `commit: README: standalone externally-operated MCP (drop opencms + stale scaffold)`；`implementation-spec.md` 明載 opencms 只是「optional integration, not the product boundary」。

**結論**：這不是「改哪個系統」的二選一，是一條 pipeline 缺一段執行：
```
萃取檔(disk) ──[缺: producer.ts ragbase_ingest/distill 執行]──▶ .specbase/ragbase.sqlite ──▶ bodesign_kb_query
```
缺的是中間那段 **host-side distill 動作**，不是任何系統要重寫。opencms 與 KB 層無關。

---

## Q2：C03 的設計能力邊界（實證圖譜）

把 C03 沿「設計 → 生成 → 驗證」三段拆開，逐段標出**真實能力**與**能力止於哪裡**。

### 邊界圖譜

| 環節 | 這件事誰做 | 工具化程度 | 證據 |
|---|---|---|---|
| **① pin 分類 → 每支 pin 的義務**（power→decoupling、clock→load cap、boot-strap→pull、diff→termination…） | **LLM reasoning，純散文方法** | ❌ **零工具化** | `pinout-to-circuit-method.md` L6-8「the most AI-heavy part of the stage, because it is reasoning, **not a tool call**」；L46「The classification is the design」 |
| **② 從 datasheet reference design 接地 → 決定要哪些輔助被動件、形成什麼 RC/LC/分壓/去耦網路** | **LLM reasoning** | ❌ **零工具化** | method L16-30 整套 loop 是給 LLM 讀的 SOP；產出物是一份 `spec` |
| **③ 把設計好的 spec 擺放+接線成 KiCad 圖** | `compose_schematic`（compute tool） | ✅ 工具化 | GUIDE L136「place + net a schematic **from the structured design spec**」；method L29「compose_schematic **places+nets**」 |
| **④ 編譯期驗證連接性/單位/公差約束** | `ato_build`（atopile 前端，可選） | ✅ 工具化 | proposal `dsl/atopile-integration`：AI 生成 `.ato`→編譯期把關；仍是**驗證** LLM 產出，不是替 LLM 合成 |
| **⑤ 反向校驗一張圖：偵測子電路 + 對 datasheet 查缺件/錯值/錯 pin** | `analyze_schematic.py`（KiCad engine） | ✅✅ 高度工具化 | `schematic-analysis.md`：偵測 regulator/divider/RC-LC/crystal/decoupling/protection…數十類子電路；PP-001 抓「power pin 只經 cap 到 rail」；crystal load cap 公式校驗 |

### 關鍵事實：`spec` 是 reasoning 的產物，不是輸入

> **"The `spec` is the output of reasoning, not a given"**（GUIDE L138、method L10）

這一行是整個問題的樞紐。`compose_schematic` / `ato_build` 都吃「**已經想好的 spec**」——「這顆 STM32N6 配這顆 PSRAM、走這條 SPI、需要這 8 顆去耦 + 這對 load cap + 這組 termination」這件**設計決策**，是 LLM 要在 ③④ 之前先產生的。工具只負責「把想好的東西畫出來/檢查連得對不對」。

### 所以使用者的觀察精確成立

- 「幾顆晶片共焊、外接元件/bus、中間需要多少被動件輔助」→ 這正是環節 **①②**，目前 **零工具化、純 LLM reasoning**。
- ⑤ 的 analyzer 很強，但它是**審查已存在的圖**（"catches design errors"），不是**從零把設計生出來**。它能告訴你「這顆 IC 的 VDD 缺去耦」，但前提是圖已經畫出來了；它不會替你決定「這顆 IC 需要幾顆什麼值的去耦、擺哪」。
- ④ 的 ato 是**編譯期驗證**（把 LLM 幻覺攔在 KiCad 前），本質仍是「驗證 LLM 的產出」，不是「代替 LLM 做合成」。

**一句話**：C03 有強的**校驗**能力（③④⑤），沒有**合成**能力（①②）——而合成正是使用者說的「設計能力」。

---

## 兩個缺口是不同層次，不能混為一談

| | 缺口 A：知識可查詢 | 缺口 B：設計合成能力 |
|---|---|---|
| **是什麼** | decoupling PDN 規則、fuse derating 值、SI 數值等**參考資料**進不了 `kb_query` | 「看著一組晶片，推導出完整輔助被動件網路」的**推理程序**沒有確定性、非幻覺的機制 |
| **現況** | 萃取檔已在 disk（batch14/15/18 verified 級），但未 ingest 進 ragbase → FTS 0 命中 | 完全落在 LLM reasoning（method 散文），系統其餘部分刻意不信任 LLM |
| **修法** | 走 producer.ts ingest/distill（工序問題，已就緒，範圍小） | 開放性難題：要嘛建確定性規則引擎把①②工具化、要嘛承認這一步靠 LLM+人審、要嘛守 bodesign 哲學把它擋在門外 |
| **和哲學的關係** | 不衝突（KB 本來就該可查） | **直接撞上核心哲學**：doctrine「LLM does upstream extraction/adjudication only; validation never involves it」 |

**我原本的 plan（把萃取檔 ingest）只解了缺口 A。** 它必要但遠遠不充分——把 decoupling 規則變成可查詢，不等於系統會自己推導出「這顆 IC 要這些去耦」。缺口 B 才是使用者真正戳的點。

---

## 對「我（Claude/Opus）懂不懂電路設計」的誠實回答

我不迴避：**我不是電路設計專家，而且這個系統從架構上就假設 LLM 不該做真正的電路設計。** bodesign 的可信度來自「展示而非宣稱」——確定性 KiCad/SPICE/EMC 驗證、對照已知良品交叉檢核，LLM 只做上游抽取/裁決。所以：

- 缺口 B 若要靠「讓 LLM 更會設計」來補，**違背 bodesign 的立身之本**，且不可驗證。
- 缺口 B 若要靠「把①②變成確定性規則引擎」來補，那是一個**真正的工程專案**（把 datasheet reference design + pin-obligation 規則庫變成可執行的合成器），不是 ingest KB 能達成。
- 缺口 B 也可能**本來就該由人/專業 EDA 做**——bodesign 定位是 co-pilot/scaffold，合成由工程師在真工具裡完成。

這三條路是產品決策，不是我能自行拍板的。

---

## 選項（不預設方案，待使用者定調）

1. **只補缺口 A（KB ingest）**——承認這只解「知識可查詢」，設計合成缺口另案；範圍小、風險低、不碰哲學。
2. **把缺口 B 當真正的能力缺口立案**——評估「pin-obligation → 輔助電路合成器」的確定性規則引擎可行性（很可能是多階段大工程）。
3. **守哲學、明文化邊界**——把「C03 不做設計合成、合成由 LLM 起草 + analyzer 校驗 + 人審」寫成 explicit 契約，讓期待對齊，不假裝有合成能力。
4. **先補 A + 用 A 強化 B 的校驗面**——ingest KB 後，讓 analyzer/review 能引用可查詢的設計規則做更硬的「輔助件完備性」反向檢查（不是合成，但把校驗網織密）。

---

## Architecture Sync

本輪為診斷，未動任何模組邊界/資料流。收尾時於 event 註記 `Architecture Sync: Verified (No doc changes)`。若使用者選 2/4 導致新增合成器或校驗閘，屆時再同步 `specs/architecture.md` C03 段。
