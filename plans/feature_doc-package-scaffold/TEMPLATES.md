# Where the runtime templates live (RB-2)

Runtime-depended template/rubric JSON was **moved out of this draft plan zone** into the
package, because runtime must not depend on a `plans/` path (it breaks on graduation/archive).

Canonical (runtime SSOT) location — edit these:

| File | Now lives at | Read by |
|---|---|---|
| `c00_prd.template.json` | `packages/workflow-core/bodesign_workflow_core/templates/` | `c00_prd_template.py` |
| `c00_prd.rubric.json` | `packages/workflow-core/bodesign_workflow_core/templates/` | `c00_prd_template.py` |
| `doc_architecture.template.json` | `packages/workflow-core/bodesign_workflow_core/templates/` | `agent_registry.py` (the C00–C06 registry SSOT) |
| `c01_id.template.json` | `packages/workflow-core/bodesign_workflow_core/templates/` | `c01_id_template.py` (loader + emitter binding) |
| `c01_id.rubric.json` | `packages/workflow-core/bodesign_workflow_core/templates/` | `c01_id_template.py` |

All runtime-depended templates now live in the package (RB-2 + RB-3 complete).

The plan narrative docs (`proposal.md`, `design.md`, `tasks.md`, `implementation-spec.md`,
`c00_c01_gap-audit.md`, `c00_downstream_contract.md`) stay here and reference the templates by name.
