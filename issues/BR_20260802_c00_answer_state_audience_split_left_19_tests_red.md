# BR: C00/C01 answer_state audience-split 遷移只做了寫入端，19 個測試永久紅

- Date: 2026-08-02
- Status: OPEN（未修 — 在 readiness-contract 派工的 scope 之外，依規定 file 不順手修）
- Family: `audience-split-migration`（`stage-structure.md` 2026-07-17 的 03_output/ 遷移）
- Severity: **medium-high** — 缺陷本身是低風險的測試漂移，但它的**二階效應**（永久紅測試摧毀
  count-based 回歸判準）在 2026-08-02 當天差點讓一次真回歸被漏掉。見 §4。
- Found by: ses_03dea7914ffeimRD6BP0rYwuGV（readiness-contract handler），在建立回歸 baseline 時撞見
- Owner: 未指定

## §1.5 History Review

- **同族**：`BR_20260719_c01_readiness_folder_arg_double_prefix.md`。同一場 audience-split 遷移的
  第二處殘留。該 BR 講的是**交付物**路徑（`C01-ID/Ai file/…` vs `C01-ID/03_output/…`），本 BR 講的是
  **answer_state.json** 路徑。兩者是同一次遷移在不同檔案類別上的外顯。
  ⇒ **復發證據：遷移是逐檔進行的，沒有一份清單保證「所有讀寫端都跟上了」。**
- **非同源澄清**：readiness-contract 派工一度懷疑 `test_c01_id_package` 那 2 條紅燈與 folder 契約同源。
  已驗證**不是**：那 2 條斷言的是 `answer_state.json`（走 `_c01_answer_state_path`），而
  `C01_OUTPUTS` 不含 answer_state（已用程式驗證）。它們屬本 BR。

## §2 症狀（在 pristine HEAD 上量，已排除工作樹中他人未 commit 的修改）

量測方法：`git archive HEAD | tar -x -C <XDG tmpdir>`，在該乾淨副本上跑，確保數字不含我或 peer 的改動。

```
模組                        失敗數   traceback 提及 legacy answer_state 路徑
test_c00_orchestration        9              9
test_c00_prd_template         7              8
test_mode_contracts           1              1
test_c01_id_package           2              3
------------------------------------------------------------ 小計 19 條
test_landing_gate             1              0     ← 不同根因，不屬本 BR
test_guide_dod                2              0     ← 不同根因，不屬本 BR
```

（提及數 ≥ 失敗數，因單一 traceback 可能重複列出該路徑。）

**控制組（證明 pattern 有鑑別力，非全域命中）**：
```
grep -c "C00-PRD/ZZZ_NOT_REAL.json"  →  0
```
控制組回 0 而目標 pattern 回 9 ⇒ 這個判準能區分「命中」與「壞掉」。

逐字錯誤：
```
FileNotFoundError: [Errno 2] No such file or directory:
  '<tmp>/bodesign-c00orch-4md3ezt9/C00-PRD/answer_state.json'
```
```
AssertionError: 'C01-ID/answer_state.json' != 'C01-ID/03_output/answer_state.json'
```

## §3 Root cause（一句話）

audience-split 遷移把 answer_state 的**寫入端**移到 `03_output/`，**讀取端**加了
`resolve_stage_json()` 的 new-then-legacy 解析，但**測試 helper 仍直接組 legacy 路徑字串**，
繞過了解析器。

證據（寫入端已遷移，無爭議）：
```
c00_prd_template.py:184  answer_path = c00_dir / "03_output" / "answer_state.json"
c00_prd_template.py:375  answer_path = root / "C00-PRD" / "03_output" / "answer_state.json"
c00_prd_template.py:438  C00UpdateResult(..., Path("C00-PRD") / "03_output" / "answer_state.json")
```
測試端（未遷移）：
```
tests/test_c00_orchestration.py:30   sp = folder / "C00-PRD" / "answer_state.json"
tests/test_c00_orchestration.py:124  sp = self.work / "C00-PRD" / "answer_state.json"
tests/test_mode_contracts.py:75      sp = self.work / "C00-PRD" / "answer_state.json"
tests/test_c01_id_package.py:122,144 (self.work / "C01-ID" / "answer_state.json")
```

**這不是「產品程式有 bug」**——實際 runtime 讀寫都走 `03_output/` 且自洽。壞的是測試對舊位置的
硬編碼。但見下一節：**壞掉的測試不是零成本的。**

## §4 為什麼這比「19 個 stale 測試」更嚴重

`readiness-contract` 派工當天的實錄：

```
baseline 全套：57 條失敗
修完之後：    56 條失敗     ← 總數「下降」
```

若以數字結案，結論會是「沒弄壞任何東西，還順手修好一條」。**差集說的完全相反**：

```
NEW（handler 造成的真回歸）：2 條
FIXED（另一顆 peer 修 kicad_emit 造成）：4 條
淨值：-2 ... 再加上 1 條 peer 未 commit 工作造成的紅 → 淨 -1
```

**兩顆 agent 在同一棵樹上並行，一方的修復把另一方的回歸完全掩蓋掉了。**
基線裡 19 條恆紅測試正是讓「57」這個數字失去意義的主因——當基線本來就有大量噪音時，
「數字沒變壞」不再是任何東西的證據。

這是 **「缺席態與失敗態共用同一個輸出」的變體**：
「我沒弄壞東西」與「我弄壞的剛好被別人修好的抵銷」產生**完全相同的數字**。

⇒ 恆紅測試的真正成本不是它們自己紅，而是**它們讓別的紅變得看不見**。

## §5 Fix 建議（bounded）

1. 測試 helper 改用產品程式同一個解析器（`resolve_stage_json` / `_c01_answer_state_path`），
   **不要**在測試裡硬編第二份路徑真相——那正是漂移的來源。
2. 或最小改法：helper 內把 legacy 路徑換成 `03_output/` 位置（19 條應全綠）。
3. **順帶建議（非必要）**：加一條 meta 測試斷言「產品程式寫入的 answer_state 路徑 == 測試預期路徑」，
   讓下次遷移時漂移**在遷移當下就紅**，而不是留給兩週後的人考古。

## §6 未量測

- 這 19 條**是否全部**只因 legacy 路徑而紅——我比對的是「失敗數 vs traceback 提及數」的聚合，
  未逐條打開確認。可能有少數是複合原因。
- `test_landing_gate`(1) 與 `test_guide_dod`(2) 的根因**未查**，只確認**不是** answer_state 路徑。
- 修好這 19 條之後總失敗數會落在哪，未預測。

## §7 我為何不修

`readiness-contract` 派工單的 Boundaries 明列可碰檔案，`c00_prd_template.py` 與上述測試檔
**不在其中**；派工單同時明令「順手發現但不在 scope 內的缺陷 file 成 BR，不要順手修——
跨界順手修會糊掉驗證邊界」。本次交付的驗證正好依賴這批測試的紅/綠狀態作為 baseline，
**在同一次任務中修改 baseline 本身會讓我的回歸差集失去意義。**
