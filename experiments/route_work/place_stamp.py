import pcbnew, sys
IN="/work/experiments/route_work/ccm.kicad_pcb"
OUT="/work/experiments/route_work/ccm.stamp.kicad_pcb"
b=pcbnew.LoadBoard(IN)          # 一個程序只做這一次 LoadBoard
if b is None or not hasattr(b,"GetFootprints"):
    print("FLAKY_BOARD"); sys.exit(3)
fps=list(b.GetFootprints())
if not fps or not all(hasattr(f,"GetReference") for f in fps):
    print("FLAKY_FP"); sys.exit(4)   # 巢狀 cast 也退化 → 讓 shell 重啟新程序

def V(x,y): return pcbnew.VECTOR2I(int(x*1e6),int(y*1e6))

# 1. 抓 J_B2B pin->net 後移除
b2b=None; pinnet={}
for fp in fps:
    if fp.GetReference()=="J_B2B":
        b2b=fp
        for p in fp.Pads():
            if p.GetNetCode()>0: pinnet[int(p.GetPadName())]=p.GetNetname()
b.Remove(b2b)
used=sorted(pinnet)

# 2. 縮板框 36x32
BW,BH=36.0,32.0
for d in list(b.GetDrawings()):
    if d.GetLayer()==pcbnew.Edge_Cuts: b.Remove(d)
def edge(x1,y1,x2,y2):
    s=pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(V(x1,y1)); s.SetEnd(V(x2,y2)); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(int(0.15*1e6)); b.Add(s)
edge(0,0,BW,0); edge(BW,0,BW,BH); edge(BW,BH,0,BH); edge(0,BH,0,0)

# 3. 三面環繞佈局 (U1 置中)
place={"U1":(12,12,0),"U3":(26,13,0),"U2":(11,24,0),"U5":(18.5,25,0),
       "U6":(21.5,25,0),"U7":(25,25,0),"U8":(28.5,25,0)}
for fp in b.GetFootprints():
    r=fp.GetReference()
    if r in place:
        x,y,rot=place[r]; fp.SetPosition(V(x,y)); fp.SetOrientationDegrees(rot)
        ref=fp.Reference(); ref.SetTextSize(V(1.1,1.1)); ref.SetTextThickness(int(0.18*1e6)); ref.SetVisible(True)

# 4. castellated 三面 28 腳 (左10/下8/右10) 承接 J_B2B net
mod=pcbnew.FOOTPRINT(b); mod.SetReference("J_STAMP"); mod.SetPosition(V(0,0)); mod.Reference().SetVisible(False)
P=1.27; pins=[]
n=10; y0=BH/2-(n-1)*P/2
for i in range(n): pins.append((0.0,y0+i*P))
n=8; x0=BW/2-(n-1)*P/2
for i in range(n): pins.append((x0+i*P,BH))
n=10; y0=BH/2+(n-1)*P/2
for i in range(n): pins.append((BW,y0-i*P))
for k,(px,py) in zip(used,pins):
    pad=pcbnew.PAD(mod); pad.SetNumber(str(k)); pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
    pad.SetShape(pcbnew.PAD_SHAPE_OVAL); pad.SetSize(V(1.0,1.7)); pad.SetDrillSize(V(0.6,0.6))
    pad.SetPosition(V(px,py)); pad.SetLayerSet(pad.PTHMask())
    ni=b.FindNet(pinnet[k])
    if ni: pad.SetNet(ni)
    mod.Add(pad)
b.Add(mod)

pcbnew.SaveBoard(OUT,b)
box=b.GetBoardEdgesBoundingBox()
print("SAVED BOARD %.1f x %.1f castellated=%d"%(box.GetWidth()/1e6,box.GetHeight()/1e6,len(pins)))
