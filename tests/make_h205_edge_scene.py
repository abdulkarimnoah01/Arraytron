"""Edge-case scene for tests/validate_h205.py (hython, any Houdini): hython tests/make_h205_edge_scene.py <out.hip> <version id>.
Prototype sources that stress the Houdini 20.5 / 21 prototype handling: two sources with the same leaf name (/A/Rock, /B/Rock), a source at the top level
(/Top), gprim sources (a Cube, a Cone: the prototype must keep its type), a USD file source, a SOP geometry source and an Input Connection source."""
import sys
from pathlib import Path
import hou
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
out,vid=sys.argv[1],versions.resolve(sys.argv[2]);ASSETS=(ROOT/'dist/test_assets').as_posix()
hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(versions.hda(vid)),force_use_assets=True);hou.hipFile.save(out)
st=hou.node('/stage')
mk=st.createNode('pythonscript','mk')
mk.parm('python').set('''from pxr import UsdGeom
s=hou.pwd().editableStage()
UsdGeom.Xform.Define(s,'/A');UsdGeom.Cube.Define(s,'/A/Rock').CreateSizeAttr(0.4)
UsdGeom.Xform.Define(s,'/B');UsdGeom.Sphere.Define(s,'/B/Rock').CreateRadiusAttr(0.3)
UsdGeom.Xform.Define(s,'/Top');UsdGeom.Cube.Define(s,'/Top/Body').CreateSizeAttr(0.5)
UsdGeom.Xform.Define(s,'/World');UsdGeom.Xform.Define(s,'/World/Props');UsdGeom.Cone.Define(s,'/World/Props/Gprim').CreateHeightAttr(0.8)
''')
crate=st.createNode('reference','crate');crate.setInput(0,mk)
for p,v in (('primpath','/World/Props/Crate'),('primpath1','/World/Props/Crate'),('filepath1',ASSETS+'/crate.usda'),('filerefprim1','defaultPrim')):crate.parm(p).set(v)
barrel=st.createNode('reference','barrel')
for p,v in (('primpath','/Barrel'),('primpath1','/Barrel'),('filepath1',ASSETS+'/barrel.usda'),('filerefprim1','defaultPrim')):barrel.parm(p).set(v)
geo=hou.node('/obj').createNode('geo','proto_cone');cone=geo.createNode('tube','cone');cone.parm('rad2').set(0);out_=geo.createNode('null','OUT');out_.setInput(0,cone);out_.setDisplayFlag(True)
a=st.createNode(versions.type_name(vid),'Edge');a.setInput(0,crate);a.setInput(1,barrel)
rows=[(0,'/World/Props/Crate'),(0,'/A/Rock'),(0,'/B/Rock'),(0,'/Top'),(0,'/World/Props/Gprim'),(2,ASSETS+'/rock.usda'),(3,out_.path()),(1,'')]
a.parm('protos').set(len(rows));a.parm('proto_mode').set(3)
for i,(kind,value) in enumerate(rows,1):
    a.parm('proto_type%d'%i).set(kind)
    if kind==0:a.parm('proto_prim%d'%i).set(value)
    elif kind==2:a.parm('proto_file%d'%i).set(value)
    elif kind==3:a.parm('proto_sop%d'%i).set(value)
    else:a.parm('proto_input%d'%i).set(0)
a.parm('mode').set(1);a.parm('area_count').set(48)
a.cook(force=True);assert not a.errors(),a.errors()
hou.hipFile.save(out);print('saved',out)
