# issue_20260903 — C00 系統架構圖與 C03 電源樹各需一個 emitter verb；drawmiat PNG 伴生檔目前不可用（誠實表態，非缺陷）

- **Type**: feature request（**非缺陷**。故用 `issue_` 前綴，見 AGENTS.md §6 Issues local-first）
- **Status**: OPEN — 需求已具名，優先序未裁示

| Field | Value |
| --- | --- |
| Title | Add stage-appropriate diagram emitter verbs for C00 system architecture and C03 power tree |
| Reporter | `thesmart_products` 值星官 `ses_038683542`（客人），跑 `04.btdongle` C00–C04 時提出 |
| Relayed by | dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH` → handler `ses_f9b3c1c20ffeHznP5iE1YLe38n` |
| Date | 2026-09-03 |
| Component | `packages/workflow-core`（landing verb 家族）、`stages/c00-prd`、`stages/c03-ee` |

## 1. 需求（客人原述，未修飾）

`c03_emit_host_block_diagram` **好用**：rc=0、`status=ok`、`png_rendered=true`，
已產出 C03 host block diagram 並落地驗收。

但它**形狀專用**（host-centric：中心 SoC/MCU + 週邊向四邊放射，匯流排畫在連線上），
套不上電源鏈那類拓樸。客人的 power tree 因此改走
`specbase_diagram_generate(diagram_type=idef0)`。

**關鍵那句**：他們是在 61 個 verb 裡**找不到對應形狀之後**才換路徑的。
換言之這不是「不知道有工具」，是「工具家族的形狀覆蓋有缺口」。

客人主張：**C00 系統架構圖**與 **C03 電源樹**各有一個 emitter verb 是真實需求。

## 2. 現況（handler 查證，非客人轉述）

`gate.py --list` 現有的 diagram emitter 只有兩個，皆在 C03：

| verb | MODEL 形狀 | 摘要（逐字取自 `--list` 輸出） |
| --- | --- | --- |
| `c03_emit_host_block_diagram` | `{center_part, peripherals[{name, side, bus?, type?}], reference_baseline?}` | Project a host/MCU MODEL into a layered block-diagram SVG (pptx=容器 tool) |
| `c03_emit_partition_diagram` | `{boards, interconnect}` | Project a partition MODEL into a layered breakout SVG (pptx=容器 tool) |

（另有 `c01_emit_id_visual_package` 屬 ID skeleton，不是拓樸圖。）

`SKILL.md:178-180` 的形狀對照表也只列這三項。**電源樹與 C00 系統架構圖確實沒有對應項** ——
客人的「找不到」是事實，不是漏看。

## 3. 附帶告知（**照實記，不升格成缺陷**）

drawmiat 自報 `embed_png_unavailable`，訊息為
"PNG companion generation is not configured"，fallback 是 `primary_svg`。

**客人明說它有誠實表態，所以不當缺陷報。** 本張同此判斷 ——
它把「PNG 沒生成」與「PNG 生成失敗」分開表達，正是 no-silent-fallback 該有的樣子。

只是告知：**有 caller 需要 PNG 伴生檔**（為了嵌進 `.docx`）。
若未來要補，這是需求來源；若不補，現況也沒有揭露缺陷。

## 4. 未做的事

- 未設計 MODEL schema（power tree 的節點/邊語義、C00 系統架構圖的層級語義都未定）。
- 未評估是否該用既有的 `specbase_diagram_generate(idef0)` 當長期解而不新增 verb ——
  客人已經證明那條路可走，新增 verb 是否划算需 dispatcher 裁決。
- 未量測 drawmiat PNG 設定要怎麼開（只記錄了它的自報訊息）。

**Related**:
- `issues/BR_20260903a_gate_py_list_enumerates_61_verbs_while_none_of_them_can_run_without_bodesign_src.md`
  — **同一條執行路徑**：客人是透過 `gate.py --list` 這份 61 verb 名冊去尋找電源樹 emitter 的。
  BR_20260903a 的主題是那份名冊「列得出卻跑不動」，本張的主題是那份名冊「跑得動但形狀不夠」。
  兩者共用同一個入口，且同一次 `04.btdongle` C00–C04 執行中一併浮現。
- `issues/BR_20260903b_emit_doc_documented_in_one_of_eight_stage_guides_so_seven_stages_cannot_discover_it.md`
  — 同一批客人回報，同一張派工單（task=file-guest-reported-teachability-defects）一併處理。
