"""Phase 7: 3D-projection-to-2D-vector SVG tests.

export_c02_projection_svg derives a 2D vector SVG FROM the 3D model via OpenSCAD
projection() — exact geometric paths, not a raster trace. We verify the fail-fast
gates (no STL / no CLI), the wrapper .scad contents, and (when openscad is present)
a real svg_exported run.
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parent.parent


def _load(mod_name: str, rel_path: str):
    # Bypass the package __init__, which on a bare host pulls in optional
    # namespace packages (bodesign_reverse_core/bodesign_design_ir) that are
    # not installed. c02_me_package itself has only stdlib top-level imports.
    spec = importlib.util.spec_from_file_location(mod_name, _ROOT / rel_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module  # register before exec for dataclass(slots=True)
    spec.loader.exec_module(module)
    return module


_c02 = _load(
    "c02_me_package_under_test",
    "packages/workflow-core/bodesign_workflow_core/c02_me_package.py",
)


class ProjectionSvgGateTests(unittest.TestCase):
    def setUp(self):
        self._export = _c02.export_c02_projection_svg
        self._outputs = _c02.C02_OUTPUTS
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_stl(self):
        stl = Path(self._tmp) / self._outputs["stl"]
        stl.parent.mkdir(parents=True, exist_ok=True)
        stl.write_text("solid x\nendsolid x\n", encoding="utf-8")
        return stl

    def test_source_missing_when_no_stl(self):
        res = self._export(self._tmp)
        self.assertEqual(res.status, "source_missing")
        self.assertIsNone(res.svg_path)

    def test_export_unavailable_when_no_cli(self):
        self._write_stl()
        # Patch on the importlib-loaded module (registered as c02_me_package_under_test),
        # not the package path — patching the latter would import the package __init__.
        with mock.patch.object(_c02.shutil, "which", return_value=None):
            res = self._export(self._tmp)
        self.assertEqual(res.status, "export_unavailable")
        self.assertIsNone(res.svg_path)
        # no fake SVG written
        self.assertFalse((Path(self._tmp) / self._outputs["projection_svg"]).exists())

    def test_wrapper_scad_contents(self):
        self._write_stl()
        # Force the "no real openscad" path but let the wrapper get written by
        # pointing the executable at a stub that does nothing, then assert wrapper.
        fake_bin = Path(self._tmp) / "fake_openscad.sh"
        fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake_bin.chmod(0o755)
        # returncode 0 but no svg created -> export_failed, but wrapper IS written
        res = self._export(self._tmp, openscad_bin=str(fake_bin))
        wrapper = Path(self._tmp) / self._outputs["projection_scad"]
        self.assertTrue(wrapper.exists(), "wrapper .scad must be written before invoking CLI")
        text = wrapper.read_text(encoding="utf-8")
        self.assertIn("projection(cut = false)", text)
        self.assertIn('import("Enclosure.stl")', text)
        # fake bin produced no svg -> export_failed
        self.assertEqual(res.status, "export_failed")

    def test_wrapper_cut_true(self):
        self._write_stl()
        fake_bin = Path(self._tmp) / "fake_openscad.sh"
        fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake_bin.chmod(0o755)
        self._export(self._tmp, openscad_bin=str(fake_bin), cut=True)
        wrapper = Path(self._tmp) / self._outputs["projection_scad"]
        self.assertIn("projection(cut = true)", wrapper.read_text(encoding="utf-8"))


class ProjectionSvgRealRunTests(unittest.TestCase):
    """Only runs when a real OpenSCAD CLI is on PATH (worker / dev box)."""

    def setUp(self):
        if not shutil.which("openscad"):
            self.skipTest("openscad CLI not on host")
        self._gen = _c02.generate_c02_openscad
        self._stl = _c02.export_c02_stl
        self._svg = _c02.export_c02_projection_svg
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(getattr(self, "_tmp", ""), ignore_errors=True)

    def test_full_chain_svg_exported(self):
        constraints = {
            "board_outline": {"width_mm": 50, "height_mm": 30},
            "component_heights": [{"height_mm": 12}],
        }
        self._gen(self._tmp, constraints, wall_thickness_mm=2,
                  clearance_mm=1, lid_clearance_mm=1)
        stl_res = self._stl(self._tmp)
        self.assertEqual(stl_res.status, "stl_exported")
        svg_res = self._svg(self._tmp)
        self.assertEqual(svg_res.status, "svg_exported")
        svg_path = Path(self._tmp) / svg_res.svg_path
        self.assertTrue(svg_path.exists())
        body = svg_path.read_text(encoding="utf-8")
        self.assertIn("<svg", body)


if __name__ == "__main__":
    unittest.main()