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
    # DISAMBIGUATION (BR_20260906 §3.3). `measure_run` and `scored_subject` have
    # similar shapes and OPPOSITE meanings, and the BR measured that this one is
    # the more likely of the two to be misread as the other:
    #     measure_run    = the run the THRESHOLDS were calibrated from (historical,
    #                      identical in every report this module ever emits)
    #     scored_subject = what THIS call scored (per-call, the thing a reader
    #                      actually wants when they ask "which drawing is this?")
    # A reader who takes `measure_run.spec` for the subject gets a path that is
    # right about the calibration and wrong about the verdict.
    "what": "threshold calibration run (NOT the subject of this report — see "
            "scored_subject for that)",
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

# --- scored subject (BR_20260906 §7) --------------------------------------
# The defect that made this field necessary: the gate reported `ratio 0.2222
# FAIL` on btdongle and it read as a verdict on the DELIVERED schematic, while
# it had in fact scored a sheet the engine composed live during the run. The two
# populations differ by an order of magnitude (delivered sch/: wire 426 /
# junction 56 across 3 sheets; the scored live compose: wire 116 / junction 6,
# single sheet), and NOTHING in the report distinguished them.
#
# CLOSED enumeration. A free string would let a caller invent a fourth meaning
# that no reader could adjudicate.
SUBJECT_LIVE_COMPOSE = "live-compose"
SUBJECT_FROZEN_STATS = "frozen-stats"
SUBJECT_ON_DISK = "on-disk"
SCORED_SUBJECTS = (SUBJECT_LIVE_COMPOSE, SUBJECT_FROZEN_STATS, SUBJECT_ON_DISK)

# `on-disk` is RESERVED AND STRUCTURALLY UNREACHABLE TODAY, and that is the
# point of naming it rather than omitting it (BR_20260906 §8): this module's
# only input is `route_stats`, which is produced by a live compose. There is no
# reader for `.kicad_sch`, so no code path can emit this value. It is declared
# so that the report can state what it did NOT score, and
# `test_readability_gate.py` asserts the unreachability rather than leaving it
# as a comment nobody re-checks. A future disk entry point must add the emission
# point AND flip that test — the thresholds are calibrated on live-compose runs
# (see MEASURE_RUN) and do not transfer to a hand-drawn sheet without recal.
NOT_SCORED = [
    "on-disk deliverable — this gate has no `.kicad_sch` reader; it scores the "
    "stats of a live compose. The delivered schematic's readability is `not-run` "
    "here, never `failed` (BR_20260906)."
]

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


class ScoredSubjectError(ValueError):
    """The caller named a subject this module cannot vouch for.

    Raised rather than defaulted. A gate whose report says `live-compose` when
    nobody established that is worse than one that says nothing, because the
    field exists precisely to be quoted.
    """


def _subject_block(subject: str, evidence) -> dict:
    """Build the `scored_subject` block, or refuse.

    Question this answers: WHICH DRAWING did this report score?

    Fail-fast, both arms, because each failure mode has its own wrong-but-
    plausible default:
      * an unknown subject value would otherwise become a free string, and the
        enumeration would stop meaning anything;
      * absent evidence would otherwise become "" or {}, and "nobody supplied a
        source" would share an output with "the source is empty" — the exact
        conflation this whole field exists to remove.
    """
    if subject not in SCORED_SUBJECTS:
        raise ScoredSubjectError(
            f"scored_subject must be one of {list(SCORED_SUBJECTS)}; got "
            f"{subject!r}. The enumeration is closed on purpose: a free string "
            "would let a caller invent a meaning no reader can adjudicate.")
    if subject == SUBJECT_ON_DISK:
        # Structurally unreachable today (see NOT_SCORED). Refusing here rather
        # than accepting keeps the claim and the capability from diverging: this
        # module cannot read a `.kicad_sch`, so it must not be able to SAY it
        # scored one.
        raise ScoredSubjectError(
            "scored_subject='on-disk' is reserved and not implemented: this gate "
            "scores route_stats from a live compose and has no `.kicad_sch` "
            "reader. Emitting it would claim a measurement that did not happen "
            "(BR_20260906).")
    if not evidence:
        raise ScoredSubjectError(
            f"scored_subject={subject!r} requires source evidence; got "
            f"{evidence!r}. Without it 'no source was supplied' and 'the source "
            "is empty' would be the same output.")
    return {"subject": subject, "source": evidence}


def _base_report(status: str, subject_block: dict) -> dict:
    """Every report carries the axis, the disclaimer and the scored subject.

    `scored_subject` is a FIELD in EVERY status, pass and fail alike, for the
    same reason `does_not_authorize` is (task 6.5 / DD-07): an aggregator that
    reformats can drop a sentence, it cannot drop a key. A `failed` verdict whose
    subject is missing is exactly the artifact BR_20260906 is about.
    """
    return {
        "status": status,
        "gate_axis": GATE_AXIS,
        "does_not_authorize": list(DOES_NOT_AUTHORIZE),
        "scored_subject": dict(subject_block),
        "not_scored": list(NOT_SCORED),
    }


def readability_gate(route_stats, *, spec: dict | None = None,
                     n: int | None = None, emit=None,
                     scored_subject: str | None = None,
                     subject_source=None) -> dict:
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
    scored_subject / subject_source: WHICH DRAWING this call scored, and the
        evidence for that claim (BR_20260906 §7). Closed enumeration
        (`SCORED_SUBJECTS`). Left unset, BOTH are derived FROM THE BRANCH THE
        CALLER TOOK, which is the only fact available that cannot disagree with
        what was actually scored:
            spec= supplied  -> `live-compose`, sourced from the spec
            n= only         -> `frozen-stats`, sourced as a fixture replay
        That derivation is an EMISSION POINT, not a default: the two arms report
        DIFFERENT values, so a reader can tell them apart, and neither is the
        empty string. What is refused outright (`ScoredSubjectError`) is a claim
        this module cannot back: a value outside the enumeration, `on-disk` (no
        `.kicad_sch` reader exists), or evidence explicitly passed as empty.

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

    Every report carries `scored_subject` (what was scored) and `not_scored`
    (what was structurally NOT scored) in EVERY status.
    """
    if n is None and spec is None:
        raise ValueError(
            "readability_gate requires either `spec` (to derive N per DD-09) or "
            "`n` (to replay a frozen fixture). Supplying neither would make N=0 "
            "mean both 'no eligible nets' and 'caller forgot the denominator'.")

    # --- subject arm: established BEFORE any verdict is computed ------------
    # Order matters. Establishing the subject after scoring would let a report
    # exist, however briefly, with a verdict and no subject -- and every arm
    # below returns early, so "after" would in practice mean "on some paths".
    if spec is not None:
        # A spec was supplied, so these stats came from composing it.
        if scored_subject is None:
            scored_subject = SUBJECT_LIVE_COMPOSE
        if subject_source is None:
            # Derive from the spec the denominator already came from, so the
            # source cannot disagree with what was scored. Keys in preference
            # order; a spec naming none of them still yields a POSITIVE
            # statement ("unnamed in-memory spec" + its shape), never "".
            for key in ("source", "spec_path", "path", "name"):
                value = spec.get(key)
                if value:
                    subject_source = {"from_spec": key, "value": value}
                    break
            else:
                subject_source = {
                    "from_spec": None,
                    "value": "unnamed in-memory spec",
                    "shape": f"{len(spec.get('components', []) or [])} components / "
                             f"{len(spec.get('nets', []) or [])} nets",
                }
    else:
        # `n=` with no spec: a frozen replay. This is a DIFFERENT subject, not a
        # weaker version of the same one -- there is no spec behind these
        # numbers, so nothing was composed and no drawing was consulted. Saying
        # `live-compose` here would be the BR_20260906 defect in miniature.
        if scored_subject is None:
            scored_subject = SUBJECT_FROZEN_STATS
        if subject_source is None:
            subject_source = {
                "from_spec": None,
                "value": "frozen route_stats replayed with an explicit "
                         "denominator (n=); no spec was composed",
            }
    subject_block = _subject_block(scored_subject, subject_source)

    # --- precondition arm: absent input is not a verdict --------------------
    if route_stats is None:
        report = _base_report("not-run", subject_block)
        report["reason"] = "compose result carries no route_stats"
        report["code"] = "READABILITY_STATS_ABSENT"
        return report

    stats = route_stats if isinstance(route_stats, dict) else route_stats.to_dict()

    missing = [f for f in _REQUIRED_STAT_FIELDS if f not in stats]
    if missing:
        report = _base_report("not-run", subject_block)
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
            report = _base_report("indeterminate", subject_block)
            report["reason"] = ("emitter predates task 6.0; its stats cannot be "
                                "reconciled against what was drawn")
            report["missing_emitter_fields"] = emitter_missing
            report["code"] = "READABILITY_STATS_INCONSISTENT"
            return report

    # --- zero-net arm --------------------------------------------------------
    labelled = stats.get("labelled_nets", 0) or 0
    if wired == 0 and labelled == 0:
        report = _base_report("empty", subject_block)
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

    report = _base_report("ok", subject_block)
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
