"""Build the Arraytron Stamp 0.9.3 demo: hython tools/build_demo_stamplite.py   (hython 22 or 20.5; build the Stamp first with tools/build_stamp_light.py)
A hilly ground (about 29 000 triangles) and three props (Rock, Fir, Stone). Two Stamp nodes:
  A  300 stamps placed like the tool does it (the same stamp_add call per click) along a wavy path on the ground (Place On = the ground): Random Scale 0.6 to 1.5, Random Tilt 8, Random Rotation, Random Prototype by weight.
  B  a few stamps, then edited by hand in the Stamps text (one bigger, one moved, one switched off).
  C  the Group brush: a row of the six layouts (Radial, Square, Hexagon, Random Cluster, Line, Spiral) of seven members each, and a row of radial groups with the group's own randomization (Random Group Scale, Random Member Scale and Rotation).
Writes dist/Arraytron_Stamp_v0.9.3_demo.hip, or otls_h205/Arraytron_Stamp_v0.9.3_H205_demo.hip with hython 20.5.
With --release <folder> the hip goes to that folder and does not record the HDA library (the installed package provides the node type: no path of this PC is stored in the shipped demo)."""
from pathlib import Path
import sys, json, time, hou
import numpy as np
from pxr import UsdGeom
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import versions
ROOT=Path(__file__).resolve().parents[1];H205=versions.is_h205();TYPE='arraytron::stamp::0.9.3'
HDA=ROOT/('otls_h205' if H205 else 'dist')/('Arraytron_Stamp_v0.9.3%s.hda'%('_H205' if H205 else ''));HIP=ROOT/('otls_h205' if H205 else 'dist')/('Arraytron_Stamp_v0.9.3%s_demo.hip'%('_H205' if H205 else ''))
SCENE='''from pxr import Gf, UsdGeom, Vt
import hou, math
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World')
g=UsdGeom.Mesh.Define(stage,'/World/Ground');n=120;pts=[];idx=[]
for j in range(n+1):
    for i in range(n+1):
        x=-15+30*i/n;z=-15+30*j/n;pts.append(Gf.Vec3f(x,0.6*math.sin(x*0.4)*math.cos(z*0.35),z))
for j in range(n):
    for i in range(n):idx+=[j*(n+1)+i,(j+1)*(n+1)+i,(j+1)*(n+1)+i+1,j*(n+1)+i+1]
g.CreatePointsAttr(Vt.Vec3fArray(pts));g.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));g.CreateFaceVertexIndicesAttr(Vt.IntArray(idx));g.CreateSubdivisionSchemeAttr('none');g.CreateDisplayColorAttr([Gf.Vec3f(0.35,0.5,0.3)])
for name,shape,color in (('Rock',UsdGeom.Sphere,(0.55,0.55,0.55)),('Fir',UsdGeom.Cone,(0.15,0.5,0.25)),('Stone',UsdGeom.Cube,(0.7,0.65,0.5))):
    UsdGeom.Xform.Define(stage,'/World/Props/'+name);s=shape.Define(stage,'/World/Props/%s/Geom'%name);s.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    if name=='Rock':s.CreateRadiusAttr(0.35)
    elif name=='Fir':s.CreateRadiusAttr(0.4);s.CreateHeightAttr(1.6);UsdGeom.Xformable(s).AddTranslateOp().Set(Gf.Vec3d(0,0.8,0))
    else:s.CreateSizeAttr(0.5)
'''
RELEASE_DIR=Path(sys.argv[sys.argv.index('--release')+1]) if '--release' in sys.argv else None
if RELEASE_DIR is not None:RELEASE_DIR.mkdir(parents=True,exist_ok=True);HIP=RELEASE_DIR/HIP.name
hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(HDA),change_oplibraries_file=RELEASE_DIR is None,force_use_assets=True);hou.hipFile.save(str(HIP))
stage=hou.node('/stage');scene=stage.createNode('pythonscript','ground_and_props');scene.parm('python').set(SCENE)
def stamper(name,out,comment):
    a=stage.createNode(TYPE,name);a.setInput(0,scene);a.parm('outputpath').set(out);a.parm('target').set('/World/Ground')
    a.parm('protos').set(3)
    for i,(p,w) in enumerate((('Fir',3.0),('Rock',2.0),('Stone',1.0)),1):a.parm('proto_prim%d'%i).set('/World/Props/'+p);a.parm('proto_weight%d'%i).set(w)
    a.parmTuple('scalerange').set((0.6,1.5));a.parm('tilt').set(8.0);a.parm('yawrand').set(180.0);a.parm('protorand').set(1);a.parm('seed').set(7)
    a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
def stamps(a,x0,count,counts=None):
    m=a.hdaModule();surf=m.stamp_surface(a);bd=m.stamp_proto_bounds(a)
    for k in range(count):
        t=k/max(count-1,1);x=x0-6+12*t;z=3.0*np.sin(t*6.0);h=surf.hit((x,50.0,z),(0,-1,0));m.stamp_add(a,h[0],h[1],bounds=bd)         # one call per click of the placing tool (the bounds: Sit On Surface, as in the tool)
A=stamper('Stamp_A_RandomPath','/World/StampA','A: 300 stamps along a wavy path on the hills, with Random Scale, Tilt, Rotation and Prototype (by weight).');t0=time.time();stamps(A,-8.0,300);took=(time.time()-t0)/300*1000
B=stamper('Stamp_B_EditedByHand','/World/StampB','B: 12 stamps, then edited (in the STAMPS table of the Parameters pane you would do it by hand): stamp 3 bigger, 6 moved, 9 switched off.');stamps(B,8.0,12)
L=B.evalParm('stamps').split('\n');v=[float(x) for x in L[2].split()];v[6:9]=[3.0,3.0,3.0];L[2]=' '.join('%g'%x for x in v)
v=[float(x) for x in L[5].split()];v[0],v[2]=v[0]+2.0,v[2]-4.0;L[5]=' '.join('%g'%x for x in v);v=L[8].split();v[10]='0';L[8]=' '.join(v);B.parm('stamps').set('\n'.join(L))
C=stamper('Stamp_C_Groups','/World/StampC','C: the Group brush. Back row: the six layouts (Radial, Square, Hexagon, Random Cluster, Line, Spiral), seven members each. Front row: radial groups of the selected cards with Random Group Scale, Random Member Scale and Rotation.')
C.parmTuple('scalerange').set((1.0,1.0));C.parm('tilt').set(0.0);C.parm('yawrand').set(0.0);C.parm('protorand').set(0);C.parm('workset').set('1 2 3');C.parm('group_spacing').set(1.3);C.parm('group_count').set(7);mc=C.hdaModule();sc_=mc.stamp_surface(C);bc=mc.stamp_proto_bounds(C)
def group(x,z):h=sc_.hit((x,50.0,z),(0,-1,0));mc.stamp_group_add(C,sc_,h[0],h[1],bounds=bc)
for k,x in enumerate((-12.5,-7.5,-2.5,2.5,7.5,12.5)):C.parm('group_layout').set(k);group(x,-10.0)                                  # the layouts, back row
C.parm('group_layout').set(0);C.parm('group_count').set(5);C.parmTuple('group_scalerange').set((0.8,1.6));C.parmTuple('group_member_scale').set((0.7,1.3));C.parm('group_member_rot').set(45.0);C.parm('seed').set(3)
for k,x in enumerate((-10.0,-5.0,0.0,5.0,10.0)):group(x,10.0)                                                                          # the randomization, front row: every group its own size, the members unlike
merge=stage.createNode('merge','merge_all');merge.setInput(0,A);merge.setInput(1,B);merge.setInput(2,C);merge.setDisplayFlag(True)
for n in (A,B,C):assert not n.errors(),(n.name(),n.errors())
def read(n):
    pi=UsdGeom.PointInstancer(n.stage().GetPrimAtPath(n.evalParm('outputpath')));return np.array(pi.GetScalesAttr().Get(hou.frame())).reshape(-1,3),np.array(pi.GetProtoIndicesAttr().Get(hou.frame()))
sa,pa=read(A);sb,pb=read(B)
sc3,pc3=read(C);assert len(sc3)==6*7+5*5 and set(pc3.tolist())=={0,1,2}
assert len(sa)==300 and sa[:,0].min()>=0.6-1e-3 and sa[:,0].max()<=1.5+1e-3 and set(pa.tolist())=={0,1,2} and len(sb)==11 and abs(sb[:,0].max()-3.0)<1e-2
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':str(HIP),'A':len(sa),'B':len(sb),'C':len(sc3),'ms_per_stamp':round(took,2)}))
