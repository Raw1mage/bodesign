"""Readiness `folder` contract — one meaning in every internal code path.

Owning contract (adjudicated 2026-08-02, BR_20260719 c01 double-prefix +
BR_20260719 c02 provenance-root/dod-surface):

    A readiness verb's `folder` argument is ALWAYS the PRODUCT ROOT. Stage
    placement is carried by the rel_path constants and by `<STAGE>/01_refs/`;
    a caller never pre-joins the stage folder itself.

Three consequences this module pins, each with a control that proves the
assertion can actually fail (缺席態與失敗態不得共用同一個輸出):

  TV-1  c01 readiness resolves a deliverable wherever the audience-split
        contract allows it to live (03_output/ first, legacy buckets after),
        so a compliant package never reads as all-missing.
  TV-2  c02 readiness resolves constraints AND refs provenance against the
        SAME folder value — no folder exists today that satisfies both.
  TV-3  c02 readiness carries dod_ok / guide_compliance like every other
        stage, because GUIDE c02-me §Self-verify tells the caller to read it.
  TV-4  the artifact track and the DoD track must never disagree about the
        same package (pct=0 while dod_ok=true is an impossible state that
        was being returned cleanly, with no warning).
  TV-5  gate.py declares `folder` required for c02_readiness, so the landing
        plane cannot silently pass folder=None (which made "folder absent"
        and "constraints genuinely missing" produce identical output).
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    assess_c01_package_readiness,
    assess_c02_constraint_readiness,
)
from bodesign_workflow_core.guide_dod import load_manifest

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

_C02_CONSTRAINTS = {
    "board_outline": {"width_mm": 80, "height_mm": 50},
    "component_heights": [{"ref": "J1", "height_mm": 8}],
    "connector_openings": [{"ref": "J1", "type": "usb-c"}],
    "antenna_keepouts": [{"zone": "top", "width_mm": 24, "height_mm": 16}],
    "battery_envelope": {"width_mm": 60, "height_mm": 50, "thickness_mm": 10},
    "provenance": {
        "board_outline": {"kind": "refs", "source": "C02_dimensions.md", "detail": "§3"},
        "component_heights": {"kind": "refs", "source": "C02_dimensions.md", "detail": "§3"},
        "connector_openings": {"kind": "refs", "source": "C02_dimensions.md", "detail": "§2"},
        "antenna_keepouts": {"kind": "refs", "source": "C02_dimensions.md", "detail": "§2"},
        "battery_envelope": {"kind": "refs", "source": "C02_dimensions.md", "detail": "§3"},
    },
}


class _ProductRootCase(unittest.TestCase):
    """A product root laid out the way the audience-split contract mandates."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-foldercontract-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _seed_c01(self) -> None:
        """C01 deliverables at their CURRENT canonical position (03_output/)."""
        out = self.work / "C01-ID" / "03_output"
        out.mkdir(parents=True, exist_ok=True)
        (out / "Design_Direction.md").write_text("# Design direction\n\ndraft\n", encoding="utf-8")
        (out / "CMF_Direction.md").write_text("# CMF\n\ndraft\n", encoding="utf-8")
        (out / "UIUX_Requirements.md").write_text("# UIUX\n\ndraft\n", encoding="utf-8")
        (out / "Handoff_to_ID_Designer.md").write_text("# Handoff\n\ndraft\n", encoding="utf-8")
        (out / "Interface_Constraints.json").write_text(
            json.dumps({"schema": "bodesign.c01.interface_constraints.v2",
                        "exposed_components": []}, ensure_ascii=False),
            encoding="utf-8")

    def _seed_c02(self) -> None:
        """C02 constraints + the stage-level 01_refs/ SSOT its provenance cites."""
        stage = self.work / "C02-ME"
        stage.mkdir(parents=True, exist_ok=True)
        (stage / "Mechanical_Constraints.json").write_text(
            json.dumps(_C02_CONSTRAINTS, ensure_ascii=False, indent=2), encoding="utf-8")
        refs = stage / "01_refs"
        refs.mkdir(parents=True, exist_ok=True)
        (refs / "C02_dimensions.md").write_text("# dimensions\n\nfrozen\n", encoding="utf-8")


class TV1C01ResolvesAudienceSplitPosition(_ProductRootCase):
    def test_compliant_package_is_not_all_missing(self):
        """BR_20260719 c01: a compliant package must not read as all-missing.

        The failure this pins is a FALSE NEGATIVE, whose cost is an agent
        regenerating deliverables that already exist.
        """
        self._seed_c01()
        r = assess_c01_package_readiness(self.work)
        missing = [a.key for a in r.artifacts if a.status != "present"]
        self.assertEqual([], missing,
                         f"deliverables exist under C01-ID/03_output/ but read as missing: {missing}")
        self.assertEqual(100, r.readiness_pct)

    def test_control_genuinely_empty_root_still_reads_missing(self):
        """CONTROL: the assertion above must be able to fail.

        An empty product root MUST still report every artifact missing —
        otherwise TV-1 would pass for a trivially-permissive resolver and
        prove nothing.
        """
        r = assess_c01_package_readiness(self.work)
        missing = [a.key for a in r.artifacts if a.status != "present"]
        self.assertEqual(5, len(missing), "empty root must still report all 5 missing")
        self.assertEqual(0, r.readiness_pct)

    def test_control_invisible_root_is_distinguishable(self):
        """CONTROL: 'not visible' must never look like 'genuinely empty'."""
        r = assess_c01_package_readiness(self.work / "NO_SUCH_DIR_ZZZ")
        self.assertFalse(r.root_visible)
        self.assertTrue(r.warnings)


class TV2C02SingleFolderBasis(_ProductRootCase):
    def test_constraints_and_provenance_share_one_folder_value(self):
        """BR_20260719 c02 symptom A: no folder value satisfied both paths.

        `_load_constraints` wanted the product root; `_refs_source_resolves`
        wanted the stage root. Passing either made the other fail, so the
        refs gap reported here was an artefact of the disagreement, not of
        the package.
        """
        self._seed_c02()
        r = assess_c02_constraint_readiness(folder=self.work)

        present = {i.key for i in r.items if i.status == "present"}
        self.assertIn("board_outline", present,
                      "constraints must load when folder is the product root")

        gap_items = [i for i in r.items if i.key == "constraint_provenance"]
        self.assertEqual([], gap_items,
                         f"refs sources resolve under C02-ME/01_refs/ but were reported as gaps: "
                         f"{[i.message for i in gap_items]}")

    def test_control_unresolvable_source_is_still_a_gap(self):
        """CONTROL: the gap detector must still fire on a genuinely bad source.

        Without this, TV-2 would also pass if provenance checking were simply
        disabled — the fix must resolve the path, not stop looking.
        """
        self._seed_c02()
        cpath = self.work / "C02-ME" / "Mechanical_Constraints.json"
        data = json.loads(cpath.read_text(encoding="utf-8"))
        data["provenance"]["board_outline"]["source"] = "NO_SUCH_REF_ZZZ.md"
        cpath.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        r = assess_c02_constraint_readiness(folder=self.work)
        gap_items = [i for i in r.items if i.key == "constraint_provenance"]
        self.assertTrue(gap_items, "a non-existent refs source must still be reported as a gap")
        self.assertIn("board_outline", gap_items[0].message)

    def test_control_traversal_escape_still_rejected(self):
        """CONTROL: containment (review F2) must survive the basis change."""
        self._seed_c02()
        (self.work / "outside_secret.md").write_text("x\n", encoding="utf-8")
        cpath = self.work / "C02-ME" / "Mechanical_Constraints.json"
        data = json.loads(cpath.read_text(encoding="utf-8"))
        data["provenance"]["board_outline"]["source"] = "../../outside_secret.md"
        cpath.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        r = assess_c02_constraint_readiness(folder=self.work)
        gap_items = [i for i in r.items if i.key == "constraint_provenance"]
        self.assertTrue(gap_items, "a ../ escape out of 01_refs/ must never pass the gate")


class TV3C02CarriesDodSurface(_ProductRootCase):
    def test_c02_readiness_exposes_dod_ok_and_guide_compliance(self):
        """BR_20260719 c02 symptom B: GUIDE says read dod_ok; c02 never had it.

        c01/c04/c05/c06 all attach guide_compliance_for; c02 was the only
        stage whose readiness verb omitted it, so a caller following the
        GUIDE literally got nothing back.
        """
        self._seed_c02()
        d = assess_c02_constraint_readiness(folder=self.work).to_dict()
        self.assertIn("guide_compliance", d)
        self.assertIn("dod_ok", d)

    def test_control_inline_constraints_mode_has_no_dod(self):
        """CONTROL: with no folder there is nothing to check against.

        guide_compliance_for returns None for a non-directory folder, so the
        keys must be ABSENT rather than defaulted to a reassuring value.
        """
        d = assess_c02_constraint_readiness(_C02_CONSTRAINTS, folder=None).to_dict()
        self.assertNotIn("guide_compliance", d)
        self.assertNotIn("dod_ok", d)


class TV4CrossTrackConsistency(_ProductRootCase):
    def test_artifact_track_and_dod_track_cannot_disagree(self):
        """The impossible state that was being returned cleanly.

        Measured at HEAD on a real package: readiness_pct=0 with every
        artifact 'missing' WHILE dod_ok=true — the two tracks were reading
        different candidate paths for the same deliverable. Neither track
        was wrong on its own terms, and nothing noticed the contradiction.
        """
        self._seed_c01()
        d = assess_c01_package_readiness(self.work).to_dict()
        if "dod_ok" not in d:
            self.skipTest("no DoD manifest for c01 — nothing to cross-check")
        all_missing = all(a["status"] != "present" for a in d["artifacts"])
        self.assertFalse(all_missing and d["dod_ok"] is True,
                         "artifact track says all-missing while DoD track says ok — "
                         "the two tracks are resolving different paths")

    def test_candidate_paths_match_the_dod_manifest(self):
        """Anti-drift: the two tracks must resolve the SAME candidate set.

        This is the structural guard. The runtime check above catches a
        disagreement once it has already happened on a real package; this
        catches the drift that causes it, at the source.
        """
        from bodesign_workflow_core.c01_id_package import C01_OUTPUT_CANDIDATES

        manifest = load_manifest("c01")
        self.assertIsNotNone(manifest, "c01 DoD manifest must exist")
        by_id = {d["id"]: d for d in manifest["deliverables"]}
        for key, dod_id in (
            ("ai_file", "design_direction"),
            ("cmf", "cmf_direction"),
            ("display_uiux", "uiux_requirements"),
        ):
            self.assertIn(dod_id, by_id)
            declared = [str(p) for p in C01_OUTPUT_CANDIDATES[key]]
            self.assertEqual(
                by_id[dod_id]["any_of"], declared,
                f"readiness candidates for {key!r} drifted from the DoD manifest's any_of")


class TV5GateDeclaresFolderRequired(unittest.TestCase):
    def _gate(self):
        import importlib.util
        repo = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "bodesign_gate_under_test", repo / "skills" / "bodesign" / "scripts" / "gate.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_c02_readiness_requires_folder(self):
        """gate.py only repo-defaults a key that the verb declares REQUIRED.

        With an empty required tuple, `gate.py c02_readiness --repo <A>` passed
        folder=None, `_load_constraints(None)` returned {}, and every constraint
        read as missing — identical output to a package that genuinely has none.
        """
        gate = self._gate()
        self.assertIn("folder", gate.VERBS["c02_readiness"][2])

    def test_control_sibling_verbs_already_declare_it(self):
        """CONTROL: proves the assertion is specific, not vacuously true."""
        gate = self._gate()
        for verb in ("c01_readiness", "c04_readiness", "c05_readiness", "c06_readiness"):
            self.assertIn("folder", gate.VERBS[verb][2], f"{verb} should already declare folder")

    def test_repo_default_only_applies_to_declared_required_keys(self):
        """The mechanism itself — why an empty tuple silently disarmed the default."""
        gate = self._gate()
        self.assertIn("folder", gate.REPO_DEFAULT_KEYS)


class TV6StageMapNeverDefaults(unittest.TestCase):
    """The one input the whole stage derivation depends on — previously unguarded.

    Found by an adversary mutation (M4): replacing ``stage_folder_for``'s fail-fast
    guard with ``if False:`` turned NOTHING red across the entire repo. The gate's
    logic was tested to saturation while the cell feeding the gate had no owner, so
    the next person could restore ``.get(key, "C01-ID")`` to make some other test
    green and this contract would not react.

    A defaulted unknown stage is exactly 天條 1's forbidden shape: "this stage does
    not exist" and "this stage's SSOT is missing" would produce the same downstream
    result — a missing-refs error naming a folder nobody asked for.
    """

    def test_unknown_stage_raises_and_is_never_defaulted(self):
        from bodesign_workflow_core.readiness_common import (
            UnknownStageError,
            stage_folder_for,
        )

        with self.assertRaises(UnknownStageError):
            stage_folder_for("C99")

        # CONTROL: a known stage must still resolve, or the assertion above is
        # vacuous — a `stage_folder_for` that raised unconditionally would pass it.
        self.assertEqual(stage_folder_for("C01"), "C01-ID")
        self.assertEqual(stage_folder_for("c01"), "C01-ID")  # case normalisation


if __name__ == "__main__":
    unittest.main()
