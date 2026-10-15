# LEGACY (pre-versioning script): writes the OLD file names into dist/. The maintained copies of these releases are in dist/archive/ (see docs/VERSIONING.md). Current builders: build_arraytron_v03.py / build_demo_v03.py.
"""Build the v0.15 demo: referenced crate, Line + Area using the Bounds Transform, floor, camera, Karma XPU."""
from pathlib import Path
import hou, json
ROOT=Path(__file__).resolve().parents[1]
TYPE='arraytron::instancer::0.15'
hou.hipFile.clear(suppress_save_prompt=True)
hou.hda.installFile(str(ROOT/'dist/Arraytron_v0.15.hda'))
hou.hipFile.save(str(ROOT/'dist/Arraytron_v0.15_demo.hip'))  # resolves $HIP for the reference paths
stage=hou.node('/stage')
ref=stage.createNode('reference','reference_test_crate')
ref.parm('primpath').set('/World/Props/Crate');ref.parm('primpath1').set('/World/Props/Crate')
ref.parm('filepath1').set('$HIP/test_assets/crate.usda');ref.parm('filerefprim1').set('defaultPrim')

line=stage.createNode(TYPE,'Arraytron');line.setInput(0,ref)
line.parm('line_axis').set(3);line.parmTuple('line_direction').set((1,.25,0))
line.parmTuple('bound_t').set((0,2,-4.5));line.parmTuple('bound_r').set((0,12,0));line.parmTuple('bound_s').set((1,.8,1))
line.setComment('LINE — custom diagonal direction. The whole line is moved, rotated and scaled from Bounds Transform (or the viewport handle).')
line.setGenericFlag(hou.nodeFlag.DisplayComment,True)

area=stage.createNode(TYPE,'Arraytron_Area');area.setInput(0,line)
area.parm('mode').set(1);area.parm('outputpath').set('/World/ArraytronArea')
area.parm('area_count').set(60);area.parm('area_sizez').set(6)
area.parmTuple('bound_t').set((0,1,1));area.parmTuple('bound_r').set((8,20,0));area.parmTuple('bound_s').set((1,.8,.8))
area.parmTuple('rotation_random').set((0,180,0));area.parm('scale_random').set(.25)
area.setComment('AREA — tilted, scaled rectangular bounds. Same Bounds Transform controls as Line.')
area.setGenericFlag(hou.nodeFlag.DisplayComment,True)

floor=stage.createNode('reference','reference_demo_floor');floor.setInput(0,area)
floor.parm('primpath').set('/World/Floor');floor.parm('primpath1').set('/World/Floor')
floor.parm('filepath1').set('$HIP/test_assets/floor.usda');floor.parm('filerefprim1').set('defaultPrim')
camera=stage.createNode('camera','render_camera');camera.setInput(0,floor)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective')
camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(45);camera.parmTuple('aspectratio').set((3,2))
camera.parmTuple('t').set((13,13,18));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0,0,-.5))
light=stage.createNode('domelight','render_light');light.setInput(0,camera)
settings=stage.createNode('karmarendersettings','karma_xpu');settings.setInput(0,light)
settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set('$HIP/../renders/arraytron_v015_demo_xpu.exr')
settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton()
settings.parmTuple('resolution').set((1200,800))
# Display upstream of the Karma settings: the viewport adopts /Render/karma_xpu includedPurposes (default, render),
# which would hide the guide-purpose Bounds Guide. karma_xpu and the render ROP are unaffected.
floor.setDisplayFlag(True)
renderstage=settings.stage()
errors={n.name():n.errors() for n in (ref,line,area,floor,camera,light,settings)}
assert renderstage and not any(errors.values()),errors
renderstage.Export(str(ROOT/'dist/v015_demo_render.usda'))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU')
render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu')
render.parm('rendercommand').set('husk --engine xpu')
render.setComment('Render the v0.15 Line + Area demo with Karma XPU.')
render.setGenericFlag(hou.nodeFlag.DisplayComment,True)
stage.layoutChildren()
hou.hipFile.save(str(ROOT/'dist/Arraytron_v0.15_demo.hip'))
print(json.dumps({'saved':hou.hipFile.path(),'errors':errors},indent=2))
