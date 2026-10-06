# S3 first-leaf independent review record (usbc, ELK engine path)

Officer record, 2026-10-06. Evidence for the S1 calibration corpus (spec.md AC16
three-part corpus, part 2: "independently reviewed S3 output classified by actual
verdict"). Reviewers were fresh task() sessions with no project context; prompts
asked four direct topology questions plus per-class a-f findings.

Candidate (run-20261006-133234, receipt s3-engine-spike-receipt.md sha256 f6d6341e…):

| artifact | sha256 |
|---|---|
| out/usbc.kicad_sch | dcfdc6b2e6ac2d830922b6e56cd02190ccd30439dc3e495dc66918ba20095bf5 |
| native/svg/usbc.svg (kicad-cli 9.0.9) | 28bd7d5e7355ec5e6711439700d18fb4c564c8ce7899a18cee45679c398e91c8 |
| native/usbc.net (fresh regen) | aed12f2f50943e7293e5d8c3df91450716423f23d2971ee11d16c230e164fa8a |
| native/usbc.png (ImageMagick 150 dpi of SVG) | 2dae808c94cba07301c3be3bdb44a4078635b49cf8f417f0a0b0e04f24122b21 |
| native/pdfpath/usbc.pdf (kicad-cli sch export pdf) | 3c5b4402ecadcd416408f19bd8e478d051cddb181812bdb068bfc03577d87338 |
| native/pdfpath/usbc-1.png (pdftoppm -r 150) | ddd66e937d04892d277d2651f05e4eb6a061a07cc1b8992b83b54180300fcdbc |

## Review 1 — ses_ef0378cc2ffeABsPl2gqj80lmq on native/usbc.png (ImageMagick render)

Verdict NO. Dominant finding: every text string double-drawn with ~3 px offset.
Topology questions: F1 in series YES; CC1/CC2 separate YES; no wire through body;
dots present. Per class: a none; b1 none; b2 one (CC1/VBUS_CON/CC2 verticals converge
~x440,y350); c none; d none; e D1 refdes/value + GND flag drawn on first diode leg;
f ghosted text (dominant), page use ~25%, R2 far below.

Status: SUPERSEDED for class f. Mechanical re-render via kicad-cli PDF -> pdftoppm
(ses_ef034051dffedTD0VVI30wFPAj) shows all text drawn once and crisp; the ghosting is
an ImageMagick built-in SVG rasteriser artifact, not present in the source. The
a/b1/c/d/e observations stand and agree with review 2.

Ruling: ImageMagick SVG rasterisation is not an acceptable human-view render path.
Formal human-view render = `kicad-cli sch export pdf` -> `pdftoppm`. SVG remains the
S1 instrument input only.

## Review 2 — ses_ef0334aadffeqEnaIpz6SI1Kz8 on native/pdfpath/usbc-1.png (PDF render)

Verdict NO, "but close". Topology: F1 in series YES (no bypass); CC1/CC2 separate
each with own resistor YES; no wire through body; three dots correct, none missing.

Per class (pixel coords on 1754x1240):
- a: none.
- b1: none.
- b2: CC1 branch to R1 crosses VBUS_CON vertical at (435,345) without a dot; CC1 dot
  only 15 px left at (420,345); "VBUS_CON" text directly under the crossing; three
  verticals x=405/420/435 run 15 px apart for ~200 px. Matches S1 finding
  B2_FOREIGN_CROSS_NO_DOT at (73.66, 58.42) mm exactly (73.66*5.906=435).
- c: none.
- d: none; near-miss F1 VBUS output corner (480,330) 15 px above R1 feed corner (480,345).
- e: CC1/VBUS_CON verticals strike through "USB_C_16P" text; TVS drawn as four bare
  diode glyphs with no body outline, only first shows GND pin.
- f: "CC2" label at (417,283) sits on the CC1 wire (labels wrong net visually);
  "CC1" label struck through by VBUS_CON vertical; GND flag overlaps D1 refdes/value;
  "500mA" nearly touches VBUS flag; ~20% page width / 45% height used; R2 hangs at
  y=645-700 stretching CC2.

Does well: crisp single text; F1 clearly series; separate pull-downs; NC crosses on
unused pins; title block correct; orthogonal on-grid wires.

## Corpus classification (officer)

- Classes a, b1, c, d: two independent reviewers, zero findings, on an artifact whose
  regenerated native netlist matches the declared circuit 24/24 pins. Candidate
  ACCEPTING evidence for a/c/d (b1 is not a measured S1 class). Not yet bound by an
  evidence-authentication boundary (S1 receipt §9) -> calibration stays partial.
- Class b2 (class b): REJECTING evidence, adjudicated, S1 and reviewer coincide on
  location.
- Class e: REJECTING (text strike-through, TVS body) — note e findings here are
  text-vs-wire, which S1 class f "text-vs-symbol-graphics NOT measured" does not cover.
- Class f: REJECTING (label-on-wrong-wire, flag/refdes overlap, page use).

Overall S3 first leaf: NO. Valid spike finding; AC18 not claimed; 3.3a/3.3c unchanged.

## Review 3 — ses_eefcccfd4ffecg4SwXuRkEeILL on R2 candidate run-20261006-150709 native/pdfpath/usbc-1.png

Candidate: out/usbc.kicad_sch 9db00c80…, fresh usbc.net 677e8d08…, usbc.svg 8cc7f322…, PDF 22d4553b…,
PNG 70335b15cc4d4b032eb26e7eedeef6273e2150172be957ba0e83e1e59ea63338. S1 instrument d0dca6c8… (r5).
The reviewer session produced TWO reports on the same hash (both verified it); they are recorded
separately because they disagree on one text finding.

Both reports: verdict NO. F1 in series YES; CC1/CC2 separate each with own resistor YES; no wire
through body; three junction dots correct, none missing; a/b1/c/d none. b2: ONE dot-free crossing
CC1 × CC2 next to the CC1 junction dot (report A ~(430,468); report B ~(413,412)) — "moderately
misleading": the adjacent dot invites misreading as a connection. Matches S1 B2_FOREIGN_CROSS_NO_DOT
at (69.85, 69.85) mm. e: D1 TVS as four bare glyphs, only one GND exit visible — cathodes look
unterminated (symbol presentation, not engine). f: page use ~14-17 % of the sheet; R2 directly under
R1 (improvement over run-133234 acknowledged by both).

Disagreement (f): report A says GND flag collides with "D1"/"PESD5V0L4UF" at ~(500,490-510) and
"VBUS" label touches F1 text; report B says GND flag (465-508,323) and D1 text (473-550,382/398) are
separate, VBUS flag is tight against F1 but not overlapping, "VBUS_CON" text sits on the wire corner.
S1 r5 on this candidate: F_WIRE_THROUGH_TEXT 0, F_FLAG_THROUGH_TEXT 0 — consistent with report B.
Officer ruling: flag/refdes overlap on R2 is CONTESTED, not established; text crowding (VBUS flag vs
F1, VBUS_CON at corner) is accepted as a near-touch finding. Not used as calibration evidence either way.

## Corpus classification (officer) — R2

- a, c, d: zero findings, two reports, fresh netlist 24/24 — accepting-candidate cells (unbound).
- b: REJECTING, adjudicated; S1 and both reports coincide on CC1 × CC2.
- e (TVS glyph): unmeasured item, carried; not resolved by any sensor.
- f: near-touch/page-use diagnostics; overlap claim contested.

Overall R2: NO on b2 (+ carried e glyph item). Astra ruling (round r2): b2-only NO ⇒ R3 bounded
D1-native-orientation extension before any five-leaf expansion.

## Contrast with slice A (legacy router)

Slice A CP1-CP3: nine NO verdicts, every one citing apparent series bypass / merged
nets / label-only local wiring (classes a, c, d). ELK path first leaf: zero findings in
a, c, d from two reviewers. Remaining defects are placement density, label placement
and one planar crossing — a different and smaller defect family.

## Review 4 — ses_eefae0217ffeygRD2CDKj8KKEl on R4 candidate run-20261006-162241 native/pdfpath/usbc-1.png

Subject: PNG sha256 9407f5c441f27135ff2261560bfbd6570198567bb3f186b5c8f5d23c1ed28533 (reviewer verified);
sch 0310d9ab4c71873f46af72c53dcdb52340e8a950c0630a5905cf7c51d56cdd62; render chain kicad-cli 9.0.9
sch export pdf -> pdftoppm -r 150. Placement model M2 (ELK partitioning J1 < R1 < D1 < R2).
S1 9c18bc51 on this candidate: a-f zero findings, verdict indeterminate (calibration partial).

Verdict: **NO** — "every net is traceable by eye, but D1 draws as four loose diode glyphs; only the
top one shows a ground return, so a reader would stop and wonder whether CC1 and CC2 are protected.
The page is also lopsided."

Direct answers: F1 in SERIES (no bypass path; D1 VBUS clamp taps pre-fuse side, correct).
CC1/CC2 SEPARATE, own pull-downs, never join. No wire through body / over foreign pin.
Three junction dots (397,465) (412,510) (555,675) all correct, none missing, none spurious.

Per class:
- a: none. (VBUS flag tip touches F1->C1 wire mid-segment without dot — legal KiCad, unmarked.)
- b1: none. b2: **none** — the R2/R3 CC1xCC2 crossing is GONE. One near-crossing at x≈397, y 480–525:
  VBUS vertical ends y≈480, CC2 vertical starts y≈525, CC1 horizontal at y=510 passes through the gap;
  reads at a glance like one continuous x=397 line crossed by CC1. "Mildly misleading, not an actual crossing."
- c: none. d: none.
- e: **D1 drawn as four separate diode glyphs (x≈607, y 465/510/555/600); only glyph 1 has a GND flag;
  glyphs 2–3 have a wire on one side and nothing on the other; glyph 4 NC only. Does not read as one component.**
  Refdes "D1"/value float between glyphs 2 and 3, away from the flagged glyph.
- f: no text-on-text overlap, no label on foreign wire. Near-touches: "B5" ~4 px under CC1 wire;
  "VBUS_CON" left edge ~3 px above the descending wire at x=450. Text ~10 px high on 1754 px render
  (legible when zoomed). Occupancy ~19%, left half / upper two-thirds only.
- VBUS flag: hexagon x 400–450, y 278–292, top edge within 1–8 px of F1's bottom pin/body — near-touch
  with symbol, NOT with "F1"/"500mA" text.
- GND vs D1 text: no overlap (~60 px apart).
- R2: x=802, 345 px right of R1 and ~175 px lower; forces a 405 px CC2 run along y=675. "Traceable but
  stretches the wire and leaves the page lopsided."

Done well: F1 series clear; CC1/CC2 cleanly separated; three correct dots; no shorts/crossings/through-body;
NC marks on unused J1 pins; refdes/values of J1/F1/C1/R1/R2 clear of wires and each other; orthogonal tidy wiring.

## Corpus classification (officer) — R4

- a, b (b1+b2), c, d: zero findings; one independent report + S1 zero findings + fresh netlist 24/24 —
  **accepting-candidate cells** for a/b/c/d (unbound; needs calibration-record binding at the boundary).
  This is the first candidate with class b clean under independent review.
- e: **REJECTING, adjudicated** — the D1 TVS multi-glyph presentation (carried since Review 1 as
  "unmeasured") is now the primary NO cause. S1 has no e sensor for symbol-coherence; this is an
  instrument gap, not a sensor miss.
- f: near-touch diagnostics (VBUS flag vs F1 body ~1–8 px; VBUS_CON corner ~3 px; B5 ~4 px); page
  occupancy 19% / lopsided; R2 far right. No overlap established. Diagnostic only.
- VBUS flag on wire mid-segment without dot: legal; not classified as a defect, noted.

Overall R4: **NO on e (D1 symbol coherence) + f layout density (R2 position / lopsided)**. b2 resolved
by lever A model M2 at the cost of +48% area. Astra r3 ruling: stop after this checkpoint; next
decision is architectural (D1 presentation = native symbol choice/unit grouping, not router work;
R2 position = ELK partition cost, not a sweep).

## Review 5 — ses_eef8cff90ffe1jrnCZvSkoVMW6 on R5b candidate run-r5b-s1-165624 native/pdfpath/usbc-1.png

Subject: PNG sha256 db0ba9ec09fb0ee829a49646c005c0d77e12ddba65dce3350f240f3d9d76b30b (reviewer verified);
manifest root 1001bc33b0c6f359a9c3ff92d41a8c22e982f159a43ea1e6866c1b153cc97638 (25 entries, officer rc=0).
Amendment A: ONE sheet-level dashed (rectangle) around D1, rectangle uuid = uuid5(D1 uuid, "presentation.outline");
0 "(group" tokens; D1 lib block byte-identical to baseline. M2 partition + S1 compact spacing
(nodeNodeBetweenLayers 6.35, nodeNode 3.81); area 7867 mm², wire 287 mm. S1 9c18bc51: a-f zero findings,
verdict indeterminate; S1 does NOT read sheet-level rectangles (lib-symbol rectangles only) — known blind spot.

Verdict: **NO — "a close call"**. "A competent engineer would hesitate over D1: only one of its four
diodes has a drawn return to GND, so the CC1 and CC2 clamps look unterminated. The dashed outline helps
and the net tracing is otherwise clean."

Direct answers: F1 SERIES ✓ (no bypass; D1 ch1 taps connector side via dot (397,457)). CC1/CC2 SEPARATE ✓,
own pull-downs, never touch. No through-body / foreign pin. Dots (397,457) (412,502) (555,667) all correct,
none missing, none spurious.

Per class:
- a none. b1 none. **b2 none** (no dot-free crossing of different nets).
- c none. d none.
- e: **D1 — dashed box groups the four glyphs visually but "still does not read cleanly as one component":
  only glyph 1 has a GND flag; glyphs 2/3 have a signal wire on the left and nothing on the right;
  glyph 4 NC (identifiable, X ~8 px outside box edge). "Clamps to nowhere unless the reader already knows
  the part has a common ground." Main readability failure.**
- f: no text overlaps, no clipping, no label on foreign wire; text small but legible. Occupancy ~18% area;
  lopsided (right 55% / bottom 35% empty).

Named questions:
- **Box implies internal shared connection?** "Reads as a package boundary only. No internal wires drawn,
  nothing suggests the diodes are wired to each other." A knowledgeable reader infers common ground from
  box + part knowledge, not from drawing. "No sign the box suggests VBUS, CC1 and CC2 are shorted."
  → Astra's NO-condition ("box implies internal wiring") did NOT fire.
- VBUS_CON: right of wire corner, "slightly tight but not ambiguous".
- VBUS flag: top edge a few px from F1 body bottom — near-touch of body; clear of F1/500mA text.
- D1/PESD5V0L4UF text: clear of GND flag (~60 px) and outline (~16 px).
- R2: ~308 px right of R1, 142 px lower; CC2 run ~370 px, "correct but stretched"; asymmetric vs CC1.
- **Collinear verticals x=397**: VBUS_CON vertical ends y=472, CC2 vertical starts y=517, CC1 horizontal
  at y=502 passes the gap → "at a glance can read as one continuous vertical crossed by a horizontal;
  misleading at a glance." Carried since Review 4; unchanged.
- A5/B5: clear of wires but cramped; B5 3–5 px below CC1 wire, "could be briefly mis-associated".
- CC1 stub x=412 vs CC2 vertical x=397: ~15 px parallel over ~8 px — mild at-a-glance risk.

Done well: F1 series; CC separation; no crossings; all dots; consistent label pattern; NC on unused
connector pins; outline non-intrusive (text and GND flag clear of it, touches no foreign wire); no
text-wire overlap; title block and frame clean.

## Corpus classification (officer) — R5b

- a, b, c, d: zero findings; second consecutive independent report with class b clean (Review 4 + 5)
  + S1 zero + fresh netlist 24/24 — accepting-candidate cells (unbound).
- e: **REJECTING, adjudicated — narrowed**. The outline resolved "does not read as one package" to
  "groups visually"; the residual e cause is **undrawn GND return for channels 2/3** (symbol-geometry:
  PESD5V0L4UF native symbol has one GND pin pair for a common anode; the per-glyph drawing has no
  anode-side terminal for ch2/ch3). Box-implies-wiring NO-condition did not fire.
- f: carried near-touches unchanged (VBUS flag vs F1 body, VBUS_CON corner, B5 3–5 px, x=397 collinear
  gap, x=397/412 parallel 15 px); lopsided layout; diagnostic.
- S1 blind spot recorded: sheet-level (rectangle) not parsed by readability_render.py (:286-294 reads
  lib-symbol rectangles only) — instrument coverage gap, S1 owner to annotate.

Overall R5b: **NO, close call, on e (D1 ch2/ch3 return not drawn) + f density/near-touches.**
Delta vs R4: outline removed "four loose glyphs"; b2 stays clean; compaction moved R2 6.35 mm left.
Astra r4 ruling §1: "If grouping cannot make each channel and actual shared return intelligible without
made-up connectivity → stop and propose a separately qualified boxed library symbol" — that branch is
now the live question.

## Review 6 — ses_eef662d7affeu5KgEQu1vhjnSu on R6 candidate run-r6-173849 native/pdfpath/usbc-1.png

Reviewer: independent task(general) session ses_eef662d7affeu5KgEQu1vhjnSu; PNG-only, no intended conclusions given.
Subject: PNG sha256 b25d7d50b3530627ec8f12a2330e568a0321d57f717d23fe5e1a3f909b261004; manifest root 174b3b4696e1edacf81aaa53d4addf58986ad371c11aeb353094ecf201e1080d.
Candidate: D1 = authored `Bodesign_Presentation:PESD5V0L4UF_Boxed` (per-run spec copy + symbol_dirs), M2 placement, R5b compact spacings; NON-FABRICABLE; S1 9c18bc51 a-f zero findings, verdict indeterminate (calibration partial).

Questions as asked: the reviewer's six-question text was written by the officer and is not in this worker's context; it is NOT reproduced here from memory. The worker-side pre-declared set is proposal §10.6 (5 visual questions: trace each clamp's return and name the net; which D1 pins are shown joined and by what drawn element; what the diagram says about the sixth pin; near-alignment x~397 / B5 under CC1 / R2 branch length; what the VBUS_CON text and the VBUS flag attach to). The officer should paste the verbatim dispatched six if this record is to carry it.

Verdict: **ACCEPT** (with carried residuals).

Accepted residuals (verbatim, as relayed by the officer):
- (a) row-3 diode exit stub ~1 line-width from row-2 wire at box left edge (~575,593) — named worst remaining issue.
- (b) VBUS_CON vertical and CC2 vertical share x≈397 column below junction, no dot between, "had to look twice".
- (c) CC1 label crowded against wire end near R1 stub; VBUS flag visually overlaps F1 stub region; D1 GND flag close to box right edge.

Reviewer findings: all four rows traced to the right-hand bar → single GND flag; no false join between left pins ("box outline is clearly a symbol body, not a wire"); x read as intentional NC.

## Corpus classification (officer) — R6

- Accepting-candidate evidence for S1 AC16 part 2 (S3 output + independent review) for the declared single-usbc scope.
- NOT a calibrated status; NOT a blanket accepting entry for every class; not human_approved; not electrical / fab / license acceptance.
- D1 readability defect closed for THIS candidate only (PNG b25d7d50…, manifest root 174b3b46…), not globally for the device/library family.

## Review 7 — power_rail — reviewer ses_eeefb4d2effe6j8oOxEB489scL — PNG 1acb3d76… — ACCEPT (marginal)

Subject: R7 run run-r7-20261006-193512 native/power_rail/pdfpath/power_rail-1.png, sha256 1acb3d761b32d67d29745796e03e80ba9459458383a24cc8705eb04a2a96981d. Independent blind review (task(general), PNG-only, open questions, no intended conclusions). Reviewer text VERBATIM as relayed by the officer:

1. Components seen: U1 ETA6003 — charger/switcher IC (pins IN 2, ENB 6, USB_DET 13, ENPPB 8, NTC 7, ISET1 11, ISET2 12; SW 3/4, SYS 1/15, BATT 14/16, STAT 9; PGND 5, GND 10, EP 17 at bottom). L1 2.2uH/3A inductor — between SW_NODE and a SYS flag. C5 1uF/10V — from BATT net to GND. R4 2k — ISET2 to GND. R3 2k — ISET1 to GND. R6 100k — pull-up from SYS flag to USB_DET net. C3 10uF/16V — USB_DET/IN node to GND. C2 10uF/16V — VBUS to GND. C4 22uF/10V — SYS flag to GND, standalone. Power flags: GND → U1 pins 5/10/17 and ENB(6), C5, R4, R3, C3, C4, C2. SYS → U1 pins 1 and 15 (two separate flags), L1 bottom, R6 top, C4 top. VBUS → C2 top and, via wire, the C3/IN/USB_DET junction. Signals ENPPB, NTC, STAT are off-sheet labels on U1 only.
2. Paths: Input: VBUS flag → wire up to junction dot → C3 to GND; same junction → long wire left → up to U1 pin 2 IN. The same junction also connects (via junction near R6) to USB_DET and pin 13 — so IN and USB_DET appear tied together with C3. Cannot tell whether that is intended; the IN wire and USB_DET wire run parallel into the same dot. Switcher output: U1 SW pins 3/4 → junction SW_NODE → L1 → SYS flag. Then SYS returns to pins 1/15 only through the flags (no drawn wire). BATT 14/16 → junction → C5 → GND.
3. Crossing/proximity concerns: Top-centre: pin 14 BATT and pin 16 BATT both have short stubs that meet with a dot; the label "BATT" text overlaps the dot and stub so it is hard to tell if pin 14's wire actually joins. Bottom-centre (D-3): the vertical IN wire and horizontal USB_DET wire both terminate at the same dot just above C3 — ambiguous whether IN joins USB_DET or just passes.
4. Text/label issues: "BATT" pin names of pins 14 and 16 overprint each other and overlap the junction dot (top of U1, right side). Net label "SW_NODE" sits right on the junction dot; readable but crowded. C4 is isolated far from everything it relates to (SYS decoupling, bottom-left). Long unlabelled wires (IN, ISET1, ISET2) run across the whole page with no label at the IC end.
5. Partially deliberate — IC left-ish with inputs left and outputs right, grounds down — but passive components are strung down a single column with huge empty runs, and C4/C2 are stranded, so it reads more like an auto-placement than a hand-arranged power stage.
6. ACCEPT (marginal). Worst problem: the BATT pin-name/junction overprint at U1 pins 14/16 combined with the IN–USB_DET shared junction above C3 leaves two power connections that a reader cannot confirm without the netlist.

## Review 8 — battery — reviewer ses_eeefa941fffe3Fin3gScYNqHim — PNG 2fb63a3d… — ACCEPT (marginal)

Subject: native/battery/pdfpath/battery-1.png, sha256 2fb63a3da91d07ab9c9f80187f52131dc1f88d0545c28b13d467481817d2749e. Independent blind review (same conditions). Reviewer text VERBATIM:

1. Components: Q1 DMG2301L (P-channel MOSFET, circular symbol, pins 1/2/4 visible); C6 100nF capacitor; R5 10k resistor; J2 BAT_PH2.0 3-pin connector (pins 1,2,3); TP2 TP_BATT test point. Labels/flags: BATT label — attaches to the wire at Q1 top side, which also runs to TP2. GND (left of Q1) — on Q1 pin 1 (gate). BAT_EXT label — on the horizontal wire from Q1 pin 2 down to J2 pin 1 and to C6 top. GND below C6 — C6 bottom. NTC label (near R5) — connects R5 top and J2 pin 2; a second NTC label at top-left (A1) floats alone with the note "→ U1.7 NTC — home: power_rail". GND at J2 — J2 pin 3. GND below R5 — R5 bottom.
2. Main path: J2 pin 1 (battery +) → wire up → junction at BAT_EXT → left to Q1 pin 2 (drain/source) → through Q1 → pin 4 at top → BATT label and TP2. Branch at junction → C6 → GND. Q1 gate pin 1 → GND (always on). J2 pin 2 → NTC → R5 → GND. J2 pin 3 → GND. Which Q1 pin is source vs drain: cannot tell from the symbol.
3. BATT label wire: the green horizontal wire at Q1 top (y≈300) attaches to the BATT label and to TP2 — but the label sits left of Q1 while Q1 pin 4 is on the right; cannot tell whether the wire actually touches Q1 pin 4 or passes beside it. The vertical wire from the junction to J2 pin 1 ends very close to pin 2's wire; pins 1 and 2 are within a line-width of each other.
4. Q1's "1" pin number overlaps the GND flag tail. J2 pin numbers 1/2/3 crowd the wires and the GND flag at pin 3 sits almost touching the pin-2 wire. "BAT_EXT" text is fine.
5. Deliberate but cramped — a small, tidy cluster with large empty sheet and tight pin spacing at J2.
6. ACCEPT (marginal). Worst problem: Q1's connection to the BATT/TP2 wire is ambiguous — the wire runs across the top of the symbol and I cannot confirm it terminates on pin 4.

## Review 9 — charge_enable — reviewer ses_eeefa6223ffeAnt7aK0XLprYwW — PNG bf550ed1… — ACCEPT (marginal)

Subject: native/charge_enable/pdfpath/charge_enable-1.png, sha256 bf550ed168047e763b41cc7b1663097bb99b3342e99f6b5ec2e1141b0fced12d. Independent blind review (same conditions). Reviewer text VERBATIM:

1. Components: R7 (resistor, 1k), vertical, top pin to net label STAT, bottom pin to a green horizontal wire. D2 (diode/LED, "CHG_AMBER"), anode on right to green wire, cathode on left to a GND label. SW1 (PWR_SW, SPDT-style switch, yellow body): pin 2 to GND label on left; pin 1 to ENPPB label; pin 3 to BATT label on right. Labels: STAT → R7 only. GND → D2 cathode and SW1 pin 2 (two separate flags). ENPPB → SW1 pin 1; a second stand-alone ENPPB label at top-left (with blue annotation "→ U1.8 ENPPB — home: power_rail") connects to nothing drawn on this sheet. BATT → SW1 pin 3. "CHG_LED_A" is a text/net name at the right end of the green wire. No power symbols.
2. Path: STAT → R7 top → R7 bottom → green wire runs right along the bottom edge, turns up at the right corner (near CHG_LED_A text), runs left into D2 anode → D2 → GND. So STAT drives the LED through R7 (LED lights when STAT low). SW1 path: BATT ↔ common ↔ ENPPB/GND — cannot tell which pin is the common pole; the switch arm appears drawn from pin 2 (GND) toward pin 1, so it reads as ENPPB shorted to GND in this position; relation to BATT on pin 3 unclear.
3. No crossings. Only ambiguity: whether the ENPPB label on SW1 pin 1 and the floating ENPPB label top-left are intended as the same net (they are by name, but one is unattached visually).
4. CHG_LED_A text abuts the wire corner, touching the wire end. "GND" label on D2 slightly collides with the LED cathode arrows. Otherwise no overlaps.
5. Reads as sparse but deliberate; three islands in the upper-left corner of an otherwise empty A4 sheet.
6. ACCEPT (marginal). Worst problem: the dangling top-left ENPPB label with the "home: power_rail" annotation sits unattached to any wire, and the switch's pole/throw assignment (what BATT actually switches) is not legible from the symbol.

## Review 10 — mcu_swd — reviewer ses_eeefb0caeffeiNGcy7ZGRz5GcZ — PNG d5aecaa1… — ACCEPT

Subject: native/mcu_swd/pdfpath/mcu_swd-1.png, sha256 d5aecaa15926557623e2faff6df4f477bd5187e3aa05093e874b432a7f118683. Independent blind review (same conditions). Reviewer text VERBATIM:

1. Components: U2 RaspberryPi_Pico_2W (large yellow MCU module); J3 "SWD" 3-pin debug header; SW2 "RESET" pushbutton; C7 100nF; R8 10k; C8 10uF/10V, C9 100nF (both SYS→GND); C10 10uF/10V, C11 100nF (both +3V3→GND); TP1 TP_SYS test point on SYS. Net labels/flags: SYS → U2 pin 39 VSYS, C8, C9, TP1. +3V3 → U2 pin 36 3V3, U2 pin 35 ADC_VREF, R8 top, C10, C11. GND → U2 pin 3 GND, U2 pin 33 AGND, SW2 far side, C7, C8–C11 bottoms, J3 pin 2. LED_BT → GPIO16 (21); LED_WIFI → GPIO17 (22); SW_USER → GPIO18 (24); VBAT_SENSE → GPIO26_ADC0 (31). VBUS (40) and 3V3_EN (37) are marked no-connect. Local labels SWCLK (at U2 SWCLK) and SWDIO/RUN (near the right-hand bus).
2. Path A, debug header → MCU: J3 pin 1 runs left along a horizontal wire to the U2 SWCLK pin (D1, label SWCLK) — clear. J3 pin 3 runs left then up to U2 SWDIO (D3) — clear. J3 pin 2 is GND. Path B, RUN: U2 pin 30 RUN goes left, down the far-left vertical, then right along a horizontal to a junction dot (right of centre), up to another junction dot, where it splits to C7/the "RUN" label and to SW2 (other side GND). R8 (10k pull-up from +3V3) drops down and joins the lower junction dot. Power: SYS flag → pin 39; +3V3 flag → pin 36; GND → pin 3. All readable.
3. Middle-right (around the J3 header): the horizontal RUN wire with its junction dot sits directly above the "SWDIO" text and the SWDIO wire's corner, one line-width apart; the SWCLK wire crosses the SWDIO vertical without a dot (correct non-connection), but the three stacked green lines are tight. No ambiguous crossing elsewhere.
4. Text/wire problems: the "SWDIO" label sits below the RUN junction and above the SWDIO corner — it visually reads as naming the RUN wire. The "RUN" label is placed at the C7 top corner rather than near pin 30. VSYS/VBUS/3V3 pin names at the top of U2 overlap each other and the diode symbol inside the body. GND flag for J3 pin 2 crowds between the pin 1 and pin 3 wires. Decoupling cap section (C8–C11, TP1) is far from the Pico it belongs to, spaced too widely.
5. The MCU/SWD/reset cluster is deliberate; the capacitor column below is a mechanical stack with excess empty page.
6. ACCEPT. Worst remaining problem: the SWDIO label placed a line-width under the RUN junction, inviting misreading of which net it names.

## Review 11 — io — reviewer ses_eeefad2e1ffeAUMfeIwbSrchsP — PNG ce066c4d… — ACCEPT

Subject: native/io/pdfpath/io-1.png, sha256 ce066c4d05184105a1fb2248577cc2ae2898f2bec1c347c7195edd0300d8e84b. Independent blind review (same conditions). Reviewer text VERBATIM:

1. Components: R9 1k (top: +3V3 flag, bottom: wire to PWR_LED_K net). D3 "PWR_GREEN" LED (GND flag on one end, other end wire to PWR_LED_K). R10 1k (top: LED_BT label, bottom: wire to BT_LED_A). D4 "BT_BLUE" LED (GND flag, other end to BT_LED_A). R11 1k (top: LED_WIFI label, bottom: WIFI_LED_A). D5 "WIFI_GREEN" LED (GND flag, other end WIFI_LED_A). SW3 "USER" pushbutton (SW_USER label on left, GND flag on right). R12 10k (+3V3 top, SW_USER bottom). C12 100nF (SW_USER top, GND bottom). R13 100k (BATT top, VBAT_SENSE bottom). R14 100k (VBAT_SENSE top, GND bottom). C13 100nF (VBAT_SENSE top, GND bottom). Net labels: +3V3 → R9, R12. GND → D3, D4, D5, SW3, C12, R14, C13. SW_USER → SW3, R12, C12. VBAT_SENSE → R13, R14, C13. LED_BT → R10 only. LED_WIFI → R11 only. BATT → R13 only. PWR_LED_K / BT_LED_A / WIFI_LED_A are wire-end text on single wires, each joining one resistor to one LED.
2. Path A, power LED: +3V3 flag → R9 top; R9 bottom → wire down, right along a horizontal run, up a vertical stub to D3's right pin; D3's left pin → GND flag. Readable. However D3 is drawn with its arrow pointing left (anode on the right, cathode toward GND), yet the wire is labeled "PWR_LED_K" (K = cathode) — which end is the cathode I cannot tell with confidence from the symbol vs. the text. Path B, user button: +3V3 → R12 → SW_USER label; SW_USER label → SW3 → GND; SW_USER → C12 → GND. Three fragments stitched only by label; each fragment is unambiguous.
3. No crossings or near-touch wires anywhere. All wire-to-pin joins look clean. The only doubt is whether the resistor bottom pin of R9/R10/R11 actually lands on the corner of the horizontal wire (it appears to, at full resolution).
4. Overlaps: the net names "PWR_LED_K", "BT_LED_A", "WIFI_LED_A" sit directly against the corner of the wire they name, nearly touching the vertical stub — crowded but legible. D3/D4/D5 value text ("PWR_GREEN" etc.) sits above the GND flag rather than above the diode body, so the GND hexagon visually separates the label from its part. No text-on-text overlap.
5. It reads as a tidy but mechanical stacking of independent fragments in one column with the right 70% of the A3 sheet empty — orderly, not composed.
6. ACCEPT as readable: every wire and label can be followed and nothing is ambiguous electrically. Worst remaining issue: the LED anode/cathode orientation versus the "_K"/"_A" wire names is not self-evidently consistent (PWR_LED_K vs BT_LED_A on identically drawn circuits), which forces the reader to trust text over symbol.

## Corpus classification (officer) — R7

- All five (Reviews 7-11) are accepting-candidate evidence for the declared per-sheet scope, each with named residuals: power_rail (BATT pin-name/junction overprint at U1 14/16; IN/USB_DET shared dot above C3), battery (Q1 pin 4 to BATT/TP2 wire ambiguity; J2 pin 1/2 within a line-width), charge_enable (unattached ENPPB annotation label; SW1 pole/throw not legible), mcu_swd (SWDIO label under the RUN junction), io (LED anode/cathode vs `_K`/`_A` wire names).
- Three are ACCEPT (marginal): power_rail, battery, charge_enable. Two are ACCEPT: mcu_swd, io.
- Together with Review 6 (usbc, ACCEPT): 6/6 ACCEPT, 3 marginal.
- None is a calibrated status; none is a blanket accepting entry for every class; not human_approved; not electrical / fab / license acceptance. The S1 diagnostic findings of R7 (power_rail f x5, battery f x1, mcu_swd b2 x1) are recorded in receipt §R7.2 and are not adjudicated against these reviews here.

## Review 12 — io (hand-drafted r8) — reviewer ses_eeeb5a91bffeLqOf609CMIfduw — PNG 3a9bd795… — ACCEPT (communicates design intent)

Reviewer: independent task(general) session ses_eeeb5a91bffeLqOf609CMIfduw; PNG-only. The question asked was "what is this page designing?" (design INTENT), not "can you trace the wires". Review 11 was the engine r7 version of the same declared circuit (now in `.history/io_engine_r7.*`); Review 12 is the hand-drafted r8 version.
Subject: PNG sha256 3a9bd795d35257d352af96d678df7ebed18efa2e45f67dcb0100f5256addbe7e.

1. This page designs the "btdongle" product's user-facing I/O: three status indicator LEDs, one debounced user push-button, and a battery-voltage divider feeding the MCU's ADC.
2. Functional blocks: Status LEDs (sub-headed PWR / BT / WIFI): three LED + 1k series-resistor strings to GND. PWR is tied to +3V3 (lit whenever the rail is up); BT and WIFI are driven by MCU GPIOs. User button (debounced): SW3 pulls SW_USER to GND when pressed; R12 10k pull-up to +3V3; C12 100nF with R12 gives ~1 ms RC debounce. VBAT sense ÷ 2 → ADC0: R13/R14 100k/100k divider halves the battery voltage (4.2 V → 2.1 V), C13 100nF filters, output to MCU ADC.
3. Off-page signals: LED_BT "← mcu_swd U2.GPIO16 (pin 21)"; LED_WIFI "← mcu_swd U2.GPIO17 (pin 22)"; SW_USER "→ mcu_swd U2.GPIO18 (pin 24)"; BATT "← power_rail U1.BATT (pins 14, 16)"; VBAT_SENSE "→ mcu_swd U2.GPIO26_ADC0 (pin 31)"; +3V3 and GND power symbols only, no source stated (normal).
4. Things I'd question: Net PWR_LED_K sits on the LED anode (R9–D3 junction). The author admits this ("name says K, node is A"). I'd ask why it was kept rather than fixed — a knowingly wrong name on the sheet is a trap for the next reader. LED current with 1k from 3.3 V is ~1 mA for green/blue (Vf ≈ 2–3 V) — dim. Is that intentional? VBAT_SENSE tap after R13 is unprotected if the MCU is unpowered while BATT is present; worth a note or a series resistor. The SW_USER hierarchical label is drawn pointing out of the page but the arrow text says the signal goes "→ mcu_swd"; fine, but for LED_BT/LED_WIFI the labels are drawn as outputs while the text says "←" inputs — label direction and arrow glyph could be made to agree. "Pins 14, 16" for BATT is plausible but unverifiable from this page.
5. Overlap/crowding: none significant. Text is clear of wires. Right ~45% of the Status LEDs box and the lower-left of the button box are somewhat empty, but not objectionable. The title-block description text runs to the frame edge on the right.
6. ACCEPT — it communicates design intent clearly. The one thing I'd still change: rename PWR_LED_K to PWR_LED_A (or drop the label) instead of annotating around a known-misleading net name.

## Corpus classification (officer) — R8

- Review 12 is the first review that asked the INTENT question ("what is this page designing?") rather than traceability. Verdict ACCEPT (communicates design intent).
- It is a DIFFERENT review axis from Reviews 1–11 (traceability / readability) and is NOT comparable to them as calibration evidence.
- The engine r7 io (Review 11, traceability ACCEPT) and the hand r8 io (Review 12, intent ACCEPT) are the same declared circuit (24/24 pin→net identical; root 58/58 net partition identical). Record the pair as the first intent-vs-traceability contrast specimen.
- None is a calibrated status; not human_approved; not electrical / fab / license acceptance. The reviewer's engineering questions are carried as open items in receipt §R8.R, not resolved here.

## Review 13 — 00.overview-v1 (root system overview, r9) — reviewer ses_eee8dabadffep0mnzPoXNbGNJk — PNG 9644759c… — ACCEPT-marginal [00.overview-v1]

Reviewer: independent task(general) session ses_eee8dabadffep0mnzPoXNbGNJk; PNG-only, no intended conclusions given. Axis: system-overview intent review (protocol = the seven questions as dispatched: what the board does, blocks and pages, power/signal flows, wires-vs-diagram, visible choices/uncertainties, designer questions, verdict). Not traceability, not S1 calibration.
Subject: PNG sha256 9644759ccc0002edab61816f48f5140d73f08cb0f46713ca3c5bd506600423b7 (page 1 of 00.btdongle_ms-v3.pdf). Reviewer text verbatim below.

**Blind review — `00.overview-v1.png` (btdongle — System Overview, Rev r9, sheet 1/7)**

**1. What the board does (one sentence)**
A USB-C powered, single-cell Li-ion charged/battery-backed Raspberry Pi Pico 2 W "btdongle" with a charge-status LED, power switch, three status LEDs, a user button and a battery-voltage sense to the ADC.

**2. Blocks seen, claimed role, page pointed to**
- **01 usbc** (`usbc.kicad_sch`) — USB-C input: J1 receptacle, F1 500 mA polyfuse, C1 10 uF, R1/R2 5.1k on CC1/CC2, D1 ESD clamp. Out: VBUS (GND common). → page 01.
- **02 power_rail** (`power_rail.kicad_sch`) — ETA6003 charger + power path (U1), L1 2.2 uH, C2–C5, R3/R4 2k (ISET). In: VBUS. Out: SYS, BATT. Also NTC, STAT, ENPPB. → page 02.
- **03 battery** (`battery.kicad_sch`) — 1S Li-ion connector J2 (BAT_PH2.0), Q1 DMG2301L load switch, C6 100 nF, R5 10k on NTC, TP2 test point. Nets: BATT, NTC. → page 03.
- **04 charge_enable** (`charge_enable.kicad_sch`) — Charge LED D2 (CHG_AMBER) via R7 1k from STAT; PWR_SW SW1 (SPDT) wired to ENPPB, GND and BATT. → page 04.
- **05 mcu_swd** (`mcu_swd.kicad_sch`) — Raspberry Pi Pico 2 W module (U2), SWD header J3, RESET button SW2, R8 10k, C7–C11, TP1 (SYS). In: SYS. Out: +3V3, LED_BT, LED_WIFI. → page 05.
- **06 io** (`io.kicad_sch`) — Status LEDs D3–D5, 1k resistors, user button SW3 + R12/C12 debounce, VBAT divider R13/R14 + C13 to ADC. → page 06.
- Title block says "six sub-circuit sheets", and the sheet count "1/7" agrees (root + 6).

**3. Power path and signal flows as written on the arrows**
Power (thick dashed):
- `VBUS 01→02` : 01 usbc → 02 power_rail.
- `BATT 02↔03` : double-headed between 02 power_rail and 03 battery.
- `BATT 03→04` : 03 battery → 04 charge_enable.
- `SYS 02→05` : 02 power_rail → 05 mcu_swd.
- `BATT 03→06` : 03 battery → 06 io.
- `+3V3 05→06` : 05 mcu_swd → 06 io.
Text box "Power path" says: VBUS 5 V (01) → ETA6003 charger/power path (02) → SYS → Pico VSYS (05); BATT 1S Li-ion (03) through Q1 load switch; Pico 3V3 output feeds LEDs/pull-ups on 06; GND common to every sheet and not drawn.

Control/signal (thin dashed):
- `STAT 02→04` : 02 → 04 (routed over the top).
- `ENPPB 04→02` : 04 → 02 (routed over the top, arrowhead into top of 02).
- `NTC 03→02` : 03 → 02.
- `LED_BT 05→06`, `LED_WIFI 05→06` : 05 → 06.
- `SW_USER 06→05`, `VBAT_SENSE 06→05` : 06 → 05.
Text box "Interfaces": SWD via J3 on 05; user I/O (3 LEDs, button, VBAT sense) on 06; ENPPB (SW1) and STAT (D2) on 04; NTC on 03.

**4. Are arrows wires or something else? Legend text**
Yes, explicit. Legend (lower right): "Functional flow — not electrical connectivity"; "thick dashed = power net, thin dashed = signal net"; "Arrow labels: NET source page –> destination page (text reference only)." Title-block comment: "Hand-drafted (r9); the native sheet instances and paths are unchanged." and "Functional overview of the six sub-circuit sheets (diagram only; not electrical connectivity)."

**5. Visible choices / uncertainties**
- `BATT 02↔03` is the only double-headed arrow, and it conflicts with the text: block 02 says "Out: SYS, BATT", block 03 says BATT is its net, and the Power-path text says BATT goes "through the Q1 load switch". Which direction current flows (charger→cell vs cell→system) is not resolved on this page.
- `BATT 03→06` goes to 06 io, but 06's role line only mentions a VBAT divider to ADC — a sense tap, not a load. Drawing it as a thick power arrow overstates it; the net on 06 is shown as BATT, yet the signal back to 05 is `VBAT_SENSE`, so the BATT/VBAT naming boundary is unclear.
- `BATT 03→04`: 04's text says SW1 is wired to ENPPB, GND and BATT, so BATT is used as a pull level for the switch, not as a load — again drawn as thick power.
- `NTC 03→02` is drawn thin dashed with the arrow pointing at 02, but the line is faint and the arrowhead near 02 is small/ambiguous at this resolution.
- The STAT/ENPPB top routes run across the whole sheet and cross the 03 battery column; readable, but the ENPPB arrowhead lands at the top edge of 02 near the STAT origin, so the two paths visually touch near 02.
- Block 03 claims a "Q1 load switch" but no arrow is labelled as a switched output; the Power-path text's "BATT through Q1" is not reflected by any distinct net name on the diagram.
- Page 03/06 arrow `BATT 03→06` and page 02/05 arrow `SYS 02→05` descend from inside the block areas; fine, but the labels float mid-line without guide ticks.
- No clipped or overlapping text observed; all labels legible. No GND, no USB data (D+/D−) shown anywhere — USB-C block mentions only CC/VBUS/ESD, so whether the dongle has USB data is unknown from this page.

**6. Questions for the designer**
- What is the actual direction of BATT between 02 and 03 under charging vs discharging, and where does the Q1 load switch sit relative to SYS and BATT?
- Does the Pico VSYS get SYS only (from the ETA6003 power-path output), or can BATT reach VSYS another way?
- What drives the Q1 load switch (gate net name)? It appears on no arrow.
- Is USB data (D+/D−) connected to the Pico, or is USB-C power-only? Nothing on this page says.
- Is `BATT 03→06` only a sense tap for the VBAT divider? If so, why thick (power) rather than thin (signal)?
- Does ENPPB originate on 04 (SW1) and terminate at U1 on 02 only, or does the MCU also see it?
- Is the NTC thermistor physically on the battery pack (J2) or on-board R5 only?
- Is there any power-good/charge-complete signal to the MCU besides the STAT LED on 04?
- Why 7 sheets in the title block count "1/7" when exactly six sub-sheets are shown — is a seventh sheet hidden?

**7. Verdict**
**ACCEPT-marginal.** The page gives a readable global map (six sheets, file names, net names with page references, explicit "not electrical connectivity" legend, power vs signal distinction, prose power path). The single worst thing: the **`BATT 02↔03` double-headed arrow** — the central power net of the design has no stated direction and contradicts the "Out: BATT" / "through Q1 load switch" text, so the one thing a reader most needs from an overview (how the battery, charger and load switch relate) still has to be resolved by opening pages 02 and 03.

## Corpus classification (officer) — R9

- Review 13 is accepting-candidate evidence for the declared scope (00.overview-v1: hand-drafted, non-electrical system overview) with named residuals, verdict ACCEPT-marginal. Axis: system-overview intent review (seven-question protocol as dispatched); NOT traceability, NOT S1 calibration; not comparable to Reviews 1–11 as calibration evidence.
- Named residuals (reviewer's words, not resolved here): (i) the BATT 02↔03 double-headed arrow leaves charger / cell / Q1 direction unresolved — the single worst item; (ii) BATT 03→06 and BATT 03→04 are drawn as thick power arrows although 06 is a sense tap and 04 a switch pull level; (iii) the Q1 load-switch gate net appears on no arrow; (iv) USB D+/D− absence is not stated; (v) the NTC arrow is faint; (vi) the ENPPB/STAT top routes visually touch near 02.
- The reviewer's nine designer questions are carried as OPEN ITEMS in receipt §R9.R, owner = design authority (user); not resolved here.
- None is a calibrated status; not human_approved; not electrical / fab / license acceptance. The root netlist invariance (58 nets / 167 pins) proves connectivity invariance only, not overview correctness.

## Review 14 — 00.overview before/after (v1 → v2, r10 typography re-compose) — reviewer ses_eee6830c2ffe7xGc4gToL0lHEF — PNGs 9644759c… → bc699a5a… — IMPROVED [00.overview-v2]

Axis: typography/composition before-after review (not traceability, not intent, not S1 calibration). Reviewer: independent task(general) session ses_eee6830c2ffe7xGc4gToL0lHEF; PNG-only; verbatim from /home/pkcs12/.cache/scratch/task-ses_eee6830c2ffe7xGc4gToL0lHEF/review.md (Pair A).

1. Balance: before — content ~4% left margin, right 4% but boxes cramped; text inside boxes hugs left edge, right half of each box blank; bottom-left text tiny, right side blank apart from title block. After — boxes span 5%→95%, text fills boxes, left/right ~5% each; Power path/Interfaces column ends ~37% leaving centre gap.
2. Font: after readable without zoom, uniform across the six boxes and the two legend/notes blocks. Only title-block text remains small (expected).
3. Whitespace: after — large empty area centre-bottom (x≈37%→57%, y≈60%→93%) between notes and legend, and right column above title block (x≈57%→95%, y≈70%→78%). Still mostly filled vs before.
4. New defects: (a) ENPPB 04→02 arrow enters the top edge of box 02 and runs through "power_rail" sheet-name text; STAT 02→04 arrow passes through "charge_enable" sheet-name text at the box-04 top-right (letters struck through by dashed line) — before had these clear. (b) SW_USER 06→05 and VBAT_SENSE 06→05 arrows plus labels now sit below box 05/06 bottom edges, floating outside both boxes; VBAT_SENSE label almost touches "Functional flow" legend heading. (c) LED_BT/LED_WIFI/+3V3 arrows run right up to box-06 text edge.
5. Verdict: IMPROVED. Most important remaining issue: the two 06→05 return arrows (SW_USER, VBAT_SENSE) have fallen below the boxes they connect, and the ENPPB/STAT arrows overstrike the sheet-name labels.

## Review 15 — 06.io before/after (v2 → v3, r10 typography re-compose) — reviewer ses_eee6830c2ffe7xGc4gToL0lHEF — PNGs 3a9bd795… → 04942fe5… — IMPROVED [06.io-v3]

Axis: typography/composition before-after review (same reviewer session and source file as Review 14, Pair B).

1. Balance: before — Status LEDs group spans full width but each sub-circuit is thin with ~35% of its column blank right; User button group ends at x≈47%, VBAT group right edge matches; margins ~4% both sides but bottom 40% of User button box empty. After — groups span 5%→95%; left/right margins ~5% each, balanced.
2. Font: notes text in after readable without zoom; same size in all three groups (LED notes, button notes, VBAT notes, sheet-pin references). Symbol value/refdes labels (R9 1k, C12 100nF, D3 PWR_GREEN) and net labels remain KiCad-default small — visibly smaller than notes; stated out of scope but reads as two sizes on the page.
3. Whitespace: after — Status LEDs group right third of each column blank above notes; VBAT group has a gap x≈60%→65%; User button box fine. Overall ~70% utilisation.
4. New defects: (a) Status LEDs: "Status LEDs" heading and "PWR" sub-heading stacked with zero gap at top-left, PWR heading no longer aligned with BT/WIFI headings (which sit one line lower); PWR column lacks the sheet-pin reference line BT/WIFI have (consistent with before). (b) VBAT group: "← power_rail U1.BATT (pins 14, 16)" wraps to "16)" on a second line directly above the BATT label; "→ mcu_swd U2.GPIO26_ADC0 (pin 31)" wraps onto two lines and "(pin 31)" sits over the VBAT_SENSE wire area — crowded but not overlapping lines. (c) User button: "→ mcu_swd U2.GPIO18 (pin 24)" wraps with "24)" alone on the second line under the SW_USER label; the line runs under the SW_USER wire, close to touching. (d) Title-block text "Hand-drafted (r10 typography re-compose); electrically identical to the engine version of this sheet." now extends past the title-block right border and the page frame (clipped at "th|s sheet."). (e) User button group: the three note paragraphs now have uneven paragraph gaps vs Status LEDs notes (single block).
5. Verdict: IMPROVED. Most important remaining issue: title-block description line overruns the frame (clipped), and the wrapped sheet-pin references leave dangling fragments ("16)", "24)") next to net labels.

## Corpus classification (officer) — R10

- Reviews 14 and 15 are typography/composition before-after evidence for the r10 re-compose (00.overview v1→v2, 06.io v2→v3). Verdict on both pairs: IMPROVED (balance and font size confirmed fixed), with NEW defects introduced by the re-compose. Different axis from Reviews 1–13; not comparable to them; not calibration evidence; not an acceptance of v2/v3 as finished pages.
- Named new defects (reviewer words, addressed in the r10 fix round v3/v4, receipt §R10.1): overview — ENPPB/STAT arrows through sheet-name text, SW_USER/VBAT_SENSE arrows fallen below boxes 05/06, arrowheads at box-06 text edge, centre-bottom hole; io — title-block description overruns the frame, dangling wrapped fragments ("16)", "(pin 31)", "24)"), "Status LEDs"/"PWR" headings stacked and misaligned, uneven note paragraphs.
- Not recorded as resolved by this entry: whether the fix round v3/v4 actually fixed them (needs a new independent review; officer dispatches).

## Review 16 — 00.overview-v3 + 06.io-v4 (r10 fix round verification) — reviewer ses_eee5db110ffeh83xtuErNW6Ra9 — PNGs 945a7df1… (00 v3), 820d88c0… (06 v4) — 06 ACCEPT; 00 ACCEPT-marginal [00.overview-v3, 06.io-v4]

Axis: typography/composition verification (verification protocol as dispatched; not traceability, not intent, not S1 calibration). Reviewer: independent task(general) session ses_eee5db110ffeh83xtuErNW6Ra9; verbatim from /home/pkcs12/.cache/scratch/task-ses_eee5db110ffeh83xtuErNW6Ra9/review-notes.md. Item codes A1–A5 / B1–B6 refer to the Review 14/15 defect lists plus new items. Fuller officer paraphrase of A4/A5 (not reviewer verbatim): A4 blank strip bottom-left x≈70–1046 px, y≈925–1165 px ≈ 12% of drawing area; A5 title-block comment line 1 "Hand-drafted (r10, typography re-compose); the native sheet instances and paths are unchanged." overruns the title-block right border, "unchanged." cut, line 2 touches the border.

```
A1 FIXED | A2 FIXED | A3 FIXED | A4 partially fixed (hole moved to bottom-left strip ~13% page area) | A5 NEW: title-block comment line 1 crosses right border of title block / frame ("...are unchanged." ends past x≈1683 line)
B1 FIXED | B2 FIXED | B3 FIXED | B4 FIXED (marginal: SW_USER off-page note wrapped mid-group; description sentence-per-line) | B5 box text uniform; ref/value/net labels ~half size STILL PRESENT (rule 5) | B6 none found
A: readable yes, L/R ~5%/5%, ACCEPT-marginal (worst: title-block overflow)
B: readable yes (box text), L/R ~5%/5%, ACCEPT (worst: small KiCad ref/value/net labels)
```

## Corpus classification (officer) — R10.2

- 06.io-v4: accepting-candidate evidence for the declared scope (hand-drafted io sheet, typography/composition axis), verdict ACCEPT; B1–B4 and B6 FIXED; B5 (KiCad ref/value/net-label text about half the size of box text) is the rule-5 exclusion, carried, not a finding against v4. Not calibrated status; not human_approved; the Review 12 intent ACCEPT is for v2 and is separate.
- 00.overview-v3: ACCEPT-marginal, superseded by 00.overview-v4 (fix2: title-block comments shortened, notes stacked and rows spread) pending an independent re-check; A1–A3 FIXED, A4 partially, A5 new. v4 is NOT yet reviewed.

## Review 17 — 00.overview-v4 (r10 fix round 2 verification) — reviewer ses_eee58b995ffeF5B0tH8xT2QveL — PNG 1fb1a3da… — ACCEPT [00.overview-v4]

Axis: typography/composition verification (not traceability, not intent, not S1 calibration). Reviewer: independent task(general) session ses_eee58b995ffeF5B0tH8xT2QveL; one image, read-only; verbatim from read_subsession(mode=summary) terminal assistant text. Item codes A4/A5 refer to the Review 14/16 defect lists.

**Review — `00.overview-v4.png`** (read-only, one image)

**A5. Title-block comment overflow → FIXED.**
Looked at the title block, bottom-right (x≈1045–1685, y≈980–1165). The two comment lines read:
- "Hand-drafted overview; sheet instances unchanged."
- "Functional overview of six sheets (diagram only)."

Both end at roughly x≈1405, well inside the title-block right border (x≈1685) and the page frame. No comment line crosses or touches either border. The remaining fields (btdongle / Sheet: / / File: btdongle_ms.kicad_sch / Title: btdongle — System Overview / Size A4 / Date 2026-10-06 / Rev r10c / KiCad E.D.A. 9.0.9 / Id 1/7) are all contained.

**A4. Bottom third → FIXED.**
Bottom third (y≈760–1165) is occupied by: left column "Power path" note (y≈770–955) and "Interfaces" note (y≈985–1145) stacked down to just above the frame; centre "Functional flow — not electrical connectivity" legend with two arrow samples and arrow-label convention (y≈770–885); right the title block (y≈980–1165). The bottom-left blank strip between the notes and the title block is gone — "Interfaces" now runs to y≈1145, level with the title block bottom.
Remaining blank: a horizontal band under the legend, between the notes' right edge (x≈560) and the title block (x≈1045), from y≈890 to y≈1165 — roughly 6% of drawing area; plus thin gaps around the 05/06 row totalling another ~4%. Estimate ~10% blank total, largest contiguous ~6%.

**Regressions: none found.**
- Dashed arrows through text: STAT 02→04 and ENPPB 04→02 now run above the boxes (y≈120 and y≈160) and drop into 02 / 04 without crossing the "power_rail" / "charge_enable" sheet names. Vertical SYS 02→05 and BATT 03→06 arrows have their labels beside, not on, the lines.
- Arrow labels floating: VBUS / BATT / NTC / BATT labels sit inside the gaps between 01–02, 02–03, 03–04; the five 05↔06 labels (LED_BT, LED_WIFI, +3V3, SW_USER, VBAT_SENSE) sit in the gap between the 05 and 06 boxes, each above its own line. SW_USER 06→05 and VBAT_SENSE 06→05 return arrows now terminate inside the gap, not below the boxes.
- Text overlapping text: none seen; box titles, body text, "File:" lines, legend, and notes are all separated.

**Readable without zoom:** yes — box body text, arrow labels, notes and legend are all legible at native size; title-block comment lines are the smallest text but still readable.

**Left/right margins:** content spans x≈90 to x≈1670 of a 1760-wide image → ≈1% left, ≈1% right of width outside the frame; inside the frame, left column text starts ≈1.5% from the frame edge, box 04 ends ≈1% from the right frame edge. Balanced.

**Verdict: ACCEPT.**
Single worst remaining issue: the ~6% blank band centre-bottom, below the legend and between the notes column and the title block (x≈560–1045, y≈890–1165). Cosmetic only; no readability or correctness defect.

## Corpus classification (officer) — R10.3

- 00.overview-v4 (PNG 1fb1a3da…): accepting-candidate evidence for the declared scope (hand-drafted, non-electrical system overview), verdict ACCEPT, axis typography/composition verification. Supersedes the Review 16 ACCEPT-marginal of v3. A4 and A5 FIXED; no regressions found.
- Named residual (reviewer's words): ~6% blank band centre-bottom below the legend (x≈560–1045, y≈890–1165 px); cosmetic only.
- Not a calibrated status; not human_approved; not electrical / fab / license acceptance. Review 13 residuals (BATT 02<->03 direction etc.) are not addressed by Reviews 14-17 and remain open (owner = user).
