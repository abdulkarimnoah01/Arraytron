"""Build the Mask demo (v0.5.0): hython tools/build_demo_mask_v050.py
The terrain of the Surface Scatter demo with two masked scatters: rocks whose DENSITY and SIZE follow fractal noise (patches of rocks, smaller ones at the
edges of the patches), and crates whose density follows a soft white blob image laid over the terrain from above (a crowd that thins out towards the edges).
Writes dist/Arraytron_<current>_mask_demo.hip and the exported render USD."""
from pathlib import Path
import sys, hou, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'mask');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
def row(node,index,**values):
    for key,value in values.items():node.parmTuple(f'proto_{key}{index}').set(value if isinstance(value,(tuple,list)) else (value,))
rock=reference('reference_rock','/World/Props/Rock',ASSETS+'/rock.usda');crate=reference('reference_crate','/World/Props/Crate',ASSETS+'/crate.usda',rock)
terrain=reference('reference_terrain','/World/Terrain',ASSETS+'/terrain.usda',crate)
rocks=stage.createNode(TYPE,'Arraytron_NoiseRocks');rocks.setInput(0,terrain);rocks.parm('outputpath').set('/World/Rocks')
rocks.parm('mode').set(5);rocks.parm('surface_prim').set('/World/Terrain');rocks.parm('surface_count').set(900);rocks.parm('surface_seed').set(2);rocks.parm('surface_normal').set(1);rocks.parm('surface_slope_max').set(40)
rocks.parm('protos').set(1);row(rocks,1,type=0,prim='/World/Props/Rock');rocks.parm('base_scale').set(0.2)
rocks.parm('mask_source').set(1);rocks.parm('mask_effect').set(2);rocks.parm('mask_minscale').set(0.35);rocks.parm('mask_noise_freq').set(0.55);rocks.parm('mask_low').set(0.35);rocks.parm('mask_high').set(0.8);rocks.parm('mask_seed').set(5)
rocks.setComment('MASK - fractal noise (Frequency 0.55) drives Density + Scale: patches of rocks, smaller towards the patch edges. 900 candidate points, Low 0.35 / High 0.8 sharpen the patches.')
rocks.setGenericFlag(hou.nodeFlag.DisplayComment,True)
crates=stage.createNode(TYPE,'Arraytron_ImageCrates');crates.setInput(0,rocks);crates.parm('outputpath').set('/World/Crates')
crates.parm('mode').set(5);crates.parm('surface_prim').set('/World/Terrain');crates.parm('surface_count').set(500);crates.parm('surface_seed').set(9);crates.parm('surface_slope_max').set(35)
crates.parm('protos').set(1);row(crates,1,type=0,prim='/World/Props/Crate');crates.parm('base_scale').set(0.16);crates.parm('rotation_random_mode').set(1);crates.parm('yaw_random').set(180)
crates.parm('mask_source').set(2);crates.parm('mask_image').set(ASSETS+'/mask_blob.exr');crates.parm('mask_proj').set(0);crates.parmTuple('mask_size').set((6,6));crates.parmTuple('mask_center').set((0,0))
crates.setComment('MASK - an image (a soft white blob, projected from above over the 6 x 6 terrain) drives the Density of the crates: a crowd in the middle that thins out to nothing at the edge.')
crates.setGenericFlag(hou.nodeFlag.DisplayComment,True)
camera=stage.createNode('camera','render_camera');camera.setInput(0,crates)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((-5.5,5.2,6.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.3,0.2,0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(192)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"mask")}.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(1600,900))
crates.setDisplayFlag(True)
renderstage=settings.stage();errors={n.name():n.errors() for n in (rock,crate,terrain,rocks,crates,camera,dome,sun,settings)}
assert renderstage and not any(errors.values()),errors
from pxr import UsdGeom
counts={p:len(UsdGeom.PointInstancer(renderstage.GetPrimAtPath(p)).GetPositionsAttr().Get() or []) for p in ('/World/Rocks','/World/Crates')}
assert 0<counts['/World/Rocks']<900 and 0<counts['/World/Crates']<500,counts
renderstage.Export(str(versions.render_usd(VID,'mask')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':counts}))
