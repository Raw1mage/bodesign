from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bodesign_doc_core import document_to_source_chunks


class DocCoreTests(unittest.TestCase):
    def test_text_document_becomes_provenance_chunks(self):
        with TemporaryDirectory() as temp_dir:
            document = Path(temp_dir) / "datasheet.txt"
            document.write_text("Page 1\nPackage: QFN-48\nPin 1 VDD\n" * 80, encoding="utf-8")

            chunks = document_to_source_chunks("demo", str(document), chunk_chars=500)

        self.assertGreater(len(chunks), 1)
        self.assertEqual("text", chunks[0].kind)
        self.assertIn("datasheet", chunks[0].source_id)
        self.assertIsNotNone(chunks[0].evidence)
        self.assertIn("#chunk-1", chunks[0].evidence.target_path)


if __name__ == "__main__":
    unittest.main()
