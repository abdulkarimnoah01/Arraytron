# LEGACY (pre-versioning script): writes the OLD file names into dist/. The maintained copies of these releases are in dist/archive/ (see docs/VERSIONING.md). Current builders: build_arraytron_v03.py / build_demo_v03.py.
"""Save an additional demo exercising arbitrary direction and layout transforms."""
from pathlib import Path
import hou
ROOT=Path(__file__).resolve().parents[1]
hou.hipFile.load(str(ROOT/'dist/Arraytron_v0.1_demo.hip'),suppress_save_prompt=True)
line=hou.node('/stage/Arraytron')
line.parm('line_axis').set(3);line.parmTuple('line_direction').set((1,.25,0))
line.parmTuple('line_offset').set((0,2,-4.5));line.parmTuple('line_rotation').set((0,12,0))
line.parmTuple('line_scale').set((1,.8,1))
line.setComment('LINE — custom diagonal direction, translated and rotated as a whole.')
area=hou.node('/stage/Arraytron_Area')
area.parmTuple('area_offset').set((0,1,1));area.parmTuple('area_rotation').set((8,20,0))
area.parmTuple('area_scale').set((1,.8,.8))
area.setComment('AREA — tilted rectangular bounds, translated and scaled as a whole.')
settings=hou.node('/stage/karma_xpu')
settings.parm('picture').set('$HIP/../renders/arraytron_transform_demo_xpu.exr')
assert settings.stage() and not settings.errors(),settings.errors()
settings.stage().Export(str(ROOT/'dist/transform_demo_render.usda'))
hou.hipFile.save(str(ROOT/'dist/Arraytron_transform_demo.hip'))
print('Saved whole-distribution transform demo')
