"""Build the Noise demo (v1.22.0): hython tools/build_demo_noise_v1220.py
Position noise on a Grid (Layout tab, section NOISE): none, smooth Perlin on the ground axes, Random per point, Perlin on the height only; a Circle in 3 rings with Stagger Rows 1.5 (the odd rings are turned and stay
on their orbit) and the same rings in the Points Only display. Writes dist/Arraytron_<version>_noise_demo.hip (and the render USD) or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'noise');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
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
        if k=='rows_stagger' and n.parm(k).parmTemplate().type()==hou.parmTemplateType.Float:v=0.5*v      # v1.18.0: Stagger Rows is a slider (the fraction of the gap); the old tick meant 0.5
        pt=n.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:n.parm(k).set(v)
    n.setComment(comment);n.setGenericFlag(hou.nodeFlag.DisplayComment,True);previous[0]=n;return n
grid=dict(mode=2,grid_countx=14,grid_county=1,grid_countz=3,grid_sizex=10.0,grid_sizez=1.6)
plain=node('Arraytron_Noise_Plain','/World/Plain','NOISE off - a Grid of 14 x 3 points as the distribution makes it.',bound_t=(0.0,0.0,-4.5),**grid)
smooth=node('Arraytron_Noise_Perlin','/World/Perlin','NOISE - Perlin noise on the ground axes (Layout tab, section NOISE: Position Noise on, Amount 0.25 0 0.25, Frequency 0.6): neighbours move alike.',bound_t=(0.0,0.0,-2.2),noise_on=1,noise_type=0,noise_amp=(0.25,0.0,0.25),noise_freq=0.6,**grid)
rand=node('Arraytron_Noise_Random','/World/Random','NOISE - Random: every point moves on its own (Amount 0.2 0 0.2).',bound_t=(0.0,0.0,0.0),noise_on=1,noise_type=2,noise_amp=(0.2,0.0,0.2),**grid)
height=node('Arraytron_Noise_Height','/World/Height','NOISE - Amount 0 0.5 0: only the height moves (Simplex, 2 octaves).',bound_t=(0.0,0.0,2.2),noise_on=1,noise_type=1,noise_amp=(0.0,0.5,0.0),noise_freq=0.5,noise_octaves=2,**grid)
rings=node('Arraytron_Noise_Rings','/World/Rings','STAGGER - 3 rings with Stagger Rows 1.5 (it cycles: 1.5 is 0.5): the odd ring is turned half a step and stays on its orbit.',bound_t=(-3.0,0.0,4.3),mode=3,circle_count=20,circle_radius=1.0,circle_facing=1,rows_count=3,rows_spacing=0.4,rows_stagger=1.5)
points=node('Arraytron_Noise_Points','/World/Points','DISPLAY - the same rings in Points Only (Debugging tab, Display): the instances are hidden and the points are drawn as guide points (never rendered).',bound_t=(3.0,0.0,4.3),mode=3,circle_count=20,circle_radius=1.0,circle_facing=1,rows_count=3,rows_spacing=0.4,rows_stagger=1.5,view_mode=1)
camera=stage.createNode('camera','render_camera');camera.setInput(0,points)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((0.0,15.5,11.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.0,0.0,0.8))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"noise")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
points.setDisplayFlag(True)
nodes=(plain,smooth,rand,height,rings,points)
errors={n.name():n.errors() for n in (rock,ground0,ground,*nodes,camera,dome,sun,settings)}
rs=settings.stage();assert rs and not any(n.errors() for n in (*nodes,settings)),errors
counts={}
for name in ('Plain','Perlin','Random','Height','Rings','Points'):
    pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/%s'%name));counts[name]=len(pi.GetPositionsAttr().Get(1) or [])
assert counts['Plain']==42 and counts['Perlin']==42 and counts['Random']==42 and counts['Height']==42 and counts['Rings']==60 and counts['Points']==60,counts
hidden=len(UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/Points')).GetInvisibleIdsAttr().Get() or []);assert hidden==60,hidden
print(counts)
rs.Export(str(versions.render_usd(VID,'noise')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':counts}))
