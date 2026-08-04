"""C02 STL export — an absent state and a failure state must not share one output.

Owning defect: `issues/BR_20260804_c02_export_stl_cannot_see_files_staged_into_its_own_token.md`

Before this change `export_c02_stl` returned a byte-identical result for three
unrelated situations — wrong argument / missing directory / source not generated
yet — plus a field whose NAME said "openscad binary" while its VALUE was the
`.scad` source. The external filer needed a full round to separate them, and only
managed it because the `folder` echo happened to print a usable path.

Every assertion here is paired with a CONTROL that proves the assertion can
actually fail. A test that passes because the code is trivially permissive
proves nothing, and reads exactly like a test that passes because the code is
correct.

Mutation proof (run by hand; each must turn this file RED):
  M1  `_classify_missing_source` -> always return ("source_missing", <fixed str>)
      => TV1/TV2/TV3 fail (statuses collapse back to one value)
  M2  drop the `root.name == C02_STAGE_DIRNAME` branch
      => TV3 fails (double prefix reads as plain source_missing)
  M3  `openscad_bin_path` default -> None
      => TV4 fails ("not probed" becomes indistinguishable from "probed, absent")
  M4  `to_dict()["openscad_path"] = self.openscad_bin_path`  (the old meaning)
      => TV5 fails (the deprecated alias stops mirroring the source path)
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bodesign_workflow_core import export_c02_stl
from bodesign_workflow_core.c02_me_package import (
    C02_OUTPUTS,
    C02_STAGE_DIRNAME,
    OPENSCAD_BIN_NOT_PROBED,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

_SCAD = "cube([10,10,10]);\n"


class _Case(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c02-fail-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _seed_source(self, root: Path) -> Path:
        path = root / C02_OUTPUTS["openscad"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_SCAD, encoding="utf-8")
        return path


class TV1ThreeAbsenceCausesAreDistinguishable(_Case):
    """The core invariant: three causes, three statuses, no collisions."""

    def _statuses(self) -> dict[str, str]:
        stage = self.work / C02_STAGE_DIRNAME
        stage.mkdir(parents=True, exist_ok=True)
        (stage / C02_OUTPUTS["openscad"].name).write_text(_SCAD, encoding="utf-8")
        return {
            "folder_absent": export_c02_stl(self.work / "does-not-exist").status,
            "source_absent": export_c02_stl(self.work / "empty-root").status,
            "double_prefix": export_c02_stl(stage).status,
        }

    def test_three_causes_do_not_collapse_to_one_status(self):
        (self.work / "empty-root").mkdir(parents=True, exist_ok=True)
        s = self._statuses()
        self.assertEqual(
            3, len(set(s.values())),
            f"three different causes must not share one output; got {s}",
        )
        self.assertEqual("folder_missing", s["folder_absent"])
        self.assertEqual("source_missing", s["source_absent"])
        self.assertEqual("folder_is_stage_dir", s["double_prefix"])

    def test_control_a_correct_call_is_unaffected(self):
        """CONTROL: the success path must NOT acquire any of the new statuses.

        Without this, TV1 would still pass for an implementation that returned a
        distinguishable status for *every* call including the good ones — i.e. a
        change that broke every existing caller.
        """
        self._seed_source(self.work)
        with patch("bodesign_workflow_core.c02_me_package.shutil.which", return_value=None):
            r = export_c02_stl(self.work, openscad_bin=None)
        self.assertEqual("export_unavailable", r.status)
        self.assertNotIn(r.status, {"folder_missing", "source_missing", "folder_is_stage_dir"})


class TV2MessageCarriesTheAbsolutePathActuallyStatted(_Case):
    """The single cheapest fix: say WHERE you looked.

    This alone lets a caller see a double prefix without knowing our contract —
    which is what the filer had to reconstruct by hand.
    """

    def test_message_and_field_name_the_probed_path(self):
        (self.work / "empty-root").mkdir(parents=True, exist_ok=True)
        r = export_c02_stl(self.work / "empty-root")
        expected = self.work / "empty-root" / C02_OUTPUTS["openscad"]
        self.assertIn(str(expected), r.message)
        self.assertEqual(str(expected), r.probed_source_path)

    def test_control_message_is_not_a_constant(self):
        """CONTROL: two different out_dirs must produce two different messages.

        The old implementation returned one hardcoded sentence for every input;
        an assertion that only checks "message is non-empty" would have passed
        against it.
        """
        (self.work / "a").mkdir(parents=True, exist_ok=True)
        (self.work / "b").mkdir(parents=True, exist_ok=True)
        ma = export_c02_stl(self.work / "a").message
        mb = export_c02_stl(self.work / "b").message
        self.assertNotEqual(ma, mb, "message must reflect the actual path, not a fixed string")


class TV3DoublePrefixIsNamedNotGuessed(_Case):
    """BR_20260719's shape: out_dir pre-joined with the stage folder.

    Named, never normalised — stripping it would make out_dir=<root> and
    out_dir=<root>/C02-ME both succeed while meaning different directories.
    """

    def test_stage_dir_argument_is_reported_with_the_fix(self):
        stage = self.work / C02_STAGE_DIRNAME
        stage.mkdir(parents=True, exist_ok=True)
        (stage / C02_OUTPUTS["openscad"].name).write_text(_SCAD, encoding="utf-8")

        r = export_c02_stl(stage)
        self.assertEqual("folder_is_stage_dir", r.status)
        self.assertIn(str(self.work), r.message, "must name the product root the caller should pass")
        self.assertIn(str(stage / C02_OUTPUTS["openscad"]), r.probed_source_path)

    def test_no_silent_normalisation(self):
        """天條 1: we must NOT quietly succeed by stripping the extra segment.

        If a future edit adds a normaliser, this goes red — which is the point.
        """
        stage = self.work / C02_STAGE_DIRNAME
        stage.mkdir(parents=True, exist_ok=True)
        (stage / C02_OUTPUTS["openscad"].name).write_text(_SCAD, encoding="utf-8")
        r = export_c02_stl(stage)
        self.assertNotEqual("stl_exported", r.status)
        self.assertIsNone(r.stl_path)

    def test_control_a_stage_named_root_that_is_genuinely_a_root_still_works(self):
        """CONTROL: the detection keys on the double prefix, not on the name alone.

        A directory that happens to be called C02-ME but IS a legitimate product
        root (i.e. it contains C02-ME/Enclosure.scad) must export normally. This
        proves the branch is not a blanket ban on a directory name.
        """
        stage_named_root = self.work / C02_STAGE_DIRNAME
        self._seed_source(stage_named_root)  # <root>/C02-ME/C02-ME/Enclosure.scad
        with patch("bodesign_workflow_core.c02_me_package.shutil.which", return_value=None):
            r = export_c02_stl(stage_named_root, openscad_bin=None)
        self.assertEqual("export_unavailable", r.status,
                         "a genuine product root named C02-ME must resolve normally")


class TV4OpenscadBinPathSeparatesNotProbedFromNotFound(_Case):
    """`None` used to mean BOTH 'no openscad installed' AND 'never looked'.

    The filer read `null` and concluded the container had no OpenSCAD; the real
    cause was a path that never resolved, several steps earlier.
    """

    def test_early_return_reports_not_probed(self):
        (self.work / "empty-root").mkdir(parents=True, exist_ok=True)
        r = export_c02_stl(self.work / "empty-root")
        self.assertEqual(OPENSCAD_BIN_NOT_PROBED, r.openscad_bin_path)
        self.assertIsNot(r.openscad_bin_path, None)

    def test_probed_and_absent_reports_none(self):
        self._seed_source(self.work)
        with patch("bodesign_workflow_core.c02_me_package.shutil.which", return_value=None):
            r = export_c02_stl(self.work, openscad_bin=None)
        self.assertEqual("export_unavailable", r.status)
        self.assertIsNone(r.openscad_bin_path)

    def test_the_two_are_distinguishable(self):
        """The whole reason this field exists. Both are 'no binary in hand'."""
        (self.work / "empty-root").mkdir(parents=True, exist_ok=True)
        not_probed = export_c02_stl(self.work / "empty-root").to_dict()["openscad_bin_path"]
        self._seed_source(self.work)
        with patch("bodesign_workflow_core.c02_me_package.shutil.which", return_value=None):
            probed_absent = export_c02_stl(self.work, openscad_bin=None).to_dict()["openscad_bin_path"]
        self.assertNotEqual(not_probed, probed_absent,
                            "'never probed' and 'probed, not found' must not share one value")

    def test_control_survives_json_round_trip(self):
        """CONTROL: the distinction must survive to_dict(), not just the dataclass.

        A JSON consumer reading `.get("openscad_bin_path")` sees None for BOTH a
        null value and a missing key — so the sentinel has to be a real string on
        the wire, and the key has to be present in both cases.
        """
        (self.work / "empty-root").mkdir(parents=True, exist_ok=True)
        d = export_c02_stl(self.work / "empty-root").to_dict()
        self.assertIn("openscad_bin_path", d)
        self.assertIsInstance(d["openscad_bin_path"], str)


class TV5DeprecatedAliasMirrorsTheSourcePath(_Case):
    """`openscad_path` kept as an alias of `source_path`, not removed.

    A repo-scoped grep found zero readers, but this repo IS an MCP server: its
    field contract is consumed mostly from OTHER repos, where the grep has no
    reach. "I could not find a reader" and "there is no reader" share one output.
    Removing the key would surface downstream as `null` — which under the new
    semantics means "probed, not found", i.e. a quiet wrong answer.
    """

    def test_alias_equals_source_path_on_every_status(self):
        (self.work / "empty-root").mkdir(parents=True, exist_ok=True)
        stage = self.work / C02_STAGE_DIRNAME
        stage.mkdir(parents=True, exist_ok=True)
        (stage / C02_OUTPUTS["openscad"].name).write_text(_SCAD, encoding="utf-8")
        results = [
            export_c02_stl(self.work / "does-not-exist").to_dict(),
            export_c02_stl(self.work / "empty-root").to_dict(),
            export_c02_stl(stage).to_dict(),
        ]
        self._seed_source(self.work)
        with patch("bodesign_workflow_core.c02_me_package.shutil.which", return_value=None):
            results.append(export_c02_stl(self.work, openscad_bin=None).to_dict())

        for d in results:
            self.assertIn("openscad_path", d, "deprecated alias must still be emitted")
            self.assertEqual(d["source_path"], d["openscad_path"],
                             f"alias must mirror source_path (status={d['status']})")

    def test_control_alias_is_not_trivially_always_none(self):
        """CONTROL: on a path where source_path IS set, the alias must be set too.

        Without this, TV5 would pass against an implementation that hardcoded the
        alias to None — every early-return case would agree by accident.
        """
        self._seed_source(self.work)
        with patch("bodesign_workflow_core.c02_me_package.shutil.which", return_value=None):
            d = export_c02_stl(self.work, openscad_bin=None).to_dict()
        self.assertIsNotNone(d["source_path"])
        self.assertEqual(str(C02_OUTPUTS["openscad"]), d["openscad_path"])


class TV6SourceReadyKeepsItsMeaning(_Case):
    """`source_ready` has 5 in-repo readers; its meaning must not drift.

    It used to be derived from the field now called `source_path` (via the badly
    named `openscad_path`). Re-deriving it from anything else — e.g. the binary
    field — would silently invert it on the early-return paths.
    """

    def test_false_when_no_source_was_found(self):
        (self.work / "empty-root").mkdir(parents=True, exist_ok=True)
        self.assertFalse(export_c02_stl(self.work / "empty-root").to_dict()["source_ready"])

    def test_true_when_source_exists(self):
        self._seed_source(self.work)
        with patch("bodesign_workflow_core.c02_me_package.shutil.which", return_value=None):
            self.assertTrue(export_c02_stl(self.work, openscad_bin=None).to_dict()["source_ready"])


if __name__ == "__main__":
    unittest.main()
