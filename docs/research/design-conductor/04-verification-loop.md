# 04 — 驗證迴圈細節（golden reference + VCD debug 鏈）

DC 的核心可靠度方法論：**每一層都有客觀 oracle，agent 的判斷永遠對著真實工具輸出校正**。原文：「It is this verification-driven approach that allows DC to arrive at a working design.」

## 驗證階梯（四層）

| 層級 | Oracle | 觸發時機 |
|---|---|---|
| 1. 模組級 | per-module testbench | 每個模組實作後、整合前 |
| 2. 整合級 | **Spike（golden reference ISA simulator）逐筆對照** | 模組全過後 |
| 3. 性能級 | testbench cycle counter ↔ Spike trace（CPI 自我量測） | spec 含 CPI 要求時自動加入 |
| 4. 物理級 | OpenROAD synthesis/P&R timing/area 報告 | 功能全過後（PPA closure） |

## 整合級對照的具體機制

1. 建 `vercore_tb.v`：輸入 RISC-V ELF → 在 DUT 上執行。
2. **逐 cycle 比對**兩條軌跡：
   - architectural state（register writes：rd、value、順序）
   - memory transactions
3. 任一筆不一致 → 進入 debug 迴圈。
4. 測試程式階梯：小程式 → MD5 → CoreMark 本身（benchmark 同時是最終驗證載體）。

## VCD Debug 迴圈（發現不一致時）

```
不一致 → 觀察條件 → dump VCD → vcd2csv.py 轉 CSV
       → 寫 ad-hoc Python 分析腳本（pandas）
       → 對齊 expected trace（reg_trace.hex）vs actual（VCD）
       → 找出第一筆 MISMATCH（含 time、PC、暫存器、值）
       → 沿 pipeline 各 stage 回溯時間軸
       → root cause（causal chain，附時間戳證據）
       → 提 fix → 實作 → 重測
```

關鍵手法：

- **把波形轉成可程式分析的資料**（VCD→CSV→pandas），用 LLM 固有的 Python 能力處理，而不是「閱讀波形圖」。
- **先找第一筆分歧點**，不是泛泛看哪裡怪。
- **證據鏈帶時間戳**。論文範例（JAL flush bug）的 root cause 報告格式：
  - WHAT WAS DONE（7 步：轉檔→解析期望→解析實際→反組譯指令→trace pipeline 狀態→定位 root cause→寫分析文件）
  - ROOT CAUSE（一句因果陳述：「pipeline flush 邏輯沒有在 branch taken 時作廢投機抓取的指令」）
  - EVIDENCE（逐時間戳：Time 85000 JAL 在 EX 且 branch_taken=1 → Time 95000 本該被 flush 的 AUIPC 出現在 EX → Time 115000 錯誤寫入 x5）
  - FIX REQUIRED

## 紀律要點（可直接移植的原則）

1. **No vibe design**：宣稱正確 = 展示對照證據，不是「看起來對」。
2. **Oracle 寫進 spec**：驗證方法（用 Spike）是輸入需求的一部分，不是事後補的。
3. **分歧點驅動 debug**：永遠從第一筆 expected vs actual 分歧開始回溯。
4. **波形/工具輸出資料化**：把人類用眼睛看的產物轉成可程式查詢的結構化資料。
5. **root cause 報告標準化**：methodology / findings / evidence(timestamped) / fix 四段式。
6. **修了再測，測過才前進**：每個 fix 後回到同一條驗證階梯重跑。
