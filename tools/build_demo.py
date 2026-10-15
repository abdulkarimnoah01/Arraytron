# LEGACY (pre-versioning script): writes the OLD file names into dist/. The maintained copies of these releases are in dist/archive/ (see docs/VERSIONING.md). Current builders: build_arraytron_v03.py / build_demo_v03.py.
"""Build a portable Solaris demo with an external test USD reference asset."""
from pathlib import Path
import hou, json
from pxr import Usd,UsdGeom,UsdShade,Gf,Sdf,Kind
ROOT=Path(__file__).resolve().parents[1]
hou.hipFile.load(str(ROOT/'dist/Arraytron_v0.1_demo.hip'),suppress_save_prompt=True)
assets=ROOT/'dist/test_assets';assets.mkdir(exist_ok=True)
file=assets/'crate.usda'
s=Usd.Stage.CreateNew(str(file));root=UsdGeom.Xform.Define(s,'/Crate')
s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y);UsdGeom.SetStageMetersPerUnit(s,1)
Usd.ModelAPI(root).SetKind(Kind.Tokens.component)
def material(stage,path,color):
    m=UsdShade.Material.Define(stage,path);shader=UsdShade.Shader.Define(stage,path+'/Surface')
    shader.CreateIdAttr('UsdPreviewSurface');shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.5)
    m.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface');return m
wood=material(s,'/Crate/Looks/Wood',(.22,.085,.028));metal=material(s,'/Crate/Looks/Trim',(.14,.22,.27))
def cube(stage,path,size,pos,mat):
    c=UsdGeom.Cube.Define(stage,path);c.CreateSizeAttr(1)
    x=UsdGeom.Xformable(c);x.AddTranslateOp().Set(Gf.Vec3d(*pos));x.AddScaleOp().Set(Gf.Vec3f(*size))
    UsdShade.MaterialBindingAPI.Apply(c.GetPrim()).Bind(mat);return c
cube(s,'/Crate/Body',(.62,.62,.62),(0,.34,0),wood)
for side in (-1,1):
    for face in (-1,1):
        name=('L' if side<0 else 'R')+('F' if face<0 else 'B')
        cube(s,'/Crate/Corner_'+name,(.075,.70,.075),(side*.32,.35,face*.32),metal)
for y,name in ((.055,'Bottom'),(.645,'Top')):
    for z,side in ((-.32,'Front'),(.32,'Back')):
        cube(s,'/Crate/'+name+side,(.70,.07,.075),(0,y,z),metal)
s.GetRootLayer().Save()
stage=hou.node('/stage')
for child in stage.children():
    if child.name() not in ('demo_crate','Arraytron','render_camera','render_light','karma_xpu'):
        child.destroy()
source=stage.node('demo_crate');line=stage.node('Arraytron')
ref=stage.createNode('reference','reference_test_crate')
ref.parm('primpath').set('/World/Props/Crate');ref.parm('primpath1').set('/World/Props/Crate');ref.parm('filepath1').set('$HIP/test_assets/crate.usda')
ref.parm('filerefprim1').set('defaultPrim')
line.setInput(0,ref)
if source:source.destroy()
line.parmTuple('line_offset').set((0,0,-5));line.setComment('LINE — ten instances; referenced test crate.');line.setGenericFlag(hou.nodeFlag.DisplayComment,True)
area=stage.createNode('arraytron::instancer::0.1','Arraytron_Area');area.setInput(0,line)
area.parm('mode').set(1);area.parm('outputpath').set('/World/ArraytronArea')
area.parm('area_count').set(60);area.parm('area_sizez').set(6);area.parmTuple('area_offset').set((0,0,1))
area.parmTuple('rotation_random').set((0,180,0));area.parm('scale_random').set(.25)
area.setComment('AREA — 60 random XZ points; shared transform/prototype pipeline.');area.setGenericFlag(hou.nodeFlag.DisplayComment,True)
# A separate USD floor keeps the HDA concerned only with instancing.
floorfile=assets/'floor.usda';floorstage=Usd.Stage.CreateNew(str(floorfile))
floorroot=UsdGeom.Xform.Define(floorstage,'/Floor');floorstage.SetDefaultPrim(floorroot.GetPrim())
mat=material(floorstage,'/Floor/Looks/Ground',(.065,.085,.105))
cube(floorstage,'/Floor/Slab',(14,.10,13),(0,-.065,-.5),mat);floorstage.GetRootLayer().Save()
floor=stage.createNode('reference','reference_demo_floor');floor.setInput(0,area)
floor.parm('primpath').set('/World/Floor');floor.parm('primpath1').set('/World/Floor');floor.parm('filepath1').set('$HIP/test_assets/floor.usda')
camera=stage.node('render_camera');camera.setInput(0,floor)
camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36)
camera.parm('focalLength').set(45);camera.parmTuple('aspectratio').set((3,2))
camera.parmTuple('t').set((13,13,18));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0,0,-.5))
light=stage.node('render_light');light.setInput(0,camera)
settings=stage.node('karma_xpu');settings.parm('picture').set('$HIP/../renders/arraytron_demo_xpu.exr');settings.parm('pathtracedsamples').set(128)
settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton()
settings.parmTuple('resolution').set((1200,800))
settings.setDisplayFlag(True)
renderstage=settings.stage()
if not renderstage:
    print({n.name():n.errors() for n in (ref,line,area,floor,camera,light,settings)})
    print('ref token',ref.parm('filerefprim1').parmTemplate().menuItems())
    raise RuntimeError('Demo stage failed')
renderstage.Export(str(ROOT/'dist/demo_render.usda'))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU')
render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu')
render.parm('rendercommand').set('husk --engine xpu')
render.setComment('Render the Line + Area reference-asset demo with Karma XPU.')
render.setGenericFlag(hou.nodeFlag.DisplayComment,True)
stage.layoutChildren();hou.hipFile.save(str(ROOT/'dist/Arraytron_v0.1_demo.hip'))
print(json.dumps({'reference':ref.evalParm('filepath1'),'line_instances':10,'area_instances':60,'errors':{n.name():n.errors() for n in (ref,line,area,settings)}},indent=2))
