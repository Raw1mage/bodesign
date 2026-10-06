# Third-party notices — packages/eda-bridge

Initial entry authored by the S3 engine spike (DD-15, DD-9 clearance
`plans/eda-bridge_unified-collaborative-rebuild/dd9-clearance-elkjs.md`).
Task 3.6 consolidates this file across the repo later; until then it covers
only the dependencies vendored or lock-pinned under `packages/eda-bridge/`.

## elkjs

```
Package:   elkjs
Version:   0.12.0
Source:    https://github.com/kieler/elkjs (tag 0.12.0, commit ff5771d7165445c42c408bb8a090c8035272218c)
Tarball:   https://registry.npmjs.org/elkjs/-/elkjs-0.12.0.tgz
Integrity: sha512-YZcKynxVxYoKIOEpywEPwCFdg+BTbxQRNf3pbwdDCvc8O3kQD8bmIwSxKU1eOTVc4Xo+VG9Te+575mlfvOrhEQ==
Copyright: Copyright (c) 2017 Kiel University and others. (as found in lib/elk-api.js)
License:   EPL-2.0 OR GPL-3.0-or-later — bodesign uses this component under the
           Eclipse Public License 2.0 (https://www.eclipse.org/legal/epl-2.0/).
           The GPL-3.0 secondary-license option is NOT exercised.
           Full text: packages/eda-bridge/elk/LICENSE.elkjs.md (unmodified copy of
           node_modules/elkjs/LICENSE.md, sha256
           637e81f4a1b6b4079535c499fca05e238cf7605c1ff5b76d60d7da7ce96700c9).
Lockfile:  packages/eda-bridge/elk/package-lock.json (lockfileVersion 3; the only
           installed package is elkjs@0.12.0 — `npm ls --all` recorded in the S3 receipt).
Note:      Contains the Eclipse Layout Kernel (ELK) 0.12.0, Eclipse Foundation,
           transpiled to JavaScript via GWT. Used unmodified, in-process, from
           packages/eda-bridge/elk/runner.cjs (one bounded Node child per emit).
           The optional `web-worker` dependency is not installed.
```

Compliance obligations (EPL-2.0, per clearance condition 1 — these are
release-owner obligations, not reduced to "no action"):

- §3.3: retain all copyright, attribution and disclaimer notices in any copy we
  distribute. The `lib/*.js` headers and `LICENSE.md` ship unmodified inside the
  EE image under `/app/packages/eda-bridge/elk/node_modules/elkjs/`.
- §3.1/§3.2: corresponding source for elkjs itself must be made available to
  recipients of a distribution (public URLs above are a pointer, not proof of
  availability — the release owner must confirm at distribution time).
- Build-time inputs compiled into the shipped bundle (GWT, Guava, Xtext, EMF —
  see clearance §3) were inventoried at manifest level only; a per-artifact
  notice scan of `lib/elk-worker*.js` is still owed before distribution
  (clearance condition 2).

## Node.js runtime (Dockerfile.ee only)

```
Package:   Node.js
Version:   22.23.3 (maintenance LTS "Jod"), linux-x64 official tarball
Source:    https://nodejs.org/dist/v22.23.3/node-v22.23.3-linux-x64.tar.xz
SHA256:    df450af89261115ef9f9e3830c3eeb2cc9213b63c720b1af623cb5dcbe2e02de
           (from SHASUMS256.txt; detached signature verified 2026-10-06 with the
           nodejs release key 5BE8A3F6C8A5C01D106C0AD820B1A390B168D356)
License:   MIT (Node.js) plus the bundled third-party licenses enumerated in the
           tarball's LICENSE file; npm (bundled) is Artistic-2.0. Both files are
           retained in the image under /opt/node/LICENSE and
           /opt/node/lib/node_modules/npm/LICENSE.
```
