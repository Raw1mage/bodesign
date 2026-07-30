# BR_20260730 — bodesign 的 `GET /skills` 服務 `.tar.gz` 並廣告檔名，偏離 R9.2 釘死的 `.zip`（且服務來源與 `skillPaths` 宣告來源不同源）

| Field | Value |
| --- | --- |
| Title | bodesign R9.2 格式偏離：`/skills` 廣告檔名 + 服務 `.tar.gz`，遠端 client 全數取不到 |
| Component | bodesign MCP HTTP introspection surface（`services/mcp/server.py`） |
| Reporter | ses_05b51c060（fleet R9 稽核，dispatcher 自驗） |
| Date | 2026-07-30 |
| Severity | high — 14 個 companion（含 `bodesign` 主 skill 894812B）全部對合規 client 不可取；且服務來源 `services/mcp/assets/skills/` 與 `mcp.json skillPaths` 宣告的 repo `skills/` **不同源** |
| Priority | P2 — 本機 opencode host 走 R9.1 本地半仍可取得；衝擊面限遠端 / 非 opencode client |
| Affected versions/tools/paths | bodesign 0.3.0；`mcp.json:14` `skillPaths:["skills"]`；`services/mcp/server.py:2869-2870`（route）、`:2733-2745`（list handler）、`:2760-2772`（download handler）、`:1932-1933`（`_assets_dir()`） |

```
State:
Fix: PARTIAL (2026-07-31, ses_04db7a1c5 — bodesign coordinator, full ownership per a2a-d2d §3.1.1)
Effect: ALL fixes through round 7 are deployed and live-verified against the built image
        (d01d10e, three images, no /app bind mounts) — see §12.6.
        Nothing is fixed-but-undeployed.
Custody: bodesign
Blocker: none
Disposition: accepted — accepted as a real defect; RCA found it WORSE than reported (see §4)
Venue: bodesign
Status: PARTIAL — deliberately NOT closed. Seven independent adversarial verification
  rounds, seven non-PASS verdicts; every round found something the previous one could not
  see, and twice (§10, §12.4) a round's own FIX created the defect the next round found.
  The original R9.2 deviation (F1/F2/F3) is fixed, deployed and repeatedly re-verified.
  What keeps this open is scoped remainder, not doubt about the shipped fix:
    - ~29 of 59 landing verbs have never been invoked; the stateful C00->C01
      orchestration loop is unexercised end-to-end (§12.7.1)
    - no round has performed a live skill() load through the daemon's directory
      scan — only opencode's parser+schema in isolation (§12.7.3)
    - the composite bundle's stale kicad/kidoc shadow is bounded, disclosed and
      guarded in both directions, but not eliminated (§10.3)
    - source parity is asserted at startup only, not continuously (§9.5)
  Two findings were split out rather than folded in: BR_20260730d (unauthenticated
  /invoke, CLOSED) and a pin_allocation silent-empty shape that deserves its own BR
  (§12.7.2).
Reopened: 2026-07-30 by ses_04db7a1c5 (bodesign coordinator), on external verdict=FAIL
Last verified: 2026-07-31 (round 7, d01d10e deployed + live-probed; see §12.6)
```

## 4. Resolution (bodesign, 2026-07-30)

### 4.1 What the RCA found beyond the report

F1/F2 were reported accurately. **F3 was understated**: the two trees had not merely
*risked* drifting — they HAD drifted, and the served copy was damaged.

| Fact | Evidence |
| --- | --- |
| `assets/skills/bodesign.tar.gz` was a 2026-06-10 frozen snapshot; repo `skills/bodesign/` last moved 2026-07-06 | `git log -1 --format=%ci` on each |
| The snapshot was missing `doctrine.md` (the R15 single-source the server fails fast on) and the **entire `scripts/` dir** — including `gate.py`, the sole entrypoint for ~52 landing verbs | `tar tzf \| grep -c doctrine.md` → 0; `grep "^bodesign/scripts"` → empty |
| It carried **2 symlinks** (`engines/emc`, `engines/datasheets`) — which R9.7.1 forbids outright, and which make opencode's consumer hard-fail the whole skill | `tar tvzf \| awk '$1~/^l/'` |
| 189 files in the repo tree vs 151 in the tarball; 8 files under `engines/kicad` had diverged | `diff -rq` |

So the correct repair was never "add a `.zip` route" — it was to stop having a second
artifact at all. R9.11.3 already names on-the-fly construction from the declared tree the
preferred implementation; had a parity assertion been added instead, it would have gone
red immediately, which is precisely its job.

### 4.2 Product decisions (owner-adjudicated)

The reporter left the back-compat tradeoff to this repo. Decisions:

1. **`.tar.gz` is kept, not dropped** — the landing page has published those links since
   2026-06-07 and an unrelated fix should not 404 a live URL. It is no longer a separate
   artifact: for a declared skill both formats project the same live tree, so the format
   can no longer encode a content difference.
2. **The R9 listing advertises only the 2 declared skills** (`bodesign`, `bodesign-kb`).
   The 13 vendored EDA companions have no in-repo source, so they can never satisfy
   R9.11 parity; advertising them as R9 skills would assert a provenance this repo cannot
   back. They moved to a separate `bundles` key (R9.9.4 permits extra keys) and keep their
   filename-addressed legacy links.

### 4.3 Changes

| Finding | Fix |
| --- | --- |
| F1 | `GET /skills` → `skills[].name` is a bare name; EDA archives split into `bundles[]` |
| F2 | `GET /skills/<name>.zip` added; suffix stripped to recover the bare name; `.tar.gz` served from the same tree |
| F3 | Archives built on the fly from `mcp.json skillPaths` (R9.11.3 by construction) + `assert_skill_source_parity()` runs in `run_http` **before binding** and kills the process on divergence (R9.11.1) |
| R9.7.1 | No absolute paths / `..` / symlinks; dotfiles + `__pycache__` excluded; fixed mtimes make archives byte-reproducible; unknown name → typed 404, never a 200 empty archive |

New `services/mcp/skill_shipping.py`; `server.py` two handlers + startup gate + landing page;
four Dockerfiles now `COPY mcp.json` + `COPY skills` (superseding the single-`doctrine.md`
COPY, whose "do not bundle the raw tree" policy is what forced the frozen-tarball design);
dev overlay mounts both; new `.dockerignore` keeps the private product-board vault symlinks
and install-layout-only engine pointers out of images; `assets/skills/bodesign.tar.gz`
retired; kicad engine extraction now reads the in-repo tree (78 files vs the tarball's 50).

### 4.4 Verification

- `tests/test_skill_shipping.py` — 23/23. Includes traversal negatives **each paired with an
  accepting control** (a reject-everything guard would otherwise pass every case), a parity
  negative control proving the assertion can fail, and a regression anchor asserting the zip
  ships `doctrine.md` + `scripts/gate.py` — the two things the frozen copy had lost.
- Live UDS probe: `GET /skills` → both names bare; `bodesign.zip` → 200, valid zip,
  169 members, `bodesign/SKILL.md` present, contains `doctrine.md` + `scripts/gate.py`.
- Negatives: `nope.zip`, `../mcp.json`, `..%2fmcp.json`, `bodesign.tar.gz.zip`, `packages.zip`
  → all 404. Back-compat: `bodesign.tar.gz`, `kicad.tar.gz`, `MANIFEST.md` → all 200.
- Pre-existing suite failures (`test_mcp_server` 3F/2E) were confirmed present on HEAD before
  this change by reverting `server.py` and re-running — they belong to a peer's uncommitted
  work and are untouched here.

### 4.5 Image-path verification (why the Dockerfile edits are not merely plausible)

The running service proves the *code*, but it runs on dev bind-mounts, so it proves nothing
about the amended Dockerfiles. Those were verified separately, without disturbing the live
container:

- **`Dockerfile.core` built end-to-end** (`docker build -f Dockerfile.core`, exit 0). Inside the
  resulting image: `/app/mcp.json` present, `/app/skills` holds both skills, `doctrine.md`
  non-empty, and `assert_skill_source_parity("bodesign")` **passes** while packing a
  1,102,227-byte zip. A green build that then dies at the startup gate would be a false pass,
  so the gate was exercised in-image rather than inferred.
- **`.dockerignore` confirmed effective in-image**: none of `openmv`, `thesmart_products`,
  `engines/emc`, `engines/datasheets` leaked in, and no `__pycache__` survived.
- **The monolith/ee/me delta was built on a light base** (`debian:bookworm-slim` + the exact
  changed lines: `COPY mcp.json`, `COPY skills`, and the new `cp -r` engine extraction with its
  `test -d` guard) — 37 engine scripts landed, guard passed, no symlink leak. Their full builds
  were NOT re-run: the changed instructions are identical to core's plus that one RUN step, and
  re-running the KiCad/LibreOffice layers costs ~20 min while proving nothing new about this
  change. This is a deliberate scope call, not an untested path — but see Status: the images
  are still unbuilt in the real registry, which is exactly why this BR is not closed.
- Verification images were deleted afterwards; `bodesign:latest`/`-ee`/`-me` are untouched.

### 4.6 Post-deployment verification (the one that actually settles it)

Deployed 2026-07-30 with `BODESIGN_WORKERS=1 ./mcpctl.sh rebuild` (all three images rebuilt,
exit 0). Crucially this was run **without** `BODESIGN_DEV`, so the container has no `/app`
bind mounts — confirmed by `docker inspect`. Everything below is therefore the **image's**
behaviour; a green result under dev mounts would have proven nothing about what ships.

| Check | Result |
| --- | --- |
| Startup parity gate at boot | passed (no violation in logs) |
| `/app/mcp.json` + `/app/skills` in image | present (`bodesign`, `bodesign-kb`) |
| `GET /skills` | `skills:[bodesign, bodesign-kb]` (bare), `bundles:13` |
| `GET /skills/bodesign.zip` | 200 · 1,102,227 B · valid zip · 169 members · `bodesign/SKILL.md` present |
| Content the frozen copy had lost | `bodesign/doctrine.md` + `bodesign/scripts/gate.py` both present |
| Symlinks in archive (R9.7.1) | **0** |
| Negatives | `nope.zip`, `../mcp.json`, `..%2fmcp.json`, `bodesign.tar.gz.zip`, `packages.zip` → all 404 |
| Back-compat | `bodesign.tar.gz`, `kicad.tar.gz`, `MANIFEST.md` → all 200 |
| C06 engine regression (ee worker) | kicad=37, spice=11, emc=4 scripts — intact after the extraction source changed |

Note the fourth row against §1.2: the reporter's consumer failed on
`bodesign-eda-skills-bundle.tar.gz.zip`. That exact shape now returns 404 **because nothing
advertises it any more** — the bare names are what the listing serves, so a tolerant reader
appending `.zip` lands on a route that exists.

## 1.1 症狀（verbatim）

對活著的 bodesign server 撥號：

```
GET /skills                  -> 200
  {"service":"bodesign","count":14,"skills":[
     {"name":"bodesign-eda-skills-bundle.tar.gz","skill":"bodesign-eda-skills-bundle",
      "bytes":1100211,"url":"/skills/bodesign-eda-skills-bundle.tar.gz"},
     {"name":"bodesign.tar.gz","skill":"bodesign","bytes":894812, ...}, ...]}

GET /skills/bodesign.tar.gz  -> 200   894812 bytes   application/gzip
GET /skills/bodesign.zip     -> 404        <- R9.2 釘死的形狀不存在
```

兩件事同時偏離規範：

1. **payload 廣告檔名**（`"name":"bodesign.tar.gz"`）而非 bare skill name。`.zip` 屬於**端點**，不屬於名字。
2. **服務 `.tar.gz`** 於 `/skills/{name}`，而 R9.2 釘死 `GET /skills/<name>.zip`。

## 1.2 消費端實測（決定性）

用 opencode 的 R9.2 消費端（`packages/opencode/src/mcp/skill-fetch.ts`）撥號：

```
{"id":"bodesign","kind":"failed",
 "reason":"GET /skills/bodesign-eda-skills-bundle.tar.gz.zip returned HTTP 404"}
```

注意那個 `.tar.gz.zip` —— 這是 tolerant reader（R9.8）忠實取用 `name` 欄位後再依 R9.2 附加 `.zip` 的**必然結果**。對照組（同一支消費端、同一次執行）：

```
{"id":"docxmcp", "kind":"materialized","skills":["doc-workflow"]}
{"id":"drawmiat","kind":"materialized","skills":["flowchart-author","miatdiagram"]}
{"id":"pmsmcp",  "kind":"materialized","skills":["pmsmcp"]}
```

三個成功證明消費端有效。bodesign 的失敗**不是** client 的問題。

## 1.3 Findings

```
Findings:
F1 GET /skills 廣告 archive 檔名而非 bare skill name（違反 R9.2 名字語義） Fix: unfixed Disposition: accepted Venue: bodesign
F2 下載端點供 .tar.gz 於 /skills/{name}，無 R9.2 釘死的 /skills/<name>.zip Fix: unfixed Disposition: accepted Venue: bodesign
F3 服務來源 services/mcp/assets/skills/ 與 mcp.json skillPaths 宣告的 repo skills/ 不同源，無單一來源 assert Fix: unfixed Disposition: accepted Venue: bodesign
```

## 1.4 RCA

`services/mcp/server.py:2733-2745`（list handler）：

```python
skills_dir = (_assets_dir() / "skills")
for f in sorted(skills_dir.glob("*.tar.gz")):
    items.append({"name": f.name,            # <- f.name 是檔名，含 .tar.gz
                  "skill": f.name[:-len(".tar.gz")],   # <- bare name 在這裡，但沒被當成 name
                  ...})
```

`"skill"` 欄位**其實已經有 bare name**，但 R9.8 的 tolerant reader 讀的是 `name`（那是 fleet 各實作的共同鍵），於是取到檔名。

`:2760-2772`（download handler）只接受 `.tar.gz` 與 `MANIFEST.md`：

```python
if not target.is_file() or not (target.name.endswith(".tar.gz") or target.name == "MANIFEST.md"):
    return JSONResponse({"error": "not_found"}, status_code=404)
```

**F3 是更深的一層**：`_assets_dir()` 是 `Path(__file__).resolve().parent / "assets"`（`:1932-1933`），即 `services/mcp/assets/skills/`——那裡有 14 個預先打包的 tarball。而 `mcp.json skillPaths:["skills"]` 指的是 **repo 根的 `skills/`**（內含 `bodesign`、`bodesign-kb` 兩個目錄）。兩個來源之間沒有任何一致性斷言，所以本地半與遠端半可以無聲漂移。

`issues/BR_20260721_mcp_r17_r0.6_conformance_gap.md:91` 自己已預警過這點：「`GET /skills`（`assets/skills/*.tar.gz`）… 三者**很可能**同一 companion 但無單一來源 assert；parity/drift test **仍可能失敗**」。本 BR 把該預警坐實。

## 1.5 Mandatory History Review

| Aspect | Finding |
| --- | --- |
| Same-family BRs | `yes（最近親，同面向但非同症狀）：issues/BR_20260721_mcp_r17_r0.6_conformance_gap.md`（**open**）。該 BR `:35` 已記「R17.5（部分）… skillPaths `mcp.json:14-16`、`GET /skills` `:2316-2328`」，`:91` 更明點 tar.gz 來源與 parity drift 風險——**已預警但未坐實遠端拿不到**。其餘命中（`BR_20260705_landing_verb…`、`closed/issue_20260623_c06_analyzer_engines…`、`closed/issue_20260623_analyze_emc…`）為 skill engine 掛載 / 本機 mirror 路徑，屬旁系。掃描 pattern：`skillPaths`/`/skills`/`skill.?ship`/`companion`/`SKILL_NOT_SHIPPED`/`HALF_SHIPPED`/`R9`/`zip`/`tar.gz`（`R9` 有誤命中 `BR_20260730c_export_bom…:119` 的「R9 標記 in_bom=no」，已排除）。 |
| Recurrence | `no（此精確症狀）／但已被自己預警` — 格式偏離（`.tar.gz` vs `.zip`）先前未被修過；`BR_20260721:91` 標為「parity/drift test 仍可能失敗」的待補項。 |
| Event log / KB hits | `none — event_search q="skill shipping companion remote" → []；wiki_search q="skillPaths companion skill R9" → []`（`.specbase/` 存在、runner 正常）。 |
| Owning spec / contract | `specs/mcp_r15-self-describing-guide/`（companion 單一來源 doctrine，`design.md:16/:45`、`proposal.md:36` R15.5 one-source：guide / prompts / companion skill 同源）——**F3 直接違反這條 one-source**。`BR_20260721` 宣告要新開 R17 spec 但尚無獨立 spec 目錄。**無任何本 repo spec 管 `GET /skills` 的 archive 格式**；格式契約只存在 fleet SSOT `opencode/specs/mcp-integration-standard/` R9.2，這是它得以偏離而不被自檢的結構原因。 |
| Isomorphic failures | `yes（同 repo）` — F3 本身就是同形失敗：宣告來源 ≠ 服務來源。同 fleet 內 specbase（零 route）、patentmcp（缺 list）、formmcp（空目錄）同屬「R9 遠端半只做一半」家族，機制各異。 |

## 2. 修復方向（venue: bodesign）

規範要求（`mcp-integration-standard` R9.2 / R9.8 / R9.4.1）：

1. **F1**：list payload 的 `name` 改為 bare skill name（現成的 `"skill"` 欄位值）。可保留 `file`/`bytes` 等額外欄位——R9.8 容忍額外鍵，只要 `name` 是 bare name。
2. **F2**：新增 `GET /skills/<name>.zip`（zip 格式）。既有 `.tar.gz` 路徑可保留作為 back-compat，但**必須另外**提供 `.zip`，否則合規 client 取不到。
3. **F3**：對 `mcp.json skillPaths` 宣告的來源與 `assets/skills/` 服務的來源加一個 parity 斷言（測試或啟動時檢查），讓兩者不能無聲漂移。這是 `mcp_r15-self-describing-guide` R15.5 one-source 的既有要求。
4. R9.7.1 producer 端：zip 內不得有絕對路徑、`..` 片段、symlink。

可參考同 fleet 已合格的 Python 實作：`docxmcp/bin/_skill_shipping.py` + `docxmcp/bin/mcp_server.py:7123-7124`。

## 3. 驗證計畫

- 正向：`GET /skills` 的每個 `name` 皆為 bare（無 archive 後綴）；逐個 `GET /skills/<name>.zip` 回 200 且 bytes > 0
- 負向：未知名 → typed 404（非 500、非 200 空 archive）；traversal → 403/404（既有 `path_escape` 檢查已有，需回歸）
- 回歸：既有 `.tar.gz` 路徑若保留，仍須可用
- F3：parity 測試證明宣告來源與服務來源一致（或明文記錄兩者的映射關係）
- 端到端：`McpSkillFetch.materialize` 對本服務回 `kind:"materialized"`
- 機檢：`McpConformanceProbe.run()`（opencode `76d58bb64`）對 bodesign 的 14 個 `MCPSTD_SKILL_LISTED_NOT_SERVED` 消失

---

## 5. External verification (2026-07-30) — verdict FAIL, close withdrawn

I closed this BR on my own live probe. This session then commissioned an
**independent adversarial verification** (session `ses_04d725f79`, model
`codex/gpt-5.6-terra`) with a brief that withheld my conclusions and stated
explicitly that a FAIL verdict was a valuable result, not a failure.

It returned **`verdict=FAIL`**. V1/V2/V3/V5/V6/V7 PASS; V4 and V8 FAIL.

### 5.1 D1 — malformed names answered in three different vocabularies (MINE)

| Input | Before | After |
| --- | --- | --- |
| `GET /skills/bodesign%00.zip` | **400** `SKILL_NAME_INVALID` | 404 |
| `GET /skills/bodesign%00` | **403** `path_escape` | 404 |
| `GET /skills/bodesign.zip%00` | **403** `path_escape` | 404 |
| `GET /skills/nosuch.zip` | 404 | 404 |
| `GET /skills/bodesign.zip` | 200 | 200 (accepting control) |

The verifier reported only the 400. Verifying its claim myself surfaced **two
more shapes it had not probed** (the 403s) — which is the point of §3.3: a
verifier's finding is a lead, not the full extent.

**Why this is a real defect and not pedantry.** R9.7.1 pins the STATUS, not
just the shape: `GET /skills/<unknown>.zip` MUST return a typed `404`. A
consumer branches on the status line, and "this is not a thing I serve" is ONE
condition — it must not be reported in three vocabularies depending on which
internal layer happened to reject it. The 403 was also an information leak: it
confirmed the name had reached the filesystem layer, which a 404 does not.

Root cause, both halves mine:

- `skill_shipping.resolve_skill_dir()` raised the `_SAFE_NAME_RE` rejection with
  status `400`.
- `server.py` `skill_download()`'s static-asset branch answered `403 path_escape`
  when `Path.resolve()` raised `OSError` — which a NUL byte does.

**Why my own test suite passed while this was broken.** The traversal test
asserted `assertIn(status, (400, 404))`. That disjunction *was* the hole: it
accepted exactly the inconsistency the BR is about. A test whose assertion is
wide enough to admit the defect is not a test of that property.

Fixed:
- `services/mcp/skill_shipping.py` — `SKILL_NAME_INVALID` now carries `404`
  (typed code retained so a human still learns *why*).
- `services/mcp/server.py` — the static-asset branch's `OSError`/`ValueError`
  path now answers `404 not_found`, not `403 path_escape`.
- `tests/test_skill_shipping.py` — the loose `assertIn(..., (400, 404))` is now
  an exact `assertEqual(404, ...)`, plus a new
  `test_every_unservable_name_answers_one_status` that asserts the whole SET of
  unservable names speaks exactly `{404}` (with an accepting control, so a
  reject-everything guard cannot pass it).

### 5.2 D2 — unauthenticated `POST /invoke` — NOT this BR, and NOT introduced here

The verifier also found that `POST /invoke` executes tools with no auth on a
`0.0.0.0`-published port. **I reproduced it from the LAN address**, not just
loopback:

```
$ curl -s -X POST http://192.168.125.117:8077/invoke \
    -d '{"name":"bodesign_init","arguments":{}}'
{"ok":true,"doctrine":"<!--\n  bodesign CANONICAL USAGE DOCTRINE …
```

This is real and it is more serious than D1. It is **not** part of this BR:

- `git log -S'Route("/invoke"'` → introduced by `a90c28f` (2026-06-07,
  worker-forwarding), **seven weeks before** this BR's fix commit `8f2e91e`.
- It appears in `8f2e91e`'s diff only as context (an unchanged `async def
  invoke` line adjacent to my edit), not as a change.
- It violates **R12.5** (a write-capable shared service MUST gate calls behind
  an identity turnstile; `auth:{type:none}` is conformant only for a read-only
  service), which is a different rule from the R9 skill-shipping contract this
  BR is about.

Filed separately as `BR_20260730d_invoke_endpoint_unauthenticated_tool_execution.md`.
Folding a pre-existing auth hole into a skill-shipping BR would hide it behind a
closed issue.

### 5.3 What this says about my original verification

My live probe was green and it was **honestly** green — every assertion it made
was true. It was structurally incapable of finding D1 because I probed the
paths I had designed for, and D1 lives in the disagreement *between* paths.
That is not a diligence failure that more care would have fixed; it is the
known limit of self-verification, and it is exactly what an independent
adversarial eye is for.

Two of my own guards should have caught it and did not:

- the test asserted `in (400, 404)` — wide enough to admit the defect;
- the tests call `skill_shipping` directly and never traverse the Starlette
  route, so the 403 branch in `server.py` had **no test coverage at all**.

The second gap remains open (see §6).

## 6. Remaining scope (why this stays PARTIAL, not closed)

1. ~~**D1 fix is committed but NOT deployed.**~~ **DISCHARGED 2026-07-30.**
   Deployed via `BODESIGN_WORKERS=1 ./mcpctl.sh rebuild` (all three images
   rebuilt). Verified INSIDE the running container (the host no longer
   publishes a port, so a host-side probe is no longer even possible — see
   BR_20260730d): all seven unservable shapes
   (`bodesign%00.zip`, `bodesign%00`, `bodesign.zip%00`, `nosuch.zip`,
   `nosuch`, `..%2f..%2fetc%2fpasswd.zip`, `a%00b.tar.gz`) answer **404**,
   with `bodesign.zip` → 200 and `bodesign.tar.gz` → 200 as accepting controls.
2. ~~**No HTTP-layer test coverage.**~~ **DISCHARGED 2026-07-30 — see §7.**
3. ~~**Re-verification after deploy** by a fresh independent verifier.~~
   **DONE — round 2 ran and returned verdict=FAIL. See §7.**

## 7. Round-2 external verification (2026-07-30) — verdict FAIL again

The re-verification §6.3 asked for was commissioned (`ses_04c90dec6`, gpt-5.6,
adversarial brief, read-only). It returned **verdict=FAIL** on the freshly
deployed state. Both new defects are real; I reproduced each before acting.

### 7.1 W1 — a well-formed name past `NAME_MAX` left as a 500

| Name length | Status before fix |
| --- | --- |
| 254, 255 | 404 — correct |
| 256, 300, 1024, 4096 | **500** |

**The verifier's root cause was close but wrong in a way that matters.** It
attributed the raise to `Path.resolve()`. A non-strict `resolve()` is pure path
arithmetic and never touches the filesystem — I confirmed this directly: on the
assets root, `(root / "a"*300).resolve()` returns cleanly. The actual raiser is
the **stat that follows**:

- `skill_shipping.resolve_skill_dir` — `candidate.is_dir()`, which had no `try`
  around it at all;
- `server.py` static-asset branch — `target.is_file()`, which sat **one line
  outside** the `try` that guarded the resolve.

Had I patched what was reported, I would have wrapped `resolve()`, seen the
tests stay green, and shipped the defect a second time. Both stats are now
inside the guard; `OSError` (ENAMETOOLONG, ELOOP, ENOTDIR) means what any other
unservable name means: 404.

### 7.2 W5 — the recurrence is the actual finding

Both BR_20260730 defects landed in the **same unlit place**:

| Round | Defect | Location |
| --- | --- | --- |
| 1 | 403 where the sibling branch said 400 and a plain miss said 404 | `server.py` static-asset branch |
| 2 | over-long name escaping as a bare `OSError` → 500 | same branch (and its sibling) |

That branch was an inline closure inside `run_http()`. Nothing could construct
it without starlette plus a live app, so it carried **zero coverage** while
holding half the "is this name servable?" decision. Twice the two halves drifted
into different answers, and twice a green suite said nothing.

So the fix is structural, not another patch: the decision is extracted to
`skill_shipping.resolve_static_asset()`, a pure function reachable by a plain
`unittest` — no server, no sockets, no HTTP client, no new dependency. The
handler is now transport only. This **discharges §6.2**: the gap was never really
"we lack `httpx`", it was "the decision lives somewhere untestable". Moving the
decision was cheaper than importing a test client, and it removes the branch
rather than merely observing it.

### 7.3 W4 — stale host-external TCP claims

BR_20260730d removed the published port; five spec statements still advertised
`http://<host>:8077/mcp/`. Current-tense claims corrected (`handoff.md`,
`design.md` DD-10 — with a revision note recording *why*, the `mcp_r16`
scenarios). The 2026-06-07 event-log entries are **deliberately left alone**:
they record what was true then, and rewriting them would be falsifying the
record rather than fixing a claim.

### 7.4 Why the suite passed 24/24 while shipping W1

Not a loose assertion this time — §5.3's `in (400, 404)` was already tightened.
The gap was **fixture selection**: every hostile name in the suite was one a
human finds suspicious (traversal, NUL byte, an archive suffix). None was
merely *long*. A guard is only ever tested against the shapes someone thought
to write down, and "well-formed but too long for the OS" is not a shape that
looks like an attack.

Added: a `NAME_MAX` boundary anchor (254/255/256/300/4096 — the seam is exactly
there, since 255 was already a clean 404) and a case set for the newly-testable
static-asset branch, each with an accepting control. 26/26.

### 7.5 Verification of the round-2 fix

- Suite: **26/26**; full-suite regression checked by diffing failing-test NAME
  SETS against a copy of this working tree with only my three files reverted to
  HEAD (peer's 93 uncommitted changes left intact; no `git stash`, which is a
  repo-global stack). **Regressions: none.** The 15F/22E are all pre-existing —
  8 baseline failures even pass on my tree.
- Deployed: `BODESIGN_WORKERS=1 ./mcpctl.sh rebuild`, all three images rebuilt.
- Live, inside the container (the host publishes no port): **25 unservable
  shapes → all 404**, covering the NAME_MAX seam (254/255/256/300/1024/4096, with
  and without extension), three null-byte placements, traversal/encoded/absolute
  forms, and case variance. Accepting controls: `bodesign.zip` → 200
  (1,102,359 B), `bodesign-kb.zip` → 200, `bodesign.tar.gz` → 200,
  `MANIFEST.md` → 200. Without those four, a route that had simply died would
  have passed every negative assertion.

### 7.6 What still stands open

1. ~~**A third independent verification.**~~ **DONE — round 3 ran and returned
   verdict=FAIL. See §8.**
2. **Residual risk carried by BR_20260730d**, unchanged: `/invoke` remains
   unauthenticated *inside* the compose network by construction, since
   core→worker forwarding is built on it. Removing the published port changed
   the reachability boundary, not the authentication posture.

## 8. Round-3 external verification (2026-07-30) — verdict FAIL again

Commissioned per §7.6.1 (`ses_04c786aaa`, gpt-5.6, adversarial, read-only).
**verdict=FAIL.** Three rounds, three FAILs, three distinct defect classes. Each
finding reproduced independently before acting.

The round-3 brief was deliberately harder than its predecessors: enumerate a
wider name space, **independently adjudicate my root-cause claim rather than
accept it**, hunt for *other* unguarded filesystem calls, and **prove the new
tests are not theatre by reverting the fix and confirming they go red**.

### 8.1 What it confirmed (worth recording, because it was load-bearing)

- **X2** — my round-2 root-cause correction was independently verified
  in-container: `resolve()` on a 4096-byte name returns normally; only the stat
  raises `OSError 36`. So the verifier's own round-2 attribution really was
  wrong, and patching what round 2 reported would have fixed nothing.
- **X4** — the tests are not theatre. It did a **surgical** revert in a scratch
  copy (function kept, guard shape restored) and got 5 errors including the
  `NAME_MAX` anchor. That is a better proof than my own: my revert would have
  removed the symbol, which fails for the wrong reason.
- **X5** — `sha256` of `skill_shipping.py` and `server.py` byte-identical across
  git HEAD, host worktree and all three containers; no `/app` bind mount.

### 8.2 D1 — the landing page still advertised the retired endpoint

`GET /` rendered `External (TCP): http://<host>:8077/mcp/`
(`services/mcp/server.py:2049`, plus `install_register` at `:1860` in both
languages).

**This one is mine and it is the sharpest finding of the three rounds.** Round 2
corrected EIGHT declaration sites and missed the only one a user actually looks
at — because it is **generated at runtime**, so it is invisible to a grep of the
tree. I audited the sources of truth and skipped the artifact. That is precisely
the defect class this whole BR family is about (a claim that no longer matches
behaviour), committed *while fixing it*.

### 8.3 D2 — the README contradicted itself

`README.md:11` said "TCP port（對外）… 不需要任何宿主外殼或閘道"; `README.md:92`
said the container does not publish a TCP port. Same file, opposite claims. Same
in `README.en.md`. Fixed both.

### 8.4 D4 — the round-2 extraction was HALF DONE

The verifier was right to push here, and this is the most substantive finding.

Round 2 moved the static-asset half of the servability decision out of the
`run_http` closure and **declared the structural problem solved**. It was not:
the suffix routing and the `list_shippable_skills()` membership gate stayed
behind — still unconstructible without starlette and a live app, still zero
coverage. That is verbatim the condition my own round-2 commit message named as
the root cause of two consecutive defects.

**Half a structural fix leaves the other half free to drift**, which is exactly
how rounds 1 and 2 happened. Now in `classify_skill_request()`, pure and tested;
the closure is transport only. The membership gate is load-bearing — a DECLARED
`.tar.gz` must project from the declared tree (so the format cannot encode a
content difference, the *original* BR_20260730 defect) while a vendored bundle
must fall through to the static file — so the test pins both directions.

### 8.5 D3 — `/tools/<unknown>` answered 200

Reported as "the same defect class one route over", and it was right: an unknown
tool returned 200 with an "Unknown tool" page while an encoded-slash name
returned 404 — one condition, two statuses, precisely what R9.7.1 forbids on
`/skills`. A human reading the page can tell; a client branching on the status
line cannot. Fixed in its own commit (`ba76fd4`) rather than smuggled into a
skill-shipping change. The page **body** is kept — the principle is that the
status be honest, not that help be withheld.

### 8.6 Residual closed: a borrowed guard

`resolve_skill_dir` caught `OSError` but not `ValueError`, which `resolve()`
raises on a NUL byte. It was safe **only because** `_SAFE_NAME_RE` rejects NUL a
few lines earlier — safety borrowed from a guard *outside* the try, while the
sibling function caught both. Safe-by-ordering is how two guards drift apart;
both now catch both.

### 8.7 Verification

- Suite **30/30**. Regression by diffing failing-test NAME SETS against a copy
  of this tree with only my three files reverted to HEAD (peer's uncommitted
  work intact, no `git stash`): **none**.
- Deployed twice (`BODESIGN_WORKERS=1 ./mcpctl.sh rebuild`), all three images.
- Live in-container: landing page **0** host-external endpoint claims in both
  languages; **17** unservable `/skills` shapes → all 404 with **5** accepting
  controls at 200; `/tools/<unknown>` → 404 with three real tools still 200 and
  `/`, `/tools`, `/healthz`, `/skills` unaffected.
- One apparent non-conformance was **run down and dismissed**: `/tools/` → 200
  is `urllib` following a 307 to the `/tools` index. Confirmed by raw socket;
  identical for `/skills/`, and identical for real and fake names, so it is no
  existence oracle.

### 8.8 The pattern across three rounds

| Round | Found | Where it hid |
| --- | --- | --- |
| 1 | 403/400/404 for one condition | untested `server.py` closure |
| 2 | over-long name → 500 | same closure + its sibling; no *long* fixture |
| 3 | runtime-generated page still advertising a retired endpoint; extraction only half applied | an artifact grep cannot see; the half I declared done |

Each round found what the previous could not, and **none of them was found by
me**. My own probes were honestly green every time. The recurring shape is not
carelessness — it is that self-verification tests the paths one designed, and
every one of these defects lived in a place the design did not look.

### 8.9 What still stands open

1. **A fourth independent verification.** On this evidence the prior that any
   round is the last one should stay low.
2. The verifier's own declared blind spots, which I am carrying forward rather
   than discarding: it probed **statuses, not payloads** (never verified that
   `bodesign.zip` holds the *current* 169 files — notable, since content drift
   was the ORIGINAL defect); it used a human-authored probe list, not a fuzzer;
   it did not measure the cost of rebuilding a ~1.1 MB archive per request; and
   it verified the deployed artifact, not the build pipeline.
3. **BR_20260730d residual**, unchanged (§7.6.2).

---

## 9. Round 4 — external verification (verdict FAIL), and the half that was never fixed

Verifier: `codex/gpt-5.6-terra`, brief aimed at the blind spot round 3 declared
honestly — *"I verified statuses, never payloads"* — which happens to be the
axis of the ORIGINAL defect. Verdict **FAIL**, six defects. I reproduced all six
myself before touching anything; each fix below carries a guard that was
mutation-tested to actually go red when the fix is reverted.

### 9.1 D4 — the original defect, alive in the half that was never fixed

This is the finding that matters. The BR opened on a frozen `.tar.gz` served
beside a source tree that had moved on. That was fixed for the **declared**
skills. The **vendored** half was left exactly as it was.

Two of the 13 bundles have in-repo sources — `kicad` and `kidoc` were folded
into the unified skill as `skills/bodesign/engines/{kicad,kidoc}`. What was
being served:

| bundle | live-only files | byte-differing | frozen |
| --- | --- | --- | --- |
| `kicad.tar.gz` | 12 (incl. `ENGINE.md`, `netlist_to_kicad_sch.py`) | 9 | 2026-06-07 |
| `kidoc.tar.gz` | 1 (`ENGINE.md`) | 1 | 2026-06-07 |

The same shape, the same 7-week staleness, in the same repo, while
`MANIFEST.md` asserted all 13 bundles *"have no source tree in this repo"* —
false for exactly these two.

Fix: `resolve_engine_bundle()` discovers a source by walking the declared tree
(`<skill>/engines/<name>`), never a hardcoded list, and a name that has one is
projected through the same deterministic packer as the declared skills. Only a
name with genuinely no source reaches the static branch. The frozen copies are
unreachable. Accepting control kept: `jlcpcb.tar.gz` (no source) still serves.

### 9.2 D1 — 75 dead links on the only live entry path

`docker-compose.yml` set `BODESIGN_HTTP_BASE: "/bodesign"` unconditionally,
asserting a prefix-stripping gateway that does not exist on this host. Every
link the landing page rendered — 75 of them — was answered 404 by the same
server. Same class as round 3's D1: a **generated** surface, invisible to grep,
contradicting reality. The declaration is now opt-in, set only where such a
gateway is actually deployed.

### 9.3 D2 — `.tar.gz` was not byte-reproducible

Every tar member already carried `_FIXED_MTIME`, but `tarfile.open(mode="w:gz")`
writes the **wall clock** into the gzip wrapper's header. Four requests gave two
distinct outer sha256 over one identical inner tar. That makes *"did the shipped
skill change?"* unanswerable by hash for that format — the precise question R9.11
exists to answer, and a consumer diffing hashes would have learned to ignore the
signal. Now `gzip.GzipFile(mtime=0)` over a `mode="w"` tar.

### 9.4 D3 — the image is not reproducible from a clean clone

A clean clone at the commit yields 164 shippable files; the running container
serves 169. The five extra are **untracked working-tree files** swept in by
`COPY skills` — and they belong to another agent's in-flight work, so silencing
the difference is not mine to do. What is mine is to stop it being invisible:
`/health` now publishes `skill_source` (per-skill file count + content digest),
so two deployments claiming one version while serving different trees differ in
one observable field.

### 9.5 D5 — the parity gate asserted presence, not parity

Reproduced: a tree holding a single truncated `SKILL.md` — or an outright decoy
reading *"NOT the real source"* — passed the startup gate and served a 135-byte
"skill". A gate that cannot fail on an empty entry point is decoration, which is
the accusation this BR has already levelled at its own tests twice.

Added a substance floor (entry ≥512B, ≥5 files) **with its limit written into
the docstring rather than implied away**: it proves the tree is structurally
capable of being what the server claims, *not* that the content is correct, and
it still runs once before bind. Overclaiming here would repeat the exact error
the gate was caught making.

### 9.6 D6 — the third recurrence of one structural condition

Round 3 fixed `/tools/<unknown>` to answer 404 — and left the decision inside
the `run_http` closure. Reverting `else 404` to `else 200` left the entire suite
green. An unguarded fix, in the same unlit place this BR has now named three
times as the root cause of every defect it has found. Lifted to module scope
(`tool_detail_status`) with a guard and an accepting control over all 57 tools.

### 9.7 Verification

- `tests/test_skill_shipping` **38** (+8), `tests/test_mcp_server` +2
- **Mutation-tested guards** — reverting each fix goes red: D2 (drop `mtime=0`)
  → 1F, D4 (drop engine routing) → 1F, D5 (zero the floor) → 2F, D6
  (`return 200`) → 1F. A guard that survives its own fix being undone is not a
  guard.
- **Zero regression** — failing-test-NAME-SET diff against a copy of the working
  tree with only my six files reverted to HEAD: `comm -13` empty, 37 pre-existing
  failures identical on both sides. Never by counting; never with `git stash`.
- **Deployed** (`051786c`, three images rebuilt, **no `/app` bind mount** — so
  what follows is the image's behaviour, not a dev-mount illusion):

| check | result |
| --- | --- |
| `.tar.gz` × 4 requests | **one** sha256; gzip header MTIME `0` |
| landing page | 75 links, **0** prefixed, **0** non-200 |
| `kicad` / `kidoc` `.tar.gz` | projected: 60 / 71 members, `ENGINE.md` present, MTIME 0 |
| `jlcpcb.tar.gz` (no source) | 200 — static branch intact |
| `/health.skill_source` | `bodesign` 169 files `f05a9429…` |
| `/tools/<unknown>` | 404; 57 real tools + index 200 |
| 14 unservable shapes | **all 404**; 5 accepting controls 200 |
| containers | 3 healthy, `Ports=[]` |

### 9.8 The pattern, four rounds in

| Round | Found | Where it hid |
| --- | --- | --- |
| 1 | one condition, three statuses | untested `server.py` closure |
| 2 | over-long name → 500 | same closure; no *long* fixture |
| 3 | generated page advertising a retired endpoint; extraction half-done | an artifact grep cannot see; the half I declared done |
| 4 | the original defect alive in the vendored half; a gate that asserts presence; a fix no test guards | **the half nobody thought to look at**, three times over |

Round 4's shape is distinct and worth naming: rounds 1–3 found defects in code I
had *touched*. Round 4 found the defect I had **decided was out of scope** — the
vendored bundles were classified as "no source, cannot satisfy parity" in round
1, and that classification was never re-examined against the filesystem. A wrong
premise survives every test built on top of it.

### 9.9 Still open

1. **A fifth independent verification.** Four rounds, four FAILs, each finding
   what the previous could not. The prior that any given round is the last one
   should stay low.
2. **The verifier's own declared blind spots**, carried forward rather than
   discarded — and it named the sharpest one yet: *"I verified content equality,
   never content correctness. Nobody in four rounds has asserted that the shipped
   skill actually **works** when installed."* No round has extracted the archive
   into a real skill layout and run it. That is the next axis.
3. **Startup-only parity** (§9.5 limit) — a post-boot mutation of a live-bound
   tree is served unchecked. Closing it needs a build-time content pin.
4. **BR_20260730d residual**, unchanged (§7.6.2).

---

## 10. Round 5 — the consumer axis, and the defect my own fix introduced

Verifier: brief aimed at the blind spot round 4 declared honestly — *"I verified
content EQUALITY, never content CORRECTNESS. Nobody in 4 rounds has asserted
that the shipped skill actually WORKS when installed."* Verdict **PARTIAL**.

### 10.1 Z1 PASS — the shipped skill does work

Five rounds in, this is the first time anyone extracted the archive and ran it.
Downloaded `bodesign.zip` from inside the container, extracted into a real skill
layout, and interrogated it as a consumer:

| check | result |
| --- | --- |
| skill root | single `bodesign/SKILL.md`, 169 files |
| frontmatter | valid YAML, `name: bodesign` matches the directory |
| `gate.py --help` / `--list` | exit 0, runs from the extracted tree |
| verb table | **59 verbs, byte-identical** to the in-image `gate.py --list` |
| `doctrine.md` | 254 lines of real content, not a stub |

The axis nobody had tested turned out to be sound. Worth stating plainly,
because four rounds of FAIL make it tempting to assume everything is broken.

### 10.2 Z2 FAIL — round 4's fix broke the thing it claimed to preserve

**This defect is mine, and it was introduced by the previous round's fix.**

Making `kicad`/`kidoc` current (§9.1) also made them **non-installable**:

```
old kicad.tar.gz  ->  kicad/SKILL.md      (frozen, installable)
new kicad.tar.gz  ->  kicad/ENGINE.md     (current, NOT installable)
MANIFEST.md:73    ->  tar -xzf kicad.tar.gz -C ~/.claude/skills/
```

The live `engines/<name>` trees carry `ENGINE.md` — they lost their standalone
entry point when they were folded into the unified skill. So the projection is
faithful *to the source* and simultaneously breaks *the install contract the
docs still advertise*. I traded a stale-but-installable artifact for a
fresh-but-uninstallable one, and wrote down only the half that flattered the fix.

**Synthesizing a `SKILL.md` during projection was considered and rejected.** It
would manufacture a declaration that no source makes — the exact failure this BR
family exists to stop. The archives stay reachable (a published URL should not
404 on an unrelated fix), but the documentation now says what they are: engine
trees, not skills.

### 10.3 A third stale copy, found while fixing the second

Not in the verifier's report — found while checking whether the fix was
complete. The composite `bodesign-eda-skills-bundle.tar.gz` embeds **a third
copy** of kicad/kidoc, still frozen at 2026-06-07:

| embedded | live-only | byte-differing |
| --- | --- | --- |
| `kicad/` (50 files) | 12 | 9 |
| `kidoc/` (71 files) | 1 | 1 |

The original defect lived in **three** places. Round 4 found and fixed two of
them and I declared that half done. The composite has no in-repo source, so it
cannot be projected like the other two — it is now **disclosed in MANIFEST with
its exact drift numbers**, and a test asserts the shadow may not GROW past them.
Disclosure without a guard is just a comment; the ceiling is what makes it a
claim.

### 10.4 Claims bound to bytes

The Z2 fix is documentation, which is precisely the kind of change that rots
silently. So each claim is now a test:

- engine trees carry `ENGINE.md` and **not** `SKILL.md` — fails in *either*
  direction, so a future change that adds one also turns the docs red
- declared skills **do** carry `SKILL.md` — accepting control; without it,
  stripping `SKILL.md` from everything would satisfy the assertion above
- the composite's stale shadow may not grow past the disclosed numbers —
  mutation-tested by tightening the ceiling to zero → 2 failures

The Contents table also gained an "installable skill?" column. My first pass
filled **3 rows and left 6 with the wrong column count** — the same half-a-fix
this BR has now flagged four times, committed by me, inside the commit fixing a
half-a-fix. Caught by checking, not by care.

### 10.5 Verification

- `tests/test_skill_shipping` **41** (+3); no production code changed this round
- **Zero regression** — 37 failing test names, identical set to §9.7
- Deployed (`e8e2e51`, three images rebuilt, **no `/app` bind mount**):

| check | result |
| --- | --- |
| served `MANIFEST.md` | 7638B; "no longer standalone-installable" present, `-C ~/.claude/skills/` for kicad **gone** |
| `kicad` / `kidoc` `.tar.gz` | 60 / 71 members, `ENGINE.md` yes, `SKILL.md` **no**, gzip MTIME 0 |
| accepting controls | `bodesign.zip` / `bodesign-kb.zip` / `.tar.gz` / `jlcpcb.tar.gz` all 200 |
| 11 unservable shapes | all 404 |
| containers | 3 healthy, `Ports=[]` |

### 10.6 The pattern, five rounds in

| Round | Found | Where it hid |
| --- | --- | --- |
| 1 | one condition, three statuses | untested `server.py` closure |
| 2 | over-long name → 500 | same closure; no *long* fixture |
| 3 | generated page advertising a retired endpoint | an artifact grep cannot see |
| 4 | the original defect alive in the vendored half | the half I ruled out of scope |
| 5 | **the previous round's fix broke the install contract** | the half of the consequence that flattered the fix |

Round 5's shape is new again. Rounds 1–4 found pre-existing defects. Round 5
found a defect **the immediately preceding fix created** — and the mechanism was
not carelessness: the fix had two consequences, one good and one bad, and I
recorded the good one. A fix is a change, and a change has a blast radius that
does not stop at the thing it was aimed at.

### 10.7 Still open

1. **A sixth verification.** Five rounds, five non-PASS verdicts. The prior that
   any given round is the last one should stay low — and round 5 adds a reason:
   a round can *introduce* the defect the next one finds.
2. **The verifier's declared blind spot**, carried forward: Z1 proved the archive
   *parses, imports and lists* — it never ran a real verb against a real project
   folder, and never fed the frontmatter to an actual skill loader. A verb that
   imports cleanly and crashes on invocation would pass everything it did.
3. **The composite bundle's stale kicad/kidoc shadow** (§10.3) — bounded and
   disclosed, not fixed. It has no in-repo source; fixing it means regenerating
   it from the live tree or retiring it.
4. **Startup-only parity** (§9.5 limit) — unchanged.
5. **BR_20260730d residual**, unchanged (§7.6.2).

---

## 11. Round 6 — the first round that RAN the thing, and what it found

Verdict: **PARTIAL**. Five rounds had checked whether the archive was *correct*.
Round 6 was the first to ask whether it *works*, by extracting `bodesign.zip`
into a real skill layout and invoking verbs against a scratch project.

### 11.1 The good news, stated plainly

Four rounds of FAIL make it easy to assume everything is broken. This is the
first independent confirmation that the shipped artifact is genuinely usable:

| Check | Result |
|---|---|
| Skill root | single `bodesign/SKILL.md`, 169 files |
| Frontmatter | valid YAML, `name` matches the directory |
| `gate.py --help` / `--list` | exit 0 from the extracted tree |
| Verb roster | 59 verbs, byte-identical to the in-image copy |
| `doctrine.md` | 254 lines of real content, not a stub |
| Verbs executed with `BODESIGN_SRC` set | `package_readiness`, `c04_readiness`, `c06_readiness` all ok; `c00_readiness` correctly errors on an absent artifact |

### 11.2 Y1 — the archive is not self-sufficient, and only the error said so

Reproduced verbatim inside the container:

```
$ cd <extracted>/bodesign && python3 scripts/gate.py c00_scaffold_prd --arg out_dir=/tmp/x
{"ok": false, "verb": "c00_scaffold_prd", "error": {
  "code": "LANDING_PACKAGES_NOT_FOUND",
  "message": "could not find bodesign packages/ (looked for packages/workflow-core); ...
              Set BODESIGN_SRC=/path/to/bodesign repo.",
  "hint": "export BODESIGN_SRC=<bodesign repo root containing packages/*>"}}

$ find <extracted> -path '*packages*' | wc -l
0
```

The archive ships the guidance and `scripts/gate.py`, but not the four
`packages/*` the verbs import. So a bare install can run `--list` — a static
registry, zero dependencies — and nothing else.

**This is not a bug in the split.** The packages are large and version-coupled
to the repo; keeping them out is a defensible architecture, and the failure is
loud and typed rather than silent. What was wrong is *where the requirement was
written down*: `SKILL.md:248` disclosed `BODESIGN_SRC` for XDG installs, but
MANIFEST's **Install** section — the thing a person actually follows when
installing — said "extract where your skill manager expects them" and stopped.
A reader following it hits an undisclosed hard error on their first real verb.

Fixed by disclosing at the install step (`MANIFEST.md`, new subsection *What the
installed skill can and cannot do on its own*), with the shape pinned by tests:
if the archive ever *becomes* self-contained, the disclosure becomes a lie and
`test_zip_really_omits_the_packages_the_verbs_import` fails, forcing its removal.

### 11.3 Found while reproducing: the docs restated counts that had drifted

Not in the verifier's report; surfaced by checking the claim around the defect.

| Site | Claimed | Live |
|---|---|---|
| `SKILL.md:233` | 52 landing verbs | **59** |
| `SKILL.md:252` | 43 MCP tools | **57** |
| `README.en.md:76`, `server.py:48` | 52 | **59** |

Replacing 52 with 59 would swap one rotting number for another — a hand-copied
count *is* a second declaration, which is precisely the failure this BR family
exists to stop. The prose now points at `gate.py --list` and `/tools`, the
sources that cannot drift, and a test forbids the pattern from returning.

`README.md`'s 0.2.0 changelog entry keeps its `52`: it records what was true on
that date. Rewriting it would be falsifying a record, not fixing a claim — the
same line already drawn for the 2026-06-07 event log in §7.

### 11.4 Defect 2 — the shadow guard capped growth but was blind to shrinkage

`test_composite_bundles_stale_engine_shadow_does_not_grow` asserted `<=` against
the disclosed drift (12/9, 1/1). But MANIFEST publishes **exact** figures, so a
deleted live file — or live and composite rotting in lockstep — shrinks the
measured drift, leaves the published number wrong, and keeps the test green.

Now asserts equality in both directions. The mutation pair is the proof:

```
delete a live-only engine file  + exact assertion  -> 3 failures
delete a live-only engine file  + old `<=`         -> 2 failures
```

That one-failure delta is the blindness, measured rather than argued.

### 11.5 Guards (each reddens when its own fix is reverted)

| Mutation | Result |
|---|---|
| strip `BODESIGN_SRC` from the Install section | 1 failure |
| restore the hand-copied "52 deterministic" | +1 failure |
| name an error code `gate.py` does not raise | accepting control fires |
| delete a live-only engine file | exact guard reddens; reverting to `<=` goes green |

45 tests (+4). Zero regressions: failing-name set identical to HEAD (37 both
sides), compared by name via a copied tree with only the five changed files
reverted — no `git stash`; the peer's 86 uncommitted changes untouched.

### 11.6 Post-deploy verification (`05afc9d`, three images, no `/app` mount)

| | |
|---|---|
| Served MANIFEST | 8824 B; Install section carries `BODESIGN_SRC`, `LANDING_PACKAGES_NOT_FOUND`, `--list` |
| Shipped `SKILL.md` | **0** hand-copied count patterns |
| Archive | 169 members, `gate.py` present, `packages/*` = **0** (the disclosure matches the artifact) |
| `/health` | `tools=57`, `skill_source.bodesign.files=169` |
| Accepting controls | `bodesign.zip` / `bodesign-kb.zip` / `kicad.tar.gz` / `MANIFEST.md` / `/tools` — all 200 |
| Unservable regression | 7 shapes incl. NUL and NAME_MAX — status set `{404}` |

### 11.7 What six rounds have shown about the rounds themselves

| Round | What it found | Why the previous round missed it |
|---|---|---|
| 1 | one condition, three statuses | untested route closure |
| 2 | overlong name → 500 | no fixture that was merely *long* |
| 3 | runtime-generated page still advertised a retired endpoint | grep cannot see a generated artifact |
| 4 | the original defect alive in the half declared out of scope | a wrong premise survives every test built on it |
| 5 | a defect *created by* round 4's fix | a change has consequences past the one it targets |
| 6 | the artifact was never *run* | five rounds inspected; none invoked |

### 11.8 Still open

1. **A seventh verification.** Six rounds, six non-PASS verdicts. Round 6's own
   declared blind spot is the natural next target: it ran **4** of 59 verbs, and
   never fed the frontmatter to a real skill loader (no loader in-container).
2. **Verb-level correctness at large** — 55 verbs are import-clean but unrun. A
   verb that returns a silently empty or degraded result would pass everything
   done so far.
3. **The bare-host scenario** — no round has confirmed end-to-end whether
   "installed with no bodesign checkout anywhere" is intended to work. §11.2
   documents the requirement; it does not settle the product question.
4. **The composite bundle's stale shadow** (§10.3) — bounded, disclosed, now
   guarded in both directions; still not fixed.
5. **Startup-only parity** (§9.5) and **BR_20260730d residual** (§7.6.2) — unchanged.

---

## 12. Round 7 — two omitted declarations, one of them inside the fix for the last one

Verdict: **PARTIAL**. Round 7 drove ~30 of the 59 verbs against a real
`BODESIGN_SRC`, ran opencode's actual `gray-matter` parser against the shipped
frontmatter, and fact-checked §11's new disclosure line by line.

### 12.1 What it cleared

| Target | Result |
|---|---|
| Z2 — real skill-loader acceptance | **PASS** — shipped `SKILL.md` parses under opencode's own `gray-matter`; `name`/`description` satisfy `Info.pick({name,description})`; name matches dir |
| Z3 — §11's install disclosure | **PASS** — every factual claim verified: 164/169 members with zero `packages/`, `--list` works zero-dep, bare verb → `LANDING_PACKAGES_NOT_FOUND`, and the four named packages are exactly the gate's import roots |
| Z1 — ~30 verbs driven | no crashes, **no silent-empty successes** — empty results carry honest `status:"missing"` / `"source_blocked"` / `error_code` |

The Z1 result matters most: this BR family is about something claiming success
while shipping nothing, and 30 verbs' worth of evidence says the landing plane
does not do that.

### 12.2 D1 — `--repo` is required by every verb and declared by none

```
$ BODESIGN_SRC=/app python3 <skill>/scripts/gate.py impedance_solve \
    --json '{"stackup":{"layers":[]},"targets":[]}'
{"ok": false, "error": {"code":"VERB_ARGS_INVALID",
                        "message":"--repo <absolute project dir> is required"}}

$ ... --list | jq '.result.verbs[] | select(.verb=="impedance_solve").required_args'
["stackup","targets"]          # both satisfied above
```

`gate.py:764` enforces `--repo` unconditionally, before any per-verb check, but
it appears in no verb's `required_args`. So a caller reads the roster, satisfies
every argument it lists, and still fails. **16 verbs need neither `folder` nor
`out_dir`** and are hit hardest — `impedance_solve`, `pin_allocation`,
`plan_design_intent`, `agent_registry`, `rca_spec_audit`, `c02_plan_intent`,
`reference_crosscheck`, `evidence_manifest` among them.

Same shape as §11.2: a declaration that omits a requirement. Fixed by stating it
once in `--list` as `always_required`, not by injecting it into 59 arg lists —
it is a property of the CLI, not of any verb's signature. **CLI behaviour is
unchanged**; existing callers keep working.

One claim in the report I did **not** sustain: the traceback visible when
`--repo` is supplied is stderr noise around a properly typed
`VERB_RUNTIME_ERROR` envelope on stdout, exit 0. Not a defect.

### 12.3 D2 — the guard I added last round was green for the wrong reason

§11's count guard matched only the two literal phrasings that happened to exist
in the tree:

```
'the 52 deterministic verbs'  -> ['52 deterministic']   caught
'the 52 repo-local verbs'     -> []                     MISSED
'57 MCP tools'                -> []                     MISSED
'43 container tools'          -> []                     MISSED
'52 verbs'                    -> []                     MISSED
```

I wrote it against the two strings I had just removed, so it could only ever
re-catch those two. It now matches on **shape** — a number qualifying a
verb/tool noun — with two documented exclusions: HTTP status codes ("answered
200 for a tool that does not exist") and identifier tails ("Bucket-2 verbs",
"R17.2 tools").

**Broadening it immediately caught a real one the narrow version had hidden**:
`README.en.md:89` still said "the container's 43 MCP tools". Round 6 fixed that
file's `52` and left its `43` standing — and the guard I wrote in the same
commit was structurally incapable of seeing it.

### 12.4 The part worth recording: I repeated the family defect inside the fix for it

My first D2 fix added a capability test that ran the pattern over synthetic
strings — and kept its **own copy** of the regex. Mutation test:

```
narrow the LIVE guard back to the round-6 form   ->  47 tests, all green
```

The capability test was proving *its duplicate* worked. A second declaration of
the very rule this BR family exists to stop, written into the fix for a second
declaration. Pattern and exclusions now live in one module-level
`count_restatements()` that both callers use; narrowing it now reddens 5 tests.

This is the second time in this BR that a fix created the defect the next check
found (§10 was the first). The mechanism is not carelessness — it is that a fix
is written while looking at the thing being fixed, so its own shape goes
unexamined.

### 12.5 Guards (each reverts to red)

| Mutation | Result |
|---|---|
| drop `always_required` from `--list` | 1 failure |
| narrow the **shared** pattern to the round-6 form | 5 failures |
| delete the status-code exclusion (over-broad guard) | 2 failures |
| restore `README.en.md`'s "43 MCP tools" | 1 failure |

47 tests (+2). Zero regressions: failing-name set identical to HEAD (37 both
sides), compared by name via a copied tree with only the three changed files
reverted — no `git stash`; the peer's uncommitted changes untouched.

### 12.6 Post-deploy verification (`d01d10e`, three images, no `/app` mount)

| | |
|---|---|
| Shipped `--list` | keys `[always_required, count, not_landing, verbs]`; `--repo` disclosed; count 59 |
| Shipped `SKILL.md` | **0** count restatements under the broadened pattern |
| Served MANIFEST | **0** restatements; §11's three install tokens still present |
| Accepting controls | `bodesign.zip` / `bodesign-kb.zip` / `kicad.tar.gz` / `MANIFEST.md` / `/tools` — all 200 |
| Unservable regression | 7 shapes incl. NUL and NAME_MAX — status set `{404}` |

### 12.7 Still open

1. **~29 verbs remain uninvoked** — the C01 answer-state mutators and the C00
   orchestration tick/dispatch spine were never driven end-to-end. Nothing
   crashed on the paths hit, but the stateful loop is unexercised.
2. **A silent-empty shape outside this BR's scope**: `pin_allocation` given a
   malformed net (`{"name","pin"}` instead of `{"nodes":["REF.PIN"]}`) returns
   `ok:true` with `net_count:0` and no signal. Correctly shaped input works.
   This is the exact failure shape this BR family is about, in a different
   surface — worth its own BR rather than folding in here.
3. **Round 7's own blind spot**: it ran opencode's parser and schema in
   isolation, not a live `skill()` load through the daemon's directory scan.
4. **A possible committed-tree inconsistency** it flagged and did not chase: a
   `_vendor_sym_scale` ImportError when running from a `git archive HEAD` tree,
   while the working tree and container are fine. Out of scope here; needs its
   own look.
5. **The composite bundle's stale shadow** (§10.3), **startup-only parity**
   (§9.5), **BR_20260730d residual** (§7.6.2) — unchanged.
