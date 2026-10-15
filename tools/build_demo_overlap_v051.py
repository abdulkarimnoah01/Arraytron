"""Build the No Overlap demo (v0.5.1): hython tools/build_demo_overlap_v051.py
Three identical Area layouts of rocks (same seed, same count) side by side on a floor: left as generated (plenty of rocks sitting inside each other),
middle with Remove Overlapping (the later rock of every overlapping pair is deleted), right with Push Apart (every rock stays, they slide apart).
Writes dist/Arraytron_<current>_overlap_demo.hip and the exported render USD."""
from pathlib import Path
import sys, hou, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'overlap');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
rock=reference('reference_rock','/World/Props/Rock',ASSETS+'/rock.usda')
last=rock;nodes=[]
for k,(label,mode,note) in enumerate((('Plain',0,'AS GENERATED - rocks sit inside each other.'),('Remove',1,'REMOVE OVERLAPPING - the later rock of every overlapping pair is deleted; the survivors keep their ids and positions.'),('Push',2,'PUSH APART - every rock stays and slides away from its neighbours until they no longer overlap (Strength 0.5, 80 iterations).'))):
    a=stage.createNode(TYPE,'Arraytron_'+label);a.setInput(0,last);a.parm('outputpath').set('/World/'+label)
    a.parm('mode').set(1);a.parm('area_sizex').set(4.2);a.parm('area_sizez').set(7.0);a.parm('area_count').set(110);a.parm('area_seed').set(4)
    a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Rock');a.parm('base_scale').set(0.55);a.parm('scale_random').set(0.35)
    a.parm('rotation_random_mode').set(1);a.parm('yaw_random').set(180)
    a.parmTuple('bound_t').set(((k-1)*4.8,0,0))
    a.parm('overlap_mode').set(mode);a.parm('overlap_axes').set(0);a.parm('overlap_tolerance').set(1.0);a.parm('overlap_iterations').set(80)
    a.setComment(note);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);nodes.append(a);last=a
floor=reference('reference_floor','/World/Floor',ASSETS+'/floor.usda',last)
camera=stage.createNode('camera','render_camera');camera.setInput(0,floor)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(40);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((0,13,11));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0,0,0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.8)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-50,25,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(192)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"overlap")}.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(1600,900))
floor.setDisplayFlag(True)
renderstage=settings.stage();errors={n.name():n.errors() for n in [rock,floor,camera,dome,sun,settings]+nodes};assert renderstage and not any(errors.values()),errors
from pxr import UsdGeom
counts={p:len(UsdGeom.PointInstancer(renderstage.GetPrimAtPath(p)).GetPositionsAttr().Get() or []) for p in ('/World/Plain','/World/Remove','/World/Push')}
assert counts['/World/Plain']==110==counts['/World/Push'] and 0<counts['/World/Remove']<110,counts
renderstage.Export(str(versions.render_usd(VID,'overlap')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':counts}))
