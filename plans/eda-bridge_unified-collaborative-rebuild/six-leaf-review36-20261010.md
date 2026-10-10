# Review 36 — six-leaf v5 blind visual review (R-M acceptance pass)

Subject: experiments/s3-formal/c03_engine-v5 (manifest b3db0c26…, S54 cf35774), rasters ~/.cache/scratch/s3-formal/v5-png/ (manifest ae64c52c…, 36 PNG, cairosvg 2.9.0, S55 dfbe063).
Method: one fresh-eyes `task(general)` session per leaf, full sheet + ≥2× crops, READ_OK recorded per image before defects, Review 35 rows re-checked last, SVG source not consulted. All six READ_OK (36/36 images). No reviewer death, no duplicate/contradictory result on any job.
Per-leaf reports (scratch): ~/.cache/scratch/s3-formal/review36/<leaf>.md — sha256 usbc 7b40cbd3… / power_rail 90b6184f… / battery 1ec24e40… / charge_enable 3580faa5… / mcu_swd 1142f70d… / io 0a5a5a12….

| Leaf | Session | Images | SIGN | BLOCKING / NOTE | Review 35 items → v5 | NEW |
|---|---|---|---|---|---|---|
| usbc | ses_ed99478cc | 5/5 | yes-with-notes | 0 / 3 | VBUS_CON/CC1/CC2 stack → RESOLVED (holds); CC1–CC2 one-grid collinear → **RESOLVED** (item E, CC1 on own column x≈76); VBUS flag zero-stub on F1.2 → PERSISTS; VBUS/CC 1.27 mm offset → PERSISTS, reduced (disjoint y ranges) | none |
| power_rail | ses_ed99443eb | 12/12 | yes-with-notes | 0 / 5 | SYS/SYS + ENPPB/NTC abutting flags → PERSISTS; BATT flag at C5 → PERSISTS; USB_DET/VBUS parallel → PERSISTS; four-wire 2.54 mm corridor (~170 mm) → PERSISTS; SW_NODE label at junction dot → PERSISTS; seven class-e sites → accepted shape confirmed; pin-4 black segment → not reproduced | none |
| battery | ses_ed99416b7 | 5/5 | yes-with-notes | 0 / 5 | Q1 value clipped → RESOLVED; BATT@Q1.3 overlap → RESOLVED; NTC@R5 no-stub → PERSISTS; BAT_EXT flush (~0.6 mm to dot, no wire under text) → PERSISTS; J2.2 wire 1.2 mm above J2.3 GND flag → PERSISTS; standalone NTC port flag → PERSISTS | none |
| charge_enable | ses_ed9917057 | 4/4 | yes-with-notes | 0 / 8 | CHG_LED_A flush (≈0.9 mm, no wire under text) → PERSISTS; STAT zero-stub R7.1 → PERSISTS; standalone ENPPB → PERSISTS; R7→D2 U-route → PERSISTS | D2 GND flag zero-stub; SW1 pin flags zero-stub with pin numbers in ≈1.5 mm gap; D2 emission arrows ≈1 mm under GND flag; ≈85–90 % blank page |
| mcu_swd | ses_ed9914a5e | 6/6 | yes-with-notes | 0 / 7 | SWCLK flush → **RESOLVED** (leftward inline stub, text on axis); SWDIO flush → **RESOLVED** on own wire (upward stub, 0.9 mm clear); U2 symbol-internal AGND→GND line → PERSISTS (library); J3.2 corridor → PERSISTS, accepted; nested loops no crossing → clean | C5-1: SWDIO text 0.3 mm under the foreign SWCLK wire (nearer wrong net than own); C5-2: SWDIO/RUN stubs vertical with 0° text abutting the tip laterally — not aligned with the stub axis as the B-1 rule states |
| io | ses_ed9912f66 | 4/4 | yes-with-notes | 0 / 7 | three *_LED labels flush → PERSISTS (judged on full sheet; crops do not cover x≈45–55 mm); PWR_LED_K naming → PERSISTS; D4 black loop → PERSISTS as renderer artefact; 80 % blank → PERSISTS | superfluous junction dot at each two-way LED-return node (x≈55.7, y≈62/99/138) |

Totals: 36/36 READ_OK, 6/6 SIGN=yes-with-notes, **0 BLOCKING**, 35 NOTE.

## Ruling (officer)

1. **R-M done condition (§4.22 item 4) is met.** Review 36 reports 0 BLOCKING on all six leaves. Every Review 35 NOTE is either RESOLVED on v5 or named accepted below.
2. **RESOLVED by round 4**: usbc CC1–CC2 one-grid collinear (item E, threshold 3.81 mm); mcu_swd SWCLK and SWDIO own-wire flush (item A / B-1); earlier round-3 resolutions hold (usbc VBUS_CON stack, battery Q1 clip, BATT@Q1.3).
3. **Named accepted (class C, zero-stub flag on pin / flag at wire node)** — C-1 was dropped by the round-4 isolation gate (+B added 5× `F_WIRE_THROUGH_TEXT`, §15 of the repair receipt): usbc VBUS@F1.2; battery NTC@R5, J2.2 near J2.3 GND; charge_enable STAT@R7.1, D2 GND, SW1 pin flags; power_rail BATT@C5. Flags sit on the pin end with no wire under the outline; legible at crop scale.
4. **Named accepted (class B, label flush on a straight run, no wire under text)**: charge_enable CHG_LED_A; battery BAT_EXT; io ×3 *_LED; power_rail SW_NODE. B-1 is scoped to corner labels on point-to-point nets (§4.22 item 1); a straight-run offset rule (B-2) is a candidate for the next 求好 round, not R-M.
5. **Named accepted (R-M step-0 ruling D, unchanged)**: power_rail SYS/SYS + ENPPB/NTC abutting flag outlines; USB_DET/VBUS parallel; four-wire corridor, charge_enable U-route, io page occupancy and PWR_LED_K naming deferred to C03 graduation; mcu_swd U2 symbol-internal line (library symbol, not emitter); io D4 colour (cairosvg artefact); standalone ENPPB / NTC port flags (annotation-only ports).
6. **New items from Review 36, entered on the 求好 backlog (not R-M blockers)**:
   - mcu_swd C5-1 + C5-2 are one defect in the B-1 implementation, not two: the stub for SWDIO/RUN was taken along the *vertical* segment with KiCad 0° text, which (a) leaves text perpendicular to the stub, contrary to the ruling "text alignment follows the stub", and (b) placed SWDIO text 0.3 mm under the foreign SWCLK wire. Candidate rule B-1′: prefer the horizontal arm when both arms are free; when the stub is vertical, rotate text 90° so it lies on the stub axis. Engine/emitter only; no detector change.
   - io superfluous junction dots at two-way nodes (emitter: dot only when degree ≥ 3).
   - charge_enable SW1 pin flags squeeze pin numbers (zero-stub class, covered by item 3).
7. **Process defects recorded against the S55 raster packet**: io crop-1..3 (x=85–125 mm) and charge_enable crop-1/crop-3 carry `review35_ref` strings for items that lie outside their mm boxes (io *_LED flush at x≈45–55 mm; CHG_LED_A, standalone ENPPB). Reviewers fell back to the full sheet (4.76 px/mm) for those rows. Next raster dispatch: hard condition — a crop's box must contain the mm coordinate of every `review35_ref`/`review36_ref` it names, otherwise the manifest is rejected.
8. **SANDBOX-ASSUMPTION** (design content, btdongle sandbox, not a drawing defect): charge_enable D2 cathode→GND with anode fed via R7 from STAT — if STAT is open-drain active-low the LED is dark while charging. Recorded for the design owner alongside the SW1 SPDT note from Review 35.
9. **R-M CLOSED on v5.** Next direction is a user decision; options are recorded in freeze §4.23.

NOT MEASURED: ERC/netlist (electrical axis, covered by S54 receipt §15); S1 instrument counts (v3 all-zero / v2 [0,0,0,0,10,0], covered by S54/S55); renderer colour at sheet scale (known cairosvg artefact); crop-scale evidence for the io/charge_enable rows named in item 7.
