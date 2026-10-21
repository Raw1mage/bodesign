---
name: bodesign-verify
description: L2/L3 hardware verification, simulation, and adversarial analysis skill for Verification Adversary.
---

# Bodesign Verify

This skill guides adversarial hardware verification, circuit simulation, and signal integrity testing.

## 1. Input Requirements

Before beginning verification, verify that upstream electrical and layout deliverables exist.

- Read schematic netlists, bill of materials, and routed board layouts.
- Ingest design requirements, operating power levels, and signal timing targets.
- Verify that reference schematics and component datasheets are accessible in 01_refs.

## 2. Core Verification Workflow

Execute independent simulations and cross-evaluations against engineering models.

- Execute SPICE simulations on power converters and analog filters using `bodesign_simulate`.
- Execute signal integrity analysis on high-speed traces using `bodesign_si_check`.
- Cross-verify component connections against known-good reference designs.
- Run electromagnetic compatibility scans to detect high-frequency radiated loops.

## 3. Exit Gates

Verify that all electrical and thermal metrics satisfy design limits.

- Verify that simulated ripple and transient voltages stay within component ratings.
- Verify that signal line impedances meet target transmission line constraints.
- Issue an independent verification ledger with explicit pass or fail findings.
- Read `skills/bodesign/stages/c06-verify/GUIDE.md` for detailed verification criteria.
