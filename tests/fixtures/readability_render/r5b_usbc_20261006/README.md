# r5b_usbc_20261006: byte-preserving copy of S3 run-r5b-s1-165624 (usbc)

Purpose: the one real subject that carries a sheet-level graphic (1 rectangle,
uuid 6fe52893-6baa-5a25-8e33-fdae41b26d87). Spec: s1-sheet-graphics-spec.md section 6.1.

Original paths (run directory ~/.cache/scratch/s3-elk-spike/run-r5b-s1-165624/):

| fixture file | original path | sha256 |
|---|---|---|
| usbc.kicad_sch | out/usbc.kicad_sch | 1a898ecc9158197e9d403b9a8fcc5886ba578aa86d303a8f463f38d17185856b |
| usbc.net | native/usbc.net | 188cc95ccbe36242878750ef6f2637b45c02485e2cb9b724f2eb19f9fbb993f2 |
| usbc.svg | native/svg/usbc.svg | 54fca7ad2508d686f15d0cdb7a455181c65fc3096a8b031dceea29510009f10b |
| usbc.export-receipt.json | native/usbc.export-receipt.json | 3619b26b92ad60bc9996c4a565c51ce748f4dba7f3297b1d8df9dbe408a41bc6 |

Nothing was regenerated; files were copied with `cp -p`. The path mapping above is
explicit and is NOT a new export receipt: `usbc.export-receipt.json` is the original
receipt written by the run (schema s1-export-receipt-v1, kicad 9.0.9), whose commands
still name the original relative paths.

Pairing re-check at copy time (2026-10-06): the receipt binds sheet 1a898ecc..., netlist
188cc95c... and render 54fca7ad...; all three match the bytes on disk. mtimes: sheet
16:56:26, netlist and svg 16:56:30 (sheet before exports). The CP3 stale-netlist caveat
does not apply to this run. kicad-cli was NOT re-run.

Restriction: internal review use only; not cleared for redistribution or global
promotion. D1 here is Power_Protection:PESD5V0L4UF (not the Bodesign_Presentation
library), so only this general internal-use caveat applies.

The sheet-level rectangle's uuid also appears in S3 receipt line 333 against a different
run's D1; that provenance is unreconciled and belongs to the S3 owner. Owner-rule AC5
for this subject is therefore UNRESOLVED PENDING S3 RECONCILIATION (see receipt s13).
