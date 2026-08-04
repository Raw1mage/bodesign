# BR_20260804k — `BODESIGN_DEV` 沒有 sticky marker 而 `BODESIGN_WORKERS` 有，於是裸跑 `restart` 會把 dev 掛載悄悄拿掉

**Status**: OPEN — 已量測定位，**未修**
**Severity**: **MEDIUM** — 不會毀資料，但會讓「我剛改的碼」與「容器實際跑的碼」分歧，而分歧點在部署層不在程式層
**Family**: `G13-harness-disclosure`（**部分**——見 §3，它並非完全靜默，我先前的描述有誤）
**Owner**: `(default)` — `ses_04db7a1c5ffelvbxyLP1p6xlRH`（bodesign 值星官）
**Filed**: 2026-08-04，在 C02 修法部署過程中量到（`BR_20260804_c02_export_stl...` §10.2）
**Related**: `issues/closed/BR_20260804_c02_export_stl_cannot_see_files_staged_into_its_own_token.md`（本缺陷是在該 BR 的部署步驟中發現的；當時已避開）· `BR_20260804j_the_verification_layer_has_no_verification_layer...md`（同族：兩個模式的持久化不對稱，而不對稱本身不被任何檢查覆蓋）

---

## 1. 事實

`mcpctl.sh` 有兩個部署模式旗標，**持久化待遇不同**：

| 旗標 | marker | 未帶環境變數時 |
|---|---|---|
| `BODESIGN_WORKERS` | `.run/.workers`（`WORKERS_MARKER:40`、`persist_mode():52`，三個 subcommand 各呼叫一次） | **維持上次的模式** |
| `BODESIGN_DEV` | **無** | **退回非 dev**（少掛 `docker-compose.dev.yml`） |

`mcpctl.sh:34-38` 的註解自己寫出了 workers 為何要 sticky：

> STICKY: once started in workers mode a marker in .run keeps every later
> restart/rebuild in workers mode, so an `mcpctl rebuild` never silently reverts
> to the monolith and orphans the workers (the regression this guards against).

**DEV 有完全相同的失效形狀，卻沒有對應防護。**

## 2. 量測

```
grep -n 'WORKERS_MARKER|persist_mode|BODESIGN_DEV' mcpctl.sh
  :40  WORKERS_MARKER="$RUN_DIR/.workers"
  :42  0) rm -f "$WORKERS_MARKER"; USE_WORKERS=0
  :44  *) [ -f "$WORKERS_MARKER" ] && USE_WORKERS=1 || USE_WORKERS=0
  :52  persist_mode() { [ "$USE_WORKERS" = "1" ] && touch "$WORKERS_MARKER" || true; }
  :157 :193 :203  ensure_run_dir; persist_mode        <- start / restart / rebuild 三處

  BODESIGN_DEV 的全部出現：:6 :8 :9（註解）· :30（唯一的行為點）· :191 :195（註解與 echo）· :231（usage）
  ⇒ 零 marker、零 persist、零讀回

CONTROL  grep -c 'ZZBOGUS_MARKER' mcpctl.sh -> 0     （證明 grep 會回 0 而非全部命中）

ls .run/  -> .workers 在（Aug 2 19:56 建立），無任何 dev marker
```

後果（`mcpctl.sh:30-32`）：`BODESIGN_DEV` 未設 ⇒ `COMPOSE` 陣列少一個 `-f docker-compose.dev.yml`
⇒ `up -d --force-recreate` 重建出**沒有 bind-mount** 的容器 ⇒ 跑 image 內烤進去的舊碼。

## 3. 誠實更正：它**不是**完全靜默（我第一次的描述是錯的）

我在口頭報告裡寫過「它只差一行 echo 措辭、沒有任何錯誤訊息」。**讀 `:195-199` 後這句話不成立**：

```sh
if [ "${BODESIGN_DEV:-}" = "1" ]; then
  echo "bodesign MCP restarted (dev: live source, no rebuild); socket -> $SOCK"
else
  echo "bodesign MCP restarted (baked image — use 'rebuild' to pick up code changes); socket -> $SOCK"
fi
```

**它有講**——`baked image — use 'rebuild' to pick up code changes`。所以這不是「成功態與危險態共用同一個輸出」那個最嚴重的形狀。

保留 G13 標記的理由縮小為兩點：

1. **狀態轉移不被揭露。** 那行 echo 描述的是「這次的模式」，不是「模式從 dev 變成了 baked」。從 dev 切到 baked 與一直都是 baked，印出的字**逐字相同**。真正該被看見的是**變化**。
2. **不對稱本身無人守護。** 同一個檔案裡一個模式有 sticky、另一個沒有，而註解明寫 sticky 是為了防「silently reverts」。這個不對稱不會被任何測試或檢查抓到。

## 4. 為什麼 MEDIUM 而非 LOW

失效後果是**部署層與程式層分歧**：你剛 commit 的修法在磁碟上、測試在磁碟上跑會綠，但容器跑的是舊碼。接著任何端對端驗證都會量到舊行為，而**你會去程式裡找一個不存在的 bug**。

本次（C02 修法部署）避開它的唯一原因是我在 restart 前讀了 `mcpctl.sh` 全文並發現這格——**那是紀律不是機制**，而紀律不能被依賴（`code-thinker` §8.1.1：對 reflex 型缺陷，純資訊性修復預期效果視為 0）。

## 5. 建議修法（三選一，成本遞增）

**A. 對稱處理（最小改動，與既有設計一致）**

```sh
DEV_MARKER="$RUN_DIR/.dev"
case "${BODESIGN_DEV:-}" in
  0) rm -f "$DEV_MARKER"; USE_DEV=0 ;;
  1) USE_DEV=1 ;;
  *) [ -f "$DEV_MARKER" ] && USE_DEV=1 || USE_DEV=0 ;;
esac
persist_mode() {
  [ "$USE_WORKERS" = "1" ] && touch "$WORKERS_MARKER" || true
  [ "$USE_DEV" = "1" ]     && touch "$DEV_MARKER"     || true
}
```

**B. 揭露轉移**（若刻意不要 sticky）：偵測既有容器是否帶 bind-mount，與本次將建立的模式不同時 loud 警告：

```
WARNING: containers are currently running in DEV mode (bind-mounted source)
         but BODESIGN_DEV is not set — this restart will recreate them from the
         BAKED image. Set BODESIGN_DEV=1 to keep live source.
```

**C. 兩者都做。** A 治預設值，B 治「使用者真的想切換」的那次。

## 6. 判準（修好後要能這樣驗）

```
BODESIGN_DEV=1 ./mcpctl.sh restart
docker inspect <container> --format '{{range .Mounts}}{{.Type}} {{.Destination}}{{"\n"}}{{end}}' | grep -c '^bind /app/services'   -> 1

./mcpctl.sh restart                    # 不帶 DEV
同一指令                                                                        -> 1（修法 A 生效）
                                                                    或 stderr 出現 loud 警告（修法 B 生效）

CONTROL  BODESIGN_DEV=0 ./mcpctl.sh restart   -> 0（顯式關閉仍必須有效，否則變成無法退出 dev）
```

**第三格是關鍵**：修法 A 若寫錯會讓 dev 模式黏住無法解除，而那個症狀比原缺陷更難察覺。
