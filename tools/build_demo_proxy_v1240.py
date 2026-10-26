"""Build the proxy display demo (v1.24.0): hython tools/build_demo_proxy_v1240.py
The same two-prototype scatter four times: Display Instances, Points Only, Boxes and Spheres (Debugging tab, section DISPLAY). Boxes and Spheres draw every instance as a guide shape from the bound of its
prototype, coloured by prototype. Writes dist/Arraytron_<version>_proxy_demo.hip (and the render USD) or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'proxy');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
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
fir=reference('reference_fir','/World/Props/Fir',ASSETS+'/fir.usda',ground)
previous=[fir]
def node(name,out,comment,**values):
    n=stage.createNode(TYPE,name);n.setInput(0,previous[0]);n.parm('outputpath').set(out);n.parm('protos').set(2);n.parm('proto_prim1').set('/World/Props/Rock');n.parm('proto_scale1').set(0.2);n.parm('proto_prim2').set('/World/Props/Fir');n.parm('proto_scale2').set(0.25)
    n.parm('scale_random_mode').set(1);n.parm('scale_min').set(0.7);n.parm('scale_max').set(1.2);n.parm('rotation_random_mode').set(1);n.parm('yaw_random').set(180)
    for k,v in values.items():
        if k=='rows_stagger' and n.parm(k).parmTemplate().type()==hou.parmTemplateType.Float:v=0.5*v      # v1.18.0: Stagger Rows is a slider (the fraction of the gap); the old tick meant 0.5
        pt=n.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:n.parm(k).set(v)
    n.setComment(comment);n.setGenericFlag(hou.nodeFlag.DisplayComment,True);previous[0]=n;return n
kw=dict(mode=1,area_sizex=4.0,area_sizez=4.0,area_count=30,area_seed=3)
plain=node('Arraytron_Proxy_Instances','/World/Instances','DISPLAY Instances - the normal result: rocks and firs.',bound_t=(-3.2,0.0,-3.2),**kw)
points=node('Arraytron_Proxy_Points','/World/Points','DISPLAY Points Only - the instances are hidden, the points are drawn.',bound_t=(3.2,0.0,-3.2),view_mode=1,**kw)
boxes=node('Arraytron_Proxy_Boxes','/World/Boxes','DISPLAY Boxes - a box of the size and place of each prototype bound, coloured by prototype (blue rock, orange fir).',bound_t=(-3.2,0.0,3.2),view_mode=2,**kw)
spheres=node('Arraytron_Proxy_Spheres','/World/Spheres','DISPLAY Spheres - a sphere around each prototype bound.',bound_t=(3.2,0.0,3.2),view_mode=3,**kw)
camera=stage.createNode('camera','render_camera');camera.setInput(0,spheres)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((0.0,13.0,9.0));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.0,0.0,0.0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"proxy")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
spheres.setDisplayFlag(True)
nodes=(plain,points,boxes,spheres)
errors={n.name():n.errors() for n in (rock,ground0,ground,fir,*nodes,camera,dome,sun,settings)}
rs=settings.stage();assert rs and not any(n.errors() for n in (*nodes,settings)),errors
counts={}
for name in ('Instances','Points','Boxes','Spheres'):
    pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/%s'%name));counts[name]=len(pi.GetPositionsAttr().Get(1) or [])
assert len(set(counts.values()))==1 and counts['Instances']>=20,counts
for name in ('Points','Boxes','Spheres'):assert len(UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/%s'%name)).GetInvisibleIdsAttr().Get() or [])==counts[name],name       # every instance hidden
assert rs.GetPrimAtPath('/World/Boxes_View/Proxy/P0').GetTypeName()=='Cube' and rs.GetPrimAtPath('/World/Spheres_View/Proxy/P1').GetTypeName()=='Sphere' and rs.GetPrimAtPath('/World/Points_View/Final')
print(counts)
rs.Export(str(versions.render_usd(VID,'proxy')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':counts}))
