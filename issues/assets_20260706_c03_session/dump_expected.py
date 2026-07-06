"""Dump gen_ccm.py's merged ccm_nets as the authoritative expected partition.

gen_ccm.py builds ccm_nets from pure data (ball reverse-map + explicit net()
calls + merge_same), then calls compose_schematic as a side effect. We import it
as a module so the net-building code runs, capture ccm_nets BEFORE trusting any
.net file, and dump {net_name: sorted(nodes)}. This is the electrical SSOT — the
.kicad_sch union must reproduce the SAME node->partition-class map.

Run inside container:  PYTHONPATH=/tmp/engpatch python3 /tmp/dump_expected.py
"""
import json
import runpy
import sys

FB = "/work/aiguard/C03-EE/full_board"

# runpy executes gen_ccm.py in a fresh namespace and returns its globals, giving
# us ccm_nets after all net() + merge_same processing (and its compose call).
ns = runpy.run_path(f"{FB}/gen_ccm.py")
ccm_nets = ns["ccm_nets"]

expected = {}
for n in ccm_nets:
    expected[n["name"]] = sorted(set(n["nodes"]))

json.dump(expected, open("/tmp/ccm_expected_partition.json", "w"), indent=0)
print("EXPECTED_NETS", len(expected))
print("HSE_IN_nodes", expected.get("HSE_IN"))
print("HSE_OUT_nodes", expected.get("HSE_OUT"))
print("GND_nodecount", len(expected.get("GND", [])))
print("total_nodes", sum(len(v) for v in expected.values()))
