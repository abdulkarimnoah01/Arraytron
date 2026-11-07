"""Build the test ground demo (v1.25.2): hython tools/build_demo_groundauto_v1252.py
Two nodes started with the test setup: A keeps the built-in test ground (30 spheres on the 10 x 10 plane at the origin); B gets an external surface (a hilly terrain made by a Python LOP,
at x 8 to 28) wired into its input, which switches the built-in ground off (the OnInputChanged handler), and Surface Prim names the terrain: no plane is added to B's stream and its spheres
sit on the hills. Writes dist/Arraytron_<version>_groundauto_demo.hip or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'groundauto')
TERRAIN='''from pxr import Gf, UsdGeom, Vt
import hou, math
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World')
mesh=UsdGeom.Mesh.Define(stage,'/World/Terrain')
n=40;size=20.0;x0=8.0
points=[]
for j in range(n+1):
    for i in range(n+1):
        x=x0+size*i/n;z=-size/2+size*j/n
        points.append(Gf.Vec3f(x,0.9*math.sin(x*0.45)*math.cos(z*0.4)+0.3*math.sin(z*1.1),z))
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
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage')
terrain=stage.createNode('pythonscript','external_terrain');terrain.parm('python').set(TERRAIN)
terrain.setComment('An external surface (Python LOP): a hilly terrain at x 8 to 28, prim /World/Terrain.');terrain.setGenericFlag(hou.nodeFlag.DisplayComment,True)
a=stage.createNode(TYPE,'Arraytron_A_BuiltInGround');ok=a.hdaModule().test_setup(a);assert ok
a.parm('outputpath').set('/World/ArraytronA')
a.setComment('A: the test setup as a new node gets it: 30 spheres on the built-in test ground plane (10 x 10 at the origin).');a.setGenericFlag(hou.nodeFlag.DisplayComment,True)
b=stage.createNode(TYPE,'Arraytron_B_ExternalSurface');ok=b.hdaModule().test_setup(b);assert ok and b.evalParm('copy_test_ground')==1
b.parm('outputpath').set('/World/ArraytronB');b.setInput(0,terrain)                  # wiring the external source switches the built-in ground off (OnInputChanged) ...
assert b.evalParm('copy_test_ground')==0,'the OnInputChanged handler did not switch the ground off'
b.parm('surface_prim').set('/World/Terrain');b.parm('surface_count').set(60)         # ... and Surface Prim names the terrain
b.setComment('B: the terrain is wired in, so the built-in ground is off and Surface Prim is /World/Terrain: no plane under the hills.');b.setGenericFlag(hou.nodeFlag.DisplayComment,True)
merge=stage.createNode('merge','merge_all');merge.setInput(0,a);merge.setInput(1,b);merge.setDisplayFlag(True)
sa=a.stage();sb=b.stage();assert sa is not None and sb is not None and not a.errors() and not b.errors(),(a.errors(),b.errors())
plane_a=bool(sa.GetPrimAtPath('/World/TestGround/Plane'));plane_b=bool(sb.GetPrimAtPath('/World/TestGround/Plane'));assert plane_a and not plane_b,(plane_a,plane_b)
pa=UsdGeom.PointInstancer(sa.GetPrimAtPath('/World/ArraytronA')).GetPositionsAttr().Get(hou.frame());pb=UsdGeom.PointInstancer(sb.GetPrimAtPath('/World/ArraytronB')).GetPositionsAttr().Get(hou.frame())
assert len(pa)==30 and len(pb)==60 and min(p[0] for p in pb)>=8.0 and max(p[0] for p in pb)<=28.0 and max(p[1] for p in pb)-min(p[1] for p in pb)>0.5   # B sits on the hills, not at y 0
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'A':{'instances':len(pa),'plane':plane_a},'B':{'instances':len(pb),'plane':plane_b,'y':[round(min(p[1] for p in pb),2),round(max(p[1] for p in pb),2)]}}))
