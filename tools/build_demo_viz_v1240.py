"""Build the Visualize demo (v1.24.0): hython tools/build_demo_viz_v1240.py
The same two-prototype scatter four times: Display Instances, Points Only, Boxes and Spheres (Debugging tab, section DISPLAY). Boxes and Spheres draw every instance as a guide shape from the bound of its
prototype, coloured by prototype. Writes dist/Arraytron_<version>_proxy_demo.hip (and the render USD) or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'viz');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
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
    n.setComment(comment);n.setGenericFlag(hou.nodeFlag.DisplayComment,True);return n
kw=dict(mode=5,surface_prim='/World/Ground',surface_count=60,surface_seed=4,mask_source=1,mask_noise_freq=0.35,mask_noise_contrast=2.5,mask_effect=1,mask_minscale=0.25,dbg_size=0.07)
surface=node('Arraytron_Viz_Surface','/World/Surface','VISUALIZE Scattering Surface - the Mask (noise) as colour on dots over the ground: blue 0, yellow 1 (Debugging tab, VISUALIZE).',viz_target=1,viz_what=0,viz_count=6000,**kw)
inst=node('Arraytron_Viz_Instances','/World/Instances','VISUALIZE Instances - a coloured dot at every instance, the Mask weight of that spot; the instances shrink where it is blue (Mask effect Scale).',viz_target=2,viz_what=0,**kw)
both=node('Arraytron_Viz_Both','/World/Both','VISUALIZE Both + Boxes - the ground colours and the boxes take the instance colour (Display Boxes).',viz_target=3,viz_what=0,viz_count=6000,view_mode=2,**kw)
fields=node('Arraytron_Viz_Field','/World/Field','VISUALIZE Field Stack - a noise row of the Field Stack on the ground and the points (Mask off).',mode=5,surface_prim='/World/Ground',surface_count=60,surface_seed=4,viz_target=3,viz_what=1,viz_count=6000,mask_source=0,fields=1,field_type1=2,field_nfreq1=0.45,field_nseed1=5,field_ncontrast1=3.0,field_effect=1,field_minscale=0.25)
noise=node('Arraytron_Viz_Noise','/World/Noise','VISUALIZE Position Noise - how far the Noise stage moved each point (Layout tab NOISE, Amount 0.5 0 0.5), colour 0 to 1 of the Amount.',mode=0,line_count=40,line_length=10.0,line_center=1,noise_on=1,noise_amp=(0.0,0.0,1.2),noise_freq=0.6,viz_target=2,viz_what=3,dbg_size=0.07)
camera=stage.createNode('camera','render_camera');merge=stage.createNode('merge','merge_all')
for k_,n_ in enumerate((surface,inst,both,fields,noise)):merge.setInput(k_,n_)
camera.setInput(0,merge)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((0.0,16.0,0.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.0,0.0,0.0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"viz")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
surface.setDisplayFlag(True)
nodes=(surface,inst,both,fields,noise)
for n_ in nodes:n_.setInput(0,fir)
errors={n.name():n.errors() for n in (rock,ground0,ground,fir,*nodes,camera,dome,sun,settings)}
rs=settings.stage();assert rs and not any(n.errors() for n in (*nodes,settings)),errors
counts={}
for name in ('Surface','Instances','Both','Field','Noise'):
    pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/%s'%name));counts[name]=len(pi.GetPositionsAttr().Get(1) or [])
print({p:bool(rs.GetPrimAtPath(p)) for p in ('/World/Surface_View/VizSurface','/World/Instances_View/VizInstances','/World/Both_View/Proxy','/World/Field_View/VizSurface','/World/Noise_View/VizInstances')})
assert rs.GetPrimAtPath('/World/Surface_View/VizSurface') and rs.GetPrimAtPath('/World/Instances_View/VizInstances') and rs.GetPrimAtPath('/World/Both_View/Proxy') and rs.GetPrimAtPath('/World/Field_View/VizSurface') and rs.GetPrimAtPath('/World/Noise_View/VizInstances')
print(counts)
rs.Export(str(versions.render_usd(VID,'viz')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':counts}))
