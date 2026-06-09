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

# engine names that the unified `bodesign` skill carries under engines/
_ENGINE_NAMES = {"kicad", "kidoc"}


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
