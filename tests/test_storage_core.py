import unittest

from bodesign_storage_core import build_kicad_happy_cache_mapping, build_project_tree_browse_contract, classify_project_folder_taxonomy


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


if __name__ == "__main__":
    unittest.main()
