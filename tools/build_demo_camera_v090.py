"""Build the Camera demo (v0.9.0): hython tools/build_demo_camera_v090.py
Firs on the terrain with Camera Optimisation (frustum culling, density by distance) and Level Of Detail (hero fir, orange LOD 1 cone, red proxy cone) driven by the render camera. Writes dist/Arraytron_<version>_camera_demo.hip and the render USD."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'camera');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
def row(node,index,**values):
    for key,value in values.items():node.parmTuple(f'proto_{key}{index}').set(value if isinstance(value,(tuple,list)) else (value,))
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf
def lod_asset(path,name,color,radius,height):
    """A one-cone stand-in for the fir (origin at the base like fir.usda): LOD 1 is a single orange cone, the proxy a small red cone, so the levels show up in a render."""
    st=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(st,'/'+name);st.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(st,UsdGeom.Tokens.y)
    mat=UsdShade.Material.Define(st,'/%s/Looks/M'%name);sh=UsdShade.Shader.Define(st,'/%s/Looks/M/Surface'%name);sh.CreateIdAttr('UsdPreviewSurface');sh.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color));mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(),'surface')
    cone=UsdGeom.Cone.Define(st,'/%s/Cone'%name);cone.CreateRadiusAttr(radius);cone.CreateHeightAttr(height);cone.CreateAxisAttr('Y');UsdGeom.Xformable(cone).AddTranslateOp().Set(Gf.Vec3d(0,height*0.5,0));UsdShade.MaterialBindingAPI.Apply(cone.GetPrim()).Bind(mat);st.GetRootLayer().Save()
lod_asset(ROOT/'dist/test_assets/fir_lod1.usda','FirLod1',(0.95,0.55,0.1),0.14,0.55);lod_asset(ROOT/'dist/test_assets/fir_proxy.usda','FirProxy',(0.9,0.12,0.1),0.1,0.5)
plant=reference('reference_plant','/World/Props/Fir',ASSETS+'/fir.usda');lod1=reference('reference_lod1','/World/Props/FirLod1',ASSETS+'/fir_lod1.usda',plant);proxy=reference('reference_proxy','/World/Props/FirProxy',ASSETS+'/fir_proxy.usda',lod1)
terrain=reference('reference_terrain','/World/Terrain',ASSETS+'/terrain.usda',proxy)
camera=stage.createNode('camera','render_camera');camera.setInput(0,terrain)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(60);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((-5.5,4.6,6.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.3,0.3,0))
trees=stage.createNode(TYPE,'Arraytron_Camera');trees.setInput(0,camera);trees.parm('outputpath').set('/World/Firs')
trees.parm('mode').set(5);trees.parm('surface_prim').set('/World/Terrain');trees.parm('surface_count').set(3000);trees.parm('surface_seed').set(4);trees.parm('surface_normal').set(1);trees.parm('surface_align').set(0.4)
trees.parm('protos').set(1);trees.parm('proto_prim1').set('/World/Props/Fir');trees.parm('proto_lod11').set('/World/Props/FirLod1');trees.parm('proto_proxy1').set('/World/Props/FirProxy')
trees.parm('scale_random_mode').set(1);trees.parm('scale_min').set(0.6);trees.parm('scale_max').set(1.3);trees.parm('rotation_random_mode').set(1);trees.parm('yaw_random').set(180)
trees.parm('overlap_mode').set(1);trees.parm('overlap_size').set(1);trees.parm('overlap_radius').set(0.06);trees.parm('overlap_tolerance').set(1.0)
trees.parm('cam_on').set(1);trees.parm('cam_prim').set('/World/Camera');trees.parm('cam_frustum').set(1);trees.parm('cam_margin').set(0.05);trees.parm('cam_densityon').set(1);trees.parm('cam_dnear').set(7.5);trees.parm('cam_dfar').set(13.0);trees.parm('cam_dmin').set(0.35)
trees.parm('cam_lod').set(1);trees.parm('lod_by').set(0);trees.parm('lod_d1').set(8.0);trees.parm('lod_d3').set(10.5);trees.parm('pv_id').set(1);trees.parm('pv_random').set(1);trees.parm('pv_proto').set(1);trees.parm('pv_lod').set(1)
trees.setComment('CAMERA + LOD - 3000 firs; Camera Optimisation hides what the render camera cannot see (frustum, 5% margin; the long lens leaves the terrain edges out of frame) and thins the far ones; Level Of Detail swaps the hero fir for an orange cone beyond 8 units and a red proxy cone beyond 10.5. Nothing is deleted: hidden instances are in invisibleIds, switch Camera Optimisation off to get them all back.')
trees.setGenericFlag(hou.nodeFlag.DisplayComment,True)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,trees);intensity=lambda light,value:(light.parm('xn__inputsintensity_control_jeb').set('set'),light.parm('xn__inputsintensity_i0a').set(value));intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"camera")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
trees.setDisplayFlag(True)
errors={n.name():n.errors() for n in (plant,lod1,proxy,terrain,camera,trees,dome,sun,settings)}
from pxr import UsdGeom as _G
rs=settings.stage();assert rs and not any(n.errors() for n in (trees,settings)),errors
info=trees.parm('cam_info').eval();print(info)
pi=_G.PointInstancer(rs.GetPrimAtPath('/World/Firs'));total=len(pi.GetPositionsAttr().Get(1) or []);hidden=len(pi.GetInvisibleIdsAttr().Get(1) or []);assert total>500 and 0<hidden<total,(total,hidden)
rs.Export(str(versions.render_usd(VID,'camera')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':total,'hidden':hidden}))
