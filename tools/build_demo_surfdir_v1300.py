"""Build the Keep By Direction demo (v1.30.0): hython tools/build_demo_surfdir_v1300.py
Two steep hilly patches (a Python LOP, with a distant light /World/Sun high in the east (the way towards it is about 0.34 0.94 0)) scattered in Surface mode with the built-in test sphere:
  A  Keep By Direction, Vector 0 1 0, Spread Angle 35, Soft Edge 0.6: only the flat tops of the hills get points, thinning out towards the slopes.
  B  Keep By Direction from the Light Prim /World/Sun, Spread Angle 70, Soft Edge 0.4: only the faces turned towards the sun get points.
Asserts what the picture should show. Writes dist/Arraytron_<version>_surfdir_demo.hip or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json, math
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'surfdir')
TERRAINS='''from pxr import Gf, UsdGeom, UsdLux, Vt
import hou, math
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World')
n=60;size=20.0
for name,x0 in (('TerrainA',0.0),('TerrainB',24.0)):
    mesh=UsdGeom.Mesh.Define(stage,'/World/'+name)
    points=[]
    for j in range(n+1):
        for i in range(n+1):
            x=x0+size*i/n;z=-size/2+size*j/n
            points.append(Gf.Vec3f(x,2.2*math.sin(x*0.5)*math.cos(z*0.45)+0.6*math.sin(z*1.3+x*0.2),z))
    indices=[]
    for j in range(n):
        for i in range(n):
            indices+=[j*(n+1)+i,(j+1)*(n+1)+i,(j+1)*(n+1)+i+1,j*(n+1)+i+1]
    mesh.CreatePointsAttr(Vt.Vec3fArray(points))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(indices))
    mesh.CreateSubdivisionSchemeAttr('none')
    mesh.CreateDisplayColorAttr([Gf.Vec3f(0.4,0.45,0.35)])
sun=UsdLux.DistantLight.Define(stage,'/World/Sun');x=UsdGeom.Xformable(sun);x.AddRotateXYZOp().Set(Gf.Vec3f(-70,90,0))
'''
def height(x,z):return 2.2*math.sin(x*0.5)*math.cos(z*0.45)+0.6*math.sin(z*1.3+x*0.2)
def normal(x,z):
    e=1e-3;dx=(height(x+e,z)-height(x-e,z))/(2*e);dz=(height(x,z+e)-height(x,z-e))/(2*e);v=np.array([-dx,1.0,-dz]);return v/np.linalg.norm(v)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage');terrain=stage.createNode('pythonscript','external_terrains');terrain.parm('python').set(TERRAINS)
terrain.setComment('Two steep hilly patches /World/TerrainA, /World/TerrainB and a distant light /World/Sun (Python LOP).');terrain.setGenericFlag(hou.nodeFlag.DisplayComment,True)
def node(name,prim,out,comment,**values):
    a=stage.createNode(TYPE,name);assert a.hdaModule().test_setup(a);a.parm('outputpath').set(out);a.setInput(0,terrain)
    a.parm('surface_prim').set(prim);a.parm('surface_count').set(1500);a.parm('scale_min').set(0.25);a.parm('scale_max').set(0.4);a.parm('surface_slope_max').set(180.0);a.parm('surface_dirsel').set(1)
    for k,v in values.items():
        if isinstance(v,(tuple,list)):a.parmTuple(k).set(v)
        else:a.parm(k).set(v)
    a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
a=node('Arraytron_A_FlatTops','/World/TerrainA','/World/ArraytronA','A: Keep By Direction, Vector 0 1 0, Spread Angle 35, Soft Edge 0.6: only the flat tops of the hills.',surface_dirsrc=0,surface_dir=(0,1,0),surface_spread=35.0,surface_soft=0.6)
b=node('Arraytron_B_SunFacing','/World/TerrainB','/World/ArraytronB','B: Keep By Direction from the Light Prim /World/Sun, Spread Angle 70, Soft Edge 0.4: only the faces turned towards the sun.',surface_dirsrc=1,surface_light='/World/Sun',surface_spread=70.0,surface_soft=0.4)
merge=stage.createNode('merge','merge_all');merge.setInput(0,a);merge.setInput(1,b);merge.setDisplayFlag(True)
for n in (a,b):assert not n.errors(),(n.name(),n.errors())
def pos(n):
    s=n.stage();return np.array(UsdGeom.PointInstancer(s.GetPrimAtPath(n.evalParm('outputpath'))).GetPositionsAttr().Get(hou.frame())).reshape(-1,3)
pa,pb=pos(a),pos(b)
na=np.array([normal(p[0],p[2]) for p in pa]);ang_a=np.degrees(np.arccos(np.clip(na[:,1],-1,1)))
from pxr import Usd
m=np.array(UsdGeom.XformCache(Usd.TimeCode.Default()).GetLocalToWorldTransform(a.stage().GetPrimAtPath('/World/Sun'))).reshape(4,4);to_sun=m[2,:3]/np.linalg.norm(m[2,:3])   # the +Z axis of the light: the way towards it
nb=np.array([normal(p[0],p[2]) for p in pb]);ang_b=np.degrees(np.arccos(np.clip(nb@to_sun,-1,1)))
assert len(pa)==1500 and np.median(ang_a)<22.0 and np.percentile(ang_a,95)<48.0                                       # A: the tops (the mesh is a little coarser than the formula)
assert len(pb)==1500 and np.median(ang_b)<40.0 and np.percentile(ang_b,95)<85.0 and (ang_b<80).mean()>0.9           # B: turned towards the sun
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'A_median_slope':round(float(np.median(ang_a)),1),'B_median_angle_to_sun':round(float(np.median(ang_b)),1),'to_sun':[round(float(v),3) for v in to_sun]}))
