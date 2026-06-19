#!/usr/bin/env python3
"""netlist_to_kicad_sch — compose a HYBRID KiCad schematic from a netlist + 4-edge symbols.

Renders a real, openable .kicad_sch (KiCad's own engine draws it): chips placed as 4-edge
symbols (run symbol_4edge.py on the lib first), every pin stubbed and terminated by:
  - GND net  -> a GND power symbol (wire drawn)
  - power net -> a power symbol carrying the rail name (V1V8/V3V3/...)
  - signal/bus net -> a global net label (buses connect by matching name)
2-pin passives (R/C) are placed in a band and drawn with their terminal connections, so
decoupling (Vrail->C->GND), series R (label<->R<->label) and pull-ups (Vrail<->R<->label)
appear as visible wired networks. This is the hybrid style: discrete networks as wires,
wide buses as labels.

Render:  kicad-cli sch export svg --exclude-drawing-sheet --no-background-color -o OUT x.kicad_sch
         then cairosvg the svg to PNG (-b white) and autocrop. Top/bottom pin labels are
         emitted vertical (angle 90/270) so they don't collide.

Usage: netlist_to_kicad_sch.py <netlist.net> <out.kicad_sch>   (symbols/ resolved beside the .net)
"""
import re,sys,uuid,os
def U(): return str(uuid.uuid4())
NET=sys.argv[1]; OUT=sys.argv[2]
SYMDIR=os.path.join(os.path.dirname(os.path.dirname(NET)),"symbols")
if not os.path.isdir(SYMDIR): SYMDIR=os.path.join(os.path.dirname(NET),"..","symbols")
KS="/usr/share/kicad/symbols"
t=open(NET,encoding="utf-8").read()
comps={}
for m in re.finditer(r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]*)"\).*?\(libsource \(lib "([^"]*)"\) \(part "([^"]*)"\)', t, re.S):
    comps[m.group(1)]=dict(value=m.group(2),lib=m.group(3),part=m.group(4))
pinnet={}; nets={}
for m in re.finditer(r'\(net \(code "?\d+"?\) \(name "([^"]+)"\)(.*?)(?=\(net |\s*\)\s*\Z)', t, re.S):
    nm=m.group(1).lstrip('/'); nodes=re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"',m.group(2))
    nets[nm]=nodes
    for r,p in nodes: pinnet[(r,p)]=nm
def find_sym_file(lib,part):
    for c in [os.path.join(SYMDIR,part+".kicad_sym"),os.path.join(SYMDIR,lib+".kicad_sym"),f"{KS}/{lib}.kicad_sym"]:
        if os.path.exists(c): return c
    return None
def extract(path, want):
    s=open(path,encoding="utf-8").read()
    for m in re.finditer(r'\n\t\(symbol "([^"]+)"', s):
        nm=m.group(1)
        if want is None or nm==want or nm.split(":")[-1]==want:
            i=m.start()+1; d=0; j=i
            while j<len(s):
                if s[j]=='(':d+=1
                elif s[j]==')':
                    d-=1
                    if d==0: return s[i:j+1],nm
                j+=1
    return None,None
def pins_of(block):
    out=[]
    for pm in re.finditer(r'\(pin\b.*?\(number "(\w+)".*?\)\s*\)', block, re.S):
        b=pm.group(0); at=re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)\s+(\d+)\)',b)
        out.append((pm.group(1),float(at.group(1)),float(at.group(2)),int(at.group(3))))
    return out
# lib_symbols (use 4-edge symbols AS-IS, no re-group)
libsyms={}; ppos={}; extent={}
for ref,c in comps.items():
    key=f"{c['lib']}:{c['part']}"
    if key in libsyms: continue
    f=find_sym_file(c['lib'],c['part'])
    if not f: print("WARN no symbol",key); continue
    blk,nm=extract(f,c['part'] or None) or (None,None)
    if not blk: blk,nm=extract(f,None)
    if not blk: print("WARN extract",key); continue
    blk=re.sub(r'^\t?\(symbol "[^"]+"', f'\t(symbol "{key}"', blk, count=1)
    libsyms[key]=blk; ps=pins_of(blk)
    ppos[(c['lib'],c['part'])]={p[0]:(p[1],p[2],p[3]) for p in ps}
    xs=[p[1] for p in ps] or [0]; ys=[p[2] for p in ps] or [0]
    extent[(c['lib'],c['part'])]=(max(xs)-min(xs), max(ys)-min(ys))
for pk,pn,src in [("power:GND","GND","power"),("power:VCC","VCC","power")]:
    if pk not in libsyms:
        blk,_=extract(f"{KS}/{src}.kicad_sym",pn)
        if blk: libsyms[pk]=re.sub(r'^\t?\(symbol "[^"]+"', f'\t(symbol "{pk}"', blk, count=1)
body=[]
def wire(x1,y1,x2,y2): body.append(f'  (wire (pts (xy {x1:.2f} {y1:.2f})(xy {x2:.2f} {y2:.2f}))(stroke (width 0.1524)(type default))(uuid "{U()}"))')
def glabel(tt,x,y,a,j): body.append(f'  (global_label "{tt}" (shape bidirectional)(at {x:.2f} {y:.2f} {a})(effects (font (size 1.27 1.27))(justify {j}))(uuid "{U()}"))')
def psym(key,x,y,val,ang=0):
    body.append(f'  (symbol (lib_id "{key}")(at {x:.2f} {y:.2f} {ang})(unit 1)(in_bom no)(on_board yes)(uuid "{U()}")'
      f'(property "Reference" "#PWR" (at {x:.2f} {y:.2f} 0)(effects (font (size 1.0 1.0)) hide))'
      f'(property "Value" "{val}" (at {x:.2f} {y+(3.5 if ang==0 else -3.5):.2f} 0)(effects (font (size 1.0 1.0))))'
      f'(instances (project "s" (path "/" (reference "#PWR")(unit 1)))))')
def place(ref,key,x,y,hh=4.0):
    ry=y-(hh+9.0); vy=y+(hh+9.0); lx=x-2.0
    body.append(f'  (symbol (lib_id "{key}")(at {x:.2f} {y:.2f} 0)(unit 1)(exclude_from_sim no)(in_bom yes)(on_board yes)(dnp no)(uuid "{U()}")\n'
      f'    (property "Reference" "{ref}" (at {lx:.2f} {ry:.2f} 0)(effects (font (size 1.4 1.4))(justify left)))\n'
      f'    (property "Value" "{comps[ref]["value"]}" (at {lx:.2f} {vy:.2f} 0)(effects (font (size 1.4 1.4))(justify left)))\n'
      f'    (instances (project "s" (path "/" (reference "{ref}")(unit 1)))))')
def is_gnd(n): return n.upper() in ("GND","GNDA","AGND","VSS","VSS1") or n.upper().startswith("GND")
def is_pwr(n): return bool(re.match(r'(VCC|VDD|V1V8|V3V3|VSYS|SYS|VBAT|VIO|VDDA|\+|3V3|1V8)', n, re.I))
ICs=[r for r in comps if len(ppos.get((comps[r]["lib"],comps[r]["part"]),{}))>2]
small=[r for r in comps if r not in ICs]
placed={}; S=5.08
# place ICs spaced by their width
x=120.0; y0=140.0; gap=40.0
for ref in sorted(ICs):
    w,h=extent.get((comps[ref]["lib"],comps[ref]["part"]),(40,40))
    x+=w/2
    placed[ref]=(x,y0); place(ref,f'{comps[ref]["lib"]}:{comps[ref]["part"]}',x,y0,h/2+5.08)
    x+=w/2+gap
# small parts (R/C) in a band below
for i,ref in enumerate(sorted(small)):
    px=70.0+(i%18)*22; py=300.0+(i//18)*36; placed[ref]=(px,py); place(ref,f'{comps[ref]["lib"]}:{comps[ref]["part"]}',px,py,5.08)
for ref,(ox,oy) in placed.items():
    pos=ppos.get((comps[ref]["lib"],comps[ref]["part"]),{})
    for num,(px,py,ang) in pos.items():
        ax=ox+px; ay=oy-py; net=pinnet.get((ref,num))
        if not net: continue
        if ang==0:    ex,ey=ax-S,ay; la,j=180,"right"
        elif ang==180:ex,ey=ax+S,ay; la,j=0,"left"
        elif ang==90: ex,ey=ax,ay+S; la,j=270,"right"
        else:         ex,ey=ax,ay-S; la,j=90,"left"
        wire(ax,ay,ex,ey)
        if is_gnd(net): psym("power:GND",ex,ey,"GND",0 if ang in(90,) else 0)
        elif is_pwr(net): psym("power:VCC",ex,ey,net,0)
        else: glabel(net,ex,ey,la,j)
doc=(f'(kicad_sch (version 20250114)(generator "ai-hybrid")(generator_version "9.0")(uuid "{U()}")(paper "A1")\n'
     f'  (lib_symbols\n'+"\n".join(libsyms.values())+'\n  )\n'+"\n".join(body)+
     '\n  (sheet_instances (path "/" (page "1")))\n)\n')
open(OUT,"w",encoding="utf-8").write(doc); print("wrote",OUT,"ICs",len(ICs),"small",len(small))
