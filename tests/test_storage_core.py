import unittest

from bodesign_storage_core import build_kicad_happy_cache_mapping, classify_project_folder_taxonomy


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


if __name__ == "__main__":
    unittest.main()
