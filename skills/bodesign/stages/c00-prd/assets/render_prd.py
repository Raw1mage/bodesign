#!/usr/bin/env python3
"""Render C00 PRD markdown + handoff report from a bodesign C00 answer_state.json.

Honesty model: every field renders with its state/owner/source/handoff_targets so open items
stay visible. No hidden defaults are applied; missing/blocked/external-needed/accepted-risk fields
are shown as-is. human_approved is read, never set here.

Readiness is NOT computed locally. All readiness numbers (pct/status/counts/gates/dod_ok/
fake-complete) come from the canonical `assess_c00_prd_readiness` in
`packages/workflow-core` — the same code path as `gate.py c00_readiness` — so this renderer
can never disagree with the gate (BR_20260703_render_prd_readiness_pct_diverges_from_canonical_assess).
If the workflow-core packages cannot be resolved, this script fails fast with an explicit
error; it never falls back to a simplified local computation.

Usage:
    python3 render_prd.py <answer_state.json> [--outdir DIR]

Expects the canonical layout `<project>/C00-PRD/answer_state.json`.

Emits (into --outdir, default = dir of the input):
    Project_Requirements.md
    RF_Requirements.md          (only if include_rf)
    C00_Handoff_Report.md
"""
import argparse
import json
import os
import sys


def _resolve_src():
    """Resolve the bodesign source root (a dir containing packages/workflow-core).

    Order: explicit $BODESIGN_SRC, else walk up from this script's location
    (the skill-shipped-in-tree case). Failure is explicit — no local fallback.
    """
    tried = []
    env = os.environ.get("BODESIGN_SRC")
    if env:
        cand = os.path.realpath(env)
        tried.append(cand)
        if os.path.isdir(os.path.join(cand, "packages", "workflow-core")):
            return cand
    else:
        cur = os.path.dirname(os.path.realpath(__file__))
        while True:
            tried.append(cur)
            if os.path.isdir(os.path.join(cur, "packages", "workflow-core")):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    sys.exit(
        "render_prd: could not find bodesign packages/workflow-core (canonical readiness "
        "source); tried: " + ", ".join(tried) + ". Set BODESIGN_SRC=/path/to/bodesign repo. "
        "No simplified local readiness fallback exists — run `gate.py c00_readiness` instead."
    )


def _prepend_packages(src_root):
    pkg_root = os.path.join(src_root, "packages")
    dirs = sorted(
        os.path.join(pkg_root, d)
        for d in os.listdir(pkg_root)
        if os.path.isdir(os.path.join(pkg_root, d))
    )
    for d in reversed(dirs):
        if d not in sys.path:
            sys.path.insert(0, d)


def _canonical_readiness(answer_state_path):
    """Run the canonical assess on the project folder that owns this answer_state."""
    c00_dir = os.path.dirname(answer_state_path)
    if os.path.basename(c00_dir) != "C00-PRD":
        sys.exit(
            f"render_prd: canonical readiness requires the <project>/C00-PRD/answer_state.json "
            f"layout; got {answer_state_path}"
        )
    _prepend_packages(_resolve_src())
    from bodesign_workflow_core import assess_c00_prd_readiness
    return assess_c00_prd_readiness(os.path.dirname(c00_dir))


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
           f"C00 readiness: {readiness.readiness_pct}% ({readiness.status})",
           f"DoD ok: {str(readiness.dod_ok).lower()}",
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


def render_handoff(state, readiness):
    counts = readiness.field_counts
    out = ["# C00 Handoff Report", "",
           f"Readiness: {readiness.readiness_pct}% ({readiness.status})",
           f"DoD ok: {str(readiness.dod_ok).lower()}",
           f"Next question: {readiness.next_question}",
           f"Human approved: {str(state.get('human_approved', False)).lower()}", ""]
    if readiness.fake_complete_fields:
        out += ["## Fake-Complete Fields (answered but placeholder value)", ""]
        out += [f"- `{k}`" for k in readiness.fake_complete_fields]
        out.append("")
    if readiness.warnings:
        out += ["## Warnings", ""]
        out += [f"- {w}" for w in readiness.warnings]
        out.append("")
    out += ["## Field Counts", ""]
    for key in ("total", "complete", "partial", "blocking"):
        if key in counts:
            out.append(f"- `{key}`: {counts[key]}")
    out += ["", "## Document Gates", ""]
    for gate in readiness.document_gates:
        blockers = gate.get("blocking_sections") or []
        out.append(f"- `{gate.get('gate', '')}`: {gate.get('status', '')}; "
                   f"blockers: {', '.join(blockers) if blockers else 'none'}")
    out += ["", "## Downstream Handoff Gates", ""]
    for gate in readiness.downstream_handoff_gates:
        blockers = gate.get("blocking_sections") or []
        out.append(f"- `{gate.get('target', '')}`: {gate.get('status', '')}; "
                   f"blockers: {', '.join(blockers) if blockers else 'none'}")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("answer_state")
    ap.add_argument("--outdir")
    args = ap.parse_args()

    answer_state_path = os.path.abspath(args.answer_state)
    with open(answer_state_path, encoding="utf-8") as fh:
        state = json.load(fh)
    outdir = args.outdir or os.path.dirname(answer_state_path)
    os.makedirs(outdir, exist_ok=True)
    include_rf = bool(state.get("include_rf"))

    readiness = _canonical_readiness(answer_state_path)
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
        fh.write(render_handoff(state, readiness))
    written.append(p)

    for w in written:
        print(f"wrote {w}")
    counts = readiness.field_counts
    print(f"readiness {readiness.readiness_pct}% ({readiness.status}) | "
          f"complete {counts.get('complete', 0)}/{counts.get('total', 0)} | "
          f"blocking {counts.get('blocking', 0)} | dod_ok {readiness.dod_ok} | "
          f"fake_complete {len(readiness.fake_complete_fields)} | approved {approved}")
    for w in readiness.warnings:
        print(f"warning: {w}")


if __name__ == "__main__":
    sys.exit(main())
