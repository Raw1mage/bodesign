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
| A (A1–A6) | 4 | 2 | 0 (selection proposal is inside sourced A1) |
| B (B1–B12) | 8 | 4 | 0 (bounded interpretations/checklists embedded) |
| C (C1–C9) | 4 | 5 | 0 |
| D (D1–D6) | 2 | 0 | 4 (all benchmark results remain unmeasured) |
| E | 0 | 0 | 7 questions, not empirical claims |

Measured: retrieved official text, exact published binary checksum/size, and current working-tree constraints. Not measured: Blender artifact/source contents or integrity, exact runtime library/asset closure, deployed image bytes/size, installation/build/start/render/memory/parity or legal compliance of an implementation. No tests are specified for this Markdown inventory; no benchmark/tests claimed.

Tool friction (not repaired): runbook lookup returned `RUNNER_NO_JSON`; pinned release licence URL returned HTTP 403; Debian metadata returned a JavaScript challenge; three manual `_sources/*.rst.txt` requests returned HTTP 404. The rendered Cycles/EEVEE manuals did succeed; their relevant exact sentences were extracted from stored webfetch output. Mechanical extraction delegation failed before session creation with `TaskDispatchPreflightError: task_dispatch_preflight:account_missing: account <none> is not present for provider codex; no session was created`; no worker result is relied on.

Boundary exception requiring officer awareness: the mandatory operational event tool recorded task start and closeout at `/home/pkcs12/projects/bodesign/.specbase/events.sqlite` despite the dispatch's no-`.specbase` boundary. No direct `.specbase` editing was performed; both events are disclosed, not concealed or undone. Apart from those event-ledger side effects, the only intended repository content change is this file. Architecture unchanged: this document proposes ownership but implements no boundary/data-flow change. No new cross-repository lesson is claimed or KB mutation undertaken in this bounded inventory.
