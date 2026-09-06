"""Design-suggestion engine (plan knowledge_c03-ee-design-kb, track C / scheme C).

The FIRST slice of the "evidence-backed suggestion" capability layer: given a
high-level design *intent* (e.g. "SHARED_I2C is a 4-device open-drain bus"),
emit a DRAFT suggestion of the concrete passive topology + component values,
every value computed from a graded KB rule and stamped with its evidence.

Honesty contract (the red line this module must never cross):
  - It SUGGESTS, it does not DECIDE. Output status is always "suggested",
    never "committed"; every payload carries review_required=True.
  - It is deterministic, side-effect free: it does not mutate its input and
    writes no files. The caller (a human, via consumer) reviews and, only
    then, commits the suggestion into the spec.
  - Every suggested value carries an `evidence` block anchoring to the KB
    object it was derived from (control.sch.pullup-termination-sizing) plus
    the formula and provenance. No fabricated values.

This module is INDEPENDENT of composer: it does not touch compose_schematic's
spec-building behaviour (BR_B: faithfully building the given spec is correct).
"""
from __future__ import annotations

import copy

# ── KB evidence anchor (control.sch.pullup-termination-sizing) ───────────────
# These constants transcribe the KB rule body; the rule is the SSOT and the
# `evidence` block on every suggestion points back to it. Not hard-coded design
# opinion — a transcription of the bus-spec-grade formulas (NXP UM10204).
_KB_OBJECT = "control.sch.pullup-termination-sizing"
_KB_FORMULA = "Rp_min=(VCC-VOL)/IOL, Rp_max=tr/(0.8473*Cb)"
_KB_PROVENANCE = "I2C-bus spec NXP UM10204 (bus-spec grade)"
_KB_CONFIDENCE = "partial"

# Standard-mode sink electrical limits (KB rule: VOL=0.4V, IOL=3mA).
_VOL_V = 0.4
_IOL_A = 3e-3

# Rise-time budget by bus speed (KB rule: standard 1000ns, fast 300ns).
# tr bounds Rp_max = tr / (0.8473 * Cb).
_TR_BY_SPEED_NS = {
    100_000: 1000.0,   # standard mode
    400_000: 300.0,    # fast mode
    1_000_000: 120.0,  # fast-mode plus
}

# KB typical values (ordered), each with the speed it is canonical for.
# chosen = the first typical that BOTH fits [Rp_min, Rp_max] AND matches speed.
_TYPICALS = [
    {"value": "2.2k", "ohm": 2200.0, "canonical_speed_hz": 400_000, "note": "400 kHz fast mode"},
    {"value": "4.7k", "ohm": 4700.0, "canonical_speed_hz": 100_000, "note": "100 kHz standard"},
    {"value": "10k", "ohm": 10000.0, "canonical_speed_hz": None, "note": "low power"},
]


def _evidence() -> dict:
    """The evidence block stamped on every suggestion — KB anchor + provenance."""
    return {
        "kb_object": _KB_OBJECT,
        "formula": _KB_FORMULA,
        "provenance": _KB_PROVENANCE,
        "confidence": _KB_CONFIDENCE,
    }


def _tr_ns_for_speed(speed_hz: float) -> float:
    """Rise-time budget (ns) for the bus speed. Nearest known tier at/above."""
    if speed_hz in _TR_BY_SPEED_NS:
        return _TR_BY_SPEED_NS[speed_hz]
    # Pick the tier for the smallest canonical speed >= requested; else the
    # fastest (tightest tr). Deterministic, no guessing beyond documented tiers.
    for tier_hz in sorted(_TR_BY_SPEED_NS):
        if speed_hz <= tier_hz:
            return _TR_BY_SPEED_NS[tier_hz]
    return _TR_BY_SPEED_NS[max(_TR_BY_SPEED_NS)]


def _compute_rp_bounds(vcc_v: float, bus_capacitance_pf: float, speed_hz: float) -> dict:
    """Rp_min / Rp_max from the KB formulas. Deterministic."""
    rp_min = (vcc_v - _VOL_V) / _IOL_A
    tr_s = _tr_ns_for_speed(speed_hz) * 1e-9
    cb_f = bus_capacitance_pf * 1e-12
    rp_max = tr_s / (0.8473 * cb_f)
    return {
        "rp_min_ohm": round(rp_min, 1),
        "rp_max_ohm": round(rp_max, 1),
        "tr_ns": _tr_ns_for_speed(speed_hz),
    }


def _choose_typical(rp_min: float, rp_max: float, speed_hz: float) -> dict:
    """Pick the KB typical value that fits [Rp_min, Rp_max] AND matches speed.

    Returns {chosen, basis, warning?}. If no typical fits the window, warn and
    do NOT force a value (honesty: the heuristic did not fit; say so).
    """
    # Prefer the typical canonical for this speed if it fits the window.
    speed_pref = [t for t in _TYPICALS if t["canonical_speed_hz"] == speed_hz]
    ordered = speed_pref + [t for t in _TYPICALS if t not in speed_pref]
    for t in ordered:
        if rp_min <= t["ohm"] <= rp_max:
            return {
                "chosen": t["value"],
                "chosen_ohm": t["ohm"],
                "basis": f"typical for {t['note']}; within [Rp_min, Rp_max]",
            }
    return {
        "chosen": None,
        "chosen_ohm": None,
        "basis": None,
        "warning": (
            "no typical value fits [Rp_min={:.0f}, Rp_max={:.0f}]; compute an exact "
            "Rp for this bus (VCC/Cb/speed combination is outside the standard "
            "typical set)".format(rp_min, rp_max)
        ),
    }


# ── Voltage inference for common named rails (deterministic, documented) ──────
# Used only when the caller passes a rail NAME but no explicit vcc_v; a named
# rail like "+1V8" encodes its own voltage. Unknown names => caller must pass
# vcc_v explicitly (no guessing).
_RAIL_NAME_VOLTS = {
    "+1V8": 1.8, "1V8": 1.8, "+3V3": 3.3, "3V3": 3.3,
    "+2V5": 2.5, "2V5": 2.5, "+5V": 5.0, "5V": 5.0, "+1V2": 1.2, "1V2": 1.2,
}


def _rail_voltage(intent: dict) -> float:
    """Resolve pull_rail voltage: explicit vcc_v wins, else infer from rail name.

    Fail-loud: an unresolvable rail raises ValueError (never a guessed voltage).
    """
    if intent.get("vcc_v") is not None:
        return float(intent["vcc_v"])
    rail = str(intent.get("pull_rail", "")).strip()
    if rail in _RAIL_NAME_VOLTS:
        return _RAIL_NAME_VOLTS[rail]
    raise ValueError(
        f"cannot resolve pull-rail voltage: rail={rail!r} is not a known named "
        f"rail and no explicit vcc_v was given. Pass vcc_v to size Rp_min honestly."
    )


def _pullup_suggestion(line_net: str, pull_rail: str, chosen: dict,
                       bounds: dict, line_label: str) -> dict:
    """One pull-up suggestion (SCL or SDA), evidence-stamped. Draft, not applied."""
    comp = {
        "type": "resistor",
        "value": chosen.get("chosen"),
        "net_from": line_net,
        "net_to": pull_rail,
    }
    computed = {
        "rp_min_ohm": bounds["rp_min_ohm"],
        "rp_max_ohm": bounds["rp_max_ohm"],
        "tr_ns": bounds["tr_ns"],
        "chosen": chosen.get("chosen"),
        "basis": chosen.get("basis"),
    }
    if chosen.get("warning"):
        computed["warning"] = chosen["warning"]
    return {
        "component": comp,
        "rationale": f"Rp for {line_label} pull-up",
        "computed": computed,
        "evidence": _evidence(),
    }


def _spec_fragment(scl_net: str, sda_net: str, pull_rail: str,
                   chosen: dict) -> dict:
    """A review-then-paste fragment: draft component + net entries the human can
    merge into the compose spec after review (consumer round=7 request).

    Shape mirrors the compose spec's {components, nets} schema so the reviewer
    pastes rather than hand-transcribes. Refs are DRAFT hints (R_SCL_PU /
    R_SDA_PU) the reviewer renames; the fragment carries the same suggested/
    review_required honesty markers — it is a pasteable draft, NOT a decision.
    """
    value = chosen.get("chosen")
    return {
        "status": "suggested",
        "review_required": True,
        "note": (
            "Draft component/net fragment — review refs/value, then merge into "
            "the compose spec. Refs are hints, rename as you like."
        ),
        "components": [
            {"ref": "R_SCL_PU", "symbol": "Device:R", "value": value,
             "draft_ref": True,
             "pins": {"1": scl_net, "2": pull_rail}},
            {"ref": "R_SDA_PU", "symbol": "Device:R", "value": value,
             "draft_ref": True,
             "pins": {"1": sda_net, "2": pull_rail}},
        ],
        "net_additions": [
            {"net": scl_net, "add_node": "R_SCL_PU.1"},
            {"net": pull_rail, "add_node": "R_SCL_PU.2"},
            {"net": sda_net, "add_node": "R_SDA_PU.1"},
            {"net": pull_rail, "add_node": "R_SDA_PU.2"},
        ],
    }


def suggest_i2c_pullups(intent: dict) -> dict:
    """Suggest (do NOT decide) the I2C pull-up pair for an open-drain bus.

    Given a high-level *intent* — the bus is an N-device open-drain I2C bus at a
    given speed on a given rail — emit a DRAFT suggestion of the concrete
    pull-up topology (one Rp on SCL, one on SDA, to the pull rail) with each
    value COMPUTED from the KB rule control.sch.pullup-termination-sizing and
    stamped with its evidence.

    Honesty contract (enforced):
      - status is always "suggested" (never "committed"); review_required=True.
      - deterministic + side-effect free: the input `intent` is NOT mutated and
        no file is written.
      - values are computed from KB formulas, never fabricated; if no typical
        value fits the [Rp_min, Rp_max] window a warning is emitted rather than
        forcing a value.

    intent keys: bus, scl_net, sda_net, pull_rail, speed_hz, bus_capacitance_pf,
                 device_count; optional vcc_v (overrides rail-name inference).

    Returns the draft suggestion dict (see design_suggest_i2c_pullup.md).
    """
    # Read-only snapshot: never mutate the caller's intent (honesty: no side
    # effects). We only READ from this copy.
    src = copy.deepcopy(intent)

    bus = src.get("bus")
    scl_net = src.get("scl_net")
    sda_net = src.get("sda_net")
    pull_rail = src.get("pull_rail")
    speed_hz = float(src.get("speed_hz", 100_000))
    bus_capacitance_pf = float(src.get("bus_capacitance_pf", 0) or 0)

    missing = [k for k in ("bus", "scl_net", "sda_net", "pull_rail")
               if not src.get(k)]
    if missing:
        raise ValueError(f"intent missing required keys: {missing}")
    if bus_capacitance_pf <= 0:
        raise ValueError("bus_capacitance_pf must be > 0 to bound Rp_max honestly")

    vcc_v = _rail_voltage(src)
    bounds = _compute_rp_bounds(vcc_v, bus_capacitance_pf, speed_hz)
    chosen = _choose_typical(bounds["rp_min_ohm"], bounds["rp_max_ohm"], speed_hz)

    suggestions = [
        _pullup_suggestion(scl_net, pull_rail, chosen, bounds, "SCL"),
        _pullup_suggestion(sda_net, pull_rail, chosen, bounds, "SDA"),
    ]

    result = {
        "status": "suggested",          # honesty: never "committed"
        "bus": bus,
        "intent_echo": {
            "speed_hz": speed_hz,
            "bus_capacitance_pf": bus_capacitance_pf,
            "device_count": src.get("device_count"),
            "pull_rail": pull_rail,
            "vcc_v": vcc_v,
        },
        "suggestions": suggestions,
        "spec_fragment": _spec_fragment(scl_net, sda_net, pull_rail, chosen),
        "review_required": True,
        "note": (
            "Draft suggestion — NOT applied to spec. Human review + commit "
            "required. Values computed from KB rule, not fabricated."
        ),
    }
    if chosen.get("warning"):
        result["warning"] = chosen["warning"]
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Scheme C slice 2: series-termination "evidence-backed suggestion" generator
# ═══════════════════════════════════════════════════════════════════════════
# Unlike I2C pull-up (value from a typical table), series R = Z0 is COMPUTED
# from physics (impedance), which is why it more sharply demonstrates "the
# engine is doing circuit design, not table lookup". KB anchor: the SI rule
# control.si.interface-requirements (track A ingest).

import math

# ── SI KB evidence anchor (control.si.interface-requirements) ────────────────
_SI_KB_OBJECT = "control.si.interface-requirements"
_SI_KB_FORMULA = (
    "series R = Z0 at source (point-to-point); "
    "Z0 microstrip = (87/sqrt(er+1.41))*ln(5.98H/(0.8W+T)); "
    "knee = 0.35/tr; transmission-line when len > lambda/10"
)
_SI_KB_PROVENANCE = (
    "design-advisory prose; standard SI engineering (Z0 microstrip, knee freq)"
)
_SI_KB_CONFIDENCE = "partial"

# Signal propagation velocity on FR4 microstrip: v = c/sqrt(er_eff), er_eff~3.0
# (KB: FR4 er~4.2, er_eff~3.0). c=2.998e8 m/s => v ~ 1.73e8 m/s.
_C_M_S = 2.998e8
_ER_EFF_FR4 = 3.0

# E24 series (5% resistors) for honest nearest-standard selection.
_E24 = [
    10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36, 39, 43, 47, 51,
    56, 62, 68, 75, 82, 91,
]


def _si_evidence() -> dict:
    """Evidence block for series-termination suggestions — SI KB anchor."""
    return {
        "kb_object": _SI_KB_OBJECT,
        "formula": _SI_KB_FORMULA,
        "provenance": _SI_KB_PROVENANCE,
        "confidence": _SI_KB_CONFIDENCE,
    }


def _microstrip_z0(er: float, h_mm: float, w_mm: float, t_mm: float) -> float:
    """Z0 (ohm) via the KB microstrip formula. Deterministic.

    Z0 = (87/sqrt(er+1.41)) * ln(5.98H / (0.8W + T))
    """
    denom = 0.8 * w_mm + t_mm
    if denom <= 0:
        raise ValueError("stackup w_mm/t_mm produce non-positive (0.8W+T)")
    ratio = 5.98 * h_mm / denom
    if ratio <= 0:
        raise ValueError("stackup geometry produces non-positive ln() argument")
    return (87.0 / math.sqrt(er + 1.41)) * math.log(ratio)


def _nearest_e24(ohm: float) -> float:
    """Nearest E24 standard resistor value (ohm) to the target — honest rounding."""
    if ohm <= 0:
        return 0.0
    decade = math.floor(math.log10(ohm))
    best = None
    for mult_pow in (decade - 1, decade, decade + 1):
        scale = 10 ** mult_pow
        for base in _E24:
            cand = base * scale / 10.0
            if best is None or abs(cand - ohm) < abs(best - ohm):
                best = cand
    return round(best, 2)


def _fmt_ohm(ohm: float) -> str:
    """Format a resistor value like '50R' / '33R' / '4.7k' honestly."""
    if ohm >= 1000:
        v = ohm / 1000.0
        return (f"{v:.1f}".rstrip("0").rstrip(".")) + "k"
    return (f"{ohm:.1f}".rstrip("0").rstrip(".")) + "R"


def _resolve_z0(intent: dict) -> tuple[float, str, str]:
    """Resolve Z0 (ohm), its source tag, and a c04 handoff note.

    Priority: caller target_z0_ohm > microstrip from assumed stackup.
    Fail-loud (ValueError) when neither is given — never a guessed Z0.
    """
    if intent.get("target_z0_ohm") is not None:
        z0 = float(intent["target_z0_ohm"])
        return (
            round(z0, 1),
            "caller-specified",
            "Z0 target is caller-specified; C04 realises it via impedance_solve "
            "(solves real trace width for this Z0 on the actual stackup).",
        )
    stackup = intent.get("stackup")
    if isinstance(stackup, dict):
        er = float(stackup.get("er", 4.2))
        h = float(stackup["h_mm"])
        w = float(stackup["w_mm"])
        t = float(stackup.get("t_mm", 0.035))
        z0 = _microstrip_z0(er, h, w, t)
        return (
            round(z0, 1),
            "derived-from-assumed-stackup",
            "Z0 derived from an ASSUMED stackup (er/H/W/T); C04 MUST confirm with "
            "the real trace width/height via impedance_solve before this value is final.",
        )
    raise ValueError(
        "no impedance source: pass target_z0_ohm (design target) OR "
        "stackup{er,h_mm,w_mm,t_mm} (to derive Z0). Refusing to guess Z0."
    )


def _termination_needed(intent: dict) -> tuple[object, dict]:
    """λ/10 transmission-line test. Returns (needed?, computed-subset).

    needed is True/False when trace_len_mm + edge_rate_ns are given; None when
    length/edge is unknown (honest — do not silently skip).
    """
    trace_len_mm = intent.get("trace_len_mm")
    edge_rate_ns = intent.get("edge_rate_ns")
    sub: dict = {"trace_len_mm": trace_len_mm}
    if edge_rate_ns is None or trace_len_mm is None:
        sub["knee_freq_hz"] = None
        sub["lambda_over_10_mm"] = None
        # Unknown length/edge: honest null (caller may force via high_speed flag).
        needed = True if intent.get("high_speed") else None
        return needed, sub
    tr_s = float(edge_rate_ns) * 1e-9
    knee = 0.35 / tr_s
    v = _C_M_S / math.sqrt(_ER_EFF_FR4)
    lambda_mm = (v / knee) * 1000.0
    lambda_over_10_mm = lambda_mm / 10.0
    sub["knee_freq_hz"] = round(knee, 1)
    sub["lambda_over_10_mm"] = round(lambda_over_10_mm, 2)
    needed = float(trace_len_mm) > lambda_over_10_mm
    return needed, sub


def _series_spec_fragment(net: str, driver_ref: str, value: str,
                          series_node: str) -> dict:
    """Review-then-paste fragment for a source series resistor (same honesty
    markers as the I2C fragment). The series R breaks the net at the driver:
    driver pin -> R -> the rest of the net. `series_node` is the intermediate
    node name between driver and R (a draft hint the reviewer renames).
    """
    return {
        "status": "suggested",
        "review_required": True,
        "note": (
            "Draft series-R fragment — the resistor goes in-line at the driver "
            "source. Review ref/value/node names, then merge into the spec. "
            "Series R splits the net: driver pin -> R -> rest of net."
        ),
        "components": [
            {"ref": f"R_{driver_ref}_{net}_ST", "symbol": "Device:R",
             "value": value, "draft_ref": True,
             "pins": {"1": series_node, "2": net}},
        ],
        "net_note": (
            f"insert R in series at {driver_ref}'s driver pin on '{net}': move "
            f"the driver pin onto new node '{series_node}', R spans "
            f"'{series_node}' <-> '{net}'."
        ),
    }


def suggest_series_termination(intent: dict) -> dict:
    """Suggest (do NOT decide) a source series-termination resistor for a net.

    Given a high-level *intent* — a net driven point-to-point by driver_ref that
    may be a transmission line — emit a DRAFT suggestion of the source series R
    (= Z0), with Z0 either caller-specified or COMPUTED from an assumed stackup
    via the KB microstrip formula, and a lambda/10 transmission-line test to say
    honestly whether termination is even needed.

    Honesty contract (enforced):
      - status is always "suggested" (never "committed"); review_required=True.
      - deterministic + side-effect free: input is NOT mutated; no file written.
      - Z0 is computed or caller-given, NEVER guessed — no impedance source
        raises ValueError.
      - a sub-lambda/10 short trace returns termination_needed=False and does
        NOT force a series R.
      - series R = Z0 depends on C04-confirmed impedance; c04_handoff says so.

    intent keys: net, driver_ref, net_class (optional); impedance source
      target_z0_ohm OR stackup{er,h_mm,w_mm,t_mm}; length test trace_len_mm +
      edge_rate_ns (optional; high_speed flag forces need when length unknown).
    """
    src = copy.deepcopy(intent)  # read-only snapshot; never mutate caller input

    net = src.get("net")
    driver_ref = src.get("driver_ref")
    missing = [k for k in ("net", "driver_ref") if not src.get(k)]
    if missing:
        raise ValueError(f"intent missing required keys: {missing}")

    # Z0 (fail-loud if no impedance source) + the lambda/10 need test.
    z0_ohm, z0_source, c04_handoff = _resolve_z0(src)
    needed, len_sub = _termination_needed(src)

    series_r_ohm = z0_ohm  # series R = Z0 at source (point-to-point)
    std_ohm = _nearest_e24(series_r_ohm)
    value = _fmt_ohm(std_ohm)
    basis = (
        f"series R = Z0 = {z0_ohm:g} ohm at source (point-to-point); "
        f"nearest E24 standard = {value} ({std_ohm:g} ohm)"
    )

    computed = {
        "z0_ohm": z0_ohm,
        "z0_source": z0_source,
        "series_r_ohm": series_r_ohm,
        "series_r_standard": value,
        "series_r_standard_ohm": std_ohm,
        "knee_freq_hz": len_sub["knee_freq_hz"],
        "lambda_over_10_mm": len_sub["lambda_over_10_mm"],
        "trace_len_mm": len_sub["trace_len_mm"],
        "basis": basis,
    }

    series_node = f"{net}_SRC"
    if needed is False:
        # Honest: sub-lambda/10 short trace — do NOT force a series R.
        component = {
            "type": "resistor",
            "value": None,
            "placement": f"series at source ({driver_ref})",
            "net_from": None,
            "net_to": None,
        }
        note_extra = (
            " Trace is sub-lambda/10 (not a transmission line at this edge "
            "rate): NO series termination needed — value withheld, not forced."
        )
        spec_fragment = None
    else:
        component = {
            "type": "resistor",
            "value": value,
            "placement": f"series at source ({driver_ref})",
            "net_from": series_node,
            "net_to": net,
        }
        note_extra = ""
        spec_fragment = _series_spec_fragment(net, driver_ref, value, series_node)

    suggestion = {
        "component": component,
        "computed": computed,
        "c04_handoff": c04_handoff,
        "evidence": _si_evidence(),
    }

    result = {
        "status": "suggested",          # honesty: never "committed"
        "net": net,
        "driver_ref": driver_ref,
        "net_class": src.get("net_class"),
        "termination_needed": needed,   # True / False / None (length unknown)
        "suggestion": suggestion,
        "spec_fragment": spec_fragment,
        "review_required": True,
        "note": (
            "Draft suggestion — NOT applied to spec. Series R = Z0 depends on "
            "C04-confirmed impedance. Human review + commit required. Values "
            "computed from KB rule, not fabricated." + note_extra
        ),
    }
    if needed is None:
        result["length_note"] = (
            "trace length / edge rate unknown: lambda/10 need-test could not "
            "run. Provide trace_len_mm + edge_rate_ns, or set high_speed=true."
        )
    return result


# ── Crystal KB evidence anchor (control.si.crystal-oscillator-layout) ─────────
# The load-cap matching CONCEPT is KB-verified (NXP AN1706 + Microchip AN826,
# source_weight=6); the explicit closed form C_load_each = 2*(CL - C_stray) is
# standard EE and is NOT verbatim-anchored to the KB object — the KB object
# itself marks the verbatim CL formula as UNVERIFIED. The evidence block below
# carries that honesty distinction in `form_note`.
_XTAL_KB_OBJECT = "control.si.crystal-oscillator-layout"
_XTAL_KB_FORMULA = "C_load_each = 2*(CL - C_stray); symmetric crystal load-cap matching"
_XTAL_KB_PROVENANCE = "NXP AN1706 §3.1 + Microchip AN826"
_XTAL_KB_CONFIDENCE = "verified"
_XTAL_KB_FORM_NOTE = (
    "load-cap matching CONCEPT is KB-verified (control.si.crystal-oscillator-layout, "
    "NXP AN1706 + Microchip AN826); the explicit closed form "
    "C_load_each=2*(CL-Cstray) is standard EE, NOT verbatim-anchored to the KB object"
)

_XTAL_DEFAULT_STRAY_PF = 4.0   # typical short-trace PCB stray (KB: 15-50pF only for long/high-Dk)
_XTAL_MATCH_TOL_PF = 1.0       # verify-mode consistency tolerance


def _xtal_evidence() -> dict:
    """Evidence block for a crystal load-cap suggestion — honest form boundary."""
    return {
        "kb_object": _XTAL_KB_OBJECT,
        "formula": _XTAL_KB_FORMULA,
        "provenance": _XTAL_KB_PROVENANCE,
        "confidence": _XTAL_KB_CONFIDENCE,
        "form_note": _XTAL_KB_FORM_NOTE,
    }


def _c_load_each_pf(cl_pf: float, stray_pf: float) -> float:
    """Per-cap load value from symmetric matching: C_load_each = 2*(CL - Cstray)."""
    return round(2.0 * (cl_pf - stray_pf), 3)


def _fmt_pf(pf: float) -> str:
    """Format a picofarad value: drop a trailing .0 (18.0 -> '18pF')."""
    if pf == int(pf):
        return f"{int(pf)}pF"
    return f"{pf:g}pF"


def _xtal_spec_fragment(crystal: str, osc_pins: list, load_cap_refs: list,
                        ground_net: str, value: str, mode: str) -> dict:
    """A review-then-paste fragment: two draft load caps (Cx/Cy), one per osc pin
    to GND. Mirrors the compose {components, nets} schema so the reviewer pastes
    rather than hand-transcribes. Carries suggested/review_required honesty
    markers — a pasteable draft, NOT a decision.
    """
    # Ref hints: reuse the spec's load_cap_refs if given, else draft CX1/CX2.
    refs = list(load_cap_refs) if load_cap_refs else ["CX1", "CX2"]
    while len(refs) < 2:
        refs.append(f"CX{len(refs) + 1}")
    pins = list(osc_pins) if osc_pins else ["OSC_IN", "OSC_OUT"]
    while len(pins) < 2:
        pins.append(f"OSC_{len(pins)}")
    note = (
        "Draft load-cap fragment — review value/refs, then merge into the "
        "compose spec. Refs are hints, rename as you like."
    )
    if mode == "verify":
        note = (
            "Verify mode: these caps ALREADY exist in the spec and match the "
            "computed value. Fragment shown for review parity, not for re-adding."
        )
    return {
        "status": "suggested",
        "review_required": True,
        "note": note,
        "components": [
            {"ref": refs[0], "symbol": "Device:C", "value": value,
             "draft_ref": mode != "verify",
             "pins": {"1": pins[0], "2": ground_net}},
            {"ref": refs[1], "symbol": "Device:C", "value": value,
             "draft_ref": mode != "verify",
             "pins": {"1": pins[1], "2": ground_net}},
        ],
        "net_additions": [
            {"net": pins[0], "add_node": f"{refs[0]}.1"},
            {"net": ground_net, "add_node": f"{refs[0]}.2"},
            {"net": pins[1], "add_node": f"{refs[1]}.1"},
            {"net": ground_net, "add_node": f"{refs[1]}.2"},
        ],
    }


def suggest_crystal_load_caps(intent: dict) -> dict:
    """Suggest (or VERIFY, do NOT decide) a crystal's two load caps.

    Given a crystal intent — the crystal ref, its two oscillator nets, the
    crystal load capacitance CL, and a PCB stray-capacitance assumption — compute
    the symmetric per-cap load value and either SUGGEST it (no existing caps) or
    VERIFY it against the spec's existing cap value (cross-check, bodesign's core
    "demonstrate reliability by comparison" philosophy).

        C_load_each = 2 * (CL - C_stray)

    Honesty contract (enforced):
      - status is always "suggested" (never "committed"); review_required=True.
      - deterministic + side-effect free: `intent` is NOT mutated, no file written.
      - C_load_each is COMPUTED, never fabricated.
      - CL SOURCE is honestly marked (`cl_source`: datasheet | back-derived-
        assumption); a back-derived CL says so in the note.
      - FORM boundary is honest: the load-cap matching CONCEPT is KB-verified
        (control.si.crystal-oscillator-layout), but the explicit closed form is
        standard EE and is NOT verbatim-anchored — carried in evidence.form_note.
      - verify mode REPORTS a CONSISTENT/MISMATCH verdict; it never edits the spec.

    intent keys: crystal, osc_pins[2], load_cap_refs[2] (optional), crystal_cl_pf,
                 cl_source (optional), stray_pf (optional, default 4),
                 existing_cap_pf (optional -> verify mode), ground_net (optional).

    Returns the draft suggestion / verify dict (see design_suggest_crystal_load_caps.md).
    """
    # Read-only snapshot: never mutate the caller's intent (honesty: no side effects).
    src = copy.deepcopy(intent)

    crystal = src.get("crystal")
    if not crystal:
        raise ValueError("intent missing required key: crystal")
    if src.get("crystal_cl_pf") is None:
        raise ValueError(
            "intent missing crystal_cl_pf: cannot size load caps without the "
            "crystal's load capacitance CL (do not guess CL)"
        )

    cl_pf = float(src["crystal_cl_pf"])
    stray_pf = float(src.get("stray_pf", _XTAL_DEFAULT_STRAY_PF))
    cl_source = src.get("cl_source", "unspecified")
    osc_pins = src.get("osc_pins") or []
    load_cap_refs = src.get("load_cap_refs") or []
    ground_net = src.get("ground_net", "GND")

    c_each = _c_load_each_pf(cl_pf, stray_pf)
    value = _fmt_pf(c_each)

    computed = {
        "crystal_cl_pf": cl_pf,
        "cl_source": cl_source,
        "stray_pf": stray_pf,
        "c_load_each_pf": c_each,
        "formula": _XTAL_KB_FORMULA,
        "basis": (
            f"C_load_each = 2*(CL - C_stray) = 2*({cl_pf:g} - {stray_pf:g}) "
            f"= {c_each:g}pF (symmetric Cx=Cy)"
        ),
    }

    existing = src.get("existing_cap_pf")
    mode = "verify" if existing is not None else "suggest"

    note_parts = [
        "Draft — NOT applied to spec. Human review + commit required. "
        "C_load_each computed from CL, not fabricated."
    ]
    if cl_source == "back-derived-assumption":
        note_parts.append(
            "CL is BACK-DERIVED from the existing caps, NOT datasheet-measured; "
            "verify against the crystal datasheet when available."
        )

    result = {
        "status": "suggested",          # honesty: never "committed"
        "mode": mode,
        "crystal": crystal,
        "computed": computed,
        "suggestion": {
            "component": {
                "type": "capacitor",
                "value": value,
                "count": 2,
                "placement": "one per oscillator pin to GND (Cx, Cy)",
            },
            "evidence": _xtal_evidence(),
        },
        "spec_fragment": _xtal_spec_fragment(
            crystal, osc_pins, load_cap_refs, ground_net, value, mode),
        "review_required": True,
    }

    if mode == "verify":
        existing_pf = float(existing)
        delta = round(existing_pf - c_each, 3)
        result["existing_cap_pf"] = existing_pf
        result["delta_pf"] = delta
        result["verdict"] = (
            "CONSISTENT" if abs(delta) <= _XTAL_MATCH_TOL_PF else "MISMATCH"
        )
        if result["verdict"] == "CONSISTENT":
            note_parts.append(
                f"VERIFY: existing {existing_pf:g}pF matches computed {c_each:g}pF "
                f"(delta {delta:g}pF, within +/-{_XTAL_MATCH_TOL_PF:g}pF)."
            )
        else:
            note_parts.append(
                f"VERIFY: existing {existing_pf:g}pF does NOT match computed "
                f"{c_each:g}pF (delta {delta:g}pF). Reported only; spec unchanged."
            )

    result["note"] = " ".join(note_parts)
    return result


# ══════════════════════════════════════════════════════════════════════════
# WP5 — `bodesign_design_suggest`: the pin-class router
# ══════════════════════════════════════════════════════════════════════════
# plan c03_delivery_contract_and_engine_seams WP5, DD-02, errors.md §WP5.
#
# The nine pin classes come from
# skills/bodesign/stages/c03-ee/references/pinout-to-circuit-method.md:32-47.
# Which of them this verb may answer is decided by MEASURED KB coverage
# (design.md §WP5 KB coverage), never by what feels reasonable: a class with no
# anchor returns `no-rule` and no value, because DD-02 property (3) says a value
# without an `evidence.kb_object` is a fabrication regardless of how right it looks.

SUGGEST_STATUSES = ("suggested", "no-rule", "indeterminate")

#: DD-02 property (1), asserted BY CONSTRUCTION rather than by convention.
#: `committed` is not a member of the codomain, so no code path can emit it --
#: a suggestion that could mark itself committed would be deciding, which is the
#: line `concept.bodesign.netlist-synthesis-gap` forbids this layer to cross.
#:
#: SCOPE, so the assert is not over-read (the red line was rewritten 2026-09-07
#: because its old wording conflated two risks): what is forbidden is THE SYSTEM
#: deciding a net -- suggest may not silently become commit. It is NOT forbidden
#: for a CALLER to hand bodesign a topology it already decided; that path has no
#: fabrication risk and is a separate, permitted entry
#: (`concept.bodesign.agent-declared-topology` -> `declare.py::declare_circuit`).
#: Three postures, only the third is banned: suggest (system proposes, human
#: adjudicates) / declare (caller decides, system lands) / synthesize (system
#: decides). This assert defends the boundary of the FIRST one only.
assert "committed" not in SUGGEST_STATUSES

PIN_CLASSES = (
    "power", "ground", "clock", "reset-en", "boot-strapping",
    "analog-reference", "io-gpio", "high-speed", "nc-dnc",
)

DESIGN_SUGGEST_INPUT_INVALID = "DESIGN_SUGGEST_INPUT_INVALID"


class DesignSuggestInputError(ValueError):
    """A refusal about the INPUT, deliberately off the `status` axis.

    A caller who omitted `pin_class` has not discovered that a class is
    uncovered -- they have a typo. Returning `no-rule` would tell them the KB is
    missing a rule, sending them to write one for a question they never asked.
    """

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.code = DESIGN_SUGGEST_INPUT_INVALID
        self.message = message
        self.hint = hint


# ── Power / decoupling rule (control.power.decoupling-pdn-strategy) ──────────
# The ONLY class among the four newly-queried ones whose anchor carries an
# actionable checker rather than an obligation sentence. Transcribed from the KB
# body (TI SPRABV2): 0.1uF per 2 power pins, ~15uF bulk per 10 power pins,
# decoupling within 1.25cm of the IC. `confidence=verified` in the KB row.
_PWR_KB_OBJECT = "control.power.decoupling-pdn-strategy"
_PWR_KB_FORMULA = ("pin caps = ceil(power_pins / 2) x 0.1uF; "
                   "bulk = ceil(power_pins / 10) x ~15uF; placement <= 1.25cm")
_PWR_KB_PROVENANCE = "TI SPRABV2 (BGA decoupling / PDN strategy); TMS320 5.6 for the 1.25cm figure"
_PWR_KB_CONFIDENCE = "verified"

_PWR_PIN_CAP_VALUE = "0.1uF"
_PWR_PINS_PER_CAP = 2
_PWR_BULK_VALUE = "15uF"
_PWR_PINS_PER_BULK = 10
_PWR_MAX_DISTANCE_CM = 1.25


def _power_evidence() -> dict:
    return {
        "kb_object": _PWR_KB_OBJECT,
        "formula": _PWR_KB_FORMULA,
        "provenance": _PWR_KB_PROVENANCE,
        "confidence": _PWR_KB_CONFIDENCE,
    }


def _suggest_power_decoupling(context: dict) -> dict:
    """Decoupling cascade for one rail, counted from its power pins.

    Returns the {status, suggestions, evidence, ...} body; the caller stamps the
    envelope. Raises DesignSuggestInputError when the context does not name the
    pins -- a count is the whole input, and defaulting it to zero would produce
    a confident "no caps needed".
    """
    pins = context.get("power_pins")
    if pins is None:
        raise DesignSuggestInputError(
            "context.power_pins is required for pin_class='power': the cap count "
            "IS ceil(pins/2), so an absent pin list has no honest default",
            hint='pass context={"power_pins": ["1", "12", ...], "rail": "+3V3"}')
    if not isinstance(pins, (list, tuple)):
        raise DesignSuggestInputError(
            "context.power_pins must be a list of pin identifiers, got "
            f"{type(pins).__name__}")

    rail = context.get("rail") or context.get("pull_rail") or "VCC"
    ref = context.get("ref") or context.get("mpn") or "U?"
    count = len(pins)

    if count == 0:
        # ZERO-SUBJECT ARM (errors.md: `no-rule` with empty suggestions, class
        # `empty`). The rule ran and matched the class; the board simply has no
        # pin of it. `evidence` is populated precisely so this is distinguishable
        # from the uncovered-class arm, which carries none.
        return {
            "status": "no-rule",
            "suggestions": [],
            "evidence": _power_evidence(),
            "reason": (
                f"rule {_PWR_KB_OBJECT} covers pin_class='power' and executed, but "
                f"the supplied context names zero power pins on {ref} -- nothing "
                "to suggest. This is NOT an uncovered class: the evidence block "
                "above names the rule that found nothing to do."),
            "rule_matched": True,
        }

    pin_caps = -(-count // _PWR_PINS_PER_CAP)      # ceil
    bulk_caps = -(-count // _PWR_PINS_PER_BULK)    # ceil

    suggestions = [
        {
            "component": {"type": "capacitor", "value": _PWR_PIN_CAP_VALUE,
                          "count": pin_caps,
                          "placement": f"local to {ref} power pins, <= {_PWR_MAX_DISTANCE_CM}cm",
                          "net_from": rail, "net_to": context.get("ground_net", "GND")},
            "basis": (f"{count} power pin(s) / {_PWR_PINS_PER_CAP} per cap "
                      f"= {pin_caps} x {_PWR_PIN_CAP_VALUE} (ceil)"),
            "evidence": _power_evidence(),
        },
        {
            "component": {"type": "capacitor", "value": _PWR_BULK_VALUE,
                          "count": bulk_caps,
                          "placement": f"bulk for rail {rail}; may sit further than the pin caps",
                          "net_from": rail, "net_to": context.get("ground_net", "GND")},
            "basis": (f"{count} power pin(s) / {_PWR_PINS_PER_BULK} per bulk cap "
                      f"= {bulk_caps} x {_PWR_BULK_VALUE} (ceil)"),
            "evidence": _power_evidence(),
        },
    ]
    return {
        "status": "suggested",
        "suggestions": suggestions,
        "evidence": _power_evidence(),
        "computed": {"power_pins": count, "pin_caps": pin_caps,
                     "bulk_caps": bulk_caps, "rail": rail,
                     "max_distance_cm": _PWR_MAX_DISTANCE_CM},
        "rule_matched": True,
    }


# ── Analog-reference rule (step.sch.mcu-adc-frontend-review) ────────────────
# MEASURED LIMIT, and it decides the shape of this arm. The anchor was read in
# full (1196 chars, `confidence=partial`, `extraction_status=raw-only`) and its
# entire VREF content is ONE obligation line:
#
#     "VREF/analog-supply pins get required filtering and grounding"
#
# There is no capacitance, no formula, no validated window -- "required" is not
# a value. So this class CANNOT reach `suggested`: emitting the customary 100nF
# would be a fabrication wearing this object's id, which is worse than no answer
# because the evidence block would make it look sourced. The anchor supports an
# OBLIGATION (this pin must be filtered) but not a VALUE, and `indeterminate`
# with the obligation named is the honest projection of exactly that.
_AREF_KB_OBJECT = "step.sch.mcu-adc-frontend-review"
_AREF_KB_PROVENANCE = "evidence-first KiCad schematic review methodology (repo tier)"
_AREF_KB_CONFIDENCE = "partial"
_AREF_KB_OBLIGATION = (
    "VREF/analog-supply pins get required filtering and grounding")


def _aref_evidence() -> dict:
    return {
        "kb_object": _AREF_KB_OBJECT,
        "formula": None,
        "obligation": _AREF_KB_OBLIGATION,
        "provenance": _AREF_KB_PROVENANCE,
        "confidence": _AREF_KB_CONFIDENCE,
        "value_bearing": False,
    }


def _suggest_analog_reference(context: dict) -> dict:
    """Report the VREF filtering OBLIGATION; never invent its value.

    Always `indeterminate` (unresolved-input arm): the anchor states that
    filtering is required and does not state what it is. The obligation is
    returned so the caller learns the pin needs attention -- which is real
    information, and is not the same as a suggestion.
    """
    pins = context.get("vref_pins")
    if pins is None:
        raise DesignSuggestInputError(
            "context.vref_pins is required for pin_class='analog-reference'",
            hint='pass context={"vref_pins": ["14"], "ref": "U3"}')
    if not isinstance(pins, (list, tuple)):
        raise DesignSuggestInputError(
            "context.vref_pins must be a list of pin identifiers, got "
            f"{type(pins).__name__}")

    ref = context.get("ref") or context.get("mpn") or "U?"
    return {
        "status": "indeterminate",
        "suggestions": [],
        "evidence": _aref_evidence(),
        "obligation": {
            "applies_to": [f"{ref}.{p}" for p in pins],
            "statement": _AREF_KB_OBLIGATION,
        },
        "reason": (
            f"{_AREF_KB_OBJECT} states the filtering OBLIGATION for VREF pins but "
            "carries no capacitance, formula or validated window -- 'required "
            "filtering' is not a value. Emitting a customary 100nF here would "
            "attach this object's id to a number it does not contain. The pin "
            "needs filtering; the value must come from the part's datasheet or "
            "from a rule distilled into KB first."),
        "rule_matched": True,
    }


#: Class -> the callable that answers it. MEMBERSHIP IS THE CONTRACT: a class
#: absent from this table returns `no-rule`, and the only way in is a measured,
#: non-degraded KB anchor (design.md WP5 KB coverage). Ground, reset-en,
#: boot-strapping and nc-dnc are deliberately absent -- their queries returned no
#: class-specific anchor on 2026-09-06.
_CLASS_RULES = {
    "power": _suggest_power_decoupling,
    "analog-reference": _suggest_analog_reference,
}


def design_suggest(mpn=None, pin_class=None, context=None) -> dict:
    """Route a pin class to its KB-anchored rule, or refuse to answer.

    Returns {status, mpn, pin_class, suggestions, evidence, review_required, ...}
    with `status` in SUGGEST_STATUSES. `review_required` is True on EVERY path,
    including the ones that suggest nothing: this layer never decides.

    Raises DesignSuggestInputError (code DESIGN_SUGGEST_INPUT_INVALID) for an
    input it cannot accept at all. That is deliberately NOT a status: a caller
    who mistyped a class name has not learned anything about KB coverage.
    """
    if not pin_class:
        raise DesignSuggestInputError(
            "pin_class is required; one of: " + ", ".join(PIN_CLASSES))
    if pin_class not in PIN_CLASSES:
        raise DesignSuggestInputError(
            f"unknown pin_class {pin_class!r}; one of: " + ", ".join(PIN_CLASSES),
            hint="the nine classes come from pinout-to-circuit-method.md:32-47")
    ctx = copy.deepcopy(context or {})   # read-only snapshot; never mutate input

    rule = _CLASS_RULES.get(pin_class)
    if rule is None:
        # UNCOVERED-CLASS ARM. `evidence` is EMPTY here and populated in the
        # zero-subject arm -- that difference is the only thing separating
        # "no rule exists" from "a rule ran and found nothing", and both say
        # `no-rule` with an empty suggestion list.
        return {
            "status": "no-rule",
            "mpn": mpn,
            "pin_class": pin_class,
            "suggestions": [],
            "evidence": {},
            "rule_matched": False,
            "reason": (
                f"pin_class {pin_class!r} has no KB anchor surviving the "
                "fallbackApplied check (design.md WP5 KB coverage, measured "
                "2026-09-06). No rule executed, so no value can exist. Distil a "
                "rule into KB before expecting a suggestion here -- a value "
                "produced without an evidence.kb_object is a fabrication."),
            "review_required": True,
        }

    body = rule(ctx)
    body.update({"mpn": mpn, "pin_class": pin_class, "review_required": True})
    # DD-02 property (1), enforced at the exit rather than trusted: a rule that
    # returned an off-codomain status is a programming error, and letting it
    # through would put an unvetted word where callers read the verdict.
    if body["status"] not in SUGGEST_STATUSES:
        raise AssertionError(
            f"rule for {pin_class!r} returned status {body['status']!r}, "
            f"outside {SUGGEST_STATUSES}")
    return body
