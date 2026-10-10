# Review 35 — six-leaf v4 blind visual review (R-L 1(c), second pass)

Subject: experiments/s3-formal/c03_engine-v4 (manifest b3bdfe8b…, S48 c467211), rasters ~/.cache/scratch/s3-formal/v4-png/ (manifest dd9702ab…, cairosvg 2.9.0, S49 5ed6969).
Method: one fresh-eyes `task(general)` session per leaf, full sheet + ≥2× crops, step 1 written before Review 34 was opened, READ_OK required. All six READ_OK (34/34 images). power_rail first reviewer ses_edaf81112 died on daemon restart with no output and was redispatched once; no duplicate/contradictory results on any job.
Per-leaf reports (scratch): ~/.cache/scratch/s3-formal/review35/<leaf>.md — sha256 usbc a5aec1d1… / power_rail 047809f1… / battery f48b7bba… / charge_enable 81dc56a6… / mcu_swd 239fd2be… / io 31e97cf1….

| Leaf | Session | SIGN | Blocking findings | Review 34 items → v4 | Residual notes |
|---|---|---|---|---|---|
| usbc | ses_edaf8353c | yes-with-notes | — | VBUS_CON/CC1/CC2 collinear stack (Review 34 BLOCKING) → **RESOLVED**: VBUS_CON on its own column x≈68.6, no y-overlap with CC column x≈67.3; VBUS flag on F1.2 → PERSISTS | CC1–CC2 still collinear on x≈67.3 with one grid of white (sheet-scale pass-through misread possible, crop-scale unambiguous); VBUS/CC column offset only 1.27 mm |
| power_rail | ses_edaf15d2c | yes-with-notes | — (round-2 outward flags still hold) | adjacent flag edges (accepted class) → PERSISTS; BATT flag at C5 node → PERSISTS; USB_DET/VBUS parallel → PERSISTS; pin-4 black segment → not reproduced | four-wire 2.54 mm corridor down the left (~170 mm); SW_NODE label hugging tie wire; all seven class-e sites confirmed accepted shape |
| battery | ses_edaf7f39a | yes-with-notes | — | Q1 value clipped → **RESOLVED** (≈1 mm clearance); BATT flag on Q1.3 overlapping wire → **RESOLVED**; NTC flag apex on R5 feed → changed, cosmetic; BAT_EXT flush → PERSISTS | NTC wire ≈1.2 mm above J2.3 GND flag; standalone NTC port flag reads as floating without its annotation |
| charge_enable | ses_edaf4a2d6 | yes-with-notes | — | CHG_LED_A flush / STAT zero-stub / standalone ENPPB / R7→D2 U-route → all PERSISTS | design aside: SW1 SPDT with GND common ties BATT to GND in position 3 (design owner, not drawing) |
| mcu_swd | ses_edaf4805c | yes-with-notes | — (SWCLK/SWDIO nested loops, no crossing) | SWDIO flush → PERSISTS; design notes → unchanged | SWCLK label flush too; symbol-internal AGND→GND line inside U2 body passes 0.3 mm from pin-3 GND name; both J3.2 corridor sites accepted shape |
| io | ses_edaf30bb0 | yes-with-notes | — | three *_LED labels flush / PWR_LED_K naming / D4 black loop (artefact, crop green) / 80 % blank → all PERSISTS | — |

Ruling (officer):
1. **R-L 1(c) CLOSED.** Six leaves, six READ_OK, six SIGN=yes-with-notes, zero BLOCKING. The single Review 34 blocker (usbc VBUS–CC short reading) is resolved by round-3 item A; Q1 value clipping and Q1.3 flag overlap resolved by item D / round 2. The sheet set is reviewable as-is.
2. Persisting notes are all in the two classes dropped this round by isolation gate (B: label text flush to wire; C: zero-stub flag on pin / flag at wire node) plus deferred 求好 items (net naming, U-route, page use, four-wire corridor). They stay as the 求好 backlog; no round 4 under R-L.
3. New observations for the 求好 backlog: usbc CC1–CC2 one-grid collinear gap (same-axis foreign separation is exactly 2.54 mm — the invariant minimum; consider ≥ 5.08 mm or a track offset); power_rail adjacent flags abutting along one edge (SYS/SYS pins 1/15, ENPPB/NTC pins 8/7); mcu_swd U2 symbol-internal AGND→GND line (library symbol, not emitter); charge_enable SW1 SPDT common-to-GND (design content, SANDBOX-ASSUMPTION — not a drawing defect, record for the design owner).
4. Next: R-L 1(d) — final same-revision bundle on v4 bytes with `symbol_source` column so served check_c03 passes R3_DRAWABILITY.

NOT MEASURED: ERC/netlist (electrical axis, covered by S48 receipt); S1 instrument counts (frozen, covered by S48); renderer colour at sheet scale (known cairosvg artefact).
