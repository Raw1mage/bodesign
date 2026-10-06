# DD-9 Clearance — elkjs (ELK layered) as pinned EE dependency

**Status: CLEARED-WITH-CONDITIONS (architecture review, 2026-10-06) for bounded S3
engineering integration only — not blanket distribution/legal clearance. Nothing installed
at the time of this verdict.** Conditions binding on S3 (verbatim summary of the verdict;
the body below is the pre-verdict draft and is corrected by these where they conflict):
1. EPL-2.0 selected for unmodified elkjs. Public URLs are not proof of corresponding-source
   availability; EPL commercial-distribution obligations are release-owner obligations, not
   reduced to "no action". §2:33-34 overstates — treat as compliance obligations.
2. Strike "GPL-only … none possible" (:36). Empty npm `dependencies` proves only no declared
   runtime npm deps; build-time code compiled into shipped JS may carry obligations — inventory
   shipped/bundled notices before distribution. Attestation *existence* is not verified SLSA
   provenance; do not infer npm gitHead == verified tag commit without checking.
3. `web-worker` optional dep stays OUT. Backend = in-process bundled elkjs in one bounded Node
   child per emit (no warm pool/service). Timeout / nonzero / malformed result ⇒ explicit
   refusal, never legacy router. Verify the installed lock graph contains only expected packages.
4. Node source = official nodejs.org Node 22 maintenance-LTS tarball, pinned patch + platform,
   SHA256 verified against signed release checksums. No NodeSource, no apt Node, no new
   multi-stage image for the spike. Unsupported arch fails explicitly. Retain Node/npm bundled
   licenses. Confirm xz/system-lib prerequisites. No placeholder pins in an accepted Dockerfile.
5. Ownership: `packages/eda-bridge/elk/{package.json,package-lock.json,runner.cjs}`;
   `packages/eda-bridge/bodesign_eda_bridge/elk_layout.py`; `npm ci --omit=dev --ignore-scripts`;
   no globals; no engine code under services/mcp. Notices: `packages/eda-bridge/THIRD_PARTY_NOTICES.md`,
   S3 implementer owns the initial entry; 3.6 consolidates later.
6. Dockerfile.ee only. Monolith (`Dockerfile`) explicitly unsupported for this engine until
   separately packaged. Record measured image / build / cold-start / RSS; unmeasured stays
   unmeasured, not invented, and is not a blocker to one-leaf acceptance.
Scope: DD-15 (`design.md:252-277`) engine adoption, governed by DD-9 (`design.md:98-101`).
Evidence fetched 2026-10-06. No npm/node executed against the repo; no Dockerfile edited.

## 1. Upstream identity

| Item | Value | Evidence |
|---|---|---|
| Repository | `https://github.com/kieler/elkjs` | registry `repository.url` |
| Latest tagged release | `0.12.0` (tag has no `v` prefix), published 2026-07-17 | `https://api.github.com/repos/kieler/elkjs/releases/latest` → `tag_name: "0.12.0"`, `html_url: .../releases/tag/0.12.0` |
| npm package | `elkjs@0.12.0` (`dist-tag latest`) | `https://registry.npmjs.org/elkjs/0.12.0` |
| `dist.tarball` | `https://registry.npmjs.org/elkjs/-/elkjs-0.12.0.tgz` | same |
| `dist.integrity` | `sha512-YZcKynxVxYoKIOEpywEPwCFdg+BTbxQRNf3pbwdDCvc8O3kQD8bmIwSxKU1eOTVc4Xo+VG9Te+575mlfvOrhEQ==` | same |
| `dist.shasum` | `7dc1bc71ab8f402d1b6564e2fa509ca1caee276c` | same |
| `gitHead` | `ff5771d7165445c42c408bb8a090c8035272218c` | same |
| Provenance | SLSA v1 attestation, trusted publisher GitHub Actions OIDC | registry `dist.attestations`, `_npmUser.trustedPublisher` |
| Unpacked size | 8,046,232 bytes, 12 files (`files: ["lib"]`) | registry `dist.unpackedSize`; tag `package.json` |

`design.md:263-264` inspected `master/package.json` (0.13.0, moving). This document supersedes that with the frozen release above.

## 2. License

- `package.json` `license` at tag `0.12.0`: `"EPL-2.0 OR GPL-3.0-or-later"` — `https://raw.githubusercontent.com/kieler/elkjs/0.12.0/package.json`; registry metadata agrees.
- `LICENSE.md` at tag `0.12.0`: full EPL-2.0 text; Exhibit A reads "…Secondary Licenses … GNU General Public License v3.0 or later" — `https://raw.githubusercontent.com/kieler/elkjs/0.12.0/LICENSE.md`. No separate GPL file in the repo root (`https://api.github.com/repos/kieler/elkjs/contents/?ref=0.12.0`).
- Source headers (`lib/elk-api.js`): `Copyright (c) 2017 Kiel University and others.` / `SPDX-License-Identifier: EPL-2.0 OR GPL-3.0-or-later`.
- Release note: "elkjs 0.12.0 adds GPL-3.0 as a secondary license" (GitHub release body). Older releases are EPL-2.0 only.
- **Astra's report "EPL-2.0 OR GPL-3.0-or-later" is CONFIRMED.**

**Selected option: EPL-2.0.** Obligations when consumed as an unmodified npm dependency:
- EPL-2.0 §3.3: retain all copyright/attribution/disclaimer notices in any copy we distribute (the `lib/*.js` headers and `LICENSE.md` stay inside `node_modules/elkjs` in the image; add our own notice entry, §5 below).
- EPL-2.0 §3.1(a)/§3.2: source availability applies to *the Program* (elkjs itself); it is satisfied by pointing to the public npm tarball/GitHub tag. Our Python/JS caller is a separate work that only invokes the API, not a "Modified Work" (§1 definition excludes files that merely link/bind by name). **No source-disclosure obligation for bodesign code.**
- EPL-2.0 §4: if shipped commercially, we indemnify upstream Contributors for claims arising from *our* product claims/warranties — standard, no action beyond not making warranties on their behalf.
- We do NOT exercise the GPL secondary option; EPL-2.0 §2(e) means no additional grants flow from it.
- GPL-only transitive dependency: **none possible — runtime `dependencies` map is empty (§3).** The only optional runtime add-on, `web-worker@1.4.1`, is a `devDependency` and not needed (README "node.js" section: elkjs falls back to in-process when absent). Flag: do not add `web-worker` without its own clearance.

## 3. Dependency inventory

- Registry metadata for `elkjs@0.12.0` has **no `dependencies` key** (only `devDependencies`: @babel/*, browserify, chai, chai-as-promised, mkdirp, mocha, web-worker). `npm ci --omit=dev` installs exactly one package.
- Bundled Java-origin ELK: GitHub release body states **"Based on ELK 0.12.0"**; ELK release notes `https://eclipse.dev/elk/downloads/releasenotes/release-0.12.0.html` (#1185/#1191/#1184 add GPL-3.0 secondary license; #1194, #1170 layered changes). `build.gradle` at the tag pins `melk: 0.12.0-SNAPSHOT`, GWT `2.11.0`, Guava `31.1-jre`, Xtext `2.36.0`, emf-gwt `2.12.4` — these are **build-time** inputs compiled into `lib/elk-worker*.js` by GWT, not runtime packages. Guava is Apache-2.0; emf-gwt/Xtext are EPL — no GPL-only build input identified (statement based on the gradle manifest, NOT a per-artifact license scan).
- README (tag) `Releases and Versioning`: minor version tracks ELK; revision may diverge.

## 4. Node layer in `Dockerfile.ee`

Read `/home/pkcs12/projects/bodesign/Dockerfile.ee` (91 lines). Findings:
- Node/npm: **NOT present.** apt list at lines 19-22 is `software-properties-common gnupg ca-certificates curl python3 python3-venv python3-pip ngspice poppler-utils default-jre xvfb wget`; no `nodejs`/`npm`, no NodeSource repo, no nvm.
- Java: present — `default-jre` (line 22) for `/opt/freerouting.jar` (line 23, `FREEROUTING_JAR`/`JAVA_BIN` line 91). Astra's statement confirmed.
- Repo has **no tracked `package.json` / `package-lock.json` / `THIRD_PARTY_NOTICES`** (`git ls-files` grep: 0 hits; only `.venv` vendor copies). S3 must create them.

Minimal added layer (sketch, after line 44 `ato --version`, before line 46 `COPY packages`):
```dockerfile
# elkjs layered engine (DD-15 / DD-9 clearance: plans/.../dd9-clearance-elkjs.md).
# Pinned Node LTS tarball by sha256; no NodeSource repo, no global npm installs.
ARG NODE_MAJOR=22            # current LTS line at authoring; S3 pins exact x.y.z + sha256
ARG NODE_VERSION=22.x.y      # PLACEHOLDER — S3 fills from https://nodejs.org/dist/index.json
ARG NODE_SHA256=<sha256>     # PLACEHOLDER — from SHASUMS256.txt of that release
RUN set -eu; \
    curl -fsSLo /tmp-node.tar.xz "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz"; \
    echo "${NODE_SHA256}  /tmp-node.tar.xz" | sha256sum -c -; \
    mkdir -p /opt/node && tar -xJf /tmp-node.tar.xz -C /opt/node --strip-components=1; \
    rm /tmp-node.tar.xz; /opt/node/bin/node --version
ENV PATH="/opt/node/bin:$PATH"
WORKDIR /app/services/mcp/elk
COPY services/mcp/elk/package.json services/mcp/elk/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund \
 && node -e "require('elkjs'); console.log('elkjs ok')"
WORKDIR /app
```
Notes: `package-lock.json` must carry `integrity` equal to §1 value; `npm ci` fails loud on mismatch. `--ignore-scripts` blocks lifecycle-script execution (elkjs declares none that run at install). Location `services/mcp/elk/` is a proposal; architecture may place it under `packages/eda-bridge/`. The monolith `Dockerfile` must mirror this ("keep in sync" rule, `Dockerfile.ee:50,68`).

S3 must MEASURE (no numbers invented here): (a) image size delta `docker image inspect` before/after; (b) `docker build` wall time delta on a cold cache and a warm cache; (c) cold start: time from `node` spawn to first `elk.layout()` resolution for a trivial 3-node graph, and for a representative CP3 leaf; (d) peak RSS of the Node process during a CP3 layout; (e) `npm ci` network bytes (for air-gapped build viability). Record all five in the S3 receipt with raw command output.

## 5. Notice text (for a new `THIRD_PARTY_NOTICES.md`)

```
## elkjs
Package:   elkjs
Version:   0.12.0
Source:    https://github.com/kieler/elkjs (tag 0.12.0, commit ff5771d7165445c42c408bb8a090c8035272218c)
Tarball:   https://registry.npmjs.org/elkjs/-/elkjs-0.12.0.tgz
Integrity: sha512-YZcKynxVxYoKIOEpywEPwCFdg+BTbxQRNf3pbwdDCvc8O3kQD8bmIwSxKU1eOTVc4Xo+VG9Te+575mlfvOrhEQ==
Copyright: Copyright (c) 2017 Kiel University and others. (as found in lib/elk-api.js)
License:   EPL-2.0 OR GPL-3.0-or-later — bodesign uses this component under the
           Eclipse Public License 2.0 (https://www.eclipse.org/legal/epl-2.0/).
           Full text: node_modules/elkjs/LICENSE.md (unmodified).
Note:      Contains the Eclipse Layout Kernel (ELK) 0.12.0, Eclipse Foundation,
           transpiled to JavaScript via GWT. Used unmodified as a layout engine.
```

## 6. Alternatives rejected (per Astra ruling, `design.md:259-260`)

- Graphviz `splines=ortho`: no port constraints; `https://graphviz.org/docs/attrs/splines/` states ortho ignores ports and dot edge labels.
- netlistsvg emitter: couples layout to its own SVG/skin model; we want only the layout engine, KiCad remains the emitter.
- JVM ELK (Maven artifacts): introduces a second long-lived runtime path beside freerouting's one-shot jar; elkjs reuses no JVM at runtime at all.
- Fallback to the hand-written router: frozen as legacy by DD-13; a fallback would hide engine failure instead of raising it (`design.md:276-277`).

## 7. Open items for the clearance verdict

1. Approve EPL-2.0 option selection and the §5 notice wording; decide file name/location of `THIRD_PARTY_NOTICES.md`.
2. Pin exact Node LTS `x.y.z` + sha256 (placeholders in §4); confirm tarball-install over apt `nodejs` (Ubuntu 24.04 apt ships Node 18, EOL).
3. Decide lockfile location (`services/mcp/elk/` vs `packages/eda-bridge/`) and whether the monolith `Dockerfile` gets the same layer now or at S3 end.
4. Confirm `web-worker` stays out (in-process layout only) — avoids a second clearance.
5. Decide whether a per-artifact license scan of GWT build inputs (§3) is required or the manifest-level statement suffices for an unmodified binary dependency.
6. Confirm process model: one Node child per `emit` call (stateless, timeout-killed) vs. warm pool — affects the cold-start measurement S3 must report.
7. Registry/GitHub were reachable at authoring; S3 must re-verify `dist.integrity` at install time and fail if it differs.
