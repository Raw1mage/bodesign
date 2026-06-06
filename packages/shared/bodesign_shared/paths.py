"""Working-data root — kept OUT of the program.

bodesign ships **no** working data (no fixtures, no product artifacts). Tests and
local runs that need real inputs read them from an external root pointed at by
``BODESIGN_DATA_DIR`` (default ``~/projects/bodesign-data``); when it's absent,
data-dependent tests skip. At runtime the MCP server receives working data via
the token ``/files`` API (TTL/GC'd), never from the repo.
"""
import os
from pathlib import Path


def data_root() -> Path:
    return Path(os.environ.get("BODESIGN_DATA_DIR", str(Path.home() / "projects" / "bodesign-data")))
