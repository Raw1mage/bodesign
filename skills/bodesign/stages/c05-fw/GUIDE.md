# C05 FW — Firmware *spec*, not firmware *code*

## Purpose & scope

C05 turns the product's intended behaviour into a **firmware specification package** the firmware
team can build against. You decompose the product into functions, modules, a top-level state model,
and a task list — and you produce a `Pin_Map_Bridge.json` that carries C03's pin truth forward into
firmware-consumable signal definitions. The deliverable is a contract, written precisely enough that
a competent FW engineer can implement it without re-guessing the hardware.

**The central boundary — read this twice.** *bodesign owns the SPEC; the firmware team owns the
CODE.* You write what the firmware must do, which signals it owns, and which states it must resolve.
You do **not** write drivers, ISRs, init sequences, an RTOS-vs-bare-metal decision, a HAL, or any
source — and you never *claim* a behaviour is implemented or working. Everything here is `draft` /
spec-level until the FW team implements it and C06 verifies it. The worked examples
(`thesmart_products/openmv/C05-FW/`, `thesmart_products/rockbox/c05-fw/`) say this on the face of
every artifact (`> bodesign owns this spec; the FW team owns the firmware code. No code is generated
here.`) — keep that header.

**This stage does NOT own:** firmware source, build/flash toolchain choice, module API signatures,
scheduler model, inter-module messaging, memory map, or any pass/fail verdict. Those are FW-team or
C06 decisions. When you find yourself writing C, stop — you've crossed the line.

## Required deliverables — Definition of Done

Produce **all** of these at the stage root before you report C05 done or hand off
(see SKILL.md § "Definition of Done"). Each exists **or** carries an explicit `draft`/`blocked`
status with a reason + owner. The whole package is spec-level `draft` until the FW team signs off —
that is honest, but every required file must still be present.

| # | Required artifact | File |
|---|---|---|
| 1 | Functional spec | `Functional_Spec.md` |
| 2 | Module architecture | `Module_Architecture.md` |
| 3 | State machine | `State_Machine.md` |
| 4 | Task breakdown | `Task_Breakdown.md` |
| 5 | Pin-map bridge | `Pin_Map_Bridge.json` (**derived from C03's pin map — zero invented pins**) |
| 6 | Build notes | `Firmware_Build_Notes.md` (→ stage root) |

**Self-verify:** run `bodesign_c05_readiness` (`folder`); validate `Pin_Map_Bridge.json` parses; every
signal must trace to a C03 pinmap row. Model: `thesmart_products/rockbox/c05-fw/`.

## Inputs (from upstream)

You consume three upstream artifacts. Read them before authoring; every line of your spec should
trace to one of them.

- **From C00 PRD (`../c00-prd/GUIDE.md`):** the **s07 Software requirements** section — on-device
  behaviour, operating modes, alerting, pairing, OTA/update, security/privacy. Your Functional Spec
  *extends* PRD §7; it is the authority for "what the firmware must do". Also read s06 (electrical:
  which ICs/peripherals exist) so your modules name real parts.
- **From C01 ID/UX (`../c01-id/GUIDE.md`):** the **UI/UX status model** (`Display UIUX/
  UIUX_Requirements.md`) — specifically the *Minimum States To Resolve* table whose
  `C05 Firmware Dependency` column was written *for you*. Each row is a product state the firmware
  must implement and a user-feedback surface (LED/display/buzzer/app) it must drive. These rows
  become your state-machine states.
- **From C03 EE (`../c03-ee/GUIDE.md`):** the **GPIO + interface pinmap** — `..._GPIO_pinout.xlsx`,
  `..._介面pinmap.xlsx`, or `Pin_Allocation.csv` (MCU ball → GPIO → peripheral function). This is the
  **pin truth**. Every signal in your `Pin_Map_Bridge.json` must come from a row here — you may not
  invent a pin, a net, or a peripheral assignment. If C03 delivered an honest interface subset (not
  full connectivity), your bridge covers that subset and records the gap; it does not back-fill.

If an input is missing or partial, that is a documented boundary, not a licence to guess — see
*Honesty notes*.

## SOP

The flow is: **read inputs → functional spec → module architecture → state machine → task breakdown
→ pin-map bridge → handoff**. Author the five markdown/JSON artifacts; optionally render the state
machine and architecture as diagrams via the companion skills. The procedure stands alone — the
companion skills are accelerators, not prerequisites.

### 1. Extract the functions from PRD §7 (→ `Functional_Spec.md`)

Open the markdown with the header line above, then `## Functions` listing each distinct
device-side behaviour as one bullet, traced to PRD §7. Keep the wording concrete and testable
(e.g. "device-side person detection ≥15 FPS", "raw image never leaves device; only events +
thumbnails egress"). Then add:

- `## Operating modes` — the product's run modes (idle / armed / alarm / pairing / charging / OTA…),
  taken verbatim from PRD §7 + C01. These are the candidate top-level states.
- `## User interactions` — how the user drives and reads the device (button gestures, status-ring
  behaviour per mode, privacy shutter, pairing flow), sourced from the C01 status model.
- `## External interfaces` — every bus/link with its physical realisation and the part on the other
  end: e.g. `I2C0 — IMU / sensors`, `XSPIM0 — octal FLASH (MX25UM256) + PSRAM (APS512)`,
  `Wi-Fi/BLE — CYW43439 (SDIO/SPI)`. Names must match C03's parts and C03's net names.
- `## Logging / Update / Security` — event log scope, debug console, telemetry level (event-level,
  **not** image), signed OTA, A/B rollback, secure boot, TLS for alerts, privacy-by-design
  (image stays on device), tamper→lockdown. State the *requirement*; do not assert it is met.

Keep the whole file in the project's working language (the openmv example is in Traditional Chinese;
the rockbox example is in English) — match the PRD.

### 2. Decompose into candidate modules (→ `Module_Architecture.md`)

Header note: `> Decomposition stubs derived from the functional spec. Concrete module APIs,
RTOS/bare-metal choice, and inter-module contracts are FW-team decisions.` Then:

- `## Candidate modules` — one bullet per function from step 1, each phrased as a module with the
  explicit tail `(interface + responsibilities — FW team)`. You name the *responsibility boundary*;
  the FW team designs the *API*. This deliberate stub-ness is the honest line: you are not designing
  their software architecture.
- `## Open architecture decisions` — list what you are *not* deciding and handing to FW: scheduler
  model (bare-metal loop vs RTOS), inter-module messaging / shared state, and the HAL boundary vs the
  C03 pin map (point at `Pin_Map_Bridge.json`).

To draw this as a C4-style container/component view, hand the module list to **drawmiat** /
**miatdiagram** (see *Tools*). The diagram is valued but optional; the markdown is the source of
truth.

### 3. Author the top-level state machine (→ `State_Machine.md`)

Header note: `> Top-level firmware state model. States/transitions below are placeholders to be
confirmed against PRD §7 modes and the C01 UI/status model (GRAFCET-style refinement).` Then:

- `## States` — the operating modes from step 1 / the C01 *Minimum States To Resolve* rows. These
  are the states the firmware must resolve and the UI must reflect.
- `## Transitions` — list the transitions and guards you can derive honestly from PRD §7 + C01
  (e.g. button-long-press-3s → pairing; tamper IMU event → alarm). Where a transition's guard is a
  FW-internal detail, leave it explicitly as `_transitions and guards to be specified with the FW
  team_` rather than fabricating timing/threshold values you don't have. A partial-but-true set of
  transitions beats a complete-but-invented one.

For a verifiable diagram, render the states/transitions as **GRAFCET (IEC 60848)** via **drawmiat**;
the C01 status model may already point at a Grafcet view you can refine. Validate before generate
(the drawmiat MCP requires `validate_diagram` first).

### 4. Write the task breakdown (→ `Task_Breakdown.md`)

Header note: `> Spec-level task list for FW planning. Effort/ownership/scheduling are FW-team owned.`
Then one `Implement \`<module>\` (spec → driver → test)` bullet per module, plus the two standing
tasks every project carries:

- `Bring up C03 pin map (see Pin_Map_Bridge.json)`
- `Define build/flash/log SOP (FW team)`

Do **not** assign effort estimates, owners, or a schedule — those are FW-team-owned. This list is a
planning scaffold the FW team costs and sequences.

### 5. Build the Pin_Map_Bridge.json (the C03→FW bridge — the load-bearing artifact)

This is where C03's pin truth becomes firmware-consumable. Copy
`assets/Pin_Map_Bridge.template.json` and fill it from the C03 pinmap — **never by hand-typing pins
from memory**. For each MCU ball that C03 assigned, emit one signal object:

```json
{
  "ref": "U_AP (STM32N657L0)",
  "pin": "PA2",
  "net": "UART0",
  "firmware_signal": "UART0",
  "responsibility": "TBD by FW team (init/direction/driver/ISR)."
}
```

- `ref` — the component reference + part, exactly as C03 names it.
- `pin` — the physical ball/pin (must exist in the C03 pinmap row).
- `net` — the C03 net name (the electrical truth).
- `firmware_signal` — the signal name firmware will use; default to the net name unless C03 gives a
  clearer functional alias. Do not promote a net into a peripheral instance C03 didn't assign.
- `responsibility` — **always** `"TBD by FW team (init/direction/driver/ISR)."` You are bridging the
  pin, not writing its driver. This phrase is the honesty marker that keeps the code/spec line crisp.

Top-level keys: `schema: "bodesign.c05.pin_map_bridge.v1"`, `state: "drafted"`,
`source: {"layer": "C05", "from_c03_pin_map": true}`, the `signals` array, and a closing
`note: "Bridges the C03 pin map to firmware signal responsibilities. Driver/ISR/init code is
FW-team owned."`

If C03 only delivered an interface subset, bridge exactly that subset and add a `note` recording the
missing-connectivity boundary — do not invent rows to look complete. Validate the file parses:
`python3 -m json.tool < <project>/C05-FW/Pin_Map_Bridge.json > /dev/null`.

### 6. Assemble the testable-behaviours list for C06

From the Functional Spec functions + state-machine transitions, write the list of **observable
behaviours** C06 will verify (e.g. "armed→alarm on IMU tamper event within N s", "image never
egresses — only events/thumbnails", "OTA image rejected if signature invalid", "status ring shows
fast-flash red in alarm"). Each item is *spec-level / pending* — a thing to test, not a passed test.
This can live as a `## Testable behaviours (→ C06)` section in the Functional Spec or a short
appended note; the openmv/rockbox examples fold it into the spec and handoff rather than a separate
file.

## Deliverables

Modelled on `thesmart_products/openmv/C05-FW/` and `thesmart_products/rockbox/c05-fw/`. Markdown +
the JSON bridge are the source of truth; diagrams are generated.

| Artifact | File | Kind | Content |
|---|---|---|---|
| Functional spec | `Functional_Spec.md` | source | functions, modes, interactions, interfaces, log/update/security; extends PRD §7; carries the testable-behaviours list to C06 |
| Module architecture | `Module_Architecture.md` | source | candidate modules (interface+responsibilities stubs) + open architecture decisions left to FW |
| State machine | `State_Machine.md` | source | top-level states + derivable transitions/guards; the rest deferred to FW |
| Task breakdown | `Task_Breakdown.md` | source | spec-level implement-per-module tasks + pin-map bring-up + build/flash/log SOP stub |
| Pin-map bridge | `Pin_Map_Bridge.json` | source/exported | C03 pin → `firmware_signal` + FW-owned responsibility; `schema bodesign.c05.pin_map_bridge.v1`, `state: drafted` |
| State / architecture diagrams | `*.svg` (+ `*.pptx`) | generated | optional Grafcet state view + C4 module view via drawmiat |

When a real firmware tree is being *archived alongside* the spec (preserve-only track, e.g. rockbox),
add a `Firmware_Build_Notes.md` that documents the vendored source's origin, toolchain/SDK version,
and build commands — and that explicitly notes build outputs (`build/`, `*.elf`, `*.hex`) are
regenerable and git-ignored, never committed. The spec artifacts still sit alongside; the build notes
*describe* the team's code, they do not become bodesign's claim to author it.

## Gate / done-criteria

C05 is genuinely complete (still `draft` until a named owner signs off) when:

- The five artifacts exist and every header carries the spec/code-boundary note.
- Every Functional-Spec function traces to PRD §7; every state traces to PRD §7 + the C01 status
  model; every external interface names a real C03 part/net.
- Every `Pin_Map_Bridge.json` signal traces to a C03 pinmap row — **zero invented pins** — and the
  file parses as JSON with `state: "drafted"` and FW-owned `responsibility` on every signal.
- Module/state/task artifacts honestly mark FW-team-owned decisions as open rather than deciding
  them.
- The testable-behaviours list for C06 exists and every item is phrased as *to-be-verified*, not
  *verified*.

It is **not** complete — and must not be marked so — if any pin lacks a C03 source, any behaviour is
claimed working, or any FW-team decision (scheduler, API, HAL) has been silently made here.

## Honesty notes for this stage

Apply `../../references/honesty-model.md`. The stage-specific traps:

- **The code/spec line is the honesty boundary.** Writing a driver, picking an RTOS, or asserting a
  module "works" fabricates a deliverable that isn't yours and isn't done. Keep `responsibility:
  "TBD by FW team..."` and the `(interface + responsibilities — FW team)` stubs — they are not
  laziness, they are the honest record of who owns what.
- **No invented pins (rule 1 + 2).** Pin/net/signal facts come from the C03 pinmap with that
  provenance (`from_c03_pin_map: true`). If C03 didn't assign it, it doesn't exist here.
- **Mark the unproven (rule 3).** Everything is `draft` / spec-level / `pending` C06 verification.
  Transitions you can't derive stay `_to be specified with the FW team_`, not guessed timings.
- **Behaviours are testable, never tested (rule 4 + C06).** C05 says what to verify; only C06 (and a
  real build) produces a verdict. Never write a pass here.
- **Document boundaries, don't back-fill (rule 6).** Missing C01 states, a bus configured by boot-ROM
  and absent from public firmware, or a C03 interface-only subset → record the gap in the relevant
  artifact and leave it out.
- **Preserve-only vaults (rule 7).** When archiving a real firmware tree, vendor source verbatim,
  never commit regenerable build outputs, and keep your spec as your own generation alongside it.

## Handoff to C06 (Verify) and to the FW team

- **To the FW team:** the full spec package — `Functional_Spec.md`, `Module_Architecture.md`,
  `State_Machine.md`, `Task_Breakdown.md` — plus `Pin_Map_Bridge.json` as the machine-readable pin
  contract they implement against. They own everything below the spec line from here.
- **To C06 (`../c06-verify/GUIDE.md`):** the **testable-behaviours list** — the observable
  device behaviours and state transitions, each `pending`. C06 turns these into pass/warn/fail
  verdicts only after the FW team builds and a real device (or model run) exists; C05 never
  pre-judges them.

Cross-links upstream: `../c00-prd/GUIDE.md` (PRD §7), `../c01-id/GUIDE.md` (UX status model),
`../c03-ee/GUIDE.md` (pinmap source of truth).

## Tools & companion skills

- **drawmiat / miatdiagram** — for the **State_Machine** as GRAFCET (IEC 60848) and the **Module
  Architecture** as a C4 container/component view. Use the `drawmiat` MCP: `validate_diagram` *then*
  `generate_diagram` (validation is required first); IDEF0/Grafcet can also emit editable PPTX.
  `miatdiagram` helps decompose requirements/repos into the JSON those renderers consume.
- **docx / pptx / pdf / xlsx + the `docxmcp` MCP** — only if the spec must be delivered as a formatted
  document/deck for a review. Author the markdown first (source of truth), then render.
- **No KiCad engine here** — C05 consumes C03's *exported* pinmap, it does not re-run schematic/PCB
  analysis. If the pinmap looks wrong, fix it in C03, not by editing the bridge.
