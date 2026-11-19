"""Build the Prototype Sockets test scene (Arraytron v1.37.0 + Arraytron Stamp 0.12.0): hython tools/build_demo_protosocket_v1370.py
A brown test ground and four prototypes wired the way an artist wires them, with NOTHING imported yet, so the new button can be tried:
  Input 2 of both nodes   a merge of three Reference LOPs (fir, rock, barrel: USD files) and one procedural sphere (a Python LOP, no file behind it)
  Input 3 of both nodes   one more Reference LOP (crate)
  TRY_Arraytron           Arraytron v1.37.0, Surface mode on the ground, 90 instances: its Prototype Bank is still the default row (an error until the import)
  TRY_Stamp               Arraytron Stamp 0.12.0 on the ground, its bank is still the built-in sphere
Select a node and click Import Prototype Inputs (Scatter tab > above the Prototype Bank for Arraytron; Brush > Asset for the Stamp): five rows appear in the bank (Input Connection, Prim Path set, Weight / Scale /
Scale Random / Rotation Offset on each), and the Asset Library gets five assets (category Imported: the three USD files themselves, the crate file, and the sphere written as a standalone file).
Writes dist/Arraytron_v1.37.0_protosocket_demo.hip or otls_h205/Arraytron_v1.37.0_H205_protosocket_demo.hip. Both HDA files are installed by their path, so the scene opens with the libraries loaded."""
from pathlib import Path
import sys, json, os
import hou
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
os.environ.pop('ARRAYTRON_STAMP',None)
VID=versions.BUILD;TYPE=versions.type_name(VID);H205=versions.is_h205();folder=ROOT/('otls_h205' if H205 else 'dist')
A_HDA=folder/('Arraytron_%s%s.hda'%(VID,'_H205' if H205 else ''));S_HDA=folder/('Arraytron_Stamp_v0.12.0%s.hda'%('_H205' if H205 else ''));STAMP_TYPE='arraytron::stamp::0.12.0'
OUT=versions.demo(VID,'protosocket')
for f in (A_HDA,S_HDA):hou.hda.installFile(str(f),force_use_assets=True)
stage=hou.node('/stage')
ASSETS='$HIP/test_assets'
GROUND='''from pxr import UsdGeom, Vt, Gf
import numpy as np
stage=hou.pwd().editableStage()
n=100;s=40.0;x=np.linspace(-s/2,s/2,n+1);X,Z=np.meshgrid(x,x);Y=0.6*np.sin(X*0.3)*np.cos(Z*0.25)+1.2*np.exp(-((X-6)**2+(Z+5)**2)/16.0)
P=np.stack([X.ravel(),Y.ravel(),Z.ravel()],1);i=np.arange(n);I,J=np.meshgrid(i,i);a=(J*(n+1)+I).ravel();idx=np.stack([a,a+n+1,a+n+2,a+1],1).ravel()
m=UsdGeom.Mesh.Define(stage,'/World/TestGround');m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(P.astype(np.float32)));m.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));m.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(idx.astype(np.int32)))
m.CreateDisplayColorAttr([Gf.Vec3f(0.4,0.36,0.3)])
'''
BALL='''from pxr import UsdGeom, Gf
stage=hou.pwd().editableStage()
s=UsdGeom.Sphere.Define(stage,'/ball');s.CreateRadiusAttr(0.6);s.CreateDisplayColorAttr([Gf.Vec3f(0.85,0.25,0.2)])
UsdGeom.Xformable(s).AddTranslateOp().Set(Gf.Vec3d(0,0.6,0))
'''
def reference(name,file,x,y):
    n=stage.createNode('reference',name);n.parm('primpath').set('/'+name);n.parm('filepath1').set('%s/%s'%(ASSETS,file));n.setPosition((x,y));return n
ground=stage.createNode('pythonscript','test_ground');ground.parm('python').set(GROUND);ground.setPosition((0,0))
fir=reference('fir','fir.usda',-6,3);rock=reference('rock','rock.usda',-3,3);barrel=reference('barrel','barrel.usda',0,3)
ball=stage.createNode('pythonscript','ball');ball.parm('python').set(BALL);ball.setPosition((3,3))
crate=reference('crate','crate.usda',9,3)
merge=stage.createNode('merge','prototypes');merge.setPosition((-1,1.5))
for k,n in enumerate((fir,rock,barrel,ball)):merge.setInput(k,n)
a=stage.createNode(TYPE,'TRY_Arraytron');a.setInput(0,ground);a.setInput(1,merge);a.setInput(2,crate);a.setPosition((-3,-2))
s=stage.createNode(STAMP_TYPE,'TRY_Stamp');s.setInput(0,ground);s.setInput(1,merge);s.setInput(2,crate);s.setPosition((4,-2))
if a.parm('copy_test_ground') is not None:a.parm('copy_test_ground').set(0)
a.parm('outputpath').set('/World/TRY_Arraytron');a.parm('mode').set(5);a.parm('surface_prim').set('/World/TestGround');a.parm('surface_count').set(90);a.parm('scale_min').set(0.8);a.parm('scale_max').set(1.3)
s.parm('target').set('/World/TestGround');s.parm('outputpath').set('/World/TRY_Stamps');s.parm('protorand').set(1);s.parm('yawrand').set(180.0)
a.setComment('TRY ME: Prototype Sockets. Input 2 holds a merge of fir, rock, barrel and a procedural ball; Input 3 holds the crate.\nScatter tab > Import Prototype Inputs: five rows appear in the Prototype Bank (and five assets in the Asset Library, category Imported). Click it again: nothing is added twice.\nThen change a Weight, Scale or Scale Random on a row, or turn on Replace The Bank and import again.')
a.setGenericFlag(hou.nodeFlag.DisplayComment,True)
s.setComment('TRY ME: Prototype Sockets. Brush > Asset > Import Prototype Inputs: the cards show fir, rock, barrel, ball and crate; the Random button then paints with all of them.\nPlace / Paint on the brown ground (Enter in the viewport).')
s.setGenericFlag(hou.nodeFlag.DisplayComment,True)
out=stage.createNode('merge','all');out.setInput(0,a);out.setInput(1,s);out.setPosition((0,-4.5));out.setDisplayFlag(True)
errs=[(n.name(),n.errors()) for n in (ground,fir,rock,barrel,ball,crate,merge,s) if n.errors()]
assert not errs,errs
a.setCurrent(True,clear_all_selected=True)
hou.hipFile.save(str(OUT))
print(json.dumps({'saved':str(OUT),'libraries':[d.libraryFilePath() for d in (a.type().definition(),s.type().definition())],'arraytron_before_import':list(a.errors())}))
