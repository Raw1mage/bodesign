# BR_20260704 — bodesign 缺「設計前必先拆解 refs 權威源」的 gate，agent 可跳過需求規格書憑空發明設計

- **軸**：A（工具/gate 缺）+ B（skill 紀律未被機制化）
- **層**：bodesign skill/workflow 層（C00/C03/C04 guide + honesty-model gate）
- **嚴重度**：Critical（直接導致整個設計偏離 owner 指定的權威需求源，是本 session 最大 gap）

## 現象（含硬證據）

Session title（owner 第一句指令）：**「根據aiguard的refs裏的需求規格書正式版，完備c00到c07交付物」**。

實際發生：agent（我）**跳過 `01_refs/` 完全沒讀**，直接在既有 C03 板檔上憑空編元件座標（U1 放 (18,16)、U2 放 (7,16)… 全部是想像），並據此迭代了 4 版 placement + render QA，全部建在沙上。直到 owner 連續質問「你的設計根源是什麼？」「你有沒有先把 01_refs 拆得明明白白？」才發現根本沒有設計依據。

硬證據——`01_refs/Reference_Baseline.md` 明文定義權威順序，且 agent 事後才讀到：

```
authority order: formal deck > X01/BOM > OpenMV heritage > concept sketches
1. 01_正式需求書/N6核心郵票模組_訊倢需求說明_優化版v3.pptx — V1 scope AUTHORITY
   (owner adjudication 2026-07-02): three-piece design, fixed single camera,
   BQ25890+1S Li-Po, PDM 3-mic, quantities... Where any other reference conflicts,
   this deck wins.
2. 02_第一代板_N6_X01參考/N6_X01 說明文件20260429v01.pdf — gen-1 stamp board:
   36-pad boundary (insufficient — renegotiated), cross-board SI rules, P0/P1 corrections
```

存在一份 owner adjudication 認定的 **V1 scope 唯一權威 PPTX**，agent 卻在整個 placement 重設計中**一次都沒開它**。

## RCA

bodesign 有 honesty-model（「引用來源才能斷言 IC/net/mechanical 事實」）與 DoD manifest，但：

1. **honesty-model 是「斷言時要引用」，不是「設計前要先攝入全部權威源」**——它擋的是「宣稱未驗證的事實」，擋不住「用憑空座標做設計但每個座標都不宣稱是事實」這種繞過。placement 座標不算「IC/net fact」，於是溜過了 honesty gate。
2. **沒有 mechanical gate 強制「refs 攝入 → 拆解 → 交叉引用」是設計的前置**。C03/C04 guide 從「已有 design intent」起跳，design intent 從哪來、有沒有 trace 到 owner 的權威 refs，無人把關。
3. Agent 手上先有一個「現成的 C03 板檔」，就順手拿它當基礎往下改，**把『既有 artifact』誤當成『設計根源』**，而真正的根源（owner refs）被跳過。這是典型的 anchor-drift：抓到最近的可執行物就開工。

## 建議修復

**軸A（工具/gate）**：新增 refs-decomposition verb + gate：

1. **`refs_ingest`**：掃描 `<project>/C00-PRD/01_refs/`（或指定 refs 根），分類每個檔（正式需求書/datasheet/heritage/concept），讀出 `Reference_Baseline.md` 的 authority order，產出 `refs_manifest.json`（每源：路徑、權威等級、媒體型別、是否已判讀）。
2. **`requirement_decompose`**：把權威源（尤其正式需求書）拆成結構化需求表（尺寸/接腳定義/元件清單/佈局要求/電源架構…），落 `requirement_spec.json`，每條需求 trace 回源檔頁碼。富媒體（PPTX/PDF）判讀走 reader-subagent（agent 環境已有此能力）。
3. **Design-root gate**：`c03_readiness` / `c04_readiness` 增加一條 machine check——**若 placement/schematic 產出物存在，但無對應 `requirement_spec.json` trace（或 trace 覆蓋率 < 門檻），DoD 判 fail**，並在 `guide_compliance` 具名「設計未 trace 到權威 refs」。

**軸B（skill 紀律機制化）**：bodesign skill 的 C03/C04 GUIDE.md 開頭加「**Design-root contract**」：進入任何 emit 前，第一動作是 `refs_ingest` + `requirement_decompose`，且明文「既有 C03/C04 artifact 不是設計根源，owner 的 refs 權威源才是；拿現成板檔往下改而未回溯 refs = 設計缺陷」。

## 影響範圍

- 所有 bodesign 設計任務（不限本專案）——只要 refs 存在而 agent 跳過，就會產生「看似完成、實則無根」的交付物，且 honesty-model 抓不到。
- 特別傷害 owner 已做 adjudication、明確指定權威源的專案（如 aiguard V1 scope）。
- 修復後：設計產出可被機器驗證「是否 trace 回權威需求」，杜絕憑空發明。

## 驗證手段

- `refs_ingest` 對 aiguard `01_refs/` → manifest 正確列出 8 個 source group + authority order。
- `requirement_decompose` 對正式需求書 PPTX → requirement_spec.json 含尺寸/castellated 腳位/元件清單，每條 trace 頁碼。
- 故意用憑空座標產 placement 但不 trace → `c04_readiness` 應判 `dod_ok:false` 並具名 design-root 缺失。
- 正常流程（先 ingest+decompose 再 place）→ readiness 綠。
