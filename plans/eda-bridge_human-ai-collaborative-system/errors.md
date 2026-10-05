# Errors: eda-bridge_human-ai-collaborative-system

## Outcome Codomain

| Module | Value | Class | Means | Emitted at |
| ------ | ----- | ----- | ----- | ---------- |
| `motifs` | 0 | ok | Subcircuit motifs recognized and placed successfully | `motifs.py:synthesize_motifs` |
| `motifs` | 1 | failed | Degenerate motif definition (e.g. shorted divider) | `motifs.py:detect_motifs` |
| `motifs` | 2 | empty | Spec contains no matching subcircuit motifs | `motifs.py:detect_motifs` |
| `motifs` | -1 | not-run | Feature flag disabled by caller | `composer.py:pre_placement` |
| `motifs` | n/a (deterministic rules) | indeterminate | Rule set has no heuristic ambiguity | n/a (deterministic rules) |
| `kicad_sync` | 0 | ok | User changes detected and pinned successfully | `kicad_sync.py:diff_and_pin` |
| `kicad_sync` | 1 | failed | Corrupted .kicad_sch or .kicad_pcb S-expression | `kicad_sync.py:parse_kicad` |
| `kicad_sync` | 2 | empty | No human modifications detected (clean git working tree) | `kicad_sync.py:diff_and_pin` |
| `kicad_sync` | -1 | not-run | No previous AI baseline commit exists | `kicad_sync.py:check_baseline` |
| `kicad_sync` | n/a (exact diff) | indeterminate | AST diff is deterministic | n/a (exact diff) |

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `E_MOTIF_DEGENERATE_DIVIDER` | Top and bottom resistors connect to same node | `FidelityError: degenerate divider topology` | Fix input spec node definitions |
| `E_KICAD_SYNC_AST_CORRUPT` | KiCad file has mismatched parentheses | `ValueError: failed to parse KiCad S-expression` | Repair or regenerate KiCad schematic |
| `E_COLLINEAR_JOG_EXHAUSTED` | Wire cannot clear obstacles after channel detours | `Warning: downgraded to global label fallback` | Increase sheet spacing or add layout split |
