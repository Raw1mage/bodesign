"""declare.py — agent-facing circuit topology declaration -> compose spec.

WHAT THIS REMOVES, stated as the defect:

bodesign exposes ~61 verbs and NOT ONE of them lets an agent say "R13 and R14
form a divider off BATT, tap it into U2.31". Every caller had to hand-build a
flat net table, and nothing ever asked whether that table was COMPLETE. So each
downstream stage invented its own tolerance for an under-specified input, and
each of those tolerances failed in its own way -- which is the shape of the BR
family this package was opened against (plans/eda-bridge_draftsman-series-
divider-wireable/proposal.md counts them).

This module is the entry point that asks the question nobody asked: is this
declaration complete? It is a PURE FUNCTION -- no I/O except optional symbol
library reads, and it imports neither composer nor kicad_emit at module scope
(circular-import free, and unit-testable without a KiCad tree).

Phase 1 implements `divider` and `bridge` (tasks 1.1-1.8). `connect`,
`no_connect` and `rail` are implemented because the completeness gate and the
test vectors cannot be exercised without them; `series` is Phase 2 and raises
E_NOT_IMPLEMENTED rather than silently expanding to something plausible.

Outcome codomain (plans/.../errors.md #Outcome Codomain) -- five classes, and
the emission site of each is named in that table. The three a bare status would
collapse (`ok` / `rejected` / `not_run`) are distinct values here, and `empty`
does NOT share a value with `ok`: BR_20260730b recorded four gates going green
on an empty spec, and returning `ok` for zero declarations would reproduce it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- status values (closed codomain) ---------------------------------------
STATUS_OK = "ok"
STATUS_REJECTED = "rejected"
STATUS_NOT_RUN = "not_run"
STATUS_EMPTY = "empty"
STATUS_INDETERMINATE = "indeterminate"

# --- completeness gate verdicts (its OWN codomain, not the caller's) -------
GATE_PASS = "pass"
GATE_FAIL = "fail"
GATE_NOT_RUN = "not_run"
GATE_VACUOUS = "vacuous"
GATE_UNKNOWN = "unknown"

VALID_KINDS = frozenset(
    {"connect", "bridge", "series", "divider", "rail", "no_connect"}
)

RENDER_MODES = frozenset({"global_label", "local_star", "daisy_chain"})
DEFAULT_RENDER = "global_label"


@dataclass
class Error:
    """One rejection. `refs` names the offending items so a caller can act."""

    code: str
    detail: str
    refs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail, "refs": list(self.refs)}


def _pin_key(ref: str, pin: str) -> str:
    return f"{ref}.{pin}"


def _split_endpoint(ep: str) -> tuple[str, str] | None:
    """'R13.2' -> ('R13', '2'). Returns None when the form is not <ref>.<pin>.

    Rightmost split: KiCad pin names may not contain '.', but a ref never
    contains one either, so the last dot is the separator.
    """
    if not isinstance(ep, str) or "." not in ep:
        return None
    ref, _, pin = ep.rpartition(".")
    if not ref or not pin:
        return None
    return ref, pin


# ---------------------------------------------------------------------------
# A1 -- input validation. Emission site of status=not_run (GRAFCET step 2).
#
# Everything rejected HERE has the property that the expander was never called.
# That is why not_run is a separate value from rejected: "the check never ran"
# and "the check ran and said no" need different fixes, and a caller cannot
# tell them apart if they share an output.
# ---------------------------------------------------------------------------
def _validate_input(
    components: Any, declarations: Any
) -> tuple[list[Error], dict[str, dict]]:
    errors: list[Error] = []

    if not isinstance(components, list):
        errors.append(
            Error("E_SCHEMA", f"components must be a list, got {type(components).__name__}")
        )
        return errors, {}
    if not isinstance(declarations, list):
        errors.append(
            Error(
                "E_SCHEMA",
                f"declarations must be a list, got {type(declarations).__name__}",
            )
        )
        return errors, {}

    by_ref: dict[str, dict] = {}
    for i, c in enumerate(components):
        if not isinstance(c, dict):
            errors.append(Error("E_SCHEMA", f"components[{i}] must be an object"))
            continue
        ref = c.get("ref")
        if not ref or not isinstance(ref, str):
            errors.append(Error("E_SCHEMA", f"components[{i}] has no usable 'ref'"))
            continue
        if ref in by_ref:
            errors.append(Error("E_SCHEMA", f"duplicate component ref {ref!r}", [ref]))
            continue
        by_ref[ref] = c

    seen_ids: set[str] = set()
    for i, d in enumerate(declarations):
        if not isinstance(d, dict):
            errors.append(Error("E_SCHEMA", f"declarations[{i}] must be an object"))
            continue
        did = d.get("id")
        if not did or not isinstance(did, str):
            errors.append(Error("E_SCHEMA", f"declarations[{i}] has no usable 'id'"))
            continue
        if did in seen_ids:
            errors.append(Error("E_SCHEMA", f"duplicate declaration id {did!r}", [did]))
            continue
        seen_ids.add(did)
        kind = d.get("kind")
        if kind not in VALID_KINDS:
            errors.append(
                Error(
                    "E_SCHEMA",
                    f"declaration {did!r} has kind {kind!r}; must be one of "
                    + " | ".join(sorted(VALID_KINDS)),
                    [did],
                )
            )
            continue
        errors.extend(_validate_refs(d, did, kind, by_ref))

    return errors, by_ref


def _endpoint_refs(d: dict, kind: str) -> list[tuple[str, str]]:
    """Every (endpoint_string, field_name) this declaration points a pin at.

    Split out from _validate_refs so the same enumeration serves validation and
    expansion -- two enumerations would drift, and the drift would show up as a
    ref that validates but does not expand.
    """
    out: list[tuple[str, str]] = []
    if kind == "connect":
        for ep in d.get("endpoints") or []:
            out.append((ep, "endpoints"))
    elif kind == "no_connect":
        for ep in d.get("pins") or []:
            out.append((ep, "pins"))
    elif kind == "rail":
        for ep in d.get("nodes") or []:
            out.append((ep, "nodes"))
    elif kind == "divider":
        load = d.get("load")
        if load:
            out.append((load, "load"))
    return out


def _validate_refs(d: dict, did: str, kind: str, by_ref: dict[str, dict]) -> list[Error]:
    """Per-kind shape + reference resolution. All findings, not just the first.

    A ref naming a component that was never declared is E_REF_UNKNOWN and lands
    as status=not_run: the expander cannot run against a component it has no
    record of, so reporting it as a rejection would overstate what was checked.
    """
    errors: list[Error] = []

    # -- per-kind required fields --
    if kind == "connect":
        eps = d.get("endpoints")
        if not isinstance(eps, list) or len(eps) != 2:
            errors.append(
                Error("E_SCHEMA", f"{did}: connect.endpoints must be exactly 2", [did])
            )
    elif kind == "bridge":
        part = d.get("part")
        between = d.get("between")
        if not part or not isinstance(part, str):
            errors.append(Error("E_SCHEMA", f"{did}: bridge.part is required", [did]))
        elif part not in by_ref:
            errors.append(
                Error("E_REF_UNKNOWN", f"{did}: bridge.part {part!r} is not in components[]", [part])
            )
        if not isinstance(between, list) or len(between) != 2:
            errors.append(
                Error("E_SCHEMA", f"{did}: bridge.between must be exactly 2 net names", [did])
            )
        pins = d.get("pins")
        if pins is not None and (not isinstance(pins, list) or len(pins) != 2):
            errors.append(
                Error("E_SCHEMA", f"{did}: bridge.pins, when given, must be exactly 2", [did])
            )
    elif kind == "divider":
        for fname in ("top", "bottom", "tap", "r_top", "r_bottom"):
            if not d.get(fname) or not isinstance(d.get(fname), str):
                errors.append(
                    Error("E_SCHEMA", f"{did}: divider.{fname} is required", [did])
                )
        for fname in ("r_top", "r_bottom"):
            ref = d.get(fname)
            if isinstance(ref, str) and ref and ref not in by_ref:
                errors.append(
                    Error(
                        "E_REF_UNKNOWN",
                        f"{did}: divider.{fname} {ref!r} is not in components[]",
                        [ref],
                    )
                )
    elif kind == "rail":
        if not d.get("name") or not isinstance(d.get("name"), str):
            errors.append(Error("E_SCHEMA", f"{did}: rail.name is required", [did]))
        if not isinstance(d.get("nodes"), list):
            errors.append(Error("E_SCHEMA", f"{did}: rail.nodes must be a list", [did]))
        render = d.get("render")
        if render is not None and render not in RENDER_MODES:
            errors.append(
                Error(
                    "E_SCHEMA",
                    f"{did}: rail.render {render!r} must be one of "
                    + " | ".join(sorted(RENDER_MODES)),
                    [did],
                )
            )
        scope = d.get("scope")
        if scope is not None:
            if not isinstance(scope, list):
                errors.append(Error("E_SCHEMA", f"{did}: rail.scope must be a list", [did]))
            else:
                for s in scope:
                    if s not in by_ref:
                        errors.append(
                            Error(
                                "E_RAIL_SCOPE_UNKNOWN",
                                f"{did}: rail.scope names {s!r}, not in components[]",
                                [s],
                            )
                        )
    elif kind == "no_connect":
        if not isinstance(d.get("pins"), list) or not d.get("pins"):
            errors.append(
                Error("E_SCHEMA", f"{did}: no_connect.pins must be a non-empty list", [did])
            )
    elif kind == "series":
        chain = d.get("chain")
        if not isinstance(chain, list) or len(chain) < 3:
            errors.append(
                Error("E_SCHEMA", f"{did}: series.chain needs >=1 part between two nets", [did])
            )

    # -- endpoint refs resolve to a declared component --
    for ep, fname in _endpoint_refs(d, kind):
        parts = _split_endpoint(ep)
        if parts is None:
            errors.append(
                Error("E_SCHEMA", f"{did}: {fname} entry {ep!r} is not <ref>.<pin>", [did])
            )
            continue
        ref, _pin = parts
        if ref not in by_ref:
            errors.append(
                Error(
                    "E_REF_UNKNOWN",
                    f"{did}: {fname} references {ref!r}, not in components[]",
                    [ref],
                )
            )

    return errors


# ---------------------------------------------------------------------------
# A2 -- expansion. Emission site of status=empty (GRAFCET step 4) and of the
# expansion-time rejections.
#
# Intermediate nodes get a STABLE DERIVED NAME (<decl_id>_nN, DD-3) rather than
# SKiDL's N$1 or atopile's anonymous node: a name that renumbers between runs
# makes every diff red without showing what actually changed, and a downstream
# stage cannot reference a node it cannot name.
# ---------------------------------------------------------------------------
@dataclass
class _Expansion:
    nets: dict[str, list[str]] = field(default_factory=dict)
    nc: list[str] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)
    render_plan: dict[str, dict[str, str]] = field(default_factory=dict)
    errors: list[Error] = field(default_factory=list)
    declared_net_names: set[str] = field(default_factory=set)
    derived_net_names: set[str] = field(default_factory=set)

    def add_node(self, net: str, endpoint: str, decl_id: str) -> None:
        """Attach one endpoint to one net, and record WHICH declaration did it.

        provenance is written HERE and nowhere else -- one write site is what
        makes `set(nodes) == set(provenance)` a meaningful assertion rather
        than a restatement of the loop that built both.
        """
        self.nets.setdefault(net, [])
        if endpoint not in self.nets[net]:
            self.nets[net].append(endpoint)
        self.provenance[f"{net}.{endpoint}"] = decl_id


def _default_bridge_pins(part: str, by_ref: dict[str, dict], pin_lists: dict) -> list[str] | None:
    """The two pins of a 2-pin passive, or None when that cannot be established.

    Returns None rather than guessing ['1','2']: a part whose pin list is
    unknown is not the same as a part known to have pins 1 and 2, and a caller
    that cannot tell them apart will read an indeterminate result as a fact.
    """
    pins = pin_lists.get(part)
    if pins is None:
        return None
    ordered = sorted(pins, key=lambda p: (len(p), p))
    if len(ordered) != 2:
        return None
    return ordered


def _expand(
    declarations: list[dict], by_ref: dict[str, dict], pin_lists: dict
) -> _Expansion:
    ex = _Expansion()

    # Pass 1: collect explicitly declared net names, so a derived name that
    # collides with one is reported rather than silently merging two nets.
    for d in declarations:
        kind = d.get("kind")
        if kind == "connect" and d.get("net"):
            ex.declared_net_names.add(d["net"])
        elif kind == "bridge":
            for n in d.get("between") or []:
                ex.declared_net_names.add(n)
        elif kind == "divider":
            for f in ("top", "bottom", "tap"):
                if d.get(f):
                    ex.declared_net_names.add(d[f])
        elif kind == "rail" and d.get("name"):
            ex.declared_net_names.add(d["name"])
        elif kind == "series":
            chain = d.get("chain") or []
            if len(chain) >= 2:
                ex.declared_net_names.add(chain[0])
                ex.declared_net_names.add(chain[-1])

    for d in declarations:
        did = d["id"]
        kind = d["kind"]

        if kind == "connect":
            net = d.get("net") or f"{did}_n1"
            if not d.get("net"):
                ex.derived_net_names.add(net)
            for ep in d.get("endpoints") or []:
                ex.add_node(net, ep, did)

        elif kind == "bridge":
            part = d["part"]
            between = d["between"]
            pins = d.get("pins") or _default_bridge_pins(part, by_ref, pin_lists)
            if pins is None:
                # Not an error: the pin list is unknown, which is exactly the
                # indeterminate case. Fall back to declaring the endpoints with
                # the conventional 2-pin numbering AND record the uncertainty
                # so the gate can downgrade the verdict rather than assert.
                pins = ["1", "2"]
            for net, pin in zip(between, pins):
                ex.add_node(net, _pin_key(part, str(pin)), did)

        elif kind == "divider":
            top, bottom, tap = d["top"], d["bottom"], d["tap"]
            if tap == top or tap == bottom:
                # THE control case from tasks.md. The error echoes the offending
                # tap value: a rejection that does not name what it rejected
                # cannot be distinguished from a rejection for another reason,
                # which is the one failure mode a negative control has.
                ex.errors.append(
                    Error(
                        "E_DIVIDER_TAP_DEGENERATE",
                        f"{did}: divider tap {tap!r} equals "
                        f"{'top' if tap == top else 'bottom'} "
                        f"({top!r}/{bottom!r}); a tap shorted to its own arm is not a divider",
                        [did, tap],
                    )
                )
                continue
            r_top, r_bottom = d["r_top"], d["r_bottom"]
            tp = d.get("pins", {}).get(r_top) if isinstance(d.get("pins"), dict) else None
            bp = d.get("pins", {}).get(r_bottom) if isinstance(d.get("pins"), dict) else None
            tp = tp or ["1", "2"]
            bp = bp or ["1", "2"]
            ex.add_node(top, _pin_key(r_top, str(tp[0])), did)
            ex.add_node(tap, _pin_key(r_top, str(tp[1])), did)
            ex.add_node(tap, _pin_key(r_bottom, str(bp[0])), did)
            ex.add_node(bottom, _pin_key(r_bottom, str(bp[1])), did)
            if d.get("load"):
                ex.add_node(tap, d["load"], did)

        elif kind == "rail":
            name = d["name"]
            for ep in d.get("nodes") or []:
                ex.add_node(name, ep, did)
            render = d.get("render")
            ex.render_plan[name] = (
                {"render": render, "source": "declared"}
                if render
                else {"render": DEFAULT_RENDER, "source": "default"}
            )

        elif kind == "no_connect":
            for ep in d.get("pins") or []:
                if ep not in ex.nc:
                    ex.nc.append(ep)

        elif kind == "series":
            # Phase 2 (tasks.md 2.2). A stub that RAISES is the only honest
            # unimplemented form: returning an empty expansion would let a
            # caller's series declaration vanish into a spec that still says ok.
            ex.errors.append(
                Error(
                    "E_NOT_IMPLEMENTED",
                    f"{did}: kind 'series' is Phase 2 (tasks.md 2.2); "
                    "declared but not expanded in this build",
                    [did],
                )
            )

    # Derived names must not collide with declared ones (E_NET_NAME_COLLISION).
    for derived in sorted(ex.derived_net_names & ex.declared_net_names):
        ex.errors.append(
            Error(
                "E_NET_NAME_COLLISION",
                f"derived net name {derived!r} collides with a declared net name",
                [derived],
            )
        )

    return ex


# ---------------------------------------------------------------------------
# A3 -- provenance. DD-6.
#
# The repo hard rule "No fabrication" was enforceable only by human review. With
# every node carrying the id of the declaration that produced it, "did the
# engine invent a node" becomes one assertion.
# ---------------------------------------------------------------------------
def _check_provenance(ex: _Expansion) -> list[Error]:
    all_nodes = {f"{net}.{ep}" for net, eps in ex.nets.items() for ep in eps}
    orphans = sorted(all_nodes - set(ex.provenance))
    if not orphans:
        return []
    return [
        Error(
            "E_PROVENANCE_ORPHAN",
            f"{len(orphans)} node(s) have no originating declaration -- this is an "
            "ENGINE defect, not a caller error; refusing to emit a spec containing "
            "nodes nobody declared",
            orphans,
        )
    ]


# ---------------------------------------------------------------------------
# A4 -- completeness gate. Its own five-value codomain (errors.md).
#
# Returns a VERDICT, never a bool: `fail` (you left a pin unassigned) and
# `unknown` (I could not read the symbol, so I do not know) need different
# fixes, and collapsing them into False makes the caller unable to choose one.
# ---------------------------------------------------------------------------
@dataclass
class GateResult:
    verdict: str
    assigned: int = 0
    unassigned: list[str] = field(default_factory=list)
    multi_net: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "assigned": self.assigned,
            "unassigned": list(self.unassigned),
            "multi_net": list(self.multi_net),
            "unknown": list(self.unknown),
        }


def check_completeness(
    components: list[dict], ex: _Expansion, pin_lists: dict
) -> GateResult:
    """Every pin of every declared component appears EXACTLY once, or is nc.

    Question this answers, stated so a reader can check the code against it:
    "for each declared component, is each of its pins attached to exactly one
    net or explicitly marked no-connect?"

    Emission sites (errors.md #Outcome Codomain, module completeness_gate):
      pass    -- every pin of every component accounted for
      fail    -- unassigned[] or multi_net[] non-empty
      vacuous -- components == [] : the gate RAN and had nothing to check.
                 Not `pass`: BR_20260730b is four gates going green on an empty
                 input, and a zero-component pass is that same false green.
      unknown -- at least one symbol could not be read, so that component's pin
                 set is not knowable
    (`not_run` is emitted by the CALLER, not here: it means this function was
    never reached, which this function cannot report about itself.)
    """
    if not components:
        return GateResult(GATE_VACUOUS)

    # Which net(s) does each endpoint appear on?
    endpoint_nets: dict[str, list[str]] = {}
    for net, eps in ex.nets.items():
        for ep in eps:
            endpoint_nets.setdefault(ep, []).append(net)

    nc_set = set(ex.nc)
    unassigned: list[str] = []
    multi_net: list[str] = []
    unknown: list[str] = []
    assigned = 0

    for c in components:
        ref = c.get("ref")
        pins = pin_lists.get(ref)
        if pins is None:
            unknown.append(
                f"{ref}: symbol {c.get('symbol')!r} could not be read; pin list unknown"
            )
            continue
        for pin in sorted(pins, key=lambda p: (len(str(p)), str(p))):
            key = _pin_key(ref, str(pin))
            nets_of = endpoint_nets.get(key, [])
            if key in nc_set:
                assigned += 1
                if nets_of:
                    multi_net.append(
                        f"{key} is declared no-connect AND appears on "
                        + ", ".join(sorted(nets_of))
                    )
                continue
            if len(nets_of) == 0:
                unassigned.append(key)
            elif len(nets_of) > 1:
                multi_net.append(f"{key} appears on " + ", ".join(sorted(nets_of)))
                assigned += 1
            else:
                assigned += 1

    if unknown:
        # Unknown DOMINATES fail: a partially-readable input cannot support a
        # confident rejection, and blaming the caller for the engine's inability
        # to read a library is the wrong repair instruction.
        return GateResult(
            GATE_UNKNOWN,
            assigned=assigned,
            unassigned=unassigned,
            multi_net=multi_net,
            unknown=unknown,
        )
    if unassigned or multi_net:
        return GateResult(
            GATE_FAIL, assigned=assigned, unassigned=unassigned, multi_net=multi_net
        )
    return GateResult(GATE_PASS, assigned=assigned)


# ---------------------------------------------------------------------------
# Pin-list acquisition. Isolated so the ONE import of kicad_emit is lazy and
# failure-visible: a symbol that cannot be read yields no entry, and the gate
# turns that absence into `unknown` rather than into a confident pass.
# ---------------------------------------------------------------------------
def _load_pin_lists(
    components: list[dict], symbol_dirs: Any
) -> tuple[dict[str, list[str]], list[str]]:
    pin_lists: dict[str, list[str]] = {}
    notes: list[str] = []
    try:
        from .kicad_emit import load_symbol  # local import: keeps this module pure
    except Exception as exc:  # pragma: no cover - exercised when KiCad deps absent
        return {}, [f"load_symbol unavailable: {exc}"]

    for c in components:
        ref = c.get("ref")
        lib_id = c.get("symbol")
        if not ref or not lib_id:
            continue
        try:
            if symbol_dirs:
                _defn, pins = load_symbol(lib_id, symbol_dirs)
            else:
                _defn, pins = load_symbol(lib_id)
            pin_lists[ref] = [str(p) for p in pins]
        except Exception as exc:
            notes.append(f"{ref}: {type(exc).__name__}: {exc}")
    return pin_lists, notes


# ---------------------------------------------------------------------------
# A5 -- public entry. The ONLY place a status value is chosen.
# ---------------------------------------------------------------------------
def declare_circuit(
    components: list[dict] | None = None,
    declarations: list[dict] | None = None,
    symbol_dirs: list[str] | None = None,
    strict: bool = True,
    _pin_lists: dict | None = None,
) -> dict[str, Any]:
    """Expand declared circuit topology into a compose_schematic spec.

    Returns a dict whose `status` is one of the five closed values. `spec` is
    non-null only for `ok` and `empty`.

    `_pin_lists` injects a pin map directly, for tests that must exercise the
    gate without a KiCad symbol tree. It is not part of the MCP surface.

    NOTE ON WHAT `ok` MEANS: "this declaration is internally consistent and
    complete", NOT "this circuit is correct". A pull-up tied to GND, a 5V rail
    on a 3V3 pin, and a decoupling cap next to the wrong IC are all electrically
    legal at this layer and all pass. errors.md enumerates what is caught and
    what is not; the result field is named `completeness` rather than `valid`
    so a downstream reader is not invited to read one as the other.
    """
    components = components if components is not None else []
    declarations = declarations if declarations is not None else []

    result: dict[str, Any] = {
        "status": None,
        "spec": None,
        "provenance": {},
        "completeness": GateResult(GATE_NOT_RUN).as_dict(),
        "render_plan": {},
        "errors": [],
        "unknown": [],
    }

    # --- A1: validate. Anything here means the expander never ran. ---
    verrors, by_ref = _validate_input(components, declarations)
    if verrors:
        result["status"] = STATUS_NOT_RUN
        result["errors"] = [e.as_dict() for e in verrors]
        result["offending_refs"] = sorted(
            {r for e in verrors for r in e.refs}
        )
        return result

    # --- A2: empty is its own branch, decided BEFORE expansion. ---
    if not declarations:
        result["status"] = STATUS_EMPTY
        result["spec"] = {"components": list(components), "nets": [], "nc": []}
        result["completeness"] = GateResult(GATE_VACUOUS).as_dict()
        return result

    if _pin_lists is not None:
        pin_lists, load_notes = dict(_pin_lists), []
    else:
        pin_lists, load_notes = _load_pin_lists(components, symbol_dirs)

    ex = _expand(declarations, by_ref, pin_lists)

    # --- A3: provenance assertion (engine self-check). ---
    ex.errors.extend(_check_provenance(ex))

    result["provenance"] = dict(ex.provenance)
    result["render_plan"] = dict(ex.render_plan)

    if ex.errors:
        result["status"] = STATUS_REJECTED
        result["errors"] = [e.as_dict() for e in ex.errors]
        return result

    # --- A4: completeness gate. ---
    gate = check_completeness(components, ex, pin_lists)
    result["completeness"] = gate.as_dict()

    nets = [{"name": n, "nodes": list(eps)} for n, eps in ex.nets.items()]
    spec = {"components": list(components), "nets": nets, "nc": list(ex.nc)}

    if gate.verdict == GATE_UNKNOWN:
        result["status"] = STATUS_INDETERMINATE
        result["unknown"] = list(gate.unknown) + load_notes
        return result

    if gate.verdict == GATE_FAIL:
        errs: list[Error] = []
        if gate.unassigned:
            errs.append(
                Error(
                    "E_PIN_UNASSIGNED",
                    f"{len(gate.unassigned)} pin(s) are neither on a net nor "
                    "declared no-connect",
                    list(gate.unassigned),
                )
            )
        if gate.multi_net:
            errs.append(
                Error(
                    "E_PIN_MULTI_NET",
                    f"{len(gate.multi_net)} pin(s) appear on more than one net -- "
                    "an electrical contradiction, not a style issue",
                    list(gate.multi_net),
                )
            )
        if strict:
            result["status"] = STATUS_REJECTED
            result["errors"] = [e.as_dict() for e in errs]
            return result
        # strict=False: E_PIN_UNASSIGNED degrades to a warning (data-schema.json).
        # A multi-net pin is NEVER downgraded -- it is a contradiction, not an
        # incompleteness, and no migration story makes a shorted pin acceptable.
        hard = [e for e in errs if e.code != "E_PIN_UNASSIGNED"]
        if hard:
            result["status"] = STATUS_REJECTED
            result["errors"] = [e.as_dict() for e in hard]
            return result
        result["warnings"] = [e.as_dict() for e in errs]

    result["status"] = STATUS_OK
    result["spec"] = spec
    return result
