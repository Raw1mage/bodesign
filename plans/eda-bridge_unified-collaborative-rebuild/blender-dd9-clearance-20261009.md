# Blender DD-9 clearance inventory — 2026-10-09

**DRAFT — inventory only; not clearance approval, renderer selection, installation authorization or task 7.7 benchmark.**

Authority: dispatch `Blender-DD-9-clearance-7.6`, following user acceptance recorded by the officer. Only this Markdown deliverable is requested. No binaries/source archives downloaded, no install, package changes, image build, render, Dockerfile edit, staging or commit performed. Tasks 7.6/7.7 remain unchecked pending officer ruling.

Evidence labels: **SOURCED** means a retrieved official page or explicitly identified repository working-tree record supports the bounded statement, not that binaries or runtime behavior were tested. **UNVERIFIED** identifies missing documentary evidence; **UNMEASURED** identifies absent measurements. **PROPOSED** is a recommendation, never an observed value or approved budget. Counts below count numbered evidence items once, not sentences, citations or questions. Proposals are counted separately.

Repository inputs: [tasks.md lines 81–89](tasks.md), [design.md DD-18 and renderer decision, lines 339–349 and 377–391](design.md), [freeze §4.11–4.16](c04-entry-freeze-20261007.md). These are current working-tree records, not a fresh deployment inspection. The officer's §4.15 supersedes §4.14's historical host blocker.

## A. Release pin and integrity

**A1 — SOURCED / proposed selection.** Propose **Blender 4.5.14 LTS, Linux x64**, not a floating `latest`. It is the highest 4.5 patch shown in the retrieved official directory and LTS page (September 15, 2026), and the branch is supported until July 2027. This gives a documented maintained branch and a patch-specific artifact for comparison; it is not a claim that 4.5 is the newest LTS across every branch. Sources: https://www.blender.org/download/lts/4-5/ and https://download.blender.org/release/Blender4.5/ .

**A2 — SOURCED.** Official binary URL (recorded, **not fetched**): https://download.blender.org/release/Blender4.5/blender-4.5.14-linux-x64.tar.xz . Listed on the official LTS page via its download redirect and the official directory above.

**A3 — SOURCED.** Published checksum line, verbatim from https://download.blender.org/release/Blender4.5/blender-4.5.14.sha256 :

```text
9ba871ff2ecd36526b77432745980b7e6664ecd0c7ca11c48849073dcfe06da3  blender-4.5.14-linux-x64.tar.xz
```

This is publication evidence only, not a locally computed Blender checksum or proof of artifact authentication independent of the website.

**A4 — SOURCED.** Matching source archive URL is linked by the official LTS page: https://download.blender.org/source/blender-4.5.14.tar.xz . URL recorded only; source archive not fetched.

**A5 — UNVERIFIED.** Matching source-archive published digest/signature has not been obtained. The binary checksum manifest does not list the source archive. Source-integrity clearance remains open.

**A6 — UNMEASURED.** Binary bytes versus A3, archive contents versus source, signature verification and provenance beyond official publication were not checked. A future separately authorized acquisition must verify exact bytes before use; this inventory does not complete the binary/source integrity part of 7.6.

## B. Licence obligations and output rights

This is an engineering inventory, not legal advice. The Foundation FAQ itself recommends legal advice when needed: https://www.blender.org/support/faq/ . Each interpretation below is labelled as such; only blockquotes are verbatim quotations.

**B1 — SOURCED. Source versus binary licence distinction.** Blender-developed source defaults to GPL-2.0-or-later, but the Foundation explicitly specifies GPL-3.0-or-later for combined Blender binary distribution. Source: https://www.blender.org/about/license/ :

> The source code we develop at blender.org is default being licensed as GNU GPL Version 2 or later.

> All the components that together make Blender are compatible under the newer GNU GPL Version 3 or later. That is also the license to use for any distribution of Blender binaries.

Interpretation: labelling a shipped official binary only GPL-2.0-or-later would omit the Foundation's binary-distribution qualification.

**B2 — SOURCED. Subprocess boundary, not blanket exemption.** The FAQ's external-program wording, under “Can I sell add-ons for Blender?”, is:

> You have full freedom to license your software product however you wish *if and only if:*  
> – It operates **outside** of Blender.  
> – Uses **no** Blender source code or API calls (including Python API).  
> – Produces data for Blender to operate on.  
> – Executes Blender to read and operate on the data.

Source: https://www.blender.org/support/faq/#using-blender-9 . Interpretation: an outside bodesign controller invoking `blender -b` on data can fit this description if all listed conditions hold. A `bpy` script passed to that process is a separate licence concern (B4); subprocess invocation alone is insufficient clearance. No current bodesign implementation was audited against these conditions.

**B3 — SOURCED. Output ownership.** FAQ, “Can I license .blend files myself?”:

> **Yes.** The output of Blender, in the form of .blend files, is considered program output, and the sole copyright of the user. The .blend file format only stores data definitions.

> In case you embed the .blend file with Python scripts, and the scripts provide bindings to other libraries or facilities, the next topic applies.

Source: https://www.blender.org/support/faq/#using-blender-7 . The licence page also says:

> What you create with Blender is your sole property. All your artwork – images or movie files – including the .blend files and other data files Blender can write, is free for you to use as you like.

Source: https://www.blender.org/about/license/#artwork . Interpretation: normal generated scene/image output is not automatically GPL solely because Blender produced it. This does not license someone else's assets, copied icons or embedded scripts.

**B4 — SOURCED. Python scripts inside Blender.** FAQ, “What about add-ons or my Python scripts?”:

> If you share or publish Python scripts **they have to be made available licensed as GNU GPL** as well, if they use Blender Python API calls.

Source: https://www.blender.org/support/faq/#using-blender-8 . Interpretation: distributed scene-building/render scripts using `bpy` require an explicit GPL plan, source availability and notices; being batch automation rather than a UI addon does not remove API use. FAQ internal-use wording:

> **Yes.** The GNU GPL does allow your organization to use a modified version of Blender internally without offering the source-code as long as you do not distribute it outside your company or organization.

Source: https://www.blender.org/support/faq/#using-blender-6 . Internal-only use and distribution to customers must be distinguished by the officer; do not infer the entire bodesign codebase's licence from these quotes.

**B5 — SOURCED, bounded requirement inventory. Addons.** DD-18 requires product/CMF scenes, assets, cameras/lights/material recipes and token bindings, but identifies no concrete addon requirement: [design.md DD-18](design.md). **No optional addon proposed or assumed needed.** This is not a claim that the official archive contains no bundled scripts. Any later requested addon needs its own exact-version licence/source inventory before installation. The Foundation confirms addons are not required for proper functioning: https://www.blender.org/about/license/#privacy .

**B6 — SOURCED, illustrative dependency licences, not a complete SBOM.** The Foundation lists Cycles Apache-2.0, Python Python License, Bullet Zlib, Libmv MIT and OSL BSD: https://www.blender.org/about/license/#license . Preserve applicable upstream texts and notices if these components are shipped. Exact versions, inclusion and obligations of every library in 4.5.14 are not established by this general page (B12).

**B7 — SOURCED. Artwork exceptions and branding.** FAQ identifies splash-screen/icons as GPL material and Blender's logo as a trademark: https://www.blender.org/support/faq/#license-5 . Repackaging must not change Blender's copyright notices or claim authorship: https://www.blender.org/support/faq/#license-6 . Proposal: no splash/icon/logo reuse in C01 renders or bodesign branding.

**B8 — SOURCED. Notices/source-access requirements for a future EE/ME image.** Regardless of worker choice, an image conveying Blender must preserve copyright/licence/no-warranty notices and include GPL text; modifications need prominent dated change notices. Corresponding Source must be accessible under an applicable GPL distribution route. Sources: GPLv3 §§4–6, https://download.blender.org/release/GPL3-license.txt , plus B1/B4/B6/B7 URLs. The FAQ says, verbatim:

> However, for sharing official releases it’s sufficient to provide information that forwards to the sources at blender.org.

Source: https://www.blender.org/support/faq/ . Interpretation: for network image distribution, document exact matching source and equivalent access under §6(d), not a generic homepage; distributor remains responsible for continued availability. Proposed ship checklist: upstream GPL/copyright/no-warranty files; per-component licence/NOTICE texts; exact binary/version and matching source directions; GPL source/licence for shipped `bpy` scripts; asset attribution/licence files once B9–B12 close; dated modifications where applicable. No claim that merely copying GPL text satisfies all obligations.

**B9 — UNVERIFIED. Fonts shipped in 4.5.14.** Exact font names, versions, licence texts and embedding/redistribution conditions not inventoried. No OFL/Apache/BSD designation assumed. Attempted pinned release licence inventory: https://projects.blender.org/blender/blender/raw/tag/v4.5.14/release/license/license.md returned HTTP 403. Do not reuse bundled fonts in C01 until individually cleared.

**B10 — UNVERIFIED. Bundled general assets.** Exact asset-library items and their per-item licences not inventoried; B3 does not clear them. Same attempted pinned licence URL as B9. No universal CC0/GPL assumption.

**B11 — UNVERIFIED. Bundled HDRIs.** Exact HDRI names, providers, licences and attribution obligations not obtained from a release-specific inventory. Same attempted URL as B9. Proposed initial comparison uses explicit analytic lights, not unverified HDRIs; this does not excuse notice obligations for any assets still shipped in a future image.

**B12 — UNVERIFIED. Matcaps and full binary dependency/asset closure.** Exact matcap licences and complete third-party library licence inventory remain open. Same attempted URL as B9; B6 is illustrative only. Preserve upstream archive notices in any future approved build, and reconcile exact included files before declaring redistribution cleared.

## C. Dependency/image cost — desk estimate only

**C1 — SOURCED / published figure.** Directory line verbatim from https://download.blender.org/release/Blender4.5/ :

```text
blender-4.5.14-linux-x64.tar.xz                    15-Sep-2026 09:16           378045212
```

Published compressed archive size: **378045212 bytes**. The LTS page labels Linux **361 MB** (publisher's label retained, not reconciled into a local measurement): https://www.blender.org/download/lts/4-5/ . Neither figure is an extracted/image size.

**C2 — SOURCED, generic published requirement only.** The current requirements page lists Linux glibc **2.28 or newer**, **4** CPU cores with SSE4.2, **8 GB** minimum RAM, **32 GB** recommended RAM, and OpenGL **4.3** / Vulkan **1.3** graphics requirements: https://www.blender.org/download/requirements/ . These are published application requirements, not measured headless scene memory or an exact 4.5.14 runtime dependency closure. The page spans current/older versions, so it must not be treated as a pinned tarball `ldd` result.

**C3 — SOURCED. Cycles versus EEVEE.** Cycles manual:

> GPU rendering makes it possible to use your graphics card for rendering, instead of the CPU.

Source: https://docs.blender.org/manual/en/4.5/render/cycles/gpu_rendering.html . Interpretation: CPU rendering is supported; a GPU is not inherently required for the Cycles render computation. Actual headless startup on the selected container is still unmeasured. EEVEE manual:

> Being a rasterization engine, EEVEE only uses the power of the GPU to render. There is no plan to support CPU (software) rendering as it would be very inefficient.

> Headless rendering is not supported on headless Windows systems.

Source: https://docs.blender.org/manual/en/4.5/render/eevee/limitations/limitations.html . Interpretation: do not promise an EEVEE CPU backend. Linux EGL/device/driver feasibility is a separate runtime check, not proven by the Windows limitation or existing pyrender EGL success.

**C4 — SOURCED, repository baseline only.** [Dockerfile.me lines 9–23](../../Dockerfile.me) declares Ubuntu 24.04 and `libgl1`, `libglx-mesa0`, `libglu1-mesa`, `libx11-6`, `libxext6`, `libxrender1`, `libxcb1`, `libsm6`, `libexpat1` for the current CAD stack. [Freeze §4.11–4.16](c04-entry-freeze-20261007.md) records pyrender 0.1.45/EGL in ME and a served core/me/ee stack. These are not evidence that Blender's required libraries are all present or that the deployed image exactly matches this working-tree Dockerfile.

**C5 — UNVERIFIED. Exact CPU/EGL runtime libraries.** No pin-specific Blender binary dependency closure was obtained. Debian package reference https://packages.debian.org/trixie/blender returned a JavaScript challenge, not dependency metadata. Therefore no Debian dependency list or install recipe is asserted. EGL/OpenGL dispatch/driver libraries, C/C++ runtime and optional GPU runtime additions must be reconciled from supported documentation and exact artifact dependencies on an authorized host. The current ME GL/X list is not a substitute.

**C6 — UNMEASURED. Extracted archive size.** No published extracted-size figure obtained; archive not downloaded/extracted. No compression multiplier fabricated.

**C7 — UNMEASURED. Current ME image size and build/start overhead.** No image inspection/build/start measurement performed. Existing image size, cached/shared layers and notices/source-storage overhead unknown.

**C8 — UNMEASURED. Expected image delta.** Positive additional payload is expected if Blender is added without removing existing functionality, but no numeric delta is supported. Desk accounting: incremental extracted Blender payload + missing runtime libs + notices/scripts/assets/source-access packaging − shared/deduplicated content. Compressed registry delta and uncompressed filesystem delta differ. C1 cannot be used as either image delta. No change to ME, EE or a new image is authorized by this estimate.

**C9 — UNMEASURED. Runtime feasibility/performance.** Cycles CPU time/RSS, EEVEE EGL/device startup, render outputs, reproducibility, GPU memory and software-driver compatibility were not tested. No GPU purchase/availability assumption and no host eligibility conclusion.

## D. Renderer ownership and predeclared 7.7 budgets

**D1 — SOURCED, local constraint.** [design.md renderer decision](design.md) keeps heavy rendering outside core and leaves ME geometry ownership unchanged (AC25). [Tasks 7.6–7.8](tasks.md) require clearance then authorized-host comparison before Blender selection; no automatic replacement or rejection of pyrender.

**D2 — SOURCED, local baseline.** [Freeze §4.16](c04-entry-freeze-20261007.md) accepts pyrender C01 r3, served scene gates S-01–05, four visible LEDs and silver/KEY distinction, with three r4 residuals. Benchmark must freeze the officer-selected revision rather than assume the older r2 remains the final comparison scene. Review/gate claims here are those of that record, not rerun checks.

**D3 — PROPOSED ownership.** Prefer **ME worker** to own any cleared Blender subprocess and GPL scene adapter initially, because it already owns the geometry and current appearance-render baseline. Keep core a lightweight routing/contract boundary. Do not install in EE merely because the plan asks to measure EE-image feasibility: report that candidate separately if the officer retains that target. A **new render worker** is an alternative only if separate GPU scheduling, failure/resource isolation or licence packaging justifies the operational cost; it needs an explicit architecture ruling. Neither option transfers OpenSCAD/build123d geometry production to Blender. This is not a deployment decision.

**D4 — PROPOSED retained pyrender responsibilities.** Keep the declared pyrender baseline available, with its geometry-bound scene manifest, gate receipts and inspection/assembly/section view path. Do not delete, replace or silently switch it on Blender failure. Any adopted Blender path adds explicitly selected C01 product/CMF rendering; ME geometry, upstream CAD/units/interfaces, AC25 ownership and non-approval markers stay unchanged. Retain/adopt/blocked requires an officer decision; retaining baseline artifacts is not authorization for fallback behavior.

**D5 — PROPOSED operational budgets, all actual values UNMEASURED.** Suggested starting limits for officer ruling (policy numbers, not published hardware figures):

| Metric | Proposed acceptance bound | Measurement definition for separately authorized 7.7 |
| --- | --- | --- |
| Incremental image size | ≤ **1.5 GiB** uncompressed and ≤ **600 MiB** compressed | Same pinned ME base versus candidate; report EE candidate separately if requested; include retained notices and layers, distinguish shared layers |
| Render time per view | ≤ **60 s** warm and ≤ **120 s** cold | Officer-approved matched **1600×1200** views; report every view, median and worst of **3** runs; wall time includes scene load through saved image |
| Memory | ≤ **4 GiB** peak per render job | Container peak including Blender/adapter children; declare CPU/GPU/backend; GPU VRAM separate, not hidden in RSS |
| Cold start overhead | ≤ **15 s** | Process start to scene-ready; also report total cold render time |
| Build overhead | ≤ **10 min** incremental | Same host and cache condition recorded; dependency fetch time disclosed separately |

Rationale: provisional bounded payload/resource/cost limits for small static C01 views, not forecasts of Blender performance. If a candidate cannot meet them, return measured failure or a ruling request; never silently relax budgets, change engines or lower scene quality.

**D6 — PROPOSED scene freeze and blind parity.** Before 7.7, lock upstream geometry digests, scale/units, camera matrices/view set, lights, materials/token bindings, transparency/world, resolution, colour-management transform/exposure/display, seeds, engine/device/samples/denoiser and output encoding. CPU Cycles and GPU EEVEE are distinct declared candidates, not interchangeable runs. Camera/backend-specific tolerance must be approved before rendering; no bit-identical GPU promise. Proposed silhouette tolerance ≤ **1 pixel** after identical camera projection at frozen resolution; colour comparison is readability/intent, not physical colour accuracy. Independent blind reviewers first describe each view without renderer labels or the frozen brief, then compare against it. Proposed **3 reviewers per matched pair**, **3/3** must identify product orientation, visible controls, ports and declared LED population; no critical geometry/interface contradiction, clipping or occlusion regression; every declared CMF token must be visually supported. Candidate must resolve at least one declared baseline appearance residual without introducing another critical failure to justify adoption. Gates (asset/geometry/token/view coverage) remain separate from comprehension. No render implies electrical, physical CMF, ergonomic or manufacturing approval. These thresholds and reviewer counts are suggestions for ruling, not authorization to run review.

## E. Numbered questions for officer/user ruling

1. Accept 4.5.14 LTS as the proposed pin, or require another maintained LTS branch? Who supplies/verifies the published matching source digest/signature before integrity clearance?
2. Is use internal-only, or will EE/ME/render images and `bpy` scripts be conveyed to customers/third parties? Approve the binary GPL-3.0-or-later and adapter GPL/source-access plan, with legal review if needed.
3. Who will close the release-specific font, asset, HDRI, matcap and full dependency licence inventory? May the first comparison exclude all optional assets/addons while still preserving notices for anything shipped?
4. Choose ME ownership or explicitly authorize a new render-worker design. Does the EE-image feasibility wording remain a separate benchmark requirement, despite existing ME render ownership?
5. Approve or revise D5/D6 budgets and evaluation protocol **before** authorizing 7.7. Which exact pyrender scene revision/view set (r3 or later accepted revision) is the baseline?
6. Which host, CPU allocation and GPU/EGL/driver backend are authorized for 7.7? Is CPU Cycles the first candidate, with EEVEE conditional on an explicitly available GPU?
7. Is the inventory accepted with B9–B12/C5 open, or must documentary clearance be completed before any binary acquisition? This report recommends keeping installation/benchmark blocked until the required clearance items and budgets are ruled on.

## Evidence counts and execution disclosure

| Section | SOURCED items | UNVERIFIED / UNMEASURED items | PROPOSED-only items |
| --- | ---: | ---: | ---: |
| A (A1–A6), after Phase 1 | 5 | 1 | 0 (A6 binary-only; source/signatures remain unverified) |
| B (B1–B12), after Phase 1 | 11 | 1 | 0 (B12 full closure still unverified; explicit per-item gaps below) |
| C (C1–C9), after Phase 2 | 7 | 2 | 0 (C9 host CPU product rendering measured only; container/GPU scope unmeasured) |
| D (D1–D6), after Phase 2 | 2 | 0 | 4 (D5/D6 partially measured below; blind acceptance and deployment undecided) |
| E | 0 | 0 | 7 questions, not empirical claims |

Measured: retrieved official text, exact published binary checksum/size, and current working-tree constraints. Not measured: Blender artifact/source contents or integrity, exact runtime library/asset closure, deployed image bytes/size, installation/build/start/render/memory/parity or legal compliance of an implementation. No tests are specified for this Markdown inventory; no benchmark/tests claimed.

Tool friction (not repaired): runbook lookup returned `RUNNER_NO_JSON`; pinned release licence URL returned HTTP 403; Debian metadata returned a JavaScript challenge; three manual `_sources/*.rst.txt` requests returned HTTP 404. The rendered Cycles/EEVEE manuals did succeed; their relevant exact sentences were extracted from stored webfetch output. Mechanical extraction delegation failed before session creation with `TaskDispatchPreflightError: task_dispatch_preflight:account_missing: account <none> is not present for provider codex; no session was created`; no worker result is relied on.

Boundary exception requiring officer awareness: the mandatory operational event tool recorded task start and closeout at `/home/pkcs12/projects/bodesign/.specbase/events.sqlite` despite the dispatch's no-`.specbase` boundary. No direct `.specbase` editing was performed; both events are disclosed, not concealed or undone. Apart from those event-ledger side effects, the only intended repository content change is this file. Architecture unchanged: this document proposes ownership but implements no boundary/data-flow change. No new cross-repository lesson is claimed or KB mutation undertaken in this bounded inventory.

## Phase 1 — acquisition, inventory, smoke (2026-10-09)

This append supersedes the initial inventory's historical not-downloaded/not-rendered statements only within this authorized phase. Authority: `Blender-7.7-phase1-acquire-verify-inventory`, freeze §4.17 (S20 `b157e30`): internal-only use; pin 4.5.14; no optional assets/addons; ME ownership; CPU Cycles first; D5/D6 budgets adopted, not measured by this smoke. Baseline inventory S18 `f86bd80`. No container, package installation, product-scene render, image edit, staging or commit. Cache root `/home/pkcs12/.cache/blender-dd9/`; temporary Blender work redirected with `TMPDIR` to its `runtime/` child.

### P1-A. Acquisition, source listing and extracted size

Downloaded official archive and checksum with `curl --fail --location --output`, both successful. Binary verified BEFORE extraction using the manifest's exact Linux line:

```text
grep '  blender-4.5.14-linux-x64.tar.xz$' blender-4.5.14.sha256 | sha256sum -c -
blender-4.5.14-linux-x64.tar.xz: OK
sha256sum /home/pkcs12/.cache/blender-dd9/blender-4.5.14-linux-x64.tar.xz
9ba871ff2ecd36526b77432745980b7e6664ecd0c7ca11c48849073dcfe06da3  /home/pkcs12/.cache/blender-dd9/blender-4.5.14-linux-x64.tar.xz
```

Exit 0. **A6 binary integrity MEASURED/SOURCED** against A3; independent signature authentication and binary/source correspondence not verified. Extracted with `tar -xf ... -C /home/pkcs12/.cache/blender-dd9/`, exit 0. **C6 MEASURED**, raw disk-usage output:

```text
1.2G	/home/pkcs12/.cache/blender-dd9/blender-4.5.14-linux-x64
```

`du -sh` is rounded allocated disk usage, not logical bytes or image delta. Source listing checked ONCE via https://download.blender.org/source/ . Relevant raw entries:

```text
blender-4.5.14.tar.xz                              15-Sep-2026 09:11            85105652
blender-4.5.14.tar.xz.md5sum                       15-Sep-2026 09:11                  56
```

No matching source `.sha256` entry appeared in that listing. **A5 source SHA256 remains UNVERIFIED**; source archive and MD5 not acquired, no invented source digest.

### P1-B. Artifact licence/asset inventory

All paths below are relative to the verified extracted root unless an absolute path is given. Native glob found the licence directory at **`license/`**, not `release/license/`. Immediate listing: `license.md`, `licenses.json`, `others/`, `spdx/`; recursive file listing and exact byte size/hash follow in P1-B metadata. Root `license.md` contains the dependency/copyright tables and full licence texts (22 second-level headings including Fonts, Apache-2.0, BSL-1.0, BSD-2/3-Clause, bzip2, Freetype, GPL-2/3, LGPL-2.1, libpng, libtiff, MIT variants, MPL-2.0, Public Domain, Python, SGI, TOST, NCSA, WC Width, Zlib). **B12 documentation inventory sourced, not a completed independent file-to-component SBOM or legal clearance.** Bundled code and private cache files were not modified.

**B9 fonts: 25 files enumerated.** No licence file sits directly in `4.5/datafiles/fonts/`; adjacent-file evidence is **UNVERIFIED for EACH listed item**. Root `license/license.md:702–712` nevertheless gives sourced family mappings: Inter, Noto Fonts and Last Resort → OFL-1.1; DejaVu Sans Mono → Arev + Bitstream Vera (DejaVu changes public domain). Exact font versions and individual metadata were not inspected. Enumeration (all `.woff2`):

```text
DejaVuSansMono.woff2
Inter.woff2
lastresort.woff2
Noto Sans CJK Regular.woff2
NotoEmoji-VariableFont_wght.woff2
NotoSansArabic-VariableFont_wdth,wght.woff2
NotoSansArmenian-VariableFont_wdth,wght.woff2
NotoSansBengali-VariableFont_wdth,wght.woff2
NotoSansDevanagari-Regular.woff2
NotoSansEthiopic-Regular.woff2
NotoSansGeorgian-VariableFont_wdth,wght.woff2
NotoSansGujarati-Regular.woff2
NotoSansGurmukhi-VariableFont_wdth,wght.woff2
NotoSansHebrew-Regular.woff2
NotoSansJavanese-Regular.woff2
NotoSansKannada-VariableFont_wdth,wght.woff2
NotoSansKhmer-VariableFont_wdth,wght.woff2
NotoSansMalayalam-VariableFont_wdth,wght.woff2
NotoSansMath-Regular.woff2
NotoSansMyanmar-Regular.woff2
NotoSansSymbols-VariableFont_wght.woff2
NotoSansSymbols2-Regular.woff2
NotoSansTamil-VariableFont_wdth,wght.woff2
NotoSansTelugu-VariableFont_wdth,wght.woff2
NotoSansThai-VariableFont_wdth,wght.woff2
```

Root font licence header, verbatim (`license/spdx/OFL-1.1.txt:1`):

> SIL Open Font License 1.1

Preserve supplied notices; OFL text requires copyright/licence inclusion for bundled redistribution, reserved-name rules for modifications, no font-alone sale; it does not require documents to use OFL (`license.md:826–852`). Internal-only ruling does not authorize removing notices.

**B10 assets: SOURCED.** `4.5/datafiles/assets/LICENSE:1–3` header, verbatim:

> Creative Commons Legal Code
>
> CC0 1.0 Universal

Observed `.blend` files under `assets/`: `geometry_nodes/{smooth_by_angle,procedural_hair_node_assets}.blend`; `brushes/essentials_brushes-{curve_sculpt,gp_draw,gp_sculpt,gp_vertex,gp_weight,mesh_sculpt,mesh_texture,mesh_vertex,mesh_weight}.blend`. Also `blender_assets.cats.txt`. This is a directory-level licence, not a claim about every other resource in Blender. No optional asset used in the default cube smoke.

**B11 HDRIs: SOURCED.** `4.5/datafiles/studiolights/world/`: `city.exr`, `courtyard.exr`, `forest.exr`, `interior.exr`, `night.exr`, `studio.exr`, `sunrise.exr`, `sunset.exr`, `license.txt`. Adjacent licence header, verbatim:

> All HDRIs are licensed as CC0.
>
> These were created by Greg Zaal (Poly Haven https://polyhaven.com).

The supplied text says “Probably” for Night/Studio originals; exact original identity remains uncertain, not rewritten as verified. No HDRI used.

**B12 matcaps: SOURCED at class level.** `4.5/datafiles/studiolights/matcap/`: `basic_1`, `basic_2`, `basic_dark`, `basic_side`, `ceramic_dark`, `ceramic_lightbulb`, `check_normal+y`, `check_rim_dark`, `check_rim_light`, `clay_brown`, `clay_muddy`, `clay_studio`, `jade`, `metal_anisotropic`, `metal_carpaint`, `metal_lead`, `metal_shiny`, `pearl`, `reflection_check_horizontal`, `reflection_check_vertical`, `resin`, `skin`, `toon` (all `.exr`), plus `license.txt`. Header, verbatim:

> These matcap images are licensed as CC0 or public domain.

Per-file CC0-versus-public-domain attribution is **UNVERIFIED for each of these 23 files**; the supplied class-level statement does not distinguish them. No matcap used. `studiolights/studio/{basic,outdoor,paint,rim,studio}.sl` have no adjacent licence: **UNVERIFIED for each of those five files**.

**Bundled addons top-level inventory** (`4.5/scripts/addons_core/`): `__pycache__`, `bl_pkg`, `copy_global_transform.py`, `cycles`, `hydra_storm`, `io_anim_bvh`, `io_curve_svg`, `io_mesh_uv_layout`, `io_scene_fbx`, `io_scene_gltf2`, `node_wrangler`, `pose_library`, `rigify`, `ui_translate`, `viewport_vr_preview`. No separate `addons/` directory was found by the requested pattern. `__pycache__` is not a licence-cleared addon. Top-level source headers at line 3, verbatim: Cycles, Hydra Storm and glTF use `# SPDX-License-Identifier: Apache-2.0`; the other eleven source entrypoints use `# SPDX-License-Identifier: GPL-2.0-or-later`. These headers do not prove every nested dependency has that licence. Cycles is the authorized built-in engine, not an optional addon installation; no optional addon enabled for this task.

### P1-B metadata. Complete root licence file listing

Native recursive glob found these 26 regular files under `license/`; `stat -c '%n %s'` and `sha256sum` supplied the following exact byte sizes and digests. Directories excluded from hashing; the first immediate-directory hash attempt reported `Is a directory` for `others`/`spdx`, then the regular-file inventory below succeeded. Directory sizes are not file sizes.

| Path | Bytes | SHA256 |
| --- | ---: | --- |
| license/license.md | 215394 | bbbae8a955a571bbd30e91c579f6f1633ec921f6317cfac9074338dfba33a7b8 |
| license/licenses.json | 3353 | 3d31ab709273e56dbb700620bdc761977011925c255c0e69dcc7ea1a4fb1f840 |
| license/others/Arev-Fonts.txt | 2252 | 1c68eacc08c5c60fddb587b528913f3859c4f0e96a5b1b01048bd51de2fefd21 |
| license/others/ICS.txt | 178 | 8e8f56b5e62935fe7fb284bdde151d11f84dac9d126c030b4fd00eadc83ccd64 |
| license/others/LLVM-exception.txt | 872 | f282823a60a9cd3e8329398f243bf3bc3cc5e80daccace5a30ee1ad7b7dbdc17 |
| license/others/TOST-1.0.txt | 10184 | c0ff03452fe9c05bff88eea4a40e6a01d80b2cc543fc92ea7220716418341211 |
| license/spdx/Apache-2.0.txt | 11357 | c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4 |
| license/spdx/BSD-2-Clause.txt | 1291 | c0f0a10042900ea04a6c30998342081baf7de45330cb9ca348e59a4d8c58488d |
| license/spdx/BSD-3-Clause.txt | 1485 | 7c0bceba5d7abaa63ead2e9af971468b5b26f4cb753aeb2a5e706625555885a6 |
| license/spdx/BSL-1.0.txt | 1338 | c9bff75738922193e67fa726fa225535870d2aa1059f91452c411736284ad566 |
| license/spdx/Bitstream-Vera.txt | 2371 | 3f5b96a6506a1c4381091688dfc35cf4c1ecae9a2b2443d3b14ce92f0bc90171 |
| license/spdx/FTL.txt | 6678 | 8c2467540e01b1ee3ae14751213ac5988c48ceabe51143aeb2e13316e0ed958a |
| license/spdx/GPL-2.0-or-later.txt | 17996 | a3ade2b6d18c7c30d89faec2ba913283fb2d56370137ea90cfa20891414492f8 |
| license/spdx/GPL-3.0-or-later.txt | 35147 | 8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903 |
| license/spdx/LGPL-2.1-or-later.txt | 26530 | dc626520dcd53a22f727af3ee42c770e56c97a64fe3adb063799d8ab032fe551 |
| license/spdx/MIT-Khronos-old.txt | 1257 | 19b92e3f10b6003614dbf70ee5a9b3ead460e84913bf9f8c89bbba49d05f2376 |
| license/spdx/MIT.txt | 1056 | 123c983ef5ff60697594e3010cb2022341450f7839d9f77d0a3943a9a5d9992c |
| license/spdx/MPL-2.0.txt | 16725 | 1f256ecad192880510e84ad60474eab7589218784b9a50bc7ceee34c2b91f1d5 |
| license/spdx/NCSA.txt | 1479 | 5dbb7a7dc7513d63c7e1b5a77ade261032e52e90d4774c773babcfb00fb560e1 |
| license/spdx/OFL-1.1.txt | 4215 | c1a781a6a032bf00b1bbffc388fd6936bf28a0ded472c263bcff88b181dea456 |
| license/spdx/Python-2.0.txt | 2396 | f59c9e092485634cac6e1ce41ba8387fb93267e3a601093501a1e684486304e6 |
| license/spdx/SGI-B-2.0.txt | 1414 | c45c70943f3223662f8647079962efb8bca616f8941812cbfe55ea669a488202 |
| license/spdx/Zlib.txt | 957 | e97d76c9516ecd9bd360267ea341c57bf93d5d162f72eb2bf29c49eae4a6a6dc |
| license/spdx/bzip2-1.0.6.txt | 1649 | beae1a4eb6ee2d815c3aa2a1ce2ec7939420574e724c2fa9570da13ca0dcca17 |
| license/spdx/libpng-2.0.txt | 1280 | d2005336d6716935d77644bf188d474dec4d3a3e0f85b556a30087d00a9e46ba |
| license/spdx/libtiff.txt | 1054 | a46d5aeb164d5f705a30ee79c356820805fdca01de0ab4c5dbe54b3c1e4d3143 |

Additional licence-directory/adjacent regular files observed:

| Path | Bytes | SHA256 |
| --- | ---: | --- |
| 4.5/scripts/addons_core/cycles/license/Apache2-license.txt | 11358 | cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30 |
| 4.5/scripts/addons_core/cycles/license/BSD-3-Clause-license.txt | 1465 | 78176499683c1e601241d901486dfdebcd0d511826e67905dd54881f5dc1d7e3 |
| 4.5/scripts/addons_core/cycles/license/MIT-license.txt | 1036 | 7a91b4754c06385f87b319313871b064d4d9e0dc1570ca94928b09fe74ed03ee |
| 4.5/scripts/addons_core/cycles/license/SPDX-license-identifiers.txt | 379 | b5f81f33f3424add5ed61be93c19e9a4caecc5ca12e50b9b0be4ceacc2832d92 |
| 4.5/scripts/addons_core/cycles/license/Zlib-license.txt | 833 | 52a1da7db7828498bb11719974c41f875e310ea241c97c8e27af7cda21887c19 |
| 4.5/scripts/addons_core/cycles/license/readme.txt | 316 | 5c2f5f1974b56d433fab60f9bf29de4d43b0b4c9eda40cfdcd0e3918993db49f |
| 4.5/datafiles/assets/LICENSE | 7048 | a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499 |
| 4.5/datafiles/studiolights/world/license.txt | 707 | adb4229abf8701b512dc75bab8e08610ecefb08e2b07e9ff5cdaf1e558195ee5 |
| 4.5/datafiles/studiolights/matcap/license.txt | 123 | b611907587d18b7d2a2f7b81e6c0fe5048a5592f2086ec8678f25d682e4cc877 |

### P1-C. Host dependency measurement

**C5 measured for this executable's `ldd`-visible linked closure only.** `ldd /home/pkcs12/.cache/blender-dd9/blender-4.5.14-linux-x64/blender` succeeded and resolved all linked dependencies; subsequent requested `ldd ... | grep 'not found'` emitted **no stdout**, grep exit **1** (no matches), **missing count 0**. This conclusion is based on the full successful `ldd` output, not the pipeline exit alone. Distinct host-system sonames (sorted unique; paths resolved under `/lib/x86_64-linux-gnu/`):

```text
libGL.so.1
libGLX.so.0
libGLdispatch.so.0
libICE.so.6
libSM.so.6
libX11.so.6
libXau.so.6
libXdmcp.so.6
libXext.so.6
libXfixes.so.3
libXi.so.6
libXrender.so.1
libbsd.so.0
libc.so.6
libdl.so.2
libgcc_s.so.1
libm.so.6
libmd.so.0
libpthread.so.0
librt.so.1
libstdc++.so.6
libutil.so.1
libuuid.so.1
libxcb.so.1
libxkbcommon.so.0
```

Also `/lib64/ld-linux-x86-64.so.2` and the virtual `linux-vdso.so.1`. Other `ldd` entries resolve into the extracted archive's `lib/` (including TBB, Vulkan, OpenSubdiv, OpenEXR/Imath, MaterialX, Embree, oneAPI/SYCL, OpenColorIO, OpenImageIO, OIDN, OSL, USD and OpenVDB). No host library absent; no packages installed. Dynamically loaded plugins, EGL/GPU devices, unused runtime paths, shared-library licence mapping and ME container closure remain **UNVERIFIED/UNMEASURED**. Host CPU smoke success is not proof of EEVEE/EGL feasibility.

### P1-D. Host-only headless smoke

Working directory: `/home/pkcs12/.cache/blender-dd9/blender-4.5.14-linux-x64`. Both commands used `/usr/bin/time -v`, `TMPDIR=/home/pkcs12/.cache/blender-dd9/runtime` and exited 0. No scene file loaded, saved preferences or product input. Single runs, not a warm/cold series or D5 acceptance measurement.

Version smoke raw stdout followed by raw timing stderr:

```text
4.5.14 LTS
Blender 4.5.14 LTS (hash 62c1db4208e8 built 2026-09-15 01:31:19)

Blender quit
	Command being timed: "./blender -b --python-expr import bpy; print(bpy.app.version_string)"
	User time (seconds): 0.34
	System time (seconds): 0.15
	Percent of CPU this job got: 100%
	Elapsed (wall clock) time (h:mm:ss or m:ss): 0:00.49
	Average shared text size (kbytes): 0
	Average unshared data size (kbytes): 0
	Average stack size (kbytes): 0
	Average total size (kbytes): 0
	Maximum resident set size (kbytes): 233164
	Average resident set size (kbytes): 0
	Major (requiring I/O) page faults: 0
	Minor (reclaiming a frame) page faults: 25591
	Voluntary context switches: 106
	Involuntary context switches: 3
	Swaps: 0
	File system inputs: 8
	File system outputs: 0
	Socket messages sent: 0
	Socket messages received: 0
	Signals delivered: 0
	Page size (bytes): 4096
	Exit status: 0
```

CPU render command (explicit 320×240/100%, 8 samples, CPU; `--factory-startup` resets the scene):

```sh
TMPDIR=/home/pkcs12/.cache/blender-dd9/runtime /usr/bin/time -v ./blender --factory-startup -b -E CYCLES --python-expr "import bpy; s=bpy.context.scene; s.render.resolution_x=320; s.render.resolution_y=240; s.render.resolution_percentage=100; s.cycles.samples=8; s.cycles.device='CPU'; s.render.image_settings.file_format='PNG'; print('SMOKE_SETTINGS', s.render.engine, s.cycles.device, s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage, s.cycles.samples); print('SMOKE_OBJECTS', sorted(o.name for o in s.objects))" -o /home/pkcs12/.cache/blender-dd9/smoke/ -f 1
```

Render raw stdout (unabridged):

```text
Blender 4.5.14 LTS (hash 62c1db4208e8 built 2026-09-15 01:31:19)
Fra:1 Mem:8.45M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Synchronizing object | Cube
Fra:1 Mem:8.45M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Synchronizing object | Light
Fra:1 Mem:8.45M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Initializing
Fra:1 Mem:8.27M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Waiting for render to start
Fra:1 Mem:8.27M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Scene
Fra:1 Mem:8.27M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Shaders
Fra:1 Mem:8.27M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Loading render kernels (may take a few minutes the first time)
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Procedurals
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Background
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Camera
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Meshes Flags
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Objects
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Objects | Copying Transformations to device
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Particle Systems
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Particle Systems | Copying Particles to device
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Meshes
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Objects | Applying Static Transformations
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Mesh | Computing attributes
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Mesh | Copying Attributes to device
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Scene BVH | Building
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Scene BVH | Building BVH
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Scene BVH | Building BVH 0%
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Scene BVH | Copying BVH to device
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Mesh | Computing normals
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Mesh | Copying Mesh to device
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Objects Flags
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Primitive Offsets
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Images
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Camera Volume
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Updating Lookup Tables
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.08M, Peak:0.08M | Scene, ViewLayer | Updating Lights
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.09M, Peak:0.09M | Scene, ViewLayer | Updating Lights | Computing tree
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.09M, Peak:0.09M | Scene, ViewLayer | Updating Integrator
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.09M, Peak:0.09M | Scene, ViewLayer | Updating Film
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.00M, Peak:0.09M | Scene, ViewLayer | Updating Lookup Tables
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.09M, Peak:0.09M | Scene, ViewLayer | Updating Baking
Fra:1 Mem:8.35M (Peak 8.45M) | Time:00:00.00 | Mem:0.09M, Peak:0.09M | Scene, ViewLayer | Updating Device | Writing constant memory
Fra:1 Mem:8.36M (Peak 8.45M) | Time:00:00.00 | Mem:0.09M, Peak:0.09M | Scene, ViewLayer | Loading denoising kernels (may take a few minutes the first time)
Fra:1 Mem:8.36M (Peak 8.45M) | Time:00:00.00 | Mem:0.09M, Peak:0.09M | Scene, ViewLayer | Sample 0/8
Fra:1 Mem:14.24M (Peak 14.24M) | Time:00:00.01 | Remaining:00:00.06 | Mem:5.66M, Peak:5.66M | Scene, ViewLayer | Sample 1/8
Fra:1 Mem:16.59M (Peak 20.10M) | Time:00:00.34 | Mem:5.66M, Peak:5.66M | Scene, ViewLayer | Sample 8/8
Fra:1 Mem:16.59M (Peak 20.10M) | Time:00:00.34 | Mem:5.66M, Peak:5.66M | Scene, ViewLayer | Finished
Saved: '/home/pkcs12/.cache/blender-dd9/smoke/0001.png'
Time: 00:00.44 (Saving: 00:00.09)

SMOKE_SETTINGS CYCLES CPU 320 240 100 8
SMOKE_OBJECTS ['Camera', 'Cube', 'Light']

Blender quit
```

Render raw timing stderr:

```text
	Command being timed: "./blender --factory-startup -b -E CYCLES --python-expr import bpy; s=bpy.context.scene; s.render.resolution_x=320; s.render.resolution_y=240; s.render.resolution_percentage=100; s.cycles.samples=8; s.cycles.device='CPU'; s.render.image_settings.file_format='PNG'; print('SMOKE_SETTINGS', s.render.engine, s.cycles.device, s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage, s.cycles.samples); print('SMOKE_OBJECTS', sorted(o.name for o in s.objects)) -o /home/pkcs12/.cache/blender-dd9/smoke/ -f 1"
	User time (seconds): 5.33
	System time (seconds): 1.45
	Percent of CPU this job got: 725%
	Elapsed (wall clock) time (h:mm:ss or m:ss): 0:00.93
	Average shared text size (kbytes): 0
	Average unshared data size (kbytes): 0
	Average stack size (kbytes): 0
	Average total size (kbytes): 0
	Maximum resident set size (kbytes): 374016
	Average resident set size (kbytes): 0
	Major (requiring I/O) page faults: 44
	Minor (reclaiming a frame) page faults: 58194
	Voluntary context switches: 884
	Involuntary context switches: 11141
	Swaps: 0
	File system inputs: 72
	File system outputs: 128
	Socket messages sent: 0
	Socket messages received: 0
	Signals delivered: 0
	Page size (bytes): 4096
	Exit status: 0
```

Output file checksum (not visual QA or product acceptance):

```text
3af6e56164d620698fb32b45f9177b4f029415454b386fe536a73844b88741ba  /home/pkcs12/.cache/blender-dd9/smoke/0001.png
```

Measured: binary checksum, allocated extracted size, complete root licence-file metadata, requested resource/addon listing, host linked libraries and single headless/version/default-cube CPU smoke. Not measured: source digest/signature, every nested code/resource licence mapping, GPU/EGL, container/image cost, product scene quality/time/RSS, reproducibility or blind parity. Phase 1 delivered; **Phase 2 is not executed**. Architecture Sync: Verified (No doc changes); no boundary implementation. KB Distill: Verified (no cross-repo lesson this round; artifact-specific inventory and measurements only).

## Phase 2 — frozen-scene CPU Cycles benchmark (2026-10-09)

### Known scene deviations

1. **SW2/SW3 STEP caps omitted in every view: UNMEASURED.** Blender has no native STEP tessellator in this adapter. The authentic recipe is `build123d.import_step`, `solids()[2:]`, STL export `tolerance=0.005`, `angular_tolerance=0.1`, then rotate pi about X (`.src/c01p_scene.py:127–140`). No build123d installation or primitive-cap substitution was attempted. SW1 remains present. Missing-button findings are attributable to this authorized omission, not an undisclosed parity failure.
2. **Upper-lid normals are not identical.** Blender EDGE_SPLIT at 35 degrees replaces baseline per-corner averaging of compatible face normals (`c01p_scene.py:64–88,100–101`). Geometry projection is retained; shading findings must be attributed to this disclosed transformation rather than treated as an unexplained regression.
3. **Lighting/material shaders are cross-engine conversions, not radiometrically equivalent.** Unit-gain SUN irradiance and Principled BSDF are explicit conventions below. No tuning or second quality pass occurred.

Authority: Phase 2 dispatch plus Option A reply and subsequent NumPy/timing ruling. Specimen checksum verification was completed before rendering; manifest root `63f58c9f…` and both consumed STL digests matched. Inputs remain read-only. Freeze authority is manifest + `.src/c01p_scene.py` + `.src/c01p_render.py` + STEP, not manifest alone. Only this report changed in the repo; scripts, freeze, logs, renders and parity artifacts are cache-only. No optional assets/addons, EEVEE, container, package install, git staging or commit.

### P2-A. Freeze and transformations

Cache root: `/home/pkcs12/.cache/blender-dd9/phase2/`. Exact artifacts: `scene_freeze-v1.json`, GPL-2.0-or-later `render.py`, GPL-2.0-or-later `parity.py`, `parity-results.json`. Freeze copies all manifest fields including camera params, materials/RGB, token bindings, surfaces, seed 42, output 1600×1200 and consumed digests; adds resolved camera/light matrices and exact conversion recipe with source line citations. Cycles CPU, 32 samples (fixed for all runs; modest static-view budget candidate), denoiser off, Standard/sRGB, exposure 0, gamma 1, opaque RGBA PNG, units mm (`scale_length=0.001`, coordinates retained as mm). Five camera views rendered; `product-sheet` excluded as composite (`c01p_render.py:324–359`), **UNMEASURED**.

Transformations:
- STLs rotated pi about X (`c01p_scene.py:97–109`); upper normals differ as disclosed above.
- Screws: 32-sided cylinders radius 1.5, height 0.8, centers `(1.5,-58.5,8)`, `(26.5,-60.2,8)` (`:119–125`). SW1 box dimensions `(1.2,3,1.8)`, center `(-1.8,-86.45,0.5)` (`:152–156`). LEDs: four 32-sided cylinders radius 0.9, height 0.6, center z=8.4 and exact declared XY (`:158–165`). USB six boxes: dimensions and translations copied verbatim into freeze `geometry_recipe.usb_boxes` (`:167–182`). Surface names bind exactly to manifest tokens.
- Camera frame: forward=normalize(target-eye), right=normalize(cross(forward,up)), corrected up=cross(right,forward), local back=-forward (`:40–49,210–216`). Blender VERTICAL sensor height 32 mm; lens=`32/(2*tan(radians(yfov)/2))`; aspect 1600/1200, no orthographic substitution. Clip .05–10000 scene units is explicit adapter choice.
- Lights key/fill/rim → SUN, angle 0; `energy[W/m²] = pyrender intensity × 1`. Unit gain is declared, not asserted physical equivalence. RGB copied directly. Light matrices use actual baseline eye/target-relative offsets (`:224–237`), not absolute manifest positions.
- Ambient → world Background with manifest linear RGBA `[0.10,0.10,0.12,1]`, strength 1. Camera-ray world background separately uses inverse-sRGB `[0.92,0.93,0.95,1]` at strength 1; Light Path/Is Camera Ray mixes these shaders; film_transparent off (`:201–203`). Inverse transfer is `c/12.92` for c≤.04045, otherwise `((c+.055)/1.055)^2.4`. Baseline and Cycles quantization differed by 1 byte in two background channels; mask method uses each image's own background.
- Principled base color takes manifest RGB directly; metallic/roughness exact. All opaque with no transmission, matching baseline `alphaMode="OPAQUE"` despite the LENS description (`:52–61`). Principled implementation is not the same BRDF as pyrender.

**C01 scene-manifest defect; product files untouched.** Verbatim manifest key values → actual code behaviour:

| Manifest declaration | Renderer behaviour (`c01p_scene.py:224–237`) |
| --- | --- |
| `lights.key.position: [-120.0,-200.0,220.0]`, `target: [14.0,-46.5,-8.6]` | `look_at(eye + key_offset, tgt, up)`; offset `[-60.0,-80.0,100.0]`, top `[-80.0,-60.0,60.0]` |
| `lights.fill.position: [160.0,120.0,150.0]`, same declared target | `look_at(eye + fill_offset, tgt, up)`; offset `[100.0,80.0,50.0]`, top `[80.0,60.0,40.0]` |
| `lights.rim.position: [14.0,80.0,200.0]`, same declared target | `look_at(tgt + rim_offset, tgt, up)`; offset `[0.0,120.0,150.0]`, top `[0.0,150.0,150.0]` |

Manifest declares positions/targets that the accepted renderer ignores. S-04 did not catch this mismatch, per officer ruling; no gate rerun or defect repair claimed. Officer owns freeze §4.18/r4 intake.

### P2-B. D5 measurements

Command: `TMPDIR=/home/pkcs12/.cache/blender-dd9/runtime /usr/bin/time -v /home/pkcs12/.cache/blender-dd9/blender-4.5.14-linux-x64/blender -b --python /home/pkcs12/.cache/blender-dd9/phase2/render.py`. Raw stdout/stderr preserved unabridged at `logs/render.log`; exit 0. One process, shared scene, three view cycles. Per-view numbers include render through PNG save, **not separate process startup/geometry load**. This timing limitation was explicitly accepted by officer; 42.05 s whole-process wall is a conservative upper bound including all setup and all 15 renders, not a per-view measured startup value.

| View | Raw runs s (1 / 2 / 3) | Median s | Worst s | RSS kB upper bound | Warm ≤60 s |
| --- | --- | ---: | ---: | ---: | --- |
| product-iso-front | 2.036039732 / 2.226000228 / 2.064857713 | 2.064858 | 2.226000 | 485248 | PASS |
| product-iso-rear | 2.054043633 / 2.219411091 / 2.092506113 | 2.092506 | 2.219411 | 485248 | PASS |
| product-top | 2.262806930 / 2.304408316 / 2.223309179 | 2.262807 | 2.304408 | 485248 | PASS |
| product-usb-end | 3.689301878 / 3.720388012 / 3.710653146 | 3.710653 | 3.720388 | 485248 | PASS |
| product-battery-end | 3.520483187 / 3.494428769 / 3.505251508 | 3.505252 | 3.520483 | 485248 | PASS |

| D5 bound | Measurement | Result / scope |
| --- | --- | --- |
| Warm render ≤60 s; cold ≤120 s | Worst warm 3.720388 s; all-15 process 42.05 s upper bound | PASS host-only bound as ruled; no 3-isolated-cold-run statistic |
| Peak RSS ≤4 GiB | Whole job 485248 kB (0.462769 GiB); individual peaks not separately sampled | PASS host-process bound; not container peak |
| Cold start ≤15 s | Isolated iso-front process wall 2.83 s including load/render/save/exit | Upper bound is below 15 s; exact start-to-ready **UNMEASURED**, not separated from render |
| Cold render ≤120 s | Isolated iso-front render/save 2.124463964 s, process 2.83 s | PASS for the one authorized isolated view |
| Image delta ≤1.5 GiB uncompressed / ≤600 MiB compressed | N/A host-only | UNMEASURED |
| Incremental build ≤10 min | No build authorized | UNMEASURED |

Additional isolated invocation (one pass): same command plus `-- --isolated`, loads scene and renders only iso-front. Raw log `logs/isolated.log`, exit 0. Output iso-front PNG retained from this invocation; other four PNGs from run 3. Representative raw timing lines (complete logs preserved):

```text
SETUP_SECONDS 0.17365396399691235
Elapsed (wall clock) time (h:mm:ss or m:ss): 0:42.05
Maximum resident set size (kbytes): 485248
Exit status: 0
BENCH_RESULT {"run": 1, "view": "product-iso-front", "wall_s": 2.1244639640062815}
Elapsed (wall clock) time (h:mm:ss or m:ss): 0:02.83
Maximum resident set size (kbytes): 443844
Exit status: 0
```

### P2-C. Mechanical parity preparation; no image judgement

Baseline left, Blender right, no rescaling. Every body crop is `[0,69,1600,1128]` (Pillow exclusive right/bottom), removing header through inclusive y=68 (`c01p_render.py:56–58`) and footer beginning H−72=1128 (`:74–80`). Pair image 3200×1083 includes an extra 24 px DRAFT label band outside the 1:1 body images. Lid crop `[720,470,1020,630]` uses baseline recipe (`:597–599`); two 300×160 crops at 1:1 plus DRAFT band.

Mask method: RGB background derived separately from pixel `(0,69)` in each image; object mask is any-channel absolute difference **>2/255** from that background within the body crop. Baseline background `[235,237,242]`; candidate `[235,238,243]`. Neither file supplies a usable object alpha mask (opaque output); these are **background-derived masks, not geometric depth silhouettes**. Interior highlights/background-like pixels and missing caps can create boundaries, so offset is not proof of an outer-outline error.

Initial parity attempt stopped with `ModuleNotFoundError: No module named 'scipy'` (exit 1). Officer explicitly authorized replacement, no installation. NumPy-only algorithm: pad mask with false; 4-neighbour eroded mask = mask AND up AND down AND left AND right via explicit shifts; boundary = mask XOR eroded mask. For every boundary pixel, compute exact squared Euclidean distances to every opposite-boundary pixel, take minimum, then maximum across both directed sets and square root. This is symmetric exact nearest-boundary distance, O(nb×mb), not an approximate distance transform. XOR count is number of differing body-mask pixels. Successful parity script exit 0.

| View | Crop box | XOR pixels | Max boundary offset px |
| --- | --- | ---: | ---: |
| product-iso-front | [0,69,1600,1128] | 1106 | 207.183493551 |
| product-iso-rear | [0,69,1600,1128] | 1130 | 1.414213562 |
| product-top | [0,69,1600,1128] | 10 | 150.000000000 |
| product-usb-end | [0,69,1600,1128] | 634 | 1.000000000 |
| product-battery-end | [0,69,1600,1128] | 710 | 1.000000000 |

No visual pass/fail assigned. The above background-mask numbers are measured, but are not a substitute for officer blind review or an outer-silhouette ground truth. Missing caps/shading deviations are disclosed, not counted as blind parity failures.

Artifacts below all exist under `/home/pkcs12/.cache/blender-dd9/phase2/out/`; full paths equal that prefix plus the listed filename. Full SHA256 values and raw numbers are in `parity-results.json`.

| Pair/crop filename | SHA16 |
| --- | --- |
| product-iso-front-pair.png | 4b9af443d0393770 |
| product-iso-rear-pair.png | 45ee820dd7b240560 |
| product-top-pair.png | bd8b08e265fe7d43 |
| product-usb-end-pair.png | 3c711ac35a337305 |
| product-battery-end-pair.png | 4ffc84e81a018494 |
| lid-top-crop-pair.png | 9a46656e48a453c2 |

Per-view raw `<view>.png` and `<view>-xor.png` exist in the same directory with digests recorded in the receipt. No image loaded for self-judgement; no blind review performed by this handler.

### P2-D. Evidence and unmeasured scope

Evidence-count convention: A/B unchanged from Phase 1; C9 now measured within host CPU scope (C7/C8 remain open), not blanket runtime clearance. D1/D2 remain sourced constraints; D3–D6 are policy/ruling items with this partial empirical append. Phase 2 primary measured groups: five three-run timings, one whole-process RSS/wall, one isolated RSS/wall, five XOR/offset receipts, six pair/crop artifacts. Unmeasured items: image deltas, incremental build, container dependency/performance/RSS, GPU/EGL/EEVEE, exact startup-only duration, three independent cold starts, SW2/SW3 authentic cap surfaces in all five views, product-sheet composite, physical colour/radiometric equivalence, geometric depth-mask parity, per-view RSS peaks, repeat-output byte reproducibility, independent blind review and adoption decision. Source integrity/full nested licence closure remain Phase 1 residuals.

Architecture Sync: Verified (No doc changes); no deployed boundary change. KB Distill: Verified (no cross-repo lesson this round; bounded specimen conversions and measurement caveats only). This append supersedes historical Phase 1 “Phase 2 not executed” statements only within the measured host-only scope above. Product tree remains read-only; report remains uncommitted.
