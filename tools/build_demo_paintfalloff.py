"""Build the Paint Falloff demo of Arraytron Stamp: hython tools/build_demo_paintfalloff.py   (hython 22 or 20.5; build the Stamp first with tools/build_stamp_light.py)
Hilly ground with a steep mound and simple rock spheres, so the falloff is easy to read. Six Stamp nodes, each painted with the same engine as the tool (stamp_paint_path), the same radius, density and Seed:
  1 Uniform         no falloff (the classic dab brush)
  2 Density only    Density Falloff on: fewer rocks towards the rim of the stroke, all the same size
  3 Scale only      Scale Falloff on: the same number everywhere, smaller towards the rim
  4 Soft Natural    both (the Soft Natural preset)
  5 Long stroke     one long S curve across the whole ground with the Soft Natural preset: a continuous ribbon, no circles at the dabs
  6 Uneven terrain  strokes across the steep mound and down its side, Growth preset
Writes dist/Arraytron_Stamp_v0.9.3_paint_falloff_demo.hip, or otls_h205/..._H205_paint_falloff_demo.hip with hython 20.5. --release <folder>: into that folder, without recording the HDA library."""
from pathlib import Path
import sys, json, time, hou
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import versions
ROOT=Path(__file__).resolve().parents[1];H205=versions.is_h205();TYPE='arraytron::stamp::0.9.3'
HDA=ROOT/('otls_h205' if H205 else 'dist')/('Arraytron_Stamp_v0.9.3%s.hda'%('_H205' if H205 else ''));HIP=ROOT/('otls_h205' if H205 else 'dist')/('Arraytron_Stamp_v0.9.3%s_paint_falloff_demo.hip'%('_H205' if H205 else ''))
SCENE='''from pxr import Gf, UsdGeom, Vt
import hou, math
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World')
g=UsdGeom.Mesh.Define(stage,'/World/Ground');n=140;pts=[];idx=[]
def height(x,z):
    h=0.5*math.sin(x*0.35)*math.cos(z*0.3)
    d=math.hypot(x-8.0,z-15.0);h+=3.2*math.exp(-(d*d)/(2*3.0*3.0))                  # a steep mound for the uneven terrain strip
    return h
for j in range(n+1):
    for i in range(n+1):
        x=-18+36*i/n;z=-18+36*j/n;pts.append(Gf.Vec3f(x,height(x,z),z))
for j in range(n):
    for i in range(n):idx+=[j*(n+1)+i,(j+1)*(n+1)+i,(j+1)*(n+1)+i+1,j*(n+1)+i+1]
g.CreatePointsAttr(Vt.Vec3fArray(pts));g.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));g.CreateFaceVertexIndicesAttr(Vt.IntArray(idx));g.CreateSubdivisionSchemeAttr('none');g.CreateDisplayColorAttr([Gf.Vec3f(0.33,0.46,0.3)])
UsdGeom.Xform.Define(stage,'/World/Props/Rock');s=UsdGeom.Sphere.Define(stage,'/World/Props/Rock/Geom');s.CreateRadiusAttr(0.22);s.CreateDisplayColorAttr([Gf.Vec3f(0.62,0.6,0.56)])
'''
RELEASE_DIR=Path(sys.argv[sys.argv.index('--release')+1]) if '--release' in sys.argv else None
if RELEASE_DIR is not None:RELEASE_DIR.mkdir(parents=True,exist_ok=True);HIP=RELEASE_DIR/HIP.name
hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(HDA),change_oplibraries_file=RELEASE_DIR is None,force_use_assets=True);hou.hipFile.save(str(HIP))
stage=hou.node('/stage');scene=stage.createNode('pythonscript','ground_and_rocks');scene.parm('python').set(SCENE)
def stamper(name,comment,preset=None,**parms):
    a=stage.createNode(TYPE,name);a.setInput(0,scene);a.parm('outputpath').set('/World/'+name);a.parm('target').set('/World/Ground');a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Rock')
    a.parm('paint_radius').set(1.6);a.parm('paint_density').set(6.0);a.parm('paint_spacing').set(0.25);a.parm('seed').set(11);a.parmTuple('scalerange').set((0.8,1.2));a.parm('yawrand').set(180.0)
    if preset:a.hdaModule().stamp_paint_preset(a,preset)
    for k,v in parms.items():a.parm(k).set(v)
    a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
def paint(a,pts):
    m=a.hdaModule();sf=m.stamp_surface(a);return m.stamp_paint_path(a,sf,pts,m.stamp_proto_bounds(a))
line=lambda z,x0=-15.0,x1=15.0:[(x,0.0,z) for x in np.arange(x0,x1+1e-9,0.25)]
nodes=[stamper('Paint1_Uniform','1 Uniform: no falloff (the classic dab brush).','uniform'),
       stamper('Paint2_DensityOnly','2 Density only: fewer rocks towards the rim of the stroke, all the same size.',None,paint_dens_on=1,paint_dens_min=0,paint_dens_width=100),
       stamper('Paint3_ScaleOnly','3 Scale only: the same number everywhere, smaller towards the rim (30 % at the edge).',None,paint_scale_on=1,paint_scale_min=30,paint_scale_width=100),
       stamper('Paint4_SoftNatural','4 Soft Natural preset: both falloffs.','soft'),
       stamper('Paint5_LongStroke','5 One long S curve with the Soft Natural preset: a continuous ribbon, no circles at the dabs.','soft'),
       stamper('Paint6_UnevenTerrain','6 Strokes across the steep mound and down its side, Growth preset.','growth')]
rows=[-15.0,-10.5,-6.0,-1.5]
paint(nodes[0],line(rows[0]));paint(nodes[1],line(rows[1]));paint(nodes[2],line(rows[2]));paint(nodes[3],line(rows[3]))
paint(nodes[4],[(x,0.0,3.5+2.5*np.sin(x*0.3)) for x in np.arange(-16.0,16.0+1e-9,0.2)])
paint(nodes[5],[(x,0.0,15.0) for x in np.arange(0.0,16.0,0.2)]);paint(nodes[5],[(8.0,0.0,z) for z in np.arange(9.0,17.4,0.2)])
merge=stage.createNode('merge','merge_all')
for i,n in enumerate(nodes):merge.setInput(i,n);assert not n.errors(),(n.name(),n.errors())
merge.setDisplayFlag(True)
def read(n):
    pi=__import__('pxr').UsdGeom.PointInstancer(n.stage().GetPrimAtPath(n.evalParm('outputpath')));return np.array(pi.GetScalesAttr().Get(hou.frame())).reshape(-1,3)
counts=[len(read(n)) for n in nodes];sc=[read(n)[:,0] for n in nodes]
assert all(c>100 for c in counts) and np.allclose(sc[1].std(),sc[1].std()) and sc[2].min()<0.5*sc[2].max()
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':str(HIP),'stamps':counts}))
