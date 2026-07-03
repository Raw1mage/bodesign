# Project Requirements

Status: generated-from-answer-state
Project: {missing}
C00 readiness: 99% (blocked)
Human approved: false

This Markdown is generated from `C00-PRD/answer_state.json`. Missing, drafted, external-needed, blocked, and accepted-risk fields remain visible; no hidden defaults are applied.

## 1. Company Vision & Business Strategy

Section ID: `s01_business_strategy`
Section state: `answered`

### Fields
- `target_customer`: Internal E2E validation (bodesign pipeline proving); persona = maker needing a USB-powered desk LED bar
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C06
- `problem_statement`: Prove bodesign compose-path can carry a real small board from PRD to Gerber with deterministic gates; product pretext: simple USB LED illumination without firmware
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C06
- `business_goal`: E2E pipeline validated with evidence at every stage (ERC/DRC/SI/Gerber)
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C06
- `success_metric`: All stage gates pass or fail loudly with structured evidence; Gerber package renders correctly
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C06
- `market_or_use_context`: Desk/bench use, indoor, 5V USB power only
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C06

### Handoff Targets
- C06

## 2. Project Overall

Section ID: `s02_project_overall`
Section state: `answered`

### Fields
- `product_summary`: USB-C powered 4-LED constant-current light bar: USB-C 5V in, input protection (polyfuse + TVS), linear LED driver with resistor-set current, on/off slide switch
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C05, C06
- `primary_use_cases`: Bench illumination; always-on when plugged; no dimming, no MCU, no firmware
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C05, C06
- `operating_environment`: Indoor, 0-40C ambient, powered from USB-C 5V 500mA budget
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C05, C06
- `package_scope`: PCB assembly only (bare board E2E validation); no enclosure in this run
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C05, C06
- `major_exclusions`: No MCU/firmware, no dimming/PWM, no battery, no RF, no enclosure
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C05, C06

### Handoff Targets
- C03
- C05
- C06

## 3. Project Objectives

Section ID: `s03_project_objectives`
Section state: `answered`

### Fields
- `functional_objectives`: F1: illuminate 4 white LEDs at 60mA total from USB 5V. F2: survive reverse/ESD events at connector (TVS). F3: overcurrent protection via polyfuse
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C05, C06
- `performance_objectives`: P1: LED string current 60mA +/-10% at 5.0V input. P2: board input current < 100mA. P3: no component above 60C at 25C ambient
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C05, C06
- `quality_objectives`: ERC clean; DRC copper+unconnected = 0; SI check pass on power rail; Gerber renders without missing layers
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C05, C06
- `acceptance_criteria`: All four verification gates (ERC, DRC, SI, Gerber preview) produce pass evidence artifacts on disk
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C05, C06

### Handoff Targets
- C03
- C05
- C06

## 4. System Architecture

Section ID: `s04_system_architecture`
Section state: `missing`

### Fields
- `subsystems`: Power input (USB-C receptacle, CC pull-downs), protection (polyfuse, TVS diode), LED driver (linear constant-current), load (4x white LED), user control (slide switch)
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `main_components`: USB-C 16P receptacle (power-only, CC1/CC2 5.1k pull-downs), PTC polyfuse 500mA, TVS diode 5V SMA, NPN/resistor linear current sink or AL5809-ish 2-pin CC regulator, 4x 0603 white LED, slide switch SPST, decoupling 100nF+10uF
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `power_flow`: USB VBUS 5V -> polyfuse -> switch -> LED string anode; return via constant-current sink to GND; TVS clamps VBUS at connector
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `data_flow`: None (no digital signals; CC pins are static resistor terminations)
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `control_flow`: Manual slide switch only
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `interfaces`: {missing}
  - state: `missing`
  - owner: `user`
  - source: `unspecified`
  - handoff_targets: C03, C04, C05, C06

### Handoff Targets
- C03
- C04
- C05
- C06

## 5. ID / Mechanical Requirements

Section ID: `s05_id_me_requirements`
Section state: `answered`

### Fields
- `industrial_design_intent`: None for this E2E run (bare PCB) _[accepted-risk]_
  - state: `accepted-risk`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C04
- `dimensions`: Target board 60x20mm 2-layer
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C04
- `mounting`: Two M3 mounting holes at board ends
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C04
- `connectors`: USB-C receptacle on short edge; slide switch on top edge
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C04
- `display_or_ui`: LEDs themselves are the UI; no display
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C04
- `environment`: Indoor desk use only
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C04
- `assembly_constraints`: Single-side SMT preferred
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C04

### Handoff Targets
- C01
- C02
- C04

## 6. Electrical Requirements

Section ID: `s06_electrical_requirements`
Section state: `answered`

### Fields
- `compute`: None - no MCU by design
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `power_input`: USB-C 5V, default USB power (500mA max), CC Rd 5.1k advertises sink
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `power_budget`: Total < 100mA @5V (0.5W); LED string 60mA; losses in linear sink
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `battery_or_charging`: None
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `memory`: None
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `connectivity`: None (power-only USB)
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `sensors`: None
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `interfaces`: USB-C power sink only; CC1/CC2 5.1k to GND; SBU/data floating
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `compliance_targets`: None for E2E validation run (would be CE/FCC unintentional radiator for product) _[accepted-risk]_
  - state: `accepted-risk`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `key_parts_or_references`: Generic: USB4085-class USB-C power connector, 0603 LEDs, SOT-23/SOT-89 current regulator; exact MPNs resolved at C03 vault stage
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06

### Handoff Targets
- C03
- C04
- C05
- C06

## 7. Software Requirements

Section ID: `s07_software_requirements`
Section state: `answered`

### Fields
- `functional_behaviors`: No software
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C05, C06
- `operating_modes`: On/Off via physical switch
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C05, C06
- `state_transitions`: None
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C05, C06
- `external_interfaces`: None
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C05, C06
- `firmware_responsibilities`: None
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C05, C06
- `logging_or_update_policy`: None
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C05, C06
- `pin_map_dependency`: None
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C05, C06

### Handoff Targets
- C05
- C06

## 8. Role & Responsibility

Section ID: `s08_roles_responsibility`
Section state: `answered`

### Fields
- `owner_matrix`: bodesign AI executes all layers; user is sole approver (E2E validation context)
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `decision_owner`: user (pkcs12)
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `review_owner`: user (pkcs12)
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `external_vendor_roles`: None
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `approval_owner`: user (pkcs12)
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06

### Handoff Targets
- C01
- C02
- C03
- C04
- C05
- C06

## 9. Assumption & Constraints

Section ID: `s09_assumptions_constraints`
Section state: `answered`

### Fields
- `assumptions`: KiCad 9 std libs contain usable symbols/footprints for all parts; host kicad-cli available for ERC/DRC
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `constraints`: No vault datasheets pre-loaded (G4 cold start is part of the test); deterministic tools only for verification
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `risks`: Symbol/footprint availability in std libs; freerouting success on 2-layer board; SI model defaults for LED nets
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `dependencies`: KiCad 9.0.9 host toolchain; ee worker for container-path tools if used
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06
- `accepted_gaps`: No thermal chamber test, no EMC lab - pre-compliance analysis only _[accepted-risk]_
  - state: `accepted-risk`
  - owner: `user`
  - source: `user`
  - handoff_targets: C03, C04, C05, C06

### Handoff Targets
- C03
- C04
- C05
- C06

## 10. Project Management

Section ID: `s10_project_management`
Section state: `answered`

### Fields
- `milestones`: Single-session E2E: PRD -> schematic -> layout -> Gerber
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `deliverables`: C00 PRD md, C03 .kicad_sch + ERC report, C04 .kicad_pcb + DRC report, gerbers/ + preview png, findings.md
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `review_gates`: ERC gate, DRC gate, SI gate, Gerber preview visual check
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `approval_process`: User reviews findings.md at end of run
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `change_control`: Plan-builder spec validation/prd-to-gerber-e2e tracks scope
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06

### Handoff Targets
- C01
- C02
- C03
- C04
- C05
- C06

## 11. Project High-level Schedule

Section ID: `s11_schedule`
Section state: `answered`

### Fields
- `target_dates`: Same-day E2E run (2026-07-03)
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `dependency_order`: C00 -> C03 -> C04 -> fab outputs
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `long_lead_items`: None (virtual run)
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `review_windows`: End of run
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `external_lead_times`: None
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06

### Handoff Targets
- C01
- C02
- C03
- C04
- C05
- C06

## 12. Company & Vendor Team Roster

Section ID: `s12_team_roster`
Section state: `answered`

### Fields
- `internal_contacts`: user pkcs12; bodesign AI agents C00-C06
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `external_vendors`: None
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `reviewers`: user pkcs12
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `approval_contacts`: user pkcs12
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06
- `escalation_path`: Blockers surface via orchestration spine return_blocker
  - state: `answered`
  - owner: `user`
  - source: `user`
  - handoff_targets: C01, C02, C03, C04, C05, C06

### Handoff Targets
- C01
- C02
- C03
- C04
- C05
- C06
