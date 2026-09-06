"""WP6 — schematic readability gate, axis = `form`.

SEQUENCING RULE (task 6.8), stated here because this docstring is the only place
a caller reliably reads before wiring the verdict into a delivery:

    The form verdict is reported ALONGSIDE, never INSTEAD OF, the WP4 electrical
    verdict (`verify_netlist_fidelity`). A delivery that presents only the form
    verdict is INCOMPLETE. This gate scores how a schematic is DRAWN. It cannot
    and does not score whether the circuit is CORRECT.

Why that separation is load-bearing, and not boilerplate (DD-07): BR_20260905
§8.5.2 measured a change that improved every geometric criterion at once —
junctions 5→43, stub share 73.0%→32.7%, drawn subcircuits 3→11 — while raising
fidelity `moved` from 10 to 67, because it wired an OPEN CIRCUIT. Every threshold
in this module would have gone green on that change. The only thing that caught
it was the electrical axis. So a form gate that could be read as an electrical
verdict would have waved through the exact defect the package exists to prevent.

Consequently `does_not_authorize` is emitted as a DATA FIELD in every report,
pass and fail alike (tasks 6.5). Prose can be dropped by an aggregator that
reformats; a field survives. A PASS from this module authorizes nothing about
electrical correctness and nothing about fidelity.

Thresholds are SCALE-DEPENDENT (task 6.3). BR_20260905 §8.5.5 measured a 28/21
synthetic corpus reporting junction 21 / stub 41.5% (an apparent near-miss) where
the SAME code on the real 45/27 board reported 43 / 32.7% (a clear pass). A
synthetic corpus may supplement the acceptance corpus; it may never decide it.
"""

from __future__ import annotations

# --- thresholds ------------------------------------------------------------
# Every threshold cites the BR_20260905 line it is calibrated against, on the
# real 45-component / 27-net btdongle spec (§8.5.1: wire=111, junction=5, stub
# share 73.0%, anti-fusion downgraded nets 3).

# §7 criterion 1 — "junction > 20 (目前 5; label farm 的定量反面)".
MIN_JUNCTIONS = 20
# §7 criterion 2 — "短樁 ... 佔 wire 比例 < 40% (目前 74%)".
MAX_STUB_SHARE = 0.40
# §7 criterion 4 — "至少能數出 N 組可辨識子電路 ... 被畫成連通實線".
# DD-09: N is SPEC-DERIVED, never a constant; the RATIO is what is thresholded.
# PINNED by task 6.2c step (2) from the step (1) measurement — see MEASURE_RUN.
MIN_SUBCIRCUIT_RATIO = 0.50

# task 6.2c step (1) MEASURE — the run this threshold was pinned from. Recorded
# so the number can be attributed to a measurement rather than to taste.
MEASURE_RUN = {
    "spec": "/home/pkcs12/products/thesmart_products/04.btdongle/"
            "C03-EE/02_build/sch_gen/design.py",
    "spec_shape": "45 components / 27 nets",
    "flags": {"style": "draftsman", "validate": False, "fidelity": False},
    "observed": {"drawn_subcircuits": 4, "N": 18, "ratio": 0.2222,
                 "stub_share": 0.715517, "junctions": 6, "fanout_proxy": 7,
                 "antifusion_downgrades": 3},
    "note": "HEAD 2026-09-06, i.e. AFTER c3019f68 signal fragmentation. These "
            "differ from BR_20260905 §8.5.1 (wire 111→116, stub 73.0%→71.55%, "
            "subcircuits 3→4, junction 5→6) in the direction §8.5.3 predicts, so "
            "the threshold is pinned on THIS run, not on the §8.5.1 figures.",
}

GATE_AXIS = "form"
# Emitted in EVERY report. `fidelity` is listed alongside `electrical_correctness`
# because BR_20260905 §8.5.2's counterexample was caught by the fidelity axis
# specifically — naming only the general term would let a reader assume the
# specific one had been covered.
DOES_NOT_AUTHORIZE = ["electrical_correctness", "fidelity"]

_PASSIVE_PREFIXES = ("R", "C", "L")
# DD-09 node-count window: a net small enough to read as ONE local subcircuit.
_N_NODE_MIN = 2
_N_NODE_MAX = 6

# The two fields task 6.0 added. Their ABSENCE is the gate's `not-run`
# precondition; a missing key must never be defaulted to 0 and scored.
_REQUIRED_STAT_FIELDS = ("stub_share", "drawn_subcircuits")


def compute_n(spec: dict) -> int:
    """DD-09: N := signal nets holding >=1 passive (ref prefix R/C/L) with node
    count in [2, 6].

    Power and bus nets are excluded by the SAME classifier the emitter and
    `_build_route_stats` use (`kicad_emit._power_net_kind` plus the spec's own
    declared `kind`), so composer, emitter and gate cannot disagree about what a
    power net is. Re-deriving that rule locally is exactly the drift BR_20260905
    was caused by.

    N counts the nets that COULD be drawn as a local subcircuit. It is the
    denominator of the ratio, and it is reported beside the ratio so a low ratio
    is distinguishable from a small denominator.
    """
    from .kicad_emit import _power_net_kind

    n = 0
    for net in spec.get("nets", []) or []:
        name = net.get("name", "")
        if (net.get("kind") or "") in ("power", "bus"):
            continue
        if _power_net_kind(name) is not None:
            continue
        nodes = net.get("nodes", []) or []
        if not (_N_NODE_MIN <= len(nodes) <= _N_NODE_MAX):
            continue
        has_passive = False
        for node in nodes:
            ref = node.split(".", 1)[0] if isinstance(node, str) else str(node[0])
            if ref[:1] in _PASSIVE_PREFIXES and ref[1:2].isdigit():
                has_passive = True
                break
        if has_passive:
            n += 1
    return n


def _base_report(status: str) -> dict:
    """Every report carries the axis and the disclaimer, in EVERY status."""
    return {
        "status": status,
        "gate_axis": GATE_AXIS,
        "does_not_authorize": list(DOES_NOT_AUTHORIZE),
    }


def readability_gate(route_stats, *, spec: dict | None = None,
                     n: int | None = None, emit=None) -> dict:
    """Score a compose result on the `form` axis. Authorizes nothing electrical.

    route_stats: the `RouteStats` (or its `to_dict()`) from a compose result, or
        None when the compose path produced none (`connection_style="netlist"`,
        where `composer.py` types it `RouteStats | None`).
    spec / n: the denominator source. Pass `spec` to derive N per DD-09; pass `n`
        directly to replay a frozen fixture. Passing neither is a caller error and
        raises — it is never silently treated as N=0, because "no eligible nets"
        and "nobody supplied the denominator" are different facts.
    emit: optional `SchematicEmitResult`. Used ONLY to detect an emitter that
        predates task 6.0 (DD-11 `indeterminate` arm).

    Returns a report dict. Statuses, per errors.md §WP6 as amended by DD-11:
      ok            every threshold met
      failed        >=1 threshold unmet; `unmet` names which
      not-run       no route_stats, or route_stats missing the task-6.0 fields;
                    `missing_fields` names them. Absence is NEVER a pass.
      empty         ran, nothing to score: no nets routed/labelled at all, or
                    N == 0 (no eligible denominator, so the ratio is not evaluated)
      indeterminate the emitter predates task 6.0 (no `wire_runs` /
                    `junctions_emitted`) while nets were wired, so the stats
                    cannot be vouched for against what was drawn
    """
    if n is None and spec is None:
        raise ValueError(
            "readability_gate requires either `spec` (to derive N per DD-09) or "
            "`n` (to replay a frozen fixture). Supplying neither would make N=0 "
            "mean both 'no eligible nets' and 'caller forgot the denominator'.")

    # --- precondition arm: absent input is not a verdict --------------------
    if route_stats is None:
        report = _base_report("not-run")
        report["reason"] = "compose result carries no route_stats"
        report["code"] = "READABILITY_STATS_ABSENT"
        return report

    stats = route_stats if isinstance(route_stats, dict) else route_stats.to_dict()

    missing = [f for f in _REQUIRED_STAT_FIELDS if f not in stats]
    if missing:
        report = _base_report("not-run")
        report["reason"] = ("route_stats lacks the task-6.0 emission(s); a missing "
                            "key is absent input, not a measured zero")
        report["missing_fields"] = missing
        report["code"] = "READABILITY_STATS_ABSENT"
        return report

    # --- DD-11 indeterminate arm --------------------------------------------
    # Pre-DD-11 this arm compared route_stats.junctions against the landed
    # `(junction` count. That comparison was structurally always-true, because
    # `junctions` was max(0, nodes-2) summed over wired nets — a FAN-OUT PROXY,
    # never a junction count (measured 7 vs 6 on the real board). A check that
    # cannot come back clean is not a check; it is a defence that always fires,
    # which reads to a later maintainer as a defence that works. Replaced with
    # the question that actually has two answers: did the emitter that produced
    # these stats carry the task-6.0 emissions at all?
    wired = stats.get("wired_nets", 0) or 0
    if emit is not None and wired > 0:
        emitter_missing = [f for f in ("wire_runs", "junctions_emitted")
                           if not hasattr(emit, f)]
        if emitter_missing:
            report = _base_report("indeterminate")
            report["reason"] = ("emitter predates task 6.0; its stats cannot be "
                                "reconciled against what was drawn")
            report["missing_emitter_fields"] = emitter_missing
            report["code"] = "READABILITY_STATS_INCONSISTENT"
            return report

    # --- zero-net arm --------------------------------------------------------
    labelled = stats.get("labelled_nets", 0) or 0
    if wired == 0 and labelled == 0:
        report = _base_report("empty")
        report["reason"] = "route_stats records zero nets; nothing to score"
        return report

    n_value = compute_n(spec) if n is None else n
    stub_share = stats.get("stub_share")
    subcircuits = stats.get("drawn_subcircuits")
    junctions = stats.get("junctions", 0) or 0

    # anti-fusion downgrades (§7 criterion 3): zero downgrades, OR every
    # downgraded net kept a drawn fragment. `drawn_fragments` is absent on the
    # 2-pin fallback shape, so `.get(...) or 0` treats absent as zero fragments —
    # the conservative reading, and the one the BR's "整個 net 丟光" case needs.
    downgrades = [d for d in (stats.get("label_fallback_reasons") or [])
                  if d.get("reason") in ("anti-fusion", "ledger-collision")]
    downgrades_without_fragment = [d["net"] for d in downgrades
                                   if not (d.get("drawn_fragments") or 0)]

    report = _base_report("ok")
    report["N"] = n_value
    report["drawn_subcircuits"] = subcircuits
    report["stub_share"] = stub_share
    report["junctions"] = junctions
    report["antifusion_downgrades"] = len(downgrades)
    report["thresholds"] = {
        "min_junctions": MIN_JUNCTIONS,
        "max_stub_share": MAX_STUB_SHARE,
        "min_subcircuit_ratio": MIN_SUBCIRCUIT_RATIO,
    }
    report["measure_run"] = MEASURE_RUN

    unmet: list[dict] = []

    if junctions <= MIN_JUNCTIONS:
        unmet.append({"criterion": "junctions", "observed": junctions,
                      "threshold": f"> {MIN_JUNCTIONS}",
                      "source": "BR_20260905 §7 criterion 1"})

    # stub_share is None when no run was measurable — report it as such rather
    # than scoring it. None and 0.0 are different facts (task 6.0 codomain).
    if stub_share is None:
        report["stub_share_note"] = ("no measurable run; not scored (this is "
                                     "not-run for this criterion, not 0.0)")
    elif stub_share >= MAX_STUB_SHARE:
        unmet.append({"criterion": "stub_share", "observed": stub_share,
                      "threshold": f"< {MAX_STUB_SHARE}",
                      "source": "BR_20260905 §7 criterion 2"})

    if downgrades_without_fragment:
        unmet.append({"criterion": "antifusion_downgrades",
                      "observed": downgrades_without_fragment,
                      "threshold": "0 downgrades, or each retains drawn_fragments > 0",
                      "source": "BR_20260905 §7 criterion 3"})

    # zero-denominator arm: the ratio has no denominator, so it is NOT evaluated
    # and NOT reported as a met or unmet threshold.
    if n_value == 0:
        report["status"] = "empty"
        report["reason"] = ("no spec net is eligible to be a subcircuit (N=0); "
                            "the ratio has no denominator and was not evaluated")
        report["subcircuit_ratio"] = None
        report["unmet"] = unmet
        return report

    ratio = round((subcircuits or 0) / n_value, 6)
    report["subcircuit_ratio"] = ratio
    if ratio < MIN_SUBCIRCUIT_RATIO:
        unmet.append({"criterion": "subcircuit_ratio",
                      "observed": f"{subcircuits}/{n_value} = {ratio}",
                      "threshold": f">= {MIN_SUBCIRCUIT_RATIO}",
                      "source": "BR_20260905 §7 criterion 4 / DD-09"})

    if unmet:
        report["status"] = "failed"
        report["code"] = "READABILITY_THRESHOLD_UNMET"
    report["unmet"] = unmet
    return report
