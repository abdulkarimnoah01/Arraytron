"""Build the Paint demo (v0.6.0): hython tools/build_demo_paint_v060.py
The terrain with two painted scatters, made by the SAME brush functions the viewport tool calls (strokes are scripted here, so the demo needs no mouse):
fir trees painted along an S-shaped path with a clearing erased in the middle (Ctrl-drag in the tool), and a few crates dabbed on the flat ground.
The stored strokes live in the nodes' hidden paint_data parameter, so you can open the node, press Start Painting and carry on with the real brush.
Writes dist/Arraytron_<version>_paint_demo.hip and Arraytron_<version>_paint_demo_render.usda."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'paint');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
def row(node,index,**values):
    for key,value in values.items():node.parmTuple(f'proto_{key}{index}').set(value if isinstance(value,(tuple,list)) else (value,))
plant=reference('reference_plant','/World/Props/Fir',ASSETS+'/fir.usda');crate=reference('reference_crate','/World/Props/Crate',ASSETS+'/crate.usda',plant)
terrain=reference('reference_terrain','/World/Terrain',ASSETS+'/terrain.usda',crate)
trees=stage.createNode(TYPE,'Arraytron_Firs_Painted');trees.setInput(0,terrain);trees.parm('outputpath').set('/World/Firs')
trees.parm('mode').set(6);trees.parm('paint_prim').set('/World/Terrain');trees.parm('paint_radius').set(0.5);trees.parm('paint_density').set(40);trees.parm('paint_spacing').set(0.12);trees.parm('paint_falloff').set(1);trees.parm('paint_align').set(0.4)
trees.parm('protos').set(1);row(trees,1,type=0,prim='/World/Props/Fir');trees.parm('scale_random_mode').set(1);trees.parm('scale_min').set(0.6);trees.parm('scale_max').set(1.3)
trees.parm('rotation_random_mode').set(1);trees.parm('yaw_random').set(180)
crates=stage.createNode(TYPE,'Arraytron_Crates_Painted');crates.setInput(0,trees);crates.parm('outputpath').set('/World/Crates')
crates.parm('mode').set(6);crates.parm('paint_prim').set('/World/Terrain');crates.parm('paint_radius').set(0.35);crates.parm('paint_density').set(6);crates.parm('paint_spacing').set(0.5);crates.parm('paint_align').set(0.0)
crates.parm('protos').set(1);row(crates,1,type=0,prim='/World/Props/Crate');crates.parm('base_scale').set(0.28);crates.parm('rotation_random_mode').set(1);crates.parm('yaw_random').set(180)
# ---- the strokes (the viewport tool calls exactly these functions)
m=trees.hdaModule();surface=m.paint_surface(trees);P,T=surface[0],surface[1]
def hit(x,z):
    t,j=m.ray_triangles(np.array([[x,50.0,z]]),np.array([0.0,-1.0,0.0]),P,T);assert j[0]>=0,(x,z);return np.array([x,50.0-t[0],z]),surface[3][j[0]]
def stroke(node,data,path,radius,kind='add',strength=1.0):
    seed=node.evalParm('paint_seed')
    for x,z in path:
        c,n=hit(x,z)
        if kind=='add':data,_=m.brush_add(data,c,n,radius,node.evalParm('paint_density'),node.evalParm('paint_spacing'),node.evalParm('paint_falloff'),strength,seed,m.make_projector(surface,c,radius,True))
        else:data,_=m.brush_remove(data,c,radius,node.evalParm('paint_falloff'),strength,seed)
    return data
bb=np.array([P.min(axis=0),P.max(axis=0)]);cx,cz=(bb[0][0]+bb[1][0])/2,(bb[0][2]+bb[1][2])/2;sx,sz=(bb[1][0]-bb[0][0])/2,(bb[1][2]-bb[0][2])/2
s=np.linspace(0,1,60);path=[(cx+sx*(-0.8+1.6*u),cz+sz*0.45*np.sin(u*2*np.pi)) for u in s]                       # an S across the terrain
data=stroke(trees,m.paint_empty(),path,0.5);data=stroke(trees,data,[(cx+sx*0.0,cz+sz*0.0)],0.9,'remove')          # a clearing in the middle
data=stroke(trees,data,[(cx+sx*(-0.5+0.25*k),cz-sz*0.7) for k in range(5)],0.5)                                   # a second small grove
m.paint_apply(trees,data)
mc=crates.hdaModule();dc=mc.paint_empty()
for x,z in ((cx,cz),(cx+0.4*sx,cz+0.15*sz),(cx-0.3*sx,cz-0.2*sz),(cx+0.1*sx,cz-0.45*sz)):
    c,n=hit(x,z);dc,_=mc.brush_add(dc,c,n,0.35,6.0,0.5,1,1.0,crates.evalParm('paint_seed'),mc.make_projector(surface,c,0.35,True))
mc.paint_apply(crates,dc)
trees.setComment('PAINT - %d firs painted with the brush functions along an S path, a clearing erased (Ctrl-drag), a small grove added. Press Start Painting on this node (or select it and press Enter in the viewport) to carry on with the real brush.'%len(data['pts']))
trees.setGenericFlag(hou.nodeFlag.DisplayComment,True)
crates.setComment('PAINT - %d crates dabbed on the ground; Paint Target /World/Terrain, Min Spacing 0.5.'%len(dc['pts']));crates.setGenericFlag(hou.nodeFlag.DisplayComment,True)
camera=stage.createNode('camera','render_camera');camera.setInput(0,crates)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((-5.5,4.6,6.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.3,0.3,0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"paint")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
crates.setDisplayFlag(True)
errors={n.name():n.errors() for n in (plant,crate,terrain,trees,crates,camera,dome,sun,settings)}
from pxr import UsdGeom
rs=settings.stage();assert rs and not any(n.errors() for n in (trees,crates,settings)),errors
counts={}
for path_,n in (('/World/Firs',len(data['pts'])),('/World/Crates',len(dc['pts']))):
    pi=UsdGeom.PointInstancer(rs.GetPrimAtPath(path_));counts[path_]=len(pi.GetPositionsAttr().Get(1) or []);assert counts[path_]==n>0,(path_,counts,n)
rs.Export(str(versions.render_usd(VID,'paint')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':counts}))
