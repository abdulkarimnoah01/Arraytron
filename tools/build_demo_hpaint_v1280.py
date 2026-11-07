"""Build the Houdini paint demo (v1.28.0): hython tools/build_demo_hpaint_v1280.py
One hilly patch (a Python LOP terrain) with an Arraytron node (the built-in sphere of the test setup, Surface mode) whose Mask Source is Houdini Paint. The node's paint helper (/obj/Arraytron_HoudiniPaint_mask_paint:
the dense surface, the Attribute Paint SOP, OUT) is in the file, and the painting a person would do with the brush is stood in for by a wrangle after the Attribute Paint SOP (a soft round clearing grown into a
meadow and a winding path kept free) so the scene shows what Finish And Scatter produces. Open the node, press Paint Mask With Houdini Brush to continue painting with the real brush, Finish And Scatter to scatter again.
Asserts what the picture should show. Writes dist/Arraytron_<version>_hpaint_demo.hip or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'hpaint')
TERRAIN='''from pxr import Gf, UsdGeom, Vt
import hou, math
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World')
mesh=UsdGeom.Mesh.Define(stage,'/World/Terrain')
n=48;size=24.0
points=[]
for j in range(n+1):
    for i in range(n+1):
        x=size*i/n-size/2;z=size*j/n-size/2
        points.append(Gf.Vec3f(x,0.8*math.sin(x*0.4)*math.cos(z*0.35)+0.25*math.sin(z*1.1),z))
indices=[]
for j in range(n):
    for i in range(n):
        indices+=[j*(n+1)+i,(j+1)*(n+1)+i,(j+1)*(n+1)+i+1,j*(n+1)+i+1]
mesh.CreatePointsAttr(Vt.Vec3fArray(points))
mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)))
mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(indices))
mesh.CreateSubdivisionSchemeAttr('none')
mesh.CreateDisplayColorAttr([Gf.Vec3f(0.35,0.5,0.3)])
'''
PAINTED='''float d=length(set(@P.x+2.0,@P.z-1.0));
float meadow=1.0-smooth(3.0,8.5,d);
float path=smooth(0.0,1.3,abs(@P.z-2.5*sin(@P.x*0.45)));
f@mask=clamp(meadow*path,0.0,1.0);
'''
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage');terrain=stage.createNode('pythonscript','external_terrain');terrain.parm('python').set(TERRAIN)
terrain.setComment('A hilly patch (Python LOP): /World/Terrain.');terrain.setGenericFlag(hou.nodeFlag.DisplayComment,True)
a=stage.createNode(TYPE,'Arraytron_HoudiniPaint');assert a.hdaModule().test_setup(a);a.parm('outputpath').set('/World/Arraytron');a.setInput(0,terrain)
a.parm('surface_prim').set('/World/Terrain');a.parm('surface_count').set(2500);a.parm('scale_min').set(0.25);a.parm('scale_max').set(0.4);a.parm('mask_source').set(5)
a.setComment('Mask Source Houdini Paint. Paint Mask With Houdini Brush enters the Attribute Paint brush (heat map) on the helper /obj/%s_mask_paint, Finish And Scatter bakes it and scatters.'%a.name());a.setGenericFlag(hou.nodeFlag.DisplayComment,True)
m=a.hdaModule();geo=m.hpaint_helper(a);wr=geo.createNode('attribwrangle','STAND_IN_FOR_THE_BRUSH');wr.parm('class').set(2);wr.parm('snippet').set(PAINTED);wr.setInput(0,geo.node('PAINT'));geo.node('OUT').setInput(0,wr);geo.layoutChildren()
wr.setComment('Stands in for the strokes of a person painting. Delete it and paint with the brush instead.');wr.setGenericFlag(hou.nodeFlag.DisplayComment,True)
count=m.hpaint_finish(a);assert not a.errors(),a.errors()
s=a.stage();P=np.array(UsdGeom.PointInstancer(s.GetPrimAtPath('/World/Arraytron')).GetPositionsAttr().Get(hou.frame())).reshape(-1,3)
near=np.hypot(P[:,0]+2.0,P[:,2]-1.0)<6.0;path=np.abs(P[:,2]-2.5*np.sin(P[:,0]*0.45))<0.6
assert len(P)>150 and near.mean()>0.8 and np.hypot(P[:,0]+2.0,P[:,2]-1.0).max()<10.0 and path.mean()<0.08                              # a meadow around (-2, 1) that leaves the path free
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'helper':geo.path(),'baked_points':count,'instances':len(P),'on_path':int(path.sum())}))
