"""Pin / GPIO allocation table (G5 / N13) — the C03↔C05 (FW) interface doc.

Given a net list (net → connected `REF.PIN` nodes — the same shape the composer
spec, the netlist, and the reference cross-check use), pivot to a per-pin
allocation table: which component pin carries which net. Optionally flag the
MCU's pins as the GPIO/FW interface view. Output renders to CSV (readable in
Excel) and markdown.

Deterministic and source-agnostic: feed it the composer spec nets or nets parsed
from a `kicad-cli` netlist. Reuses `kicad_emit._parse_netlist_nets` for the
netlist case.
"""

from dataclasses import dataclass, field
import csv
import io
import re


@dataclass(slots=True)
class PinAllocationRow:
    ref: str
    pin: str
    net: str
    is_mcu: bool = False


@dataclass(slots=True)
class PinAllocation:
    rows: list[PinAllocationRow] = field(default_factory=list)
    refs: list[str] = field(default_factory=list)
    net_count: int = 0
    mcu_refs: list[str] = field(default_factory=list)


def _pin_sort_key(pin: str):
    # natural-ish sort: split letters/digits so "PN2" < "PN10" and "A1" < "A10"
    return [int(t) if t.isdigit() else t for t in re.findall(r"\d+|\D+", pin)]


def _iter_nodes(net: dict):
    for node in net.get("nodes", []):
        if isinstance(node, (list, tuple)) and len(node) == 2:
            yield str(node[0]).strip(), str(node[1]).strip()
        else:
            ref, _, pin = str(node).partition(".")
            if pin:
                yield ref.strip(), pin.strip()


def build_pin_allocation(nets: list[dict], mcu_refs: tuple[str, ...] = ()) -> PinAllocation:
    mcu = {r.upper() for r in mcu_refs}
    rows: list[PinAllocationRow] = []
    for net in nets:
        name = str(net.get("name", "")).strip()
        for ref, pin in _iter_nodes(net):
            rows.append(PinAllocationRow(ref=ref, pin=pin, net=name, is_mcu=ref.upper() in mcu))
    rows.sort(key=lambda r: (r.ref, _pin_sort_key(r.pin)))
    return PinAllocation(
        rows=rows,
        refs=sorted({r.ref for r in rows}),
        net_count=len({r.net for r in rows}),
        mcu_refs=sorted(mcu),
    )


def render_pin_allocation_csv(alloc: PinAllocation, mcu_only: bool = False) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["RefDes", "Pin", "Net", "MCU_GPIO"])
    for row in alloc.rows:
        if mcu_only and not row.is_mcu:
            continue
        writer.writerow([row.ref, row.pin, row.net, "yes" if row.is_mcu else ""])
    return buf.getvalue()


def render_pin_allocation_md(alloc: PinAllocation) -> str:
    lines = ["# Pin / GPIO allocation (C03 → FW interface)", "",
             f"- Components: {len(alloc.refs)} · Nets: {alloc.net_count}"
             + (f" · MCU: {', '.join(alloc.mcu_refs)}" if alloc.mcu_refs else ""), ""]
    for ref in alloc.refs:
        ref_rows = [r for r in alloc.rows if r.ref == ref]
        tag = " (MCU/GPIO)" if ref_rows and ref_rows[0].is_mcu else ""
        lines.append(f"## {ref}{tag}")
        lines.append("| Pin | Net |")
        lines.append("|---|---|")
        for r in ref_rows:
            lines.append(f"| {r.pin} | {r.net} |")
        lines.append("")
    return "\n".join(lines)
