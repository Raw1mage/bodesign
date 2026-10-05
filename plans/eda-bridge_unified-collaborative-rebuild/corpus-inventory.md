# P0.3 Test Corpus & Mechanical Availability Inventory

**Milestone**: Phase 1 (P0 Baseline Inventory, Suite Classification & Corpus Setup)  
**Task**: P0.3 / Section 1.3 in [tasks.md](file:///home/pkcs12/projects/bodesign/plans/eda-bridge_unified-collaborative-rebuild/tasks.md)  
**Date**: 2026-10-06  
**Status**: Completed (Reconciled with Astra Architecture Review)  
**Rule Compliance**: Strict inventory and classification. Zero data mutation, zero external credentialing, zero AGPL code copying.

---

## 1. Authorized Test Corpus Classification

The test corpus provides verified reference benchmarks across each circuit and design tier. All GUEST repository files are accessed **READ-ONLY**.

| Corpus Name | Domain & Class | Primary Input Files & SHA256 | Expected Outputs Status | Access Permission | Key Characteristics & Architecture Scope |
|---|---|---|---|---|---|
| **`04.btdongle`** | **MCU / RF / PMIC** | `C03-EE/02_build/sch_gen/design.py`<br>`SHA256: 0c2efef734f1ecacbd6c01ec27357c425ed20bbf7794bdb4d62c1a9c245cbb00` | **Expected Outputs Present**:<br>• Human delivered schematics (`mk_sch.py` generated, 426 wires, 56 junctions across 3 sheets)<br>• Multi-sheet generator output `btdongle_ms.net`<br>• C02 enclosure STEP & STL | **GUEST REPO (READ-ONLY)** | 45 components, 27 canonical nets, 58 node classes. ETA6003 Li-Po charger (`U1`), RP2350 Pico 2 W (`U2`), Type-C (`J1`). Reference for hierarchical multi-sheet schematics (5 subsystem views, 2 replica instances). |
| **`03.aiguard`** | **MCU / Sensor (High-Density Edge AI)** | `experiments/aiguard_c04/aiguard_ccm.net`<br>`SHA256: d3b69cc3a6fdaf3532bd6daaedfd517feb751eaee4232adf5b4aafcfc13e2cf9`<br>`03.aiguard/README.md`<br>`SHA256: 1c8173d780e587ddbdea8a6a75c9f6118d277aad2efdbc4e4a11874941d9f7a8` | **Expected Outputs Present**:<br>• Routed 8-layer board `ccm8_routed.kicad_pcb`<br>• Final poured board `ccm8mp40_final.kicad_pcb`<br>• Enclosure concept STLs | **GUEST REPO (READ-ONLY)** | **MCU / Sensor Reference Case**: STM32N657 MCU (VFBGA223), Sony IMX335 image sensor, ST LSM6DSM IMU motion sensor, NRF7002 companion (QFN48). High-density 8-layer board layout, VIP fanout, micro-stubs, plane pouring, BGA escape. |
| **`01.openmv`** | **MCU / Sensor (Embedded Vision)** | `01.openmv/README.md`<br>`SHA256: 5e1d0997d39a503ed8ab1f14cb58f5eaabe58e93318babd762450f457b6e1696` | **Expected Outputs: NONE (Unmeasured)**:<br>Upstream product reference files present; no formal bodesign end-to-end regression output committed yet. | **GUEST REPO (READ-ONLY)** | **MCU / Sensor Reference Case**: STM32H743VI MCU + OmniVision OV7725/OV5640 image sensors. Multi-sheet schematic reference and gap report fixture. |
| **`e2e-led-driver`** | **Power / Interface / Analog** | `C03-EE/e2e-led-driver.kicad_sch`<br>`SHA256: 876e6c5f1093bd00da3bcc5b76689e922fdbe24eadcce8da19f61a936928114d`<br>`C03-EE/e2e-led-driver.kicad_pro`<br>`SHA256: 15a17e27a30b0284403a4c96c3b73578ded4be8722e3db25d13fda196e81de87` | **Expected Outputs Present**:<br>• Routed 2-layer board `e2e-led-driver.routed.kicad_pcb`<br>• Poured board `e2e-led-driver.poured.kicad_pcb`<br>• Fab STEP assembly `fab/e2e-led-driver.poured.step` | **IN-REPO FIXTURE** | Discrete analog power fixture: S8050 NPN transistor, current-limiting resistors, flyback diode, screw terminal connector. Complete C03 schematic -> C04 layout -> fab STEP assembly. |
| **`02.rockbox`** | **Consumer Media Audio** | `02.rockbox/README.md`<br>`SHA256: dcf88c82c7f94d756a220e732c0aefdd1664ba6cdf889d7f36140c78dc17d6e5` | **Expected Outputs: NONE (Raw Evidence Only)**:<br>Reverse-core extraction artifacts present; formal C03 emission outputs absent. | **GUEST REPO (READ-ONLY)** | Complex multi-IC consumer audio architecture; used for reverse-core extraction and format parity tests. |

---

## 2. Expected-Refusal & Negative Control Vectors

To guarantee deterministic gate enforcement, the test corpus maintains dedicated refusal vectors:

| Refusal Fixture | Primary Input & SHA256 | Expected Refusal Output Behavior |
|---|---|---|
| **PC-001 Decoupling Absence** | `tests/test_passive_completeness.py`<br>`SHA256: 75599f47a313ec4f3a33e4eed557a1e15747f793826252c5caec2cfae3dcb761` | Pinout-only active IC (STM32N657) with zero decoupling capacitors. Must trigger HARD FAIL (`E_PASSIVE_COMPLETENESS_ERROR`) unless an explicit authenticated waiver is provided. |
| **Vacuous Pass Defense** | `tests/test_vacuous_pass_gates.py`<br>`SHA256: d279cabeb9cbeae1e5949e9fd216683a00f68cdccbd55fb0e466c31ea7be4245` | RF value-domain check on circuit with zero RF matching components. Gate must emit `indeterminate` / omitted field rather than synthetic `pass=True`. |
| **Open Circuit Form Gate Separation** | `tests/test_readability_gate.py`<br>`SHA256: bff9119f80b3c183e45e1c4cd5956a7f74dc7b29dbceb97238b7234b5f58a8f6` | Open-circuit fixture with 67 displaced nodes. Aesthetic readability gate passes form axis while explicitly emitting `does_not_authorize: ["electrical_correctness", "fidelity"]`. |
| **Output Path Overwrite Collision** | `bodesign_eda_bridge.hierarchical` (`experiments/btdongle_multisheet_e2e.py`)<br>`SHA256: a89b10e643f7ace6b360878e879a7d5a08acfb0fdf84a197eb0484d612336e3f` | Refuses to overwrite occupied output path without cleanup ownership (`E_OUTPUT_PATH_OCCUPIED`), preventing silent data loss. |

---

## 3. Mechanical 3D Assets & CAD Availability

### 3.1 Mechanical Asset Inventory

| Project / Benchmark | Model Format | Relative Path & SHA256 | Size | Description |
|---|---|---|---|---|
| **`04.btdongle`** | OpenSCAD | `C02-ME/Enclosure.scad`<br>`SHA256: 492ca67a5985111ac5b4cbdaf5569745a15057bd222ea661446da7c350563d3b` | 7.8 KB | Parametric enclosure model source |
| **`04.btdongle`** | STEP Solid | `C02-ME/Enclosure.step`<br>`SHA256: c5844a101bcfc8e3819aeeb2f298740df40f0bd4af2c15c2aac417018af2f88d` | 68.1 KB | Neutral AP214 CAD exchange solid |
| **`04.btdongle`** | STL Mesh | `C02-ME/enclosure_assembly.stl`<br>`SHA256: 13d218916e5b3ce3ae58c12184db175d9293f43cc9c5d73392fae37d1e24509f` | 22.5 KB | Full assembled 3D mesh |
| **`04.btdongle`** | STL Mesh | `C02-ME/enclosure_upper.stl` | 11.3 KB | Upper clamshell shell |
| **`04.btdongle`** | STL Mesh | `C02-ME/enclosure_lower.stl` | 11.3 KB | Lower clamshell shell |
| **`04.btdongle`** | STL Mesh | `C02-ME/battery_bay.stl`<br>`SHA256: 8b388ae4d47126ce331a8cc6a56fcd2bc665120ae18d176b4b38dbf56e818d3e` | 52.3 KB | Battery retention bay |
| **`03.aiguard`** | OpenSCAD / STL | `experiments/aiguard_c01/aiguard_pantilt_concept_v3.*` | ~120 KB | Pan-tilt robotic mount concept |
| **`03.aiguard`** | OpenSCAD / STL | `experiments/aiguard_c01/aiguard_enclosure_concept_v1/v2.*` | ~250 KB | Camera module enclosure concepts |
| **`c02_me_build`** | OpenSCAD / STEP / STL | `experiments/c02_me_build/` | ~300 KB | Multi-part test enclosure benchmark |
| **`route_work`** | glTF / GLB | `experiments/route_work/ccm_routed.glb` | 1.2 MB | 3D board rendering with Draco compression |

---

### 3.2 Supported CAD & Backend Availability

- **Host Capabilities (Measured vs Unverified)**:
  - `kicad-cli` and `pcbnew`: Installed on host (`9.0.9`); board layout execution is verified.
  - Native host **lacks** `openscad`, `build123d`, and `dxf2dwg` (measured absent via `which` / `import`).
- **Worker Allocation (Unverified pending live container receipt)**:
  - All heavy CSG/B-Rep operations (`bodesign_c02_export_stl`, `bodesign_c02_export_step`, `bodesign_c02_project_svg`) belong to the `ME` tool group.
  - In local dev mode without containers, these operations fail fast with explicit toolchain requirements.
  - In production / DockerLab mode (`registore.thesmart.cc/bodesign:v0.3.0-dockerlab`), these route over HTTP to the dedicated `bodesign-me` container. **Worker live execution remains unverified in this P0 receipt until an end-to-end receipt is produced in Phase 2.**
- **Data Access & Privacy Guarantees**:
  - GUEST repository `/home/pkcs12/products/thesmart_products/` is protected and accessed in **read-only mode**.
  - No customer proprietary schematics, STEP models, or netlists are transmitted to unauthenticated cloud services.
