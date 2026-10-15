"""Build the Field Stack demo (v0.7.0): hython tools/build_demo_fields_v070.py
A forest on the terrain thinned by a Field Stack (slope, distance to a road curve, noise, exclusion of a pond). Writes dist/Arraytron_<version>_fields_demo.hip and the render USD.
"""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'fields');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
def row(node,index,**values):
    for key,value in values.items():node.parmTuple(f'proto_{key}{index}').set(value if isinstance(value,(tuple,list)) else (value,))
from make_test_assets_v045 import height
from pxr import Usd, UsdGeom, Gf
POND_AT=(-1.3,1.6)                                          # a pond: a sphere sunk into the terrain at this x, z
pond_file=ROOT/'dist/test_assets/pond.usda';ps=Usd.Stage.CreateNew(str(pond_file));pr=UsdGeom.Xform.Define(ps,'/Pond');ps.SetDefaultPrim(pr.GetPrim());UsdGeom.SetStageUpAxis(ps,UsdGeom.Tokens.y)
sp=UsdGeom.Sphere.Define(ps,'/Pond/Water');sp.CreateRadiusAttr(0.55);UsdGeom.Xformable(sp).AddTranslateOp().Set(Gf.Vec3d(POND_AT[0],height(*POND_AT)+0.05,POND_AT[1]));ps.GetRootLayer().Save()
plant=reference('reference_plant','/World/Props/Fir',ASSETS+'/fir.usda');road=reference('reference_road','/World/Road',ASSETS+'/curve_s.usda',plant)
pondref=reference('reference_pond','/World/Pond',ASSETS+'/pond.usda',road);terrain=reference('reference_terrain','/World/Terrain',ASSETS+'/terrain.usda',pondref)
trees=stage.createNode(TYPE,'Arraytron_Forest_FieldStack');trees.setInput(0,terrain);trees.parm('outputpath').set('/World/Firs')
trees.parm('mode').set(5);trees.parm('surface_prim').set('/World/Terrain');trees.parm('surface_count').set(1600);trees.parm('surface_seed').set(4);trees.parm('surface_normal').set(1);trees.parm('surface_align').set(0.4)
trees.parm('protos').set(1);trees.parmTuple('proto_type1').set((0,));trees.parm('proto_prim1').set('/World/Props/Fir');trees.parm('scale_random_mode').set(1);trees.parm('scale_min').set(0.6);trees.parm('scale_max').set(1.3)
trees.parm('rotation_random_mode').set(1);trees.parm('yaw_random').set(180)
def field(i,**values):
    trees.parm('fields').set(max(trees.evalParm('fields'),i))
    for k,v in values.items():trees.parmTuple(f'{k}{i}').set(v if isinstance(v,(tuple,list)) else (v,))
field(1,field_type=1,field_prim='/World/Terrain',field_smin=0,field_smax=22,field_sfall=10)                              # only gentle ground
field(2,field_type=4,field_op=0,field_prim='/World/Road',field_dnear=0.25,field_dfar=0.9,field_daxes=0)                   # a clear road, softly edged
field(3,field_type=2,field_op=0,field_nfreq=0.55,field_nseed=6,field_ncontrast=3.0)                                         # patchy groves
field(4,field_type=5,field_op=0,field_prim='/World/Pond',field_xmargin=0.15,field_xfall=0.35)                              # nothing in the pond
trees.parm('field_effect').set(0)
trees.setComment('FIELD STACK - 1600 surface points thinned by four fields multiplied together: Slope (gentle ground only), Distance to the S road (clear road, soft edge), Noise (patchy groves) and Exclusion of the pond sphere.')
trees.setGenericFlag(hou.nodeFlag.DisplayComment,True)
crates=trees
camera=stage.createNode('camera','render_camera');camera.setInput(0,trees)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((-5.5,4.6,6.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.3,0.3,0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"fields")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
crates.setDisplayFlag(True)
errors={n.name():n.errors() for n in (plant,road,pondref,terrain,trees,camera,dome,sun,settings)}
from pxr import UsdGeom
rs=settings.stage();assert rs and not any(n.errors() for n in (trees,settings)),errors
pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/Firs'));kept=len(pi.GetPositionsAttr().Get(1) or []);assert 100<kept<1000,kept
rs.Export(str(versions.render_usd(VID,'fields')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'kept of 1600':kept}))
