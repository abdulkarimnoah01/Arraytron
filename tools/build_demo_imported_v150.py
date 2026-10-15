"""Build the Imported Points demo (v1.5.0): hython tools/build_demo_imported_v150.py
Firs and rocks on the points of a (fake) FX simulation in /obj, with percentages, scale from pscale, orientation along the velocity and ids kept for AOVs. Writes dist/Arraytron_<version>_imported_demo.hip and the render USD (frame 48)."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'imported');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
def row(node,index,**values):
    for key,value in values.items():node.parmTuple(f'proto_{key}{index}').set(value if isinstance(value,(tuple,list)) else (value,))
# ---- a fake FX simulation in /obj: 1800 particles thrown from a fountain over the terrain (ballistic, animated, with id / pscale / v / Cd / age)
SIM_VEX="""int n = 1800;
for (int k = 0; k < n; k++) {
    float a = rand(k*3.1)*6.2831853, r = rand(k*7.7)*0.25, sp = 1.6 + rand(k*1.9)*1.4, up = 2.8 + rand(k*5.3)*1.6;
    float born = rand(k*2.3)*1.6;
    float t = max(0.0, (@Frame - 1)/24.0 - born);
    vector v0 = set(cos(a)*sp, up, sin(a)*sp);
    vector p0 = set(-1.2 + cos(a)*r, 0.15, 0.4 + sin(a)*r);
    vector p = p0 + v0*t + set(0.0, -4.9*t*t, 0.0);
    p.y = max(p.y, 0.02);
    int pt = addpoint(0, p);
    vector vel = v0 + set(0.0, -9.8*t, 0.0);
    setpointattrib(0, "id", pt, 40000 + k*3);
    setpointattrib(0, "pscale", pt, 0.7 + rand(k*9.1)*0.8);
    setpointattrib(0, "v", pt, vel);
    setpointattrib(0, "Cd", pt, set(rand(k*4.1), 0.3 + 0.7*rand(k*6.1), 0.2));
    setpointattrib(0, "age", pt, t);
}
"""
fx=hou.node('/obj').createNode('geo','fx_sim');wr=fx.createNode('attribwrangle','sim');wr.parm('class').set(0);wr.parm('snippet').set(SIM_VEX);wr.setDisplayFlag(True);wr.setRenderFlag(True)
plant=reference('reference_plant','/World/Props/Fir',ASSETS+'/fir.usda');rock=reference('reference_rock','/World/Props/Rock',ASSETS+'/rock.usda',plant);terrain=reference('reference_terrain','/World/Terrain',ASSETS+'/terrain.usda',rock)
trees=stage.createNode(TYPE,'Arraytron_ImportedPoints');trees.setInput(0,terrain);trees.parm('outputpath').set('/World/Debris')
trees.parm('mode').set(8);trees.parm('imp_sop').set('/obj/fx_sim/sim');trees.parm('imp_scale').set(1);trees.parm('imp_scale_mult').set(0.5);trees.parm('imp_orient').set(2)
trees.parm('protos').set(2);trees.parm('proto_prim1').set('/World/Props/Fir');trees.parm('proto_weight1').set(3.0);trees.parm('proto_prim2').set('/World/Props/Rock');trees.parm('proto_weight2').set(7.0);trees.parm('proto_mode').set(4);trees.parm('proto_seed').set(2);trees.parm('proto_scale1').set(0.8);trees.parm('proto_scale2').set(0.38)
trees.parm('scale_random_mode').set(1);trees.parm('scale_min').set(0.8);trees.parm('scale_max').set(1.25);trees.parm('rotation_random_mode').set(1);trees.parm('yaw_random').set(180)
trees.parm('pv_id').set(1);trees.parm('pv_srcid').set(1);trees.parm('pv_proto').set(1);trees.parm('imp_copy').set('age');trees.parm('pv_copy').set('age')
trees.setComment('IMPORTED POINTS - the instances ride on the points of an FX simulation (/obj/fx_sim/sim, 1800 animated particles): 30% firs and 70% rocks (Selection Mode Even Percent), scale from pscale x 0.5 (the bank scales set per prototype), oriented along the velocity, ids kept from the simulation (primvars:arraytron_id, source_id for AOVs), age copied as a primvar. Scrub the timeline.')
trees.setGenericFlag(hou.nodeFlag.DisplayComment,True)
hou.setFrame(48)
crates=trees
camera=stage.createNode('camera','render_camera');camera.setInput(0,trees)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((-5.5,4.6,6.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.3,0.3,0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"imported")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
crates.setDisplayFlag(True)
errors={n.name():n.errors() for n in (plant,rock,terrain,trees,camera,dome,sun,settings)}
from pxr import UsdGeom
rs=settings.stage();assert rs and not any(n.errors() for n in (trees,settings)),errors
pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/Debris'));kept=len(pi.GetPositionsAttr().Get(hou.frame()) or []);assert 1000<kept<=1800,kept
rs.Export(str(versions.render_usd(VID,'imported')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':kept}))
