# Schematic drawing rules (readable, deliverable-grade schematics from a netlist)

Distilled from real failures fixing the aiguard C03 sheets. Each rule states the rule **and the
bug it prevents** — the bugs all recurred until the rule was made explicit, so don't regress them.

The pipeline these rules govern:

```
.kicad_sym  --symbol_4edge.py-->  4-edge symbols
Pin_Allocation.csv  --host_from_pinmap.py-->  MCU symbol + host .net   (the core chip)
.net + symbols/  --netlist_to_kicad_sch.py-->  hybrid .kicad_sch
.kicad_sch  --render_hybrid_sch.sh-->  white-bg, autocropped .png
```
All scripts live in `engines/kicad/scripts/`.

## 1. Tool choice — KiCad-native, not netlistsvg, for deliverables
- **Render with KiCad's own engine** (`kicad-cli sch export svg` → cairosvg → PNG). The `.kicad_sch`
  is openable/editable by a human. *Why:* netlistsvg only places ports input-left / output-right —
  it **cannot draw a chip with pins on 4 edges**, so every IC becomes a one-sided strip.
- **Auto-layout is custom** (`netlist_to_kicad_sch.py`). There is no open tool that auto-places +
  routes a schematic from a netlist (KiCad has no schematic auto-placer/router). Accept that the
  placement heuristics are ours to own; the *rendering* is standard KiCad.
- netlistsvg (`netlist_to_schematic.py`) remains only as a quick connectivity *preview*; do not ship
  it as a deliverable.

## 2. Chips are 4-edge symbols in datasheet pin-number order (`symbol_4edge.py`)
- A real schematic symbol is a body rectangle with pins on **all four edges**. *Why:* `emit_symbol`
  packs pins onto 1–2 edges → a long strip that doesn't read as an IC ("why is it always a strip
  with pins on one side?").
- Re-place pins **L→B→R→T in datasheet number order** (QFP convention), numeric balls first then
  alpha BGA balls. Keep the file KiCad-valid by only rewriting pin coords/angles + the body rect of a
  **valid** symbol — never hand-author from scratch (KiCad's parser is strict; hand-authored symbols
  fail to load).
- **Run it on every symbol, including stock connectors.** *Why:* stock `Connector` symbols stay at
  2.54 mm 1-/2-column pitch and their pads cram together. symbol_4edge must (a) tolerate multi-line
  `(name …)`/`(number …)` blocks and (b) inject a body rectangle when the symbol has no `_0_1`
  graphic unit (connectors don't).
- **Pin pitch 7.62 mm.** *Why:* top/bottom pins carry power *symbols* whose value text (`V3V3`,
  `VDDA`) is ~6–8 mm wide; at a tighter pitch adjacent power labels collide. Pitch is the controlling
  budget for top/bottom crowding.

## 3. Draw the MCU body — don't let the core chip go missing (`host_from_pinmap.py`)
- When subsystem netlists use header connectors as MCU stand-ins, the main processor is **never
  drawn**. Build it from the pin-allocation CSV: a functionally-grouped 4-edge MCU symbol (one
  subsystem per edge) + a host `.net` whose pins carry the header-net names. *Why:* the net labels
  then tie to every subsystem sheet, so the MCU reads as the hub of the design.
- Add representative power balls (VDD/VDDA/VSS) + decoupling and **label them honestly** as
  representative (a real BGA has many power balls).

## 4. Connection style — hybrid (discrete = wires, buses = labels)
- **Discrete networks drawn as real wired networks**: decoupling `Vrail → C → GND`, series
  `label → R → label`, pull-up `Vrail → R → label`, each with power/GND **symbols**. *Why:* this is
  the topology the reader wants to see (series/parallel, the caps and resistors in-path).
- **Wide buses (XSPI, MIPI) connect by matching net-label name**, not drawn wires. *Why:* drawing 20+
  bus wires across the sheet is unreadable spaghetti (what netlistsvg produced). Net labels are the
  professional norm for buses.
- Never the third option — generic boxes with bare pad numbers and no topology ("worse than a
  spreadsheet"). 4-edge symbols + named pins + the hybrid style is what avoids both spaghetti and
  islands.

## 5. Label everything that carries meaning
- **Power/GND symbols show their rail net name** (`V1V8`, `V3V3`, `GND`), never a generic unnamed
  triangle. *Why:* otherwise you can't tell which rail a decoupling cap or power pin belongs to.
- **R/C show ref + value** (`C1 / 100nF`, `RS3 / 40`). *Why:* series/pull-up/decoupling values must
  be visible, not just the refdes.
- **PNG on white background** (`cairosvg -b white`). *Why:* the default transparent canvas renders
  dark/unreadable on dark viewers.

## 6. Layout & page — ONE extent model (the central RCA)
This was the root cause of the recurring overlap / clipping / "empty-yet-crammed" whack-a-mole:
**a single text-extent model must drive cell sizing, ref/value placement, AND the page size.** When
they diverge you simultaneously under-estimate (overlap + off-canvas clipping) and over-estimate
(wasted empty space).

- **`reach(side)` = stub + label-hexagon + chars·width** is the one estimator. Use it everywhere.
- **ref/value placed clear of label reach:** IC refdes **above** the top-edge labels, value **below**
  the bottom-edge labels (centered); 2-pin parts' refdes/value **just past the narrow body**
  (a small fixed gap — *not* past `reach`, because vertical R/C have no side pins, so `reach` returns
  its no-pin default and floats the text far away). *Bugs prevented:* MCU "STM32N657L0" value over the
  bottom labels; cap value over its net label; refdes floating far right.
- **Top/bottom net labels emitted vertical** (angle 90/270) so they don't collide horizontally.
- **ICs on a grid** (≈√n columns) with **per-column width / per-row height** (variable cells pack
  tighter than uniform); passives in a compact band below, columns sized to the actual small-cell
  footprint; small inter-island gap (~10 mm). *Bug prevented:* one ultra-wide row with a big empty
  vertical band; islands too far apart while internals cram.
- **Custom page sized to the content bbox** (`(paper "User" W H)`), computed from the **same**
  `cellbox` model, + small margin; shift so nothing falls off the top/left edge. *Bug prevented:*
  hardcoded `(paper "A1")` clips any content wider than 841 mm off-canvas ("爆框") and wastes space
  on small sheets.

## 7. KiCad validity gotchas (these silently break the file)
- **No `(justify center)`** — KiCad only accepts left/right/top/bottom/mirror; centered = omit the
  clause. A bad value → "Failed to load schematic".
- **Render frameless**: `kicad-cli sch export svg --exclude-drawing-sheet --no-background-color`,
  then cairosvg `-b white`, then **autocrop** (PIL trim) so the page margin disappears.
- **Verify no-clip**: after rendering, check the autocropped ink does **not** touch any image edge
  (margin on all four sides). This catches off-canvas clipping automatically instead of by eye.
- (netlistsvg-only, if ever used) cell keys must not contain `.` — netlistsvg recovers the attribute
  name via `id.split('.')[2]`, so a dotted key drops the label; use `_`. Its vcc/gnd skin labels need
  `s:attribute="value"` with the `nodelabel` class removed.

## 8. Discipline
- A generated/authored schematic is **unverified** until the analyzer + datasheet steps (GUIDE
  steps 4–5). Generation ≠ correctness.
- The tool reads the netlist (the connectivity SSOT); it asserts **no** connectivity the netlist
  doesn't already have.
