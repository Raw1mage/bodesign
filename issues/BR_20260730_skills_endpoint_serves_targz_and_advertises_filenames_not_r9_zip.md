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
Fix: PARTIAL (2026-07-30, ses_04db7a1c5 — bodesign coordinator, full ownership per a2a-d2d §3.1.1)
Effect: F1/F2/F3 deployed and live-verified against the built image (no dev mounts) — see §4.6
        D1 (status-code uniformity) fixed in the tree but NOT yet deployed — see §5
Custody: bodesign
Blocker: none
Disposition: accepted — accepted as a real defect; RCA found it WORSE than reported (see §4)
Venue: bodesign
Status: REOPENED -> PARTIAL. Was CLOSED 2026-07-30 on my own live probe; an INDEPENDENT
  adversarial verification (ses_04d725f79, gpt-5.6, commissioned by this session) returned
  verdict=FAIL and found a real defect my probe had missed. The close was premature and is
  withdrawn. See §5 for what the external eye caught that my own verification structurally
  could not.
Reopened: 2026-07-30 by ses_04db7a1c5 (bodesign coordinator), on external verdict=FAIL
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

1. **A third independent verification.** Round 1 found what my probe could not;
   round 2 found what round 1 did not. The prior on "this round found
   everything" should stay low.
2. **Residual risk carried by BR_20260730d**, unchanged: `/invoke` remains
   unauthenticated *inside* the compose network by construction, since
   core→worker forwarding is built on it. Removing the published port changed
   the reachability boundary, not the authentication posture.
