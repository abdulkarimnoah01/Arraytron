"""Build the Grow demo (v0.5.2): hython tools/build_demo_grow_v052.py
The terrain with two animated scatters: little fir trees (Surface Scatter on the gentle ground) that GROW as a wave sweeps from the left edge to the right
(Plant style: taller first, wider later; Overshoot easing; a random delay so the wave front is organic), and crates that POP UP out of the ground from the
middle outwards (Rise style, Outward From Centre). Writes dist/Arraytron_<version>_grow_demo.hip and one exported render USD per frame in FRAMES
(Arraytron_<version>_grow_demo_render_f####.usda); render them with tools/render_grow_sheet.py."""
from pathlib import Path
import sys, hou, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD;FRAMES=(1,24,44,64,84,110)
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'grow');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
def row(node,index,**values):
    for key,value in values.items():node.parmTuple(f'proto_{key}{index}').set(value if isinstance(value,(tuple,list)) else (value,))
def keep(parm,value):                                    # type a number over an expression such as $FSTART
    parm.deleteAllKeyframes();parm.set(value)
plant=reference('reference_plant','/World/Props/Fir',ASSETS+'/fir.usda');crate=reference('reference_crate','/World/Props/Crate',ASSETS+'/crate.usda',plant)
terrain=reference('reference_terrain','/World/Terrain',ASSETS+'/terrain.usda',crate)
trees=stage.createNode(TYPE,'Arraytron_Firs');trees.setInput(0,terrain);trees.parm('outputpath').set('/World/Firs')
trees.parm('mode').set(5);trees.parm('surface_prim').set('/World/Terrain');trees.parm('surface_count').set(900);trees.parm('surface_seed').set(4);trees.parm('surface_normal').set(1);trees.parm('surface_slope_max').set(38);trees.parm('surface_align').set(0.4)
trees.parm('protos').set(1);row(trees,1,type=0,prim='/World/Props/Fir');trees.parm('base_scale').set(1.0);trees.parm('scale_random_mode').set(1);trees.parm('scale_min').set(0.6);trees.parm('scale_max').set(1.3)
trees.parm('rotation_random_mode').set(1);trees.parm('yaw_random').set(180)
trees.parm('overlap_mode').set(1);trees.parm('overlap_tolerance').set(0.55)
trees.parm('grow_on').set(1);trees.parm('grow_direction').set(0);keep(trees.parm('grow_start'),6);trees.parm('grow_sweep').set(60);trees.parm('grow_time').set(18);trees.parm('grow_delay').set(0.35);trees.parm('grow_style').set(1);trees.parm('grow_ease').set(2)
trees.setComment('GROW - the firs grow from the left edge (-X) to the right over 60 frames, Plant style (taller first, wider later), Overshoot easing, Random Delay 0.35 so the wave front is ragged. No Overlap keeps the trunks apart.')
trees.setGenericFlag(hou.nodeFlag.DisplayComment,True)
crates=stage.createNode(TYPE,'Arraytron_Crates');crates.setInput(0,trees);crates.parm('outputpath').set('/World/Crates')
crates.parm('mode').set(5);crates.parm('surface_prim').set('/World/Terrain');crates.parm('surface_count').set(40);crates.parm('surface_seed').set(11);crates.parm('surface_slope_max').set(25)
crates.parm('protos').set(1);row(crates,1,type=0,prim='/World/Props/Crate');crates.parm('base_scale').set(0.28);crates.parm('rotation_random_mode').set(1);crates.parm('yaw_random').set(180)
crates.parm('overlap_mode').set(1);crates.parm('overlap_tolerance').set(1.0)
crates.parm('grow_on').set(1);crates.parm('grow_direction').set(4);keep(crates.parm('grow_start'),30);crates.parm('grow_sweep').set(40);crates.parm('grow_time').set(14);crates.parm('grow_style').set(2);crates.parm('grow_rise').set(0.5);crates.parm('grow_ease').set(2)
crates.setComment('POP UP - the crates climb out of the ground from the middle outwards (Rise style, Outward From Centre, Overshoot easing).')
crates.setGenericFlag(hou.nodeFlag.DisplayComment,True)
camera=stage.createNode('camera','render_camera');camera.setInput(0,crates)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((-5.5,4.6,6.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.3,0.3,0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"grow")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
crates.setDisplayFlag(True)
errors={n.name():n.errors() for n in (plant,crate,terrain,trees,crates,camera,dome,sun,settings)}
from pxr import UsdGeom
counts={}
for frame in FRAMES:
    hou.setFrame(frame);rs=settings.stage();assert rs and not any(n.errors() for n in (trees,crates,settings)),errors
    pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/Firs'));counts[frame]=(len(pi.GetPositionsAttr().Get(frame) or []),len(pi.GetInvisibleIdsAttr().Get(frame) or []))
    rs.Export(str(versions.render_usd(VID,'grow')).replace('_render.usda','_render_f%04d.usda'%frame))
assert counts[FRAMES[0]][1]==counts[FRAMES[0]][0] and counts[FRAMES[-1]][1]==0,counts            # everything hidden at the start, everything there at the end
hou.setFrame(1)
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'frames':counts}))
