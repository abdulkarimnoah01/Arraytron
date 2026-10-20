"""Package Arraytron v0.3 (Prototype Bank: four source methods, weighted selection, modular processor-stage network) v0.3.5 (adds Circle / Radial),
v0.3.6 (adds the variation extras), v0.4.0 (adds the optional Physics Settle system), v0.4.5 (adds the Curve distribution)
v0.4.6 (adds Surface Scatter) v0.5.0 (adds the Mask pipeline) v0.5.1 (adds No Overlap) or v0.5.2 (adds the Grow animation and the six-tab interface).
Usage: hython tools/build_arraytron_v03.py [v0.3.0|v0.3.5|v0.3.6|v0.4.0|v0.4.5|v0.4.6|v0.5.0|v0.5.1|v0.5.2]   (old tags v03 / v035 still work)
Network (master plan names): LOP side  merge_inputs > sop_stage_1..4 > SOURCE_RESOLVER > USD_COMPILER > ensure_prototype_visible
> bounds_guide > transform_distribution > OUT_ARRAYTRON.  SOP side inside USD_COMPILER  generate_* > DISTRIBUTION_GENERATOR >
VARIATION_PROCESSOR > PROTOTYPE_ASSIGNMENT > OUT_POINTS.  v0.4.0 inserts PHYSICS_WORLD > PHYSICS_SPAWN > PHYSICS_APPLY behind a PHYSICS_SWITCH, and a
sim branch PHYSICS_PROXIES > PHYSICS_SOLVER (rbdbulletsolver) with PHYSICS_COLLIDERS that only cooks while baking."""
from pathlib import Path
import json, re, sys, hou
from pxr import UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_arraytron_v016 as base
import versions
CONFIG={'v0.3.0':dict(vex='vex_v03',guide='guide_bounds_v021.py',circle=False,variation=False),
        'v0.3.5':dict(vex='vex_v035',guide='guide_bounds_v035.py',circle=True,variation=False),
        'v0.3.6':dict(vex='vex_v036',guide='guide_bounds_v035.py',circle=True,variation=True),
        'v0.4.0':dict(vex='vex_v040',guide='guide_bounds_v040.py',circle=True,variation=True,physics=True),
        'v0.4.5':dict(vex='vex_v040',guide='guide_bounds_v045.py',circle=True,variation=True,physics=True,curve=True),
        'v0.4.6':dict(vex='vex_v040',guide='guide_bounds_v045.py',circle=True,variation=True,physics=True,curve=True,surface=True),
        'v0.5.0':dict(vex='vex_v050',guide='guide_bounds_v045.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True),
        'v0.5.1':dict(vex='vex_v050',guide='guide_bounds_v045.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True),
        'v0.5.2':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True),
        'v0.6.0':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True),
        'v0.7.0':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True),
        'v0.8.0':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True),
        'v0.9.0':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True),
        'v1.0.0':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True),
        'v1.1.0':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True),
        'v1.5.0':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True),
        'v1.6.0':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True),     # v1.6.0: the same features with the Paint tool shortcuts; v1.1.0: the same features, plus the Houdini 20.5 / 21 build (H205, chosen by the running Houdini: versions.is_h205())
        'v1.6.1':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True),     # v1.6.1: the same features, the Paint tool no longer switches the Distribution Mode on its own; v1.6.0: the same features with the Paint tool shortcuts; v1.1.0: the same features, plus the Houdini 20.5 / 21 build (H205, chosen by the running Houdini: versions.is_h205())
        'v1.6.2':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True),     # v1.6.2: the same features, the Settle tab is called Physics
        'v1.7.0':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True,pick=True),     # v1.7.0: the same features, plus Pick Instance (click an instance in the viewport to create its override row)
        'v1.8.0':dict(vex='vex_v050',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True,pick=True,lodgen=True),     # v1.8.0: the same features, plus the built-in LOD generator (Optimize tab)
        'v1.9.0':dict(vex='vex_v190',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True,pick=True,lodgen=True,place=True),     # v1.9.0: the same features, plus the Instance Place distribution mode
        'v1.10.0':dict(vex='vex_v190',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True,pick=True,lodgen=True,place=True),     # v1.10.0: the same features, plus Instance Place arrays (copies with steps)
        'v1.11.0':dict(vex='vex_v190',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True,pick=True,lodgen=True,place=True),     # v1.11.0: the same features, plus the Place tool extras (snap, drag, along curve) and the new node name
        'v1.12.0':dict(vex='vex_v190',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True,pick=True,lodgen=True,place=True,falloff=True),     # v1.12.0: the same features, plus Falloff (scale and density towards the edge of the layout)
        'v1.13.0':dict(vex='vex_v190',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True,pick=True,lodgen=True,place=True,falloff=True),     # v1.13.0: the same features, plus the mode-aware Falloff (paint strokes, clusters, 3D grid) and the renamed tabs with an Export tab
        'v1.14.0':dict(vex='vex_v190',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True,pick=True,lodgen=True,place=True,falloff=True,rows=True),     # v1.14.0: the same features, plus Rows for the Line, Circle and Curve modes
        'v1.15.0':dict(vex='vex_v190',guide='guide_bounds_v052.py',circle=True,variation=True,physics=True,curve=True,surface=True,mask=True,overlap=True,grow=True,ui=True,paint=True,fields=True,cluster=True,camera=True,finish=True,imported=True,pick=True,lodgen=True,place=True,falloff=True,rows=True,biome=True)}     # v1.15.0: the same features, plus the Biome distribution mode
H205=False
TYPE=HDA=VEX=GUIDE=CIRCLE=VARIATION=PHYSICS=CURVE=SURFACE=MASK=OVERLAP=GROW=UI=PAINT=FIELDS=CLUSTER=CAMERA=FINISH=IMPORTED=PICK=LODGEN=PLACE=FALLOFF=ROWS=BIOME=LABEL=PHYS_TAB=NEWTABS=None
def configure(version):
    """version: a new id (v0.3.5) or an old tag (v035). Type name and file location come from tools/versions.py."""
    global H205,TYPE,HDA,VEX,GUIDE,CIRCLE,VARIATION,PHYSICS,CURVE,SURFACE,MASK,OVERLAP,GROW,UI,PAINT,FIELDS,CLUSTER,CAMERA,FINISH,IMPORTED,PICK,LODGEN,PLACE,FALLOFF,ROWS,BIOME,LABEL,PHYS_TAB,NEWTABS
    vid=versions.resolve(version);c=CONFIG[vid];H205=versions.is_h205() and bool(versions.VERSIONS[vid].get('h205'))
    TYPE=versions.type_name(vid);HDA=versions.hda(vid);VEX=ROOT/'src'/c['vex'];GUIDE=c['guide'];CIRCLE=c['circle'];VARIATION=c['variation'];PHYSICS=c.get('physics',False);CURVE=c.get('curve',False);SURFACE=c.get('surface',False);MASK=c.get('mask',False);OVERLAP=c.get('overlap',False);GROW=c.get('grow',False);UI=c.get('ui',False);PAINT=c.get('paint',False);FIELDS=c.get('fields',False);CLUSTER=c.get('cluster',False);CAMERA=c.get('camera',False);FINISH=c.get('finish',False);IMPORTED=c.get('imported',False);PICK=c.get('pick',False);LODGEN=c.get('lodgen',False);PLACE=c.get('place',False);FALLOFF=c.get('falloff',False);ROWS=c.get('rows',False);BIOME=c.get('biome',False);LABEL=vid
    NEWTABS=tuple(int(x) for x in vid[1:].split('.'))>=(1,13,0)                                                      # v1.13.0: Prototypes, Variation, Debugging and an Export tab
    PHYS_TAB='Physics' if tuple(int(x) for x in vid[1:].split('.'))>=(1,6,2) else 'Settle'                  # v1.6.2: the Settle tab is called Physics
    HDA.parent.mkdir(parents=True,exist_ok=True)
configure(versions.CURRENT)
FIELD_TYPE_LABELS=('Height','Slope','Noise','Image','Distance','Exclusion')
INPUT_LABELS=('Scene Stream: terrain, curve, models','Input 2: extra prototype (optional)','Input 3: extra prototype (optional)','Input 4: extra prototype (optional)')
SOP_SLOTS=4

def source_folder():
    tags=base.picker_tags()
    output=hou.StringParmTemplate('outputpath','Output Prim Path',1,default_value=('/World/Arraytron',),tags=tags,help='Absolute USD prim path outside every prototype hierarchy.')
    def t(template,**kw):
        if 'hide' in kw:template.setConditional(hou.parmCondType.HideWhen,kw['hide'])
        if 'disable' in kw:template.setConditional(hou.parmCondType.DisableWhen,kw['disable'])    # greyed out in Random and Cycle: they ignore weights
        return template
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    entry=(
        hou.ToggleParmTemplate('proto_on#','Enable',default_value=True,help='Disabled entries are ignored: they are not instanced and not counted in the selection.'),
        menu('proto_type#','Source Type',('Prim Path','Input Connection','USD File','SOP Geometry'),help='Where this prototype comes from. Prim Path: a prim path in the incoming stream, which also contains everything wired into Prototype Inputs 2-4 (they are merged in). Input Connection: wire any LOP (a Reference, a SOP Create, ...) into Prototype Input 2/3/4. USD File: a USD file on disk. SOP Geometry: a SOP network anywhere in the scene.'),
        t(hou.StringParmTemplate('proto_prim#','Prim Path',1,default_value=('/World/Props/Crate',),tags=tags,help='One exact prim in the incoming stream (the main input, or anything merged in from Prototype Inputs). Its own transform is kept; the transform of its parents is not.'),hide='{ proto_type# != 0 }'),
        t(menu('proto_input#','Input',('Input 2','Input 3','Input 4'),help='Which Prototype Input to take the prototype from.'),hide='{ proto_type# != 1 }'),
        t(hou.StringParmTemplate('proto_inprim#','Prim Path (optional)',1,default_value=('',),tags=tags,help='Leave empty to pick the prim automatically: the only top-level prim, followed down single-child chains to the first component or geometry. Type a path when the input holds several things.'),hide='{ proto_type# != 1 }'),
        t(hou.StringParmTemplate('proto_file#','USD File',1,default_value=('',),string_type=hou.stringParmType.FileReference,tags={'filechooser_pattern':'*.usd,*.usda,*.usdc,*.usdz','filechooser_mode':'read'},help='USD file to reference as the prototype. It is staged as a hidden reference next to the output prim.'),hide='{ proto_type# != 2 }'),
        t(hou.StringParmTemplate('proto_fileprim#','Prim Path (optional)',1,default_value=('',),help='Prim inside the file. Empty uses the file default prim.'),hide='{ proto_type# != 2 }'),
        t(hou.StringParmTemplate('proto_sop#','SOP Path',1,default_value=('',),string_type=hou.stringParmType.NodeReference,tags={'opfilter':'!!SOP!!','oprelative':'/'},help='A SOP node whose geometry becomes the prototype (for example /obj/geo1/OUT). Up to 4 SOP Geometry entries per Arraytron.'),hide='{ proto_type# != 3 }'),
        t(hou.FloatParmTemplate('proto_weight#','Weight',1,default_value=(1,),min=0,max=10,min_is_strict=True,help='Relative weight; any positive numbers work (1 and 2 mean the same as 10 and 20). Weighted Random: the chance of being picked. Sequential: the size of this prototype block in id order. 0 never selects it. Random and Cycle ignore weights. If every weight is 0 the choice is uniform.'),disable='{ proto_mode == 0 } { proto_mode == 3 }'),
        hou.FloatParmTemplate('proto_scale#','Scale',1,default_value=(1,),min=0.0001,max=10,min_is_strict=True,help='Size multiplier for this prototype only, on top of Instance Transform > Scale.'),
        hou.FloatParmTemplate('proto_scalevar#','Scale Random',1,default_value=(0,),min=0,max=0.99,min_is_strict=True,max_is_strict=True,help='Extra random size variation for this prototype only, as a fraction: scale x (1 +/- amount).'),
        hou.FloatParmTemplate('proto_rot#','Rotation Offset (deg)',3,default_value=(0,0,0),min=-180,max=180,help='Turns this prototype itself (XYZ Euler degrees) FIRST, before Instance Transform > Rotation, Randomize and any Facing (Circle). Use it to correct a model authored facing the wrong way: a +X-authored model on the ground plane needs (0, -90, 0) to face along +Z.'))
    if CAMERA:
        entry=tuple(entry)+(
            hou.StringParmTemplate('proto_lod1#','LOD 1 Prim',1,default_value=('',),tags=tags,help='Optional lighter version of this prototype (a prim in the stream, like Prim Path). Used by the Camera section\'s LOD when an instance is farther than the LOD 1 distance (or smaller than the LOD 1 screen size).'),
            hou.StringParmTemplate('proto_lod2#','LOD 2 Prim',1,default_value=('',),tags=tags,help='Optional lighter version still, used beyond the LOD 2 distance.'),
            hou.StringParmTemplate('proto_proxy#','Proxy Prim',1,default_value=('',),tags=tags,help='Optional proxy (a box, a card ...), used beyond the Proxy distance. A missing level falls back to the next finer one that is defined.'))
    bank=hou.FolderParmTemplate('protos','Prototype Bank',folder_type=hou.folderType.MultiparmBlock,default_value=1,parm_templates=entry)
    mode=menu('proto_mode','Selection Mode',('Random','Weighted Random','Sequential','Cycle')+(('Even Percent',) if IMPORTED else ()),default_value=1,help='How each point picks a prototype. Random: uniform. Weighted Random: by Weight. Sequential: the points in id order, in blocks sized by Weight. Cycle: round robin in id order. Random draws are keyed on the stable point id, so changing a weight only moves the points that cross a boundary.')
    seed=hou.IntParmTemplate('proto_seed','Selection Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the prototype selection (and of the per-prototype scale random).')
    summary=hou.StringParmTemplate('proto_summary','Resolved Prototypes',1,default_value=('',),tags={'editor':'1','editorlines':'3-8'},help='Read only. The prim each enabled row resolved to, in selection order, with the Prototype Input it came from. An enabled row that cannot be resolved stops the cook with a row-numbered error, here and on the node; disable the row to skip it. Two prototypes with the same prim name are renamed by Houdini (Rock, Rock2) in bank order.')
    summary.setDefaultExpression(('hou.pwd().hdaModule().summary(hou.pwd())',))
    summary.setDefaultExpressionLanguage((hou.scriptLanguage.Python,))
    summary.setConditional(hou.parmCondType.DisableWhen,'{ protos >= 0 }')
    templates=[output,bank,mode,seed,summary]
    if IMPORTED:
        percent=hou.StringParmTemplate('proto_percent','Share Of The Points',1,default_value=('',),help='Read only. The share of the points each enabled prototype gets: its weight divided by the sum of the weights for Weighted Random and Even Percent, equal shares for Random and Cycle. Even Percent keeps the counts almost exactly on these percentages for any set of ids.')
        percent.setDefaultExpression(('hou.pwd().hdaModule().percent_text(hou.pwd())',));percent.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));percent.setConditional(hou.parmCondType.DisableWhen,'{ protos >= 0 }');templates.insert(3,percent)
    return hou.FolderParmTemplate('source','Source',folder_type=hou.folderType.Simple,parm_templates=tuple(templates))

def circle_folder():
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def readonly(template,expression):
        template.setDefaultExpression((expression,));template.setDefaultExpressionLanguage((hou.scriptLanguage.Hscript,))
        template.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }');return template
    step=readonly(hou.FloatParmTemplate('circle_step_out','Angle Step (deg)',1,default_value=(30,),help='Read only. Angle between neighbouring points: 360 / Count on a full circle (Count intervals), Arc / (Count - 1) on a partial arc (Count - 1 intervals). 0 for a single point.'),
        'if(ch("circle_count") < 2, 0, if(ch("circle_arc") >= 359.9999, 360 / ch("circle_count"), ch("circle_arc") / (ch("circle_count") - 1)))')
    spacing=readonly(hou.FloatParmTemplate('circle_spacing_out','Spacing (local)',1,default_value=(2.618,),help='Read only. Arc distance between neighbouring point centres before Bounds Scale: Radius x Angle Step in radians. It is not the gap between instances: that also depends on the prototype size.'),
        'ch("circle_radius") * rad(ch("circle_step_out"))')
    return hou.FolderParmTemplate('circle','Circle',folder_type=hou.folderType.Simple,parm_templates=(
        menu('circle_plane','Plane',('XZ (ground)','XY','YZ'),help='The plane the circle lies in: XZ is the ground (normal +Y), XY a wall facing +Z, YZ a wall facing +X. Angles run counter-clockwise looking down the normal and start at +X on XZ and XY (3 o\'clock on a wall: use Start Angle 90 for the top) and at +Y on YZ.'),
        hou.FloatParmTemplate('circle_radius','Radius',1,default_value=(5,),min=0,max=50,min_is_strict=True,help='Circle radius in the local space; 0 stacks every point at the centre.'),
        hou.IntParmTemplate('circle_count','Count',1,default_value=(12,),min=1,max=10000,min_is_strict=True,help='Number of points. A full circle (Arc 360) spaces them evenly with Count intervals and does not repeat the first point; a partial arc puts the first point at Start and the last at Start + Arc, with Count - 1 intervals, so spacing jumps when Arc drops just below 360. Count 1 sits at the Start angle.'),
        hou.FloatParmTemplate('circle_arc','Arc (deg)',1,default_value=(360,),min=0,max=360,min_is_strict=True,max_is_strict=True,help='Angular extent: 360 is the full circle, less is an arc. 0 stacks the points at the Start angle.'),
        hou.FloatParmTemplate('circle_start','Start Angle (deg)',1,default_value=(0,),min=-360,max=360,help='Angle of the first point.'),
        menu('circle_facing','Facing',('None','Outward','Center','Tangent'),help='Turns each instance about the plane normal so its forward axis points Outward from the centre, towards the Center, or along the Tangent (counter-clockwise). Forward is +Z on the ground (XZ) plane, +X on XY, +Y on YZ. None keeps the prototype orientation. Order of rotations on each instance: the prototype Rotation Offset first, then Instance Transform > Rotation and Randomize, then Facing last. A prototype authored facing +X on the ground plane needs a Prototype Bank Rotation Offset of (0, -90, 0). With Radius 0 the facing still follows each point angle.'),
        step,spacing))

def curve_folder():
    """Curve distribution (v0.4.5): points along BasisCurves read from the incoming stage."""
    tags=base.picker_tags()
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    info=hou.StringParmTemplate('curve_info','Curve',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. How many curves were found, their total length and the number of points each gets.')
    info.setDefaultExpression(('hou.pwd().hdaModule().curve_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    return hou.FolderParmTemplate('curve','Curve',folder_type=hou.folderType.Simple,parm_templates=(
        hou.StringParmTemplate('curve_prim','Curve Prim',1,default_value=('/World/Curve',),tags=tags,help='A prim in the incoming stream: a BasisCurves prim, or any prim whose subtree holds BasisCurves (linear, or cubic bezier / bspline / catmullRom; nonperiodic, periodic or pinned). The curves are used at their world transform, so the points land where the curve is drawn; leave the Bounds Transform at its defaults to keep them there. NurbsCurves are not supported.'),
        hou.IntParmTemplate('curve_index','Curve Index',1,default_value=(-1,),min=-1,max=10000,min_is_strict=False,help='-1 uses every curve found under the prim; 0, 1, ... picks one curve (in stage traversal order, then in the order they are stored inside a BasisCurves prim).'),
        menu('curve_spacemode','Placement',('By Count','By Spacing','Random'),help='By Count: Count points per curve, evenly by arc length, the end points included (a closed curve does not repeat its start). By Spacing: a point every Spacing units from the start of each curve. Random: Count points per curve at random positions keyed on the stable point id and Seed.'),
        hide(hou.IntParmTemplate('curve_count','Count (per curve)',1,default_value=(10,),min=1,max=10000,min_is_strict=True,help='Number of points on each curve. The total is capped at 10000.'),'{ curve_spacemode == 1 }'),
        hide(hou.FloatParmTemplate('curve_spacing','Spacing',1,default_value=(1.0,),min=0.001,max=100,min_is_strict=True,help='Distance between neighbouring points along each curve (floor(Length / Spacing) + 1 points on an open curve).'),'{ curve_spacemode != 1 }'),
        hide(hou.IntParmTemplate('curve_seed','Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the random positions.'),'{ curve_spacemode != 2 }'),
        hou.ToggleParmTemplate('curve_reverse','Reverse',default_value=False,help='Walk each curve from its end to its start: the point order, the ids and the tangent direction flip.'),
        menu('curve_align','Alignment',('None','Tangent'),default_value=1,help='Tangent turns each instance so its forward axis (+Z, as in Circle Facing) follows the curve and its up axis (+Y) stays as close to the Up Vector as possible. None keeps the prototype orientation. Instance Transform, Randomize and the Prototype Bank rotation offset apply BEFORE the alignment, as with Circle Facing.'),
        hide(menu('curve_upmode','Up',('World Y','Custom'),help='The direction the instances keep as their up.'),'{ curve_align == 0 }'),
        hide(hou.FloatParmTemplate('curve_up','Up Vector',3,default_value=(0,1,0),min=-1,max=1,help='Custom up direction in world space. Only its direction matters; a zero vector falls back to +Y, and a curve running along it picks a stable side axis instead.'),'{ curve_align == 0 } { curve_upmode != 1 }'),
        hide(hou.FloatParmTemplate('curve_roll','Roll (deg)',1,default_value=(0,),min=-180,max=180,help='Extra turn of every instance about the curve tangent.'),'{ curve_align == 0 }'),
        info))

def surface_folder():
    """Surface Scatter (v0.4.6): stable random points on triangles read from the incoming stage."""
    tags=base.picker_tags()
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    info=hou.StringParmTemplate('surface_info','Surface',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. Triangle count, total area, the area inside the slope limits and the number of points.')
    info.setDefaultExpression(('hou.pwd().hdaModule().surface_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    return hou.FolderParmTemplate('surface','Surface',folder_type=hou.folderType.Simple,parm_templates=(
        hou.StringParmTemplate('surface_prim','Surface Prim',1,default_value=('/World/Terrain',),tags=tags,help='A prim in the incoming stream: a Mesh, a Cube / Sphere / Cylinder / Cone / Capsule prim, or any prim whose subtree holds some. Every mesh under it is used at its world transform, so the points land on the surface as drawn; leave the Bounds Transform at its defaults to keep them there. The output prim itself is skipped.'),
        menu('surface_countmode','Amount',('By Count','By Density'),help='By Count: exactly Count points. By Density: Density points per unit of area (the world-space area of the allowed triangles, at most 10000 points).'),
        hide(hou.IntParmTemplate('surface_count','Count',1,default_value=(100,),min=1,max=10000,min_is_strict=True,help='Number of points, at most 10000.'),'{ surface_countmode != 0 }'),
        hide(hou.FloatParmTemplate('surface_density','Density (per area)',1,default_value=(100.0,),min=0,max=100000,help='Points per square unit of surface.'),'{ surface_countmode != 1 }'),
        hou.IntParmTemplate('surface_seed','Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the scatter. Point i depends only on its own id and the seed, so raising the Count adds points and never moves the earlier ones (while the surface and the slope limits stay the same).'),
        menu('surface_normal','Normal',('Face','Smooth'),help='Face: the flat normal of the triangle the point lies on. Smooth: the area-weighted vertex normals blended across the triangle (soft terrain). Used for Align to Normal and for the Offset.'),
        hou.FloatParmTemplate('surface_align','Align to Normal',1,default_value=(1.0,),min=0,max=1,help='0 keeps every instance upright, 1 tilts its up axis (+Y) fully onto the surface normal, in between blends. The tilt is applied AFTER Instance Transform and Randomize, so a Yaw Only variation turns the instances about the surface normal.'),
        hou.FloatParmTemplate('surface_offset','Offset',1,default_value=(0.0,),min=-10,max=10,help='Moves every point along its normal, in scene units (a negative value sinks the instances into the surface).'),
        hou.FloatParmTemplate('surface_slope_min','Slope Min (deg)',1,default_value=(0.0,),min=0,max=90,help='Smallest slope, in degrees from horizontal (0 flat, 90 a wall), a triangle may have to receive points. Downward-facing triangles count as 90 to 180.'),
        hou.FloatParmTemplate('surface_slope_max','Slope Max (deg)',1,default_value=(90.0,),min=0,max=180,help='Largest slope a triangle may have to receive points. Triangles outside the range are excluded and the points go on the others, so the count stays exact.'),
        info))

def paint_folder():
    """Paint (v0.6.0): points painted with a viewport brush on the Paint Target. The strokes are stored as points in the hidden parm paint_data."""
    tags=base.picker_tags()
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def callback(template,code):
        template.setScriptCallback(code);template.setScriptCallbackLanguage(hou.scriptLanguage.Python);return template
    info=hou.StringParmTemplate('paint_info','Paint',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. How many points are painted.')
    info.setDefaultExpression(('hou.pwd().hdaModule().paint_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    data=hou.StringParmTemplate('paint_data','Paint Data',1,default_value=('',),help='The painted points (compressed text). Written by the brush; Clear Paint empties it.')
    data.hide(True)
    return hou.FolderParmTemplate('paint','Paint',folder_type=hou.folderType.Simple,parm_templates=(
        callback(hou.ButtonParmTemplate('paint_start','Start Painting',help='Select this node and enter the Arraytron Paint viewport tool (you can also select the node and press Enter in the viewport). Drag over the Paint Target to add points, Ctrl-drag to erase, [ and ] change the radius, Esc or Enter to finish.'),"kwargs['node'].hdaModule().paint_start(kwargs['node'])"),
        hou.StringParmTemplate('paint_prim','Paint Target',1,default_value=('/World/Terrain',),tags=tags,help='The surface to paint on: a prim in the Scene Stream (first input), a Mesh or a basic shape, or any prim whose subtree holds some. Leave it EMPTY to paint on an invisible ground plane at Y = 0.'),
        menu('paint_op','Operation',('Add','Remove','Replace','Relax'),help='What a plain drag does. Add: paint new points. Remove: erase points. Replace: clear the points under the brush and paint new ones there. Relax: spread the points under the brush towards an even spacing (Min Spacing, or their own average spacing). Ctrl-drag erases (or paints when the Operation is Remove).'),
        hou.FloatParmTemplate('paint_radius','Brush Radius',1,default_value=(1.0,),min=0.01,max=100,help='Radius of the brush, in scene units. [ and ] change it while painting.'),
        hou.FloatParmTemplate('paint_strength','Brush Strength',1,default_value=(1.0,),min=0,max=1,help='Add: the chance that a candidate point inside the brush is kept. Remove: the chance that a point inside the brush is removed. Multiplied by the falloff.'),
        hou.FloatParmTemplate('paint_density','Density (per area)',1,default_value=(20.0,),min=0,max=1000,help='Candidate points per square unit under the brush for every dab (at most 2000 per dab).'),
        hou.FloatParmTemplate('paint_spacing','Min Spacing',1,default_value=(0.1,),min=0,max=10,help='No new point is placed closer than this to another painted point, so dragging back and forth does not pile points up. 0 allows overlapping points.'),
        menu('paint_falloff','Falloff',('Linear','Smooth','Gaussian','Hard'),help='How the brush weakens from the centre to the rim: Linear, Smooth (smoothstep), Gaussian, Hard (full strength to the rim).'),
        hou.IntParmTemplate('paint_seed','Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the random choices of the brush. The same strokes with the same seed always give the same points.'),
        hou.FloatParmTemplate('paint_align','Align to Normal',1,default_value=(1.0,),min=0,max=1,help='0 keeps every instance upright, 1 tilts its up axis (+Y) fully onto the surface normal. Applied after Instance Transform and Randomize.'),
        hou.FloatParmTemplate('paint_offset','Offset',1,default_value=(0.0,),min=-10,max=10,help='Moves every painted point along its normal, in scene units (negative sinks the instances into the surface).'),
        info,
        callback(hou.ButtonParmTemplate('paint_clear','Clear Paint',help='Remove every painted point (undoable).'),"kwargs['node'].hdaModule().paint_clear(kwargs['node'])"),
        data))

def place_folder():
    """Instance Place (v1.9.0): instances placed one at a time, like the transforms of a Copy and Transform SOP, by a table or by clicking a surface in the viewport."""
    tags=base.picker_tags()
    def callback(template,code):
        template.setScriptCallback(code);template.setScriptCallbackLanguage(hou.scriptLanguage.Python);return template
    hide=lambda template,condition:(template.setConditional(hou.parmCondType.HideWhen,condition),template)[1]
    row=(
        hou.ToggleParmTemplate('place_on#','On',default_value=True,help='Switch this instance off without deleting its row.'),
        hou.IntParmTemplate('place_id#','Id',1,default_value=(0,),min=0,max=100000000,help='The stable id of this instance (Variation, Mask, Instance Overrides, primvars and Grow key on it). 0 or a repeated id gets the next free number: press Fix Ids to write them into the table. The viewport tool fills it in.'),
        hou.FloatParmTemplate('place_pos#','Position',3,default_value=(0,0,0),min=-100000,max=100000,help='World position of the instance.'),
        hou.FloatParmTemplate('place_rot#','Rotate (deg)',3,default_value=(0,0,0),min=-360,max=360,help='Rotation in degrees about X, then Y, then Z (fixed axes), the same convention as the Instance Overrides. Applied before the Variation tab rotation.'),
        hou.FloatParmTemplate('place_scale#','Scale',3,default_value=(1,1,1),min=0.0001,max=1000,min_is_strict=True,help='Scale of the instance, multiplied by the Variation tab scale and the Prototype Bank scale.'),
        hou.IntParmTemplate('place_proto#','Prototype Row',1,default_value=(0,),min=0,max=1000,help='The Prototype Bank row this instance uses (its number in the bank). 0 lets the Selection Mode choose. A row that is not enabled is ignored.'),
        hou.IntParmTemplate('place_copies#','Copies',1,default_value=(1,),min=1,max=9999,help='Make an array like the Copy and Transform SOP: this many copies of the instance, each one moved by one more step (below). 1 is a single instance. The copies share the row: On, Prototype Row and the viewport Ctrl-click act on all of them; copy 0 keeps the row Id and the others get ids derived from it (a row that makes copies needs an Id below 100000).'),
        hide(hou.FloatParmTemplate('place_ctrans#','Step Translate',3,default_value=(0,0,0),min=-1000,max=1000,help='How far each copy moves from the one before: X, Y, Z in the Step Space.'),'{ place_copies# <= 1 }'),
        hide(hou.FloatParmTemplate('place_crot#','Step Rotate (deg)',3,default_value=(0,0,0),min=-360,max=360,help='How much each copy turns from the one before (degrees about X, then Y, then Z).'),'{ place_copies# <= 1 }'),
        hide(hou.FloatParmTemplate('place_cscale#','Step Scale',1,default_value=(1.0,),min=0.0001,max=1000,min_is_strict=True,help='Each copy is this many times the size of the one before (1 keeps the size, 0.9 shrinks every copy by ten percent).'),'{ place_copies# <= 1 }'),
        hide(hou.MenuParmTemplate('place_cspace#','Step Space',('0','1'),('Local (follows the copy)','World'),default_value=0,help='Local: every step is applied in the frame of the previous copy, like the Copy and Transform SOP, so a rotation makes spirals and fans and the translation turns and shrinks with the copy. World: the translation is along the world axes, the rotation turns the copy about its own position in world axes.'),'{ place_copies# <= 1 }'))
    table=hou.FolderParmTemplate('places','Placed Instances',folder_type=hou.folderType.MultiparmBlock,default_value=0,parm_templates=row)
    info=hou.StringParmTemplate('place_info','Placed',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. How many instances are placed.')
    info.setDefaultExpression(('hou.pwd().hdaModule().place_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    return hou.FolderParmTemplate('place','Instance Place',folder_type=hou.folderType.Simple,parm_templates=(
        callback(hou.ButtonParmTemplate('place_start','Place Instances in Viewport',help='Switch to Instance Place and enter the viewport tool: click a surface to place one instance at a time (a row is added to the table). Press, drag and release: the drag turns and scales the new instance (Drag Sets Rotation And Scale). Ctrl-click deletes the placed instance under the mouse; the wheel with Shift changes the scale, with Ctrl the rotation; [ ] scale, comma and period rotate, 0 to 9 pick the Prototype Row (0 = automatic). Esc or Enter finishes.'),"kwargs['node'].hdaModule().place_start(kwargs['node'])"),
        hou.StringParmTemplate('place_target','Place On',1,default_value=('',),tags=tags,help='The surface the tool places on: a Mesh, a basic shape or a hierarchy of the Scene Stream (first input). Empty: the ground plane Y = 0.'),
        hou.FloatParmTemplate('place_align','Align To Surface',1,default_value=(0.0,),min=0,max=1,help='0 keeps new instances upright, 1 tilts their up axis (+Y) fully onto the surface normal.'),
        hou.FloatParmTemplate('place_offset','Offset',1,default_value=(0.0,),min=-10,max=10,help='Moves a new instance along the surface normal (negative sinks it into the surface).'),
        hou.FloatParmTemplate('place_snap','Snap Position',1,default_value=(0.0,),min=0,max=1000,help='Snap new instances to a grid of this size (X and Z, in scene units; the point is put back on the surface). 0 = off.'),
        hou.FloatParmTemplate('place_snap_rot','Snap Rotation (deg)',1,default_value=(0.0,),min=0,max=180,help='Round the rotation of a new instance about the up axis to a multiple of this many degrees (15 gives 0, 15, 30 ...). 0 = off.'),
        hou.ToggleParmTemplate('place_dragset','Drag Sets Rotation And Scale',default_value=True,help='On: press the mouse button to set the position, drag to turn the new instance (sideways, half a degree per pixel) and scale it (up doubles its size every 150 pixels), release to place it. Off: a click places at once.'),
        hou.FloatParmTemplate('place_def_scale','New Scale',1,default_value=(1.0,),min=0.0001,max=1000,min_is_strict=True,help='The scale a new instance gets (the wheel with Shift and the [ ] keys change it in the viewport).'),
        hou.FloatParmTemplate('place_def_yaw','New Rotation (deg)',1,default_value=(0.0,),min=-360,max=360,help='The rotation about the up axis a new instance gets (the wheel with Ctrl and the comma and period keys change it in the viewport).'),
        hou.FloatParmTemplate('place_def_yawrand','Random Rotation (+/- deg)',1,default_value=(0.0,),min=0,max=180,help='A random extra rotation about the up axis for every new instance, from minus to plus this many degrees.'),
        hou.IntParmTemplate('place_def_proto','New Prototype Row',1,default_value=(0,),min=0,max=1000,help='The Prototype Bank row a new instance uses; 0 lets the Selection Mode choose (the keys 0 to 9 set it in the viewport).'),
        hou.IntParmTemplate('place_def_copies','New Copies',1,default_value=(1,),min=1,max=9999,help='Copies a new instance gets (1 = a single instance). More makes an array like the Copy and Transform SOP from every click.'),
        hou.FloatParmTemplate('place_def_ctrans','New Step Translate',3,default_value=(0,0,0),min=-1000,max=1000,help='The step translation of a new instance that makes copies.'),
        hou.FloatParmTemplate('place_def_crot','New Step Rotate (deg)',3,default_value=(0,0,0),min=-360,max=360,help='The step rotation of a new instance that makes copies.'),
        hou.FloatParmTemplate('place_def_cscale','New Step Scale',1,default_value=(1.0,),min=0.0001,max=1000,min_is_strict=True,help='The step scale of a new instance that makes copies.'),
        hou.MenuParmTemplate('place_def_cspace','New Step Space',('0','1'),('Local (follows the copy)','World'),default_value=0,help='Local or World steps for a new instance that makes copies.'),
        hou.IntParmTemplate('place_seed','Rotation Seed',1,default_value=(1,),min=0,max=10000,help='Seed of the random rotation of new instances.'),
        hou.StringParmTemplate('place_curve','Along Curve Prim',1,default_value=('',),tags=tags,help='A BasisCurves prim (or a prim whose subtree holds curves) of the Scene Stream: the Place Along Curve button adds one instance per sample of it.'),
        hou.MenuParmTemplate('place_curve_mode','Along Curve By',('0','1'),('Count','Spacing'),default_value=0,help='Count: this many instances along every curve, the ends included. Spacing: one instance every so many scene units.'),
        hide(hou.IntParmTemplate('place_curve_count','Along Curve Count',1,default_value=(10,),min=1,max=100000,help='Instances along every curve.'),'{ place_curve_mode != 0 }'),
        hide(hou.FloatParmTemplate('place_curve_spacing','Along Curve Spacing',1,default_value=(1.0,),min=0.001,max=100000,help='Distance between instances along the curve.'),'{ place_curve_mode != 1 }'),
        hou.ToggleParmTemplate('place_curve_follow','Follow Curve',default_value=True,help='Turn every instance so that its +Z axis points along the curve (about the up axis); New Rotation is added.'),
        hou.ToggleParmTemplate('place_curve_project','Project On Surface',default_value=False,help='Put the instances on the Place On surface (straight down from the curve) and align them with Align To Surface.'),
        callback(hou.ButtonParmTemplate('place_curve_go','Place Along Curve',help='Append one instance per curve sample to the table (undoable). Scale, rotation offset and Prototype Row come from the New settings.'),"kwargs['node'].hdaModule().place_along_curve(kwargs['node'])"),
        info,
        callback(hou.ButtonParmTemplate('place_fix','Fix Ids',help='Write a unique id into every row that has none or a repeated one (undoable).'),"kwargs['node'].hdaModule().place_normalize(kwargs['node'])"),
        callback(hou.ButtonParmTemplate('place_clear','Clear Placed Instances',help='Remove every placed instance (undoable).'),"kwargs['node'].hdaModule().place_clear(kwargs['node'])"),
        table))

def rows_folder():
    """Rows (v1.14.0): the linear modes (Line, Circle, Curve) scatter in several parallel rows, optionally randomised."""
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    info=hou.StringParmTemplate('rows_info','Rows',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. How many rows and points the Rows stage made.')
    info.setDefaultExpression(('hou.pwd().hdaModule().rows_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    return hou.FolderParmTemplate('rows','Rows',folder_type=hou.folderType.Simple,parm_templates=(
        hou.IntParmTemplate('rows_count','Rows',1,default_value=(1,),min=1,max=50,help='How many parallel rows the path is laid out in. 1 is the path alone, exactly as before. Line: rows next to each other; Circle: concentric rings; Curve: copies of the curve pushed to the side. The Count / Spacing of the mode is the number of points of ONE row, so the total is Rows times that. Row 0 keeps its ids and every other row gets ids derived from them, so changing the number of rows never renames a point.'),
        hou.FloatParmTemplate('rows_spacing','Row Spacing',1,default_value=(0.5,),min=0,max=100000,help='The distance between two rows, sideways from the path (horizontal and perpendicular to it; for a Circle in its plane, radially).'),
        hou.ToggleParmTemplate('rows_center','Centre The Rows',default_value=True,help='On: the rows are spread around the path (the middle one is on it when the number of rows is odd). Off: the path is the first row and the others follow on one side (a Circle: outwards).'),
        hou.FloatParmTemplate('rows_random','Random Offset',1,default_value=(0.0,),min=0,max=1,help='Randomise the position of every point sideways by up to this fraction of half the Row Spacing, so the rows are not straight lines. 0 keeps them straight. Works with one row too (a rough band along the path).'),
        hou.FloatParmTemplate('rows_shift','Random Shift Along',1,default_value=(0.0,),min=0,max=1,help='Randomise the position of every point along the path by up to this fraction of half the gap between neighbours, so the points of the rows do not line up. 0 keeps them in step.'),
        hou.ToggleParmTemplate('rows_stagger','Stagger Rows',default_value=False,help='Shift every second row along the path by half the gap between neighbours (a brick pattern).'),
        hou.IntParmTemplate('rows_seed','Rows Seed',1,default_value=(1,),min=0,max=10000,help='Seed of the random offsets. They are keyed on the id of every point, so a point keeps its offset when other rows come and go.'),
        info))

def biome_folder():
    """Biome (v1.15.0): rule based scatter on a terrain by elevation, slope, moisture and temperature, one row per biome."""
    tags=base.picker_tags()
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    rng=lambda name,label,default,lo,hi,help_:hou.FloatParmTemplate(name,label,2,default_value=default,min=lo,max=hi,help=help_)
    edge=lambda name,label,help_:hou.FloatParmTemplate(name,label,1,default_value=(0.0,),min=0,max=1000000,help=help_)
    row=(
        hou.ToggleParmTemplate('biome_on#','On',default_value=True,help='Switch this biome off without deleting its row.'),
        hou.StringParmTemplate('biome_name#','Name',1,default_value=('Biome',),help='A name for the read-out.'),
        hou.FloatParmTemplate('biome_density#','Density (per 100 area)',1,default_value=(20.0,),min=0,max=100000,help='Candidates of this biome per 100 square scene units of terrain (at most 100,000 per biome). Where the conditions hold only partly the candidates are thinned out, so this is the density at full weight. A higher density only ever adds points.'),
        hou.StringParmTemplate('biome_mix#','Prototype Mix',1,default_value=('1',),help='Which Prototype Bank rows this biome plants: bank row numbers with optional weights, separated by spaces, for example 1 2:3 4:0.5 (row 2 three times as often as row 1, row 4 half as often). A row that is not enabled is ignored.'),
        rng('biome_hrange#','Elevation',(-100000.0,100000.0),-1000000,1000000,'The heights (world Y) where this biome grows: minimum and maximum. The defaults cover everything.'),
        edge('biome_hedge#','Elevation Edge','Over this distance outside the elevation range the weight falls smoothly from 1 to 0 (an ecotone). 0 is a hard edge.'),
        rng('biome_srange#','Slope (deg)',(0.0,180.0),0,180,'The slopes where this biome grows, in degrees from flat (0) to a wall (90).'),
        edge('biome_sedge#','Slope Edge','Degrees outside the slope range over which the weight falls from 1 to 0. 0 is a hard edge.'),
        rng('biome_mrange#','Moisture',(0.0,1.0),-1,2,'The moisture values (0 dry to 1 wet) where this biome grows.'),
        edge('biome_medge#','Moisture Edge','Moisture outside the range over which the weight falls from 1 to 0. 0 is a hard edge.'),
        rng('biome_trange#','Temperature',(-100.0,100.0),-1000,1000,'The temperatures (degrees) where this biome grows.'),
        edge('biome_tedge#','Temperature Edge','Degrees outside the temperature range over which the weight falls from 1 to 0. 0 is a hard edge.'),
        rng('biome_scale#','Scale Min / Max',(0.8,1.2),0.0001,1000,'Every instance gets a random scale between the two (keyed on its id). Multiplied with the Variation tab and Prototype Bank scales.'))
    table=hou.FolderParmTemplate('biomes','Biomes',folder_type=hou.folderType.MultiparmBlock,default_value=0,parm_templates=row)
    info=hou.StringParmTemplate('biome_info','Biomes',1,default_value=('',),tags={'editor':'1','editorlines':'3-8'},help='Read only. The points every biome made in the last cook.')
    info.setDefaultExpression(('hou.pwd().hdaModule().biome_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    return hou.FolderParmTemplate('biome','Biome',folder_type=hou.folderType.Simple,parm_templates=(
        hou.StringParmTemplate('biome_prim','Terrain',1,default_value=('/World/Terrain',),tags=tags,help='The terrain to scatter on: a prim in the Scene Stream (first input), a Mesh or a basic shape, or any prim whose subtree holds some. Elevation is the height (world Y), slope the angle of the surface from flat.'),
        hou.IntParmTemplate('biome_seed','Seed',1,default_value=(1,),min=0,max=10000,help='Seed of the candidates and of every random choice (survival, prototype, scale, noise).'),
        menu('biome_normal','Normal',('Face','Smooth'),default_value=1,help='Face: the flat normal of the triangle. Smooth: the area-weighted vertex normals.'),
        hou.FloatParmTemplate('biome_align','Align to Normal',1,default_value=(1.0,),min=0,max=1,help='0 keeps every instance upright, 1 tilts its up axis (+Y) fully onto the terrain normal.'),
        hou.FloatParmTemplate('biome_offset','Offset',1,default_value=(0.0,),min=-10,max=10,help='Moves every instance along the terrain normal (negative sinks it).'),
        menu('biome_moist_mode','Moisture From',('Constant','Noise','Distance To Water','Image'),default_value=1,help='Constant: one value everywhere. Noise: fractal noise. Distance To Water: 1 at a water mesh or curve prim, falling to 0 at the Reach. Image: a grey value image seen from above.'),
        hide(hou.FloatParmTemplate('biome_moist_const','Moisture',1,default_value=(0.5,),min=0,max=1,help='The moisture everywhere.'),'{ biome_moist_mode != 0 }'),
        hide(hou.StringParmTemplate('biome_water','Water Prim',1,default_value=('',),tags=tags,help='A mesh, shape or curve prim (or a hierarchy) of the Scene Stream that counts as water: a lake, a river.'),'{ biome_moist_mode != 2 }'),
        hide(hou.FloatParmTemplate('biome_water_reach','Water Reach',1,default_value=(10.0,),min=0.001,max=100000,help='The distance from the water (measured on the ground plane) where the moisture has fallen to 0.'),'{ biome_moist_mode != 2 }'),
        hide(hou.StringParmTemplate('biome_moist_image','Moisture Image',1,default_value=('',),string_type=hou.stringParmType.FileReference,tags={'filechooser_pattern':'*.exr,*.png,*.jpg,*.tif,*.tiff,*.tga,*.hdr'},help='A grey value image (the luminance) projected from above onto the terrain.'),'{ biome_moist_mode != 3 }'),
        hide(hou.FloatParmTemplate('biome_moist_center','Image Centre (X, Z)',2,default_value=(0.0,0.0),min=-100000,max=100000,help='Where the middle of the image lies on the ground plane.'),'{ biome_moist_mode != 3 }'),
        hide(hou.FloatParmTemplate('biome_moist_size','Image Size (X, Z)',2,default_value=(20.0,20.0),min=0.001,max=1000000,help='The width and depth the image covers.'),'{ biome_moist_mode != 3 }'),
        hou.FloatParmTemplate('biome_moist_noise','Moisture Variation',1,default_value=(0.0,),min=0,max=1,help='Adds noise to the moisture (up to plus or minus this much), so the borders are not smooth contours.'),
        hou.FloatParmTemplate('biome_moist_bias','Moisture Bias',1,default_value=(0.0,),min=-1,max=1,help='Added to the moisture (a wetter or drier world); the result is kept in 0 to 1.'),
        hou.FloatParmTemplate('biome_temp','Temperature (base)',1,default_value=(15.0,),min=-1000,max=1000,help='The temperature in degrees at the Base Height.'),
        hou.FloatParmTemplate('biome_temp_h','Base Height',1,default_value=(0.0,),min=-1000000,max=1000000,help='The height (world Y) where the temperature is the base temperature.'),
        hou.FloatParmTemplate('biome_lapse','Lapse (deg per 100 units)',1,default_value=(10.0,),min=-1000,max=1000,help='How much colder it gets for every 100 scene units of height (the real atmosphere loses about 0.65 degrees per 100 metres; use more for a small stylised terrain).'),
        hou.FloatParmTemplate('biome_temp_noise','Temperature Noise',1,default_value=(0.0,),min=0,max=1000,help='Noise added to the temperature, plus or minus this many degrees.'),
        hou.FloatParmTemplate('biome_warm','Warm Facing (deg)',1,default_value=(0.0,),min=-1000,max=1000,help='Slopes that face the Warm Direction are warmer by up to this many degrees (and the opposite slopes colder), like a sunny and a shady hillside. 0 turns it off.'),
        hou.FloatParmTemplate('biome_warm_dir','Warm Direction (deg)',1,default_value=(180.0,),min=-360,max=360,help='The direction the warm slopes face, in degrees in the XZ plane from +X towards +Z.'),
        hide(hou.FloatParmTemplate('biome_noise_freq','Noise Frequency',1,default_value=(0.08,),min=0.0001,max=1000,help='Frequency of the noise used for moisture and temperature variation, in cycles per scene unit.'),'{ biome_moist_mode != 1 } { biome_moist_noise == 0 } { biome_temp_noise == 0 }'),
        info,
        table))

def falloff_folder():
    """Falloff (v1.12.0): the scatter is full size and densest in the centre of its layout and fades towards the edges (scale and density)."""
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    info=hou.StringParmTemplate('fall_info','Falloff',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. The centre and reach of the falloff and how many points it kept.')
    info.setDefaultExpression(('hou.pwd().hdaModule().falloff_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    return hou.FolderParmTemplate('falloff','Falloff',folder_type=hou.folderType.Simple,parm_templates=(
        hou.ToggleParmTemplate('fall_on','Falloff',default_value=False,help='Off: one density and one scale all over, exactly as before. On: the scatter is full size and densest in the centre of its layout and fades towards the edges. It works with every Distribution Mode and after the Mask and the Field Stack (their results are kept).'),
        hide(menu('fall_region','Region',('Automatic (follows the mode)','Whole layout'),default_value=0,help='Automatic: Cluster mode fades every cluster to its own boundary (its centre and radius, not the box or circle around all of them); Paint mode fades across the width of every stroke (the distance to the nearest stroke path divided by its brush radius; scenes painted before v1.13.0 have no stroke paths and use the whole layout until they are painted again); Grid mode uses all three axes when the grid has layers in Y; every other mode the whole layout. Whole layout: always one centre and one reach for everything (the behaviour of v1.12.0).'),'{ fall_on == 0 }'),
        hide(menu('fall_shape','Shape',('Radial (circle)','Box (every edge)'),default_value=0,help='Radial: the distance from the centre divided by the reach, so the fade is circular. Box: every edge of the layout fades, not only the corners (the largest of the offsets along the axes divided by the half size of the layout; per cluster a square of the cluster radius). Along a paint stroke the distance to the path is used whatever the shape.'),'{ fall_on == 0 }'),
        hide(menu('fall_curve','Curve',('Linear','Smooth','Gaussian'),default_value=1,help='How the weight falls from 1 in the centre to 0 at the edge: Linear, Smooth (smoothstep) or Gaussian.'),'{ fall_on == 0 }'),
        hide(hou.FloatParmTemplate('fall_inner','Flat Centre (%)',1,default_value=(0.0,),min=0,max=95,help='The central part of the reach (in percent) that keeps full size and full density before the fade starts.'),'{ fall_on == 0 }'),
        hide(hou.FloatParmTemplate('fall_density','Edge Density (%)',1,default_value=(0.0,),min=0,max=100,help='The share of the points that is kept at the edge. 0: the density falls to nothing at the edge. 100: the density does not change (only the scale falls). A point is kept when its own random number (keyed on its id) is below this share plus the rest times the weight, so more weight or more edge density only ever adds points.'),'{ fall_on == 0 }'),
        hide(hou.FloatParmTemplate('fall_scale','Edge Scale',1,default_value=(0.2,),min=0,max=1,help='The scale at the edge as a fraction of the full size (the centre keeps the true scale). 1: the scale does not change (only the density falls). Multiplied with the Mask Scale and the Field Stack scale.'),'{ fall_on == 0 }'),
        hide(hou.MenuParmTemplate('fall_axes','Axes',('0','1'),('X and Z (ground plane)','X, Y and Z'),default_value=0,help='Which coordinates count for the distance. X and Z (the default) fades on the ground plane whatever the height; X, Y and Z fades in all directions (a vertical line or a volume). With Region Automatic a Grid that has layers in Y (a 3D matrix) always fades in all three axes, so its top and bottom boundaries are respected too.'),'{ fall_on == 0 }'),
        hide(menu('fall_center_mode','Centre',('Automatic (middle of the layout)','Custom'),default_value=0,help='Automatic: the middle of the bounding box of the generated points. Custom: the position below.'),'{ fall_on == 0 }'),
        hide(hou.FloatParmTemplate('fall_center','Centre Position',3,default_value=(0,0,0),min=-100000,max=100000,help='The centre of the falloff in the space the points are generated in (the layout space of Line, Area, Grid and Circle; world space of Surface, Cluster and Imported Points).'),'{ fall_on == 0 } { fall_center_mode == 0 }'),
        hide(menu('fall_radius_mode','Reach',('Automatic (to the farthest point)','Custom'),default_value=0,help='Automatic: the distance of the farthest generated point (the box shape: the half sizes of the layout). Custom: the radius below, which also keeps the falloff steady while you change the count.'),'{ fall_on == 0 }'),
        hide(hou.FloatParmTemplate('fall_radius','Reach Radius',1,default_value=(10.0,),min=0.001,max=100000,help='The distance from the centre where the weight reaches 0 (the box shape: the half size). Points farther away are at the edge density and the edge scale.'),'{ fall_on == 0 } { fall_radius_mode == 0 }'),
        hide(hou.IntParmTemplate('fall_seed','Falloff Seed',1,default_value=(1,),min=0,max=10000,help='Seed of the random numbers that decide which points survive the density falloff.'),'{ fall_on == 0 }'),
        info))

def mask_folder():
    """Mask (v0.5.0): one 0..1 value per point from noise, an image or a mesh primvar, used to remove points and / or scale them."""
    tags=base.picker_tags()
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    info=hou.StringParmTemplate('mask_info','Mask',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. The weight range of the mask over the generated points and how many points survived.')
    info.setDefaultExpression(('hou.pwd().hdaModule().mask_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    on_mesh='{ mask_source == 0 } { mask_source == 1 } { mask_source == 2 mask_proj != 2 }'
    return hou.FolderParmTemplate('mask','Mask',folder_type=hou.folderType.Simple,parm_templates=(
        menu('mask_source','Mask Source',('None','Noise','Image','Mesh Primvar'),help='Where the 0 to 1 mask value of each point comes from. None: no mask (the points are exactly as generated). Noise: procedural fractal noise of the point position. Image: an image file, projected from above or the front, or through a mesh\'s UVs. Mesh Primvar: a float primvar painted on a mesh (for example a vertex-colour or opacity map). The value is read at the point\'s position in the space the points are generated in (before the Bounds Transform).'),
        menu('mask_effect','Mask Effect',('Density','Scale','Density + Scale'),help='Density: a point survives with a probability equal to the mask weight (weight 1 always, 0 never). Each point has its own fixed random number keyed on its id, so raising the weight only ever adds points and the survivors keep their ids. Scale: every point stays and is scaled between Min Scale (weight 0) and 1 (weight 1). Density + Scale does both.'),
        hou.ToggleParmTemplate('mask_invert','Invert',default_value=False,help='Use 1 - mask.'),
        hou.FloatParmTemplate('mask_low','Low',1,default_value=(0.0,),min=0,max=1,help='Mask values at or below Low give weight 0. Together with High this is the contrast control: raise Low and lower High to make the mask harder-edged.'),
        hou.FloatParmTemplate('mask_high','High',1,default_value=(1.0,),min=0,max=1,help='Mask values at or above High give weight 1; in between the weight rises linearly.'),
        hide(hou.FloatParmTemplate('mask_minscale','Min Scale',1,default_value=(0.2,),min=0,max=1,help='Scale at weight 0 (Scale effects only). Multiplies the instance scale after Randomize and the Prototype Bank scale.'),'{ mask_effect == 0 }'),
        hou.IntParmTemplate('mask_seed','Mask Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the noise and of the per-point random numbers of the Density effect.'),
        hide(hou.FloatParmTemplate('mask_noise_freq','Noise Frequency',1,default_value=(1.0,),min=0.001,max=100,min_is_strict=True,help='Noise features per scene unit.'),'{ mask_source != 1 }'),
        hide(hou.FloatParmTemplate('mask_noise_offset','Noise Offset',3,default_value=(0,0,0),min=-100,max=100,help='Slides the noise through space (in noise units, after Frequency).'),'{ mask_source != 1 }'),
        hide(hou.IntParmTemplate('mask_noise_octaves','Octaves',1,default_value=(3,),min=1,max=6,min_is_strict=True,max_is_strict=True,help='Layers of noise, each twice as fine as the one before.'),'{ mask_source != 1 }'),
        hide(hou.FloatParmTemplate('mask_noise_rough','Roughness',1,default_value=(0.5,),min=0,max=1,help='How strong each finer layer is compared with the one before.'),'{ mask_source != 1 }'),
        hide(hou.FloatParmTemplate('mask_noise_contrast','Contrast',1,default_value=(2.5,),min=0.1,max=10,help='Fractal noise clusters around 0.5; Contrast stretches it around 0.5 to use the whole 0 to 1 range before Low / High.'),'{ mask_source != 1 }'),
        hide(hou.StringParmTemplate('mask_image','Image',1,default_value=('',),string_type=hou.stringParmType.FileReference,tags={'filechooser_pattern':'*.png,*.jpg,*.jpeg,*.tif,*.tiff,*.exr,*.tx,*.hdr','filechooser_mode':'read'},help='Image file read with OpenImageIO. Pixel values are used as stored (no colour transform): a black to white 8-bit map gives 0 to 1.'),'{ mask_source != 2 }'),
        hide(menu('mask_channel','Channel',('Luminance','Red','Green','Blue','Alpha'),help='Which channel becomes the mask.'),'{ mask_source != 2 }'),
        hide(menu('mask_proj','Projection',('Top (XZ)','Front (XY)','Mesh UV'),help='Top: the image is laid over the XZ plane seen from above (X to the right, the image top is -Z). Front: laid over XY (the image top is +Y). Mesh UV: the image is read through the UV (st primvar) of the Mask Prim mesh, found by looking down from above at each point.'),'{ mask_source != 2 }'),
        hide(hou.FloatParmTemplate('mask_center','Image Center',2,default_value=(0,0),min=-100,max=100,help='Center of the projected image: (X, Z) for Top, (X, Y) for Front, in the space the points are generated in.'),'{ mask_source != 2 } { mask_proj == 2 }'),
        hide(hou.FloatParmTemplate('mask_size','Image Size',2,default_value=(10,10),min=0.001,max=1000,min_is_strict=True,help='Width and depth (Top) or height (Front) the image covers.'),'{ mask_source != 2 } { mask_proj == 2 }'),
        hide(menu('mask_outside','Outside The Image',('Black (0)','Repeat','Clamp'),help='What is read beyond the image edge (or beyond the UV 0 to 1 square).'),'{ mask_source != 2 }'),
        hide(hou.StringParmTemplate('mask_uvname','UV Primvar',1,default_value=('st',),help='Name of the UV primvar of the Mask Prim mesh (two floats).'),'{ mask_source != 2 } { mask_proj != 2 }'),
        hide(hou.StringParmTemplate('mask_prim','Mask Prim',1,default_value=('/World/Terrain',),tags=tags,help='The mesh (or a prim whose subtree holds meshes) the primvar or UVs are read from, at its world transform. Each point is looked up by looking down from +Y onto the triangles; the highest triangle wins. Points outside every triangle get the outside value.'),on_mesh),
        hide(hou.StringParmTemplate('mask_primvar','Primvar',1,default_value=('mask',),help='Name of a float primvar of the Mask Prim meshes (vertex, faceVarying, uniform or constant interpolation), e.g. mask, displayOpacity.'),'{ mask_source != 3 }'),
        hide(hou.FloatParmTemplate('mask_mesh_outside','Outside The Mesh',1,default_value=(0.0,),min=0,max=1,help='Mask value for points that are not above any triangle of the Mask Prim.'),'{ mask_source != 3 }'),
        info))

def cluster_folder():
    """Cluster (v0.8.0): groups of instances around centres scattered over a surface."""
    tags=base.picker_tags()
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    info=hou.StringParmTemplate('cluster_info','Clusters',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. How many clusters and instances come out.')
    info.setDefaultExpression(('hou.pwd().hdaModule().cluster_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    area=hou.FloatParmTemplate('cluster_area','Ground Size',2,default_value=(10.0,10.0),min=0.01,max=10000,help='Width and depth (X, Z) of the flat ground at Y = 0, centred on the origin, that the clusters are spread over. Used when the Cluster Surface is empty.')
    area.setConditional(hou.parmCondType.HideWhen,'{ cluster_prim != "" }')
    return hou.FolderParmTemplate('cluster','Cluster',folder_type=hou.folderType.Simple,parm_templates=(
        hou.StringParmTemplate('cluster_prim','Cluster Surface',1,default_value=('/World/Terrain',),tags=tags,help='The surface to scatter the clusters over: a prim in the Scene Stream (a mesh or basic shape, or any prim whose subtree holds some), at its world transform. Leave it EMPTY for a flat ground rectangle (Ground Size).'),
        area,
        hou.IntParmTemplate('cluster_count','Cluster Count',1,default_value=(8,),min=1,max=500,min_is_strict=True,help='Number of clusters. Cluster c depends only on its own number and the seed, so raising the count adds clusters and never moves the earlier ones.'),
        hou.IntParmTemplate('cluster_per','Instances Per Cluster',1,default_value=(20,),min=1,max=999,min_is_strict=True,help='Average number of instances in a cluster (at most 999; the total is at most 20000).'),
        hou.FloatParmTemplate('cluster_radius','Cluster Radius',1,default_value=(1.0,),min=0.01,max=1000,help='Radius of a cluster, in scene units.'),
        hou.FloatParmTemplate('cluster_falloff','Cluster Falloff',1,default_value=(0.5,),min=0,max=1,help='0 spreads the instances evenly over the disc, 1 packs them towards the centre.'),
        hou.FloatParmTemplate('cluster_jitter','Cluster Jitter',1,default_value=(0.3,),min=0,max=1,help='Random variation of every cluster\'s size and of its number of instances, as a fraction (0.3 = +/- 30%).'),
        hou.IntParmTemplate('cluster_seed','Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the cluster centres and of the placement inside the clusters.'),
        menu('cluster_normal','Normal',('Face','Smooth'),default_value=1,help='Face: the flat normal of the triangle. Smooth: the area-weighted vertex normals blended across the triangle.'),
        hou.FloatParmTemplate('cluster_align','Align to Normal',1,default_value=(1.0,),min=0,max=1,help='0 keeps every instance upright, 1 tilts its up axis (+Y) fully onto the surface normal. Applied after Instance Transform and Randomize.'),
        hou.FloatParmTemplate('cluster_offset','Offset',1,default_value=(0.0,),min=-10,max=10,help='Moves every instance along its normal, in scene units.'),
        info))

def optimize_folder():
    """Optimize (v0.9.0): camera-aware culling, density and LOD (Python LOP camera_optimize) and the extended primvars."""
    tags=base.picker_tags()
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    info=hou.StringParmTemplate('cam_info','Camera',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. What the camera section did at the current frame.')
    info.setDefaultExpression(('hou.pwd().hdaModule().camera_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    frame=hou.FloatParmTemplate('cam_frame','Frame',1,default_value=(1,),help='Internal: the current frame, which makes the node depend on time while Camera is on.');frame.setDefaultExpression(('$FF',));frame.setDefaultExpressionLanguage((hou.scriptLanguage.Hscript,));frame.hide(True)
    off='{ cam_on == 0 }'
    fold=hou.FolderParmTemplate('optimize','Optimize',folder_type=hou.folderType.Simple,parm_templates=(
        hou.ToggleParmTemplate('cam_on','Camera Optimisation',default_value=False,help='Hide or simplify instances by their distance to a camera. Nothing is deleted: instances are hidden through the PointInstancer\'s invisibleIds and level of detail switches protoIndices to the LOD prototypes, so turning this off brings everything back. The camera is read at the current frame (animated cameras work).'),
        hide(hou.StringParmTemplate('cam_prim','Camera Prim',1,default_value=('/cameras/camera1',),tags=tags,help='A USD camera in the stream: wire a Camera LOP into the first input (before Arraytron) and pick it.'),off),
        hide(hou.ToggleParmTemplate('cam_frustum','Frustum Culling',default_value=False,help='Hide instances that lie completely outside the camera\'s view (their bounding sphere is tested against the field of view and the clipping range). The camera aperture decides the aspect ratio, not the render resolution.'),off),
        hide(hou.FloatParmTemplate('cam_margin','Frustum Margin',1,default_value=(0.1,),min=0,max=2,help='Widens the field of view by this fraction before culling, so instances just outside the frame stay (shadows, motion, camera moves).'),'{ cam_on == 0 } { cam_frustum == 0 }'),
        hide(menu('cam_behind','Behind Camera',('Keep All','Reduce','Hide'),help='What happens to instances behind the camera plane. Reduce keeps only the fraction below; Hide hides them all.'),off),
        hide(hou.FloatParmTemplate('cam_behind_keep','Behind Keep',1,default_value=(0.25,),min=0,max=1,help='Fraction of the instances behind the camera that stay visible (Reduce).'),'{ cam_on == 0 } { cam_behind != 1 }'),
        hide(hou.ToggleParmTemplate('cam_distcull','Distance Culling',default_value=False,help='Hide instances farther than the Max Distance.'),off),
        hide(hou.FloatParmTemplate('cam_maxdist','Max Distance',1,default_value=(100.0,),min=0,max=100000,help='Instances whose bounding sphere starts farther than this from the camera are hidden.'),'{ cam_on == 0 } { cam_distcull == 0 }'),
        hide(hou.ToggleParmTemplate('cam_densityon','Density By Distance',default_value=False,help='Thin the instances with distance: all of them up to Near Distance, falling to the Minimum fraction at Far Distance. Each instance has its own fixed random number keyed on its id, so a nearer camera only ever adds instances back.'),off),
        hide(hou.FloatParmTemplate('cam_dnear','Near Distance',1,default_value=(10.0,),min=0,max=100000,help='Full density up to this distance.'),'{ cam_on == 0 } { cam_densityon == 0 }'),
        hide(hou.FloatParmTemplate('cam_dfar','Far Distance',1,default_value=(60.0,),min=0,max=100000,help='Minimum density from this distance on.'),'{ cam_on == 0 } { cam_densityon == 0 }'),
        hide(hou.FloatParmTemplate('cam_dmin','Minimum Density',1,default_value=(0.1,),min=0,max=1,help='Fraction of instances kept at and beyond Far Distance.'),'{ cam_on == 0 } { cam_densityon == 0 }'),
        hide(hou.IntParmTemplate('cam_seed','Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the per-id random numbers used for Density By Distance and Behind Camera.'),off),
        hide(hou.ToggleParmTemplate('cam_lod','Level Of Detail',default_value=False,help='Switch instances to the LOD 1 / LOD 2 / Proxy prims of their Prototype Bank row by distance or screen size. A row without LOD prims keeps its prototype.'),off),
        hide(menu('lod_by','Switch By',('Distance','Screen Size'),help='Distance: the camera distance. Screen Size: the percentage of the image height covered by the instance\'s bounding sphere (the aperture ratio decides the height).'),'{ cam_on == 0 } { cam_lod == 0 }'),
        hide(hou.FloatParmTemplate('lod_d1','LOD 1 Distance',1,default_value=(20.0,),min=0,max=100000,help='From this distance on the LOD 1 prim is used.'),'{ cam_on == 0 } { cam_lod == 0 } { lod_by != 0 }'),
        hide(hou.FloatParmTemplate('lod_d2','LOD 2 Distance',1,default_value=(50.0,),min=0,max=100000,help='From this distance on the LOD 2 prim is used.'),'{ cam_on == 0 } { cam_lod == 0 } { lod_by != 0 }'),
        hide(hou.FloatParmTemplate('lod_d3','Proxy Distance',1,default_value=(100.0,),min=0,max=100000,help='From this distance on the Proxy prim is used.'),'{ cam_on == 0 } { cam_lod == 0 } { lod_by != 0 }'),
        hide(hou.FloatParmTemplate('lod_s1','LOD 1 Size (%)',1,default_value=(10.0,),min=0,max=1000,help='Below this screen size (percent of the image height) the LOD 1 prim is used.'),'{ cam_on == 0 } { cam_lod == 0 } { lod_by != 1 }'),
        hide(hou.FloatParmTemplate('lod_s2','LOD 2 Size (%)',1,default_value=(4.0,),min=0,max=1000,help='Below this screen size the LOD 2 prim is used.'),'{ cam_on == 0 } { cam_lod == 0 } { lod_by != 1 }'),
        hide(hou.FloatParmTemplate('lod_s3','Proxy Size (%)',1,default_value=(1.5,),min=0,max=1000,help='Below this screen size the Proxy prim is used.'),'{ cam_on == 0 } { cam_lod == 0 } { lod_by != 1 }'),
        info,frame,
        hou.ToggleParmTemplate('pv_id','Primvar: arraytron_id',default_value=False,help='Write primvars:arraytron_id, the stable id of every instance.'),
        hou.ToggleParmTemplate('pv_proto','Primvar: prototype_id',default_value=False,help='Write primvars:prototype_id, the Prototype Bank row of every instance.'),
        hou.ToggleParmTemplate('pv_random','Primvar: random',default_value=False,help='Write primvars:random, a stable random number in [0, 1) per instance (for colour or shader variation).'),
        hou.ToggleParmTemplate('pv_mask','Primvar: mask',default_value=False,help='Write primvars:mask, the Mask weight of every instance (1 without a mask).'),
        hou.ToggleParmTemplate('pv_density','Primvar: density',default_value=False,help='Write primvars:density, the Field Stack weight of every instance (1 without a stack).'),
        hou.ToggleParmTemplate('pv_cluster','Primvar: cluster',default_value=False,help='Write primvars:cluster, the cluster number of every instance (Cluster mode).'),
        *((hou.ToggleParmTemplate('pv_biome','Primvar: biome',default_value=False,help='Write primvars:biome, the row of the Biome table every instance belongs to (Biome mode), for shaders, filtering and the like.'),) if BIOME else ()),
        *((hou.ToggleParmTemplate('pv_srcid','Primvar: source_id',default_value=False,help='Write primvars:source_id, the id the instance had in the imported source (Imported Points; its own id attribute, or the point number when it had none), for AOVs and matte ids.'),
          hou.StringParmTemplate('pv_copy','Copy Attributes As Primvars',1,default_value=('',),help='Imported Points: names of the source attributes (separated by spaces) that are written as primvars, for example Cd age temperature. They are copied by name; vectors and floats are supported.')) if IMPORTED else ()),
        hide(hou.ToggleParmTemplate('pv_lod','Primvar: arraytron_lod',default_value=False,help='Write primvars:arraytron_lod, the level of detail every instance uses (0 hero, 1 LOD 1, 2 LOD 2, 3 proxy). Needs Camera Optimisation.'),off),
        hou.IntParmTemplate('pv_seed','Primvar Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of primvars:random.')))
    if LODGEN:
        gen=lambda template,cond='{ lodg_on == 0 }':hide(template,cond)
        fold.addParmTemplate(hou.ToggleParmTemplate('lodg_on','Generate LODs',default_value=False,help='Write reduced copies of every Prototype Bank row and use them as its LOD 1, LOD 2 and Proxy levels. A level that has a prim of its own in the bank keeps it. The hero prims are never changed. The levels are switched by distance or screen size in the LEVEL OF DETAIL section (Camera Optimisation and Level Of Detail on).'))
        fold.addParmTemplate(gen(hou.FloatParmTemplate('lodg_1','LOD 1 Triangles (%)',1,default_value=(50.0,),min=1,max=100,min_is_strict=True,help='Triangles kept for LOD 1, as a percentage of the hero (all meshes of the prototype are reduced by the same fraction).')))
        fold.addParmTemplate(gen(hou.FloatParmTemplate('lodg_2','LOD 2 Triangles (%)',1,default_value=(20.0,),min=1,max=100,min_is_strict=True,help='Triangles kept for LOD 2, as a percentage of the hero.')))
        fold.addParmTemplate(gen(hou.FloatParmTemplate('lodg_3','Proxy Triangles (%)',1,default_value=(5.0,),min=0.1,max=100,min_is_strict=True,help='Triangles kept for the Proxy, as a percentage of the hero (see Minimum Triangles).')))
        fold.addParmTemplate(gen(hou.IntParmTemplate('lodg_min','Minimum Triangles',1,default_value=(12,),min=4,max=100000,min_is_strict=True,help='No generated mesh gets fewer triangles than this (a mesh that already has fewer is copied as it is).')))
        info=hou.StringParmTemplate('lodg_info','Generated LODs',1,default_value=('',),tags={'editor':'1','editorlines':'2-4'},help='Read only. The triangle count of every prototype and of its generated levels (after the node has cooked).')
        info.setDefaultExpression(('hou.pwd().hdaModule().lodgen_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
        fold.addParmTemplate(info)
    return fold


def finish_folder():
    """Finish (v1.0.0): manual instance overrides, debug views and the USD export."""
    tags=base.picker_tags()
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    def callback(template,code):
        template.setScriptCallback(code);template.setScriptCallbackLanguage(hou.scriptLanguage.Python);return template
    row=(
        hou.IntParmTemplate('ovr_id#','Instance Id',1,default_value=(0,),min=0,max=100000000,help='The id of the instance to edit (the stable id: primvars:arraytron_id, or the Id debug colours). A row whose id does not exist is ignored.'),
        hou.ToggleParmTemplate('ovr_delete#','Delete',default_value=False,help='Remove this instance. The other instances keep their ids.'),
        hide(hou.FloatParmTemplate('ovr_move#','Move',3,default_value=(0,0,0),min=-1000,max=1000,help='Offset added to the position, in the space the points are generated in (before the Bounds Transform).'),'{ ovr_delete# == 1 }'),
        hide(hou.FloatParmTemplate('ovr_rot#','Rotate (deg)',3,default_value=(0,0,0),min=-360,max=360,help='Extra rotation in the instance\'s own frame: degrees about X, then Y, then Z.'),'{ ovr_delete# == 1 }'),
        hide(hou.FloatParmTemplate('ovr_scale#','Scale',1,default_value=(1,),min=0.0001,max=1000,min_is_strict=True,help='Multiplies the instance scale.'),'{ ovr_delete# == 1 }'),
        hide(hou.IntParmTemplate('ovr_proto#','Prototype Row',1,default_value=(0,),min=0,max=1000,help='Switch the instance to the prototype of this Prototype Bank row number (0 keeps the one it has). The row must be enabled.'),'{ ovr_delete# == 1 }'))
    table=hou.FolderParmTemplate('overrides','Instance Overrides',folder_type=hou.folderType.MultiparmBlock,default_value=0,parm_templates=row)
    info=hou.StringParmTemplate('ovr_info','Overrides',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. What the override rows did.')
    info.setDefaultExpression(('hou.pwd().hdaModule().override_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    clear=callback(hou.ButtonParmTemplate('ovr_clear','Clear Overrides',help='Remove every override row (undoable). The generated instances come back unchanged.'),"kwargs['node'].hdaModule().override_clear(kwargs['node'])")
    cinfo=hou.StringParmTemplate('cache_info','Stored On This Node',1,default_value=('',),tags={'editor':'1','editorlines':'3-6'},help='Read only. What this node stores or caches: the Physics Settle cache, the painted points, the override rows and the export file.')
    cinfo.setDefaultExpression(('hou.pwd().hdaModule().cache_overview(hou.pwd())',));cinfo.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));cinfo.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    export=callback(hou.ButtonParmTemplate('export_usd','Export USD',help='Write the final instances of this node (positions, orientations, scales, ids, prototype indices, hidden ids, primvars and the prototypes) to a self-contained USD file, for a cache, a hand-over or a reference. The debug guides are not exported.'),"n=kwargs['node']\npath,count=n.hdaModule().export_instances(n)\nprint('Arraytron: wrote %d instances to %s' % (count,path))")
    path=hou.StringParmTemplate('export_path','Export File',1,default_value=('$HIP/arraytron_export/$OS.usd',),string_type=hou.stringParmType.FileReference,tags={'filechooser_pattern':'*.usd,*.usda,*.usdc','filechooser_mode':'write'},help='Where Export USD writes. $OS is the node name.')
    dbg=lambda name,label,default,help_:hide(hou.ToggleParmTemplate(name,label,default_value=default,help=help_),'{ dbg_on == 0 }')
    fold=hou.FolderParmTemplate('finish','Finish',folder_type=hou.folderType.Simple,parm_templates=(table,info,clear,
        hou.ToggleParmTemplate('dbg_on','Debug Views',default_value=False,help='Show debug guides under the output prim (Debug). They are guide purpose: visible in the viewport, never rendered. Off by default.'),
        dbg('dbg_generated','Generated Points',True,'The points as the distribution generated them (white), before the Mask, Field Stack, Separation and Avoid Geometry.'),
        dbg('dbg_rejected','Rejected Points',True,'Generated points that are gone at the end: masked, thinned, separated or avoided (red).'),
        hide(menu('dbg_color','Colour Final Points By',('Off','Prototype','Id','Weight')+(('Biome',) if BIOME else ()),help='Colour the final instance points: by prototype index, by a colour per id, by weight (Mask x Field Stack: red 0 to green 1) or by biome (Biome mode: one colour per row of the table).'),'{ dbg_on == 0 }'),
        dbg('dbg_axes','Axes',False,'The up (green) and forward (blue) axis of every instance.'),
        dbg('dbg_radius','Collision Radius',False,'The Separation sphere of every instance (a ring in the XZ plane).'),
        dbg('dbg_centres','Cluster Centres',False,'The cluster centres (Cluster mode).'),
        hide(hou.FloatParmTemplate('dbg_size','Debug Size',1,default_value=(0.05,),min=0.001,max=100,help='Size of the debug points and axes.'),'{ dbg_on == 0 }'),
        path,export,cinfo))
    if PICK:fold.addParmTemplate(callback(hou.ButtonParmTemplate('ovr_pick','Pick Instance in Viewport',help='Click an instance in the viewport to create its override row (its stable id is filled in for you). Ctrl-click ticks Delete as well. The marker shows the instance under the mouse and the prompt its id. Esc or Enter finishes. The instances come from the node output, so hidden or deleted ones cannot be picked.'),"kwargs['node'].hdaModule().pick_start(kwargs['node'])"))
    return fold

def imported_folder():
    """Imported Points (v1.5.0): scatter on points from a SOP (an FX simulation, a scatter ...) or on a USD Points / PointInstancer prim."""
    tags=base.picker_tags()
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    info=hou.StringParmTemplate('imp_info','Imported Points',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. How many points the source has, how many are used and where the ids come from.')
    info.setDefaultExpression(('hou.pwd().hdaModule().imported_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    frame=hou.FloatParmTemplate('imp_frame','Frame',1,default_value=(1,),help='Internal: the current frame, so the node follows the source over time.');frame.setDefaultExpression(('$FF',));frame.setDefaultExpressionLanguage((hou.scriptLanguage.Hscript,));frame.hide(True)
    sop=hou.StringParmTemplate('imp_sop','Source SOP',1,default_value=('',),string_type=hou.stringParmType.NodeReference,tags={'opfilter':'!!SOP!!','oprelative':'.'},help='The SOP node whose points are used, for example the output of a POP / Vellum / FLIP simulation or any point cloud: /obj/sim/OUT_POINTS. The points are used as they are stored (no object transform is applied). The source is cooked at the current frame, so an animated simulation drives the instances.')
    return hou.FolderParmTemplate('imported','Imported Points',folder_type=hou.folderType.Simple,parm_templates=(
        menu('imp_source','Source',('SOP Node','USD Prim'),help='Where the points come from. SOP Node: any SOP in the scene. USD Prim: a Points or PointInstancer prim of the Scene Stream (first input), for example an FX cache imported as USD; it is read at the current frame in world space.'),
        hide(sop,'{ imp_source != 0 }'),
        hide(hou.StringParmTemplate('imp_prim','Source Prim',1,default_value=('/World/Sim',),tags=tags,help='A UsdGeomPoints or UsdGeomPointInstancer prim in the Scene Stream. Points: points, widths (pscale = width / 2), ids, velocities, normals. PointInstancer: positions, orientations, scales, ids, velocities. Its primvars with one value per point become point attributes of the same name.'),'{ imp_source != 1 }'),
        hide(hou.FloatParmTemplate('imp_offset','Time Offset',1,default_value=(0.0,),min=-100000,max=100000,help='Frames added to the current frame when the USD prim is read (to start the source later or earlier).'),'{ imp_source != 1 }'),
        hou.FloatParmTemplate('imp_percent','Use Percent Of Points',1,default_value=(100.0,),min=0,max=100,help='Use only this percentage of the source points. Every point has its own fixed random number keyed on its id, so a higher percentage only ever adds points and the others keep their prototype and look.'),
        hou.IntParmTemplate('imp_seed','Percent Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the per-id numbers of Use Percent Of Points.'),
        menu('imp_idmode','Instance Ids',('From Source Attribute','Point Number'),help='From Source Attribute: the integer attribute named below (a simulation keeps it for a point over time, so the instance keeps its prototype, random variation and overrides from frame to frame). It must be unique, otherwise the point number is used and a warning says so. Point Number: the order of the points (changes when the source count changes).'),
        hide(hou.StringParmTemplate('imp_idattr','Id Attribute',1,default_value=('id',),help='Name of the integer point attribute that holds the id (id for a POP simulation, for example).'),'{ imp_idmode != 0 }'),
        menu('imp_scale','Scale',('Off','From Attribute'),help='Off: the scale of the source is ignored (the Variation tab scale applies). From Attribute: the instance scale is multiplied by the attribute below times the multiplier.'),
        hide(hou.StringParmTemplate('imp_scale_attr','Scale Attribute',1,default_value=('pscale',),help='A float attribute (pscale, a radius) or a vector attribute (scale).'),'{ imp_scale == 0 }'),
        hou.FloatParmTemplate('imp_scale_mult','Scale Multiplier',1,default_value=(1.0,),min=0.0001,max=10000,help='Multiplies the source scale (or, with Scale Off, every instance). Applied on top of Look > Randomize.'),
        menu('imp_orient','Orientation',('Upright','From Orient Attribute','Along Velocity','From Normal'),help='Upright: no tilt. From Orient Attribute: the source quaternion. Along Velocity: the instance +Z follows the velocity (a point that is not moving stays upright). From Normal: the instance +Y follows the normal. Look > Randomize still turns the instance in its own frame.'),
        hide(hou.StringParmTemplate('imp_orient_attr','Orient Attribute',1,default_value=('orient',),help='A 4-float quaternion attribute (x, y, z, w).'),'{ imp_orient != 1 }'),
        hide(hou.StringParmTemplate('imp_vel_attr','Velocity Attribute',1,default_value=('v',),help='A vector attribute (v for a simulation).'),'{ imp_orient != 2 }'),
        hide(hou.StringParmTemplate('imp_normal_attr','Normal Attribute',1,default_value=('N',),help='A vector attribute.'),'{ imp_orient != 3 }'),
        hou.StringParmTemplate('imp_copy','Copy Attributes',1,default_value=('',),help='Names of source attributes (separated by spaces) to keep on the instance points, for example Cd age. Tick Primvar: ... in the Optimize tab or use Copy Attributes As Primvars to write them as primvars (AOVs).'),
        info,frame))

def fields_folder():
    """Field Stack (v0.7.0): rows of fields (Height, Slope, Noise, Image, Distance, Exclusion) combined into one 0..1 weight per point."""
    tags=base.picker_tags()
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    row=(
        hou.ToggleParmTemplate('field_on#','Enable',default_value=True,help='Switch this field off to leave it out without deleting it.'),
        menu('field_type#','Field',FIELD_TYPE_LABELS,help='Height: the Y position of the point. Slope: how steep the surface under the point is (read from a prim). Noise: fractal noise of the position. Image: an image laid over the layout. Distance: how far the point is from a prim (a road curve, a wall). Exclusion: keeps points out of a closed mesh (and a margin around it).'),
        menu('field_op#','Combine',('Multiply','Add','Subtract','Min','Max'),help='How this field joins the result of the rows above it: Multiply (both must be high), Add, Subtract, Min, Max. The first row ignores it. The running result is kept between 0 and 1 after every row.'),
        hou.ToggleParmTemplate('field_invert#','Invert',default_value=False,help='Use 1 - value for this field.'),
        hide(hou.FloatParmTemplate('field_hmin#','Min Height',1,default_value=(0.0,),min=-1000,max=1000,help='Lowest Y that gets weight 1, in the space the points are generated in.'),'{ field_type# != 0 }'),
        hide(hou.FloatParmTemplate('field_hmax#','Max Height',1,default_value=(10.0,),min=-1000,max=1000,help='Highest Y that gets weight 1.'),'{ field_type# != 0 }'),
        hide(hou.FloatParmTemplate('field_hfall#','Falloff',1,default_value=(1.0,),min=0,max=1000,help='Distance beyond Min / Max over which the weight falls from 1 to 0 (smoothly). 0 is a hard edge.'),'{ field_type# != 0 }'),
        hide(hou.StringParmTemplate('field_prim#','Prim',1,default_value=('/World/Terrain',),tags=tags,help='A prim in the Scene Stream (first input). Slope: the surface that is judged (the triangle under each point, looking down from +Y; points not above it are not judged). Distance: a mesh, shape or curve to measure to. Exclusion: a CLOSED mesh or shape. Read at its world transform.'),'{ field_type# < 1 } { field_type# == 2 } { field_type# == 3 }'),
        hide(hou.FloatParmTemplate('field_smin#','Min Slope (deg)',1,default_value=(0.0,),min=0,max=180,help='Smallest slope that gets weight 1 (0 flat, 90 a wall; downward faces are 90 to 180).'),'{ field_type# != 1 }'),
        hide(hou.FloatParmTemplate('field_smax#','Max Slope (deg)',1,default_value=(30.0,),min=0,max=180,help='Largest slope that gets weight 1.'),'{ field_type# != 1 }'),
        hide(hou.FloatParmTemplate('field_sfall#','Falloff (deg)',1,default_value=(10.0,),min=0,max=180,help='Degrees beyond Min / Max over which the weight falls from 1 to 0. 0 is a hard edge.'),'{ field_type# != 1 }'),
        hide(hou.FloatParmTemplate('field_nfreq#','Frequency',1,default_value=(1.0,),min=0.001,max=100,min_is_strict=True,help='Noise features per scene unit.'),'{ field_type# != 2 }'),
        hide(hou.FloatParmTemplate('field_noffset#','Offset',3,default_value=(0,0,0),min=-100,max=100,help='Slides the noise through space (after Frequency).'),'{ field_type# != 2 }'),
        hide(hou.IntParmTemplate('field_noct#','Octaves',1,default_value=(3,),min=1,max=6,min_is_strict=True,max_is_strict=True,help='Layers of noise, each twice as fine as the one before.'),'{ field_type# != 2 }'),
        hide(hou.FloatParmTemplate('field_nrough#','Roughness',1,default_value=(0.5,),min=0,max=1,help='How strong each finer layer is compared with the one before.'),'{ field_type# != 2 }'),
        hide(hou.FloatParmTemplate('field_ncontrast#','Contrast',1,default_value=(2.5,),min=0.1,max=10,help='Fractal noise clusters around 0.5; Contrast stretches it around 0.5.'),'{ field_type# != 2 }'),
        hide(hou.IntParmTemplate('field_nseed#','Noise Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the noise.'),'{ field_type# != 2 }'),
        hide(hou.StringParmTemplate('field_image#','Image',1,default_value=('',),string_type=hou.stringParmType.FileReference,tags={'filechooser_pattern':'*.png,*.jpg,*.jpeg,*.tif,*.tiff,*.exr,*.tx,*.hdr','filechooser_mode':'read'},help='Image file read with OpenImageIO; pixel values as stored.'),'{ field_type# != 3 }'),
        hide(menu('field_channel#','Channel',('Luminance','Red','Green','Blue','Alpha'),help='Which channel is the field.'),'{ field_type# != 3 }'),
        hide(menu('field_proj#','Projection',('Top (XZ)','Front (XY)'),help='Top: laid over the XZ plane seen from above (X to the right, the image top is -Z). Front: laid over XY (the image top is +Y).'),'{ field_type# != 3 }'),
        hide(hou.FloatParmTemplate('field_icenter#','Image Center',2,default_value=(0,0),min=-100,max=100,help='Center of the projected image: (X, Z) for Top, (X, Y) for Front.'),'{ field_type# != 3 }'),
        hide(hou.FloatParmTemplate('field_isize#','Image Size',2,default_value=(10,10),min=0.001,max=1000,min_is_strict=True,help='Width and depth (Top) or height (Front) the image covers.'),'{ field_type# != 3 }'),
        hide(menu('field_ioutside#','Outside The Image',('Black (0)','Repeat','Clamp'),help='What is read beyond the image edge.'),'{ field_type# != 3 }'),
        hide(hou.FloatParmTemplate('field_dnear#','Near Distance',1,default_value=(1.0,),min=0,max=1000,help='At or closer than this to the Prim the weight is 0.'),'{ field_type# != 4 }'),
        hide(hou.FloatParmTemplate('field_dfar#','Far Distance',1,default_value=(3.0,),min=0,max=1000,help='At or farther than this from the Prim the weight is 1; in between it rises smoothly.'),'{ field_type# != 4 }'),
        hide(menu('field_daxes#','Measure In',('XZ (ignore height)','XYZ'),default_value=1,help='XZ measures along the ground only (a road clears everything above and below it too); XYZ measures in 3D.'),'{ field_type# != 4 }'),
        hide(hou.FloatParmTemplate('field_xmargin#','Margin',1,default_value=(0.2,),min=0,max=1000,help='Points inside the mesh, or closer than this to it, get weight 0.'),'{ field_type# != 5 }'),
        hide(hou.FloatParmTemplate('field_xfall#','Falloff',1,default_value=(0.0,),min=0,max=1000,help='Distance beyond the margin over which the weight rises from 0 to 1. 0 is a hard edge.'),'{ field_type# != 5 }'))
    stack=hou.FolderParmTemplate('fields','Field Stack',folder_type=hou.folderType.MultiparmBlock,default_value=0,parm_templates=row)
    effect=menu('field_effect','Stack Effect',('Density','Scale','Density + Scale'),help='Density: a point survives with a probability equal to the combined weight (each point has its own fixed random number keyed on its id, so a higher weight only ever adds points). Scale: the instance is scaled between Min Scale (weight 0) and 1 (weight 1). Multiplies the Mask Scale when both are used.')
    minscale=hide(hou.FloatParmTemplate('field_minscale','Min Scale',1,default_value=(0.2,),min=0,max=1,help='Scale at weight 0 (Scale effects only).'),'{ field_effect == 0 }')
    seed=hou.IntParmTemplate('field_seed','Stack Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the per-point random numbers of the Density effect.')
    info=hou.StringParmTemplate('field_info','Field Stack',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. The weight range of the stack over the generated points and how many points survived.')
    info.setDefaultExpression(('hou.pwd().hdaModule().field_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    return hou.FolderParmTemplate('fieldstack','Field Stack',folder_type=hou.folderType.Simple,parm_templates=(stack,effect,minscale,seed,info))

def overlap_folder():
    """No Overlap (v0.5.1): remove or push apart instances whose bounding spheres overlap."""
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    info=hou.StringParmTemplate('overlap_info','Separation',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. How many points were removed or moved and how much overlap or violation is left.')
    info.setDefaultExpression(('hou.pwd().hdaModule().overlap_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    return hou.FolderParmTemplate('overlap','Separation & Collision',folder_type=hou.folderType.Simple,parm_templates=(
        menu('overlap_mode','Separation',('Off','Remove Overlapping','Push Apart'),help='Off: points stay exactly as generated. Remove Overlapping: visiting the points in id order, a point is deleted when an earlier surviving point overlaps it (the first points always survive, the survivors keep their ids and positions, and adding points at the end never changes earlier survivors). Push Apart: keeps every point and moves overlapping pairs apart along the line between them, repeatedly, until they no longer overlap or the iterations run out (a crowded area may stay partly overlapping: the read-out says how much).'),
        menu('overlap_size','Size From',('Prototype Bounds','Fixed Radius'),help='Prototype Bounds: each instance counts as the bounding sphere of its prototype (from the prototype geometry, at the instance scale, centred where the geometry is). Fixed Radius: every instance counts as a sphere of the Radius below at the instance scale.'),
        hide(menu('overlap_priority','Priority',('Id Order','Biggest First','Smallest First','Random'),help='Which of two overlapping instances survives Remove Overlapping. Id Order: the earlier point (the default, and what every earlier version did). Biggest First: the larger instance wins. Smallest First: the smaller wins. Random: a fixed random order keyed on the id. Ties go to the earlier point, so the result is stable.'),'{ overlap_mode != 1 }'),
        hide(hou.FloatParmTemplate('overlap_radius','Radius',1,default_value=(0.5,),min=0.0001,max=100,min_is_strict=True,help='Sphere radius of an instance at scale 1.'),'{ overlap_size != 1 }'),
        hou.FloatParmTemplate('overlap_tolerance','Spacing',1,default_value=(1.0,),min=0.05,max=4,help='The distance two instances must keep, as a multiple of the sum of their radii: 1 means the bounding spheres just touch, 0.7 allows them to sink into each other by 30%, 1.5 leaves a gap of half a radius. Tweak it to make the layout tighter or looser.'),
        menu('overlap_axes','Measure In',('XZ (ground plane)','XYZ (3D)'),default_value=1,help='XZ ignores height: two points above each other count as overlapping (use for one layer on a ground, and Push Apart then only slides points sideways). XYZ uses the true 3D distance (use for Grid layers, Circle on a wall, Curve in the air).'),
        hide(hou.IntParmTemplate('overlap_iterations','Iterations',1,default_value=(30,),min=1,max=500,min_is_strict=True,help='Push Apart passes. More passes resolve more crowding.'),'{ overlap_mode != 2 }'),
        menu('avoid_mode','Avoid Geometry',('Off','Remove','Push Out'),help='Keeps instances out of scene geometry. Each instance counts as a sphere (see Size From) and collides when its centre is inside a closed mesh or closer than its radius plus the Margin to the geometry. Remove: colliding instances are deleted. Push Out: they are moved away from the nearest surface point until clear (when both this and Separation push, a last pass puts geometry first).'),
        hide(hou.StringParmTemplate('avoid_prim','Avoid Prim',1,default_value=('/World/Hero',),tags=base.picker_tags(),help='A prim in the Scene Stream (first input): a mesh, shape or curve (or a prim whose subtree holds some) at its world transform. Inside / outside needs a closed mesh; open meshes and curves use distance only.'),'{ avoid_mode == 0 }'),
        hide(hou.FloatParmTemplate('avoid_margin','Margin',1,default_value=(0.1,),min=0,max=100,help='Extra clearance beyond the instance radius, in scene units.'),'{ avoid_mode == 0 }'),
        hide(menu('avoid_axes','Measure In',('XZ (ground plane)','XYZ (3D)'),default_value=1,help='XZ ignores height: the geometry clears everything above and below it too (a building footprint). XYZ is the true 3D distance and also tests inside a closed mesh.'),'{ avoid_mode == 0 }'),
        hide(hou.IntParmTemplate('avoid_iterations','Iterations',1,default_value=(20,),min=1,max=200,min_is_strict=True,help='Push Out passes.'),'{ avoid_mode != 2 }'),
        hide(hou.FloatParmTemplate('overlap_strength','Strength',1,default_value=(0.5,),min=0.05,max=1,help='Fraction of each pair\'s overlap that is corrected per pass (half by each point). 0.5 is stable; 1 resolves a pair at once but can overshoot in crowds.'),'{ overlap_mode != 2 }'),
        info))

def randomize_folder():
    """Randomize with the shared variation extras (master plan section 16): Rotation Variation and Scale Variation modes, Non-Uniform scale."""
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    seed=hou.IntParmTemplate('random_seed','Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the random draws below. Each draw is keyed on the stable point id, so adding points never reshuffles earlier ones.')
    position=hou.FloatParmTemplate('position_random','Position',3,default_value=(0,0,0),min=0,max=5,help='Symmetric +/- jitter after distribution, per axis, in local units. 0 on an axis locks it. Nonzero Y explicitly moves points off the ground plane.')
    keep=hide(hou.ToggleParmTemplate('area_keepinside','Keep Inside Area',default_value=False,help='Area only. Reflect Position jitter back at the Area rectangle edges so no point leaves the bounds (X and Z; Y jitter is unaffected). Reflecting, not clamping, so points do not pile up on the edge.'),'{ mode != 1 }')
    rotmode=menu('rotation_random_mode','Rotation Variation',('Euler XYZ','Yaw Only'),help='Euler XYZ: each axis varies by its own +/- amount (0 locks that axis). Yaw Only: only the Y Euler angle varies, by one +/- Yaw range. Either way the variation is ADDED to Instance Transform > Rotation, so a tilted Instance Rotation or Bounds Rotation still tilts the result: Yaw Only keeps the random part level, it does not force the instance upright.')
    euler=hide(hou.FloatParmTemplate('rotation_random','Rotation (deg)',3,default_value=(0,0,0),min=0,max=180,help='Maximum +/- Euler rotation per axis, in degrees. 0 on an axis locks it. For tumbling debris use (180, 180, 180).'),'{ rotation_random_mode != 0 }')
    yaw=hide(hou.FloatParmTemplate('yaw_random','Yaw (deg)',1,default_value=(0,),min=0,max=180,help='Maximum +/- rotation around the up (Y) axis, in degrees, added to the Y Euler angle of Instance Transform > Rotation. 180 gives every heading. X and Z stay as set in Instance Transform.'),'{ rotation_random_mode != 1 }')
    scalemode=menu('scale_random_mode','Scale Variation',('Fraction +/-','Min / Max'),help='Fraction +/-: Base Scale x (1 +/- Amount). Min / Max: Base Scale x a uniform random number between Minimum and Maximum. Both are uniform on every axis; use Non-Uniform for per-axis variation.')
    amount=hide(hou.FloatParmTemplate('scale_random','Amount (+/-)',1,default_value=(0,),min=0,max=0.99,min_is_strict=True,max_is_strict=True,help='Fractional variation around Base Scale, from 0 to 0.99. 0.25 gives 0.75 to 1.25 times Base Scale. Always positive.'),'{ scale_random_mode != 0 }')
    smin=hide(hou.FloatParmTemplate('scale_min','Minimum Multiplier',1,default_value=(0.8,),min=0.0001,max=5,min_is_strict=True,help='Smallest random multiplier applied to Base Scale (not a final size: per-prototype Scale, Non-Uniform and Bounds Scale multiply on top). If it is larger than the Maximum Multiplier the two are swapped.'),'{ scale_random_mode != 1 }')
    smax=hide(hou.FloatParmTemplate('scale_max','Maximum Multiplier',1,default_value=(1.2,),min=0.0001,max=5,min_is_strict=True,help='Largest random multiplier applied to Base Scale (not a final size: per-prototype Scale, Non-Uniform and Bounds Scale multiply on top).'),'{ scale_random_mode != 1 }')
    warn=hide(hou.LabelParmTemplate('scale_range_warn','',column_labels=('Minimum is larger than Maximum: the two are swapped.',)),'{ scale_random_mode != 1 } { scale_min <= scale_max }')
    nonuniform=hou.FloatParmTemplate('scale_nonuniform','Non-Uniform (0 = locked)',3,default_value=(0,0,0),min=0,max=0.99,min_is_strict=True,max_is_strict=True,help='Extra independent +/- variation per axis (a fraction, 0 to 0.99), on top of the uniform variation above. 0 on an axis locks that axis. For crates that vary in height only use (0, 0.3, 0). Per-prototype Scale in the Prototype Bank multiplies on top.')
    return hou.FolderParmTemplate('randomize','Randomize',folder_type=hou.folderType.Simple,parm_templates=(seed,position,keep,rotmode,euler,yaw,scalemode,amount,smin,smax,warn,nonuniform))

def physics_folder():
    """Physics Settle (v0.4.0): optional rigid-body settle of the distribution, simulated once (Simulate & Cache) and frozen."""
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    on=hou.ToggleParmTemplate('phys_on','Settle Instances',default_value=False,help='Off: Arraytron behaves exactly as without this folder. On: the distribution (Line, Area, Grid or Circle, with all Randomize and Prototype Bank settings) is the SPAWN state of a rigid-body simulation. Press Simulate & Cache; the settled positions and orientations replace the spawn state in the PointInstancer. While on, the Bounds Transform is applied to the points in world space (Scale moves the stones apart, it never stretches them) so the stones can meet world-space colliders; changing it needs a new Simulate & Cache.')
    status=hou.StringParmTemplate('phys_status','Status',1,default_value=('',),tags={'editor':'1','editorlines':'3-6'},help='Read only. Whether a cached simulation exists for the current settings, and how it ended.')
    status.setDefaultExpression(('hou.pwd().hdaModule().physics_status(hou.pwd())',));status.setDefaultExpressionLanguage((hou.scriptLanguage.Python,))
    status.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    spawn=hou.StringParmTemplate('phys_spawn','Spawn',1,default_value=('',),tags={'editor':'1','editorlines':'2-4'},help='Read only. The spawn region and the count are the Distribution settings (Line, Area, Grid or Circle); Randomize and the Prototype Bank apply to the spawn state as usual.')
    spawn.setDefaultExpression(('hou.pwd().hdaModule().spawn_text(hou.pwd())',));spawn.setDefaultExpressionLanguage((hou.scriptLanguage.Python,))
    spawn.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    bake=hou.ButtonParmTemplate('phys_bake','Simulate & Cache',help='Run the rigid-body simulation (Houdini Bullet) from the current spawn state until everything is at rest, then freeze the last frame in a cache file. The count, the spawn region and the shape of the pile come from the Distribution folder above (for example Area: Size and Count).')
    bake.setScriptCallback("n=kwargs['node']\ntry:\n    r=n.hdaModule().bake(n)\nexcept hou.OperationInterrupted:\n    print('Arraytron: simulation cancelled, nothing was cached')\nelse:\n    msg='Arraytron: %d stones, %d frames, %s, %.1fs' % (r['count'],r['frames'],'at rest' if r['settled'] else 'NOT at rest (%d stones still moving: raise Duration)' % r['active'],r['seconds'])\n    print(msg)\n    hou.ui.setStatusMessage(msg) if hou.isUIAvailable() else None")
    bake.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    clear=hou.ButtonParmTemplate('phys_clear','Clear Cache',help='Delete this node\'s cache files in the Cache Folder. The pile goes back to the unsettled spawn state until you simulate again.')
    clear.setScriptCallback("n=kwargs['node']\nprint('Arraytron: removed %d cache file(s)' % n.hdaModule().clear_cache(n))")
    clear.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    rev=hou.IntParmTemplate('phys_cache_rev','Cache Revision',1,default_value=(0,),help='Internal counter that makes the node recook after a simulation or Clear Cache.');rev.hide(True)
    def f(name,label,default,lo,hi,help,strict=False):
        return hou.FloatParmTemplate(name,label,1,default_value=(default,),min=lo,max=hi,min_is_strict=strict,help=help)
    templates=(
        on,status,spawn,bake,clear,
        f('phys_drop','Drop Height',0.3,0,20,'Height above the distribution plane where the lowest stones start, in scene units. The spawn region and the count are the Distribution settings; Position jitter in Y (Randomize) adds to this.'),
        hou.ToggleParmTemplate('phys_stack','Avoid Overlap At Spawn',default_value=True,help='Lift stones that would overlap another one at spawn just above it (bounding spheres, in a random but stable order), so the solver never starts with interpenetrating stones. Off: every stone starts at the drop height, which is only safe for sparse spawns.'),
        hou.IntParmTemplate('phys_seed','Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the spawn stacking order, i.e. which stones end up on top. Positions, rotations and scales still come from Randomize and the Distribution seeds.'),
        f('phys_gravity','Gravity',9.80665,0.01,100,'Acceleration along -Y in scene units per second squared (the scene is assumed to be in meters).',True),
        f('phys_density','Density',2600,10,20000,'Mass density of the stones in kg/m3. Only the ratio between differently sized stones matters for the pile shape; 2600 is granite.',True),
        f('phys_friction','Friction',0.9,0,2,'Friction of the stones. The ground and colliders are fixed at 1, so this is the combined value: 0.9 gives the stable, interlocked piles of loose stone; low values slide.'),
        f('phys_bounce','Bounce',0.1,0,1,'Restitution of the stones: 0 absorbs impacts, 1 is perfectly elastic. Gravel is dead, keep it low.'),
        f('phys_drag','Air Drag',5,0,100,'Slows falling stones the way air or a damp medium would: the fall speed levels off at about sqrt(Gravity / Air Drag) (1.4 m/s at the default, 0 is a vacuum). It calms the impacts, so the stones land where they were dropped and stack into a tighter pile instead of bouncing and scattering; it also makes the fall cheaper to simulate. Lower it for a violent, scattered pour.'),
        f('phys_duration','Maximum Sim Time (s)',10,0.1,60,'Longest time to simulate, in seconds at the scene frame rate. The simulation stops earlier once at most 2% of the stones still move more than 8% of a stone size (or 0.15 rad) per half second, three checks (0.75 s) in a row. If the time runs out first the status says how many stones were still moving.',True),
        menu('phys_quality','Collision Quality',('Draft','Standard','High'),default_value=1,help='Draft: hull proxies of at most 24 vertices, a wide collision margin (4% of the thinnest stone), coarse substeps and 4 solver iterations: about a third of the cost per frame, contacts a few percent of a stone loose: fast, small gaps and slight sinking are possible. Standard: 96 vertices. High: 256 vertices (the whole hull of nearly every stone), tiny margin, twice the substeps and iterations: slowest and the tightest contacts. Every proxy is the convex hull of the real prototype geometry at the stone\'s scale. Concave prototypes rest on their hull.'),
        hou.ToggleParmTemplate('phys_ground','Ground Plane',default_value=True,help='Infinite static ground plane at the Ground Height. Off: stones only meet the Collider Prims (and fall forever without any).'),
        f('phys_ground_height','Ground Height',0,-1000,1000,'World height (Y) of the ground plane.'),
        hou.StringParmTemplate('phys_colliders','Collider Prims',1,default_value=('',),help='Space separated prim path patterns (with * wildcards) of meshes in the incoming stream that the stones collide with, e.g. /World/Ground /World/Rocks*. They are used as static triangle meshes at their world transform. Prototype and output prims are skipped.'),
        hou.ToggleParmTemplate('phys_strict','Error If Not Simulated',default_value=False,help='Turn the node into an error (instead of showing the unsettled or stale pile with a warning) when there is no simulation for the current settings. Use it for farm and hand-off scenes so a missing cache can never render silently.'),
        hou.StringParmTemplate('phys_cachedir','Cache Folder',1,default_value=('$HIP/arraytron_cache',),string_type=hou.stringParmType.FileReference,file_type=hou.fileType.Directory,tags={'filechooser_mode':'write'},help='Folder for the frozen simulation results. The file name carries a fingerprint of everything that affects the result: only a file with the matching fingerprint is shown as settled. After a change of settings the newest older result of this node stays visible, marked STALE, until you simulate again. Ship this folder with the scene: it is not inside the HIP.'),
        rev)
    for template in templates:
        if template.name() not in ('phys_on','phys_status','phys_spawn','phys_cache_rev'):template.setConditional(hou.parmCondType.DisableWhen,'{ phys_on == 0 }')    # greyed out while the system is off
    return hou.FolderParmTemplate('physics','Physics Settle',folder_type=hou.folderType.Simple,parm_templates=templates)

def grow_templates():
    """Grow animation (v0.5.2): the parameters of the Animate tab (a list, not a folder)."""
    def menu(name,label,items,**kw):
        return hou.MenuParmTemplate(name,label,tuple(str(i) for i in range(len(items))),tuple(items),**kw)
    def hide(template,condition):
        template.setConditional(hou.parmCondType.HideWhen,condition);return template
    on=hou.ToggleParmTemplate('grow_on','Grow Animation',default_value=False,help='Off: nothing changes and the node does not depend on time. On: the instances are revealed over the timeline in a sweep across the layout: each one starts at a frame that depends on where it lies along the Direction and grows (or climbs out of the ground) over Grow Time frames. Instances that have not started yet are hidden (PointInstancer invisibleIds and a vanishing scale); finished ones are exactly the normal result. It animates the final (cached) transforms, so Physics Settle does not run again.')
    info=hou.StringParmTemplate('grow_info','Timing',1,default_value=('',),tags={'editor':'1','editorlines':'2-3'},help='Read only. When the first instance starts, when the last one is full size, and the current frame.')
    info.setDefaultExpression(('hou.pwd().hdaModule().grow_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ mode >= 0 }')
    start=hou.FloatParmTemplate('grow_start','Start Frame',1,default_value=(1,),min=-10000,max=100000,help='Frame at which the first instance starts to grow. New nodes start at the start of the playback range.')
    start.setDefaultExpression(('$FSTART',));start.setDefaultExpressionLanguage((hou.scriptLanguage.Hscript,))
    frame=hou.FloatParmTemplate('grow_frame','Frame',1,default_value=(1,),help='Internal: the current frame, which makes the node depend on time while Grow is on.');frame.setDefaultExpression(('$FF',));frame.setDefaultExpressionLanguage((hou.scriptLanguage.Hscript,));frame.hide(True)
    items=(on,info,
        menu('grow_direction','Sweep Direction',('Along X','Along Y (upward)','Along Z','Custom Vector','Outward From Centre','By Point Order'),help='Where the growth starts and where it ends. Along X: from the lowest X to the highest. Custom Vector: along the vector below. Outward From Centre: from the middle of the layout (distance in XZ). By Point Order: in id order, which follows a curve or a Line from its start to its end. The position of every instance along the sweep is measured once from its final position in the space of the generated points (before the Bounds Transform; world space with Physics Settle), so it never changes while the instances move.'),
        hide(hou.FloatParmTemplate('grow_vector','Custom Vector',3,default_value=(1,0,0),min=-1,max=1,help='Direction of the sweep. Only its direction matters.'),'{ grow_direction != 3 }'),
        hou.ToggleParmTemplate('grow_reverse','Reverse',default_value=False,help='Start at the other end of the sweep.'),
        start,
        hou.FloatParmTemplate('grow_sweep','Sweep Duration',1,default_value=(48,),min=0,max=10000,help='Frames the start of the growth takes to travel from the first instance to the last: the last instance starts this many frames after the first. 0 starts everything together.'),
        hou.FloatParmTemplate('grow_time','Grow Time',1,default_value=(12,),min=1,max=10000,help='Frames each instance takes to go from nothing to full size.'),
        hou.FloatParmTemplate('grow_delay','Random Delay',1,default_value=(0.0,),min=0,max=1,help='Adds a stable random extra delay to every instance, up to this fraction of Sweep Duration + Grow Time, so the wave front looks organic instead of a clean line.'),
        hide(hou.IntParmTemplate('grow_seed','Delay Seed',1,default_value=(1,),min=0,max=10000,min_is_strict=True,help='Seed of the random delay (keyed on the stable id).'),'{ grow_delay == 0 }'),
        menu('grow_style','Style',('Grow (scale up)','Plant (taller first, wider later)','Rise (climb out of the ground)'),help='Grow: the whole instance scales from nothing to full size about its origin. Plant: the height (Y scale) leads, finishing at 70% of the time, and the width (X and Z) follows from 20%. Rise: the instance keeps its size, starts Rise Distance below its final position and climbs up, scaling in over the first 30% of the time so it does not show under the surface. Instances grow about their prototype origin: author plants with the origin at the base.'),
        menu('grow_ease','Easing',('Linear','Smooth','Overshoot (pop)','Bounce'),default_value=1,help='How the growth speeds up and slows down. Overshoot pops slightly past full size and settles back; Bounce lands like a ball. Every curve ends exactly at the normal transform.'),
        hide(hou.FloatParmTemplate('grow_rise','Rise Distance',1,default_value=(0.5,),min=0,max=1000,help='How far below its final position a Rise instance starts, in scene units.'),'{ grow_style != 2 }'),
        frame)
    for template in items:
        if template.name() not in ('grow_on','grow_info','grow_frame'):
            cond=template.conditionals().get(hou.parmCondType.DisableWhen) if template.conditionals() else None
            template.setConditional(hou.parmCondType.DisableWhen,'{ grow_on == 0 }')
    return items

def ui_layout(g):
    """Regroup the flat parameter group into six workflow tabs: Source, Layout, Look, Spacing, Settle, Animate. Parameter NAMES, defaults and conditionals
    do not change (scenes, scripts and the viewport handle keep working); only containers, order and headings do. Mode panels become headings with
    the parameters directly beneath, shown by the same `mode` conditional, so no tab row changes under the artist's hands; specialist settings sit in
    collapsible '... Details' sections."""
    folders={e.name():e for e in g.entries()};count=[0]
    def uid(prefix):
        count[0]+=1;return 'ui_%s%d'%(prefix,count[0])
    def also_hide(template,condition):
        existing=template.conditionals().get(hou.parmCondType.HideWhen,'') if template.conditionals() else ''
        template.setConditional(hou.parmCondType.HideWhen,(existing+' '+condition).strip());return template
    def heading(title,condition=None):
        items=[hou.SeparatorParmTemplate(uid('sep')),hou.LabelParmTemplate(uid('head'),'',column_labels=(title,),is_label_hidden=True)]
        if condition:
            for item in items:also_hide(item,condition)
        return items
    def hint(text):return [hou.LabelParmTemplate(uid('hint'),'',column_labels=(text,),is_label_hidden=True)]
    def details(name,label,items,condition=None):
        folder=hou.FolderParmTemplate(name,label,folder_type=hou.folderType.Collapsible,parm_templates=tuple(items))
        if condition:folder.setConditional(hou.parmCondType.HideWhen,condition)
        return folder
    def tab(name,label,items):
        return hou.FolderParmTemplate(name,label,folder_type=hou.folderType.Tabs,parm_templates=tuple(items))
    def content(folder):return {t.name():t for t in folders[folder].parmTemplates()}
    def pick(folder,*names):
        c=content(folder);return [c[n] for n in names]
    # ---- Source
    src=content('source')
    source=hint('Choose what to scatter. Wire the scene (terrain, curve) into the first input, extra models into inputs 2 to 4.')+[src['protos'],src['proto_mode']]+([src['proto_percent']] if 'proto_percent' in src else [])+[src['proto_summary'],details('ui_selection','Selection Details',[src['proto_seed']]),
        *heading('OUTPUT'),src['outputpath']]
    # ---- Layout
    layout=hint('Choose how the points are laid out, then move the whole layout.')+list(folders['distribution'].parmTemplates())
    for index,(name,title) in enumerate((('line','LINE SETTINGS'),('area','AREA SETTINGS'),('grid','GRID SETTINGS'),('circle','CIRCLE SETTINGS'),('curve','CURVE SETTINGS'),('surface','SURFACE SETTINGS'),('paint','PAINT SETTINGS'),('cluster','CLUSTER SETTINGS'),('imported','IMPORTED POINTS'),('place','INSTANCE PLACE'),('biome','BIOME'))):
        if name not in folders:continue
        condition='{ mode != %d }'%index
        layout+=heading(title,condition)+[also_hide(t,condition) for t in folders[name].parmTemplates()]
    if 'rows' in folders:
        r=content('rows');rcond='{ mode != 0 mode != 3 mode != 4 }';layout+=heading('ROWS',rcond)+[also_hide(r[n],rcond) for n in ('rows_count','rows_spacing','rows_center','rows_random','rows_shift','rows_stagger','rows_seed','rows_info')]
    bounds=content('bounds')
    layout+=heading('MOVE THE LAYOUT')+pick('bounds','bound_t','bound_r','bound_s','bound_scale_instances')+[bounds['reset_bounds'],details('ui_pivot','Pivot & Guide',[bounds['bound_p'],bounds['show_bounds']])]
    if 'falloff' in folders:
        f=content('falloff');layout+=heading('FALLOFF')+[f[n] for n in ('fall_on','fall_region','fall_shape','fall_curve','fall_inner','fall_density','fall_scale')]+[details('ui_falloff','Falloff Details',[f[n] for n in ('fall_axes','fall_center_mode','fall_center','fall_radius_mode','fall_radius','fall_seed')],'{ fall_on == 0 }'),f['fall_info']]
    # ---- Look
    transform=content('transform');rnd=content('randomize')
    look=heading('INDIVIDUAL INSTANCES')+[transform['base_rotation'],transform['base_scale']]+heading('VARIATION')+[t for n,t in rnd.items() if n!='scale_nonuniform']+[details('ui_variation','Variation Details',[rnd['scale_nonuniform']])]
    if 'mask' in folders:
        m=content('mask');main=['mask_source','mask_effect','mask_noise_freq','mask_image','mask_prim','mask_primvar','mask_invert','mask_low','mask_high','mask_minscale','mask_seed','mask_info']
        detail=[n for n in m if n not in main]
        look+=heading('MASK')+[m[n] for n in main[:-1]]+[details('ui_mask','Mask Details',[m[n] for n in detail],'{ mask_source == 0 }'),m['mask_info']]
    if 'fieldstack' in folders:
        f=content('fieldstack');look+=heading('FIELD STACK')+[f['fields'],f['field_effect'],f['field_minscale'],f['field_seed'],f['field_info']]
    # ---- Spacing
    spacing=[]
    if 'overlap' in folders:
        o=content('overlap');hint_text='Keep instances apart from each other and out of geometry.'
        spacing=hint(hint_text)+heading('SEPARATION')+[o['overlap_mode'],o['overlap_priority'] if 'overlap_priority' in o else None,o['overlap_size'],o['overlap_radius'],o['overlap_tolerance'],o['overlap_axes'],
            details('ui_solver','Solver Settings',[o['overlap_iterations'],o['overlap_strength']],'{ overlap_mode != 2 }')]
        spacing=[t for t in spacing if t is not None]
        if 'avoid_mode' in o:spacing+=heading('AVOID GEOMETRY')+[o['avoid_mode'],o['avoid_prim'],o['avoid_margin'],o['avoid_axes'],o['avoid_iterations']]
        spacing+=[o['overlap_info']]
    # ---- Settle
    settle=[]
    if 'physics' in folders:
        p=content('physics')
        settle=hint('Let the instances fall into place with real physics, then freeze the result.')+pick('physics','phys_on','phys_status','phys_spawn','phys_bake','phys_drop','phys_stack','phys_seed','phys_duration','phys_quality')+[
            details('ui_forces','Material & Forces',pick('physics','phys_gravity','phys_density','phys_friction','phys_bounce','phys_drag')),
            details('ui_collision','Collision Settings',pick('physics','phys_ground','phys_ground_height','phys_colliders')),
            details('ui_cache','Cache Settings',pick('physics','phys_cachedir','phys_strict','phys_clear','phys_cache_rev'))]
    # ---- Animate
    animate=(hint('Reveal the instances over time: they grow or rise in a sweep across the layout.')+list(grow_templates())) if GROW else []
    optimize=[]
    if CAMERA:
        o2=content('optimize');optimize=hint('Hide or simplify instances by camera distance, and write extra data for shaders.')+heading('CAMERA')+[o2[n] for n in ('cam_on','cam_prim','cam_frustum','cam_margin','cam_behind','cam_behind_keep','cam_distcull','cam_maxdist','cam_densityon','cam_dnear','cam_dfar','cam_dmin','cam_seed')]
        optimize+=heading('LEVEL OF DETAIL')+[o2[n] for n in ('cam_lod','lod_by','lod_d1','lod_d2','lod_d3','lod_s1','lod_s2','lod_s3')]+[o2['cam_info'],o2['cam_frame']]
        if LODGEN:optimize+=heading('LOD GENERATOR')+[o2[n] for n in ('lodg_on','lodg_1','lodg_2','lodg_3','lodg_min','lodg_info')]
        optimize+=heading('PRIMVARS')+[o2[n] for n in ('pv_id','pv_proto','pv_random','pv_mask','pv_density','pv_cluster')+(('pv_biome',) if BIOME else ())+(('pv_srcid','pv_copy') if IMPORTED else ())+('pv_lod','pv_seed')]
    finish=[];export=[]
    if FINISH:
        f2=content('finish');finish=hint('Fix single instances by hand and look inside the result.' if NEWTABS else 'Fix single instances by hand, look inside the result, and write it out.')+heading('INSTANCE OVERRIDES')+([f2['ovr_pick']] if PICK else [])+[f2['overrides'],f2['ovr_info'],f2['ovr_clear']]
        finish+=heading('DEBUG')+[f2[n] for n in ('dbg_on','dbg_generated','dbg_rejected','dbg_color','dbg_axes','dbg_radius','dbg_centres','dbg_size')]
        if NEWTABS:export=hint('Write the result out and see what this node stores.')+heading('EXPORT USD')+[f2['export_path'],f2['export_usd']]+heading('CACHE')+[f2['cache_info']]
        else:finish+=heading('EXPORT AND CACHE')+[f2['export_path'],f2['export_usd'],f2['cache_info']]
    tabs=[tab('tab_source','Prototypes' if NEWTABS else 'Source',source),tab('tab_layout','Layout',layout),tab('tab_look','Variation' if NEWTABS else 'Look',look)]
    if spacing:tabs.append(tab('tab_spacing','Spacing',spacing))
    if settle:tabs.append(tab('tab_settle',PHYS_TAB,settle))
    if animate:tabs.append(tab('tab_animate','Animate',animate))
    if optimize:tabs.append(tab('tab_optimize','Optimize',optimize))
    if finish:tabs.append(tab('tab_finish','Debugging' if NEWTABS else 'Finish',finish))
    if export:tabs.append(tab('tab_export','Export',export))
    ng=hou.ParmTemplateGroup()
    for t in tabs:ng.append(t)
    return ng

def parms():
    g=base.parms(True,True)           # v0.21 layout: Line/Area/Grid, Bounds Transform with Scale Instances, Instance Transform, Randomize
    g.replace('source',source_folder())
    if VARIATION:g.replace('randomize',randomize_folder())
    if CIRCLE:
        g.replace('distribution',hou.FolderParmTemplate('distribution','Distribution',folder_type=hou.folderType.Simple,parm_templates=(
            hou.MenuParmTemplate('mode','Distribution Mode',('0','1','2','3'),('Line','Area','Grid / Matrix','Circle / Radial')),)))
        circle=circle_folder();circle.setConditional(hou.parmCondType.HideWhen,'{ mode != 3 }')
        g.insertAfter('grid',circle)
    if CURVE:
        names=['Line','Area','Grid / Matrix','Circle / Radial','Curve']+(['Surface'] if SURFACE else [])+(['Paint'] if PAINT else [])+(['Cluster'] if CLUSTER else [])+(['Imported Points'] if IMPORTED else [])+(['Instance Place'] if PLACE else [])+(['Biome'] if BIOME else [])
        g.replace('distribution',hou.FolderParmTemplate('distribution','Distribution',folder_type=hou.folderType.Simple,parm_templates=(
            hou.MenuParmTemplate('mode','Distribution Mode',tuple(str(i) for i in range(len(names))),tuple(names)),)))
        curve=curve_folder();curve.setConditional(hou.parmCondType.HideWhen,'{ mode != 4 }');g.insertAfter('circle',curve)
        if SURFACE:
            surface=surface_folder();surface.setConditional(hou.parmCondType.HideWhen,'{ mode != 5 }');g.insertAfter('curve',surface)
        if PAINT:
            paint=paint_folder();paint.setConditional(hou.parmCondType.HideWhen,'{ mode != 6 }');g.insertAfter('surface',paint)
        if CLUSTER:
            cluster=cluster_folder();cluster.setConditional(hou.parmCondType.HideWhen,'{ mode != 7 }');g.insertAfter('paint',cluster)
        if IMPORTED:
            imported=imported_folder();imported.setConditional(hou.parmCondType.HideWhen,'{ mode != 8 }');g.insertAfter('cluster',imported)
        if PLACE:
            place=place_folder();place.setConditional(hou.parmCondType.HideWhen,'{ mode != 9 }');g.insertAfter('imported',place)
        if BIOME:
            biome=biome_folder();biome.setConditional(hou.parmCondType.HideWhen,'{ mode != 10 }');g.insertAfter('place' if PLACE else 'imported',biome)
    if MASK:g.insertAfter('randomize',mask_folder())
    if FIELDS:g.insertAfter('mask',fields_folder())
    if OVERLAP:g.insertAfter('fieldstack' if FIELDS else 'mask',overlap_folder())
    if FALLOFF:g.append(falloff_folder())
    if ROWS:g.append(rows_folder())
    if PHYSICS:g.append(physics_folder())
    if CAMERA:g.append(optimize_folder())
    if FINISH:g.append(finish_folder())
    if UI:g=ui_layout(g)
    return g

def wrangle(parent,name,filename,run_over):
    n=parent.createNode('attribwrangle',name)
    n.parm('class').set(run_over)
    n.parm('snippet').set((VEX/filename).read_text())
    return n

def set_dialog_script(definition):
    """Input labels and the viewport handle binding live in the DialogScript."""
    section=definition.sections()['DialogScript']
    text=section.contents()
    for index,label in enumerate(INPUT_LABELS,1):
        text,count=re.subn(r'^\s*inputlabel\s+%d\s+.*$'%index,'    inputlabel\t%d\t"%s"'%(index,label),text,flags=re.M)
        assert count==1,('inputlabel',index)
    section.setContents(text)
    base.bind_viewport_handle(definition)

def add_viewer_state(definition):
    """Embed the Arraytron Paint Python Viewer State (the same sections Houdini's own Interactive tab writes)."""
    state='arraytron_paint_'+LABEL.replace('.','')
    code=(ROOT/'src/arraytron_paint_state.py').read_text().replace("STATE_NAME='arraytron_paint'","STATE_NAME=%r"%state)
    definition.addSection('ViewerStateModule',code);definition.addSection('DefaultState',state);definition.addSection('ViewerStateName.orig',state)
    definition.addSection('ViewerStateInstall',"__import__('viewerstate.utils', fromlist=[None]).register_pystate_embedded(kwargs['type'])")
    definition.addSection('ViewerStateUninstall',"__import__('viewerstate.utils', fromlist=[None]).unregister_pystate_embedded(kwargs['type'])")
    for name in ('ViewerStateModule','ViewerStateInstall','ViewerStateUninstall'):
        definition.setExtraFileOption(name+'/IsPython',True);definition.setExtraFileOption(name+'/IsScript',True)
    definition.setExtraFileOption('ViewerStateInstall/IsViewerState',True);definition.setExtraFileOption('ViewerStateUninstall/IsViewerState',True)
    definition.setExtraFileOption('ViewerStateName.orig/IsPython',True);definition.setExtraFileOption('ViewerStateName.orig/IsExpr',False)

def set_icon(definition):
    """Embed icon/Arraytron-Clean.svg in the HDA as the section Icon.svg and point the type's icon at it (opdef:), so the HDA needs no external file."""
    definition.addSection('Icon.svg',(ROOT/'icon'/'Arraytron-Clean.svg').read_text(encoding='utf8'))
    definition.setIcon('opdef:/'+definition.nodeType().nameWithCategory()+'?Icon.svg')

def module_text():
    text=(ROOT/'src/arraytron_module.py').read_text()
    if PHYSICS:text+='\n\n# ---- Physics Settle (src/arraytron_physics.py)\n'+(ROOT/'src/arraytron_physics.py').read_text()
    if CURVE:text+='\n\n# ---- Curve and Surface Scatter (src/arraytron_scatter.py)\n'+(ROOT/'src/arraytron_scatter.py').read_text()
    if MASK:text+='\n\n# ---- Mask pipeline (src/arraytron_mask.py)\n'+(ROOT/'src/arraytron_mask.py').read_text()
    if OVERLAP:text+='\n\n# ---- No Overlap (src/arraytron_overlap.py)\n'+(ROOT/'src/arraytron_overlap.py').read_text()
    if GROW:text+='\n\n# ---- Grow animation (src/arraytron_grow.py)\n'+(ROOT/'src/arraytron_grow.py').read_text()
    if PAINT:text+='\n\n# ---- Viewport brush (src/arraytron_paint.py)\n'+(ROOT/'src/arraytron_paint.py').read_text()
    if FIELDS:text+='\n\n# ---- Field Stack (src/arraytron_fields.py)\n'+(ROOT/'src/arraytron_fields.py').read_text()
    if FALLOFF:text+='\n\n# ---- Falloff (src/arraytron_falloff.py)\n'+(ROOT/'src/arraytron_falloff.py').read_text()
    if ROWS:text+='\n\n# ---- Rows (src/arraytron_rows.py)\n'+(ROOT/'src/arraytron_rows.py').read_text()
    if BIOME:text+='\n\n# ---- Biome (src/arraytron_biome.py)\n'+(ROOT/'src/arraytron_biome.py').read_text()
    if CLUSTER:text+='\n\n# ---- Clustering (src/arraytron_cluster.py)\n'+(ROOT/'src/arraytron_cluster.py').read_text()
    if CAMERA:text+='\n\n# ---- Camera, LOD and primvars (src/arraytron_camera.py)\n'+(ROOT/'src/arraytron_camera.py').read_text()
    if LODGEN:text+='\n\n# ---- LOD generator (src/arraytron_lodgen.py)\n'+(ROOT/'src/arraytron_lodgen.py').read_text()
    if H205:text+='\n\n# ---- Houdini 20.5 / 21 support (src/arraytron_h205.py)\n'+(ROOT/'src/arraytron_h205.py').read_text()
    if IMPORTED:text+='\n\n# ---- Imported points (src/arraytron_imported.py)\n'+(ROOT/'src/arraytron_imported.py').read_text()
    if FINISH:text+='\n\n# ---- Manual overrides (src/arraytron_overrides.py)\n'+(ROOT/'src/arraytron_overrides.py').read_text()+'\n\n# ---- Production finishing (src/arraytron_finish.py)\n'+(ROOT/'src/arraytron_finish.py').read_text()
    if PICK:text+='\n\n# ---- Pick Instance (src/arraytron_pick.py)\n'+(ROOT/'src/arraytron_pick.py').read_text()
    if PLACE:text+='\n\n# ---- Instance Place (src/arraytron_place.py)\n'+(ROOT/'src/arraytron_place.py').read_text()
    return text

def python_sop(parent,name,call):
    node=parent.createNode('python',name)
    node.parm('python').set('asset=hou.pwd().parent().parent()\nasset.hdaModule().%s(hou.pwd().geometry(),asset)\n'%call)
    return node

def physics_network(inst,assignment):
    """Insert the physics branch behind PROTOTYPE_ASSIGNMENT; returns the node that feeds OUT_POINTS."""
    world=wrangle(inst,'PHYSICS_WORLD','physics_world.vfl',2);world.setInput(0,assignment)
    spawn=python_sop(inst,'PHYSICS_SPAWN','sop_spawn');spawn.setInput(0,world)
    apply_=python_sop(inst,'PHYSICS_APPLY','sop_apply');apply_.setInput(0,spawn)
    switch=inst.createNode('switch','PHYSICS_SWITCH');switch.setInput(0,assignment);switch.setInput(1,apply_)
    switch.parm('input').setExpression('ch("../../phys_on")',hou.exprLanguage.Hscript)
    # simulation branch: only cooked by Simulate & Cache
    colliders=python_sop(inst,'PHYSICS_COLLIDERS','sop_colliders')
    proxies=python_sop(inst,'PHYSICS_PROXIES','sop_proxies');proxies.setInput(0,spawn)
    solver=inst.createNode('rbdbulletsolver','PHYSICS_SOLVER');solver.setInput(0,proxies);solver.setInput(3,colliders)
    plan=lambda name:'detail("../PHYSICS_PROXIES","plan_%s",0)'%name
    def expr(name,text):
        if solver.parm(name) is not None:solver.parm(name).setExpression(text,hou.exprLanguage.Hscript)        # ground_margin does not exist in Houdini 20.5 / 21
    solver.parm('startframe').set(1)
    expr('useground','ch("../../phys_ground")');expr('ground_posy','ch("../../phys_ground_height")')
    for name in ('margin','collision_margin','ground_margin'):expr(name,plan('margin'))
    expr('substeps','fit01(clamp(($F-1-%s)/12,0,1),%s,%s)'%(plan('fall_frames'),plan('substeps'),plan('substeps_late')))     # many substeps while the stones fall, fewer once the pile only shuffles
    expr('numiteration',plan('iters'))
    expr('density','ch("../../phys_density")');expr('friction','ch("../../phys_friction")');expr('bounce','ch("../../phys_bounce")')
    expr('gravityy','-ch("../../phys_gravity")')
    expr('adddrag','ch("../../phys_drag") > 0');expr('drag_airresist','ch("../../phys_drag")')
    for name in ('ground_friction','collision_friction','ground_bounce','collision_bounce'):solver.parm(name).set(1)
    solver.parm('collision_bullet_georep').set('concave')
    expr('bullet_linear_sleep_threshold',plan('vtol'));expr('bullet_angular_sleep_threshold',plan('wtol'))
    return switch

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
    # The Python module must exist before the network cooks, so package first and build inside the asset.
    asset=asset.createDigitalAsset(name=TYPE,hda_file_name=str(HDA),description='Arraytron',min_num_inputs=1,max_num_inputs=4)
    definition=asset.type().definition()
    definition.addSection('PythonModule',module_text())
    hou.hda.reloadFile(str(HDA))
    asset=hou.node('/stage/Arraytron');definition=asset.type().definition()
    asset.allowEditingOfContents()
    indirect=asset.indirectInputs()
    # --- SOURCE_RESOLVER side
    merge=asset.createNode('merge','merge_inputs')
    for k,node in enumerate(indirect[:4]):merge.setInput(k,node)
    previous=merge
    for k in range(SOP_SLOTS):
        stager=asset.createNode('sopimport','sop_stage_%d'%(k+1));stager.setInput(0,previous)
        stager.parm('soppath').setExpression('hou.pwd().parent().hdaModule().sop_slot(hou.pwd().parent(),%d)[1]'%k,hou.exprLanguage.Python)
        stager.parm('pathprefix').setExpression('(lambda m,a:(m.staged_path(a,m.sop_slot(a,%d)[0]) if m.sop_slot(a,%d)[0] else "/_arraytron_unused_%d"))(hou.pwd().parent().hdaModule(),hou.pwd().parent())'%(k,k,k),hou.exprLanguage.Python)
        previous=stager
    resolver=asset.createNode('pythonscript','SOURCE_RESOLVER');resolver.setInput(0,previous)
    resolver.parm('python').set((ROOT/'src/source_resolver.py').read_text())
    source=resolver
    if LODGEN:
        source=asset.createNode('pythonscript','LOD_GENERATOR');source.setInput(0,resolver);source.parm('python').set((ROOT/'src/lod_generate.py').read_text())
    # --- USD_COMPILER (native PointInstancer; SOP stages inside)
    if H205:
        # Houdini 20.5 / 21: the older instancer LOP. Prototypes come from the second input (PROTO_STAGE) at flat top-level paths, are picked per
        # point by the string attribute protopath, and PROTO_NORMALIZE restores the bank order afterwards (src/arraytron_h205.py explains why).
        proto_stage=asset.createNode('pythonscript','PROTO_STAGE');proto_stage.setInput(0,source);proto_stage.parm('python').set((ROOT/'src/proto_stage_h205.py').read_text())
        inst=asset.createNode('instancer','USD_COMPILER');inst.setInput(0,source);inst.setInput(1,proto_stage)
        inst.parm('primpath').setExpression('chs("../outputpath")',hou.exprLanguage.Hscript)
        inst.parm('method').set('pointinstancer');inst.parm('transformsourcemode').set('intsop')
        inst.parm('protosourcemode').set('second')
        inst.parm('protopattern').setExpression('" ".join(hou.pwd().parent().hdaModule().flat_paths(hou.pwd().parent()))',hou.exprLanguage.Python)
        inst.parm('protoreftype').set('prim');inst.parm('hideprotosourceprims').set(0)
        inst.parm('protoindexsrc').set('pathattr');inst.parm('pathattr').set('protopath')
        inst.parm('attribs').set('')
        if CAMERA:inst.parm('attribs').setExpression('hou.pwd().parent().hdaModule().primvar_attribs(hou.pwd().parent())',hou.exprLanguage.Python)
    else:
        inst=asset.createNode('pointinstancer','USD_COMPILER');inst.setInput(0,source)
        inst.parm('primpath').setExpression('chs("../outputpath")',hou.exprLanguage.Hscript)
        inst.parm('protosourcemode').set('first')
        inst.parm('protopattern').setExpression('hou.pwd().parent().hdaModule().pattern(hou.pwd().parent())',hou.exprLanguage.Python)
        inst.parm('createprotoarea').set(1);inst.parm('hideprotosourceprims').set(1)
        inst.parm('protodestrootprim').setExpression('chs("../outputpath") + "/Prototypes"',hou.exprLanguage.Hscript)
        inst.parm('protoreftype').set('prim')
        inst.parm('importsoppoints').set(1);inst.parm('sopsourcemode').set('intsop')
        inst.parm('newprotoindexsrc').set('intattr');inst.parm('newintattr').set('protoindex')
        inst.parm('updateinstancemode').set('overwrite');inst.parm('existingprototypemode').set('overwrite')
        inst.parm('existingprotoindexsrc').set('intattr');inst.parm('existingintattr').set('protoindex')
        inst.parm('attribs').set('')
        if CAMERA:inst.parm('attribs').setExpression('hou.pwd().parent().hdaModule().primvar_attribs(hou.pwd().parent())',hou.exprLanguage.Python)
        if GROW:inst.parm('importinvisids').setExpression('1 - ch("../grow_on")',hou.exprLanguage.Hscript)        # the importer writes an EMPTY invisibleIds that would hide the ones Grow lists; unchanged output while Grow is off
    for c in inst.children():c.destroy()
    generators=[wrangle(inst,'generate_line','line.vfl',0),wrangle(inst,'generate_area','area.vfl',0),wrangle(inst,'generate_grid','grid.vfl',0)]
    if CIRCLE:generators.append(wrangle(inst,'generate_circle','circle.vfl',0))
    if CURVE:generators.append(python_sop(inst,'generate_curve','sop_curve'))
    if SURFACE:generators.append(python_sop(inst,'generate_surface','sop_surface'))
    if PAINT:generators.append(python_sop(inst,'generate_paint','sop_paint'))
    if CLUSTER:generators.append(python_sop(inst,'generate_cluster','sop_cluster'))
    if IMPORTED:
        source=inst.createNode('object_merge','imported_source');source.parm('numobj').set(1);source.parm('objpath1').setExpression("(lambda a:a.evalParm('imp_sop') if a.evalParm('imp_source')==0 else '')(hou.pwd().parent().parent())",hou.exprLanguage.Python)
        imported_sop=python_sop(inst,'generate_imported','sop_imported');imported_sop.setInput(0,source);generators.append(imported_sop)
    if PLACE:generators.append(python_sop(inst,'generate_place','sop_place'))
    if BIOME:generators.append(python_sop(inst,'generate_biome','sop_biome'))
    switch=inst.createNode('switch','DISTRIBUTION_GENERATOR')
    for index,generator in enumerate(generators):switch.setInput(index,generator)
    switch.parm('input').setExpression('ch("../../mode")',hou.exprLanguage.Hscript)
    after=switch
    if ROWS:
        rows=python_sop(inst,'ROWS','sop_linerows');rows.setInput(0,switch);after=rows                      # Line / Circle / Curve: several rows (after the generator, before everything else)
    if MASK:
        mask_node=python_sop(inst,'MASK_PROCESSOR','sop_mask');mask_node.setInput(0,after);after=mask_node         # removes points / writes f@maskscale; ids of the survivors are untouched
    if FIELDS:
        stack=python_sop(inst,'FIELD_STACK','sop_fields');stack.setInput(0,after);after=stack         # after the Mask, before Variation: removes points / multiplies f@maskscale; ids of the survivors are untouched
    if FALLOFF:
        fall=python_sop(inst,'FALLOFF','sop_falloff');fall.setInput(0,after);after=fall                # after the Mask and the Field Stack, before Variation: removes points / multiplies f@maskscale; ids of the survivors are untouched
    variation=wrangle(inst,'VARIATION_PROCESSOR','transforms.vfl',2);variation.setInput(0,after)
    assignment=wrangle(inst,'PROTOTYPE_ASSIGNMENT','prototype_assignment.vfl',2);assignment.setInput(0,variation)
    if OVERLAP:
        overlap=python_sop(inst,'NO_OVERLAP','sop_overlap');overlap.setInput(0,assignment);assignment=overlap        # after the prototype is known: the sizes decide what overlaps
    feed=physics_network(inst,assignment) if PHYSICS else assignment
    if FINISH:
        ov=python_sop(inst,'OVERRIDES','sop_overrides');ov.setInput(0,feed);feed=ov                    # the Override Database: edits single instances by id, after everything that generates or places them
    if GROW:
        grow=python_sop(inst,'GROW','sop_grow');grow.setInput(0,feed);feed=grow                 # last: animates the final transforms by the timeline
    if CAMERA:
        pv=wrangle(inst,'PRIMVARS','primvars.vfl',2);pv.setInput(0,feed);feed=pv                  # last: the per-instance data the PointInstancer may copy to primvars
    if H205:
        pp=python_sop(inst,'PROTO_PATH','sop_protopath');pp.setInput(0,feed);feed=pp                  # last: the per-point prototype path the older instancer picks by
    out=inst.createNode('output','OUT_POINTS');out.setInput(0,feed);out.setDisplayFlag(True)
    compiled=inst
    if H205:
        compiled=asset.createNode('pythonscript','PROTO_NORMALIZE');compiled.setInput(0,inst);compiled.parm('python').set((ROOT/'src/proto_normalize.py').read_text())
    visibility=asset.createNode('configureprimitive','ensure_prototype_visible');visibility.setInput(0,compiled)
    visibility.parm('primpattern').setExpression('chs("../outputpath") + "/Prototypes/*"',hou.exprLanguage.Hscript)
    visibility.parm('setvisibility').set(1);visibility.parm('visibility').set('inherit')
    guide=asset.createNode('pythonscript','bounds_guide');guide.setInput(0,visibility)
    guide.parm('python').set((ROOT/'src'/GUIDE).read_text())
    layout=asset.createNode('xform','transform_distribution');layout.setInput(0,guide)
    layout.parm('setabsolutexform').set(1);layout.parm('xforminworldspace').set(1)
    layout.parm('primpattern').setExpression('chs("../outputpath")',hou.exprLanguage.Hscript)
    for tuple_name in 'trsp':
        for parm,axis in zip(layout.parmTuple(tuple_name),'xyz'):
            expression=f'ch("../bound_{tuple_name}{axis}")'
            if tuple_name=='s':expression=f'if(ch("../bound_scale_instances"), max(0.0001, {expression}), 1)'
            if PHYSICS:expression='if(ch("../phys_on"), %s, %s)'%('1' if tuple_name=='s' else '0',expression)    # Physics Settle bakes the Bounds Transform into the points
            parm.setExpression(expression,hou.exprLanguage.Hscript)
    last=layout
    if CAMERA:
        cam=asset.createNode('pythonscript','camera_optimize');cam.setInput(0,layout);cam.parm('python').set((ROOT/'src/camera_optimize.py').read_text());last=cam
    if FINISH:
        dbg=asset.createNode('pythonscript','debug_guide');dbg.setInput(0,last);dbg.parm('python').set((ROOT/'src/debug_guide.py').read_text());last=dbg
    out=asset.createNode('output','OUT_ARRAYTRON');out.setInput(0,last);out.setDisplayFlag(True)
    inst.layoutChildren();asset.layoutChildren()
    usd=asset.stage();errors=(asset.errors(),resolver.errors(),source.errors(),inst.errors(),guide.errors())
    pi=UsdGeom.PointInstancer(usd.GetPrimAtPath('/World/Arraytron')) if usd else None
    assert pi and len(pi.GetPositionsAttr().Get(hou.frame()))==10,errors
    assert usd.GetPrimAtPath('/World/Arraytron/Bounds_Guide/Bounds'),'bounds guide was not authored'
    definition.setParmTemplateGroup(parms())
    definition.addSection('OnCreated',"node=kwargs['node']\nif node.name().startswith('instancer'):\n    node.setName('arraytron1',unique_name=True)\n");definition.setExtraFileOption('OnCreated/IsPython',True)           # a new node is called arraytron1, not instancer1
    definition.addSection('ArraytronVersion',LABEL+(' Prototype Bank, Line/Area/Grid/Circle, Bounds Transform'+(', variation extras' if VARIATION else '')+(', Physics Settle' if PHYSICS else '')+(', Curve' if CURVE else '')+(', Surface Scatter' if SURFACE else '')+(', Mask' if MASK else '')+(', No Overlap' if OVERLAP else '')+(', Grow animation' if GROW else '') if CIRCLE else ' Prototype Bank, Line/Area/Grid, Bounds Transform'))
    definition.addSection('Help','<html><body><h1>Arraytron '+LABEL+'</h1><p>A Solaris instancer: it scatters USD prototypes with a native <b>UsdGeomPointInstancer</b>. Every instance has a <b>stable id</b>, so changing the look, weights or transform never reshuffles the layout.</p>'
        '<h2>Quick start</h2><ol><li>Wire your scene (terrain, curve, models) into the <b>first input</b>; extra models into inputs 2 to 4.</li><li><b>Prototypes</b>: fill the Prototype Bank (a prim path per model).</li><li><b>Layout</b>: pick a Distribution Mode (Line, Area, Grid, Circle, Curve, Surface, Paint, Cluster) and a count.</li><li><b>Variation</b>: switch Randomize on.</li></ol>'
        '<h2>The tabs</h2><ul><li><b>Prototypes</b> Prototype Bank, selection, LOD / proxy prims.</li><li><b>Layout</b> distribution, Move the Layout, painting.</li><li><b>Variation</b> variation, Mask, Field Stack.</li><li><b>Spacing</b> Separation and Avoid Geometry.</li><li><b>Settle</b> Physics Settle.</li><li><b>Animate</b> Grow.</li><li><b>Optimize</b> camera culling, LOD, primvars.</li><li><b>Debugging</b> instance overrides, debug views.</li><li><b>Export</b> USD export and what the node stores.</li></ul>'
        '<p>Documentation: docs/USER_GUIDE.md, docs/INDEX.md, docs/TROUBLESHOOTING.md and docs/CACHING_AND_PIPELINE.md next to the HDA project.</p></body></html>')
    definition.updateFromNode(asset);asset.matchCurrentDefinition()
    set_dialog_script(definition)
    if PAINT:add_viewer_state(definition)
    set_icon(definition)
    print(json.dumps({'hda':str(HDA),'type':TYPE,'errors':asset.errors()},indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('version',nargs='?',default=versions.CURRENT)
    configure(parser.parse_args().version)
    build()
