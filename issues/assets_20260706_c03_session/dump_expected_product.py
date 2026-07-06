"""Dump gen_product.py's merged nets as the authoritative expected partition.

Same SSOT logic as dump_expected.py (CCM): exec gen_product.py with compose
stubbed, capture its `nets` (post-merge electrical truth), dump {name: sorted
nodes}. The .kicad_sch union must reproduce the SAME node->partition-class map.
"""
import json, sys
import bodesign_eda_bridge as _beb

FB = "/work/aiguard/C03-EE/full_board"

# gen_product.py does `from bodesign_eda_bridge import compose_schematic` at module
# top; a stub injected only into the exec namespace is re-bound to the REAL
# function by that import, so gen_product's own wire-style compose runs and
# OVERWRITES the label-style sch we built. Patch the attribute ON THE MODULE so
# the re-import resolves to the stub, then restore it. (Root cause of the fidelity
# gate reading a stale wire sch: this dump ran before the gate and clobbered it.)
_REAL = _beb.compose_schematic
def _stub_compose(*a, **k):
    class _R:
        placed = 0; nets = 0
        class emit: unresolved_pins = []
        warnings = []; validation = None
    return _R()

_beb.compose_schematic = _stub_compose
try:
    src = open(f"{FB}/gen_product.py").read()
    ns = {"__name__": "_genprod", "json": json, "sys": sys}
    exec(src, ns)
finally:
    _beb.compose_schematic = _REAL
nets = ns["nets"]

expected = {}
for n in nets:
    expected[n["name"]] = sorted(set(n["nodes"]))

json.dump(expected, open(f"{FB}/product_expected_partition.json", "w"), indent=0)
print("EXPECTED_NETS", len(expected))
print("BAT_SENSE_nodes", expected.get("BAT_SENSE"))
print("GND_nodecount", len(expected.get("GND", [])))
print("total_nodes", sum(len(v) for v in expected.values()))
