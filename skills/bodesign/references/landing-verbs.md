# Landing / compute routing contract (MCP server ≥ 0.2.0)

The tool surface is split into two planes. Route by plane, not by habit:

- **Landing plane — run locally via `gate.py`.** The deterministic, repo-local verbs (C00 + C01
  full families, C02 analysis-only, C03 emitters, C04–C06 scaffold/readiness, the orchestration
  spine, read/gate verbs — `ingest_project` / `package_readiness` / `datasheet_lookup` /
  `spec_check` / `rca_spec_audit` — and pure functions — `plan_design_intent` /
  `evidence_manifest` / `pin_allocation` / `reference_crosscheck` / `impedance_solve`) are **no
  longer MCP tools**. `gate.py --list` is the authoritative count and roster; this document
  deliberately does not restate a number, because a hand-copied count is exactly the kind of
  second declaration that drifts (BR_20260730). Run them agent-local against the client project
  folder:

  ```bash
  python3 <skill>/scripts/gate.py --list                 # authoritative verb list + summaries
  python3 <skill>/scripts/gate.py <verb> --repo <abs> [--json '{…}' | --arg k=v]
  ```

  Output is one JSON envelope on stdout (`{ok, verb, result}`; errors carry a typed code —
  `VERB_UNKNOWN` / `VERB_NOT_LANDING` / `LANDING_PYTHON_TOO_OLD` / `LANDING_PACKAGES_NOT_FOUND` —
  and exit≠0). When the skill is projected outside the bodesign checkout (XDG install), set
  `BODESIGN_SRC=<bodesign repo>` explicitly. Heavy names are hard-guarded: a blacklisted verb
  returns `VERB_NOT_LANDING` naming the container tool to use instead.

- **Compute plane — container MCP tools (`/tools` and `/health.tools` are authoritative).** Heavy toolchain
  work stays server-side: the C04 layout/routing family, `emit_symbol` / `compose_schematic` /
  `emit_layout` / `emit_fab`, `simulate` / `analyze_emc` / `analyze_thermal` /
  `spice_model_card`, the render family, C02 exports (STL/STEP/SKP) / render / `voice_to_design` /
  `project_svg`, DXF↔DWG, `export_bom` / `export_netlist`, `emit_doc` / `render_companion`,
  `c00_emit_prd_docx` (docxmcp assemble path), `c01_generate_concept_image`, the `vault_*` family,
  `stage_dir`, `mcp_call`, and the three cache-lifecycle tools.

- **`TOOL_LANDED` interception**: calling a landed name as an MCP tool returns a typed error
  `TOOL_LANDED` carrying the equivalent `landing_command`. Follow the command; do not retry the
  tool.

**Cache 三層心智模型** — where files live and how they move:

| Tier | What it is | How you touch it |
|---|---|---|
| **truth store** | client-owned project tree (durable inputs + deliverables) | landing verbs read/write it directly on the host; the container ingests it read-only |
| **working cache** | per-deliverable WebDAV workspace (`deliverable-cache` kind) on the server | `bodesign_cache_provision` → mount `/dav/{token}` (rclone/davfs2, per-owner Basic credential) or let heavy tools emit into it → `bodesign_cache_export` back to a host target → `bodesign_cache_close` (dirty-gate: un-exported changes 409 unless forced) |
| **vault** | cross-project component knowledge (server SQLite) | `vault_*` tools only |

**Stage → MCP tool family** (use when the MCP is present; otherwise fall back to the manual/KiCad
path each guide documents). **Routing note (≥ 0.2.0):** most lightweight entries below are now
*landing verbs* — same name, run via `gate.py`, and the MCP answers `TOOL_LANDED` if called as a
tool. This table remains a *family* router; `--list` / `/tools` decide which plane a name lives on:

| Stage | Tool family (landing verbs run via `gate.py`; compute tools carry the `bodesign_` prefix) |
|---|---|
| C00 | `c00_scaffold_prd` · `c00_emit_prd` · `c00_readiness` · `plan_design_intent` · `evidence_manifest` |
| C01 | `c01_emit_package` · `c01_emit_concept_prompts` · `c01_generate_concept_image` · `c01_readiness` |
| C02 | `c02_emit_enclosure_package` · `c02_generate_openscad` · `c02_export_{stl,step,skp}` · `c02_readiness` |
| C03 | `emit_symbol` · `compose_schematic` · `pin_allocation` · `export_bom` · `export_netlist` · `c03_export_mechanical_constraints` |
| C04 | `c04_emit_layout_package` (one-shot) **or** `impedance_solve` · `c04_face_placement` · `route_net2pcb`/`autoroute` · `c04_castellation` · `pour_planes` · `widen_bus_tracks` · `length_match_bus` · `via_in_pad` · `si_check` · `layout_drc_gate` · `emit_fab` · `c04_readiness` · `c04_dod_traceback` |
| C05 | `c05_scaffold_fw_spec` · `c05_readiness` |
| C06 | `c06_assemble_test_plan` · `reference_crosscheck` · `simulate` · `analyze_emc` · `analyze_thermal` · `c06_readiness` |
| C07 | `package_readiness` · `render_companion` · `emit_doc` |
| files/orchestration | `stage_dir` · `ingest_project` · `refs_ingest` · `datasheet_lookup`/`register`/`spec_check` · `dispatch_work_packet` · `mcp_call` |

**Refs-derived design verbs** (EPIC capability-inversion 切面 1/2/3/5; landing verbs via `gate.py`) —
these make the refs-first workflow executable end-to-end; the stage guides wire them into their SOPs:

| Verb | 切面 | One-line purpose |
|---|---|---|
| `refs_ingest` | 1 | Scan a stage's `01_refs/` SSOT into a ranked, read-only source manifest (authority order from the baseline file; rich media flagged unadjudicated; absent root → `root_visible:false`, loud — never a clean empty). Run as **step 0 of every stage** — the refs-gated emitters hard-fail `REFS_SSOT_MISSING` without the SSOT. |
| `c04_face_placement` | 2 | Deterministic placement bands binding each connector to its **frozen** C01 face/edge (DD-4: the face is not a C04 degree of freedom). Output feeds `placement_to_coords` → `route_net2pcb(placement=…)`. |
| `c04_castellation` | 3 | Stamp-module castellated edge pads as segfault-free S-expression injection (DD-5: refuses the known-crash pcbnew mutation paths); provenance-gated (天條 2). |
| `c04_dod_traceback` | 5 | Upgrade DoD from surface-existence to SSOT traceability: every delivered item must trace to an SSOT anchor (`untraceable` = 憑空發明) and every SSOT-required ref must be delivered (`unfulfilled` = 漏做). Either non-empty → **blocking**. |

**A2A governance verbs** (plan `workflow_guarded-hardware-governance`; landing verbs via `gate.py`) —
the stage guides (C03 §A2A, C04 §A2A) define when each fires:

| Verb | One-line purpose |
|---|---|
| `c03_substate_advance` | Advance C03 micro-state S0→S5 with role verification and a receipt listing unmeasured axes. |
| `c04_substate_advance` | Advance C04 micro-state P0→P7; P3/P6 need gate verdicts, P7 needs `human_approved`. |
| `circuit_block_apply` | Instantiate a verified circuit block with instance-scoped nets and layout constraints. |
| `layout_tidy` | Grid snap, passive distribution and silkscreen-pad clearance on a `.kicad_pcb`. |
| `blocker_record` | Write a structured `BLK-nnn.json` blocker routed to the owning activity. |

C00 answer loop: `c00_scaffold_prd` → `c00_update_answers` → `c00_readiness` → `c00_emit_prd`.

**Do not hardcode tool schemas from this table** — it is a router, not a contract. The server is
self-describing: open `/tools` and `/tools/{name}` (or the `/` landing page) on the running
service for the authoritative, current argument schemas. This keeps the skill light and prevents
it drifting out of sync as the MCP's tool surface evolves.
