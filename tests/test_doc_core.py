from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bodesign_doc_core import NormalizedPinRow, build_pin_table_gap_report, document_to_source_chunks, normalize_pin_table_text, validate_pin_table


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

    def test_stm32_pin_table_normalizer_preserves_vfbga223_rows(self):
        text = """
                B2         D3          D3         E3         F4         G4              BOOT0              I            -            -              -                     -
                R9         M6          P7         R8         W7         U6         PA13 (JTMS/SWDIO)    I/O             -              -   JTMS/SWDIO, HDP5                                     -
                A4         A4          A3         A3         B1         B4                NC               -            -            -                          -                                -
                C1         B1          B1         C1         E1         D1                              I/O                                                                          OSC32_IN
                                                                                          PB4                           -                  SPI1_MISO/I2S1_SDI
                L14 M11 L11 N13 W15 T12                                                                 I/O                        -
                   -          -           -          -          -       C10               PC0           I/O
        """

        rows = normalize_pin_table_text(text)

        self.assertEqual(["F4", "W7", "B1", "E1", "W15"], [row.ball for row in rows])
        self.assertEqual("PA13 (JTMS/SWDIO)", rows[1].pin_name)
        self.assertEqual("I/O", rows[1].pin_type)
        self.assertTrue(rows[1].functions)
        self.assertEqual("NC", rows[2].pin_name)
        self.assertEqual("-", rows[2].pin_type)
        self.assertEqual("OSC32_IN", rows[3].pin_name)
        self.assertEqual("I/O", rows[3].pin_type)
        self.assertEqual("PB4", rows[4].pin_name)
        self.assertIsNotNone(rows[0].evidence)

    def test_pin_table_validator_blocks_incomplete_tables(self):
        rows = [
            NormalizedPinRow(ball="A1", pin_name="PDR_ON", pin_type="I"),
            NormalizedPinRow(ball="F2", pin_name="NRST", pin_type="I"),
            NormalizedPinRow(ball="F4", pin_name="BOOT0", pin_type="I"),
        ]

        validation = validate_pin_table(rows, expected_balls={"A1", "F2", "F4", "W19"})
        report = build_pin_table_gap_report(rows, validation)

        self.assertFalse(validation.passed)
        self.assertIn("W19", validation.missing_balls)
        self.assertIsNone(report["pin_table_output"])
        self.assertFalse(report["raw_pdf_text_committed"])


if __name__ == "__main__":
    unittest.main()
