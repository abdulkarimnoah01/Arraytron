"""Build the Arraytron Stamp demo: hython tools/build_demo_stamp.py   (hython 22 or 20.5; build the Stamp HDA first with tools/build_arraytron_stamp.py)
A hilly ground and three props (Rock, Fir, Stone) made by a Python LOP. Two Stamp nodes:
  A  Hand placed like the tool does it (the same place_add call, one per click) along a wavy path: Random Scale 0.6 to 1.5, Random Tilt 8 degrees, Random Rotation, Random Prototype by weight (Fir 3, Rock 2, Stone 1).
  B  The same stamps, then three of them edited by hand in the table (one scaled up, one moved, one switched to another prototype, one off) - what Placed Instances lets you do after placing.
Writes dist/Arraytron_Stamp_v0.1.0_demo.hip, or otls_h205/Arraytron_Stamp_v0.1.0_H205_demo.hip with hython 20.5."""
from pathlib import Path
import sys, json, hou
import numpy as np
from pxr import UsdGeom
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import versions
ROOT=Path(__file__).resolve().parents[1];H205=versions.is_h205()
HDA=ROOT/('otls_h205' if H205 else 'dist')/('Arraytron_Stamp_v0.1.0%s.hda'%('_H205' if H205 else ''));HIP=ROOT/('otls_h205' if H205 else 'dist')/('Arraytron_Stamp_v0.1.0%s_demo.hip'%('_H205' if H205 else ''))
SCENE='''from pxr import Gf, UsdGeom, Vt
import hou, math
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World')
g=UsdGeom.Mesh.Define(stage,'/World/Ground');n=30;pts=[];idx=[]
for j in range(n+1):
    for i in range(n+1):
        x=-15+30*i/n;z=-15+30*j/n;pts.append(Gf.Vec3f(x,0.0,z))
for j in range(n):
    for i in range(n):idx+=[j*(n+1)+i,(j+1)*(n+1)+i,(j+1)*(n+1)+i+1,j*(n+1)+i+1]
g.CreatePointsAttr(Vt.Vec3fArray(pts));g.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));g.CreateFaceVertexIndicesAttr(Vt.IntArray(idx));g.CreateSubdivisionSchemeAttr('none');g.CreateDisplayColorAttr([Gf.Vec3f(0.35,0.5,0.3)])
for name,shape,color in (('Rock',UsdGeom.Sphere,(0.55,0.55,0.55)),('Fir',UsdGeom.Cone,(0.15,0.5,0.25)),('Stone',UsdGeom.Cube,(0.7,0.65,0.5))):
    UsdGeom.Xform.Define(stage,'/World/Props/'+name);s=shape.Define(stage,'/World/Props/%s/Geom'%name);s.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    if name=='Rock':s.CreateRadiusAttr(0.35)
    elif name=='Fir':s.CreateRadiusAttr(0.4);s.CreateHeightAttr(1.6);UsdGeom.Xformable(s).AddTranslateOp().Set(Gf.Vec3d(0,0.8,0))
    else:s.CreateSizeAttr(0.5)
'''
hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(HDA),force_use_assets=True);hou.hipFile.save(str(HIP))
stage=hou.node('/stage');scene=stage.createNode('pythonscript','ground_and_props');scene.parm('python').set(SCENE)
def stamper(name,out,comment):
    a=stage.createNode('arraytron::stamp::0.1.0',name);a.setInput(0,scene);a.parm('outputpath').set(out);a.parm('protos').set(3)
    for i,(p,w) in enumerate((('Fir',3.0),('Rock',2.0),('Stone',1.0)),1):a.parm('proto_prim%d'%i).set('/World/Props/'+p);a.parm('proto_weight%d'%i).set(w)
    a.parmTuple('place_def_scalerange').set((0.6,1.5));a.parm('place_def_tilt').set(8.0);a.parm('place_def_yawrand').set(180.0);a.parm('place_def_protorand').set(1);a.parm('place_seed').set(7)
    a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
def stamps(a,x0):
    m=a.hdaModule()
    for k in range(40):t=k/39.0;m.place_add(a,(x0-6+12*t,0.0,3.0*np.sin(t*6.0)))                    # one call per click of the placing tool
A=stamper('Stamp_A_RandomPath','/World/StampA','A: 40 stamps along a wavy path with Random Scale, Tilt, Rotation and Prototype (by weight).');stamps(A,-8.0)
B=stamper('Stamp_B_EditedByHand','/World/StampB','B: the same stamps, then four edited in the Placed Instances table: row 5 bigger, row 12 moved, row 20 another prototype, row 30 switched off.');stamps(B,8.0)
B.parmTuple('place_scale5').set((3.0,3.0,3.0));B.parmTuple('place_pos12').set((6.0,0.0,-5.0));B.parm('place_proto20').set(3);B.parm('place_on30').set(0)
merge=stage.createNode('merge','merge_all');merge.setInput(0,A);merge.setInput(1,B);merge.setDisplayFlag(True)
for n in (A,B):assert not n.errors(),(n.name(),n.errors())
def read(n):
    pi=UsdGeom.PointInstancer(n.stage().GetPrimAtPath(n.evalParm('outputpath')));return np.array(pi.GetScalesAttr().Get(hou.frame())).reshape(-1,3),np.array(pi.GetProtoIndicesAttr().Get(hou.frame()))
sa,pa=read(A);sb,pb=read(B)
assert len(sa)==40 and len(sb)==39 and sa[:,0].min()>=0.6-1e-3 and sa[:,0].max()<=1.5+1e-3 and set(pa.tolist())=={0,1,2} and abs(sb[:,0].max()-3.0)<1e-2      # random in range; one stamp off; one scaled to 3
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':str(HIP),'A':len(sa),'B':len(sb),'A_protos':np.bincount(pa).tolist()}))
