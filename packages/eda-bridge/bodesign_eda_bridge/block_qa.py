"""Single pinout block QA loop (eda_draftsman-v2 task 1.4, IDEF0 A3).

Wires the two preserved gates (render_qa text-bbox + fidelity connected-component)
around block_drafter's emit, driven by kicad-cli. This is the DD-4 TDD red line:
a block is `validated=True` ONLY when BOTH gates are green on the RENDERED output.

Anti-treadmill contract (observability.md): on FAIL we record a defect signature
(error code + block_id + location). The caller-facing loop tries at most 2 rounds
of the SAME signature; a 2nd unresolved round HALTS and reports for RCA rather
than stacking a 3rd patch on the same layer.
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .render_qa import qa_svg_text
from .fidelity import verify_partition_fidelity, FidelityReport


@dataclass
class BlockQAVerdict:
    block_id: str
    render_qa_ok: bool
    fidelity_ok: bool
    overlap_count: int
    fidelity_diff: int
    roundtrip_exit: int
    signatures: list[str] = field(default_factory=list)   # defect signatures
    detail: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return (self.render_qa_ok and self.fidelity_ok
                and self.roundtrip_exit == 0)

    def summary(self) -> str:
        tag = "PASS" if self.ok else "FAIL"
        return (f"[{self.block_id}] render_qa={'ok' if self.render_qa_ok else f'FAIL({self.overlap_count})'} "
                f"fidelity={'ok' if self.fidelity_ok else f'FAIL({self.fidelity_diff})'} "
                f"roundtrip_exit={self.roundtrip_exit} -> {tag}")


def _render_svg(sch_path: Path, out_dir: Path) -> tuple[int, Path | None]:
    out_dir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["kicad-cli", "sch", "export", "svg", "-o", str(out_dir), str(sch_path)],
        capture_output=True, text=True,
    )
    svg = out_dir / (sch_path.stem + ".svg")
    return r.returncode, (svg if svg.exists() else None)


def qa_block(sch_path: str | Path, pin_map: dict[str, str], *,
             block_id: str | None = None,
             svg_dir: Path | str | None = None) -> BlockQAVerdict:
    """Run the two gates on ONE emitted block. pin_map is the expected
    partition (pin_number -> net); fidelity groups pins sharing a net.

    The block's own refdes is unknown at draft time, so fidelity is checked
    against a single-symbol expected partition keyed by net name; nodes are
    "U.<pin>" placeholders consistent between expected and exported netlist.
    """
    sch_path = Path(sch_path)
    block_id = block_id or sch_path.stem
    svg_dir = Path(svg_dir) if svg_dir else sch_path.parent / "svg"

    rc, svg = _render_svg(sch_path, svg_dir)
    sigs: list[str] = []
    if rc != 0 or svg is None:
        sigs.append(f"ROUNDTRIP_FAIL:{block_id}")
        return BlockQAVerdict(block_id=block_id, render_qa_ok=False,
                              fidelity_ok=False, overlap_count=-1,
                              fidelity_diff=-1, roundtrip_exit=rc, signatures=sigs)

    # render_qa text-bbox gate. DD-8 (task 1.5): scope the gate to the peripheral
    # artifacts THIS drafter drew (net labels off pin_map), so vendor symbol-body
    # internal pin-name<->pin-name overlaps (which DD-1 forbids the drafter from
    # moving) are excluded. A violation counts only if at least one overlapping
    # text is a drafter net label.
    rep = qa_svg_text(str(svg), peripheral_texts=set(pin_map.values()))
    overlap_n = len(rep.violations)
    if not rep.ok:
        for a, b, x, y, r in rep.violations[:8]:
            sigs.append(f"TEXT_BBOX_OVERLAP:{block_id}:{a}X{b}@({x},{y})")

    # fidelity gate: build expected partition {net: [U.pin,...]} from pin_map
    part: dict[str, list[str]] = {}
    for pin, net in pin_map.items():
        part.setdefault(net, []).append(f"U.{pin}")
    # only nets with >=2 pins form a real connectivity class worth checking
    expected = {n: nodes for n, nodes in part.items() if len(nodes) >= 2}
    fid_diff = 0
    fid_ok = True
    fid_detail = {}
    if expected:
        try:
            frep: FidelityReport = verify_partition_fidelity(expected, sch_path)
            fid_ok = frep.ok
            fid_diff = len(frep.moved) + len(frep.only_baseline) + len(frep.only_candidate)
            fid_detail = {"moved": frep.moved[:20], "only_baseline": frep.only_baseline[:20],
                          "only_candidate": frep.only_candidate[:20]}
            if not fid_ok:
                sigs.append(f"CONNECTIVITY_DIVERGE:{block_id}:diff={fid_diff}")
        except Exception as e:  # noqa: BLE001 — surface as gate failure, not crash
            fid_ok = False
            fid_diff = -1
            sigs.append(f"CONNECTIVITY_DIVERGE:{block_id}:{type(e).__name__}")

    return BlockQAVerdict(
        block_id=block_id,
        render_qa_ok=rep.ok, fidelity_ok=fid_ok,
        overlap_count=overlap_n, fidelity_diff=fid_diff,
        roundtrip_exit=rc, signatures=sigs,
        detail={"render_qa": rep.summary(), "fidelity": fid_detail},
    )


class TwoRoundHalt(RuntimeError):
    """Raised when the same defect signature survives 2 rounds — stop, do RCA."""


def qa_loop(draft_fn, *, max_rounds: int = 2):
    """Drive draft→QA up to `max_rounds` times. `draft_fn(round_idx)` must emit
    the block and return (sch_path, pin_map, block_id). If the SAME signature
    set persists across rounds, halt for RCA (anti-treadmill, observability.md).

    Returns the final BlockQAVerdict (ok or the last FAIL). Raises TwoRoundHalt
    only if a caller opts to treat unresolved persistence as fatal.
    """
    prev_sig: set[str] | None = None
    verdict: BlockQAVerdict | None = None
    for rnd in range(max_rounds):
        sch_path, pin_map, block_id = draft_fn(rnd)
        verdict = qa_block(sch_path, pin_map, block_id=block_id)
        if verdict.ok:
            return verdict
        cur_sig = set(verdict.signatures)
        if prev_sig is not None and cur_sig == prev_sig:
            # same defect two rounds running — do not attempt a 3rd same-layer patch
            break
        prev_sig = cur_sig
    return verdict
