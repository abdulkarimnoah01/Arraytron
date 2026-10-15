# LEGACY (pre-versioning script): writes the OLD file names into dist/. The maintained copies of these releases are in dist/archive/ (see docs/VERSIONING.md). Current builders: build_arraytron_v03.py / build_demo_v03.py.
"""Package Arraytron v0.16 (Line By Spacing, Keep Inside Area), v0.2 (adds Grid / Matrix) or v0.21 (adds Scale Instances).
Usage: hython tools/build_arraytron_v016.py [v016|v02|v021]"""
from pathlib import Path
import argparse, json, re, hou
from pxr import UsdGeom
ROOT=Path(__file__).resolve().parents[1]
VERSIONS={'v016':dict(type='arraytron::instancer::0.16',hda='Arraytron_v0.16.hda',label='0.16',grid=False,scaleinst=False,vex='vex_v016',guide='guide_bounds_v016.py'),
          # Houdini compares type versions component-wise as numbers: 0.2 would sort below 0.16, so v0.2 is type 0.20.
          'v02':dict(type='arraytron::instancer::0.20',hda='Arraytron_v0.2.hda',label='0.2',grid=True,scaleinst=False,vex='vex_v016',guide='guide_bounds_v016.py'),
          'v021':dict(type='arraytron::instancer::0.21',hda='Arraytron_v0.21.hda',label='0.21',grid=True,scaleinst=True,vex='vex_v021',guide='guide_bounds_v021.py')}

def picker_tags():
    """Reuse the stock single-prim picker so Prototype/Output get the viewport select button."""
    template=[t for t in hou.nodeType(hou.lopNodeTypeCategory(),'createxform').parmTemplates() if t.name()=='primpath'][0]
    return dict(template.tags())

def hscript_default(template,expressions):
    template.setDefaultExpression(tuple(expressions))
    template.setDefaultExpressionLanguage(tuple(hou.scriptLanguage.Hscript for _ in expressions))
    return template

def parms(grid=False,scaleinst=False):
    g=hou.ParmTemplateGroup()
    def f(name,label,default,minimum=0,maximum=10,strict=False,help=''):
        return hou.FloatParmTemplate(name,label,1,default_value=(default,),min=minimum,max=maximum,min_is_strict=strict,help=help)
    def i(name,label,default,minimum=1,maximum=10000,help=''):
        return hou.IntParmTemplate(name,label,1,default_value=(default,),min=minimum,max=maximum,min_is_strict=True,help=help)
    def v(name,label,default=(0,0,0),minimum=-10,maximum=10,help=''):
        return hou.FloatParmTemplate(name,label,3,default_value=default,min=minimum,max=maximum,help=help)
    def section(name,label,ps):
        g.append(hou.FolderParmTemplate(name,label,parm_templates=ps,folder_type=hou.folderType.Simple))
    def menu(name,label,items,**kw):
        # Numeric tokens: folder conditionals such as { mode != 0 } compare against these.
        # String tokens ('line','area') made every conditional evaluate true, hiding both folders.
        return hou.MenuParmTemplate(name,label,tuple(str(n) for n in range(len(items))),tuple(items),**kw)
    def readonly(template,condition='{ mode >= 0 }',hide=None):
        template.setConditional(hou.parmCondType.DisableWhen,condition)
        if hide:template.setConditional(hou.parmCondType.HideWhen,hide)
        return template
    tags=picker_tags()
    prototype=hou.StringParmTemplate('prototype','Prototype Prim',1,default_value=('/World/Props/Crate',),tags=tags,help='One exact prim path in the incoming Solaris stream. Its transform is preserved; author an origin-centered prototype when desired.')
    output=hou.StringParmTemplate('outputpath','Output Prim Path',1,default_value=('/World/Arraytron',),tags=tags,help='Absolute USD prim path outside the source prototype hierarchy.')
    section('source','Source',(prototype,output))
    section('distribution','Distribution',(menu('mode','Distribution Mode',('Line','Area','Grid / Matrix') if grid else ('Line','Area')),))

    # ---- Line
    direction=v('line_direction','Direction (local)',(1,0,0),-1,1,'Line direction in the distribution local space, used when Direction Mode is Custom. Only its direction matters (it is normalized; its length does not change the Line length). A zero vector falls back to +X. Bounds Rotation is applied afterwards and turns the whole line.')
    direction.setConditional(hou.parmCondType.HideWhen,'{ line_axis != 3 }')
    count=i('line_count','Count',10,help='Number of points along the Line (By Count).')
    count.setConditional(hou.parmCondType.HideWhen,'{ line_spacemode != 0 }')
    spacing=f('line_spacing','Spacing',1,0.001,10,True,'Distance between neighbouring points (By Spacing). The Line gets floor(Length / Spacing) + 1 points, at most 10000.')
    spacing.setConditional(hou.parmCondType.HideWhen,'{ line_spacemode != 1 }')
    spacing_out=hscript_default(f('line_spacing_out','Spacing (local)',0,help='Read only. Distance between neighbouring points before Bounds Scale: Length / (Count - 1), 0 for a single point.'),
        ['if(ch("line_count") > 1, ch("line_length") / (ch("line_count") - 1), 0)'])
    readonly(spacing_out,hide='{ line_spacemode != 0 }')
    count_out=hscript_default(hou.IntParmTemplate('line_count_out','Resulting Count',1,default_value=(11,),help='Read only. Number of points produced by Length and Spacing.'),
        ['min(10000, floor(max(0, ch("line_length")) / max(0.001, ch("line_spacing")) + 0.000001) + 1)'])
    readonly(count_out,hide='{ line_spacemode != 1 }')
    span_out=hscript_default(f('line_span_out','Occupied Length',0,help='Read only. Distance from the first to the last point. It can be shorter than Length because the last whole Spacing step must fit inside it.'),
        ['(ch("line_count_out") - 1) * max(0.001, ch("line_spacing"))'])
    readonly(span_out,hide='{ line_spacemode != 1 }')
    line=hou.FolderParmTemplate('line','Line',folder_type=hou.folderType.Simple,parm_templates=(
        menu('line_axis','Direction Mode',('X','Y','Z','Custom')),
        direction,
        menu('line_spacemode','Spacing Mode',('By Count','By Spacing'),help='By Count: you set the number of points and they span the Length. By Spacing: you set the distance between points and the count follows from the Length.'),
        count,f('line_length','Length',10,0,50,True),spacing,
        hou.ToggleParmTemplate('line_center','Center',default_value=True,help='Center the points on the local origin. A single point sits at the origin.'),
        spacing_out,count_out,span_out))
    line.setConditional(hou.parmCondType.HideWhen,'{ mode != 0 }');g.append(line)

    # ---- Area
    area=hou.FolderParmTemplate('area','Area',folder_type=hou.folderType.Simple,parm_templates=(
        f('area_sizex','Size X',10,0,50,True),f('area_sizez','Size Z',10,0,50,True),
        i('area_count','Count',100),i('area_seed','Seed',1,0)))
    area.setConditional(hou.parmCondType.HideWhen,'{ mode != 1 }');g.append(area)

    # ---- Grid
    if grid:
        gcount=hou.IntParmTemplate('grid_count','Count',3,default_value=(5,1,5),min=1,max=100,min_is_strict=True,help='Points along X, Y and Z (By Count), 1 to 100 each. A count of 1 on an axis flattens the grid on that axis; raise Y for a 3D matrix.')
        gcount.setConditional(hou.parmCondType.HideWhen,'{ grid_spacemode != 0 }')
        gsize=v('grid_size','Size (point span)',(10,10,10),0,50,'Distance from the first to the last point CENTER on each axis, not the outer edge of the instances. Ignored on an axis whose count is 1 (the value is kept for when you raise that count). Size 0 with several points stacks them.')
        gspacing=hou.FloatParmTemplate('grid_spacing','Spacing',3,default_value=(2,2,2),min=.001,max=10,min_is_strict=True,help='Distance between neighbouring points on each axis (By Spacing). Each axis gets floor(Size / Spacing) + 1 points, at most 100.')
        gspacing.setConditional(hou.parmCondType.HideWhen,'{ grid_spacemode != 1 }')
        gspacing_out=hscript_default(hou.FloatParmTemplate('grid_spacing_out','Spacing (local)',3,default_value=(0,0,0),help='Read only. Distance between neighbouring points before Bounds Scale: Size / (Count - 1) per axis, 0 where the count is 1.'),
            [f'if(ch("grid_count{a}") > 1, ch("grid_size{a}") / (ch("grid_count{a}") - 1), 0)' for a in 'xyz'])
        readonly(gspacing_out,hide='{ grid_spacemode != 0 }')
        gcount_out=hscript_default(hou.IntParmTemplate('grid_count_out','Resulting Count',3,default_value=(6,6,6),help='Read only. Points per axis produced by Size and Spacing.'),
            [f'min(100, floor(ch("grid_size{a}") / max(0.001, ch("grid_spacing{a}")) + 0.000001) + 1)' for a in 'xyz'])
        readonly(gcount_out,hide='{ grid_spacemode != 1 }')
        gspan_out=hscript_default(hou.FloatParmTemplate('grid_span_out','Occupied Size',3,default_value=(10,10,10),help='Read only. Distance from the first to the last point on each axis. It can be shorter than Size because the last whole Spacing step must fit inside it.'),
            [f'(ch("grid_count_out{a}") - 1) * max(0.001, ch("grid_spacing{a}"))' for a in 'xyz'])
        readonly(gspan_out,hide='{ grid_spacemode != 1 }')
        warn=hou.LabelParmTemplate('grid_warn','',column_labels=('More than 100,000 instances: cooks and the viewport may be slow.',))
        warn.setConditional(hou.parmCondType.HideWhen,'{ grid_total < 100000 }')
        total=hscript_default(hou.IntParmTemplate('grid_total','Total Points',1,default_value=(25,),help='Read only. Number of instances the Grid produces. Ids run X fastest (id = i + nx*(j + ny*k)), so changing the X or Y count renumbers existing points; adding layers along Z keeps them.'),
            ['if(ch("grid_spacemode") == 1, ch("grid_count_outx") * ch("grid_count_outy") * ch("grid_count_outz"), ch("grid_countx") * ch("grid_county") * ch("grid_countz"))'])
        readonly(total)
        grid_folder=hou.FolderParmTemplate('grid','Grid',folder_type=hou.folderType.Simple,parm_templates=(
            menu('grid_spacemode','Spacing Mode',('By Count','By Spacing'),help='By Count: set points per axis; they span Size. By Spacing: set the distance between points; counts follow from Size.'),
            gcount,gsize,gspacing,
            hou.ToggleParmTemplate('grid_center','Center',default_value=True,help='Center the points on the local origin. Off: the first point sits at the origin and the grid extends along +X, +Y, +Z.'),
            gspacing_out,gcount_out,gspan_out,total,warn))
        grid_folder.setConditional(hou.parmCondType.HideWhen,'{ mode != 2 }');g.append(grid_folder)

    # ---- Bounds Transform
    guide=hou.ToggleParmTemplate('show_bounds','Show Bounds Guide',default_value=True,help='Draw the bounds and the pivot as viewport-only guide curves. They do not render in Karma.')
    reset=hou.ButtonParmTemplate('reset_bounds','Reset Bounds Transform',help='Return Position, Rotation, Scale and Pivot to their defaults.')
    reset.setScriptCallback("n=kwargs['node']\nfor name in ('bound_t','bound_r','bound_s','bound_p'):\n    n.parmTuple(name).revertToDefaults()")
    reset.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    if scaleinst:
        scale_help='Positive XYZ scale of the whole layout, applied before Rotation. It stretches the bounds and the spacing. Whether the instances stretch too is set by Scale Instances. Use Instance Transform > Scale to resize only the crates.'
        scale_toggle=(hou.ToggleParmTemplate('bound_scale_instances','Scale Instances',default_value=False,help='Off (default): Scale moves the instances apart or together but they keep their own size and shape, so a non-uniform Scale cannot stretch the crates by accident. On: Scale also stretches every instance, as if the whole array were one scaled object.'),)
    else:
        scale_help='Positive XYZ scale of the whole distribution: it stretches the bounds, the spacing AND the instance geometry, and is applied before Rotation. Use Instance Transform > Scale to resize only the crates.'
        scale_toggle=()
    section('bounds','Bounds Transform',(
        v('bound_t','Position',help='World translation of the whole distribution and its instances. Also driven by the viewport handle.'),
        v('bound_r','Rotation (deg)',minimum=-180,maximum=180,help='XYZ Euler degrees turning the whole distribution and its instances around Pivot. Applied after the local Line Direction.'),
        hou.FloatParmTemplate('bound_s','Scale',3,default_value=(1,1,1),min=.0001,max=5,min_is_strict=True,help=scale_help),
        *scale_toggle,
        v('bound_p','Pivot (local)',help='Pivot in the distribution local space; Rotation and Scale act around it. With no rotation or scale, moving the Pivot moves nothing. With rotation or scale, moving the Pivot moves the layout (as in the Houdini Xform node): adjust Position to compensate.'),
        guide,reset))

    section('transform','Instance Transform',(v('base_rotation','Rotation (deg)',minimum=-180,maximum=180,help='Orientation of each copy before the Bounds Transform.'),f('base_scale','Scale',1,0.0001,10,True)))
    amount=f('scale_random','Scale',0,0,0.99,True);amount.setMaxIsStrict(True)
    amount.setHelp('Fractional variation around Base Scale, from 0 to 0.99. Always positive.')
    jitter=v('position_random','Position',minimum=0,maximum=5,help='Symmetric +/- jitter after distribution. Nonzero Y explicitly moves points off the ground plane.')
    keep=hou.ToggleParmTemplate('area_keepinside','Keep Inside Area',default_value=False,help='Area only. Reflect Position jitter back at the Area rectangle edges so no point leaves the bounds (X and Z; Y jitter is unaffected). Reflecting, not clamping, so points do not pile up on the edge.')
    keep.setConditional(hou.parmCondType.HideWhen,'{ mode != 1 }')
    section('randomize','Randomize',(i('random_seed','Seed',1,0),jitter,keep,v('rotation_random','Rotation (deg)',minimum=0,maximum=180),amount))
    return g

def wrangle(parent,name,filename,run_over,vex):
    n=parent.createNode('attribwrangle',name)
    n.parm('class').set(run_over)
    n.parm('snippet').set((ROOT/'src'/vex/filename).read_text())
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

def build(version='v016'):
    info=VERSIONS[version];grid=info['grid'];scaleinst=info['scaleinst'];vex=info['vex'];hda=ROOT/'dist'/info['hda']
    hou.hipFile.clear(suppress_save_prompt=True)
    stage=hou.node('/stage')
    source=stage.createNode('sopcreate','demo_crate')
    source.parm('pathprefix').set('/World/Props/Crate')
    sop=source.node('sopnet/create')
    for c in sop.children(): c.destroy()
    box=sop.createNode('box','crate');box.parmTuple('size').set((0.55,0.55,0.55))
    out=sop.createNode('output','output0');out.setInput(0,box);out.setDisplayFlag(True)
    asset=stage.createNode('subnet','Arraytron');asset.setInput(0,source)
    asset.setParmTemplateGroup(parms(grid,scaleinst))
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
    generators=[wrangle(inst,'generate_line','line.vfl',0,vex),wrangle(inst,'generate_area','area.vfl',0,vex)]
    if grid:generators.append(wrangle(inst,'generate_grid','grid.vfl',0,vex))
    switch=inst.createNode('switch','distribution_mode')
    for index,generator in enumerate(generators):switch.setInput(index,generator)
    switch.parm('input').setExpression('ch("../../mode")',hou.exprLanguage.Hscript)
    transform=wrangle(inst,'modify_point_transforms','transforms.vfl',2,vex);transform.setInput(0,switch)
    assign=inst.createNode('attribwrangle','assign_prototype');assign.setInput(0,transform)
    assign.parm('class').set(2);assign.parm('snippet').set('i@protoindex = 0;')
    out=inst.createNode('output','OUT_POINTS');out.setInput(0,assign);out.setDisplayFlag(True)
    visibility=asset.createNode('configureprimitive','ensure_prototype_visible')
    visibility.setInput(0,inst)
    visibility.parm('primpattern').setExpression('hou.pwd().parent().evalParm("outputpath") + "/Prototypes/" + hou.pwd().parent().evalParm("prototype").rsplit("/",1)[-1]',hou.exprLanguage.Python)
    visibility.parm('setvisibility').set(1);visibility.parm('visibility').set('inherit')
    guide=asset.createNode('pythonscript','bounds_guide');guide.setInput(0,visibility)
    guide.parm('python').set((ROOT/'src'/info['guide']).read_text())
    layout=asset.createNode('xform','transform_distribution');layout.setInput(0,guide)
    layout.parm('setabsolutexform').set(1);layout.parm('xforminworldspace').set(1)
    layout.parm('primpattern').setExpression('chs("../outputpath")',hou.exprLanguage.Hscript)
    for tuple_name in 'trsp':
        for parm,axis in zip(layout.parmTuple(tuple_name),'xyz'):
            expression=f'ch("../bound_{tuple_name}{axis}")'
            if tuple_name=='s':
                expression=f'max(0.0001, {expression})'
                if scaleinst:expression=f'if(ch("../bound_scale_instances"), {expression}, 1)'
            parm.setExpression(expression,hou.exprLanguage.Hscript)
    out=asset.createNode('output','OUT_ARRAYTRON');out.setInput(0,layout);out.setDisplayFlag(True)
    inst.layoutChildren();asset.layoutChildren()
    usd=asset.stage();pi=UsdGeom.PointInstancer(usd.GetPrimAtPath('/World/Arraytron'))
    assert pi and len(pi.GetPositionsAttr().Get(hou.frame()))==10,(asset.errors(),inst.errors(),guide.errors())
    assert usd.GetPrimAtPath('/World/Arraytron/Bounds_Guide/Bounds'),'bounds guide was not authored'
    asset=asset.createDigitalAsset(name=info['type'],hda_file_name=str(hda),description='Arraytron',min_num_inputs=1,max_num_inputs=1)
    definition=asset.type().definition();definition.setParmTemplateGroup(parms(grid,scaleinst))
    modes='Line, Area and Grid' if grid else 'Line and Area'
    definition.addSection('ArraytronVersion',f"{info['label']} {modes}, Bounds Transform")
    definition.addSection('Help',f"<html><body><h1>Arraytron {info['label']}</h1><p>Connect a USD prototype stream, choose its exact prim path, then choose {modes.replace(' and ',', ')}. Move, rotate and scale the whole distribution from the <b>Bounds Transform</b> section or the viewport handle. VEX points feed the Houdini 22 native PointInstancer.</p></body></html>")
    definition.updateFromNode(asset);asset.matchCurrentDefinition()
    bind_viewport_handle(definition)
    print(json.dumps({'hda':str(hda),'type':info['type'],'errors':asset.errors()},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('version',nargs='?',default='v016',choices=sorted(VERSIONS))
    build(parser.parse_args().version)
