# Errors: deployment_c06-analyzer-engines-in-container

This change is about restoring a *runnable* state, so its "errors" are (a) the bug
outcome being eliminated, (b) a new build-time loud failure that prevents shipping a
silently-broken image, and (c) the honest skip that legitimately remains.

## Error Catalogue

## E-C06-001 SKIPPED_NO_SKILLS (the bug — must not occur by default after the fix)
- **Trigger (pre-fix)**: `resolve_skill(engine, env)` returns None because the engine
  scripts are not in the image and no `BODESIGN_*_SKILL` env is set.
- **Surface**: `bodesign_simulate` / `analyze_emc` / `analyze_thermal` return
  `status: "skipped-no-skills"` with a `kicad/spice/emc skill not found` warning.
- **Post-fix expectation**: in every EE-executing image this outcome is unreachable
  (engines bundled + env set). If it reappears, the image build or env wiring regressed.
- **Caller action (pre-fix only)**: none possible from tool args — env+packaging are
  deployment-layer. That non-actionability is exactly why this is a deployment fix.

## E-C06-002 ENGINE_SCRIPTS_MISSING_AT_BUILD (raise — new, intentional)
- **Trigger**: the build-time assert `test -d "$BODESIGN_*_SKILL/scripts"` fails — a
  tarball failed to extract, or the env path and the extracted layout disagree (R2).
- **Surface**: `docker build` exits non-zero with a message naming the missing
  `scripts/` path. The image is never produced.
- **Caller action**: fix the extraction step / env path so the layout and env agree;
  rebuild. Fail-loud-at-build is preferred over shipping an image that silently
  returns `skipped-no-skills` at runtime.

## E-C06-003 SKIPPED_NO_SIMULATOR (honest skip — preserved, distinct)
- **Trigger**: the engine IS resolvable but its binary (e.g. ngspice) is genuinely
  absent on PATH.
- **Surface**: the existing `skipped-no-simulator` verdict.
- **Caller action**: install/enable the binary in the image. This is a legitimate,
  distinct outcome and must NOT be conflated with E-C06-001. The self-check (DD-5)
  reports `engine_resolvable=true, binary_present=false` so the two are
  distinguishable without guesswork.

## Non-fallback invariants

- The fix bundles engines into the image; it NEVER auto-mounts the user's
  `~/.claude/skills` at runtime as the correctness path (a mount may exist only as
  optional operator convenience).
- `skipped-no-skills` (E-C06-001, engine script absent) and `skipped-no-simulator`
  (E-C06-003, binary absent) are two distinct signals; neither masks the other, and
  the self-check separates them.
- The lean core (`Dockerfile.core`) reporting "engines absent" is by-design (it
  forwards EE), not an error — `image_role: core` qualifies it.
