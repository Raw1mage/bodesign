---
name: bodesign-tools
description: L4 command-line execution syntax, landing verbs, and analyzer engine interfaces for bodesign.
---

# Bodesign Tools

This skill defines command-line verbs, analyzer scripts, and error codes for hardware tooling.

## 1. Landing Gate Execution

Execute local deterministic landing verbs through the Python runner.

- Run gate verbs directly using Python.
- Format command as: `python3 skills/bodesign/scripts/gate.py <verb> --repo <abs-project> [--arg k=v]`
- Use `c00_readiness` through `c06_readiness` to evaluate individual stage gates.
- Use `package_readiness` to evaluate the complete multi-stage project state.

## 2. Hardware Engine Scripts

Run specialized analysis engines for deep deterministic verification.

- Run schematic analysis: `python3 skills/bodesign/engines/kicad/scripts/analyze_schematic.py --project-root <dir>`
- Run PCB layout analysis: `python3 skills/bodesign/engines/kicad/scripts/analyze_pcb.py <board.kicad_pcb>`
- Run reference board cross-verification: `python3 skills/bodesign/engines/kicad/scripts/cross_verify.py`
- Run manufacturing release gate: `python3 skills/bodesign/engines/kicad/scripts/fab_release_gate.py`

## 3. Remote MCP Endpoints

Call native MCP tools for heavy CAD operations when the server is reachable.

- Run `bodesign_layout_drc_gate` to verify clearance and unrouted nets.
- Run `bodesign_prd_bom_crosscheck` to verify netlist fidelity against the BOM.
- Run `bodesign_simulate` to execute SPICE circuit simulations.
- Run `bodesign_si_check` to verify signal impedance and transmission lines.

## 4. Common Error Codes

Handle structured error codes explicitly.

- `REFS_SSOT_MISSING`: Ingest upstream reference materials into 01_refs before continuing.
- `UPSTREAM_CONSTRAINT_MISSING`: Freeze mechanical or electrical constraints in the upstream stage first.
- `CONNECTOR_FACE_CONFLICT`: Keep connector placements strictly within the assigned board face.
- `DOD_TRACEBACK_FAILED`: Ensure every deliverable traces to an authoritative reference anchor.
