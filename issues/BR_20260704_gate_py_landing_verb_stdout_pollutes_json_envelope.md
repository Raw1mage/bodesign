# BR: gate.py landing-verb stdout 混入非 JSON 前綴行,破壞程式化 pipe 消費

- **Date**: 2026-07-04
- **Component**: bodesign skill — `scripts/gate.py`(landing-verb runner)
- **Severity**: medium(不阻塞人工使用,但阻塞所有程式化 pipe 消費 readiness/gate 結果)
- **Reporter**: aiguard C00~C04 single-camera rearchitecture 工作線(orchestrator + 2× coding subagent 三方獨立踩到同一坑)

## 現象(硬證據)

`gate.py <verb>` 的 stdout **在 JSON envelope 前混入 2 行非 JSON 診斷輸出**:

```
$ python3 gate.py c04_readiness --repo <ROOT> --arg folder=<ROOT>/03.aiguard 2>&1 | head -3 | cat -A
landing_verb_start verb=c04_readiness repo=/mnt/d/users/.../thesmart_products$
landing_verb_ok verb=c04_readiness$
{"ok": true, "verb": "c04_readiness", "result": {...}}$
```

任何 `gate.py <verb> ... | python3 -c 'json.load(sys.stdin)'` 直接消費都會 `Expecting value: line 1 column 1 (char 0)` 失敗,因為第一行是 `landing_verb_start ...` 而非 `{`。

三方獨立命中證據:
1. orchestrator 首輪 C00~C06 readiness 批次:6 verb 全 `parse-fail`,需回退 `grep '^{'` 濾行才拿到 JSON。
2. C04 subagent 收尾主動回報:「`gate.py` stdout 前綴 `landing_verb_start` 非 JSON 行,直接 pipe json.load 會 parse 失敗,需先 `grep '^{'`」。
3. error case 亦然:`landing_verb_error` 前綴 + traceback 混在 JSON error envelope 前(見 C00 folder 語意誤用時的輸出)。

## RCA

`gate.py` 的 landing-verb 生命週期日誌(`landing_verb_start` / `landing_verb_ok` / `landing_verb_error`)與**結果 envelope 寫到同一個 stream(stdout)**。SKILL.md 對外契約明載:

> Output is one JSON envelope on stdout (`{ok, verb, result}`;...)

實作違反了「stdout = 單一 JSON envelope」契約 —— 診斷行應走 **stderr**,stdout 只留 JSON。目前診斷行走 stdout,使契約承諾的「pipe 進 json parser」路徑失效。

## 建議修復

`gate.py` 內 `landing_verb_start` / `landing_verb_ok` / `landing_verb_error` 這幾行 `print(...)` 改為 `print(..., file=sys.stderr)`。stdout 只保留最終 `json.dumps(envelope)`。這樣:
- 人工 `2>&1` 檢視行為不變(診斷行仍可見)。
- 程式化 `gate.py <verb> ... 2>/dev/null | json.load` 直接成立,無需 `grep '^{'` workaround。
- 與 SKILL.md「one JSON envelope on stdout」契約一致。

## 影響範圍

所有 landing-verb(52 個:c00~c06 readiness/scaffold/emit、package_readiness、orchestration 全家)。凡 CI / 自動化 / subagent 想程式化取 readiness 結果者,目前都必須知道並套用 `grep '^{'` workaround,屬未文件化的隱性契約。

## 驗證手段

修復後:
```
python3 gate.py c04_readiness --repo <ROOT> --arg folder=<ROOT>/03.aiguard 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin)["ok"])'
# 期望輸出:True(無需任何 grep 濾行)
```
並確認 `2>&1` 檢視時 3 條 `landing_verb_*` 診斷行仍出現(只是改走 stderr)。
