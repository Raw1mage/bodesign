# C01 Industrial Design Requirements Skill Build Plan

## Decision

Build C01 method authority inside the repo-local canonical `bodesign` skill (`skills/bodesign/stages/c01-id/GUIDE.md`). Public GitHub discovery did not find a ready-to-adopt specialist skill, and generic visual/brand/frontend skills are insufficient authority for the C01 workflow. Do not maintain a separate plan-local `c01-industrial-design-requirements` skill copy.

## Skill Purpose

C01 is an industrial-design requirement deepening helper. It turns C00 product intent into structured scripts for Rockbox-style C01 deliverables: `Ai file`, `CMF`, and `Display UI/UX`. It does not claim final industrial design, 3D CAD, manufacturing sign-off, or Adobe Illustrator final output.

## Initial Knowledge Sources

- Rockbox C01 target package: `Ai file`, `CMF`, `Display UI/UX`.
- C00 PRD sections that feed C01: product context, target user, form factor, external interface, exposed sensors, UI/status behavior, constraints, risks, schedule, and approval owner.
- Common industrial-design requirement practice: usage scenario, form archetype, primary face, touch/visibility zones, exposed-component treatment, CMF direction, visual hierarchy, and handoff to ID/ME/EE/FW.
- Borrowed support patterns only: `canvas-design` for simple visual source drafts, `brand-guidelines` for brand language discipline, `frontend-design` for UI hierarchy language. These are helpers, not C01 authorities.
- GitHub discovery candidates: industrial design brief apps and CMF agent fragments may inform examples, but none are canonical enough to import directly.

## Initial Skill Modules

1. **Role and Boundary Prompt** — C01 consumes C00, deepens only external appearance/human-interface intent, and returns blockers to C00.
2. **Question Strategy** — ask one C01-specific question at a time: form archetype, product posture, primary face, exposed component treatment, CMF mood, display/status behavior, and human approval owner.
3. **Reference Image Intake** — accept user-uploaded reference images, extract visible style/CMF/form/UI cues, ask what the user likes or rejects, and convert confirmed cues into C01 scripts without copying a protected design.
4. **CMF Framework** — convert product context into color/material/finish options with tradeoffs, unresolved sample/vendor checks, and ID designer approval gates.
5. **Display UI/UX Script** — map screen, LED, button, buzzer, or app-facing status behavior to user-visible states; no-display products still need interaction/status scripts.
6. **Exposed Interface Checklist** — camera, mic, LED, button, USB-C, antenna, speaker, display, vents, mounting, branding, service access, and safety/labeling surfaces.
7. **Downstream Constraint Map** — translate C01 decisions into C02 enclosure/opening constraints, C03 component/interface constraints, C04 placement/keepout constraints, and C05 status/UI behavior constraints.
8. **Risk Map** — antenna metal blockage, camera FOV obstruction, mic acoustic path, LED visibility, USB insertion clearance, button ergonomics, thermal/material conflict, waterproofing vs openings, and CMF cost/manufacturability.
9. **Handoff Format** — produce structured scripts and blockers, not final ID approval.

## Iteration / Experience Accumulation

- Start with a conservative skill that asks clear questions and prevents silent visual defaults.
- Add examples from real C01 sessions after each project: what question worked, what downstream blocker appeared, what ID/ME/EE/FW conflict was found.
- Track reusable patterns by product archetype: development board, desktop sensor, handheld device, wearable, wall-mounted box, industrial module, consumer accessory.
- Promote repeated fixes into checklists only after evidence from actual sessions.
- Keep a `known_gaps` section in the skill so missing professional knowledge is visible instead of hidden by confident prose.

## MVP Outputs

The first usable C01 capability must produce a Rockbox-like C01 package, even before Adobe/Figma/CAD tooling exists. "Rockbox-like" means the package preserves the three original C01 deliverable intents and fills them with structured, editable requirement scripts instead of leaving them as empty folders.

```text
C01-ID/
├─ Ai file/
│  └─ Design_Direction.md
├─ CMF/
│  └─ CMF_Direction.md
├─ Display UIUX/
│  └─ UIUX_Requirements.md
├─ Interface_Constraints.json
└─ Handoff_to_ID_Designer.md
```

### Minimum Rockbox-Like Content

- **`Ai file/Design_Direction.md`**: product form archetype, usage posture, primary face, visible component placement intent, logo/label zones, visual hierarchy, and AI-drafted assumptions.
- **`CMF/CMF_Direction.md`**: color/material/finish direction, environment/use-case rationale, 2-3 candidate CMF routes, tradeoffs, supplier/sample checks, and ID designer approval gates.
- **`Display UIUX/UIUX_Requirements.md`**: screen/LED/button/buzzer/app-facing status behavior, user-visible states, basic interaction flow, error/status vocabulary, and C05 firmware dependency notes.
- **`Interface_Constraints.json`**: machine-readable exposed-component constraints for C02/C03/C04/C05, including placement preference, keepout/visibility/acoustic/RF notes, decision status, and owner.
- **`Handoff_to_ID_Designer.md`**: what came from C00, what AI drafted, what the human/ID designer must decide, blockers, downstream risks, and accepted assumptions.

## Concept Image Prompt Capability

C01 should be able to produce concept-image prompts from the accumulated C00/C01 appearance requirements as soon as enough visual intent exists. Prompt generation is a normal C01 skill behavior and communication aid. Actual image generation through an external model/API is an add-on, not an MVP readiness requirement, and must never replace the Rockbox-like script package above.

```text
C01-ID/
├─ Ai file/
│  ├─ Concept_Image_Prompts.md
│  └─ Concept_Reference.md
├─ CMF/
│  └─ Moodboard_Prompts.md
└─ Display UIUX/
   └─ UI_Concept_Prompts.md
```

- Concept-image prompts can be generated from the current C01 script state without requiring image API access.
- Generated images, when available, are mood/reference artifacts only: not dimensionally accurate, not manufacturing-ready, not ID-approved, and not a substitute for C02 CAD/STEP.
- If an image-generation API is used, the tool must require an explicit provider/API key configuration, fail fast when unavailable, and avoid silent provider fallback.
- The skill may generate prompts and explain visual tradeoffs; deterministic MCP tools may save prompts, generated image metadata, file paths, provider/model names, and limitation statements.

## Reference Image Intake Capability

C01 should let the user upload or point to existing reference images and use them as preference evidence. The goal is not to replicate the reference image; the goal is to understand what the user means and translate that into Rockbox-like C01 deliverables.

- Extractable cues include form archetype, proportions, visual weight, primary face, component treatment, color/material/finish mood, display/UI style, visible interaction patterns, and user-stated likes/dislikes.
- The skill must ask clarification questions such as: which parts should be borrowed, which parts should be avoided, and whether the reference is for form, CMF, UI, mood, or all of them.
- Reference-derived content should be labeled as `reference-derived` until the user confirms it as an actual product preference.
- The output should preserve traceability from each confirmed cue to the relevant C01 document section or downstream constraint.
- The skill must avoid copying proprietary/brand-specific designs and should generalize references into design intent language.

## Acceptance Criteria

- The skill can explain C01 as requirement deepening, not final design production.
- The skill can ask focused C01 questions without redoing C00 PRD discovery.
- The skill can separate AI draft, human decision, ID designer confirmation, and downstream engineering blockers.
- The skill can ingest reference images as preference evidence and convert confirmed visual cues into C01 scripts without treating the image as a final design.
- The skill can produce structured scripts that C02/C03/C04/C05 can consume without guessing.
- The skill refuses to fabricate final `.ai`, 3D CAD, CMF sample approval, or ID sign-off.
- The MVP cannot be marked ready unless it can produce the Rockbox-like C01 package above with non-empty, labeled draft content for all three canonical targets.
- Concept-image prompts may be produced by the skill whenever current C01 inputs are sufficient; actual generated images do not affect MVP readiness and must be labeled as reference-only add-ons.
