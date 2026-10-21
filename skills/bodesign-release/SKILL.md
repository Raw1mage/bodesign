---
name: bodesign-release
description: L2/L3 manufacturing package assembly, Gerber export, and fab release skill for Release Engineer.
---

# Bodesign Release

This skill guides manufacturing package assembly, artwork export, and fab release verification.

## 1. Input Requirements

Before creating manufacturing deliverables, verify that upstream layout is complete.

- Read the fully routed board file from stage C04.
- Ingest the approved bill of materials and component reference assignments.
- Verify that design rule verification passed with zero unresolved violations.

## 2. Core Manufacturing Workflow

Export artwork and assemble the complete fabrication package.

- Export copper, solder mask, silkscreen, paste, and board outline Gerber layers.
- Export Excellon drill files for plated and unplated holes.
- Export pick and place component centroid coordinates for assembly machines.
- Export the IPC-D-356 electrical test netlist for bare board testing.
- Assemble all fabrication assets into a zip archive with a release note.

## 3. Exit Gates

Verify fabrication deliverable completeness before sending to production.

- Run `bodesign_c04_gerber_gate` to verify that all required layers exist.
- Verify that the zip archive checksum matches the manufacturing package manifest.
- Ensure that the BOM format matches fabricator assembly requirements.
- Read `skills/bodesign/stages/c07-mfg/GUIDE.md` for detailed manufacturing criteria.
