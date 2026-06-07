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

## C02 — Mechanical / CAD (CANDIDATE — PoC pending)

- **Source:** `earthtojake/text-to-cad` — https://github.com/earthtojake/text-to-cad
- **License:** MIT (commercial OK).
- **Why:** real text/image → CAD with **build123d/OCP backend, STEP primary
  output** (enclosures/brackets/standard parts) — could fill C02's STEP-export
  gap (`bodesign_c02_export_step` currently returns `step_export_unavailable`).
- **Status:** evaluate via PoC against the existing OpenSCAD path before adopting.
  DFM coverage is limited (SendCutSend format check only), so the C02 DFM
  consultant remains self-built.

## C01 — Industrial Design / CMF (NO EXTERNAL SOLUTION — self-build)

- Searched the community (GitHub `SKILL.md`, awesome-design lists, claude-design,
  canvas/frontend-design): every "design" skill found is graphic/UI/HTML-artifact
  design, **none is industrial/product design (form, CMF, enclosure aesthetics,
  moodboard for physical products)**. This confirms the earlier gap-audit finding.
- **Decision:** keep and strengthen the self-built
  `skills/c01-industrial-design-requirements`, seeded from the RockBox C01
  shipped-product document architecture.
