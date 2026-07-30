"""BR_20260730 F4 — consumer_fork_drift lint.

The lint exists because §A–§L (twelve landed platform fixes) reached zero product
repos: the forks under `generated/tools/` froze on 2026-07-07 and still silently
drop 8 active ICs, while every gate stayed green.

Two defects were found in the lint's OWN first version, both of the shape this BR
family fights, so each has a dedicated regression test here:
  * `KNOWN_FORKS` named platform functions that do not exist (`widen`,
    `length_match` vs the real `widen_bus_tracks`, `length_match_bus`), so the AST
    fallback flagged an unrelated local helper — accusation from a wrong baseline.
  * all sentinels were applied to every fork regardless of which function owns
    them, turning 4 real findings into 11 — the same cry-wolf failure this BR's own
    F2 proposal was rejected for.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core.checkers.consumer_fork_drift import (
    KNOWN_FORKS,
    PLATFORM_SENTINELS,
    check_consumer_repo,
    platform_sentinel_state,
    sentinels_for,
)

_REPO = Path(__file__).parent.parent
_ROUTING = _REPO / "packages" / "eda-bridge" / "bodesign_eda_bridge" / "routing.py"


def _write(d: str, rel: str, body: str) -> str:
    p = Path(d) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return str(p)


class SentinelProvenanceTests(unittest.TestCase):
    """The sentinel table claims each token was introduced by a specific commit.
    That is a checkable fact, and checking it is what keeps the table from becoming
    another hand-copied list that drifts (BR_20260729 V4-c)."""

    def test_every_sentinel_exists_in_platform_source(self):
        state = platform_sentinel_state(_REPO)
        absent = sorted(t for t, ok in state.items() if not ok)
        self.assertEqual(absent, [],
                         f"sentinels no longer present in {_ROUTING.name}: {absent} — "
                         "scanning forks against a token the platform dropped would "
                         "accuse them from a baseline that does not exist")

    def test_every_sentinel_traces_to_the_commit_it_claims(self):
        for token, (sha, _owner, _why) in PLATFORM_SENTINELS.items():
            with self.subTest(token=token):
                out = subprocess.run(
                    ["git", "log", "-S", token, "--oneline", "--reverse", "--",
                     str(_ROUTING.relative_to(_REPO))],
                    cwd=_REPO, capture_output=True, text=True)
                self.assertEqual(out.returncode, 0, out.stderr[-400:])
                first = out.stdout.split("\n", 1)[0].split(" ", 1)[0]
                self.assertTrue(first.startswith(sha[:7]) or sha[:7].startswith(first[:7]),
                                f"{token!r} claims commit {sha} but was introduced by {first}")

    def test_every_known_fork_names_a_real_platform_function(self):
        """REGRESSION for the lint's own first defect. `widen` / `length_match` do
        not exist in the platform; the real names are `widen_bus_tracks` /
        `length_match_bus`. A wrong name silently redirects the AST fallback onto
        unrelated code (it matched a schematic helper `widen(block, name)` in
        01.openmv and reported it as a stale fork)."""
        src = _ROUTING.read_text(encoding="utf-8")
        for fork_file, fn in KNOWN_FORKS.items():
            with self.subTest(fork=fork_file):
                self.assertIn(f"\ndef {fn}(", src,
                              f"KNOWN_FORKS[{fork_file!r}] = {fn!r} is not a function in "
                              f"{_ROUTING.name}")

    def test_every_sentinel_owner_is_a_real_platform_function(self):
        src = _ROUTING.read_text(encoding="utf-8")
        for token, (_sha, owner, _why) in PLATFORM_SENTINELS.items():
            with self.subTest(token=token):
                self.assertIn(f"\ndef {owner}(", src,
                              f"sentinel {token!r} claims owner {owner!r}, absent from source")


class SentinelScopingTests(unittest.TestCase):
    """REGRESSION for the lint's second defect: a fork must only be judged against
    the fixes belonging to the function it forks."""

    def test_sentinels_are_scoped_to_their_owning_function(self):
        live = {t: m for t, m in PLATFORM_SENTINELS.items()}
        for_net2pcb = sentinels_for("net2pcb_board", live)
        self.assertIn("footprint_lib_unresolved", for_net2pcb)
        self.assertNotIn("vias_per_ref", for_net2pcb,
                         "vias_per_ref belongs to via_in_pad, not net2pcb_board")
        for_via = sentinels_for("via_in_pad", live)
        self.assertEqual(set(for_via), {"vias_per_ref"})

    def test_a_stale_fork_is_reported_against_only_its_own_fixes(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tools/net2pcb.py",
                   "def net2pcb_board(a, b):\n    return {'ok': True}\n")
            findings, cov = check_consumer_repo(d, platform_root=_REPO, with_coverage=True)
            d1 = [f for f in findings if f.rule == "D1"]
            self.assertEqual(len(d1), 1)
            self.assertIn("net2pcb_board", d1[0].fork_of)
            # exactly the 3 net2pcb-owned sentinels, never the other five
            self.assertIn("3/3", d1[0].message)
            self.assertNotIn("vias_per_ref", d1[0].message)
            self.assertEqual(cov.fork_files_found, 1)

    def test_a_fork_carrying_its_fixes_is_clean(self):
        """REVERSE DISCRIMINATION: an up-to-date fork must NOT be reported, else the
        lint would flag correct work and get switched off."""
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tools/net2pcb.py", (
                "def net2pcb_board(a, b):\n"
                "    footprint_lib_unresolved = []\n"
                "    dropped_components = []\n"
                "    plane_layers_applied = []\n"
                "    return {'footprint_lib_unresolved': footprint_lib_unresolved,\n"
                "            'dropped_components': dropped_components,\n"
                "            'plane_layers_applied': plane_layers_applied}\n"))
            findings = check_consumer_repo(d, platform_root=_REPO)
            self.assertEqual([f for f in findings if f.rule == "D1"], [])

    def test_fork_without_any_owned_sentinel_is_coverage_not_a_finding(self):
        """A fork of a function with no sentinel is OUR table's gap, not the
        consumer's defect. Recording it as a per-file finding put our
        incompleteness on their ledger and inflated the count (4 of 11)."""
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tools/pour.py", "def pour_planes(a):\n    return 1\n")
            findings, cov = check_consumer_repo(d, platform_root=_REPO, with_coverage=True)
            self.assertEqual([f for f in findings if f.rule in ("D1", "D2")], [],
                             "an unassessable fork must not be reported as drift")
            self.assertEqual(len(cov.forks_unassessable), 1)
            self.assertEqual(cov.forks_unassessable[0]["fork_of"], "pour_planes")


class DelegationAndSilencingTests(unittest.TestCase):

    def test_thin_wrapper_delegating_to_platform_is_not_a_fork(self):
        """This is the end-state F4(b) asks for; the lint must reward it, not
        penalise it — a delegating wrapper cannot freeze."""
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tools/net2pcb.py",
                   "from bodesign_eda_bridge import net2pcb_board\n"
                   "def net2pcb_board_cli(a, b):\n    return net2pcb_board(a, b)\n")
            findings, cov = check_consumer_repo(d, platform_root=_REPO, with_coverage=True)
            self.assertEqual(findings, [])
            self.assertEqual(cov.fork_files_found, 0)

    def test_silenced_shell_invocation_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tools/build_c04.sh",
                   '#!/bin/sh\npython3 "$TD/pour.py" "$PCB" out.kicad_pcb >/dev/null 2>&1\n')
            findings = check_consumer_repo(d, platform_root=_REPO)
            d3 = [f for f in findings if f.rule == "D3"]
            self.assertEqual(len(d3), 1)
            self.assertIn("pour.py", d3[0].message)

    def test_visible_shell_invocation_is_not_reported(self):
        """REVERSE: only the SILENCED invocation is a finding."""
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tools/build_c04.sh",
                   '#!/bin/sh\npython3 "$TD/pour.py" "$PCB" out.kicad_pcb\n')
            self.assertEqual([f for f in check_consumer_repo(d, platform_root=_REPO)
                              if f.rule == "D3"], [])


class CoverageHonestyTests(unittest.TestCase):
    """A checker that returns only findings cannot tell `clean` from `never
    scanned` — it would be an instance of the anti-pattern it enforces."""

    def test_missing_root_is_a_coverage_gap_not_a_clean_result(self):
        findings, cov = check_consumer_repo("/nonexistent/consumer/repo",
                                            platform_root=_REPO, with_coverage=True)
        self.assertEqual(findings, [])
        self.assertEqual(cov.missing_roots, ["/nonexistent/consumer/repo"])
        self.assertEqual(cov.files_scanned, 0)

    def test_cli_exits_2_on_a_coverage_gap(self):
        """A typo'd path must not exit 0 (green) with zero findings."""
        env = dict(os.environ,
                   PYTHONPATH=os.pathsep.join(str(p) for p in sorted(
                       (_REPO / "packages").glob("*/"))))
        r = subprocess.run(
            ["python3", "-m", "bodesign_workflow_core.checkers.consumer_fork_drift",
             "/nonexistent/consumer/repo", str(_REPO)],
            capture_output=True, text=True, env=env, cwd=str(_REPO))
        self.assertEqual(r.returncode, 2, f"stdout={r.stdout[-400:]}")
        self.assertIn("COVERAGE GAP", r.stdout)

    def test_cli_exits_1_when_drift_found_and_0_when_clean(self):
        env = dict(os.environ,
                   PYTHONPATH=os.pathsep.join(str(p) for p in sorted(
                       (_REPO / "packages").glob("*/"))))
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tools/net2pcb.py", "def net2pcb_board(a, b):\n    return 1\n")
            r = subprocess.run(
                ["python3", "-m", "bodesign_workflow_core.checkers.consumer_fork_drift",
                 d, str(_REPO)], capture_output=True, text=True, env=env, cwd=str(_REPO))
            self.assertEqual(r.returncode, 1, f"stdout={r.stdout[-400:]}")
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tools/unrelated.py", "def helper():\n    return 1\n")
            r = subprocess.run(
                ["python3", "-m", "bodesign_workflow_core.checkers.consumer_fork_drift",
                 d, str(_REPO)], capture_output=True, text=True, env=env, cwd=str(_REPO))
            self.assertEqual(r.returncode, 0, f"stdout={r.stdout[-400:]}")


class RealConsumerRepoTests(unittest.TestCase):
    """§7.2 item 6: the lint MUST report net2pcb.py as missing the §B fix in both
    product repos. Skipped (not silently passed) when the Google-Drive-mounted
    consumer tree is unavailable."""

    _ROOT = Path("/home/pkcs12/GoogleDrive/Projects/thesmart_products")

    def test_both_product_repos_report_the_net2pcb_regression(self):
        if not self._ROOT.is_dir():
            self.skipTest(f"consumer tree not mounted at {self._ROOT}")
        for repo in ("03.aiguard", "01.openmv"):
            with self.subTest(repo=repo):
                findings = check_consumer_repo(self._ROOT / repo, platform_root=_REPO)
                stale = [f for f in findings
                         if f.rule == "D1" and f.path.endswith("net2pcb.py")]
                self.assertTrue(stale, f"{repo}: net2pcb fork not reported as stale")
                self.assertIn("footprint_lib_unresolved", stale[0].message)


if __name__ == "__main__":
    unittest.main()
