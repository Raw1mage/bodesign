# PC-001 Coverage and Waiver Boundary Receipt — 2026-10-09

Status: Complete measurement, test bounding, and receipt for Task 3.4. Non-fabricable; draft documentation only.
Authority: Freeze §4.19 Ruling R-K (content first). Dispatch: `[BRNS-DISPATCH] br=task-3.4-pc001-coverage-and-waiver-bounds reply-to=ses_04db7a1c5ffelvbxyLP1p6xlRH`.

---

## 1. Per-IC Measurement on S36 Six Leaves + Root

Target subject: S36 formal emission at `/work/experiments/s3-formal/c03_engine-v1/` (host `/home/pkcs12/projects/bodesign/experiments/s3-formal/c03_engine-v1/`).
BOM: `/work/products/bodesign/outputs/btdongle_ms/c03_engine-v1/bundle/bom/bom_per_ref.csv` (45 refs, components U1 ETA6003 and U2 RaspberryPi_Pico_2W).

Two measurement seams were executed:
1. **Public detector function**: `validation_detectors.validate_passive_completeness` (skill engine, schematic AST input).
2. **Served MCP gate**: `bodesign_check_c03` invoked over live UDS `/mcp/` socket (`.run/bodesign.sock`) with container paths.

### 1.1 Per-IC Measurement Table

| Ref | Value / Part | Symbol Sheet | Seam | Power Pins Found (Type) | Power Pins Found (Name Hint) | Non-GND Power Rails | Decoupling Found | Seam Verdict |
|---|---|---|---|---|---|---|---|---|
| **U1** | ETA6003 | `power_rail.kicad_sch` | `validate_passive_completeness` (Public function) | 4 (`IN`:2, `PGND`:5, `GND`:10, `EP`:17 as `power_in`) | 0 (`IN` not in hints) | `VBUS` (Pin 2) | Yes (C1, C2 bridge VBUS to GND) | **OK** (0 findings) |
| **U1** | ETA6003 | `native/root/btdongle_ms.net` | Served `bodesign_check_c03` (UDS MCP) | N/A (netlist pinfunction used) | 0 (`IN`, `SYS`, `BATT` not in hints) | None (`rails = []`) | N/A (0 rails checked) | **Unidentified rail** (`ics_without_identifiable_rail: ['U1']`) |
| **U2** | RaspberryPi_Pico_2W | `mcu_swd.kicad_sch` | `validate_passive_completeness` (Public function) | 2 (`ADC_VREF`:35, `VSYS`:39 as `power_in`) | 0 (`ADC_VREF`, `VSYS` not in hints) | `+3V3` (Pin 35; net `SYS` on Pin 39 not recognised as power) | Yes (C9, C10, C11 bridge +3V3 to GND) | **OK** (0 findings) |
| **U2** | RaspberryPi_Pico_2W | `native/root/btdongle_ms.net` | Served `bodesign_check_c03` (UDS MCP) | N/A (netlist pinfunction used) | 0 (`VSYS`, `ADC_VREF`, `3V3`, `VBUS` not in hints) | None (`rails = []`) | N/A (0 rails checked) | **Unidentified rail** (`ics_without_identifiable_rail: ['U2']`) |

### 1.2 Per-Sheet Seam Results

- **`validate_passive_completeness`**:
  - `root` (`btdongle_ms.kicad_sch` full hierarchy): U1 on `VBUS` (decoupled), U2 on `+3V3` (decoupled). 0 findings.
  - `power_rail.kicad_sch`: U1 on `VBUS` (decoupled). 0 findings.
  - `mcu_swd.kicad_sch`: U2 on `+3V3` (decoupled). 0 findings.
  - `battery.kicad_sch`: 0 active ICs in scope. 0 findings.
  - `charge_enable.kicad_sch`: 0 active ICs in scope. 0 findings.
  - `io.kicad_sch`: 0 active ICs in scope. 0 findings.
  - `usbc.kicad_sch`: 0 active ICs in scope. 0 findings.

- **Served `bodesign_check_c03` over UDS**:
  - Across all netlist targets (`root`, all six individual leaves, `all_leaves`, `all_7`):
    - `gate: FAIL` (due to baseline R3_DRAWABILITY on unadorned BOM).
    - `passive_completeness.status: "not_run"`
    - `passive_completeness.reason: "the netlist carries pinfunction annotations but NO active IC in the BOM exposed a supply pin on a power net, so zero rails were examined. A PASS here means nothing was looked at."`
    - `passive_completeness.rails_checked: None`
    - `passive_completeness.ics_without_identifiable_rail: ["U1", "U2"]`
    - `passive_completeness.waivers: {"status": "not_run", "reason": "passive_waivers.json sidecar (DD-3) is NOT ported to the delivery path in this pass — every decoupling gap blocks here and NO waiver can be honoured, however well-provenanced"}`
    - PC-001 blocking findings: 0 (rule reports `not_run`, refusing to falsely pass or fail).

---

## 2. Coverage Boundary Statement

### 2.1 What PC-001 CAN Judge
1. **In `validation_detectors.py` (skill-side public function)**:
   - Components explicitly typed as `comp.type in {'ic'}`.
   - Supply pins with electrical type in `{'power_in'}`.
   - Supply pins lacking `power_in` type whose name contains a hint from `_POWER_PIN_NAME_HINTS` (`VDD`, `VCC`, `AVDD`, `DVDD`, `VBAT`, `VIN`, `VDDA`, `VDDIO`, `VREF+`, `AVCC`, `VDDCORE`, `VDD33`, `VDD18`).
   - Power nets identified by `#PWR` symbols or standard prefixes/names (`+*`, `VCC`, `VDD`, `VBUS`, `VBAT`, etc.).
2. **In `bodesign_workflow_core.check_c03` (delivery-path gate)**:
   - Components whose reference starts with `U` (`r.get("_ref").upper().startswith("U")`).
   - Pins whose netlist `pinfunction` contains a token from `_PC_POWER_PIN_HINTS`.
   - Nets matching `_polarity_of(net) == "power"` (`_PWR_PATTERN` regex).

### 2.2 What PC-001 CANNOT Judge (Reproduced Fixture Gap Classes)
1. **Supply pin naming mismatch (Plan 2.8 gap class A)**:
   - Charger/buck input pin named `IN` (e.g. ETA6003 pin 2): misses in `check_c03` because hints contain `VIN` but not `IN`.
   - System supply pins named `VSYS` (e.g. Pico W pin 39): misses in `check_c03` because hints omit `VSYS`.
   - Voltage reference pins named `ADC_VREF` or `VREF`: misses in `check_c03` because hints expect `VREF+`.
   - 3.3V power pins named `3V3`: misses in `check_c03` because hints expect `VDD33`.
   - USB power pins named `VBUS`: misses in `check_c03` because hints omit `VBUS`.
2. **Net name polarity mismatch (Plan 2.8 gap class B)**:
   - Regulated power net named `SYS`: `ctx.is_power_net("SYS")` is False; `_polarity_of("SYS")` is None. Consequently, supply pins connected to `SYS` are not recognized as power rails, leaving decoupling on `SYS` completely unverified.
3. **Refdes prefix mismatch**:
   - Multi-chip modules or active ICs lettered other than `U*` (e.g. `MOD1`, `IC1`, `N1`) are bypassed by `check_c03`.
4. **Non-IC symbol category**:
   - Devices typed as `module`, `subcircuit`, or `connector` are bypassed by `validate_passive_completeness` (`comp.type != 'ic'`).
5. **Completely floating / isolated power pins**:
   - An active IC whose `power_in` pins have NO nets attached has 0 detectable rails; `validate_passive_completeness` line 1290 executes `if not rails: continue` ("Skip rather than false-positive"), silently returning zero findings.

---

## 3. Waiver Boundary Statement

1. **Hierarchy case (leaf sidecar next to sub-sheet)**:
   - When `check_c03` is called on the project root, a `passive_waivers.json` sidecar placed next to a leaf `.kicad_sch` is **NOT honoured**.
   - `check_c03` delivery path declares `waivers.status == "not_run"`, as the DD-3 waiver sidecar has not been ported to the delivery path. Every undecoupled IC remains a blocking `PC-001` error.
2. **Skill-side `validate_passive_completeness`**:
   - `_load_passive_waivers(sch_path)` inspects only `os.path.dirname(sch_path)`. When called with `sch_path` pointing to the root schematic, sidecars located in child sheet subdirectories are ignored.

---

## 4. The Three Case Outcomes

1. **(1) EMPTY sheet (zero symbols)**:
   - `validate_passive_completeness` returns `[]` findings.
   - The test asserts that zero findings is bounded by `active_ics == []` (explicitly zero active ICs in scope), rather than a pass-by-absence.
2. **(2) ISOLATED active IC (power_in pins with NO nets attached)**:
   - `validate_passive_completeness` currently **silently passes** (`findings == []`) because `_ic_power_rails` requires a connected net to identify a rail, and line 1290 skips ICs with zero identifiable rails.
   - In `check_c03`, the IC is named under `ics_without_identifiable_rail: ['U1']` with status `not_run`.
   - Tested and bounded in unit test `test_isolated_active_ic_unconnected_power_pins_bounds`.
3. **(3) NC-marked power pin (carrying no-connect flag)**:
   - `validate_passive_completeness` currently **silently passes** (`findings == []`) because `no_connect` flags are not inspected by PC-001, and pins without a connected power rail net are skipped.
   - Tested and bounded in unit test `test_nc_marked_power_pin_silently_passes_bounds`.

---

## 5. Test Execution Evidence

Unit tests executed via `./scripts/run_tests.sh test_passive_completeness test_check_c03_passive_completeness` with preceding `find . -name __pycache__ -prune -exec rm -rf {} +`.

### 5.1 Before
```text
Ran 19 tests in 0.018s

OK
```

### 5.2 After (4 new unit tests added)
```text
Ran 23 tests in 0.024s

OK
```

Git whitespace check:
```bash
git diff --check
# rc=0 (clean)
```

---

## 6. Changed Files and SHA256

```text
269ff0ca1ee542228d15e133bedf0b7c0bd435ede4223359e53e80c8194b5ce1  tests/test_passive_completeness.py
4f49792a936fe426dbf8face33af759dc9fbb77c8609b1d0076940aec490f684  tests/test_check_c03_passive_completeness.py
```

---

## 7. NOT MEASURED List

1. Visual layout, aesthetic review, or human CMF sign-off.
2. Electrical design approval or release sign-off.
3. Fabrication/manufacturing readiness approval.
4. Source code modifications to `validation_detectors.py` or `check_c03.py` (explicitly forbidden by dispatch order: measure + test + document only).
5. Re-measurement of the historical `aiguard` board (explicitly excluded by dispatch order).

---

## 8. Fix: Served bodesign_check_c03 PC-001 Real Verdict (BR_20261009)

Authority: Dispatch `[BRNS-DISPATCH] br=BR_20261009_check_c03_pc001_identifies_no_power_rail_on_u1_u2_while_detector_judges_them_ok reply-to=ses_04db7a1c5ffelvbxyLP1p6xlRH`.

### 8.1 Root Cause & Diff Summary
- **Root Cause**: `check_c03.py` `_ic_power_rails` identified supply pins solely via pinfunction matching `_PC_POWER_PIN_HINTS` on nets where `_polarity_of(net) == "power"`. Symbols on KiCad netlists already carry `pintype "power_in"` (e.g. ETA6003 pin 2 "IN" on `VBUS`, Pico_W pin 39 "VSYS" on `SYS`, pin 35 "ADC_VREF" on `+3V3`), and net `SYS` returned `_polarity_of("SYS") = None`. Consequently, supply pins were missed and reported as 0 rails examined (`not_run`).
- **Diff Summary**:
  1. `_polarity_of`: Recognise numbered ground tokens (e.g. `gnd2`, `vss1`) as `"gnd"` via `head.startswith(g) and head[len(g):].isdigit()`.
  2. `_netlist_pin_meta`: Single-pass netlist parser extracting `{ref: {pin: pinfunction}}` and `{ref: {pin: pintype}}` without redundant reading. `_netlist_pin_functions` delegates to it.
  3. `_ic_power_rails`: Type-first supply pin identification (`power_in` on non-ground net, `_polarity_of(net) != "gnd"`), fallback to hint matching on power nets (`_polarity_of(net) == "power"`). Returns `(rails, identified_by)` tracking `identified_by: type|hint` per rail.
  4. `_check_passive_completeness`: Exposes `identified_by` in `ics_checked`. Active ICs without identifiable rails (`ics_no_rail`) emit blocking `RowFinding(..., ref, "PC-001", ...)` entries, ensuring `gate=FAIL` and never a silent non-verdict.

### 8.2 Per-IC Rails & Identification Table (S36 btdongle_ms.net)

| Ref | IC Part | Netlist Supply Pins | Rail(s) Identified | identified_by | Decoupling Caps to GND | Verdict |
|---|---|---|---|---|---|---|
| **U1** | ETA6003 | Pin 2 (`IN`, `power_in`) | `['VBUS']` | `{'VBUS': 'type'}` | C1, C2 bridge VBUS to GND | **ok** |
| **U2** | RaspberryPi_Pico_2W | Pin 35 (`ADC_VREF`, `power_in`), Pin 39 (`VSYS`, `power_in`) | `['+3V3', 'SYS']` | `{'+3V3': 'type', 'SYS': 'type'}` | C9, C10, C11 bridge +3V3 to GND; C4–C8 bridge SYS to GND | **ok** |

- `passive_completeness.status`: `"run"`
- `passive_completeness.reason`: `None`
- `passive_completeness.rails_checked`: `3`
- `passive_completeness.ics_without_identifiable_rail`: `[]`

### 8.3 Test Execution Evidence (pycache cleared)

- **BEFORE**:
```text
Ran 37 tests in 0.036s

OK
```

- **AFTER** (4 new unit tests added covering cases a–d):
```text
Ran 41 tests in 0.039s

OK
```

Git whitespace check:
```bash
git diff --check
# rc=0 (clean)
```

### 8.4 Changed Files and SHA256

```text
ab167ee212689dec27e63f7439ebb184c5510db28d42f05d144a017f33eb1519  packages/workflow-core/bodesign_workflow_core/check_c03.py
65dbfd5ce62c078a4f884106d313b5f012cd9911363aff28309adce9ade2c05d  tests/test_check_c03_passive_completeness.py
```

### 8.5 Served Raw SSE Excerpt (Live UDS `/mcp/`)

Invoked over `/home/pkcs12/projects/bodesign/.run/bodesign.sock` against:
- BOM: `/work/products/bodesign/outputs/btdongle_ms/c03_engine-v1/bundle/bom/bom_per_ref.csv`
- Netlist: `/work/experiments/s3-formal/c03_engine-v1/native/root/btdongle_ms.net`

**Before Fix**:
```json
"passive_completeness": {
  "status": "not_run",
  "reason": "the netlist carries pinfunction annotations but NO active IC in the BOM exposed a supply pin on a power net, so zero rails were examined. A PASS here means nothing was looked at.",
  "rails_checked": null,
  "ics_checked": null,
  "ics_without_identifiable_rail": ["U1", "U2"],
  "waivers": { ... }
}
```

**After Fix (Served Raw Excerpt)**:
```text
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"{\n  \"ok\": true,\n  \"result\": {\n    \"schema\": \"bodesign.c03.stage_entry_gate.v1\",\n    \"gate\": \"FAIL\",\n    \"blocking\": [\n      {\n        \"board\": \"\",\n        \"ref\": \"<schema>\",\n        \"code\": \"R3_DRAWABILITY\",\n        \"detail\": \"no symbol-source column found in BOM header (looked for: symbol_source, symbol, sym_source, drawability, deck_status) — cannot assess drawability for any row\"\n      }\n    ],\n    \"warnings\": [],\n    \"bom_rows\": 45,\n    \"active_parts\": 8,\n    \"ssot_checked\": false,\n    \"netlist_crosscheck\": {\n      \"status\": \"run\",\n      \"netlists\": [\n        \"btdongle_ms.net\"\n      ],\n      ...\n    },\n    \"passive_completeness\": {\n      \"status\": \"run\",\n      \"reason\": null,\n      \"ics_checked\": [\n        {\n          \"ref\": \"U1\",\n          \"rails\": [\n            \"VBUS\"\n          ],\n          \"identified_by\": {\n            \"VBUS\": \"type\"\n          },\n          \"undecoupled\": [],\n          \"verdict\": \"ok\"\n        },\n        {\n          \"ref\": \"U2\",\n          \"rails\": [\n            \"+3V3\",\n            \"SYS\"\n          ],\n          \"identified_by\": {\n            \"+3V3\": \"type\",\n            \"SYS\": \"type\"\n          },\n          \"undecoupled\": [],\n          \"verdict\": \"ok\"\n        }\n      ],\n      \"rails_checked\": 3,\n      \"ics_without_identifiable_rail\": [],\n      \"scope\": \"presence of >=1 rail->GND capacitor per identified power rail on U* parts; value, count and placement are NOT examined\",\n      \"waivers\": {\n        \"status\": \"not_run\",\n        \"reason\": \"passive_waivers.json sidecar (DD-3) is NOT ported to the delivery path in this pass — every decoupling gap blocks here and NO waiver can be honoured, however well-provenanced\"\n      }\n    }\n  }\n}"}],"isError":false}}
```
