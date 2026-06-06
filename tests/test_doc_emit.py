import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_reverse_core import emit_document, markdown_to_html

HAS_SOFFICE = (shutil.which("soffice") or shutil.which("libreoffice")) is not None
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

SAMPLE_MD = """# Title

Intro paragraph with **bold** and `code`.

## Section
- bullet one
- bullet two

| A | B |
|---|---|
| 1 | 2 |
"""


class DocEmitTests(unittest.TestCase):
    def test_markdown_to_html_covers_constructs(self):
        html = markdown_to_html(SAMPLE_MD)
        self.assertIn("<h1>Title</h1>", html)
        self.assertIn("<h2>Section</h2>", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<code>code</code>", html)
        self.assertIn("<table>", html)
        self.assertIn("<th>A</th>", html)
        self.assertIn("<li>bullet one</li>", html)

    @unittest.skipUnless(HAS_SOFFICE, "LibreOffice not installed")
    def test_emit_document_produces_docx_and_pdf(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-docemit-", dir=PRIVATE_BASE))
        try:
            md = work / "sample.md"
            md.write_text(SAMPLE_MD, encoding="utf-8")

            result = emit_document(md, work, ("docx", "pdf"))

            self.assertEqual("ok", result.status)
            self.assertIn("docx", result.outputs)
            self.assertIn("pdf", result.outputs)
            self.assertTrue(Path(result.outputs["docx"]).exists())
            self.assertTrue(Path(result.outputs["pdf"]).exists())
            self.assertGreater(Path(result.outputs["docx"]).stat().st_size, 0)
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
