#!/usr/bin/env python3
"""netlist_to_schematic — draw a readable, CONNECTED schematic from a netlist (the SSOT).

The netlist (KiCad `.net`) is the single source of truth for connectivity. This tool maps
it to a netlistsvg JSON and lets netlistsvg (ELK auto-layout) draw the actual circuit:
components connected by routed wires + junctions, with the analog skin rendering R/C/L as
proper symbols, per-pin GND/VCC symbols, and ICs/connectors as pinout boxes. Series
elements sit IN the wire path; parallel taps show junction dots; pull-ups go to VCC.

This is the connection-centric replacement for per-pin "label fan-out" renders (which show
no inter-component relationship — worse than a spreadsheet).

Pipeline:  KiCad .net  ->  netlistsvg JSON  ->  netlistsvg (--skin analog)  ->  SVG  ->  PNG
Deps:      node + `netlistsvg` (npm i -g netlistsvg)   ;   `cairosvg` (pip) for PNG.

Usage:
    netlist_to_schematic.py <netlist.net> <out.svg> [--png out.png] [--skin skin.svg]
"""
import re, sys, json, os, shutil, subprocess, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SKIN = os.path.join(HERE, "netlistsvg_analog_skin.svg")

def parse_netlist(path):
    t = open(path, encoding="utf-8").read()
    comps = {}
    for m in re.finditer(r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]*)"\).*?\(libsource \(lib "([^"]*)"\) \(part "([^"]*)"\)', t, re.S):
        comps[m.group(1)] = dict(value=m.group(2), lib=m.group(3), part=m.group(4))
    nets = {}
    for m in re.finditer(r'\(net \(code "?\d+"?\) \(name "([^"]+)"\)(.*?)(?=\(net |\s*\)\s*\Z)', t, re.S):
        nets[m.group(1).lstrip('/')] = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"', m.group(2))
    return comps, nets

def is_gnd(n): return n.upper().startswith(("GND", "VSS", "AGND"))
def is_pwr(n): return bool(re.match(r'(VCC|VDD|V1V8|V3V3|VSYS|SYS|VBAT|VIO|VDDA|\+|3V3|1V8)', n, re.I))

def to_netlistsvg(comps, nets, module="sch"):
    nid = [1]
    def newid(): nid[0] += 1; return nid[0]
    pinsof = {}
    for nm, nodes in nets.items():
        for r, p in nodes: pinsof.setdefault(r, []).append((p, nm))
    sigid = {nm: newid() for nm in nets if not is_gnd(nm) and not is_pwr(nm)}
    cells = {}; gc = [0]; vc = [0]
    for ref, pins in pinsof.items():
        c = comps.get(ref, {})
        rc = "r_v" if c.get("part") == "R" else ("c_v" if c.get("part") == "C" else None)
        conn = {}; pdir = {}
        for idx, (p, nm) in enumerate(sorted(pins)):
            port = (("A", "B")[min(idx, 1)] if rc else p)
            if is_gnd(nm):
                pp = newid(); g = f"GND{gc[0]}"; gc[0] += 1
                cells[g] = {"type": "gnd", "port_directions": {"A": "input"}, "connections": {"A": [pp]}}
                conn[port] = [pp]
            elif is_pwr(nm):
                pp = newid(); v = f"PWR{vc[0]}"; vc[0] += 1
                cells[v] = {"type": "vcc", "port_directions": {"A": "input"}, "connections": {"A": [pp]}}
                conn[port] = [pp]
            else:
                conn[port] = [sigid[nm]]
            pdir[port] = "input"
        cells[ref] = {"type": rc if rc else f"{ref}\n{c.get('part', ref)}", "port_directions": pdir, "connections": conn}
    netnames = {nm: {"bits": [b], "hide_name": 0} for nm, b in sigid.items()}
    return {"modules": {module: {"ports": {}, "cells": cells, "netnames": netnames}}}, len(cells), gc[0], vc[0]

def find_netlistsvg():
    for c in ("netlistsvg", os.path.expanduser("~/.cache/claude-work/nsvg/node_modules/.bin/netlistsvg")):
        if shutil.which(c) or os.path.exists(c): return shutil.which(c) or c
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist"); ap.add_argument("out_svg")
    ap.add_argument("--png"); ap.add_argument("--skin", default=DEFAULT_SKIN)
    ap.add_argument("--png-width", type=int, default=2600)
    a = ap.parse_args()
    comps, nets = parse_netlist(a.netlist)
    spec, ncells, ng, nv = to_netlistsvg(comps, nets)
    jpath = a.out_svg + ".json"
    json.dump(spec, open(jpath, "w"), indent=1)
    nsvg = find_netlistsvg()
    if not nsvg:
        sys.exit("netlistsvg not found — install: npm i -g netlistsvg")
    subprocess.run([nsvg, jpath, "-o", a.out_svg, "--skin", a.skin], check=True)
    print(f"schematic: {a.out_svg}  ({ncells} cells incl {ng} GND + {nv} VCC, {len(nets)} nets)")
    if a.png:
        if not shutil.which("cairosvg"): sys.exit("cairosvg not found — pip install cairosvg")
        subprocess.run(["cairosvg", a.out_svg, "-o", a.png, "-b", "white", "--output-width", str(a.png_width)], check=True)
        print(f"png: {a.png}")

if __name__ == "__main__":
    main()
