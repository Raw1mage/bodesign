# BR_20260906 — `OccupancyLedger` wire reserves never survive to the final ledger (71 attempted, 0 landed)

- **Status**: OPEN
- **Family**: `eda-bridge` (see "Why not G13" below — this is a reserve that never lands, not a disclosure gap)
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py` (`_reserve_wire:1747-1759`), `packages/eda-bridge/bodesign_eda_bridge/occupancy.py` (`OccupancyLedger.try_reserve:343`)
- **Filed**: 2026-09-06, during WP6 closeout of `plans/c03_delivery_contract_and_engine_seams`
- **Related**: this plan's **DD-10** (`route_stats` carries neither WP6 quantity; no second parser over `.kicad_sch`), `BR_20260905_draftsman_connection_strategy_degenerates_to_label_farm_on_non_label_friendly_topology.md`, `BR_20260905_schematic_emitter_produces_pin_label_stubs_only_zero_pin_to_pin_wires_and_zero_junctions.md`

## Scope of this report — read this first

This BR proves **one** thing: the composer's `OccupancyLedger` **cannot be used as a
data source for `stub_share`**, because every `wire` rect written to it is rejected
and nothing about that rejection is visible downstream.

**The root cause is NOT investigated.** Why `_conflicts_with` rejects all 71 is not
determined here — it may be correct behaviour (wires genuinely crossing reserved
pin extents) or a defect (the inflation at `:1755-1758`, the owner semantics, or
the ordering against `pin_extent`). This report deliberately stops at the
measurement, because WP6 needed only to rule the ledger out as a channel and
diagnosing the router's keep-out semantics is a different piece of work.

Consequently: **do not read this as "the ledger is broken".** Read it as "the
ledger's `wire` arm has an attempt count of 71 and a survival count of 0, and no
caller can tell."

## Measurement

Live compose of the real btdongle board, `try_reserve` wrapped with a counting spy
that records both the attempt and the returned `ok`:

```
spec: 45 components / 27 nets
style="draftsman", validate=False, fidelity=False
```

| kind | attempts | succeeded | in FINAL ledger |
| --- | --- | --- | --- |
| `body` | 45 | **45** | 45 |
| `pin_extent` | 201 | **201** | 201 |
| `label` | 57 | **17** | 17 |
| **`wire`** | **71** | **0** | **absent** |
| **`power`** | **61** | **0** | **absent** |

`distinct ledger instances that saw a try_reserve: 1` — so this is not two ledgers
being confused for one; every reserve above went to the same object, and that
object ends as `{'body': 45, 'pin_extent': 201, 'label': 17}`.

**Controls.** The `body` and `pin_extent` rows are the positive control: the spy
sees reserves that DO land, so a zero in the `wire` row is a real rejection and not
a spy that never fired. The `label` row (57 → 17) is the discriminating control:
it shows the ledger *partially* accepting, so `wire`'s 0 is not "this ledger rejects
everything after some point". On the same run the emitter wrote **116 `(wire`** and
**6 `(junction`** to disk, and `emit.wire_runs` = 116 / `emit.junctions_emitted` = 6
— so the wires unquestionably exist; only their ledger entries do not.

**`power` shows the identical shape (61 → 0)** and was not part of the original
question. It is recorded here because it is the same signature, but it is likewise
undiagnosed.

## Why this matters (the WP6 consequence)

WP6 needed the drawn-run geometry to compute `stub_share`. The ledger looked like
the natural source — `_reserve_wire` writes a rect per accepted segment, so a
consumer would reasonably expect the drawn geometry to be readable from it after
the compose. It is not: **the rect is written and discarded in the same call**, and
`try_reserve` returns a `ReserveResult` whose `ok=False` the call site at
`kicad_emit.py:1759` **does not read**:

```python
ledger.try_reserve(LedgerRect(x0, y0, x1, y1, net_name, "wire"))
```

No assignment, no branch. A reserve that fails and a reserve that succeeds produce
**identical observable behaviour at this call site** — which is why 71 consecutive
failures could persist without anything reporting them.

That is what forced WP6's emission to be added directly in `kicad_emit.py` as
additive `SchematicEmitResult` fields (`wire_runs`, `junctions_emitted`) under the
round-8 boundary amendment, rather than derived from the ledger.

## Reproduction

```bash
cd /home/pkcs12/projects/bodesign
find . -name __pycache__ -prune -exec rm -rf {} +   # AGENTS.md §6.3
python3 - <<'PY'
import sys, glob, collections, importlib.util, tempfile, re
from pathlib import Path
sys.path[:0] = glob.glob('/home/pkcs12/projects/bodesign/packages/*/')
SCH = "/home/pkcs12/products/thesmart_products/04.btdongle/C03-EE/02_build/sch_gen"
m = importlib.util.spec_from_file_location("design", SCH + "/design.py")
design = importlib.util.module_from_spec(m); m.loader.exec_module(design)
from bodesign_eda_bridge import occupancy, compose_schematic
att, ok = collections.Counter(), collections.Counter()
orig = occupancy.OccupancyLedger.try_reserve
def spy(self, rect):
    att[rect.kind] += 1
    r = orig(self, rect)
    if r.ok: ok[rect.kind] += 1
    return r
occupancy.OccupancyLedger.try_reserve = spy
spec = {"components":[{"ref":r,"symbol":l,"value":v,"footprint":f,"group":g}
                      for r,l,v,f,g,_ in design.COMPONENTS],
        "nets":[{"name":n,"nodes":[f"{a}.{b}" for a,b in nd]}
                for n,nd in design.NETS.items()],
        "nc":[f"{a}.{b}" for a,b in getattr(design,"NO_CONNECT",[])]}
w = tempfile.mkdtemp(prefix="lp-", dir=os.environ.get("XDG_RUNTIME_DIR","/home/pkcs12/.cache"))
res = compose_schematic(out_dir=w, project_name="probe", spec=spec,
        symbol_dirs=[SCH,"/usr/share/kicad/symbols"],
        style="draftsman", validate=False, fidelity=False)
for k in sorted(set(att)|set(ok)):
    print(f"{k:12} attempts={att[k]:4} succeeded={ok[k]:4}")
PY
```

Expected: `wire` and `power` both print `succeeded=0`; `body` and `pin_extent`
print attempts == succeeded (the control that proves the spy fired).

## Suggested direction (NOT adjudicated)

Two separable pieces, in this order:

1. **Make the failure observable** — the call site discards a `ReserveResult` that
   carries `conflicts`. Whatever the correct geometry turns out to be, "71 wire
   reserves were refused" should not be silent. This is cheap and does not require
   deciding the semantics question.
2. **Then** decide whether the refusals are correct. Only after (1) is there
   anything to read while changing (2).

Doing (2) first would mean tuning geometry against an invisible signal.

## Not measured

- **Root cause of the rejections.** Not attempted. `_conflicts_with:315-329` is
  owner-aware and a wire's owner is its net name while a pin extent's owner is a
  component ref, so cross-owner geometric intersection is the plausible mechanism —
  but that is a hypothesis stated for the next reader, not a finding.
- Whether `power`'s 61 → 0 shares the cause with `wire`'s 71 → 0.
- Whether any consumer downstream depends on `wire` rects being absent (i.e.
  whether "fixing" this would change routing output). This matters: the router
  reads the ledger via `_route_clears_ledger:1729`, so landing 71 new rects could
  alter accepted routes. Not evaluated.
- Behaviour under `style="netlist"` — only `draftsman` was run.
