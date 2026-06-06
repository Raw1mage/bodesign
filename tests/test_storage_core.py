import unittest

from bodesign_storage_core import build_cache_conflict_status, build_folder_open_request, build_kicad_analysis_evidence_manifest, build_kicad_analysis_status, build_kicad_happy_cache_mapping, build_project_registry, build_project_tree_browse_contract, build_save_back_proposals, build_source_chunk_materialization, classify_project_folder_taxonomy


class StorageCoreTests(unittest.TestCase):
    def test_classifies_kicad_eda_taxonomy_without_filesystem_access(self):
        taxonomy = classify_project_folder_taxonomy(
            [
                "docs/nrf52840.pdf",
                "inputs/reference/openmv.zip",
                "eda/openmv/openmv.kicad_pro",
                "eda/openmv/openmv.kicad_sch",
                "eda/openmv/openmv.kicad_pcb",
                "libraries/symbols/openmv.kicad_sym",
                "outputs/gerbers/openmv-F_Cu.gbr",
                "outputs/drill/openmv.drl",
                "outputs/bom/openmv.bom.csv",
                "outputs/3d/openmv.step",
                "reports/design-review.md",
                ".bodesign/ir/snapshot.json",
            ]
        )

        self.assertEqual(["eda/openmv/openmv.kicad_pro"], taxonomy.kicad_sources["project"])
        self.assertEqual(["eda/openmv/openmv.kicad_sch"], taxonomy.kicad_sources["schematic"])
        self.assertEqual(["eda/openmv/openmv.kicad_pcb"], taxonomy.kicad_sources["pcb"])
        self.assertIn("docs/nrf52840.pdf", taxonomy.roles["docs"])
        self.assertIn("libraries/symbols/openmv.kicad_sym", taxonomy.roles["libraries"])
        self.assertIn("reports/design-review.md", taxonomy.roles["reports"])
        self.assertIn(".bodesign/ir/snapshot.json", taxonomy.hidden_paths)
        self.assertFalse(any(path.startswith(".bodesign/") for paths in taxonomy.roles.values() for path in paths))
        self.assertEqual({"gerber", "drill", "bom", "step-3d"}, {artifact.artifact_type for artifact in taxonomy.output_artifacts})

    def test_builds_hidden_kicad_happy_cache_mapping_by_default(self):
        mapping = build_kicad_happy_cache_mapping()

        self.assertEqual(".kicad-happy.json", mapping.config_path)
        self.assertEqual(".bodesign/analysis/kicad-happy", mapping.analysis_root)
        self.assertEqual("hidden-mcp-analysis-cache", mapping.mode)
        self.assertFalse(mapping.track_in_git)
        self.assertIn("disposable", mapping.cache_policy)
        self.assertTrue(all(artifact.path.startswith(".bodesign/analysis/kicad-happy/") for artifact in mapping.artifact_paths))
        self.assertEqual(
            {"manifest", "analyzer-json", "trust-summary", "diffs", "renders", "report-figures", "drc", "erc", "dfm", "emc", "thermal"},
            {artifact.category for artifact in mapping.artifact_paths},
        )

    def test_supports_visible_analysis_opt_in_mapping(self):
        mapping = build_kicad_happy_cache_mapping(visible_analysis_opt_in=True)

        self.assertEqual("analysis", mapping.analysis_root)
        self.assertEqual("visible-compatibility-analysis", mapping.mode)
        self.assertFalse(mapping.track_in_git)
        self.assertTrue(all(artifact.path.startswith("analysis/") for artifact in mapping.artifact_paths))
        self.assertIn("opt-in", " ".join(mapping.warnings))

    def test_builds_read_only_project_tree_from_manifest_paths(self):
        tree = build_project_tree_browse_contract(
            "openmv",
            [
                "docs/nrf52840.pdf",
                "eda/openmv/openmv.kicad_pro",
                "eda/openmv/openmv.kicad_sch",
                "libraries/symbols/openmv.kicad_sym",
                "outputs/gerbers/openmv-F_Cu.gbr",
                "reports/design-review.md",
                ".bodesign/analysis/kicad-happy/manifest.json",
            ],
        )

        self.assertEqual("client", tree.durable_owner)
        self.assertEqual("read-only-fixture-backed", tree.access_mode)
        self.assertEqual({"docs", "inputs", "eda", "libraries", "outputs", "reports"}, {node.role for node in tree.folder_nodes})
        eda_node = next(node for node in tree.folder_nodes if node.role == "eda")
        self.assertEqual("human-facing-folder", eda_node.kind)
        self.assertEqual("human-facing", eda_node.visibility)
        self.assertIn("eda/openmv/openmv.kicad_pro", eda_node.sample_paths)
        self.assertIsNotNone(tree.hidden_workspace)
        self.assertEqual(".bodesign", tree.hidden_workspace.path)
        self.assertEqual("hidden-system-summary", tree.hidden_workspace.visibility)
        self.assertIn("analysis", tree.hidden_workspace.categories)
        self.assertTrue(any("Save-back" in blocker for blocker in tree.blockers))

    def test_builds_client_owned_project_registry_without_filesystem_access(self):
        registry = build_project_registry(["demo-board"], {"demo-board": "Demo reference board"})

        self.assertEqual("project-registry-fixture-ready", registry.status)
        self.assertEqual("client", registry.durable_owner)
        self.assertEqual("read-only-fixture-backed", registry.access_mode)
        self.assertEqual(["demo-board"], [record.project_id for record in registry.records])
        record = next(r for r in registry.records if r.project_id == "demo-board")
        self.assertEqual("Demo reference board", record.display_name)
        self.assertEqual("fixture-not-granted", record.folder_handle_status)
        self.assertEqual("client-owned-local-folder", record.storage_model)
        self.assertEqual("/bodesign/projects/demo-board", record.links.dashboard)
        self.assertEqual("/bodesign/api/projects/demo-board/storage-share", record.links.storage_share)
        self.assertEqual("/bodesign/api/projects/demo-board/project-tree", record.links.project_tree)
        self.assertEqual("/bodesign/api/projects/demo-board/kicad-foundation", record.links.kicad_foundation)
        self.assertEqual("/bodesign/api/projects/demo-board/kicad-native-extension", record.links.kicad_native_extension)
        self.assertEqual("/bodesign/api/projects/demo-board/kicad-plugin-handshake", record.links.kicad_plugin_handshake)
        self.assertTrue(any("not granted" in blocker for blocker in record.blockers))
        self.assertTrue(any("not a server-owned durable file store" in warning for warning in registry.warnings))

    def test_builds_folder_open_request_without_filesystem_access(self):
        request = build_folder_open_request("openmv")

        self.assertEqual("folder-open-openmv", request.request_id)
        self.assertEqual("openmv", request.project_id)
        self.assertEqual("client", request.durable_owner)
        self.assertEqual("no-server-filesystem-access", request.access_mode)
        self.assertEqual("needs-client-grant/not-approved", request.approval_state)
        self.assertIn("read-project-tree", request.requested_permissions)
        self.assertIn("represent-client-approved-save-back", request.requested_permissions)
        self.assertEqual(["project-read"], [scope.scope_id for scope in request.read_scopes])
        self.assertEqual(["mcp-save-back"], [scope.scope_id for scope in request.write_scopes])
        self.assertIn("refresh-project-registry", request.post_grant_actions)
        self.assertIn("refresh-kicad-foundation", request.post_grant_actions)
        self.assertTrue(any("must not scan arbitrary server filesystem" in blocker for blocker in request.blockers))
        self.assertTrue(any("not a server filesystem operation" in warning for warning in request.warnings))

    def test_builds_client_applied_save_back_proposal_without_mutation(self):
        proposals = build_save_back_proposals("openmv")
        proposal = proposals[0]

        self.assertEqual("save-back-openmv-analysis-report", proposal.proposal_id)
        self.assertEqual("openmv", proposal.project_id)
        self.assertEqual("mcp-save-back", proposal.target_scope)
        self.assertEqual("reports/bodesign-analysis-summary.md", proposal.target_path)
        self.assertEqual("create-or-update-report", proposal.operation_intent)
        self.assertEqual("client-applied/native-kicad-plugin", proposal.application_mode)
        self.assertEqual("not-approved", proposal.approval_state)
        self.assertTrue(proposal.direct_mcp_mutation_blocked)
        self.assertIn("/bodesign/api/projects/openmv/kicad-foundation", proposal.evidence_refs)
        self.assertIn("client-checks-conflicts", proposal.next_actions)
        self.assertTrue(any("does not write client files directly" in warning for warning in proposal.warnings))

    def test_builds_cache_conflict_status_without_resolution(self):
        status = build_cache_conflict_status(
            "openmv",
            [
                "eda/openmv/openmv.kicad_pro",
                ".bodesign/analysis/kicad-happy/manifest.json",
                ".bodesign/render/board.png",
            ],
        )

        self.assertEqual("disposable-mcp-cache", status.cache_authority)
        self.assertEqual("client-owned-folder", status.source_authority)
        self.assertEqual("fixture-stale/needs-client-refresh", status.freshness_state)
        self.assertEqual("explicit-user-resolution", status.conflict_policy)
        self.assertTrue(status.silent_resolution_blocked)
        self.assertIn("refresh-from-client-folder", status.required_actions)
        self.assertIn("invalidate-disposable-mcp-cache", status.required_actions)
        self.assertIn("review-save-back-proposals", status.required_actions)
        self.assertTrue(any(anchor.startswith("client-folder-handle:openmv") for anchor in status.source_revision_anchors))
        self.assertEqual(".bodesign", status.cache_entries[0].path)
        self.assertIn("analysis", status.cache_entries[0].categories)
        self.assertIn("render", status.cache_entries[0].categories)
        self.assertTrue(any("silent resolution is blocked" in blocker for blocker in status.blockers))

    def test_builds_source_chunk_materialization_without_copying_files(self):
        materialization = build_source_chunk_materialization("openmv")
        first_chunk = materialization.chunk_items[0]

        self.assertEqual("openmv", materialization.project_id)
        self.assertEqual("client-owned-folder", materialization.source_authority)
        self.assertEqual(".bodesign/sources", materialization.target_workspace)
        self.assertEqual("client-applied/docxmcp-orchestration", materialization.materialization_mode)
        self.assertEqual("not-approved/needs-client-grant", materialization.approval_state)
        self.assertTrue(materialization.direct_server_copy_blocked)
        self.assertEqual("docs/reference-datasheet.pdf", first_chunk.source_path)
        self.assertEqual(".bodesign/sources/docs/reference-datasheet/chunks.jsonl", first_chunk.target_path)
        self.assertEqual("pdf-source-chunks", first_chunk.content_kind)
        self.assertEqual("represented-not-materialized", first_chunk.cache_state)
        self.assertIn("/bodesign/api/projects/openmv/project-tree", first_chunk.evidence_refs)
        self.assertIn("run-docxmcp-client-side-decomposition", materialization.next_actions)
        self.assertTrue(any("does not read or copy files" in warning for warning in materialization.warnings))

    def test_builds_kicad_analysis_status_without_native_execution(self):
        status = build_kicad_analysis_status("openmv")

        self.assertEqual("kicad-analysis-openmv", status.request_id)
        self.assertEqual("native-kicad-plugin/client-orchestrated-kicad-happy", status.orchestration_mode)
        self.assertEqual("not-approved/needs-client-grant", status.approval_state)
        self.assertEqual("represented-not-run", status.run_state)
        self.assertEqual(".bodesign/analysis/kicad-happy", status.analysis_root)
        self.assertTrue(status.direct_server_execution_blocked)
        self.assertIn("drc", status.requested_checks)
        self.assertIn("erc", status.requested_checks)
        self.assertIn("emc", status.requested_checks)
        self.assertIn("/bodesign/api/projects/openmv/kicad-plugin-handshake", status.evidence_refs)
        self.assertTrue(all(output.target_path.startswith(".bodesign/analysis/kicad-happy/") for output in status.expected_outputs))
        self.assertEqual("represented-not-run", status.expected_outputs[0].cache_state)
        self.assertIn("run-analysis-through-kicad-plugin-or-client", status.next_actions)
        self.assertTrue(any("must not run KiCad" in blocker for blocker in status.blockers))

    def test_builds_kicad_analysis_evidence_manifest_without_browsing_files(self):
        evidence = build_kicad_analysis_evidence_manifest("openmv")
        categories = {artifact.category for artifact in evidence.artifacts}

        self.assertEqual("kicad-analysis-evidence-openmv", evidence.manifest_id)
        self.assertEqual(".bodesign/analysis/kicad-happy", evidence.analysis_root)
        self.assertEqual("client-owned-kicad-project", evidence.source_authority)
        self.assertEqual("disposable-mcp-evidence-cache", evidence.cache_authority)
        self.assertEqual("fixture-stale/needs-client-refresh", evidence.freshness_state)
        self.assertEqual("manifest-index-only/no-raw-filesystem-browse", evidence.access_mode)
        self.assertTrue(evidence.direct_filesystem_browse_blocked)
        self.assertIn("manifest", categories)
        self.assertIn("trust-summary", categories)
        self.assertIn("drc", categories)
        self.assertIn("erc", categories)
        self.assertTrue(all(artifact.path.startswith(".bodesign/analysis/kicad-happy/") for artifact in evidence.artifacts))
        self.assertTrue(all(artifact.cache_state == "represented-not-materialized" for artifact in evidence.artifacts))
        self.assertIn("refresh-analysis-evidence-manifest", evidence.next_actions)
        self.assertTrue(any("must not browse raw hidden folders" in blocker for blocker in evidence.blockers))


if __name__ == "__main__":
    unittest.main()
