# BR_20260804i — `HOST_UID`/`HOST_GID` 從未進入容器，而在開發者的機器上失效與生效產生逐字相同的觀察結果

**Status**: OPEN — 已量測定位，**刻意未修**（修法要動 compose，不在本 handler 的可碰檔案集）
**Severity**: medium（今日無害；在 `id -u ≠ 1000` 的 host 上靜默失效）
**Family**: `readiness-contract`（發現於缺陷 3 的修法過程；與 entrypoint 同一支檔案但**不同缺陷**）
**Owner**: `(default)` — dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`
**Filed by**: `ses_0330e7869ffev0nZL0XqoXSp78`（BRNS handler）
**Filed**: 2026-08-04
**Related**:
- `issues/BR_20260804_c02_export_stl_cannot_see_files_staged_into_its_own_token.md`
  （§0.3 的 HOME 根因；本 BR 是那個修法的**串聯前置**，見 §4）
- `issues/BR_20260804h_c02_outputs_constants_are_dual_role_so_the_one_place_stage_prefix_claim_is_false.md`
  （同一輪 handler 產出，同族：宣稱與實況不符）

---

## 1. 一句話

`mcpctl.sh:26-27` 匯出 `HOST_UID`/`HOST_GID` 給 docker compose，但**三個 compose 檔沒有任何一處把它們傳進容器**。
`docker-entrypoint.sh:21` 的 `TARGET_UID="${HOST_UID:-1000}"` 因此**永遠取到預設值 1000**。

## 2. 量測（附控制組——這格是關鍵，見 §3）

```
$ grep -n 'HOST_UID' mcpctl.sh
  26:export HOST_UID="$(id -u)"
  27:export HOST_GID="$(id -g)"                        ← 確實 export 了

$ grep -rn 'HOST_UID|HOST_GID' docker-compose.yml docker-compose.workers.yml docker-compose.dev.yml
  （空，rc=1）                                          ← 三個檔都沒有
$ CONTROL：同一組檔案、同一個 grep 形狀、換一個必然存在的字串
$ grep -c 'BODESIGN_' docker-compose.yml docker-compose.workers.yml docker-compose.dev.yml
  6 / 5 / 5                                             ← 語法會命中，所以上面的空是真的空

$ grep -rn 'HOME' docker-compose*.yml
  （空，rc=1）                                          ← 也沒有任何 HOME 設定

$ 三個容器內實測：
  docker exec <core|ee|me> sh -c 'echo "${HOST_UID:-UNSET}"'
    → UNSET / UNSET / UNSET
  getent passwd 1000  →  ubuntu:x:1000:1000:Ubuntu:/home/ubuntu:/bin/bash   （三容器一致）
  awk '/^Uid:/' /proc/1/status  →  uid=1000                （server 確實跑在 1000）

$ host 端：id -u → 1000
```

## 3. 為什麼這是判準 1 的教科書標本（本 BR 最重要的一段）

**本機 `id -u` 恰好等於 `${HOST_UID:-1000}` 的預設值。**

⇒ 在唯一會執行它的這台機器上：

| | 觀察到的結果 |
|---|---|
| 機制正常運作（`HOST_UID=1000` 有傳進來） | chown 到 1000、server 跑 1000 |
| **機制從未收到輸入**（實況） | chown 到 1000、server 跑 1000 |

**兩者逐字相同。** 這個缺陷**在開發者的機器上不可觀測**，只會在別人的機器上發作——
而那時沒有人會想到要回頭看 compose，因為 `mcpctl.sh` 裡明明白白寫著 `export HOST_UID`。

**更惡的一格**：它的偽裝不是巧合，是**預設值挑得「合理」造成的**。
一個挑得不好的預設會立刻爆炸；挑得好的預設會讓缺陷活很久。

（發現經過符合判準 2：我 grep compose 找 `HOST_UID` 回空時，第一反應是**「我 grep 打錯了」**——
所以補了 `BODESIGN_` 控制組。那一格資訊系統當下有，只是沒有任何東西會說出來。）

## 4. 與缺陷 3（HOME）的串聯關係——修一個不夠

本輪已修：`docker-entrypoint.sh` 在 `setpriv` 前用 `getent passwd "$TARGET_UID"` 取真實 home
（取不到 ⇒ fail loud），解掉 `HOME=/root` 導致 openscad abort 的問題。

**但那個修法讀的是 `TARGET_UID`，而 `TARGET_UID` 本身就是錯的**：

```
HOST_UID≠1000 的 host
  → compose 不傳 → TARGET_UID 落到 1000
  → getent passwd 1000 → /home/ubuntu
  → server 以 uid 1000 執行（而非該 host 的真實 uid）
  → 產物 owner 錯 → 回到 BR_20260705 的 root-owned-products 那一類問題
```

⇒ **HOME 正確、uid 錯誤。** 兩者串聯，本 BR 不修則 entrypoint 的修法只在 uid=1000 的機器上正確。

## 5. 建議修法（不在本 handler 邊界內）

在三個 compose 檔的每個 service 加：

```yaml
    environment:
      HOST_UID: "${HOST_UID:-1000}"
      HOST_GID: "${HOST_GID:-1000}"
```

**但預設值本身要重新考慮**——`:-1000` 正是讓這個缺陷隱形的東西。
可考慮不給預設、讓 compose 在變數未設時 fail（`${HOST_UID:?...}`），
使「mcpctl.sh 沒 export」與「export 了」不再共用同一個成功輸出。

**驗證方式**（未跑，因為需要改 compose + 重建）：
以 `HOST_UID=1234 ./mcpctl.sh restart` 起容器，斷言容器內 `${HOST_UID}` = 1234
且 `/proc/1/status` 的 Uid = 1234。控制組：不設 `HOST_UID` 時應 fail loud 而非靜默落 1000。

## 6. 誠實邊界 — 我沒量的

- **`HOST_UID≠1000` 的實際行為未實測。** §4 的推導鏈是**推斷**，不是量測——
  本機無法產生該條件（改 compose 不在我的可碰清單，且需 rebuild）。
- **`getent passwd` 在「容器 passwd 沒有該 uid」時的分支未實測**，同上理由。
  該分支寫成 fail loud（不落預設），但**未經實機驗證**。
- 是否有其他機制（Dockerfile `USER`、compose `user:`）在別處補上 uid 對齊：**未掃**。
