---
name: bodesign-ee
description: L2/L3 electrical schematic, BOM extraction, and netlist authoring skill for EE Designer.
---

# Bodesign EE

This skill guides the authoring of electrical schematics, component BOMs, and netlists.

## 1. Input Requirements

Before beginning electrical design, verify that upstream constraints exist.

- Read the product requirements specification from the upstream stage.
- Ingest interface constraints and connector pin definitions from 01_refs.
- Verify that power rails and current budgets match system targets.

## 2. Core Electrical Workflow

Author schematics and extract manufacturing netlists.

- Compose hierarchical schematics using standard functional blocks.
- Assign reference designators and footprint attributes to all components.
- Place decoupling capacitors on all integrated circuit power pins.
- Export the complete bill of materials using `bodesign_export_bom`.
- Generate the authoritative electrical netlist using `bodesign_export_netlist`.

## 3. Exit Gates

Verify schematic integrity before handing off to layout.

- Run the schematic analyzer to verify zero high-severity findings.
- Run `bodesign_prd_bom_crosscheck` to verify netlist fidelity against the BOM.
- Ensure that power pins connect to valid supply nets.
- Read `skills/bodesign/stages/c03-ee/GUIDE.md` for detailed stage requirements.
