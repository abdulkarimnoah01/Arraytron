# LEGACY (pre-versioning script): writes the OLD file names into dist/. The maintained copies of these releases are in dist/archive/ (see docs/VERSIONING.md). Current builders: build_arraytron_v03.py / build_demo_v03.py.
"""Build a demo: hython tools/build_demo_v016.py [v016|v02|v021]. Referenced crate, Line By Spacing, Area with Keep Inside, Grid (v02/v021)."""
from pathlib import Path
import argparse, hou, json
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('version',nargs='?',default='v016',choices=('v016','v02','v021'))
VERSION=parser.parse_args().version
TYPE,HDA,HIPNAME=dict(v016=('arraytron::instancer::0.16','Arraytron_v0.16.hda','Arraytron_v0.16_demo.hip'),
                      v02=('arraytron::instancer::0.20','Arraytron_v0.2.hda','Arraytron_v0.2_demo.hip'),
                      v021=('arraytron::instancer::0.21','Arraytron_v0.21.hda','Arraytron_v0.21_demo.hip'))[VERSION]
TAG=VERSION;GRID=VERSION!='v016';HIP=ROOT/'dist'/HIPNAME
hou.hipFile.clear(suppress_save_prompt=True)
hou.hda.installFile(str(ROOT/'dist'/HDA))
hou.hipFile.save(str(HIP))  # resolves $HIP for the reference paths
stage=hou.node('/stage')
ref=stage.createNode('reference','reference_test_crate')
ref.parm('primpath').set('/World/Props/Crate');ref.parm('primpath1').set('/World/Props/Crate')
ref.parm('filepath1').set('$HIP/test_assets/crate.usda');ref.parm('filerefprim1').set('defaultPrim')

line=stage.createNode(TYPE,'Arraytron');line.setInput(0,ref)
line.parm('line_axis').set(3);line.parmTuple('line_direction').set((1,.25,0))
line.parm('line_spacemode').set(1);line.parm('line_spacing').set(1.4);line.parm('line_length').set(12)
line.parmTuple('bound_t').set((0,2,-4.5));line.parmTuple('bound_r').set((0,12,0));line.parmTuple('bound_s').set((1,.8,1))
line.setComment('LINE — By Spacing: a crate every 1.4 units over a 12 unit length, custom diagonal direction, moved/rotated/scaled by the Bounds Transform.')
line.setGenericFlag(hou.nodeFlag.DisplayComment,True)

area=stage.createNode(TYPE,'Arraytron_Area');area.setInput(0,line)
area.parm('mode').set(1);area.parm('outputpath').set('/World/ArraytronArea')
area.parm('area_count').set(60);area.parm('area_sizex').set(8);area.parm('area_sizez').set(6)
area.parmTuple('bound_t').set((-1.5,1,1));area.parmTuple('bound_r').set((8,20,0));area.parmTuple('bound_s').set((1,.8,.8))
area.parmTuple('position_random').set((2,0,2));area.parm('area_keepinside').set(1)
area.parmTuple('rotation_random').set((0,180,0));area.parm('scale_random').set(.25)
area.setComment('AREA — tilted, scaled bounds'+(' (Scale Instances is off: the layout is scaled, the crates keep their size)' if VERSION=='v021' else '')+'. Position jitter 2 with Keep Inside Area on: no crate leaves the rectangle.')
area.setGenericFlag(hou.nodeFlag.DisplayComment,True)
last=area
if GRID:
    grid=stage.createNode(TYPE,'Arraytron_Grid');grid.setInput(0,area)
    grid.parm('mode').set(2);grid.parm('outputpath').set('/World/ArraytronGrid')
    grid.parmTuple('grid_count').set((3,3,3));grid.parmTuple('grid_size').set((4,3,4))
    grid.parmTuple('bound_t').set((3.8,1.6,1.2));grid.parmTuple('bound_r').set((0,15,0))
    grid.setComment('GRID — a 3 x 3 x 3 matrix of crates (By Count), 4 x 3 x 4 units, rotated by the Bounds Transform.')
    grid.setGenericFlag(hou.nodeFlag.DisplayComment,True)
    last=grid

floor=stage.createNode('reference','reference_demo_floor');floor.setInput(0,last)
floor.parm('primpath').set('/World/Floor');floor.parm('primpath1').set('/World/Floor')
floor.parm('filepath1').set('$HIP/test_assets/floor.usda');floor.parm('filerefprim1').set('defaultPrim')
camera=stage.createNode('camera','render_camera');camera.setInput(0,floor)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective')
camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(45);camera.parmTuple('aspectratio').set((3,2))
camera.parmTuple('t').set((13,13,18));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0,0,-.5))
light=stage.createNode('domelight','render_light');light.setInput(0,camera)
settings=stage.createNode('karmarendersettings','karma_xpu');settings.setInput(0,light)
settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'$HIP/../renders/arraytron_{TAG}_demo_xpu.exr')
settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton()
settings.parmTuple('resolution').set((1200,800))
# Display upstream of the Karma settings: the viewport adopts /Render/karma_xpu includedPurposes (default, render),
# which would hide the guide-purpose Bounds Guide. karma_xpu and the render ROP are unaffected.
floor.setDisplayFlag(True)
renderstage=settings.stage()
nodes=[ref,line,area,floor,camera,light,settings]+([grid] if GRID else [])
errors={n.name():n.errors() for n in nodes}
assert renderstage and not any(errors.values()),errors
renderstage.Export(str(ROOT/'dist'/f'{TAG}_demo_render.usda'))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU')
render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu')
render.parm('rendercommand').set('husk --engine xpu')
render.setComment('Render the demo with Karma XPU.')
render.setGenericFlag(hou.nodeFlag.DisplayComment,True)
stage.layoutChildren()
hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'errors':errors},indent=2))
