# External specialist skills adopted per C00–C06 layer

bodesign *generates* the design and *orchestrates* mature skills for the rest
(its own EDA skills ship in `services/mcp/assets/skills/`; the per-layer `skill`
binding lives in `templates/doc_architecture.template.json` and flows into
`agent_registry`). This file records third-party skills adopted to fill the
non-EE upstream layers, with provenance and license so an externally-operated
deployment stays compliant.

## C00 — Product / PRD (ADOPTED)

- **Source:** `product-on-purpose/pm-skills` — https://github.com/product-on-purpose/pm-skills
- **License:** Apache-2.0 (commercial use OK; each `SKILL.md` carries its own
  `license: Apache-2.0` frontmatter + attribution comment, preserved on install).
- **Why:** the strongest, commercially-licensable PM-method library (65 skills,
  Triple Diamond); covers exactly C00's gap — PRD authoring, problem framing,
  prioritization tradeoffs, market/competition, persona, business-model thesis.
- **Installed subset** (curated for C00 — not all 65; measure/iterate/sprint
  tooling omitted), placed under the operator skill location `~/.claude/skills/`:
  `deliver-prd`, `define-problem-statement`, `define-prioritization-framework`,
  `discover-competitive-analysis`, `discover-market-sizing`, `foundation-persona`,
  `foundation-lean-canvas`, `develop-solution-brief`.
- **Install command (operator):**
  `npx skills install product-on-purpose/pm-skills` (or clone and copy the subset
  into your skill location). bodesign does not vendor these into the repo; it
  orchestrates them, the same way it orchestrates `kicad`/`kidoc`.
- **Boundary:** pm-skills supply the *consultant method*; bodesign keeps the
  RockBox-derived PRD *output structure* and remains the requirement-contract
  owner (C00). Product direction stays a human decision (no fabricated scores —
  these skills explicitly refuse to invent missing data, matching bodesign's
  no-fallback rule).

## C02 — Mechanical / CAD (A+B LANDED — build123d STEP backend; Docker dep deferred)

> **Update:** the recommended A+B integration is now implemented. `export_c02_step`
> builds a real `Enclosure.step` via build123d/OCP from the same constraints as the
> OpenSCAD path (`_build_enclosure_part`), toolchain-gated: kernel + explicit dims →
> real STEP (`step_exported`, `draft_unapproved`); no kernel / no dims →
> `step_export_unavailable`, never a fake STEP. Tests cover both paths (T7 skip-guarded
> on clones without the kernel; V5 patches the kernel absent). **build123d is
> dev-installed only — NOT in `services/mcp/requirements.txt` or the Docker image yet**
> (the ~400 MB OCP/vtk dependency is a separate operational decision), so production
> runtime stays honestly gated until approved. Original evaluation retained below.



- **Source:** `earthtojake/text-to-cad` — https://github.com/earthtojake/text-to-cad
  (its CAD backend is **build123d** on OpenCASCADE/OCP).
- **License:** MIT (text-to-cad); build123d is Apache-2.0 — both commercial-OK.
- **Why:** real text/image → CAD with **STEP primary output** — fills C02's STEP
  gap (`bodesign_c02_export_step` returns `step_export_unavailable` today).
- **PoC result (2026-06-07):** `poc/c02_build123d_step_poc.py` built a parametric
  enclosure shell (outer box, hollowed cavity, 4 mounting standoffs with holes)
  from the **same constraint inputs C02 already holds** (board outline, wall,
  clearance, internal height) and exported a **valid 61 KB `ISO-10303-21` STEP in
  ~0.1 s** via `build123d 0.10.0` / `cadquery-ocp 7.8`. Verified the header +
  size; no fake output. So build123d→STEP is feasible and fast.
- **Recommended integration (follow-up slice, needs your go):**
  1. Add a `build123d` backend to `export_c02_step`: when build123d imports AND a
     constraint/geometry spec exists, generate a real `Enclosure.step`; otherwise
     keep the existing fail-fast `step_export_unavailable` (same gate shape — no
     contract change). This finally closes C02-T6 when the kernel is present.
  2. A parallel `generate_c02_build123d` (constraint→geometry) mirroring
     `generate_c02_openscad`. OpenSCAD path stays for STL/printing; build123d adds
     STEP for vendor/ME handoff. **Coexist, don't replace.**
  3. **Operational cost to weigh:** build123d pulls cadquery-ocp + vtk (~heavy,
     hundreds of MB). It is installed in the dev venv for the PoC but is **NOT yet
     in `services/mcp/requirements.txt` or the Docker image** — runtime stays
     honestly gated until you approve adding the dependency.
- **DFM caveat:** text-to-cad's DFM is only a SendCutSend format check, so the C02
  DFM/manufacturing consultant remains self-built (`c02-mechanical-enclosure-consultant`).

## C01 — Industrial Design / CMF (NO EXTERNAL SOLUTION — self-build)

- Searched the community (GitHub `SKILL.md`, awesome-design lists, claude-design,
  canvas/frontend-design): every "design" skill found is graphic/UI/HTML-artifact
  design, **none is industrial/product design (form, CMF, enclosure aesthetics,
  moodboard for physical products)**. This confirms the earlier gap-audit finding.
- **Decision:** keep and strengthen the self-built
  `skills/c01-industrial-design-requirements`, seeded from the RockBox C01
  shipped-product document architecture.
