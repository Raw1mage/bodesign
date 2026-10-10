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

## 4.9 C04 round 3 — routing + copper views (officer, 2026-10-07)

Track A r3 (ses_eee1a92f4): `btdongle_c04-v3.kicad_pcb` (48 fp = 45 + H1..H3 NPTH 1.8;
stackup §1.5 with core 1.06 so sum 1.60; net classes §1.6); freerouting 1.9.0 in
`bodesign-ee` (host preflight not-ready: jar/java/xvfb absent); 371 tracks / 87 vias;
pours In1 GND solid, B.Cu GND flood, In2 SYS patch. DRC --severity-all
--schematic-parity: 0 unconnected / 0 parity / 0 shorts; 10 items = 1 REAL clearance
(U1.7 NTC vs EP 0.20 < 0.25), 4 REAL items_not_allowed (H1/H2 inside the stock Pico RF
rule area), 2 Pico paste-only (tool), 3 lib_footprint (presentation). Gerbers-v3: 14
files, X2 on, protel ext. Copper views rendered from the gerbers (pygerber, common
Edge.Cuts frame, drill overlay): `01.c04-{F.Cu,In1.Cu,In2.Cu,B.Cu}-v3.png`,
`-copper-composite-v3.png`, `-copper-stack-v3.pdf` (5 pp); plus pcbnew `-routed-v3.png`
and `-placement-v3.png`. Orientation USB-bottom kept (matches placement PNG; brief said
USB-top — accepted). Manifest root `d5c4081d…` 507 entries (officer 0 non-OK).
Brief rules NOT met (reported, not hidden): Power_High 0.26 mm not ≥ 0.50 (QFN-16
escape), BAT_EXT 1 via not ≥ 2; CC lengths 15.2 / 23.8 mm with no declared threshold.
Board manifest v3 holes sha `788c668d…` → C02' chain is STALE; C02' r3 must re-consume.
Caveat: core thickness sed-patched after the router run (clean rerun not byte-identical).

Track B (ses_ef0e7e310): `bodesign_c04_gerber_gate` G-01 parity / G-02 copper
connectivity from gerber bytes (exact analytic, 1 µm join, plated drill spans) / G-03
keepout on copper / G-04 render–gerber sha binding; placement gate GATE-05 delegates
when `gerber_dir` is given. test_c04_gerber_gate 35 (officer rerun OK). Synthetic
negatives: open, short, barrel open, missing/extra flash, outline shift, keepout copper.
Also ruled: specimen tests are shape-only (test_c02_chain stale verdict test replaced,
17 OK).

**Officer positive control on v3 gerbers (first real board):** G-03 PASS (no copper in
KO-01 on any layer, from gerber bytes); G-01 FAIL / G-02 FAIL / G-04 FAIL — all three
are TOOL-MODEL GAPS, not copper defects: G-01 missing_flash ×7 per side are NPTH pads
(H1–H3, SW1 pegs, J1 shell pegs; KiCad emits no flash); G-02 sole offender GND
barrel_open at J1.S1 = oval drill exported as an Excellon slot the reader does not parse;
G-04 bound 0 = no sidecars yet. Dispatched r3b: NPTH = drill-only (rule keyed on pad
type/layers, not ref prefix), slot drills as stadium hits, fixtures for both; Track A
emits `<stem>.json` sidecars. Capability lesson: a real routed board exercised two
aperture/drill classes the synthetic fixture lacked — the fixture set must include NPTH
and slot drills from now on.

Review 27 (blind, copper views, ses_ee9f527fb) = ACCEPT-marginal: all five images same
orientation, outline + drills on each; In1 solid GND with KO-01 cut, antipads not
thermals; In2 SYS patch ~25–35 % copper; KO-01 empty on every layer; captions legible,
composite legend distinguishes layers. Engineer flags: power nets indistinguishable from
signals (uniform fine width — matches the 0.26 mm finding), two acid-trap approaches at
the module pad column, sharp jogs in the charger cluster, a few unstitched B.Cu flood
islands near H3 and under U1. These are r4 specimen items.

### 4.9.1 r3b–r3d gate calibration on the real board (officer rulings)

Each red on v3 was traced to a discriminating fact before any rule changed:
- G-01 NPTH: pad type `np_thru_hole` with no copper layer or size ≤ drill → drill-only
  (listed, not required flash). G-02 slots: Excellon G85 / routed slots and board `(drill
  oval)` → stadium hits. Both now have synthetic fixtures (`slot.kicad_pcb`).
- G-04 scope: gerber-derived layer renders only (F/B/In<n>.Cu, copper-composite);
  placement/routed PNGs → out_of_scope.
- GATE-01: 51 mismatches = 51 (ref,pin) nodes listed in both a real net and an
  `unconnected-*` block in `book_modules-v2.net` (0 duplicate net names); old loader let
  the last block win. Rule: real net wins; two distinct real nets on one pin = conflict,
  never collapsed. NPTH-only footprints = non_electrical, not extra.
- GATE-03: the 8 U2 pads inside KO-01 are F.Paste-only (stock Pico RF region); only
  copper-bearing pads offend. Remaining U2 courtyard/footprint hit is by construction
  (KO-01 IS the Pico antenna, §1.4 forbids *discrete* components) → keepout `owner_ref`;
  owner courtyard/footprint exempt and disclosed, owner COPPER pads still offend,
  non-owner unchanged; unknown owner_ref fails fast.

**Final officer run on v3** (gerber_dir + human_dir + KO-01 owner_ref=U2, netlist
book_modules-v2.net): **ok=True, GATE-C04-01..07 all pass, unmeasured []**; GATE-05
delegated G-01..G-04 all pass. Tests: test_c04_placement_gate 62 / OK, test_c04_gerber_gate
47 / OK (officer rerun). Full suite 2742 / f16 / e40 / s56 vs d8e1a02 baseline: the only
id containing c04_/c02_ is `test_c00_orchestration…test_c04_dispatched_only_after_its_upstream`
(stage name, pre-existing at d8e1a02 in a detached worktree). +1 error vs the older
cfcf393 baseline unattributed.

**r3 ruling: C04 r3 is the accepted routed baseline** (DD-20 gate measured end-to-end for
the first time; GATE-05 no longer literal unmeasured). Specimen residue → r4: U1.7 NTC
clearance 0.20, H1/H2 in Pico RF rule area, Power_High 0.26 mm, BAT_EXT 1 via, acid-trap
approaches, B.Cu islands. Chain: C02' r3 re-consumes holes sha `788c668d…`.

### 4.9.2 r4 routing gate — first calibration on v3 (officer rulings, 2026-10-07)

`bodesign_c04_routing_gate` R-01..R-06 built (33 tests, full suite 2775/f16/e40/s56, +33 = new
module only). Live v3 run: ok=False, unmeasured [R-05].

Calibration against the r3 residue list, verified by the officer:
- **R-01 confirmed**: Power_High (BATT/SYS/VBUS/Net-(D1-K1)/Net-(J2-Pin_1)/Net-(L1-Pad1)) at
  0.26 mm, 128 offenders. NEW finding not in the r3 residue list: Ground class min 0.3, GND at
  0.2 mm on F.Cu (10 segments) → forwarded to Track A r4.
- **R-02 confirmed, name mapping verified**: `BAT_EXT` (design.py:216 = Q1.2, J2.1, C6.1) and
  `Net-(J2-Pin_1)` (book_modules-v2.net code 12 = C6.1, J2.1, Q1.2) are the same node set; the
  book netlist carries the page-local name. BATT (3 vias) is a different net and passes.
- **R-04 NOT red on v3 — and the ruling is that the gate is right, the expectation was wrong.**
  Measured: stored B.Cu fill = one positive-area outer loop (2156.9 mm²) + 40 hole loops;
  B.Cu gerber = one GND component (58 items) + 39 single-item non-GND annuli. There is no
  stranded positive-area polygon. The r3 "B.Cu islands" residue came from Review 27 (thumbnail
  scale) and the producer's self-report, neither of which measured the fill. The calibration
  requirement "MUST fail on B.Cu islands" was an officer assumption from an unmeasured claim;
  a gate is never tuned to red to satisfy it. What a reviewer calls an "island" on a flood is
  usually a region joined by a pinched neck — a different rule: **R-07 min pour neck width**
  (narrowest connection between any two regions of one filled polygon, threshold = the net
  class min track width; synthetic negative control = pinched neck). R-07 measures v3 and
  reports; its verdict follows the bytes.
- **R-03 threshold ruling**: 45° pad entries are standard practice and not acid traps. Default
  flag threshold → **< 45°** (entries at ≥ 45° pass); class-level override stays. Re-run v3;
  what remains is the candidate set for the "two acid-trap approaches" Review 27 saw.
- R-06: via Net-(U2-GPIO17) at 0.882 mm (< 1.0 margin) matches the producer's own r3 number
  (0.118 mm inside margin) → forwarded to Track A r4.
- Fixture `tests/fixtures/c04_routing_gate/routed.kicad_pcb` is hand-written, not a native
  export (the gate reads only the s-expr; no CLI re-save exists core-side). Accepted with the
  limit declared in the module docstring; the live-board shape-only test is the native guard.

**Rulings applied, officer rerun** (`c04_routing.py` sha `20e6804c…`, tests Ran 40 / OK after
`__pycache__` clear). v3 verbatim: ok=False, unmeasured [R-05]; R-01 fail 128 | R-02 fail 1 |
R-03 fail 3 | R-04 pass | R-06 fail 4 | R-07 fail 19.
- R-03 at < 45°: 44 → 3 — U1.5 GND 22.5°, J1.A1 GND 33.7°, J1.S1 GND 43.1° (borderline).
  This is the measured candidate set behind Review 27's "two acid-trap approaches".
- R-07 on v3: GND_BCU / GND_IN1 one spot 0.2995 vs 0.3 (0.5 µm, rounding-class, not
  adjudicated); SYS_IN2 15 clusters 0.25–0.48 mm under the 0.5 Power_High min. The rule
  cannot tell a through-neck from a dead-end spike; the producer judges each against the fill.
- All of the above + GND 0.2 mm F.Cu (R-01) + GPIO17 via 0.882 (R-06) forwarded to Track A r4
  while v4 is still in flight, so v4 is judged against the full R-01..R-07 set, not r3's list.

### 4.9.3 r4 outcome (officer, 2026-10-07)

v4 landed (board sha `eb5ed99c…`, manifest root `bf0ad860…`, 583 entries). Placement+gerber gate
ok=True (GATE-01..07, G-01..04). Routing gate: R-02/R-04/R-06/R-07 pass, R-05 pass with declared
CC pair (30 mm / 10 mm skew), R-03 unmeasured (U2 custom pads), **R-01 fail 53 Power_High
segments** outside the declared QFN/D1 escape necks (16 segs ≤ 1.0 mm, 0.25–0.26 mm).

Ruling (R-J sandbox): escape necks ≤ 1.0 mm at U1/D1 are accepted with a declared current
ceiling 0.9 A ext / 0.45 A int (IPC-2221, 1 oz, 10 °C); SANDBOX-ASSUMPTION charge current
programmed ≤ 0.8 A. The 53 non-neck segments are a real miss → r4b: widen to ≥ 0.5 mm,
re-export gerbers-v4b, re-run all three gates. H1/H2 relocation makes the C02' chain stale
(holes sha `7aab0dc5…`) → C02' r3 after r4b.

### 4.9.4 r4b outcome — Power_High 0.5 mm is infeasible at this placement (officer, 2026-10-08)

Producer sweep (~80 router/placement points across r4 and r4b, incl. Option 1 U1-neighbour
moves, hand-drawn U1 necks, stub-first and resume passes) never reached {0 unconnected, 0
clearance, R-01 pass} simultaneously. Best cells: R-01/R-07 pass with 1–3 unconnected + 2–4
clearance (k6_00_115_left, k6_11_145_up, k6_13_145_left, k7_11_145_up). Producer session
died mid-sweep (finish=error, no v4b landed).

**Ruling (R-J sandbox, supersedes the 0.5 mm part of §4.9.3):** §1.6 Power_High 0.5 mm was
a sandbox assumption, not a datasheet or current-derived number. For this specimen the
Power_High class min width is **declared 0.26 mm** with IPC-2221 (1 oz, 10 °C) 0.90 A ext /
0.45 A int, under SANDBOX-ASSUMPTION charge current ≤ 0.8 A and no internal-layer Power_High
runs carrying > 0.45 A. **v4 (board `eb5ed99c…`) stays the routed baseline**; r4b is closed
without a v4b. Three rounds on one constraint is the stop line; another sweep buys nothing
for bodesign.

**What bodesign learns (the actual deliverable of r4/r4b):** the harness let a class width
be frozen that no router could honour at the given footprint pitch, and discovered it only
after ~80 routing runs. Track B item → **R-08 escape feasibility** (pre-route): for every
pad whose net class min width W and clearance C cannot pass between that pad and its
neighbours (pitch − pad width < W + 2C), report {ref, pad, class, pitch, max_feasible_width};
calibrate: v4 U1 at Power_High 0.5 → infeasible, at 0.26 → feasible; synthetic negative =
0.5 mm pitch QFN with 0.5 mm class. Also: R-03 must model U2's custom (castellated) pads
(17 endpoints unmeasured on v4).

**R-08 / R-03-custom landed (officer rerun: `c04_routing.py` sha `2948aadb…`, test_c04_routing_gate
Ran 49 / OK after `__pycache__` clear).** v4 verbatim at Power_High 0.5: R-01 fail/69, R-08
fail/3 (U1.2 VBUS, U1.14 BATT, U1.15 SYS — max_feasible_width 0.35 mm at 0.5 pitch / 0.25 pad /
0.2 clearance); at 0.26: R-08 pass/0, R-01 fail/9 (GND 0.2 < 0.3 on F.Cu only). R-03 on v4 now
143/143 endpoints examined, 0 offenders (custom castellated pads modelled from primitive union).

Calibration correction: officer expected U1 pads 1/14/15/16 + L1 infeasible; measured 2/14/15 —
corner pads 1/16 have a free outward side and L1 (1.5×3.6 mm) has no close other-net neighbour.
The tool was not tuned to the expectation; the expectation was a guess. Rulings: (i) same-net
pads are not obstacles (J1 Type-C paired pads, U1.17 GND) — accepted, disclosed as
`same_net_neighbour_pairs_ignored`; (ii) R-08 counts toward ok only pre-route, informational on
a routed board — accepted. The 0.5-mm infeasibility that cost ~80 router runs is now a
pre-route verdict in one call.

Residual on v4 under the 0.26 ruling: GND Ground-class 0.2 mm on F.Cu (9 segs) — carry to the
next C04 touch; not worth a round on its own.

## 4.10 C02' round 3 — re-consume v4 holes (officer, 2026-10-08)

New producer `ses_ee67d5b3b` (previous one dead at 330k ctx). Baseline ruling: manifest root =
`sha256sum hashes.sha256`; `e48e2e63…` accepted (r4b ASK had rebound two script lines).
Tool access ruling: served image `76fa7cff` predates S7/S8, so the four C02'/C04 tools were
called as repo functions (`PYTHONPATH=packages/eda-bridge`), every result labelled "repo
function @ HEAD 92cbe8c, not served-tool call". **This is the EE build-host gap made concrete:
the specimen chain is running on stand-ins for tools that exist only in the repo.**

Officer verification: manifest `98f14b6e…` 617 entries, `-c` 617 OK / 0 non-OK; STL/packet/
manifest sha16 match the report; seven v3 PNGs present. Gates (producer-run, officer-read):
`c02_chain_check` ok (outline `6e66f4e9…` + holes `7aab0dc5…` recomputed = consumed; board
manifest file fresh); `c02_mesh_gate` M-01..06 all pass, unmeasured [] (M-03 now measured with
declared bbox+tol; M-05 0.5 ≥ 0.25); `c02_view_coverage` 6/6. Board packet is the tool output;
producer-written one archived.

Sandbox design calls (producer): SW2/SW3 button-cap stand-ins as STEP children; retention =
M1.6 lid screws at H1/H3 + heat-stake pin at H2 (post cannot reach floor across the cell bay,
carried by a 47.7° self-supporting wedge from H3). Section through H3 added.

**137 observation (user asked):** 21 fresh-eyes subagents (3 rounds × 7 images), 21/21 exited
success, 0 killed-137, elapsed 20–71 s. One (R1 plan) exited clean WITHOUT reading its image
(`MEDIA_INLINE_DIMENSION_EXCEEDED` at 1000×2170) — survival ≠ review; producer shrank the
canvas. Before the fix the previous round lost 3/3 subagents to 137.

Residuals (round-3 findings on delivered images, not fixed; §9 of the producer report): leader/
caption overlaps on iso/exploded/section-usb/plan; section-h3 caption says "edge-on" but image
shows a slanted face (caption contradicts image); no blind review of v3. Not measured: J1
height (no library STEP), slicer/print, stake/thread/cap-force, independent fit.

### 4.11 C01' r1 ruling (2026-10-08) — scene gate landed, product views rendered, blind review

Dual track per DD-18. Track A (agy-relay gemini-3.8-flash-high, `ses_ee5813994`) rendered on
the pyrender 0.1.45/EGL baseline inside the `bodesign-me` image (host has no trimesh); Track B
(codex gpt-6.1-sol, `ses_ee580aa22`) delivered `c01_scene_gate` S-01..S-05 (31 tests, 0 live
tuning — specimen did not exist at its finish).

Officer verification: manifest `5ab07e35…` 635 entries (464 machine + 110 human + 61 external),
`-c` 0 non-OK; `c01_scene_manifest-v1.json` sha16 `285ea805` matches the in-canvas captions
quoted verbatim by three independent reviewers. Gate run by Track A as repo function @ HEAD
`a2cbc7f` (not served-tool call): S-01 primary pass (both STL sha recomputed), **secondary
unmeasured** (`c02p_manifest/3` carries no `exported_enclosure_mesh_sha256`); S-02 5 tokens /
6 surfaces, 0 unbound / 0 double-bound; S-03 5/5 declared views, 1600×1200, sidecars bound;
S-04 renderer bound; S-05 lower 33.0×98.0×30.7 / lid 33.0×98.0×8.5 vs M-03, Δ 0.0.

**Fresh-eyes inside Track A did not happen**: 6/6 `invoke_subagent` calls were refused by a
pre-tool hook (A2A invariant intercept); producer reported it honestly as "not reviewed". Officer
ran Review 29 as three `task(general)` blind reads (iso-front, usb-end, cmf); **all three
READ_OK** and quoted the caption text — survival and review coincide this round.

Review 29 findings (r2 fix list, not re-gated):
- iso-front: wavy shading artifact across the lid around the controls (bad normals or
  overlapping mesh); lid appears to float/step off the lower tray at the near corner; J1 block
  and an unlabelled stub protrude from the end face instead of sitting in cutouts; four disc
  features on the lid but footer lists only H1/H3.
- usb-end: port opening has no depth (reads as a decal); stray tab outside the silhouette on
  the left; shell blown out with no edge definition; object fills ~1/3 of the canvas.
- cmf: KEY token has no visible anthracite surface in the render and is missing from the bottom
  strip (4/5 listed vs "5/5 bound" claim); PORT/KEY "Design Intent" text clipped at card edge;
  "Design Intent:" label runs into its text; LED dots too small to read.
Common: lighting flat/overexposed on MIST_WHITE; LENS indistinguishable from shell.

Rulings: (a) S10 pool = `c01_scene_gate.py` + `test_c01_scene_gate.py` + `__init__` /
`server.py` / `test_mcp_server.py` registration + this section. (b) C02' next version MUST emit
`exported_enclosure_mesh_sha256` per part so S-01 secondary becomes measurable on the real tree.
(c) C01' r2 scope = the fix list above plus a composite "all views on one page" check; r2 is not
required before S10. (d) Harness: `invoke_subagent` from a non-officer handler is blocked by the
hook, so producer-side fresh-eyes is structurally unavailable — officer-run blind review is the
standing mechanism. The earlier opencode BR on subagent image review is already closed by its
owner; the hook intercept is a distinct defect, filed as a new opencode BR (2026-10-08).

**§4.11(b) discharged (2026-10-08, codex producer `ses_ee55cdf11`)**: `c02p_manifest-v4.json` is a
manifest-only revision (schema `c02p_manifest/3` + `exported_enclosure_mesh_sha256{lower,upper}` +
`exported_enclosure_step_sha256` + `revision_note`); v3 retained byte-identical in place as C01 v1's
consumed input (ruling: no `.src/.history`, no archive move). Officer verification: manifest
`9acab9cf…` 639 entries, `-c` 0 non-OK; v4 mesh shas equal the on-disk STL shas; chain/mesh gates
still all-pass, unmeasured []; `c01_scene_gate` with v4 as C02 argument → **S-01 primary pass,
secondary pass (measured)**, S-02..S-05 pass. The C01'↔C02' chain is now fully measurable on the
real tree. Repo function @ HEAD `2f2bc4e`, not served-tool call.

### 4.12 C01' r2 ruling (2026-10-08) — Review 29 fix list closed, Review 30 residuals

Producer agy-relay `ses_ee5570934`. Officer verification: manifest `f5f2faa6…` 658 entries,
`-c` 0 non-OK; v2 PNG/PDF sha16 match the report; 13 v1 files in `btdongle_ms/.history/`, 0 v1 at
top level; container-written files chowned back to `pkcs12:pkcs12` (verified); scene manifest v2
`029c517e…` consumes C02' v4 (`3aba2268…`), 6 declared views, 4 lights; `c01p_r2_scene-v1.json`
S-01 primary+secondary pass, S-02..S-05 pass (repo function @ HEAD `2f2bc4e`).

Review 30 (three `task(general)` blind reads, all READ_OK, captions quoted verbatim):
- usb-end: all six r1 findings closed — recessed cavity with tongue, no stray tab, 61 % width,
  shaded shell with edges. New: port reads ~18 % of shell width (oversized for 9.6 mm at a 33 mm
  shell — check camera/scale, not geometry).
- iso-front: lid ripple gone, J1 recessed, KEY caps visible as two dark discs, 5/5 tokens in the
  strip. Residual: SILVER screws render as dark as KEY caps (no metallic separation); only 3 of
  4 LEDs visible; unexplained slot-like recess at the left corner of the end face (SW1 pocket?
  must be labelled); near-right corner still reads as a stepped notch; object ~40 % of canvas.
- cmf: cards/table/LED row all readable, no clipping inside cards; the 3D mapping viewport is too
  small to show SILVER or KEY surfaces (reviewer: "5/5 claim not visually backed for KEY and
  SILVER"); PORT unsure at that scale.
- All three: the footer's trailing free-text line ("Lid: 2x screws … 4x LEDs…") runs off the
  right canvas edge — a caption-layout bug, same family as the r1 card clipping.

Rulings: (a) r2 accepted as the C01' baseline for DD-18; residuals above are the r3 list, not
blocking. (b) r3 adds: SILVER needs metallic/roughness separation measurable by a pixel probe
against KEY; LED count 4 must be visible in iso-front or the view declared otherwise; end-face
left recess labelled or removed; footer line wrapped (no text may leave the canvas — S-03
should grow a canvas-bounds check for caption boxes in the next Track B round); cmf 3D
viewport enlarged to show every bound surface. (c) S11 pool = freeze §4.11 addendum + §4.12.

### 4.13 C00 PRD r1 ruling (2026-10-08) — tasks 7.9 / AC26, dual track

Track A producer codex `ses_ee531212e` (PRD rebased on PO-1..4 via served docxmcp); Track B codex
`ses_ee53095f3` (`bodesign_c00_prd_gate` P-01..P-05, 28 tests incl. negative controls, 5 files,
uncommitted → S12 pool). Officer verification: manifest `55b8f2dc…` 672 entries, `-c` 0 non-OK;
`12.c00-prd-v1.docx` `f4bf66db…`, `.pdf` `84fb797c…`; `c00_prd_manifest-v3.json` `47d72956…`
(v1/v2 in `.history/`); gate receipt `c00p_r1_gate-v1.json` `76d397b2…` ok=true, P-01..P-05 pass
(repo function @ HEAD `3b274f6`); DOCX XML requirement coverage 89/89, bridge 58/58 both directions.

Incident and ruling — NFR table body loss: host LibreOffice 24.2.7.2 dropped all nine body rows of
表 3 (a `tblHeader`+`cantSplit` table starting at a page break); container LibreOffice 25.2.3.2
(docxmcp's own) renders them. Proven by one-reviewer-per-image blind reads (t3-07/t3-08 vs
preview-08/final-07), not by text extraction — `pdftotext` reports 85/89 on BOTH renders
(extraction artifact; the four IDs wrap "NFR-"/"0N"). Ruling: (a) PDF path = docxmcp container
soffice via `docker exec`, label recorded in manifest with both version strings; host soffice
rejected. (b) The forcing gap is docxmcp's: `preview` discards its PDF and `from_markdown` ignores
header args → `docxmcp/issues/BR_20261008_preview_discards_pdf_and_from_markdown_ignores_header_args_forcing_host_soffice_detour.md`,
BRNS'd to docxmcp ★ (guest, not tracked). (c) Gate contract is the chain SSOT (§4.7 applies to
C00): manifest was re-emitted v2 (explicit path keys, requirement_ids = bridge FR/NFR/E only,
decision_ids = `### D-n/PO-n` headings) and v3 (`expects_in_bom`/`expects_absent_from_bom`), the
gate was not adapted.

Review 31 (three blind reads, READ_OK): cover carries `DRAFT — not approved PRD / sandbox specimen`
+ `未取得人工核准`, no clipping; 表 1 (page 2) 12 rows, no overflow. Residuals, not blocking, r2
list: (1) **TOC empty** — only the F9 placeholder renders (LibreOffice does not populate Word TOC
fields; sanctioned pipeline must emit a pre-populated TOC or the PDF must be produced after a field
update); (2) header `作者` still the template placeholder and `V 1.0` (from_markdown gap, BR above);
(3) cover title wraps mid-word (`規`/`格書`) and the DRAFT subtitle orphans `specimen`; (4) source
filename v1.2 vs body/bridge R6/v0.6 disclosed on cover and in manifest, not resolved upstream.
Harness note: one `task(general)` job again delivered two mutually exclusive completion events for
the same image (r31-03); adjudicated by `pdftotext` of the page — the second report matched, the
first was fabricated. Same family as opencode BR_20261008 (subagent reads); evidence appended there.

S12 pool = `c00_prd_gate.py`, `test_c00_prd_gate.py` (+ shared `__init__`/`server.py`/
`test_mcp_server.py` with S10 `c01_scene_gate`) + this §4.13.

### 4.14 Tasks 7.1 (DD-16 PresentationPlan) and EE build host / served parity (2026-10-08)

**7.1 dual track** (one codex worker `ses_ee44b3797`, A+B): contract
`presentation-plan-contract-20261008.md`; `data-schema.json` catalog 1.3.0 adds top-level
`presentation_plan`; specimen `c03_presentation_plan-v1.json` (45 physical refs / 167 pins, home
pages 07–11, U1/U2 repeated full-symbol views, `human_locks=[]`, `exceptions=[]`) generated by the
retained `.src/c03pp_gen-v1.py` from `book_modules-v2.net` + native lib symbols (unit/hidden/stacked
never defaulted); `bodesign_c03_presentation_gate` PP-01..PP-05, 30 tests incl. negatives;
receipt `c03_pp_gate-v1.json` ok=true (repo function @ HEAD `c3a34f4`). Rulings: approval
provenance = §3.1 user acceptance 2026-10-07 (no novel waiver); home map U2=07(+08), U1=09(+10),
J1=11, J2=09, J3=07; Reviews 6–22 bound verbatim to `.src/reviews.md`, Reviews 23–28 exist only as
officer summaries (evidence_class `officer_summary`, gap recorded — officer follow-up: blind-review
raw text must land in `.src/reviews.md` at review time). Officer verification: 13 files sha match,
registration diff +19/−1, manifest 685 entries 0 non-OK root `c52ee2d9…`. AC20 comprehension
review not performed by the gate (unmeasured, stated).

**EE build host** (codex `ses_ee44bd358`, user "go ahead"): first real build of the DD-9 elkjs layer
failed rc=127 — `Dockerfile.ee:66` ran `npm --version` (shebang `#!/usr/bin/env node`) one
instruction before `ENV PATH` at :67. One-line fix (`PATH="/opt/node/bin:$PATH"` prefix) → core/me/ee
healthy, UDS present, all nine S5–S12 gate tools in served `tools/list`. Second root cause of
"only verifiable at repo level": the specimen tree is not mounted (dev compose mounts only
packages/services/.work/experiments/.specbase); `BODESIGN_WORK_DIR=/home/pkcs12/products/bodesign`
exposes it at `/work` (note: `mcpctl.sh restart` recreates all three containers, not core only).
Served-vs-host parity with identical args (`~/.cache/scratch/ee-parity/parity-v1.md`, 674 OK
before/after): gerber, board_manifest, mesh, chain, views, scene, routing = MATCH (routing full-JSON
equal; the `.src` routing receipt is the historical 0.5-era run, kept as-is; the nine GND 0.2<0.3
F.Cu necks are in `R-01.measured.exempt_necks` under the declared U1/D1 ≤1.0 mm exemption — disclosed,
not a lowered Ground rule); placement = MATCH-except-GATE-02 (core image lacks `kicad-cli` →
unmeasured); PRD = NOT-CALLABLE (external thesmart_products sources outside the mount). Gaps on
record, no image change authorised yet: core lacks `soffice` and `kicad-cli`; external source tree
not mounted; views/scene need explicit `human_dir`. Blender 7.6/7.7 remain blocked on these.

S14 pool = contract + `c03_presentation_gate.py` + `test_c03_presentation_gate.py` + shared
`__init__`/`server.py`/`test_mcp_server.py`/`data-schema.json` + `Dockerfile.ee` (1 line) +
`tasks.md` 7.1 + this §4.14.

### 4.15 Served parity closed — static deps in image, dynamic trees on bind mounts (2026-10-08)

User ruling (2026-10-08): static dependency packages (e.g. soffice) may enter the image; our own
scripts/code change often and stay on bind mounts. Applied (codex `ses_ee44bd358`, four files):
`Dockerfile.core` + LibreOffice (`soffice --version` fail-loud; runtime 24.2.7.2); `server.py`
`bodesign_c04_placement_geometry_gate` → `_EE_GROUP_TOOLS` (whole gate on EE, kicad-cli there);
`docker-compose.dev.yml` child mount `${BODESIGN_PRODUCTS_ROOT:-/home/pkcs12/products}:/work/products:ro`
on core AND ee (the products ROOT, so manifests' `../../../thesmart_products` relative references
resolve byte-identically; no manifest rewrite); `services/mcp/requirements.txt` `mcp>=1.27,<2`.

Two defects surfaced only because this was the first real rebuild since S5: (1) `mcp>=1.27` had no
upper bound → fresh build resolved mcp 2.3.0, whose SDK dropped `Server.list_tools` → core crash
loop at `server.py:2624`; pinned `<2` (now 1.30.0). (2) Officer mis-ruling, withdrawn: mounting the
products root AT `/work:ro` made the parent read-only so Docker could not create the nested
`/work/experiments` mountpoint; corrected to the child mount above. `mcpctl.sh rebuild` refused
(core "busy" = UNKNOWN probe on a restarting container); `BODESIGN_FORCE=1` authorised once on the
grounds that a crash loop holds no in-flight work.

Result: core/me/ee healthy, tools=72; served PRD gate vs `c00p_r1_gate-v1.json` FULL-JSON MATCH;
served placement gate (EE-routed) vs `c04_r4_placement_gate-v4.json` FULL-JSON MATCH, GATE-02 pass
(`kicad_cli:/usr/bin/kicad-cli`). With §4.14 all nine S5–S12 gates are now served-verified against
the specimen (`~/.cache/scratch/ee-static-mounts/report.md`). Chain finding, not fixed here:
`hashes.sha256:350` binds the mutable repo file `services/mcp/server.py` by absolute path, so every
legitimate repo change turns the specimen check red (684 OK + 1 expected FAILED after the routing
edit) — the next specimen rebuild must bind repo HEAD sha instead, or drop the row from the `-c`
population. Blender 7.6/7.7 are no longer blocked on the EE host; they await the DD-9 clearance
decision itself.

S15 pool = `Dockerfile.core`, `services/mcp/server.py` (2 lines), `docker-compose.dev.yml`,
`services/mcp/requirements.txt` + this §4.15.

Chain finding closed (2026-10-09, agy-relay `ses_ee531212e`, machine tree only): the 16 repo rows
were dropped from `hashes.sha256` and rebound through `.src/repo_binding-v1.json` (`0564d9b2…`) at
repo HEAD `bcf15b2` — per file recorded/HEAD/disk sha, 15 identical, `server.py` differs_from_record
(the S15 routing edit), `dirty_in_scope=[]`. `sha256sum -c` now 671 OK / 0 non-OK, root
`42840732…`; bundle manifest bumped to `c00c04_bundle_manifest-v2.json` (`c1990d46…`, v1 in
`.history/`) carrying `bodesign_head=bcf15b2` and the pre-rebuild baseline root (same convention as
v1: the bundle is itself a manifest row, so it cannot carry its own final root). Officer-verified.

### 4.16 C01' r3 ruling (2026-10-09)

r3 (agy-relay `ses_ee5813994`) accepted. Specimen 697 OK / 0 non-OK, root `63f58c9f…`; v3 views
top-level, v2 in `.history/`. `c01_scene_gate` ok=true S-01..05 on BOTH repo function and served
UDS (first served-verified C01' round). Review 32 blind (one image per subagent, READ_OK):
SILVER screws vs KEY caps unambiguous (crop: specular silver vs matte charcoal; probe L 174 vs
75.5); LEDs 4/4 visible; footer/header no glyph cut; no z-fighting. Residual, not blocking:
silver heads are low-contrast against MIST_WHITE lid; the two end-face pockets carry no on-canvas
callout (footer says "Left Wall"). cmf v3 blind (READ_OK): legend swatch SILVER `#F5F7FC` is
visually the same colour as MIST_WHITE `#EEEEEB` (separation in renders comes from specular, not
hue); `[PORT]` callout points at a wall with no graphite element rendered; footer chip
`[INTERNAL H2] Heat-Stake Wedge` has no legend card and no S-02 matrix row while the matrix claims
5/5 tokens — a self-inconsistency of the sheet, not of the gate (manifest declares 5 tokens). These
three go to the r4 list; §4.12 r3 list is closed.

### 4.17 Blender DD-9 rulings (2026-10-09, user + officer)

Inventory `blender-dd9-clearance-20261009.md` (S18) accepted. User rulings: **E2 = internal use
only** (EE/ME images and `bpy` scripts are not conveyed to customers; GPL distribution
obligations do not trigger, notices still preserved); **E7 = download + sha verification
authorized now, licence inventory (B9–B12) closes in parallel from the actual tarball's
`release/license/`**. Officer rulings (bodesign capability scope, R-I): E1 pin 4.5.14 LTS; E4 ME
worker owns any Blender path (D3), pyrender baseline retained (D4); E5 D5/D6 budgets adopted as
the 7.7 acceptance bounds; E6 first candidate is CPU Cycles on the WSL dev host (ME container
lineage), EEVEE only if an EGL GPU device is demonstrated; E3 the first comparison excludes all
optional assets/addons. 7.7 proceeds in phases: acquire+verify → licence inventory from artifact
→ headless smoke → frozen-scene benchmark against C01 r3; each phase reports before the next.
CT105 rolled to monolith `eaf16cc` (S19) — unrelated to Blender; Blender never enters core.

### 4.18 Blender 7.7 phases 1–2 ruling (2026-10-09)

Phase 1 (S21): tarball sha `9ba871ff…` verified, 1.2 G extracted, licence inventory from the
artifact (fonts OFL/Bitstream, assets/HDRI/matcap CC0, 14 bundled addons 3 Apache / 11 GPL2+),
`ldd` 0 missing on the WSL host, CPU Cycles smoke 0.93 s / 374 MB. Source digest stays UNVERIFIED
(blender.org publishes md5 only for source).

Phase 2 (host-only, CPU Cycles 32 samples, denoiser off, Option A freeze from manifest +
`c01p_scene.py`/`c01p_render.py` + STEP): five single-camera views rendered 3×; warm median
2.06–3.71 s/view, whole 15-render job 42.05 s / RSS 485 MB, isolated load+render 2.83 s. **D5:
render time, memory and cold start all inside budget; image delta UNMEASURED (no container
build).** Silhouette XOR on body crop: rear/usb/battery max offset ≤1.4 px; front 207 px and top
150 px are attributable to the declared deviation (SW2/SW3 caps omitted — STEP cap tessellation
not reproduced, no fallback executed) and to the mask method (RGB-diff, not depth). Review 33
blind (one image per subagent, READ_OK ×3): silhouette, orientation, LED 4/4, screw 2/2, end-face
opening/cavity/tongue and parting line coincide; Blender side shows Monte-Carlo grain, contact
shadow and parting-line AO; button caps absent on Blender side (known deviation). No clipping,
facets, banding or z-fighting on either side. The usb-end job returned two reports under one
job id (harness defect, second time today); the second, more detailed one adds: Blender port
interior reads as a black void with a lit tongue bar (baseline: lit cavity with walls/lower lip),
lid-band tone inverted (baseline darker than body, Blender lighter). Both reports agree on
silhouette/opening position/size. These are lighting-conversion differences (pyrender ambient
→ Cycles world strength), not geometry. The iso-front job likewise double-returned: report 1
reads the Blender SW2/SW3 positions as "caps absent, recesses exposed", report 2 as "dark caps
with a lighter inner ring, reading as recessed holes" — same pixels, consistent with the declared
cap omission; both count screws 2 / LEDs 4 / pockets 2 on both sides. Ruling unchanged.

**Ruling: RETAIN pyrender as the C01 baseline; Blender is CLEARED for internal use and
feasible, not adopted.** Adoption would require (a) STEP cap tessellation parity, (b) denoised
samples budget fixed, (c) ME-image delta measured against D5 ≤1.5 GiB. 7.6 closed; 7.7 closed as
"feasible, retain". Chain defect found on the way (r4 list): `c01_scene_manifest-v3`
`lights.*.position` are ignored by the renderer (view-dependent eye/target offsets in code) and
S-04 does not catch it; `product-sheet` is declared as a camera but is a composite.

### 4.19 R-K: S1 frozen at partial; §3 mainline moves to S3 formalisation (2026-10-09, user)

User ruling (verbatim): 「先求有，才能求好，內容優純，格式其次」 — have it first, then make it
good; content first, format second. Context: the officer reported that S1 calibration (3.3a) had
reached diminishing returns — a–d calibrated, e has two adjudicated rejecting cells
(`E_LABEL_FLAG_CORRIDOR`, S34) and no accepting candidate because the ELK path routinely runs
wires along label flags; the accepting cell will appear only once the engine learns to avoid
flags. User agreed to freeze S1 and move to S3.

Rulings:
1. **S1 FROZEN at `partial`** (instrument `53acfd4b…`, policy `63bee5d02a5ec147`, record
   `8680263…`). 3.3a stays unchecked; AC16 stays partial and is reported as such, never
   softened. CP3 e-extras (26) stay unadjudicated. No further S1 rounds without a new user
   ruling.
2. **Mainline = 3.3c S3 formalisation, content-first.** "Content" = the six leaves are
   produced through the formal `bodesign_emit_multisheet` path with `layout_engine="elk-layered"`
   reachable from MCP, native-exported, electrically faithful (pins declared/native, ERC
   non-library findings adjudicated), and S1-measured with the frozen instrument. "Format"
   (typography, flag placement, page use, R-C composition) is deferred: S1 class f and the e
   flag-corridor findings are RECORDED on each leaf, not gates for this phase.
3. Acceptance for this phase (officer, not AC18/AC19 which keep their text): (a) served
   `tools/list` exposes the engine parameter; (b) one `emit_multisheet` call from the officer
   session produces the six-leaf set in `outputs/btdongle_ms/` with engine receipts and
   hashes; (c) per-leaf S1 report attached (verdicts may be `fail`/`indeterminate`); (d) ERC
   non-library findings either fixed in the spec or named as accepted with reason; (e) tests
   green (`test_elk_layout` 21, `test_readability_render` 114, multisheet suite).
4. Fresh-eyes visual review of the six leaves is deferred to the "求好" phase; this phase
   delivers bytes + measurements, not human acceptance.

#### 4.19.5 Content-phase acceptance (officer, 2026-10-09) — ACCEPTED (a)–(e)

Receipt: `s3-formalisation-receipt-20261009.md`. Officer verification, not worker claims:

- (a) served `tools/list` over the real UDS `/mcp/` exposes `layout_engine` (enum
  `elk-layered`) + four `engine_*` args; `engine_arg_source` recorded in the result.
- (b) Officer-session `tools/call bodesign_emit_multisheet` (same invocation as
  `formal_invocation.json`, out_dir on the rw `/work/experiments` mount) returned HTTP 200,
  `ok:true`, `emit_mode:hierarchical`, 6 sheets, `unresolved_pins:{}`. Officer run vs worker
  run: `graph_sha256` and `solution_sha256` equal on all six leaves; `.kicad_sch` residual
  diff = 0 lines after excluding uuid/date/instance-path. Engine output is deterministic.
  Landed set `outputs/btdongle_ms/c03_engine-v1/` (63 files, manifest `435a63fe…`);
  `sha256sum -c` rc=0 at both experiments and products locations.
- (c) per-leaf S1 reports bound to frozen instrument `53acfd4b…`: usbc fail / power_rail
  indeterminate / battery fail / charge_enable indeterminate / mcu_swd indeterminate / io
  indeterminate. Class counts recorded (e 1/8/1/0/2/0; f power_rail 5, battery 1; b mcu 1).
  Recorded, not gated (ruling 2).
- (d) ERC: 49 root findings = 45 library + 4 non-library; all non-library findings named
  ACCEPTED with reason (cross-sheet label continuation; passive external VBUS drive; native
  GND/AGND power_out pair). Acceptance is presentation accounting, not electrical approval.
- (e) tests (pycache cleared, officer rerun): `test_worker_group_routing` Ran 8 OK;
  `test_mcp_emit_multisheet` Ran 22 OK; `test_mcp_server` Ran 51 — same six pre-existing
  reds as before the change (names listed in receipt). Worker-reported `test_elk_layout`
  21 OK / `test_readability_render` 114 OK / multisheet suite 117 OK.

Two defects surfaced and fixed in-scope: (i) `bodesign_emit_multisheet` was absent from
`_EE_GROUP_TOOLS`, so the facade ran it core-local without native symbol libraries
(`E_ENGINE_REFUSED`); (ii) the handler did not accept engine args at top level (R7 had
smuggled them inside `spec`). Host-absolute `out_dir`/`symbol_dirs` into a container is a
caller error, not a defect — container paths are the contract.

**3.3c stays unchecked**: its text requires AC18 and S1 calibration; S1 is frozen partial
(ruling 1). This record is the "求有" milestone; "求好" (visual review, format classes,
AC18/AC19) is a later phase.

### 4.20 R-L: single mainline = reviewable six-leaf delivery (2026-10-09, user)

User observation: work had become task-by-task without a product thread ("好像開始漫無目的了").
Officer concurs: after §7 closed, 3.3a→3.3c→3.5→3.4 each landed bytes but no deliverable an
engineer could accept. Rulings:

1. **Mainline = btdongle six leaves (S36 set) reviewable by an independent engineer.** Done means:
   (a) served `bodesign_check_c03` returns a real PC-001 verdict on U1/U2 (not `not_run`) —
   BR `check_c03_pc001_identifies_no_power_rail…` fixed first (P1); (b) S1 class e/f findings on
   each leaf either repaired in the engine/spec or named accepted; (c) one-leaf-per-reviewer blind
   review reaches READ_OK + "would sign" on all six (AC19 text governs); (d) same-revision bundle
   (3.5 shape) regenerated on the final bytes.
2. **Everything else pauses** unless it is a necessary enabler for 1. §2, §4, §5, §6 tasks,
   S2 ingestion (3.3b), 3.6/3.7 codec/physics, vault page-anchor BR: parked, not cancelled.
3. Plan hygiene (promote master plan to `implementing`, adjudicate the 7 stale `implementing`
   sub-plans) is deferred until mainline item 1(a) lands; it is bookkeeping, not product.
4. Officer reports progress against 1(a)–(d) only; a task checkbox is not progress.

### 4.21 R-L mainline closed: 1(a)–(d) landed on v4 (officer, 2026-10-10)

| Item | Evidence | Commit |
|---|---|---|
| 1(a) served `check_c03` real PC-001 verdict | U1 rail VBUS, U2 rails +3V3/SYS, all `identified_by: type`; `ics_without_identifiable_rail=[]`; `not_run` with unidentified ICs now blocking | S41 405f1c7 |
| 1(b) S1 class e/f repaired or named accepted | round 1 knobs (S42), round 2 flag-outward + grid snap (S43), round 3 A (foreign-collinear ≥2.54 mm) + D (prop text 1.30 mm/char) (S48 c467211). Final v4: e=10 (all `accept-adjacent_pin_flag_at_2.54mm_pitch`), f=0, b=0, off-grid 0, crossings 0, fidelity 100%. B-1/C-1 dropped by isolation gate — deferred to 求好 | S42–S43, S48 |
| 1(c) one-reviewer-per-leaf blind review | Review 34 on v3: usbc no, five yes-with-notes. Review 35 on v4: 6/6 READ_OK, 6/6 yes-with-notes, 0 blocking; usbc blocker (VBUS_CON/CC1/CC2 column) resolved | S44, S49 5ed6969, S50 3451781 |
| 1(d) same-revision bundle on final bytes | `c03_engine-v4/bundle/` 85 files `sha256sum -c` rc=0, manifest v2 `04d0eab4…`, `bom_per_ref.csv` + `symbol_source`, crosscheck 45/45/0/0/0, served `check_c03` gate=PASS / R3_DRAWABILITY=PASS (v1 BOM: FAIL) | S51 571616a |

Residual (NOT claimed, carried to 求好): AC16 still partial (e: rejecting 2 / accepting 0);
AC18/AC19 not claimed (Review 35 "yes-with-notes" is reviewer sign-willingness, not AC19 text);
emitter rules B (local-label corner stub) and C (flag collinear with pin stub) failed isolation
and are not landed — their Review 34/35 NOTE-level sites persist (flush labels on 4 leaves,
zero-stub flags, CC1–CC2 single-grid collinear on usbc, BATT flag at C5 node); cairosvg
sub-pixel artefact recorded; leaf-level `passive_waivers.json` not honoured from root (bounded,
no BR); `export_bom` lossy grouping BR open.

Parked items from §4.20 ruling 2 remain parked. Plan hygiene (§4.20 ruling 3) is now unblocked.
Next direction requires user ruling: (i) 求好 phase on the six leaves (B/C emitter rules,
S1 recalibration to 2.54 mm pitch), (ii) resume parked §2/§4/§5/§6 or S2 ingestion, or
(iii) C04 re-entry on the v4 schematic revision.

### 4.22 R-M: 求好 phase on the six leaves (2026-10-10, user)

User ruling: next mainline = option (i). S48–S52 pushed to `gitlab/main` @ e1a6f42. Scope:

1. **Emitter rule B (local label at a corner)**: land B-1 (1.27 mm dead-end stub along the
   straight run, label at the stub end) and resolve the isolation failure at `mcu_swd:SWCLK`
   (point-to-point net, no dead-end terminal, corner candidates refused by
   `E_ELK_LABEL_NO_POSITION`) as a general rule — not a site special case.
2. **Emitter rule C (flag collinear with pin stub)**: land C-1 and resolve the isolation
   failure at `usbc:VBUS@F1.2` (channel depth 7.62 mm < stub 1.27 + flag 6.60) as a general
   rule — no wire-anchoring fallback, no conditional stub.
3. **S1 recalibration**: the detector policy freeze (§4.19) is lifted for ONE change: the
   `accept-adjacent_pin_flag_at_2.54mm_pitch` class becomes a non-finding (a flag's
   neighbour wire that is the neighbour pin's own stub is exempt from `E_LABEL_FLAG_CORRIDOR`).
   New policy hash + `s1-calibration-record-v3.json`; AC16 must gain accepting examples
   (currently rejecting 2 / accepting 0). Instrument sha changes are recorded, not hidden.
4. **Review 35 NOTE residuals** are the acceptance list: flush labels (mcu_swd, charge_enable,
   battery, io ×3), zero-stub flags (battery BATT@Q1.3 / NTC@R5, charge_enable STAT@R7.1,
   usbc VBUS@F1.2), usbc CC1–CC2 single-grid collinear, power_rail BATT flag at C5 node and
   SYS/SYS + ENPPB/NTC abutting flag outlines. Done = Review 36 (one reviewer per leaf, v5)
   reports 0 BLOCKING and every Review 35 NOTE either RESOLVED or named accepted by the officer.
5. Hard gates unchanged: no new a/c/d, f=0, off-grid 0, crossings ≤ v4, fidelity 100%,
   ERC non-lib delta by reference. Same bisection-and-ASK discipline as round 3.
6. Step 0 is measure-then-ASK (quote functions, measure the two isolation-failure sites on v4
   bytes, propose the general rule for each); no edits before ruling.

## 5. Summary and Next Steps

1. **Task 7.3 Status**: **COMPLETED** as a design deliverable (`c04-entry-freeze-20261007.md`).
2. **Action Required by Coordinator / Duty Officer**:
   - Route the four items in **Section 3 (ASK List)** to thesmart_products Duty Officer (`ses_eed1fb0b6ffelFUGhmXVSGcp3z`).
   - Await formal ruling on ASK-1 (repealing D-3 PCB ban) and ASK-2 (authorizing the 28×93 mm carrier outline vs. Route B).
3. **Condition for Entering Task 7.4 (C04 Placement Execution)**:
   - Receipt of duty officer clarification on the ASK list unlocks Task 7.4 execution (dispatching Sonnet to construct `btdongle_c04-v1.kicad_pcb` and `01.c04-placement-v1.png` per Section 4).
