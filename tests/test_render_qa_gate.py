"""Independent unit tests for the render-QA text-overlap gate (task 0.2).

Proves the SVG <text>-bbox overlap gate BITES: a clean layout passes, an
overlapping-label layout fails. Synthesizes minimal SVG strings so the test is
hermetic (no kicad-cli needed).
"""
import os
import tempfile
import unittest

from bodesign_eda_bridge.render_qa import qa_svg_text


def _svg(texts: list[tuple]) -> str:
    # each text: (x, y, font_size, content)
    body = "\n".join(
        f'<text x="{x}" y="{y}" font-size="{fs}" text-anchor="start">{c}</text>'
        for (x, y, fs, c) in texts
    )
    return f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>'


class RenderQAGateTests(unittest.TestCase):
    def _run(self, svg: str):
        fd, path = tempfile.mkstemp(suffix=".svg")
        os.close(fd)
        try:
            with open(path, "w") as f:
                f.write(svg)
            return qa_svg_text(path)
        finally:
            os.unlink(path)

    def test_clean_layout_passes(self):
        # well-separated labels: no overlap
        svg = _svg([
            (0, 0, 1.27, "VDD"),
            (0, 20, 1.27, "GND"),
            (0, 40, 1.27, "SDA"),
            (50, 0, 1.27, "SCL"),
        ])
        rep = self._run(svg)
        self.assertTrue(rep.ok, msg=rep.summary())
        self.assertEqual(rep.violations, [])

    def test_stacked_labels_fail(self):
        # two long labels at nearly the same coordinate: must collide
        svg = _svg([
            (0, 0, 2.0, "SHARED_I2C_SDA"),
            (0, 0.3, 2.0, "SHARED_I2C_SCL"),
        ])
        rep = self._run(svg)
        self.assertFalse(rep.ok, msg="stacked labels must be flagged")
        self.assertTrue(rep.violations)

    def test_partial_overlap_below_thresh_passes(self):
        # tiny nudge that stays under THRESH*min_area should not trip
        svg = _svg([
            (0, 0, 1.27, "A"),
            (0.9, 0, 1.27, "B"),
        ])
        rep = self._run(svg)
        self.assertTrue(rep.ok, msg=rep.summary())


if __name__ == "__main__":
    unittest.main()
