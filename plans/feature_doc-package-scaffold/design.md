# Design: C00 PRD expert-consultant layer

## Product Intent

C00/C07 is not a document generator. It is the front-door expert consultant that turns an incomplete product idea into a PRD contract that C01-C06 teams can use. The MCP stores state, scaffolds files, renders outputs, and computes readiness. The AI workflow skill provides expert questioning, synthesis, risk interpretation, and cross-layer teaching. Humans own business choices, approval, and professional sign-off.

## Operating Model

1. The user starts with an idea, partial notes, or a project folder.
2. MCP scaffolds a blank C00 PRD package from `c00_prd.template.json`.
3. AI reads the PRD state and readiness rubric.
4. AI asks the single highest-value missing question, explicitly labeling whether the answer is a human decision, AI-draftable assumption, or external expert input.
5. MCP persists the answer/draft into the C00 source state and re-runs readiness.
6. AI repeats until all required C00 gates are either filled, explicitly blocked, or accepted as risk by the user.
7. MCP emits the PRD and handoff report; downstream C01-C06 workflows start from mapped sections.

## Three-Way Boundary

### MCP Tools

- Scaffold deterministic blank PRD files and answer-state records.
- Load the PRD template and rubric.
- Compute field, section, document, and downstream handoff readiness.
- Render Markdown/docx/pdf outputs from approved source state.
- Produce a handoff report listing open decisions and blocked downstream layers.

### AI Workflow Skill

- Act as the PRD consultant and explain the purpose of each section.
- Translate vague user intent into structured PRD draft language.
- Ask one focused next question instead of dumping the whole questionnaire.
- Separate facts, assumptions, AI-suggested defaults, human decisions, and external expert confirmations.
- Keep PRD §5, §6, and §7 synchronized with C01/C02, C03, and C05 implications.

### Human / External Experts

- Choose product positioning, target customer, success metrics, price/cost targets, schedule, and team responsibility.
- Approve strategic, legal, compliance, commercial, and final product claims.
- Provide or approve ID/ME/FW/EE/testing constraints that require professional responsibility.
- Accept or reject risks when a PRD proceeds with unresolved assumptions.

## Readiness Semantics

- `missing`: no usable content exists.
- `drafted`: AI has proposed content but human approval is pending.
- `answered`: user provided usable content.
- `external-needed`: downstream expert input is required before completion.
- `blocked`: a decision or artifact is required before the PRD can advance.
- `accepted-risk`: user explicitly allows the PRD to proceed with a documented gap.

## Downstream Handoff Gates

- **C01/C02 from PRD §5**: industrial/mechanical constraints, size, mounting, interface, display/UI, enclosure, and assembly context are clear enough for ID/ME kickoff.
- **C03 from PRD §6**: compute, power, interfaces, memory, connectivity, sensors, compliance, and key electrical constraints are clear enough for circuit design kickoff.
- **C05 from PRD §7**: functional behavior, modes, user interaction, interfaces, firmware responsibilities, update/logging/security expectations, and C03 pin-map dependency are clear enough for FW spec scaffolding.
- **C06 from PRD §3/§6/§9/§10**: success criteria, verification targets, assumptions, constraints, certification goals, EVT/DVT intent, and outsourced lab needs are clear enough for a validation plan.

## Non-Goals

- Do not treat PRD generation as a single-shot LLM output.
- Do not claim legal/regulatory compliance without human or lab approval.
- Do not hide gaps with defaults or fallback assumptions.
- Do not require every consultant action to be an MCP tool.

## Implementation Direction

The first code implementation should keep the AI consultant as workflow behavior and implement only deterministic support surfaces as tools: template loading, scaffold output, readiness scoring, and document rendering. This preserves the correct product boundary: tools provide evidence and state; the expert AI guides the person.
