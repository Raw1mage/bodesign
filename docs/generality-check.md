# bodesign Tool Generality Check

A repeatable audit for the bodesign MCP tool layer. It exists because the suite
was derived from one real board run (OpenMV / STM32N657) and must not silently
carry that board's assumptions into reuse on a different design.

**The bar (DD-1):** *no SILENT overfit.* A board-specific or process-specific
value is acceptable **only if** it is either (a) caller-overridable through the
tool's inputs, or (b) explicitly reported in the tool's result. It is a defect
only when the tool silently does the wrong thing (or a no-op) on a non-reference
board without telling the caller. The goal is not universal coverage — an
explicit, reported limitation is a passing outcome.

Scope: the **shipped tool layer** only — `packages/*/bodesign_*` and the
`services/mcp/server.py` handlers/schemas. Tests, docs, and plans are out of
scope.

## The 5-axis checklist

Run this for every tool (new or changed):

1. **Input-driven vs hardcoded.** Does behaviour come from caller arguments, or
   from baked-in constants? List every numeric/string constant that affects
   output and classify it:
   - *universal physics* (speed of light, copper resistivity, a closed-form
     microstrip coefficient) → fine, never flag.
   - *board/process-specific* (a refdes, a stackup value, a layer set, a fixed
     clearance/pitch/via geometry, a small-board grid) → must be overridable or
     reported.
2. **Hidden defaults.** If the caller omits an input, does the tool invent a
   board/process value silently? Defaults are allowed **only** when documented as
   a named reference AND echoed/reported so the caller knows what was used.
3. **Toolchain coupling.** Does it hardwire a specific KiCad version, a fixed
   layer count, a single process capability, or a file/refdes naming convention
   that only the reference board uses?
4. **Domain breadth.** Would it work for a clearly different board (2-layer motor
   driver, 6-layer FPGA, RF front-end), or only an STM32N6-class design? If not,
   is the limitation *reported* rather than silent?
5. **Silent vs reported failure.** When an assumption does not apply, does the
   tool fail-fast / report it, or produce plausible-but-wrong output with no
   signal? Silent-wrong is the only category that blocks the bar.

A tool **passes** when every board/process constant it touches is overridable or
reported, and any genuinely missing required input makes it fail-fast (never a
fabricated success).

## Severity classes

- **silent-failure** — produces wrong/no-op output with no signal. Must fix.
- **rule-violation** — hidden default that is not caller-overridable. Should fix.
- **acceptable-caveat** — overridable or visibly-wrong default. Document + expose.

## Current audit (2026-06-09)

| Tool | Board/process assumption | Status |
|---|---|---|
| `route_net2pcb` | USB-C pin expansion | ✅ `connectors` input + `applied_pinmaps`/`unmapped_connectors` report; applies to any USB-C footprint, any refdes |
| `si_check` | driver/load/edge/thresholds | ✅ `rdrv`/`cload`/`edge_ns`/`overshoot_*_pct` inputs + `effective` echo (defaults = STM32-class CMOS reference) |
| `emit_layout` | placement grid / outline | ✅ `board_mm`/`columns`/`place_start_mm`/`place_pitch_mm`/`margin_mm` inputs |
| `emit_fab` | PDF layer set | ✅ `pdf_layers` input (default = 2/4-layer set) |
| `via_in_pad` | POFV via geometry | ✅ `drill_mm`/`pad_mm`/`keep_rings` inputs (default = JLCPCB advanced) |
| `pour_planes` | stitch net + grid/via | ✅ `stitch_net`/`stitch_pitch_mm`/`stitch_drill_mm`/`stitch_pad_mm` inputs (default = JLCPCB-class) |
| `impedance_solve` | — | ✅ universal physics only |
| C00–C07 workflow-core | — | ✅ de-productized, keyword/input-driven, never fabricates |
| ME group (`c02_*`, `render_board_model`) | wall/clearance/render size | ✅ caller-driven inputs |

## Automated arm

`tests/test_tool_generality.py` encodes the contract as data: a table of
`(tool, required_override_inputs)` asserted against each tool's live MCP schema.
If a future change removes an override that was added to de-overfit a tool, the
test fails — that is the regression guard. Add a new row whenever a tool gains a
board/process input so the contract stays enforced.

Run it as part of the suite; it needs no `pcbnew`/`ngspice` (schema-level only).
