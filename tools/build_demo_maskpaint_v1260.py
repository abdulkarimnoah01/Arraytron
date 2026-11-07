"""Build the painted mask demo (v1.26.0): hython tools/build_demo_maskpaint_v1260.py
Three hilly patches (Python LOP terrains, one Arraytron node each, spheres of the built-in test setup, Surface mode) whose scatter is a painted mask. The paint is written the way the viewport brush writes it
(maskpaint_add, one stamp per dab) so the file shows what a painting session produces:
  A  Feathered clearing: a soft blob painted onto an empty patch (Unpainted Value 0), brush feather 0.8 - the scatter fades out towards the rim of every dab.
  B  A path through a forest: Unpainted Value 1 (full scatter), a winding path erased with a feathered brush, Map Feather 0.5 blurring it further.
  C  Remap: a broad soft stroke painted at strength 0.35 several times (the airbrush builds up), then Gamma, a Remap Curve (an S curve) and an Output Range thin it out everywhere.
Asserts what the picture should show. Writes dist/Arraytron_<version>_maskpaint_demo.hip or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'maskpaint')
TERRAINS='''from pxr import Gf, UsdGeom, Vt
import hou, math
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World')
n=40;size=20.0
for name,x0 in (('TerrainA',0.0),('TerrainB',24.0),('TerrainC',48.0)):
    mesh=UsdGeom.Mesh.Define(stage,'/World/'+name)
    points=[]
    for j in range(n+1):
        for i in range(n+1):
            x=x0+size*i/n;z=-size/2+size*j/n
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
def node(stage,terrain,name,prim,out,comment,**values):
    a=stage.createNode(TYPE,name);assert a.hdaModule().test_setup(a);a.parm('outputpath').set(out);a.setInput(0,terrain)            # the test setup, then the terrain wired in (this switches the built-in ground off)
    assert a.evalParm('copy_test_ground')==0
    a.parm('surface_prim').set(prim);a.parm('surface_count').set(1800);a.parm('scale_min').set(0.25);a.parm('scale_max').set(0.4)
    for k,v in values.items():
        if isinstance(v,(tuple,list)):a.parmTuple(k).set(v)
        else:a.parm(k).set(v)
    a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
def stamps(m,rows):
    """The paint of a session: rows of (op, x, z, radius, strength, feather, value, curve) added the way the brush adds them."""
    data=np.zeros((0,m.MASKPAINT_COLUMNS))
    for op,x,z,r,s,f,v,c in rows:data,_=m.maskpaint_add(data,op,(x,0.0,z),r,s,f,v,c)
    return data

hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage');terrain=stage.createNode('pythonscript','external_terrains');terrain.parm('python').set(TERRAINS)
terrain.setComment('Three hilly patches (Python LOP): /World/TerrainA, B and C.');terrain.setGenericFlag(hou.nodeFlag.DisplayComment,True)
probe=stage.createNode(TYPE,'probe');m=probe.hdaModule();probe.destroy()
blob=[(0,10.0+4.0*np.cos(t),0.0+3.0*np.sin(t),2.6,1.0,0.8,1.0,1) for t in np.linspace(0,2*np.pi,28)]+[(0,10.0,0.0,3.2,1.0,0.8,1.0,1)]                                              # A: a ring of dabs and one in the middle
path=[(1,24.0+x,3.0*np.sin(x*0.35)-1.0,1.7,1.0,0.6,1.0,1) for x in np.linspace(-1.0,21.0,60)]                                                                                    # B: the path, erased
broad=[(0,48.0+x,0.0,7.0,0.35,1.0,1.0,0) for x in np.linspace(3.0,17.0,8) for _ in range(3)]                                                                                  # C: a broad airbrush stroke, three passes
a=node(stage,terrain,'Arraytron_A_FeatheredClearing','/World/TerrainA','/World/ArraytronA','A: Mask Source Painted. A soft blob painted onto an empty patch (Unpainted Value 0): the scatter fades out towards the edge of the brush (Brush Feather 0.8).',mask_source=4,mask_paint_data=m.maskpaint_encode(stamps(m,blob)))
b=node(stage,terrain,'Arraytron_B_PathThroughForest','/World/TerrainB','/World/ArraytronB','B: Unpainted Value 1 (a full scatter) and a winding path erased with a feathered brush; Map Feather 0.5 softens the path edges further.',mask_source=4,mask_paint_base=1.0,mask_paint_blur=0.5,mask_paint_data=m.maskpaint_encode(stamps(m,path)))
c=node(stage,terrain,'Arraytron_C_Remap','/World/TerrainC','/World/ArraytronC','C: a broad stroke painted three times at strength 0.35 (it builds up), then Gamma 1.6, a Remap Curve (S shape) and Output Range 0.1 to 0.9 thin the scatter out everywhere.',mask_source=4,mask_paint_data=m.maskpaint_encode(stamps(m,broad)),mask_gamma=1.6,mask_curve_on=1,mask_outrange=(0.1,0.9))
c.parm('mask_curve').set(hou.Ramp((hou.rampBasis.MonotoneCubic,)*4,(0.0,0.3,0.7,1.0),(0.0,0.1,0.9,1.0)))
merge=stage.createNode('merge','merge_all')
for k,n in enumerate((a,b,c)):merge.setInput(k,n)
merge.setDisplayFlag(True)
for n in (a,b,c):assert not n.errors(),(n.name(),n.errors())
def pos(n):
    s=n.stage();return np.array(UsdGeom.PointInstancer(s.GetPrimAtPath(n.evalParm('outputpath'))).GetPositionsAttr().Get(hou.frame())).reshape(-1,3)
pa,pb,pc=pos(a),pos(b),pos(c)
assert 150<len(pa)<900 and np.hypot(pa[:,0]-10.0,pa[:,2]).max()<7.5 and np.hypot(pa[:,0]-10.0,pa[:,2]).min()<2.0           # A: only around the painted blob
yp=3.0*np.sin((pb[:,0]-24.0)*0.35)-1.0;on_path=np.abs(pb[:,2]-yp)<0.9                                                         # B: the path is (nearly) free
assert len(pb)>700 and on_path.sum()<0.15*len(pb)*(1.8/20.0)*4 and (~on_path).sum()>0.7*len(pb)
assert 100<len(pc)<1200 and pc[:,0].min()>48.0 and pc[:,0].max()<68.0                                                          # C: sparse, inside the patch
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'A':len(pa),'B':len(pb),'B_on_path':int(on_path.sum()),'C':len(pc)}))
