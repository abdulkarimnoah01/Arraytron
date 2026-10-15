# LEGACY (pre-versioning script): writes the OLD file names into dist/. The maintained copies of these releases are in dist/archive/ (see docs/VERSIONING.md). Current builders: build_arraytron_v03.py / build_demo_v03.py.
"""Package a Solaris HDA; Python builds nodes, VEX generates every point."""
from pathlib import Path
import argparse, json, hou
from pxr import UsdGeom
ROOT=Path(__file__).resolve().parents[1]
TYPE='arraytron::instancer::0.1'

def parms(area=False):
    g=hou.ParmTemplateGroup()
    def f(name,label,default,minimum=0,maximum=10,strict=False):
        return hou.FloatParmTemplate(name,label,1,default_value=(default,),min=minimum,max=maximum,min_is_strict=strict)
    def i(name,label,default,minimum=1):
        return hou.IntParmTemplate(name,label,1,default_value=(default,),min=minimum,max=10000,min_is_strict=True)
    def v(name,label,default=(0,0,0)):
        return hou.FloatParmTemplate(name,label,3,default_value=default)
    def section(name,label,ps):
        g.append(hou.FolderParmTemplate(name,label,parm_templates=ps,folder_type=hou.folderType.Simple))
    section('source','Source',(
        hou.StringParmTemplate('prototype','Prototype Prim',1,default_value=('/World/Props/Crate',),help='One exact prim path in the incoming Solaris stream. Its transform is preserved; author an origin-centered prototype when desired.'),
        hou.StringParmTemplate('outputpath','Output Prim Path',1,default_value=('/World/Arraytron',),help='Absolute USD prim path outside the source prototype hierarchy.'),))
    section('distribution','Distribution',(
        hou.MenuParmTemplate('mode','Distribution Mode',('line','area') if area else ('line',),('Line','Area') if area else ('Line',)),))
    direction=v('line_direction','Direction',(1,0,0))
    direction.setConditional(hou.parmCondType.HideWhen,'{ line_axis != 3 }')
    direction.setHelp('Normalized local-space direction. Select Custom in Direction Mode. A zero vector falls back to +X. Distribution Rotation then turns the whole line.')
    def layout_controls(prefix):
        position=v(prefix+'_offset','Position')
        position.setHelp('World translation of the whole distribution. Existing Offset values are preserved.')
        rotation=v(prefix+'_rotation','Rotation')
        rotation.setHelp('XYZ Euler degrees applied to the entire distribution and its instances, around Pivot.')
        scale=hou.FloatParmTemplate(prefix+'_scale','Scale',3,default_value=(1,1,1),min=.0001,min_is_strict=True)
        scale.setHelp('Positive XYZ scale of the whole distribution and its instances, applied before Rotation.')
        pivot=v(prefix+'_pivot','Pivot')
        pivot.setHelp('Pivot in the distribution local space. Zero rotates/scales around Position. Changing Pivot alone does not move an unrotated, unscaled distribution.')
        return (position,rotation,scale,pivot)
    line=hou.FolderParmTemplate('line','Line',folder_type=hou.folderType.Simple,parm_templates=(
        hou.MenuParmTemplate('line_axis','Direction Mode',('x','y','z','custom'),('X','Y','Z','Custom')),
        direction,
        i('line_count','Count',10),f('line_length','Length',10,strict=True),
        hou.ToggleParmTemplate('line_center','Center',default_value=True,help='Center the endpoints. A single point is at Offset.'),
        *layout_controls('line')))
    line.setConditional(hou.parmCondType.HideWhen,'{ mode != 0 }'); g.append(line)
    if area:
        a=hou.FolderParmTemplate('area','Area',folder_type=hou.folderType.Simple,parm_templates=(
            f('area_sizex','Size X',10,strict=True),f('area_sizez','Size Z',10,strict=True),
            i('area_count','Count',100),i('area_seed','Seed',1,0),*layout_controls('area')))
        a.setConditional(hou.parmCondType.HideWhen,'{ mode != 1 }');g.append(a)
    section('transform','Instance Transform',(v('base_rotation','Rotation'),f('base_scale','Scale',1,0.0001,10,True)))
    amount=f('scale_random','Scale',0,0,0.99,True); amount.setMaxIsStrict(True)
    amount.setHelp('Fractional variation around Base Scale, from 0 to 0.99. Always positive.')
    position=v('position_random','Position');position.setHelp('Symmetric +/- jitter after distribution. Nonzero Y explicitly moves points off the ground plane.')
    section('randomize','Randomize',(i('random_seed','Seed',1,0),position,v('rotation_random','Rotation'),amount))
    return g

def wrangle(parent,name,filename,run_over):
    n=parent.createNode('attribwrangle',name)
    n.parm('class').set(run_over)
    n.parm('snippet').set((ROOT/'src/vex'/filename).read_text())
    return n

def build(area=False):
    hou.hipFile.clear(suppress_save_prompt=True)
    stage=hou.node('/stage')
    source=stage.createNode('sopcreate','demo_crate')
    source.parm('pathprefix').set('/World/Props/Crate')
    sop=source.node('sopnet/create')
    for c in sop.children(): c.destroy()
    box=sop.createNode('box','crate');box.parmTuple('size').set((0.55,0.55,0.55))
    out=sop.createNode('output','output0');out.setInput(0,box);out.setDisplayFlag(True)
    asset=stage.createNode('subnet','Arraytron');asset.setInput(0,source)
    asset.setParmTemplateGroup(parms(area))
    for c in asset.children():c.destroy()
    validate=asset.createNode('pythonscript','validate_source_paths')
    validate.setInput(0,asset.indirectInputs()[0])
    validate.parm('python').set((ROOT/'src/validate_source.py').read_text())
    inst=asset.createNode('pointinstancer','build_pointinstancer')
    inst.setInput(0,validate)
    inst.parm('primpath').setExpression('chs("../outputpath")',hou.exprLanguage.Hscript)
    inst.parm('protosourcemode').set('first')
    inst.parm('protopattern').setExpression('chs("../prototype")',hou.exprLanguage.Hscript)
    inst.parm('createprotoarea').set(1);inst.parm('hideprotosourceprims').set(1)
    inst.parm('protodestrootprim').setExpression('chs("../outputpath") + "/Prototypes"',hou.exprLanguage.Hscript)
    inst.parm('protoreftype').set('prim')
    inst.parm('importsoppoints').set(1);inst.parm('sopsourcemode').set('intsop')
    inst.parm('newprotoindexsrc').set('intattr');inst.parm('newintattr').set('protoindex')
    inst.parm('updateinstancemode').set('overwrite');inst.parm('existingprototypemode').set('overwrite')
    inst.parm('existingprotoindexsrc').set('intattr');inst.parm('existingintattr').set('protoindex')
    inst.parm('attribs').set('')
    for c in inst.children():c.destroy()
    line=wrangle(inst,'generate_line','line.vfl',0)
    generator=line
    if area:
        a=wrangle(inst,'generate_area','area.vfl',0)
        switch=inst.createNode('switch','distribution_mode');switch.setInput(0,line);switch.setInput(1,a)
        switch.parm('input').setExpression('ch("../../mode")',hou.exprLanguage.Hscript)
        generator=switch
    transform=wrangle(inst,'modify_point_transforms','transforms.vfl',2);transform.setInput(0,generator)
    assign=inst.createNode('attribwrangle','assign_prototype');assign.setInput(0,transform)
    assign.parm('class').set(2);assign.parm('snippet').set('i@protoindex = 0;')
    out=inst.createNode('output','OUT_POINTS');out.setInput(0,assign);out.setDisplayFlag(True)
    visibility=asset.createNode('configureprimitive','ensure_prototype_visible')
    visibility.setInput(0,inst)
    visibility.parm('primpattern').setExpression('hou.pwd().parent().evalParm("outputpath") + "/Prototypes/" + hou.pwd().parent().evalParm("prototype").rsplit("/",1)[-1]',hou.exprLanguage.Python)
    visibility.parm('setvisibility').set(1);visibility.parm('visibility').set('inherit')
    layout=asset.createNode('xform','transform_distribution');layout.setInput(0,visibility)
    layout.parm('setabsolutexform').set(1);layout.parm('xforminworldspace').set(1)
    layout.parm('primpattern').setExpression('chs("../outputpath")',hou.exprLanguage.Hscript)
    for tuple_name,suffix in (('t','offset'),('r','rotation'),('s','scale'),('p','pivot')):
        for parm,axis in zip(layout.parmTuple(tuple_name),'xyz'):
            expression=f'if(ch("../mode") == 0, ch("../line_{suffix}{axis}"), ch("../area_{suffix}{axis}"))' if area else f'ch("../line_{suffix}{axis}")'
            if tuple_name=='s':expression=f'max(0.0001, {expression})'
            parm.setExpression(expression,hou.exprLanguage.Hscript)
    out=asset.createNode('output','OUT_ARRAYTRON');out.setInput(0,layout);out.setDisplayFlag(True)
    inst.layoutChildren();asset.layoutChildren()
    # Fail build on a real cook error before packaging.
    usd=asset.stage();pi=UsdGeom.PointInstancer(usd.GetPrimAtPath('/World/Arraytron'))
    assert pi and len(pi.GetPositionsAttr().Get(hou.frame()))==10,(asset.errors(),inst.errors())
    hda=ROOT/'dist/Arraytron_v0.1.hda'
    asset=asset.createDigitalAsset(name=TYPE,hda_file_name=str(hda),description='Arraytron',min_num_inputs=1,max_num_inputs=1)
    definition=asset.type().definition();definition.setParmTemplateGroup(parms(area))
    definition.addSection('ArraytronVersion','0.1 Line + Area' if area else '0.1 Line prototype')
    definition.addSection('Help', '<html><body><h1>Arraytron</h1><p>Connect a USD prototype stream, choose its exact prim path, then choose Line or Area. VEX points feed Houdini 22 native PointInstancer.</p></body></html>')
    definition.updateFromNode(asset);asset.matchCurrentDefinition()
    asset.setDisplayFlag(True)
    camera=stage.createNode('camera','render_camera');camera.setInput(0,asset)
    camera.parm('primpath').set('/World/Camera')
    camera.parm('projection').set('orthographic');camera.parm('horizontalAperture').set(14000)
    camera.parmTuple('aspectratio').set((1000,240))
    camera.parmTuple('t').set((0,0,20))
    dome=stage.createNode('domelight','render_light');dome.setInput(0,camera)
    settings=stage.createNode('karmarendersettings','karma_xpu');settings.setInput(0,dome)
    settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera')
    settings.parm('pathtracedsamples').set(32)
    settings.parm('picture').set(str(ROOT/'renders/line_xpu.exr'))
    renderstage=settings.stage()
    renderstage.Export(str(ROOT/'dist/line_render.usda'))
    stage.layoutChildren();hou.hipFile.save(str(ROOT/'dist/Arraytron_v0.1_demo.hip'))
    print(json.dumps({'hda':str(hda),'hip':hou.hipFile.path(),'errors':asset.errors()},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--area',action='store_true');args=p.parse_args();build(args.area)
