# Amendment: Presentation Authority Inversion (officer draft, 2026-10-06)

Status: duty-officer ruling draft. Astra integrates it into design.md / spec.md /
tasks.md / data-schema.json (DD numbering continues at DD-13; existing IDs unchanged).
User ruling (same day): fix at the architecture, not by local patching of the
router. Dispatch policy (user, later same day): flexible scheduling by task
nature — Astra 6 (codex) for architecture/review; Fable 5.1 (claude-cli) for
judgement-heavy implementation such as S1; Sonnet 5.5 (claude-cli) or agy-relay
for well-specified, high-volume implementation. This supersedes the earlier
"workers only via agy-relay" rule.
Dispatch policy revision (user, 2026-10-06, after S3 spike observation): Fable 5.1
is too expensive and too slow as a WORKER. From the next dispatch onward, workers
use Sonnet 5.5 (claude-cli) or agy-relay only; Fable 5.1 is reserved for the duty
officer. The running S3 spike (ses_ef06f84fe) finishes its current turn on Fable
and is not re-dispatched on it. Astra 6 remains the architecture/review brain.

## 1. Finding that forces the amendment

Three checkpoints x three leaves x independent reviewers = nine NO verdicts on the
same electrical-illusion classes (see `p2-slice-a-pause-20261006.md`). Native netlist
diff against spec = 0 fused / 0 missing / 0 misrouted on every leaf. The worker's own
geometric assertion was green on every round.

Conclusion: `kicad_emit.py`'s hand-rolled router cannot guarantee what a reviewer
sees, and its instrument is not isomorphic to reviewer judgement. KiCad decides
connectivity by endpoint coincidence; a human decides it by where a line passes and
where a junction dot sits. Three rounds targeted the wrong population.

Ruling: no further remediation rounds on the hand-rolled router. It is frozen as
legacy N=1 compatibility under DD-7 and receives no new acceptance targets.

## 2. Proposed decisions

### DD-13 Presentation authority order

Schematic presentation (placement, routing, label style) has three authority
sources, in priority order:

1. **Human draft.** A native `.kicad_sch` set produced by the user's own tool is
   authoritative for everything it places. The agent never moves, reroutes or
   restyles what the human placed (extends DD-6 and the existing user-pinning
   guarantee). The agent's work on a human draft is the repetitive remainder:
   topology reconcile against the declared circuit (fused / missing / misrouted = 0,
   otherwise an explicit ChangeProposal), annotation, value/footprint completion,
   missing-label completion, sheet partition honouring existing placement, BOM,
   ERC, companions, evidence binding.
2. **Machine draft.** When no human draft exists, placement and inter-motif routing
   are produced by an adopted layered-orthogonal layout engine (ELK layered family as
   used by netlistsvg; alternatives are Astra's call) in which symbol bodies are hard
   obstacles *structurally*, not by post-hoc avoidance. Motif-internal wiring
   (`motifs.py`) stays local. The machine draft is a draft *for the human*: it must be
   an editable native `.kicad_sch` so the user's tool can take over, i.e. it re-enters
   as a tier-1 input. This closes the human-in-the-loop without building a UI.
3. **Hand-rolled router.** Legacy only.

### DD-14 Reviewer-isomorphic readability instrument

Metrics are computed in render space (geometry of the native `kicad-cli sch export
svg` output), and the measured population is the defect classes reviewers cited:

Input is a paired set: native `.kicad_sch` + native `kicad-cli` export + render, with
matching provenance (same bytes, recorded hashes). SVG alone cannot recover net
identity or semantic roles and is not an accepted input on its own.

- (a) junction semantics: at every point where wires/pins meet, compute the number
  of *normalized incident branches* (segment interiors count, collinear splits do
  not, native pin/junction semantics apply). Junction dot present iff branches >= 3
  and the meet is electrically one net; dot absent otherwise. Raw wire-end count is
  not the measure (segmentation-dependent).
- (b) two sub-classes, reported separately: (b1) actual electrical junction error
  (distinct-net meet with a dot, same-net T without one); (b2) perceptual ambiguity
  (distinct-net wires crossing *without* a dot, explicitly cited by reviewers).
  b1 is an electrical defect; b2 is a presentation defect. Neither is folded into
  the other.
- (c) pin attached by label only, for intra-sheet nets with <= K nodes = 0;
- (d) series-element visual continuity: for each two-terminal series element, test
  whether the drawn-connectivity graph (wires + junctions + pin tips; labels
  excluded) plus near-contact evidence (a foreign wire passing within the pin-tip
  tolerance band, a dot on a pin tip that continues past the element) presents the
  element as bypassed. This is an *illusion* finding; the instrument never claims the
  element is electrically bypassed when the native netlist already matches.
- (e) collinear distinct-net runs along a pin-tip row = 0;
- (f) page use and text-vs-graphics clearance, reported as measurements. The 50 %
  page-use figure in the first draft is uncalibrated and is not a PASS gate; reuse
  existing DD-14/DD-16 child-plan tests where they already measure render space.

**Calibration gate.** Two exemplar populations are required: (i) rejecting
exemplars — every archived leaf render carrying an independent NO (CP1-CP3; at
minimum usbc/power_rail/battery at CP3) must yield a non-empty offender set naming
the reviewer's defect class; (ii) accepting exemplars — at least one render with an
independent YES or a hand-verified clean fixture must yield an empty offender set
for classes a-e. An always-NO detector satisfies (i) and fails (ii); both are
required. A YES on any NO artifact, or a NO on an accepting exemplar, rejects the
instrument; thresholds are not tuned to pass. Fresh-eyes review remains the final
gate; the instrument is the engine's *target*, not a replacement for the human gate.
(Class list corrected per Astra interim reply, topic
master-presentation-authority-amendment, 2026-10-06.)

### DD-15 Engine adoption follows DD-9

License / revision / notice clearance before any copying. ELK is EPL-2.0 (flag for
clearance: use as a dependency, do not vendor); netlistsvg is MIT. Compute placement
(core vs ee worker) per dependency (node / JVM). No new service, no competing MCP.

## 3. Short-term slices authorized to start now

| Slice | Owner | Scope | Acceptance |
|---|---|---|---|
| S1 Instrument + calibration | Fable 5.1 | New module + tests; no router edits | Calibration gate above, receipt with per-artifact verdict table |
| S2 Human-draft ingestion vertical | Fable 5.1 (after S1 or in parallel) | Formal entrypoint accepts a native `.kicad_sch` set as presentation baseline; emits reconcile report + completed outputs | Human geometry byte-retained (existing pinning tests), topology diff = 0 or explicit proposal; fixture source pending user |
| S3 Engine spike | Fable 5.1, after Astra's engine ruling | One leaf (usbc) through the engine -> `.kicad_sch` -> native render -> S1 instrument -> one fresh-eyes | Checkpoint only; not five-page completion |
| S4 Milestone commit | Officer | Multi-sheet modules + tests + slice-A tree | Pending user authorization |

## 3.1 User rulings on partition (2026-10-06, after viewing 01-06 v1 and 06.io-v2)

Recorded verbatim-in-substance; Astra integrates into the PresentationPlan DD
(ruling topic granularity-and-global-view-ruling, same day).

- R-A (granularity): io-v2 is "合理正常多了" but "粒度拆得有點細，缺乏全局觀".
- R-B (IC-centric pages, binding): a reviewer wants to see an IC with ALL its pins
  and how each pin connects to the other components. Splitting an IC's pins across
  function-named pages and drawing partial net fragments removes the global view and
  forces the reader to map label text -> pin number -> physical pin before they can
  solder. Therefore: a multi-pin IC is drawn once, whole, with its peripherals
  attached by wire on the same page; pages are organized around ICs / connectors,
  not around function nets. Label-only attachment of a pin is the exception that
  must be justified (off-page destination), never the default partition mechanism.
- Consequence for this board: the current six-leaf partition (by `design.py` sheet
  field) violates R-B for U1 (charger) and U2 (MCU). Current partition stays the
  declared legacy baseline until a PresentationPlan candidate is approved.

Astra integration verdict (topic ic-centric-partition-user-ruling, same day):
- R-B is an INVARIANT, not a heuristic; no numeric pin threshold. Applicability is
  declared by component role (IC / connector / named central device) with explicit
  per-ref coverage. Each applicable physical instance has ONE authoritative home page
  carrying its complete logical pin inventory (multi-unit, hidden/stacked, power, NC)
  reconciled against the native/declared physical inventory. Exceptions are proposed
  per ref/pin/net with reason + impact and need explicit user/design-authority
  approval; no agent or heuristic may waive. Label-only pin attachment requires a real
  declared remote destination AND no concealed local relationship; an off-page net
  that also has local peripherals keeps the visible local wire.
- Validation is PresentationPlan-level, two layers: (1) plan conformance (pin
  inventory, home-page/unit coverage, declared local-support membership, cross-page
  destinations, exception records); (2) native-artifact realization (pin presence,
  realized page membership, visible local connection vs label-only). S1 class c is
  supporting evidence within its measured scope only; no S1 class added, no K change.
- Intent-review protocol gains explicit questions: identify the main IC/connector and
  locate ALL pin numbers incl. supply/hidden/NC; explain each pin's local connection or
  declared off-page destination; can this be done without reconstructing the chip
  from labelled fragments; where must the reader leave the page. Labels are schematic
  references, never assembly instructions.
- Next allocation (after r9 overview + user viewing): bounded DESIGN slice —
  PresentationPlan schema (minimum: baseline digests; page id/role/order/primary
  refs; instance identity -> home page + unit/pin coverage; per-ref local-support;
  interface net -> remote endpoint/page; exceptions with justification + approval
  provenance; human locks; intent/review criteria) + four-page baseline-bound
  ChangeProposal + pin/page/support/exception table + human-viewable composition
  proposal. Producer = agent hand drafting (r8 method); native export, identity/
  legality/fidelity and S1 checks still apply. Schema/plan authorship stays with the
  architecture owner; Sonnet materializes after sign-off. Any editable draft is a
  candidate workspace under the ChangeProposal, never authoritative. New DD encodes
  R-B + presentation-authority separation (next unused ID at amendment edit).
- Six-leaf ACCEPTs (Reviews 6–12) remain traceability evidence; they do not
  establish R-B compliance.

User ruling R-C (2026-10-06, after viewing 00.overview-v1 and 06.io-v2): hand-drafted
pages have good logical sense but (1) content is biased left — text hugs the left
frame edge while the right side is blank; (2) font is too small; (3) too much
whitespace. Typography rule for text inside boxes/groups, binding for the hand-draft
producer: pick the box with the most text; find the largest font size at which that
text fits inside its box (fit-to-box); apply that single font size to the text of
every box on the page. Boxes resize to content at that size; the page composition is
re-centred/re-spread so left and right margins are balanced. Electrical content is
untouched; this is presentation only.

User ruling R-D (2026-10-06, after viewing 00.overview-v4 "understood" and 06.io-v4
"not understood"): 06 fails because the reader cannot see which chip pin each LED
branch comes from; group headings and off-page text do not repair that. Required
page form, superseding the "four merged pages" candidate as the leading shape:
- For EVERY module (multi-pin IC / connector / header), draw the module ONCE with its
  COMPLETE pin set as the page's anchor, then draw, pin by pin, what each pin connects
  to (resistor, LED, capacitor, connector, net), wired directly from the pin.
- If the page allows, several modules' pin diagrams may share one page; not required.
- A module with many pins MAY be spread across SEVERAL pages, each page repeating the
  full module symbol and wiring one pin GROUP (e.g. U2 page A: power/SWD/reset; page B:
  GPIO16/17/18/26 user I/O). Every page shows the whole module; only the wired pin
  group differs. Pins not wired on that page carry an off-page reference to the page
  that wires them, never left ambiguous.
  Clarification R-D' (user, same day, two statements read together): "a chip module
  with its pins is already the smallest unit of a schematic — do not pull pins OFF
  the module and draw them separately" AND "you may split one module across pages,
  repeating the whole module on each page and expanding a different pin group per
  page." The unit that must never be broken is the MODULE SYMBOL WITH ITS FULL PIN
  SET; pagination by pin group is allowed as long as each page carries the whole
  module. (Officer note: an interim single-page-only reading was recorded and
  withdrawn the same minute; it never reached a landed deliverable.)
  User example: a 100-pin module split into 10 pages, each page repeating all 100
  pins, each page wiring 10 of them.

User ruling R-E (2026-10-06, cross-module boundaries): "apart from not pulling pins
off a module, draw per industry convention." Officer's stated convention, accepted
by that ruling:
1. Each module has a home page (R-D' pagination allowed). A net that leaves the module
   to another module is terminated by an off-page connector labelled
   `NET → <page>.<ref>.<pin>`; the other page carries the mirror `NET ← …`.
2. A passive between two modules is drawn once, on the driver / protected-device page;
   the other page keeps only the connector.
3. Headers, test points and 2-pin connectors are drawn on the page of the module they
   serve; they get no page of their own.
4. Interfaces with >= 8 lines use a bus (`NAME[0..n]`).
5. Two modules share a page only when they are mutually dedicated, heavily wired and
   no third party touches those nets; three or more modules on one page is not done.
Root sheet = block diagram (00.overview) whose links are, in convention, real buses /
sheet pins; our 00 is diagram-mode until sheet pins are allocated (receipt §R9).

User acceptance (2026-10-07, after viewing candidate-r11 07.u2_power_swd-v3 /
08.u2_user_io-v2, Review 18 ACCEPT-marginal): "U2 is much better. This way, how every
chip module's pins are wired in a product can always be fully expressed in a bounded
number of pages." R-D'/R-E confirmed as the page form. Next: U1 (ETA6003 charger) and
J1 (USB-C) by the same producer method; engine pages 01–05 retire to .history/ once
the module set covers them.

User ruling R-F (2026-10-07, abstraction layer / root page): "The 00 page only needs
to express high-level concepts: a few simple lines defining functional links. Each
line implicitly carries the idea of a multi-port bus; it is not to be expanded into
detail." Officer formalization, accepted:
1. 00 is a FUNCTIONAL BLOCK DIAGRAM. One line between two blocks = one functional
   link, implicitly a bus of whatever nets realise it. Lines are not expanded into
   individual nets, ports or sheet pins on 00. The current diagram-mode 00 (dashed
   arrows, legend "Functional flow — not electrical connectivity") is the correct
   form, not an interim.
2. Power and ground never appear as links on 00; they are global power symbols on the
   module pages.
3. Electrical realisation of a link (which nets, which pins) lives on the module
   pages (R-D'/R-E): pin-level wiring plus `NET → <page>.<ref>.<pin>` text. True
   sheet pins / hierarchical ports on 00 are NOT required; any future use is a
   separate, user-approved proposal.
4. A multi-wire chip-to-chip interface (≥ 3 lines, or with mid-path passives) gets
   its own INTERFACE PAGE drawing only the interface and the relevant pins of both
   ends with back-references to their home pages. On 00 it remains one line. Not
   triggered on btdongle (all cross-module links are single nets).
5. Logic beyond wiring (timing, sequencing, protocol) belongs to design documents,
   not schematic pages.
- R-F clarification (user, 2026-10-07, after Review 21 ACCEPT-marginal on 00.overview-v5:
  J1 orphaned, U2 visually cut off from the power side): item 2 excludes rail/GND
  SYMBOLS. The board's PRIMARY POWER TRANSFER (J1→U1 VBUS, U1→U2 SYS, J2↔U1 BATT) is
  a functional link of this product and IS drawn as a dashed link on 00. Ground is
  never drawn. 00.overview-v6 follows. Outcome: r14 landed (manifest root
  `623fca73…` → `9e20483e…` after Reviews 21/22 were appended to reviews.md; 390
  entries, officer-verified 0 non-OK); Review 22 (blind, image-only, ses_eed00e490) on v6 =
  ACCEPT — all six blocks linked, J1→U1→U2 power spine traceable from drawn links
  alone; residual: "charge control / status" label slightly right of span centre.
  C03 presentation layer is at standard; remaining C03 residual is the 11-page
  "6 K4" label crossed by the CC2 vertical (geometry, next 11 round).
- Peripherals (2-terminal parts) live on the page of the pin they serve; a peripheral
  shared by two modules is drawn once, on its primary module's page, and referenced
  from the other.
- This is a presentation form under R-B; the electrical declaration and the native
  58-net partition stay invariant. Module repetition across pages is a presentation
  view of ONE physical instance (DD/Astra: instance identity preserved via explicit
  mapping; no cloned electrical instances).

User ruling R-G (2026-10-07, deliverable directory layout, two rulings same session):
1. "Do not open subdirectories on your own. Emit trial artifacts in their original
   location." The officer-opened `candidate-r11/` was dissolved; all pages live at
   the deliverable root.
2. "`btdongle_ms/` holds only human-viewable image files. Machine-readable
   deliverables move to `outputs/`." Layout:
   - `~/products/bodesign/btdongle_ms/`: `NN.<name>-vN.{png,pdf}`, `README.md`
     (index), `.history/` (superseded images only).
   - `~/products/bodesign/outputs/btdongle_ms/`: `*.kicad_sch`, `editable/`,
     `pin_inventory_*.md`, `.src/` (generators, netlists, ERC, bbox, review corpus,
     manifest), `.history/` machine files.
   - One manifest at `outputs/btdongle_ms/.src/hashes.sha256` binding both trees.
   Naming rule NN-vN (R-C ruling, Round 572) applies to both trees.
3. Environment finding (same day): `~/products` is not version-controlled and is
   watched by gdrive-bisync; the daemon re-created deleted files twice. Eight sealed
   top-level images vanished before 01:46 and were restored by the officer from
   byte-identical scratch originals (sha 8/8). Tracked as a harness BR; no sync
   configuration touched by agents.

User ruling R-H (2026-10-07, scope of this rebuild): "In this rebuild plan, all
C00–C04 deliverables must be brought to standard. C01 must produce a product
render (Blender raised by user); C02 must produce a printable STL; C03 the schematic
set and related data; C04 a Gerber copper-layer render." Confirmed as the original
design intent (architecture.md §C01/C02/C03/C04 entries). Officer formalization:
1. One amendment covers all five stages; Astra integrates per-stage DDs for
   human-viewable deliverable + independent blind-review acceptance axis, mirroring
   the C03 method proven on btdongle (declaration invariant, presentation layer
   separate, agent hand-draft as producer, blind review, manifest binding, NN-vN
   naming, human/machine tree split per R-G).
2. Execution order: C03 close-out (ERC adjudication, BOM export, 00 block names) →
   C04 (Gerber copper render; same board) → C02 (printable STL) → C01 (product
   render) → C00 (PRD docx check).
3. C01 renderer: user asked why Blender was not chosen originally. Measured: the
   repo has zero Blender references in source/specs/plans; the only renderer is
   pyrender/EGL (`eda-bridge/model_render.py`, shared by C02 enclosure + C04 board).
   No recorded decision against Blender exists — it was never evaluated. Blender
   adoption goes through DD-9 clearance (GPL-2+ tool used as external subprocess,
   headless `blender -b` feasibility in the ee image, image size, license of any
   addon) before any implementation. Not a fallback: pyrender stays until Blender
   is cleared or rejected on evidence.

## 3.2 R-H integration draft (Astra, 2026-10-07, topic R-H-scope-amendment)

Status: DRAFT amendment, not implementation authorization. DD IDs below are stage
placeholders; allocate the next unused DD IDs at integration (DD-1..15 unchanged).
R-H restores C00–C04 as delivery scope; it does not erase stage dependencies or turn
previews into engineering acceptance.

COMMON DD — producer-independent, stage-bound presentation authority
- Each stage binds in ONE manifest: approved declaration, candidate revision,
  producer/toolchain identity, machine evidence, independent visual review.
- User-approved geometry/placement/intent outranks machine proposals; agent hand
  drafting is a PRODUCER, not human approval. Changes are baseline-bound proposals.
- R-G preserved: human PNG/PDF + index in the human tree; editable sources, STL,
  Gerbers, data and evidence in the machine tree; no new directory allocation.
- Filenames `NN.<stage>-<name>-vN`; one coherent revision per artifact set; history
  retained; every view names its source revision and carries visible DRAFT status.
- A review ACCEPT cannot override a failed/unmeasured deterministic gate; a passing
  gate cannot substitute for an intelligible view. No silent producer fallback.

DD-C01 — product appearance and intent
- Human: `NN.c01-product-vN.png` (declared exterior views), `NN.c01-cmf-vN.png`,
  review PDF. Machine: scene/source, assets, camera/light/material recipe, tokens,
  manifest.
- Invariants: approved ID direction, CMF tokens, interface/face layout, envelope, with
  source attribution. Missing appearance/geometry stays unresolved, never invented.
- Producer: TBD by clearance + benchmark; pyrender is the explicit baseline, neither
  presumed sufficient nor automatically replaced.
- Checkable: source/asset completeness, token→material assignment, declared view/
  camera coverage, dimension/interface conformance where geometry exists, render
  success, version binding. Pixel colour is not material/finish certification.
- Blind review: what product/use is shown; identify controls, connectors, status
  indications, user orientation; which materials/finishes differ; what is obscured or
  contradictory. Compare afterwards to the frozen ID brief.
- Not claimed: electrical correctness, physical CMF approval, colour accuracy,
  ergonomics, manufacturability.

DD-C02 — printable enclosure geometry
- Human: `NN.c02-enclosure-vN.png`, `NN.c02-exploded-vN.png`, section/clearance PDF.
  Machine: real per-part STL, parametric source, STEP only when genuinely exported,
  units/print-profile metadata, reports.
- Invariants: versioned constraint set — board envelope, component heights, holes,
  connector faces/openings, wall/clearance, assembly interfaces, coordinate frames.
- Producers: existing OpenSCAD/build123d in ME worker, both on the same constraints,
  per-export evidence, no assumed equivalence.
- Gate: non-empty valid mesh, manifold/watertight, orientation, scale, measured wall/
  clearance/fit vs declared thresholds; process/material/nozzle/build-volume/
  orientation assumptions + slicer check for any qualified "printable" claim.
- Blind review: how parts assemble, how the board is supported, which opening serves
  which interface, access/clearance/print-orientation concerns; section/exploded
  views must expose hidden relations.
- Not claimed: watertight ≠ printable; no physical print, tolerance fit, strength,
  thermal/fire/IP, production approval without evidence.

DD-C04 — placement and actual copper presentation
- Human: `NN.c04-placement-vN.png`, `NN.c04-<layer>-vN.png` for EVERY declared copper
  layer, labelled stack/orientation composite PDF. Machine: editable PCB, exact
  Gerber/drill set, BOM/CPL where applicable, gate reports.
- Invariants: frozen C03 pin/net partition, qualified footprint/pad mapping, board/
  mechanical constraints, stackup, net classes, DRC rules. Changes are separate
  proposals, never aesthetic corrections.
- Producers: approved human placement first; agent placement is a proposal;
  constrained engine placement/routing within locks. Existing workers remain the
  execution boundary.
- Gate: final filled-board DRC + pad/net-vs-actual-copper connectivity + complete
  unrouted/short/open coverage; bind the exact exported Gerber/drill set and verify
  export parity/connectivity (not merely board net attributes). If Gerber-level
  parity cannot be measured, mark UNMEASURED — a Gerber preview or PCB DRC does not
  prove those bytes. Export-for-review ≠ authorized fabrication release.
- Blind review: locate main ICs/connectors + support groups; explain visible power/
  signal/return organization, orientation, layer legend; identify congestion, access,
  isolation/clearance concerns without claiming invisible connectivity.
- Not claimed: SI/EMC/thermal, fabrication readiness, assembly correctness; send-to-
  fab keeps deterministic gates + explicit user approval.

C00/C03 closure anchors
- C00: `NN.c00-prd-vN.docx` in machine tree + human PDF; check requirements/source/
  decision coverage, cross-stage consistency, render/readability — not mere existence.
- C03: preserve accepted module book, exact native/netlist baseline, reviewer scope;
  finish ERC adjudication, BOM coverage, J1/U1/U2 overview naming. Pin-group equality
  is not relabelled as complete electrical validation.

Blender DD-9 decision gate (no prior rejection exists; absence of references is not
an evaluation)
- Pin exact release/source/binary digest; verify actual GPL licence/redistribution
  obligations. Subprocess use is not blanket clearance for bundled assets, addons or
  linked code. Inventory addons, deps, fonts/textures/models, notices; default NO
  optional addon until cleared. Separate project output rights from tool
  redistribution.
- Evaluate headless `blender -b` in the proposed EE image on an AUTHORIZED build
  host; record CPU/GPU/EGL needs, image/build/cold-start/render-time/memory deltas,
  failure behaviour. No core heavy dependency. EE hosting is a deployment candidate,
  not permission to move C02 geometry ownership out of ME; decide renderer
  ownership/reuse explicitly before integration.
- Freeze scene/units/cameras/lights/materials/colour management/seed/backend/version;
  measure reproducibility; declare comparison tolerance (no bit-identical GPU promise);
  separate stable geometry from stochastic rendering.
- Matched C01 subjects through pyrender AND Blender, same ID intent/views; compare
  fidelity, missing features, blinded comprehension/CMF acceptance, operational
  budgets fixed BEFORE selection. Retain pyrender if it meets required views/quality
  at acceptable cost; adopt Blender only if it demonstrably closes a required gap and
  clears licence/runtime/reproducibility. Neither passes → report BLOCKED; no
  automatic fallback or forced replacement.

Order ruling
- Output sequence stays R-H §2 (C03 close-out → C04 → C02 → C01 → C00 doc check), BUT
  C00 requirements and frozen C01/C02 mechanical inputs are validated BEFORE C04 entry.
- Missing/contradictory footprint, board outline, connector face or envelope BLOCKS
  production C04; obtain upstream decisions, never invent geometry. The known D1
  footprint conflict (SOT-363 vs SOT886, thesmart_products BR 2026-10-06) must be
  resolved before this board enters C04.
- C01 last is acceptable only because its ID/CMF constraints already exist or are
  resolved earlier; C00 cannot be deferred as the source of requirements.
- C04 transfer from C03: intent-first/module-aware placement, locks, native evidence,
  two-axis review. Schematic page partition and "all IC pins visible" do NOT transfer
  literally to PCB geometry.
- No new user ruling round is needed to PROPOSE a C04 spike under R-H; freeze
  board-specific constraints and obtain approval of the placement candidate.
  Mechanical/electrical/scope conflicts → ASK. Do not assume reroute-on-human-
  placement is already proven.
- Packaging/build-host and S4 commit gates unchanged.

User ruling (2026-10-07, after reading §3.2): draft APPROVED as written; C03 close-out
dispatch authorized (ERC adjudication, BOM export, 00 block names J1/U1/U2; Sonnet 5.5,
one round, table deliverable). Astra allocates the formal DD IDs for §3.2 at
integration. Same ruling on the D1 footprint path: the three conflicting ★ bindings
in thesmart_products are not to be adjudicated by this officer — the user orders a NEW
thesmart_products duty-officer session; the D1 BR is handed to it. Still not
implementation authorization for C04/C02/C01/C00.

D1 block LIFTED (2026-10-07, thesmart_products ★ ses_eed1fb0b6ffelFUGhmXVSGcp3z,
BR §5 option (a)): design.py:84-89 now declares `Package_TO_SOT_SMD:SOT-886` with
datasheet provenance (PESDXL4UF_G_W Rev.04 Table 1 p.1 / Table 4 p.3 / Fig 13 p.12;
pads 1..6 = pins 1..6, netlist nodes unchanged). Officer-verified on disk: design.py
bytes + generated/sch_bodesign/btdongle.net SOT-363 count 0 (mtime 04:22 same day).
Uncommitted in that repo; commit is their authorization. Consequence here: the
module book (11.j1_usb-v3, editable/usbc) still carries SOT-363 → REAL footprint
mismatch, to be closed by a baseline-bound ChangeProposal (11.j1_usb-v4) after the
C03 close-out round, not by editing page files mid-round.

User ruling R-I (2026-10-07, after the question "is this building the real product or
developing bodesign?"): **dual track**. The btdongle board is the SPECIMEN; bodesign
grows capability on it in the same rounds. Each C04 round therefore has two
deliverables: (A) the product artefact in `~/products` (Sonnet hand-draft producer,
same method as C03); (B) the bodesign tool/test that judges (A), landed in
`packages/` + `tests/` with (A) as fixture. Acceptance of a round shifts from "the
specimen looks right" to "the bodesign gate decides correctly on the specimen"
(positive + negative control). Hand-drafting that leaves no tool behind is a
method note, not progress. ASK-1..4 of `c04-entry-freeze-20261007.md` §3.1 ruled by
the user as product owner (D-3 repealed; Option A 28×93 carrier; ETA6003 supersedes
OD-1; 3-pin JST-PH).

## 4. Not changed

P1 contracts (7b0d8b5 / 6363c54 / d190480) accepted. Partition, replica, netlist
arbitration settled. DD-1..DD-12 stand. 3.3's acceptance (five readable leaves)
stands; only the path to it changes. Slice-A handler `ses_f8309c2e0` stays parked;
its tree edits are preserved, not reverted.
