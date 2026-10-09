# BR_20260907 — `verify_netlist_fidelity` 接受形狀錯誤的 spec，回傳一份看起來合理、實際全錯的裁決

- **Status**: OPEN（未修 · 本單只立案取證，未動 code）
- **Severity**: **HIGH** — 缺陷長在仲裁者自己身上；它回綠或回紅都不再有意義
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/fidelity.py:561`（`verify_netlist_fidelity`）、
  致命行為在 `:594-595`
- **Filed**: 2026-09-07 by handler `ses_f87134d36ffe7Bgm4z5GclPidc`，
  依 btdongle 真板 baseline 量測 session `ses_f871fc491ffeUC3rImkn99fop4` §Issues-1 取證立案
- **Family**: `G13-harness-disclosure` — 失效態與成功態共用同一個輸出形狀
- **HEAD at filing**: `ded8b95`
- **Related**:
  - `issues/BR_20260906_gate_unit_fixtures_blind_to_emission_site_mutation.md` —
    **同一失效類別**（`G13-harness-disclosure`）：驗證器本身壞掉時，它的輸出與正常運作
    逐字相同。該單是「23 顆綠燈無法表達生產端未被覆蓋」，本單是「一份判決無法表達
    輸入根本沒被理解」。兩者共用判準：**pass/fail 這個值本身不承載「我有沒有看懂題目」**。
  - `issues/BR_20260905_router_corner_and_stacked_pins_short_declared_no_connect_pins.md` §5 —
    **同一條執行路徑**（`fidelity.py` 的裁決輸出）。該單量出「加了 NC 豁免後 gate 轉綠、
    而短路仍實際存在」的假綠燈；本單是同一個函式的另一個假裁決入口。該單 §5 引用的
    `fidelity.py:61` 設計自陳「an exemption the reader cannot see is indistinguishable from
    a check that was never made」——本單是那句話的形狀錯誤版本。

---

## 1. 症狀（一手實錄，非推論）

量測 worker 首次呼叫本 verb 時，誤把 **composer spec**（`{components, nets, nc}` 三鍵結構）
當成本 verb 要的 **partition spec**（`{net_name: [[ref, pin], ...]}`）傳入。

**它沒有拋錯。** 它回傳了一份完整、欄位齊全、格式正確的判決：

```
status    = failed
split     = [31 pins]
node_diff.spec_only 內含「被字串化的 component dict」，當作 net node 在用
```

`status=failed` 在這個 repo 的語意是「**我比對過了，兩邊不一致**」。實際發生的是
「我把三個 top-level 鍵當成三條 net 名，把它們的 value 當成節點清單」。
**沒有比對發生過。**

---

## 2. 根因（機制層）

`fidelity.py:594-595`：

```python
expected = {str(name): [_node_str(nd) for nd in nodes]
            for name, nodes in dict(spec).items()}
```

`dict(spec)` 迭代外層 key。給它 `{components: [...], nets: {...}, nc: [...]}`，
它就得到三條分別叫 `components` / `nets` / `nc` 的「net」。`_node_str` 對 dict 元素
做字串化，於是 component dict 變成了 node 字串。**全程沒有任何一行驗證形狀。**

---

## 3. 為什麼這是 RULE-D 破口，不是「使用者傳錯參數」

**RULE-D：非空的答案一樣什麼都沒證明。** 一個回空、回 error、回 crash 的仲裁者是安全的
——呼叫端會發現。一個**回傳合理判決**的壞掉仲裁者不安全，因為呼叫端沒有任何線索。

這個 verb 的**全部存在理由**就是當仲裁者。本 repo 三個月、40 張 BR 的老病
（「畫出來的線 KiCad 不認」）之所以難收斂，正是因為反覆出現「看起來對、實際錯」的中間結論。
**現在同一個形狀出現在防護措施自己身上**：

- 若誤傳發生在一次**回綠**的呼叫上 → 交付一塊沒被驗過的板，而帳面上寫著「fidelity ok」。
- 本次誤傳恰好回紅（`failed`），於是被人注意到。**那是運氣，不是機制。**

「使用者傳錯參數」這個 framing 之所以要拒絕：docstring（`:562-571`）確實寫明了형狀，
但**契約有寫 ≠ 契約有被執行**。同一個函式對「路徑不存在」這種呼叫端錯誤是
**raise `FidelityInputError`**（`:587-592`），對「spec 形狀完全錯誤」卻靜默續跑——
**同一類錯誤，兩種待遇，而較嚴重的那一種待遇較輕。**

---

## 4. 現有 codomain 已經做對了三格，缺的是第四格

`verify_netlist_fidelity` 的產出狀態設計其實**優於**本 repo 平均水準，這點必須寫下來，
因為修法要接在它上面而不是另起爐灶：

| 既有狀態 | 位置 | 觸發條件 |
| --- | --- | --- |
| `not-run` | `:573-583` | `spec` 空或 `emitted` 空 — 自陳「this is NOT a clean result」 |
| `indeterminate` | `:598-613` | `nets_parsed == 0` 或有無法解析的檔 |
| `ok` / `failed` | `:615` 之後 | 真的比對過 |
| **（缺）`spec 形狀不受理`** | — | **沒有這一格** |

`FIDELITY_ARGS_INVALID`（`:480`）**這個錯誤碼已經存在**、`FidelityInputError`（`:483`）
也已經存在。缺的不是機制，是**沒有人在入口呼叫它**。

> 這正是 code-thinker §12 產出狀態 codomain 說的那件事：`ok` / `failed` / `not-run` /
> `indeterminate` 都表態了，唯獨「我根本沒看懂你給我什麼」這一格塌進了 `failed`。

---

## 5. Proposed（**方向，不是實作** — 本單未動任何 code）

入口驗形狀，形狀不符 ⇒ **fail fast**，不得靜默續跑：

1. 在 `:594` 之前插入形狀檢查：`spec` 的每個 value 必須是 sequence，且其元素必須是
   `[ref, pin]` 二元序列或 `"REF.PIN"` 字串。
2. 不符 ⇒ `raise FidelityInputError(FIDELITY_ARGS_INVALID, ...)`，**訊息必須同時說出兩件事**：
   - **你傳的是什麼形狀**（例：`top-level keys ['components','nets','nc'] with values of type
     list/dict/list — this looks like a composer spec`）
   - **我要的是什麼形狀**（例：`expected {net_name: [[ref, pin], ...]}`）

   只說「invalid spec」不夠：本次誤傳的人手上就有正確的 composer spec，缺的是
   「這兩個結構長得像、但不是同一個東西」這句話。
3. **特例辨識值得做**：`{components, nets, nc}` 是本 repo 內部**唯一**會被誤傳的結構，
   直接認出它並提示 `did you mean spec["nets"]?`。
4. **不要用「猜測並自動轉換」解決**（例如偵測到 composer spec 就自動取 `spec["nets"]`）。
   那違反本 repo 天條 §2.1 no silent fallback，且會製造一個新的、更難察覺的版本。

### 5.1 修法必須自帶的控制組（寫給未來 handler）

- **正控制**：傳 composer spec ⇒ 必須 raise。
- **負控制**：傳正確的 partition spec ⇒ 必須**不** raise，且 `status` 與修改前逐字相同
  （證明形狀檢查沒有誤殺合法輸入）。
- **回歸控制**：既有 `tests/test_fidelity_*` 四顆模組必須維持綠，判別欄位取 `Ran N` 而非 rc
  （AGENTS.md §5），跑前清 `__pycache__`（AGENTS.md §6.3）。

---

## 6. 邊界宣告（引用本批讀數者必須一併帶走）

本單引用的讀數來自 btdongle fixture。**這塊板沒有被製造、組裝或量測過**——
`design.py:44-46` 自陳：「no board here has been fabricated, assembled, or measured.
Charge current, buck output and antenna performance are design targets computed from
datasheet formulae, never bench results.」

這批讀數是有效的**幾何／連通性**回歸母體，**不是**已驗證的電氣行為基準。
**任何電氣宣稱不得引用它。**

---

## 7. 量了什麼 / 沒量什麼

**量了（一手，本單 handler）**：
- `verify_netlist_fidelity` 的簽章與 docstring 契約（`fidelity.py:561-571`）
- `dict(spec).items()` 的位置與寫法（`:594-595`）
- 既有三格 codomain 的實際觸發條件（`:573-583`、`:587-592`、`:598-613`）
- `FIDELITY_ARGS_INVALID` / `FidelityInputError` 已存在（`:479-483`）
  — 控制組：同一支 grep 對 `ZZZ_NOT_A_CODE` 回 0，證明它不會亂回非零

**轉述（來源：`ses_f871fc491ffeUC3rImkn99fop4` §Issues-1，本單 handler 未複現）**：
- 誤傳當下的實際回傳值（`status=failed` / `split=[31 pins]` / stringified component dicts）

**沒量**：
- **未複現該次誤呼叫**。上表的回傳值是轉述，不是本單 handler 一手觀測。
  修法落地時應先把它變成一個會紅的測試，再修。
- **未盤查其他呼叫端是否也在誤傳**。只知道有一次誤傳，不知道母體。
- **未量形狀檢查的效能成本**（大 spec 上逐節點驗型的代價）。
- **未評估 `_node_str` 對其他非預期型別的行為**，只知道它對 dict 會字串化。
