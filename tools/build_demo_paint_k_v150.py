"""Build the Paint-only demo (v1.5.0): hython tools/build_demo_paint_k_v150.py
A flat ground and the letter K painted on it with stones and crates, made by the SAME brush functions the viewport tool calls (the strokes are scripted, so the demo needs no mouse). Select the node and press Start Painting to add or erase by hand. Writes dist/Arraytron_<version>_paint_k_demo.hip and the render USD."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'paint_k');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
def row(node,index,**values):
    for key,value in values.items():node.parmTuple(f'proto_{key}{index}').set(value if isinstance(value,(tuple,list)) else (value,))
# ---- a flat ground (written once next to the other test assets) and the stones to paint with
from pxr import Usd, UsdGeom
ground_file=ROOT/'dist/test_assets/paint_ground.usda'
if not ground_file.exists():
    gs=Usd.Stage.CreateNew(str(ground_file));gr=UsdGeom.Xform.Define(gs,'/Ground');gs.SetDefaultPrim(gr.GetPrim());UsdGeom.SetStageUpAxis(gs,UsdGeom.Tokens.y)
    gm=UsdGeom.Mesh.Define(gs,'/Ground/Plane');gm.CreatePointsAttr([(-8,0,5),(8,0,5),(8,0,-5),(-8,0,-5)]);gm.CreateFaceVertexCountsAttr([4]);gm.CreateFaceVertexIndicesAttr([0,1,2,3]);gm.CreateOrientationAttr('rightHanded')
    gm.CreateDisplayColorAttr([(0.32,0.27,0.22)]);gs.GetRootLayer().Save()
rock=reference('reference_rock','/World/Props/Rock',ASSETS+'/rock.usda');crate=reference('reference_crate','/World/Props/Crate',ASSETS+'/crate.usda',rock)
ground=reference('reference_ground','/World/Ground',ASSETS+'/paint_ground.usda',crate)
paint=stage.createNode(TYPE,'Arraytron_Paint_K');paint.setInput(0,ground);paint.parm('outputpath').set('/World/PaintedK')
paint.parm('mode').set(6);paint.parm('paint_prim').set('/World/Ground');paint.parm('paint_radius').set(0.42);paint.parm('paint_density').set(200);paint.parm('paint_spacing').set(0.1);paint.parm('paint_falloff').set(1);paint.parm('paint_align').set(0.0)
paint.parm('protos').set(2);paint.parm('proto_prim1').set('/World/Props/Rock');paint.parm('proto_weight1').set(2.0);paint.parm('proto_prim2').set('/World/Props/Crate');paint.parm('proto_weight2').set(1.0);paint.parm('proto_scale1').set(0.17);paint.parm('proto_scale2').set(0.14)
paint.parm('scale_random_mode').set(1);paint.parm('scale_min').set(0.75);paint.parm('scale_max').set(1.2);paint.parm('rotation_random_mode').set(1);paint.parm('yaw_random').set(180)
# ---- paint the letter K: three strokes, dabbed along each line exactly as the viewport tool does (x to the right, "up" is -Z as seen from the camera)
m=paint.hdaModule();surface=m.paint_surface(paint);data=m.paint_empty();seed=paint.evalParm('paint_seed')
def line(a,b,step=0.16):
    a=np.array(a,float);b=np.array(b,float);n=max(2,int(np.linalg.norm(b-a)/step)+1);return [a+(b-a)*t for t in np.linspace(0,1,n)]
def stroke(points,data):
    for x,up in points:
        c=np.array([x,0.0,-up]);data,_=m.brush_add(data,c,np.array([0.0,1.0,0.0]),paint.evalParm('paint_radius'),paint.evalParm('paint_density'),paint.evalParm('paint_spacing'),paint.evalParm('paint_falloff'),1.0,seed,m.make_projector(surface,c,paint.evalParm('paint_radius'),True))
    return data
data=stroke(line((-3.2,-3.4),(-3.2,3.4)),data)                       # the stem
data=stroke(line((3.0,3.4),(-3.0,0.15)),data)                        # the upper arm, from the top right into the stem
data=stroke(line((-1.6,0.95),(3.2,-3.4)),data)                        # the leg, from the arm down to the bottom right
m.paint_apply(paint,data)
paint.setComment('PAINT ONLY - the letter K, painted with the same brush functions as the viewport tool (%d points in 3 strokes). Select this node and press Start Painting. Shortcuts: LMB paint, Ctrl+LMB erase, Shift+LMB relax, Ctrl+Shift+LMB drag sideways = radius, wheel with Shift = radius / Ctrl = strength / Ctrl+Shift = density, [ ] radius, - = strength, , . density, 1-4 operation (Add Remove Replace Relax), F falloff, H hides the help line.'%len(data['pts']))
paint.setGenericFlag(hou.nodeFlag.DisplayComment,True)
crates=paint
camera=stage.createNode('camera','render_camera');camera.setInput(0,crates)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((0.0,11.5,8.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.0,0.0,0.0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"paint_k")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
crates.setDisplayFlag(True)
errors={n.name():n.errors() for n in (rock,crate,ground,paint,camera,dome,sun,settings)}
from pxr import UsdGeom as _G
rs=settings.stage();assert rs and not any(n.errors() for n in (paint,settings)),errors
pi=_G.PointInstancer(rs.GetPrimAtPath('/World/PaintedK'));kept=len(pi.GetPositionsAttr().Get(1) or []);assert kept>300,kept
rs.Export(str(versions.render_usd(VID,'paint_k')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'painted points':kept}))
