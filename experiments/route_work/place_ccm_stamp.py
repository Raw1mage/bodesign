import pcbnew, math
IN="/work/experiments/route_work/ccm.kicad_pcb"
OUT="/work/experiments/route_work/ccm.stamp.kicad_pcb"
b=pcbnew.LoadBoard(IN)
assert hasattr(b,"GetFootprints"),"FLAKY_CAST"
def V(x,y): return pcbnew.VECTOR2I(int(x*1e6),int(y*1e6))

# --- 1. 抓 J_B2B pin -> netname, 然後移除 J_B2B ---
b2b=None; pinnet={}
for fp in b.GetFootprints():
    if fp.GetReference()=="J_B2B":
        b2b=fp
        for p in fp.Pads():
            nc=p.GetNetCode()
            if nc>0: pinnet[int(p.GetPadName())]=p.GetNetname()
assert b2b is not None
b.Remove(b2b)
used=sorted(pinnet)  # 28 pins with net
print("castellated 接腳數:",len(used))

# --- 2. 重畫板框 Edge.Cuts 成 36 x 32 ---
BW,BH=36.0,32.0
for d in list(b.GetDrawings()):
    if d.GetLayer()==pcbnew.Edge_Cuts: b.Remove(d)
def edge(x1,y1,x2,y2):
    s=pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(V(x1,y1)); s.SetEnd(V(x2,y2))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(int(0.15*1e6)); b.Add(s)
edge(0,0,BW,0); edge(BW,0,BW,BH); edge(BW,BH,0,BH); edge(0,BH,0,0)

# --- 3. 搬元件到 castellated 三面環繞佈局 (中央主晶片) ---
place={  # ref:(x,y,rot)
 "U1":(12,12,0),   # STM32N657 主晶片, 中央
 "U3":(26,13,0),   # Octal Flash (最大件), 右
 "U2":(11,24,0),   # PSRAM, 左下
 "U5":(18.5,25,0), # 3V3 buck
 "U6":(21.5,25,0), # 1V8 buck
 "U7":(25,25,0),   # VDDA LDO
 "U8":(28.5,25,0), # backup LDO
}
for fp in b.GetFootprints():
    r=fp.GetReference()
    if r in place:
        x,y,rot=place[r]
        fp.SetPosition(V(x,y))
        fp.SetOrientationDegrees(rot)
        # 放大 refdes 絲印便於審圖
        ref=fp.Reference()
        ref.SetTextSize(V(1.1,1.1)); ref.SetTextThickness(int(0.18*1e6))
        ref.SetVisible(True)

# --- 4. 建 castellated 邊緣接腳 (左10/下8/右10 = 28), 承接 J_B2B net ---
mod=pcbnew.FOOTPRINT(b)
mod.SetReference("J_STAMP")
mod.SetPosition(V(0,0))
mod.Reference().SetVisible(False)
P=1.27  # pitch
pins=[]
# 左邊 x=0, 上->下, 10 pin, 置中 y
n=10; y0=BH/2-(n-1)*P/2
for i in range(n): pins.append((0.0, y0+i*P))
# 下邊 y=BH, 左->右, 8 pin
n=8; x0=BW/2-(n-1)*P/2
for i in range(n): pins.append((x0+i*P, BH))
# 右邊 x=BW, 下->上, 10 pin
n=10; y0=BH/2+(n-1)*P/2
for i in range(n): pins.append((BW, y0-i*P))
assert len(pins)==len(used),f"{len(pins)} vs {len(used)}"
for k,(px,py) in zip(used,pins):
    pad=pcbnew.PAD(mod)
    pad.SetNumber(str(k))
    pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
    pad.SetShape(pcbnew.PAD_SHAPE_OVAL)
    pad.SetSize(V(1.0,1.7))
    pad.SetDrillSize(V(0.6,0.6))
    pad.SetPosition(V(px,py))
    pad.SetLayerSet(pad.PTHMask())
    ni=b.FindNet(pinnet[k])
    if ni: pad.SetNet(ni)
    mod.Add(pad)
b.Add(mod)
pcbnew.SaveBoard(OUT,b)
print("SAVED",OUT,"board",BW,"x",BH,"castellated",len(pins))
