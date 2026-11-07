"""Build the Group Children demo (v1.29.0): hython tools/build_demo_groups_v1290.py
A group /World/Group of three props (a cube, a cone and a sphere, each a different colour) made by a Python LOP. Two Arraytron nodes use it through ONE Prototype Bank row of the new Source Type Group Children:
  A  Prim Path /World/Group/*: a Line of 12 instances, Selection Mode Cycle - the three children take turns (cube, cone, sphere, cube ...).
  B  Prim Path /World/Group/C*: a name pattern - only the Cube and the Cone - scattered over an Area with Weighted Random, the row Scale 0.6.
Asserts what the picture should show. Writes dist/Arraytron_<version>_groups_demo.hip or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'groups')
PROPS='''from pxr import Gf, UsdGeom
import hou
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World');UsdGeom.Xform.Define(stage,'/World/Group')
for name,shape,color in (('Cube',UsdGeom.Cube,(0.9,0.3,0.25)),('Cone',UsdGeom.Cone,(0.25,0.7,0.35)),('Sphere',UsdGeom.Sphere,(0.3,0.45,0.95))):
    UsdGeom.Xform.Define(stage,'/World/Group/'+name)
    g=shape.Define(stage,'/World/Group/%s/Geom'%name);g.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    if name=='Cube':g.CreateSizeAttr(0.8)
    elif name=='Cone':g.CreateRadiusAttr(0.4);g.CreateHeightAttr(0.9)
    else:g.CreateRadiusAttr(0.4)
'''
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage');props=stage.createNode('pythonscript','group_of_props');props.parm('python').set(PROPS)
props.setComment('A group /World/Group of three props: Cube, Cone, Sphere (Python LOP).');props.setGenericFlag(hou.nodeFlag.DisplayComment,True)
def node(name,out,comment,**values):
    a=stage.createNode(TYPE,name);a.setInput(0,props);a.parm('outputpath').set(out);a.parm('protos').set(1);a.parm('proto_type1').set(4)
    for k,v in values.items():
        if isinstance(v,(tuple,list)):a.parmTuple(k).set(v)
        else:a.parm(k).set(v)
    a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
a=node('Arraytron_A_AllChildren','/World/ArraytronA','A: one Prototype Bank row, Source Type Group Children, Prim Path /World/Group/*: the cube, the cone and the sphere take turns (Cycle).',proto_prim1='/World/Group/*',mode=0,line_count=12,proto_mode=3)
b=node('Arraytron_B_NamePattern','/World/ArraytronB','B: Prim Path /World/Group/C*: only Cube and Cone, Weighted Random, row Scale 0.6, over an Area.',proto_prim1='/World/Group/C*',mode=1,area_count=50,area_seed=4,proto_mode=1,proto_scale1=0.6,bound_t=(0.0,0.0,5.0))
merge=stage.createNode('merge','merge_all');merge.setInput(0,a);merge.setInput(1,b);merge.setDisplayFlag(True)
for n in (a,b):assert not n.errors(),(n.name(),n.errors())
def read(n):
    s=n.stage();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(n.evalParm('outputpath')));return np.array(pi.GetProtoIndicesAttr().Get(hou.frame())),np.array(pi.GetIdsAttr().Get(hou.frame())),[p.pathString.rsplit('/',1)[1] for p in pi.GetPrototypesRel().GetTargets()]
ia,ida,na=read(a);ib,idb,nb=read(b)
assert na==['Cube','Cone','Sphere'] and len(ia)==12 and np.array_equal(ia,ida%3)                                  # A: three prototypes taking turns
assert nb==['Cube','Cone'] and len(ib)==50 and set(ib.tolist())=={0,1}                                           # B: the pattern left the sphere out
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'A':{'prototypes':na,'instances':len(ia)},'B':{'prototypes':nb,'instances':len(ib),'counts':np.bincount(ib).tolist()}}))
