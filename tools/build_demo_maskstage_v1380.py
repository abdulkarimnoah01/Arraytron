"""Build the Saved Masks test scene (Arraytron v1.38.0): hython tools/build_demo_maskstage_v1380.py
A brown test ground with three Arraytron nodes in a tree:
  Trees            Surface scatter of firs on the ground with a Noise mask (the mask decides where trees grow); Save Mask is ON with the custom name forest_density (the mask is saved in the stage as a grid and
                   as primvars:forest_density on every tree)
  Bushes           wired BELOW Trees, Mask Source Upstream Mask = forest_density with Invert: bushes grow where the trees do not (no noise to set up again)
  TRY_Wire_Me      Rocks, wired to the ground only: drag its first input from the ground (the Merge) to Trees: a window offers the mask forest_density; Use This Mask makes it the Mask Source
Click Trees > Mask > Save, Cache And Export to see the saved mask and its name; click Bushes > Mask > Upstream Mask to see the masks above it.
Writes dist/Arraytron_v1.38.0_maskstage_demo.hip or otls_h205/Arraytron_v1.38.0_H205_maskstage_demo.hip (the HDA is installed by its path)."""
from pathlib import Path
import sys, json, os
import hou
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
os.environ.pop('ARRAYTRON_STAMP',None)
VID=versions.BUILD;TYPE=versions.type_name(VID);H205=versions.is_h205();folder=ROOT/('otls_h205' if H205 else 'dist')
HDA=folder/('Arraytron_%s%s.hda'%(VID,'_H205' if H205 else ''));OUT=versions.demo(VID,'maskstage')
hou.hda.installFile(str(HDA),force_use_assets=True)
stage=hou.node('/stage')
ASSETS='$HIP/test_assets'
GROUND='''from pxr import UsdGeom, Vt, Gf
import numpy as np
stage=hou.pwd().editableStage()
n=100;s=60.0;x=np.linspace(-s/2,s/2,n+1);X,Z=np.meshgrid(x,x);Y=0.6*np.sin(X*0.2)*np.cos(Z*0.17)+1.2*np.exp(-((X-6)**2+(Z+5)**2)/30.0)
P=np.stack([X.ravel(),Y.ravel(),Z.ravel()],1);i=np.arange(n);I,J=np.meshgrid(i,i);a=(J*(n+1)+I).ravel();idx=np.stack([a,a+n+1,a+n+2,a+1],1).ravel()
m=UsdGeom.Mesh.Define(stage,'/World/TestGround');m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(P.astype(np.float32)));m.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));m.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(idx.astype(np.int32)))
m.CreateDisplayColorAttr([Gf.Vec3f(0.4,0.36,0.3)])
'''
def reference(name,file,x,y):
    n=stage.createNode('reference',name);n.parm('primpath').set('/'+name);n.parm('filepath1').set('%s/%s'%(ASSETS,file));n.setPosition((x,y));return n
ground=stage.createNode('pythonscript','test_ground');ground.parm('python').set(GROUND);ground.setPosition((0,3))
fir=reference('fir','fir.usda',-3,3);rock=reference('rock','rock.usda',3,3);barrel=reference('barrel','barrel.usda',6,3)
scene=stage.createNode('merge','scene');scene.setPosition((1,1.5))
for k,n in enumerate((ground,fir,rock,barrel)):scene.setInput(k,n)
def scatter(name,inp,out,prim,count,x,y):
    n=stage.createNode(TYPE,name);n.setInput(0,inp);n.setPosition((x,y))
    if n.parm('copy_test_ground') is not None:n.parm('copy_test_ground').set(0)
    n.parm('outputpath').set(out);n.parm('mode').set(5);n.parm('surface_prim').set('/World/TestGround');n.parm('surface_count').set(count)
    n.parm('protos').set(1);n.parm('proto_type1').set(0);n.parm('proto_prim1').set(prim);n.parm('scale_min').set(0.8);n.parm('scale_max').set(1.3)
    return n
trees=scatter('Trees',scene,'/World/Trees','/fir',900,-2,-1.5)
trees.parm('mask_source').set(1);trees.parm('mask_noise_freq').set(0.09);trees.parm('mask_noise_contrast').set(3.0)
trees.parm('mstage_on').set(1);trees.parm('mstage_name').set('forest_density');trees.parm('mstage_res').set(256)
bushes=scatter('Bushes',trees,'/World/Bushes','/rock',1100,-2,-4)
bushes.parm('mask_source').set(6);bushes.parm('mup_name').set('forest_density');bushes.parm('mask_invert').set(1)
wire=scatter('TRY_Wire_Me',scene,'/World/Rocks','/barrel',400,5,-3)
trees.setComment('Trees: a Noise mask decides where the firs grow. Mask > Save, Cache And Export > Save Mask is ON, named forest_density (a grid in the stage and primvars:forest_density on every tree).')
trees.setGenericFlag(hou.nodeFlag.DisplayComment,True)
bushes.setComment('Bushes: wired below Trees; Mask Source Upstream Mask = forest_density, Invert on: rocks grow where the trees do not. No noise to set up again.')
bushes.setGenericFlag(hou.nodeFlag.DisplayComment,True)
wire.setComment('TRY ME: drag the first input of this node from the Merge (scene) to Trees. A window offers the mask forest_density: Use This Mask makes it the Mask Source.')
wire.setGenericFlag(hou.nodeFlag.DisplayComment,True)
out=stage.createNode('merge','all');out.setInput(0,bushes);out.setInput(1,wire);out.setPosition((1,-6.5));out.setDisplayFlag(True)
hou.hipFile.save(str(OUT))                                                                    # first: $HIP/test_assets resolves beside the saved scene
errs=[(n.name(),n.errors()) for n in (ground,fir,rock,barrel,scene,trees,bushes,wire) if n.errors()];assert not errs,errs
try:trees.cook(force=True)
except hou.OperationFailed:pass
bad=[(c.path(),c.errors()) for c in [trees]+list(trees.allSubChildren()) if c.errors()]
assert not bad,bad[:4]
prim=trees.stage().GetPrimAtPath('/World/Trees');saved=prim.GetCustomDataByKey('arraytron:mask')
assert saved and saved['name']=='forest_density',saved
counts={n.name():len(UsdGeomPI.GetPositionsAttr().Get()) for n in (trees,bushes,wire) for UsdGeomPI in [__import__('pxr.UsdGeom',fromlist=['x']).PointInstancer(n.stage().GetPrimAtPath(n.evalParm('outputpath')))]}
trees.setCurrent(True,clear_all_selected=True)
hou.hipFile.save(str(OUT))
print(json.dumps({'saved':str(OUT),'library':trees.type().definition().libraryFilePath(),'saved_mask':{k:v for k,v in saved.items() if k!='data'},'instances':counts}))
