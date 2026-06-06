import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from bodesign_component_kb import build_component_knowledge_queue, ingest_datasheet_knowledge, reuse_component_knowledge


class ComponentKnowledgeTests(unittest.TestCase):
    def test_datasheet_ingestion_creates_reusable_component_key(self):
        result = ingest_datasheet_knowledge(
            "rockbox",
            "MDBT53-P1M",
            ["datasheets/MDBT53-P1M.pdf"],
            "module",
        )

        self.assertEqual(result.reusable_key, "component:mdbt53-p1m")
        self.assertEqual(result.component.part_number, "MDBT53-P1M")
        self.assertEqual(result.component.package, "module")
        self.assertEqual(result.component.source_evidence[0].target_path, "component/MDBT53-P1M")
        self.assertIn("Pinout extraction is pending.", result.component.knowledge_gaps)

    def test_component_knowledge_can_be_reused(self):
        ingestion = ingest_datasheet_knowledge("rockbox", "W25Q128JVSIQ", ["W25Q128JVSIQ.pdf"])
        reused = reuse_component_knowledge("new-board", "W25Q128JVSIQ", ingestion.component)

        self.assertEqual(reused.project_id, "new-board")
        self.assertEqual(reused.status, "placeholder-reused")
        self.assertEqual(reused.component.part_number, "W25Q128JVSIQ")

    def test_user_provided_text_datasheet_extracts_package_hint(self):
        with TemporaryDirectory() as temp_dir:
            datasheet = Path(temp_dir) / "part.txt"
            datasheet.write_text("Part XYZ123\nPackage: QFN-48\nPin 1 is VDD\n", encoding="utf-8")

            result = ingest_datasheet_knowledge("demo", "XYZ123", [str(datasheet)])

        self.assertGreater(result.extracted_text_chars, 20)
        self.assertEqual("QFN-48", result.extracted_fields["package"])
        self.assertEqual("QFN-48", result.component.package)
        self.assertNotIn("Pinout extraction is pending.", result.component.knowledge_gaps)

    def test_component_queue_groups_reusable_parts(self):
        queue = build_component_knowledge_queue(
            [
                {"refdes": "U401", "part_number": "MDBT53-P1M", "footprint": "module"},
                {"refdes": "U402", "part_number": "MDBT53-P1M", "footprint": "module"},
                {"refdes": "C1", "part_number": "0.1uF", "footprint": "0402"},
            ]
        )

        self.assertEqual("component:mdbt53-p1m", queue[0].reusable_key)
        self.assertEqual("high", queue[0].priority)
        self.assertEqual(2, queue[0].occurrence_count)
        self.assertEqual(["U401", "U402"], queue[0].refdes)


if __name__ == "__main__":
    unittest.main()
