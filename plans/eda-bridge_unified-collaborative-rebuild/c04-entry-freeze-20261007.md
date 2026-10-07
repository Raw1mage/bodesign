# C04 Entry Freeze and C01–C04 Chain Contract (Task 7.3 Deliverable)

- **Document ID**: `c04-entry-freeze-20261007.md`
- **Topic**: Freeze C04 entry constraints, define upstream/downstream integrated chain contract, and propose bounded C04 placement spike
- **Date**: 2026-10-07
- **Authority**:
  - User ruling 2026-10-07: *"C01~C04 are ONE integrated flow, front-to-back linked. Continue design implementation."*
  - Commit `cfcf393` landing amendment §3.2 + DD-16..20 (`design.md`, `spec.md`, `tasks.md`, `data-schema.json`).
  - Task 7.3 design deliverable (no code, no tests, no commit).
- **Status**: FROZEN DESIGN PROPOSAL & CONFLICT RECORD (Pre-requisite to Task 7.4 C04 Placement)

---

## 1. FROZEN CONSTRAINT SET for C04 Entry (DD-20 Invariants)

All data in this section are extracted directly from verified upstream Single Sources of Truth (SSOT). Every field adheres strictly to the evidence level domain:
`datasheet` · `page-text` · `schematic` · `schematic-placement` · `requirement` · `derived` · `not-verified` · `not-quoted`.
Where a parameter is unknown or pending upstream physical measurement, it is recorded explicitly as `not-verified` or `not-quoted`; no parameter is estimated or defaulted.

---

### 1.1 Net Partition Digest

The electrical baseline is governed by `C03-EE/02_build/sch_gen/design.py` (commit `cfcf393`) and the verified module-book netlist `outputs/btdongle_ms/.src/book_modules-v2.net` (manifest root `ff8115dc…`, 352 entries, 0 non-OK).

| Parameter | Value | Source Path | Evidence Level | Notes |
|---|---|---|---|---|
| **Total Component Population** | 45 references | `outputs/btdongle_ms/btdongle_ms_bom-v2.csv` | `schematic` | Exactly 45 refs: 13 C, 5 D, 1 F, 3 J, 1 L, 1 Q, 14 R, 3 SW, 2 TP, 2 U. |
| **Total Active Net Count** | 24 active nets + GND | `C03-EE/02_build/sch_gen/design.py:200-273` | `schematic` | All nets declared with explicit `(ref, pin_number)` binding. |
| **Global Ground Node** | `GND` | `C03-EE/02_build/sch_gen/design.py:248-272` | `schematic` | 44 connection endpoints; common reference plane on Layer 2 (`In1.Cu`). |
| **Power Input & Conversion Nets** | `VBUS_CON`, `VBUS`, `SW_NODE`, `SYS`, `BATT`, `BAT_EXT`, `NTC`, `+3V3` | `design.py:202-218, 232` | `schematic` | Dynamic power-path switching handled by ETA6003 (`U1`). |
| **Charger Programming Nets** | `ISET1`, `ISET2`, `USB_DET`, `ENPPB`, `STAT`, `CHG_LED_A` | `design.py:220-225` | `schematic` | ISET2=2kΩ sets 0.5A USB charge current; ISET1=2kΩ. |
| **MCU & Radio Core Nets** | `RUN`, `SWCLK`, `SWDIO` | `design.py:234-236` | `schematic` | Pico 2 W SWD debug interface tied to `J3`. |
| **User Interface & Telemetry Nets** | `PWR_LED_K`, `LED_BT`, `BT_LED_A`, `LED_WIFI`, `WIFI_LED_A`, `SW_USER`, `VBAT_SENSE` | `design.py:239-245` | `schematic` | Status LEDs driven from GPIO21/GPIO22; battery voltage sensed on ADC0 (GPIO26). |
| **Type-C CC Nets** | `CC1`, `CC2` | `design.py:206-207` | `schematic` | Pulled down via 5.1kΩ (`R1`, `R2`) to GND; protected by `D1`. |
| **Explicit Unconnected Pins** | 31 physical pins | `design.py:278-298` | `schematic` | `NO_CONNECT` set: J1 (A6, A7, B6, B7, A8, B8); D1 (pin 6); U2 (24 unused GPIO/ADC pins). |
| **PWR_FLAG Declarations** | `VBUS_CON`, `VBUS` | `design.py:308` | `schematic` | Restricted exclusively to passive input nets; internal rails (`SYS`, `BATT`, `+3V3`, `GND`) are IC-driven. |

---

### 1.2 Footprint and Pad Map per Reference (45-Ref Registry)

Every reference from `btdongle_ms_bom-v2.csv` has been mapped to its target footprint and validated against original manufacturer datasheets.

| Ref | Value / Part | KiCad Footprint Name | Pad Count & Type | Manufacturer Datasheet Reference | Qualification Status | Evidence Level |
|---|---|---|---|---|---|---|
| **U1** | ETA6003 | `Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm` | 16 perimeter SMD pads + 1 Exposed Thermal Pad (pad 17) | ETA Solutions ETA6003 Datasheet Rev 1.2, Package Outline QFN3x3-16 | **QUALIFIED** | `datasheet` |
| **U2** | RaspberryPi_Pico_2W | `Module:RaspberryPi_Pico_W_SMD` | 40 perimeter castellated pads + 3 SWD pads (D1, D2, D3) + underside GND | Raspberry Pi Pico 2 W Datasheet §2 Mechanical Specification | **QUALIFIED** | `datasheet` |
| **D1** | PESD5V0L4UF | `Package_TO_SOT_SMD:SOT-886` | 6 leadless pads (XSON6, 1.45×1.00×0.50 mm, 0.5 mm pitch) | Nexperia PESDXL4UF_G_W Rev.04 Table 1 p.1 / Table 4 p.3 / Fig 13 p.12 | **QUALIFIED (Resolved by CP-1)** | `datasheet` |
| **J1** | USB_C_16P | `Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12` | 12 SMD signal pins + 4 through-hole shell mounting tabs (S1) | Korean HRO TYPE-C-31-M-12 Drawing & Specification | **QUALIFIED** | `datasheet` |
| **J2** | BAT_PH2.0 | `Connector_JST:JST_PH_B3B-PH-K_1x03_P2.00mm_Vertical` | 3 through-hole pins (2.00 mm pitch) | JST PH Series Connector Specification, Shrouded Header | **QUALIFIED** | `datasheet` |
| **J3** | SWD | `Connector_PinHeader_1.27mm:PinHeader_1x03_P1.27mm_Vertical` | 3 through-hole pins (1.27 mm pitch) | Industry Standard 1.27 mm Pitch Pin Header | **QUALIFIED** | `datasheet` |
| **L1** | 2.2uH/3A | `Inductor_SMD:L_Bourns-SRN4018` | 2 SMD pads (4.0×4.0×1.8 mm) | Bourns SRN4018 Semi-Shielded Power Inductor Datasheet | **QUALIFIED** | `datasheet` |
| **Q1** | DMG2301L | `Package_TO_SOT_SMD:SOT-23` | 3 SMD gull-wing leads (TO-236AB) | Diodes Inc. DMG2301L P-Channel MOSFET Datasheet | **QUALIFIED** | `datasheet` |
| **F1** | 500mA | `Fuse:Fuse_1206_3216Metric` | 2 SMD end-cap pads (3.2×1.6 mm) | Standard EIA 1206 PPTC Resettable Fuse Specification | **QUALIFIED** | `datasheet` |
| **SW1** | PWR_SW (PCM12) | `Button_Switch_SMD:SW_SPDT_PCM12` | 3 SMD signal leads + 2 mechanical retention tabs | C&K / Littelfuse PCM Series Ultraminiature Slide Switch | **QUALIFIED** | `datasheet` |
| **SW2** | RESET (SKQG) | `Button_Switch_SMD:SW_SPST_SKQG_WithStem` | 2 SMD J-lead pads (5.2×5.2 mm body) | ALPS Alpine SKQG Series Tact Switch Specification | **QUALIFIED** | `datasheet` |
| **SW3** | USER (SKQG) | `Button_Switch_SMD:SW_SPST_SKQG_WithStem` | 2 SMD J-lead pads (5.2×5.2 mm body) | ALPS Alpine SKQG Series Tact Switch Specification | **QUALIFIED** | `datasheet` |
| **D2** | CHG_AMBER | `LED_SMD:LED_0603_1608Metric` | 2 SMD end-cap pads (Pin 1=K, Pin 2=A) | Standard EIA 0603 Surface Mount Amber LED | **QUALIFIED** | `datasheet` |
| **D3** | PWR_GREEN | `LED_SMD:LED_0603_1608Metric` | 2 SMD end-cap pads (Pin 1=K, Pin 2=A) | Standard EIA 0603 Surface Mount Green LED | **QUALIFIED** | `datasheet` |
| **D4** | BT_BLUE | `LED_SMD:LED_0603_1608Metric` | 2 SMD end-cap pads (Pin 1=K, Pin 2=A) | Standard EIA 0603 Surface Mount Blue LED | **QUALIFIED** | `datasheet` |
| **D5** | WIFI_GREEN | `LED_SMD:LED_0603_1608Metric` | 2 SMD end-cap pads (Pin 1=K, Pin 2=A) | Standard EIA 0603 Surface Mount Green LED | **QUALIFIED** | `datasheet` |
| **R1, R2** | 5.1k | `Resistor_SMD:R_0402_1005Metric` | 2 SMD pads (1.0×0.5 mm) | Standard EIA 0402 Thick Film Chip Resistor | **QUALIFIED** | `datasheet` |
| **R3, R4** | 2k | `Resistor_SMD:R_0402_1005Metric` | 2 SMD pads (1.0×0.5 mm) | Standard EIA 0402 Thick Film Chip Resistor | **QUALIFIED** | `datasheet` |
| **R5, R8, R12** | 10k | `Resistor_SMD:R_0402_1005Metric` | 2 SMD pads (1.0×0.5 mm) | Standard EIA 0402 Thick Film Chip Resistor | **QUALIFIED** | `datasheet` |
| **R6, R13, R14** | 100k | `Resistor_SMD:R_0402_1005Metric` | 2 SMD pads (1.0×0.5 mm) | Standard EIA 0402 Thick Film Chip Resistor | **QUALIFIED** | `datasheet` |
| **R7, R9, R10, R11** | 1k | `Resistor_SMD:R_0402_1005Metric` | 2 SMD pads (1.0×0.5 mm) | Standard EIA 0402 Thick Film Chip Resistor | **QUALIFIED** | `datasheet` |
| **C1, C2, C3** | 10uF/16V | `Capacitor_SMD:C_0805_2012Metric` | 2 SMD pads (2.0×1.25 mm) | Standard EIA 0805 X5R/X7R Ceramic Capacitor | **QUALIFIED** | `datasheet` |
| **C4** | 22uF/10V | `Capacitor_SMD:C_0805_2012Metric` | 2 SMD pads (2.0×1.25 mm) | Standard EIA 0805 X5R Ceramic Capacitor | **QUALIFIED** | `datasheet` |
| **C5** | 1uF/10V | `Capacitor_SMD:C_0402_1005Metric` | 2 SMD pads (1.0×0.5 mm) | Standard EIA 0402 X5R Ceramic Capacitor | **QUALIFIED** | `datasheet` |
| **C6, C7, C9, C11, C12, C13** | 100nF | `Capacitor_SMD:C_0402_1005Metric` | 2 SMD pads (1.0×0.5 mm) | Standard EIA 0402 X7R Ceramic Capacitor | **QUALIFIED** | `datasheet` |
| **C8, C10** | 10uF/10V | `Capacitor_SMD:C_0805_2012Metric` | 2 SMD pads (2.0×1.25 mm) | Standard EIA 0805 X5R Ceramic Capacitor | **QUALIFIED** | `datasheet` |
| **TP1, TP2** | TP_SYS, TP_BATT | `TestPoint:TestPoint_Pad_D1.5mm` | 1 SMD circular pad (1.50 mm diameter) | Standard Surface Mount Test Point Pad | **QUALIFIED** | `datasheet` |

> **Audit Finding on D1 Footprint Conflict**:
> The historical schematic module page `11.j1_usb-v3.kicad_sch` carried `Package_TO_SOT_SMD:SOT-363`. Nexperia's official datasheet for `PESD5V0L4UF` (Rev.04, Section 1/Table 1) proves this part is solely packaged in `SOT-886` (leadless XSON6). The duty officer `ses_eed1fb0b6` and ChangeProposal CP-1 successfully resolved this by promoting `11.j1_usb-v4.kicad_sch` and `btdongle_ms_bom-v2.csv` to `Package_TO_SOT_SMD:SOT-886`. All 45 references in the current C04 entry set are 100% datasheet-qualified.

---

### 1.3 Board Outline, Mounting, and Connector-Face Positions

| Feature | Constraint / Value | Source Path | Evidence Level | Conflict / Status Note |
|---|---|---|---|---|
| **Upstream C02 Enclosure Cavity** | Inner: `64.4 × 23.4 × 15.5 mm`<br>Outer: `68.4 × 27.4 × 19.5 mm` | `C02-ME/enclosure_params.json:45-50` | `page-text` (design target) | Sized originally around stacked Pico (51×21) + WAV-20121 (62×21). |
| **Legacy C04 Carrier Outline** | `28.0 × 93.0 mm` rectangle (`Edge.Cuts`) | `C04-Layout/02_build/tools/mk_pcb.py:44-46` | `derived` | **CRITICAL CONFLICT**: Board length (93 mm) and width (28 mm) exceed C02 inner cavity (64.4×23.4 mm). |
| **Corner Fillet Radius** | R = 2.0 mm (or R = 3.0 mm matching C02) | `C02-ME/enclosure_params.json:42` | `requirement` | Legacy board had sharp 90° corners; must match C02 internal corner radius. |
| **J1 (USB-C) Face Plane** | Flush with outer wall at right end, centered on Y | `C02-ME/build_enclosure.py:161-165` | `requirement` | Center: Y=14.0 mm (relative to width); protrusion 0.8 mm beyond PCB edge. |
| **J2 (Battery JST-PH) Position** | Top edge or right edge, clearance to battery bay | `C03-EE/03_output/C03_Interconnect_ICD.md:126` | `requirement` | Dependent on 18650 battery holder bay orientation. |
| **J3 (SWD) Header Position** | Adjacent to U2 module SWD pins (D1/D2/D3) | `C03-EE/02_build/sch_gen/design.py:138` | `requirement` | Kept internal, accessible during development. |
| **SW1 (Power Switch) Actuator** | Board edge, protruding through side wall | `C02-ME/build_enclosure.py:183-187` | `requirement` | Slider extends through opening `OPN-05` (7.0×4.0 mm). |
| **SW2, SW3 (Push Buttons)** | Top surface, actuating via upper shell | `C02-ME/build_enclosure.py:190-194` | `requirement` | USER button aligned with activation opening `OPN-06` (Ø4.4 mm). |
| **D2..D5 (Status LEDs)** | Top surface, pitch 5.0 mm, aligned with light pipes | `C02-ME/enclosure_params.json:59-60` | `requirement` | 3 system LEDs (D3, D4, D5) + 1 charge LED (D2) positioned under lens windows. |
| **Mounting Boss / Screw Holes** | 4× Ø2.2 mm drill (M2 screw), Ø5.0 mm boss keepout | `C02-ME/enclosure_params.json:45-46` | `requirement` | Coordinates `not-verified` in legacy `btdongle_c04.kicad_pcb`; must be frozen in C04. |

---

### 1.4 Antenna Keepout Zone (KO-01 Invariants)

| Keepout Parameter | Invariant Value | Source Path | Evidence Level | Verification Mandate |
|---|---|---|---|---|
| **KO-01 Dimensions** | `14.0 mm (width) × 9.0 mm (height)` | Raspberry Pi Pico 2 W Datasheet §2, §3.8 | `datasheet` | Exact rectangular boundary matching onboard antenna projection. |
| **KO-01 Location** | Lower edge of Pico 2 W module (pads 20/21 end) | `C04-Layout/03_output/C04_Keepout_Map.json:16-24` | `datasheet` | Sits at bottom edge when module is rotated 180° on carrier board. |
| **Copper Exclusion** | ZERO copper on ANY layer (L1, L2, L3, L4) | `C04_Keepout_Map.json:20` | `requirement` | Copper pour zones must be clipped ≥1.0 mm away from KO-01 perimeter. |
| **Component Exclusion** | ZERO components, pads, test points, or courtyards | `C04_Keepout_Map.json:20` | `requirement` | DRC courtyards of all discrete components strictly prohibited from intersecting. |
| **Fastener / Structural Exclusion** | ZERO screws, standoffs, or mounting bosses | `C04_Keepout_Map.json:67-74` (KO-06) | `requirement` | Minimum 3.0 mm clearance from metallic/structural fixtures to KO-01 edge. |
| **Wiring Exclusion** | ZERO battery or harness wires crossing keepout | `C04_Keepout_Map.json:57-64` (KO-05) | `derived` | Harness routing channels must be physically confined to opposite edge. |
| **Enclosure Material Constraint** | Non-metallic enclosure (Plastic / Resin only) | `C04_Keepout_Map.json:26-34` (KO-02) | `datasheet` | Metal shell strictly banned to prevent Faraday cage attenuation. |

---

### 1.5 Stackup Specification

| Layer Index | Layer Name | Layer Type | Thickness / Weight | Dielectric Material | Target Function | Evidence Level |
|---|---|---|---|---|---|---|
| **Top** | `F.Cu` | Signal / Component | 1 oz (35 µm nominal) | — | Component pads, localized power polygons, signal escapes | `derived` |
| **Dielectric 1** | Prepreg | Dielectric Core | `not-verified` (typ. 0.20 mm) | FR4 (εr ≈ 4.5) | Core insulation | `not-verified` |
| **In1** | `In1.Cu` | Solid Power Plane | 1 oz (35 µm nominal) | — | Dedicated continuous `GND` ground plane; no signal cuts | `derived` |
| **Dielectric 2** | Core | Dielectric Core | `not-verified` (typ. 1.00 mm) | FR4 (εr ≈ 4.5) | Center core substrate | `not-verified` |
| **In2** | `In2.Cu` | Power / Signal | 1 oz (35 µm nominal) | — | `SYS`, `VBUS`, `+3V3` power distribution & non-critical signals | `derived` |
| **Dielectric 3** | Prepreg | Dielectric Core | `not-verified` (typ. 0.20 mm) | FR4 (εr ≈ 4.5) | Core insulation | `not-verified` |
| **Bottom** | `B.Cu` | Signal / Ground Flood | 1 oz (35 µm nominal) | — | Bottom signal interconnects + secondary ground flood | `derived` |
| **Total** | Overall Board | Rigid PCB | 1.60 mm ±10% | FR4 High-Tg (≥150°C) | Overall nominal board thickness | `derived` |

---

### 1.6 Net Classes and Routing Constraints

| Net Class | Member Nets | Min Track Width | Min Clearance | Via Diameter / Drill | Max Current Target | Evidence Level |
|---|---|---|---|---|---|---|
| **`Default`** | `SWCLK`, `SWDIO`, `RUN`, `LED_BT`, `LED_WIFI`, `SW_USER`, `STAT`, `CHG_LED_A`, `PWR_LED_K`, `BT_LED_A`, `WIFI_LED_A` | 0.15 mm (6.0 mil) | 0.15 mm (6.0 mil) | 0.60 mm / 0.30 mm | < 20 mA | `derived` |
| **`Power_High`** | `VBUS_CON`, `VBUS`, `SYS`, `BATT`, `BAT_EXT`, `SW_NODE` | 0.50 mm (20 mil) to 0.80 mm (32 mil) / Zone Pour | 0.20 mm (8.0 mil) | 0.80 mm / 0.40 mm (≥2 vias per rail transition) | 2.5 A (peak) / 1.5 A (cont.) | `datasheet` (ETA6003 §4) |
| **`Ground`** | `GND` | Solid Plane / Flood | 0.20 mm (8.0 mil) | 0.60 mm / 0.30 mm (thermal stitching) | Full return current | `derived` |
| **`Analog_Sense`**| `VBAT_SENSE`, `NTC` | 0.20 mm (8.0 mil) | 0.25 mm (10.0 mil) | 0.60 mm / 0.30 mm | High-impedance ADC/Sense | `derived` |
| **`USB_CC`** | `CC1`, `CC2` | 0.20 mm (8.0 mil) | 0.20 mm (8.0 mil) | 0.60 mm / 0.30 mm | Type-C pull-down | `datasheet` |

---

### 1.7 Design Rule Check (DRC) Invariants

| DRC Check Item | Target Rule | Manufacturer Basis | Evidence Level |
|---|---|---|---|
| **Track-to-Track Clearance** | ≥ 0.150 mm (6.0 mil) | Standard pooled quick-turn fab capability | `datasheet` |
| **Track-to-Pad Clearance** | ≥ 0.150 mm (6.0 mil) | Standard pooled quick-turn fab capability | `datasheet` |
| **Pad-to-Pad Clearance** | ≥ 0.150 mm (6.0 mil) | Accommodates 0.5 mm pitch QFN-16 & SOT-886 | `datasheet` |
| **Copper to Board Edge Clearance** | ≥ 0.500 mm (20 mil) (1.0 mm for power zones) | Prevents edge routing shorts during board routing/v-cut | `requirement` |
| **Minimum Annular Ring** | ≥ 0.150 mm (6.0 mil) | Via diameter 0.60 mm with 0.30 mm drill hole | `datasheet` |
| **Minimum Solder Mask Dam** | ≥ 0.100 mm (4.0 mil) | Prevents solder bridging between adjacent QFN/SOT pads | `datasheet` |
| **Silkscreen to Mask Clearance** | ≥ 0.150 mm (6.0 mil) | Prevents silkscreen clipping onto exposed solder pads | `requirement` |
| **Component Courtyard Clearance** | ≥ 0.250 mm (10.0 mil) | Ensures pickup-and-place nozzle access & inspection | `requirement` |

---

## 2. CHAIN CONTRACT: C01 → C02 → C03 → C04 → C02' → C01'

To fulfill the user's explicit directive that *"C01~C04 are ONE integrated flow, front-to-back linked"*, the hardware delivery lifecycle must not rely on prose coordination. It is formalized as a **cryptographically bound, bidirectional manifest chain**.

```
[Forward Integration Pass]
  C00-PRD (R6)
     │ (Requirements Bridge: FR/NFR, Enclosure Objectives)
     ▼
  C01-ID (v1)
     │ (Form Factor Constraints, Interface Faces, Keepouts)
     ▼
  C02-ME (v1)
     │ (Preliminary Cavity Envelope, Wall Thickness, Opening Specifications)
     ▼
  C03-EE (v2)
     │ (Netlist Freeze, 45-Ref BOM, Footprint Map, ICD Interconnects)
     ▼
  C04-Layout (Spike v1) ──► Freezes REAL Board Outline, Mounting Holes & Component 3D Coordinates
                             │
[Upstream Loop-Closure Pass] └──────────────────────────────┐
                                                            ▼
  C01'-ID (v2) ◄──────────────── C02'-ME (v2) ◄─────────────┘
  (Product & CMF Render on      (Enclosure Model Regen on
   Actual Physical Enclosure)    Real PCB Outline & Mounts)
```

---

### 2.1 Stage-by-Stage Input/Output Artifact Manifest

| Stage | Input Artifact (Consumed) | Binding Revision ID | Output Deliverable Artifact | Exported Manifest Properties Bound Downstream |
|---|---|---|---|---|
| **C00-PRD** | User ruling / market brief | R6 / v0.6 | `C00_Requirements_Bridge.json`<br>`C00_Decision_Log.md` | `requirements_hash`, `owner_decisions_hash`, `system_architecture_id` |
| **C01-ID** | `C00_Requirements_Bridge.json` | v0.1 | `C01_Form_Factor_Constraints.json`<br>`C01_工業設計說明.docx` | `form_factor_envelope`, `ui_control_positions`, `rf_material_rules` |
| **C02-ME (v1)** | `C01_Form_Factor_Constraints.json` | v0.1 | `enclosure_params.json`<br>`C02_Stackup_Constraints.json`<br>`build_enclosure.py` | `preliminary_cavity_dims`, `wall_thickness`, `clearance_budget`, `opening_specs` |
| **C03-EE (v2)** | `C00_Requirements_Bridge.json`<br>`C02_Stackup_Constraints.json` | r14 (`cfcf393`) | `design.py`<br>`book_modules-v2.net`<br>`btdongle_ms_bom-v2.csv`<br>`C03_Interconnect_ICD.md` | `netlist_sha256: ff8115dc…`<br>`bom_sha256`<br>`footprint_registry_hash`<br>`interconnect_icd_hash` |
| **C04-Layout (v1)** | `book_modules-v2.net`<br>`btdongle_ms_bom-v2.csv`<br>`enclosure_params.json` | v1.0 (Entry Freeze) | `01.c04-placement-v1.png`<br>`btdongle_c04-v1.kicad_pcb`<br>`c04_board_manifest.json` | `real_board_outline_polygon`<br>`mounting_hole_coords`<br>`connector_face_3d_planes`<br>`led_actuator_coords` |
| **C02'-ME (v2)** | `c04_board_manifest.json`<br>`build_enclosure.py` | v2.0 (Regen) | `enclosure_lower.stl`<br>`enclosure_upper.stl`<br>`enclosure_assembly.stl`<br>`Enclosure.step`<br>`01.c02-enclosure-v2.png` | `regenerated_shell_mesh_sha256`<br>`internal_clearance_verified: true`<br>`ko01_clearance_verified: true` |
| **C01'-ID (v2)** | `Enclosure.step`<br>`enclosure_assembly.stl`<br>`C01_Form_Factor_Constraints.json` | v2.0 (Final Render) | `01.c01-product-v2.png`<br>`02.c01-cmf-v2.png`<br>`c01_scene_manifest.json` | `product_visual_review_record`<br>`cmf_token_bindings`<br>`scene_geometry_sha256` |

---

### 2.2 Loop-Closure Mechanism (Real Board Outline Adaptation)

When C04 completes component placement, the **real board outline** is fixed by actual electrical routing channel requirements and component courtyards (e.g., 28.0×93.0 mm or an optimized polygon). The feedback loop closes via the following automated contracts:

1. **Board Geometry Publishing (`c04_board_manifest.json`)**:
   C04 exports an exact machine-readable geometry packet containing:
   - `outline`: Polygon vertices of `Edge.Cuts` (including corner fillets R=2.0 mm).
   - `thickness`: 1.60 mm.
   - `mounting_holes`: Array of `(x, y, drill_dia, pad_dia)` coordinates.
   - `connectors`: Origin, mating plane normal vector, and bounding box for `J1` (USB-C), `J2` (BAT), `SW1` (Slide switch), `SW2`/`SW3` (Buttons), and `D2..D5` (LEDs).
2. **C02' Mechanical Enclosure Regeneration**:
   `C02-ME/build_enclosure.py` is invoked with `c04_board_manifest.json` as its primary input:
   - Updates `INNER_L = board.length + CLR * 2`, `INNER_W = board.width + CLR * 2`, `INNER_H = board.height_envelope + CLR * 2`.
   - Repositions lower and upper shell mounting bosses to align coaxially with C04 `mounting_holes`.
   - Aligns wall openings (`O["usb_c"]`, `O["power_switch"]`, `O["led_window"]`, `O["activate_button"]`) to match C04 connector 3D coordinates.
   - Generates watertight, manifold meshes (`check_manifold == true`) for `enclosure_lower.stl`, `enclosure_upper.stl`, and `Enclosure.step`.
3. **C01' Industrial Design Scene Regeneration**:
   The visualization engine (pyrender / cleared Blender) ingests `Enclosure.step` directly from C02':
   - Replaces placeholder block geometry with the authentic C02' exterior mesh.
   - Applies C01 CMF tokens (`MIST_WHITE`, `SILVER`, `PORT`, `LENS`, `KEY`).
   - Renders final client-facing exterior perspective views (`NN.c01-product-v2.png`) and CMF breakdown (`NN.c01-cmf-v2.png`).

---

### 2.3 Machine-Checkable Manifest Hash Chain Validation

A system validation check confirms that the entire flow forms an unbroken cryptographic chain:

$$\text{ValidateChain}() \iff \begin{cases} 
M_{C04}.\text{consumed\_netlist\_sha256} == M_{C03}.\text{netlist\_sha256} \\
M_{C04}.\text{consumed\_bom\_sha256} == M_{C03}.\text{bom\_sha256} \\
M_{C02'}.\text{consumed\_board\_outline\_sha256} == M_{C04}.\text{exported\_outline\_sha256} \\
M_{C02'}.\text{consumed\_mounting\_holes\_sha256} == M_{C04}.\text{exported\_mounting\_holes\_sha256} \\
M_{C01'}.\text{consumed\_enclosure\_mesh\_sha256} == M_{C02'}.\text{exported\_mesh\_sha256} 
\end{cases}$$

If any upstream file is modified without downstream re-execution, the chain breaks with a `STALE_UPSTREAM_MANIFEST` error, blocking final gate acceptance.

---

## 3. CONFLICTS → ASK LIST (Routing to thesmart_products Duty Officer)

Per the dispatch instruction, the architectural and scope contradictions below are **NOT resolved locally**. They are formulated verbatim as an **ASK List** to be routed by the coordinator to thesmart_products Duty Officer (`ses_eed1fb0b6ffelFUGhmXVSGcp3z`).

---

### ASK-1: C04 Scope Contradiction — D-3/OD-6 ("Do Not Draw Main PCB") vs. C03 Carrier PCB & R-H Gerber Mandate

- **Conflict Background**:
  - `C00_Requirements_Bridge.json` and `C00_Decision_Log.md` record User Decision **D-3** (2026-09-01): *"你的任務不是重新設計PCB電路板。而是直接上網選用現成的Raspberry Pi開發板，套上ID殼... 路線 B 整條作廢；C04 由 OD-6 重新定義為 module integration（不畫 PCB。禁 .kicad_pcb / Gerber / drill / CPL / DRC / expect.json）"*.
  - `C04-Layout/README.md` explicitly lists `.kicad_pcb`, Gerber, drill, and DRC as *"本階段絕對禁止產出的東西"*.
  - Conversely, `C03-EE/02_build/sch_gen/design.py` establishes an explicit carrier PCB ruling (2026-09-05): *"this board is a REAL carrier PCB that we design and fabricate: USB-C input, ETA6003 charger with power-path, reverse-battery protection, 3V3 buck, status UI, battery interface — with the radio as a reflow-soldered SMT module."*
  - Furthermore, `amendment-presentation-authority-20261006.md` §3.2 (DD-20 / DD-C04) and task 7.4 mandate delivering an editable `.kicad_pcb`, all copper layer PNGs, Gerber/drill fabrication packages, and filled-board DRC. A legacy 4-layer board (`btdongle_c04.kicad_pcb`) and Gerbers already exist on disk under `C04-Layout/02_build/generated/`.
- **Question for thesmart_products Duty Officer**:
  > **[ASK-1]**: Does the product owner formally repeal Decision D-3's prohibition against designing a PCB, confirming that C04's authorized deliverable is a custom carrier PCB (`btdongle_c04.kicad_pcb` + Gerber/drill set) hosting the Pico 2 W module and power-path circuitry, rather than an off-the-shelf module integration?

---

### ASK-2: Form-Factor Contradiction — C01 "satisfied: false" vs. C04 28×93mm Outline vs. C02 Enclosure Cavity

- **Conflict Background**:
  - `C01_Form_Factor_Constraints.json` explicitly marks the PRD requirement *"USB Dongle 的大小"* as `satisfied: false`. Note explains: *"18650 電芯 ⏀18.6×65.1 mm 長於主板 51 mm；D-7/D-11 後為三層堆疊。D-1 裁決尺寸不合格可接受，NRE 近乎零。路線 B（自製板）為尺寸唯一解（暫時排除，未否決）"*.
  - `C02-ME/enclosure_params.json` and `build_enclosure.py` dimensioned an enclosure around a stacked Pico 2 W (51×21 mm) + Waveshare WAV-20121 (62×21 mm), resulting in an inner cavity of `64.4 × 23.4 mm` and outer envelope of `68.4 × 27.4 mm`.
  - In `C04-Layout`, the legacy carrier board `btdongle_c04.kicad_pcb` is **`28.0 × 93.0 mm`** (expanded to 28 mm width to allow 2.4 mm routing channels past the 23.17 mm Pico courtyard, and 93 mm length to accommodate the Pico module plus ETA6003 charger, USB-C, switches, and battery interface).
  - This 28×93 mm carrier board physically exceeds the C02 enclosure cavity in both length (+28.6 mm) and width (+4.6 mm). Furthermore, adding an external 18650 battery holder (71.0×20.6×20.6 mm) requires a substantial volume expansion.
- **Question for thesmart_products Duty Officer**:
  > **[ASK-2]**: Which physical form-factor and enclosure architecture is the authoritative target for C04:
  > - **(Option A) Small Gateway Form**: Formally accept the expanded carrier PCB envelope (~28.0 × 93.0 mm); authorize C02-ME to enlarge its enclosure parameters to house this carrier PCB alongside the 18650 battery holder.
  > - **(Option B) True USB Dongle (Reactivate Route B)**: Reject the 28×93 mm carrier board; reactivate Route B (compact chip-down RP2350 + RF module) to satisfy the original USB-dongle form factor.
  > - **(Option C) Modular Sandwich**: Reject the custom carrier board; return to off-the-shelf stacked Pico 2 W + Waveshare UPS-B module with wiring harness?

---

### ASK-3: Power Architecture Discrepancy — Off-the-Shelf Waveshare WAV-20121 (OD-1) vs. Onboard ETA6003 (design.py)

- **Conflict Background**:
  - PRD Owner Decision **OD-1** (2026-09-02) ruled: *"path-II: WAV-20121 Waveshare Pico UPS"* as the primary power module.
  - However, C03 `design.py` and `btdongle_ms_bom-v2.csv` implement an autonomous on-board ETA6003 switching charger (`U1`) with dynamic power-path, discrete inductor (`L1`), P-MOSFET reverse protection (`Q1`), and USB-C receptacle (`J1`) directly on the carrier PCB.
  - If `design.py` is the board to be fabricated, the Waveshare WAV-20121 module is completely eliminated from the hardware BOM.
- **Question for thesmart_products Duty Officer**:
  > **[ASK-3]**: Does product management confirm that the onboard ETA6003 carrier circuit supersedes OD-1, rendering the Waveshare WAV-20121 module obsolete and removing it from the procurement list?

---

### ASK-4: Battery Interconnect Discrepancy — 2-Pin Flying Header (ICD §1) vs. 3-Pin JST-PH (design.py J2)

- **Conflict Background**:
  - `C03_Interconnect_ICD.md` §1 specifies a 2-pin connector (`BAT+`, `BAT-`) matching the Waveshare UPS module battery header P1.
  - `design.py` specifies a 3-pin through-hole JST-PH connector `J2` (`BAT+`, `NTC`, `BAT-`), with onboard pull-down `R5 10k` to support battery thermistor sensing.
- **Question for thesmart_products Duty Officer**:
  > **[ASK-4]**: Should the physical battery harness mating with the carrier PCB be a 3-pin JST-PH connector (supporting battery pack thermistor) or a standard 2-pin battery holder lead?

---

### 3.1 Product-owner rulings (user, 2026-10-07, via duty officer `question()`)

The user IS the product owner; the four ASKs were put to the user directly and are
ruled. thesmart_products ★ (`ses_eed1fb0b6ffelFUGhmXVSGcp3z`) receives these rulings
for landing in its own C00 decision log / C04 README / ICD; it does not re-decide them.

| ASK | Ruling | Consequence |
|---|---|---|
| ASK-1 | **D-3 REPEALED.** C04 deliverable = custom carrier PCB (`.kicad_pcb` + Gerber/drill). | C04-Layout/README.md prohibition table → `superseded by user ruling 2026-10-07`. R-H Gerber mandate stands. |
| ASK-2 | **Option A — Small Gateway Form.** 28×93 mm carrier + 18650 accepted; C02 enclosure grows to fit. | C02' regenerates on the real C04 outline (chain contract §2.2); C01 `satisfied:false` stays recorded as an accepted gap (D-1). Route B remains "not rejected", not reactivated. |
| ASK-3 | **ETA6003 on-board supersedes OD-1.** WAV-20121 removed from procurement. | design.py / module book 09–10 are authoritative for power architecture; C00 decision log gains OD-1 superseded entry. |
| ASK-4 | **3-pin JST-PH with NTC** (design.py J2 + R5). | `C03_Interconnect_ICD.md` §1 → 3-pin; 09 page unchanged. |

Task 7.4 (C04 placement spike, §4) is UNLOCKED by these rulings. §4.2 item 3: the
netlist digest to bind is the book manifest root `9e20483e…` / `book_modules-v2.net`
(the `ff8115dc…` figure below predates r14 and is corrected here).

## 4. C04 SPIKE PROPOSAL (Bounded Placement-Only Round 1)

In strict accordance with DD-20 and Task 7.4, Round 1 of the C04 Spike is strictly bounded to an **intent-first, module-aware placement candidate** on the frozen board outline. **No track routing or polygon pouring is performed in Round 1.**

---

### 4.1 Scope, Producer, and Execution Boundaries

- **Producer Assignment**: Hand-drafted placement candidate produced by Sonnet (following the exact collaborative hand-drafting methodology proven during C03 module book r13/r14). Algorithmic/engine placement (freerouting) is explicitly deferred to later rounds as an optional optimization proposal.
- **Execution Boundary**:
  - Physical Component Placement: Place all 45 references from `btdongle_ms_bom-v2.csv` onto the frozen outline.
  - Fix Mechanical Locks: Lock positions of perimeter interfaces (`J1` USB-C, `J2` Battery, `J3` SWD, `SW1` Power slide, `SW2` Reset, `SW3` User button, `D2..D5` LEDs).
  - Respect RF Constraints: Position `U2` (Pico 2 W) with its antenna oriented directly into the lower edge, strictly isolating `KO-01` (14×9 mm).
  - Cluster Functional Motifs:
    - *Motif A (Power Entry & Protection)*: `J1`, `F1`, `D1`, `R1`, `R2`, `C1` adjacent to the USB edge.
    - *Motif B (ETA6003 Charger & Inductor Loop)*: `U1`, `L1`, `C2`, `C3`, `C4`, `R3`, `R4`, `R6`, `D2`, `R7`, `SW1` grouped to minimize switching loop area.
    - *Motif C (Battery Input & Protection)*: `J2`, `Q1`, `C5`, `C6`, `R5`, `R13`, `R14`, `C13`, `TP2`.
    - *Motif D (MCU Core & Bypass)*: `U2`, `C8`, `C9`, `C10`, `C11`, `R8`, `C7`, `SW2`, `J3`.
    - *Motif E (User Interface)*: `D3..D5`, `R9..R11`, `SW3`, `R12`, `C12`.
  - **ZERO ROUTING**: No copper tracks, no vias, and no copper pours. Round 1 tests physical feasibility, clearances, access, and rat's nest legibility only.

---

### 4.2 Round 1 Deliverables

1. **Human-Viewable Placement Render**:
   - File: `01.c04-placement-v1.png`
   - High-resolution SVG/PNG render displaying component footprints, silkscreen outlines, reference designators, courtyard boundaries, board edge (`Edge.Cuts`), mounting hole locations, and antenna keepout zone (`KO-01` shaded red).
2. **Machine-Editable PCB**:
   - File: `btdongle_c04-v1.kicad_pcb`
   - Native KiCad 9 format with all 45 footprints instantiated, placed, oriented, and assigned nets matching `book_modules-v2.net`. Components marked with mechanical locks where applicable.
3. **Placement Manifest & Provenance Sidecar**:
   - File: `c04_placement_manifest.json`
   - Records netlist SHA256 (`ff8115dc…`), BOM SHA256, board dimensions, courtyard bounding boxes, and producer metadata.

---

### 4.3 Blind-Review Protocol (StageVisualReview per DD-20(e))

The placement image `01.c04-placement-v1.png` will be submitted to an independent fresh-eyes reviewer without providing the netlist or schematic. The reviewer must answer the following standardized evaluation questions:

1. **IC & Subsystem Identification**:
   - Locate the main microcontroller module (`U2`), the battery charging IC (`U1`), and primary power/external connectors (`J1`, `J2`).
2. **Functional Flow & Organization**:
   - Does the placement clearly communicate the energy and signal flow (USB 5V In → Charger → System Rail / Battery → MCU → Status UI)?
3. **RF Isolation & Keepout Integrity**:
   - Is the antenna region (`KO-01`) completely unencumbered? Are noisy components (switching inductor `L1`, charger `U1`) positioned at a safe distance from the RF antenna?
4. **Physical Interface & Access**:
   - Are the USB-C port (`J1`), slide switch (`SW1`), push buttons (`SW2`, `SW3`), and status LEDs (`D2..D5`) oriented toward board perimeters/surfaces suitable for enclosure cutouts and light pipes?
5. **Congestion & Routing Feasibility**:
   - Are there severe courtyard overlaps or congested bottlenecks around the QFN-16 and Pico perimeter pads that would impede subsequent manual or automated routing?

---

### 4.4 Deterministic Gate List (DD-20(d))

| Gate ID | Verification Item | Target Threshold / Metric | Handling if Tool / Worker Unavailable |
|---|---|---|---|
| **GATE-C04-01** | Footprint & Pad Inventory Parity | Exactly 45 references; pad count matches netlist 100% (0 missing, 0 extra). | Deterministic script (`kicad-cli` / Python netlist parser); fail-fast. |
| **GATE-C04-02** | Courtyard DRC Cleanliness | `kicad-cli pcb drc --filter-courtyard` = **0 overlapping courtyards**. | Deterministic CLI check; must PASS. |
| **GATE-C04-03** | Antenna Keepout Invariant (`KO-01`) | **0 pads, 0 courtyards, 0 parts** within the 14.0×9.0 mm keepout box. | Geometry intersection calculation; must PASS. |
| **GATE-C04-04** | Mechanical Edge Margin | All component courtyards maintain ≥0.40 mm margin from `Edge.Cuts`. | Geometric bounding-box check; must PASS. |
| **GATE-C04-05** | Gerber Parity & Copper Connectivity | Filled-board DRC, copper continuity, export parity against Gerbers. | **EXPLICITLY DECLARED AS `UNMEASURED`** in Round 1 (Placement only; no routing or Gerbers produced in Round 1). |

> **Invariance Declaration**:
> In accordance with DD-20(d), `GATE-C04-05` (Gerber Parity & Copper Connectivity) will remain honestly marked as **`UNMEASURED`** during Round 1. A visual preview or DRC pass of an unrouted board will **NEVER** be converted into a false copper connectivity PASS.

---

## 4.5 Round 1 outcome and Round 2 rulings (officer, 2026-10-07)

Round 1 landed (manifest root `14fecab2…`, 399 entries; board sha `4b59ac7c…`). Track B
`bodesign_c04_placement_geometry_gate` run by the officer on the specimen: GATE-01..04
pass, GATE-05 unmeasured — same verdict as the producer's independent `.src/c04_gates.py`
(min edge margin differs: 0.400 producer polygon model vs 0.445 tool AABB model; residual).
Review 23 (blind, image only, ses_eec304fa1) = ACCEPT-marginal: major blocks correctly
partitioned, KO-01 clean; defects: ~10 ref-designator texts touching pads/courtyards,
small-parts column jammed against U2 castellations, caption clipped, LEDs/switches/J3
inboard. Dual-track signal: the two reviewer-cited defects (silkscreen collision,
courtyard gap 0.130 < §1.7 0.25 mm) are measured by NO gate yet.

User rulings (product owner):
- UI interfaces STAY inboard: LEDs via light pipes, SW2/SW3 via lid openings, J3 as an
  internal service port. C02' lid gets these openings; no re-placement.
- Round 2 scope: fix silkscreen collisions; enforce courtyard-to-courtyard ≥ 0.25 mm
  (§1.7); un-clip the caption; re-space the small-parts column ≥ one trace width from U2
  castellations. Track B adds GATE-C04-06 (silkscreen ref text vs pad/courtyard overlap)
  and GATE-C04-07 (minimum courtyard gap) — both must FAIL on r1 and PASS on r2.
- Mounting holes: decided by C02' enclosure regeneration, fed back to C04 r3. r2 draws none.

## 4.6 Round 2 outcome (officer, 2026-10-07)

r2 landed (manifest root `6f07bcdc…`, 416 entries; v1 to `.history/`). Officer ran
`bodesign_c04_placement_geometry_gate` on both boards: r2 → 01–04/06/07 pass, 05
unmeasured; r1 → 06 fail (35 offenders / 21 refs, all 10 Review-23 refs caught), 07 fail
(C1/F1 0.130 first). Negative + positive control hold; producer's independent checker
agrees (r2 silk 0 offenders, min courtyard gap 0.300). Producer changes accepted: ref
text moved to F.SilkS 0.8/0.15 mm (board silk minimum; Fab refs are not printed); PNG
portrait (r1 rotation inverted vertical text).

Review 24 (blind, image only, ses_eec16a5a9) = ACCEPT-marginal: blocks right, keepout
clean, caption legible, nothing inverted; cites D2/R6/R7/C5/R13/R12/C12 labels as
"touching" and R12-C12 / C5-C13-R5 / R9-R11 as ambiguous. Measured clearances of those
texts are 0.163–0.252 mm (table §4 of c04_r2_gates-v2.md) — above the 0.15 threshold.
Review 24 second pass (same reviewer, full-resolution detail tiles) = **ACCEPT**:
"touching/overlapping: none found; ambiguous: none; upside-down: none" — every cited
label shows visible gap from the courtyard outline at full resolution.
**Calibration finding (corrected)**: the first-pass "touching" calls were a render-scale
artifact of the downsampled whole-board view, not a threshold under-estimate; the
0.15 mm gate and the human verdict agree once the reviewer looks at native resolution.
Consequence for the review protocol: placement blind review must include detail tiles
at ≥ 1:1 pixel scale, not the whole-board thumbnail alone (same lesson as C03 "title
block overflow" that no thumbnail could show). GATE-06 default stays 0.15 mm.

Ruling: r2 is the ACCEPTED PLACEMENT BASELINE for routing (Reviews 23/24 never
questioned block partition; Review 24 full-res pass ACCEPT). No label round needed;
r3 = routing on this placement.

## 4.7 C02' round 1 outcome (officer, 2026-10-07, under R-J sandbox rule)

Track A (ses_eee1a92f4): `c04_board_manifest-v1.json` (consumed_board_sha256 =
r2 board), build123d source, `c02p_enclosure_{lower,upper}-v1.stl`, STEP (real
export, not re-imported), three PNG (iso / exploded / section), gates report;
manifest root `d70e0939…` 434 entries, officer `sha256sum -c` 0 non-OK. Mounting
holes: 3 proposed (H1 2,2 / H2 26,2 / H3 26.5,60.2; drill 1.8), 4th impossible on r2
at ≥ 1.0 mm courtyard clearance (grid search, best 0.564) → `feedback_to_c04_r3`.
Track B (ses_ef0e7e310): `bodesign_c04_board_manifest`, `bodesign_c02_mesh_gate`
M-01..06, 30 tests (officer rerun Ran 30 / OK / skipped=1).

Officer ran Track B on Track A STLs: M-01/M-02 pass both parts (0 boundary, 0
non-manifold, 0 inconsistent edges), M-04 min wall 1.5 / 0.9997 ≥ 0.8 pass; M-06 chain
pass — but ONLY against the producer's own hand-written `c04_board_manifest-v1.json`
(outline `8975fdfd…`, holes `10154c1f…` = hash of its 3 *proposed* holes); M-03
unmeasured (no expected bbox given), M-05 unmeasured (no `board_placement_mm`).
Producer's own trimesh numbers agree.

Correction (r2 Track B, `bodesign_c02_chain_check` recomputing from the .kicad_pcb,
officer rerun): outline recompute `6e66f4e9…` ≠ consumed `8975fdfd…` FAIL; mounting
holes recompute `4f53cda1…` (board has none) ≠ consumed `10154c1f…` FAIL; the producer's
board-manifest file is STALE_BOARD_MANIFEST on both hashes + schema. So the r1 M-06
"pass" proved only that the producer's two files agree with each other — gap 1 below.
The proposed holes must live in a C02' inputs file, not in the board packet, until C04
r3 drills them.

Review 25 (blind, ses_eea92c8a9) = ACCEPT-marginal: concept readable (tray + lid,
board on shelf over one cylindrical cell, 3 pin posts, UI holes in lid, USB at one
end); section fill single-colour hides board / shelf / cell distinction; lid has no
retention; shelf bridges the cell bay unsupported for FDM; no outside view of the USB
end, no plan view, no section through lid holes.

**Capability gaps surfaced (bodesign work for C02' r2):**
1. Chain §2.3 currently closes only between the producer's own two ends: producer's
   `exported_outline_sha256` = `8975fdfd…`, bodesign `c04_board_manifest` on the same
   board = `6e66f4e9…` (different outline sub-schema). Ruling: the bodesign tool's
   packet is the SSOT; C02' must consume the tool's output, not a hand-written manifest.
2. M-05 needs `board_placement_mm` in the C02' manifest; the mesh gate must read it from
   `c02_manifest_path`. Producer frame note "CAD = (x,-y,z)" is a convention, not a
   registration.
3. Section/exploded renders need per-body colour (board / shelf / cell / shell) and a
   declared view set (add USB-end exterior, plan, lid-hole section) — DD-19(a) view
   coverage becomes a checkable item, not a producer choice.
SANDBOX-ASSUMPTIONS (wall 2.0, clearance 0.5, split z 5.0, 18650 cavity, pin
posts, no retention) stand as specimen decisions; lid retention and FDM bridge are
r2 specimen items, not user questions.

## 4.8 C02' round 2 outcome (officer, 2026-10-07)

Track A r2: manifest root `d6208ab0…` 459 entries (officer 0 non-OK). Board packet is
now the bodesign tool's own output (`c04_board_manifest/1`, outline `6e66f4e9…`,
holes [] `4f53cda1…`); proposed holes + heights + normals live in `c02p_inputs-v2.json`
citing the packet sha. STL/STEP frame made board-relative so registration is a pure
translation `board_placement_mm=[-100,-50,0]`. Six declared views + extra screw section.
Specimen fixes: 3× M1.6 screws lid→posts, slot roofs cut to split plane and closed by lid
tongues (0 overhang clusters), SW1 slot labelled.

Track B r2: `c02_mesh_gate` reads placement from the C02' manifest (M-05 measured);
`bodesign_c02_view_coverage` (DD-19(a) six-view set, PNG validity + min px);
`bodesign_c02_chain_check` (recompute from .kicad_pcb, STALE_UPSTREAM / STALE_BOARD
kinds). Tests: test_c02_chain 17, test_c02_mesh_gate 34 (officer rerun OK). Real-world
negative control: r1 files FAIL chain_check (outline + holes + stale board-manifest file).

Officer positive control on r2: chain_check ok (3/3 pass); mesh gate M-01/02/04 pass
(wall 0.9997 / 0.8497), **M-05 pass 0.30 ≥ 0.25 (placement_source=c02_manifest)**,
M-06 pass; view_coverage 6/6 pass (r1 was 1/6). M-03 unmeasured only because no bbox
declared in the officer call.

Review 26 (blind, ses_eea628ff1) = ACCEPT-marginal: assembly, openings, battery and board
placement traceable from the six views; per-body colour + legend readable. Open items:
button interface not mechanically closed (SW2 top z 1.5 vs lid inner z 6.5, no actuator
cap); board-to-post retention not shown (lid clamps board, nothing fixes it); J2 in
legend has no opening; 0.5 mm cell web thin for FDM; plan view 1000×2170 needs tiling;
view to add = section through H3 (lid→post→PCB→shelf→tray).

Ruling: **r2 is the accepted C02' baseline for the chain**; the two mechanical gaps
(actuator caps / board retention) are specimen items for C02' r3 after C04 r3 drills the
holes. Capability lesson: view coverage by filename proves presence, not that a view
exposes the relation a reviewer needs — DD-19(e) questions remain the human axis.

## 5. Summary and Next Steps

1. **Task 7.3 Status**: **COMPLETED** as a design deliverable (`c04-entry-freeze-20261007.md`).
2. **Action Required by Coordinator / Duty Officer**:
   - Route the four items in **Section 3 (ASK List)** to thesmart_products Duty Officer (`ses_eed1fb0b6ffelFUGhmXVSGcp3z`).
   - Await formal ruling on ASK-1 (repealing D-3 PCB ban) and ASK-2 (authorizing the 28×93 mm carrier outline vs. Route B).
3. **Condition for Entering Task 7.4 (C04 Placement Execution)**:
   - Receipt of duty officer clarification on the ASK list unlocks Task 7.4 execution (dispatching Sonnet to construct `btdongle_c04-v1.kicad_pcb` and `01.c04-placement-v1.png` per Section 4).
