"""Build the Instance Place demo (v1.9.0): hython tools/build_demo_place_v190.py
Instances placed one at a time, like the transforms of a Copy and Transform SOP: a pyramid of crates, an arc of rocks growing in size and a few single rocks with their own
rotation, all made by the SAME functions the viewport tool calls (place_add), so the demo needs no mouse. Select the node, press Place Instances in Viewport and click the
ground to add more; Ctrl+click deletes. The table of the Layout tab lists every instance (position, rotation, scale, prototype row, stable id).
Writes dist/Arraytron_<version>_place_demo.hip (and the render USD) or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'place');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
from pxr import Usd, UsdGeom
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
def bounds(name):
    """Size and the height of the origin above the base of a test asset (the demo scales them by the bank scale)."""
    st=Usd.Stage.Open(str(ROOT/'dist/test_assets'/name));box=UsdGeom.BBoxCache(Usd.TimeCode.Default(),[UsdGeom.Tokens.default_]).ComputeWorldBound(st.GetDefaultPrim()).ComputeAlignedRange()
    return np.array(box.GetSize()),float(-box.GetMin()[1])
crate_size,crate_base=bounds('crate.usda');rock_size,rock_base=bounds('rock.usda')
# ---- a wavy path (a BasisCurves prim, written once next to the other test assets) for Place Along Curve
for folder in (ROOT/'dist/test_assets',ROOT/'otls_h205/test_assets'):
    if folder.exists() and not (folder/'path_curve.usda').exists():
        cs=Usd.Stage.CreateNew(str(folder/'path_curve.usda'));root=UsdGeom.Xform.Define(cs,'/PathCurve');cs.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(cs,UsdGeom.Tokens.y)
        xs=np.linspace(-6.5,6.5,14);curve=UsdGeom.BasisCurves.Define(cs,'/PathCurve/Curve');curve.CreateTypeAttr('linear');curve.CreateWrapAttr('nonperiodic');curve.CreatePointsAttr([(float(x),0.0,float(-3.6+0.7*np.sin(x*0.9))) for x in xs]);curve.CreateCurveVertexCountsAttr([len(xs)]);curve.CreateWidthsAttr([0.02]);UsdGeom.Imageable(curve).CreateVisibilityAttr('invisible');cs.GetRootLayer().Save()                    # a guide for the demo, not rendered
rock=reference('reference_rock','/World/Props/Rock',ASSETS+'/rock.usda');crate=reference('reference_crate','/World/Props/Crate',ASSETS+'/crate.usda',rock)
ground0=reference('reference_ground','/World/Ground',ASSETS+'/paint_ground.usda',crate)
ground=reference('reference_path','/World/PathCurve',ASSETS+'/path_curve.usda',ground0)
place=stage.createNode(TYPE,'Arraytron_Place');place.setInput(0,ground);place.parm('outputpath').set('/World/Placed')
place.parm('mode').set(9);place.parm('place_target').set('/World/Ground');place.parm('place_align').set(0.0)
place.parm('protos').set(2);place.parm('proto_prim1').set('/World/Props/Rock');place.parm('proto_scale1').set(0.5);place.parm('proto_prim2').set('/World/Props/Crate');place.parm('proto_scale2').set(0.5)
m=place.hdaModule();s_rock=0.6;s_crate=0.6;edge=float(crate_size[0])*s_crate;drop=crate_base*s_crate
# ---- a pyramid of crates (3 - 2 - 1), every crate rotated a little differently
levels=((3,0.0),(2,0.5),(1,1.0));rng=np.random.RandomState(5)
for level,(count,shift) in enumerate(levels):
    for k in range(count):
        x=-3.3+(k-(count-1)*0.5)*edge*1.02;y=level*edge*0.999;m.place_add(place,(x,y,-1.5),normal=(0,1,0),scale=1.0,yaw=float(rng.uniform(-8,8)),proto=2)
# ---- an arc of rocks, growing in size and turned along the arc
n=12
for k in range(n):
    t=k/(n-1);angle=np.radians(200+t*140);r=3.4;p=(1.5+r*np.cos(angle),0.0,0.3+r*np.sin(angle));m.place_add(place,p,normal=(0,1,0),scale=0.55+0.9*t,yaw=float(-np.degrees(angle)),proto=1)
# ---- three single rocks, each with its own rotation, scale and position
for p,yaw,sc in (((4.6,0.0,2.4),35.0,1.3),((-3.2,0.0,2.8),-70.0,0.8),((0.2,0.0,3.2),10.0,1.0)):m.place_add(place,p,normal=(0,1,0),scale=sc,yaw=yaw,proto=1)
# ---- two ARRAYS (Copy and Transform): a spiral of rocks (every copy turns 26 degrees, steps forward and shrinks a little) and a fence of crates (a straight row, world steps)
m.place_add(place,(2.2,0.0,1.4),normal=(0,1,0),scale=1.2,yaw=0.0,proto=1,rot=(0,0,0));spiral=place.evalParm('places')
place.parm('place_copies%d'%spiral).set(14);place.parmTuple('place_ctrans%d'%spiral).set((0.5,0.0,0.0));place.parmTuple('place_crot%d'%spiral).set((0.0,26.0,0.0));place.parm('place_cscale%d'%spiral).set(0.93);place.parm('place_cspace%d'%spiral).set(0)
m.place_add(place,(-2.0,0.0,2.9),normal=(0,1,0),scale=1.0,yaw=0.0,proto=2,rot=(0,0,0));fence=place.evalParm('places')
place.parm('place_copies%d'%fence).set(5);place.parmTuple('place_ctrans%d'%fence).set((edge*1.05,0.0,0.0));place.parm('place_cspace%d'%fence).set(1)
# ---- stepping stones along the path (Place Along Curve): turned to follow the curve
place.parm('place_curve').set('/World/PathCurve');place.parm('place_curve_mode').set(1);place.parm('place_curve_spacing').set(0.8);place.parm('place_curve_follow').set(1);place.parm('place_curve_project').set(1);place.parm('place_target').set('/World/Ground')
place.parm('place_def_scale').set(0.4);place.parm('place_def_proto').set(1);stones=m.place_along_curve(place);place.parm('place_def_scale').set(1.0);place.parm('place_def_proto').set(0)
place.setComment('INSTANCE PLACE - 23 rows placed one at a time (Distribution Mode: Instance Place): a pyramid of crates, an arc of rocks, three single rocks and two ARRAYS made like the Copy and Transform SOP: a spiral of 14 rocks (Copies 14, each one turns 26 degrees, steps forward and shrinks), a fence of 5 crates (World steps) and a path of stepping stones made with Place Along Curve (Along Curve Prim /World/PathCurve, every 0.8 units, projected on the ground). Select this node and press Place Instances in Viewport: click the ground to add an instance, Ctrl+click deletes the one under the mouse, wheel + Shift scale, wheel + Ctrl rotation, [ ] scale, comma / period rotation, 0-9 the Prototype Row. The table (Placed Instances) holds the position, rotation, scale, prototype and stable id of every instance, so a row can be edited or switched off by hand.')
place.setGenericFlag(hou.nodeFlag.DisplayComment,True)
camera=stage.createNode('camera','render_camera');camera.setInput(0,place)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((0.0,4.8,8.2));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.2,0.4,0.6))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"place")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
place.setDisplayFlag(True)
errors={n.name():n.errors() for n in (rock,crate,ground0,ground,place,camera,dome,sun,settings)}
rs=settings.stage();assert rs and not any(n.errors() for n in (place,settings)),errors
pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/Placed'));ids=list(pi.GetIdsAttr().Get(1));proto=list(pi.GetProtoIndicesAttr().Get(1));assert len(ids)==40+stones and len(set(ids))==40+stones,len(ids)
assert proto.count(1)==11 and proto.count(0)==29+stones,(proto.count(0),proto.count(1))
print(place.parm('place_info').eval())
rs.Export(str(versions.render_usd(VID,'place')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':len(ids),'stones':stones,'rows':place.evalParm('places')}))
