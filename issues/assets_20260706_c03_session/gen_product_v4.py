"""Product board schematic generator v04 — 方案 (a): label_nets={ALL}.

前棒 RCA 閉合:product 全板單頁 connector 密集,emit 對 2-node net 在 drawn-wire
mode 用 _orthogonal_route 畫 wire,密集 x column 共線熔合 → +3V3_PB 吞 189 pin。
呼叫層 style 窮舉(draftsman / netlist)皆 FAIL,因兩者對 2-node net 都畫 wire。

正解 (orchestrator 裁決 a):顯式傳 label_nets={所有 net 名}。emit.py:562
`force_label = label_nets is not None and net.name in label_nets` → 每個 net
force_label=True → :574 drawn-wire 分支 `drawn and not force_label` 短路 → 全走
global label,wire=0,collinearity-free by construction。

composer.py:589-593 只在 label_nets is None 時才套「>=3 節點」預設;外部傳入
非 None 即覆蓋,故顯式全集傳入生效。用 style="draftsman" 取得 placement
(netlist path 是 naive grid);connection_style 留 None 避免 explicit_conn 副作用。

gen_product.py 電氣定義(net 節點列表)一行未動 —— 只在呼叫層加 label_nets。
compose 例外 re-raise (fail-loud),杜絕 stale-sch 誤判。
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

# Capture comp + nets from gen_product.py with its own compose stubbed (patch on
# the MODULE so gen_product's top-level `from ... import compose_schematic`
# re-import resolves to the stub, else its wire-style compose overwrites ours).
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

# 方案 (a): spec["all_label"]=True → composer 把每個 net (2-node 含在內) 送 label。
# emit force_label=True 對全 net 生效 → wire=0，collinearity-free。
# 電氣定義（net 節點列表）一行未動 — 只加 all_label 旗標。
spec = {"components": comp, "nets": nets, "all_label": True}
for c in spec["components"]:
    c.pop("_rail", None)

print(f"all_label=True ({len(nets)} nets, includes 2-node)")

print("=== PRODUCT compose (style=draftsman + all_label) ===")
try:
    r = compose_schematic(
        f"{FB}/sch_product", "aiguard_product", spec, symbol_dirs=SYMDIRS,
        validate=True, style="draftsman",
    )
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
