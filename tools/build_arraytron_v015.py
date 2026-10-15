# LEGACY (pre-versioning script): writes the OLD file names into dist/. The maintained copies of these releases are in dist/archive/ (see docs/VERSIONING.md). Current builders: build_arraytron_v03.py / build_demo_v03.py.
"""Package Arraytron v0.15: shared Bounds Transform, working Line/Area UI, viewport handle and guide."""
from pathlib import Path
import json, re, hou
from pxr import UsdGeom
ROOT=Path(__file__).resolve().parents[1]
TYPE='arraytron::instancer::0.15'
HDA=ROOT/'dist/Arraytron_v0.15.hda'

def picker_tags():
    """Reuse the stock single-prim picker so Prototype/Output get the viewport select button."""
    template=[t for t in hou.nodeType(hou.lopNodeTypeCategory(),'createxform').parmTemplates() if t.name()=='primpath'][0]
    return dict(template.tags())

def parms():
    g=hou.ParmTemplateGroup()
    def f(name,label,default,minimum=0,maximum=10,strict=False):
        return hou.FloatParmTemplate(name,label,1,default_value=(default,),min=minimum,max=maximum,min_is_strict=strict)
    def i(name,label,default,minimum=1):
        return hou.IntParmTemplate(name,label,1,default_value=(default,),min=minimum,max=10000,min_is_strict=True)
    def v(name,label,default=(0,0,0),minimum=-10,maximum=10,help=''):
        return hou.FloatParmTemplate(name,label,3,default_value=default,min=minimum,max=maximum,help=help)
    def section(name,label,ps):
        g.append(hou.FolderParmTemplate(name,label,parm_templates=ps,folder_type=hou.folderType.Simple))
    def menu(name,label,items,**kw):
        # Numeric tokens: folder conditionals such as { mode != 0 } compare against these.
        # String tokens ('line','area') made every conditional evaluate true, hiding both folders.
        return hou.MenuParmTemplate(name,label,tuple(str(n) for n in range(len(items))),tuple(items),**kw)
    tags=picker_tags()
    prototype=hou.StringParmTemplate('prototype','Prototype Prim',1,default_value=('/World/Props/Crate',),tags=tags,help='One exact prim path in the incoming Solaris stream. Its transform is preserved; author an origin-centered prototype when desired.')
    output=hou.StringParmTemplate('outputpath','Output Prim Path',1,default_value=('/World/Arraytron',),tags=tags,help='Absolute USD prim path outside the source prototype hierarchy.')
    section('source','Source',(prototype,output))
    section('distribution','Distribution',(menu('mode','Distribution Mode',('Line','Area')),))

    direction=v('line_direction','Direction (local)',(1,0,0),-1,1,'Line direction in the distribution local space, used when Direction Mode is Custom. Only its direction matters (it is normalized; its length does not change the Line length). A zero vector falls back to +X. Bounds Rotation is applied afterwards and turns the whole line.')
    direction.setConditional(hou.parmCondType.HideWhen,'{ line_axis != 3 }')
    spacing=hou.FloatParmTemplate('line_spacing','Spacing (local)',1,default_value=(0,),help='Read only. Distance between neighbouring points before Bounds Scale: Length / (Count - 1), 0 for a single point.')
    spacing.setDefaultExpression(('if(ch("line_count") > 1, ch("line_length") / (ch("line_count") - 1), 0)',))
    spacing.setDefaultExpressionLanguage((hou.scriptLanguage.Hscript,))
    spacing.setConditional(hou.parmCondType.DisableWhen,'{ line_count > 0 }')
    line=hou.FolderParmTemplate('line','Line',folder_type=hou.folderType.Simple,parm_templates=(
        menu('line_axis','Direction Mode',('X','Y','Z','Custom')),
        direction,
        i('line_count','Count',10),f('line_length','Length',10,0,50,True),
        hou.ToggleParmTemplate('line_center','Center',default_value=True,help='Center the line on the local origin. A single point sits at the origin.'),
        spacing))
    line.setConditional(hou.parmCondType.HideWhen,'{ mode != 0 }');g.append(line)
    area=hou.FolderParmTemplate('area','Area',folder_type=hou.folderType.Simple,parm_templates=(
        f('area_sizex','Size X',10,0,50,True),f('area_sizez','Size Z',10,0,50,True),
        i('area_count','Count',100),i('area_seed','Seed',1,0)))
    area.setConditional(hou.parmCondType.HideWhen,'{ mode != 1 }');g.append(area)

    guide=hou.ToggleParmTemplate('show_bounds','Show Bounds Guide',default_value=True,help='Draw the Line/Area bounds and the pivot as viewport-only guide curves. They do not render in Karma.')
    reset=hou.ButtonParmTemplate('reset_bounds','Reset Bounds Transform',help='Return Position, Rotation, Scale and Pivot to their defaults.')
    reset.setScriptCallback("n=kwargs['node']\nfor name in ('bound_t','bound_r','bound_s','bound_p'):\n    n.parmTuple(name).revertToDefaults()")
    reset.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    section('bounds','Bounds Transform',(
        v('bound_t','Position',help='World translation of the whole Line or Area bounds and its instances. Also driven by the viewport handle.'),
        v('bound_r','Rotation (deg)',minimum=-180,maximum=180,help='XYZ Euler degrees turning the whole distribution and its instances around Pivot. Applied after the local Line Direction.'),
        hou.FloatParmTemplate('bound_s','Scale',3,default_value=(1,1,1),min=.0001,max=5,min_is_strict=True,help='Positive XYZ scale of the whole distribution: it stretches the bounds, the spacing AND the instance geometry, and is applied before Rotation. Use Instance Transform > Scale to resize only the crates.'),
        v('bound_p','Pivot (local)',help='Pivot in the distribution local space; Rotation and Scale act around it. With no rotation or scale, moving the Pivot moves nothing. With rotation or scale, moving the Pivot moves the layout (as in the Houdini Xform node): adjust Position to compensate.'),
        guide,reset))

    section('transform','Instance Transform',(v('base_rotation','Rotation (deg)',minimum=-180,maximum=180,help='Orientation of each copy before the Bounds Transform.'),f('base_scale','Scale',1,0.0001,10,True)))
    amount=f('scale_random','Scale',0,0,0.99,True);amount.setMaxIsStrict(True)
    amount.setHelp('Fractional variation around Base Scale, from 0 to 0.99. Always positive.')
    jitter=v('position_random','Position',minimum=0,maximum=5,help='Symmetric +/- jitter after distribution. Nonzero Y explicitly moves points off the ground plane.')
    section('randomize','Randomize',(i('random_seed','Seed',1,0),jitter,v('rotation_random','Rotation (deg)',minimum=0,maximum=180),amount))
    return g

def wrangle(parent,name,filename,run_over):
    n=parent.createNode('attribwrangle',name)
    n.parm('class').set(run_over)
    n.parm('snippet').set((ROOT/'src/vex'/filename).read_text())
    return n

HANDLE_BINDINGS=(('bound_t','t'),('bound_r','r'),('bound_s','s'),('bound_p','p'))
def bind_viewport_handle(definition):
    """Bind the stock LOP transform gizmo to the Bounds Transform parameters (DialogScript bindhandle)."""
    section=definition.sections()['DialogScript']
    text=re.sub(r'^\s*bindhandle .*\n','',section.contents(),flags=re.M)
    lines=''.join(f'    bindhandle {parm}{axis} lopxform "Transformer" {handle}{axis} ""\n'
                  for parm,handle in HANDLE_BINDINGS for axis in 'xyz')
    first=re.search(r'^    (group|groupsimple|parm)\b',text,re.M)
    assert first,'DialogScript layout changed'
    section.setContents(text[:first.start()]+lines+'\n'+text[first.start():])

def build():
    hou.hipFile.clear(suppress_save_prompt=True)
    stage=hou.node('/stage')
    source=stage.createNode('sopcreate','demo_crate')
    source.parm('pathprefix').set('/World/Props/Crate')
    sop=source.node('sopnet/create')
    for c in sop.children(): c.destroy()
    box=sop.createNode('box','crate');box.parmTuple('size').set((0.55,0.55,0.55))
    out=sop.createNode('output','output0');out.setInput(0,box);out.setDisplayFlag(True)
    asset=stage.createNode('subnet','Arraytron');asset.setInput(0,source)
    asset.setParmTemplateGroup(parms())
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
    area=wrangle(inst,'generate_area','area.vfl',0)
    switch=inst.createNode('switch','distribution_mode');switch.setInput(0,line);switch.setInput(1,area)
    switch.parm('input').setExpression('ch("../../mode")',hou.exprLanguage.Hscript)
    transform=wrangle(inst,'modify_point_transforms','transforms.vfl',2);transform.setInput(0,switch)
    assign=inst.createNode('attribwrangle','assign_prototype');assign.setInput(0,transform)
    assign.parm('class').set(2);assign.parm('snippet').set('i@protoindex = 0;')
    out=inst.createNode('output','OUT_POINTS');out.setInput(0,assign);out.setDisplayFlag(True)
    visibility=asset.createNode('configureprimitive','ensure_prototype_visible')
    visibility.setInput(0,inst)
    visibility.parm('primpattern').setExpression('hou.pwd().parent().evalParm("outputpath") + "/Prototypes/" + hou.pwd().parent().evalParm("prototype").rsplit("/",1)[-1]',hou.exprLanguage.Python)
    visibility.parm('setvisibility').set(1);visibility.parm('visibility').set('inherit')
    guide=asset.createNode('pythonscript','bounds_guide');guide.setInput(0,visibility)
    guide.parm('python').set((ROOT/'src/guide_bounds.py').read_text())
    layout=asset.createNode('xform','transform_distribution');layout.setInput(0,guide)
    layout.parm('setabsolutexform').set(1);layout.parm('xforminworldspace').set(1)
    layout.parm('primpattern').setExpression('chs("../outputpath")',hou.exprLanguage.Hscript)
    for tuple_name,suffix in (('t','t'),('r','r'),('s','s'),('p','p')):
        for parm,axis in zip(layout.parmTuple(tuple_name),'xyz'):
            expression=f'ch("../bound_{suffix}{axis}")'
            if tuple_name=='s':expression=f'max(0.0001, {expression})'
            parm.setExpression(expression,hou.exprLanguage.Hscript)
    out=asset.createNode('output','OUT_ARRAYTRON');out.setInput(0,layout);out.setDisplayFlag(True)
    inst.layoutChildren();asset.layoutChildren()
    usd=asset.stage();pi=UsdGeom.PointInstancer(usd.GetPrimAtPath('/World/Arraytron'))
    assert pi and len(pi.GetPositionsAttr().Get(hou.frame()))==10,(asset.errors(),inst.errors(),guide.errors())
    assert usd.GetPrimAtPath('/World/Arraytron/Bounds_Guide/Bounds'),'bounds guide was not authored'
    asset=asset.createDigitalAsset(name=TYPE,hda_file_name=str(HDA),description='Arraytron',min_num_inputs=1,max_num_inputs=1)
    definition=asset.type().definition();definition.setParmTemplateGroup(parms())
    definition.addSection('ArraytronVersion','0.15 Line + Area, Bounds Transform')
    definition.addSection('Help','<html><body><h1>Arraytron 0.15</h1><p>Connect a USD prototype stream, choose its exact prim path, then choose Line or Area. Move, rotate and scale the whole Line/Area bounds from the <b>Bounds Transform</b> section or the viewport handle. VEX points feed the Houdini 22 native PointInstancer.</p></body></html>')
    definition.updateFromNode(asset);asset.matchCurrentDefinition()
    bind_viewport_handle(definition)
    print(json.dumps({'hda':str(HDA),'type':TYPE,'errors':asset.errors()},indent=2))

if __name__=='__main__':
    build()
