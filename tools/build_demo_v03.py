"""Build the Prototype Bank demo: hython tools/build_demo_v03.py [v0.3.0|v0.3.5|v0.3.6|v0.4.0]. All four source methods, three selection modes; v0.3.5+ adds a Circle, v0.3.6+ the variation extras. v0.4.0 is the same scene (Physics Settle off): its pile demo is build_demo_physics_v04.py."""
from pathlib import Path
import argparse, sys, hou, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
parser=argparse.ArgumentParser();parser.add_argument('version',nargs='?',default=versions.CURRENT)
VID=versions.resolve(parser.parse_args().version);CIRCLE=VID in ('v0.3.5','v0.3.6','v0.4.0','v0.4.5','v0.4.6','v0.5.0','v0.5.1','v0.5.2','v0.6.0','v0.7.0','v0.8.0','v0.9.0','v1.0.0','v1.1.0','v1.5.0','v1.6.0','v1.6.1','v1.6.2','v1.7.0','v1.8.0','v1.9.0','v1.10.0','v1.11.0','v1.12.0','v1.13.0','v1.14.0','v1.15.0');VARIATION=VID in ('v0.3.6','v0.4.0','v0.4.5','v0.4.6','v0.5.0','v0.5.1','v0.5.2','v0.6.0','v0.7.0','v0.8.0','v0.9.0','v1.0.0','v1.1.0','v1.5.0','v1.6.0','v1.6.1','v1.6.2','v1.7.0','v1.8.0','v1.9.0','v1.10.0','v1.11.0','v1.12.0','v1.13.0','v1.14.0','v1.15.0')
assert VID in ('v0.3.0','v0.3.5','v0.3.6','v0.4.0','v0.4.5','v0.4.6','v0.5.0','v0.5.1','v0.5.2','v0.6.0','v0.7.0','v0.8.0','v0.9.0','v1.0.0','v1.1.0','v1.5.0','v1.6.0','v1.6.1','v1.6.2','v1.7.0','v1.8.0','v1.9.0','v1.10.0','v1.11.0','v1.12.0','v1.13.0','v1.14.0','v1.15.0'),'this builder makes the Prototype Bank demos (v0.3.0 to v0.4.0); the Physics Settle demo is tools/build_demo_physics_v04.py'
TYPE=versions.type_name(VID);HIP=versions.demo(VID);ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
HIP.parent.mkdir(parents=True,exist_ok=True)
hou.hipFile.clear(suppress_save_prompt=True)
versions.ensure_installed(VID)
hou.hipFile.save(str(HIP))  # resolves $HIP for the reference paths
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path)
    n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
crate=reference('reference_test_crate','/World/Props/Crate',ASSETS+'/crate.usda')
barrel=reference('reference_test_barrel','/World/Props/Barrel',ASSETS+'/barrel.usda')
# SOP Geometry source: an ordinary geometry object anywhere in the scene (here a cone).
geo=hou.node('/obj').createNode('geo','proto_cone');cone=geo.createNode('tube','cone')
cone.parm('rad1').set(.28);cone.parm('rad2').set(0);cone.parm('height').set(.9);cone.parmTuple('t').set((0,.45,0))
out=geo.createNode('null','OUT');out.setInput(0,cone);out.setDisplayFlag(True);out.setRenderFlag(True)

def row(node,index,**values):
    for key,value in values.items():
        parm=node.parmTuple(f'proto_{key}{index}')
        parm.set(value if isinstance(value,(tuple,list)) else (value,))

line=stage.createNode(TYPE,'Arraytron');line.setInput(0,crate);line.setInput(1,barrel)
line.parm('protos').set(2);line.parm('proto_mode').set(3)                 # Cycle
row(line,1,type=0,prim='/World/Props/Crate')
row(line,2,type=1,input=0)                                                # Input Connection: wired barrel, prim picked automatically
line.parm('line_axis').set(3);line.parmTuple('line_direction').set((1,.25,0))
line.parm('line_spacemode').set(1);line.parm('line_spacing').set(1.4);line.parm('line_length').set(12)
line.parmTuple('bound_t').set((0,2,-4.5));line.parmTuple('bound_r').set((0,12,0));line.parmTuple('bound_s').set((1,.8,1))
line.setComment('LINE — Cycle: crate, barrel, crate, barrel. The barrel arrives through Prototype Input 2 (Input Connection), no path typed.')
line.setGenericFlag(hou.nodeFlag.DisplayComment,True)

area=stage.createNode(TYPE,'Arraytron_Area');area.setInput(0,line)
area.parm('mode').set(1);area.parm('outputpath').set('/World/ArraytronArea')
area.parm('protos').set(4);area.parm('proto_mode').set(1);area.parm('proto_seed').set(7)    # Weighted Random
row(area,1,type=0,prim='/World/Props/Crate',weight=4)
row(area,2,type=0,prim='/World/Props/Barrel',weight=2)                    # Prim in Stream (already in the incoming stream)
row(area,3,type=2,file=ASSETS+'/rock.usda',weight=3,scale=1.25,scalevar=.25)   # USD File
row(area,4,type=3,sop=out.path(),weight=1,rot=(0,45,0))                   # SOP Geometry
area.parm('area_count').set(80);area.parm('area_sizex').set(8);area.parm('area_sizez').set(6)
area.parmTuple('bound_t').set((-1.5,1,1));area.parmTuple('bound_r').set((8,20,0))
area.parmTuple('position_random').set((1.2,0,1.2));area.parm('area_keepinside').set(1)
if VARIATION:
    area.parm('rotation_random_mode').set(1);area.parm('yaw_random').set(180)             # Yaw Only: every heading, always level
    area.parm('scale_random_mode').set(1);area.parm('scale_min').set(.75);area.parm('scale_max').set(1.35)   # Min / Max range
    area.setComment('AREA — Weighted Random (crate 4, barrel 2, rock 3 via USD File, cone 1 via SOP Geometry). Variation: Yaw Only 180 (every heading, always level) and Scale Min / Max 0.75 to 1.35.')
else:
    area.parmTuple('rotation_random').set((0,180,0));area.parm('scale_random').set(.15)
    area.setComment('AREA — Weighted Random: crate 4, barrel 2, rock 3 (USD File, scaled 1.25 +/-25%), cone 1 (SOP Geometry).')
area.setGenericFlag(hou.nodeFlag.DisplayComment,True)

grid=stage.createNode(TYPE,'Arraytron_Grid');grid.setInput(0,area)
grid.parm('mode').set(2);grid.parm('outputpath').set('/World/ArraytronGrid')
grid.parm('protos').set(2);grid.parm('proto_mode').set(2)                 # Sequential: blocks in id order
row(grid,1,type=0,prim='/World/Props/Crate',weight=2)
row(grid,2,type=0,prim='/World/Props/Barrel',weight=1)
grid.parmTuple('grid_count').set((3,3,3));grid.parmTuple('grid_size').set((4,3,4))
grid.parmTuple('bound_t').set((3.8,1.6,1.2));grid.parmTuple('bound_r').set((0,15,0))
if VARIATION:
    grid.parmTuple('scale_nonuniform').set((0,.35,0))                                       # heights vary, widths stay locked
    grid.setComment('GRID — Sequential: the first two thirds of the points (by id) are crates, the last third barrels. Variation: Non-Uniform (0, 0.35, 0): every height differs, widths stay locked.')
else:
    grid.setComment('GRID — Sequential: the first two thirds of the points (by id) are crates, the last third barrels.')
grid.setGenericFlag(hou.nodeFlag.DisplayComment,True)

last=grid
if CIRCLE:
    circle=stage.createNode(TYPE,'Arraytron_Circle');circle.setInput(0,grid)
    circle.parm('mode').set(3);circle.parm('outputpath').set('/World/ArraytronCircle')
    circle.parm('protos').set(2);circle.parm('proto_mode').set(3)           # Cycle: crate, barrel, crate, ...
    row(circle,1,type=0,prim='/World/Props/Crate');row(circle,2,type=0,prim='/World/Props/Barrel')
    circle.parm('circle_radius').set(2.2);circle.parm('circle_count').set(14);circle.parm('circle_arc').set(270);circle.parm('circle_start').set(-45)
    circle.parm('circle_facing').set(1)                                      # Outward: each crate's forward axis points away from the centre
    circle.parmTuple('bound_t').set((4.6,.1,-3.6))
    circle.setComment('CIRCLE — 14 points on a 270 degree arc, Facing: Outward. Cycle: crate, barrel, crate, ...')
    circle.setGenericFlag(hou.nodeFlag.DisplayComment,True)
    last=circle
CURVES=VID in ('v0.4.5','v0.4.6','v0.5.0','v0.5.1','v0.5.2','v0.6.0','v0.7.0','v0.8.0','v0.9.0','v1.0.0','v1.1.0','v1.5.0','v1.6.0','v1.6.1','v1.6.2','v1.7.0','v1.8.0','v1.9.0','v1.10.0','v1.11.0','v1.12.0','v1.13.0','v1.14.0','v1.15.0')
if CURVES:
    curve_ref=reference('reference_curve','/World/Curve',ASSETS+'/curve_s.usda',last)
    curve=stage.createNode(TYPE,'Arraytron_Curve');curve.setInput(0,curve_ref)
    curve.parm('mode').set(4);curve.parm('outputpath').set('/World/ArraytronCurve');curve.parm('curve_prim').set('/World/Curve')
    curve.parm('protos').set(2);curve.parm('proto_mode').set(3)                                  # Cycle: crate, barrel, crate, ...
    row(curve,1,type=0,prim='/World/Props/Crate');row(curve,2,type=0,prim='/World/Props/Barrel')
    curve.parm('curve_spacemode').set(1);curve.parm('curve_spacing').set(0.8);curve.parm('curve_align').set(1)   # a point every 0.8 along the S bend, facing along the curve
    curve.parm('base_scale').set(0.75)
    curve.parmTuple('bound_t').set((2.5,0,3.8))
    curve.setComment('CURVE - the S shaped bezier /World/Curve (a curve prim from the stream), a point every 0.8 units, Alignment: Tangent (the crate and barrel forward axes follow the curve). Cycle: crate, barrel, ...')
    curve.setGenericFlag(hou.nodeFlag.DisplayComment,True)
    last=curve
floor=stage.createNode('reference','reference_demo_floor');floor.setInput(0,last)
floor.parm('primpath').set('/World/Floor');floor.parm('primpath1').set('/World/Floor')
floor.parm('filepath1').set(ASSETS+'/floor.usda');floor.parm('filerefprim1').set('defaultPrim')
camera=stage.createNode('camera','render_camera');camera.setInput(0,floor)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective')
camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(45);camera.parmTuple('aspectratio').set((3,2))
camera.parmTuple('t').set((13,13,18));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0,0,-.5))
light=stage.createNode('domelight','render_light');light.setInput(0,camera)
settings=demo_compat.karma_settings(stage,light)
settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID)}.exr')
settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton()
demo_compat.set_resolution(settings,(1200,800))
# Display upstream of the Karma settings: the viewport adopts /Render/karma_xpu includedPurposes (default, render),
# which would hide the guide-purpose Bounds Guide. karma_xpu and the render ROP are unaffected.
floor.setDisplayFlag(True)
renderstage=settings.stage()
nodes=[crate,barrel,line,area,grid,floor,camera,light,settings]+([circle] if CIRCLE else [])+([curve] if CURVES else [])
errors={n.name():n.errors() for n in nodes}
assert renderstage and not any(errors.values()),errors
renderstage.Export(str(versions.render_usd(VID)))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU')
render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu')
render.parm('rendercommand').set('husk --engine xpu')
render.setComment('Render the demo with Karma XPU.')
render.setGenericFlag(hou.nodeFlag.DisplayComment,True)
stage.layoutChildren()
hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'errors':errors},indent=2))
