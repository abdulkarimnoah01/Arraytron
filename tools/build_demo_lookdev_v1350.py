"""Build the Lookdev demo (v1.35.0): hython tools/build_demo_lookdev_v1350.py
A small material library (a Python LOP that writes /materials/tint, MaterialX standard_surface fed by an hsvadjust, and /materials/clay, a USD Preview Surface) is wired into two Area scatters:
  A  Lookdev > Material Assignment: /materials/tint on All Prototypes; Per-Instance Variation: hsvadjust1.amount from -0.45 1 1 to 0.45 1 1 per instance id, so every instance gets its own hue.
  B  /materials/clay on Prototype Row 1; Per-Instance Variation: preview.diffuseColor between a dark and a light clay colour per instance id.
  C  a ready-made asset (Houdini's rubber toy) with its own MaterialX material and textures: Operation Multiply tints its subsurface_color per instance, the texture is kept.
Asserts the bindings, the primvars (one value per instance, the same for the same id when the scatter changes) and the wiring. Writes dist/Arraytron_<version>_lookdev_demo.hip or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom, UsdShade
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'lookdev')
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage')
lib=stage.createNode('pythonscript','material_library');lib.setComment('Two materials written in Python for the demo: /materials/tint (MaterialX: standard_surface <- hsvadjust1) and /materials/clay (USD Preview Surface). Use your own Material Library LOP the same way.')
lib.parm('python').set('''from pxr import UsdShade, Sdf, Gf
stage=hou.pwd().editableStage()
def mtlx():
    m=UsdShade.Material.Define(stage,'/materials/tint')
    s=UsdShade.Shader.Define(stage,'/materials/tint/standard_surface1');s.CreateIdAttr('ND_standard_surface_surfaceshader')
    h=UsdShade.Shader.Define(stage,'/materials/tint/hsvadjust1');h.CreateIdAttr('ND_hsvadjust_color3')
    h.CreateInput('in',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.85,0.25,0.2));h.CreateInput('amount',Sdf.ValueTypeNames.Float3).Set(Gf.Vec3f(0,1,1))
    s.CreateInput('base_color',Sdf.ValueTypeNames.Color3f).ConnectToSource(h.CreateOutput('out',Sdf.ValueTypeNames.Color3f))
    s.CreateInput('specular_roughness',Sdf.ValueTypeNames.Float).Set(0.4)
    m.CreateSurfaceOutput('mtlx').ConnectToSource(s.CreateOutput('out',Sdf.ValueTypeNames.Token))
def preview():
    m=UsdShade.Material.Define(stage,'/materials/clay')
    s=UsdShade.Shader.Define(stage,'/materials/clay/preview');s.CreateIdAttr('UsdPreviewSurface')
    s.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.6,0.4,0.25));s.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(0.7)
    m.CreateSurfaceOutput().ConnectToSource(s.CreateOutput('surface',Sdf.ValueTypeNames.Token))
mtlx();preview()
''')
lib.setPosition((2,3))
def node(name,out,comment,x):
    a=stage.createNode(TYPE,name);assert a.hdaModule().test_setup(a);a.setInput(0,lib)
    a.parm('copy_test_ground').set(1);a.parm('outputpath').set(out);a.parm('mode').set(1);a.parm('area_count').set(1500);a.parm('area_sizex').set(10.0);a.parm('area_sizez').set(10.0)
    a.parm('scale_min').set(0.25);a.parm('scale_max').set(0.4);a.parm('bound_tx').set(x*12.0);a.setPosition((x*4,0));a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
a=node('Arraytron_A_HuePerInstance','/World/ArraytronA','A: Lookdev tab: /materials/tint (MaterialX) on All Prototypes, and hsvadjust1.amount varies per instance id: every instance gets its own hue.',0)
a.parm('lk_mats').set(1);a.parm('lk_target1').set(0);a.parm('lk_mat1').set('/materials/tint')
a.parm('lk_vars').set(1);a.parm('lk_vmat1').set('/materials/tint');a.parm('lk_vshader1').set('hsvadjust1');a.parm('lk_vinput1').set('amount');a.parm('lk_vtype1').set(1)
a.parmTuple('lk_vmin1').set((-0.45,1.0,1.0));a.parmTuple('lk_vmax1').set((0.45,1.0,1.0))
b=node('Arraytron_B_ClayPerRow','/World/ArraytronB','B: /materials/clay (USD Preview Surface) on Prototype Row 1, and its diffuseColor varies per instance between a dark and a light clay.',1)
b.parm('lk_mats').set(1);b.parm('lk_target1').set(1);b.parm('lk_row1').set(1);b.parm('lk_mat1').set('/materials/clay')
b.parm('lk_vars').set(1);b.parm('lk_vmat1').set('/materials/clay');b.parm('lk_vshader1').set('preview');b.parm('lk_vinput1').set('diffuseColor');b.parm('lk_vtype1').set(2)
b.parmTuple('lk_vmin1').set((0.25,0.13,0.07));b.parmTuple('lk_vmax1').set((0.95,0.7,0.45))
def check(n,mat,shader,inp):
    st=n.stage();assert not n.errors(),(n.name(),n.errors())
    pi=UsdGeom.PointInstancer(st.GetPrimAtPath(n.evalParm('outputpath')));ids=np.array(pi.GetIdsAttr().Get(),dtype=int)
    for t in pi.GetPrototypesRel().GetTargets():
        bound=UsdShade.MaterialBindingAPI(st.GetPrimAtPath(t)).GetDirectBinding().GetMaterialPath();assert str(bound)==mat,(t,bound)
    pv=UsdGeom.PrimvarsAPI(pi.GetPrim()).GetPrimvar('arraytron_lk1');vals=np.array(pv.Get());assert len(vals)==len(ids) and vals.std(axis=0).max()>0.05,(len(vals),len(ids))
    src=UsdShade.Shader(st.GetPrimAtPath(mat+'/'+shader)).GetInput(inp).GetConnectedSource();assert src and str(src[0].GetPath()).endswith('arraytron_lk1_reader'),src
    return ids,vals,n.evalParm('lk_info')
ia,va,info_a=check(a,'/materials/tint','hsvadjust1','amount');ib,vb,info_b=check(b,'/materials/clay','preview','diffuseColor')
assert np.allclose(va[:,1:],1.0) and va[:,0].min()<-0.3 and va[:,0].max()>0.3
# the value follows the id: more instances, the same ids keep their hue
before=dict(zip(ia.tolist(),va[:,0].tolist()));a.parm('area_count').set(2000);ia2,va2,_=check(a,'/materials/tint','hsvadjust1','amount')
common=[i for i in ia2.tolist() if i in before];after=dict(zip(ia2.tolist(),va2[:,0].tolist()));assert common and max(abs(before[i]-after[i]) for i in common)<1e-6
a.parm('area_count').set(1500)
# C: a ready-made USD asset (Houdini's rubber toy) keeps its own MaterialX material and textures; Multiply tints subsurface_color (what drives its look) per instance
toy=stage.createNode('reference','rubbertoy');toy.parm('filepath1').set('$HH/usd/assets/rubbertoy/rubbertoy.usd');toy.parm('primpath1').set('/rubbertoy')
c=stage.createNode(TYPE,'Arraytron_C_ReadyAsset');assert c.hdaModule().test_setup(c);c.setInput(0,toy);c.parm('copy_test_ground').set(1)
c.parm('proto_type1').set(0);c.parm('proto_prim1').set('/rubbertoy');c.parm('outputpath').set('/World/ArraytronC');c.parm('mode').set(1);c.parm('area_count').set(60);c.parm('area_sizex').set(10.0);c.parm('area_sizez').set(10.0)
c.parm('scale_min').set(0.6);c.parm('scale_max').set(0.8);c.parm('bound_tx').set(24.0);c.setComment('C: a ready-made asset (the rubber toy) keeps its own material and textures: Lookdev multiplies its subsurface_color by a random colour per instance (Operation Multiply).');c.setGenericFlag(hou.nodeFlag.DisplayComment,True)
toymat='/World/ArraytronC/Prototypes/rubbertoy/mtl/ToyShader'
c.parm('lk_vars').set(1);c.parm('lk_vmat1').set(toymat);c.parm('lk_vshader1').set('materialx/mtlxstandard_surface');c.parm('lk_vinput1').set('subsurface_color');c.parm('lk_vop1').set(1);c.parm('lk_vtype1').set(1)
c.parmTuple('lk_vmin1').set((0.15,0.15,0.15));c.parmTuple('lk_vmax1').set((1.0,1.0,1.0))
sc=c.stage();assert not c.errors(),c.errors();mix=UsdShade.Shader(UsdShade.Shader(sc.GetPrimAtPath(toymat+'/materialx/mtlxstandard_surface')).GetInput('subsurface_color').GetConnectedSource()[0].GetPrim())
assert mix.GetIdAttr().Get()=='ND_multiply_color3' and str(mix.GetInput('in1').GetConnectedSource()[0].GetPath()).endswith('mtlximage_color')            # the texture is kept
merge=stage.createNode('merge','merge_all');merge.setInput(0,a);merge.setInput(1,b);merge.setInput(2,c);merge.setDisplayFlag(True)
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'A':len(ia),'B':len(ib),'info_A':info_a,'info_B':info_b}))
