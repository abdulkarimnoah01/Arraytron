"""Build the Surface Scatter demo (v0.4.6): hython tools/build_demo_scatter_v046.py
A bumpy 6 x 6 m terrain (a Mesh prim in the stream) with a steep bank on one side. Two Arraytron nodes scatter on it: small rocks on the gentle ground
(Slope Max 40, Align to Normal 0.8, smooth normals, Min / Max scale) and crates tilted onto the steep bank (Slope Min 28, full Align to Normal).
Writes dist/Arraytron_v0.4.6_scatter_demo.hip and the exported render USD."""
from pathlib import Path
import sys, hou, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID='v0.4.6';assert versions.resolve(VID)==versions.CURRENT
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'scatter');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True)
versions.ensure_installed(VID)
hou.hipFile.save(str(HIP))
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
def row(node,index,**values):
    for key,value in values.items():node.parmTuple(f'proto_{key}{index}').set(value if isinstance(value,(tuple,list)) else (value,))
rock=reference('reference_rock','/World/Props/Rock',ASSETS+'/rock.usda')
crate=reference('reference_crate','/World/Props/Crate',ASSETS+'/crate.usda',rock)
terrain=reference('reference_terrain','/World/Terrain',ASSETS+'/terrain.usda',crate)

rocks=stage.createNode(TYPE,'Arraytron_Rocks');rocks.setInput(0,terrain);rocks.parm('outputpath').set('/World/Rocks')
rocks.parm('mode').set(5);rocks.parm('surface_prim').set('/World/Terrain');rocks.parm('surface_count').set(260);rocks.parm('surface_seed').set(7)
rocks.parm('surface_normal').set(1);rocks.parm('surface_align').set(0.8);rocks.parm('surface_slope_max').set(40);rocks.parm('surface_offset').set(-0.02)
rocks.parm('protos').set(1);row(rocks,1,type=0,prim='/World/Props/Rock')
rocks.parm('base_scale').set(0.22);rocks.parm('scale_random_mode').set(1);rocks.parm('scale_min').set(0.5);rocks.parm('scale_max').set(1.3)
rocks.parm('rotation_random_mode').set(1);rocks.parm('yaw_random').set(180)
rocks.setComment('SURFACE - 260 rocks on the gentle ground only (Slope Max 40), smooth normals, Align to Normal 0.8, Yaw Only 180 (turning about the surface normal), Min / Max scale.')
rocks.setGenericFlag(hou.nodeFlag.DisplayComment,True)

crates=stage.createNode(TYPE,'Arraytron_Bank');crates.setInput(0,rocks);crates.parm('outputpath').set('/World/BankCrates')
crates.parm('mode').set(5);crates.parm('surface_prim').set('/World/Terrain');crates.parm('surface_count').set(90);crates.parm('surface_seed').set(3)
crates.parm('surface_normal').set(1);crates.parm('surface_align').set(1);crates.parm('surface_slope_min').set(28)
crates.parm('protos').set(1);row(crates,1,type=0,prim='/World/Props/Crate');crates.parm('base_scale').set(0.22);crates.parm('rotation_random_mode').set(1);crates.parm('yaw_random').set(180)
crates.setComment('SURFACE - 90 crates on the steep bank only (Slope Min 28), Align to Normal 1: each crate sits square on the slope.')
crates.setGenericFlag(hou.nodeFlag.DisplayComment,True)

camera=stage.createNode('camera','render_camera');camera.setInput(0,crates)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200)
camera.parmTuple('t').set((-5.5,4.2,6.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.3,0.2,0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=stage.createNode('karmarendersettings','karma_xpu');settings.setInput(0,sun)
settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(192)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"scatter")}.exr')
settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();settings.parmTuple('resolution').set((1600,900))
crates.setDisplayFlag(True)
renderstage=settings.stage();errors={n.name():n.errors() for n in (rock,crate,terrain,rocks,crates,camera,dome,sun,settings)}
assert renderstage and not any(errors.values()),errors
from pxr import UsdGeom
counts={p:len(UsdGeom.PointInstancer(renderstage.GetPrimAtPath(p)).GetPositionsAttr().Get()) for p in ('/World/Rocks','/World/BankCrates')}
assert counts=={'/World/Rocks':260,'/World/BankCrates':90},counts
renderstage.Export(str(versions.render_usd(VID,'scatter')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'instances':counts},indent=1))
