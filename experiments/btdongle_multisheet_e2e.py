#!/usr/bin/env python3
"""Phase 4 end-to-end: emit the real btdongle board as root + N leaf schematics.

READ-ONLY GUEST BOUNDARY
------------------------
The component list, net list and no-connect list are imported verbatim from the
GUEST repo's design SSOT:

    /home/pkcs12/products/thesmart_products/04.btdongle/C03-EE/02_build/sch_gen/design.py

Nothing is written there. The `sheet` declarations are authored HERE, because
design.py's own field-5 carries a THREE-way split (power/mcu/io) and the five
subsystems this run targets are a different decomposition. No component,
symbol, pin or net is invented: every ref, lib_id, footprint and node below
comes from the guest module.

WHY THE FIVE SUBSYSTEMS ARE NOT FIVE SHEETS -- AND WHAT DD-13 CHANGES
---------------------------------------------------------------------
The requested subsystems are defined by NETS (SYS/BATT, VBUS_CON/CC1/CC2,
BAT_EXT/NTC, ENPPB/CHG_LED_A, SWCLK/SWDIO) and those net sets SHARE components:
U1 sits on SYS, BATT, NTC and ENPPB; U2 sits on SYS and SWCLK/SWDIO; Q1 sits on
BATT and BAT_EXT; SW1 sits on BATT and ENPPB. HOME assignment still puts each
component on exactly one sheet -- invariant I-1 is unchanged.

DD-13 adds the second channel the earlier rounds lacked: a component may be DRAWN
AGAIN on another sheet as a netlist- and BOM-neutral replica, so a subsystem whose
members live on several sheets can still be read end-to-end on ONE page. The old
table was called SUBSYSTEM_ARBITRATION because a shared component was forced onto
one sheet and lost elsewhere; nothing is arbitrated away any more, so it is now
SUBSYSTEM_PLACEMENT: {ref: {home, replicas, reason}}.

ONE VIEW SHEET PER REQUESTED SUBSYSTEM (round 46 fix)
-----------------------------------------------------
Round 45 homed the ETA6003 core and the enable/LED parts on ONE `charger` sheet.
Because the view sheet is the one already holding the most members, `power-rail`
and `charge-enable` both resolved to `charger`, so five requested subsystems
produced FOUR pages and a reviewer could not read either one on its own. `charger`
is therefore split into `power_rail` (U1 C2 C3 L1 C4 C5 R3 R4 R6) and
`charge_enable` (SW1 R7 D2), which makes the five view sheets distinct:

    power-rail SYS/BATT        -> power_rail
    USB-C + CC                 -> usbc
    battery + NTC              -> battery
    charge-enable ENPPB/LED    -> charge_enable
    SWD SWCLK/SWDIO            -> mcu_swd

The replica rule applied below is stated rather than improvised: for a subsystem
spanning several sheets, the VIEW SHEET is the one already holding the most of its
members, and every member living elsewhere is replicated onto it with the net
subset `subsystem nets` INTERSECT `that ref's canonical nets`. The intersection is
what keeps the view local -- U1 carries SYS, BATT, NTC and ENPPB, and a view of the
battery subsystem must show only its BAT_EXT/NTC half.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

GUEST_SCH_GEN = Path(
    "/home/pkcs12/products/thesmart_products/04.btdongle/C03-EE/02_build/sch_gen")
GUEST_DESIGN = GUEST_SCH_GEN / "design.py"

PROJECT_NAME = "btdongle_ms"

# Authored HERE. Every ref below appears in the guest COMPONENTS list; the
# assertion at the bottom of build_spec() proves the two sets are equal, so a
# ref added upstream cannot be silently dropped from this partition.
SHEET_OF_REF = {
    # usbc -- USB-C receptacle, CC pulldowns, ESD array, fuse, input bulk
    "J1": "usbc", "R1": "usbc", "R2": "usbc", "F1": "usbc", "D1": "usbc",
    "C1": "usbc",
    # power_rail -- ETA6003 core, SYS/BATT rail passives, ISET and USB_DET network
    "U1": "power_rail", "C2": "power_rail", "C3": "power_rail",
    "L1": "power_rail", "C4": "power_rail", "C5": "power_rail",
    "R3": "power_rail", "R4": "power_rail", "R6": "power_rail",
    # charge_enable -- ENPPB button and the CHG_LED_A status indicator
    "R7": "charge_enable", "D2": "charge_enable", "SW1": "charge_enable",
    # battery -- cell connector, reverse-protection FET, NTC bias, BATT testpoint
    "Q1": "battery", "J2": "battery", "C6": "battery", "R5": "battery",
    "TP2": "battery",
    # mcu_swd -- Pico 2 W module, SWD header, RUN network, module rail bypass
    "U2": "mcu_swd", "J3": "mcu_swd", "SW2": "mcu_swd", "R8": "mcu_swd",
    "C7": "mcu_swd", "C8": "mcu_swd", "C9": "mcu_swd", "C10": "mcu_swd",
    "C11": "mcu_swd", "TP1": "mcu_swd",
    # io -- status LEDs, user button, battery sense divider
    "D3": "io", "R9": "io", "D4": "io", "R10": "io", "D5": "io", "R11": "io",
    "SW3": "io", "R12": "io", "C12": "io", "R13": "io", "R14": "io", "C13": "io",
}

#: The five requested subsystems, by the nets that DEFINE them. Which sheets each
#: one spans is MEASURED from the guest net list at run time, never hardcoded --
#: a hardcoded span would keep reporting yesterday's answer after an upstream edit.
REQUESTED_SUBSYSTEMS = {
    "power-rail SYS/BATT": ["SYS", "BATT"],
    "USB-C + CC VBUS_CON/CC1/CC2": ["VBUS_CON", "CC1", "CC2"],
    "battery + NTC BAT_EXT/NTC": ["BAT_EXT", "NTC"],
    "charge-enable ENPPB/CHG_LED_A": ["ENPPB", "CHG_LED_A"],
    "SWD SWCLK/SWDIO": ["SWCLK", "SWDIO"],
}

#: ALL FIVE requested subsystems get a real local view (dispatcher ruling, round
#: 46). Round 45 shipped only `battery + NTC` and excluded the rest -- `power-rail`
#: on the grounds that SYS/BATT reach 13 of the 45 components. That exclusion is
#: withdrawn: the deliverable is the five REQUESTED views, and a subsystem that is
#: already wholly on one sheet simply needs no replica for its view to be complete.
#: Whether a dense page is READABLE is a fresh-eye question, not a reason to omit it.
REPLICATED_SUBSYSTEMS = list(REQUESTED_SUBSYSTEMS)


def measure_subsystem_placement(design, sheet_of_ref, view_local_max_nodes):
    """SUBSYSTEM_PLACEMENT, derived from the guest net list.

    Returns (placement, replicas_by_ref, subsystem_report).

    placement: {ref: {"home": <sheet>, "replicas": [<sheet>...], "reason": <str>}}
               -- the DD-13 clause 7 replacement for SUBSYSTEM_ARBITRATION. Nothing
               is arbitrated away: a component serving several subsystems keeps one
               home and gains a replica view on each sheet that needs to show it.
    """
    nets_of_ref: dict[str, set] = {}
    for name, nodes in design.NETS.items():
        for ref, _pin in nodes:
            nets_of_ref.setdefault(ref, set()).add(name)

    placement = {ref: {"home": sheet, "replicas": [], "reason": "single subsystem"}
                 for ref, sheet in sheet_of_ref.items()}
    replicas_by_ref: dict[str, list] = {}
    report = {}

    for label, subsystem_nets in REQUESTED_SUBSYSTEMS.items():
        members = sorted({ref for net in subsystem_nets
                          for ref, _pin in design.NETS.get(net, [])})
        by_sheet: dict[str, list] = {}
        for ref in members:
            by_sheet.setdefault(sheet_of_ref[ref], []).append(ref)
        # The view sheet is the one ALREADY holding the most members: it minimises
        # how many replicas the page needs, and it is a deterministic tie-break
        # (count, then name) rather than a judgement call.
        view_sheet = min(by_sheet, key=lambda s: (-len(by_sheet[s]), s))

        # A replica earns its place only if the net it is there to show will
        # ACTUALLY be drawn as a local wire. The emitter draws a subsystem net
        # locally only while its whole slice on that page stays within
        # `view_local_max_nodes` (measured: above it the trunk+stub route fuses
        # rails -- at bound 12 the btdongle netlist collapsed 58 node classes to
        # 56). A replica added for a net that will stay on a label contributes no
        # wire, so it lands as a symbol wearing a name tag: exactly the
        # "label-only U2" a reviewer rejected. Those replicas are NOT emitted, and
        # the nets they would have served are reported as label-only with the
        # measured slice size rather than disappearing.
        projected = {}
        for net in subsystem_nets:
            nodes = design.NETS.get(net, [])
            on_view = [n for n in nodes if sheet_of_ref[n[0]] == view_sheet]
            off_view = [n for n in nodes if sheet_of_ref[n[0]] != view_sheet]
            projected[net] = {
                "on_view_sheet": len(on_view),
                "from_replicas": len(off_view),
                "total": len(on_view) + len(off_view),
            }
        drawable = {net for net, size in projected.items()
                    if size["total"] <= view_local_max_nodes}
        label_only = {net: projected[net] for net in subsystem_nets
                      if net not in drawable}

        replicated = []
        skipped = []
        if label in REPLICATED_SUBSYSTEMS:
            for sheet, refs in by_sheet.items():
                if sheet == view_sheet:
                    continue
                for ref in refs:
                    incident = set(subsystem_nets) & nets_of_ref.get(ref, set())
                    if not incident:
                        # Cannot happen for a member (membership IS net incidence),
                        # but an empty subset would emit a decoration, so it raises
                        # rather than being written out.
                        raise SystemExit(
                            f"REPLICA_SUBSET_EMPTY: {ref} is a member of {label} "
                            f"yet shares no net with it")
                    subset = sorted(incident & drawable)
                    if not subset:
                        skipped.append({
                            "ref": ref, "from_sheet": sheet,
                            "onto_sheet": view_sheet,
                            "nets_not_drawable": sorted(incident),
                            "reason": "every net this replica would show stays on "
                                      "label continuation, so the replica would "
                                      "carry no wire"})
                        continue
                    replicas_by_ref.setdefault(ref, []).append(
                        {"sheet": view_sheet, "nets": subset})
                    placement[ref]["replicas"].append(view_sheet)
                    placement[ref]["reason"] = (
                        f"home {placement[ref]['home']}; drawn again on "
                        f"{view_sheet} to complete the {label} view")
                    replicated.append({"ref": ref, "from_sheet": sheet,
                                       "onto_sheet": view_sheet, "nets": subset})
        report[label] = {
            "nets": subsystem_nets,
            "members": members,
            "members_by_sheet": {s: sorted(r) for s, r in sorted(by_sheet.items())},
            "spans_sheets": sorted(by_sheet),
            "wholly_local": len(by_sheet) == 1,
            "view_sheet": view_sheet,
            "replicated": replicated,
            "replicas_skipped_not_drawable": skipped,
            # PROJECTIONS, computed BEFORE pruning to decide which replicas earn
            # their place. They are deliberately pessimistic: pruning a replica
            # shrinks that net's slice, so a net projected label-only here can end
            # up drawn. What the emitter ACTUALLY left on labels is reported
            # separately as `view_nets_label_only`, measured from the landed leaf.
            # Naming them `projected_` keeps the two apart -- as plain
            # `nets_label_only` this table said BATT was label-only while the
            # emitter had drawn it, and nothing in either number said which was
            # the measurement.
            "projected_drawable_before_pruning": sorted(drawable),
            "projected_label_only_before_pruning": label_only,
            "replication_applied": label in REPLICATED_SUBSYSTEMS,
        }
    return placement, replicas_by_ref, report


def load_guest_design():
    """Import the guest SSOT read-only. Fails loudly if it is absent."""
    if not GUEST_DESIGN.is_file():
        raise SystemExit(f"GUEST_ABSENT: {GUEST_DESIGN}")
    spec = importlib.util.spec_from_file_location("btdongle_design", GUEST_DESIGN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_spec(design, replicas_by_ref=None):
    """Real components + real nets + locally authored sheet/replica declarations."""
    guest_refs = {row[0] for row in design.COMPONENTS}
    declared = set(SHEET_OF_REF)
    if guest_refs != declared:
        raise SystemExit(
            f"PARTITION_COVERAGE_MISMATCH: guest_only={sorted(guest_refs - declared)} "
            f"declared_only={sorted(declared - guest_refs)}")

    replicas_by_ref = replicas_by_ref or {}
    components = []
    for ref, symbol, value, footprint, guest_sheet, _desc in design.COMPONENTS:
        entry = {
            "ref": ref,
            "symbol": symbol,
            "value": value,
            "footprint": footprint,
            "sheet": SHEET_OF_REF[ref],
            "group": guest_sheet,
        }
        if ref in replicas_by_ref:
            entry["replicas"] = replicas_by_ref[ref]
        components.append(entry)

    nets = [{"name": name, "nodes": [f"{ref}.{pin}" for ref, pin in nodes]}
            for name, nodes in design.NETS.items()]
    nc = [f"{ref}.{pin}" for ref, pin in design.NO_CONNECT]
    return {"components": components, "nets": nets, "nc": nc}


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if out_dir is None:
        base = os.environ.get("XDG_RUNTIME_DIR")
        if not base:
            raise SystemExit("XDG_RUNTIME_DIR unset and no out_dir argument given")
        out_dir = Path(base) / "bodesign-btdongle-multisheet" / "out"
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    from bodesign_eda_bridge.hierarchical import (
        VIEW_LOCAL_MAX_NODES, emit_multisheet)

    design = load_guest_design()
    placement, replicas_by_ref, subsystem_report = measure_subsystem_placement(
        design, SHEET_OF_REF, VIEW_LOCAL_MAX_NODES)
    spec = build_spec(design, replicas_by_ref)

    # power_ports=False is a MEASURED necessity, not a preference. With the
    # default power_ports=True the emitter raises POWER_PORT_INSIDE_SYMBOL_BODY:
    # at the 45 mm naive grid the GND/+3V3 port stubs land inside a neighbouring
    # symbol body. The FLAT emitter raises the same error on the same components
    # (control run, see the plan's Phase 4 record), so this is a property of
    # naive-grid placement, NOT of multi-sheet emission. Connectivity is
    # unaffected: with power ports off, GND and +3V3 are carried by global
    # labels, which is what the netlist arbitration below checks.
    # connection_style="wire" (round 45, after fresh-eye visual QA).
    # THREE independent reviewers reported the same blocker on the default
    # "label" style: the pages are "parts each wearing a name tag, not wired to
    # each other" -- connectivity existed only as matching label text, which is
    # precisely what a LOCAL-connection-principles page is supposed to remove.
    # MEASURED before switching, because a drawing change that alters
    # connectivity would be a regression dressed as a readability fix: comparing
    # the two exports by NODE-SET PARTITION (net names discarded, since wire mode
    # renames nets to sheet-local paths like /charger/ISET1) gives 58 classes on
    # each side, 0 classes unique to either, and the comparator reports a
    # difference when one class is removed. 39 real wire runs are drawn.
    # DD-14: the sheets that host a requested subsystem view draw their cross-sheet
    # nets as LOCAL WIRES and carry an appended global_label for continuation. Round
    # 45's battery page had four nets, all cross-sheet, so DD-2's label-only rule
    # left it with zero wires -- a column of name tags that three reviewers rejected.
    # The mapping is sheet -> that sheet's SUBSYSTEM nets, never a bare sheet list.
    # Un-scoped local drawing was MEASURED to fuse the shared rails: with every
    # cross-sheet net drawn as a wire, 7 node classes collapsed into 2 (53 classes
    # against the control's 58). Only the subsystem's own nets are drawn locally.
    view_nets_by_sheet: dict[str, set] = {}
    for entry in subsystem_report.values():
        view_nets_by_sheet.setdefault(entry["view_sheet"], set()).update(entry["nets"])
    view_sheets = sorted(view_nets_by_sheet)
    result = emit_multisheet(
        out_dir, PROJECT_NAME, spec,
        symbol_dir=[str(GUEST_SCH_GEN), "/usr/share/kicad/symbols"],
        power_ports=False,
        connection_style="wire",
        subsystem_views={s: sorted(n) for s, n in view_nets_by_sheet.items()},
    )

    # Coverage is measured from what the EMITTER reported per leaf, not from the
    # spec we handed it: reading our own input back would confirm the dict we
    # wrote, not what landed on the sheets.
    #
    # DD-13 clause 6: `component_count` per leaf counts DRAWN SYMBOLS, and a replica
    # is a drawn symbol that is NOT a component. Subtracting the replica views is
    # what keeps "how many components landed" apart from "how many symbols were
    # drawn" -- without it the coverage line read `placed=46 declared=45
    # unplaced=-1`, a negative count that looked like a partition defect and was in
    # fact the two quantities being added together.
    drawn_total = sum(leaf.component_count for leaf in result.leaf_results.values())
    replica_total = result.replica_views_requested
    placed_total = drawn_total - replica_total
    declared_total = len(spec["components"])

    report = {
        "population_components_declared": declared_total,
        "population_components_placed_on_a_sheet": placed_total,
        "population_components_unplaced": declared_total - placed_total,
        "population_drawn_symbols_on_leaves": drawn_total,
        "population_nets": len(spec["nets"]),
        "population_nc": len(spec["nc"]),
        "emit_mode": result.emit_mode,
        "root": result.schematic_path,
        "leaf_paths": result.leaf_paths,
        "sheet_component_counts": {
            name: leaf.component_count for name, leaf in result.leaf_results.items()},
        "cross_sheet_nets": result.cross_sheet_nets,
        "unresolved_pins": {
            name: leaf.unresolved_pins for name, leaf in result.leaf_results.items()
            if leaf.unresolved_pins},
        "warnings": result.warnings,
        "files": result.files,
        "subsystem_placement": subsystem_report,
        "component_placement": {
            ref: entry for ref, entry in sorted(placement.items())
            if entry["replicas"]},
        "population_replica_views_requested": replica_total,
        "population_replica_symbols_marked": sum(result.replica_marked.values()),
        "replica_marked_per_sheet": result.replica_marked,
        "population_drawn_instances": declared_total + replica_total,
        "connection_style": "wire",
        "population_wire_runs": sum(
            len(leaf.wire_runs) for leaf in result.leaf_results.values()),
        "population_junctions": sum(
            leaf.junctions_emitted for leaf in result.leaf_results.values()),
        "power_ports": False,
        "power_ports_reason": (
            "POWER_PORT_INSIDE_SYMBOL_BODY at the naive 45mm grid; the flat "
            "emitter raises it identically on the same components"),
        "subsystem_view_sheets": view_sheets,
        "subsystem_view_nets": {s: sorted(n) for s, n in view_nets_by_sheet.items()},
        "page_fit": result.page_fit,
        "continuation_labels": result.continuation_labels,
        # Named rather than left as an absence: a subsystem net whose local slice
        # exceeds the guarded route stays on label continuation, and the reader is
        # told which nets and how big their slice was.
        "view_nets_label_only": result.view_nets_label_only,
        "view_local_max_nodes": VIEW_LOCAL_MAX_NODES,
        # How many lib_ids the size-aware layout measured per sheet versus how
        # many fell back to the minimum cell. A defaulted cell is a guessed size.
        "symbol_boxes": result.symbol_boxes,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))

    netlist = out_dir / f"{PROJECT_NAME}.net"
    proc = subprocess.run(
        ["kicad-cli", "sch", "export", "netlist",
         "--output", str(netlist), result.schematic_path],
        capture_output=True, text=True)
    print(f"KICAD_CLI_RC={proc.returncode}")
    print(f"KICAD_CLI_STDOUT={proc.stdout.strip()}")
    print(f"KICAD_CLI_STDERR={proc.stderr.strip()}")
    print(f"NETLIST_PATH={netlist}")
    print(f"NETLIST_EXISTS={netlist.is_file()}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
