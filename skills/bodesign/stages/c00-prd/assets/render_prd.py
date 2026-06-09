#!/usr/bin/env python3
"""Render C00 PRD markdown + handoff report from a bodesign C00 answer_state.json.

Honesty model: every field renders with its state/owner/source/handoff_targets so open items
stay visible. No hidden defaults are applied; missing/blocked/external-needed/accepted-risk fields
are shown as-is. human_approved is read, never set here.

Usage:
    python3 render_prd.py <answer_state.json> [--outdir DIR]

Emits (into --outdir, default = dir of the input):
    Project_Requirements.md
    RF_Requirements.md          (only if include_rf)
    C00_Handoff_Report.md
"""
import argparse
import json
import os
import sys

OPEN_STATES = {"missing", "blocked", "external-needed"}        # count as blocking
PARTIAL_STATES = {"drafted"}                                    # authored, unconfirmed
DONE_STATES = {"answered", "accepted-risk"}                     # answered, or knowingly accepted

# Which document group each section belongs to (for document gates).
DOC_GROUPS = {
    "business_contract": ["s01_business_strategy", "s02_project_overall", "s03_project_objectives"],
    "engineering_kickoff": ["s04_system_architecture", "s05_id_me_requirements",
                            "s06_electrical_requirements", "s07_software_requirements",
                            "s09_assumptions_constraints"],
    "execution_control": ["s08_roles_responsibility", "s10_project_management",
                          "s11_schedule", "s12_team_roster"],
    "rf_appendix": ["rf01_product_brief", "rf02_project_objectives", "rf03_rf_specifications"],
}
# Which sections gate each downstream handoff (derived from field handoff_targets, mirrored here
# at section granularity for the report).
HANDOFF_GATES = {
    "C01/C02": ["s05_id_me_requirements", "s09_assumptions_constraints", "s10_project_management"],
    "C03": ["s04_system_architecture", "s06_electrical_requirements", "s09_assumptions_constraints"],
    "C05": ["s07_software_requirements", "s08_roles_responsibility"],
    "C06": ["s01_business_strategy", "s03_project_objectives", "s09_assumptions_constraints",
            "s10_project_management"],
    "C07": ["s03_project_objectives", "rf03_rf_specifications"],
}


def iter_sections(state):
    for doc_name, doc in state["documents"].items():
        for sec in doc.get("sections", []):
            yield doc_name, sec


def section_blocking(sec):
    """Return list of field keys in this section that are still blocking."""
    out = []
    for k, f in sec.get("fields", {}).items():
        if (f.get("state") or "missing") in OPEN_STATES:
            out.append(k)
    return out


def count_fields(state):
    total = complete = partial = blocking = 0
    for _, sec in iter_sections(state):
        for f in sec.get("fields", {}).values():
            total += 1
            st = f.get("state") or "missing"
            if st in DONE_STATES:
                complete += 1
            elif st in PARTIAL_STATES:
                partial += 1
            else:
                blocking += 1
    return total, complete, partial, blocking


def render_field(key, f):
    val = f.get("value")
    val = "(unset)" if val in (None, "") else val
    lines = [f"- `{key}`: {val}"]
    lines.append(f"  - state: `{f.get('state') or 'missing'}`")
    if f.get("reason"):
        lines.append(f"  - reason: {f['reason']}")
    lines.append(f"  - owner: `{f.get('owner') or 'unassigned'}`")
    lines.append(f"  - source: `{f.get('source') or 'none'}`")
    ht = f.get("handoff_targets") or []
    if ht:
        lines.append(f"  - handoff_targets: {', '.join(ht)}")
    return "\n".join(lines)


def render_document(state, doc_name, readiness, approved):
    doc = state["documents"][doc_name]
    title = "Project Requirements" if doc_name.startswith("Project") else "RF Requirements"
    out = [f"# {title}", "",
           "Status: generated-from-answer-state",
           f"Project: {state.get('project_name')}",
           f"C00 readiness: {readiness}",
           f"Human approved: {str(approved).lower()}", "",
           "This Markdown is generated from `C00-PRD/answer_state.json`. Missing, drafted, "
           "external-needed, blocked, and accepted-risk fields remain visible; no hidden "
           "defaults are applied.", ""]
    for sec in doc.get("sections", []):
        out.append(f"## {sec.get('title', sec['id'])}")
        out.append("")
        out.append(f"Section ID: `{sec['id']}`")
        out.append(f"Section state: `{sec.get('state') or 'missing'}`")
        out.append("")
        out.append("### Fields")
        for k, f in sec.get("fields", {}).items():
            out.append(render_field(k, f))
        ht = sec.get("handoff_targets") or []
        if ht:
            out.append("")
            out.append("### Handoff Targets")
            out.append("- " + ", ".join(ht))
        out.append("")
    return "\n".join(out)


def render_handoff(state, sec_by_id, readiness, blocked, total, complete, partial, blocking,
                   include_rf):
    next_q = None
    for sid in ("s08_roles_responsibility", "s09_assumptions_constraints",
                "s10_project_management", "s11_schedule", "s12_team_roster"):
        if sid in sec_by_id and section_blocking(sec_by_id[sid]):
            next_q = {
                "s08_roles_responsibility": "Who approves PRD, circuit, layout, FW spec, "
                                            "verification plan, and factory release?",
            }.get(sid, f"Resolve open fields in {sid}.")
            break

    out = ["# C00 Handoff Report", "",
           f"Readiness: {readiness}{' (blocked)' if blocked else ''}",
           f"Next question: {next_q or 'none — all gating sections answered'}",
           f"Human approved: {str(state.get('human_approved', False)).lower()}", "",
           "## Field Counts", "",
           f"- `total`: {total}",
           f"- `complete`: {complete}",
           f"- `partial`: {partial}",
           f"- `blocking`: {blocking}", "",
           "## Document Gates", ""]
    for group, sids in DOC_GROUPS.items():
        if group == "rf_appendix" and not include_rf:
            continue
        blockers = [s for s in sids if s in sec_by_id and section_blocking(sec_by_id[s])]
        status = "ready" if not blockers else "blocked"
        out.append(f"- `{group}`: {status}; blockers: {', '.join(blockers) if blockers else 'none'}")
    out += ["", "## Downstream Handoff Gates", ""]
    for stage, sids in HANDOFF_GATES.items():
        if stage == "C07" and not include_rf:
            sids = [s for s in sids if not s.startswith("rf")]
        blockers = [s for s in sids if s in sec_by_id and section_blocking(sec_by_id[s])]
        status = "ready" if not blockers else "blocked"
        out.append(f"- `{stage}`: {status}; blockers: {', '.join(blockers) if blockers else 'none'}")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("answer_state")
    ap.add_argument("--outdir")
    args = ap.parse_args()

    with open(args.answer_state, encoding="utf-8") as fh:
        state = json.load(fh)
    outdir = args.outdir or os.path.dirname(os.path.abspath(args.answer_state))
    include_rf = bool(state.get("include_rf"))

    total, complete, partial, blocking = count_fields(state)
    pct = round(100 * complete / total) if total else 0
    blocked = blocking > 0 or not state.get("human_approved", False)
    readiness = f"{pct}%"

    sec_by_id = {sec["id"]: sec for _, sec in iter_sections(state)}
    approved = state.get("human_approved", False)

    written = []
    p = os.path.join(outdir, "Project_Requirements.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(render_document(state, "Project_Requirements.md", readiness, approved))
    written.append(p)

    if include_rf and "RF_Requirements.md" in state["documents"]:
        p = os.path.join(outdir, "RF_Requirements.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(render_document(state, "RF_Requirements.md", readiness, approved))
        written.append(p)

    p = os.path.join(outdir, "C00_Handoff_Report.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(render_handoff(state, sec_by_id, readiness, blocked,
                                total, complete, partial, blocking, include_rf))
    written.append(p)

    for w in written:
        print(f"wrote {w}")
    print(f"readiness {readiness} | complete {complete}/{total} | "
          f"blocking {blocking} | approved {approved}")


if __name__ == "__main__":
    sys.exit(main())
