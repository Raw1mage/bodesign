"""WP3 — the projected skill must carry a reachable executable body.

plan c03_delivery_contract_and_engine_seams DD-03/DD-04, tasks 3.5/3.6/3.7.

The defect: `mcp.json` projects `skillPaths: ["skills"]`, so `packages/` is
structurally OUTSIDE the projection unit. A `gate.py` running from the published
install at ~/.local/share/opencode/skills/ can walk up forever and never reach a
repo — every landing verb is unrunnable there, and the roster still printed a
confident `count: 61`.

These tests run gate.py from a SCRATCH COPY outside the repo, which is what makes
them measure anything: with the module loaded from its real in-tree path the
walk-up succeeds regardless of the candidate list, so the candidate tier would be
untested and would pass either way.

Scratch lives under $XDG_RUNTIME_DIR (AGENTS.md §3: /tmp is forbidden) and is
removed in tearDown.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / "skills" / "bodesign" / "scripts" / "gate.py"

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR")
                    or (Path.home() / ".cache")) / "claude-work"


def _load_from(path: Path, name: str):
    """Load gate.py from an arbitrary location, so __file__ (and therefore the
    walk-up start point) is the scratch copy rather than the in-tree original."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call(module, argv):
    """Run main(argv) in-process, returning (envelope, rc)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = module.main(argv)
    out = buf.getvalue().strip()
    return (json.loads(out) if out else None), rc


class _ScratchGateCase(unittest.TestCase):
    """A gate.py copy that stands where the published skill stands: a scripts/
    directory with NO packages/ anywhere above it."""

    _counter = 0

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-wp3-", dir=PRIVATE_BASE))
        published = self.work / "skills" / "bodesign" / "scripts"
        published.mkdir(parents=True)
        shutil.copy2(GATE, published / "gate.py")
        self.gate_path = published / "gate.py"

        # Precondition, asserted rather than assumed: nothing above the scratch
        # copy holds packages/workflow-care — if it did, the walk-up would answer
        # and every candidate-tier assertion below would be vacuous.
        cur = published
        while True:
            self.assertFalse((cur / "packages" / "workflow-core").is_dir(),
                             f"scratch tree is contaminated: {cur} has packages/")
            if cur.parent == cur:
                break
            cur = cur.parent

        self._env = dict(os.environ)
        os.environ.pop("BODESIGN_SRC", None)

        type(self)._counter += 1
        self.module = _load_from(self.gate_path, f"wp3_gate_{type(self)._counter}")

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.work, ignore_errors=True)


class PublishedInstallResolvesTests(_ScratchGateCase):
    """3.5 POSITIVE CONTROL — a consumer holding only the projected skill."""

    def test_roster_resolves_packages_via_the_candidate_list(self):
        env, rc = _call(self.module, ["--list"])
        self.assertEqual(rc, 0)
        self.assertTrue(env["result"]["packages_resolved"],
                        f"packages_error={env['result'].get('packages_error')}")
        self.assertTrue(env["result"]["packages_origin"].startswith("candidate:"),
                        "the walk-up must NOT be what answered here — if it did, "
                        "the scratch tree is not standing in for a published one")
        self.assertTrue(
            (Path(env["result"]["packages_root"]) / "packages" / "workflow-core").is_dir())

    def test_a_verb_actually_runs_from_the_published_tree(self):
        """`packages_resolved` is a directory test, not a health check — the only
        evidence a verb runs is running one (BR_20260903a §7 attack 2).

        Two verbs, in order: the scaffold creates the artifact the reader needs,
        and the reader proves the imported module did real work rather than
        merely importing. A single verb that only writes would not distinguish
        "the package imported" from "the package functions".
        """
        env, rc = _call(self.module, ["c00_scaffold_prd", "--repo", str(self.work)])
        self.assertEqual(rc, 0, f"scaffold envelope={env}")
        self.assertEqual(env["status"], "ok")
        # Paths come from the envelope, not from a hand-written guess: the verb
        # writes C00-PRD/03_output/answer_state.json, and a test asserting the
        # wrong location fails for a reason that has nothing to do with what it
        # claims to measure (tests/test_landing_gate.py:186 does exactly that and
        # is red at HEAD for it).
        written = env["result"]["files"]
        self.assertIn("C00-PRD/03_output/answer_state.json", written)
        for rel in written:
            self.assertTrue((self.work / rel).is_file(),
                            f"envelope claims {rel} but it is not on disk")

        env, rc = _call(self.module, ["c00_readiness", "--repo", str(self.work)])
        self.assertEqual(rc, 0, f"readiness envelope={env}")
        self.assertTrue(env["ok"])
        self.assertEqual(env["status"], "ok")
        self.assertEqual(env["result"]["readiness_pct"], 0)


class UnresolvableIsNotRunTests(_ScratchGateCase):
    """3.6 NEGATIVE CONTROL — every verb must say not-run, never ok."""

    def _blind(self):
        """Point every candidate at a directory with no packages/workflow-core."""
        return mock.patch.object(
            self.module, "_LANDING_SRC_CANDIDATES",
            ("/nonexistent-a", "/nonexistent-b"))

    def test_roster_reports_unresolved_with_the_typed_error(self):
        with self._blind():
            env, rc = _call(self.module, ["--list"])
        self.assertEqual(rc, 0, "the roster stays complete and rc stays 0")
        res = env["result"]
        self.assertFalse(res["packages_resolved"])
        self.assertIsNone(res["packages_root"])
        self.assertIsNone(res["packages_origin"])
        self.assertEqual(res["packages_error"]["code"], "LANDING_PACKAGES_NOT_FOUND")
        self.assertIn("impact", res["packages_error"])

    def test_every_roster_verb_returns_not_run_and_none_returns_ok(self):
        """The whole roster, not a sample: the claim is universal.

        `ok=false` alone was not enough — it cannot separate "the verb ran and
        rejected your input" from "no verb ever executed".
        """
        with self._blind():
            _, rc = _call(self.module, ["--list"])
            verbs = sorted(self.module.VERBS)
            self.assertGreater(len(verbs), 20, "roster suspiciously small")
            statuses = {}
            for verb in verbs:
                env, rc = _call(self.module, [verb, "--repo", str(self.work)])
                statuses[verb] = (env.get("status"), env.get("ok"), rc)

        not_run = [v for v, (s, _, _) in statuses.items() if s == "not-run"]
        self.assertEqual(sorted(not_run), verbs,
                         "every verb must report not-run when nothing can execute")
        oks = [v for v, (_, ok, _) in statuses.items() if ok]
        self.assertEqual(oks, [], "no verb may report ok when packages/ is unresolvable")
        codes = {env for env, _, _ in statuses.values()}
        self.assertEqual(codes, {"not-run"})

    def test_not_run_is_distinct_from_a_verb_level_failure(self):
        """REVERSE CONTROL for the status field itself.

        If `status` were hard-coded to "not-run" on every failure, this passes
        only by accident — so assert a reachable-verb failure still says "failed".
        A field with one possible value measures nothing.
        """
        env, rc = _call(self.module, ["emit_fab", "--repo", str(self.work)])
        self.assertNotEqual(rc, 0)
        self.assertEqual(env["error"]["code"], "VERB_NOT_LANDING")
        self.assertEqual(env["status"], "failed",
                         "a verb that was reachable and refused is NOT 'not-run'")


class CandidateListDisciplineTests(_ScratchGateCase):
    """3.7 — the list is re-derived here, never restated (V4-c shape)."""

    def test_candidates_are_literal_paths_not_a_search(self):
        """No glob, no wildcard, no filesystem walk in the candidate tier."""
        for cand in self.module._LANDING_SRC_CANDIDATES:
            self.assertTrue(os.path.isabs(cand), f"{cand!r} is not absolute")
            for meta in ("*", "?", "["):
                self.assertNotIn(meta, cand, f"{cand!r} looks like a glob")

    def test_a_nonexistent_candidate_is_skipped_without_altering_the_error(self):
        """Prepending a dead path must change nothing a caller can observe."""
        real = tuple(self.module._LANDING_SRC_CANDIDATES)
        with mock.patch.object(self.module, "_LANDING_SRC_CANDIDATES",
                               ("/nonexistent-zzz",) + real):
            env_a, _ = _call(self.module, ["--list"])
        env_b, _ = _call(self.module, ["--list"])
        self.assertEqual(env_a["result"]["packages_root"],
                         env_b["result"]["packages_root"])
        self.assertTrue(env_a["result"]["packages_resolved"])

    def test_every_candidate_is_gated_on_packages_workflow_core(self):
        """A candidate that merely EXISTS must not be accepted.

        The scratch root exists and is a perfectly good directory; accepting it
        would silently run the roster against a tree with no packages at all.
        """
        with mock.patch.object(self.module, "_LANDING_SRC_CANDIDATES",
                               (str(self.work),)):
            env, _ = _call(self.module, ["--list"])
        self.assertFalse(env["result"]["packages_resolved"],
                         "an existing directory without packages/workflow-core "
                         "was accepted — the acceptance predicate is not applied")

    def test_explicit_bodesign_src_that_is_wrong_fails_loud(self):
        """An override must never be silently replaced by a candidate.

        Falling through would make a typo indistinguishable from a correct
        setting, and the verbs would run against a tree nobody named.
        """
        empty = self.work / "empty-src"
        empty.mkdir()
        os.environ["BODESIGN_SRC"] = str(empty)
        try:
            env, rc = _call(self.module, ["c00_readiness", "--repo", str(self.work)])
        finally:
            os.environ.pop("BODESIGN_SRC", None)
        self.assertNotEqual(rc, 0)
        self.assertEqual(env["error"]["code"], "LANDING_PACKAGES_NOT_FOUND")
        self.assertEqual(env["status"], "not-run")
        self.assertIn(str(empty), env["error"]["message"])


if __name__ == "__main__":
    unittest.main()
