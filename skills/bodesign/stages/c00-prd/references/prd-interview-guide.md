# C00 PRD Interview Guide — the question catalog for the collect-ideas loop

This is the question bank C00 draws on to run its core workflow:

> **generate questions from PRD knowledge → collect the owner's ideas → analyze → render the PRD docx
> from the standard template.**

Every question here is keyed to a field in `assets/answer_state.template.json`, so an answer drops
straight into the answer-state and renders into the docx with no translation step. Questions are *what to
consider* — not a script to read aloud. Pick the few that unblock the most, ask them well, fold answers
back as `answered` with a `source`; leave the rest honestly `missing`.

---

## Interview protocol

1. **Scan context first, then confirm.** If a reference design, prior PRD, or brief exists, read it
   before asking anything — then ask the owner *which documents are current* and what's missing. Don't
   ask what a document already answers; don't trust a document the owner hasn't confirmed.
2. **For a derived product, build the capability/gap table before interviewing the body.** What does the
   baseline already provide (sourced)? Match level (full / partial / none)? Gap a downstream stage must
   close? The interview then focuses on the *gaps and the net-new*, not on re-deciding inherited facts.
3. **Batch the high-leverage questions first.** Ask the 3–5 that unblock the most fields — problem/goal,
   core scope, hard boundaries (non-goals), the headline targets (cost / quantity / cert), the success
   metric. Everything else can follow once these anchor the PRD.
4. **Use `AskUserQuestion` with named options; ≤ 6 questions per round; critical decisions only.** Never
   pose non-critical questions as prose. Give the owner choices to pick from rather than a blank page,
   but treat "Other" as intent to re-derive, not a literal value.
5. **One answer can fill several fields — tag each back.** Record `value`, `state`, `owner`, `source`,
   `handoff_targets` per field. A value with no source is a defect.
6. **Never invent. Mark `missing` / `external-needed` / `blocked` / `accepted-risk` with a reason.** A
   half-known PRD that says what it doesn't know beats a complete-looking one that guessed.

---

## Cross-cutting dimensions — hit these for every substantive requirement

These are the angles that make the PRD *周全*. For each objective and each requirement line, make sure the
interview has captured all six — they're what the three reference PRD skills converge on:

| Dimension | The question behind it | Where it lands |
|---|---|---|
| **What / Why, not How** | "What capability, and why does it matter?" — never "which part / which API." | the field value; *how* is C03/C05 |
| **Priority & scope** | "Must-have for this build, or nice-to-have? In scope or explicitly out?" | section field + `s09.out_of_scope` |
| **Measurable success** | "How will we know it's met — what number, measured how?" | `s03.objectives`, `s01.success_metric` |
| **Provenance** | "Where does this value come from — your call, a datasheet, the reference?" | field `source` (or honest `missing`) |
| **Risk + mitigation + owner** | "What could make this fail, what's the mitigation, who owns it?" | `s10.risk_register` |
| **Target ≠ result** | Cost / cert / performance are *targets the program commits to*, never achievements. | recorded as targets only |

---

## Question catalog by section

Field names below match `answer_state.template.json` exactly.

### s01 — Company Vision & Business Strategy → C06
- **target_customer** — Who is this for, specifically? Primary user vs. buyer vs. operator?
- **problem_statement** — What problem are we solving, and what's the cost of the status quo? Why us?
- **business_goal** — What business outcome does shipping this serve (revenue, strategic foothold, …)?
- **success_metric** — The headline measure of success — *with a number and a measurement method*. Often
  carries the cost & maturity headline (e.g. "BOM ≤ $X at EVT, reach DVT by Qn").
- **market_or_use_context** — Where/how is it used? Market or deployment context, competitors if relevant
  (carry any market-sizing/competitive confidence labels through — don't launder a range into a fact).

### s02 — Project Overall → C03, C05, C06
- **product_summary** — One-paragraph description a junior engineer could act on.
- **primary_use_cases** — The top 2–4 end-to-end use cases / scenarios.
- **engineering_scope** — Which disciplines are in play (ID/ME, EE, FW, RF)? What's explicitly excluded?
- **build_volume** — Intended build ramp (e.g. EVT 50 → 500-unit pilot → MP). Feeds C07 quantity target.
- **derivation_baseline** — If derived, from what (reference design / prior board)? Cited by path + role.

### s03 — Project Objectives → C06, C07
- **objectives** — The numbered product goals. Phrase **each with its measurable acceptance criterion**
  so C06 can write a test against it ("FPS ≥ N at resolution R", not "fast").
- **performance_target** — The hard performance numbers (throughput, latency, battery life, …).
- **cost_target** — PCBA and finished-good BOM cost targets — *targets, not quotes*.
- **maturity_target** — How far this program goes (EVT / DVT / pre-MP / MP).

### s04 — System Architecture → C03, C05
- **architecture_diagram** — The product-level block diagram (render via `drawmiat` C4/block, or ASCII).
- **compute / memory / power_chain / connectivity / sensors_io** — For each block: what's required and
  why, and (if derived) what the baseline provides vs. the gap. *Requirement-level, not part-level* — the
  application processor *class and need*, not the final MPN (that's C03).

### s05 — ID / ME Requirements → C01, C02
- **enclosure_material_tooling** — Material, finish, tooling intent (injection / CNC / sheet).
- **form_and_mount** — Form factor and how it mounts / is held / worn.
- **dimensions** — Target envelope (mark `TBD` where ID hasn't decided — honest, not blank).
- **front_face_features** — Display, lens, indicators, branding on the visible face.
- **buttons_leds** — Controls and indicators: count, type, behaviour.
- **ports** — External connectors (USB-C, jacks, SIM, …) and their placement intent.
- **antenna_keepout_ingress_drop** — Antenna keep-out, ingress (IP) target, drop/impact target.

### s06 — Electrical Requirements → C03
For each: state the **requirement and its source** (reference design / datasheet + page), not a final
decision. Mark `tbc` for anything not yet chosen.
- **application_processor / flash / ram** — Compute & memory requirements.
- **radios / phy_or_wired** — Wireless standards and wired interfaces required.
- **camera_sensors** — Imaging / sensing requirements.
- **power_input / charger_powerpath / regulators_loadswitches** — Power source, charging, rail plan.
- **esd_tvs_temp** — ESD/TVS protection spec and operating temperature range.

### s07 — Software Requirements → C05
- **on_device_behaviour** — What the device does on its own; the core behaviour.
- **operating_modes** — Modes / states and the transitions between them.
- **alerting** — Notifications / alarms: triggers and channels.
- **pairing** — Onboarding / pairing flow, if any.
- **update_ota** — Firmware update / OTA requirement.
- **security** — Auth, secure boot, data-at-rest/in-transit requirements.
- **model_data_management** — On-device model / data lifecycle, if applicable.

### s08 — Roles & Responsibility → C05
- **product_owner / ee_owner / me_id_owner / fw_owner / qa_lab_owner** — Who owns each discipline's
  deliverable for C00–C07? Often `external-needed` early — leave it visibly open, don't invent names.

### s09 — Assumptions & Constraints → C01, C02, C03, C06
- **baseline_assumption** — The assumptions the design rests on (reference-design baseline, etc.).
- **external_cert_gates** — Which certifications gate ship, and that they're external-lab gates (targets).
- **out_of_scope** — What is explicitly NOT in this build — state it aggressively to stop scope creep.
- **tbc_component_choices** — Component choices deferred to C03 (named as deferred, not guessed).
- **known_limits** — Known limitations accepted for this generation.
- *(Risks with mitigation + owner live in `s10.risk_register`, not here — keep this to standing
  assumptions and limits.)*

### s10 — Project Management → C06
- **stage_gate_plan** — The EVT → DVT → pre-MP gate plan and entry/exit criteria.
- **sync_cadence** — Review / sync rhythm.
- **change_control** — How PRD/spec changes are proposed, reviewed, and written back.
- **issue_tracking** — Where issues/defects are logged and triaged.
- **risk_register** — The program risks, **each with likelihood/impact, a mitigation, and an owner**. A
  risk with no mitigation or owner is a worry, not a plan — record it `accepted-risk` with who signed off,
  or give it a mitigation.

### s11 — High-level Schedule
- **prd_freeze / schematic_bom / layout_gerber / evt_build / verify / dvt_pre_mp** — Milestone dates vs.
  M0. Mark `TBC` until committed — a `drafted` schedule is honest; a fabricated one is not.

### s12 — Team Roster
- **chip_vendor / module_vendor / odm_assembly / cert_lab / internal_team** — Named suppliers and team.
  Vendors and lab `TBC` stay `external-needed`.

### RF appendix (only if `include_rf`)
- **rf01** — rf_use_case, region, radio_standard, antenna_context.
- **rf02** — rf_success_criteria, range_or_link_target, power_constraint.
- **rf03** — frequency_bands, module_or_chip, antenna_type, **certification_target** (FCC/IC/CE/PTCRB/
  NCC/JATE/TELEC…), test_needs. The certification target is a *target only* — never a pass.

---

## Before rendering the docx — the analyze pass

Once ideas are collected, before emitting the PRD package:
- **Completeness** — every gating field `answered`, or honestly `missing`/`external-needed`/`blocked`/
  `accepted-risk` with a reason and owner.
- **Boundary** — no C03/C05-level detail (schematic, pin map, part numbers as *decisions*, code) leaked
  in. The PRD says what/why; downstream owns how.
- **Evidence** — every asserted value and capability-table row carries a `source`.
- **Consistency** — terminology stable; targets phrased as targets; no contradictions across sections.
- **Verifiability** — each objective carries a measurable acceptance criterion C06 can test.

Then render with `assets/render_prd.py` (markdown SoT + handoff report) and emit the `.docx` via the
**docxmcp** MCP. Open items stay visible on the face of the document — that's the point.
