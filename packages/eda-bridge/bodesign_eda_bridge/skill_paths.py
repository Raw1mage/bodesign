"""Resolve a companion skill's directory, tolerant of the unified bodesign layout.

The `kicad` (analysis) and `kidoc` (documentation) engines were folded into the
single `bodesign` skill, where they live as `~/.claude/skills/bodesign/engines/<name>/`.
Standalone companion skills (`emc`, `spice`, `datasheets`, ...) still install at
`~/.claude/skills/<name>/`.

Resolution order for `resolve_skill(name, env, explicit)`:
  1. `explicit` arg (caller override) — no fallback if it is invalid.
  2. `$<env>` env var — no fallback if it is invalid.
  3. neither given → try `skills/bodesign/engines/<name>` (for absorbed engines),
     then `skills/<name>` (standalone / legacy layout).

A candidate qualifies only if it contains a `scripts/` subdir. Returns the first
valid `Path`, else `None`. This keeps the MCP's analysis/SPICE/EMC delegation
working whether the host has the unified `bodesign` skill or the legacy
standalone `kicad`/`kidoc` skills installed.
"""
from pathlib import Path
import os
import shutil

# engine names that the unified `bodesign` skill carries under engines/
_ENGINE_NAMES = {"kicad", "kidoc"}

# The three analyzer engines the C06 verification tools resolve, each with its
# env override and the underlying binary its scripts shell out to. kicad-cli backs
# the kicad analyzer (and the emc analyzer, which runs over kicad output); ngspice
# backs the spice analyzer.
_ANALYZER_ENGINES = (
    ("kicad", "BODESIGN_KICAD_SKILL", "kicad-cli"),
    ("spice", "BODESIGN_SPICE_SKILL", "ngspice"),
    ("emc", "BODESIGN_EMC_SKILL", "kicad-cli"),
)


def _ok(p) -> Path | None:
    p = Path(p)
    return p if (p / "scripts").is_dir() else None


def resolve_skill(name: str, env: str, explicit=None) -> Path | None:
    if explicit:
        return _ok(explicit)
    env_val = os.environ.get(env)
    if env_val:
        return _ok(env_val)
    home = Path.home() / ".claude" / "skills"
    if name in _ENGINE_NAMES:
        found = _ok(home / "bodesign" / "engines" / name)
        if found:
            return found
    return _ok(home / name)


def analyzer_engine_status() -> list[dict]:
    """Deployment self-check (DD-5): per analyzer engine, report whether the engine
    SCRIPTS are resolvable (resolve_skill non-None) and whether the underlying BINARY
    is on PATH. This makes "can C06 run here?" answerable in one call instead of a
    `docker exec` probe, and keeps the two failure modes distinct:

      - engine_resolvable False  -> would surface as `skipped-no-skills`  (the bug
        this fix removes from the container by bundling the engines).
      - binary_present  False    -> would surface as `skipped-no-simulator` (a
        legitimate, distinct outcome when e.g. ngspice is genuinely absent).

    Pure + side-effect-free (only reads env + PATH), so it is safe to call anywhere.
    """
    out: list[dict] = []
    for name, env, binary in _ANALYZER_ENGINES:
        path = resolve_skill(name, env)
        binary_present = shutil.which(binary) is not None
        out.append({
            "engine": name,
            "engine_resolvable": path is not None,
            "binary": binary,
            "binary_present": binary_present,
            "resolved_path": str(path) if path is not None else None,
            "can_run": path is not None and binary_present,
        })
    return out
