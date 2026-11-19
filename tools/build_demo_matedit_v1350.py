"""Build the material-edit demo (v1.35.0): hython tools/build_demo_matedit_v1350.py
Edit the existing material of a ready-made USD asset after the scatter. Houdini's rubber toy is scattered twice:
  A  as scattered: the toy's own MaterialX material (Arraytron's copy of it under /World/ArraytronA/Prototypes).
  B  the same scatter, then the Python LOP edit_toy_material: it overrides values of the shaders inside Arraytron's copy of the material
     (Tint, Subsurface, Roughness Scale are parameters on the node). Only the values set are written; the textures and the rest of the
     material stay, and every instance of the prototype gets the edit. The asset file on disk is never touched.
Houdini's Edit Material LOP is not used: on this asset (shaders inside a MaterialX node graph) it writes the shaders back without their
values (black toys, also on the original /rubbertoy material, Houdini 20.5). Edit Properties on the shader prim is the other way.
Asserts the overrides land on Arraytron's copy, the texture input is kept, A is unchanged. Writes dist/Arraytron_<version>_matedit_demo.hip
or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdShade
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'matedit')
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage')
toy=stage.createNode('reference','rubbertoy');toy.parm('filepath1').set('$HH/usd/assets/rubbertoy/rubbertoy.usd');toy.parm('primpath1').set('/rubbertoy')
toy.setPosition((0,4))
def scatter(name,out,x,comment):
    c=stage.createNode(TYPE,name);assert c.hdaModule().test_setup(c);c.setInput(0,toy);c.parm('copy_test_ground').set(1)
    c.parm('proto_type1').set(0);c.parm('proto_prim1').set('/rubbertoy');c.parm('outputpath').set(out);c.parm('mode').set(1)
    c.parm('area_count').set(40);c.parm('area_sizex').set(9.0);c.parm('area_sizez').set(9.0);c.parm('scale_min').set(0.6);c.parm('scale_max').set(0.8)
    c.parm('bound_tx').set(x);c.setPosition((x/3.0,2));c.setComment(comment);c.setGenericFlag(hou.nodeFlag.DisplayComment,True);return c
a=scatter('Arraytron_A_AsScattered','/World/ArraytronA',-6.0,'A: the rubber toy as scattered, with its own material (Arraytron copies it into /World/ArraytronA/Prototypes).')
b=scatter('Arraytron_B_Scatter','/World/ArraytronB',6.0,'B: the same scatter; the node below edits its material.')
CODE='''# Edit the existing material of a scattered USD asset: override shader values in Arraytron's copy of the material.
# The copy lives under <Output Path>/Prototypes/<asset>/...; every instance of that prototype uses it. Only the values set here are written.
from pxr import Usd, Gf
node = hou.pwd()
stage = node.editableStage()
mat = stage.GetPrimAtPath(node.evalParm('material'))
if not mat:
    raise hou.NodeError('No material at ' + node.evalParm('material'))
def shader(name):
    """The shader prim called name anywhere inside the material (also inside its MaterialX node graph)."""
    for p in Usd.PrimRange(mat):
        if p.GetName() == name:
            return p
    raise hou.NodeError('No shader %s inside %s' % (name, mat.GetPath()))
surface = shader('mtlxstandard_surface')
surface.GetAttribute('inputs:subsurface').Set(node.evalParm('subsurface'))     # the toy's look comes from subsurface; 0 shows base_color
tint = node.evalParmTuple('tint')
shader('mtlxmultiply1').GetAttribute('inputs:in2').Set(Gf.Vec3f(*tint))          # base_color = colour texture x tint
shader('mtlxmultiply2').GetAttribute('inputs:in2').Set(node.evalParm('roughness')) # specular_roughness = spec texture x this
'''
ed=stage.createNode('pythonscript','edit_toy_material');ed.setInput(0,b);ed.setPosition((2,0.5))
ptg=ed.parmTemplateGroup()
fold=hou.FolderParmTemplate('edit','Material Edit',folder_type=hou.folderType.Simple)
fold.addParmTemplate(hou.StringParmTemplate('material','Material',1,default_value=('/World/ArraytronB/Prototypes/rubbertoy/mtl/ToyShader',),help="Arraytron's copy of the asset's material (under the Output Path / Prototypes)."))
fold.addParmTemplate(hou.FloatParmTemplate('tint','Tint',3,default_value=(1.0,0.15,0.12),naming_scheme=hou.parmNamingScheme.RGBA,look=hou.parmLook.ColorSquare,help='Multiplies the colour texture (mtlxmultiply1.in2).'))
fold.addParmTemplate(hou.FloatParmTemplate('subsurface','Subsurface',1,default_value=(0.0,),min=0.0,max=1.0,help='mtlxstandard_surface.subsurface; the asset has 1, which hides base_color.'))
fold.addParmTemplate(hou.FloatParmTemplate('roughness','Roughness Scale',1,default_value=(0.6,),min=0.0,max=1.0,help='Multiplies the spec texture into specular_roughness (mtlxmultiply2.in2; the asset has 0.25).'))
ptg.insertBefore(ptg.find('python') or ptg.entries()[0],fold);ed.setParmTemplateGroup(ptg)
ed.parm('python').set(CODE)
ed.setComment('Edits the material of the scattered toys after the scatter: Tint, Subsurface, Roughness Scale override values of the shaders in Arraytron\'s copy of the material. Change them on this node.')
ed.setGenericFlag(hou.nodeFlag.DisplayComment,True)
merge=stage.createNode('merge','merge_all');merge.setInput(0,a);merge.setInput(1,ed);merge.setDisplayFlag(True);merge.setPosition((0,-1))
cam=stage.createNode('camera','camera1');cam.setInput(0,merge);cam.setPosition((0,-2))
for p,v in (('tx',0.0),('ty',19.0),('tz',34.0),('rx',-29.0)):
    cam.parm(p).set(v)
# checks
st=merge.stage();assert not ed.errors(),ed.errors()
def val(root,name,inp):
    for p in st.Traverse():
        if str(p.GetPath()).startswith(root) and p.GetName()==name:
            return UsdShade.Shader(p).GetInput(inp)
mb='/World/ArraytronB/Prototypes/rubbertoy/mtl/ToyShader';ma='/World/ArraytronA/Prototypes/rubbertoy/mtl/ToyShader'
assert tuple(round(x,3) for x in val(mb,'mtlxmultiply1','in2').Get())==(1.0,0.15,0.12)
assert val(mb,'mtlxstandard_surface','subsurface').Get()==0.0 and abs(val(mb,'mtlxmultiply2','in2').Get()-0.6)<1e-6
assert str(val(mb,'mtlxmultiply1','in1').GetConnectedSources()[0][0].source.GetPath()).endswith('mtlximage_color')   # the texture is kept
assert 'toylowres' in str(val(mb,'mtlximage_color','file').Get())
assert val(ma,'mtlxstandard_surface','subsurface').Get()==1.0 and abs(val(ma,'mtlxmultiply1','in2').Get()[1]-0.588)<1e-3          # A unchanged
hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path()}))
