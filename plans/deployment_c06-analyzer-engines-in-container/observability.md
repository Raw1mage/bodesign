# Observability: deployment_c06-analyzer-engines-in-container

The point of this change is to make "can C06 run here?" answerable without
`docker exec` probing. Observability lives in two places: the build (fail loud) and
the runtime self-check payload (DD-5).

## Events

- **engine-bundled-at-build** — the Dockerfile extraction step succeeded and the
  build-time assert passed; the image carries the three engines.
- **engine-missing-at-build** — the build-time assert failed (E-C06-002); the image
  was never produced. The loudest possible signal — build stops.
- **c06-skipped-no-skills** — a C06 tool returned `skipped-no-skills` at runtime.
  Post-fix this should be unreachable in an EE-executing image; its appearance is a
  regression alarm.
- **c06-skipped-no-simulator** — a C06 tool returned `skipped-no-simulator`
  (engine resolvable, binary absent). Legitimate; distinct from the above.

## Metrics

Carried in the self-check payload, per `AnalyzerEngineReadiness`:

- `engine_resolvable` (bool, per engine) — `resolve_skill` returned non-None.
- `binary_present` (bool, per engine) — kicad-cli / ngspice on PATH.
- `can_run` (bool, per engine) — `engine_resolvable AND binary_present`; the single
  health bit for "this engine can produce a verdict here".
- `image_role` (monolith/ee/core) — qualifies a core report of engines-absent as
  by-design rather than broken.

## Logs (structured)

- Build: the assert message names the missing `scripts/` path on failure.
- Runtime: the existing `warnings` on a `skipped-no-*` result already name which
  engine/skill was not found; unchanged. The self-check is the new structured
  surface that pre-empts having to read those warnings reactively.

## Invariants observed

- After the fix, no EE-executing image yields `engine_resolvable=false` for
  kicad/spice/emc (asserted at build + verifiable via self-check).
- `skipped-no-skills` and `skipped-no-simulator` remain distinguishable in both the
  tool result and the self-check (never collapsed into one).

## Alerts (manual gate, not automated)

- A self-check showing `engine_resolvable=false` on a monolith/ee image means the
  image is mis-built — rebuild; do not work around at runtime.
- A `binary_present=false` with `engine_resolvable=true` is a toolchain-install gap
  (add the binary to the image), not the packaging bug this spec fixes.
