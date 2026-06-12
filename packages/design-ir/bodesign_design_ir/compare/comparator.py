"""G7 reference comparator entry point (DD-10..DD-13).

`compare_designs(generated, reference)` returns a `CompareResult`:
  - three sub-scores: S_comp (Dice over component matching), S_attr (value/
    part attribute agreement on matched pairs), S_conn (pin-level connectivity
    agreement on matched pairs)
  - weighted total S = w_comp*S_comp + w_attr*S_attr + w_conn*S_conn
  - structured mismatch details expressed as CrossCheckDiffItem dicts
    (dimension ∈ component/pin/component_value, status matched/missing/extra)
    so the cross-check layer consumes ONE schema (DD-11), plus first_divergence
  - `to_validation_evidence()` wraps the result as a ValidationEvidence
    envelope (tool="crosscheck") for A3 spine backflow

Deterministic: stable ordering everywhere; identical inputs yield
byte-identical `to_dict()` output. No LLM involvement.
"""

from dataclasses import dataclass, field
from typing import Any

from bodesign_design_ir.contracts import BoardDesign

from .config import DEFAULT_SCORING_CONFIG, CompareError, ScoringConfig
from .matching import (
    ComponentMatch,
    _build_views,
    _match_components,
    _neighbor_profile,
    _validate_design,
)

_SEVERITY_RANK = {"critical": 0, "major": 1, "minor": 2, "info": 3}
_DIMENSION_ORDER = ("component", "component_value", "pin")


@dataclass(slots=True)
class CompareResult:
    label: str
    s_comp: float
    s_attr: float
    s_conn: float
    s_total: float
    matches: list[ComponentMatch] = field(default_factory=list)
    items: list[dict[str, Any]] = field(default_factory=list)  # CrossCheckDiffItem dicts
    first_divergence: int | None = None
    config: ScoringConfig = field(default_factory=lambda: DEFAULT_SCORING_CONFIG)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "scores": {
                "S_comp": self.s_comp, "S_attr": self.s_attr,
                "S_conn": self.s_conn, "S_total": self.s_total,
                "weights": {"comp": self.config.weight_comp,
                            "attr": self.config.weight_attr,
                            "conn": self.config.weight_conn},
            },
            "matches": [
                {"generated_refdes": m.generated_refdes, "reference_refdes": m.reference_refdes,
                 "similarity": m.similarity, "part_match": m.part_match,
                 "value_match": m.value_match}
                for m in self.matches
            ],
            "items": list(self.items),
            "first_divergence": self.first_divergence,
        }

    def to_validation_evidence(self) -> dict[str, Any]:
        """DD-11: wrap as a ValidationEvidence envelope (tool='crosscheck')."""
        from bodesign_workflow_core.validation_evidence import (
            ValidationEvidence,
            ValidationFinding,
        )
        findings = []
        for item in self.items:
            if item["status"] == "matched":
                continue
            findings.append(ValidationFinding(
                id=f"cmp-{item['dimension']}-{item['key']}",
                severity=item["severity"],
                message=f"{item['dimension']} {item['key']}: {item['status']} vs reference",
                anchor={"kind": "component" if item["dimension"] != "pin" else "net",
                        "ref": item["key"]},
            ))
        severity = "info"
        if findings:
            severity = min((f.severity for f in findings), key=lambda s: _SEVERITY_RANK[s])
        return ValidationEvidence(
            tool="crosscheck",
            inputs={"comparator": "design_ir.compare", "label": self.label,
                    "weights": {"comp": self.config.weight_comp,
                                "attr": self.config.weight_attr,
                                "conn": self.config.weight_conn}},
            findings=findings,
            severity=severity,
            anchors=[f.anchor for f in findings if f.anchor],
            raw_result=self.to_dict(),
        ).to_dict()


def _dice(matched: int, gen_total: int, ref_total: int) -> float:
    denom = gen_total + ref_total
    return (2.0 * matched / denom) if denom else 1.0


def compare_designs(
    generated: BoardDesign,
    reference: BoardDesign,
    label: str = "reference-compare",
    config: ScoringConfig | None = None,
) -> CompareResult:
    cfg = config or DEFAULT_SCORING_CONFIG
    _validate_design(generated, "candidate")
    _validate_design(reference, "reference")

    gen_views = _build_views(generated, cfg)
    ref_views = _build_views(reference, cfg)
    gen_by_net: dict[str, set[str]] = {}
    for net in generated.nets:
        for pad in net.connected_pads:
            gen_by_net.setdefault(net.name, set()).add(pad.partition("-")[0])
    ref_by_net: dict[str, set[str]] = {}
    for net in reference.nets:
        for pad in net.connected_pads:
            ref_by_net.setdefault(net.name, set()).add(pad.partition("-")[0])
    gen_profiles = {r: _neighbor_profile(v, gen_by_net, gen_views) for r, v in gen_views.items()}
    ref_profiles = {r: _neighbor_profile(v, ref_by_net, ref_views) for r, v in ref_views.items()}

    matches, missing_required, missing_optional, extra_generated = _match_components(
        gen_views, ref_views, gen_profiles, ref_profiles, cfg)

    # ── S_comp: Dice over required component matching (optional absence free) ──
    ref_required_total = sum(1 for v in ref_views.values() if not v.comp.optional)
    required_matched = sum(
        1 for m in matches if not ref_views[m.reference_refdes].comp.optional)
    # extra generated parts dilute the Dice denominator (novel content to verify)
    s_comp = _dice(required_matched, required_matched + len(extra_generated), ref_required_total)

    # ── S_attr: part/value agreement across matched pairs ──
    if matches:
        attr_scores = []
        for m in matches:
            score = 1.0 if m.part_match else 0.0
            if m.value_match is not None:
                score = 0.5 * score + 0.5 * (1.0 if m.value_match else 0.0)
            attr_scores.append(score)
        s_attr = sum(attr_scores) / len(attr_scores)
    else:
        s_attr = 0.0

    # ── S_conn: pin-level connectivity agreement on matched pairs ──
    items: list[dict[str, Any]] = []
    conn_matched = conn_gen_total = conn_ref_total = 0
    ref_to_gen = {m.reference_refdes: m.generated_refdes for m in matches}
    for m in matches:
        gv, rv = gen_views[m.generated_refdes], ref_views[m.reference_refdes]
        gen_pins, ref_pins = set(gv.pin_nets), set(rv.pin_nets)
        conn_gen_total += len(gen_pins)
        conn_ref_total += len(ref_pins)
        for pin in sorted(gen_pins | ref_pins):
            key = f"{m.reference_refdes}.{pin}"
            if pin in gen_pins and pin in ref_pins:
                # the pin exists on both sides; do its net neighborhoods agree?
                gen_neighbors = {
                    frozenset(gen_by_net.get(n, set()) - {m.generated_refdes})
                    for n in gv.pin_nets[pin]}
                ref_neighbors_raw = {
                    frozenset(ref_by_net.get(n, set()) - {m.reference_refdes})
                    for n in rv.pin_nets[pin]}
                # translate reference neighbor refdes via the match map
                ref_neighbors = {
                    frozenset(ref_to_gen.get(r, f"!{r}") for r in group)
                    for group in ref_neighbors_raw}
                if gen_neighbors == ref_neighbors:
                    conn_matched += 1
                    items.append({"dimension": "pin", "key": key, "status": "matched",
                                  "severity": "info", "evidence_refs": []})
                else:
                    items.append({"dimension": "pin", "key": key, "status": "missing",
                                  "severity": "major", "evidence_refs": []})
            elif pin in ref_pins:
                items.append({"dimension": "pin", "key": key, "status": "missing",
                              "severity": "major", "evidence_refs": []})
            else:
                items.append({"dimension": "pin", "key": key, "status": "extra",
                              "severity": "minor", "evidence_refs": []})
    s_conn = _dice(conn_matched, conn_gen_total, conn_ref_total)

    # ── component-level mismatch items ──
    for m in matches:
        items.append({"dimension": "component", "key": m.reference_refdes,
                      "status": "matched", "severity": "info", "evidence_refs": []})
        if m.value_match is False:
            gv = gen_views[m.generated_refdes].comp.value or ""
            rv = ref_views[m.reference_refdes].comp.value or ""
            items.append({"dimension": "component_value", "key": m.reference_refdes,
                          "status": "missing", "severity": "major",
                          "evidence_refs": [{"kind": "component", "ref": m.reference_refdes,
                                             "detail": f"candidate={gv!r} reference={rv!r}"}]})
    for refdes in missing_required:
        items.append({"dimension": "component", "key": refdes, "status": "missing",
                      "severity": "critical", "evidence_refs": []})
    for refdes in missing_optional:
        # optional absence: reported for visibility, info severity, no score impact
        items.append({"dimension": "component", "key": refdes, "status": "missing",
                      "severity": "info", "evidence_refs": [
                          {"kind": "component", "ref": refdes, "detail": "optional in reference"}]})
    for refdes in extra_generated:
        items.append({"dimension": "component", "key": refdes, "status": "extra",
                      "severity": "minor", "evidence_refs": []})

    # deterministic ordering: severity → dimension → key
    items.sort(key=lambda i: (_SEVERITY_RANK[i["severity"]],
                              _DIMENSION_ORDER.index(i["dimension"]), i["key"]))
    first_divergence = next(
        (idx for idx, i in enumerate(items)
         if i["status"] != "matched" and i["severity"] != "info"),
        None)

    s_total = (cfg.weight_comp * s_comp + cfg.weight_attr * s_attr + cfg.weight_conn * s_conn)
    return CompareResult(
        label=label,
        s_comp=round(s_comp, 6), s_attr=round(s_attr, 6),
        s_conn=round(s_conn, 6), s_total=round(s_total, 6),
        matches=matches, items=items, first_divergence=first_divergence,
        config=cfg,
    )
