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
- Peripherals (2-terminal parts) live on the page of the pin they serve; a peripheral
  shared by two modules is drawn once, on its primary module's page, and referenced
  from the other.
- This is a presentation form under R-B; the electrical declaration and the native
  58-net partition stay invariant. Module repetition across pages is a presentation
  view of ONE physical instance (DD/Astra: instance identity preserved via explicit
  mapping; no cloned electrical instances).

## 4. Not changed

P1 contracts (7b0d8b5 / 6363c54 / d190480) accepted. Partition, replica, netlist
arbitration settled. DD-1..DD-12 stand. 3.3's acceptance (five readable leaves)
stands; only the path to it changes. Slice-A handler `ses_f8309c2e0` stays parked;
its tree edits are preserved, not reverted.
