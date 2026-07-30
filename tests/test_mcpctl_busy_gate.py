"""BR_20260729 §L — mcpctl.sh must refuse to destroy work in flight.

restart/rebuild/stop recreate the containers, killing everything inside them.
A freerouting run on a real BGA board takes 30-165 minutes. Before this gate,
a restart during one destroyed it and then printed "bodesign MCP restarted" —
reporting the outcome the command intended rather than the one it produced.
That is the silent-degradation shape this repo lints for in Python, one layer
down in ops.

These tests drive the real script with a stub `docker` on PATH, so they assert
the shipped control flow rather than a re-implementation of it.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MCPCTL = REPO / "mcpctl.sh"

# Fixtures mimic `ps -eo pid,stat,etimes,args --no-headers` — the exact column
# set busy_report asks for. TestPsFixturesMatchTheScript below asserts that
# correspondence, because a fixture is a hand-copy of the script's ps spec: when
# the STAT column was added for zombie detection, these fixtures still carried
# the old 3-column shape, awk silently read etimes as STAT and args as etimes,
# and six tests failed with confusing rc mismatches instead of "your fixture is
# the wrong shape". Same V4-c duplicate-fact defect this repo lints for.
#
# What a busy ee worker looks like: the server at pid 1 plus a long-running route.
PS_BUSY = "    1 Ssl  3600 python /app/services/mcp/server.py --tools ee\n  402 Sl   1800 java -jar /opt/freerouting.jar -de board.dsn -do out.ses -mp 40"
# Idle: only the server itself. Its age is irrelevant — it is not "work".
PS_IDLE = "    1 Ssl  3600 python /app/services/mcp/server.py --tools ee"
# A just-started helper: younger than the threshold, not worth blocking on.
PS_YOUNG = "    1 Ssl  3600 python /app/services/mcp/server.py --tools ee\n  402 S       3 sh -c echo hello"
# BR_20260730b §M: xvfb-run leaks a defunct Xvfb per freerouting run. These are
# ALREADY DEAD — no CPU, no memory, nothing a restart could destroy — but their
# etimes keeps climbing, so the original gate read three 12-hour-old corpses as
# live work and refused every restart forever.
PS_ZOMBIE = (
    "    1 Ssl  3600 python /app/services/mcp/server.py --tools ee\n"
    "  399 Z   43512 [Xvfb] <defunct>\n"
    " 3322 Z   40797 [Xvfb] <defunct>"
)
# A zombie does not launder a real job sitting next to it.
PS_ZOMBIE_PLUS_LIVE = (
    "    1 Ssl  3600 python /app/services/mcp/server.py --tools ee\n"
    "  399 Z   43512 [Xvfb] <defunct>\n"
    "  402 Sl   1800 java -jar /opt/freerouting.jar -de board.dsn -do out.ses -mp 40"
)


class _Harness:
    """Run mcpctl.sh against a stubbed `docker`, capturing what it would do."""

    def __init__(self, ps_output: str, *, ps_rc: int = 0, running: str = "true"):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir(parents=True)
        self.marker = Path(self.tmp.name) / "compose-was-called"
        stub = self.bin / "docker"
        stub.write_text(
            textwrap.dedent(
                f"""\
                #!/usr/bin/env bash
                # `docker compose ...` — record that a destructive action got through.
                if [ "$1" = "compose" ]; then
                  echo "compose $*" >> {self.marker}
                  exit 0
                fi
                if [ "$1" = "inspect" ]; then
                  echo {running}
                  exit 0
                fi
                if [ "$1" = "exec" ]; then
                  cat <<'PSEOF'
{ps_output}
PSEOF
                  exit {ps_rc}
                fi
                exit 0
                """
            )
        )
        stub.chmod(0o755)
        # `tee` is used by build paths; keep the real one reachable.
        self.env = dict(os.environ)
        self.env["PATH"] = f"{self.bin}:{self.env['PATH']}"

    def run(self, *args: str, **extra_env: str) -> subprocess.CompletedProcess:
        env = dict(self.env)
        env.update(extra_env)
        return subprocess.run(
            [str(MCPCTL), *args],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    @property
    def compose_ran(self) -> bool:
        return self.marker.exists()

    def close(self) -> None:
        self.tmp.cleanup()


class TestBusyGate(unittest.TestCase):
    def tearDown(self) -> None:
        h = getattr(self, "_h", None)
        if h is not None:
            h.close()

    def _harness(self, *a, **kw) -> _Harness:
        self._h = _Harness(*a, **kw)
        return self._h

    # -- refusal -----------------------------------------------------------

    def test_restart_refuses_while_a_route_is_running(self):
        h = self._harness(PS_BUSY)
        r = h.run("restart")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("REFUSING to restart", r.stderr)
        self.assertFalse(
            h.compose_ran,
            "restart reached docker compose despite a busy worker — the gate is decorative",
        )

    def test_rebuild_and_stop_are_gated_too(self):
        # The original incident was a restart, but rebuild and stop recreate or
        # remove the same containers. Gating only the one we happened to hit
        # would leave the other two as unguarded paths to the same loss.
        for action in ("rebuild", "stop"):
            with self.subTest(action=action):
                h = self._harness(PS_BUSY)
                r = h.run(action)
                self.assertEqual(r.returncode, 3, r.stderr)
                self.assertFalse(h.compose_ran)
                h.close()
                self._h = None

    def test_refusal_names_the_process_it_protected(self):
        # "Busy, try later" would force the caller to go find out what is
        # running. The command already knows; it must say.
        h = self._harness(PS_BUSY)
        r = h.run("restart")
        self.assertIn("freerouting", r.stderr)
        self.assertIn("402", r.stderr)
        self.assertIn("BODESIGN_FORCE=1", r.stderr, "refusal must state its own override")

    # -- passage (reverse discrimination) ----------------------------------
    #
    # Without these, a gate that refuses unconditionally would pass every
    # refusal test above and make the tool unusable.

    def test_idle_workers_do_not_block(self):
        h = self._harness(PS_IDLE)
        r = h.run("restart")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(h.compose_ran, "an idle worker must not block a restart")

    def test_server_process_itself_is_not_work_in_flight(self):
        # pid 1 is the MCP server, always old, always there. Counting it would
        # make the gate permanently closed.
        h = self._harness(PS_IDLE)
        r = h.run("busy")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("idle", r.stdout)

    def test_a_process_younger_than_the_threshold_does_not_block(self):
        h = self._harness(PS_YOUNG)
        r = h.run("restart")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(h.compose_ran)

    def test_stopped_containers_are_genuinely_idle(self):
        h = self._harness(PS_BUSY, running="false")
        r = h.run("restart")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(h.compose_ran)

    # -- the failure mode this whole BR line is about ----------------------

    def test_an_unprobeable_container_blocks_rather_than_reads_as_idle(self):
        # `docker exec` failing means we could not look. Treating that as "no
        # processes found" would turn every probe outage into a green light to
        # destroy work — the same silent degradation the gate exists to stop.
        h = self._harness("Error response from daemon: container not running", ps_rc=1)
        r = h.run("restart")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("UNKNOWN", r.stderr)
        self.assertFalse(h.compose_ran)

    def test_unknown_state_is_reported_as_unknown_not_as_busy(self):
        # It must not claim to have found a running job it never saw.
        h = self._harness("Error response from daemon: no such container", ps_rc=1)
        r = h.run("busy")
        self.assertEqual(r.returncode, 3)
        self.assertIn("UNKNOWN", r.stdout)
        self.assertNotIn("\tBUSY\t", r.stdout)

    # -- override ----------------------------------------------------------

    def test_force_proceeds_but_says_what_it_is_killing(self):
        h = self._harness(PS_BUSY)
        r = h.run("restart", BODESIGN_FORCE="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(h.compose_ran, "the override must actually override")
        self.assertIn("WARNING", r.stderr)
        self.assertIn("freerouting", r.stderr, "an override must still name the casualty")

    # -- query without side effects ---------------------------------------

    def test_busy_subcommand_never_touches_the_containers(self):
        # A peer session sharing these workers needs to ask "is it safe?"
        # without any chance of the asking itself causing a restart.
        for ps, expected_rc in ((PS_BUSY, 3), (PS_IDLE, 0)):
            with self.subTest(rc=expected_rc):
                h = self._harness(ps)
                r = h.run("busy")
                self.assertEqual(r.returncode, expected_rc, r.stderr)
                self.assertFalse(h.compose_ran)
                h.close()
                self._h = None


class TestZombiesAreNotWork(unittest.TestCase):
    """BR_20260730b §M — a defunct process must not hold the gate shut forever.

    xvfb-run leaks one defunct Xvfb per freerouting run. A zombie has already
    exited: no CPU, no memory, nothing a restart could destroy. But its etimes
    keeps climbing, so the age-based gate read three 12-hour-old corpses as live
    work and refused every restart INDEFINITELY — with no run to protect.

    That inverts the gate's own contract, and its failure mode was worse than
    the inconvenience: the only way out is BODESIGN_FORCE=1, so a permanently
    stuck gate trains the operator to reach for the override reflexively — the
    guard teaches people to disarm it. These tests pin both directions.
    """

    def tearDown(self) -> None:
        h = getattr(self, "_h", None)
        if h is not None:
            h.close()

    def _harness(self, *a, **kw) -> _Harness:
        self._h = _Harness(*a, **kw)
        return self._h

    def test_zombies_alone_do_not_block_a_restart(self):
        h = self._harness(PS_ZOMBIE)
        r = h.run("restart")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(
            h.compose_ran,
            "a container holding only defunct processes is idle — blocking it "
            "means the gate can never reopen without BODESIGN_FORCE=1",
        )

    def test_busy_still_reports_zombies_so_a_leak_stays_visible(self):
        # Filtering them out silently would hide the fact that xvfb-run is not
        # reaping its children — a real defect worth seeing, just not one that
        # should block a restart. Report, do not block.
        h = self._harness(PS_ZOMBIE)
        r = h.run("busy")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ZOMBIE", r.stdout)
        self.assertIn("399", r.stdout, "a reported zombie must name its pid")
        self.assertNotIn("\tBUSY\t", r.stdout, "a corpse must not be labelled BUSY")

    def test_a_zombie_does_not_launder_a_live_job_beside_it(self):
        # THE reverse-discrimination test for this fix. If the zombie rule were
        # written as "any zombie present => idle", this passes a restart straight
        # through a running 165-minute route. The classification must be
        # per-process, not per-container.
        h = self._harness(PS_ZOMBIE_PLUS_LIVE)
        r = h.run("restart")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertFalse(h.compose_ran)
        self.assertIn("freerouting", r.stderr, "the live job must still be named")

    def test_the_refusal_text_explains_the_zombie_class(self):
        # A caller who sees ZOMBIE rows from `busy` and then a refusal needs to
        # know which rows caused it.
        h = self._harness(PS_ZOMBIE_PLUS_LIVE)
        r = h.run("restart")
        self.assertIn("ZOMBIE", r.stderr)
        self.assertIn("NEVER blocks", r.stderr)


class TestPsFixturesMatchTheScript(unittest.TestCase):
    """The fixtures above are a hand-copy of the script's `ps -eo` column spec.

    That duplication is the V4-c defect this repo lints for: when STAT was added
    for zombie detection, the fixtures still carried the old 3-column shape, awk
    read etimes as STAT and args as etimes, and six tests failed with confusing
    rc mismatches rather than "your fixture has the wrong number of columns".
    Derive the expected shape from the script instead of trusting the copy.
    """

    def test_fixture_columns_match_the_ps_spec_the_script_asks_for(self):
        import re

        src = MCPCTL.read_text()
        m = re.search(r"ps -eo ([a-z,]+) --no-headers", src)
        self.assertIsNotNone(m, "could not find the ps spec in mcpctl.sh")
        cols = m.group(1).split(",")
        self.assertEqual(
            cols[:3],
            ["pid", "stat", "etimes"],
            "busy_report's awk indexes $1=pid $2=stat $3=etimes; if the script's "
            "column order changed, every fixture below is now misaligned",
        )
        # Every fixture line must carry at least as many fields as the script
        # asks for, or awk silently shifts columns.
        for name, fixture in (
            ("PS_BUSY", PS_BUSY),
            ("PS_IDLE", PS_IDLE),
            ("PS_YOUNG", PS_YOUNG),
            ("PS_ZOMBIE", PS_ZOMBIE),
            ("PS_ZOMBIE_PLUS_LIVE", PS_ZOMBIE_PLUS_LIVE),
        ):
            for line in fixture.splitlines():
                with self.subTest(fixture=name, line=line):
                    fields = line.split()
                    self.assertGreaterEqual(
                        len(fields), len(cols),
                        f"{name} row has {len(fields)} fields but the script asks "
                        f"for {len(cols)} ({m.group(1)}) — awk will misread it",
                    )
                    self.assertRegex(
                        fields[1], r"^[A-Za-z<>+sl]+$",
                        f"{name} field 2 must be a ps STAT code (script column "
                        f"order: {m.group(1)})",
                    )
                    self.assertRegex(
                        fields[2], r"^\d+$",
                        f"{name} field 3 must be etimes seconds",
                    )


class TestGateIsWiredToEveryDestructiveAction(unittest.TestCase):
    """Guard the wiring itself, so a future subcommand cannot quietly skip it.

    The behavioural tests above only cover the actions that exist today. This
    one fails when a new destructive case appears without a guard, rather than
    waiting for someone to lose a route to it.
    """

    def test_every_compose_recreating_case_calls_guard_busy(self):
        import re

        src = MCPCTL.read_text()
        body = src.split("case \"${1:-}\" in", 1)[1]
        # Split into case arms: `  <pattern>)` at the start of a line.
        arms = re.split(r"\n  (?=[a-z|]+\))", body)
        destructive = []
        for arm in arms:
            head = arm.split(")", 1)[0].strip()
            if not head or head == "*":
                continue
            recreates = "--force-recreate" in arm or "compose[@]}\" down" in arm
            if recreates:
                destructive.append((head, "guard_busy" in arm))
        self.assertTrue(destructive, "found no destructive arms — parser is broken")
        unguarded = [name for name, guarded in destructive if not guarded]
        self.assertEqual(
            unguarded,
            [],
            f"these mcpctl actions destroy containers without a busy check: {unguarded}",
        )

    def test_the_wiring_check_can_actually_fail(self):
        # Reverse discrimination for the AST-ish check above: if the parser
        # silently matched nothing, the assertion would pass forever.
        import re

        src = MCPCTL.read_text().replace("    guard_busy restart\n", "")
        body = src.split("case \"${1:-}\" in", 1)[1]
        arms = re.split(r"\n  (?=[a-z|]+\))", body)
        unguarded = [
            arm.split(")", 1)[0].strip()
            for arm in arms
            if ("--force-recreate" in arm or "compose[@]}\" down" in arm)
            and "guard_busy" not in arm
        ]
        self.assertIn(
            "restart",
            unguarded,
            "removing restart's guard did not trip the check — it has no discriminating power",
        )


if __name__ == "__main__":
    unittest.main()
