# Design Conductor (DC) 論文拆解

> 來源：arXiv 2603.08716v1 — "Design Conductor: An agent autonomously builds a 1.5 GHz Linux-capable RISC-V CPU"（Verkor Team, 2026-02-06）
>
> 目的：將論文方法論拆解為可引用的 src 文檔，作為強化 bodesign workflow 的依據。
>
> **⚠️ 定位修正（2026-06-12）**：本論文的領域專業（RTL/timing/PDK/Spike/OpenROAD）與 PCB 設計**零轉移**；其全自主能力的核心前提——可執行的 cycle-accurate 整體 golden model（Spike）——在 PCB 領域**不存在**。本系列文檔僅作為「對自己的 workflow 提問」的研究記錄；實際的改良 plan（`plans/workflow_verification-discipline/`）每一項都獨立站在 bodesign 自身程式碼缺口的行號證據上，與本論文無依賴。

## 文檔索引

| 檔案 | 內容 |
|---|---|
| [`01-capabilities.md`](./01-capabilities.md) | DC 七大關鍵能力（長程執行、context 管理、驗證、探索/速度平衡…） |
| [`02-architecture.md`](./02-architecture.md) | DC 系統架構：DC Core、worker/tool servers、記憶庫、context 管理 |
| [`03-workflow.md`](./03-workflow.md) | 完整工作流：spec → proposal → review → 實作 → 整合驗證 → PPA → GDSII |
| [`04-verification-loop.md`](./04-verification-loop.md) | 驗證迴圈細節：golden reference 對照、VCD→CSV→Python debug 鏈、root cause 紀律 |
| [`05-results-lessons.md`](./05-results-lessons.md) | 結果數據 + LLM 弱點清單 + spec 撰寫要求 + 未來設計流程 |
| [`06-bodesign-gap-analysis.md`](./06-bodesign-gap-analysis.md) | **差距分析：DC 工作流 vs bodesign，可借鏡點與工具擴充候選** |
| [`07-architecture-improvements.md`](./07-architecture-improvements.md) | **架構級改良分析（基於 workflow-core 原始碼偵查）：A1–A5 結構性建議** |

## 一句話總結

DC 用「**spec 即合約 → living design proposal → 實作前紙上審查 → 模組級先測後行 → golden-reference 逐筆對照 → 工具報告驅動的 PPA 迭代 → 多變體全做到底再比較**」的工作流，在 12 小時內全自主從 219 字需求文件建出 1.48 GHz 的 RISC-V CPU GDSII。

## 與 bodesign 的對應關係（速查）

| DC（數位 IC） | bodesign（PCB） |
|---|---|
| 219 字需求文件（可量測目標） | 自然語言規格 → 結構化計畫 |
| Spike ISA simulator（golden reference） | 已知良品參考板交叉檢核 |
| Verilog RTL | BoardDesign IR / KiCad schematic |
| per-module testbench | 子系統級驗證（待強化） |
| OpenROAD + ASAP7 PDK | KiCad bridge + kicad-cli + pygerber |
| timing report → RTL 迭代 | DRC/ERC/SI/EMC → IR 迭代 |
| GDSII tape-out package | Gerber/drill/BOM/pos 製造包 |
