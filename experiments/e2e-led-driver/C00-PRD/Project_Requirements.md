# Project Requirements

Status: scaffold-only

This file is a blank C00 source scaffold. Fill content through C00 consultant intake; do not treat placeholders as answered requirements.

## 1. Company Vision & Business Strategy

Section ID: `s01_business_strategy`

State: `missing`

Required fields:
- `target_customer`: {missing}
- `problem_statement`: {missing}
- `business_goal`: {missing}
- `success_metric`: {missing}
- `market_or_use_context`: {missing}

Consultant prompts:
- Who is the first real customer or user for this product?
- What business outcome proves this product is worth building?
- Which claim must the PRD avoid until customer or legal approval?

Handoff targets:
- C06

## 2. Project Overall

Section ID: `s02_project_overall`

State: `missing`

Required fields:
- `product_summary`: {missing}
- `primary_use_cases`: {missing}
- `operating_environment`: {missing}
- `package_scope`: {missing}
- `major_exclusions`: {missing}

Consultant prompts:
- Describe the product in one sentence as if briefing an engineering manager.
- Where will the product be used physically and environmentally?
- What tempting feature is explicitly out of scope for this version?

Handoff targets:
- C03
- C05
- C06

## 3. Project Objectives

Section ID: `s03_project_objectives`

State: `missing`

Required fields:
- `functional_objectives`: {missing}
- `performance_objectives`: {missing}
- `quality_objectives`: {missing}
- `acceptance_criteria`: {missing}

Consultant prompts:
- Which three outcomes must be true for POC success?
- Which objective is allowed to be weak in POC but not in EVT/DVT?
- What measurable signal proves the main function works?

Handoff targets:
- C03
- C05
- C06

## 4. System Architecture

Section ID: `s04_system_architecture`

State: `missing`

Required fields:
- `subsystems`: {missing}
- `main_components`: {missing}
- `power_flow`: {missing}
- `data_flow`: {missing}
- `control_flow`: {missing}
- `interfaces`: {missing}

Consultant prompts:
- What are the required compute, sensing, connectivity, power, storage, and UI blocks?
- Which subsystem choice is already fixed by business or supply constraints?
- Which architecture decision needs evidence before schematic work begins?

Handoff targets:
- C03
- C04
- C05
- C06

## 5. ID / Mechanical Requirements

Section ID: `s05_id_me_requirements`

State: `missing`

Required fields:
- `industrial_design_intent`: {missing}
- `dimensions`: {missing}
- `mounting`: {missing}
- `connectors`: {missing}
- `display_or_ui`: {missing}
- `environment`: {missing}
- `assembly_constraints`: {missing}

Consultant prompts:
- What physical size or enclosure constraint must the electronics respect?
- Which connectors, camera, microphone, display, buttons, or LEDs are user-facing?
- What must ID/ME decide before PCB placement can be safe?

Handoff targets:
- C01
- C02
- C04

## 6. Electrical Requirements

Section ID: `s06_electrical_requirements`

State: `missing`

Required fields:
- `compute`: {missing}
- `power_input`: {missing}
- `power_budget`: {missing}
- `battery_or_charging`: {missing}
- `memory`: {missing}
- `connectivity`: {missing}
- `sensors`: {missing}
- `interfaces`: {missing}
- `compliance_targets`: {missing}
- `key_parts_or_references`: {missing}

Consultant prompts:
- Which MCU/SoC/module choices are fixed, preferred, or still open?
- What power source, battery, charging, and runtime assumptions are required?
- Which electrical interface must be correct for firmware and mechanical teams?

Handoff targets:
- C03
- C04
- C05
- C06

## 7. Software Requirements

Section ID: `s07_software_requirements`

State: `missing`

Required fields:
- `functional_behaviors`: {missing}
- `operating_modes`: {missing}
- `state_transitions`: {missing}
- `external_interfaces`: {missing}
- `firmware_responsibilities`: {missing}
- `logging_or_update_policy`: {missing}
- `pin_map_dependency`: {missing}

Consultant prompts:
- What should the product do from power-on to normal operation?
- Which behaviors belong in firmware versus app, cloud, or manufacturing tools?
- Which C03 pin or interface decisions block the FW spec?

Handoff targets:
- C05
- C06

## 8. Role & Responsibility

Section ID: `s08_roles_responsibility`

State: `missing`

Required fields:
- `owner_matrix`: {missing}
- `decision_owner`: {missing}
- `review_owner`: {missing}
- `external_vendor_roles`: {missing}
- `approval_owner`: {missing}

Consultant prompts:
- Who approves PRD, circuit, layout, FW spec, verification plan, and factory release?
- Which deliverables are bodesign-assisted versus engineer/vendor-owned?
- Who is responsible when a handoff has an unresolved assumption?

Handoff targets:
- C01
- C02
- C03
- C04
- C05
- C06

## 9. Assumption & Constraints

Section ID: `s09_assumptions_constraints`

State: `missing`

Required fields:
- `assumptions`: {missing}
- `constraints`: {missing}
- `risks`: {missing}
- `dependencies`: {missing}
- `accepted_gaps`: {missing}

Consultant prompts:
- Which assumption would be expensive if wrong?
- What evidence is missing but required before EVT/DVT?
- Which gap can proceed as accepted risk and which blocks handoff?

Handoff targets:
- C03
- C04
- C05
- C06

## 10. Project Management

Section ID: `s10_project_management`

State: `missing`

Required fields:
- `milestones`: {missing}
- `deliverables`: {missing}
- `review_gates`: {missing}
- `approval_process`: {missing}
- `change_control`: {missing}

Consultant prompts:
- Is the immediate milestone POC, EVT, DVT, or production release?
- Which artifact must be approved before money is spent externally?
- How should requirement changes be handled after schematic kickoff?

Handoff targets:
- C01
- C02
- C03
- C04
- C05
- C06

## 11. Project High-level Schedule

Section ID: `s11_schedule`

State: `missing`

Required fields:
- `target_dates`: {missing}
- `dependency_order`: {missing}
- `long_lead_items`: {missing}
- `review_windows`: {missing}
- `external_lead_times`: {missing}

Consultant prompts:
- What date matters, and what happens if it slips?
- Which external lead time is most likely to dominate the schedule?
- Which downstream team must start first after PRD approval?

Handoff targets:
- C01
- C02
- C03
- C04
- C05
- C06

## 12. Company & Vendor Team Roster

Section ID: `s12_team_roster`

State: `missing`

Required fields:
- `internal_contacts`: {missing}
- `external_vendors`: {missing}
- `reviewers`: {missing}
- `approval_contacts`: {missing}
- `escalation_path`: {missing}

Consultant prompts:
- Who will receive each handoff package?
- Which vendor or lab must be contacted before the next milestone?
- Who has final authority to approve the PRD?

Handoff targets:
- C01
- C02
- C03
- C04
- C05
- C06
