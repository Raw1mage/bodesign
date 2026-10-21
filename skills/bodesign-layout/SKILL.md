---
name: bodesign-layout
description: L2/L3 printed circuit board placement, routing, and DRC verification skill for Layout Specialist.
---

# Bodesign Layout

This skill guides printed circuit board placement, routing, and design rule verification.

## 1. Input Requirements

Before beginning board layout, verify that upstream electrical and mechanical inputs exist.

- Read the authoritative netlist and bill of materials from stage C03.
- Ingest board outline dimensions and mounting hole positions from 01_refs.
- Verify that frozen connector face assignments exist in Face_Layout.json.

## 2. Core Layout Workflow

Place components and route copper tracks according to manufacturing rules.

- Bind connectors to their frozen board faces deterministically.
- Place sensitive analog parts away from high-speed digital switching nodes.
- Route differential pairs with controlled impedance and matched lengths.
- Pour ground copper planes on internal and external reference layers.
- Apply half-plated castellated pads along module edges where specified.

## 3. Exit Gates

Verify board layout compliance before generating manufacturing packages.

- Run `bodesign_layout_drc_gate` to verify zero clearance violations and zero unrouted nets.
- Run `bodesign_si_check` to verify signal impedance on critical high-speed tracks.
- Ensure that copper pours satisfy thermal relief and minimum annular ring rules.
- Read `skills/bodesign/stages/c04-layout/GUIDE.md` for detailed layout rules.
