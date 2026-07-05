---
name: bodesign-kb
description: >-
  Client-facing knowledge interface for bodesign's refs-derived design paradigm
  (EPIC capability_refs-derived-design, 切面 7). Load this when you are a working
  agent DRIVING the bodesign MCP server to produce a C00~C04 hardware design and
  you need to know the refs-derived contract — how to decompose owner authority
  sources into per-layer 01_refs/ SSOT, how the fail-fast gates behave, and which
  verbs consume frozen upstream constraints rather than fabricate geometry. Use
  when the task is "generate a PCB / placement / castellated module from a
  reference or requirement spec" and you must not invent coordinates, pins, or
  component lists. This skill teaches the WORKFLOW + the guarantees; the full
  lifecycle engine lives in the `bodesign` skill (load that for stage guides).
---

# bodesign-kb — refs-derived design, the client contract

bodesign was inverted from a "generate artifacts from thin air" tool into a
**refs-derived** one: every delivered coordinate / pin / component must trace to
an SSOT, and every SSOT must trace to an owner authority source (PDF / PPTX).
This skill is the client interface to that guarantee — read it before you drive
any C00~C04 generation, so you consume constraints instead of inventing them.

## The one rule that changes everything

**You cannot design from thin air anymore, and the tooling enforces it.** Before
any downstream generation, the owning stage's `01_refs/` SSOT must exist and be
traceable. Miss it → the verb fail-fasts with a typed error + a missing list.
This is the machine form of repo 天條 1 (No silent fallback) / 天條 2 (No
fabrication). Do not try to route around it; the gate is the point.

## The refs-derived loop (do these in order)

1. **Decompose the owner authority source into per-layer `01_refs/` SSOT.**
   Reverse-decompose the formal deck / datasheet / heritage board into each
   stage's `01_refs/` (C01-ID/01_refs, C03-EE/01_refs, C04-Layout/01_refs, …).
   Each source keeps a provenance anchor; a `Reference_Baseline.md` declares the
   authority order (`authority order: formal deck > X01/BOM > heritage > concept`).

2. **Ingest + verify the SSOT** — `bodesign_refs_ingest` (landing verb
   `refs_ingest`). Returns a manifest: classified sources, parsed authority
   order, and which rich-media sources are **unadjudicated** (a PPTX/PDF a reader
   must interpret before its content may be asserted). `root_visible: false` is a
   LOUD signal the refs root is absent — never read it as an empty-but-fine folder.

3. **Freeze the upstream constraints, then consume them.** Downstream C04
   generation REQUIRES the frozen upstream JSON as a mandatory input (lifecycle
   directionality, 切面 4). Absent → `UPSTREAM_CONSTRAINT_MISSING`. The frozen
   contracts:
   - **C01 `Face_Layout.json`** (`bodesign.c01.face_layout.v1`) — each connector's
     board face/edge (`TOP/BOTTOM/LEFT/RIGHT/FRONT/BACK`) + a provenance anchor.
     **A connector's face is FROZEN upstream, not a C04 degree of freedom** (DD-4).
     This is the "USB won't plug in" root cause: the face is owner-decided.
   - **C02 `Envelope_Constraint.json`** / **C03 `Mechanical_Constraint_Export.json`**.

4. **Constraint-driven placement** — `c04_face_placement` (verb). Binds each
   connector to its frozen face/edge deterministically (same input → same output),
   every placement `movable_by_c04: false`. Asking to move a connector off its
   frozen face raises `CONNECTOR_FACE_CONFLICT` — obey the face, place WITHIN it.

5. **Castellated / stamp-module edges** — `c04_castellation` (verb). Half-plated
   edge pads are emitted as **segfault-free S-expression injection** (DD-5); the
   known-unsafe pcbnew mutation paths are hard-refused (`BOARD_SURGERY_UNSAFE_PATH`).
   Every castellation spec needs a `provenance` anchor (no-fabrication).

6. **DoD refs-traceback gate** — `c04_dod_traceback` (verb). The acceptance gate:
   every delivered item must trace to an SSOT anchor (`untraceable[]` = 憑空發明),
   and every SSOT-required ref must appear (`unfulfilled[]` = 漏做). Either
   non-empty → `DOD_TRACEBACK_FAILED` (blocking). Surface-existence is NOT enough.

## Typed error → what to do

| Error | Means | Do |
| ----- | ----- | -- |
| `REFS_SSOT_MISSING` | the stage's `01_refs/` SSOT is absent/empty | decompose the owner source into it first |
| `UPSTREAM_CONSTRAINT_MISSING` | a required frozen upstream JSON is absent | freeze face-layout / envelope upstream, retry |
| `CONNECTOR_FACE_CONFLICT` | you asked to move a connector off its frozen face | obey the C01 face; place within it |
| `BOARD_SURGERY_UNSAFE_PATH` | castellation asked for a segfault pcbnew path | use `sexpr_injection` (the default) |
| `DOD_TRACEBACK_FAILED` | a deliverable has untraceable or missing items | remove invented items / add SSOT traceback |

Every one is fail-fast with a structured `detail` — act on the detail, never
retry blindly or paper over it with a default.

## Verb quick-reference (all pure-python core landing verbs)

- `refs_ingest(folder)` → refs manifest (classify + authority order + adjudication)
- `c04_face_placement(face_layout)` → deterministic connector placements (frozen faces)
- `c04_castellation(spec, board_outline)` → S-expr injection block for castellated edge
- `c04_dod_traceback(deliverable_items, ssot_required_refs)` → traceback report (blocking gate)

Run them via the landing plane: `python3 skills/bodesign/scripts/gate.py <verb>
--repo <abs-project-dir> [--json '{...}' | --arg k=v]`. They are core (no KiCad
needed); the actual board mutation (pcbnew placement, S-expr injection into a real
`.kicad_pcb`) runs in the ee worker consuming these verbs' deterministic output.

## Division of labor

- **This skill (`bodesign-kb`)** — the refs-derived contract + verb interface for
  a client agent. What the guarantees are, which verb to call, how the gates fail.
- **`bodesign` skill** — the full C00~C07 lifecycle engine + stage guides. Load it
  when you need a stage's SOP, the honesty model, or the container boundary.
- **`specs/architecture.md`** — the cross-cutting module-boundary source of truth.
