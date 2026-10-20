"""Build the Rows demo (v1.14.0): hython tools/build_demo_rows_v1140.py
The linear Distribution Modes scatter in several rows (Layout tab, section ROWS): a Line in 4 straight rows, a Line in 4 rows randomised across and along, a Circle as 3 concentric rings, and a Curve (a wavy
path) in 3 rows. Writes dist/Arraytron_<version>_rows_demo.hip (and the render USD) or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'rows');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
from pxr import Usd, UsdGeom
for folder in (ROOT/'dist/test_assets',ROOT/'otls_h205/test_assets'):                       # the wavy path (an invisible BasisCurves prim), shared with the Place demo
    if folder.exists() and not (folder/'path_curve.usda').exists():
        cs=Usd.Stage.CreateNew(str(folder/'path_curve.usda'));root=UsdGeom.Xform.Define(cs,'/PathCurve');cs.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(cs,UsdGeom.Tokens.y)
        xs=np.linspace(-6.5,6.5,14);curve=UsdGeom.BasisCurves.Define(cs,'/PathCurve/Curve');curve.CreateTypeAttr('linear');curve.CreateWrapAttr('nonperiodic');curve.CreatePointsAttr([(float(x),0.0,float(-3.6+0.7*np.sin(x*0.9))) for x in xs]);curve.CreateCurveVertexCountsAttr([len(xs)]);curve.CreateWidthsAttr([0.02]);UsdGeom.Imageable(curve).CreateVisibilityAttr('invisible');cs.GetRootLayer().Save()
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
rock=reference('reference_rock','/World/Props/Rock',ASSETS+'/rock.usda');ground0=reference('reference_ground','/World/Ground',ASSETS+'/paint_ground.usda',rock);ground=reference('reference_path','/World/PathCurve',ASSETS+'/path_curve.usda',ground0)
previous=[ground]
def node(name,out,comment,**values):
    n=stage.createNode(TYPE,name);n.setInput(0,previous[0]);n.parm('outputpath').set(out);n.parm('protos').set(1);n.parm('proto_prim1').set('/World/Props/Rock');n.parm('proto_scale1').set(0.2)
    n.parm('scale_random_mode').set(1);n.parm('scale_min').set(0.7);n.parm('scale_max').set(1.2);n.parm('rotation_random_mode').set(1);n.parm('yaw_random').set(180)
    for k,v in values.items():
        pt=n.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:n.parm(k).set(v)
    n.setComment(comment);n.setGenericFlag(hou.nodeFlag.DisplayComment,True);previous[0]=n;return n
straight=node('Arraytron_Rows_Straight','/World/Straight','ROWS - a Line of 14 points laid out in 4 straight rows (Layout tab, section ROWS: Rows 4, Row Spacing 0.5, centred).',mode=0,line_count=14,line_length=6.0,line_center=1,rows_count=4,rows_spacing=0.5,bound_tx=-4.0,bound_tz=3.4)
loose=node('Arraytron_Rows_Random','/World/Random','ROWS - the same 4 rows with Random Offset 0.9 and Random Shift Along 0.8: a loose band instead of straight lines (each point keeps its offset when rows are added).',mode=0,line_count=14,line_length=6.0,line_center=1,rows_count=4,rows_spacing=0.6,rows_random=0.9,rows_shift=0.8,rows_seed=3,bound_tx=-4.0,bound_tz=1.0)
stagger=node('Arraytron_Rows_Stagger','/World/Stagger','ROWS - Stagger Rows: every second row is shifted by half the gap along the path (a brick pattern).',mode=0,line_count=14,line_length=6.0,line_center=1,rows_count=4,rows_spacing=0.45,rows_stagger=1,bound_tx=-4.0,bound_tz=-1.4)
rings=node('Arraytron_Rows_Rings','/World/Rings','ROWS - a Circle as 3 concentric rings (Rows 3, Row Spacing 0.5, centred on the circle), facing outward.',mode=3,circle_count=26,circle_radius=1.7,circle_facing=1,rows_count=3,rows_spacing=0.5,bound_tx=4.2,bound_tz=1.8)
curve=node('Arraytron_Rows_Curve','/World/Curve','ROWS - a Curve (the wavy path at the back) in 3 rows pushed to the side of it, a little random.',mode=4,curve_prim='/World/PathCurve',curve_count=40,rows_count=3,rows_spacing=0.55,rows_random=0.3,rows_seed=5)
camera=stage.createNode('camera','render_camera');camera.setInput(0,curve)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((0.0,13.5,9.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.0,0.0,0.4))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"rows")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
curve.setDisplayFlag(True)
nodes=(straight,loose,stagger,rings,curve)
errors={n.name():n.errors() for n in (rock,ground0,ground,*nodes,camera,dome,sun,settings)}
rs=settings.stage();assert rs and not any(n.errors() for n in (*nodes,settings)),errors
counts={}
for name in ('Straight','Random','Stagger','Rings','Curve'):
    pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/%s'%name));counts[name]=len(pi.GetPositionsAttr().Get(1) or [])
assert counts['Straight']==56 and counts['Random']==56 and counts['Stagger']==56 and counts['Rings']==78 and counts['Curve']>100,counts
print(straight.parm('rows_info').eval());print(rings.parm('rows_info').eval());print(curve.parm('rows_info').eval());print(counts)
rs.Export(str(versions.render_usd(VID,'rows')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':counts}))
