# C01 ID Visual Source Workflow

## Role

C01 is the visual source layer derived from C00. It does not rediscover product requirements and does not replace a human industrial designer. It converts C00's visual, human-interface, exposed-component, and brand intent into a Rockbox-style ID package: `Ai file`, `CMF`, and `Display UI/UX`, plus machine-readable constraints for C02/C03/C04/C05.

## Inputs From C00

- §1/§2: target user, product context, business/brand direction.
- §3: milestone and success level; whether ID output is rough POC or near-product direction.
- §5: industrial/mechanical requirements, dimensions, mounting, display, buttons, connectors, environment, assembly context.
- §6: exposed electrical parts: camera, mic, LED, USB-C, antenna, sensors, display, buttons, power indicators.
- §7: display/UI/status/interaction behavior that must appear in visual source.
- §9-§12: assumptions, constraints, risks, schedule, owner, and approval context.

## Workflow Loop

1. Read C00 PRD state and C01 readiness.
2. Extract visual/interface requirements into `Interface_Constraints.json`.
3. Ask only C01-specific visual questions when C00 data is insufficient.
4. Draft source carriers under the original Rockbox deliverable slots: `Ai file/Ai_Source.svg`, `CMF/CMF_Direction.md`, and `Display UIUX/Display_UIUX_Mock.svg` from C00-derived intent.
5. Keep AI-drafted visual decisions marked as draft until human/ID approval.
6. Recompute C01 readiness and downstream blockers.
7. Emit `Handoff_to_ID_Designer.md` for human designer continuation.

## Tool vs Skill Boundary

### MCP Tool Candidates

- `bodesign_c01_extract_visual_requirements`: read C00 state and produce normalized visual/interface requirements.
- `bodesign_c01_scaffold`: create the C01-ID folder and blank target artifacts.
- `bodesign_c01_emit_sources`: generate deterministic SVG/Markdown/JSON drafts from template + answers.
- `bodesign_c01_readiness`: score artifact completeness and downstream constraint gates.

### AI Workflow Skill

- Choose visual language candidates from C00 intent.
- Draft CMF mood and prompt pack.
- Explain visual tradeoffs and downstream consequences.
- Ask human/ID only the missing visual decisions, not generic product questions.
- Keep aesthetic claims and final design decisions as human-approved gates.

### Human / ID Designer

- Final form language, proportions, CMF, brand fit, and visual quality.
- Final Illustrator/Figma/CAD source and design sign-off.
- Physical sample/material/color approval.

## Output Package

The MVP output must be usable as a Rockbox-like C01 package: it may be Markdown/JSON/SVG instead of final Adobe Illustrator/CMF boards, but it must contain substantive first-pass content for the original `Ai file`, `CMF`, and `Display UI/UX` targets.

```text
C01-ID/
├─ Ai file/
│  └─ Design_Direction.md        # requirement script for the Rockbox Ai file target
├─ CMF/
│  └─ CMF_Direction.md           # requirement script for the Rockbox CMF target
├─ Display UIUX/
│  └─ UIUX_Requirements.md       # requirement script for the Rockbox Display UI/UX target
├─ Interface_Constraints.json
└─ Handoff_to_ID_Designer.md
```

Optional draft carriers such as `Ai_Source.svg` or `Display_UIUX_Mock.svg` may be added later, but the MVP must not depend on them. The first reliable ability is structured Rockbox-like scripts that a human ID designer and downstream layers can act on.

## Completion Standard

C01 is not complete because the visual draft looks nice. It is complete when the original Rockbox C01 targets (`Ai file`, `CMF`, `Display UI/UX`) exist in recognizable, non-empty script form, all AI-drafted assumptions are visible, human/ID decisions are labeled, and C02/C03/C04/C05 can consume the machine-readable constraints without guessing.
