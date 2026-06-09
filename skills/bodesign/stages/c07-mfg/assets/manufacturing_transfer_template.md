# C07 — Manufacturing Transfer / Fab Package (<PRODUCT>)

> **Derived, git-safe, pre-fabrication.** This is the manufacturing-transfer **readiness**
> record for **<PRODUCT>** — <one-line provenance, e.g. "derived from the <REFERENCE>">.
> Its C04 layout is still a **board draft** (see `../C04-Layout/`): there are **no released
> Gerber/drill/IPC/stackup binaries yet**. Every fab deliverable below is tracked as **pending**
> against the gate that owns it. bodesign never fabricates a fab output or claims a build that did
> not happen.

## Provenance & status

| Aspect | State |
|---|---|
| Electrical baseline | <baseline + C06 cross-check, e.g. "100% net coverage, 269/269 matched"> |
| Product deltas | <product-specific deltas vs baseline> |
| Layout (C04) | **draft** — outline, placement, stackup remain layout-owned |
| Fab outputs | **not released** — pending C04 layout freeze |
| Build performed | **none yet** — this is pre-EVT |

## Fab output inventory (target — pending C04 freeze)

| Deliverable | Owner / Gate | Status |
|---|---|---|
| Gerber copper + mask + paste + silk | C04 layout | pending — no `.kicad_pcb` released |
| NC drill + route | C04 layout | pending |
| IPC-D-356 netlist (bare-board ET) | C04 layout | pending |
| Stackup definition | C04 layout / fab | pending — layer count TBC |
| Panelization (連板) drawing | C04 layout / assembly house | pending |
| Pick-and-place (CPL) + centroid | C04 layout | pending |
| Assembly BOM (placement) | C03 EE | **available** (design BOM); CPL pairing pending |
| Fabrication / aperture parameters | C04 layout / fab | pending |

> The **design** BOM and netlist already exist under `../C03-EE/`. They become a **manufacturing**
> BOM/CPL only after C04 places parts and exports fab outputs.

## Cost & quantity targets (from C00 PRD §2–§3)

- **PCBA BOM cost target ≤ USD <X>**; **finished good ≤ USD <Y>** (excl. tooling).
- Build ramp: **EVT <n> 套** → **試產 <m> 台** → DVT / pre-MP.
- Enclosure: <material>, **soft tooling** for EVT/DVT (injection moulding at MP).

## Certification targets (external-lab gate — never marked passed here)

- **FCC Part 15** Subpart B/C (US).
- **CE RED** 2014/53/EU (EU radio equipment).
- **EN 55032 / CISPR 32** EMC emissions.
- **IEC 62368-1** safety; **RoHS / REACH** material compliance.
- ESD **±4 kV air / ±8 kV contact** on external ports.

## Manufacturing transfer checklist (DFM / handoff gate)

- [ ] C04 layout frozen; board outline + stackup confirmed by ME + fab.
- [ ] Gerber / drill / IPC / panel released and DFM-reviewed by fab house.
- [ ] CPL (pick-and-place) generated and reconciled with C03 BOM.
- [ ] Manufacturing BOM costed against the PCBA target; sourcing confirmed.
- [ ] Stencil / paste design for the EVT build.
- [ ] Enclosure soft-tooling drawings (C02 STEP draft → ME production release).
- [ ] First-article inspection + C06 bring-up plan handed to EVT line.
- [ ] Certification samples reserved for FCC / CE external lab.

## Status

This is a **pre-fabrication manufacturing-readiness** record. <PRODUCT> reuses the **verified
<baseline> electrical baseline** (control group) and adds the product-specific deltas; it is
**not** a record of a fabricated board. The next gate is **C04 layout freeze**, which unblocks the
entire fab-output inventory above.
