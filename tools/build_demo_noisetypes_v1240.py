"""Build the Noise types + Visualize demo (v1.24.0): hython tools/build_demo_noisetypes_v1240.py
The eleven new noise types of the Noise section (Variation tab) on a small grid each, coloured by how far the noise moved every point (Noise > Visualize), and a Mask noise shown on the ground and the
instances (Mask > Visualize). Writes dist/Arraytron_<version>_noisetypes_demo.hip (and the render USD) or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'noisetypes');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
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
grid=dict(mode=2,grid_countx=14,grid_county=1,grid_countz=2,grid_sizex=5.6,grid_sizez=0.7,dbg_size=0.09)
nodes=[]
nodes.append(node('Arraytron_Noise_Value','/World/Value','NOISE Value (Variation tab, Noise > Noise Type Value): colour = how far the noise moved the point, blue 0 to yellow 1 (Noise > Visualize).',bound_t=(-3.6,0.0,-5.0),noise_on=1,noise_type=4,noise_amp=(0.45,0.0,0.45),noise_viz=1,noise_freq=0.9,**grid))
nodes.append(node('Arraytron_Noise_Alligator','/World/Alligator','NOISE Alligator (Variation tab, Noise > Noise Type Alligator): colour = how far the noise moved the point, blue 0 to yellow 1 (Noise > Visualize).',bound_t=(3.6,0.0,-5.0),noise_on=1,noise_type=5,noise_amp=(0.45,0.0,0.45),noise_viz=1,noise_freq=0.9,**grid))
nodes.append(node('Arraytron_Noise_Worley','/World/Worley','NOISE Worley (Variation tab, Noise > Noise Type Worley): colour = how far the noise moved the point, blue 0 to yellow 1 (Noise > Visualize).',bound_t=(-3.6,0.0,-3.0),noise_on=1,noise_type=6,noise_amp=(0.45,0.0,0.45),noise_viz=1,noise_freq=0.9,**grid))
nodes.append(node('Arraytron_Noise_Voronoi','/World/Voronoi','NOISE Voronoi (Variation tab, Noise > Noise Type Voronoi): colour = how far the noise moved the point, blue 0 to yellow 1 (Noise > Visualize).',bound_t=(3.6,0.0,-3.0),noise_on=1,noise_type=7,noise_amp=(0.45,0.0,0.45),noise_viz=1,noise_freq=0.9,**grid))
nodes.append(node('Arraytron_Noise_Ridged','/World/Ridged','NOISE Ridged (Variation tab, Noise > Noise Type Ridged): colour = how far the noise moved the point, blue 0 to yellow 1 (Noise > Visualize).',bound_t=(-3.6,0.0,-1.0),noise_on=1,noise_type=8,noise_amp=(0.45,0.0,0.45),noise_viz=1,noise_freq=0.9,**grid))
nodes.append(node('Arraytron_Noise_Billow','/World/Billow','NOISE Billow (Variation tab, Noise > Noise Type Billow): colour = how far the noise moved the point, blue 0 to yellow 1 (Noise > Visualize).',bound_t=(3.6,0.0,-1.0),noise_on=1,noise_type=9,noise_amp=(0.45,0.0,0.45),noise_viz=1,noise_freq=0.9,**grid))
nodes.append(node('Arraytron_Noise_Turbulence','/World/Turbulence','NOISE Turbulence (Variation tab, Noise > Noise Type Turbulence): colour = how far the noise moved the point, blue 0 to yellow 1 (Noise > Visualize).',bound_t=(-3.6,0.0,1.0),noise_on=1,noise_type=10,noise_amp=(0.45,0.0,0.45),noise_viz=1,noise_freq=0.9,**grid))
nodes.append(node('Arraytron_Noise_FBM','/World/FBM','NOISE FBM (Variation tab, Noise > Noise Type FBM): colour = how far the noise moved the point, blue 0 to yellow 1 (Noise > Visualize).',bound_t=(3.6,0.0,1.0),noise_on=1,noise_type=11,noise_amp=(0.45,0.0,0.45),noise_viz=1,noise_freq=0.9,**grid))
nodes.append(node('Arraytron_Noise_DomainWarp','/World/DomainWarp','NOISE DomainWarp (Variation tab, Noise > Noise Type DomainWarp): colour = how far the noise moved the point, blue 0 to yellow 1 (Noise > Visualize).',bound_t=(-3.6,0.0,3.0),noise_on=1,noise_type=12,noise_amp=(0.45,0.0,0.45),noise_viz=1,noise_freq=0.9,**grid))
nodes.append(node('Arraytron_Noise_Flow','/World/Flow','NOISE Flow (Variation tab, Noise > Noise Type Flow): colour = how far the noise moved the point, blue 0 to yellow 1 (Noise > Visualize).',bound_t=(3.6,0.0,3.0),noise_on=1,noise_type=13,noise_amp=(0.45,0.0,0.45),noise_viz=1,noise_freq=0.9,**grid))
nodes.append(node('Arraytron_Noise_Periodic','/World/Periodic','NOISE Periodic (Variation tab, Noise > Noise Type Periodic): colour = how far the noise moved the point, blue 0 to yellow 1 (Noise > Visualize).',bound_t=(-3.6,0.0,5.0),noise_on=1,noise_type=14,noise_amp=(0.45,0.0,0.45),noise_viz=1,noise_period=2.0,noise_freq=0.5,**grid))
mask=node('Arraytron_Mask_Viz','/World/MaskViz','MASK Visualize - the Mask noise on the ground and on the instances (Variation tab, Mask > Visualize: Both).',bound_t=(3.6,0.0,5.0),mode=1,area_sizex=5.6,area_sizez=3.0,area_count=40,area_seed=2,mask_source=1,mask_noise_freq=0.6,mask_noise_contrast=2.5,mask_effect=1,mask_minscale=0.25,mask_viz=3,viz_count=3000,dbg_size=0.09)
nodes.append(mask)
camera=stage.createNode('camera','render_camera');merge=stage.createNode('merge','merge_all')
for k_,n_ in enumerate(nodes):n_.setInput(0,fir);merge.setInput(k_,n_)
camera.setInput(0,merge)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((0.0,17.0,6.0));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.0,0.0,0.0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"noisetypes")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
merge.setDisplayFlag(True)
errors={n.name():n.errors() for n in (rock,ground0,ground,fir,*nodes,camera,dome,sun,settings)}
rs=settings.stage();assert rs and not any(n.errors() for n in (*nodes,settings)),errors
counts={}
for nm in [n_.name().split('_',2)[2] if n_.name().startswith('Arraytron_Noise_') else 'MaskViz' for n_ in nodes]:
    pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/%s'%nm));counts[nm]=len(pi.GetPositionsAttr().Get(1) or [])
    assert rs.GetPrimAtPath('/World/%s_View/VizInstances'%nm),nm
assert rs.GetPrimAtPath('/World/MaskViz_View/VizSurface')
print(counts)
rs.Export(str(versions.render_usd(VID,'noisetypes')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':counts}))
