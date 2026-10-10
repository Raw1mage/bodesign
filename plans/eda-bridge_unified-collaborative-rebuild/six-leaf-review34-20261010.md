# Review 34 — six-leaf v3 blind visual review (R-L 1(c), first pass)

Subject: experiments/s3-formal/c03_engine-v3 (manifest c4aa76dd…), rasters ~/.cache/scratch/s3-formal/v3-png/ (manifest dc9722a4…, cairosvg 2.9.0).
Method: one fresh-eyes `task(general)` session per leaf, full sheet + ≥2× crops, READ_OK required. All six READ_OK; no duplicate/contradictory results on any job.

| Leaf | Session | SIGN | Blocking findings | Cosmetic notes |
|---|---|---|---|---|
| usbc | ses_edc4816a5 | **no** | VBUS_CON / CC1 / CC2 (three nets) stacked collinearly on one x-column with ≤1-grid gaps — reads as VBUS–CC short at sheet scale | VBUS flag jammed onto F1 lower pin |
| power_rail | ses_edc47eb5d | yes-with-notes | — (U1 right-edge SYS/STAT flags outward, no pin-name overlap: round-2 fix confirmed) | adjacent flag outlines share an edge (accepted 2.54 mm class); BATT flag on wire above C5 not at pin; USB_DET/VBUS parallel 1 grid; pin-4 segment black in full raster (crop green: renderer artefact) |
| battery | ses_edc46a081 | yes-with-notes | — | Q1 value text clipped by body; BATT flag on Q1.3 stub overlapping wire; NTC flag left apex over R5 feed wire; BAT_EXT text flush to wire end |
| charge_enable | ses_edc467ba4 | yes-with-notes | — | CHG_LED_A text flush to wire corner; STAT flag on R7 pin with no stub; standalone ENPPB flag looks orphaned; R7→D2 U-route |
| mcu_swd | ses_edc47ca51 | yes-with-notes | — (SWCLK/SWDIO do not cross: round-1 fix confirmed) | SWDIO label flush against own vertical wire; design notes (VBUS NC, SWD pin order) not drawing defects |
| io | ses_edc46564a | yes-with-notes | — | PWR_LED_K/BT_LED_A/WIFI_LED_A labels flush to wire corner; PWR_LED_K vs *_LED_A naming consistency question; D4 loop black in raster (artefact); sheet 80% blank |

Ruling (officer):
1. usbc collinear multi-net column is an ENGINE routing defect not covered by S1 classes a–f (new shape: distinct nets collinear with sub-grid gaps). → round 3 repair; also an S1 calibration observation for the 求好 phase.
2. Label text flush to wire (4 leaves) and flag-on-wire / zero-stub flag (battery, charge_enable) are EMITTER placement defects → round 3.
3. Q1 value text clipped by body (battery) → emitter prop placement defect → round 3.
4. Renderer black/green segment artefact: cairosvg only; not a sheet defect. Record, do not fix.
5. Net naming (io), design notes (mcu_swd), U-route (charge_enable), blank page use: deferred to 求好.

Not measured: no re-review after round 3 yet; 1(c) is not closed until all six leaves reach SIGN yes or yes-with-notes with no blocking finding.
