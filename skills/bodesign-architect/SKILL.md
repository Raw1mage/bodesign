---
name: bodesign-architect
description: L2/L3 product requirements, system architecture, and interface constraints skill for Systems Architect.
---

# Bodesign Architect

This skill guides product requirements definition, system architecture, and interface constraint freezing.

## 1. Input Requirements

Before beginning system architecture, collect target product specifications.

- Ingest customer functional requirements and target performance metrics.
- Record power supply voltages, battery constraints, and operating environments.
- Collect mechanical form factors, user interface needs, and external connectors.

## 2. Core Architecture Workflow

Define system architecture and freeze downstream physical constraints.

- Author the product requirements document outlining system vision and module boundaries.
- Define power trees and allocate current budgets across all operational states.
- Freeze connector face assignments and edge locations in Face_Layout.json.
- Generate architecture block diagrams depicting central controllers and peripheral buses.

## 3. Exit Gates

Verify requirements completeness before handing off to electrical engineering.

- Verify that the requirements specification defines all required functional attributes.
- Ensure that mechanical envelope and connector assignments contain zero conflicting dimensions.
- Read `skills/bodesign/stages/c00-prd/GUIDE.md` for detailed PRD stage criteria.
