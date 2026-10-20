"""Build the Falloff demo (v1.12.0, extended in v1.13.0): hython tools/build_demo_falloff_v1120.py
Front row, three patches of rocks scattered with the Area mode on the same ground: no falloff, a radial falloff (full size and densest in the centre, a flat centre, smaller and thinner towards the rim)
and a box falloff (every edge of the rectangle fades). Back row (v1.13.0, Region: Automatic): two crossing paint strokes fading across their width, five clusters each fading to its own boundary, and a
3D grid (a matrix with layers in Y) fading to all its faces. The Layout tab section FALLOFF holds the controls. Writes dist/Arraytron_<version>_falloff_demo.hip (and the render USD) or the Houdini 20.5 / 21
equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'falloff');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
# ---- a small patch of ground for the Cluster mode (written once next to the other test assets)
from pxr import Usd, UsdGeom
for folder in (ROOT/'dist/test_assets',ROOT/'otls_h205/test_assets'):
    if folder.exists() and not (folder/'falloff_patch.usda').exists():
        ps=Usd.Stage.CreateNew(str(folder/'falloff_patch.usda'));pr=UsdGeom.Xform.Define(ps,'/FalloffPatch');ps.SetDefaultPrim(pr.GetPrim());UsdGeom.SetStageUpAxis(ps,UsdGeom.Tokens.y)
        pm=UsdGeom.Mesh.Define(ps,'/FalloffPatch/Plane');pm.CreatePointsAttr([(-2.2,0.003,-0.6),(2.2,0.003,-0.6),(2.2,0.003,-5.0),(-2.2,0.003,-5.0)]);pm.CreateFaceVertexCountsAttr([4]);pm.CreateFaceVertexIndicesAttr([0,1,2,3]);pm.CreateOrientationAttr('rightHanded')
        pm.CreateDisplayColorAttr([(0.30,0.26,0.22)]);ps.GetRootLayer().Save()
rock=reference('reference_rock','/World/Props/Rock',ASSETS+'/rock.usda');ground0=reference('reference_ground','/World/Ground',ASSETS+'/paint_ground.usda',rock);ground=reference('reference_patch','/World/Patch',ASSETS+'/falloff_patch.usda',ground0)
def patch(name,out,x,sizex,sizez,**fall):
    n=stage.createNode(TYPE,name);n.setInput(0,previous[0]);n.parm('outputpath').set(out);n.parm('mode').set(1);n.parm('area_count').set(700);n.parm('area_sizex').set(sizex);n.parm('area_sizez').set(sizez);n.parm('area_seed').set(4)
    n.parm('protos').set(1);n.parm('proto_prim1').set('/World/Props/Rock');n.parm('proto_scale1').set(0.17);n.parm('bound_tx').set(x);n.parm('bound_tz').set(2.6)
    n.parm('scale_random_mode').set(1);n.parm('scale_min').set(0.7);n.parm('scale_max').set(1.2);n.parm('rotation_random_mode').set(1);n.parm('yaw_random').set(180)
    for k,v in fall.items():n.parm(k).set(v)
    previous[0]=n;return n
previous=[ground]
plain=patch('Arraytron_Plain','/World/Plain',-5.0,4.4,4.4)
radial=patch('Arraytron_Radial','/World/Radial',0.0,4.4,4.4,fall_on=1,fall_shape=0,fall_curve=1,fall_inner=15.0,fall_density=5.0,fall_scale=0.15)
box=patch('Arraytron_Box','/World/Box',5.0,4.4,4.4,fall_on=1,fall_shape=1,fall_curve=0,fall_inner=0.0,fall_density=0.0,fall_scale=0.2)
# ---- back row: the new regions (Region: Automatic)
def world_node(name,out,**values):
    n=stage.createNode(TYPE,name);n.setInput(0,previous[0]);n.parm('outputpath').set(out);n.parm('protos').set(1);n.parm('proto_prim1').set('/World/Props/Rock');n.parm('proto_scale1').set(0.17)
    n.parm('scale_random_mode').set(1);n.parm('scale_min').set(0.7);n.parm('scale_max').set(1.2);n.parm('rotation_random_mode').set(1);n.parm('yaw_random').set(180)
    for k,v in values.items():n.parm(k).set(v)
    previous[0]=n;return n
fall=dict(fall_on=1,fall_shape=0,fall_curve=1,fall_inner=10.0,fall_density=10.0,fall_scale=0.15)
paint=world_node('Arraytron_Paint_Strokes','/World/Strokes',mode=6,paint_prim='/World/Ground',paint_radius=0.62,paint_density=18.0,paint_spacing=0.1,paint_falloff=3,**fall)
m=paint.hdaModule();surface=m.paint_surface(paint);data=m.paint_empty()
for path in (((-7.2,0.0,-2.8),(-3.2,0.0,-2.8)),((-5.2,0.0,-4.7),(-5.2,0.0,-0.9))):
    a,b=np.array(path[0]),np.array(path[1]);steps=[a+(b-a)*t for t in np.linspace(0,1,int(np.linalg.norm(b-a)/0.2)+1)]
    for c in steps:data,_=m.brush_add(data,c,np.array([0.0,1.0,0.0]),0.62,18.0,0.1,3,1.0,1,m.make_projector(surface,c,0.62,True))
    data=m.paint_stroke_add(data,steps,0.62)
m.paint_apply(paint,data)
clusters=world_node('Arraytron_Clusters','/World/Clusters',mode=7,cluster_prim='/World/Patch',cluster_count=5,cluster_per=110,cluster_radius=0.85,cluster_falloff=0.2,cluster_jitter=0.3,cluster_seed=6,**fall)
grid=world_node('Arraytron_Grid3D','/World/Grid3D',mode=2,grid_countx=7,grid_county=5,grid_countz=7,bound_tx=5.2,bound_ty=0.8,bound_tz=-2.8,fall_on=1,fall_shape=1,fall_curve=0,fall_inner=0.0,fall_density=100.0,fall_scale=0.2)
for k,v in (('grid_sizex',3.3),('grid_sizey',2.2),('grid_sizez',3.3)):
    if grid.parm(k) is not None:grid.parm(k).set(v)
paint.setComment('FALLOFF, Region Automatic - Paint: two crossing strokes; the brush records the stroke paths, so the instances are full size on the path and fade across its width.');paint.setGenericFlag(hou.nodeFlag.DisplayComment,True)
clusters.setComment('FALLOFF, Region Automatic - Cluster: every cluster fades to its own boundary (centre and radius of each cluster), not to the box around all of them.');clusters.setGenericFlag(hou.nodeFlag.DisplayComment,True)
grid.setComment('FALLOFF, Region Automatic - Grid: a 3D matrix (5 layers in Y) fades towards all its faces (Box shape, Edge Scale 0.2, density kept).');grid.setGenericFlag(hou.nodeFlag.DisplayComment,True)
plain.setComment('FALLOFF - left: no falloff (one density, one scale). Layout tab, section FALLOFF: Falloff on, Shape, Curve, Flat Centre, Edge Density and Edge Scale.');plain.setGenericFlag(hou.nodeFlag.DisplayComment,True)
radial.setComment('FALLOFF - Radial, Smooth, Flat Centre 15%, Edge Density 5%, Edge Scale 0.15: full size and densest in the centre, smaller and thinner towards the rim.');radial.setGenericFlag(hou.nodeFlag.DisplayComment,True)
box.setComment('FALLOFF - Box, Linear, Edge Density 0, Edge Scale 0.2: every edge of the rectangle fades, not only the corners. Works with every Distribution Mode, after the Mask and the Field Stack.');box.setGenericFlag(hou.nodeFlag.DisplayComment,True)
camera=stage.createNode('camera','render_camera');camera.setInput(0,previous[0])
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((0.0,15.0,13.0));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.0,0.0,0.0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"falloff")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
grid.setDisplayFlag(True)
errors={n.name():n.errors() for n in (rock,ground0,ground,plain,radial,box,paint,clusters,grid,camera,dome,sun,settings)}
rs=settings.stage();assert rs and not any(n.errors() for n in (plain,radial,box,paint,clusters,grid,settings)),errors
from pxr import UsdGeom
counts={}
for name in ('Plain','Radial','Box','Strokes','Clusters','Grid3D'):
    pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/%s'%name));counts[name]=len(pi.GetPositionsAttr().Get(1) or [])
assert counts['Plain']==700 and 100<counts['Radial']<500 and 100<counts['Box']<500 and counts['Strokes']>60 and counts['Clusters']>100 and counts['Grid3D']==245,counts
print(radial.parm('fall_info').eval());print(paint.parm('fall_info').eval());print(clusters.parm('fall_info').eval());print(grid.parm('fall_info').eval());print(counts)
rs.Export(str(versions.render_usd(VID,'falloff')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':counts}))
