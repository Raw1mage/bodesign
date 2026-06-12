# 03 — DC 工作流（§3）

## 3.1 輸入：219 字需求文件（spec 即合約）

唯一的使用者輸入是一份極短但**極度刻意撰寫**的需求文件，結構拆解如下：

| 區塊 | 內容 | 性質 |
|---|---|---|
| 功能範圍 | RV32I + ZMMUL；i-cache/d-cache 32-bit 介面；clock/reset_n | 功能合約 |
| 微架構約束 | 5-stage in-order single-issue；register file 用 FF（async read / sync write）；**禁止**壓縮指令 | 設計約束（含明確負面清單） |
| 可量測目標 | CPI ≤ 1.5；目標 1.6 GHz；最大化 CoreMark | **可驗證的數值目標** |
| 工具鏈指定 | OpenROAD flow scripts、ASAP7 PDK、產出 GDSII + area/timing 報告 | 工具合約 |
| 介面時序合約 | 輸入在 cycle 70% 處有效；輸出須在 20% 內有效 | I/O timing 合約 |
| **驗證方法** | 用 Spike 建 cycle-by-cycle 整合測試，行為必須與 Spike 一致 | **驗證合約直接寫進 spec** |

另外提供：Spike ISA simulator、RISC-V ISA/ASM 手冊、RISC-V GNU toolchain。

> §5.3 關鍵教訓：spec 沒寫 CPI 時，DC 會生出 branch/forwarding 差很多的設計；寫了之後 DC **自己**在 testbench 加 cycle counter 對 Spike trace 估 CPI 來自我把關。**每個目標都要可量測，每個量測都要有 oracle。**

## 3.2 工作流步驟

流程由 DC Core 動態組合（非寫死 pipeline），VerCore 案例的實際路徑：

```
需求文件 ──→ ① Design Proposal（living document）
                │
                ▼
            ② 設計審查（subagent，紙上 cycle-by-cycle trace）
                │ APPROVE 後
                ▼
            ③ 模組實作 + per-module testbench（先測後行）
                │ 全部模組 testbench 通過
                ▼
            ④ Spike 對照整合驗證（vercore_tb.v + ELF 測試程式）
                │←─ 失敗：VCD debug 迴圈（見 04）
                │ MD5、CoreMark 等全部通過
                ▼
            ⑤ PPA closure（timing report → RTL 迭代）
                │←─ timing 回饋可反寫 ① 的 proposal
                ▼
            ⑥ 多變體完整實作到 GDSII → 真實數據裁決
                │
                ▼
            GDSII + area/timing 報告
```

### ① Design Proposal — living document

- 根據需求 + memory + 知識生成完整微架構文件：每個 pipeline stage 的職責、pipeline registers 清單、forwarding 路徑與優先序、hazard/stall/flush 邏輯、乘法器 handshake 協議。
- **Living**：實作中發現功能或 timing 問題時更新；論文觀察到 DC 甚至根據 **P&R 之後的 final timing** 回頭更新設計文件。
- 文件粒度到「SB: dc_byte_en = 4'b0001 << addr[1:0]」這種 bit-level 合約——proposal 不是大方向描述，是**可直接實作的合約**。

### ② 設計審查 — 實作前的紙上驗證

- 由 subagent 執行，DC 自述「manual and painstaking」。
- 方法：**手動 cycle-by-cycle trace** 多個測試情境（乘法器審查走了 7 個情境：簡單乘法、back-to-back、RAW hazard、load-use hazard、branch 附近、x0 destination、branch 打斷乘法）。
- 產出正式 review 文件：版本、方法論、情境清單、**分級結論**（CRITICAL/MAJOR/MINOR/RECOMMENDATIONS 計數）+ 總體裁決（APPROVE WITH MINOR CONCERNS）。
- 意義：**在寫任何 RTL 之前**就用推演消滅設計級 bug——這比實作後 debug 便宜幾個數量級。

### ③ 模組實作 — per-module testbench 先行

- 每個模組都建獨立 testbench，**測過才往下走**。
- 不允許「全部寫完再一起 debug」——錯誤被限制在模組邊界內。

### ④ 整合驗證 — golden reference 逐筆對照

- 建 `vercore_tb.v`：給定 RISC-V ELF → 在 DUT 上跑 → **逐筆比對 architectural state 與 memory transactions 與 Spike 一致**。
- 測試程式階梯式升級：小程式 → MD5 → CoreMark 本身。
- 失敗時進入 VCD debug 迴圈（詳見 `04-verification-loop.md`）。

### ⑤ PPA closure — 工具報告驅動迭代

- 全部功能測試通過後才進入。
- 讀 synthesis/P&R timing report → 改 RTL → 重驗。
- 此階段 DC 自行發明：ID-stage early forwarding、4 級平衡 Booth-Wallace 乘法器（單獨 2.57 GHz）。

### ⑥ 多變體全做到底（不靠猜）

- 1-cycle vs 2-cycle branch penalty 等變體**全部完整實作到 GDSII**。
- 用真實 P&R 數據裁決，不用架構直覺估算。
- 結論：1-cycle penalty 版本勝出（critical path 較長但達標）——重新發現了經典 MIPS 五級設計的 critical path。

### 終止條件

DC 可無限執行；本案例由人為設定 token 預算終止。報告的是終止時的結果（1.48 GHz，未達 1.6 目標但接近）。
