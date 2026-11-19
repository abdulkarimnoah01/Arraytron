"""Build the Paint Engine 2.0 TEST scene (v1.36.0 + Arraytron Stamp 0.11.0): hython tools/build_demo_painttest_v1360.py
The Paint Engine demo (tools/build_demo_paintengine_v1360.py: the painted rows A-G and the Stamp row S) plus a free test ground beside it with two EMPTY nodes ready to paint:
  TRY_Arraytron_Paint  Arraytron v1.36.0 in Paint mode on /World/TestGround (Sparse Organic falloff, three prototypes): select it, press Enter in the viewport (or Start Painting)
  TRY_Stamp            Arraytron Stamp 0.11.0 with the Paint brush on /World/TestGround (Sparse Organic, Random Prototype of three): select it, press Enter
Both HDA files are installed by their path, so the scene records the two libraries and opens with them loaded (no Install Asset Library needed).
Writes dist/Arraytron_v1.36.0_painttest.hip or otls_h205/Arraytron_v1.36.0_H205_painttest.hip (built after the demo; it loads that demo)."""
from pathlib import Path
import sys, json, os
import hou
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
os.environ.pop('ARRAYTRON_STAMP',None)
VID=versions.BUILD;TYPE=versions.type_name(VID);H205=versions.is_h205();folder=ROOT/('otls_h205' if H205 else 'dist')
A_HDA=folder/('Arraytron_%s%s.hda'%(VID,'_H205' if H205 else ''));S_HDA=folder/('Arraytron_Stamp_v0.11.0%s.hda'%('_H205' if H205 else ''));STAMP_TYPE='arraytron::stamp::0.11.0'
for f in (A_HDA,S_HDA):hou.hda.installFile(str(f),force_use_assets=True)                     # once each, the real files: the scene records these two libraries (a second install in 20.5 / 21 would take a copy, tools/h205_compat.py)
hou.hipFile.merge(str(versions.demo(VID,'paintengine')),ignore_load_warnings=True)          # merged, not loaded: loading would unload the HDAs
OUT=Path(str(versions.demo(VID,'paintengine')).replace('paintengine_demo','painttest'))
stage=hou.node('/stage');old=hou.node('/stage/terrain_and_props')
GROUND='''from pxr import UsdGeom, Vt, Gf
import numpy as np
stage=hou.pwd().editableStage()
n=120;s=30.0;x=np.linspace(-s/2,s/2,n+1);X,Z=np.meshgrid(x,x);Y=0.5*np.sin(X*0.35)*np.cos(Z*0.3)+1.5*np.exp(-((X-5)**2+(Z+4)**2)/12.0)
P=np.stack([X.ravel()+55.0,Y.ravel(),Z.ravel()],1);i=np.arange(n);I,J=np.meshgrid(i,i);a=(J*(n+1)+I).ravel();idx=np.stack([a,a+n+1,a+n+2,a+1],1).ravel()
m=UsdGeom.Mesh.Define(stage,'/World/TestGround');m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(P.astype(np.float32)));m.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));m.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(idx.astype(np.int32)))
m.CreateDisplayColorAttr([Gf.Vec3f(0.4,0.36,0.3)])
'''
g=stage.createNode('pythonscript','test_ground');g.parm('python').set(GROUND);g.setInput(0,old);g.setPosition((old.position()[0],old.position()[1]-1.0))
for n in stage.children():
    if n is not g and n.inputs() and n.inputs()[0]==old and n.type().name()!='pythonscript':n.setInput(0,g)
a=stage.createNode(TYPE,'TRY_Arraytron_Paint');a.setInput(0,g)
if a.parm('copy_test_ground') is not None:a.parm('copy_test_ground').set(0)
a.parm('protos').set(3)
for i,prim in enumerate(('/World/Props/Shrub','/World/Props/Rock','/World/Props/Fern'),1):a.parm('proto_type%d'%i).set(0);a.parm('proto_prim%d'%i).set(prim)
a.parm('outputpath').set('/World/TRY_Arraytron');a.parm('mode').set(6);a.parm('paint_prim').set('/World/TestGround')
for k,v in dict(paint_radius=1.5,paint_density=8.0,paint_spacing=0.2).items():a.parm(k).set(v)
a.setComment('TRY ME: Arraytron Paint Engine 2.0. Select this node, mouse over the viewport, press Enter (or Layout > Paint > Start Painting). Paint on the brown test ground (x = 55).\nLMB paint | Ctrl erase | 1-9 brushes | C brush menu | H hints | F falloff preset | [ ] radius | Esc cancels a stroke | Ctrl+Z undoes a whole stroke')
a.setGenericFlag(hou.nodeFlag.DisplayComment,True)
s=stage.createNode(STAMP_TYPE,'TRY_Stamp');s.setInput(0,g);s.parm('target').set('/World/TestGround');s.parm('outputpath').set('/World/TRY_Stamps');s.parm('protos').set(3)
for i,prim in enumerate(('/World/Props/Shrub','/World/Props/Rock','/World/Props/Fern'),1):s.parm('proto_type%d'%i).set(0);s.parm('proto_prim%d'%i).set(prim)
s.parm('protorand').set(1);s.parm('yawrand').set(180.0);s.parmTuple('scalerange').set((0.8,1.2));s.parm('brush').set(2);s.parm('paint_radius').set(1.5);s.parm('paint_density').set(6.0);s.parm('paint_spacing').set(0.25)
s.setComment('TRY ME: Arraytron Stamp 0.11.0. Select this node, press Enter in the viewport. Paint brush is on: drag on the brown test ground.\nC brush menu (Erase, Relax, Grow / Shrink, Push, Replace, Orient, Clone) | Shift+B Edit mode | H hints | Esc cancels a stroke | Ctrl+Z undoes a whole stroke')
s.setGenericFlag(hou.nodeFlag.DisplayComment,True)
merge=hou.node('/stage/all_rows');k=len(merge.inputs());merge.setInput(k,a);merge.setInput(k+1,s)
x,y=g.position();a.setPosition((x-2,y-1.5));s.setPosition((x+2,y-1.5))
cam=hou.node('/stage/camera1')
for p_,v in (('tx',28.0),('ty',140.0),('tz',2.0)):cam.parm(p_).set(v)
st=merge.stage();errs=[(n.name(),n.errors()) for n in (a,s,merge) if n.errors()];assert not errs,errs
a.setCurrent(True,clear_all_selected=True)
hou.hipFile.save(str(OUT))
libs=[d.libraryFilePath() for d in (a.type().definition(),s.type().definition())]
print(json.dumps({'saved':str(OUT),'libraries':libs}))
