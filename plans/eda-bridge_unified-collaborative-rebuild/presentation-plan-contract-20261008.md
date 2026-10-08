# PresentationPlan / Intent Review Contract v1.0.0

Status: DRAFT contract materialization of DD-16 / R13 / AC20, not human,
electrical or manufacturing approval. Data catalog revision: 1.3.0. The executable
JSON Schema is the new top-level `presentation_plan` definition in
`data-schema.json`; existing catalog definitions are unchanged.

## Authority and baseline

DD-16 separates composition from circuit identity; DD-17 / R14 / AC27 bind exact
human and machine subjects. Amendment §3.1 R-B, R-D', R-E, R-F and R-G govern
complete module views, support ownership, functional overview and tree separation.
R-C typography is a separate human/native realization concern. R15 and freeze §4
do not authorize fabrication. Sandbox decisions are not human product approval.

Every source reference carries a path, SHA256 and purpose. `baseline_refs` binds
the circuit netlist, book netlist, native pages, human PNG/PDF, inventories,
generators, review corpus and authority texts. The baseline checksum root is the
pre-materialization root, never a self-referential post-rebuild hash.
Legacy `Sheetname`, `Sheetfile`, `sheetpath.names/tstamps` and component `tstamps`
are imported explicitly per reference; a physical identity is derived from that
legacy source identity, not from the repeated book symbols. Changes require a
baseline-bound ChangeProposal. This plan proposes no repartition or geometry edit.

## Schema semantics

- `pages`: ordered page IDs, role, heading, primary refs, native/image source
  references and intent anchors. One overview is non-electrical; `book_pages`
  lists the five existing module pages, not the overview or unrelated C00–C04 views.
- `instances`: exactly one record per physical ref, legacy identity/mapping,
  role, authoritative `home_page`, all presentation `views` and unit inventory.
  U2 home 07/view 08; U1 home 09/view 10; J1 home 11; J2 home 09; J3 home 07.
  All other refs retain their existing book-page membership. Repeated full symbols
  are views of one instance, not clones. Named view approval records bind the
  amendment/user acceptance and historical review ID; historical acceptance never
  implies a fresh review of a later version.
- `pins`: each physical `(ref,pin)` exactly once; native unit membership and
  hidden/stacked metadata are sourced from embedded native library symbols. Each
  record has one ownership page and status `placed`, `off-page-label`, `NC` or
  `hidden-stacked`. `views[].pins` separately accounts every pin of the full
  symbol on every view, including remote stubs, NC and stacked pin lists. Shared
  power pins can be wired in more than one view without duplicate physical rows.
- `local_support`: named relationships with page, anchor ref, member refs and
  evidence. These declare ownership, not electrical behavior or sufficient support.
- `interfaces`: each declared off-page reference names source and destination
  `(page,ref,pin)`, source evidence, and either a named support relationship or a
  named approved exception. Remote labels do not waive local relationships.
  In v1 interface `evidence_ref` is the named `local_support.id`; that relationship
  supplies the native evidence path. Per-view remote stubs use `relationship_id`
  or `exception_id` explicitly. These are declarations, not a native label census.
- `human_locks` and `exceptions`: named target, justification, approval decision,
  actor and source. Empty lists mean no recorded novel lock/waiver, not permission
  to alter existing human geometry. A checker never changes an approval field.
- `reviews`: immutable source SHA256 and line range with evidence class;
  `producer_review_verbatim` and `officer_summary` remain distinct. Review bodies,
  verdicts, scopes and labels are not reconstructed or relabelled.
- `evidence_gaps`: includes missing full text for Reviews 23–28. Those reviews
  concern C04/C02', not acceptance of C03 pages, and are not newly applied to C03.
- `generator`: retained provenance script path/digest. No producer result is a
  verification receipt. Gate receipts name the repo function and HEAD explicitly.

Netlist inventory uses library pin declarations as well as net nodes: isolated
and NC pins cannot disappear because no active net mentions them. Duplicate
physical references in approved module views are normalized explicitly. Per freeze
§4.9.1, real-net membership outranks duplicate `unconnected-*` blocks; two distinct
real nets on one pin remain a conflict. An unconnected node alone is not proof of
NC intent: NC must also be declared and present in the sourced native inventory.
Missing symbols, units, destinations or authority facts are input gaps, not defaults.

## Deterministic scope (PP-01..05)

| Gate | Measured | Not established |
|---|---|---|
| PP-01 | Supported schema/version, required fields and typed structure | Correctness of source prose |
| PP-02 | Symmetric ref/pin coverage, unique physical rows, complete view/unit/NC and native hidden/stacked inventory, no orphan net nodes | Visible routing, actual drawn pin legibility, electrical correctness |
| PP-03 | Named source/destination endpoints, support/exception binding for every declared off-page label | Whether the drawing hides a local connection or communicates intent |
| PP-04 | Declared module/home-view page set equals book netlist leaf pages and current declared files on disk | PNG content, PDF page-content equivalence or readable scale |
| PP-05 | Named lock/exception/view targets, justification and explicit approval provenance | Authenticity of a human decision; no tool-issued approval |

Input/file/parser failures fail fast. PP-01 rejects unsupported schemas before any
downstream gate runs. Missing native library inventory remains unmeasured and
blocks `ok`; it never becomes unit 1 or an empty passing population. `ok` requires
all five gates pass. Negative controls are synthetic; live specimen tests check
shape only. The live positive-control receipt is not a served-runtime test.

## Independent intent-review protocol

Bind reviewer identity, exact image/native hashes, protocol version and answers.
First show artifacts only, at readable/native scale; compare with frozen intent
after answers, not before. Report traceability and comprehension separately:

1. Identify the main module and its purpose; find all pin numbers, supply, hidden/
   stacked lists, units and NC. Can this be done without reconstructing fragments?
2. Explain each pin's local support or named remote destination. Where must the
   reader leave the page? Are local relationships obscured by labels?
3. Explain input/output/control/return organization and why the peripherals belong
   to that module. Identify ambiguity; labels are references, not assembly instructions.
4. From overview alone, recover the J1→U1→U2 power spine and J2 battery relationship;
   distinguish functional dashed links from electrical wires. Ground is not a link.
5. Name residuals and give scoped accept/reject/unmeasured decisions for traceability
   and intent independently. No electrical, calibration or fabrication approval.

Reviews 6–22 remain baseline evidence with original subjects/scopes. No new review
or AC20 native-realization/comprehension completion is inferred by materializing
this contract or passing the plan gate. Architecture boundaries remain core-side
pure analysis; no renderer, service, router or producer fallback is introduced.
