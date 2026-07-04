# C00 Autonomous Orchestration Loop (Batch D — design)

Status: planned (design before code, per the user's "land it in the plan first")

## Why

The spine (Batch B) wired the primitives — agent registry, `work_packet.v1` /
`blocker_return.v1`, `mode_contracts.enter_c01_mode` — but a human still has to
decide *which* primitive to call next. That makes bodesign a pile of tools, not a
copilot. The loop is the **conductor**: at each turn it looks at the whole board
and surfaces the single highest-value next step, so C00 *takes the non-EE owner
through* the C00→C06 chain instead of waiting to be driven.

This realizes the proposal's core verb — **"引導 (guide)"** the non-EE owner — and
closes the last open spine item in `c00_c01_gap-audit.md` ("Runtime UX: user stays
in C00; downstream layers work in the background and return questions to C00").

## What it is (and is NOT)

- It is a **deterministic selector/state-machine** over existing runtime state. It
  reads readiness + orchestration state and returns ONE next action. It is NOT an
  LLM; the C00 consultant skill phrases the surfaced question, the loop picks WHICH.
- It MAY auto-**dispatch** a work packet (safe: a scoped, reversible task record).
- It NEVER auto-answers a PRD field, auto-resolves a blocker, or marks approval.
  Human decisions and blocker resolutions always return to the user. No fabrication,
  no fallback — consistent with every other layer.

## Inputs (all already in runtime — no new state)

- `assess_c00_prd_readiness(folder)` → `next_question`, `overall_status`,
  `downstream_handoff_gates` (each: `target` C01..C06, `status` ∈ ready|partial|blocked,
  `blocking_sections`). This is how the loop knows which layers are dispatchable and
  which C00 fields gate them.
- `list_work_packets(folder)` → which layers are already dispatched + packet status.
- `list_blockers(folder, unresolved_only=True)` → decisions the user still owes.
- `load_agent_registry()` → the C00–C06 roster + authority (downstream layers only).

## Selector priority (returns exactly one next action)

The order encodes "unblock the human's own queue first, then advance the frontier":

1. **`resolve_blocker`** — if any unresolved blocker exists, surface the
   highest-severity / earliest one's `question_for_user`. The user owes a decision;
   nothing downstream should outrun it. (severity order: decision >
   accepted-risk-request > external-needed > blocked.)
2. **`ask_c00`** — else if `readiness.next_question` is non-empty AND at least one
   downstream gate is still `blocked` by a missing/blocked C00 section, ask that C00
   PRD question (it unblocks dispatch). Carries which gate(s) it unblocks.
3. **`dispatch`** — else if a downstream gate is `ready` and that layer has no work
   packet yet, dispatch one (via `dispatch_work_packet`, or `enter_<layer>_mode`
   where a mode contract exists, e.g. C01). Auto-dispatch is allowed because it only
   creates a scoped task; it changes nothing the user must approve.
4. **`ask_c00` (advance)** — else if `next_question` exists (PRD not fully answered
   but no gate is hard-blocked), keep deepening the PRD.
5. **`waiting`** — else if packets are dispatched and nothing is actionable by the
   user right now, report in-flight status (which layers, what they're producing).
6. **`done`** — all gates ready, all dispatchable layers dispatched, no open blockers:
   report "ready for review", list per-layer readiness, name remaining human gates.

Every action carries: `kind`, a human-facing `message`/`question`, the `layer`(s)
involved, the `owner` (user | downstream_agent | external), and the `evidence`
(gate/blocker/packet id) so the surface is auditable.

## Outputs (two functions)

- `c00_orchestration_tick(folder) -> NextAction` — the single next step (above).
- `c00_orchestration_status(folder) -> Board` — the whole board for an overview:
  per layer { gate status, dispatched?, packet status, open blockers }, plus C00
  PRD overall status and the counts. Read-only; mutates nothing.

`tick` may dispatch (step 3); `status` is pure. Both are deterministic and fail-fast.

## MCP surface

- `bodesign_c00_orchestration_status` — the board (read-only).
- `bodesign_c00_orchestration_tick` — advance one step; returns the next action and,
  if it dispatched, the new packet. An `auto_dispatch: false` arg lets a caller get
  the *recommendation* without performing the dispatch (dry-run), for UIs that want
  to confirm first.

## Boundary recap (human stays in control)

- Auto-allowed: selecting the next step, dispatching scoped work packets.
- Never auto: answering PRD fields, resolving blockers, marking human/ID/ME/EE/lab
  approval, claiming compliance. Those always surface back to the user/owner.
- The loop is a guide, not an autopilot: it can run dry (recommend-only) and a human
  can override the chosen step at any tick.

## Acceptance

- Given a fresh scaffolded C00, `tick` first asks C00 PRD questions (step 2/4), never
  dispatches a layer whose gate is still `blocked`.
- When a layer's gate turns `ready`, the next `tick` dispatches exactly that layer
  (once), and a subsequent `tick` does not re-dispatch it.
- An unresolved blocker preempts everything (step 1) until ingested.
- With all gates ready + all layers dispatched + no blockers, `tick` returns `done`
  and `status` shows the full board.
- No tick ever writes a PRD answer, resolves a blocker, or sets an approval flag.
- Deterministic: same state → same action (no timestamps/randomness in the decision).
