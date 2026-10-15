"""Build the Finish demo (v1.0.0): hython tools/build_demo_finish_v100.py
The cluster forest with manual instance overrides (delete, scale, move + rotate, prototype switch, keyed on stable ids) and the debug views on. Writes dist/Arraytron_<version>_finish_demo.hip and the render USD."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'finish');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
def row(node,index,**values):
    for key,value in values.items():node.parmTuple(f'proto_{key}{index}').set(value if isinstance(value,(tuple,list)) else (value,))
from make_test_assets_v045 import height
from pxr import Usd, UsdGeom, Gf
POND_AT=(-1.3,1.6)                                          # a pond: a sphere sunk into the terrain at this x, z
pond_file=ROOT/'dist/test_assets/pond.usda';ps=Usd.Stage.CreateNew(str(pond_file));pr=UsdGeom.Xform.Define(ps,'/Pond');ps.SetDefaultPrim(pr.GetPrim());UsdGeom.SetStageUpAxis(ps,UsdGeom.Tokens.y)
sp=UsdGeom.Sphere.Define(ps,'/Pond/Water');sp.CreateRadiusAttr(0.55);UsdGeom.Xformable(sp).AddTranslateOp().Set(Gf.Vec3d(POND_AT[0],height(*POND_AT)+0.05,POND_AT[1]));ps.GetRootLayer().Save()
plant=reference('reference_plant','/World/Props/Fir',ASSETS+'/fir.usda');road=reference('reference_road','/World/Road',ASSETS+'/curve_s.usda',plant)
pondref=reference('reference_pond','/World/Pond',ASSETS+'/pond.usda',road);terrain=reference('reference_terrain','/World/Terrain',ASSETS+'/terrain.usda',pondref)
trees=stage.createNode(TYPE,'Arraytron_Clusters');trees.setInput(0,terrain);trees.parm('outputpath').set('/World/Firs')
trees.parm('mode').set(7);trees.parm('cluster_prim').set('/World/Terrain');trees.parm('cluster_count').set(16);trees.parm('cluster_per').set(40);trees.parm('cluster_radius').set(0.8);trees.parm('cluster_falloff').set(0.6);trees.parm('cluster_jitter').set(0.35);trees.parm('cluster_seed').set(5);trees.parm('cluster_align').set(0.4)
trees.parm('protos').set(1);trees.parm('proto_prim1').set('/World/Props/Fir');trees.parm('scale_random_mode').set(1);trees.parm('scale_min').set(0.6);trees.parm('scale_max').set(1.3)
trees.parm('rotation_random_mode').set(1);trees.parm('yaw_random').set(180)
trees.parm('fields').set(1);trees.parm('field_type1').set(1);trees.parm('field_prim1').set('/World/Terrain');trees.parm('field_smin1').set(0);trees.parm('field_smax1').set(24);trees.parm('field_sfall1').set(8)       # nothing on the steep bank
trees.parm('overlap_mode').set(1);trees.parm('overlap_priority').set(1);trees.parm('overlap_size').set(1);trees.parm('overlap_radius').set(0.11);trees.parm('overlap_tolerance').set(1.0)                                                                                               # trunks may not overlap; the bigger trees win
trees.parm('avoid_mode').set(2);trees.parm('avoid_prim').set('/World/Pond');trees.parm('avoid_margin').set(0.08);trees.parm('avoid_axes').set(1)                                                              # nothing in or touching the pond
# ---- v1.0.0: hand edits by stable id, and the debug views
from pxr import UsdGeom as _UG
probe=trees.stage();pi0=_UG.PointInstancer(probe.GetPrimAtPath('/World/Firs'));ids0=[int(i) for i in pi0.GetIdsAttr().Get(1)];pos0=pi0.GetPositionsAttr().Get(1)
order=sorted(range(len(ids0)),key=lambda k:(pos0[k][0],pos0[k][2]))                      # pick instances by position so the demo does not depend on id values
trees.parm('overrides').set(4)
trees.parm('ovr_id1').set(ids0[order[3]]);trees.parm('ovr_delete1').set(1)                          # a tree removed by hand
trees.parm('ovr_id2').set(ids0[order[len(order)//2]]);trees.parm('ovr_scale2').set(2.6)               # a hero tree, 2.6 x bigger
trees.parm('ovr_id3').set(ids0[order[len(order)//3]]);trees.parmTuple('ovr_move3').set((0.0,0.0,0.25));trees.parmTuple('ovr_rot3').set((0.0,0.0,18.0))   # one nudged and tilted
trees.parm('ovr_id4').set(ids0[order[2*len(order)//3]]);trees.parm('ovr_proto4').set(1)             # (row 1 = the same fir: a re-assignment that keeps the look)
trees.parm('dbg_on').set(1);trees.parm('dbg_generated').set(1);trees.parm('dbg_rejected').set(1);trees.parm('dbg_color').set(3);trees.parm('dbg_size').set(0.04);trees.parm('dbg_centres').set(1)
trees.parm('export_path').set('$HIP/arraytron_export/$OS.usd')
trees.setComment('FINISH - the Cluster demo with hand edits keyed on stable ids (one tree deleted, one hero tree 2.6 x bigger, one nudged and tilted) and the DEBUG views switched on: the viewport shows the generated points (white), the rejected ones (red) and the weight (green to red); none of it renders. Export USD writes this result to a file.')
trees.setGenericFlag(hou.nodeFlag.DisplayComment,True)
crates=trees
camera=stage.createNode('camera','render_camera');camera.setInput(0,trees)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((-5.5,4.6,6.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.3,0.3,0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"finish")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
crates.setDisplayFlag(True)
errors={n.name():n.errors() for n in (plant,road,pondref,terrain,trees,camera,dome,sun,settings)}
from pxr import UsdGeom
rs=settings.stage();assert rs and not any(n.errors() for n in (trees,settings)),errors
pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/Firs'));kept=len(pi.GetPositionsAttr().Get(1) or []);assert 60<kept<2000,kept
rs.Export(str(versions.render_usd(VID,'finish')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':kept}))
