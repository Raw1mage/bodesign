"""Unit tests for Adapter Parity (Task 2.3 / AC9).

Drives the ACTUAL existing MCP handler path (services.mcp.server.run_tool) and
the landing runner (skills/bodesign/scripts/gate.py) on identical pinned inputs
for named use-case populations (readability_gate and verify_netlist_fidelity).

Verifies:
- Domain result parity on identical pinned inputs.
- Documented transport envelopes and exit-code mapping.
- No mocked transports (actual MCP dispatch and actual subprocess execution).
- Successful cases, refusal cases, and no-verdict (empty/not-run) cases.
- Mapping to unified OperationOutcome contract via rebuild_compat.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from services.mcp.server import run_tool
from bodesign_workflow_core.rebuild_compat import wrap_operation_outcome


REPO_ROOT = Path(__file__).resolve().parent.parent
GATE_PY = REPO_ROOT / "skills" / "bodesign" / "scripts" / "gate.py"

# Strict XDG scratch placement (no /tmp)
SCRATCH_BASE = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "scratch" / "rebuild-parity"


def _build_net_content(nets: dict[str, list[tuple[str, str]]]) -> str:
    """Generate a minimal valid KiCad .net export containing the given nets."""
    blocks = []
    for i, (name, nodes) in enumerate(nets.items(), start=1):
        node_lines = "\n".join(
            f'      (node (ref "{r}") (pin "{p}") (pintype "passive"))'
            for r, p in nodes
        )
        blocks.append(
            f'    (net (code "{i}") (name "{name}") (class "Default")\n{node_lines})'
        )
    return '(export (version "E")\n  (nets\n' + "\n".join(blocks) + "))\n"


def _run_gate_subprocess(verb: str, args: dict) -> tuple[dict, int, str]:
    """Execute gate.py via actual subprocess with --repo and --json arguments."""
    cmd = [
        sys.executable,
        str(GATE_PY),
        verb,
        "--repo",
        str(REPO_ROOT),
        "--json",
        json.dumps(args),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # Parse last stdout line as JSON
    stdout_lines = [line.strip() for line in proc.stdout.strip().splitlines() if line.strip()]
    json_line = stdout_lines[-1] if stdout_lines else "{}"
    try:
        parsed = json.loads(json_line)
    except json.JSONDecodeError:
        parsed = {"raw_stdout": proc.stdout, "raw_stderr": proc.stderr}
    return parsed, proc.returncode, proc.stderr


class TestReadabilityGateAdapterParity(unittest.TestCase):
    """Parity tests for readability_gate (form-axis gate)."""

    def test_readability_gate_success_parity(self):
        pinned_args = {
            "route_stats": {
                "wired_nets": 10,
                "labelled_nets": 0,
                "drawn_subcircuits": 10,
                "anti_fusion_downgrades": 0,
                "junctions": 25,
                "stub_share": 0.1,
            },
            "n": 5,
        }

        # 1. MCP handler path
        mcp_res = run_tool("bodesign_readability_gate", pinned_args)
        self.assertTrue(mcp_res.get("ok"), mcp_res)
        self.assertEqual(mcp_res.get("result_status"), "ok")
        mcp_domain = mcp_res["result"]

        # 2. Gate runner subprocess path
        gate_res, gate_rc, stderr = _run_gate_subprocess("readability_gate", pinned_args)
        self.assertEqual(gate_rc, 0, f"gate.py failed with rc={gate_rc}, stderr={stderr}")
        self.assertTrue(gate_res.get("ok"))
        self.assertEqual(gate_res.get("status"), "ok")
        gate_domain = gate_res["result"]

        # Domain result parity: exact match
        self.assertEqual(mcp_domain, gate_domain)

        # Wrap into unified OperationOutcome
        outcome_mcp = wrap_operation_outcome(mcp_res, module="A3")
        outcome_gate = wrap_operation_outcome(gate_res, module="A3")
        self.assertEqual(outcome_mcp.outcome, "ok")
        self.assertEqual(outcome_gate.outcome, "ok")

    def test_readability_gate_refusal_parity(self):
        # Missing both spec and n: caller error refusal
        pinned_args = {}

        # 1. MCP handler path
        mcp_res = run_tool("bodesign_readability_gate", pinned_args)
        self.assertTrue(mcp_res.get("ok"))
        mcp_inner = mcp_res["result"]
        self.assertFalse(mcp_inner.get("ok"))
        self.assertEqual(mcp_inner["error"]["code"], "READABILITY_ARGS_INVALID")

        # 2. Gate runner subprocess path
        gate_res, gate_rc, _ = _run_gate_subprocess("readability_gate", pinned_args)
        self.assertEqual(gate_rc, 1)  # Refusal maps to exit code 1
        self.assertFalse(gate_res.get("ok"))
        self.assertEqual(gate_res["error"]["code"], "READABILITY_ARGS_INVALID")

        # Error code parity
        self.assertEqual(mcp_inner["error"]["code"], gate_res["error"]["code"])

    def test_readability_gate_empty_no_verdict_parity(self):
        # Zero nets: legitimate empty subject (not a failure)
        pinned_args = {
            "route_stats": {
                "wired_nets": 0,
                "labelled_nets": 0,
                "drawn_subcircuits": 0,
                "anti_fusion_downgrades": 0,
                "stub_share": None,
            },
            "n": 0,
        }

        # 1. MCP handler path
        mcp_res = run_tool("bodesign_readability_gate", pinned_args)
        self.assertTrue(mcp_res.get("ok"))
        self.assertEqual(mcp_res.get("result_status"), "empty")
        mcp_domain = mcp_res["result"]

        # 2. Gate runner subprocess path
        gate_res, gate_rc, _ = _run_gate_subprocess("readability_gate", pinned_args)
        self.assertEqual(gate_rc, 2)  # Empty maps to exit code 2
        self.assertFalse(gate_res.get("ok"))
        self.assertEqual(gate_res.get("status"), "empty")
        gate_domain = gate_res["result"]

        # Domain result parity
        self.assertEqual(mcp_domain, gate_domain)

        # Unified outcome mapping
        outcome_mcp = wrap_operation_outcome(mcp_res, module="A3")
        outcome_gate = wrap_operation_outcome(gate_res, module="A3")
        self.assertEqual(outcome_mcp.outcome, "empty")
        self.assertEqual(outcome_gate.outcome, "empty")


class TestVerifyNetlistFidelityAdapterParity(unittest.TestCase):
    """Parity tests for verify_netlist_fidelity (electrical-axis gate)."""

    def setUp(self):
        SCRATCH_BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.work_dir = Path(tempfile.mkdtemp(prefix="fidelity-parity-", dir=SCRATCH_BASE))

    def tearDown(self):
        shutil.rmtree(self.work_dir, ignore_errors=True)

    def test_fidelity_success_parity(self):
        # Create matching .net export
        net_content = _build_net_content({
            "N1": [("U1", "1"), ("R1", "1")],
            "N2": [("U1", "2"), ("R2", "1")],
        })
        net_file = self.work_dir / "matching.net"
        net_file.write_text(net_content, encoding="utf-8")

        pinned_args = {
            "spec": {
                "N1": [["U1", "1"], ["R1", "1"]],
                "N2": [["U1", "2"], ["R2", "1"]],
            },
            "emitted": [str(net_file)],
        }

        # 1. MCP handler path
        mcp_res = run_tool("bodesign_verify_netlist_fidelity", pinned_args)
        self.assertTrue(mcp_res.get("ok"), mcp_res)
        self.assertEqual(mcp_res.get("result_status"), "ok")
        mcp_domain = mcp_res["result"]

        # 2. Gate runner subprocess path
        gate_res, gate_rc, stderr = _run_gate_subprocess("verify_netlist_fidelity", pinned_args)
        self.assertEqual(gate_rc, 0, f"gate.py failed with rc={gate_rc}, stderr={stderr}")
        self.assertTrue(gate_res.get("ok"))
        self.assertEqual(gate_res.get("status"), "ok")
        gate_domain = gate_res["result"]

        # Domain result parity: exact match
        self.assertEqual(mcp_domain, gate_domain)

        # Unified outcome mapping
        outcome_mcp = wrap_operation_outcome(mcp_res, module="A3")
        outcome_gate = wrap_operation_outcome(gate_res, module="A3")
        self.assertEqual(outcome_mcp.outcome, "ok")
        self.assertEqual(outcome_gate.outcome, "ok")

    def test_fidelity_refusal_missing_netlist_parity(self):
        # Refusal when named file does not exist on disk
        missing_path = str(self.work_dir / "nonexistent_board_fidelity.net")
        pinned_args = {
            "spec": {"N1": [["U1", "1"], ["R1", "1"]]},
            "emitted": [missing_path],
        }

        # 1. MCP handler path
        mcp_res = run_tool("bodesign_verify_netlist_fidelity", pinned_args)
        self.assertTrue(mcp_res.get("ok"))
        mcp_inner = mcp_res["result"]
        self.assertFalse(mcp_inner.get("ok"))
        self.assertEqual(mcp_inner["error"]["code"], "NETLIST_MISSING")

        # 2. Gate runner subprocess path
        gate_res, gate_rc, _ = _run_gate_subprocess("verify_netlist_fidelity", pinned_args)
        self.assertEqual(gate_rc, 1)  # Refusal maps to exit code 1
        self.assertFalse(gate_res.get("ok"))
        self.assertEqual(gate_res["error"]["code"], "NETLIST_MISSING")

        # Error code parity
        self.assertEqual(mcp_inner["error"]["code"], gate_res["error"]["code"])

    def test_fidelity_not_run_no_verdict_parity(self):
        # Empty spec and emitted: not-run outcome (precondition unmet before comparison)
        pinned_args = {
            "spec": {},
            "emitted": [],
        }

        # 1. MCP handler path
        mcp_res = run_tool("bodesign_verify_netlist_fidelity", pinned_args)
        self.assertTrue(mcp_res.get("ok"))
        self.assertEqual(mcp_res.get("result_status"), "not-run")
        mcp_domain = mcp_res["result"]

        # 2. Gate runner subprocess path
        gate_res, gate_rc, _ = _run_gate_subprocess("verify_netlist_fidelity", pinned_args)
        self.assertEqual(gate_rc, 2)  # not-run maps to exit code 2
        self.assertFalse(gate_res.get("ok"))
        self.assertEqual(gate_res.get("status"), "not-run")
        gate_domain = gate_res["result"]

        # Domain result parity
        self.assertEqual(mcp_domain, gate_domain)

        # Unified outcome mapping
        outcome_mcp = wrap_operation_outcome(mcp_res, module="A3")
        outcome_gate = wrap_operation_outcome(gate_res, module="A3")
        self.assertEqual(outcome_mcp.outcome, "not-run")
        self.assertEqual(outcome_gate.outcome, "not-run")


if __name__ == "__main__":
    unittest.main()
