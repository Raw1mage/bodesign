# BR_20260907 — A1 封存 patch 對今日 HEAD 已不可套用，而 `design.md` 仍逐字斷言它可以

- **Family**: `plans/eda-bridge_draftsman-series-divider-wireable`（舊包）／stale-assertion
- **Status**: open（僅立案，本輪不修；處置 1「加指標」已做）
- **Filed by**: `ses_f884168d5ffeCB4omppZFOFXzk`（BRNS handler，make-bodesign-draw-a-real-schematic round 40）
- **Repo**: `/home/pkcs12/projects/bodesign`
- **Severity**: 中。不影響執行中的程式碼；影響的是**下一個人以為手上有一條可用的回頭路**。
- **發現於**: round 38（三選項代價量測，該輪由 dispatcher 中止）

## 1. 斷言原文在哪裡

`plans/eda-bridge_draftsman-series-divider-wireable/design.md:318-322`：

```
## A1 逃逸樁：已封存，不是被否決（round 20-23）

**先講結論，因為最容易被讀錯**：`archived/A1_escape_stub.patch` 裡那份修法
**不是被判定為錯而拒收**，是**被降級為「未觸發」**——它防的那件事，在本 repo
的 HEAD 上量不到。**若未來量到 state A，它是現成的，直接 apply。**
```

**承重的是最後一句：「它是現成的，直接 apply」。** round 23 當時確實驗過——
把 patch `git apply` 到一份 pristine HEAD 副本可逐字重建，並錨在 `refs/wip/r22-a1-full`。
**那句話在 round 23 是真的。**

`design.md:346-352` 的復活條件四條也建立在同一個前提上：條件成立 ⇒ 直接 apply。

## 2. 今天實際發生什麼

round 38 依 dispatcher 指示，把該 patch 套進 scratch 副本以量測「選項 3 = 復活 A1」的代價。

**`git apply` 失敗。** 失敗點在 `kicad_emit.py:3349` 附近的 **hunk 5**。

根因不是 patch 壞掉，也不是檔案漂移造成的 context 不符，而是：

> **hunk 5 要加的那個 `_segment_fuses` 豁免，已經在 `0195950` 落地了**
> （即本線 round 26-27 的 A-1「`interior_retry` 豁免，SITE1 only」）。

而且兩者**簽名不相容**：

| 來源 | 參數 |
|---|---|
| A1 封存 patch 的 hunk 5 | `exempt_interior=bool` |
| HEAD（`0195950` 落地版） | `exempt_interior_pt=callable` |

所以問題不是「重複套用」（那只會 already-applied 而已），是
**其餘 4 個 hunk 若強行套上去，會呼叫一個今天已不存在的參數名** ⇒ 套出來的樹不可執行。

**⇒ A1 今天不是「現成的、直接 apply」，是「需要人工改寫 hunk 5 與其呼叫端之後才能重建」。**

## 3. 為什麼這值得一張 BR，而不是順手記一下

**斷言變假比缺一格證據嚴重。**

- 「缺一格證據」的讀者會知道自己不知道。
- **一句過期的斷言會讓讀者停止懷疑。** 下一個人讀到「它是現成的，直接 apply」，
  會把「復活 A1」估成零成本，並據此排程；直到他真的去 apply 才會發現。
  round 38 就是那個人，而那次 apply 是為了量代價——**代價的第一格就是這個。**

這與舊包 `errors.md` 已記的一族同形：**成功態與失效態共用同一個外觀**。
`archived/A1_escape_stub.patch` 這個檔今天仍在磁碟上、仍可讀、仍是 round 23 驗過的那份 bytes；
「它還在」與「它還能用」共用**檔案存在**這個輸出。

**同時它是 §6.1 那條「我以為我快照了」的姊妹形狀**：封存動作當時是正確且經過驗證的，
失效的是**它與一個持續前進的 HEAD 之間的關係**，而封存物本身不會知道這件事。

## 4. 這張 BR 立案時，A1 是否仍有復活價值？——**有，明確地有**

**這不是廢棄品**，理由是量測而非推測：

- round 37 已證 **復活條件 2 成立**：falsification 決定性——豁免中性化後短路消失、
  `changed_verdict` 3→0（四格讀數見新包 `design.md` §Q4）。
- 但同一輪也量到：那格成立於 **no-group 母體**（round 36 判為 `(B)` 非自然構法）；
  用真板第 5 欄原始分派（with-group）重組 power 紙**不復現**。
- ⇒ **A1 的復活價值仍在，但尚未被自然構法上的證據支撐。** Q4 未結案。

所以本 BR 的處置**不是「刪掉 A1」**，是讓那份封存物與它的斷言重新對齊。

## 5. 建議處置（不在本輪執行，待裁決）

三選一，成本遞增：

1. **只標記，不重建**（最小）：在 `design.md:322` 那句旁邊加一行指回本 BR，
   **不改原句**——過去式的記錄不會爛，爛的是它沒被標記已失效。**本輪已做這一格。**
2. **重建 patch**：把 hunk 5 改寫成對齊 `0195950` 的 `exempt_interior_pt=callable`
   簽名，重新驗證「apply 到 pristine HEAD 可逐字重建」，並更新錨點。
   代價：一輪，且做完仍需 Q4 的自然構法證據才會真的復活它。
3. **改記錄形式**：patch 檔對持續前進的 HEAD 天生會腐爛；改存成「意圖 + 關鍵 diff 片段」
   而非可套用的 patch，並在 `design.md` 明說它需要重寫而非套用。

## 6. 驗收（誰來修，怎麼知道修好了）

- 選 1 ⇒ `design.md:322` 附近可 grep 到本 BR 檔名。**（已滿足，見下）**
- 選 2 ⇒ 對一份 pristine HEAD 副本 `git apply --check` 回 rc=0，
  且**控制組**：對一份**故意改壞**的副本必須非零（否則 `--check` 可能根本沒讀到檔）。
- 選 3 ⇒ `archived/` 下不再有宣稱可直接 apply 的 `.patch`，或該檔開頭逐字標明「不可直接套用」。

## 7. 本輪已做的部分

依 round 40 dispatcher 指示採**處置 1**：`design.md` 原句**未改**，
旁邊加一行指回本 BR。原句是 round 23 的事實記錄（過去式，不會爛），
本 BR 記錄的是它與今日 HEAD 的關係已失效。
