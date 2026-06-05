import unittest

from bodesign_component_kb import ingest_datasheet_knowledge, reuse_component_knowledge


class ComponentKnowledgeTests(unittest.TestCase):
    def test_datasheet_ingestion_creates_reusable_component_key(self):
        result = ingest_datasheet_knowledge(
            "rockbox",
            "MDBT53-P1M",
            ["fixtures/private/rockbox/datasheets/MDBT53-P1M.pdf"],
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


if __name__ == "__main__":
    unittest.main()
