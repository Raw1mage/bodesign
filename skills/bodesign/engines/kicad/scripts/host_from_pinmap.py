#!/usr/bin/env python3
"""host_from_pinmap — build a functionally-grouped MCU symbol + host netlist from a pin-map CSV.

The big MCU is usually never drawn (subsystem netlists use header connectors as stand-ins).
This builds the missing core: reads a pin-allocation CSV (columns: subsystem, header_net,
mcu_signal, mcu_ball, ...) and emits (1) a 4-edge MCU .kicad_sym grouped by subsystem per edge
(so the bus structure reads), and (2) a host .net (U1 + decoupling caps) whose signal pins carry
the header_net names — so netlist_to_kicad_sch renders the MCU body with net labels that tie to
every subsystem schematic. Representative power balls are added + labelled honestly (real BGA
power balls are many). Edit the subsystem->edge mapping + power list for your part.

Usage: host_from_pinmap.py <Pin_Allocation.csv> <out.kicad_sym> <out.net>
"""
import csv, os, sys
CSV=sys.argv[1]; OUTSYM=sys.argv[2]; OUTNET=sys.argv[3]
rows=[r for r in csv.DictReader(open(CSV,encoding="utf-8"))]
# group by subsystem -> edge
groups={"radio":[], "memory":[], "sensors":[], "debug":[]}
for r in rows: groups.setdefault(r["subsystem"],[]).append(r)
# representative power pins (BGA power balls are many; show a representative set, honestly labelled)
power=[("VDD","VDD_P1"),("VDD","VDD_P2"),("VDDA","VDDA_P"),("VDDCORE","VCAP_P"),("VSS","VSS_P1"),("VSS","VSS_P2")]
P=3.81; LEN=5.08
# edges: LEFT=radio, RIGHT=memory, BOTTOM=sensors+debug, TOP=power
left=[(r["mcu_signal"],r["mcu_ball"] or r["header_net"]) for r in groups["radio"]]
right=[(r["mcu_signal"],r["mcu_ball"] or r["header_net"]) for r in groups["memory"]]
bottom=[(r["mcu_signal"],r["mcu_ball"] or r["header_net"]) for r in groups["sensors"]+groups["debug"]]
top=power
nL,nR,nB,nT=len(left),len(right),len(bottom),len(top)
half_h=round((max(nL,nR)/2*P+P)/1.27)*1.27
half_w=round((max(nB,nT)/2*P+15)/1.27)*1.27
pins=[]
def emit(typ,name,num,x,y,ang): pins.append(
 f'\t\t\t(pin {typ} line\n\t\t\t\t(at {x} {y} {ang})\n\t\t\t\t(length {LEN})\n'
 f'\t\t\t\t(name "{name}" (effects (font (size 1.27 1.27))))\n'
 f'\t\t\t\t(number "{num}" (effects (font (size 1.27 1.27))))\n\t\t\t)')
y0=(nL-1)/2*P
for i,(nm,no) in enumerate(left): emit("bidirectional",nm,no,round(-(half_w+LEN),2),round(y0-i*P,2),0)
y0=(nR-1)/2*P
for i,(nm,no) in enumerate(right): emit("bidirectional",nm,no,round(half_w+LEN,2),round(y0-i*P,2),180)
x0=-(nB-1)/2*P
for i,(nm,no) in enumerate(bottom): emit("bidirectional",nm,no,round(x0+i*P,2),round(-(half_h+LEN),2),90)
x0=-(nT-1)/2*P
for i,(nm,no) in enumerate(top): emit(("power_in" if nm!="VSS" else "power_in"),nm,no,round(x0-i*P,2),round(half_h+LEN,2),270)
sym=f'''(kicad_symbol_lib
\t(version 20241209)
\t(generator "bodesign")
\t(symbol "STM32N657"
\t\t(exclude_from_sim no)(in_bom yes)(on_board yes)
\t\t(property "Reference" "U" (at {-half_w} {half_h+8} 0)(effects (font (size 1.27 1.27))))
\t\t(property "Value" "STM32N657L0" (at {-half_w} {-half_h-8} 0)(effects (font (size 1.27 1.27))))
\t\t(property "Footprint" "" (at 0 0 0)(effects (font (size 1.27 1.27))(hide yes)))
\t\t(property "Datasheet" "STM32N657 datasheet (ball map per Pin_Allocation.csv)" (at 0 0 0)(effects (font (size 1.27 1.27))(hide yes)))
\t\t(symbol "STM32N657_0_1"
\t\t\t(rectangle (start {-half_w} {half_h})(end {half_w} {-half_h})(stroke (width 0.254)(type default))(fill (type background))))
\t\t(symbol "STM32N657_1_1"
{chr(10).join(pins)}
\t\t)
\t)
)
'''
open(OUTSYM,"w",encoding="utf-8").write(sym)
# host netlist: U1 + decoupling caps; each signal pin -> net (header_net); power balls -> rails
nl=['(export (version "E")','  (components']
nl.append('    (comp (ref "U1") (value "STM32N657L0") (libsource (lib "stm32") (part "STM32N657")))')
caps=[("C1","100nF"),("C2","100nF"),("C3","100nF"),("C4","100nF"),("C5","4u7"),("C6","1uF")]
for ref,val in caps: nl.append(f'    (comp (ref "{ref}") (value "{val}") (libsource (lib "Device") (part "C")))')
nl.append('  )')
nl.append('  (nets')
code=1
def net(name,nodes):
    global code
    s=f'    (net (code "{code}") (name "{name}")'
    for r,p in nodes: s+=f'(node (ref "{r}") (pin "{p}"))'
    s+=')'; code+=1; nl.append(s)
# signal nets: pin number=ball ; net name = header_net (ties to subsystems)
for r in rows:
    ball=r["mcu_ball"] or r["header_net"]
    net(r["header_net"], [("U1",ball)])
# power: VDD pins -> V3V3, VDDA->VDDA, VDDCORE->V1V8(core cap), VSS->GND, with decoupling caps
net("V3V3",[("U1","VDD_P1"),("U1","VDD_P2"),("C1","1"),("C2","1"),("C6","1")])
net("VDDA",[("U1","VDDA_P"),("C3","1")])
net("V1V8",[("U1","VCAP_P"),("C4","1"),("C5","1")])
net("GND",[("U1","VSS_P1"),("U1","VSS_P2"),("C1","2"),("C2","2"),("C3","2"),("C4","2"),("C5","2"),("C6","2")])
nl.append('  )')
nl.append(')')
open(OUTNET,"w",encoding="utf-8").write("\n".join(nl))
print(f"symbol pins L/R/B/T={nL}/{nR}/{nB}/{nT}, body {2*half_w:.0f}x{2*half_h:.0f}mm; netlist {len(rows)} signals + power")
