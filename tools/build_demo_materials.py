"""Build the Material Variants demo of Arraytron Stamp: hython tools/build_demo_materials.py   (hython 22 or 20.5; build the Stamp first with tools/build_stamp_light.py)
A ground, three props (a rock, a tree, a crate) each with its own material, and eight UsdPreviewSurface materials. Five Stamp nodes, all point instancers:
  1 Mat1_Random       rocks, Materials /World/Materials/rock_* (three), Material: Random: every rock draws one of them by the Seed
  2 Mat2_Edited       trees placed with their own material, then edited afterwards: the middle third set to 1 (autumn), the last third to 2 (spring) with stamp_material_edit
  3 Mat3_Painted      a Paint stroke (Soft Natural falloff) of rocks and crates (Random Prototype), each with a random material of its own row
  4 Mat4_Group        a custom Group layout captured from three stamps with three materials, stamped five times: every copy keeps the materials
  5 Mat5_Select10k    10 000 small rocks with random materials, to try the Edit mode with many stamps (box select, M, the STAMPS table)
Writes dist/Arraytron_Stamp_v<ver>_materials_demo.hip, or otls_h205/..._H205_materials_demo.hip with hython 20.5. --release <folder>: into that folder, without recording the HDA library."""
from pathlib import Path
import sys, re, json, hou
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import versions
ROOT=Path(__file__).resolve().parents[1];H205=versions.is_h205()
VER=re.search(r"STAMP_VERSION='([0-9.]+)'",(ROOT/'tools'/'build_stamp_light.py').read_text(encoding='utf-8')).group(1);TYPE='arraytron::stamp::%s'%VER
FOLDER=ROOT/('otls_h205' if H205 else 'dist');SUFFIX='_H205' if H205 else ''
HDA=FOLDER/('Arraytron_Stamp_v%s%s.hda'%(VER,SUFFIX));HIP=FOLDER/('Arraytron_Stamp_v%s%s_materials_demo.hip'%(VER,SUFFIX))
SCENE='''from pxr import Gf, Sdf, UsdGeom, UsdShade, Vt
import math
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World')
def material(name,color,rough=0.6):
    m=UsdShade.Material.Define(stage,'/World/Materials/'+name);s=UsdShade.Shader.Define(stage,'/World/Materials/%s/surface'%name);s.CreateIdAttr('UsdPreviewSurface')
    s.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color));s.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(rough)
    m.CreateSurfaceOutput().ConnectToSource(s.ConnectableAPI(),'surface');return m
UsdGeom.Scope.Define(stage,'/World/Materials')
mats={n:material(n,c) for n,c in (('ground',(0.32,0.42,0.28)),('rock_grey',(0.55,0.55,0.55)),('rock_red',(0.62,0.25,0.18)),('rock_moss',(0.25,0.5,0.2)),
                                   ('tree_autumn',(0.85,0.45,0.1)),('tree_spring',(0.55,0.85,0.3)),('crate_wood',(0.6,0.42,0.22)),('crate_blue',(0.2,0.35,0.8)),('own_white',(0.92,0.92,0.92)))}
def bind(path,name):UsdShade.MaterialBindingAPI.Apply(stage.GetPrimAtPath(path)).Bind(mats[name])
g=UsdGeom.Mesh.Define(stage,'/World/Ground');n=120;pts=[];idx=[]
for j in range(n+1):
    for i in range(n+1):
        x=-60+120*i/n;z=-30+60*j/n;pts.append(Gf.Vec3f(x,0.35*math.sin(x*0.25)*math.cos(z*0.2),z))
for j in range(n):
    for i in range(n):idx+=[j*(n+1)+i,(j+1)*(n+1)+i,(j+1)*(n+1)+i+1,j*(n+1)+i+1]
g.CreatePointsAttr(Vt.Vec3fArray(pts));g.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));g.CreateFaceVertexIndicesAttr(Vt.IntArray(idx));g.CreateSubdivisionSchemeAttr('none');bind('/World/Ground','ground')
UsdGeom.Xform.Define(stage,'/World/Props/Rock');r=UsdGeom.Sphere.Define(stage,'/World/Props/Rock/Geom');r.CreateRadiusAttr(0.45);UsdGeom.Xformable(r).AddScaleOp().Set(Gf.Vec3f(1.0,0.6,0.85));bind('/World/Props/Rock/Geom','own_white')
UsdGeom.Xform.Define(stage,'/World/Props/Tree');t=UsdGeom.Cone.Define(stage,'/World/Props/Tree/Crown');t.CreateRadiusAttr(0.7);t.CreateHeightAttr(2.0);t.CreateAxisAttr('Y');UsdGeom.Xformable(t).AddTranslateOp().Set(Gf.Vec3d(0,1.6,0))
k=UsdGeom.Cylinder.Define(stage,'/World/Props/Tree/Trunk');k.CreateRadiusAttr(0.15);k.CreateHeightAttr(0.6);k.CreateAxisAttr('Y');UsdGeom.Xformable(k).AddTranslateOp().Set(Gf.Vec3d(0,0.3,0))
bind('/World/Props/Tree/Crown','own_white');bind('/World/Props/Tree/Trunk','crate_wood')
UsdGeom.Xform.Define(stage,'/World/Props/Crate');c=UsdGeom.Cube.Define(stage,'/World/Props/Crate/Geom');c.CreateSizeAttr(0.8);bind('/World/Props/Crate/Geom','own_white')
'''
RELEASE_DIR=Path(sys.argv[sys.argv.index('--release')+1]) if '--release' in sys.argv else None
if RELEASE_DIR is not None:RELEASE_DIR.mkdir(parents=True,exist_ok=True);HIP=RELEASE_DIR/HIP.name
hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(HDA),change_oplibraries_file=RELEASE_DIR is None,force_use_assets=True);hou.hipFile.save(str(HIP))
stage=hou.node('/stage');scene=stage.createNode('pythonscript','ground_props_materials');scene.parm('python').set(SCENE)
ROWS={'Rock':('/World/Props/Rock','/World/Materials/rock_*'),'Tree':('/World/Props/Tree','/World/Materials/tree_autumn /World/Materials/tree_spring'),'Crate':('/World/Props/Crate','/World/Materials/crate_wood /World/Materials/crate_blue')}
def stamper(name,comment,rows,**parms):
    a=stage.createNode(TYPE,name);a.setInput(0,scene);a.parm('outputpath').set('/World/'+name);a.parm('target').set('/World/Ground');a.parm('protos').set(len(rows))
    for i,key in enumerate(rows,1):a.parm('proto_prim%d'%i).set(ROWS[key][0]);a.parm('proto_mats%d'%i).set(ROWS[key][1])
    a.parm('seed').set(5);a.parm('yawrand').set(180.0);a.parmTuple('scalerange').set((0.8,1.25))
    for k,v in parms.items():(a.parmTuple(k).set(v) if isinstance(v,tuple) else a.parm(k).set(v))
    a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
def place(a,points,proto=None):
    m=a.hdaModule();sf=m.stamp_surface(a);bd=m.stamp_proto_bounds(a)
    for p in points:
        h=sf.hit((p[0],50.0,p[1]),(0.0,-1.0,0.0),stamps=False);m.stamp_add(a,h[0],h[1],bounds=bd,proto=proto)
nodes=[]
a=stamper('Mat1_Random','1 Random: every rock draws one of the three rock_* materials (Brush > Randomization > Material: Random).',['Rock'],matmode=0)
place(a,[(x,z) for x in np.arange(-55.0,-35.0,1.6) for z in np.arange(-25.0,-15.0,1.6)]);nodes.append(a)
a=stamper('Mat2_Edited',"2 Edited afterwards: placed with their own material (white), then the middle third set to 1 (autumn), the last third to 2 (spring).",['Tree'],matmode=2)
place(a,[(x,-20.0+(k%2)*3.0) for k,x in enumerate(np.arange(-30.0,-6.0,2.0))]);m=a.hdaModule();n=m.stamp_count(a.evalParm('stamps'))
m.stamp_material_edit(a,range(n//3,2*n//3),'set',1);m.stamp_material_edit(a,range(2*n//3,n),'set',2);nodes.append(a)
a=stamper('Mat3_Painted','3 A Paint stroke (Soft Natural falloff) of rocks and crates: each stamp a random material of its own row.',['Rock','Crate'],matmode=0,protorand=1,paint_radius=2.5,paint_density=2.5,paint_spacing=0.6)
m=a.hdaModule();m.stamp_paint_preset(a,'soft');sf=m.stamp_surface(a);m.stamp_paint_path(a,sf,[(x,0.0,-20.0+4.0*np.sin(x*0.25)) for x in np.arange(0.0,30.0,0.2)],m.stamp_proto_bounds(a));nodes.append(a)
a=stamper('Mat4_Group','4 A custom Group layout (a tree, two rocks) captured with their materials and stamped five times: every copy keeps them.',['Tree','Rock'],matmode=2)
m=a.hdaModule();a.parm('stamps').set('0 0 0  0 0 0  1 1 1  1 1 1\n1.6 0 0.4  0 40 0  1 1 1  2 1 2\n-0.8 0 1.2  0 0 0  0.7 0.7 0.7  2 1 3');m.stamp_set_selection(a,[0,1,2]);m.stamp_group_capture_selected(a)
a.parm('stamps').set('');sf=m.stamp_surface(a);bd=m.stamp_proto_bounds(a)
for x in (36.0,42.0,48.0,54.0,45.0):
    h=sf.hit((x,50.0,-20.0 if x!=45.0 else -14.0),(0.0,-1.0,0.0),stamps=False);m.stamp_group_add(a,sf,h[0],h[1],bounds=bd)
a.parm('brush').set(0);m.stamp_set_selection(a,[]);nodes.append(a)
a=stamper('Mat5_Select10k','5 10 000 rocks with random materials: try the Edit mode (Shift+B), box select, M for the next material, the STAMPS table.',['Rock'],matmode=0,onstamps=0,sit=0)
rg=np.random.RandomState(7);m=a.hdaModule();cfg=m.stamp_settings(a);lines=[]
for k in range(10000):
    x=rg.uniform(-58.0,58.0);z=rg.uniform(-8.0,28.0);nx=m.stamp_make(cfg,k+1);s=0.45*nx['scale']
    lines.append(m.stamp_line((x,0.35*np.sin(x*0.25)*np.cos(z*0.2),z),m.stamp_euler(nx['quat']),(s,s,s),1,mat=nx['mat']))
a.parm('stamps').set('\n'.join(lines));nodes.append(a)
merge=stage.createNode('merge','merge_all')
for i,n in enumerate(nodes):merge.setInput(i,n)
merge.setDisplayFlag(True)
from pxr import UsdGeom, UsdShade
st=merge.stage();report={}
for n in nodes:
    assert not n.errors(),(n.name(),n.errors())
    pi=UsdGeom.PointInstancer(st.GetPrimAtPath('/World/'+n.name()));idx=list(pi.GetProtoIndicesAttr().Get(hou.frame()));tg=[str(t) for t in pi.GetPrototypesRel().GetTargets()]
    bound=[str(UsdShade.MaterialBindingAPI(st.GetPrimAtPath(t)).ComputeBoundMaterial()[0].GetPath()).rsplit('/',1)[-1] or 'own' for t in tg]
    report[n.name()]=dict(stamps=len(idx),prototypes=len(tg),materials=sorted({bound[i] for i in set(idx)}))
assert report['Mat1_Random']['materials']==['rock_grey','rock_moss','rock_red'] and report['Mat5_Select10k']['stamps']==10000,report
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':str(HIP),'nodes':report}))
