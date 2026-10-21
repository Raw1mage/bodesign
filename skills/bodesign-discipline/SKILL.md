---
name: bodesign-discipline
description: L1 quality gates, honesty model, and Definition of Done standards for all bodesign hardware deliverables.
---

# Bodesign Discipline

This skill governs quality gates and honesty contracts across the hardware lifecycle.

## 1. Honesty Model

Hardware designs must reflect genuine engineering facts.

- Never fabricate engineering files or native CAD deliverables.
- Never set human approval flags to true in automated code.
- Mark missing tools or inputs as blocked with explicit reasons.
- List only files that exist on disk in deliverable inventories.
- Ground all component electrical claims in datasheets or vault specifications.

## 2. Definition of Done

A stage completes only when all required deliverables pass deterministic gates.

- Produce the complete required deliverable set for the active stage.
- Verify that the stage readiness gate reports dod_ok true.
- Do not treat readiness percentage 100 as complete if dod_ok is false.
- Resolve or record all open cross-stage blockers before handoff.
- Fail fast when constraints or upstream requirements are missing.

## 3. Deliverable Directory Structure

Organize stage outputs by audience and function.

- Place human deliverables at the stage root.
- Place machine deliverables and JSON bridges in 03_output.
- Place external references and SSOT inputs in 01_refs.
- Place intermediate build files and markdown drafts in 02_build.
- Never write ad-hoc folders outside this structure.

## 4. Verification Gate

Run deterministic gates before declaring completion.

- Execute the designated readiness gate for the active stage.
- Compare delivered netlists against upstream schematic intent.
- Ensure that DRC and electrical rule audits return clean pass verdicts.
- Stop execution immediately when a deterministic gate fails.
