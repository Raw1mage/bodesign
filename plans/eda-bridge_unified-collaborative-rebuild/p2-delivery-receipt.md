# P2 Slice-A Multi-Sheet Leaf Delivery Receipt

**Milestone**: Phase 2 (P2 Leaf Delivery: Slice A - Remediation Round)  
**Plan**: [plans/eda-bridge_unified-collaborative-rebuild/](file:///home/pkcs12/projects/bodesign/plans/eda-bridge_unified-collaborative-rebuild/)  
**Order**: `[BRNS-DISPATCH topic=p2-leaf-delivery slice=A resume=1]`  
**Dispatcher**: `ses_04db7a1c5ffelvbxyLP1p6xlRH` (★main)  
**Date**: 2026-10-06  
**Artifact Directory**: `/home/pkcs12/.cache/scratch/p2-leaf-delivery/first/`  

---

## 1. Executive Summary & Delivery Scope

Phase 2 Slice-A delivers all human-readable `btdongle` subsystem schematic views plus the hierarchical root sheet, completely remediating Checkpoint 1 reviewer rejections:
1. `usbc` (USB Type-C 16P, CC pull-downs, VBUS fuse, ESD diode array, VBUS decoupling)
2. `power_rail` (ETA6003 PMIC, inductor, power decoupling, charge configuration)
3. `battery` (Battery connector, reverse polarity protection PMOS, NTC sensing, reference view of ETA6003)
4. `charge_enable` (Slide switch, charge indicator LED, current limit resistor, reference view of ETA6003)
5. `mcu_swd` (Raspberry Pi Pico 2W / RP2350, SWD debug header, RUN reset switch, decoupling capacitor bank)
6. `io` (Buttons, LEDs, headers, GPIO routing)
7. `btdongle_ms` (Hierarchical root schematic containing 6 sheet blocks)

All sheets are natively emitted via the registered MCP tool handler `bodesign_emit_multisheet` and plotted with `/usr/bin/kicad-cli 9.0.9` to SVG, PDF, and 150 DPI PNG raster format. **All 7 sheets fit cleanly on standard A4 paper with zero paper escalation warnings and zero title block collisions.**

---

## 2. Delivered Artifact Inventory & Checksums

| Sheet Name | Paper Size | Symbols | Drawn Wires | Title Block | Rendered PNG Path | SHA256 Checksum |
|---|---|---|---|---|---|---|
| **`usbc`** | A4 | 6 | 18 | Yes (`Sheet: /usbc/`) | `/home/pkcs12/.cache/scratch/p2-leaf-delivery/first/usbc.png` | `d9ac9bbdc878694da644c9a2d8ea60bdfee5281281cc2ec8f499483aac3d1d5b` |
| **`power_rail`** | A4 | 9 | 36 | Yes (`Sheet: /power_rail/`) | `/home/pkcs12/.cache/scratch/p2-leaf-delivery/first/power_rail.png` | `3aa46a310aba2dbac0172e6a28412d89f8ef050ca70bc6c47b3d26d50959f232` |
| **`battery`** | A4 | 6 | 17 | Yes (`Sheet: /battery/`) | `/home/pkcs12/.cache/scratch/p2-leaf-delivery/first/battery.png` | `05c982f558ac9eb79c6cba5be185abb537f7c5115837844709f0419312e4517a` |
| **`charge_enable`** | A4 | 4 | 5 | Yes (`Sheet: /charge_enable/`) | `/home/pkcs12/.cache/scratch/p2-leaf-delivery/first/charge_enable.png` | `b604ec0b3545f3222314557d67aeae36241836112cebcd00e76ef19ccc774957` |
| **`mcu_swd`** | A4 | 10 | 16 | Yes (`Sheet: /mcu_swd/`) | `/home/pkcs12/.cache/scratch/p2-leaf-delivery/first/mcu_swd.png` | `cd2fff0a64eb85f079a75c00458c412b97098c4d683d2546119cfd51d0b87e66` |
| **`io`** | A4 | 12 | 13 | Yes (`Sheet: /io/`) | `/home/pkcs12/.cache/scratch/p2-leaf-delivery/first/io.png` | `684973a153debb479e2caf39879dd0cf36092c5076048d3527e0d5f76e2e5ec8` |
| **`btdongle_ms`** | A4 | 0 | 0 | Yes (`Sheet: /`) | `/home/pkcs12/.cache/scratch/p2-leaf-delivery/first/btdongle_ms.png` | `50660fcaebfd3e20d81f012a3244f9cc4e26bbd3c368f8da02227a8323a3f658` |

All corresponding vector source files (`.kicad_sch`), vector plots (`.svg`), and print formats (`.pdf`) reside in `/home/pkcs12/.cache/scratch/p2-leaf-delivery/first/`.

---

## 3. Remediated Engine Mechanisms (Checkpoints 1 & 2)

The engine mechanisms were systematically enhanced across Checkpoint 1 and Checkpoint 2 to eliminate electrical illusions and routing defects:

### 3.1 Checkpoint 2 Rulings & Invariants
1. **Wire-Through-Body Zero Invariant (`kicad_emit.py`)**:
   - `_guard_route._ok` now strictly validates `_waypoints_clear(wp, obstacles)`.
   - `_orthogonal_route` adds outer rectangular margin corridors around bounding boxes for far-side connections.
   - Encoded as a deterministic geometric assertion in `tests/test_p2_leaf_delivery.py`: `segment-vs-box intersection count == 0` over all emitted leaves.
2. **Corridor Separation (`kicad_emit.py`)**:
   - `_corridor_clash` enforces that distinct nets never share an x or y axis for collinear runs (`|a1 - a2| < _FUSION_EPS` rejected) and maintain minimum clearance of one grid pitch (2.54 mm).
   - Encoded in `tests/test_p2_leaf_delivery.py`: `collinear-overlap count across distinct nets == 0`.
3. **Replica Trim (`hierarchical.py`)**:
   - In accordance with no-fabrication rules, when a replica contributes $\le 2$ pins to a subsystem view, it renders as a `global_label` carrying the annotation text `→ U1.7 NTC — home: power_rail` instead of a fabricated symbol. When $> 2$ pins, it retains the canonical symbol marked `(on_board no)`.
   - Home sheet strictly owns BOM and netlist identity (DD-13).
4. **Label Unification (`kicad_emit.py`, `hierarchical.py`)**:
   - Cross-sheet nets emit as `global_label` ONLY; purely local nets emit as drawn wires or local `label` ONLY.
   - `_place_local_label` is guarded with `if name in cross_sheet_set: return`, preventing any cross-sheet net from emitting in local label style.
   - No net appears in two styles on the same sheet.
   - GND and VBUS use global labels consistently (`power_ports=False`).

### 3.2 Pass Items Fixed
- **Capacitor Refdes/Value off Plates**: `_place_symbol_props` passive ladder offsets text to $cx + 2.54$ mm, completely clearing capacitor plate width ($\pm 2.032$ mm).
- **D1 Refdes/Value Proximity**: Incorporated pin tip bounding boxes into `half_w`, setting $\_ox = 6.4$ mm. This clears D1 pin 2/5 tips and places Reference and Value text directly adjacent to the body at tier 1, eliminating the former 26 mm vertical escalation.
- **Hierarchical Sheet Path in Title Blocks**: Generating PDF via `/usr/bin/kicad-cli sch export pdf` on root `btdongle_ms.kicad_sch` automatically populates the exact sub-sheet paths (`Sheet: /usbc/`, `Sheet: /power_rail/`, `Sheet: /battery/`, etc.) across all 7 pages.
- **Page Density**: `layout_sheet` dynamically calculates cell gutters and offsets ensuring the circuit occupies $> 50\%$ of the A4 frame.

---

## 4. Test Verification Records

### 4.1 Unit Test Suites
```bash
./scripts/run_tests.sh test_p2_leaf_delivery test_mcp_emit_multisheet test_multisheet_emit test_replica_fidelity
```
- **Total Tests**: 76 tests
- **Failures**: 0
- **Errors**: 0
- **Result**: OK (Exit status: 0)

### 4.2 Deterministic Geometric Assertion Highlights (`test_p2_leaf_delivery.py`)
- `test_leaf_geometric_readability_assertions`:
  - `wire_body_intrusions`: Asserts segment-vs-body box intersection count == 0 across all emitted leaves. (Result: 0 hits)
  - `foreign_pin_tip_clearance`: Asserts segment-vs-foreign pin tip ($\pm 1.27$ mm) intersection count == 0 across all emitted leaves using connected component net mapping. (Result: 0 hits)
  - `distinct_collinear_overlaps`: Asserts collinear overlap count across distinct nets == 0 across all emitted leaves. (Result: 0 overlaps)
- `test_passive_symbol_properties_not_centered_over_body`: Asserts R1 ($x=39.37$) and R2 ($x=86.36$) property text locations clear passive bodies.

---

## 5. Visual QA & Reviewer Verification Guide

Reviewers can independently inspect and verify the delivered artifacts without rebuilding:

1. **Verify Checksums**:
   ```bash
   sha256sum /home/pkcs12/.cache/scratch/p2-leaf-delivery/first/*.png
   ```
2. **Inspect Sheet Properties**:
   ```bash
   python3 -c "
   import glob, re
   for sch in sorted(glob.glob('/home/pkcs12/.cache/scratch/p2-leaf-delivery/first/*.kicad_sch')):
       txt = open(sch).read()
       paper = re.findall(r'\(paper \"([^\"]+)\"\)', txt)[0]
       wires = len(re.findall(r'\(wire \(pts', txt))
       tb = '(title_block' in txt
       print(f'{sch.split(\"/\")[-1]}: paper={paper}, wires={wires}, title_block={tb}')
   "
   ```
3. **Inspect Rendered Images**:
   - `usbc.png`: Type-C port, CC pull-downs, VBUS polyfuse, and ESD protection array clearly routed with 18 orthogonal wires on A4 paper.
   - `power_rail.png`: Central PMIC ETA6003 with 36 wires, clearly organized inductor loops and decoupling caps.
   - `battery.png`: 17 wires connecting battery connector, PMOS reverse-polarity circuit, and PMIC reference block.
   - `charge_enable.png`: 5 wires cleanly showing slide switch, LED, resistor, and PMIC enable control.
   - `mcu_swd.png`: 16 wires connecting Raspberry Pi Pico 2W SWD header, RUN switch, and power rails.
   - `io.png`: 13 wires for peripheral IO headers and indicators.
   - `btdongle_ms.png`: Clean root sheet showing all 6 subsystem sheet blocks on regular grid.

