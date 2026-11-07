"""Build the Mirror demo (v1.34.0): hython tools/build_demo_mirror_v1340.py
Six small Area scatters, each with a different mirror setup (Mirror tab): one plane, two planes (4 copies), a flip (Keep Original off), a radial ring of 6, a kaleidoscope (Mirror Each Slice) and a custom
diagonal plane. The source scatter is the small patch near the origin of every cell; everything else is its mirror image. Writes dist/Arraytron_<version>_mirror_demo.hip (and the render USD) or the
Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'mirror');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
from pxr import UsdGeom
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
rock=reference('reference_rock','/World/Props/Rock',ASSETS+'/rock.usda');ground=reference('reference_ground','/World/Ground',ASSETS+'/paint_ground.usda',rock);fir=reference('reference_fir','/World/Props/Fir',ASSETS+'/fir.usda',ground)
def node(name,out,comment,cell,rows,**values):
    n=stage.createNode(TYPE,name);n.setInput(0,fir);n.parm('outputpath').set(out);n.parm('protos').set(2);n.parm('proto_prim1').set('/World/Props/Rock');n.parm('proto_scale1').set(0.2);n.parm('proto_prim2').set('/World/Props/Fir');n.parm('proto_scale2').set(0.25)
    n.parm('scale_random_mode').set(1);n.parm('scale_min').set(0.7);n.parm('scale_max').set(1.2);n.parm('rotation_random_mode').set(1);n.parm('yaw_random').set(180)
    n.parm('mode').set(1);n.parm('area_sizex').set(2.4);n.parm('area_sizez').set(2.4);n.parm('area_count').set(14);n.parm('area_seed').set(3);n.parmTuple('bound_t').set((cell[0],0.0,cell[1]))
    n.parm('mirror_on').set(1);n.parm('mirror_ops').set(len(rows))
    for i,row in enumerate(rows,1):
        for k,v in row.items():
            pt=n.parmTuple('%s%d'%(k,i));pt.set(v if isinstance(v,(tuple,list)) else (v,))
    n.setComment(comment);n.setGenericFlag(hou.nodeFlag.DisplayComment,True);return n
nodes=[
 node('Arraytron_Mirror_Plane','/World/Plane','MIRROR one Plane X at x = 2 (Mirror tab): the patch and its mirror image.',(-12.0,-6.0),[dict(mirror_type=0,mirror_center=(2.0,0.0,0.0))]),
 node('Arraytron_Mirror_FourWay','/World/FourWay','MIRROR two operations, Plane X then Plane Z: 4 copies.',(0.0,-6.0),[dict(mirror_type=0,mirror_center=(2.0,0.0,0.0)),dict(mirror_type=2,mirror_center=(0.0,0.0,2.0))]),
 node('Arraytron_Mirror_Flip','/World/Flip','MIRROR Plane X with Keep Original off: the patch is replaced by its mirror image (a flip).',(12.0,-6.0),[dict(mirror_type=0,mirror_center=(2.0,0.0,0.0),mirror_keep=0)]),
 node('Arraytron_Mirror_Radial','/World/Radial','MIRROR Radial, Count 6 about Y, Center x = 3: a ring of six patches.',(-12.0,6.0),[dict(mirror_type=4,mirror_axis=1,mirror_count=6,mirror_center=(3.0,0.0,0.0))]),
 node('Arraytron_Mirror_Kaleidoscope','/World/Kaleidoscope','MIRROR Radial, Count 3, Mirror Each Slice: a kaleidoscope (6 patches, every slice the mirror image of its neighbour).',(0.0,6.0),[dict(mirror_type=4,mirror_axis=1,mirror_count=3,mirror_slice=1,mirror_center=(3.0,0.0,0.0))]),
 node('Arraytron_Mirror_Diagonal','/World/Diagonal','MIRROR Custom Plane, normal (1, 0, 1) through (2, 0, 2), then Plane X: the diagonal mirror and then a second mirror.',(12.0,6.0),[dict(mirror_type=3,mirror_normal=(1.0,0.0,1.0),mirror_center=(2.0,0.0,2.0)),dict(mirror_type=0,mirror_center=(-1.0,0.0,0.0))]),
]
camera=stage.createNode('camera','render_camera');merge=stage.createNode('merge','merge_all')
for k_,n_ in enumerate(nodes):merge.setInput(k_,n_)
camera.setInput(0,merge)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(300);camera.parmTuple('t').set((0.0,34.0,19.0));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.0,0.0,0.0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"mirror")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
merge.setDisplayFlag(True)
errors={n.name():n.errors() for n in (rock,ground,fir,*nodes,camera,dome,sun,settings)}
rs=settings.stage();assert rs and not any(n.errors() for n in (*nodes,settings)),errors
counts={}
for n_ in nodes:
    nm=n_.name().split('_',2)[2];pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/%s'%nm));counts[nm]=len(pi.GetPositionsAttr().Get(1) or [])
assert counts=={'Plane':28,'FourWay':56,'Flip':14,'Radial':84,'Kaleidoscope':84,'Diagonal':56},counts
rs.Export(str(versions.render_usd(VID,'mirror')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':counts}))
