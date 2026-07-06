"""Product board schematic generator v03.2 — connector-dense board fix (落盤修正版).

Root cause (isomorphic to the CCM stamp page 141-node GND short): the product
board is a CONNECTOR board — J1/JSA/JSB/J_CAM/J_OLED/J_SD pack dozens of pins on
tight x columns. gen_product.py composed it with style="draftsman" (drawn-wire),
whose _bus_route daisy-chains same-net pins with orthogonal wires that, on a dense
column, run COLLINEAR; KiCad fuses collinear wire runs into one net (+3V3_PB
absorbed 189 pins, BAT_SENSE 177).

v2 卡點根因(本棒 RCA 閉合):v2 傳 style="draftsman" + connection_style="label",
兩者語意衝突 —— composer 的 draftsman 路徑仍走 force-directed placement + emit
drawn-wire(即使標了 connection_style="label" 也照畫 322 條 wire),_bus_route
共線熔合致短路。正解:style="netlist"(byte-equivalent legacy path),純 global
label、零 daisy-chain drawn-wire,collinearity-free by construction。實測 +3V3_PB
節點 189→1(SSOT 期望 1)。電氣定義(net 節點列表)一行未動 —— 只 flip style。

This file imports gen_product.py's net-building logic verbatim (exec with compose
stubbed), then re-composes with the netlist(label)-style fix. gen_product.py is
NOT edited. Compose exceptions are re-raised (fail-loud) so a silent stub-swallow
never again leaves a stale wire-style sch masquerading as the deliverable.
"""
import json, sys

FB = "/work/aiguard/C03-EE/full_board"
SYMDIRS = [
    f"{FB}/symbols",
    f"{FB}/authentic_lib",
    f"{FB}/authentic_host",
    "/usr/share/kicad/symbols",
]

from bodesign_eda_bridge import compose_schematic
import bodesign_eda_bridge as _beb

# Capture comp + nets from gen_product.py without triggering its own compose.
# gen_product.py does `from bodesign_eda_bridge import compose_schematic` at
# module top, so injecting a stub into the exec namespace is NOT enough — the
# re-import re-binds the REAL function inside the exec'd namespace, and its
# style="draftsman" compose runs (writing the wire-style sch that shadows our
# fix). We must patch the attribute ON THE MODULE so the re-import resolves to
# the stub, then restore it before our own label-style compose.
_REAL_COMPOSE = _beb.compose_schematic
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
    _beb.compose_schematic = _REAL_COMPOSE
comp = ns["comp"]
nets = ns["nets"]
print(f"captured product components={len(comp)} nets={len(nets)}")

spec = {"components": comp, "nets": nets}
for c in spec["components"]:
    c.pop("_rail", None)

print("=== PRODUCT compose (netlist/label-style fix) ===")
# fail-loud: any compose exception propagates — no silent stub-swallow that
# leaves a stale wire-style sch. (v2 antipattern: TypeError on power_ports left
# the 09:16 draftsman残檔 masquerading as the deliverable → 189-pin misdiagnosis.)
try:
    r = compose_schematic(f"{FB}/sch_product", "aiguard_product", spec, symbol_dirs=SYMDIRS,
                          validate=True, style="netlist")
except Exception as e:
    print(f"FATAL compose failed: {type(e).__name__}: {e}", file=sys.stderr)
    raise
print("placed", r.placed, "nets", r.nets)
print("unresolved_pins", r.emit.unresolved_pins)
print("warnings", r.warnings)
if r.validation:
    print("erc_errors", r.validation.erc_errors,
          "components", r.validation.netlist_components,
          "nets", len(r.validation.netlist_nets))
