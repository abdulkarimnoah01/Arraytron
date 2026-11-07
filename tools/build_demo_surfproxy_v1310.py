"""Build the Reduced Proxy demo (v1.31.0): hython tools/build_demo_surfproxy_v1310.py
A dense mountain (about 780 000 triangles, a Python LOP) scattered in Surface mode with the built-in test sphere, twice:
  A  on the surface itself (every cook reads and keeps the whole mesh once; a recook with another Seed then takes a fraction of a second).
  B  Scatter On Reduced Proxy, Target Triangles 40 000, with the ghost: the reduced surface is drawn as a translucent guide next to the instancer, the points lie on it.
Asserts that both give the same number of points and that B's points lie near the real surface. Writes dist/Arraytron_<version>_surfproxy_demo.hip or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json, time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'surfproxy')
N=620
MOUNTAIN='''from pxr import Gf, UsdGeom, Vt
import hou
import numpy as np
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World')
n=%d;xs=np.linspace(-30,30,n+1);X,Z=np.meshgrid(xs,xs)
Y=6.0*np.exp(-(X**2+Z**2)/300.0)+1.2*np.sin(X*0.35)*np.cos(Z*0.3)+0.25*np.sin(X*2.1+Z*1.7)
pts=np.stack([X.ravel(),Y.ravel(),Z.ravel()],1);idx=np.arange((n+1)*(n+1)).reshape(n+1,n+1)
quads=np.stack([idx[:-1,:-1].ravel(),idx[1:,:-1].ravel(),idx[1:,1:].ravel(),idx[:-1,1:].ravel()],1)
m=UsdGeom.Mesh.Define(stage,'/World/Mountain');m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(pts.astype(np.float32)))
m.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(np.full(n*n,4,dtype=np.int32)));m.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(quads.ravel().astype(np.int32)));m.CreateSubdivisionSchemeAttr('none')
m.CreateDisplayColorAttr([Gf.Vec3f(0.42,0.46,0.38)])
'''%N
def height(x,z):return 6.0*np.exp(-(x**2+z**2)/300.0)+1.2*np.sin(x*0.35)*np.cos(z*0.3)+0.25*np.sin(x*2.1+z*1.7)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage');mountain=stage.createNode('pythonscript','dense_mountain');mountain.parm('python').set(MOUNTAIN)
mountain.setComment('A dense mountain /World/Mountain, %d triangles (Python LOP).'%(2*N*N));mountain.setGenericFlag(hou.nodeFlag.DisplayComment,True)
def node(name,out,comment,**values):
    a=stage.createNode(TYPE,name);assert a.hdaModule().test_setup(a);a.parm('outputpath').set(out);a.setInput(0,mountain)
    a.parm('surface_prim').set('/World/Mountain');a.parm('surface_countmode').set(1);a.parm('surface_density').set(1.2);a.parm('scale_min').set(0.25);a.parm('scale_max').set(0.4)
    for k,v in values.items():
        if isinstance(v,(tuple,list)):a.parmTuple(k).set(v)
        else:a.parm(k).set(v)
    a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
a=node('Arraytron_A_OnTheSurface','/World/ArraytronA','A: scattered on the dense surface itself.')
b=node('Arraytron_B_ReducedProxy','/World/ArraytronB','B: Scatter On Reduced Proxy, 40 000 triangles, with the ghost (the translucent guide mesh next to the instancer).',surface_proxy=1,surface_proxy_tris=40000,surface_ghost=1)
merge=stage.createNode('merge','merge_all');merge.setInput(0,a);merge.setInput(1,b);merge.setDisplayFlag(True)
def cook(n):
    t=time.time();n.cook(force=True);return time.time()-t
ta=cook(a);tb=cook(b)
for n in (a,b):assert not n.errors(),(n.name(),n.errors())
def pos(n):
    s=n.stage();return np.array(UsdGeom.PointInstancer(s.GetPrimAtPath(n.evalParm('outputpath'))).GetPositionsAttr().Get(hou.frame())).reshape(-1,3)
pa,pb=pos(a),pos(b)
err=np.abs(pb[:,1]-height(pb[:,0],pb[:,2]))
assert len(pa)==len(pb) and len(pa)>1000 and err.mean()<0.1 and err.max()<0.8,(len(pa),len(pb),err.mean(),err.max())
ghost=b.stage().GetPrimAtPath('/World/ArraytronB_View/GhostProxy');assert ghost and ghost.IsValid()
a.parm('surface_seed').set(2);b.parm('surface_seed').set(2);ra=cook(a);rb=cook(b)
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'triangles':2*N*N,'points':len(pa),'first_cook_s':{'A':round(ta,2),'B':round(tb,2)},'recook_new_seed_s':{'A':round(ra,2),'B':round(rb,2)},'proxy_mean_error':round(float(err.mean()),3)}))
