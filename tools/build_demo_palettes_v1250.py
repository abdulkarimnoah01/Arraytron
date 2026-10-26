"""Build the Visualize palettes demo (v1.25.0): hython tools/build_demo_palettes_v1250.py
The same Mask noise on ten small Area scatters, each shown as Vertex Colours on a copy of the ground with another palette (Blue to Yellow, Heat, Viridis, Magma, Rainbow, Grayscale, Red Yellow Green,
Cool to Warm, Terrain and a Custom Gradient ramp); one more with a narrowed Range and a lower opacity (Debugging tab, section VISUALIZE). Writes dist/Arraytron_<version>_palettes_demo.hip (and the render
USD) or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'palettes');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
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
nodes=[]
base=dict(mode=1,area_sizex=3.4,area_sizez=3.4,area_count=40,area_seed=2,mask_source=1,mask_noise_type=0,mask_noise_freq=0.55,mask_noise_octaves=2,mask_noise_contrast=3.0,mask_effect=1,mask_minscale=0.25,viz_target=3,viz_style=0,viz_res=30000,dbg_size=0.07)
nodes.append(node('Arraytron_Palette_BlueYellow','/World/BlueYellow','VISUALIZE Palette BlueYellow: the Mask noise as vertex colours on the ground (Debugging tab, VISUALIZE: Palette).',bound_t=(-6.0,0.0,-4.0),viz_palette=0,**base))
nodes.append(node('Arraytron_Palette_Heat','/World/Heat','VISUALIZE Palette Heat: the Mask noise as vertex colours on the ground (Debugging tab, VISUALIZE: Palette).',bound_t=(-2.0,0.0,-4.0),viz_palette=1,**base))
nodes.append(node('Arraytron_Palette_Viridis','/World/Viridis','VISUALIZE Palette Viridis: the Mask noise as vertex colours on the ground (Debugging tab, VISUALIZE: Palette).',bound_t=(2.0,0.0,-4.0),viz_palette=2,**base))
nodes.append(node('Arraytron_Palette_Magma','/World/Magma','VISUALIZE Palette Magma: the Mask noise as vertex colours on the ground (Debugging tab, VISUALIZE: Palette).',bound_t=(6.0,0.0,-4.0),viz_palette=3,**base))
nodes.append(node('Arraytron_Palette_Rainbow','/World/Rainbow','VISUALIZE Palette Rainbow: the Mask noise as vertex colours on the ground (Debugging tab, VISUALIZE: Palette).',bound_t=(-6.0,0.0,0.0),viz_palette=4,**base))
nodes.append(node('Arraytron_Palette_Grayscale','/World/Grayscale','VISUALIZE Palette Grayscale: the Mask noise as vertex colours on the ground (Debugging tab, VISUALIZE: Palette).',bound_t=(-2.0,0.0,0.0),viz_palette=5,**base))
nodes.append(node('Arraytron_Palette_RedYellowGreen','/World/RedYellowGreen','VISUALIZE Palette RedYellowGreen: the Mask noise as vertex colours on the ground (Debugging tab, VISUALIZE: Palette).',bound_t=(2.0,0.0,0.0),viz_palette=6,**base))
nodes.append(node('Arraytron_Palette_CoolWarm','/World/CoolWarm','VISUALIZE Palette CoolWarm: the Mask noise as vertex colours on the ground (Debugging tab, VISUALIZE: Palette).',bound_t=(6.0,0.0,0.0),viz_palette=7,**base))
nodes.append(node('Arraytron_Palette_Terrain','/World/Terrain','VISUALIZE Palette Terrain: the Mask noise as vertex colours on the ground (Debugging tab, VISUALIZE: Palette).',bound_t=(-6.0,0.0,4.0),viz_palette=8,**base))
nodes.append(node('Arraytron_Palette_Custom','/World/Custom','VISUALIZE Palette Custom: the Mask noise as vertex colours on the ground (Debugging tab, VISUALIZE: Palette).',bound_t=(-2.0,0.0,4.0),viz_palette=9,**base))
nodes.append(node('Arraytron_Palette_RangeOpacity','/World/RangeOpacity','VISUALIZE Palette RangeOpacity: the Mask noise as vertex colours on the ground (Debugging tab, VISUALIZE: Palette).',bound_t=(2.0,0.0,4.0),viz_palette=2,viz_range=(0.4,0.9),viz_opacity=0.6,**base))
custom=nodes[9];custom.parm('viz_ramp').set(hou.Ramp((hou.rampBasis.Linear,)*3,(0.0,0.5,1.0),((0.05,0.05,0.4),(1.0,0.2,0.6),(1.0,0.95,0.3))))                                   # the Custom Gradient: indigo, pink, yellow
camera=stage.createNode('camera','render_camera');merge=stage.createNode('merge','merge_all')
for k_,n_ in enumerate(nodes):n_.setInput(0,fir);merge.setInput(k_,n_)
camera.setInput(0,merge)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((0.0,20.0,8.0));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.0,0.0,0.0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"palettes")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
merge.setDisplayFlag(True)
errors={n.name():n.errors() for n in (rock,ground0,ground,fir,*nodes,camera,dome,sun,settings)}
rs=settings.stage();assert rs and not any(n.errors() for n in (*nodes,settings)),errors
counts={}
for n_ in nodes:
    nm=n_.name().split('_',2)[2];pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/%s'%nm));counts[nm]=len(pi.GetPositionsAttr().Get(1) or [])
    assert rs.GetPrimAtPath('/World/%s_View/VizSurface'%nm).GetTypeName()=='Mesh' and rs.GetPrimAtPath('/World/%s_View/VizInstances'%nm),nm
print(counts)
rs.Export(str(versions.render_usd(VID,'palettes')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':counts}))
